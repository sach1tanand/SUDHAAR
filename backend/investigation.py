"""Multi-source evidence investigation (spec §4.4-4.6).

Everything here produces *supporting* information for departmental officers. It never blocks forwarding.
The scoring formula and severity rubric are PROVISIONAL (spec lists them as deferred decisions) and are
isolated in WEIGHTS / severity_rules() so they can be tuned during testing.
"""
import base64, hashlib, json, os, re, shutil, subprocess, tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from . import db, config, vision
from .trace import NullTracer
from .routing import haversine_m, CATEGORIES

WEIGHTS = dict(  # PROVISIONAL - tune with real data. Weights add up to exactly 10 (own evidence 8 + corroboration 2).
    # --- own evidence: what the reporter's own capture proves (max 8 when vision is available) ---
    video=2.6, photo_gps=2.2, photo=1.6, both_bonus=0.4, capture_cap=3.0,      # how it was captured   (max 3.0)
    loc_gps=0.7, loc_manual=0.35, description=0.3,                              # context               (max 1.0)
    vision=4.0, vision_mismatch=0.25,                                           # AI saw the problem    (max 4.0)
    own_max=8.0, own_max_no_vision=6.0,   # without a vision result the capture+context evidence is scaled to 6, not 8
    # --- corroboration bonus: independent confirmation (max 2.0). Absence is NOT evidence against a complaint. ---
    internal_each=0.6, internal_cap=2, external_each=0.4, external_cap=2, rain=0.3, bonus_max=2.0,
)
NEARBY_M, LOOKBACK_DAYS = 150, 90

# ------------------------------------------------------------------ computer vision
def _frame_from_video(path: str) -> bytes | None:
    if not shutil.which("ffmpeg"): return None
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "f.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", path, "-frames:v", "1", out],
                       timeout=60, check=False)
        return open(out, "rb").read() if os.path.exists(out) else None

def _vision_claude(img: bytes, category: str) -> dict:
    prompt = (f"A citizen reported a civic problem in category '{category}'. Examine the photo. Reply ONLY with JSON: "
              '{"detected":[list of civic issues visible, e.g. "pothole","open manhole","garbage accumulation","exposed wire",'
              '"waterlogging","broken streetlight","damaged road"],"matches_category":true|false,"confidence":0-1,'
              '"size_hint":"small|medium|large|unknown","hazard_notes":"short"}')
    r = httpx.post("https://api.anthropic.com/v1/messages", timeout=60,
                   headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
                   json={"model": config.ANTHROPIC_MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": [
                       {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(img).decode()}},
                       {"type": "text", "text": prompt}]}]})
    r.raise_for_status()
    txt = "".join(b.get("text", "") for b in r.json()["content"])
    return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))

def analyse_media(media: list[dict], category: str, tr=None) -> dict:
    """Returns AI findings. Never raises; failures are recorded as 'not analysed'."""
    tr = tr or NullTracer(None)
    findings, engine = [], "none"
    with tr.step("vision", "Computer-vision analysis", category=category, media=len(media),
                 engines_available=dict(yolo=[n for n, _ in config.YOLO_MODELS], claude_vision=bool(config.ANTHROPIC_API_KEY))) as st:
        out = _analyse_media(media, category, findings, st)
        st.out(engine=out["engine"], analysed=out["analysed"], detected=out["detected"], confidence=round(out["confidence"], 2),
               matches_category=out["matches_category"], per_media=[{k: v for k, v in f.items() if k not in ("hazard_notes", "detections")} for f in out["findings"]])
        if not out["analysed"]:
            st.warn("No vision engine produced a result - the score omits the vision component and officers are told to review media manually.")
        elif out["matches_category"] is False:
            st.warn(f"Media may not match the selected category '{category}' (flagged for officers; complaint is still forwarded).")
        return out

