"""
Drive ComfyUI's HTTP API for the asset pipeline. Python 3.10+; refs and non-square shape
inputs also need Pillow (for the review sheet and padding, via image_tools.py).

  python pipeline/comfy_gen.py check
  python pipeline/comfy_gen.py refs  <id> [--prompts work/refs/<id>/prompts.json]
                                     [--ref <image>] [--batch 1] [--seed N]
  python pipeline/comfy_gen.py edit  <id> --image <png> [--image2 <png>] --prompt "..." --name N
  python pipeline/comfy_gen.py shape <id> --left work/refs/<id>/<name>_1.png
                                     [--front F] [--back B] [--right R]
                                     [--seed N] [--turbo] [--octree 256] [--steps N] [--cfg X]

refs   builds each prompt from pipeline/prompts/style.md around a subject: the asset's
       manifest "prompt", or each {"name", "prompt"} in a --prompts JSON list. Plain prompts
       run workflows/reference_qwen.json (Qwen-Image) on the canvas of the asset's bodyPlan.
       With --ref (a photo, sketch, art or an earlier image to redraw) it runs
       workflows/edit_qwen.json (Qwen-Image-Edit) instead. Saves
       work/refs/<id>/<name>_<n>.png, the full prompt as <name>.txt, and sheet.png.
edit   runs a free-form Qwen-Image-Edit instruction on one image (add a feature, show
       another view) and saves work/refs/<id>/<name>.png at the input's size.
shape  uploads the chosen views (padding non-square ones to a square), runs
       workflows/shape_hunyuan3d_mv.json and saves work/raw-meshes/<id>_s<seed>.glb.
       Views you don't pass are left out of the graph.

The ComfyUI URL comes from pipeline/local.settings.jsonc ("comfyUiUrl"). Workflow nodes are
found by their _meta.title, so a re-exported workflow keeps working if the titles are kept.
Every run prints the files it wrote as "wrote <path>" lines.
"""

import argparse
import json
import random
import re
import struct
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
REPO = PIPELINE.parent
VIEWS = ["front", "left", "back", "right"]


# ---------------------------------------------------------------- data files

def load_jsonc(path):
    """JSON with // and /* */ comments and trailing commas. Comment markers inside strings
    (e.g. "http://...") are kept."""
    text = Path(path).read_text(encoding="utf-8")
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            out.append(c)
            i += 1
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))


def settings():
    path = PIPELINE / "local.settings.jsonc"
    if not path.exists():
        sys.exit(f"Missing {path.relative_to(REPO)}. Copy local.settings.example.jsonc and edit it.")
    return load_jsonc(path)


def work_dir(cfg):
    return (REPO / cfg.get("workDir", "work")).resolve()


def rel(path):
    try:
        return Path(path).relative_to(REPO)
    except ValueError:
        return path


def manifest_entry(asset_id):
    for a in load_jsonc(PIPELINE / "manifest.jsonc")["assets"]:
        if a["id"] == asset_id:
            return a
    sys.exit(f"'{asset_id}' is not in pipeline/manifest.jsonc. Add it first (/new-asset).")


def style_template():
    """The prompt blocks and the body-plan canvas table from prompts/style.md."""
    md = (PIPELINE / "prompts" / "style.md").read_text(encoding="utf-8")

    def block(heading):
        m = re.search(rf"^## {heading}\s*\n.*?```\s*\n(.*?)```", md, re.S | re.M)
        if not m:
            sys.exit(f"prompts/style.md has no code block under '## {heading}'.")
        return " ".join(m.group(1).split())

    blocks = {h: block(h) for h in ("Style", "Pose", "View", "From reference")}
    canvas = {plan: (int(w), int(h)) for plan, w, h in
              re.findall(r"^\|\s*(\w+)\s*\|\s*`(\d+)x(\d+)`\s*\|", md, re.M)}
    return blocks, canvas


def build_prompt(subject, with_ref):
    blocks, _ = style_template()
    parts = [blocks["From reference"]] if with_ref else []
    parts += [" ".join(subject.split()), blocks["Pose"], blocks["View"], blocks["Style"]]
    return " ".join(parts)


def canvas_for(entry):
    _, canvas = style_template()
    plan = entry.get("bodyPlan")
    if plan not in canvas:
        sys.exit(f"'{entry['id']}' needs a bodyPlan in manifest.jsonc, one of: {', '.join(canvas)}.")
    return canvas[plan]


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"{path} is not a PNG.")
    return struct.unpack(">II", head[16:24])


