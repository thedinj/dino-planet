"""
Render a .glb from four sides into one 2x2 contact sheet, for reviewing generated meshes.

Run headless (Blender 4.2+):

  blender -b -P pipeline/blender_turntable.py -- --in work/raw-meshes/deinonychus_s1.glb
          [--out work/turntables/deinonychus_s1.png] [--size 512] [--asset deinonychus]

--out defaults to <workDir>/turntables/<input name>.png (workDir from local.settings.jsonc).
--asset applies that registry entry's modelYawDegrees and scale from game/data/assets.jsonc
and draws its sockets as magenta balls, so the sheet shows the model as the game will.
--yaw N overrides modelYawDegrees, to try a value before writing it to the registry.

Sheet layout (the asset's own facing; game forward = glTF -Z):
  top-left: front     top-right: left side
  bottom-left: back   bottom-right: three-quarter (front-left, from above)

Orthographic camera, white background, Workbench engine with cavity and outlines. Vertex
colors are shown when the mesh has them (cleaned models), otherwise a flat grey.
A thin red bar on the ground marks the front edge of the bounding box.
"""

import argparse
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfy_gen import load_jsonc  # noqa: E402  (stdlib-only helper shared with the ComfyUI driver)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def work_dir():
    settings = os.path.join(REPO, "pipeline", "local.settings.jsonc")
    work = load_jsonc(settings).get("workDir", "work") if os.path.exists(settings) else "work"
    return os.path.abspath(os.path.join(REPO, work))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out")
    p.add_argument("--size", type=int, default=512)
    p.add_argument("--asset", help="asset id: apply its yaw/scale and draw its sockets")
    p.add_argument("--yaw", type=float, help="with --asset: override modelYawDegrees")
    return p.parse_args(argv)


def import_mesh(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        sys.exit(f"No mesh in {path}")
    return meshes


def paint(obj, rgba):
    """Flat color that shows in both Workbench color modes (material and vertex)."""
    mat = bpy.data.materials.new(obj.name + "_mat")
    mat.diffuse_color = rgba
    obj.data.materials.append(mat)
    attr = obj.data.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    attr.data.foreach_set("color", list(rgba) * len(obj.data.vertices))
    obj.data.color_attributes.active_color = attr


def apply_asset(meshes, asset_id, yaw_override=None):
    """Pose the model like AssetFactory does and add socket markers. Returns the markers."""
    registry = load_jsonc(os.path.join(REPO, "game", "data", "assets.jsonc"))
    asset = next((a for a in registry["assets"] if a["id"] == asset_id), None)
    if asset is None:
        sys.exit(f"'{asset_id}' is not in game/data/assets.jsonc")
    scale = asset.get("scale", 1.0)
    yaw_deg = asset.get("modelYawDegrees", 0) if yaw_override is None else yaw_override
    yaw = math.radians(yaw_deg)
    # Godot yaw about +Y is a rotation about Blender +Z with the same sign.
    pose = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Scale(scale, 4)
    for o in meshes:
        o.matrix_world = pose @ o.matrix_world

    markers = []
    lo, hi = bounds(meshes)
    radius = max(hi - lo) * 0.025
    print(f"[turntable] {asset_id}: modelYawDegrees={yaw_deg:g} scale={scale} "
          f"collider r={asset['collider']['radius']} h={asset['collider']['height']}")
    for name, sock in asset.get("sockets", {}).items():
        x, y, z = (c * scale for c in sock["position"])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=(x, -z, y))  # Godot -> Blender axes
        ball = bpy.context.active_object
        ball.name = "socket_" + name
        paint(ball, (1.0, 0.1, 0.8, 1.0))
        markers.append(ball)
        print(f"[turntable] socket {name} at {sock['position']}")
    return markers


