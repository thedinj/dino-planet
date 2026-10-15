"""
Blender cleanup for AI-generated meshes -> chunky, Tunic-style game assets.

Takes the dense, messy .glb that Hunyuan3D writes to ComfyUI/output/mesh and produces
a small, clean, game-ready .glb with flat palette vertex colors (no textures).

Run headless (Blender 4.x / 5.x):

  blender -b -P blender_cleanup.py -- --in raw.glb --out velociraptor.glb
  blender -b -P blender_cleanup.py -- --in C:/ComfyUI/output/mesh --out C:/game/assets/raw_models

Options:
  --in        .glb file, or a folder (every .glb inside is processed)
  --out       output .glb file (single input) or folder (folder input)
  --tris      target triangle count            (default 3000)
  --size      longest dimension in meters      (default 2.0)
  --voxel     voxel remesh size before decimating, 0 = off (default 0.004 of size).
              Bigger = blobbier/chunkier (0.02 of size already melts thin arms), smaller =
              more detail. It also fixes the holes and non-manifold junk AI meshes usually
              have; with 0 the decimator can stall far above --tris on those meshes.
  --color     base color hex                   (default 6B8E4E, jungle green)
  --belly     underside color hex, "" = off    (default C9B98A, sandy belly)
  --flat      flat shading (faceted). Default is smooth; the toon shader handles the look.
  --min-island  drop disconnected pieces smaller than this fraction of the mesh's faces
              (default 0.02), and flat pieces under 3% of the model's height whatever their
              size. Removes background noise and floor shadows that the shape generator
              turned into geometry. 0 = keep everything.
  --yaw       degrees to turn the mesh about the up axis before sizing, so the output faces
              the game's forward (-Z). Same sign as modelYawDegrees in assets.jsonc; find the
              value with blender_turntable.py --asset <id> --yaw N. "auto" (the default)
              lines the mesh's long axis up with forward and picks the end nearest
              --yaw-prior; it prints the yaw it chose.
  --yaw-prior the yaw "auto" leans toward (default -135: single side-view meshes from
              Hunyuan3D-2mv come out turned about that far).
"""

import argparse
import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector


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
    p.add_argument("--yaw", default="auto")
    p.add_argument("--yaw-prior", type=float, default=-135.0)
    p.add_argument("--min-island", type=float, default=0.02)
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


def drop_floaters(obj, min_fraction):
    """Delete connected pieces with fewer than min_fraction of all faces, and flat
    sheets (a floor shadow turned into geometry) whatever their size."""
    if min_fraction <= 0:
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    if not bm.verts:
        bm.free()
        raise RuntimeError("mesh is empty")

    zs = [v.co.z for v in bm.verts]
    flat_limit = 0.03 * (max(zs) - min(zs))

    seen, islands = set(), []
    for face in bm.faces:
        if face in seen:
            continue
        seen.add(face)
        stack, island = [face], []
        while stack:
            f = stack.pop()
            island.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        islands.append(island)
    limit = min_fraction * len(bm.faces)

    def height(island):
        z = [v.co.z for f in island for v in f.verts]
        return max(z) - min(z)

    doomed = [i for i in islands if len(i) < limit or height(i) < flat_limit]
    drop = [f for island in doomed for f in island]
    if drop:
        bmesh.ops.delete(bm, geom=drop, context="FACES")
        print(f"[cleanup] dropped {len(drop)} faces in {len(doomed)} floating or flat pieces")

    bm.to_mesh(obj.data)
    bm.free()


