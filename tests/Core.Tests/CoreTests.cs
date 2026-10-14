using System.Numerics;
using DinoPlanet.Core.Assets;
using DinoPlanet.Core.Data;
using DinoPlanet.Core.Procgen;
using DinoPlanet.Core.Scenarios;
using DinoPlanet.Core.Sim;
using DinoPlanet.Core.Sim.Behaviors;
using DinoPlanet.Core.Spatial;
using Xunit;

namespace DinoPlanet.Core.Tests;

public class MathTests
{
    [Fact]
    public void Yaw_zero_faces_negative_z_like_godot()
    {
        var f = MathUtil.Forward(0f);
        Assert.Equal(0f, f.X, 4);
        Assert.Equal(-1f, f.Z, 4);
    }

    [Fact]
    public void Positive_yaw_turns_left_like_godot()
    {
        // In Godot, rotating +90 degrees about Y turns a -Z facing node to face -X.
        var f = MathUtil.Forward(MathF.PI / 2f);
        Assert.Equal(-1f, f.X, 4);
        Assert.Equal(0f, f.Z, 4);
    }

    [Theory]
    [InlineData(1f, 0f, 0f)]
    [InlineData(0f, 0f, 1f)]
    [InlineData(-0.6f, 0f, -0.8f)]
    public void YawFromDirection_round_trips_with_Forward(float x, float y, float z)
    {
        var dir = Vector3.Normalize(new Vector3(x, y, z));
        var back = MathUtil.Forward(MathUtil.YawFromDirection(dir));
        Assert.Equal(dir.X, back.X, 4);
        Assert.Equal(dir.Z, back.Z, 4);
    }

    [Fact]
    public void TurnToward_takes_the_short_way_and_respects_the_limit()
    {
        float result = MathUtil.TurnToward(MathUtil.DegToRad(170), MathUtil.DegToRad(-170), MathUtil.DegToRad(5));
        Assert.Equal(MathUtil.DegToRad(175), result, 4);
    }
}

public class DataTests
{
    [Fact]
    public void Game_asset_registry_loads()
    {
        var registry = AssetRegistry.FromJson(TestWorlds.DataFile("assets.jsonc"));
        Assert.Contains(registry.All, a => a.Id == "raptor" && a.Kind == AssetKind.Dino);
        Assert.True(registry.Get("raptor").Sockets.ContainsKey("turret"));
    }

    [Fact]
    public void Game_tuning_loads_and_lookups_ignore_case()
    {
        var tuning = Tuning.FromJson(TestWorlds.DataFile("tuning.jsonc"));
        Assert.True(tuning.Mover("RAPTOR").MoveSpeed > 0);
        Assert.True(tuning.Weapon("laser_cannon").Damage > 0);
    }

    [Fact]
    public void Every_weapon_projectile_exists_in_the_registry()
    {
        var registry = AssetRegistry.FromJson(TestWorlds.DataFile("assets.jsonc"));
        var tuning = Tuning.FromJson(TestWorlds.DataFile("tuning.jsonc"));
        foreach (var (weaponId, stats) in tuning.Weapons)
        {
            Assert.True(registry.TryGet(weaponId, out _), $"Tuning has weapon '{weaponId}' that isn't in the registry.");
            Assert.True(registry.TryGet(stats.Projectile, out _), $"Weapon '{weaponId}' fires unknown '{stats.Projectile}'.");
        }
    }

    [Fact]
    public void Duplicate_asset_ids_are_rejected()
    {
        var json = """{ "assets": [ { "id": "a", "kind": "prop" }, { "id": "A", "kind": "prop" } ] }""";
        Assert.Throws<InvalidDataException>(() => AssetRegistry.FromJson(json));
    }

    [Fact]
    public void Vectors_must_have_three_numbers()
    {
        var json = """{ "assets": [ { "id": "a", "kind": "prop", "sockets": { "s": { "position": [1, 2] } } } ] }""";
        Assert.ThrowsAny<System.Text.Json.JsonException>(() => AssetRegistry.FromJson(json));
    }
}

public class AttachmentTests
{
    [Fact]
    public void Attached_entity_follows_parent_socket_through_rotation()
    {
        var world = TestWorlds.World();
        var dino = world.Spawn("dino", new Vector3(10, 0, 0));
        var gun = world.SpawnAttached(dino, "side", "gun");

        dino.Yaw = MathF.PI / 2f; // face -X
        world.Tick(0.016f);

        // Socket is +X in local space; after +90 yaw local +X maps to world -Z.
        Assert.Equal(10f, gun.Position.X, 3);
        Assert.Equal(1f, gun.Position.Y, 3);
        Assert.Equal(-1f, gun.Position.Z, 3);
        // Socket yaw -90 + parent yaw +90 = facing forward of world 0.
        Assert.Equal(0f, gun.Yaw, 3);
    }

    [Fact]
    public void Attaching_inherits_faction_and_rejects_bad_sockets()
    {
        var world = TestWorlds.World();
        var dino = world.Spawn("dino", Vector3.Zero, faction: Faction.Enemy);
        var gun = world.SpawnAttached(dino, "turret", "gun");
        Assert.Equal(Faction.Enemy, gun.Faction);
        Assert.Throws<ArgumentException>(() => world.SpawnAttached(dino, "nope", "gun"));
        Assert.Throws<InvalidOperationException>(() => world.Attach(dino, "turret", world.Spawn("gun", Vector3.Zero)));
    }

