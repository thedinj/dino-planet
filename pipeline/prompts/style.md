# Style template

The one place the game's look is defined for image generation (Qwen-Image with the
Lightning 4-step LoRA, or Qwen-Image-Edit when an image goes in). `comfy_gen.py refs` and
`redraw` build their prompts as:

```
[From reference]  subject  Pose  View  Style
```

`subject` is the asset's `prompt` from `manifest.jsonc` (or a variant passed with
`--prompts`). It describes only the creature: anatomy, proportions and colors. Everything
else comes from the blocks below, so change the look here, not per asset. `comfy_gen.py`
reads the code blocks under these headings; keep the headings.

## Style

```
Low-poly 3D video game creature model, flat-shaded faceted polygons, clean solid colors, no texture.
```

## Pose

Neutral, so the model rigs cleanly: feet down, mouth closed, tail level.

```
It stands still in a neutral pose with all feet flat on the ground and its mouth closed.
The tail extends straight back horizontally, level with the spine, and tapers to a point.
```

## View

```
Seen in a flat orthographic side view, exactly perpendicular, facing left: one eye visible,
the far legs hidden behind the near legs. Full body, the whole tail, head and all feet in
frame. Plain pure white background, flat even lighting, nothing else in the image.
```

## From reference

Prefix used when a reference image goes in as image 1: a photo, sketch, toy or art. It
redraws the creature in the game's style, side-on, keeping its shape and pose. Images that
are already in the game's style come back almost unchanged, so it can't straighten up our
own outputs. A second "match this style" image doesn't work either: the model puts both
creatures in the picture.

```
Redraw the creature in image 1 as a fierce low-poly 3D video game creature model, keeping
its body shape and proportions.
```

## Pose transfer

Used by `comfy_gen.py pose`: image 1 is the creature in any pose, image 2 a black outline
of the standing pose. Features the outline doesn't show (a raised claw) tend to get lost;
`--keep` fills `{keep}` with ones to hold on to, e.g. "long hooked hand claws".

```
Redraw the dinosaur from image 1 in the standing pose shown by the outline in image 2: both
feet on the ground, legs under the hips, body level, tail straight back. Keep everything else
about the dinosaur from image 1: its style, colors and head{keep}. Side view facing left,
plain white background, one dinosaur only.
```

## Stylize

Used by `comfy_gen.py stylize`, the step that sets the final look: a smooth, stylized
creature with somewhat exaggerated proportions. The early images keep the low-poly
**Style** above because it gives clean shapes and flat colors to work from. `{species}` is
the asset id; `{traits}` is written per asset (see **Writing the traits**).

```
Restyle this {species} as a creature from a stylized 3D action-adventure game: {traits}.
Smooth 3D render, same standing pose, exact side view facing left, same colors, plain white
background.
```

## Front view

Used by `comfy_gen.py views` with the multi-angle camera LoRA, whose training prompts are
Chinese; the English half says the same thing. "Rotate 90 degrees" only turns about 60
degrees, and asking for a rear view gave the other side profile, so the front view is
asked for directly and the right view is the side view mirrored.

```
将镜头转为正面视角，平视 Turn the camera to a straight-on front view of the dinosaur, eye level,
the dinosaur faces the camera.
```

## Body plans

The canvas follows the body. Long, low animals need a wide canvas, or the model draws an
upright neck. Wide images are padded to a square before the shape step.

| Plan | Canvas | For |
|---|---|---|
| biped | `1024x1024` | raptors, tyrannosaurs, other two-legged theropods |
| quadruped | `1024x1024` | stegosaurs, ceratopsians, ankylosaurs |
| long_quadruped | `1472x832` | sauropods and anything much longer than it is tall |

## Writing the subject

Claude writes the subject from the user's plain request (kept as `request` in the
manifest). Rules learned from testing (details in the run logs):

1. **Spell out the anatomy.** Short prompts fail: this style pulls everything toward a
   T-rex. Name the body plan, the head, neck, arms or front legs, body, legs, tail and any
   signature feature.
2. **Give proportions relative to other parts.** "The head is small, about as long as the
   thigh, low and narrow like a wedge, with a slender upturned snout" works; "small head"
   doesn't.
3. **Describe shapes geometrically.** No metaphors or object nouns for body parts: "sickle
   claw" drew a farming sickle, "barrel-shaped body" drew barrel hoops.
4. **Never name what shouldn't appear.** There is no negative prompt (cfg 1), so "no saddle"
   adds a saddle. Say "bare" and describe only what is there.
5. **No toy words** (toy, figure, figurine, vinyl, plastic): they make it cute and round.
6. **End with the colors**, e.g. "olive green with a tan belly". The cleanup samples its
   colors from the picked image, so the image's colors are the model's colors.
7. **Small features are weak spots.** If one doesn't appear after a couple of wordings,
   add it afterwards with `comfy_gen.py edit` instead of more rewording.
8. **Variety comes from wording, not seeds.** With Lightning, seeds barely change the image.

Dinos are always bare. Riders, saddles, armor and guns are separate assets on sockets.

## Writing the traits

The `--traits` text for `stylize` says how the creature is exaggerated. Rules learned
from the deinonychus run:

1. **Name the kind of creature it stays**, then the exaggerations: "still a lean raptor
   with a long, narrow snout, but with a larger head with a bold brow ridge, ...".
   Without the anchor, strong wording turns anything into a cartoon T. rex.
2. **Exaggerate with plain words** (larger, bold, chunky, muscular). Percentages ("head 20%
   larger") change nothing.
3. **Say "mouth closed"**: strong wording opens the mouth.
4. **Leave out small signature features** such as a sickle claw on the foot: any mention
   draws a detached crescent next to the foot. Those become separate 3D pieces.

Example traits (deinonychus):

```
still a lean raptor with a long, narrow snout, but with a larger head with a bold brow
ridge, mouth closed, a muscular neck and chest, chunky powerful thighs and long hooked hand
claws
```

Example subject (velociraptor):

```
A fierce bare velociraptor with lightweight, birdlike proportions: the head is small, about
as long as the thigh, low and narrow like a wedge, with a slender upturned snout; long arms
folded with three-fingered clawed hands; a lean body balanced over long slim legs; a stiff
rod-like tail as long as the body; olive green with a tan belly.
```
