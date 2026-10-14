using System.Numerics;

namespace DinoPlanet.Core.Sim;

/// <summary>
/// What the player wants this frame, already converted to world space by the view layer
/// (so camera angle is not Core's problem). Move is on the XZ ground plane, length 0..1.
/// </summary>
public readonly record struct PlayerIntent(Vector2 Move, bool Fire)
{
    public static readonly PlayerIntent None = new(Vector2.Zero, false);
}
