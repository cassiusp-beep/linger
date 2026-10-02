"""Linger agent: a fixed loop with three LLM decision points (plan, label, branch) + recommend.

Every step is timed into a trace the UI replays. With no LLM available, every LLM step falls
back to rules, so the demo never dies.
"""
import json
import time
from . import llm
from .extract import extract_events
from .links import build_links, critical_moves, degrees, STATIONARY
from .branches import (gather_evidence, template_branches, llm_branches, verify,
                       zone_stats, light_stats, template_recommendation, llm_recommendation)
from .search import get_search, search_label

DEFAULT_QUERIES = ["people standing on the sidewalk", "people lingering near the bus stop",
                   "group of people stopped together", "person sitting on a bench or ledge",
                   "people walking around an obstacle", "people waiting to cross"]

PLAN_SYSTEM = """You plan video searches for a public-space design question. The archive holds short
segments from one fixed street camera, each described for pedestrian behavior only.
Return JSON {"queries": [4 to 6 short search phrases about observable behavior]}.
No faces, identity, emotion or clothing."""

LABEL_SYSTEM = """Label links between observed pedestrian events. For each link return
{"id","type","rationale"}: type is one of attracts|blocks|follows|displaces|co-occurs;
rationale is one sentence, max 20 words, observed behavior only. A link is an association,
not a cause: use "followed by", "near", "after"; never "caused", "because", "made".
Return JSON {"links": [...]}."""


class Trace:
    def __init__(self):
        self.steps = []

    def run(self, step, tool, fn, summarize):
        t0 = time.time()
        try:
            out, mode = fn(), "ok"
        except Exception as e:  # any failure becomes a visible, honest fallback
            out, mode = None, f"fallback ({type(e).__name__})"
        ms = int((time.time() - t0) * 1000)
        self.steps.append({"step": step, "tool": tool, "summary": summarize(out) if out is not None else mode,
                           "ms": ms, "mode": mode})
        return out


def _neighbors(hit_ids, segments, cam, pad=1):
    cam_segs = sorted([s for s in segments if s["camera_id"] == cam], key=lambda s: s["offset"])
    idx = {s["segment_id"]: i for i, s in enumerate(cam_segs)}
    keep = set()
    for sid in hit_ids:
        if sid in idx:
            for j in range(idx[sid] - pad, idx[sid] + pad + 1):
                if 0 <= j < len(cam_segs):
                    keep.add(j)
    return [cam_segs[j] for j in sorted(keep)]


def _vehicle_links(links, events):
    by = {e["id"]: e for e in events}
    return sum(1 for l in links if "vehicle" in (by[l["from"]].get("actor"), by[l["to"]].get("actor")))


def _pick_link(events, links, crit):
    by = {e["id"]: e for e in events}
    # a seating question is about where people stay, so start from the best-linked stationary move
    stay = [c for c in crit if by[c]["behavior"] in STATIONARY]
    top = (stay or crit or [None])[0]
    cands = [l for l in links if top in (l["from"], l["to"])] or links
    def rank(l):
        a, b = by[l["from"]], by[l["to"]]
        bus_draw = a["behavior"] == "bus_arrive" and b["behavior"] in STATIONARY  # the clearest cross-actor story
        both_stay = a["behavior"] in STATIONARY and b["behavior"] in STATIONARY
        return (bus_draw, both_stay, l["score"])
    return max(cands, key=rank) if cands else None