    [Fact]
    public void Killing_a_dino_removes_everything_bolted_to_it()
    {
        var world = TestWorlds.World();
        var dino = world.Spawn("dino", Vector3.Zero, faction: Faction.Enemy);
        var gun = world.SpawnAttached(dino, "turret", "gun");
        world.Damage(dino, 1000f);
        world.Tick(0.016f);
        Assert.False(world.TryGet(dino.Id, out _));
        Assert.False(world.TryGet(gun.Id, out _));
        var events = world.DrainEvents();
        Assert.Contains(events, e => e is Died d && d.Entity == dino.Id);
        Assert.Contains(events, e => e is Despawned d && d.Entity == gun.Id);
    }
}

public class BehaviorTests
{
    [Fact]
    public void Earlier_behaviors_win_steering()
    {
        var world = TestWorlds.World();
        world.Spawn("dino", new Vector3(0, 0, -15), faction: Faction.Player);
        var hunter = world.Spawn("dino", Vector3.Zero, MathF.PI, Faction.Enemy,
            new ChaseNearestHostile(sightRange: 30f, stopDistance: 2f), new Wander());

        TestWorlds.Run(world, 1f);

        // It should have moved toward the target (-Z), not wandered randomly.
        Assert.True(hunter.Position.Z < -2f, $"Hunter at {hunter.Position} should have closed in.");
    }

    [Fact]
    public void Player_input_moves_the_player()
    {
        var world = TestWorlds.World();
        var player = world.Spawn("dino", Vector3.Zero, 0f, Faction.Player, new PlayerControlled());
        world.Input = new PlayerIntent(new Vector2(1f, 0f), false);
        TestWorlds.Run(world, 1f);
        Assert.True(player.Position.X > 2f);
    }

    [Fact]
    public void Turret_aims_fires_and_the_bolt_hurts_the_target()
    {
        var world = TestWorlds.World();
        var shooter = world.Spawn("dino", Vector3.Zero, 0f, Faction.Player);
        world.SpawnAttached(shooter, "turret", "gun", new TurretAim());
        var target = world.Spawn("dino", new Vector3(8, 0, 0), 0f, Faction.Enemy); // off to the side

        TestWorlds.Run(world, 1.2f);

        Assert.True(target.Health < 30f, $"Target health {target.Health} should have dropped.");
    }

    [Fact]
    public void Player_turret_only_fires_while_trigger_held()
    {
        var world = TestWorlds.World();
        var shooter = world.Spawn("dino", Vector3.Zero, 0f, Faction.Player);
        world.SpawnAttached(shooter, "turret", "gun", new TurretAim(triggerFromPlayer: true));
        var target = world.Spawn("dino", new Vector3(0, 0, -8), 0f, Faction.Enemy);

        TestWorlds.Run(world, 1f);
        Assert.Equal(30f, target.Health);

        world.Input = new PlayerIntent(Vector2.Zero, true);
        TestWorlds.Run(world, 1f);
        Assert.True(target.Health < 30f);
    }

    [Fact]
    public void Same_seed_same_outcome()
    {
        static string RunOnce()
        {
            var world = TestWorlds.World(seed: 42);
            for (int i = 0; i < 4; i++)
                world.Spawn("dino", new Vector3(i * 3, 0, 0), 0f, Faction.Enemy, new Wander(radius: 5f));
            TestWorlds.Run(world, 5f);
            return string.Join("|", world.Entities.Select(e => $"{e.Position.X:F3},{e.Position.Z:F3}"));
        }

        Assert.Equal(RunOnce(), RunOnce());
    }
}

public class ProcgenTests
{
    private static readonly ScatterLayer[] Layers = { new("tree", 3f), new("rock", 1f) };

    [Fact]
    public void Scatter_is_deterministic_per_seed()
    {
        var a = Scatter.Generate(7, 30f, Layers, 4f);
        var b = Scatter.Generate(7, 30f, Layers, 4f);
        var c = Scatter.Generate(8, 30f, Layers, 4f);
        Assert.Equal(a, b);
        Assert.NotEqual(a, c);
    }

    [Fact]
    public void Scatter_respects_spacing_bounds_and_keep_out()
    {
        var points = Scatter.Generate(3, 30f, Layers, 4f, keepOut: p => p.Length() < 8f);
        Assert.True(points.Count > 50);
        foreach (var p in points)
        {
            Assert.InRange(p.Position.X, -30f, 30f);
            Assert.InRange(p.Position.Z, -30f, 30f);
            Assert.True(new Vector2(p.Position.X, p.Position.Z).Length() >= 8f);
        }
        for (int i = 0; i < points.Count; i++)
        for (int j = i + 1; j < points.Count; j++)
            Assert.True(Vector3.Distance(points[i].Position, points[j].Position) >= 4f - 1e-3f);
    }
}

public class ScenarioTests
{
    [Fact]
    public void Test_arena_builds_and_runs_with_the_real_data()
    {
        var registry = AssetRegistry.FromJson(TestWorlds.DataFile("assets.jsonc"));
        var tuning = Tuning.FromJson(TestWorlds.DataFile("tuning.jsonc"));
        var world = new World(registry, tuning, seed: 1);

        var arena = TestArena.Build(world);
        Assert.Equal(Faction.Player, arena.Player.Faction);
        Assert.Equal(2, arena.Player.Attachments.Count);

        TestWorlds.Run(world, 20f);
        Assert.Contains(world.DrainEvents(), e => e is Fired);
    }
}
