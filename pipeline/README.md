# Asset pipeline

Where things live:

| What                                              | Where                           | In git?                  |
| ------------------------------------------------- | ------------------------------- | ------------------------ |
| ComfyUI + AI models (tens of GB)                  | e.g. `D:\AI\ComfyUI`            | No                       |
| Reference images, raw meshes, turntables, rejects | `work\` at the repo root        | No (gitignored)          |
| Prompts, workflows, manifest, scripts             | `pipeline\`                     | Yes                      |
| Your machine's paths                              | `pipeline\local.settings.jsonc` | No (gitignored)          |
| Final cleaned models                              | `game\models\*.glb`             | Yes (small, no textures) |

Goal: one dino from a description or a picture to a game model in Godot: symmetric,
stylized, smooth-shaded at about 12k triangles, in a neutral standing pose for rigging.

**Scripted version (the normal way):** with ComfyUI Desktop running,
`/generate-model <id> [plain description] [--ref=<photo or sketch>]` in Claude Code runs the
steps below for an asset already registered with `/new-asset`. Claude writes the prompts,
and you approve each stage. The pieces it uses (also runnable by hand):

- `python pipeline/comfy_gen.py check | refs | redraw | pose | stylize | views | edit | shape`:
  drives ComfyUI's API with the workflows in `workflows/`. Prompts come from
  `prompts/style.md`. Run it with `--help` for every option.
- `python pipeline/image_tools.py colors | sheet | pad | align | outline`: samples model
  colors, makes review sheets, pads wide images to a square, scales a view to match
  another, traces a pose outline. Needs Pillow (`pip install pillow`).
- `pipeline/blender_turntable.py`: renders a 2x2 review sheet of a `.glb`; `--asset <id>`
  shows it posed as in the game, with sockets.
- `pipeline/blender_cleanup.py`: turns (automatically by default), sizes, straightens and
  mirrors, remeshes, decimates and colors the raw mesh.

### The chain

The shape model (Hunyuan3D-2mv) meshes whatever it's shown, pose included, and from one side
view it has to guess the width, which comes out bent and lopsided. So the pictures are
brought to a standing side view first, and a front view is added:

```
 1. side view      refs (from a description), or
                   redraw (a drawing or photo, following its outline with a ControlNet)
 2. pose           only if it isn't standing: pose transfer onto a standing outline
 3. stylize        restyle with exaggerated, game-like proportions
 4. views          front view (multi-angle camera LoRA), scaled to match; right = mirrored side
 5. shape          Hunyuan3D-2mv from left + front + right -> raw .glb
 6. cleanup        straighten, mirror one half, remesh, 12k tris, two vertex colors with the
                   belly line copied from the stylized picture; then blender_parts.py adds
                   small features the AI steps can't make (the sickle claw)
 7. Godot          game/models/<id>.glb, sockets fitted in assets.jsonc
```

Each image step takes about 2 to 5 minutes on an 8 GB card, `redraw` up to 10 (it runs 20
steps without the Lightning LoRA), the shape about 2 to 3, the cleanup seconds. Example, the
deinonychus from a 1969 pen drawing:

```powershell
python pipeline/comfy_gen.py redraw  deinonychus --guide work/inputs/deinonychus/drawing.png --flip --clean 1.8
python pipeline/image_tools.py outline <a standing picture of a similar animal> work/refs/deinonychus/outline_stand.png
python pipeline/comfy_gen.py pose    deinonychus --image work/refs/deinonychus/redraw.png --outline work/refs/deinonychus/outline_stand.png
python pipeline/comfy_gen.py stylize deinonychus --image work/refs/deinonychus/posed.png --traits "still a lean raptor with ..."
python pipeline/comfy_gen.py views   deinonychus --image work/refs/deinonychus/stylized.png
python pipeline/comfy_gen.py shape   deinonychus --left ...stylized.png --front ...stylized_front.png --right ...stylized_right.png
pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_cleanup.py -- --in work/raw-meshes/deinonychus_s<seed>.glb `
  --out work/cleaned/deinonychus.glb --size 3.0 --color 80957D --belly B8CE8D --belly-image work/refs/deinonychus/stylized.png
pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline/blender_parts.py -- --in work/cleaned/deinonychus.glb `
  --out work/cleaned/deinonychus_parts.glb --part sickle_claw:1.3
