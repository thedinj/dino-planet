# Asset pipeline

Where things live:

| What                                              | Where                           | In git?                  |
| ------------------------------------------------- | ------------------------------- | ------------------------ |
| ComfyUI + AI models (tens of GB)                  | e.g. `D:\AI\ComfyUI`            | No                       |
| Reference images, raw meshes, turntables, rejects | `work\` at the repo root        | No (gitignored)          |
| Prompts, workflows, manifest, scripts             | `pipeline\`                     | Yes                      |
| Your machine's paths                              | `pipeline\local.settings.jsonc` | No (gitignored)          |
| Final cleaned models                              | `game\models\*.glb`             | Yes (small, no textures) |

Goal: one dino from prompt to a Tunic-style model in Godot.

**Scripted version:** with ComfyUI Desktop running, `/generate-model <id>` in Claude Code runs
the steps below for an asset already registered with `/new-asset`, and stops for your
approval after the reference image, the raw mesh, the cleanup and the in-game fit. The
pieces it uses (also runnable by hand):

- `python pipeline/comfy_gen.py check | refs <id> | shape <id> --left <png>`: drives
  ComfyUI's API with the workflows in `workflows/`.
- `pipeline/blender_turntable.py`: renders a 2x2 review sheet of a `.glb`; `--asset <id>`
  shows it posed as in the game, with sockets.
- `pipeline/blender_cleanup.py --yaw N`: turns the mesh to face the game's forward before sizing.

The manual steps follow.

```
SDXL reference image  ->  Hunyuan3D-2mv shape (.glb)  ->  blender_cleanup.py  ->  Godot + toon shader
     (ComfyUI)                 (ComfyUI)                      (Blender)              (your project)
```

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

Put each file in `Comfy-Desktop\ComfyUI-Shared\models\checkpoints` and rename as shown.

| Model                            | Download                                                                                                | Rename to                               | Size    |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------- | ------- |
| Hunyuan3D-2mv (multi-view shape) | https://huggingface.co/tencent/Hunyuan3D-2mv/blob/main/hunyuan3d-dit-v2-mv/model.fp16.safetensors       | `hunyuan3d-dit-v2-mv.safetensors`       | ~2.5 GB |
| _(optional)_ Hunyuan3D-2mv Turbo | https://huggingface.co/tencent/Hunyuan3D-2mv/blob/main/hunyuan3d-dit-v2-mv-turbo/model.fp16.safetensors | `hunyuan3d-dit-v2-mv-turbo.safetensors` | ~2.5 GB |
| SDXL base (reference images)     | Easiest: open the **SDXL** template in Template Library and let it download                             | —                                       | ~7 GB   |

Restart ComfyUI (or press R to refresh model lists) after downloading.

## 3. Make the reference images (SDXL)

Open **Template Library -> SDXL** (or "SDXL Simple"). Size **1024 x 1024**.

**Positive prompt — front view** (swap the bold part per asset):

```
game asset, single **velociraptor with a small cannon pod strapped to its back**,
full body, side view facing left, standing pose, simple chunky stylized shapes,
low poly toy figure, smooth matte plastic, solid flat colors, no texture detail,
plain pure white background, soft even studio lighting, no shadows, centered, whole body in frame
```

**Negative prompt:**

```
background scenery, ground, grass, shadow, text, watermark, multiple creatures, cropped,
cut off tail, realistic skin, scales detail, fur, photo, motion blur, rider, person
```

Tips:

- Generate the **side view** first; it shows legs and tail best. Make a batch of 4 and pick one.
- For the other views, keep the same seed and change only `side view facing left` to
  `front view` / `back view` / `side view facing right`. They won't match perfectly; that's fine.
  A single good side view alone also works.
- Leave riders and big gear off the body. Those become separate attachment models later.

Save the picks to `work\refs\` (e.g. `raptor_left.png`), and copy the one you're
using into `ComfyUI/input/` so the 3D workflow can load it.

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
- Make sure the SDXL workflow tab isn't holding memory: click **Unload models**
  (in the queue/menu) before running the 3D workflow.
- Last resort: switch ComfyUI to lowvram (step 1.4).

## 5. Clean it up (Blender)

Install Blender 4.2 or newer (blender.org) and put its path in `pipeline\local.settings.jsonc`
(`blenderExe`). Then, from the repo root in a terminal (PowerShell):

```powershell
pwsh -NoProfile -File tools/blender.ps1 -b -P pipeline\blender_cleanup.py -- `
  --in work\raw-meshes\raptor.glb `
  --out game\models\raptor.glb `
  --tris 3000 --size 2.0 --color 6B8E4E --belly C9B98A
```

Knobs worth playing with:

- `--voxel` — chunkiness, in meters. Default is 0.4% of `--size` (0.008 for a 2 m dino), which keeps arms and facets; `0.04`+ is blobby and melts thin parts; `0` = off (decimation may stall).
- `--tris` — 1500–4000 is a good range for a Tunic-scale creature.
- `--flat` — faceted low-poly look instead of smooth.
- Point `--in` at the whole `raw-meshes` folder and `--out` at `game\models` to batch everything.

## 6. See it in the game

No Godot scene work needed: the game builds every asset from its registry entry.

1. Save the cleaned model as `game/models/<id>.glb` (e.g. `raptor.glb`).
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

