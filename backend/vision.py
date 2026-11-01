"""YOLO vision engine: any number of ultralytics models, loaded once, run on photos AND video frames.

Configuration (environment):
  SUDHAAR_YOLO_MODELS   comma/semicolon separated list. Each item is `path` or `name=path`.
                        e.g.  "road=/models/road_best.pt,waste=/models/waste_best.pt"
  SUDHAAR_YOLO_WEIGHTS  legacy single path (still honoured; may also be a list).
  SUDHAAR_YOLO_CONF     minimum per-box confidence (default 0.25).
  SUDHAAR_YOLO_MAP      optional JSON file that overrides how class names map to Sudhaar labels/categories:
                        {"pothole": {"label": "pothole", "categories": ["roads"]}, "mh_open": {"label": "open manhole", "categories": ["drainage"]}}
                        Keys are your model's class names (case-insensitive).

Every detection is normalised to {cls, label, conf, model, functions, area}. `functions` are the Sudhaar category
functions (roads, drainage, sanitation, lighting, water, traffic, public_spaces) the detection is evidence for, so
`matches_category` is true only when something relevant to the *reported* category was actually seen.
"""
import json, os, re, shutil, subprocess, tempfile, threading
from . import config
from .routing import CATEGORIES

# class-name keywords -> (label, functions). Order matters: first match wins. `label` feeds the severity rules
# in investigation.py, so "open manhole" / "exposed wire" must keep exactly these spellings.
DEFAULT_RULES = [
    (r"open.*man ?hole|man ?hole.*open|missing.*(cover|lid)|uncovered", "open manhole", ["drainage"]),
    (r"man ?hole|sewer|drain|gutter|culvert", "manhole / drain", ["drainage"]),
    (r"exposed.*(wire|cable)|live.*wire|(wire|cable|electric)", "exposed wire", ["lighting"]),
    (r"street ?light|lamp|light ?pole|broken.*light", "streetlight", ["lighting"]),
    (r"pot ?hole", "pothole", ["roads"]),
    (r"crack|alligator|rut|damaged.*road|road.*damage|broken.*road|patch", "damaged road", ["roads"]),
    (r"garbage|trash|waste|litter|dump|rubbish|debris", "garbage accumulation", ["sanitation", "public_spaces"]),
    (r"water.*log|flood|puddle|stagnant", "waterlogging", ["drainage", "water"]),
    (r"leak|pipe|burst|water", "water leakage", ["water"]),
    (r"signal|traffic.*light|sign|barrier|cone|encroach|illegal.*park", "traffic issue", ["traffic"]),
    (r"tree|bench|park|playground|fence|graffiti", "public space damage", ["public_spaces"]),
]

_lock = threading.Lock()
_cache: dict[str, object] = {}
_rules_cache: list | None = None


def conf_threshold() -> float:
    try: return float(os.environ.get("SUDHAAR_YOLO_CONF", "0.25"))
    except ValueError: return 0.25


def models() -> list[tuple[str, str]]:
    return config.YOLO_MODELS


def _rules() -> list:
    """Default keyword rules, with the optional SUDHAAR_YOLO_MAP overrides placed first."""
    global _rules_cache
    if _rules_cache is not None: return _rules_cache
    rules = []
    path = os.environ.get("SUDHAAR_YOLO_MAP", "")
    if path and os.path.exists(path):
        try:
            for k, v in json.load(open(path)).items():
                rules.append((r"^" + re.escape(k.lower().strip()) + r"$", v.get("label", k), list(v.get("categories", []))))
        except Exception:
            pass
    _rules_cache = rules + DEFAULT_RULES
    return _rules_cache


def normalise(cls_name: str) -> tuple[str, list[str]]:
    n = re.sub(r"[_\-]+", " ", str(cls_name).lower()).strip()
    for pat, label, funcs in _rules():
        if re.search(pat, n) or re.search(pat, str(cls_name).lower()): return label, funcs
    return n, []          # unknown class: kept as its own label, evidence for no specific category


def _load(path: str):
    with _lock:
        if path not in _cache:
            from ultralytics import YOLO      # optional dependency, imported lazily
            _cache[path] = YOLO(path)
        return _cache[path]


def _frames_from_video(path: str, n: int = 4) -> list[str]:
    """Up to n evenly spaced JPEG frames written next to a temp dir the caller cleans up. Returns file paths."""
    if not shutil.which("ffmpeg"): return []
    td = tempfile.mkdtemp(prefix="sdh_frames_")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", "fps=1", "-frames:v", str(n),
                        os.path.join(td, "f%02d.jpg")], timeout=90, check=False)
    except Exception:
        pass
    return sorted(os.path.join(td, f) for f in os.listdir(td) if f.endswith(".jpg"))


def _run_model(name: str, path: str, image_path: str, thresh: float) -> list[dict]:
    res = _load(path)(image_path, verbose=False, conf=thresh)[0]
    h, w = (res.orig_shape or (0, 0))[:2]
    dets = []
    for i in range(len(res.boxes)):
        conf = float(res.boxes.conf[i]); cls = res.names[int(res.boxes.cls[i])]
        if conf < thresh: continue
        label, funcs = normalise(cls)
        area = 0.0
        try:
            x1, y1, x2, y2 = [float(v) for v in res.boxes.xyxy[i]]
            area = max(0.0, (x2 - x1) * (y2 - y1)) / float(w * h) if w and h else 0.0
        except Exception:
            pass
        dets.append(dict(model=name, cls=str(cls), label=label, conf=round(conf, 3), functions=funcs, area=round(area, 4)))
    return dets


def analyse_image(image_paths: list[str], category: str) -> dict:
    """Run every configured model on every image path and merge into one finding.
    A model that fails is reported in `model_errors`; the others still count. Raises only if ALL models fail."""
    func = CATEGORIES.get(category, "general")
    thresh, dets, errors, ok_models = conf_threshold(), [], {}, 0
    for name, path in models():
        try:
            for ip in image_paths: dets += _run_model(name, path, ip, thresh)
            ok_models += 1
        except Exception as e:
            errors[name] = str(e)[:160]
    if models() and ok_models == 0:
        raise RuntimeError("all YOLO models failed: " + "; ".join(f"{k}: {v}" for k, v in errors.items()))
    relevant = [d for d in dets if func == "general" or func in d["functions"]]
    pool = relevant or dets
    conf = max((d["conf"] for d in pool), default=0.0)
    big = max((d["area"] for d in pool), default=0.0)
    size = "unknown" if not pool else "large" if big >= .15 else "medium" if big >= .04 else "small"
    per_model = {}
    for d in dets:
        m = per_model.setdefault(d["model"], dict(detections=0, max_conf=0.0, labels=set()))
        m["detections"] += 1; m["max_conf"] = max(m["max_conf"], d["conf"]); m["labels"].add(d["label"])
    for m in per_model.values(): m["labels"] = sorted(m["labels"])
    return dict(detected=sorted({d["label"] for d in dets}), matches_category=bool(relevant) if dets else False,
                confidence=conf, size_hint=size, hazard_notes="", models=per_model, model_errors=errors,
                detections=sorted(dets, key=lambda d: -d["conf"])[:12])


def analyse_photo(path: str, category: str) -> dict:
    return analyse_image([path], category)


def analyse_video(path: str, category: str) -> dict:
    frames = _frames_from_video(path)
    if not frames: raise RuntimeError("no frames could be extracted from the video (ffmpeg missing?)")
    try: return analyse_image(frames, category)
    finally: shutil.rmtree(os.path.dirname(frames[0]), ignore_errors=True)