def _analyse_one(m: dict, category: str, st) -> tuple[dict | None, str]:
    """One media item -> (findings, engine). YOLO (all configured models, photos and video frames) comes first;
    Claude vision is the fallback when YOLO is not configured or every YOLO model failed."""
    path = m["path"]
    if config.YOLO_MODELS:
        try:
            f = vision.analyse_photo(path, category) if m["kind"] == "photo" else vision.analyse_video(path, category)
            for name, err in f.get("model_errors", {}).items(): st.warn(f"YOLO model '{name}' failed: {err}")
            return f, "yolo"
        except Exception as e:
            if not config.ANTHROPIC_API_KEY: raise
            st.warn(f"YOLO failed ({str(e)[:100]}); falling back to Claude vision")
    if config.ANTHROPIC_API_KEY:
        img = open(path, "rb").read() if m["kind"] == "photo" else _frame_from_video(path)
        if img: return _vision_claude(img, category), "claude-vision"
    return None, "none"

def _analyse_media(media, category, findings, st) -> dict:
    engines = []
    for m in media:
        try:
            f, engine = _analyse_one(m, category, st)
            if f: findings.append({"media_id": m["id"], "kind": m["kind"], "engine": engine, **f}); engines.append(engine)
            else: st.note(f"media #{m['id']} ({m['kind']}): no engine configured or no frame extractable")
        except Exception as e:  # AI may fail; the complaint must still be forwarded
            findings.append({"media_id": m["id"], "error": str(e)[:200]}); st.fail(f"media #{m['id']}: {str(e)[:150]}")
    ok = [f for f in findings if "error" not in f]
    return dict(engine="+".join(sorted(set(engines))) or "none", analysed=bool(ok), findings=findings,
                confidence=max([float(f.get("confidence", 0)) for f in ok], default=0.0),
                detected=sorted({d for f in ok for d in f.get("detected", [])}),
                matches_category=any(f.get("matches_category") for f in ok) if ok else None,
                disclaimer="AI findings are supporting information, not conclusions. Verify on site.")

# ------------------------------------------------------------------ internal corroboration
def internal_matches(c: dict) -> dict:
    rows = db.q("SELECT code,user_id,lat,lon,created_at,status FROM complaints WHERE category=? AND id<>? "
                "AND created_at >= datetime('now', ?)", (c["category"], c["id"], f"-{LOOKBACK_DAYS} days"))
    near = [r for r in rows if haversine_m(c["lat"], c["lon"], r["lat"], r["lon"]) <= NEARBY_M]
    indep = {r["user_id"] for r in near if r["user_id"] != c["user_id"]}
    return dict(nearby_codes=[r["code"] for r in near][:20], independent_reporters=len(indep),
                same_reporter_repeats=sum(1 for r in near if r["user_id"] == c["user_id"]),
                radius_m=NEARBY_M, lookback_days=LOOKBACK_DAYS)

# ------------------------------------------------------------------ external corroboration
def origin_key(item: dict) -> str:
    """Posts that repeat one original share a key and count once."""
    if item.get("repost_of"): return "u:" + item["repost_of"]
    if item.get("url"):
        u = urlparse(item["url"]); return "u:" + u.netloc.lower().removeprefix("www.") + u.path.rstrip("/")
    return "t:" + hashlib.sha1(re.sub(r"\W+", " ", item.get("text", "").lower())[:200].encode()).hexdigest()

def _news(query: str) -> list[dict]:
    key = os.environ.get("NEWSAPI_KEY")
    if not key or config.OFFLINE: return []
    r = httpx.get("https://newsapi.org/v2/everything", timeout=15,
                  headers={"X-Api-Key": key},
                  params={"q": query, "pageSize": 10, "sortBy": "publishedAt", "language": "en"})
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok": raise RuntimeError(data.get("message", "NewsAPI request failed"))
    return [dict(source="news", url=a["url"], text=a["title"] or "", published=a["publishedAt"])
            for a in data.get("articles", []) if a.get("url")]

# Social platforms need approved API access / have restrictive terms (spec §9.6). Register adapters here:
#   SOCIAL_ADAPTERS.append(fn)  where fn(query, lat, lon) -> [{"source","url","text","published","repost_of"?}]
SOCIAL_ADAPTERS: list = []

