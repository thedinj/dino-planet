using DinoPlanet.Core.Assets;
using Godot;

namespace DinoPlanet.Game.View;

/// <summary>
/// Simple stand-in shapes, sized from the asset's collider, used until a generated model exists.
/// Each one shows which way is forward (-Z) so sockets and facing can be checked early.
/// </summary>
public static class Placeholders
{
    public static string DefaultTint(AssetDef def) => def.Kind switch
    {
        AssetKind.Dino => "#7E9F5A",
        AssetKind.Weapon => "#8C8F99",
        AssetKind.Rider => "#D8C27A",
        AssetKind.Prop when def.Id.Contains("rock") => "#9A938A",
        AssetKind.Prop => "#4F7A3E",
        _ => "#FFFFFF",
    };

    public static Node3D For(AssetDef def)
    {
        var root = new Node3D();
        float r = def.Collider.Radius;
        float h = def.Collider.Height;

        switch (def.Kind)
        {
            case AssetKind.Dino:
                // Body lying along Z, head out front, tail behind, two stubby legs.
                Add(root, new CapsuleMesh { Radius = h * 0.28f, Height = r * 3.2f },
                    new Vector3(0, h * 0.62f, 0), new Vector3(90, 0, 0));
                Add(root, new SphereMesh { Radius = h * 0.2f, Height = h * 0.4f },
                    new Vector3(0, h * 0.85f, -r * 1.75f));
                Add(root, new CylinderMesh { TopRadius = 0.02f, BottomRadius = h * 0.16f, Height = r * 2.2f },
                    new Vector3(0, h * 0.6f, r * 2.2f), new Vector3(80, 0, 0));
                Add(root, new CapsuleMesh { Radius = h * 0.09f, Height = h * 0.6f },
                    new Vector3(-r * 0.45f, h * 0.25f, r * 0.2f));
                Add(root, new CapsuleMesh { Radius = h * 0.09f, Height = h * 0.6f },
                    new Vector3(r * 0.45f, h * 0.25f, r * 0.2f));
                break;

            case AssetKind.Weapon:
                Add(root, new BoxMesh { Size = new Vector3(0.35f, 0.25f, 0.4f) }, new Vector3(0, 0.1f, 0));
                Add(root, new CylinderMesh { TopRadius = 0.06f, BottomRadius = 0.06f, Height = 0.6f },
                    new Vector3(0, 0.12f, -0.35f), new Vector3(90, 0, 0));
                break;

            case AssetKind.Rider:
                Add(root, new CapsuleMesh { Radius = r, Height = h }, new Vector3(0, h * 0.5f, 0));
                break;

            case AssetKind.Projectile:
                var bolt = Add(root, new CapsuleMesh { Radius = 0.06f, Height = 0.9f },
                    Vector3.Zero, new Vector3(90, 0, 0));
                var color = Color.FromHtml(def.Tint ?? "#FF5A3C");
                bolt.MaterialOverride = new StandardMaterial3D
                {
                    AlbedoColor = color,
                    ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
                    EmissionEnabled = true,
                    Emission = color,
                    EmissionEnergyMultiplier = 4f,
                };
                break;

            case AssetKind.Prop when def.Id.Contains("rock"):
                Add(root, new SphereMesh { Radius = r, Height = h * 1.2f, RadialSegments = 7, Rings = 4 },
                    new Vector3(0, h * 0.35f, 0));
                break;

            case AssetKind.Prop:
                // Tree: trunk plus a chunky canopy.
                Add(root, new CylinderMesh { TopRadius = r * 0.3f, BottomRadius = r * 0.45f, Height = h * 0.6f },
                    new Vector3(0, h * 0.3f, 0));
                Add(root, new SphereMesh { Radius = r * 2.4f, Height = h * 0.55f, RadialSegments = 8, Rings = 4 },
                    new Vector3(0, h * 0.75f, 0));
                break;
        }

        return root;
    }

    private static MeshInstance3D Add(Node3D parent, Mesh mesh, Vector3 position, Vector3? rotationDegrees = null)
    {
        var mi = new MeshInstance3D
        {
            Mesh = mesh,
            Position = position,
            RotationDegrees = rotationDegrees ?? Vector3.Zero,
        };
        parent.AddChild(mi);
        return mi;
    }
}
