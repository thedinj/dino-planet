using DinoPlanet.Core.Sim;
using DinoPlanet.Core.Spatial;
using DinoPlanet.Game.View;
using Godot;

namespace DinoPlanet.Game.Controls;

/// <summary>
/// Registers input actions in code (no editor Input Map), and turns raw input into Core's
/// camera-independent <see cref="PlayerIntent"/>.
/// </summary>
public static class InputSetup
{
    public const string MoveLeft = "move_left";
    public const string MoveRight = "move_right";
    public const string MoveForward = "move_forward";
    public const string MoveBack = "move_back";
    public const string Fire = "fire";
    public const string Restart = "restart";
    public const string DebugReload = "debug_reload";
    public const string DebugSockets = "debug_sockets";
    public const string DebugScreenshot = "debug_screenshot";

    public static void Register()
    {
        AddKeys(MoveLeft, Key.A, Key.Left);
        AddKeys(MoveRight, Key.D, Key.Right);
        AddKeys(MoveForward, Key.W, Key.Up);
        AddKeys(MoveBack, Key.S, Key.Down);
        AddAxis(MoveLeft, JoyAxis.LeftX, -1f);
        AddAxis(MoveRight, JoyAxis.LeftX, 1f);
        AddAxis(MoveForward, JoyAxis.LeftY, -1f);
        AddAxis(MoveBack, JoyAxis.LeftY, 1f);

        AddKeys(Fire, Key.Space);
        AddAxis(Fire, JoyAxis.TriggerRight, 1f);
        AddButton(Fire, JoyButton.A);
        Ensure(Fire);
        InputMap.ActionAddEvent(Fire, new InputEventMouseButton { ButtonIndex = MouseButton.Left, Device = -1 });

        AddKeys(Restart, Key.R);
        AddButton(Restart, JoyButton.Start);
        AddKeys(DebugReload, Key.F5);
        AddKeys(DebugSockets, Key.F3);
        AddKeys(DebugScreenshot, Key.F12);
    }

    /// <summary>Reads movement and fire, rotated so "up" on the stick means "away from the camera".</summary>
    public static PlayerIntent ReadIntent()
    {
        var stick = Godot.Input.GetVector(MoveLeft, MoveRight, MoveForward, MoveBack);
        float camYaw = Mathf.DegToRad(SceneSetup.CameraYawDegrees);

        var right = MathUtil.RotateY(new System.Numerics.Vector3(1, 0, 0), camYaw);
        var back = MathUtil.RotateY(new System.Numerics.Vector3(0, 0, 1), camYaw);
        var move = right * stick.X + back * stick.Y;

        return new PlayerIntent(new System.Numerics.Vector2(move.X, move.Z), Godot.Input.IsActionPressed(Fire));
    }

    private static void Ensure(string action)
    {
        if (!InputMap.HasAction(action)) InputMap.AddAction(action, 0.2f);
    }

    private static void AddKeys(string action, params Key[] keys)
    {
        Ensure(action);
        foreach (var key in keys) InputMap.ActionAddEvent(action, new InputEventKey { PhysicalKeycode = key, Device = -1 });
    }

    private static void AddAxis(string action, JoyAxis axis, float direction)
    {
        Ensure(action);
        InputMap.ActionAddEvent(action, new InputEventJoypadMotion { Axis = axis, AxisValue = direction, Device = -1 });
    }

    private static void AddButton(string action, JoyButton button)
    {
        Ensure(action);
        InputMap.ActionAddEvent(action, new InputEventJoypadButton { ButtonIndex = button, Device = -1 });
    }
}
