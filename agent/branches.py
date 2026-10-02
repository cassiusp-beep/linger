"""Evidence retrieval, branch generation (LLM or template), verification, recommendation."""
import json
from . import llm
from .links import STATIONARY, VEHICLE, VERB

BRANCH_SYSTEM = """You are a public-space design analyst in the tradition of William Whyte. Given one
observed link and evidence segments retrieved from similar footage, propose plausible futures.
Return a JSON array of exactly 3 branches:
{"id","kind","intervention","prediction","evidence":[{"segment_id","match"}],"risk",
 "timeline":[{"t":"+0m","state"},{"t":"+10m","state"},{"t":"+30m","state"}]}
Branch 1: kind "baseline", intervention "No change". Branches 2 and 3: kind "intervention", one physical
change each (add or move seating, lighting, a planter, a sign, shade, a bus shelter, a curb extension).
If LIGHT_STATS show many stays at night, consider lighting. If a bus arrival is in the link, consider the stop layout.
Each branch cites at least 2 segment_ids from EVIDENCE; never invent ids.
Each intervention names one risk, always checking the clear walking path and accessibility.
Use "likely", "may", "in similar clips". Describe behavior only: no faces, identity, emotion, clothing.
Never use "will": every prediction and timeline state uses "may" or "likely".
Do not claim outcomes like "reducing congestion"; describe only what people may do.
Never say "caused", "because", or "made"."""

REC_SYSTEM = """From zone stats, critical events and branches, give ONE placement recommendation for a
public space. Return JSON {"zone","action","why","segment_ids"}: action is one full sentence naming
what to place (seating, table, sign, shelter), where (use the place's feature name, like "the bus stop"),
and which way it faces, for example "Add a bench at the bus stop, facing the crosswalk."; why is 2 short
sentences about observed behavior; segment_ids are cited from the branches only. Links are associations,
not causes."""


def gather_evidence(a, b, segments, events, search_fn, cam):
    queries = [
        f"people {VERB[b['behavior']]} near {b.get('near') or 'edge'}",
        "people sitting on a bench or ledge",
        "people walking around an obstacle",
        f"group {VERB[a['behavior']]} at {a['zone']}",
        "people waiting at night",
        "bus arrives at the stop",
    ]
    ids = []
    # Prefer this camera's clips so citations map to the moments on the place page.
    for scope in (cam, None):
        for q in queries:
            for sid in search_fn(q, segments, scope, 4):
                if sid not in ids:
                    ids.append(sid)
    seg_by = {s["segment_id"]: s for s in segments}
    return [{"segment_id": sid, "camera_id": seg_by[sid]["camera_id"],
             "caption": seg_by[sid]["caption"],
             "match": "same_space" if seg_by[sid]["camera_id"] == cam else "similar_space"}
            for sid in ids[:10]], queries


def _segs_with(events, pred, cam=None):
    out = []
    for e in events:
        if pred(e) and (cam is None or e["camera_id"] == cam) and e["segment_id"] not in out:
            out.append(e["segment_id"])
    return out


