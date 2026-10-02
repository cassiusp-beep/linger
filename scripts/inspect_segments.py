"""Check that exported captions are usable before running the agent. Run on the VM after exporting.

  python scripts/inspect_segments.py                 # data/segments.json (else mock)
  python scripts/inspect_segments.py path/to/file.json --camera sf_streets_cam-2

Prints parse rate, behaviors, zones, day/night, vehicle events, banned words, and the worst captions.
Rule of thumb: parse rate under 70% means the re-ingest prompt was not followed. Fix that first.
"""
import argparse, collections, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.extract import LINE, parse_caption, segment_light, privacy_check
from agent.links import build_links
from agent.extract import extract_events

p = argparse.ArgumentParser()
p.add_argument("path", nargs="?")
p.add_argument("--camera")
a = p.parse_args()
path = pathlib.Path(a.path) if a.path else (ROOT / "data" / "segments.json")
if not path.exists():
    path = ROOT / "data" / "mock_segments.json"
segs = json.loads(path.read_text())
if a.camera:
    segs = [s for s in segs if s["camera_id"] == a.camera]
print(f"file: {path.name}   segments: {len(segs)}")

cams = collections.Counter(s["camera_id"] for s in segs)
print("cameras:", dict(cams))
lines_total = lines_parsed = 0
beh, zones, lights, banned, worst = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter(), []
guessed = 0
for s in segs:
    cap = s.get("caption", "")
    n_lines = len(LINE.findall(cap))
    evs = parse_caption(cap)
    lines_total += n_lines
    lines_parsed += len(evs)
    lights[segment_light(s)] += 1
    for e in evs:
        beh[e["behavior"]] += 1
        zones[e["zone"]] += 1
        guessed += e["zone_guessed"]
    for w in privacy_check(cap):
        banned[w] += 1
    if n_lines == 0 or len(evs) < n_lines / 2:
        worst.append(s)

rate = lines_parsed / lines_total if lines_total else 0
print(f"timestamped lines: {lines_total}   parsed into events: {lines_parsed}   parse rate: {rate:.0%}")
print(f"segments with no [t=Xs] lines at all: {sum(1 for s in segs if not LINE.search(s.get('caption','')))}")
print("behaviors:", dict(beh.most_common()))
print("zones:", dict(zones.most_common()), f"  (no zone token, defaulted to C: {guessed})")
print("light:", dict(lights))
print("banned words found (should be empty):", dict(banned))
evs = extract_events(segs)
links = build_links(evs)
veh = sum(1 for e in evs if e.get("actor") == "vehicle")
print(f"events: {len(evs)} ({veh} vehicle)   links: {len(links)}   links per event: {len(links)/max(1,len(evs)):.1f}")
print("\nworst captions (fix the prompt if these look typical):")
for s in worst[:3]:
    print(f"  {s['segment_id']}: {s.get('caption','')[:220]}")
