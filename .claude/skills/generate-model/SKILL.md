---
name: generate-model
description: Generate the 3D model for a registered Dino Planet asset with the local ComfyUI pipeline (a standing side view from a description, photo or drawing -> stylize -> front view -> Hunyuan3D-2mv mesh -> symmetric Blender cleanup -> game/models/<id>.glb), stopping for the user's sign-off at each review gate. Use when the user asks to generate, make or regenerate a model for an asset.
argument-hint: <asset-id> [plain description] [--ref=<image>] [--from=prompt|side|stylize|views|shape|cleanup|fit] [--turbo]
---

# /generate-model

Turn a registered asset into a real model: `$ARGUMENTS`. The first word is the asset id.
Anything after it, other than flags, is the user's plain description of what they want.

The target (CLAUDE.md): a symmetric creature with stylized, somewhat exaggerated
proportions, smooth-shaded at about 12k triangles, standing in a neutral pose (feet down,
mouth closed, tail level) so it can be rigged.

The user signs off at every gate marked **GATE**. At a gate: send the images with
SendUserFile (`display: "render"`), say in a few lines what you see and what you recommend,
then ask with AskUserQuestion, recommended option first. Never go past a gate without an
answer, and never pick for the user. Your job at a gate is to look hard and give an honest
read, including flaws.

## Tools

All run from the repo root. Don't call ComfyUI, Blender or Godot any other way.
`comfy_gen.py <command> --help` lists every option.

| Step | Command |
|---|---|
| Check ComfyUI | `python pipeline/comfy_gen.py check` |
| Side view from a description | `python pipeline/comfy_gen.py refs <id> [--prompts work/refs/<id>/prompts.json] [--ref <image>] [--seed N]` |
| Side view following a picture's outline | `python pipeline/comfy_gen.py redraw <id> --guide <image> [--subject "..."] [--flip] [--clean 1.8] [--name N]` |
| Pose outline | `python pipeline/image_tools.py outline <standing picture> work/refs/<id>/outline_stand.png` |
| Re-pose to standing | `python pipeline/comfy_gen.py pose <id> --image <png> --outline <png> [--keep "..."] [--seed N]` |
| Stylize | `python pipeline/comfy_gen.py stylize <id> --image <png> [--traits "..."] [--seed N] [--name N]` (default: manifest `traits`) |
| Front and right views | `python pipeline/comfy_gen.py views <id> --image <side png> [--seed N]` |
| Fix-up | `python pipeline/comfy_gen.py edit <id> --image <png> --prompt "<instruction>" --name <name>` |
| Raw mesh | `python pipeline/comfy_gen.py shape <id> --left <png> --front <png> --right <png> [--seed N] [--turbo]` |
| Colors | `python pipeline/image_tools.py colors <png>` |
| Contact sheet | `python pipeline/image_tools.py sheet <out.png> <png>...` |
| Turntable sheet | `pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_turntable.py -- --in <glb> [--out <png>] [--asset <id>] [--yaw N]` |
| Cleanup | `pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_cleanup.py -- --in <raw glb> --out work/cleaned/<id>_s<seed>.glb --tris T --size S --color C --belly B --belly-image <stylized png> [--sym neg\|pos] [--yaw auto\|N] [--voxel V]` |

They print `wrote <path>`, `sheet <path>`, `[turntable] <path>` and `[ok] ...` lines; read
paths from there. Timings on the 8 GB card: 2-5 min per image step (`refs`, `pose`,
`stylize`, `views`), up to 10 min for `redraw`, 2-3 min per shape, seconds for cleanup.
Run them in the foreground with a 10 minute timeout, one command at a time (ComfyUI runs
one job anyway). ComfyUI needs most of the 32 GB of RAM: if a run dies or ComfyUI stops
answering, ask the user to restart it and close other programs; never start it yourself.

**Turntable sheet layout:** top-left front, top-right left side, bottom-left back,
bottom-right three-quarter. A red bar on the ground marks the front (game forward, -Z).
A correctly facing model looks **at the camera in the front tile** and points its head
**to screen left in the left tile**. If the front tile shows the head pointing screen right,
the yaw is about -90 off; screen left, about +90; away from the camera, 180. The printed
`size` helps: a long animal facing forward has z much bigger than x; x and z about equal
means it's diagonal.

