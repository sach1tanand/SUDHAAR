import hashlib, json, random, re, secrets, string, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import chatbot, config, db, investigation, routing, trace, security as sec

app = FastAPI(title="Sudhaar", description="Report. Resolve. Improve.")
FRONTEND = config.BASE / "frontend"

@app.on_event("startup")
def _startup():
    db.init(); routing.seed()

STATUSES = ["Complaint Registered", "Forwarded to Department", "Complaint Acknowledged", "Under Review",
            "Field Officer Assigned", "Work In Progress", "Resolved", "Rejected", "Reopened"]
# Provisional transition rules (spec §4.10 leaves these open)
OPEN = ["Complaint Acknowledged", "Under Review", "Field Officer Assigned", "Work In Progress", "Resolved", "Rejected"]
TRANSITIONS = {
    "Forwarded to Department": OPEN, "Reopened": OPEN,
    "Complaint Acknowledged": OPEN[1:], "Under Review": ["Field Officer Assigned", "Work In Progress", "Resolved", "Rejected"],
    "Field Officer Assigned": ["Under Review", "Work In Progress", "Resolved", "Rejected"],
    "Work In Progress": ["Under Review", "Resolved", "Rejected"],
    "Resolved": [], "Rejected": [],
}

# ------------------------------------------------------------------ helpers
def _mobile(m: str) -> str:
    m = re.sub(r"[\s\-]", "", m or "")
    m = re.sub(r"^(\+91|91|0)(?=\d{10}$)", "", m)
    if not re.fullmatch(r"[6-9]\d{9}", m): raise HTTPException(400, "Enter a valid 10-digit Indian mobile number")
    return m

SIGS = {b"\xff\xd8\xff": ("photo", "image/jpeg"), b"\x89PNG": ("photo", "image/png"), b"\x1aE\xdf\xa3": ("video", "video/webm")}
def sniff(data: bytes):
    for sig, v in SIGS.items():
        if data.startswith(sig): return v
    if data[4:8] == b"ftyp": return ("video", "video/mp4")
    return None

async def save_media(f: UploadFile, expect: str, complaint_id: int, role: str, lat=None, lon=None, cap=None, by=None):
    data = await f.read()
    if len(data) > config.MAX_UPLOAD_MB * 1_048_576: raise HTTPException(413, "File too large")
    kind = sniff(data)
    if not kind or kind[0] != expect: raise HTTPException(400, f"Invalid {expect} file")
    sha = hashlib.sha256(data).hexdigest()
    ext = {"image/jpeg": "jpg", "image/png": "png", "video/webm": "webm", "video/mp4": "mp4"}[kind[1]]
    d = config.MEDIA / str(complaint_id); d.mkdir(parents=True, exist_ok=True)
    path = d / f"{secrets.token_hex(8)}.{ext}"
    path.write_bytes(data)
    mid = db.x("INSERT INTO media(complaint_id,kind,role,path,mime,sha256,size,lat,lon,captured_at,uploaded_by,created_at) "
               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (complaint_id, kind[0], role, str(path), kind[1], sha, len(data), lat, lon, cap, by, db.now()))
    return mid

def _set_status(c: dict, status: str, note: str, actor: str, visible=1, notify_citizen=True):
    db.x("UPDATE complaints SET status=?, updated_at=? WHERE id=?", (status, db.now(), c["id"]))
    db.add_timeline(c["id"], status, note, actor, visible)
    if notify_citizen and visible and c.get("user_id"):
        db.notify(c["user_id"], c["code"], f"{c['code']}: {status}" + (f" - {note}" if note else ""))

def _get(code: str) -> dict:
    c = db.q("SELECT * FROM complaints WHERE code=?", (code,), one=True)
    if not c: raise HTTPException(404, "Complaint not found")
    return c

def _dept_name(did):
    d = db.q("SELECT name FROM departments WHERE id=?", (did,), one=True) if did else None
    return d["name"] if d else None

# ------------------------------------------------------------------ meta & auth
@app.get("/api/meta")
def meta():
    return dict(categories=list(routing.CATEGORIES), statuses=STATUSES, tagline="Report. Resolve. Improve.",
                max_upload_mb=config.MAX_UPLOAD_MB)

class OtpReq(BaseModel): mobile: str
class OtpVerify(BaseModel): mobile: str; code: str
class StaffLogin(BaseModel): username: str; password: str

