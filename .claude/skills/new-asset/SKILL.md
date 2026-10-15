---
name: new-asset
description: Register a new game asset (dino, weapon, rider, prop or projectile) in Dino Planet's data files - the pipeline manifest entry, the asset registry entry and the tuning entry - then run the tests. Generates no model; that's /generate-model. Use when the user asks to add a new dino, gun, prop or other asset.
argument-hint: <asset-id> [kind] [short description]
---

# /new-asset

Register one asset so the game knows about it and draws a placeholder for it. This step
generates no art. It writes the data entries that `/generate-model <id>` reads to make the model.

Arguments: `$ARGUMENTS`. The first word is the id. Ids are `snake_case`, so turn
`raptor-scout` into `raptor_scout`. Anything after it is the kind and/or a description.
If the kind isn't given, infer it from the name (`*cannon`, `*gun` → weapon; dino species →
dino). Ask only if it's genuinely unclear.

## 1. Look before writing

Read all three files, plus the closest existing asset of the same kind to copy from:

- `pipeline/manifest.jsonc`: what the asset pipeline should generate.
- `game/data/assets.jsonc`: the registry, the contract between pipeline and game.
- `game/data/tuning.jsonc`: gameplay numbers.

Stop and tell the user if the id already exists in any of them.

## 2. Add the entries

Keep each file's existing style: comments, key order and alignment. Insert the new entry
next to others of the same kind.

**`game/data/assets.jsonc`** (always):
- `id`, `kind`, `model: "res://models/<id>.glb"` (the file needn't exist yet).
- `collider` with `radius` and `height` in meters. The placeholder is drawn from it, so
  size it sensibly relative to its siblings (raptor 0.6 × 1.4, trex 1.3 × 3.2).
- Sockets the kind needs, in the asset's own space (Y up, facing -Z, meters):
  - dino: `saddle` plus at least one `turret*`. Scale positions from the nearest sibling
    by collider height. Side mounts get `yawDegrees`.
  - weapon: `muzzle` at the barrel tip (negative Z).
  - rider, prop and projectile: usually none.
- Optional `tint` only if it should differ from the kind's default.

**`pipeline/manifest.jsonc`** (dino, weapon, rider and prop; skip projectiles, which have no model):
- `request`: the user's own description, as they wrote it (or the species name if they gave
  none).
- `bodyPlan` for dinos: `biped`, `quadruped` or `long_quadruped` (see the table in
  `pipeline/prompts/style.md`).
- `prompt`: leave it `""`. `/generate-model` writes it with the user at its first gate.
- `colors.base` / `colors.belly` hex (placeholders; `/generate-model` samples the real ones),
  `size` (meters, roughly the collider's largest dimension), `tris` (dino 3000–4000,
  weapon ~800, prop ~1000).

**`game/data/tuning.jsonc`**:
- dino or rider → `movers.<id>`: `moveSpeed`, `turnRateDegrees`, `maxHealth`. Place it
  between its neighbours (a scout is faster and frailer than a raptor).
- weapon → `weapons.<id>`: every field the existing weapons have. `projectile` must be an
  asset id that exists in the registry (a DataTest enforces this).
- prop and projectile → nothing.

Don't touch the spawns in `TestArena` unless the user asked for the asset to appear in the
arena. If they did, that's a Core change and needs a test.

## 3. Verify

1. `dotnet test tests/Core.Tests`. The DataTests load the real files, so this catches
   broken JSONC and dangling projectile ids.
2. If a test fails, fix the data. Don't loosen the test.
3. Report what you added, with the numbers you chose and why, and say that the model file is
   still to be generated (`pipeline/README.md`). Suggest `/visual-check` if it spawns in the arena.
