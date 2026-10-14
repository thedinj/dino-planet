using System.Numerics;

namespace DinoPlanet.Core.Sim;

/// <summary>
/// Things that happened during a tick that the view layer may want to show or play a sound for.
/// Core never calls into the view; the view drains these after each tick.
/// </summary>
public abstract record WorldEvent;

public sealed record Spawned(EntityId Entity) : WorldEvent;

public sealed record Despawned(EntityId Entity) : WorldEvent;

public sealed record Fired(EntityId Weapon, Vector3 Muzzle, float Yaw) : WorldEvent;

public sealed record Damaged(EntityId Target, float Amount, float HealthLeft, Vector3 At) : WorldEvent;

public sealed record Died(EntityId Entity, Vector3 At) : WorldEvent;
