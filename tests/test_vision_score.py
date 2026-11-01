"""Multi-model YOLO + evidence-score tests. YOLO is stubbed, so these run without ultralytics or weights."""
import json, pytest
from backend import config, vision, investigation as inv


# ------------------------------------------------------------- fake ultralytics
class _T(list):            # tiny tensor-ish list
    pass

class FakeRes:
    def __init__(self, names, boxes, shape=(480, 640)):
        self.names = names; self.orig_shape = shape
        self.boxes = type("B", (), {})()
        self.boxes.cls = _T(b[0] for b in boxes); self.boxes.conf = _T(b[1] for b in boxes); self.boxes.xyxy = _T(b[2] for b in boxes)
        self.boxes.__class__.__len__ = lambda s: len(s.cls)

class FakeYOLO:
    def __init__(self, names, boxes=None, fail=False): self.names, self.boxes, self.fail = names, boxes or [], fail
    def __call__(self, path, verbose=False, conf=0.25): 
        if self.fail: raise RuntimeError("weights corrupted")
        return [FakeRes(self.names, self.boxes)]

@pytest.fixture
def two_models(monkeypatch):
    road = FakeYOLO({0: "pothole", 1: "crack"}, [(0, .82, (100, 100, 400, 400)), (1, .10, (0, 0, 10, 10))])   # 2nd is below threshold
    waste = FakeYOLO({0: "garbage"}, [(0, .60, (0, 0, 50, 50))])
    reg = {"/m/road.pt": road, "/m/waste.pt": waste}
    monkeypatch.setattr(config, "YOLO_MODELS", [("road", "/m/road.pt"), ("waste", "/m/waste.pt")])
    monkeypatch.setattr(vision, "_load", lambda p: reg[p])
    monkeypatch.setattr(vision, "_rules_cache", None)
    return reg


# ------------------------------------------------------------- config parsing
def test_parse_models_formats():
    assert config.parse_models("a=/x/a.pt, b=/x/b.pt") == [("a", "/x/a.pt"), ("b", "/x/b.pt")]
    assert config.parse_models("/x/best.pt;/y/best.pt") == [("best", "/x/best.pt"), ("best2", "/y/best.pt")]
    assert config.parse_models("") == []


# ------------------------------------------------------------- vision
def test_two_models_merge_and_category_match(two_models):
    f = vision.analyse_photo("img.jpg", "Roads and Infrastructure")
    assert f["matches_category"] is True and f["confidence"] == pytest.approx(.82)
    assert set(f["detected"]) == {"pothole", "garbage accumulation"}          # low-confidence crack ignored
    assert set(f["models"]) == {"road", "waste"} and f["size_hint"] in ("medium", "large")

def test_detection_for_other_category_does_not_match(two_models):
    f = vision.analyse_photo("img.jpg", "Water Supply")
    assert f["matches_category"] is False                                      # old code said True for any detection

def test_one_failing_model_does_not_kill_the_other(two_models):
    two_models["/m/waste.pt"].fail = True
    f = vision.analyse_photo("img.jpg", "Roads and Infrastructure")
    assert f["matches_category"] and "waste" in f["model_errors"]

def test_all_models_failing_raises(two_models):
    for m in two_models.values(): m.fail = True
    with pytest.raises(RuntimeError): vision.analyse_photo("img.jpg", "Roads and Infrastructure")

def test_label_normalisation_feeds_severity():
    assert vision.normalise("Open_Manhole")[0] == "open manhole"
    assert vision.normalise("exposed_wire")[0] == "exposed wire"

def test_class_map_override(tmp_path, monkeypatch):
    mp = tmp_path / "map.json"; mp.write_text(json.dumps({"xyz9": {"label": "pothole", "categories": ["roads"]}}))
    monkeypatch.setenv("SUDHAAR_YOLO_MAP", str(mp)); monkeypatch.setattr(vision, "_rules_cache", None)
    assert vision.normalise("XYZ9") == ("pothole", ["roads"])

def test_models_are_loaded_once(monkeypatch):
    calls = []
    monkeypatch.setattr(vision, "_cache", {})
    import types, sys
    mod = types.SimpleNamespace(YOLO=lambda p: calls.append(p) or FakeYOLO({0: "pothole"}))
    monkeypatch.setitem(sys.modules, "ultralytics", mod)
    vision._load("/m/a.pt"); vision._load("/m/a.pt"); vision._load("/m/a.pt")
    assert calls == ["/m/a.pt"]


# ------------------------------------------------------------- score
C = dict(loc_source="gps", captured_at="2026-01-01T00:00:00", lat=25.3, lon=82.9, description="big pothole", category="Roads and Infrastructure")
AI_OK = dict(analysed=True, confidence=1.0, matches_category=True)
AI_NONE = dict(analysed=False, confidence=0, matches_category=None)
NONE_I, NONE_E = dict(independent_reporters=0), dict(independent_sources=0)
def score(c=C, kinds=("video", "photo"), ai=AI_OK, i=NONE_I, e=NONE_E, w=None, sv=None):
    return inv.validity_score(c, [dict(kind=k) for k in kinds], ai, i, e, w or {}, sv or {})

def test_weights_add_up_to_ten():
    W = inv.WEIGHTS
    assert W["capture_cap"] + W["loc_gps"] + W["description"] + W["vision"] == pytest.approx(W["own_max"])
    assert W["own_max"] + W["bonus_max"] == pytest.approx(10)
    assert W["internal_each"] * W["internal_cap"] + W["external_each"] * W["external_cap"] == pytest.approx(W["bonus_max"])

def test_perfect_complaint_scores_exactly_ten():
    r = score(i=dict(independent_reporters=5), e=dict(independent_sources=5))
    assert r["score"] == 10.0 and sum(r["parts"].values()) == pytest.approx(10.0, abs=.02)

def test_no_vision_is_scaled_not_punished_to_a_ceiling():
    r = score(ai=AI_NONE)
    assert r["score"] == 6.0 and "scored out of 6" in r["note"]

def test_vision_mismatch_gets_little_credit():
    good = score(ai=AI_OK)["parts"]["vision"]; bad = score(ai=dict(AI_OK, matches_category=False))["parts"]["vision"]
    assert bad == pytest.approx(good * .25)

def test_first_report_is_not_penalised_for_no_corroboration():
    assert score()["score"] == 8.0

def test_manual_pin_scores_lower_than_gps():
    assert score(c=dict(C, loc_source="manual"))["score"] < score()["score"]

def test_rain_only_helps_drainage_and_street_view_gives_nothing():
    road = score(w=dict(heavy_rain=True))["score"]; assert road == score()["score"]
    drn = score(c=dict(C, category="Manholes and Drainage"), w=dict(heavy_rain=True))["score"]; assert drn == 8.3
    assert score(sv=dict(available=True))["score"] == score()["score"]

def test_bonus_is_capped_and_parts_stay_consistent():
    r = score(c=dict(C, category="Manholes and Drainage"), i=dict(independent_reporters=9), e=dict(independent_sources=9), w=dict(heavy_rain=True))
    assert r["score"] == 10.0 and sum(r["parts"].values()) == pytest.approx(10.0, abs=.02)
