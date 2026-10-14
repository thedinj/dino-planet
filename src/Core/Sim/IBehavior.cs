namespace DinoPlanet.Core.Sim;

/// <summary>
/// A small piece of logic attached to an entity. Entities get their personality by stacking
/// behaviors: an enemy raptor might be [ChaseNearestHostile, Wander], a turret [TurretAim].
/// Behaviors run in list order every tick, so earlier ones get first claim on steering.
/// </summary>
public interface IBehavior
{
    void Update(Entity self, World world, float dt);
}