## 0. Preconditions

1. The id must be in `pipeline/manifest.jsonc` and `game/data/assets.jsonc`. If not, stop
   and suggest `/new-asset <id>` first. Only `kind: "dino"` has prompt templates so far;
   for gear, say so and stop.
2. `pipeline/local.settings.jsonc` must exist with `comfyUiUrl` and `blenderExe`.
3. `python pipeline/comfy_gen.py check` must print `ready`. If it can't reach ComfyUI, ask
   the user to start ComfyUI Desktop. Don't try to launch it yourself.
4. Look in `work/runs/<id>.md`. If an earlier run exists and `--from` wasn't given, ask
   whether to continue from its last approved stage or start over.

Keep a log in `work/runs/<id>.md` (gitignored): one line per step with the date, the command,
the prompt variant, what the user picked and why. Later runs and `--from` rely on it.

## 1. The source

Read `pipeline/prompts/style.md` first: it holds every prompt block and the rules for
writing subjects and traits.

1. The user's plain description is the `request`: from the arguments, else the manifest's
   `request`. If the manifest has none and no description was given, ask for one.
2. Set the manifest's `bodyPlan` if it's missing (biped, quadruped, long_quadruped; see the
   table in style.md).
3. Reference image: `--ref=<image>`, or the manifest's `reference`, or an image the user
   attached or named. Copy it to `work/inputs/<id>/` (gitignored: found art and photos are
   never committed) and record its file name in the manifest's `reference`. Look at it and
   say what it will contribute and what to watch.
4. Pick the route for the side view:
   - **No picture:** `refs` from a written subject. Write **3 subject variants** that follow
     **Writing the subject** (different in wording, not just adjectives) to
     `work/refs/<id>/prompts.json` as `[{"name": "a_short_slug", "prompt": "..."}]`.
   - **A clean side-on picture** (a toy photo, side-view art): `refs --ref`. It keeps the
     picture's shape and pose, and tends to keep its rendering style too.
   - **A drawing, a busy photo or art in an odd style:** `redraw --guide` with one subject.
     It follows the outline almost exactly and takes the look from the prompt. The
     creature must face left (`--flip` otherwise). Clean the guide first if it has a
     ground line, signature, text or other animals: paint them white with a short Pillow
     script into `work/refs/<id>/guide.png`. Use `--clean 1.8` for scans and stippled or
     hatched ink.

**GATE 1: approve the prompts and route.** Show the request, body plan, reference, route
and subject(s). Options: go ahead, or edit first.

## 2. Standing side view

Run the route from step 1. Judge each image: side view facing left, whole body in frame,
mouth closed, right anatomy, bare (no gear, riders or extra creatures). Its **pose** is
fixed in the next step if needed, so a running or leaping pose is fine here.

If the creature isn't standing neutrally, re-pose it:
1. Get a standing outline: `image_tools.py outline` on any picture of a similar animal
   standing side-on, facing left: an earlier `refs` image, a `refs` run with a short
   prompt just for the pose, or the user's own. Look at the outline: one closed shape,
   feet on the ground line, nothing else in it.
2. `pose --image <side view> --outline <outline>`, with `--keep` naming features that must
   survive (e.g. "long hooked hand claws").

Features the outline doesn't show tend to get lost. Small signature features (a raised
sickle claw, horns' tips) are expected to go; they become 3D add-ons later. Say so.

**GATE 2: pick the standing side view.** Send a sheet of the candidates. Options: use image
X, re-pose with another seed or outline, fix a detail with `edit` (end the instruction
with "Change nothing else."), or back to Gate 1. After 2 rejected rounds, say what keeps
failing and suggest a different route instead of more rewording.

When one is picked, write its subject to the manifest's `prompt` (show the edit).

## 3. Stylize

Write the `--traits` for this creature following **Writing the traits** in style.md (anchor
the kind of creature, plain exaggeration words, "mouth closed", no small signature
features). Run `stylize` with 2 seeds; seeds vary edits more than they vary `refs`.

Judge: still the same species at a glance, proportions pushed (head, chest, thighs) but
not cartoonish, mouth closed, same standing pose, exact side view (a three-quarter turn
hurts the mesh), no detached bits. Then run `image_tools.py colors` on the pick.

