"""Overlay Linger-format captions on real VSS segments for public-space cameras.

Keeps real segment_ids so clip_sources.json / playback still work.
Skips toronto, nashville, warehouse3 (not designable places).

  python3 scripts/overlay_structured.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Per-camera caption packs: (light, caption). Varied places so ranks differ.
PACKS = {
    "sf_streets_cam-1": [
        ("day", "Day. [t=1s] 4 walking, BC. [t=4s] 2 standing, BL, group, near curb. [t=8s] 1 lingering, BL, near curb."),
        ("day", "Day. [t=2s] 1 sitting, ML, near ledge. [t=5s] 2 stops, ML, group, near ledge. [t=8s] 3 walking, BC."),
        ("day", "Day. [t=1s] 2 waiting to cross, BR, group, near crosswalk. [t=4s] car blocks the crosswalk, BR, near crosswalk. [t=7s] 1 path change, BR, near crosswalk, detour."),
        ("day", "Day. [t=3s] 3 standing, TC, group, near storefront. [t=6s] 1 path change, BC, near pole, slowdown."),
        ("day", "Day. [t=1s] 2 lingering, BL, group, near curb. [t=5s] 1 stops, BL, near curb. [t=9s] 2 walking, MR."),
        ("day", "Day. [t=2s] 1 sitting, ML, near ledge. [t=6s] 1 lingering, MR, near tree."),
        ("night", "Night. [t=1s] 2 standing, BL, group, near curb. [t=5s] 1 lingering, BL, near curb. [t=8s] 1 walking, BC."),
        ("night", "Night. [t=2s] 2 waiting to cross, BR, near crosswalk. [t=6s] 1 path change, C, near pole, detour."),
        ("night", "Night. [t=1s] 3 standing, TC, group, near storefront. [t=5s] 1 stops, TC, near storefront."),
        ("night", "Night. [t=3s] 1 lingering, ML, near ledge. [t=7s] 2 standing, BL, group, near curb."),
        ("day", "Day. [t=0s] 5 walking, BC. [t=4s] 2 stops, BL, group, near curb. [t=8s] 1 path change, BC, near curb, detour."),
        ("day", "Day. [t=2s] 1 sitting, ML, near ledge. [t=5s] 2 lingering, ML, group, near ledge. [t=8s] 1 walking, BC."),
    ],
    "sf_streets_cam-4": [
        ("day", "Day. [t=1s] 3 walking, BC. [t=3s] bus arrives, BL, near bus stop. [t=5s] 3 standing, BL, group, near bus stop."),
        ("day", "Day. [t=2s] 2 standing, BL, group, near bus stop. [t=5s] 1 path change, BC, near bus stop, detour. [t=8s] 4 walking, BC."),
        ("day", "Day. [t=1s] 1 sitting, MR, near bench. [t=4s] 2 lingering, MR, group, near bench. [t=8s] 1 stops, MR, near bench."),
        ("day", "Day. [t=3s] 2 waiting to cross, BR, group, near crosswalk. [t=6s] car blocks the crosswalk, BR, near crosswalk."),
        ("day", "Day. [t=1s] bus arrives, BL, near bus stop. [t=3s] 4 standing, BL, group, near bus stop. [t=7s] 1 path change, BC, near pole, slowdown."),
        ("day", "Day. [t=2s] 2 lingering, BL, near bus stop. [t=6s] 1 sitting, MR, near bench."),
        ("night", "Night. [t=1s] 3 standing, BL, group, near bus stop. [t=5s] 1 lingering, BL, near bus stop."),
        ("night", "Night. [t=2s] bus arrives, BL, near bus stop. [t=4s] 2 standing, BL, group, near bus stop. [t=8s] 1 walking, BR."),
        ("night", "Night. [t=1s] 2 sitting, MR, group, near bench. [t=6s] 1 lingering, MR, near bench."),
        ("night", "Night. [t=3s] 2 waiting to cross, BR, near crosswalk. [t=7s] 1 path change, BR, near crosswalk, detour."),
        ("day", "Day. [t=0s] 2 stops, TC, group, near doorway. [t=5s] 3 walking, BC. [t=8s] 1 standing, BL, near bus stop."),
        ("day", "Day. [t=2s] 1 sitting, MR, near bench. [t=5s] 2 standing, BL, group, near bus stop. [t=8s] 1 path change, BC, near bus stop, detour."),
    ],
    "neighborhood_cam-1": [
        ("day", "Day. [t=1s] 2 walking, BC. [t=4s] 1 stops, BL, near curb. [t=8s] 1 lingering, BL, near tree."),
        ("day", "Day. [t=2s] 2 standing, ML, group, near doorway. [t=6s] 1 path change, BC, near pole, slowdown."),
        ("day", "Day. [t=1s] 1 sitting, MR, near ledge. [t=5s] 2 lingering, MR, group, near ledge."),
        ("day", "Day. [t=3s] 2 waiting to cross, BR, near crosswalk. [t=7s] 1 path change, BR, near crosswalk, detour."),
        ("day", "Day. [t=0s] 3 walking, BC. [t=4s] 2 stops, BL, group, near curb. [t=8s] 1 standing, TL, near tree."),
        ("day", "Day. [t=2s] 1 lingering, ML, near doorway. [t=6s] 1 sitting, MR, near ledge."),
        ("night", "Night. [t=1s] 2 standing, BL, group, near curb. [t=5s] 1 lingering, BL, near tree."),
        ("night", "Night. [t=2s] 1 stops, ML, near doorway. [t=6s] 1 path change, C, near pole, detour."),
        ("night", "Night. [t=1s] 2 lingering, MR, group, near ledge. [t=7s] 1 walking, BC."),
        ("day", "Day. [t=3s] 2 standing, BL, group, near curb. [t=6s] 1 sitting, MR, near ledge. [t=9s] 2 walking, BC."),
        ("day", "Day. [t=1s] 1 waiting to cross, BR, near crosswalk. [t=5s] 2 stops, BL, near curb."),
        ("night", "Night. [t=2s] 2 standing, ML, group, near doorway. [t=6s] 1 lingering, BL, near curb."),
    ],
    "smartspace_cam-1": [
        ("day", "Day. [t=1s] 3 walking, BC. [t=4s] 2 sitting, ML, group, near bench. [t=8s] 1 lingering, ML, near table."),
        ("day", "Day. [t=2s] 1 sitting, ML, near bench. [t=5s] 2 stops, TC, group, near doorway. [t=8s] 1 path change, BC, near pole, slowdown."),
        ("day", "Day. [t=1s] 2 lingering, MR, group, near ledge. [t=5s] 1 sitting, MR, near ledge. [t=8s] 3 walking, BC."),
        ("day", "Day. [t=3s] 2 standing, BL, group, near doorway. [t=6s] 1 stops, BL, near doorway."),
        ("day", "Day. [t=0s] 4 walking, BC. [t=4s] 2 sitting, ML, group, near table. [t=8s] 1 lingering, C, near bench."),
        ("day", "Day. [t=2s] 1 path change, BC, near pole, detour. [t=6s] 2 sitting, ML, near bench."),
        ("night", "Night. [t=1s] 2 sitting, ML, group, near bench. [t=5s] 1 lingering, ML, near table."),
        ("night", "Night. [t=2s] 1 standing, BL, near doorway. [t=6s] 2 sitting, MR, group, near ledge."),
        ("night", "Night. [t=1s] 2 lingering, TC, group, near doorway. [t=7s] 1 walking, BC."),
        ("day", "Day. [t=3s] 1 sitting, ML, near table. [t=6s] 2 stops, ML, group, near bench. [t=9s] 1 path change, BC, near bench, detour."),
        ("day", "Day. [t=1s] 2 standing, BL, group, near doorway. [t=5s] 1 sitting, MR, near ledge."),
        ("night", "Night. [t=2s] 2 sitting, ML, group, near bench. [t=6s] 1 lingering, C, near table."),
    ],
}


def _pick(rows, n):
    step = max(1, len(rows) // n)
    picks, seen = [], set()
    for i in range(n):
        s = rows[min(i * step, len(rows) - 1)]
        if s["segment_id"] not in seen:
            picks.append(s)
            seen.add(s["segment_id"])
    for s in rows:
        if len(picks) >= n:
            break
        if s["segment_id"] not in seen:
            picks.append(s)
            seen.add(s["segment_id"])
    return picks[:n]


def main():
    path = ROOT / "data" / "segments.json"
    segs = json.loads(path.read_text())
    by_cam = {}
    for s in segs:
        by_cam.setdefault(s["camera_id"], []).append(s)

    keep_ids = set()
    rebuilt = []
    # Keep cameras we are not overlaying as-is (including already-structured cam-2/3).
    overlay_cams = set(PACKS)
    for s in segs:
        if s["camera_id"] not in overlay_cams:
            rebuilt.append(s)
            keep_ids.add(s["segment_id"])

    for cam, pack in PACKS.items():
        rows = by_cam.get(cam) or []
        if len(rows) < len(pack):
            raise SystemExit(f"{cam}: need {len(pack)} segments, have {len(rows)}")
        picks = _pick(rows, len(pack))
        for i, (s, (light, cap)) in enumerate(zip(picks, pack)):
            out = dict(s)
            out["caption"] = cap
            out["light"] = light
            out["offset"] = i * 10
            out["clip_url"] = f"/app/api/clip/{out['segment_id']}"
            rebuilt.append(out)
            keep_ids.add(out["segment_id"])
        print(f"{cam}: {len(pack)} structured clips (real segment ids)")

    rebuilt.sort(key=lambda s: (s["camera_id"], s.get("offset", 0)))
    path.write_text(json.dumps(rebuilt))
    print(f"wrote {path} ({len(rebuilt)} segments)")


if __name__ == "__main__":
    main()
