import base64, hashlib, hmac, json, secrets, time
from fastapi import Header, HTTPException
from .config import SECRET
from . import db

def hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + "$" + h.hex()

def check_pw(pw: str, stored: str) -> bool:
    salt, h = stored.split("$")
    return hmac.compare_digest(hash_pw(pw, bytes.fromhex(salt)).split("$")[1], h)

def hash_otp(mobile: str, code: str) -> str:
    return hmac.new(SECRET.encode(), f"{mobile}:{code}".encode(), hashlib.sha256).hexdigest()

def _b64(b: bytes) -> str: return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _unb64(s: str) -> bytes: return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def sign(payload: dict, ttl: int) -> str:
    payload = {**payload, "exp": int(time.time()) + ttl}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"

def verify(token: str) -> dict | None:
    try:
        body, sig = token.split(".")
        good = _b64(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good): return None
        p = json.loads(_unb64(body))
        return p if p["exp"] > time.time() else None
    except Exception:
        return None

def _principal(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    p = verify(authorization[7:])
    if not p: raise HTTPException(401, "Session expired")
    return p

def citizen(authorization: str | None = Header(None)) -> dict:
    p = _principal(authorization)
    if p.get("role") != "citizen": raise HTTPException(403, "Citizen access only")
    # Resolve citizen identity by its stable mobile number in the active shared
    # database. A numeric ID from an instance-local SQLite file can collide with
    # another user's ID on a different Render instance.
    mobile = p.get("mobile")
    if not isinstance(mobile, str) or not mobile:
        raise HTTPException(401, "Citizen session is outdated. Sign in again.")
    user = db.q("SELECT id FROM users WHERE mobile=?", (mobile,), one=True)
    if not user:
        raise HTTPException(401, "Citizen account is not in the active database. Sign in again.")
    p["sub"] = user["id"]
    return p

def officer(authorization: str | None = Header(None)) -> dict:
    p = _principal(authorization)
    if p.get("role") != "officer": raise HTTPException(403, "Department access only")
    return p

def admin(authorization: str | None = Header(None)) -> dict:
    p = _principal(authorization)
    if p.get("role") != "super_admin": raise HTTPException(403, "Super Admin only")
    return p

def staff(authorization: str | None = Header(None)) -> dict:
    p = _principal(authorization)
    if p.get("role") not in ("officer", "super_admin"): raise HTTPException(403, "Staff only")
    return p

def any_user(authorization: str | None = Header(None)) -> dict:
    return _principal(authorization)

def monitor(authorization: str | None = Header(None)) -> dict:
    """Sudhaar AI-monitor (read-only view of how the AI pipeline worked). Super Admin may also look."""
    p = _principal(authorization)
    if p.get("role") not in ("ai_monitor", "super_admin"): raise HTTPException(403, "Sudhaar AI monitor access only")
    return p
