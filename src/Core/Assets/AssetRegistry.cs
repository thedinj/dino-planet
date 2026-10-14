using System.Numerics;
using DinoPlanet.Core.Data;

namespace DinoPlanet.Core.Assets;

public enum AssetKind
{
    Dino,
    Weapon,
    Rider,
    Projectile,
    Prop,
}

/// <summary>A named attachment point on an asset, in the asset's local space (meters, Y up, facing -Z).</summary>
public sealed record SocketDef
{
    public Vector3 Position { get; init; }

    /// <summary>Extra yaw applied to whatever is attached here (e.g. a side-facing gun mount).</summary>
    public float YawDegrees { get; init; }
}

public sealed record ColliderDef
{
    /// <summary>Radius on the ground plane, used for hits and separation.</summary>
    public float Radius { get; init; } = 0.5f;

    public float Height { get; init; } = 1f;
}

/// <summary>
/// One entry in data/assets.jsonc. This is the contract between the asset pipeline and the game:
/// the pipeline writes it, Core reads gameplay-relevant parts, the view layer reads the rest.
/// </summary>
public sealed record AssetDef
{
    public string Id { get; init; } = "";
    public AssetKind Kind { get; init; }

    /// <summary>Godot resource path of the model (res://models/x.glb). May not exist yet; the view uses a placeholder.</summary>
    public string Model { get; init; } = "";

    /// <summary>Uniform scale applied to the model and its sockets.</summary>
    public float Scale { get; init; } = 1f;

    /// <summary>View-only correction when a generated model faces the wrong way.</summary>
    public float ModelYawDegrees { get; init; }

    /// <summary>Hex color multiplied over the model's vertex colors (view-only).</summary>
    public string? Tint { get; init; }

    public ColliderDef Collider { get; init; } = new();

    public Dictionary<string, SocketDef> Sockets { get; init; } = new();

    /// <summary>Socket position scaled into the parent's local space.</summary>
    public Vector3 SocketPosition(string socket) =>
        Sockets.TryGetValue(socket, out var s)
            ? s.Position * Scale
            : throw new KeyNotFoundException($"Asset '{Id}' has no socket '{socket}'.");
}

/// <summary>All assets, loaded from data/assets.jsonc.</summary>
public sealed class AssetRegistry
{
    private readonly Dictionary<string, AssetDef> _assets;

    public AssetRegistry(IEnumerable<AssetDef> assets)
    {
        _assets = new Dictionary<string, AssetDef>(StringComparer.OrdinalIgnoreCase);
        foreach (var a in assets)
        {
            if (string.IsNullOrWhiteSpace(a.Id))
                throw new InvalidDataException("An asset in the registry has no id.");
            if (!_assets.TryAdd(a.Id, a))
                throw new InvalidDataException($"Duplicate asset id '{a.Id}'.");
        }
    }

    public IReadOnlyCollection<AssetDef> All => _assets.Values;

    public AssetDef Get(string id) =>
        _assets.TryGetValue(id, out var a) ? a : throw new KeyNotFoundException($"Unknown asset '{id}'.");

    public bool TryGet(string id, out AssetDef asset) => _assets.TryGetValue(id, out asset!);

    public static AssetRegistry FromJson(string json) => new(Json.Parse<RegistryFile>(json).Assets);

    private sealed record RegistryFile
    {
        public List<AssetDef> Assets { get; init; } = new();
    }
}
