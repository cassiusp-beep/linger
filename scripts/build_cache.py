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

p = argparse.ArgumentParser()
p.add_argument("--camera", default=None)
p.add_argument("--question", default="Where should seating go on this block?")
args = p.parse_args()

real = ROOT / "data" / "segments.json"
src = real if real.exists() else ROOT / "data" / "mock_segments.json"
segments = json.loads(src.read_text())
cam = args.camera or max({s["camera_id"] for s in segments},
                         key=lambda c: sum(1 for s in segments if s["camera_id"] == c))
llm.init_tracing() if llm.available() else None
res = ask(args.question, cam, segments)
res["source"] = src.name
(ROOT / "data" / "cache.json").write_text(json.dumps(res, indent=1))
(ROOT / "app" / "static" / "cache.js").write_text("window.LINGER_CACHE = " + json.dumps(res) + ";\n")
print(f"source={src.name} camera={cam} mode={res['mode']} events={len(res['events'])} "
      f"links={len(res['links'])} branches={len(res['branches'])}")
for s in res["trace"]:
    print(f"  {s['step']:<20} {s['tool']:<26} {s['ms']:>5}ms  {s['summary']}")
print("REC:", res["recommendation"]["action"], "|", res["recommendation"]["label"])
