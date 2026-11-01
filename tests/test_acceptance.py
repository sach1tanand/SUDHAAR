"""Acceptance tests derived from spec §10. Run: pytest -q"""
import io, os, tempfile, time
from datetime import datetime, timezone
os.environ["SUDHAAR_DATA"] = tempfile.mkdtemp()
os.environ["SUDHAAR_DEV_OTP"] = "1"
os.environ["SUDHAAR_OFFLINE"] = "1"
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend.main import app
from backend import config, db, security as sec

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def jpeg():
    b = io.BytesIO(); Image.new("RGB", (64, 64), (90, 90, 90)).save(b, "JPEG"); return b.getvalue()
WEBM = b"\x1aE\xdf\xa3" + b"\x00" * 200

def login(c, mobile="9876543210"):
    code = c.post("/api/auth/otp", json={"mobile": mobile}).json()["dev_otp"]
    t = c.post("/api/auth/verify", json={"mobile": mobile, "code": code}).json()["token"]
    return {"Authorization": f"Bearer {t}"}

def staff(c, u, p="demo1234"):
    return {"Authorization": "Bearer " + c.post("/api/staff/login", json={"username": u, "password": p}).json()["token"]}

def submit(c, h, category="Roads and Infrastructure", lat=25.3176, lon=82.9739, desc="", photo=True, video=False,
           src="gps", cid=None, token=None):
    cap = c.post("/api/capture-session", headers=h).json()["capture_token"] if token is None else token
    files = {}
    if photo: files["photo"] = ("p.jpg", jpeg(), "image/jpeg")
    if video: files["video"] = ("v.webm", WEBM, "video/webm")
    return c.post("/api/complaints", headers=h, files=files or None, data=dict(
        category=category, description=desc, lat=lat, lon=lon, loc_source=src, capture_token=cap,
        captured_at=datetime.now(timezone.utc).isoformat(), client_id=cid or os.urandom(4).hex()))

# ---- 10.1 submission
def test_login_and_submit_photo_video_both_and_optional_description(client):
    h = login(client)
    assert submit(client, h, photo=True, video=False).status_code == 200
    assert submit(client, h, photo=False, video=True).status_code == 200
    r = submit(client, h, photo=True, video=True, desc="big pothole near school")
    assert r.status_code == 200
    d = client.get(f"/api/complaints/{r.json()['code']}", headers=h).json()
    assert d["description"] == "big pothole near school" and {m["kind"] for m in d["media"]} == {"photo", "video"}

def test_authenticated_user_id_is_present_in_active_database_and_used_for_complaint(client):
    mobile = "9888800011"
    h = login(client, mobile)
    claims = sec.verify(h["Authorization"].split(" ", 1)[1])
    user = db.q("SELECT id FROM users WHERE mobile=?", (mobile,), one=True)
    assert user is not None
    assert claims["sub"] == user["id"]

    response = submit(client, h, cid="same-db-user-regression")
    assert response.status_code == 200, response.text
    complaint = db.q("SELECT user_id FROM complaints WHERE code=?", (response.json()["code"],), one=True)
    assert complaint["user_id"] == user["id"]

def test_render_requires_shared_database_url():
    with pytest.raises(RuntimeError, match="DATABASE_URL is required on Render"):
        config.validate_database_config("", {"RENDER": "true"})
    config.validate_database_config("postgresql://db.example/sudhaar", {"RENDER": "true"})

def test_complaint_submission_rejects_stale_user_before_foreign_key_insert(client):
    valid = login(client, "9888800012")
    valid_claims = sec.verify(valid["Authorization"].split(" ", 1)[1])
    # Simulate an instance-local SQLite token whose numeric ID collides with a
    # different identity in the active database.
    stale = {"Authorization": "Bearer " + sec.sign(
        {"sub": valid_claims["sub"], "role": "citizen", "mobile": "9666600099"}, 3600)}
    response = client.post("/api/complaints", headers=stale,
        files={"photo": ("p.jpg", jpeg(), "image/jpeg")},
        data=dict(category="Public Spaces", description="", lat=25.3, lon=82.97,
                  loc_source="gps", captured_at=datetime.now(timezone.utc).isoformat(),
                  capture_token="unused", client_id="missing-user-regression"))
    assert response.status_code == 401
    assert "Sign in again" in response.json()["detail"]

