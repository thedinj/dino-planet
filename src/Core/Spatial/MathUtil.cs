using System.Numerics;

namespace DinoPlanet.Core.Spatial;

/// <summary>
/// Shared math conventions. Matches Godot so the view layer can copy values straight across:
/// Y is up, yaw is rotation about +Y in radians, and yaw 0 faces -Z.
/// </summary>
public static class MathUtil
{
    public const float Tau = MathF.PI * 2f;

    /// <summary>Rotates a vector about the Y axis by <paramref name="yaw"/> radians (Godot convention).</summary>
    public static Vector3 RotateY(Vector3 v, float yaw)
    {
        float c = MathF.Cos(yaw), s = MathF.Sin(yaw);
        return new Vector3(v.X * c + v.Z * s, v.Y, -v.X * s + v.Z * c);
    }

    /// <summary>Unit vector an entity with this yaw is facing.</summary>
    public static Vector3 Forward(float yaw) => new(-MathF.Sin(yaw), 0f, -MathF.Cos(yaw));

    /// <summary>Yaw that faces along <paramref name="direction"/> (ignores Y).</summary>
    public static float YawFromDirection(Vector3 direction) => MathF.Atan2(-direction.X, -direction.Z);

    /// <summary>Wraps an angle to (-PI, PI].</summary>
    public static float WrapAngle(float a)
    {
        a %= Tau;
        if (a <= -MathF.PI) a += Tau;
        else if (a > MathF.PI) a -= Tau;
        return a;
    }

    /// <summary>Turns <paramref name="current"/> toward <paramref name="target"/> by at most <paramref name="maxDelta"/>.</summary>
    public static float TurnToward(float current, float target, float maxDelta)
    {
        float diff = WrapAngle(target - current);
        if (MathF.Abs(diff) <= maxDelta) return WrapAngle(target);
        return WrapAngle(current + MathF.Sign(diff) * maxDelta);
    }

    public static float DistanceXZ(Vector3 a, Vector3 b)
    {
        float dx = a.X - b.X, dz = a.Z - b.Z;
        return MathF.Sqrt(dx * dx + dz * dz);
    }

    public static float DegToRad(float degrees) => degrees * (MathF.PI / 180f);
}