def template_branches(link, a, b, events, evidence):
    ev_ids = {x["segment_id"]: x["match"] for x in evidence}
    cam, zone, near = a["camera_id"], b["zone"], b.get("near") or a.get("near") or "edge"

    def cite(ids):
        ids = [i for i in ids if i in ev_ids]
        return [{"segment_id": i, "match": ev_ids[i]} for i in ids[:4]]

    stay_here = _segs_with(events, lambda e: e["behavior"] in STATIONARY and e["zone"] == zone, cam)
    sitting = _segs_with(events, lambda e: e["behavior"] == "sit")
    detours = _segs_with(events, lambda e: e["behavior"] == "path_change")
    night_stays = _segs_with(events, lambda e: e["behavior"] in STATIONARY and e.get("light") == "night")
    bus = _segs_with(events, lambda e: e["behavior"] == "bus_arrive")
    blocks = _segs_with(events, lambda e: e["behavior"] in VEHICLE and e["behavior"] != "bus_arrive")
    here = [e for e in events if e["camera_id"] == cam and e["zone"] == zone and e["behavior"] in STATIONARY]
    night_share = sum(e.get("light") == "night" for e in here) / max(1, len(here))
    bus_link = "bus_arrive" in (a["behavior"], b["behavior"])

    if night_share >= 0.3:
        third = {"id": "b3", "kind": "intervention", "intervention": f"Pedestrian lighting over {zone} by the {near}",
                 "prediction": f"{round(night_share * 100)}% of stays at {zone} are at night. In similar clips, lit edges may keep night waits shorter and closer to the curb.",
                 "evidence": cite(night_stays + stay_here), "risk": "Glare into ground-floor windows; keep fixtures low and shielded.",
                 "timeline": [{"t": "+0m", "state": "Night waits under light"}, {"t": "+10m", "state": "Groups gather in the lit area"},
                              {"t": "+30m", "state": "Night stays look like day stays"}]}
    elif bus_link or bus:
        third = {"id": "b3", "kind": "intervention", "intervention": "Move the bus stop marker 15 ft so riders wait off the walking path",
                 "prediction": "Riders likely gather where the bus actually stops; walkers may stop detouring around the waiting group.",
                 "evidence": cite(bus + detours), "risk": "Check the boarding area stays level and accessible.",
                 "timeline": [{"t": "+0m", "state": "Bus arrives at the new marker"}, {"t": "+10m", "state": "Waiting group off the path"},
                              {"t": "+30m", "state": "Fewer detours at BC"}]}
    else:
        third = {"id": "b3", "kind": "intervention", "intervention": "Clear the walking path at BC (move the pole-mounted sign to the curb edge)",
                 "prediction": "Walkers may stop detouring at BC, and standing groups likely stay where they are.",
                 "evidence": cite(detours + blocks), "risk": "Does not add seating; the stopping pattern likely stays the same.",
                 "timeline": [{"t": "+0m", "state": "Straight path through BC"}, {"t": "+10m", "state": "Fewer slowdowns"},
                              {"t": "+30m", "state": "Flow steadier, no new places to stay"}]}
    feat = (near or "").lower()
    has_crosswalk = any(e.get("near") == "crosswalk" or e["behavior"] == "crosswalk_block"
                        for e in events if e["camera_id"] == cam)
    if feat in ("bench", "seat", "ledge"):
        seating = f"More seating at {zone} next to the existing {near}"
    elif has_crosswalk and feat != "crosswalk":
        seating = f"Bench at {zone} beside the {near}, facing the crosswalk"
    elif feat == "crosswalk":
        seating = f"Bench at {zone} beside the {near}, facing the street"
    else:
        seating = f"Bench at {zone} beside the {near}, facing the walkway"

    return [
        {"id": "b1", "kind": "baseline", "intervention": "No change",
         "prediction": f"People likely keep standing at {zone} near the {near} in short stops; groups form and break up within a minute.",
         "evidence": cite(stay_here), "risk": "None added. Standing groups may keep spilling into the walking path.",
         "timeline": [{"t": "+0m", "state": f"Standing cluster at {zone}"}, {"t": "+10m", "state": "Short stops repeat"},
                      {"t": "+30m", "state": "Same pattern, no place to sit"}]},
        {"id": "b2", "kind": "intervention", "intervention": seating,
         "prediction": f"In similar clips, stops near seating may turn into longer sitting and lingering at {zone}, with groups gathering beside them.",
         "evidence": cite(sitting + stay_here), "risk": "Keep at least 5 ft of clear path behind the bench for wheelchairs and strollers.",
         "timeline": [{"t": "+0m", "state": "First person sits"}, {"t": "+10m", "state": "Others stop beside the bench"},
                      {"t": "+30m", "state": "Longer stays, fewer people standing in the path"}]},
        third,
    ]


def verify(branches, evidence):
    valid = {x["segment_id"]: x["match"] for x in evidence}
    out = []
    for br in branches:
        cited = [c for c in br.get("evidence", []) if c.get("segment_id") in valid]
        for c in cited:
            c["match"] = valid[c["segment_id"]]
        if len(cited) < 2:
            continue
        br["evidence"] = cited
        br["plausibility_n"] = len(cited)
        br["label"] = f"plausible, based on {len(cited)} clips"
        out.append(br)
    return out


@llm.op
def llm_branches(link, a, b, evidence):
    user = json.dumps({"LINK": link, "EVENT_A": a, "EVENT_B": b,
                       "EVIDENCE": [{k: x[k] for k in ("segment_id", "camera_id", "caption", "match")} for x in evidence]})
    res = llm.chat_json(BRANCH_SYSTEM, user, max_tokens=1600)
    return res if isinstance(res, list) else res.get("branches", [])


def light_stats(events, cam):
    """stays per zone split by day and night, people only"""
    out = {}
    for e in events:
        if e["camera_id"] == cam and e["behavior"] in STATIONARY:
            z = out.setdefault(e["zone"], {"day": 0, "night": 0, "unknown": 0})
            z[e.get("light", "unknown")] += e["count"]
    return out


def zone_stats(events, cam):
    stats = {}
    for e in events:
        if e["camera_id"] == cam and e["behavior"] in STATIONARY:
            stats[e["zone"]] = stats.get(e["zone"], 0) + e["count"]
    return dict(sorted(stats.items(), key=lambda kv: -kv[1]))


def template_recommendation(branches, stats, b):
    pick = next((br for br in branches if br["kind"] == "intervention"
                 and ("Bench" in br["intervention"] or "seating" in br["intervention"].lower())), None) \
        or next((br for br in branches if br["kind"] == "intervention"), None)
    if not pick:
        return None
    zone = b["zone"]
    return {"zone": zone, "action": pick["intervention"],
            "why": f"{zone} has the most standing and lingering on this camera ({stats.get(zone, 0)} person-stops) and no seating. "
                   f"In similar clips, people stay longer where there is a place to sit.",
            "segment_ids": [c["segment_id"] for c in pick["evidence"]], "n": pick["plausibility_n"],
            "label": f"plausible, based on {pick['plausibility_n']} clips"}


@llm.op
def llm_recommendation(branches, stats, critical):
    res = llm.chat_json(REC_SYSTEM, json.dumps({"ZONE_STATS": stats, "CRITICAL": critical, "BRANCHES": branches}))
    if len(str(res.get("action", "")).split()) < 5:
        return None
    cited = {c["segment_id"] for br in branches for c in br["evidence"]}
    res["segment_ids"] = [s for s in res.get("segment_ids", []) if s in cited]
    res["n"] = len(res["segment_ids"])
    res["label"] = f"plausible, based on {res['n']} clips"
    return res if res["n"] >= 2 else None