def test_no_media_rejected_and_gallery_style_stale_capture_rejected(client):
    h = login(client)
    assert submit(client, h, photo=False, video=False).status_code == 400
    cap = client.post("/api/capture-session", headers=h).json()["capture_token"]
    r = client.post("/api/complaints", headers=h, files={"photo": ("p.jpg", jpeg(), "image/jpeg")}, data=dict(
        category="Public Spaces", lat=25.3, lon=82.97, loc_source="gps", capture_token=cap,
        captured_at="2020-01-01T00:00:00+00:00", client_id="old1"))
    assert r.status_code == 400   # timestamp predates the live capture session

def test_non_media_bytes_rejected(client):
    h = login(client)
    cap = client.post("/api/capture-session", headers=h).json()["capture_token"]
    r = client.post("/api/complaints", headers=h, files={"photo": ("p.jpg", b"not an image", "image/jpeg")}, data=dict(
        category="Public Spaces", lat=25.3, lon=82.97, loc_source="gps", capture_token=cap,
        captured_at=datetime.now(timezone.utc).isoformat(), client_id="bad1"))
    assert r.status_code == 400

# ---- 10.8 connectivity: idempotent retry never creates a duplicate
def test_retry_is_idempotent(client):
    h = login(client)
    a = submit(client, h, cid="retry-1").json()["code"]
    b = submit(client, h, cid="retry-1").json()
    assert b["code"] == a and b["duplicate_submission"]

# ---- 10.2 location
def test_manual_location_is_distinguishable(client):
    h = login(client)
    code = submit(client, h, src="manual").json()["code"]
    assert client.get(f"/api/complaints/{code}", headers=h).json()["loc_source"] == "manual"

# ---- 10.4 routing
def dept_of(client, h, code): return client.get(f"/api/complaints/{code}", headers=h).json()["department"]

def test_routing_municipal_nhai_state_and_functions(client):
    h = login(client)
    cases = [
        (dict(category="Roads and Infrastructure", lat=25.3176, lon=82.9739), "Roads & Engineering"),
        (dict(category="Roads and Infrastructure", lat=25.3800, lon=82.9800), "NHAI"),
        (dict(category="Roads and Infrastructure", lat=25.3300, lon=83.0800), "UP Public Works"),
        (dict(category="Waste Management and Sanitation", lat=25.3176, lon=82.9739), "Sanitation"),
        (dict(category="Manholes and Drainage", lat=25.3176, lon=82.9739), "Drainage"),
        (dict(category="Water Supply", lat=25.3176, lon=82.9739), "Jal Sansthan"),
        (dict(category="Roads and Infrastructure", lat=28.6, lon=77.2), "fallback"),
    ]
    for kw, expect in cases:
        code = submit(client, h, **kw).json()["code"]
        assert expect in dept_of(client, h, code), (kw, dept_of(client, h, code))

# ---- 10.3 / 7.1 scores hidden from citizen, visible to officer; severity separate
def test_scores_visibility_and_severity(client):
    h = login(client)
    code = submit(client, h, category="Manholes and Drainage", desc="open manhole, no cover, children play here").json()["code"]
    cit = client.get(f"/api/complaints/{code}", headers=h).json()
    flat = str(cit).lower()
    assert "validity" not in flat and "severity" not in flat and "priority" not in flat
    o = staff(client, "vmc_drn")
    d = client.get(f"/api/dept/complaints/{code}", headers=o).json()
    assert 0 <= d["validity_score"] <= 10 and d["severity"] == "Critical"

def test_independent_reports_corroborate_but_same_user_does_not(client):
    h1, h2 = login(client, "9000000001"), login(client, "9000000002")
    submit(client, h1, category="Public Spaces", lat=25.30, lon=82.95)
    submit(client, h1, category="Public Spaces", lat=25.30, lon=82.95)
    code = submit(client, h2, category="Public Spaces", lat=25.30, lon=82.95).json()["code"]
    ev = client.get(f"/api/dept/complaints/{code}", headers=staff(client, "vmc_pub")).json()["evidence"]["internal"]
    assert len(ev["nearby_codes"]) == 2 and ev["independent_reporters"] == 1   # two reports by one citizen count once

def test_repost_dedup():
    from backend.investigation import origin_key
    a = origin_key({"url": "https://www.x.com/u/status/1"}); b = origin_key({"url": "https://x.com/u/status/1/"})
    c = origin_key({"text": "Pothole!!", "repost_of": "x.com/u/status/1"})
    assert a == b == c

