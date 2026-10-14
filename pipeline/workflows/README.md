# ComfyUI workflows

Save the workflows the pipeline uses here so they're versioned with the game.

For each one, once it works in ComfyUI:

1. Settings (gear) -> enable **Dev mode** (shows the API export option).
2. Workflow menu -> **Export (API)**. Save it here, e.g.
   - `reference_sdxl.json` — prompt to reference image
   - `shape_hunyuan3d_mv.json` — reference image(s) to raw mesh
3. Also save the normal (UI) export with a `.ui.json` suffix, so it can be reopened and edited.

The API-format files are what the batch script will send to ComfyUI's HTTP API, swapping in the
prompt, seed and image names for each asset in `../manifest.jsonc`.
