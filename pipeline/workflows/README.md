# ComfyUI workflows

API-format workflows that `../comfy_gen.py` sends to ComfyUI's HTTP API:

| File | Does | Nodes the script edits (by title) |
|---|---|---|
| `reference_sdxl.json` | prompt -> 4 SDXL reference images | `positive`, `negative`, `latent`, `sampler`, `save` |
| `shape_hunyuan3d_mv.json` | reference view(s) -> raw Hunyuan3D-2mv mesh | `checkpoint`, `image_<view>`, `encode_<view>`, `conditioning`, `sampler`, `decode`, `save` |

The script finds nodes by their `_meta.title`, not by id. Views that aren't passed to `shape`
are removed from the graph before it's queued.

To change a workflow in ComfyUI's editor and bring it back:

1. Settings (gear) -> enable **Dev mode** (shows the API export option).
2. Load and edit the workflow, then Workflow menu -> **Export (API)** and save it over the file here.
3. Keep the node titles in the table above (right-click a node -> Title), or the script can't find them.
4. Also save the normal (UI) export with a `.ui.json` suffix, so it can be reopened and edited.

Check the result with `python pipeline/comfy_gen.py check`.
