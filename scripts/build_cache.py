"""Run the agent once and save the result as the demo cache.

  python scripts/build_cache.py                       # uses data/segments.json, else mock
  python scripts/build_cache.py --camera sf_streets_cam-1 --question "Where should seating go on this block?"
  LINGER_LLM=0 python scripts/build_cache.py          # rules only, no W&B calls
"""
import argparse, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import llm
from agent.agent import ask
from agent.library import summarize

p = argparse.ArgumentParser()
p.add_argument("--camera", default=None)
p.add_argument("--question", default="Where should seating go on this block?")
args = p.parse_args()

real = ROOT / "data" / "segments.json"
src = real if real.exists() else ROOT / "data" / "mock_segments.json"
segments = json.loads(src.read_text())
library = summarize(segments)
analyzable = [c for c in library["cameras"] if c["analyzed"]]
if args.camera:
    cam = args.camera
elif analyzable:
    cam = analyzable[0]["camera_id"]
else:
    cam = max({s["camera_id"] for s in segments},
              key=lambda c: sum(1 for s in segments if s["camera_id"] == c))

llm.init_tracing() if llm.available() else None
res = ask(args.question, cam, segments)
res["source"] = src.name
(ROOT / "data" / "cache.json").write_text(json.dumps(res, indent=1))

# Rules-only run for every other analyzable camera (place pages offline)
runs = {cam: res}
for c in analyzable:
    cid = c["camera_id"]
    if cid == cam:
        continue
    runs[cid] = ask(args.question, cid, segments, use_llm=False)
    runs[cid]["source"] = src.name

library_payload = {"library": {**library, "source": src.name}, "runs": runs}
(ROOT / "data" / "library.json").write_text(json.dumps(library_payload, indent=1))
(ROOT / "app" / "static" / "cache.js").write_text(
    "window.LINGER_CACHE = " + json.dumps(res) + ";\n"
    "window.LINGER_LIBRARY = " + json.dumps(library_payload) + ";\n"
)

print(f"source={src.name} camera={cam} mode={res['mode']} events={len(res.get('events') or [])} "
      f"links={len(res.get('links') or [])} branches={len(res.get('branches') or [])}")
print(f"library cameras={library['total_cameras']} analyzed={library['analyzed_cameras']} "
      f"runs={len(runs)}")
for s in res.get("trace") or []:
    print(f"  {s['step']:<20} {s['tool']:<26} {s['ms']:>5}ms  {s['summary']}")
rec = res.get("recommendation") or {}
print("REC:", rec.get("action"), "|", rec.get("label"))
