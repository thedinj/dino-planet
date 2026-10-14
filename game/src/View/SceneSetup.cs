using Godot;

namespace DinoPlanet.Game.View;

/// <summary>
/// Builds the camera, lighting, environment and ground in code. This is where the Tunic look
/// comes from: a long-lens camera pitched down, warm sun, cool ambient, glow and depth-of-field.
/// </summary>
public static class SceneSetup
{
    /// <summary>Camera heading around Y. 45 degrees gives the diagonal, diorama view.</summary>
    public const float CameraYawDegrees = 45f;

    public const float CameraPitchDegrees = -40f;
    public const float CameraDistance = 34f;

    public static Camera3D Build(Node3D root, float groundHalfSize)
    {
        var sun = new DirectionalLight3D
        {
            Name = "Sun",
            LightColor = new Color(1f, 0.93f, 0.8f),
            LightEnergy = 1.2f,
            ShadowEnabled = true,
            RotationDegrees = new Vector3(-55f, 30f, 0f),
        };
        root.AddChild(sun);

        var env = new Godot.Environment
        {
            BackgroundMode = Godot.Environment.BGMode.Color,
            BackgroundColor = new Color(0.55f, 0.68f, 0.78f),
            AmbientLightSource = Godot.Environment.AmbientSource.Color,
            AmbientLightColor = new Color(0.55f, 0.6f, 0.85f),
            AmbientLightEnergy = 0.6f,
            TonemapMode = Godot.Environment.ToneMapper.Filmic,
            GlowEnabled = true,
            GlowIntensity = 0.6f,
            SsaoEnabled = true,
            FogEnabled = true,
            FogLightColor = new Color(0.6f, 0.72f, 0.8f),
            FogDensity = 0.004f,
        };
        root.AddChild(new WorldEnvironment { Name = "Environment", Environment = env });

        var ground = new MeshInstance3D
        {
            Name = "Ground",
            Mesh = new PlaneMesh { Size = new Vector2(groundHalfSize * 2.5f, groundHalfSize * 2.5f) },
            MaterialOverride = ToonMaterials.Get("#8DB35E"),
        };
        root.AddChild(ground);

        var camera = new Camera3D
        {
            Name = "Camera",
            Fov = 30f,
            Far = 400f,
            Attributes = new CameraAttributesPractical
            {
                DofBlurFarEnabled = true,
                DofBlurFarDistance = CameraDistance + 14f,
                DofBlurFarTransition = 20f,
                DofBlurNearEnabled = true,
                DofBlurNearDistance = CameraDistance - 12f,
                DofBlurNearTransition = 8f,
                DofBlurAmount = 0.06f,
            },
        };
        root.AddChild(camera);
        camera.MakeCurrent();
        return camera;
    }

    /// <summary>Places the camera at the fixed diorama angle looking at <paramref name="target"/>.</summary>
    public static void AimCamera(Camera3D camera, Vector3 target)
    {
        var basis = Basis.FromEuler(new Vector3(
            Mathf.DegToRad(CameraPitchDegrees), Mathf.DegToRad(CameraYawDegrees), 0f));
        camera.GlobalTransform = new Transform3D(basis, target + basis.Z * CameraDistance);
    }
}