@app.post("/api/auth/otp")
def otp(r: OtpReq):
    m = _mobile(r.mobile)
    row = db.q("SELECT * FROM otps WHERE mobile=?", (m,), one=True)
    if row and time.time() - row["sent_at"] < 30: raise HTTPException(429, "Please wait 30 seconds before requesting another OTP")
    code = "".join(random.SystemRandom().choice(string.digits) for _ in range(6))
    db.x("INSERT INTO otps(mobile,code_hash,expires,attempts,sent_at) VALUES(?,?,?,0,?) "
         "ON CONFLICT(mobile) DO UPDATE SET code_hash=excluded.code_hash, expires=excluded.expires, attempts=0, sent_at=excluded.sent_at",
         (m, sec.hash_otp(m, code), time.time() + 300, time.time()))
    # TODO(production): send `code` through an SMS gateway (e.g. MSG91/Twilio) - spec leaves auth implementation open.
    print(f"[sudhaar] OTP for {m}: {code}")
    return {"sent": True, **({"dev_otp": code} if config.DEV_OTP else {})}

@app.post("/api/auth/verify")
def verify_otp(r: OtpVerify):
    m = _mobile(r.mobile)
    row = db.q("SELECT * FROM otps WHERE mobile=?", (m,), one=True)
    if not row or row["expires"] < time.time(): raise HTTPException(400, "OTP expired. Request a new one")
    if row["attempts"] >= 5: raise HTTPException(429, "Too many attempts. Request a new OTP")
    db.x("UPDATE otps SET attempts=attempts+1 WHERE mobile=?", (m,))
    if sec.hash_otp(m, r.code.strip()) != row["code_hash"]: raise HTTPException(400, "Incorrect OTP")
    db.x("DELETE FROM otps WHERE mobile=?", (m,))
    u = db.q("SELECT * FROM users WHERE mobile=?", (m,), one=True)
    uid = u["id"] if u else db.x("INSERT INTO users(mobile,created_at) VALUES(?,?)", (m, db.now()))
    return {"token": sec.sign({"sub": uid, "role": "citizen"}, 30 * 86400), "role": "citizen"}

@app.post("/api/staff/login")
def staff_login(r: StaffLogin):
    o = db.q("SELECT * FROM officers WHERE username=?", (r.username.strip().lower(),), one=True)
    if not o or not sec.check_pw(r.password, o["pw_hash"]): raise HTTPException(401, "Invalid username or password")
    p = {"sub": o["id"], "role": o["role"], "dept": o["dept_id"], "name": o["name"]}
    db.audit(p, "LOGIN")
    return {"token": sec.sign(p, 12 * 3600), "role": o["role"], "name": o["name"], "dept": _dept_name(o["dept_id"])}

@app.post("/api/chat")
def chat(body: dict):
    msg = str(body.get("message", ""))[:500]
    tr = trace.Tracer(None, run_id="chat-" + secrets.token_hex(4))
    with tr.step("chatbot", "Helper chatbot answered a question", message=msg) as st:
        out = chatbot.reply(msg)
        st.out(intent=out.get("intent"), language=out["lang"], reply=out["reply"])
        if out.get("intent") == "fallback": st.warn("No rule matched - gave the default help menu.")
    return {k: v for k, v in out.items() if k != "intent"}

# ------------------------------------------------------------------ citizen: submit
@app.post("/api/capture-session")
def capture_session(u=Depends(sec.citizen)):
    """Server-issued window during which live media must be captured (guards against stale/gallery media)."""
    iat = int(time.time())
    return {"capture_token": sec.sign({"sub": u["sub"], "role": "capture", "iat": iat}, 7 * 86400), "iat": iat, "window_min": config.CAPTURE_WINDOW_MIN}

