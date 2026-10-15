---
name: generate-model
description: Generate the 3D model for a registered Dino Planet asset with the local ComfyUI pipeline (Qwen-Image reference images, optionally redrawn from a user's photo or sketch -> Hunyuan3D-2mv mesh -> Blender cleanup -> game/models/<id>.glb), stopping for the user's sign-off at each review gate. Use when the user asks to generate, make or regenerate a model for an asset.
argument-hint: <asset-id> [plain description] [--ref=<image>] [--from=prompt|refs|shape|cleanup|fit] [--turbo]
---

# /generate-model

Turn a registered asset into a real model: `$ARGUMENTS`. The first word is the asset id.
Anything after it, other than flags, is the user's plain description of what they want.

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
| Reference images | `python pipeline/comfy_gen.py refs <id> [--prompts work/refs/<id>/prompts.json] [--ref <image>] [--batch 1] [--seed N]` |
| Fix-up or extra view | `python pipeline/comfy_gen.py edit <id> --image <png> --prompt "<instruction>" --name <name>` |
| Raw mesh | `python pipeline/comfy_gen.py shape <id> --left <png> [--front <png>] [--back <png>] [--seed N] [--turbo]` |
| Colors | `python pipeline/image_tools.py colors <png>` |
| Contact sheet | `python pipeline/image_tools.py sheet <out.png> <png>...` |
| Turntable sheet | `pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_turntable.py -- --in <glb> [--out <png>] [--asset <id>] [--yaw N]` |
| Cleanup | `pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_cleanup.py -- --in <raw glb> --out work/cleaned/<id>_s<seed>.glb --tris T --size S --color C --belly B [--yaw auto\|N] [--voxel V] [--flat]` |

They print `wrote <path>`, `sheet <path>`, `[turntable] <path>` and `[ok] ...` lines; read
paths from there. Timings on the 8 GB card: about 105 s per reference prompt (first one
includes model loading), about 70-110 s per edit, about 1 min per shape. Run them in the
foreground with a 10 minute timeout, one command at a time (ComfyUI runs one job anyway).

**Turntable sheet layout:** top-left front, top-right left side, bottom-left back,
bottom-right three-quarter. A red bar on the ground marks the front (game forward, -Z).
A correctly facing model looks **at the camera in the front tile** and points its head
**to screen left in the left tile**. If the front tile shows the head pointing screen right,
the yaw is about -90 off; screen left, about +90; away from the camera, 180. The printed
`size` helps: a long animal facing forward has z much bigger than x; x and z about equal
means it's diagonal.

## 0. Preconditions

1. The id must be in `pipeline/manifest.jsonc` and `game/data/assets.jsonc`. If not, stop
   and suggest `/new-asset <id>` first. Only `kind: "dino"` has a prompt template so far;
   for gear, say so and stop.
2. `pipeline/local.settings.jsonc` must exist with `comfyUiUrl` and `blenderExe`.
3. `python pipeline/comfy_gen.py check` must print `ready`. If it can't reach ComfyUI, ask
   the user to start ComfyUI Desktop. Don't try to launch it yourself.
4. Look in `work/runs/<id>.md`. If an earlier run exists and `--from` wasn't given, ask
   whether to continue from its last approved stage or start over.

Keep a log in `work/runs/<id>.md` (gitignored): one line per step with the date, the command,
the prompt variant, what the user picked and why. Later runs and `--from` rely on it.

## 1. The prompt

Read `pipeline/prompts/style.md`, especially **Writing the subject**. The subject is only
the creature (anatomy, proportions, colors); style.md adds pose, view and style.

1. The user's plain description is the `request`: from the arguments, else the manifest's
   `request`. If the manifest has none and no description was given, ask for one.
2. Set the manifest's `bodyPlan` if it's missing (biped, quadruped, long_quadruped; see the
   table in style.md). It sets the canvas.
3. Reference image: `--ref=<image>`, or the manifest's `reference`, or an image the user
   attached or named. Copy it to `work/inputs/<id>/` (gitignored: found art and photos are
   never committed) and record its file name in the manifest's `reference`. Look at it and
   say what it will contribute (shape, pose, proportions) and anything to watch, like an
   open mouth or a raised foot, which carry over.
4. Write **3 subject variants** that follow the rules, different in wording, not just
   adjectives (variety comes from wording; seeds barely change anything). With a reference
   the subject can be shorter, since the image carries the shape; still name the species
   and colors. Save them to `work/refs/<id>/prompts.json` as `[{"name": "a_short_slug",
   "prompt": "..."}]`.

**GATE 1: approve the prompts.** Show the request, the body plan, the reference (if any) and
the 3 subjects. Options: generate with these, or edit them first. Cheap to fix now, a
few minutes per batch after.

## 2. Reference images

Run `refs <id> --prompts work/refs/<id>/prompts.json` (plus `--ref` when there is one).
One image per variant is enough. It writes a contact sheet.

Judge every image against: side view facing left (prompt-only images often come out
slightly three-quarter on a light grey backdrop; that meshes fine), whole body in frame
including the tail, all feet down, mouth closed, matches the subject's anatomy, bare (no
gear, riders or extra creatures). Note which ones fail and why.

