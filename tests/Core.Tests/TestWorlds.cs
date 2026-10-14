using System.Numerics;
using DinoPlanet.Core.Assets;
using DinoPlanet.Core.Data;
using DinoPlanet.Core.Sim;

namespace DinoPlanet.Core.Tests;

/// <summary>Small hand-built registries and worlds so tests don't depend on the game's data files.</summary>
public static class TestWorlds
{
    public static AssetRegistry Registry() => new(new[]
    {
        new AssetDef
        {
            Id = "dino",
            Kind = AssetKind.Dino,
            Collider = new ColliderDef { Radius = 0.5f, Height = 1f },
            Sockets = new()
            {
                ["turret"] = new SocketDef { Position = new Vector3(0, 1, 0) },
                ["side"] = new SocketDef { Position = new Vector3(1, 1, 0), YawDegrees = -90 },
            },
        },
        new AssetDef
        {
            Id = "gun",
            Kind = AssetKind.Weapon,
            Sockets = new() { ["muzzle"] = new SocketDef { Position = new Vector3(0, 0, -1) } },
        },
        new AssetDef { Id = "bolt", Kind = AssetKind.Projectile },
        new AssetDef { Id = "rock", Kind = AssetKind.Prop },
    });

    public static Tuning Tuning() => new()
    {
        Movers = new(StringComparer.OrdinalIgnoreCase)
        {
            ["dino"] = new MoverStats { MoveSpeed = 5f, TurnRateDegrees = 720f, MaxHealth = 30f },
        },
        Weapons = new(StringComparer.OrdinalIgnoreCase)
        {
            ["gun"] = new WeaponStats
            {
                Damage = 10f, Cooldown = 0.5f, Range = 20f, TurnRateDegrees = 720f,
                Projectile = "bolt", ProjectileSpeed = 40f,
            },
        },
    };

    public static World World(int seed = 1) => new(Registry(), Tuning(), seed);

    public static void Run(World world, float seconds, float step = 1f / 60f)
    {
        for (float t = 0; t < seconds; t += step) world.Tick(step);
    }

    /// <summary>Finds a file copied next to the test binaries (see the .csproj).</summary>
    public static string DataFile(string name) =>
        File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "data", name));
}
