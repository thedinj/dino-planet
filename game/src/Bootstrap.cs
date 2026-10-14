using System;
using DinoPlanet.Core.Assets;
using DinoPlanet.Core.Data;
using DinoPlanet.Core.Scenarios;
using DinoPlanet.Core.Sim;
using DinoPlanet.Game.Controls;
using DinoPlanet.Game.Debug;
using DinoPlanet.Game.View;
using Godot;

namespace DinoPlanet.Game;

/// <summary>
/// The only script attached to a scene. It wires Core to Godot and runs the loop:
/// read input -> step the simulation at a fixed rate -> sync the view -> move the camera.
/// Everything game-specific happens in Core.
/// </summary>
public partial class Bootstrap : Node3D
{
    private const string AssetsPath = "res://data/assets.jsonc";
    private const string TuningPath = "res://data/tuning.jsonc";
    private const float FixedStep = 1f / 60f;
    private const int MaxStepsPerFrame = 5;

    private CommandLine _cli = new();
    private AssetRegistry _assets = null!;
    private AssetFactory _factory = null!;
    private Camera3D _camera = null!;

    private World _world = null!;
    private WorldView _view = null!;
    private EntityId _playerId;
    private int _seed;

    private float _accumulator;
    private int _frames;
    private int _errors;
    private float _restartTimer = -1f;
    private bool _showSockets;
    private Vector3 _cameraTarget;

    public override void _Ready()
    {
        _cli = CommandLine.Parse();
        _seed = _cli.Seed ?? (int)(Time.GetUnixTimeFromSystem() % int.MaxValue);
        _showSockets = _cli.ShowSockets;

        InputSetup.Register();
        _assets = AssetRegistry.FromJson(DebugTools.ReadText(AssetsPath));
        _factory = new AssetFactory { ShowSockets = _showSockets };
        _camera = SceneSetup.Build(this, TestArena.HalfSize);
        _view = new WorldView(this, _factory);

        StartWorld(_seed);
        GD.Print($"[game] Started with seed {_seed}. WASD/stick move, Space/RT fire, R restart, " +
                 "F3 sockets, F5 reload tuning, F12 screenshot.");
    }

    public override void _Process(double delta)
    {
        try
        {
            HandleDebugKeys();
            Step((float)delta);
            _view.Sync(_world);
            FollowPlayer((float)delta);
        }
        catch (Exception ex)
        {
            _errors++;
            GD.PushError($"[game] {ex}");
            if (_cli.SmokeFrames.HasValue) GetTree().Quit(1);
        }

        _frames++;
        CheckAutomation();
    }

    private void StartWorld(int seed)
    {
        _view.Clear();
        var tuning = Tuning.FromJson(DebugTools.ReadText(TuningPath));
        _world = new World(_assets, tuning, seed);
        _playerId = TestArena.Build(_world).Player.Id;
        _accumulator = 0f;
        _restartTimer = -1f;
        _view.Sync(_world);

        if (_world.TryGet(_playerId, out var player)) _cameraTarget = player.Position.ToGodot();
        SceneSetup.AimCamera(_camera, _cameraTarget);
    }

    private void Step(float delta)
    {
        _world.Input = InputSetup.ReadIntent();

        // Smoke tests run exactly one fixed step per frame so results don't depend on machine speed.
        if (_cli.SmokeFrames.HasValue)
        {
            _world.Tick(FixedStep);
        }
        else
        {
            _accumulator = Math.Min(_accumulator + delta, FixedStep * MaxStepsPerFrame);
            while (_accumulator >= FixedStep)
            {
                _world.Tick(FixedStep);
                _accumulator -= FixedStep;
            }
        }

        bool playerAlive = _world.TryGet(_playerId, out _);
        if (!playerAlive && _restartTimer < 0f) _restartTimer = 2.5f;
        if (_restartTimer >= 0f)
        {
            _restartTimer -= delta;
            if (_restartTimer < 0f) StartWorld(++_seed);
        }
    }

    private void FollowPlayer(float delta)
    {
        if (_world.TryGet(_playerId, out var player))
        {
            _cameraTarget = _cameraTarget.Lerp(player.Position.ToGodot(), 1f - Mathf.Exp(-5f * delta));
        }
        SceneSetup.AimCamera(_camera, _cameraTarget);
    }

    private void HandleDebugKeys()
    {
        if (Godot.Input.IsActionJustPressed(InputSetup.Restart)) StartWorld(++_seed);

        if (Godot.Input.IsActionJustPressed(InputSetup.DebugReload))
        {
            _world.Tuning = Tuning.FromJson(DebugTools.ReadText(TuningPath));
            GD.Print("[game] Reloaded tuning.jsonc");
        }

        if (Godot.Input.IsActionJustPressed(InputSetup.DebugSockets))
        {
            _showSockets = !_showSockets;
            _factory.ShowSockets = _showSockets;
            DebugTools.SetSocketGizmos(GetTree(), _showSockets);
        }

        if (Godot.Input.IsActionJustPressed(InputSetup.DebugScreenshot))
        {
            DebugTools.SaveScreenshot(GetViewport(), $"user://screenshots/shot_{DateTime.Now:yyyyMMdd_HHmmss}.png");
        }
    }

    private void CheckAutomation()
    {
        if (_cli.SmokeFrames is { } smoke && _frames >= smoke)
        {
            GD.Print($"[smoke] {_frames} frames, {_world.Entities.Count} entities, {_errors} errors.");
            GetTree().Quit(_errors == 0 ? 0 : 1);
        }

        if (_cli.ScreenshotPath is { } path && _frames == _cli.ScreenshotFrame)
        {
            DebugTools.SaveScreenshot(GetViewport(), path);
            GetTree().Quit();
        }
    }
}
