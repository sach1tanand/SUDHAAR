import os, re, secrets
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env", override=False)
DATA = Path(os.environ.get("SUDHAAR_DATA", BASE / "data"))
MEDIA = DATA / "media_private"          # never served statically
DB_PATH = DATA / "sudhaar.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
# Render may provide the legacy postgres:// scheme; psycopg 3 expects postgresql://.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
DATA.mkdir(parents=True, exist_ok=True)
MEDIA.mkdir(parents=True, exist_ok=True)

_sk = DATA / "secret.key"
if not _sk.exists():
    _sk.write_text(secrets.token_hex(32))
SECRET = os.environ.get("SUDHAAR_SECRET", _sk.read_text().strip())

# Dev mode returns the OTP in the API response. Turn OFF in production and wire an SMS gateway.
DEV_OTP = os.environ.get("SUDHAAR_DEV_OTP", "1") == "1"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("SUDHAAR_VISION_MODEL", "claude-sonnet-4-6")
def parse_models(spec: str) -> list[tuple[str, str]]:
    """'road=/m/a.pt, waste=/m/b.pt' or '/m/a.pt;/m/b.pt' -> [(name, path), ...] with unique names."""
    out, seen = [], set()
    for part in re.split(r"[;,]", spec or ""):
        part = part.strip()
        if not part: continue
        name, path = part.split("=", 1) if "=" in part else ("", part)
        path = path.strip()
        model_path = Path(path)
        # Keep POSIX absolute paths intact when parsing config on Windows.
        if not model_path.is_absolute() and not path.startswith("/"): path = str((BASE / model_path).resolve())
        name = name.strip() or os.path.splitext(os.path.basename(path))[0] or "model"
        base, i = name, 2
        while name in seen: name, i = f"{base}{i}", i + 1
        seen.add(name); out.append((name, path))
    return out
# One or more ultralytics models (see backend/vision.py). SUDHAAR_YOLO_WEIGHTS is the legacy single-path setting.
YOLO_MODELS = parse_models(os.environ.get("SUDHAAR_YOLO_MODELS", "") or os.environ.get("SUDHAAR_YOLO_WEIGHTS", ""))
YOLO_WEIGHTS = ",".join(p for _, p in YOLO_MODELS)           # kept so older code/tests that test its truthiness still work
MAX_UPLOAD_MB = int(os.environ.get("SUDHAAR_MAX_UPLOAD_MB", "60"))
CAPTURE_WINDOW_MIN = 45   # media must be captured within this window of a server-issued capture session
OFFLINE = os.environ.get("SUDHAAR_OFFLINE", "0") == "1"   # skip all external HTTP calls (tests / air-gapped)
