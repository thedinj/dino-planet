"""
Add procedural parts to a cleaned model: features too small or thin for the image and shape
models, which draw them detached or melt them (a raptor's sickle claw).

Run headless on a cleaned .glb (Blender 4.x / 5.x):

  blender -b -P blender_parts.py -- --in work/cleaned/deinonychus.glb --out work/cleaned/deinonychus_parts.glb
                                    --part sickle_claw[:scale] [--color 2E2A26]

Parts (more to come as assets need them):
  sickle_claw  a raised, hooked claw on the inner toe of each foot, curving forward and down.
               Its size follows the model's height; the optional :scale multiplies it.
Pass --part once per part. The manifest's "parts" list uses the same "name:scale" form.

The part is joined into the model's mesh with its own vertex color, so the file stays one
mesh with two-plus colors. Expects the cleanup's orientation: Z up, head toward +Y, feet
at z = 0, mirrored about x = 0.
"""

import argparse
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_cleanup import export, hex_to_linear, reset_scene  # noqa: E402


PARTS = ("sickle_claw",)


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--part", action="append", required=True, help="name[:scale]")
    p.add_argument("--color", default="2E2A26")
    return p.parse_args(argv)


def load_model(path):
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"expected one mesh in {path}, found {len(meshes)}")
    obj = meshes[0]
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = mw
    for o in list(bpy.context.scene.objects):
        if o is not obj:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def find_inner_toe(verts, height, side):
    """Where the claw sits on one foot (side = +1 or -1 in x): on top of the inner toe.

    The foot is the mesh near the ground on that side; the inner toe is its part nearest
    the midline. Returns a point inside the toe (centre x, y, half its height) and the foot's
    length."""
    foot = [v for v in verts if v.z < 0.05 * height and v.x * side > 0]
    if not foot:
        raise RuntimeError("no foot found near the ground")
    xs = sorted(abs(v.x) for v in foot)
    inner_limit = xs[0] + 0.3 * (xs[-1] - xs[0])
    toe = [v for v in foot if abs(v.x) <= inner_limit]
    foot_len = max(v.y for v in foot) - min(v.y for v in foot)
    x = sum(v.x for v in toe) / len(toe)
    y = sum(v.y for v in toe) / len(toe)
    mid = 0.5 * max(v.z for v in toe)  # halfway up the toe: the claw grows out of it
    return Vector((x, y, mid)), foot_len


def add_sickle_claw(bm, color_layer, color, height, scale, toe):
    """A tapered tube swept along a hook: up from the toe, then forward and down."""
    r = 0.045 * height * scale                 # radius of the hook's arc
    thick = 0.42 * r                           # tube radius at the base
    base = toe
    centre = base + Vector((0, r, 0))
    steps, around = 18, 10
    rings = []
    for i in range(steps + 1):
        t = i / steps
        phi = math.radians(165) * t            # 0 at the base, sweeping over the top and down
        p = centre + Vector((0, -r * math.cos(phi), r * math.sin(phi)))
        tangent = Vector((0, math.sin(phi), math.cos(phi)))
        side_axis = Vector((1, 0, 0))
        normal = tangent.cross(side_axis).normalized()
        rad = thick * (1 - t) ** 0.8
        ring = []
        for k in range(around):
            a = 2 * math.pi * k / around
            # Flattened sideways, like a blade.
            off = side_axis * (0.6 * rad * math.cos(a)) + normal * (rad * math.sin(a))
            ring.append(bm.verts.new(p + off))
        rings.append(ring)
    faces = []
    for i in range(steps):
        for k in range(around):
            a, b = rings[i][k], rings[i][(k + 1) % around]
            c, d = rings[i + 1][(k + 1) % around], rings[i + 1][k]
            faces.append(bm.faces.new((a, b, c, d)))
    faces.append(bm.faces.new(list(reversed(rings[0]))))  # base cap, buried in the toe
    bmesh.ops.remove_doubles(bm, verts=rings[-1], dist=1e-6)  # the tip collapses to a point
    for f in faces:
        if f.is_valid:
            f.smooth = True
            for loop in f.loops:
                loop[color_layer] = color


def main():
    a = parse_args()
    reset_scene()
    obj = load_model(a.inp)
    me = obj.data
    height = max(v.co.z for v in me.vertices)
    if not me.color_attributes:
        raise RuntimeError("model has no vertex colors; run blender_cleanup.py first")
    layer_name = me.color_attributes[0].name

    bm = bmesh.new()
    bm.from_mesh(me)
    byte_layer = bm.loops.layers.color.get(layer_name)
    color_layer = byte_layer or bm.loops.layers.float_color.get(layer_name)
    if color_layer is None:
        raise RuntimeError(f"can't find color layer {layer_name} as corner colors")
    # bmesh byte color layers hold sRGB values; float layers hold linear ones.
    h = a.color.lstrip("#")
    color = ([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]) if byte_layer else hex_to_linear(a.color)
    verts = [v.co.copy() for v in bm.verts]

    for spec in a.part:
        part, _, scale = spec.partition(":")
        scale = float(scale or 1.0)
        if part not in PARTS:
            raise SystemExit(f"unknown part '{part}'; known: {', '.join(PARTS)}")
        if part == "sickle_claw":
            for side in (1, -1):
                toe, foot_len = find_inner_toe(verts, height, side)
                add_sickle_claw(bm, color_layer, color, height, scale, toe)
                print(f"[parts] sickle claw on the {'+x' if side > 0 else '-x'} foot at "
                      f"({toe.x:.3f}, {toe.y:.3f}, {toe.z:.3f}); foot {foot_len:.3f} long")

    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    export(a.out)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    print(f"[ok] {os.path.basename(a.inp)} + {', '.join(a.part)} -> {a.out}  ({tris} tris)")


if __name__ == "__main__":
    main()
