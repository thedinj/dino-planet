# Style template

The one place the game's look is defined for image generation. Every reference prompt is this
template with an asset's `describe` text from `manifest.jsonc` dropped into `{describe}`.
Change the look here, not per asset.

## Positive

```
game asset, single {describe}, full body, {view}, standing pose,
simple chunky stylized shapes, low poly toy figure, smooth matte plastic,
solid flat colors, no texture detail, plain pure white background,
soft even studio lighting, no shadows, centered, whole body in frame
```

`{view}` is one of:

| View | Text |
|---|---|
| left | `side view facing left` |
| right | `side view facing right` |
| front | `front view` |
| back | `back view` |

## Negative

```
background scenery, ground, grass, shadow, text, watermark, multiple creatures, cropped,
cut off tail, realistic skin, scales detail, fur, photo, motion blur, rider, person
```

For weapons and props, drop `rider, person` and `cut off tail` from the negative.

## Settings

- SDXL base, 1024 x 1024, batch of 4.
- Generate `left` first; reuse its seed for the other views.
- Keep riders and gear off the dinos. They are separate assets attached to sockets.
