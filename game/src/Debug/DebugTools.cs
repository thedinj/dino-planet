using Godot;

namespace DinoPlanet.Game.Debug;

public static class DebugTools
{
    /// <summary>Saves what's on screen. Paths may use user:// (per-user app data) or an absolute path.</summary>
    public static string SaveScreenshot(Viewport viewport, string path)
    {
        var image = viewport.GetTexture().GetImage();
        string resolved = path.StartsWith("user://") || path.StartsWith("res://")
            ? ProjectSettings.GlobalizePath(path)
            : path;
        DirAccess.MakeDirRecursiveAbsolute(resolved.GetBaseDir());
        var err = image.SavePng(resolved);
        if (err != Error.Ok) GD.PushError($"[debug] Screenshot failed: {err}");
        else GD.Print($"[debug] Screenshot saved to {resolved}");
        return resolved;
    }

    /// <summary>Shows or hides every socket marker in the scene.</summary>
    public static void SetSocketGizmos(SceneTree tree, bool visible)
    {
        foreach (var node in tree.GetNodesInGroup(View.AssetFactory.SocketGizmoGroup))
        {
            if (node is Node3D n) n.Visible = visible;
        }
    }

    public static string ReadText(string resPath)
    {
        using var file = Godot.FileAccess.Open(resPath, Godot.FileAccess.ModeFlags.Read);
        if (file is null)
            throw new System.IO.FileNotFoundException($"Could not open {resPath}: {Godot.FileAccess.GetOpenError()}");
        return file.GetAsText();
    }
}