**GATE 2: pick a reference.** Send the sheet. Options: use image X (recommend the best),
fix a detail on one with `edit`, or rewrite the prompts (back to Gate 1).
- **Fix-ups:** for a missing small feature, run `edit` on the picked image with a precise
  instruction ending in "Change nothing else.", e.g. "The second toe of each foot is lifted
  and carries one very large, dark, hooked claw. Change nothing else." Show the result at
  this same gate.
- After 2 rejected rounds, say what keeps failing and suggest a different approach (a
  reference image, a fix-up, a different body plan) instead of more rewording.
- When an image is picked, write its subject to the manifest's `prompt` (show the edit) and
  run `image_tools.py colors` on it. Show the two colors and write them to the manifest's
  `colors` on a yes.

Extra views are optional: `edit` the picked image with "Show this exact same creature from
directly in front, full body. Keep the same shapes, proportions and colors. Plain pure white
background." (and the same for behind). They give a straighter mesh but cost about 2 min
more, and a wrong extra view hurts more than a missing one. Offer them only if the
single-view mesh comes out wrong.

## 3. Raw mesh

Run `shape <id> --left <picked png>` (plus `--front`/`--back` if approved; `--turbo` only if
the user asked for speed). Wide canvases are padded to a square automatically. Render a
turntable of the raw mesh.

Check the silhouette against the reference: all limbs present, no fused blobs, no missing
tail or head, nothing large floating free. Raw single-view meshes usually sit diagonally;
the cleanup's automatic yaw fixes that.

**GATE 3: approve the mesh.** Send the turntable sheet. Options: approve, reroll the shape
seed, go back to Gate 2 for a different image, or add front/back views.

## 4. Cleanup

Run the cleanup into `work/cleaned/`, never straight into `game/models/`. Take `--tris`,
`--size`, `--color`, `--belly` from the manifest entry (`colors.base`/`colors.belly`, drop
the `#`; an empty belly means `--belly ""`). Leave `--yaw` at its default `auto`: it lines
the long axis up with forward and prints the yaw it chose. For bipeds and quadrupeds use
`--flat` (the faceted low-poly look). Turntable the result with `--asset <id>`.

Check the facing first. If it's wrong, rerun with `--yaw <printed value + 180>` (a
head/tail swap) or the value you work out from the sheet. Then look for: thin parts (arms,
tails, claws) broken into floating bits, holes, belly color in odd places, a melted look.
Knobs: the default `--voxel` is 0.4% of `--size` (0.008 for a 2 m dino); smaller (0.005)
keeps thinner parts, 0.02+ melts arms, 0.04-0.06 is blobby. More `--tris` keeps detail.
Only two colors survive (base and belly); plates, stripes and armor colors are lost.

**GATE 4: approve the cleaned model.** Send the sheet, with the raw sheet for comparison
if useful. Options: approve, or rerun cleanup with the knob changes you suggest.

## 5. Fit in the game

1. Copy the approved file to `game/models/<id>.glb`.
2. Registry (`game/data/assets.jsonc`): keep `modelYawDegrees` at 0 (the yaw is baked by
   cleanup) and `scale` at 1.0 unless the model must match the collider better. Fit the
   sockets to the mesh using the `--asset` turntable: the saddle sits on the back, turrets
   on the shoulders or back, muzzles at the barrel tip. Scale the collider to the model's
   printed size if they differ a lot (the collider drives the placeholder, collisions and
   hit range). Re-render the `--asset` sheet after each change.
3. `pwsh -NoProfile -File tools/godot.ps1 --headless --path game --import`, then
   `dotnet test tests/Core.Tests`, then run the `/visual-check` steps with `--sockets`.

**GATE 5: approve the fit.** Send the final `--asset` sheet and the in-game screenshot.
List every registry change (before -> after). Options: approve, or adjust specific sockets,
scale or collider.

## 6. Finish

1. Record the final choices in `work/runs/<id>.md`.
2. Report: files written, the prompt variant, knobs, registry changes, anything still
   imperfect.
3. Don't commit on your own. Offer to run the `reviewer` agent and commit
   `game/models/<id>.glb` plus the data changes. **GATE 6:** commit only on a yes.

## Notes

- Everything under `work/` is gitignored and safe to throw away; `game/models/` is
  committed, so only approved models go there. Never copy a user's reference image
  anywhere outside `work/`.
- The Qwen models and Hunyuan3D don't fit in 8 GB together. Every command frees ComfyUI's
  models first. If a shape run still fails with out-of-memory, retry with `--octree 192`.
- Outputs also land in ComfyUI's own `output/dinoplanet/` folder. That's harmless; leave it.