def bounds(objs):
    """World-space box from the actual vertices (a rotated bound_box would overstate it)."""
    pts = []
    for o in objs:
        co = np.empty(len(o.data.vertices) * 3, dtype=np.float64)
        o.data.vertices.foreach_get("co", co)
        co = np.c_[co.reshape(-1, 3), np.ones(len(o.data.vertices))]
        pts.append((co @ np.array(o.matrix_world).T)[:, :3])
    pts = np.concatenate(pts)
    return Vector(pts.min(axis=0)), Vector(pts.max(axis=0))


def add_front_marker(lo, hi):
    # glTF -Z (game forward) imports as Blender +Y.
    width = hi.x - lo.x
    bpy.ops.mesh.primitive_cube_add(location=((lo.x + hi.x) / 2, hi.y + 0.02 * width, lo.z))
    bar = bpy.context.active_object
    bar.scale = (width / 2, 0.01 * width, 0.005 * width)
    paint(bar, (0.9, 0.1, 0.1, 1.0))


def setup_scene(meshes, size):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    shading = scene.display.shading
    shading.light = "STUDIO"
    has_colors = any(o.data.color_attributes for o in meshes)
    shading.color_type = "VERTEX" if has_colors else "MATERIAL"
    for o in meshes:
        if not has_colors:
            o.data.materials.clear()
    shading.show_cavity = True
    shading.show_object_outline = True
    shading.background_type = "VIEWPORT"
    shading.background_color = (1.0, 1.0, 1.0)
    scene.view_settings.view_transform = "Standard"

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def aim(cam, center, direction, frame):
    direction = direction.normalized()
    cam.location = center + direction * frame * 4
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = frame * 1.15
    cam.data.clip_end = frame * 10


def render_views(cam, lo, hi, tmp_base):
    center = (lo + hi) / 2
    extent = max(hi - lo)
    diagonal = (hi - lo).length  # angled views need room for the whole box
    views = [
        ("front", Vector((0, 1, 0))),
        ("left", Vector((-1, 0, 0))),
        ("back", Vector((0, -1, 0))),
        ("three_quarter", Vector((-1, 1, 0.8))),
    ]
    paths = []
    for name, d in views:
        aim(cam, center, d, extent if name != "three_quarter" else diagonal)
        path = f"{tmp_base}_{name}.png"
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        paths.append(path)
    return paths


def contact_sheet(paths, out, size):
    tiles = []
    for p in paths:
        img = bpy.data.images.load(p)
        px = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        tiles.append(px.reshape(size, size, 4))  # rows go bottom-up in Blender
        bpy.data.images.remove(img)
        os.remove(p)
    # Bottom-up rows: the second pair goes in the lower half.
    sheet = np.concatenate([np.concatenate(tiles[2:4], axis=1), np.concatenate(tiles[0:2], axis=1)], axis=0)
    sheet[:, size - 1:size + 1] = (0.6, 0.6, 0.6, 1)
    sheet[size - 1:size + 1, :] = (0.6, 0.6, 0.6, 1)
    image = bpy.data.images.new("sheet", size * 2, size * 2, alpha=True)
    image.pixels.foreach_set(sheet.ravel())
    image.filepath_raw = out
    image.file_format = "PNG"
    image.save()


def main():
    a = parse_args()
    src = os.path.abspath(a.inp)
    out = os.path.abspath(a.out) if a.out else os.path.join(
        work_dir(), "turntables", os.path.splitext(os.path.basename(src))[0] + ".png")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    meshes = import_mesh(src)
    markers = apply_asset(meshes, a.asset, a.yaw) if a.asset else []
    lo, hi = bounds(meshes)
    add_front_marker(lo, hi)
    cam = setup_scene(meshes, a.size)
    view_lo, view_hi = bounds(meshes + markers)  # frame sockets that stick out too
    paths = render_views(cam, view_lo, view_hi, os.path.splitext(out)[0] + "_tmp")
    contact_sheet(paths, out, a.size)
    dims = hi - lo
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    print(f"[turntable] {out}")
    print(f"[turntable] size x={dims.x:.3f} y(up)={dims.z:.3f} z={dims.y:.3f}  tris={tris}")


main()