@llm.op
def ask(question, camera_id, segments, use_llm=None):
    use_llm = llm.available() if use_llm is None else use_llm
    search = get_search()
    tr = Trace()

    def plan():
        if not use_llm:
            return DEFAULT_QUERIES
        return llm.chat_json(PLAN_SYSTEM, f"CAMERA: {camera_id}\nQUESTION: {question}")["queries"][:6]
    queries = tr.run("Plan searches", "W&B LLM" if use_llm else "rules", plan,
                     lambda q: f"{len(q)} queries: " + "; ".join(q)) or DEFAULT_QUERIES

    def do_search():
        hits = []
        for q in queries:
            for sid in search(q, segments, camera_id, 5):
                if sid not in hits:
                    hits.append(sid)
        return hits
    hits = tr.run("Search footage", search_label(), do_search, lambda h: f"{len(h)} matching segments on {camera_id}") or []

    window = tr.run("Load moments", "segments + YOLO zones", lambda: _neighbors(hits, segments, camera_id),
                    lambda w: f"{len(w)} segments, {w[0]['offset']:.0f}s to {w[-1]['offset'] + 10:.0f}s" if w else "none")
    window = window or [s for s in segments if s["camera_id"] == camera_id]

    events = tr.run("Extract events", "caption parser", lambda: extract_events(window),
                    lambda ev: f"{len(ev)} behavior events on a 3x3 zone grid")
    links = tr.run("Link events", "timing + proximity score", lambda: build_links(events),
                   lambda ls: f"{len(ls)} links above 0.5, {_vehicle_links(ls, events)} between vehicles and people")

    def split_light():
        ls = light_stats(events, camera_id)
        day = sum(v["day"] for v in ls.values()); night = sum(v["night"] for v in ls.values())
        top_night = max(ls.items(), key=lambda kv: kv[1]["night"])[0] if night else None
        return ls, day, night, top_night
    light = tr.run("Split day and night", "segment light", split_light,
                   lambda r: f"{r[1]} daytime stays, {r[2]} night stays" + (f"; most night stays at {r[3]}" if r[3] else ""))

    if use_llm and links:
        def relabel():
            by = {e["id"]: e for e in events}
            top = sorted(links, key=lambda l: -l["score"])[:12]
            payload = [{"id": l["id"], "A": by[l["from"]], "B": by[l["to"]], "dt": l["dt"], "zone_rel": l["zone_rel"]} for l in top]
            res = llm.chat_json(LABEL_SYSTEM, json.dumps(payload))["links"]
            lab = {r["id"]: r for r in res}
            bad = ("caused", "because", "made ")
            for l in links:
                r = lab.get(l["id"])
                if r and not any(w in r.get("rationale", "").lower() for w in bad):
                    l["type"], l["rationale"] = r.get("type", l["type"]), r["rationale"]
            return len(lab)
        tr.run("Label links", "W&B LLM", relabel, lambda n: f"{n} strongest links labeled")

    crit = critical_moves(events, links, k=5)
    deg = degrees(events, links)
    link = _pick_link(events, links, crit)
    by = {e["id"]: e for e in events}
    if not link:
        tr.steps.append({"step": "Find critical moves", "tool": "link degree", "ms": 1, "mode": "ok",
                         "summary": "not enough connected moments here to suggest a change"})
        stats = zone_stats(events, camera_id)
        seg_ids = {e["segment_id"] for e in events} or {s["segment_id"] for s in (window or [])[:24]}
        return {
            "question": question, "camera_id": camera_id, "mode": "llm" if use_llm else "rules",
            "segments": [{k: s.get(k) for k in ("segment_id", "camera_id", "offset", "caption", "clip_url")}
                         for s in segments if s["segment_id"] in seg_ids],
            "events": [{**e, "degree": deg.get(e["id"], 0)} for e in events],
            "links": links, "critical": crit, "selected_link": None, "evidence": [],
            "branches": [], "recommendation": None,
            "zone_stats": stats, "light_stats": light[0] if light else {}, "trace": tr.steps,
        }
    a, b = by[link["from"]], by[link["to"]]
    tr.steps.append({"step": "Find critical moves", "tool": "link degree", "ms": 1, "mode": "ok",
                     "summary": f"{len(crit)} critical moves; selected {link['id']}: {link['rationale']}"})

    ev = tr.run("Retrieve evidence", search_label() + ", all cameras",
                lambda: gather_evidence(a, b, segments, events_all(segments), search, camera_id),
                lambda r: f"{len(r[0])} evidence segments across {len({x['camera_id'] for x in r[0]})} cameras")
    evidence = ev[0] if ev else []

    branches = None
    if use_llm:
        branches = tr.run("Branch futures", "W&B LLM", lambda: verify(llm_branches(link, a, b, evidence), evidence),
                          lambda bs: f"{len(bs)} verified branches")
        if branches is not None and len(branches) < 3:
            branches = None
    if branches is None:
        branches = tr.run("Branch futures", "templates", lambda: verify(template_branches(link, a, b, events_all(segments), evidence), evidence),
                          lambda bs: f"{len(bs)} verified branches")
    tr.steps.append({"step": "Verify citations", "tool": "code check", "ms": 1, "mode": "ok",
                     "summary": "every cited clip exists; N recomputed: " + ", ".join(f"{br['id']}={br['plausibility_n']}" for br in branches)})

    stats = zone_stats(events, camera_id)
    rec = None
    if use_llm:
        rec = tr.run("Recommend", "W&B LLM", lambda: llm_recommendation(branches, stats, [by[c] for c in crit]),
                     lambda r: f"{r['action']} ({r['label']})")
    if not rec:
        rec = tr.run("Recommend", "rules", lambda: template_recommendation(branches, stats, b),
                     lambda r: f"{r['action']} ({r['label']})")

    seg_ids = {e["segment_id"] for e in events} | {x["segment_id"] for x in evidence}
    return {
        "question": question, "camera_id": camera_id, "mode": "llm" if use_llm else "rules",
        "segments": [{k: s.get(k) for k in ("segment_id", "camera_id", "offset", "caption", "clip_url")}
                     for s in segments if s["segment_id"] in seg_ids],
        "events": [{**e, "degree": deg[e["id"]]} for e in events], "links": links, "critical": crit,
        "selected_link": link["id"], "evidence": evidence, "branches": branches,
        "recommendation": rec, "zone_stats": stats, "light_stats": light[0] if light else {}, "trace": tr.steps,
    }


_EV_CACHE = {}


def events_all(segments):
    key = id(segments)
    if key not in _EV_CACHE:
        _EV_CACHE[key] = extract_events(segments)
    return _EV_CACHE[key]
