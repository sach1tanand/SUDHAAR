"""AI step tracing: every stage of the Sudhaar pipeline (and the helper chatbot) records what it received,
what it decided and how long it took, so the `sudhaar` monitor login can replay exactly how the AI worked.

A step is written as 'running' when it starts and finalised when it ends, so a live view can watch a
complaint move through the pipeline. Tracing must never break the pipeline: every write is guarded.
"""
import json, time, uuid
from . import db

def _safe(v, depth=0):
    """Make values JSON-safe and bounded in size (no giant blobs in the trace table)."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v[:600] if isinstance(v, str) else v
    if depth > 3: return str(v)[:200]
    if isinstance(v, dict): return {str(k): _safe(x, depth + 1) for k, x in list(v.items())[:30]}
    if isinstance(v, (list, tuple, set)): return [_safe(x, depth + 1) for x in list(v)[:20]]
    return str(v)[:200]

class Step:
    def __init__(self, tracer, stage: str, title: str, inputs: dict):
        self.t, self.stage, self.title = tracer, stage, title
        self.inputs, self.outputs, self.notes, self.status = _safe(inputs), {}, [], "ok"
        self.t0, self.id = time.perf_counter(), None
        try:
            self.id = db.x("INSERT INTO ai_trace(run_id,complaint_code,seq,stage,title,status,inputs,outputs,notes,started_at) "
                           "VALUES(?,?,?,?,?,'running',?,'{}','[]',?)",
                           (tracer.run_id, tracer.code, tracer.next_seq(), stage, title, json.dumps(self.inputs), db.now()))
        except Exception as e:
            print("[sudhaar] trace start failed:", e)

    def out(self, **kw): self.outputs.update(_safe(kw)); return self
    def note(self, text: str): self.notes.append(str(text)[:300]); return self
    def warn(self, text: str): self.status = "warn" if self.status == "ok" else self.status; return self.note(text)
    def skip(self, text: str): self.status = "skipped"; return self.note(text)
    def fail(self, text: str): self.status = "error"; return self.note(text)

    def __enter__(self): return self
    def __exit__(self, et, ev, tb):
        if ev is not None: self.fail(f"{et.__name__}: {ev}")
        try:
            if self.id:
                db.x("UPDATE ai_trace SET status=?, outputs=?, notes=?, inputs=?, duration_ms=?, finished_at=? WHERE id=?",
                     (self.status, json.dumps(self.outputs), json.dumps(self.notes), json.dumps(self.inputs),
                      int((time.perf_counter() - self.t0) * 1000), db.now(), self.id))
        except Exception as e:
            print("[sudhaar] trace finish failed:", e)
        return False   # never swallow the pipeline's own exceptions

class Tracer:
    def __init__(self, code: str | None, run_id: str | None = None):
        self.code, self.run_id, self._seq = code, run_id or uuid.uuid4().hex[:12], 0
    def next_seq(self): self._seq += 1; return self._seq
    def step(self, stage: str, title: str, **inputs) -> Step: return Step(self, stage, title, inputs)

class NullTracer(Tracer):
    """Used when a caller doesn't want tracing (keeps investigation functions usable standalone)."""
    def step(self, stage, title, **inputs):
        s = Step.__new__(Step); s.t, s.id = self, None
        s.stage, s.title, s.inputs, s.outputs, s.notes, s.status, s.t0 = stage, title, {}, {}, [], "ok", time.perf_counter()
        return s

def _row(r: dict) -> dict:
    for k in ("inputs", "outputs", "notes"):
        try: r[k] = json.loads(r[k] or ("[]" if k == "notes" else "{}"))
        except Exception: r[k] = {}
    return r

def for_complaint(code: str) -> list[dict]:
    return [_row(r) for r in db.q("SELECT * FROM ai_trace WHERE complaint_code=? ORDER BY id", (code,))]

def feed(after: int = 0, limit: int = 100) -> list[dict]:
    return [_row(r) for r in db.q("SELECT * FROM ai_trace WHERE id>? ORDER BY id LIMIT ?", (after, limit))]

def recent(limit: int = 60) -> list[dict]:
    return [_row(r) for r in reversed(db.q("SELECT * FROM ai_trace ORDER BY id DESC LIMIT ?", (limit,)))]
