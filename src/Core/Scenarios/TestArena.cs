using System.Numerics;
using DinoPlanet.Core.Procgen;
using DinoPlanet.Core.Sim;
using DinoPlanet.Core.Sim.Behaviors;

namespace DinoPlanet.Core.Scenarios;

/// <summary>
/// The first playable setup: the player's raptor with a rider and a cannon, a few enemy raptors,
/// one enemy T-rex with twin guns, and a scattered jungle. Lives in Core so it can be tested.
/// </summary>
public static class TestArena
{
    public const float HalfSize = 40f;

    public sealed record Result(Entity Player);

    public static Result Build(World world)
    {
        // Jungle props first, keeping a clearing around the player's start.
        var props = Scatter.Generate(
            world.Seed,
            HalfSize,
            new[] { new ScatterLayer("tree", 3f), new ScatterLayer("rock", 1f) },
            minSpacing: 4.5f,
            keepOut: p => p.Length() < 9f);
        foreach (var p in props)
        {
            world.Spawn(p.AssetId, p.Position, p.Yaw);
        }

        // Player.
        var player = world.Spawn("raptor", Vector3.Zero, 0f, Faction.Player, new PlayerControlled());
        world.SpawnAttached(player, "saddle", "rider");
        world.SpawnAttached(player, "turret", "laser_cannon", new TurretAim(triggerFromPlayer: true));

        // Enemy raptors in a loose ring.
        for (int i = 0; i < 3; i++)
        {
            float angle = MathF.PI * 2f * i / 3f + (float)world.Rng.NextDouble();
            var pos = new Vector3(MathF.Cos(angle), 0f, MathF.Sin(angle)) * 22f;
            var raptor = world.Spawn("raptor", pos, angle, Faction.Enemy,
                new ChaseNearestHostile(sightRange: 20f, stopDistance: 8f), new Wander(radius: 8f));
            world.SpawnAttached(raptor, "turret", "laser_cannon", new TurretAim());
        }

        // The big one.
        var trex = world.Spawn("trex", new Vector3(0f, 0f, -32f), 0f, Faction.Enemy,
            new ChaseNearestHostile(sightRange: 26f, stopDistance: 10f), new Wander(radius: 6f, throttle: 0.25f));
        world.SpawnAttached(trex, "saddle", "rider");
        world.SpawnAttached(trex, "turret_left", "laser_cannon", new TurretAim(maxSwivelDegrees: 100f));
        world.SpawnAttached(trex, "turret_right", "laser_cannon", new TurretAim(maxSwivelDegrees: 100f));

        return new Result(player);
    }
}