def cut_floor(obj, fraction=0.02):
    """Slice off a thin slab at ground level and cap the cut.

    A floor shadow in the reference image often becomes a thin sheet fused to the feet,
    which the island pass can't separate. Run this on the clean, closed mesh the voxel
    remesh produces: the level cut then leaves simple loops that cap reliably. It flattens
    the soles very slightly."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if not bm.verts:
        bm.free()
        raise RuntimeError("mesh is empty after the remesh; try a smaller --voxel")
    zs = [v.co.z for v in bm.verts]
    top = min(zs) + fraction * (max(zs) - min(zs))
    before = len(bm.faces)
    cut = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                                 plane_co=(0, 0, top), plane_no=(0, 0, 1), clear_inner=True)
    if any(isinstance(g, bmesh.types.BMEdge) for g in cut["geom_cut"]):
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    open_edges = sum(1 for e in bm.edges if e.is_boundary)
    bm.to_mesh(obj.data)
    bm.free()
    print(f"[cleanup] floor cut: {before} -> {len(obj.data.polygons)} faces, {open_edges} open edges left")


def wrap180(deg):
    return (deg + 180.0) % 360.0 - 180.0


def auto_yaw(obj, prior):
    """Yaw that turns the mesh's long ground-plane axis onto forward (Blender +Y, which the
    glTF export makes -Z), choosing between the two ends by closeness to prior.

    The long axis comes from the 2x2 covariance of the vertices' ground-plane positions.
    Which end is the head can't be told from the shape alone, hence the prior. Vertices in
    the bottom 15% are skipped: a floor-shadow sheet fused to the feet would hide the axis."""
    if not obj.data.vertices:
        raise RuntimeError("mesh is empty")
    zs = [v.co.z for v in obj.data.vertices]
    floor = min(zs) + 0.15 * (max(zs) - min(zs))
    vs = [v for v in obj.data.vertices if v.co.z > floor]
    n = len(vs)
    if n == 0:
        return prior
    mx = sum(v.co.x for v in vs) / n
    my = sum(v.co.y for v in vs) / n
    sxx = sum((v.co.x - mx) ** 2 for v in vs) / n
    syy = sum((v.co.y - my) ** 2 for v in vs) / n
    sxy = sum((v.co.x - mx) * (v.co.y - my) for v in vs) / n
    axis = math.degrees(0.5 * math.atan2(2 * sxy, sxx - syy))  # long axis angle from +X
    spread = math.sqrt((sxx - syy) ** 2 + 4 * sxy ** 2)
    elongation = (sxx + syy + spread) / max(1e-12, sxx + syy - spread)
    if elongation < 1.5:
        print(f"[cleanup] auto yaw: no clear long axis (elongation {elongation:.2f}); using the prior {prior:g}")
        return prior
    candidates = [wrap180(90.0 - axis), wrap180(-90.0 - axis)]
    yaw = min(candidates, key=lambda c: abs(wrap180(c - prior)))
    margin = abs(abs(wrap180(candidates[0] - prior)) - abs(wrap180(candidates[1] - prior)))
    note = "  (ends nearly tied: check the turntable)" if margin < 30 else ""
    print(f"[cleanup] auto yaw: {yaw:.0f} (long axis {axis:.0f} deg, candidates "
          f"{candidates[0]:.0f}/{candidates[1]:.0f}, prior {prior:g}){note}")
    return yaw


def turn(obj, yaw_degrees):
    # Godot yaw about +Y is a rotation about Blender +Z with the same sign.
    # Transform the mesh data directly: glTF imports use quaternion rotation mode, so setting
    # rotation_euler would be silently ignored.
    if yaw_degrees:
        obj.data.transform(Matrix.Rotation(math.radians(yaw_degrees), 4, "Z"))
        obj.data.update()
        bpy.context.view_layer.update()


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


def remesh_and_decimate(obj, voxel, target_tris, min_island=0.02):
    if voxel and voxel > 0:
        m = obj.modifiers.new("Remesh", "REMESH")
        m.mode = "VOXEL"
        m.voxel_size = voxel
        m.use_smooth_shade = False
        apply_modifier(obj, m)
        if min_island > 0:
            cut_floor(obj)
        drop_floaters(obj, min_island)  # sheet remnants the cut left behind
    else:
        # Without a remesh, weld first: raw AI meshes often have unshared vertices, which
        # stops the decimator from collapsing edges.
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
        bm.to_mesh(obj.data)
        bm.free()

    # One collapse pass can stall well above the target on non-manifold AI meshes; repeat
    # until it gets close or stops making progress.
    for _ in range(6):
        current = tri_count(obj)
        if current <= target_tris * 1.05:
            break
        m = obj.modifiers.new("Decimate", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = max(0.001, target_tris / current)
        m.use_collapse_triangulate = True
        apply_modifier(obj, m)
        if tri_count(obj) > current * 0.95:
            break

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
    drop_floaters(obj, a.min_island)
    turn(obj, auto_yaw(obj, a.yaw_prior) if a.yaw == "auto" else float(a.yaw))
    normalize_size(obj, a.size)
    voxel = a.voxel if a.voxel is not None else a.size * 0.004
    remesh_and_decimate(obj, voxel, a.tris, a.min_island)
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
