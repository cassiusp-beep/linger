"""Deterministic link scoring. Links are associations by timing and proximity, never causes."""
import math
from .zones import relation

STATIONARY = {"stop", "stand", "sit", "linger"}
VEHICLE = {"bus_arrive", "crosswalk_block", "vehicle_stop"}
COMPAT = {
    ("sit", "linger"): 1.0, ("linger", "sit"): 1.0, ("linger", "stop"): 0.9, ("stop", "linger"): 0.9,
    ("linger", "stand"): 0.9, ("stand", "stand"): 0.6, ("stand", "linger"): 0.8, ("stop", "stand"): 0.8,
    ("stop", "path_change"): 0.8, ("stand", "path_change"): 0.8, ("linger", "path_change"): 0.8,
    ("sit", "stop"): 0.8, ("stop", "stop"): 0.7, ("walk", "path_change"): 0.5, ("walk", "walk"): 0.2,
    # vehicles as moves: a bus arrival followed by people gathering, a blocked crosswalk followed by detours
    ("bus_arrive", "stand"): 1.0, ("bus_arrive", "linger"): 0.9, ("bus_arrive", "stop"): 0.9, ("bus_arrive", "walk"): 0.5,
    ("stand", "bus_arrive"): 0.7, ("linger", "bus_arrive"): 0.7,
    ("crosswalk_block", "path_change"): 1.0, ("crosswalk_block", "stand"): 0.8, ("crosswalk_block", "stop"): 0.8,
    ("vehicle_stop", "path_change"): 0.8, ("vehicle_stop", "stand"): 0.6,
}
ZONE_PROX = {"same": 1.0, "adjacent": 0.6, "far": 0.0}

THRESHOLD = 0.5
MAX_DT = 60
MAX_OUT = 6

VERB = {"walk": "walking", "stop": "stopping", "stand": "standing", "sit": "sitting",
        "linger": "lingering", "path_change": "changing path",
        "bus_arrive": "arriving", "crosswalk_block": "blocking the crosswalk", "vehicle_stop": "stopping"}


def score(a, b):
    dt = b["t"] - a["t"]
    zr = relation(a["zone"], b["zone"])
    s = 0.5 * math.exp(-dt / 20) + 0.3 * ZONE_PROX[zr] + 0.2 * COMPAT.get((a["behavior"], b["behavior"]), 0.3)
    return round(s, 3), dt, zr


def label(a, b):
    """Rule label. The LLM can overwrite type and rationale; is_causal stays False."""
    if a["behavior"] in VEHICLE and b["behavior"] == "path_change":
        return "blocks"
    if a["behavior"] == "bus_arrive" and b["behavior"] in STATIONARY:
        return "attracts"
    if a["behavior"] in STATIONARY and b["behavior"] == "path_change":
        return "blocks"
    if a["behavior"] in STATIONARY and b["behavior"] in STATIONARY:
        return "attracts"
    if a["behavior"] == b["behavior"]:
        return "follows"
    return "co-occurs"


def phrase(e):
    if e.get("actor") == "vehicle":
        who = f"a {e.get('vehicle') or 'vehicle'}"
    else:
        who = "1 person" if e["count"] == 1 else f"{e['count']} people"
    near = f" near the {e['near']}" if e.get("near") else ""
    return f"{who} {VERB.get(e['behavior'], e['behavior'])} at {e['zone']}{near}"


def build_links(events):
    links = []
    by_cam = {}
    for e in events:
        by_cam.setdefault(e["camera_id"], []).append(e)
    for cam_events in by_cam.values():
        for i, a in enumerate(cam_events):
            cands = []
            for b in cam_events[i + 1:]:
                if b["t"] - a["t"] > MAX_DT:
                    break
                if a["behavior"] == "walk" and b["behavior"] == "walk":
                    continue  # passers-by next to passers-by is noise, not a design signal
                if a["behavior"] in VEHICLE and b["behavior"] in VEHICLE:
                    continue  # traffic next to traffic is a traffic study, not ours
                s, dt, zr = score(a, b)
                if zr == "far":
                    continue
                if s >= THRESHOLD:
                    cands.append((s, b, dt, zr))
            cands.sort(key=lambda c: -c[0])
            for s, b, dt, zr in cands[:MAX_OUT]:
                p = phrase(b)
                links.append({
                    "id": f"l{len(links):03d}", "from": a["id"], "to": b["id"], "score": s,
                    "dt": round(dt, 1), "zone_rel": zr, "type": label(a, b),
                    "rationale": f"{p[0].upper()}{p[1:]}, {round(dt)}s after {phrase(a)}.",
                    "is_causal": False,
                })
    return links


def degrees(events, links):
    deg = {e["id"]: 0 for e in events}
    for l in links:
        deg[l["from"]] += 1
        deg[l["to"]] += 1
    return deg


def critical_moves(events, links, k=3):
    deg = degrees(events, links)
    ranked = sorted(events, key=lambda e: -deg[e["id"]])
    return [e["id"] for e in ranked[:k] if deg[e["id"]] > 0]
