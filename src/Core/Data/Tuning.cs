namespace DinoPlanet.Core.Data;

/// <summary>Movement and survivability numbers for anything that walks.</summary>
public sealed record MoverStats
{
    public float MoveSpeed { get; init; } = 4f;
    public float TurnRateDegrees { get; init; } = 270f;
    public float MaxHealth { get; init; } = 100f;
}

public sealed record WeaponStats
{
    public float Damage { get; init; } = 10f;
    public float Cooldown { get; init; } = 0.5f;
    public float Range { get; init; } = 12f;
    public float TurnRateDegrees { get; init; } = 360f;
    public string Projectile { get; init; } = "laser_bolt";
    public float ProjectileSpeed { get; init; } = 25f;
}

/// <summary>Difficulty knobs applied per faction on top of the per-asset numbers.</summary>
public sealed record FactionScaling
{
    public float Health { get; init; } = 1f;
    public float Damage { get; init; } = 1f;

    /// <summary>Multiplies shots per second (0.5 = fires half as often).</summary>
    public float FireRate { get; init; } = 1f;
}

/// <summary>
/// All gameplay numbers, loaded from data/tuning.jsonc. The game reloads this file while running
/// (F5), so balance changes never need a recompile. Keyed by asset id.
/// </summary>
public sealed record Tuning
{
    public Dictionary<string, MoverStats> Movers { get; init; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<string, WeaponStats> Weapons { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    public FactionScaling Player { get; init; } = new();
    public FactionScaling Enemy { get; init; } = new();

    public FactionScaling Scaling(Sim.Faction faction) => faction switch
    {
        Sim.Faction.Player => Player,
        Sim.Faction.Enemy => Enemy,
        _ => NoScaling,
    };

    private static readonly FactionScaling NoScaling = new();

    public MoverStats Mover(string assetId) => Movers.TryGetValue(assetId, out var s) ? s : DefaultMover;
    public WeaponStats Weapon(string assetId) => Weapons.TryGetValue(assetId, out var s) ? s : DefaultWeapon;

    private static readonly MoverStats DefaultMover = new();
    private static readonly WeaponStats DefaultWeapon = new();

    public static Tuning FromJson(string json)
    {
        var t = Json.Parse<Tuning>(json);
        // Re-wrap so lookups stay case-insensitive after deserializing.
        return t with
        {
            Movers = new(t.Movers, StringComparer.OrdinalIgnoreCase),
            Weapons = new(t.Weapons, StringComparer.OrdinalIgnoreCase),
        };
    }
}
