# Dino Planet

Dinosaurs with laser cannons bolted on, in a chunky Tunic-style jungle. Built in Godot 4 + C#,
with nearly all game logic in a plain C# library so Claude can write and test it.

```
src/Core/          Game rules: simulation, behaviors, combat, level generation. No Godot.
tests/Core.Tests/  Unit tests for Core (dotnet test).
game/              Godot project: renderer, input, effects. One script on one scene.
  data/            assets.jsonc (models, sockets) and tuning.jsonc (numbers, F5 to reload)
  models/          Final cleaned .glb models (small, committed)
  shaders/         Toon + outline shaders
pipeline/          Asset pipeline: guide, Blender cleanup, prompts, workflows, manifest
CLAUDE.md          Architecture rules and commands for Claude Code
```

Big files stay out of git:

```
D:\AI\ComfyUI\   ComfyUI + AI models (tens of GB), outside the repo (path is up to you)
work\            refs, raw meshes, turntables, rejects (in the repo folder, gitignored)
```

Machine-specific paths go in `pipeline\local.settings.jsonc` (gitignored). Copy
`pipeline\local.settings.example.jsonc` to create it.

## Setup (Windows)

1. Install the **.NET 8 SDK**: https://dotnet.microsoft.com/download/dotnet/8.0
2. Download **Godot 4.6 — .NET edition** from https://godotengine.org/download
   (the ".NET" download, not the standard one). Unzip it somewhere permanent.
3. The project targets Godot 4.6.2. If you upgrade Godot, edit the first line of
   `game/DinoPlanet.Game.csproj` to match (e.g. `Godot.NET.Sdk/4.6.3`).
   `nuget.config` also points at Godot's local package folder in `C:\Program Files\Godot`.
4. In a terminal at the repo root:

   ```powershell
   dotnet test tests/Core.Tests
   ```

   All tests should pass. This checks the game logic and the data files.

5. Open Godot, **Import** `game/project.godot`, then press **Build** (hammer, top right) and
   **Run** (F5). The first open also imports shaders and models.

You should see a placeholder raptor (yours) in a scattered jungle, with enemy raptors closing in
and a T-rex to the north.

## Controls

| Action | Keyboard | Controller |
|---|---|---|
| Move | WASD / arrows | Left stick |
| Fire (auto-aims at nearest enemy in range) | Space / left mouse | RT or A |
| Restart with a new seed | R | Start |
| Show socket markers | F3 | |
| Reload `tuning.jsonc` | F5 | |
| Screenshot | F12 | |

## Working with Claude Code

Open Claude Code at the repo root. `CLAUDE.md` tells it the rules: logic goes in Core with tests,
the Godot side stays thin, numbers go in data files. It can run the tests, run a headless smoke
test, and take screenshots to check its own work (commands are in `CLAUDE.md`).

Good first asks:
- "Add simple separation so dinos don't walk through each other or the trees."
- "Make the T-rex charge in a straight line every few seconds."
- "Generate clearings and a winding path through the jungle in the scatter."

## Adding a generated model

1. Make it with the pipeline in `pipeline/README.md` and save it as `game/models/<id>.glb`.
2. Make sure `game/data/assets.jsonc` has an entry whose `model` points at it.
3. Open the editor once (or run `pwsh -NoProfile -File tools/godot.ps1 --headless --path game --import`) so Godot imports it.
4. Run, press F3, and adjust `modelYawDegrees`, `scale` and socket positions until the markers
   sit in the right places.
