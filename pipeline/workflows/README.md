# ComfyUI workflows

API-format workflows that `../comfy_gen.py` sends to ComfyUI's HTTP API:

| File | Does | Nodes the script edits (by title) |
|---|---|---|
| `reference_qwen.json` | prompt -> Qwen-Image reference image(s) | `positive`, `latent`, `sampler`, `save` |
| `edit_qwen.json` | image(s) + instruction -> Qwen-Image-Edit-2509 image | `image1`, `image2`, `scale2`, `positive`, `negative`, `latent`, `sampler`, `save`; `lora` and `sampling` when an extra LoRA is stacked |
| `redraw_qwen_canny.json` | guide image + prompt -> Qwen-Image image following the guide's canny edges (InstantX ControlNet Union) | `positive`, `guide`, `control`, `latent`, `sampler`, `save`, `save_edges` |
| `shape_hunyuan3d_mv.json` | reference view(s) -> raw Hunyuan3D-2mv mesh | `checkpoint`, `image_<view>`, `encode_<view>`, `conditioning`, `sampler`, `decode`, `save` |

The script finds nodes by their `_meta.title`, not by id. Views that aren't passed to `shape`
are removed from the graph before it's queued, and so is `image2` when an edit has one
input. `check` also verifies the model files named in the loader nodes titled `unet`,
`clip`, `vae`, `lora`, `checkpoint` and `controlnet`, plus the multi-angle LoRA that
`comfy_gen.py views` adds to the edit graph (as a `LoraLoaderModelOnly` after `lora`).

`redraw_qwen_canny.json` was written by hand in API format (no `.ui.json`); it runs 20
steps at cfg 2.5 with a negative prompt and no Lightning LoRA. With Lightning it's about
twice as fast with the same shape, but has a hard cast shadow and muddier faces.

The edit workflow samples from an empty latent at full denoise, so its output size is set
by `latent`, not by the input image.

To change a workflow in ComfyUI's editor and bring it back:

1. Settings (gear) -> enable **Dev mode** (shows the API export option).
2. Load and edit the workflow, then Workflow menu -> **Export (API)** and save it over the file here.
3. Keep the node titles in the table above (right-click a node -> Title), or the script can't find them.
4. Also save the normal (UI) export with a `.ui.json` suffix, so it can be reopened and edited.

Check the result with `python pipeline/comfy_gen.py check`.
