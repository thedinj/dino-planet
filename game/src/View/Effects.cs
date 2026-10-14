using Godot;

namespace DinoPlanet.Game.View;

/// <summary>
/// Code-only juice: flashes, punches and bursts. No sprites or particle assets needed.
/// </summary>
public static class Effects
{
    public static void MuzzleFlash(Node3D parent, Vector3 at)
    {
        var light = new OmniLight3D
        {
            Position = at,
            LightColor = new Color(1f, 0.45f, 0.25f),
            LightEnergy = 4f,
            OmniRange = 3f,
        };
        parent.AddChild(light);
        var tween = light.CreateTween();
        tween.TweenProperty(light, "light_energy", 0f, 0.08f);
        tween.TweenCallback(Callable.From(light.QueueFree));
    }

    /// <summary>Quick squash-and-stretch so hits feel like they land.</summary>
    /// <remarks>Takes the rest scale explicitly so overlapping hits can't leave the model squashed.</remarks>
    public static void HitPunch(Node3D node, float restScale)
    {
        var model = node.GetNodeOrNull<Node3D>("Model") ?? node;
        var tween = model.CreateTween();
        var baseScale = Vector3.One * restScale;
        tween.TweenProperty(model, "scale", baseScale * new Vector3(1.15f, 0.85f, 1.15f), 0.05f);
        tween.TweenProperty(model, "scale", baseScale, 0.12f).SetTrans(Tween.TransitionType.Elastic);
    }

    /// <summary>A short-lived glowing sphere burst, e.g. when something dies.</summary>
    public static void Burst(Node3D parent, Vector3 at, Color color, float size)
    {
        var mesh = new MeshInstance3D
        {
            Mesh = new SphereMesh { Radius = 0.5f, Height = 1f },
            Position = at,
            Scale = Vector3.One * 0.2f,
            MaterialOverride = new StandardMaterial3D
            {
                AlbedoColor = color,
                ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
                Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
                EmissionEnabled = true,
                Emission = color,
                EmissionEnergyMultiplier = 3f,
            },
        };
        parent.AddChild(mesh);

        var tween = mesh.CreateTween().SetParallel();
        tween.TweenProperty(mesh, "scale", Vector3.One * size * 2f, 0.3f).SetEase(Tween.EaseType.Out);
        tween.TweenProperty(mesh.MaterialOverride, "albedo_color:a", 0f, 0.3f);
        tween.Chain().TweenCallback(Callable.From(mesh.QueueFree));
    }
}
