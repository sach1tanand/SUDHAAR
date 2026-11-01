"""Department identification & routing (spec §4.7).

Step 1 government level -> Step 2 functional responsibility -> Step 3 jurisdiction / infrastructure
ownership -> Step 4 department -> Step 5 forward to the department dashboard.

IMPORTANT: the zone geometries and department names seeded below are ILLUSTRATIVE PLACEHOLDERS for the
Varanasi pilot. Replace them with surveyed road-ownership / jurisdiction data (spec §9.6) using the
Super Admin console before any real deployment.
"""
import json, math
from . import db

CATEGORIES = {
    "Roads and Infrastructure": "roads",
    "Manholes and Drainage": "drainage",
    "Waste Management and Sanitation": "sanitation",
    "Streetlights and Electrical Safety": "lighting",
    "Water Supply": "water",
    "Traffic and Public Safety": "traffic",
    "Public Spaces": "public_spaces",
    "Other Civic Issue": "general",
}

SEED_DEPTS = [
    # name, short, level, functions, jurisdiction, is_fallback
    ("Varanasi Municipal Corporation - Roads & Engineering", "VMC-ENG", "local", ["roads"], "Varanasi Municipal Corporation limits", 0),
    ("Varanasi Municipal Corporation - Drainage & Sewerage", "VMC-DRN", "local", ["drainage"], "Varanasi Municipal Corporation limits", 0),
    ("Varanasi Municipal Corporation - Sanitation", "VMC-SAN", "local", ["sanitation"], "Varanasi Municipal Corporation limits", 0),
    ("Varanasi Municipal Corporation - Street Lighting & Electrical", "VMC-LGT", "local", ["lighting"], "Varanasi Municipal Corporation limits", 0),
    ("Varanasi Municipal Corporation - Parks & Public Spaces", "VMC-PUB", "local", ["public_spaces"], "Varanasi Municipal Corporation limits", 0),
    ("Jal Sansthan Varanasi - Water Supply", "JAL", "local", ["water"], "Varanasi urban area", 0),
    ("Varanasi Traffic Police", "VTP", "state", ["traffic"], "Varanasi Commissionerate", 0),
    ("UP Public Works Department - Varanasi Division", "UPPWD", "state", ["roads", "drainage"], "State-controlled roads, Varanasi", 0),
    ("NHAI - Varanasi Project Implementation Unit", "NHAI", "central", ["roads", "drainage"], "National highways, Varanasi", 0),
    ("VMC General Grievance Desk (fallback)", "VMC-GEN", "local", ["general"], "Varanasi Municipal Corporation limits", 1),
]

# Illustrative zones. geometry: polyline [[lat,lon],...] for corridors, bbox [s,w,n,e] for areas.
SEED_ZONES = [
    ("Varanasi Municipal Corporation area (illustrative bbox)", "area", "local", None, [25.20, 82.90, 25.42, 83.08], 0, [], "PLACEHOLDER"),
    ("NH bypass corridor (illustrative)", "corridor", "central", "NHAI", [[25.3750, 82.9150], [25.3800, 82.9800], [25.3700, 83.0500]], 45, ["roads", "drainage"], "PLACEHOLDER - replace with surveyed NH alignment"),
    ("State highway corridor (illustrative)", "corridor", "state", "UPPWD", [[25.3180, 83.0300], [25.3300, 83.0800], [25.3500, 83.1300]], 40, ["roads", "drainage"], "PLACEHOLDER - replace with surveyed SH alignment"),
]

def seed_monitor():
    """The `sudhaar` login: read-only AI monitor. Added separately so existing databases get it too."""
    if not db.q("SELECT 1 FROM officers WHERE username='sudhaar'"):
        from .security import hash_pw
        db.x("INSERT INTO officers(username,pw_hash,name,role,dept_id) VALUES(?,?,?,?,NULL)",
             ("sudhaar", hash_pw("sudhaar1234"), "Sudhaar AI Monitor", "ai_monitor"))

