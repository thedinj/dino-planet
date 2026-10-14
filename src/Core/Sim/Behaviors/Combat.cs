using DinoPlanet.Core.Assets;
using DinoPlanet.Core.Spatial;

namespace DinoPlanet.Core.Sim.Behaviors;

/// <summary>
/// For a weapon attached to a socket: swivels toward the nearest hostile dino in range and fires
/// when lined up. With <see cref="TriggerFromPlayer"/> it still auto-aims but only shoots while
/// the player holds fire.
/// </summary>
public sealed class TurretAim : IBehavior
{
    private float _cooldown;

    public TurretAim(bool triggerFromPlayer = false, float fireConeDegrees = 12f, float maxSwivelDegrees = 180f)
    {
        TriggerFromPlayer = triggerFromPlayer;
        FireConeDegrees = fireConeDegrees;
        MaxSwivelDegrees = maxSwivelDegrees;
    }

    public bool TriggerFromPlayer { get; set; }
    public float FireConeDegrees { get; set; }

    /// <summary>How far the turret may turn from its mount's facing, each way. 180 = full circle.</summary>
    public float MaxSwivelDegrees { get; set; }

    public EntityId? Target { get; private set; }

    public void Update(Entity self, World world, float dt)
    {
        var stats = world.Tuning.Weapon(self.Asset.Id);
        _cooldown -= dt;

        var target = world.NearestHostileDino(self.Position, self.Faction, stats.Range);
        Target = target?.Id;

        // Aim: work out the local yaw that would face the target (or straight ahead if none).
        float mountYaw = MathUtil.WrapAngle(self.Yaw - self.LocalYaw);
        float desiredLocal = 0f;
        if (target is not null)
        {
            float worldYaw = MathUtil.YawFromDirection(target.Position - self.Position);
            float limit = MathUtil.DegToRad(MaxSwivelDegrees);
            desiredLocal = Math.Clamp(MathUtil.WrapAngle(worldYaw - mountYaw), -limit, limit);
        }

        self.LocalYaw = MathUtil.TurnToward(self.LocalYaw, desiredLocal,
            MathUtil.DegToRad(stats.TurnRateDegrees) * dt);

        bool wantsToFire = TriggerFromPlayer ? world.Input.Fire : target is not null;
        if (!wantsToFire || _cooldown > 0f) return;

        // Player weapons shoot straight ahead when nothing is in range; AI only fires when aimed.
        bool aimed = target is null
            || MathF.Abs(MathUtil.WrapAngle(desiredLocal - self.LocalYaw)) <= MathUtil.DegToRad(FireConeDegrees);
        if (!aimed) return;

        // The turret's world yaw is updated after behaviors run; use the freshly turned local yaw.
        self.Yaw = MathUtil.WrapAngle(mountYaw + self.LocalYaw);
        world.Fire(self);
        _cooldown = stats.Cooldown / MathF.Max(0.05f, world.Tuning.Scaling(self.Faction).FireRate);
    }
}

/// <summary>Flies straight, damages the first hostile dino or rider it touches, expires after a while.</summary>
public sealed class Projectile : IBehavior
{
    public Projectile(float damage, float speed, float lifetime, float radius = 0.2f)
    {
        Damage = damage;
        Speed = speed;
        Lifetime = lifetime;
        Radius = radius;
    }

    public float Damage { get; }
    public float Speed { get; }
    public float Lifetime { get; }
    public float Radius { get; }

    public void Update(Entity self, World world, float dt)
    {
        self.Velocity = MathUtil.Forward(self.Yaw) * Speed;

        if (self.Age >= Lifetime)
        {
            world.Despawn(self);
            return;
        }

        // Sweep the segment this bolt covers this tick so fast bolts can't skip through targets.
        var start = self.Position;
        var end = self.Position + self.Velocity * dt;
        foreach (var e in world.Entities)
        {
            if (!e.IsAlive || e.IsAttached) continue;
            if (e.Asset.Kind is not (AssetKind.Dino or AssetKind.Rider)) continue;
            if (!World.AreHostile(self.Faction, e.Faction)) continue;

            float reach = e.Asset.Collider.Radius * e.Asset.Scale + Radius;
            if (DistanceToSegmentXZ(e.Position, start, end) <= reach)
            {
                world.Damage(e, Damage);
                world.Despawn(self);
                return;
            }
        }
    }

    private static float DistanceToSegmentXZ(System.Numerics.Vector3 p, System.Numerics.Vector3 a, System.Numerics.Vector3 b)
    {
        float abx = b.X - a.X, abz = b.Z - a.Z;
        float lenSq = abx * abx + abz * abz;
        float t = lenSq > 1e-8f ? Math.Clamp(((p.X - a.X) * abx + (p.Z - a.Z) * abz) / lenSq, 0f, 1f) : 0f;
        float cx = a.X + abx * t - p.X, cz = a.Z + abz * t - p.Z;
        return MathF.Sqrt(cx * cx + cz * cz);
    }
}