def process(complaint_id: int):
    """Investigation -> routing -> forward. Fast phase first so critical/high are never delayed.
    Every stage is recorded in ai_trace so the Sudhaar monitor can replay exactly what the AI did."""
    c = db.q("SELECT * FROM complaints WHERE id=?", (complaint_id,), one=True)
    media = db.q("SELECT * FROM media WHERE complaint_id=? AND role='original'", (complaint_id,))
    tr = trace.Tracer(c["code"])
    with tr.step("intake", "Complaint received", category=c["category"], lat=c["lat"], lon=c["lon"], loc_source=c["loc_source"],
                 captured_at=c["captured_at"], has_description=bool(c["description"])) as st:
        st.out(media=[dict(id=m["id"], kind=m["kind"], size_kb=round(m["size"] / 1024, 1), sha256=m["sha256"][:12]) for m in media])
        if c["loc_source"] == "manual": st.note("Location was pinned manually by the citizen (not GPS).")
    try:
        p1 = investigation.investigate(c, media, enrich=False, tr=tr)
    except Exception as e:
        p1 = dict(ai=dict(analysed=False, error=str(e)[:200], findings=[], detected=[]), evidence={}, validity=0.0,
                  severity=dict(category="Medium", priority=2, reasons=["Investigation error; defaulted to Medium"]), enriched=False)
        with tr.step("fallback", "Investigation failed - using safe defaults") as st: st.fail(str(e)[:200])
    with tr.step("routing", "Identify the responsible department", category=c["category"], lat=c["lat"], lon=c["lon"]) as st:
        r = routing.route(c["category"], c["lat"], c["lon"])
        st.out(department=_dept_name(r["dept_id"]), level=r["level"], function=r["function"], confidence=r["confidence"], reasoning=r["steps"])
        if r["fallback"]: st.warn("Could not identify the authority confidently - sent to the general desk and flagged for Super Admin review.")
    db.x("UPDATE complaints SET dept_id=?, gov_level=?, severity=?, priority=?, validity_score=?, ai_json=?, evidence_json=?, routing_json=? WHERE id=?",
         (r["dept_id"], r["level"], p1["severity"]["category"], p1["severity"]["priority"], p1["validity"],
          json.dumps({**p1["ai"], "severity": p1["severity"]}), json.dumps(p1["evidence"]), json.dumps(r), complaint_id))
    c = db.q("SELECT * FROM complaints WHERE id=?", (complaint_id,), one=True)
    with tr.step("forward", "Forward to department dashboard", department=_dept_name(r["dept_id"]), severity=p1["severity"]["category"]) as st:
        _set_status(c, "Forwarded to Department", f"Sent to {_dept_name(r['dept_id'])}" if r["dept_id"] else "", "system")
        db.audit({"role": "system", "sub": 0, "name": "sudhaar-pipeline"}, "FORWARDED", c["code"],
                 f"dept={r['dept_id']} sev={p1['severity']['category']} fallback={r['fallback']}", dept_id=r["dept_id"])
        st.out(status="Forwarded to Department", priority=p1["severity"]["priority"], validity_score=p1["validity"])
        st.note("Forwarded before slow external lookups so critical/high complaints are never delayed.")
    try:  # slow phase: external sources + weather + historical context
        p2 = investigation.investigate(c, media, ai=p1["ai"], enrich=True, tr=tr)
        db.x("UPDATE complaints SET validity_score=?, severity=?, priority=?, evidence_json=?, ai_json=? WHERE id=?",
             (p2["validity"], p2["severity"]["category"], p2["severity"]["priority"], json.dumps(p2["evidence"]),
              json.dumps({**p2["ai"], "severity": p2["severity"]}), complaint_id))
        with tr.step("final", "Pipeline complete", validity_score=p2["validity"], severity=p2["severity"]["category"]) as st:
            st.out(validity_before=p1["validity"], validity_after=p2["validity"])
    except Exception as e:
        print("[sudhaar] enrichment failed:", e)
        with tr.step("final", "Enrichment failed - complaint already forwarded") as st: st.fail(str(e)[:200])