```

Things learned the hard way (details in `prompts/style.md`):

- Text edits can't re-pose a creature reliably (claws vanish, bipeds turn four-legged);
  pose transfer onto an outline can. It loses small features the outline doesn't show.
- Small signature features (a raptor's sickle claw) don't survive: the image models draw
  them detached, and the cleanup melts them. They're to become separate 3D pieces.
- A generated right view is no better than the mirrored side view, and asking the camera
  LoRA for a rear view gave the right profile instead.

The manual, in-ComfyUI version of steps 1 and 5 follows.

Pieces involved:

| File                            | What it does                                                           |
| ------------------------------- | ---------------------------------------------------------------------- |
| `pipeline/blender_cleanup.py`   | Decimates, remeshes, scales, grounds and vertex-colors the raw AI mesh |
| `game/shaders/toon.gdshader`    | Two-band toon lighting with cool shadows and a rim light               |
| `game/shaders/outline.gdshader` | Ink outline, used as the toon material's Next Pass                     |
| `game/data/assets.jsonc`        | Registry entry per asset: model path, scale, facing, collider, sockets |

---

## 1. Install ComfyUI (Windows, NVIDIA)

> These steps assume an NVIDIA card. If yours is AMD, stop here and say so — the install is different.

1. Update your NVIDIA driver (GeForce Experience / NVIDIA App, or nvidia.com).
2. Download **ComfyUI Desktop** from https://www.comfy.org/download and run the installer.
    - GPU: choose **NVIDIA (CUDA)**.
    - Install location: anywhere **outside the repo** with **40 GB+ free**, e.g.
      `D:\AI\ComfyUI`. Avoid OneDrive folders. Models download into its
      `models\` folder, so nothing large ever lands in the repo.
    - Put that path in `pipeline\local.settings.jsonc` (copy the `.example` file) so scripts can find it.
    - If it offers to reuse an old ComfyUI install's models, say yes if you still have them.
3. Launch it. It opens a browser-style window with a default workflow. Click **Run** once to
   make sure it works (it may ask to download a model first).
4. **8 GB tweak:** Settings (gear) -> Server Config -> set VRAM management to **lowvram** if
   you hit "out of memory" errors later. Leave it on default until then.

Find your folders: Settings -> About (or the folder icon in the sidebar) shows the base path.
Everything below says `ComfyUI/` for that path.

## 2. Download the models

About 57 GB in all. Put each file in the ComfyUI `models\` subfolder shown. The names must
match exactly; `python pipeline/comfy_gen.py check` reports anything missing.

| Model | Folder | File | Size |
|---|---|---|---|
| Qwen-Image (reference images) | `diffusion_models` | [`qwen_image_fp8_e4m3fn.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/tree/main/split_files/diffusion_models) | 20 GB |
| Qwen-Image-Edit-2509 (redraw a photo or sketch, fix-ups, extra views) | `diffusion_models` | [`qwen_image_edit_2509_fp8_e4m3fn.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/tree/main/split_files/diffusion_models) | 20 GB |
| Qwen text encoder (both) | `text_encoders` | [`qwen_2.5_vl_7b_fp8_scaled.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/tree/main/split_files/text_encoders) | 9 GB |
| Qwen VAE (both) | `vae` | [`qwen_image_vae.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/tree/main/split_files/vae) | 0.3 GB |
| Lightning 4-step LoRA | `loras` | [`Qwen-Image-Lightning-4steps-V1.0.safetensors`](https://huggingface.co/lightx2v/Qwen-Image-Lightning/tree/main) | 1.7 GB |
| Lightning 4-step LoRA for Edit | `loras` | [`Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors`](https://huggingface.co/lightx2v/Qwen-Image-Lightning/tree/main/Qwen-Image-Edit-2509) | 0.8 GB |
| InstantX ControlNet Union for Qwen-Image (`redraw`) | `controlnet` | [`Qwen-Image-InstantX-ControlNet-Union.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-InstantX-ControlNets/tree/main/split_files/controlnet) | 3.5 GB |
| Multiple-angles camera LoRA for Edit (`views`) | `loras` | [`Qwen-Edit-2509-Multiple-angles.safetensors`](https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/tree/main/split_files/loras) | 0.2 GB |
| Hunyuan3D-2mv (multi-view shape) | `checkpoints` | [`model.fp16.safetensors`](https://huggingface.co/tencent/Hunyuan3D-2mv/blob/main/hunyuan3d-dit-v2-mv/model.fp16.safetensors), renamed to `hunyuan3d-dit-v2-mv.safetensors` | 2.5 GB |
| _(optional)_ Hunyuan3D-2mv Turbo | `checkpoints` | [`model.fp16.safetensors`](https://huggingface.co/tencent/Hunyuan3D-2mv/blob/main/hunyuan3d-dit-v2-mv-turbo/model.fp16.safetensors), renamed to `hunyuan3d-dit-v2-mv-turbo.safetensors` | 2.5 GB |

This runs on an 8 GB card with 32 GB of RAM: ComfyUI keeps the Qwen weights in RAM and
streams them to the GPU. Restart ComfyUI (or press R to refresh model lists) after
downloading.

## 3. Make the reference image (Qwen-Image)

The prompt is `prompts/style.md`'s blocks around a detailed description of the creature.
Read its **Writing the subject** rules before writing one by hand: short prompts all turn
into a T-rex. Settings: 4 steps, cfg 1, euler / simple, shift 3.1, with the Lightning LoRA
(`workflows/reference_qwen.json` has them). Canvas 1024 x 1024, or 1472 x 832 for long,
low animals (sauropods), padded to a square with white before the shape step.

To start from a photo, toy, sketch or piece of art instead, use the Qwen-Image-Edit
workflow (`workflows/edit_qwen.json`) with the image as image 1 and style.md's
**From reference** prefix in front of the prompt. It keeps the image's shape and pose, so
pick one standing with its feet down and its mouth closed.

Tips:

- One side view facing left is enough. Seeds barely change Qwen's output; reword instead.
- Leave riders and gear off the body. Those become separate attachment models.
- A small feature that won't appear (a raptor's raised toe claw) can be added afterwards
  with an edit: "...carries one very large, dark, hooked claw. Change nothing else."

Save the pick to `work\refs\<id>\` and copy it into `ComfyUI/input/` so the 3D workflow
can load it.

## 4. Generate the shape (Hunyuan3D-2mv)

1. Template Library -> search **"HY 3D 2.0 MV"** -> open it.
   (No template? Update ComfyUI: Settings -> About -> Update.)
2. In **Image Only Checkpoint Loader**, pick `hunyuan3d-dit-v2-mv.safetensors`.
3. Load your images into the **Load Image** nodes (front / left / back / right).
   Bypass (Ctrl+B) any view you don't have; only one view is required.
4. Run. The mesh lands in `ComfyUI/output/mesh/` as a `.glb`. Copy the ones worth keeping to
   `work\raw-meshes\` (gitignored, so it never gets committed).

**If it runs out of memory (8 GB):**

- In the VAE decode node, lower **octree_resolution** (try 256). You'll decimate later anyway.
- Make sure the Qwen workflow isn't holding memory: click **Unload models**
  (in the queue/menu) before running the 3D workflow.
- Last resort: switch ComfyUI to lowvram (step 1.4).

## 5. Clean it up (Blender)

Install Blender 4.2 or newer (blender.org) and put its path in `pipeline\local.settings.jsonc`
(`blenderExe`). Then, from the repo root in a terminal (PowerShell):

```powershell
pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline\blender_cleanup.py -- `
  --in work\raw-meshes\deinonychus_s7.glb `
  --out work\cleaned\deinonychus.glb `
  --size 3.0 --color 80957D --belly B8CE8D
```

Knobs worth playing with:

- `--voxel` — chunkiness, in meters. Default is 0.4% of `--size` (0.008 for a 2 m dino), which keeps arms and facets; `0.04`+ is blobby and melts thin parts; `0` = off (decimation may stall).
- `--tris` — default 12000, smooth-shaded. Fewer (3000-4000) with `--flat` gives a faceted
  low-poly look instead.
- `--belly-image` — the stylized side view the mesh came from. The belly color then follows
  the picture's belly line (projected from the side, kept off up-facing surfaces). Without
  it, the belly is wherever the surface faces down, which comes out patchy on smooth meshes.
- `--sym` — `neg` (default) or `pos` picks which half of the body is mirrored onto the other,
  after straightening the spine; if the feet splay or thin with one, try the other. `off`
  leaves the mesh as generated (gear and props).
- `--yaw` — `auto` (default) turns the mesh's long axis to face forward and prints the yaw
  it chose; if the head ends up backwards, rerun with that number + 180.
- `python pipeline/image_tools.py colors <png>` suggests `--color` and `--belly` from the
  reference image.
- Point `--in` at a folder and `--out` at another to clean every `.glb` in it with the same
  options (one `--belly-image` for all, and no parts: run `blender_parts.py` per model after).

## 6. See it in the game

No Godot scene work needed: the game builds every asset from its registry entry.

1. Save the cleaned model as `game/models/<id>.glb` (e.g. `deinonychus.glb`).
2. Check `game/data/assets.jsonc` has an entry with that `model` path. New asset? Add one;
   copy an existing entry of the same `kind`.
3. Let Godot import it: open the editor once, or run `godot --headless --path game --import`.
4. Run the game and press **F3** to show socket markers (pink dots). Adjust in `assets.jsonc`:
    - `modelYawDegrees` until the model faces the same way as the placeholder did (forward = -Z),
    - `scale` until it matches the collider size,
    - socket `position`s until the saddle, turrets and muzzle sit where they should.
5. If the colors look washed out, set `vertex_color_is_srgb` to `true` at the top of `game/shaders/toon.gdshader`.

---

## What's next once this works

- A manifest listing every asset, and a script that drives ComfyUI's API to batch
  reference images and shapes overnight, then writes the `assets.jsonc` entries.
- Dinos generated in parts (body, head, tail, legs) with sockets for procedural animation.
- Automatic first-guess socket placement from the mesh shape (top of back, front of head).

