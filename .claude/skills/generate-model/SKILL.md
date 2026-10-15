---
name: generate-model
description: Generate the 3D model for a registered Dino Planet asset with the local ComfyUI pipeline (SDXL reference images -> Hunyuan3D-2mv mesh -> Blender cleanup -> game/models/<id>.glb), stopping for the user's sign-off at each review gate. Use when the user asks to generate, make or regenerate a model for an asset.
argument-hint: <asset-id> [--from=refs|shape|cleanup|fit] [--turbo]
---

# /generate-model

Turn a registered asset into a real model: `$ARGUMENTS`. The first word is the asset id.

The user signs off at every gate marked **GATE**. At a gate: send the images with
SendUserFile (`display: "render"`), say in a few lines what you see and what you recommend,
then ask with AskUserQuestion, recommended option first. Never go past a gate without an
answer, and never pick for the user. Your job at a gate is to look hard and give an honest
read, including flaws.

## Tools

All run from the repo root. Don't call ComfyUI, Blender or Godot any other way.

| Step | Command |
|---|---|
| Check ComfyUI | `python pipeline/comfy_gen.py check` |
| Reference images | `python pipeline/comfy_gen.py refs <id> --view left [--seed N] [--batch 4]` |
| Raw mesh | `python pipeline/comfy_gen.py shape <id> --left <png> [--front <png>] [--back <png>] [--right <png>] [--seed N] [--turbo]` |
| Turntable sheet | `pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_turntable.py -- --in <glb> [--out <png>] [--asset <id>] [--yaw N]` |
| Cleanup | `pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_cleanup.py -- --in <raw glb> --out work/cleaned/<id>_s<seed>.glb --tris T --size S --color C --belly B --yaw Y [--voxel V] [--flat]` |

Each prints `wrote <path>` / `[turntable] <path>` / `[ok] ...` lines; read the paths from
there. A shape run takes about 1 min on the 8 GB card (references about 1 min per batch of 4).
Run them in the foreground with a 10 minute timeout.

**Turntable sheet layout:** top-left front, top-right left side, bottom-left back,
bottom-right three-quarter. A red bar on the ground marks the front (game forward, -Z).
A correctly facing model looks **at the camera in the front tile** and points its head
**to screen left in the left tile**. If the front tile shows the head pointing screen right,
the yaw is about -90; screen left, about +90; away from the camera, 180. Diagonal meshes need
values like -135. Confirm a guess with `--asset <id> --yaw N` before cleanup.

## 0. Preconditions

1. The id must be in `pipeline/manifest.jsonc` and `game/data/assets.jsonc`. If not, stop
   and suggest `/new-asset <id>` first. Projectiles have no model; refuse those.
2. `pipeline/local.settings.jsonc` must exist with `comfyUiUrl` and `blenderExe`.
3. `python pipeline/comfy_gen.py check` must print `ready`. If it can't reach ComfyUI, ask
   the user to start ComfyUI Desktop. Don't try to launch it yourself.
4. Look in `work/runs/<id>.md`. If an earlier run exists and `--from` wasn't given, ask
   whether to continue from its last approved stage or start over.

Keep a log in `work/runs/<id>.md` (gitignored): one line per step with the date, the command,
the seed, what the user picked and why. Later runs and `--from` rely on it.

## 1. Reference images

1. Show the user the prompt that will be used: print it by running `refs` (it echoes the
   positive and negative text) or build it from `pipeline/prompts/style.md` + the manifest's
   `describe`.
2. Generate the `left` view, batch of 4, random seed.
3. Look at every image. Judge it against: side view facing left, whole body in frame
   including the tail, plain white or near-white background, chunky toy-like shapes (not
   mecha, not realistic), matches `describe`, no riders or extra creatures. Note which ones
   fail and why.

**GATE 1: pick a reference.** Send all 4. Options: use image N (recommend the best one), or
generate another batch (new seed), or change the `describe` text first.
- Prompt changes go in `pipeline/manifest.jsonc` (`describe`) for one asset, or
  `pipeline/prompts/style.md` for the whole look. Show the exact edit and get a yes before
  writing it, since style.md affects every asset.
- After 3 rejected batches, suggest a prompt change instead of more seeds.

Optionally, if the user wants more views: run `refs` again with `--view front` / `--view back`
and the **same seed**. Views rarely match the picked left view. At the same gate, the user
picks which extra views (if any) go into the mesh. A wrong extra view hurts more than a
missing one, so recommend left only unless a view clearly matches.

## 2. Raw mesh

Run `shape` with the picked views (use `--turbo` only if the user asked for speed). Then
render a turntable of the raw mesh (`--in work/raw-meshes/<id>_s<seed>.glb`).

Check the silhouette against the reference: all limbs present, no fused blobs, no missing
tail or head, nothing large floating free. Work out the facing and the yaw that fixes it,
and confirm it with a second turntable using `--asset <id> --yaw N`.

**GATE 2: approve the mesh.** Send the turntable sheet(s). Options: approve (with the yaw
you found), reroll the shape seed, go back to Gate 1 for a different reference, or try
with/without extra views.

## 3. Cleanup

Run the cleanup into `work/cleaned/`, never straight into `game/models/`. Take `--tris`,
`--size`, `--color`, `--belly` from the manifest entry (`colors.base`/`colors.belly`, drop
the `#`; an empty belly means `--belly ""`), plus the approved `--yaw`. Turntable the
result with `--asset <id>`.

Look for: thin parts (arms, tails, barrels) broken into floating bits, holes, belly color
in odd places, a lumpy or melted look. Knobs: a smaller `--voxel` (e.g. 0.01) keeps thin
parts, a larger one (0.04–0.06) is chunkier; more `--tris` keeps detail; `--flat` gives
facets.

**GATE 3: approve the cleaned model.** Send the sheet, with the raw sheet for comparison
if useful. Options: approve, or rerun cleanup with the knob changes you suggest.

## 4. Fit in the game

1. Copy the approved file to `game/models/<id>.glb`.
2. Registry (`game/data/assets.jsonc`): keep `modelYawDegrees` at 0 (the yaw is baked by
   cleanup) and `scale` at 1.0 unless the model must match the collider better. Fit the
   sockets to the mesh using the `--asset` turntable: the saddle sits on the back, turrets
   on the shoulders or back, muzzles at the barrel tip. Scale the collider to the model's
   printed size if they differ a lot (the collider drives the placeholder, collisions and
   hit range). Re-render the `--asset` sheet after each change.
3. `pwsh -NoProfile -File tools/godot.ps1 --headless --path game --import`, then
   `dotnet test tests/Core.Tests`, then run the `/visual-check` steps with `--sockets`.

**GATE 4: approve the fit.** Send the final `--asset` sheet and the in-game screenshot.
List every registry change (before -> after). Options: approve, or adjust specific sockets,
scale or collider.

## 5. Finish

1. Record the final choices in `work/runs/<id>.md`.
2. Report: files written, seeds, knobs, registry changes, anything still imperfect.
3. Don't commit on your own. Offer to run the `reviewer` agent and commit
   `game/models/<id>.glb` plus the data changes. **GATE 5:** commit only on a yes.

## Notes

- Everything under `work/` is gitignored and safe to throw away; `game/models/` is
  committed, so only approved models go there.
- SDXL and Hunyuan3D don't both fit in 8 GB. `shape` frees ComfyUI's models first. If a
  run still fails with out-of-memory, retry with `--octree 192`.
- Outputs also land in ComfyUI's own `output/dinoplanet/` folder. That's harmless; leave it.
