using System.Collections.Generic;
using Godot;

namespace DinoPlanet.Game.View;

/// <summary>
/// One shared toon material (with ink outline) for everything, plus cached tinted copies.
/// Using a single material for every asset is what keeps generated models looking like one game.
/// </summary>
public static class ToonMaterials
{
    private static ShaderMaterial? _base;
    private static readonly Dictionary<string, ShaderMaterial> Tinted = new();

    public static ShaderMaterial Base => _base ??= CreateBase();

    /// <summary>The shared material, or a cached copy tinted with a hex color like "#C9A27A".</summary>
    public static ShaderMaterial Get(string? tintHex)
    {
        if (string.IsNullOrWhiteSpace(tintHex)) return Base;
        if (Tinted.TryGetValue(tintHex, out var cached)) return cached;

        var m = (ShaderMaterial)Base.Duplicate();
        m.SetShaderParameter("tint", Color.FromHtml(tintHex));
        Tinted[tintHex] = m;
        return m;
    }

    /// <summary>Overrides the material on every mesh under <paramref name="node"/>.</summary>
    public static void ApplyTo(Node node, Material material)
    {
        if (node is MeshInstance3D mesh) mesh.MaterialOverride = material;
        foreach (var child in node.GetChildren()) ApplyTo(child, material);
    }

    private static ShaderMaterial CreateBase()
    {
        var outline = new ShaderMaterial { Shader = GD.Load<Shader>("res://shaders/outline.gdshader") };
        return new ShaderMaterial
        {
            Shader = GD.Load<Shader>("res://shaders/toon.gdshader"),
            NextPass = outline,
        };
    }
}
