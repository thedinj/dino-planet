using System.Numerics;
using DinoPlanet.Core.Assets;
using DinoPlanet.Core.Data;
using DinoPlanet.Core.Spatial;

namespace DinoPlanet.Core.Sim;

/// <summary>
/// The whole game state and the rules that advance it. No rendering, no engine calls:
/// the view layer feeds in <see cref="Input"/>, calls <see cref="Tick"/>, then reads
/// <see cref="Entities"/> and <see cref="DrainEvents"/> to update what's on screen.
/// </summary>
public sealed class World
{
    private readonly Dictionary<EntityId, Entity> _entities = new();
    private readonly List<Entity> _order = new();
    private readonly List<WorldEvent> _events = new();
    private int _nextId = 1;

    public World(AssetRegistry assets, Tuning tuning, int seed)
    {
        Assets = assets;
        Tuning = tuning;
        Seed = seed;
        Rng = new Random(seed);
    }

    public AssetRegistry Assets { get; }

    /// <summary>Swappable at runtime for hot-reloading data/tuning.jsonc.</summary>
    public Tuning Tuning { get; set; }

    public int Seed { get; }
    public Random Rng { get; }

    /// <summary>Seconds of simulated time.</summary>
    public float Time { get; private set; }

    public PlayerIntent Input { get; set; } = PlayerIntent.None;

    /// <summary>Live entities in spawn order.</summary>
    public IReadOnlyList<Entity> Entities => _order;

    public Entity Get(EntityId id) =>
        _entities.TryGetValue(id, out var e) ? e : throw new KeyNotFoundException($"No entity {id}.");

    public bool TryGet(EntityId id, out Entity entity) => _entities.TryGetValue(id, out entity!);

    // ---- Spawning & attachment --------------------------------------------------

    public Entity Spawn(string assetId, Vector3 position, float yaw = 0f, Faction faction = Faction.Neutral,
        params IBehavior[] behaviors)
    {
        var asset = Assets.Get(assetId);
        var e = new Entity(new EntityId(_nextId++), asset, faction)
        {
            Position = position,
            Yaw = yaw,
        };

        if (asset.Kind is AssetKind.Dino or AssetKind.Rider)
        {
            e.MaxHealth = e.Health = Tuning.Mover(asset.Id).MaxHealth * Tuning.Scaling(faction).Health;
        }

        e.Behaviors.AddRange(behaviors);
        _entities.Add(e.Id, e);
        _order.Add(e);
        _events.Add(new Spawned(e.Id));
        return e;
    }

    /// <summary>Bolts <paramref name="child"/> onto a named socket of <paramref name="parent"/>.</summary>
    public void Attach(Entity parent, string socket, Entity child)
    {
        if (!parent.Asset.Sockets.ContainsKey(socket))
            throw new ArgumentException($"'{parent.Asset.Id}' has no socket '{socket}'.", nameof(socket));
        if (parent.AttachmentMap.ContainsKey(socket))
            throw new InvalidOperationException($"Socket '{socket}' on {parent} is already in use.");
        if (child.IsAttached)
            throw new InvalidOperationException($"{child} is already attached to something.");
        if (ReferenceEquals(parent, child) || IsAncestor(child, parent))
            throw new InvalidOperationException("Cannot attach an entity to itself or its own child.");

        parent.AttachmentMap[socket] = child.Id;
        child.Parent = parent.Id;
        child.ParentSocket = socket;
        child.Faction = parent.Faction;
        child.Velocity = Vector3.Zero;
        UpdateAttachedTransforms(parent);
    }

    /// <summary>Spawns an asset directly onto a socket. Handy for loadouts.</summary>
    public Entity SpawnAttached(Entity parent, string socket, string assetId, params IBehavior[] behaviors)
    {
        var child = Spawn(assetId, parent.Position, parent.Yaw, parent.Faction, behaviors);
        Attach(parent, socket, child);
        return child;
    }

    /// <summary>The top-most entity this one is attached to (itself if unattached).</summary>
    public Entity Root(Entity e)
    {
        while (e.Parent is { } p && _entities.TryGetValue(p, out var parent)) e = parent;
        return e;
    }

    /// <summary>A point given in an entity's local space (e.g. its "muzzle" socket), in world space.</summary>
    public Vector3 SocketWorldPosition(Entity e, string socket) =>
        e.Position + MathUtil.RotateY(e.Asset.SocketPosition(socket), e.Yaw);

    public void Despawn(Entity e)
    {
        if (!e.IsAlive) return;
        e.IsAlive = false;
        foreach (var childId in e.AttachmentMap.Values)
        {
            if (_entities.TryGetValue(childId, out var child)) Despawn(child);
        }
    }

    // ---- Combat -----------------------------------------------------------------

    public static bool AreHostile(Faction a, Faction b) =>
        a != b && a != Faction.Neutral && b != Faction.Neutral;

    public void Damage(Entity target, float amount)
    {
        if (!target.IsAlive || amount <= 0) return;
        target.Health = MathF.Max(0f, target.Health - amount);
        _events.Add(new Damaged(target.Id, amount, target.Health, target.Position));
        if (target.Health <= 0f)
        {
            _events.Add(new Died(target.Id, target.Position));
            Despawn(target);
        }
    }

