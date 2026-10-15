# ComfyUI workflows

API-format workflows that `../comfy_gen.py` sends to ComfyUI's HTTP API:

| File | Does | Nodes the script edits (by title) |
|---|---|---|
| `reference_qwen.json` | prompt -> Qwen-Image reference image(s) | `positive`, `latent`, `sampler`, `save` |
| `edit_qwen.json` | image(s) + instruction -> Qwen-Image-Edit-2509 image | `image1`, `image2`, `scale2`, `positive`, `negative`, `latent`, `sampler`, `save` |
| `shape_hunyuan3d_mv.json` | reference view(s) -> raw Hunyuan3D-2mv mesh | `checkpoint`, `image_<view>`, `encode_<view>`, `conditioning`, `sampler`, `decode`, `save` |

The script finds nodes by their `_meta.title`, not by id. Views that aren't passed to `shape`
are removed from the graph before it's queued, and so is `image2` when an edit has one
input. `check` also verifies the model files named in the loader nodes titled `unet`,
`clip`, `vae`, `lora` and `checkpoint`.

The edit workflow samples from an empty latent at full denoise, so its output size is set
by `latent`, not by the input image.

To change a workflow in ComfyUI's editor and bring it back:

1. Settings (gear) -> enable **Dev mode** (shows the API export option).
2. Load and edit the workflow, then Workflow menu -> **Export (API)** and save it over the file here.
3. Keep the node titles in the table above (right-click a node -> Title), or the script can't find them.
4. Also save the normal (UI) export with a `.ui.json` suffix, so it can be reopened and edited.

Check the result with `python pipeline/comfy_gen.py check`.
