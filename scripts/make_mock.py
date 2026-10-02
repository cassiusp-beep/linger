"""Scripted mock footage in the exact format our ingest prompt asks Cosmos for.
Hero camera: an SF-style block. Bus stop at BL, ledge at ML, pole at C/BC, storefront at TC,
tree at MR, crosswalk at BR. Day segments first, then night. A second camera has a real bench."""
import json, pathlib

HERO = "sf_streets_cam-2"
OTHER = "sf_streets_cam-3"
hero = [  # (light, caption)
    ("day", "Day. [t=1s] 3 walking, BC. [t=4s] 1 stops, BL, near bus stop. [t=8s] 1 lingering, BL, near bus stop."),
    ("day", "Day. [t=1s] bus arrives, BL, near bus stop. [t=3s] 2 standing, BL, group, near bus stop. [t=5s] 4 walking, BC. [t=7s] 1 path change, BC, near bus stop, detour."),
    ("day", "Day. [t=3s] 3 standing, BL, group, near bus stop. [t=5s] car blocks the crosswalk, BR, near crosswalk. [t=7s] 2 waiting to cross, BR, near crosswalk."),
    ("day", "Day. [t=1s] 1 sitting, ML, near ledge. [t=4s] 1 stops, ML, near ledge. [t=9s] 2 walking, BC."),
    ("day", "Day. [t=2s] 2 lingering, ML, group, near ledge. [t=6s] 1 path change, BC, near pole, slowdown."),
    ("day", "Day. [t=0s] 5 walking, BC. [t=3s] 3 waiting to cross, BR, group, near crosswalk. [t=8s] 1 stops, BL, near bus stop."),
    ("day", "Day. [t=1s] bus arrives, BL, near bus stop. [t=3s] 2 standing, BL, group, near bus stop. [t=5s] 1 path change, BC, near bus stop, detour."),
    ("day", "Day. [t=3s] 1 sitting, ML, near ledge. [t=6s] 1 lingering, MR, near tree."),
    ("night", "Night. [t=1s] 2 standing, BL, group, near bus stop. [t=4s] 1 lingering, BL, near bus stop. [t=7s] 2 walking, BR."),
    ("night", "Night. [t=2s] 1 lingering, BL, near bus stop. [t=5s] 2 standing, BL, group, near bus stop. [t=8s] 1 path change, C, near pole, detour."),
    ("night", "Night. [t=2s] bus arrives, BL, near bus stop. [t=4s] 3 standing, BL, group, near bus stop. [t=8s] 1 standing, TC, near storefront."),
    ("night", "Night. [t=1s] 1 lingering, BL, near bus stop. [t=4s] 2 waiting to cross, BR, near crosswalk. [t=7s] car blocks the crosswalk, BR, near crosswalk. [t=9s] 1 path change, BR, near crosswalk, detour."),
    ("night", "Night. [t=3s] 2 stops, TC, group, near storefront. [t=6s] 1 lingering, BL, near bus stop."),
]
other = [
    ("day", "Day. [t=2s] 2 sitting, BL, group, near bench. [t=6s] 1 stops, BL, near bench."),
    ("day", "Day. [t=1s] 1 sitting, BL, near bench. [t=5s] 2 lingering, BL, group, near bench."),
    ("day", "Day. [t=3s] 3 walking, BC. [t=6s] 1 path change, BC, near bench, detour."),
    ("night", "Night. [t=2s] 2 sitting, BL, group, near bench. [t=7s] 1 sitting, BL, near bench."),
    ("night", "Night. [t=2s] bus arrives, BL, near bus stop. [t=4s] 2 standing, BL, group, near bus stop."),
]
segs = []
for cam, rows, pre, vid in ((HERO, hero, "cam2", "sf-streets/2"), (OTHER, other, "cam3", "sf-streets/3")):
    for i, (light, cap) in enumerate(rows):
        segs.append({"segment_id": f"{pre}_s{i:02d}", "video_id": vid, "camera_id": cam, "offset": i * 10,
                     "t0": 0, "t1": 10, "light": light, "caption": cap, "clip_url": None})
out = pathlib.Path(__file__).resolve().parents[1] / "data" / "mock_segments.json"
out.write_text(json.dumps(segs, indent=1))
print("wrote", out, len(segs), "segments")
