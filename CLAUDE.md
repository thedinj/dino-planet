# Dino Planet — notes for Claude

A hobby 3D game: dinosaurs with weapons bolted on, ridden into battle. The art is
loosely Tunic-inspired (toon shading, readable shapes), not strict low-poly: creatures are
symmetric with stylized, somewhat exaggerated proportions, and a smoother, higher-poly mesh
(around 12k triangles) is fine when it looks better.
The owner wants Claude to write most of the game logic. Godot is used only for rendering,
input, audio and the game loop.

## Architecture rules

- **Game rules live in `src/Core`.** It is plain C# (net8.0) with **no Godot references**.
  Simulation, behaviors, combat, procedural generation and data loading all go here.
- **`game/` is a thin view layer.** It reads input, calls `World.Tick`, and mirrors entities as
  nodes. If you're adding an `if` about gameplay in `game/`, it probably belongs in Core.
- **No hand-made scenes.** `Main.tscn` holds only `Bootstrap`. Nodes are built in code
  (`AssetFactory`, `SceneSetup`, `Effects`). Don't add scenes or editor-configured resources
  unless asked (UI may become an exception later).
- **Data over code for numbers and assets.** Gameplay numbers go in `game/data/tuning.jsonc`
  (hot-reloaded with F5). Assets, sizes and sockets go in `game/data/assets.jsonc`.
- **Behaviors compose.** Entities get personality from a list of `IBehavior`s that run in order.
  Movement uses `Entity.TrySteer`: the first behavior to claim steering each tick wins, so put
  higher-priority behaviors first (e.g. `ChaseNearestHostile` before `Wander`).
- **Determinism.** Use `world.Rng` (seeded), never `new Random()` or `Godot.GD.Randf` in Core.
  Core steps at a fixed 1/60 s. Same seed + same input = same result.
- **Events, not callbacks.** Core reports what happened via `WorldEvent`s; the view drains them
  for effects and sound. Core never calls into the view.

## Conventions

- Coordinates match Godot: Y up, meters, yaw in radians about +Y, **yaw 0 faces -Z**.
  Use `MathUtil.Forward`, `RotateY`, `YawFromDirection`, `TurnToward`.
- Core uses `System.Numerics`; convert with `.ToGodot()` / `.ToCore()` in the view.
- Attached entities (guns, riders) have world transforms computed by Core from the parent's
  socket each tick; their own `LocalYaw` is for swiveling.
- Data files are `.jsonc` (JSON with comments) so Godot doesn't try to import them. When an
  export preset is added, include `*.jsonc` in its non-resource export filter.

## Commands

```bash
# Logic tests (fast, no engine). Run after every Core change.
dotnet test tests/Core.Tests

# Build everything including the Godot project.
dotnet build DinoPlanet.sln

# Import assets (first run, or after adding models), headless.
pwsh -NoProfile -File tools/godot.ps1 --headless --path game --import

# Smoke test: run 600 ticks with no window; exit code 0 = no exceptions.
pwsh -NoProfile -File tools/godot.ps1 --headless --path game -- --smoke-frames=600

# Screenshot after 120 frames, then quit. Look at it to check visual changes.
pwsh -NoProfile -File tools/godot.ps1 --path game -- --screenshot=user://shot.png --screenshot-frame=120 --seed=7
```

`tools/godot.ps1` runs the Godot **.NET** editor named by `godotExe` in
`pipeline/local.settings.jsonc` (its `_console` variant when present, for readable output).
`tools/blender.ps1` does the same for `blenderExe`. Use these wrappers exactly as written:
they're pre-approved in `.claude/settings.json` and keep machine paths out of the repo.
`user://` resolves to `%APPDATA%\Godot\app_userdata\Dino Planet\`.

## Workflow expectations

1. Write or update tests in `tests/Core.Tests` for new Core behavior.
2. `dotnet test` must pass.
3. For anything visible, run the smoke test, then a screenshot, and inspect the image.
4. Keep `game/data/*.jsonc` valid; `DataTests` load the real files.
5. Before committing, run the `reviewer` subagent (`.claude/agents/reviewer.md`) on the diff
   and fix its blockers.

Claude tooling in `.claude/`: a Stop hook runs `dotnet test` when a turn ends with uncommitted
changes under `src/`, `tests/` or `game/data/`, and sends failures back to Claude. Skills:
`/new-asset <id>` (registers an asset in the data files; no art), `/generate-model <id>`
(ComfyUI -> Blender -> `game/models/<id>.glb`, with a user sign-off at each review gate),
`/visual-check`, `/devlog` (entries go in `docs/devlog/`).

## Asset pipeline

See `pipeline/README.md`. Generated models go in `game/models/` as `.glb`, cleaned by
`pipeline/blender_cleanup.py`. `pipeline/comfy_gen.py` drives ComfyUI (workflows in
`pipeline/workflows/`, prompt template in `pipeline/prompts/style.md`), `pipeline/image_tools.py`
samples colors and makes review sheets, `pipeline/blender_parts.py` adds procedural parts too
small for the AI steps (claws), and `pipeline/blender_turntable.py` renders review sheets of
a mesh. Users' reference photos and sketches go in `work/inputs/<id>/` and are never
committed. Until a model exists, `Placeholders` draws a stand-in sized from
the asset's collider. Press F3 in-game to see socket markers.

**Keep big files out of git.** ComfyUI and its AI models live outside the repo. Reference images,
raw meshes, turntables and rejects go in `work/` at the repo root, which is gitignored and never
imported by Godot (only `game/` is). Machine paths are in `pipeline/local.settings.jsonc`
(gitignored; copy from `local.settings.example.jsonc`). Pipeline scripts must read paths from that
file, never hard-code them; `workDir` is relative to the repo root. Only final cleaned `.glb`
models (a few hundred KB each) are committed.