**GATE 3: approve the stylized side view.** Send the sheet. Options: use image X, rerun with
reworded traits, or skip stylizing (use the Gate 2 image). On a yes, show the two colors and
write them to the manifest's `colors`, and the traits to its `traits`.

## 4. Front view

Run `views --image <stylized pick>`. It writes a raw front view, the front view scaled to the
side view's height and ground line, the mirrored right view, and a sheet; it prints the
`shape` command to run next.

Judge the front view: straight on, symmetric, legs under the body, arms tucked, the same
creature and colors as the side view. A slightly turned view or one with the head looking
aside makes a crooked mesh: reroll with `--seed`.

**GATE 4: approve the views.** Send the sheet. Options: approve, reroll the front view, or go
back to Gate 3.

## 5. Raw mesh

Run the printed `shape` command (`--turbo` only if the user asked for speed). Render a
turntable of the raw mesh.

Check against the views: all limbs present, no fused blobs, no missing tail or head,
nothing large floating free, front tile symmetric with legs under the body.

**GATE 5: approve the mesh.** Send the turntable sheet. Options: approve, reroll the shape
seed, or go back to Gate 4.

## 6. Cleanup

Run the cleanup into `work/cleaned/`, never straight into `game/models/`. Take `--tris`,
`--size`, `--color`, `--belly` from the manifest entry (`colors.base`/`colors.belly`, drop
the `#`; an empty belly means `--belly ""`). Pass `--belly-image <stylized pick>` so the
belly line follows the picture. Leave `--yaw` at `auto` and `--sym` at its default (`neg`);
both print what they did. If the manifest lists `parts`, add them next with
`pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_parts.py -- --in <cleaned glb> --out <glb> --part <name[:scale]>`
once per listed part (the script's header lists the parts it knows). Turntable the result with `--asset <id>`.

Check the facing first. If it's wrong, rerun with `--yaw <printed value + 180>` (a head/tail
swap) or the value you work out from the sheet. Then look for: feet splayed or thinned (rerun
with `--sym pos` and compare), thin parts broken into floating bits, holes, belly color in
odd places, a melted look. Knobs: the default `--voxel` is 0.4% of `--size`; smaller (0.005
for a 2-3 m dino) keeps thinner parts, 0.02+ melts arms. More `--tris` keeps detail. Only two
colors survive (base and belly).

**GATE 6: approve the cleaned model.** Send the sheet, with the raw sheet for comparison if
useful. Options: approve, or rerun cleanup with the knob changes you suggest.

## 7. Fit in the game

1. Copy the approved file to `game/models/<id>.glb`.
2. Registry (`game/data/assets.jsonc`): keep `modelYawDegrees` at 0 (the yaw is baked by
   cleanup) and `scale` at 1.0 unless the model must match the collider better. Fit the
   sockets to the mesh using the `--asset` turntable: the saddle sits on the back, turrets
   on the shoulders or back, muzzles at the barrel tip. Scale the collider to the model's
   printed size if they differ a lot (the collider drives the placeholder, collisions and
   hit range). Re-render the `--asset` sheet after each change.
3. `pwsh -NoProfile -File tools/godot.ps1 --headless --path game --import`, then
   `dotnet test tests/Core.Tests`, then run the `/visual-check` steps with `--sockets`.

**GATE 7: approve the fit.** Send the final `--asset` sheet and the in-game screenshot.
List every registry change (before -> after). Options: approve, or adjust specific sockets,
scale or collider.

## 8. Finish

1. Record the final choices in `work/runs/<id>.md`.
2. Report: files written, the prompts and traits, knobs, registry changes, anything still
   imperfect (lost signature features especially).
3. Don't commit on your own. Offer to run the `reviewer` agent and commit
   `game/models/<id>.glb` plus the data changes. **GATE 8:** commit only on a yes.

## Notes

- Everything under `work/` is gitignored and safe to throw away; `game/models/` is
  committed, so only approved models go there. Never copy a user's reference image, or
  anything traced or redrawn from it, outside `work/`.
- The Qwen models and Hunyuan3D don't fit in 8 GB together. Every command frees ComfyUI's
  models first. If a shape run still fails with out-of-memory, retry with `--octree 192`.
- Outputs also land in ComfyUI's own `output/dinoplanet/` folder. That's harmless; leave it.