def _reddit(query: str, lat: float, lon: float) -> list[dict]:
    """Search Reddit using its approved Data API application-only OAuth flow."""
    client_id, client_secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "web:sudhaar-civic:v1.0 (by u/replace_me)")
    if not client_id or not client_secret or config.OFFLINE: return []
    with httpx.Client(timeout=15, auth=(client_id, client_secret), headers={"User-Agent": user_agent}) as client:
        token_res = client.post("https://www.reddit.com/api/v1/access_token",
                                data={"grant_type": "client_credentials"})
        token_res.raise_for_status()
        token = token_res.json()["access_token"]
        res = client.get("https://oauth.reddit.com/search.json",
                         params={"q": query, "sort": "new", "t": "month", "limit": 10, "type": "link"},
                         headers={"Authorization": f"Bearer {token}"})
        res.raise_for_status()
        children = res.json().get("data", {}).get("children", [])
        return [dict(source="reddit", url="https://www.reddit.com" + item["permalink"],
                     text=item.get("title", ""),
                     published=datetime.fromtimestamp(item["created_utc"], timezone.utc).isoformat())
                for row in children if (item := row.get("data", {})).get("permalink")]

def external_matches(c: dict) -> dict:
    q = f"Varanasi {c['category']} {(c.get('description') or '')[:60]}".strip()
    items, errors = [], []
    adapters = list(SOCIAL_ADAPTERS)
    if os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"):
        adapters.append(_reddit)
    for fn in [lambda: _news(q)] + [lambda f=f: f(q, c["lat"], c["lon"]) for f in adapters]:
        try: items += fn()
        except Exception as e: errors.append(str(e)[:120])
    groups: dict[str, list] = {}
    for it in items: groups.setdefault(origin_key(it), []).append(it)
    return dict(raw_items=len(items), independent_sources=len(groups),
                sources=[dict(origin=k, copies=len(v), first=v[0]) for k, v in list(groups.items())[:10]],
                adapters_configured=bool(os.environ.get("NEWSAPI_KEY")) or bool(adapters), errors=errors)

# ------------------------------------------------------------------ contextual sources
def weather_context(c: dict) -> dict:
    if CATEGORIES.get(c["category"]) not in ("drainage", "roads", "water", "public_spaces"):
        return dict(relevant=False)
    if config.OFFLINE: return dict(relevant=True, available=False, error="offline mode")
    try:  # Open-Meteo: free, no key
        r = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=10, params=dict(
            latitude=c["lat"], longitude=c["lon"], past_days=3, forecast_days=1, daily="precipitation_sum", timezone="auto"))
        vals = r.json()["daily"]["precipitation_sum"]
        return dict(relevant=True, available=True, precip_mm_last_days=vals, heavy_rain=any((v or 0) >= 20 for v in vals))
    except Exception as e:
        return dict(relevant=True, available=False, error=str(e)[:100])

def street_view_context(c: dict) -> dict:
    key = os.environ.get("GOOGLE_MAPS_KEY")
    if not key or config.OFFLINE: return dict(available=False, note="GOOGLE_MAPS_KEY not set. Historical imagery is context only, not proof of current condition.")
    try:
        r = httpx.get("https://maps.googleapis.com/maps/api/streetview/metadata", timeout=10,
                      params=dict(location=f"{c['lat']},{c['lon']}", key=key)).json()
        return dict(available=r.get("status") == "OK", imagery_date=r.get("date"),
                    note="Historical imagery is context only, not proof of current condition.")
    except Exception as e:
        return dict(available=False, error=str(e)[:100])