def to_png(path, out_dir):
    """Uploads go in as PNG; convert anything else (a phone photo, a .jpg) with Pillow."""
    path = Path(path)
    if not path.exists():
        sys.exit(f"No such image: {path}")
    if path.suffix.lower() == ".png":
        return path
    from PIL import Image
    dest = out_dir / f"{path.stem}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.open(path).convert("RGB").save(dest)
    return dest


# ---------------------------------------------------------------- ComfyUI API

class Comfy:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    def _req(self, path, data=None, headers=None, timeout=30):
        req = urllib.request.Request(self.url + path, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            sys.exit(f"ComfyUI {path} -> HTTP {e.code}: {body[:2000]}")
        except urllib.error.URLError as e:
            sys.exit(f"Can't reach ComfyUI at {self.url} ({e.reason}). Is ComfyUI Desktop running?")

    def get(self, path):
        return json.loads(self._req(path))

    def post(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        raw = self._req(path, body, {"Content-Type": "application/json"})
        return json.loads(raw) if raw.strip() else {}

    def upload(self, file_path, name):
        boundary = uuid.uuid4().hex
        parts = []
        for key, value in (("overwrite", "true"), ("type", "input"), ("subfolder", "dinoplanet")):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f"Content-Type: image/png\r\n\r\n".encode() + Path(file_path).read_bytes() + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        res = json.loads(self._req("/upload/image", b"".join(parts),
                                   {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
        return f"{res['subfolder']}/{res['name']}" if res.get("subfolder") else res["name"]

    def run(self, workflow, label, timeout_min=20):
        """Queue a workflow, wait for it, return its history entry."""
        res = self.post("/prompt", {"prompt": workflow, "client_id": self.client_id})
        prompt_id = res["prompt_id"]
        print(f"queued {label} ({prompt_id})", flush=True)
        start = time.time()
        while True:
            time.sleep(2)
            if time.time() - start > timeout_min * 60:
                sys.exit(f"{label}: no result after {timeout_min} min. Check ComfyUI's console.")
            hist = self.get(f"/history/{prompt_id}")
            if prompt_id in hist:
                entry = hist[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                    detail = msgs[0][1] if msgs else status
                    sys.exit(f"{label} failed in ComfyUI: "
                             f"{detail.get('exception_message', detail) if isinstance(detail, dict) else detail}")
                print(f"done {label} in {time.time() - start:.0f}s", flush=True)
                return entry

    def outputs(self, entry):
        """Every file a history entry produced, as dicts with filename/subfolder/type."""
        for node_out in entry.get("outputs", {}).values():
            for value in node_out.values():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and "filename" in item:
                            yield item

    def download(self, item, dest):
        q = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                                    "type": item.get("type", "output")})
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self._req(f"/view?{q}", timeout=300))
        print(f"wrote {rel(dest)}", flush=True)

    def free(self):
        """Unload ComfyUI's models. The Qwen models and Hunyuan3D don't fit in 8 GB together."""
        self.post("/free", {"unload_models": True, "free_memory": True})


def load_workflow(name):
    return json.loads((PIPELINE / "workflows" / name).read_text(encoding="utf-8"))


def node(workflow, title):
    for node_id, n in workflow.items():
        if n.get("_meta", {}).get("title") == title:
            return node_id, n
    sys.exit(f"Workflow has no node titled '{title}'.")


def pngs(comfy, entry):
    return [i for i in comfy.outputs(entry) if i["filename"].lower().endswith(".png")]


# ---------------------------------------------------------------- commands

# Model-loader node titles, the input naming the file, and the ComfyUI folder it lives in.
MODEL_NODES = {"unet": ("unet_name", "diffusion_models"), "clip": ("clip_name", "text_encoders"),
               "vae": ("vae_name", "vae"), "lora": ("lora_name", "loras"),
               "checkpoint": ("ckpt_name", "checkpoints")}
WORKFLOWS = ("reference_qwen.json", "edit_qwen.json", "shape_hunyuan3d_mv.json")


def cmd_check(comfy, _args):
    stats = comfy.get("/system_stats")
    print(f"ComfyUI {stats['system']['comfyui_version']} at {comfy.url}")
    for d in stats.get("devices", []):
        print(f"  {d['name']}: {d['vram_total'] // 2**20} MB VRAM, {d['vram_free'] // 2**20} MB free")
    nodes = set(comfy.get("/object_info"))
    folders = {}
    ok = True
    for wf in WORKFLOWS:
        for n in load_workflow(wf).values():
            if n["class_type"] not in nodes:
                print(f"  MISSING node {n['class_type']} (used by {wf})")
                ok = False
            model = MODEL_NODES.get(n.get("_meta", {}).get("title"))
            if model:
                field, folder = model
                if folder not in folders:
                    folders[folder] = set(comfy.get(f"/models/{folder}"))
                if n["inputs"][field] not in folders[folder]:
                    print(f"  MISSING {folder}/{n['inputs'][field]} (used by {wf})")
                    ok = False
    if "hunyuan3d-dit-v2-mv-turbo.safetensors" not in folders.get("checkpoints", set()):
        print("  note: turbo checkpoint not installed; --turbo won't work")
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("  MISSING Pillow for this Python (pip install pillow)")
        ok = False
    print("ready" if ok else "not ready")
    sys.exit(0 if ok else 1)


def set_edit_images(comfy, wf, image1, image2, asset_id):
    """Upload image1, and image2 or drop its nodes, into an edit_qwen.json graph."""
    node(wf, "image1")[1]["inputs"]["image"] = comfy.upload(image1, f"{asset_id}_image1.png")
    if image2:
        node(wf, "image2")[1]["inputs"]["image"] = comfy.upload(image2, f"{asset_id}_image2.png")
    else:
        for title in ("image2", "scale2"):
            del wf[node(wf, title)[0]]
        for title in ("positive", "negative"):
            node(wf, title)[1]["inputs"].pop("image2")


def cmd_refs(comfy, args):
    entry = manifest_entry(args.id)
    if entry["kind"] != "dino":
        sys.exit(f"refs only has a dino template so far; '{args.id}' is a {entry['kind']}.")
    out_dir = work_dir(settings()) / "refs" / args.id
    if args.prompts:
        variants = json.loads((REPO / args.prompts).read_text(encoding="utf-8"))
    elif entry.get("prompt"):
        variants = [{"name": "manifest", "prompt": entry["prompt"]}]
    else:
        sys.exit(f"'{args.id}' has no manifest prompt yet; write one or pass --prompts.")
    ref = to_png(REPO / args.ref, out_dir / "inputs") if args.ref else None
    width, height = canvas_for(entry)
    seed = args.seed if args.seed is not None else random.randrange(2**32)
    out_dir.mkdir(parents=True, exist_ok=True)

    comfy.free()
    written = []
    for v in variants:
        prompt = build_prompt(v["prompt"], ref is not None)
        if ref:
            wf = load_workflow("edit_qwen.json")
            set_edit_images(comfy, wf, ref, None, args.id)
            node(wf, "positive")[1]["inputs"]["prompt"] = prompt
        else:
            wf = load_workflow("reference_qwen.json")
            node(wf, "positive")[1]["inputs"]["text"] = prompt
        node(wf, "latent")[1]["inputs"].update(width=width, height=height, batch_size=args.batch)
        node(wf, "sampler")[1]["inputs"]["seed"] = seed
        name = v["name"] + ("_ref" if ref else "")
        node(wf, "save")[1]["inputs"]["filename_prefix"] = f"dinoplanet/{args.id}_{name}"

        print(f"[{name}] {prompt}")
        # Number on from earlier runs of the same variant, so nothing is overwritten.
        n = max((int(m.group(1)) for f in out_dir.glob(f"{name}_*.png")
                 if (m := re.fullmatch(rf"{re.escape(name)}_(\d+)\.png", f.name))), default=0)
        for item in pngs(comfy, comfy.run(wf, f"{args.id} {name}")):
            n += 1
            dest = out_dir / f"{name}_{n}.png"
            comfy.download(item, dest)
            written.append(dest)
        (out_dir / f"{name}.txt").write_text(prompt + "\n", encoding="utf-8")

    if written:
        from image_tools import sheet
        print(f"sheet {rel(sheet(out_dir / 'sheet.png', written))}")


def cmd_edit(comfy, args):
    manifest_entry(args.id)  # fail early on a typo'd id
    out_dir = work_dir(settings()) / "refs" / args.id
    image1 = to_png(REPO / args.image, out_dir / "inputs")
    image2 = to_png(REPO / args.image2, out_dir / "inputs") if args.image2 else None
    width, height = png_size(image1)

    wf = load_workflow("edit_qwen.json")
    set_edit_images(comfy, wf, image1, image2, args.id)
    node(wf, "positive")[1]["inputs"]["prompt"] = args.prompt
    # Same size as the input, rounded down to the latent grid.
    node(wf, "latent")[1]["inputs"].update(width=width // 16 * 16, height=height // 16 * 16, batch_size=1)
    node(wf, "sampler")[1]["inputs"]["seed"] = args.seed if args.seed is not None else random.randrange(2**32)
    node(wf, "save")[1]["inputs"]["filename_prefix"] = f"dinoplanet/{args.id}_{args.name}"

    comfy.free()
    images = pngs(comfy, comfy.run(wf, f"{args.id} edit {args.name}"))
    if not images:
        sys.exit("ComfyUI finished but returned no image.")
    comfy.download(images[0], out_dir / f"{args.name}.png")
    (out_dir / f"{args.name}.txt").write_text(args.prompt + "\n", encoding="utf-8")


def cmd_shape(comfy, args):
    manifest_entry(args.id)  # fail early on a typo'd id
    views = {v: getattr(args, v) for v in VIEWS if getattr(args, v)}
    if not views:
        sys.exit("Pass at least one view image, e.g. --left work/refs/<id>/manifest_1.png")
    seed = args.seed if args.seed is not None else random.randrange(2**32)

    wf = load_workflow("shape_hunyuan3d_mv.json")
    cond_id, cond = node(wf, "conditioning")
    for v in VIEWS:
        img_id, img = node(wf, f"image_{v}")
        enc_id, _ = node(wf, f"encode_{v}")
        if v in views:
            path = REPO / views[v]
            w, h = png_size(path)
            if w != h:  # the shape model crops to a square; pad so the tail and neck survive
                from image_tools import pad
                path = pad(path, work_dir(settings()) / "refs" / args.id / "padded" / f"{path.stem}_{v}.png")
            img["inputs"]["image"] = comfy.upload(path, f"{args.id}_{v}.png")
        else:
            del wf[img_id], wf[enc_id]
            cond["inputs"].pop(v, None)

    sampler = node(wf, "sampler")[1]["inputs"]
    sampler["seed"] = seed
    if args.turbo:
        node(wf, "checkpoint")[1]["inputs"]["ckpt_name"] = "hunyuan3d-dit-v2-mv-turbo.safetensors"
        sampler["steps"] = 10
    if args.steps:
        sampler["steps"] = args.steps
    if args.cfg is not None:
        sampler["cfg"] = args.cfg
    node(wf, "decode")[1]["inputs"]["octree_resolution"] = args.octree
    node(wf, "save")[1]["inputs"]["filename_prefix"] = f"dinoplanet/{args.id}"

    comfy.free()
    print(f"views: {', '.join(views)}  seed: {seed}  octree: {args.octree}")
    entry_out = comfy.run(wf, f"{args.id} shape")
    meshes = [i for i in comfy.outputs(entry_out) if i["filename"].lower().endswith(".glb")]
    if not meshes:
        sys.exit("ComfyUI finished but returned no .glb.")
    comfy.download(meshes[0], work_dir(settings()) / "raw-meshes" / f"{args.id}_s{seed}.glb")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", help="override comfyUiUrl from local.settings.jsonc")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="verify ComfyUI is up and has the models and nodes")

    r = sub.add_parser("refs", help="generate side-view reference images")
    r.add_argument("id")
    r.add_argument("--prompts", help="JSON list of {name, prompt} subject variants, relative to the repo root")
    r.add_argument("--ref", help="image to redraw (photo, sketch, art), relative to the repo root")
    r.add_argument("--batch", type=int, default=1)
    r.add_argument("--seed", type=int)

    e = sub.add_parser("edit", help="run a free-form edit instruction on one image")
    e.add_argument("id")
    e.add_argument("--image", required=True, help="relative to the repo root")
    e.add_argument("--image2", help="optional second image the instruction can refer to")
    e.add_argument("--prompt", required=True)
    e.add_argument("--name", required=True, help="output name: work/refs/<id>/<name>.png")
    e.add_argument("--seed", type=int)

    s = sub.add_parser("shape", help="generate a raw mesh from chosen reference views")
    s.add_argument("id")
    for v in VIEWS:
        s.add_argument(f"--{v}", help=f"{v} view image, relative to the repo root")
    s.add_argument("--seed", type=int)
    s.add_argument("--turbo", action="store_true")
    s.add_argument("--octree", type=int, default=256)
    s.add_argument("--steps", type=int)
    s.add_argument("--cfg", type=float)

    args = p.parse_args()
    comfy = Comfy(args.url or settings().get("comfyUiUrl", "http://127.0.0.1:8000"))
    {"check": cmd_check, "refs": cmd_refs, "edit": cmd_edit, "shape": cmd_shape}[args.cmd](comfy, args)


if __name__ == "__main__":
    main()
