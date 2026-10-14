---
name: visual-check
description: Build Dino Planet, run the headless smoke test, take an in-game screenshot and review it. Use after any change that could affect what the game looks like or whether it runs (view code, shaders, assets, spawns, data files).
argument-hint: "[what to look for] [--seed=N] [--frame=N] [--sockets]"
---

# /visual-check

Check that the game runs and looks right. Focus: `$ARGUMENTS` (may be empty). Defaults are
seed 7 and frame 120. If the arguments give `--seed=N` or `--frame=N`, substitute them into
`--seed=` and `--screenshot-frame=` in step 4. Append `--sockets` to the step 4 command when
asked, or when the change is about attachment points.

Godot is run through `tools/godot.ps1`, which reads `godotExe` from
`pipeline/local.settings.jsonc`. If that file or path is missing, stop and tell the user how
to fix it. Never hard-code the Godot path.

## Steps

1. **Build.** `dotnet build DinoPlanet.sln`. Fix compile errors before anything else.

2. **Import** (only if `game/.godot/` is missing or new models were added to `game/models/`):
   `pwsh -NoProfile -File tools/godot.ps1 --headless --path game --import`

3. **Smoke test.**
   `pwsh -NoProfile -File tools/godot.ps1 --headless --path game -- --smoke-frames=600`
   Exit code 0 means no exceptions. On non-zero, read the output for `ERROR`/exception lines,
   fix the cause, and start again from step 1. Don't take a screenshot of a broken build.

4. **Screenshot.** This opens a window for a moment, which is expected:
   `pwsh -NoProfile -File tools/godot.ps1 --path game -- --screenshot=user://shot.png --screenshot-frame=120 --seed=7`
   The game prints `[debug] Screenshot saved to <path>`. It's normally
   `%APPDATA%\Godot\app_userdata\Dino Planet\shot.png`.

5. **Look at it** with the Read tool. Check:
   - The thing that changed is visible and looks intended (the focus above, if one was given).
   - Toon look intact: two-band shading, ink outlines, no pure-black or magenta (missing
     shader or material) surfaces.
   - Scale and placement: dinos stand on the ground, not sunk or floating. Riders sit in
     saddles. Guns sit on turrets and face forward (-Z).
   - Nothing obviously wrong: blank or grey frame, camera inside geometry, z-fighting,
     placeholders where a real model should now load.

6. **Report** in a few lines: smoke result (frames, entities, errors from the `[smoke]`
   line), what the screenshot shows, and anything that looks off with a guess at the cause.
   Send the screenshot to the user if they're likely to want to see it. Don't fix visual
   problems you weren't asked to fix. Point them out instead.