def seed():
    seed_monitor()
    if db.q("SELECT 1 FROM departments LIMIT 1"):
        return
    ids = {}
    for name, short, level, funcs, jur, fb in SEED_DEPTS:
        ids[short] = db.x("INSERT INTO departments(name,short,level,functions,jurisdiction,is_fallback) VALUES(?,?,?,?,?,?)",
                          (name, short, level, json.dumps(funcs), jur, fb))
    for name, kind, level, short, geom, buf, cats, note in SEED_ZONES:
        db.x("INSERT INTO zones(name,kind,owner_level,dept_id,geometry,buffer_m,categories,note) VALUES(?,?,?,?,?,?,?,?)",
             (name, kind, level, ids.get(short), json.dumps(geom), buf, json.dumps(cats), note))
    from .security import hash_pw
    db.x("INSERT INTO officers(username,pw_hash,name,role,dept_id) VALUES(?,?,?,?,NULL)",
         ("admin", hash_pw("admin1234"), "Super Admin", "super_admin"))
    for short, did in ids.items():
        u = short.lower().replace("-", "_")
        db.x("INSERT INTO officers(username,pw_hash,name,role,dept_id) VALUES(?,?,?,?,?)",
             (u, hash_pw("demo1234"), f"{short} Officer", "officer", did))
        for i in (1, 2):
            db.x("INSERT INTO field_officers(dept_id,name,phone) VALUES(?,?,?)", (did, f"{short} Field Officer {i}", ""))

def _m_per_deg(lat): return 111_320.0, 111_320.0 * math.cos(math.radians(lat))

def dist_to_polyline_m(lat, lon, pts) -> float:
    my, mx = _m_per_deg(lat)
    best = float("inf")
    for (a_lat, a_lon), (b_lat, b_lon) in zip(pts, pts[1:]):
        ax, ay = (a_lon - lon) * mx, (a_lat - lat) * my
        bx, by = (b_lon - lon) * mx, (b_lat - lat) * my
        dx, dy = bx - ax, by - ay
        t = 0 if dx == dy == 0 else max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best

def haversine_m(a_lat, a_lon, b_lat, b_lon) -> float:
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))

def route(category: str, lat: float, lon: float) -> dict:
    func = CATEGORIES.get(category, "general")
    steps = []
    zones = db.q("SELECT * FROM zones")
    # Step 3a: infrastructure ownership (corridors take precedence over municipal ownership)
    for z in zones:
        if z["kind"] != "corridor": continue
        cats = json.loads(z["categories"] or "[]")
        if func not in cats: continue
        d = dist_to_polyline_m(lat, lon, json.loads(z["geometry"]))
        if d <= z["buffer_m"] and z["dept_id"]:
            steps.append(f"Location is {d:.0f} m from '{z['name']}' -> {z['owner_level']} government owns this road")
            dept = db.q("SELECT * FROM departments WHERE id=? AND active=1", (z["dept_id"],), one=True)
            if dept:
                steps.append(f"Function '{func}' + level '{z['owner_level']}' -> {dept['name']}")
                return dict(dept_id=dept["id"], level=z["owner_level"], function=func, confidence="high", fallback=False, steps=steps)
    # Step 3b: municipal area
    inside = any(z["kind"] == "area" and
                 (lambda b: b[0] <= lat <= b[2] and b[1] <= lon <= b[3])(json.loads(z["geometry"])) for z in zones)
    if inside:
        steps.append("Location is inside the municipal jurisdiction -> local government")
        for d in db.q("SELECT * FROM departments WHERE active=1 AND is_fallback=0"):
            if func in json.loads(d["functions"]) and d["level"] in ("local", "state") and \
               (d["level"] == "local" or func == "traffic"):
                steps.append(f"Function '{func}' -> {d['name']}")
                return dict(dept_id=d["id"], level=d["level"], function=func, confidence="high", fallback=False, steps=steps)
        fb = db.q("SELECT * FROM departments WHERE is_fallback=1 AND active=1", one=True)
        if fb:
            steps.append("No department matched the function; sent to the general grievance desk")
            return dict(dept_id=fb["id"], level="local", function=func, confidence="low", fallback=True, steps=steps)
    # Outside any known jurisdiction: provisional fallback = general desk, flagged for Super Admin reassignment.
    fb = db.q("SELECT * FROM departments WHERE is_fallback=1 AND active=1", one=True)
    steps.append("Location is outside configured jurisdictions; routed to the fallback desk and flagged for Super Admin review")
    return dict(dept_id=fb["id"] if fb else None, level="unknown", function=func, confidence="low", fallback=True, steps=steps)
