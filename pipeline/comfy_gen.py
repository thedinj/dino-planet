"""
Drive ComfyUI's HTTP API for the asset pipeline. Python 3.10+, standard library only.

  python pipeline/comfy_gen.py check
  python pipeline/comfy_gen.py refs  <id> [--view left] [--seed N] [--batch 4] [--steps 30]
  python pipeline/comfy_gen.py shape <id> --left work/refs/<id>/left_s123_1.png
                                     [--front F] [--back B] [--right R]
                                     [--seed N] [--turbo] [--octree 256] [--steps N] [--cfg X]

refs   builds the prompt from pipeline/prompts/style.md + the asset's manifest "describe",
       runs workflows/reference_sdxl.json and saves work/refs/<id>/<view>_s<seed>_<n>.png.
shape  uploads the chosen views, runs workflows/shape_hunyuan3d_mv.json and saves
       work/raw-meshes/<id>_s<seed>.glb. Views you don't pass are left out of the graph.

The ComfyUI URL comes from pipeline/local.settings.jsonc ("comfyUiUrl"). Workflow nodes are
found by their _meta.title, so a re-exported workflow keeps working if the titles are kept.
Every run prints the files it wrote as "wrote <path>" lines.
"""

import argparse
import json
import random
import re
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


def manifest_entry(asset_id):
    for a in load_jsonc(PIPELINE / "manifest.jsonc")["assets"]:
        if a["id"] == asset_id:
            return a
    sys.exit(f"'{asset_id}' is not in pipeline/manifest.jsonc. Add it first (/new-asset).")


def style_template():
    """Positive and negative prompt text and the view phrases, from prompts/style.md."""
    md = (PIPELINE / "prompts" / "style.md").read_text(encoding="utf-8")

    def block(heading):
        m = re.search(rf"## {heading}\s*\n.*?```\s*\n(.*?)```", md, re.S)
        if not m:
            sys.exit(f"prompts/style.md has no code block under '## {heading}'.")
        return " ".join(m.group(1).split())

    views = dict(re.findall(r"^\|\s*(\w+)\s*\|\s*`([^`]+)`\s*\|", md, re.M))
    return block("Positive"), block("Negative"), views


def build_prompts(entry, view):
    positive, negative, views = style_template()
    if view not in views:
        sys.exit(f"Unknown view '{view}'. style.md defines: {', '.join(views)}.")
    positive = positive.replace("{describe}", entry["describe"]).replace("{view}", views[view])
    if entry["kind"] != "dino":
        # Per style.md: weapons and props drop the creature-only negatives.
        for term in ("rider", "person", "cut off tail"):
            negative = re.sub(rf"(^|,\s*){re.escape(term)}(?=,|$)", "", negative)
        negative = negative.strip(" ,")
    return positive, negative


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

    def run(self, workflow, label):
        """Queue a workflow, wait for it, return its history entry."""
        res = self.post("/prompt", {"prompt": workflow, "client_id": self.client_id})
        prompt_id = res["prompt_id"]
        print(f"queued {label} ({prompt_id})", flush=True)
        start = time.time()
        while True:
            time.sleep(2)
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
        print(f"wrote {dest.relative_to(REPO)}", flush=True)


def load_workflow(name):
    return json.loads((PIPELINE / "workflows" / name).read_text(encoding="utf-8"))


def node(workflow, title):
    for node_id, n in workflow.items():
        if n.get("_meta", {}).get("title") == title:
            return node_id, n
    sys.exit(f"Workflow has no node titled '{title}'.")


# ---------------------------------------------------------------- commands

def cmd_check(comfy, _args):
    stats = comfy.get("/system_stats")
    print(f"ComfyUI {stats['system']['comfyui_version']} at {comfy.url}")
    for d in stats.get("devices", []):
        print(f"  {d['name']}: {d['vram_total'] // 2**20} MB VRAM, {d['vram_free'] // 2**20} MB free")
    ckpts = set(comfy.get("/models/checkpoints"))
    nodes = set(comfy.get("/object_info"))
    ok = True
    for wf in ("reference_sdxl.json", "shape_hunyuan3d_mv.json"):
        workflow = load_workflow(wf)
        for n in workflow.values():
            if n["class_type"] not in nodes:
                print(f"  MISSING node {n['class_type']} (used by {wf})")
                ok = False
        need = node(workflow, "checkpoint")[1]["inputs"]["ckpt_name"]
        if need not in ckpts:
            print(f"  MISSING checkpoint {need} (used by {wf})")
            ok = False
    if "hunyuan3d-dit-v2-mv-turbo.safetensors" not in ckpts:
        print("  note: turbo checkpoint not installed; --turbo won't work")
    print("ready" if ok else "not ready")
    sys.exit(0 if ok else 1)


def cmd_refs(comfy, args):
    entry = manifest_entry(args.id)
    positive, negative = build_prompts(entry, args.view)
    seed = args.seed if args.seed is not None else random.randrange(2**32)

    wf = load_workflow("reference_sdxl.json")
    node(wf, "positive")[1]["inputs"]["text"] = positive
    node(wf, "negative")[1]["inputs"]["text"] = negative
    node(wf, "latent")[1]["inputs"]["batch_size"] = args.batch
    sampler = node(wf, "sampler")[1]["inputs"]
    sampler["seed"] = seed
    if args.steps:
        sampler["steps"] = args.steps
    node(wf, "save")[1]["inputs"]["filename_prefix"] = f"dinoplanet/{args.id}_{args.view}"

    print(f"positive: {positive}\nnegative: {negative}\nseed: {seed}")
    entry_out = comfy.run(wf, f"{args.id} {args.view} refs")
    out_dir = work_dir(settings()) / "refs" / args.id
    images = [i for i in comfy.outputs(entry_out) if i["filename"].lower().endswith(".png")]
    for n, item in enumerate(images, 1):
        comfy.download(item, out_dir / f"{args.view}_s{seed}_{n}.png")


def cmd_shape(comfy, args):
    manifest_entry(args.id)  # fail early on a typo'd id
    views = {v: getattr(args, v) for v in VIEWS if getattr(args, v)}
    if not views:
        sys.exit("Pass at least one view image, e.g. --left work/refs/<id>/left_s1_1.png")
    seed = args.seed if args.seed is not None else random.randrange(2**32)

    wf = load_workflow("shape_hunyuan3d_mv.json")
    cond_id, cond = node(wf, "conditioning")
    for v in VIEWS:
        img_id, img = node(wf, f"image_{v}")
        enc_id, _ = node(wf, f"encode_{v}")
        if v in views:
            img["inputs"]["image"] = comfy.upload(REPO / views[v], f"{args.id}_{v}.png")
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

    # SDXL and Hunyuan3D don't both fit in 8 GB; drop whatever is loaded first.
    comfy.post("/free", {"unload_models": True, "free_memory": True})
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

    r = sub.add_parser("refs", help="generate reference images for one view")
    r.add_argument("id")
    r.add_argument("--view", default="left")
    r.add_argument("--seed", type=int)
    r.add_argument("--batch", type=int, default=4)
    r.add_argument("--steps", type=int)

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
    {"check": cmd_check, "refs": cmd_refs, "shape": cmd_shape}[args.cmd](comfy, args)


if __name__ == "__main__":
    main()
