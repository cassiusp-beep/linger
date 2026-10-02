"""Turn behavior-only captions into events.

Our ingest prompt forces lines like:  [t=4s] 2 standing, BL, group, near bus stop
so a rules parser is fast and reliable. The LLM is not needed for this step.
"""
import re

LINE = re.compile(r"\[t=(\d+(?:\.\d+)?)s\]\s*([^\[]+)")
ZONE = re.compile(r"\b(TL|TC|TR|ML|MR|BL|BC|BR|C)\b")
NEAR = re.compile(r"near (?:the |a )?([a-z][a-z ]*?)(?:,|\.|;|$)")
COUNT = re.compile(r"\b(\d+)\b")

# order matters: first match wins. Vehicle lines are checked first because "bus stops" contains "stops".
VEHICLE_BEHAVIOR = [
    ("crosswalk_block", ("blocks crosswalk", "blocks the crosswalk", "blocking the crosswalk", "blocking crosswalk", "in crosswalk", "in the crosswalk")),
    ("bus_arrive", ("bus arrives", "bus stops", "bus pulls", "bus arriving", "bus stopped")),
    ("vehicle_stop", ("car stops", "truck stops", "vehicle stops", "bicycle stops", "car stopped", "truck stopped", "car parks", "double parked", "double-parked")),
]
VEHICLES = ("bus", "truck", "bicycle", "car", "vehicle")
LIGHT = re.compile(r"\b(night|nighttime|dark|day|daytime|daylight)\b", re.I)
BEHAVIOR = [
    ("path_change", ("path change", "detour", "slowdown", "slows", "turns")),
    ("sit", ("sitting", "seated", "sits")),
    ("linger", ("lingering", "lingers")),
    ("stop", ("stops", "stopped", "stopping")),
    ("stand", ("standing", "waiting")),
    ("walk", ("walking", "walks", "passing")),
]
BANNED = ("face", "shirt", "jacket", "dress", "happy", "sad", "angry", " man ", "woman", "male", "female", "plate")


def parse_caption(caption):
    out = []
    for m in LINE.finditer(caption or ""):
        t = float(m.group(1))
        raw = m.group(2).strip()
        body = raw.lower()
        actor, vehicle = "person", None
        behavior = next((b for b, keys in VEHICLE_BEHAVIOR if any(k in body for k in keys)), None)
        if behavior:
            actor = "vehicle"
            vehicle = next((v for v in VEHICLES if v in body), "vehicle")
        else:
            behavior = next((b for b, keys in BEHAVIOR if any(k in body for k in keys)), None)
        if not behavior:
            continue
        zone_m = ZONE.search(raw)
        count_m = COUNT.search(body)
        near_m = NEAR.search(body)
        count = 1 if actor == "vehicle" else (int(count_m.group(1)) if count_m else 1)
        if count == 0:
            continue
        out.append({
            "t_local": t,
            "actor": actor,
            "vehicle": vehicle,
            "behavior": behavior,
            "zone": zone_m.group(1) if zone_m else "C",
            "zone_guessed": zone_m is None,
            "count": count,
            "group": "group" in body,
            "near": near_m.group(1).strip() if near_m else None,
            "confidence": 0.4 if "unsure" in body else 0.75,
        })
    return out


def segment_light(seg):
    """day | night | unknown, from an explicit field or the caption (our prompt asks Cosmos to say it)."""
    if seg.get("light") in ("day", "night"):
        return seg["light"]
    m = LIGHT.search(seg.get("caption", ""))
    if not m:
        return "unknown"
    return "night" if m.group(1).lower() in ("night", "nighttime", "dark") else "day"


def extract_events(segments):
    """segments: list of dicts per schemas/segments. Returns events sorted by camera then time."""
    events = []
    for seg in segments:
        for e in parse_caption(seg.get("caption", "")):
            t_local = e.pop("t_local")
            events.append({
                "segment_id": seg["segment_id"],
                "camera_id": seg["camera_id"],
                "t": round(seg.get("offset", 0) + t_local, 1),
                "dur": 3,
                "light": segment_light(seg),
                **e,
            })
    events.sort(key=lambda e: (e["camera_id"], e["t"]))
    for i, e in enumerate(events):
        e["id"] = f"e{i:03d}"
    return events


def privacy_check(text):
    t = f" {(text or '').lower()} "
    return [w.strip() for w in BANNED if w in t]
