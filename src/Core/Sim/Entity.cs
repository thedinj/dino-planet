using System.Numerics;
using DinoPlanet.Core.Assets;

namespace DinoPlanet.Core.Sim;

public readonly record struct EntityId(int Value)
{
    public override string ToString() => $"#{Value}";
}

public enum Faction
{
    Neutral,
    Player,
    Enemy,
}

/// <summary>
/// Anything in the world: a dino, a gun bolted to it, its rider, a laser bolt, a rock.
/// Entities are plain data plus a list of behaviors; the view layer mirrors them as Godot nodes.
/// </summary>
public sealed class Entity
{
    internal Entity(EntityId id, AssetDef asset, Faction faction)
    {
        Id = id;
        Asset = asset;
        Faction = faction;
    }

    public EntityId Id { get; }
    public AssetDef Asset { get; }
    public Faction Faction { get; internal set; }

    /// <summary>World position. For attached entities this is computed from the parent each tick.</summary>
    public Vector3 Position { get; set; }

    /// <summary>World yaw in radians (Godot convention: 0 faces -Z).</summary>
    public float Yaw { get; set; }

    public Vector3 Velocity { get; set; }

    public float Health { get; set; } = 1f;
    public float MaxHealth { get; set; } = 1f;

    /// <summary>Seconds since spawn.</summary>
    public float Age { get; internal set; }

    public bool IsAlive { get; internal set; } = true;

    // ---- Attachment -------------------------------------------------------------

    public EntityId? Parent { get; internal set; }
    public string? ParentSocket { get; internal set; }

    /// <summary>Yaw relative to the socket, e.g. a turret swiveling on its mount.</summary>
    public float LocalYaw { get; set; }

    internal Dictionary<string, EntityId> AttachmentMap { get; } = new();
    public IReadOnlyDictionary<string, EntityId> Attachments => AttachmentMap;

    public bool IsAttached => Parent.HasValue;

    // ---- Behavior ---------------------------------------------------------------

    public List<IBehavior> Behaviors { get; } = new();

    public T? GetBehavior<T>() where T : class, IBehavior => Behaviors.OfType<T>().FirstOrDefault();

    /// <summary>
    /// Desired movement for this tick. The first behavior that sets it wins, so behaviors listed
    /// earlier have priority (e.g. Chase before Wander). Reset by the world every tick.
    /// </summary>
    public SteeringRequest? Steering { get; private set; }

    /// <summary>Claims movement for this tick. Returns false if a higher-priority behavior already did.</summary>
    public bool TrySteer(SteeringRequest request)
    {
        if (Steering.HasValue) return false;
        Steering = request;
        return true;
    }

    public bool HasSteering => Steering.HasValue;

    internal void ResetSteering() => Steering = null;

    public override string ToString() => $"{Asset.Id}{Id}";
}

/// <summary>Where an entity wants to go this tick: a ground-plane direction and a 0..1 throttle.</summary>
public readonly record struct SteeringRequest(Vector3 Direction, float Throttle = 1f);