# ------------------------------------------------------------------ scoring
def validity_score(c: dict, media: list[dict], ai: dict, internal: dict, external: dict, weather: dict, sv: dict) -> dict:
    """0-10 evidence validity. Own evidence (capture + context + AI vision) is worth 8; independent corroboration
    (other citizens, news, heavy rain for drainage) adds up to 2. Nothing is double counted and no component is
    clipped away: the weights sum to 10. Street View availability earns no credit (it says nothing about validity)."""
    W = WEIGHTS
    kinds = {m["kind"] for m in media}
    has_gps = c.get("loc_source") == "gps"
    raw = {}
    cap = 0.0
    if "video" in kinds: cap = W["video"]
    elif "photo" in kinds: cap = W["photo_gps"] if has_gps else W["photo"]
    if len(kinds) == 2: cap += W["both_bonus"]
    if cap: raw["live_capture"] = min(cap, W["capture_cap"])
    if c.get("captured_at") and c.get("lat") is not None: raw["location_and_time"] = W["loc_gps"] if has_gps else W["loc_manual"]
    if (c.get("description") or "").strip(): raw["description"] = W["description"]
    vision_ok = bool(ai.get("analysed"))
    if vision_ok:
        factor = 1.0 if ai.get("matches_category") else W["vision_mismatch"]
        raw["vision"] = W["vision"] * max(0.0, min(1.0, float(ai.get("confidence") or 0))) * factor
    available = W["capture_cap"] + W["loc_gps"] + W["description"] + (W["vision"] if vision_ok else 0.0)
    k = (W["own_max"] if vision_ok else W["own_max_no_vision"]) / available
    parts = {n: v * k for n, v in raw.items()}
    own = sum(parts.values())
    bonus_parts = {}
    n_int = min(internal.get("independent_reporters", 0), W["internal_cap"])
    if n_int: bonus_parts["other_citizens"] = W["internal_each"] * n_int
    n_ext = min(external.get("independent_sources", 0), W["external_cap"])
    if n_ext: bonus_parts["news_or_social"] = W["external_each"] * n_ext
    if weather.get("heavy_rain") and CATEGORIES.get(c.get("category")) == "drainage": bonus_parts["heavy_rain"] = W["rain"]
    raw_bonus = sum(bonus_parts.values())
    bonus = min(W["bonus_max"], raw_bonus)
    if raw_bonus > bonus and raw_bonus:   # keep the parts consistent with the total when the cap bites
        bonus_parts = {n: v * bonus / raw_bonus for n, v in bonus_parts.items()}
    parts.update(bonus_parts)
    score = round(max(0.0, min(10.0, own + bonus)), 1)
    note = ("Own evidence is scored out of 8 and independent corroboration adds up to 2. "
            + ("" if vision_ok else "No AI vision result was available, so own evidence is scored out of 6. ")
            + "Provisional formula. Not a rejection threshold: every complaint is forwarded.")
    return dict(score=score, parts={k_: round(v, 2) for k_, v in parts.items()}, max=10, own_max=W["own_max"] if vision_ok else W["own_max_no_vision"], note=note)

# ------------------------------------------------------------------ severity
SEV_ORDER = ["Low", "Medium", "High", "Critical"]
CRIT_WORDS = r"open manhole|uncovered manhole|no cover|exposed wire|live wire|electrocut|sparking|collapsed|child fell|fell in|drown|accident|injur|death|died"
HIGH_WORDS = r"deep|large|huge|big|highway|bridge|school|hospital|night|dark|flood|overflow|sewage|blocked road"

