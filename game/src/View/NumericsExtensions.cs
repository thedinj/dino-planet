namespace DinoPlanet.Game.View;

/// <summary>Conversions between Core's System.Numerics types and Godot's types.</summary>
public static class NumericsExtensions
{
    public static Godot.Vector3 ToGodot(this System.Numerics.Vector3 v) => new(v.X, v.Y, v.Z);

    public static System.Numerics.Vector3 ToCore(this Godot.Vector3 v) => new(v.X, v.Y, v.Z);

    public static System.Numerics.Vector2 ToCore(this Godot.Vector2 v) => new(v.X, v.Y);
}
