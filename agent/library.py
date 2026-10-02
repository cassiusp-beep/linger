"""Rank every camera in the archive by how much people stop and wait."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .extract import extract_events, LINE
from .links import STATIONARY

PLACE = {
    "san_francisco": "San Francisco street",
    "indoor": "Indoor public space",
    "neighborhood": "Neighborhood street",
    "nashville": "Nashville highway",
    "warehouse3": "Warehouse",
    "toronto": "Toronto drive",
}

REASON = {
    "toronto": "Moving dashcam: positions in the frame don't map to places",
    "nashville": "Highway: no pedestrian space to design",
    "warehouse3": "Industrial floor: not a public space",
}


def _camera_n(camera_id: str) -> str:
    m = re.search(r"(\d+)$", camera_id or "")
    return m.group(1) if m else "?"


def _score(stops: int, clips: int, night_share: float, groups: int, stationary_n: int) -> float:
    if clips <= 0 or stops <= 0:
        return 0.0
    group_factor = 1 + (groups / stationary_n if stationary_n else 0)
    return (stops / clips) * (1 + night_share) * group_factor * min(1.0, clips / 8)


def summarize(segments: list[dict]) -> dict:
    by_cam: dict[str, list] = defaultdict(list)
    for s in segments:
        by_cam[s["camera_id"]].append(s)

    cameras = []
    for camera_id, segs in by_cam.items():
        loc = next((s.get("location") for s in segs if s.get("location")), "unknown")
        place = PLACE.get(loc, loc.replace("_", " ").title() if loc else "Unknown place")
        clips = len(segs)
        events = extract_events(segs)
        lines = sum(len(LINE.findall(s.get("caption") or "")) for s in segs)
        stationary = [e for e in events if e["behavior"] in STATIONARY]
        stops = sum(e["count"] for e in stationary)
        zones: dict[str, int] = {}
        for e in stationary:
            zones[e["zone"]] = zones.get(e["zone"], 0) + e["count"]
        top_zone = max(zones, key=zones.get) if zones else None
        top_feature = None
        if top_zone:
            near_counts = Counter(
                e["near"] for e in stationary if e["zone"] == top_zone and e.get("near")
            )
            top_feature = near_counts.most_common(1)[0][0] if near_counts else None
        night_stops = sum(e["count"] for e in stationary if e.get("light") == "night")
        night_share = (night_stops / stops) if stops else 0.0
        groups = sum(1 for e in stationary if e.get("group"))
        buses = sum(1 for e in events if e["behavior"] == "bus_arrive")
        analyzed = bool(lines) and len(events) >= max(3, 0.3 * lines)
        reason = None
        if not analyzed:
            reason = REASON.get(loc, "Not analyzed yet: re-ingest with the Linger prompt")
        score = _score(stops, clips, night_share, groups, len(stationary)) if analyzed else 0.0
        cameras.append({
            "camera_id": camera_id,
            "camera_n": _camera_n(camera_id),
            "location": loc,
            "place": place,
            "clips": clips,
            "stops": stops,
            "zones": zones,
            "top_zone": top_zone,
            "top_feature": top_feature,
            "night_share": round(night_share, 4),
            "groups": groups,
            "buses": buses,
            "analyzed": analyzed,
            "reason": reason,
            "score": round(score, 4),
        })

    analyzable = sorted([c for c in cameras if c["analyzed"]], key=lambda c: -c["score"])
    rest = sorted([c for c in cameras if not c["analyzed"]], key=lambda c: (-c["clips"], c["camera_id"]))
    for i, c in enumerate(analyzable, 1):
        c["rank"] = i
    for c in rest:
        c["rank"] = None
    ordered = analyzable + rest
    return {
        "cameras": ordered,
        "total_clips": sum(c["clips"] for c in ordered),
        "total_cameras": len(ordered),
        "analyzed_cameras": len(analyzable),
    }