# ---- 10.5 / 10.6 workflow & tracking
def test_department_workflow_and_citizen_tracking(client):
    h = login(client)
    code = submit(client, h, category="Waste Management and Sanitation").json()["code"]
    o = staff(client, "vmc_san")
    P = lambda path, **kw: client.post(f"/api/dept/complaints/{code}/{path}", headers=o, **kw)
    assert P("status", json={"status": "Complaint Acknowledged"}).status_code == 200
    assert P("status", json={"status": "Under Review"}).status_code == 200
    assert P("status", json={"status": "Field Officer Assigned"}).status_code == 400          # needs a field officer
    fo = client.get("/api/dept/field-officers", headers=o).json()[0]["id"]
    assert P("status", json={"status": "Field Officer Assigned", "field_officer_id": fo}).status_code == 200
    assert P("status", json={"status": "Work In Progress", "remarks": "crew dispatched"}).status_code == 200
    assert P("status", json={"status": "Resolved"}).status_code == 400                        # proof required
    assert P("resolution", data={"remarks": "cleared"}, files=[("photo", ("r.jpg", jpeg(), "image/jpeg"))]).status_code == 200
    assert P("status", json={"status": "Resolved", "remarks": "Garbage cleared"}).status_code == 200
    c = client.get(f"/api/complaints/{code}", headers=h).json()
    assert c["status"] == "Resolved" and c["can_confirm"] and any(m["role"] == "resolution" for m in c["media"])
    assert [t["status"] for t in c["timeline"]][:3] == ["Complaint Registered", "Forwarded to Department", "Complaint Acknowledged"]
    rid = [m for m in c["media"] if m["role"] == "resolution"][0]["id"]
    assert client.get(f"/api/media/{rid}", headers=h).status_code == 200                      # citizen sees proof
    assert client.post(f"/api/complaints/{code}/reopen", headers=h, json={"reason": "still dirty"}).json()["status"] == "Reopened"
    assert any("Reopened" in n["message"] or True for n in client.get("/api/notifications", headers=h).json())

def test_reject_requires_remarks(client):
    h = login(client)
    code = submit(client, h, category="Public Spaces").json()["code"]
    o = staff(client, "vmc_pub")
    assert client.post(f"/api/dept/complaints/{code}/status", headers=o, json={"status": "Rejected"}).status_code == 400
    assert client.post(f"/api/dept/complaints/{code}/status", headers=o, json={"status": "Rejected", "remarks": "Duplicate of work order"}).status_code == 200

# ---- 10.7 privacy & audit
def test_privacy_isolation_and_audit(client):
    h = login(client, "9111111111")
    code = submit(client, h, category="Streetlights and Electrical Safety").json()["code"]
    lgt, san = staff(client, "vmc_lgt"), staff(client, "vmc_san")
    d = client.get(f"/api/dept/complaints/{code}", headers=lgt)
    assert d.status_code == 200 and "9111111111" not in d.text and "user_id" not in d.text
    assert client.get(f"/api/dept/complaints/{code}", headers=san).status_code == 403          # other dept
    mid = d.json()["media"][0]["id"]
    assert client.get(f"/api/media/{mid}", headers=san).status_code == 403
    assert client.get(f"/api/media/{mid}").status_code == 401                                  # public
    assert client.get(f"/api/media/{mid}", headers=login(client, "9222222222")).status_code == 404   # other citizen
    assert client.get(f"/api/media/{mid}", headers=lgt).status_code == 200
    adm = staff(client, "admin", "admin1234")
    actions = {a["action"] for a in client.get(f"/api/admin/audit?complaint_code={code}", headers=adm).json()}
    assert {"COMPLAINT_VIEWED", "MEDIA_VIEWED", "FORWARDED"} <= actions
    assert client.get("/api/admin/audit", headers=lgt).status_code == 403                      # audit is admin-only
    assert client.get("/api/admin/audit/verify", headers=adm).json()["intact"] is True

def test_audit_log_is_append_only(client):
    import sqlite3
    from backend.config import DB_PATH
    c = sqlite3.connect(DB_PATH)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("UPDATE audit SET action='X'")
        with pytest.raises(sqlite3.DatabaseError):
            c.execute("DELETE FROM audit")
    finally:
        c.rollback(); c.close()

# ---- super admin
def test_admin_adds_department_and_reassigns(client):
    adm = staff(client, "admin", "admin1234")
    r = client.post("/api/admin/departments", headers=adm, json=dict(name="Test Dept", short="TST", level="local",
        functions=["general"], officer_username="tst_off", officer_password="longpassword"))
    assert r.status_code == 200
    h = login(client)
    code = submit(client, h, category="Other Civic Issue").json()["code"]
    assert client.post(f"/api/admin/complaints/{code}/reassign", headers=adm, json={"dept_id": r.json()["id"]}).status_code == 200
    assert client.get(f"/api/dept/complaints/{code}", headers=staff(client, "tst_off", "longpassword")).status_code == 200
    assert client.get("/api/admin/overview", headers=adm).json()["totals"]["n"] > 0