def severity(c: dict, ai: dict, internal: dict) -> dict:
    func = CATEGORIES.get(c["category"], "general")
    text = ((c.get("description") or "") + " " + " ".join(ai.get("detected", []))).lower()
    lvl, why = 0, []
    base = {"drainage": 1, "lighting": 1, "roads": 1, "traffic": 1, "water": 1, "sanitation": 0, "public_spaces": 0, "general": 0}[func]
    lvl = base
    if re.search(CRIT_WORDS, text): lvl = 3; why.append("Description/AI mentions an immediate danger to life")
    elif re.search(HIGH_WORDS, text): lvl = max(lvl, 2); why.append("Size/location/hazard keywords raise severity")
    if func == "lighting" and re.search(r"wire|electr|spark", text): lvl = 3; why.append("Electrical hazard")
    if func == "drainage" and re.search(r"manhole", text) and "cover" in text: lvl = 3
    if any(s in ai.get("detected", []) for s in ("open manhole", "exposed wire")): lvl = 3; why.append("Computer vision flagged a critical hazard")
    sizes = {f.get("size_hint") for f in ai.get("findings", []) if isinstance(f, dict)}
    if "large" in sizes: lvl = max(lvl, 2); why.append("Large defect in imagery")
    if internal["independent_reporters"] >= 2 and lvl < 3: lvl += 1; why.append("Multiple independent citizens reported the same issue")
    lvl = min(lvl, 3)
    if not why: why.append(f"Default for category '{c['category']}'")
    # priority: 1 (most urgent) .. 4
    return dict(category=SEV_ORDER[lvl], priority=4 - lvl, reasons=why,
                note="Severity is independent of evidence validity; critical/high are never delayed waiting for corroboration.")

# ------------------------------------------------------------------ entry
def investigate(c: dict, media: list[dict], ai: dict | None = None, enrich: bool = True, tr=None) -> dict:
    """enrich=False is the fast phase (vision + internal reports + severity) so complaints are forwarded
    immediately; enrich=True adds slow external/contextual sources and recomputes the score."""
    tr = tr or NullTracer(None)
    sfx = " (final pass)" if enrich else " (fast pass)"
    ai = ai or analyse_media(media, c["category"], tr)
    with tr.step("internal", "Search Sudhaar's own complaints for the same problem" + sfx, category=c["category"],
                 radius_m=NEARBY_M, lookback_days=LOOKBACK_DAYS) as st:
        internal = internal_matches(c)
        st.out(**internal)
        st.note(f"{internal['independent_reporters']} independent citizen(s) nearby; same-citizen repeats ({internal['same_reporter_repeats']}) are not counted twice.")
    if enrich and c.get("lat") is not None:
        with tr.step("external", "Look for external corroboration (news / social)", query=f"Varanasi {c['category']}") as st:
            external = external_matches(c); st.out(**{k: v for k, v in external.items() if k != "sources"}, sources=external["sources"][:3])
            if not external["adapters_configured"]: st.skip("No external adapters configured (NEWSAPI_KEY / SOCIAL_ADAPTERS). Reposts would be de-duplicated by origin.")
            elif external["errors"]: st.warn("; ".join(external["errors"]))
        with tr.step("weather", "Check rainfall context", lat=c["lat"], lon=c["lon"]) as st:
            weather = weather_context(c); st.out(**weather)
            if not weather.get("relevant"): st.skip("Weather is not relevant to this category")
            elif not weather.get("available"): st.warn(weather.get("error", "weather unavailable"))
        with tr.step("street_view", "Check historical Street View imagery") as st:
            sv = street_view_context(c); st.out(**sv)
            if not sv.get("available"): st.skip(sv.get("note") or sv.get("error") or "unavailable")
    else:
        external = dict(raw_items=0, independent_sources=0, sources=[], errors=[], pending=not enrich)
        weather, sv = dict(relevant=False, pending=True), dict(available=False, pending=True)
    with tr.step("severity", "Assess how dangerous the problem is" + sfx, category=c["category"], description=(c.get("description") or "")[:120]) as st:
        sev = severity(c, ai, internal)
        st.out(category=sev["category"], priority=sev["priority"], reasons=sev["reasons"])
        st.note("Severity is independent of evidence validity; critical/high are never held back for corroboration.")
    with tr.step("score", "Calculate evidence validity score (0-10)" + sfx, phase="final" if enrich else "initial") as st:
        val = validity_score(c, media, ai, internal, external, weather, sv)
        st.out(score=val["score"], parts=val["parts"])
        st.note("Provisional formula - the score never blocks forwarding.")
    return dict(ai=ai, evidence=dict(internal=internal, external=external, weather=weather, street_view=sv, score_breakdown=val),
                validity=val["score"], severity=sev, enriched=enrich)
