using System.Collections.Generic;
using DinoPlanet.Core.Assets;
using Godot;

namespace DinoPlanet.Game.View;

/// <summary>
/// Builds the Godot node for an asset from its registry entry: loads the generated model
/// (or a placeholder shape if it doesn't exist yet), applies the toon material, and adds
/// socket markers for debugging. No hand-made scenes needed per asset.
/// </summary>
public sealed class AssetFactory
{
    public const string SocketGizmoGroup = "socket_gizmo";

    private readonly Dictionary<string, PackedScene?> _models = new();

    /// <summary>Whether new socket markers start visible (F3 toggles existing ones).</summary>
    public bool ShowSockets { get; set; }

    public Node3D Create(AssetDef def)
    {
        var root = new Node3D { Name = def.Id };

        var model = LoadModel(def.Model)?.Instantiate<Node3D>() ?? Placeholders.For(def);
        model.Name = "Model";
        model.Scale = Vector3.One * def.Scale;
        model.RotationDegrees = new Vector3(0f, def.ModelYawDegrees, 0f);
        root.AddChild(model);

        if (def.Kind != AssetKind.Projectile)
        {
            ToonMaterials.ApplyTo(model, ToonMaterials.Get(def.Tint ?? Placeholders.DefaultTint(def)));
        }

        foreach (var (name, socket) in def.Sockets)
        {
            root.AddChild(CreateSocketGizmo(name, (socket.Position * def.Scale).ToGodot()));
        }

        return root;
    }

    private PackedScene? LoadModel(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return null;
        if (_models.TryGetValue(path, out var cached)) return cached;

        // Models must have been imported once (open the editor, or run `godot --headless --import`).
        var scene = ResourceLoader.Exists(path) ? GD.Load<PackedScene>(path) : null;
        if (scene is null) GD.Print($"[assets] {path} not found, using placeholder.");
        _models[path] = scene;
        return scene;
    }

    private Marker3D CreateSocketGizmo(string name, Vector3 position)
    {
        var marker = new Marker3D { Name = $"socket_{name}", Position = position, Visible = ShowSockets };
        marker.AddChild(new MeshInstance3D
        {
            Mesh = new SphereMesh { Radius = 0.08f, Height = 0.16f },
            MaterialOverride = new StandardMaterial3D
            {
                AlbedoColor = new Color(1f, 0.2f, 0.8f),
                ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
                NoDepthTest = true,
            },
        });
        marker.AddToGroup(SocketGizmoGroup);
        return marker;
    }
}
