"""
Image helpers for the asset pipeline. Needs Pillow (`pip install pillow`).

  python pipeline/image_tools.py colors <png>              base and belly hex from an image
  python pipeline/image_tools.py sheet  <out.png> <png>... labeled contact sheet for review
  python pipeline/image_tools.py pad    <in.png> <out.png>  pad to a square with white

comfy_gen.py imports pad() and sheet() from here.
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
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
    if len(sys.argv) < 3 or sys.argv[1] not in ("colors", "sheet", "pad"):
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "colors":
        base, belly = colors(args[0])
        print(f"base {base}\nbelly {belly or '(none)'}")
    elif cmd == "sheet":
        print(f"sheet {sheet(args[0], args[1:])}")
    else:
        print(f"wrote {pad(args[0], args[1])}")


if __name__ == "__main__":
    main()