    /// <summary>Fires a weapon entity: spawns its projectile at the "muzzle" socket (or its center).</summary>
    public Entity Fire(Entity weapon)
    {
        var stats = Tuning.Weapon(weapon.Asset.Id);
        var muzzle = weapon.Asset.Sockets.ContainsKey("muzzle")
            ? SocketWorldPosition(weapon, "muzzle")
            : weapon.Position;

        var bolt = Spawn(stats.Projectile, muzzle, weapon.Yaw, weapon.Faction,
            new Sim.Behaviors.Projectile(stats.Damage * Tuning.Scaling(weapon.Faction).Damage, stats.ProjectileSpeed, stats.Range / MathF.Max(0.01f, stats.ProjectileSpeed)));
        _events.Add(new Fired(weapon.Id, muzzle, weapon.Yaw));
        return bolt;
    }

    // ---- Queries ----------------------------------------------------------------

    /// <summary>Closest live, unattached entity within range that passes the filter.</summary>
    public Entity? Nearest(Vector3 from, float range, Func<Entity, bool> filter)
    {
        Entity? best = null;
        float bestDist = range;
        foreach (var e in _order)
        {
            if (!e.IsAlive || e.IsAttached || !filter(e)) continue;
            float d = MathUtil.DistanceXZ(from, e.Position);
            if (d <= bestDist)
            {
                bestDist = d;
                best = e;
            }
        }
        return best;
    }

    /// <summary>Closest dino hostile to <paramref name="faction"/> within range.</summary>
    public Entity? NearestHostileDino(Vector3 from, Faction faction, float range) =>
        Nearest(from, range, e => e.Asset.Kind == AssetKind.Dino && AreHostile(faction, e.Faction));

    // ---- Simulation -------------------------------------------------------------

    public void Tick(float dt)
    {
        if (dt <= 0f) return;
        Time += dt;

        // Snapshot: entities spawned during this tick start updating next tick.
        int count = _order.Count;
        for (int i = 0; i < count; i++)
        {
            var e = _order[i];
            if (!e.IsAlive) continue;
            e.Age += dt;
            e.ResetSteering();
            foreach (var b in e.Behaviors)
            {
                b.Update(e, this, dt);
                if (!e.IsAlive) break;
            }
        }

        for (int i = 0; i < _order.Count; i++)
        {
            var e = _order[i];
            if (!e.IsAlive || e.IsAttached) continue;
            ApplySteering(e, dt);
            e.Position += e.Velocity * dt;
        }

        foreach (var e in _order)
        {
            if (e.IsAlive && !e.IsAttached) UpdateAttachedTransforms(e);
        }

        RemoveDead();
    }

    /// <summary>Hands this tick's events to the caller and clears them.</summary>
    public IReadOnlyList<WorldEvent> DrainEvents()
    {
        var copy = _events.ToArray();
        _events.Clear();
        return copy;
    }

    private void ApplySteering(Entity e, float dt)
    {
        // Only walkers steer. Projectiles and props manage their own velocity.
        if (e.Asset.Kind is not (AssetKind.Dino or AssetKind.Rider)) return;

        var stats = Tuning.Mover(e.Asset.Id);
        if (e.Steering is not { } s || s.Direction.LengthSquared() < 1e-6f || s.Throttle <= 0f)
        {
            e.Velocity = Vector3.Zero;
            return;
        }

        var dir = Vector3.Normalize(new Vector3(s.Direction.X, 0f, s.Direction.Z));
        float targetYaw = MathUtil.YawFromDirection(dir);
        e.Yaw = MathUtil.TurnToward(e.Yaw, targetYaw, MathUtil.DegToRad(stats.TurnRateDegrees) * dt);

        // Creatures move the way they face, slowing while they turn hard.
        float alignment = MathF.Max(0.25f, MathF.Cos(MathUtil.WrapAngle(targetYaw - e.Yaw)));
        e.Velocity = MathUtil.Forward(e.Yaw) * stats.MoveSpeed * MathF.Min(1f, s.Throttle) * alignment;
    }

    private void UpdateAttachedTransforms(Entity parent)
    {
        foreach (var (socket, childId) in parent.AttachmentMap)
        {
            if (!_entities.TryGetValue(childId, out var child) || !child.IsAlive) continue;
            var def = parent.Asset.Sockets[socket];
            child.Position = SocketWorldPosition(parent, socket);
            child.Yaw = MathUtil.WrapAngle(parent.Yaw + MathUtil.DegToRad(def.YawDegrees) + child.LocalYaw);
            UpdateAttachedTransforms(child);
        }
    }

    private void RemoveDead()
    {
        for (int i = _order.Count - 1; i >= 0; i--)
        {
            var e = _order[i];
            if (e.IsAlive) continue;

            if (e.Parent is { } pid && _entities.TryGetValue(pid, out var parent) && e.ParentSocket is { } sock)
                parent.AttachmentMap.Remove(sock);

            _order.RemoveAt(i);
            _entities.Remove(e.Id);
            _events.Add(new Despawned(e.Id));
        }
    }

    private bool IsAncestor(Entity candidate, Entity of)
    {
        var e = of;
        while (e.Parent is { } p && _entities.TryGetValue(p, out var parent))
        {
            if (ReferenceEquals(parent, candidate)) return true;
            e = parent;
        }
        return false;
    }
}