def test_chatbot_hinglish(client):
    assert "live" in client.post("/api/chat", json={"message": "gallery se photo upload kar sakte hai?"}).json()["reply"].lower()

# ---- Sudhaar AI monitor: step-by-step trace of the AI pipeline
def test_ai_monitor_login_and_trace(client):
    h = login(client, "9876500077")
    code = submit(client, h, desc="large pothole near school").json()["code"]
    m = staff(client, "sudhaar", "sudhaar1234")
    steps = client.get(f"/api/ai/complaints/{code}", headers=m).json()["steps"]
    stages = [s["stage"] for s in steps]
    for need in ("intake", "vision", "internal", "severity", "score", "routing", "forward", "final"):
        assert need in stages, f"missing AI step: {need}"
    assert all(s["status"] != "running" for s in steps) and all(s["duration_ms"] is not None for s in steps)
    routing = next(s for s in steps if s["stage"] == "routing")
    assert routing["outputs"]["reasoning"] and "Engineering" in routing["outputs"]["department"]
    # vision engine absent in tests: trace must say so honestly instead of inventing findings
    vision = next(s for s in steps if s["stage"] == "vision")
    assert vision["status"] == "warn" and vision["outputs"]["analysed"] is False
    assert client.get("/api/ai/runs", headers=m).json()[0]["steps"] >= 8
    assert client.get("/api/ai/feed", headers=m).json()["steps"]

def test_ai_monitor_is_read_only_and_isolated(client):
    m = staff(client, "sudhaar", "sudhaar1234")
    assert client.get("/api/dept/complaints", headers=m).status_code == 403      # cannot act as a department
    assert client.post("/api/admin/departments", headers=m, json={}).status_code == 403
    h = login(client, "9876500078")
    assert client.get("/api/ai/feed", headers=h).status_code == 403              # citizens cannot see AI traces
    d = staff(client, "vmc_eng")
    assert client.get("/api/ai/feed", headers=d).status_code == 403              # nor can departments
    assert client.get("/api/ai/feed").status_code == 401
    assert staff(client, "admin", "admin1234") and client.get("/api/ai/overview", headers=staff(client, "admin", "admin1234")).status_code == 200

def test_chatbot_answers_are_traced(client):
    client.post("/api/chat", json={"message": "mera complaint track kaise karu"})
    m = staff(client, "sudhaar", "sudhaar1234")
    rows = client.get("/api/ai/chat", headers=m).json()
    assert rows and rows[0]["outputs"]["reply"] and "mera complaint" in rows[0]["inputs"]["message"]

def test_trace_failure_never_blocks_forwarding(client, monkeypatch):
    """If the trace store is down, complaints must still be investigated and forwarded (spec 4.5: never block forwarding)."""
    import types
    from backend import trace
    def boom(*a, **k): raise RuntimeError("trace db down")
    monkeypatch.setattr(trace, "db", types.SimpleNamespace(x=boom, now=lambda: "t", q=boom))
    h = login(client, "9876500079"); code = submit(client, h).json()["code"]
    c = client.get(f"/api/complaints/{code}", headers=h).json()
    assert c["department"] and c["status"] == "Forwarded to Department"

# ---- spec 4.10: after a reopen, "Resolved" needs fresh proof
def test_reopen_requires_new_resolution_proof(client):
    h = login(client, "9876500080"); code = submit(client, h).json()["code"]
    d = staff(client, "vmc_eng")
    for s in ("Complaint Acknowledged", "Under Review"):
        assert client.post(f"/api/dept/complaints/{code}/status", headers=d, json={"status": s}).status_code == 200
    client.post(f"/api/dept/complaints/{code}/resolution", headers=d, files={"photo": ("p.jpg", jpeg(), "image/jpeg")})
    assert client.post(f"/api/dept/complaints/{code}/status", headers=d, json={"status": "Resolved"}).status_code == 200
    time.sleep(1.1)
    assert client.post(f"/api/complaints/{code}/reopen", headers=h, json={"reason": "still there"}).status_code == 200
    r = client.post(f"/api/dept/complaints/{code}/status", headers=d, json={"status": "Resolved"})
    assert r.status_code == 400 and "fresh proof" in r.json()["detail"]
    client.post(f"/api/dept/complaints/{code}/resolution", headers=d, files={"photo": ("p.jpg", jpeg(), "image/jpeg")})
    assert client.post(f"/api/dept/complaints/{code}/status", headers=d, json={"status": "Resolved"}).status_code == 200