@app.post("/api/complaints")
async def submit(bg: BackgroundTasks, u=Depends(sec.citizen),
                 category: str = Form(...), description: str = Form(""), lat: float = Form(...), lon: float = Form(...),
                 loc_source: str = Form(...), captured_at: str = Form(...), capture_token: str = Form(...),
                 client_id: str = Form(...), photo: UploadFile | None = File(None), video: UploadFile | None = File(None)):
    prior = db.q("SELECT code FROM complaints WHERE user_id=? AND client_id=?", (u["sub"], client_id), one=True)
    if prior:   # idempotent retry after a dropped connection
        return {"code": prior["code"], "duplicate_submission": True}
    if category not in routing.CATEGORIES: raise HTTPException(400, "Unknown category")
    if loc_source not in ("gps", "manual"): raise HTTPException(400, "loc_source must be gps or manual")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise HTTPException(400, "Invalid coordinates")
    if not photo and not video: raise HTTPException(400, "Capture a live photo or video to submit")
    cs = sec.verify(capture_token)
    if not cs or cs.get("role") != "capture" or cs.get("sub") != u["sub"]:
        raise HTTPException(400, "Capture session invalid or expired. Capture the media again inside Sudhaar")
    try: cap = datetime.fromisoformat(captured_at.replace("Z", "+00:00")).timestamp()
    except Exception: raise HTTPException(400, "Invalid captured_at")
    # media must be captured within the window after the session was issued (tokens last 7 days so offline drafts can still upload)
    if cap < cs["iat"] - 120 or cap > cs["iat"] + config.CAPTURE_WINDOW_MIN * 60 + 120 or cap > time.time() + 120:
        raise HTTPException(400, "Media timestamp is outside the live capture window")
    code = f"SDH-{datetime.now(timezone.utc):%y%m%d}-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
    cid = db.x("INSERT INTO complaints(code,user_id,category,description,lat,lon,loc_source,captured_at,status,client_id,created_at,updated_at) "
               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (code, u["sub"], category, description.strip()[:1000], lat, lon, loc_source,
               captured_at, "Complaint Registered", client_id, db.now(), db.now()))
    try:
        if photo: await save_media(photo, "photo", cid, "original", lat, lon, captured_at)
        if video: await save_media(video, "video", cid, "original", lat, lon, captured_at)
    except HTTPException:
        db.x("DELETE FROM media WHERE complaint_id=?", (cid,)); db.x("DELETE FROM complaints WHERE id=?", (cid,)); raise
    db.add_timeline(cid, "Complaint Registered", "Complaint received by Sudhaar", "system")
    db.notify(u["sub"], code, f"{code}: complaint registered")
    bg.add_task(process, cid)
    return {"code": code, "status": "Complaint Registered", "category": category, "lat": lat, "lon": lon}

# ------------------------------------------------------------------ citizen: view & respond
def citizen_view(c: dict) -> dict:
    media = db.q("SELECT id,kind,role,captured_at FROM media WHERE complaint_id=?", (c["id"],))
    tl = db.q("SELECT status,note,created_at FROM timeline WHERE complaint_id=? AND citizen_visible=1 ORDER BY id", (c["id"],))
    return dict(code=c["code"], category=c["category"], description=c["description"], lat=c["lat"], lon=c["lon"],
                loc_source=c["loc_source"], status=c["status"], department=_dept_name(c["dept_id"]),
                created_at=c["created_at"], updated_at=c["updated_at"], timeline=tl, media=media,
                citizen_confirmed=bool(c["citizen_confirmed"]),
                can_confirm=c["status"] == "Resolved" and not c["citizen_confirmed"],
                can_reopen=c["status"] in ("Resolved", "Rejected"))   # NB: no scores / AI data / severity exposed

def _own(code: str, u: dict) -> dict:
    c = _get(code)
    if c["user_id"] != u["sub"]: raise HTTPException(404, "Complaint not found")
    return c

@app.get("/api/complaints")
def my_complaints(u=Depends(sec.citizen)):
    rows = db.q("SELECT * FROM complaints WHERE user_id=? ORDER BY id DESC", (u["sub"],))
    return [dict(code=c["code"], category=c["category"], status=c["status"], created_at=c["created_at"],
                 department=_dept_name(c["dept_id"])) for c in rows]

@app.get("/api/complaints/{code}")
def my_complaint(code: str, u=Depends(sec.citizen)): return citizen_view(_own(code, u))

@app.post("/api/complaints/{code}/confirm")
def confirm(code: str, u=Depends(sec.citizen)):
    c = _own(code, u)
    if c["status"] != "Resolved": raise HTTPException(400, "Only resolved complaints can be confirmed")
    db.x("UPDATE complaints SET citizen_confirmed=1 WHERE id=?", (c["id"],))
    db.add_timeline(c["id"], "Resolution Confirmed", "Citizen confirmed the issue is fixed", "citizen")
    db.audit({"role": "citizen", "sub": u["sub"], "name": "citizen"}, "CITIZEN_CONFIRMED", code, dept_id=c["dept_id"])
    return citizen_view(_get(code))

class Reopen(BaseModel): reason: str = ""
@app.post("/api/complaints/{code}/reopen")
def reopen(code: str, r: Reopen, u=Depends(sec.citizen)):
    c = _own(code, u)
    if c["status"] not in ("Resolved", "Rejected"): raise HTTPException(400, "Only resolved or rejected complaints can be reopened")
    db.x("UPDATE complaints SET citizen_confirmed=0, reopen_count=reopen_count+1 WHERE id=?", (c["id"],))
    _set_status(c, "Reopened", r.reason.strip()[:500] or "Citizen reports the problem still exists", "citizen", notify_citizen=False)
    db.audit({"role": "citizen", "sub": u["sub"], "name": "citizen"}, "CITIZEN_REOPENED", code, r.reason[:200], dept_id=c["dept_id"])
    return citizen_view(_get(code))

