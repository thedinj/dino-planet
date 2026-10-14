"""
Blender cleanup for AI-generated meshes -> chunky, Tunic-style game assets.

Takes the dense, messy .glb that Hunyuan3D writes to ComfyUI/output/mesh and produces
a small, clean, game-ready .glb with flat palette vertex colors (no textures).

Run headless (Blender 4.x / 5.x):

  blender -b -P blender_cleanup.py -- --in raw.glb --out dino_raptor.glb
  blender -b -P blender_cleanup.py -- --in C:/ComfyUI/output/mesh --out C:/game/assets/raw_models

Options:
  --in        .glb file, or a folder (every .glb inside is processed)
  --out       output .glb file (single input) or folder (folder input)
  --tris      target triangle count            (default 3000)
  --size      longest dimension in meters      (default 2.0)
  --voxel     voxel remesh size before decimating, 0 = off (default 0.02 of size).
              Bigger = blobbier/chunkier, smaller = more detail. This also fixes the
              holes and non-manifold junk AI meshes usually have.
  --color     base color hex                   (default 6B8E4E, jungle green)
  --belly     underside color hex, "" = off    (default C9B98A, sandy belly)
  --flat      flat shading (faceted). Default is smooth; the toon shader handles the look.
"""

import argparse
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tris", type=int, default=3000)
    p.add_argument("--size", type=float, default=2.0)
    p.add_argument("--voxel", type=float, default=None)
    p.add_argument("--color", default="6B8E4E")
    p.add_argument("--belly", default="C9B98A")
    p.add_argument("--flat", action="store_true")
    return p.parse_args(argv)


def hex_to_linear(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def to_lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return [to_lin(c) for c in srgb] + [1.0]


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_and_join(path):
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh found in {path}")

    # Bake parent transforms, drop empties, join into one object.
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)

    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def strip_materials(obj):
    obj.data.materials.clear()
    for uv in list(obj.data.uv_layers):
        obj.data.uv_layers.remove(uv)


def normalize_size(obj, size):
    dims = obj.dimensions
    longest = max(dims.x, dims.y, dims.z)
    if longest > 0:
        s = size / longest
        obj.scale = (s, s, s)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def apply_modifier(obj, mod):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def remesh_and_decimate(obj, voxel, target_tris):
    if voxel and voxel > 0:
        m = obj.modifiers.new("Remesh", "REMESH")
        m.mode = "VOXEL"
        m.voxel_size = voxel
        m.use_smooth_shade = False
        apply_modifier(obj, m)

    current = tri_count(obj)
    if current > target_tris:
        m = obj.modifiers.new("Decimate", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = max(0.001, target_tris / current)
        m.use_collapse_triangulate = True
        apply_modifier(obj, m)

    # Merge stray verts and drop loose bits.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()


def ground_and_center(obj):
    # Blender is Z-up: put the feet at z=0 and center x/y on the origin.
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    min_v = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    max_v = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    offset = Vector(((min_v.x + max_v.x) / 2, (min_v.y + max_v.y) / 2, min_v.z))
    for v in obj.data.vertices:
        v.co -= offset
    obj.location = (0, 0, 0)


def paint_vertex_colors(obj, base_hex, belly_hex):
    mesh = obj.data
    base = hex_to_linear(base_hex)
    belly = hex_to_linear(belly_hex) if belly_hex else None

    attr = mesh.color_attributes.new(name="Col", type="BYTE_COLOR", domain="CORNER")
    mesh.color_attributes.active_color = attr

    for poly in mesh.polygons:
        # Faces pointing mostly downward get the belly color.
        col = belly if (belly and poly.normal.z < -0.35) else base
        for li in poly.loop_indices:
            attr.data[li].color = col

    # Material that reads the vertex colors, so the glTF exporter keeps them.
    mat = bpy.data.materials.new("VertexColorMat")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0
    mesh.materials.append(mat)


def set_shading(obj, flat):
    for p in obj.data.polygons:
        p.use_smooth = not flat


def export(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    kwargs = dict(filepath=path, export_format="GLB", use_selection=False, export_apply=True)
    try:
        # Blender 4.2+ vertex color option
        bpy.ops.export_scene.gltf(**kwargs, export_vertex_color="ACTIVE")
    except TypeError:
        bpy.ops.export_scene.gltf(**kwargs)


def process(src, dst, a):
    reset_scene()
    obj = import_and_join(src)
    strip_materials(obj)
    normalize_size(obj, a.size)
    voxel = a.voxel if a.voxel is not None else a.size * 0.02
    remesh_and_decimate(obj, voxel, a.tris)
    ground_and_center(obj)
    set_shading(obj, a.flat)
    paint_vertex_colors(obj, a.color, a.belly)
    export(dst)
    print(f"[ok] {os.path.basename(src)} -> {dst}  ({tri_count(obj)} tris)")


def main():
    a = parse_args()
    if os.path.isdir(a.inp):
        os.makedirs(a.out, exist_ok=True)
        files = sorted(f for f in os.listdir(a.inp) if f.lower().endswith(".glb"))
        for f in files:
            try:
                process(os.path.join(a.inp, f), os.path.join(a.out, f), a)
            except Exception as e:  # keep going on bad meshes
                print(f"[fail] {f}: {e}")
    else:
        process(a.inp, a.out, a)


if __name__ == "__main__":
    main()
