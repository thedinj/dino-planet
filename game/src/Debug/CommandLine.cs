using System.Collections.Generic;
using Godot;

namespace DinoPlanet.Game.Debug;

/// <summary>
/// Options passed after "--" on the Godot command line, so Claude (or a script) can run the game
/// unattended:
///
///   godot --headless --path game -- --smoke-frames=600
///       Runs 600 fixed ticks with no window, then exits 0 if nothing threw, 1 otherwise.
///
///   godot --path game -- --screenshot=user://shot.png --screenshot-frame=120 --seed=7
///       Opens a window, saves a screenshot after 120 frames, then exits.
/// </summary>
public sealed class CommandLine
{
    public int? SmokeFrames { get; private set; }
    public string? ScreenshotPath { get; private set; }
    public int ScreenshotFrame { get; private set; } = 120;
    public int? Seed { get; private set; }
    public bool ShowSockets { get; private set; }

    public static CommandLine Parse()
    {
        var cl = new CommandLine();
        foreach (var arg in OS.GetCmdlineUserArgs())
        {
            var (key, value) = Split(arg);
            switch (key)
            {
                case "--smoke-frames" when int.TryParse(value, out var n):
                    cl.SmokeFrames = n;
                    break;
                case "--screenshot":
                    cl.ScreenshotPath = string.IsNullOrEmpty(value) ? "user://screenshot.png" : value;
                    break;
                case "--screenshot-frame" when int.TryParse(value, out var f):
                    cl.ScreenshotFrame = f;
                    break;
                case "--seed" when int.TryParse(value, out var s):
                    cl.Seed = s;
                    break;
                case "--sockets":
                    cl.ShowSockets = true;
                    break;
                default:
                    GD.PushWarning($"[cmdline] Ignoring unknown option '{arg}'.");
                    break;
            }
        }
        return cl;
    }

    private static (string Key, string Value) Split(string arg)
    {
        int eq = arg.IndexOf('=');
        return eq < 0 ? (arg, "") : (arg[..eq], arg[(eq + 1)..]);
    }
}