@app.get("/api/notifications")
def notifications(u=Depends(sec.citizen)):
    return db.q("SELECT id,complaint_code,message,read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["sub"],))

@app.post("/api/notifications/read")
def notifications_read(u=Depends(sec.citizen)):
    db.x("UPDATE notifications SET read=1 WHERE user_id=?", (u["sub"],)); return {"ok": True}

# ------------------------------------------------------------------ media (private, access-controlled)
@app.get("/api/media/{mid}")
def get_media(mid: int, p=Depends(sec.any_user)):
    m = db.q("SELECT * FROM media WHERE id=?", (mid,), one=True)
    if not m: raise HTTPException(404, "Not found")
    c = db.q("SELECT * FROM complaints WHERE id=?", (m["complaint_id"],), one=True)
    if p["role"] == "citizen":
        if c["user_id"] != p["sub"]: raise HTTPException(404, "Not found")
    elif p["role"] == "officer":
        if c["dept_id"] != p.get("dept"): raise HTTPException(403, "This complaint belongs to another department")
        db.audit(p, "MEDIA_VIEWED", c["code"], f"media={mid} kind={m['kind']} role={m['role']}")
    elif p["role"] in ("super_admin", "ai_monitor"):
        db.audit(p, "MEDIA_VIEWED", c["code"], f"media={mid}", dept_id=c["dept_id"])
    else:
        raise HTTPException(403, "Forbidden")
    return FileResponse(m["path"], media_type=m["mime"], headers={"Cache-Control": "private, no-store"})

# ------------------------------------------------------------------ department dashboard
def _scope(code: str, o: dict) -> dict:
    c = _get(code)
    if o["role"] == "officer" and c["dept_id"] != o.get("dept"): raise HTTPException(403, "Access denied: not your department's complaint")
    return c

def dept_view(c: dict) -> dict:
    """What officers see. Deliberately contains NO citizen identity or mobile number."""
    media = db.q("SELECT id,kind,role,lat,lon,captured_at,sha256,size FROM media WHERE complaint_id=?", (c["id"],))
    tl = db.q("SELECT status,note,actor,citizen_visible,created_at FROM timeline WHERE complaint_id=? ORDER BY id", (c["id"],))
    fo = db.q("SELECT id,name FROM field_officers WHERE id=?", (c["field_officer_id"],), one=True) if c["field_officer_id"] else None
    return dict(code=c["code"], category=c["category"], description=c["description"], lat=c["lat"], lon=c["lon"],
                loc_source=c["loc_source"], captured_at=c["captured_at"], status=c["status"], severity=c["severity"],
                priority=c["priority"], validity_score=c["validity_score"], gov_level=c["gov_level"],
                department=_dept_name(c["dept_id"]), ai=json.loads(c["ai_json"] or "{}"), evidence=json.loads(c["evidence_json"] or "{}"),
                routing=json.loads(c["routing_json"] or "{}"), media=media, timeline=tl, field_officer=fo,
                reopen_count=c["reopen_count"], created_at=c["created_at"], updated_at=c["updated_at"],
                allowed_next=TRANSITIONS.get(c["status"], []))

def _list_row(c): return dict(code=c["code"], category=c["category"], status=c["status"], severity=c["severity"], priority=c["priority"],
                              validity_score=c["validity_score"], created_at=c["created_at"], lat=c["lat"], lon=c["lon"],
                              department=_dept_name(c["dept_id"]), loc_source=c["loc_source"], reopen_count=c["reopen_count"])

@app.get("/api/dept/complaints")
def dept_list(status: str | None = None, severity: str | None = None, o=Depends(sec.officer)):
    sql, a = "SELECT * FROM complaints WHERE dept_id=?", [o["dept"]]
    if status: sql += " AND status=?"; a.append(status)
    if severity: sql += " AND severity=?"; a.append(severity)
    # Severity-based recommended work order (priority 1 = critical); not a rejection mechanism
    rows = db.q(sql + " ORDER BY CASE WHEN status IN ('Resolved','Rejected') THEN 1 ELSE 0 END, priority, created_at", a)
    return [_list_row(c) for c in rows]

@app.get("/api/dept/complaints/{code}")
def dept_detail(code: str, o=Depends(sec.officer)):
    c = _scope(code, o)
    db.audit(o, "COMPLAINT_VIEWED", code)
    return dept_view(c)

@app.get("/api/dept/field-officers")
def field_officers(o=Depends(sec.officer)): return db.q("SELECT id,name FROM field_officers WHERE dept_id=?", (o["dept"],))

class StatusChange(BaseModel):
    status: str; remarks: str = ""; field_officer_id: int | None = None; visible: bool = True

def _transition(c: dict, to: str, remarks: str, o: dict, fo_id=None, visible=True):
    if to not in TRANSITIONS.get(c["status"], []):
        raise HTTPException(400, f"Cannot move from '{c['status']}' to '{to}'")
    if to == "Rejected" and not remarks.strip(): raise HTTPException(400, "Remarks are required when rejecting a complaint")
    if to == "Resolved":
        last_reopen = db.q("SELECT MAX(created_at) t FROM timeline WHERE complaint_id=? AND status='Reopened'", (c["id"],), one=True)["t"] or ""
        if not db.q("SELECT 1 FROM media WHERE complaint_id=? AND role='resolution' AND created_at>=?", (c["id"], last_reopen)):
            raise HTTPException(400, "Upload resolution proof (photo/video) before marking resolved"
                                + (" - fresh proof is needed after a reopen" if last_reopen else ""))
    if to == "Field Officer Assigned":
        if not fo_id or not db.q("SELECT 1 FROM field_officers WHERE id=? AND dept_id=?", (fo_id, c["dept_id"])):
            raise HTTPException(400, "Select a field officer from your department")
        db.x("UPDATE complaints SET field_officer_id=? WHERE id=?", (fo_id, c["id"]))
    old = c["status"]
    _set_status(c, to, remarks.strip()[:1000], f"officer:{o.get('name')}", 1 if visible else 0)
    db.audit(o, "STATUS_CHANGED", c["code"], f"{old} -> {to}; remarks={'yes' if remarks.strip() else 'no'}", dept_id=c["dept_id"])

@app.post("/api/dept/complaints/{code}/status")
def dept_status(code: str, s: StatusChange, o=Depends(sec.officer)):
    c = _scope(code, o)
    _transition(c, s.status, s.remarks, o, s.field_officer_id, s.visible)
    return dept_view(_get(code))

class Remark(BaseModel): remarks: str; visible: bool = True
@app.post("/api/dept/complaints/{code}/remarks")
def dept_remark(code: str, r: Remark, o=Depends(sec.officer)):
    c = _scope(code, o)
    if not r.remarks.strip(): raise HTTPException(400, "Remark is empty")
    db.add_timeline(c["id"], "Remark", r.remarks.strip()[:1000], f"officer:{o.get('name')}", 1 if r.visible else 0)
    if r.visible and c["user_id"]: db.notify(c["user_id"], code, f"{code}: update from department - {r.remarks.strip()[:120]}")
    db.audit(o, "REMARK_ADDED", code, f"visible={r.visible}", dept_id=c["dept_id"])
    return dept_view(_get(code))

@app.post("/api/dept/complaints/{code}/resolution")
async def dept_resolution(code: str, remarks: str = Form(""), photo: list[UploadFile] = File(default=[]),
                          video: list[UploadFile] = File(default=[]), o=Depends(sec.officer)):
    c = _scope(code, o)
    if c["status"] in ("Resolved", "Rejected"): raise HTTPException(400, "Complaint is already closed")
    if not photo and not video: raise HTTPException(400, "Attach at least one photo or video")
    for f in photo: await save_media(f, "photo", c["id"], "resolution", by=o["sub"])
    for f in video: await save_media(f, "video", c["id"], "resolution", by=o["sub"])
    db.audit(o, "RESOLUTION_UPLOADED", code, f"files={len(photo) + len(video)}", dept_id=c["dept_id"])
    db.add_timeline(c["id"], "Resolution Proof Uploaded", remarks.strip()[:500], f"officer:{o.get('name')}", 0)
    return dept_view(_get(code))

# ------------------------------------------------------------------ super admin
@app.get("/api/admin/overview")
def overview(a=Depends(sec.admin)):
    depts = db.q("""SELECT d.id,d.name,d.short,d.level,d.functions,d.jurisdiction,d.is_fallback,d.active,
        COUNT(c.id) total, SUM(c.status NOT IN ('Resolved','Rejected')) open_count,
        SUM(c.severity='Critical' AND c.status NOT IN ('Resolved','Rejected')) critical_open,
        SUM(c.status='Resolved') resolved FROM departments d LEFT JOIN complaints c ON c.dept_id=d.id GROUP BY d.id""")
    tot = db.q("SELECT COUNT(*) n, SUM(status NOT IN ('Resolved','Rejected')) open_n FROM complaints", one=True)
    return dict(departments=depts, totals=tot, low_confidence_routing=db.q(
        "SELECT code,category,lat,lon,severity,status FROM complaints WHERE routing_json LIKE '%\"fallback\": true%' AND status NOT IN ('Resolved','Rejected')"))

@app.get("/api/admin/complaints")
def admin_complaints(dept_id: int | None = None, status: str | None = None, a=Depends(sec.admin)):
    sql, args = "SELECT * FROM complaints WHERE 1=1", []
    if dept_id: sql += " AND dept_id=?"; args.append(dept_id)
    if status: sql += " AND status=?"; args.append(status)
    return [_list_row(c) for c in db.q(sql + " ORDER BY id DESC LIMIT 300", args)]

@app.get("/api/admin/complaints/{code}")
def admin_detail(code: str, a=Depends(sec.admin)):
    c = _get(code); db.audit(a, "COMPLAINT_VIEWED", code, dept_id=c["dept_id"]); return dept_view(c)

class NewDept(BaseModel):
    name: str; short: str; level: str; functions: list[str]; jurisdiction: str = ""; officer_username: str; officer_password: str
@app.post("/api/admin/departments")
def add_dept(d: NewDept, a=Depends(sec.admin)):
    if d.level not in ("local", "state", "central"): raise HTTPException(400, "level must be local, state or central")
    bad = [f for f in d.functions if f not in routing.CATEGORIES.values()]
    if bad: raise HTTPException(400, f"Unknown functions: {bad}. Valid: {sorted(set(routing.CATEGORIES.values()))}")
    if len(d.officer_password) < 8: raise HTTPException(400, "Password must be at least 8 characters")
    try:
        did = db.x("INSERT INTO departments(name,short,level,functions,jurisdiction) VALUES(?,?,?,?,?)",
                   (d.name, d.short, d.level, json.dumps(d.functions), d.jurisdiction))
        db.x("INSERT INTO officers(username,pw_hash,name,role,dept_id) VALUES(?,?,?,?,?)",
             (d.officer_username.lower(), sec.hash_pw(d.officer_password), f"{d.short} Officer", "officer", did))
    except Exception as e:
        raise HTTPException(400, f"Could not create department (duplicate name or username?): {e}")
    db.audit(a, "DEPARTMENT_ADDED", detail=d.name, dept_id=did)
    return {"id": did}

class Reassign(BaseModel): dept_id: int; reason: str = ""
@app.post("/api/admin/complaints/{code}/reassign")
def reassign(code: str, r: Reassign, a=Depends(sec.admin)):
    c = _get(code)
    if not db.q("SELECT 1 FROM departments WHERE id=? AND active=1", (r.dept_id,)): raise HTTPException(400, "Unknown department")
    db.x("UPDATE complaints SET dept_id=? WHERE id=?", (r.dept_id, c["id"]))
    _set_status(c, "Forwarded to Department", f"Re-routed to {_dept_name(r.dept_id)}", "admin")
    db.audit(a, "COMPLAINT_REASSIGNED", code, f"{c['dept_id']} -> {r.dept_id}: {r.reason[:200]}", dept_id=r.dept_id)
    return dept_view(_get(code))

@app.get("/api/admin/zones")
def zones(a=Depends(sec.admin)): return db.q("SELECT * FROM zones")

class NewZone(BaseModel):
    name: str; kind: str; owner_level: str; dept_id: int | None = None; geometry: list; buffer_m: float = 40; categories: list[str] = ["roads"]; note: str = ""
@app.post("/api/admin/zones")
def add_zone(z: NewZone, a=Depends(sec.admin)):
    if z.kind not in ("corridor", "area"): raise HTTPException(400, "kind must be corridor or area")
    zid = db.x("INSERT INTO zones(name,kind,owner_level,dept_id,geometry,buffer_m,categories,note) VALUES(?,?,?,?,?,?,?,?)",
               (z.name, z.kind, z.owner_level, z.dept_id, json.dumps(z.geometry), z.buffer_m, json.dumps(z.categories), z.note))
    db.audit(a, "ZONE_ADDED", detail=z.name); return {"id": zid}

@app.get("/api/admin/audit")
def audit_log(limit: int = 200, complaint_code: str | None = None, a=Depends(sec.admin)):
    if complaint_code: return db.q("SELECT * FROM audit WHERE complaint_code=? ORDER BY id DESC LIMIT ?", (complaint_code, limit))
    return db.q("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))

@app.get("/api/admin/audit/verify")
def audit_verify(a=Depends(sec.admin)): return db.verify_audit_chain()

# ------------------------------------------------------------------ Sudhaar AI monitor (read-only)
@app.get("/api/ai/overview")
def ai_overview(m=Depends(sec.monitor)):
    rows = db.q("SELECT stage, COUNT(*) n, AVG(duration_ms) avg_ms, SUM(status='error') errors, SUM(status='warn') warns, "
                "SUM(status='skipped') skipped FROM ai_trace GROUP BY stage")
    runs = db.q("SELECT COUNT(DISTINCT run_id) n FROM ai_trace WHERE complaint_code IS NOT NULL", one=True)["n"]
    return dict(runs=runs, stages=rows, running=db.q("SELECT COUNT(*) n FROM ai_trace WHERE status='running'", one=True)["n"],
                engines=dict(claude_vision=bool(config.ANTHROPIC_API_KEY), claude_model=config.ANTHROPIC_MODEL if config.ANTHROPIC_API_KEY else None,
                             yolo=[n for n, _ in config.YOLO_MODELS], news=bool(__import__("os").environ.get("NEWSAPI_KEY")),
                             street_view=bool(__import__("os").environ.get("GOOGLE_MAPS_KEY")), offline=config.OFFLINE, weather=not config.OFFLINE),
                chat_answers=db.q("SELECT COUNT(*) n FROM ai_trace WHERE stage='chatbot'", one=True)["n"])

@app.get("/api/ai/runs")
def ai_runs(limit: int = 100, m=Depends(sec.monitor)):
    """One row per complaint pipeline run, newest first."""
    rows = db.q("""SELECT t.complaint_code code, MIN(t.started_at) started, COUNT(*) steps, SUM(t.status='running') running,
        SUM(t.status='error') errors, SUM(t.status='warn') warns, SUM(t.duration_ms) total_ms, MAX(t.id) last_id
        FROM ai_trace t WHERE t.complaint_code IS NOT NULL GROUP BY t.complaint_code ORDER BY last_id DESC LIMIT ?""", (limit,))
    for r in rows:
        c = db.q("SELECT category,severity,validity_score,status FROM complaints WHERE code=?", (r["code"],), one=True) or {}
        r.update(category=c.get("category"), severity=c.get("severity"), validity_score=c.get("validity_score"), status=c.get("status"))
    return rows

@app.get("/api/ai/complaints/{code}")
def ai_complaint(code: str, m=Depends(sec.monitor)):
    c = _get(code)
    db.audit(m, "AI_TRACE_VIEWED", code, dept_id=c["dept_id"])
    return dict(complaint=dept_view(c), steps=trace.for_complaint(code))

@app.get("/api/ai/feed")
def ai_feed(limit: int = 80, m=Depends(sec.monitor)):
    """Live feed: the latest steps across all complaints and the chatbot. Re-sent in full so 'running' steps update as they finish."""
    steps = trace.recent(min(limit, 200))
    return dict(steps=steps, last_id=max([x["id"] for x in steps], default=0), running=sum(1 for x in steps if x["status"] == "running"))

@app.get("/api/ai/steps/{sid}")
def ai_step(sid: int, m=Depends(sec.monitor)):
    r = db.q("SELECT * FROM ai_trace WHERE id=?", (sid,), one=True)
    if not r: raise HTTPException(404, "Step not found")
    return trace._row(r)

@app.get("/api/ai/chat")
def ai_chat(limit: int = 50, m=Depends(sec.monitor)):
    return [trace._row(r) for r in db.q("SELECT * FROM ai_trace WHERE stage='chatbot' ORDER BY id DESC LIMIT ?", (limit,))]

# ------------------------------------------------------------------ frontend
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
@app.get("/")
def index(): return FileResponse(FRONTEND / "index.html")
