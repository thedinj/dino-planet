"""
Image helpers for the asset pipeline. Needs Pillow (`pip install pillow`).

  python pipeline/image_tools.py colors <png>              base and belly hex from an image
  python pipeline/image_tools.py sheet  <out.png> <png>... labeled contact sheet for review
  python pipeline/image_tools.py pad    <in.png> <out.png>  pad to a square with white
  python pipeline/image_tools.py align  <ref.png> <in.png> <out.png>
                                       scale in.png's creature to ref's height and ground line
  python pipeline/image_tools.py outline <in.png> <out.png> silhouette outline (pose guide)

comfy_gen.py imports pad(), sheet() and align() from here.
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
except ImportError:
    sys.exit("image_tools.py needs Pillow: pip install pillow")


def pad(src, dst):
    """Pad an image to a square with white, centered. Returns dst."""
    im = Image.open(src).convert("RGB")
    side = max(im.size)
    out = Image.new("RGB", (side, side), "white")
    out.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return dst


def sheet(dst, files, tile=360):
    """Grid of thumbnails labeled A, B, C... with their file names, two or three per row."""
    files = [Path(f) for f in files]
    cols = 2 if len(files) <= 4 else 3
    rows = (len(files) + cols - 1) // cols
    label = 22
    out = Image.new("RGB", (cols * tile, rows * (tile + label)), "white")
    d = ImageDraw.Draw(out)
    for i, f in enumerate(files):
        x, y = (i % cols) * tile, (i // cols) * (tile + label)
        d.text((x + 6, y + 5), f"{chr(65 + i)}. {f.stem}", fill="black")
        im = Image.open(f).convert("RGB")
        im.thumbnail((tile - 8, tile - 8))
        out.paste(im, (x + (tile - im.width) // 2, y + label + (tile - im.height) // 2))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return dst


def _mask(im):
    """White-on-black mask of the creature on a white background: pixels clearly darker than
    white that aren't the near-black floor shadow some views get."""
    r, g, b = im.convert("RGB").split()
    darkest = ImageChops.darker(ImageChops.darker(r, g), b)
    brightest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return ImageChops.multiply(darkest.point(lambda v: 255 if v < 215 else 0),
                               brightest.point(lambda v: 255 if v > 70 else 0))


def align(ref, src, dst):
    """Scale src so its creature is as tall as ref's and stands on the same ground line,
    centered on a white canvas of ref's size. Multi-view shape inputs must agree in scale.
    Returns dst."""
    ref_im, im = Image.open(ref).convert("RGB"), Image.open(src).convert("RGB")
    rb, ib = _mask(ref_im).getbbox(), _mask(im).getbbox()
    if not rb or not ib:
        sys.exit(f"align: no creature found in {ref if not rb else src}")
    s = (rb[3] - rb[1]) / (ib[3] - ib[1])
    crop = im.crop(ib).resize((round((ib[2] - ib[0]) * s), round((ib[3] - ib[1]) * s)), Image.Resampling.LANCZOS)
    out = Image.new("RGB", ref_im.size, "white")
    out.paste(crop, (round((ref_im.width - crop.width) / 2), rb[3] - crop.height))
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return dst


def outline(src, dst, width=5):
    """Black outline of the creature's silhouette on white: the pose guide for
    comfy_gen.py pose. Returns dst."""
    mask = _mask(Image.open(src))
    # Fill holes (gaps between legs stay open: they touch the background).
    filled = ImageOps.expand(mask, 1, 0)  # a background border, so one fill reaches all of it
    ImageDraw.floodfill(filled, (0, 0), 128)
    solid = filled.point(lambda v: 0 if v == 128 else 255).crop((1, 1, mask.width + 1, mask.height + 1))
    inner = solid.filter(ImageFilter.MinFilter(width if width % 2 else width + 1))
    edge = ImageChops.subtract(solid, inner)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    ImageOps.invert(edge).convert("RGB").save(dst)
    return dst


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def colors(src, k=4):
    """(base, belly) as hex strings from a creature on a white background. base is the
    biggest color cluster; belly is a clearly lighter cluster with at least 8% of the
    pixels, or "" if there isn't one."""
    im = Image.open(src).convert("RGB")
    im.thumbnail((160, 160))
    px = [p for p in im.getdata()
          if not (_lum(p) > 170 and max(p) - min(p) < 30)  # white background, soft shadows
          and _lum(p) > 35]                              # outlines, eyes, claws
    if not px:
        sys.exit(f"{src}: no non-background pixels")

    # Plain k-means with a deterministic start: centers spread over the brightness range.
    px.sort(key=_lum)
    centers = [px[int((i + 0.5) * len(px) / k)] for i in range(k)]
    for _ in range(12):
        groups = [[] for _ in centers]
        for p in px:
            best = min(range(len(centers)), key=lambda j: sum((p[c] - centers[j][c]) ** 2 for c in range(3)))
            groups[best].append(p)
        centers = [tuple(sum(p[c] for p in g) / len(g) for c in range(3)) if g else centers[j]
                   for j, g in enumerate(groups)]

    clusters = sorted(((len(g), centers[j]) for j, g in enumerate(groups) if g), reverse=True)
    base = clusters[0][1]

    def dist(a, b):
        return sum((a[c] - b[c]) ** 2 for c in range(3)) ** 0.5

    belly = ""
    lighter = [c for n, c in clusters[1:]
               if n >= 0.08 * len(px) and _lum(c) > _lum(base) + 20 and dist(c, base) > 40]
    if lighter:
        belly = _hex(max(lighter, key=_lum))
    return _hex(base), belly


def _hex(c):
    return "#" + "".join(f"{round(v):02X}" for v in c)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("colors", "sheet", "pad", "align", "outline"):
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "colors":
        base, belly = colors(args[0])
        print(f"base {base}\nbelly {belly or '(none)'}")
    elif cmd == "sheet":
        print(f"sheet {sheet(args[0], args[1:])}")
    elif cmd == "align":
        print(f"wrote {align(args[0], args[1], args[2])}")
    elif cmd == "outline":
        print(f"wrote {outline(args[0], args[1])}")
    else:
        print(f"wrote {pad(args[0], args[1])}")


if __name__ == "__main__":
    main()
