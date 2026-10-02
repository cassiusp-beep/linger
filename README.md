# Linger: linkography for video

A video agent for public-space design. Ask it a design question ("Where should seating go on this block?").
It searches indexed street footage, turns behavior-only descriptions into timestamped events on a 3x3 zone
grid, links events by timing and proximity into a linkograph, finds the critical moves, branches one link
into plausible futures with cited evidence clips, and makes one placement recommendation.

Vehicles are moves too: a bus arriving, a car blocking the crosswalk. The linkograph links them to what
people do next, and splits day from night, so lighting can show up as a future alongside seating.

Links are associations, not causes. Every branch says how many real clips support it.

Laptop setup and the laptop-to-VM loop: see SETUP_LAPTOP.md.

## Re-ingest prompt (726 characters)

```
Describe only how people and vehicles use this street space. Report: people visible; how many walk, stand, sit, or linger (still over 5s, not seated); where they stop, on a 3x3 frame grid: TL, TC, TR, ML, C, MR, BL, BC, BR; groups of 2+ stopping together; path changes (turn, detour, slowdown, waiting to cross) and the nearby feature (bench, ledge, curb, crosswalk, bus stop, doorway, storefront, tree, pole); vehicles that stop, block a crosswalk, or arrive at a stop (car, bus, truck, bicycle), with zone. Give approximate seconds and say day or night. Never describe faces, identity, age, gender, race, emotion, clothing, plates, or speech. If unsure, write unsure. Short lines only: [t=4s] bus arrives, BL, near bus stop.
```

## Run it (works offline on mock data)

```bash
pip install -r requirements.txt
python scripts/make_mock.py                 # scripted street-camera mock in our ingest-prompt format
LINGER_LLM=0 python scripts/build_cache.py  # rules-only run, writes data/cache.json + app/static/cache.js
uvicorn app.main:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/app/
```

You can also open `app/static/index.html` straight from disk; it falls back to `cache.js`.

## Swap in real VSS data

1. Export the hero camera's segments to `data/segments.json` in the shape of `schemas/segment.example.json`.
   `offset` is seconds from the start of that camera's timeline, `light` is day, night or unknown, `caption` is the Cosmos description from our
   re-ingest prompt (lines like `[t=4s] 2 standing, BL, group, near bus stop`), `clip_url` is anything a browser
   can play. When `data/segments.json` exists it is used instead of the mock.
2. Optional: wire `vss_search` in `agent/search.py` to the VSS search endpoint and set `LINGER_SEARCH=vss`.
   Until then the agent searches captions locally, and the Agent steps panel says so.
3. With W&B keys in the environment, run `python scripts/build_cache.py` (no `LINGER_LLM=0`). The plan, link
   labels, branches and recommendation then come from W&B serverless inference, traced in Weave.
   Set `LINGER_MODEL` to a model id from `python -c "from agent import llm; print(llm.list_models())"`.
4. Rebuild the cache, redeploy.

## How it works

| Step | Tool | Notes |
|---|---|---|
| Plan searches | W&B LLM (rules fallback) | 4 to 6 behavior queries for the question |
| Search footage | VSS search (local fallback) | filtered to the hero camera |
| Load moments | segments + YOLO zones | hits plus neighbouring segments |
| Extract events | caption parser | our ingest prompt makes captions structured, so no LLM needed |
| Link events | `score = 0.5*exp(-dt/20) + 0.3*zone_prox + 0.2*type_compat` | keep >= 0.5, same camera, dt <= 60s, adjacent zones; vehicle-to-person links included, vehicle-to-vehicle skipped |
| Split day and night | segment light | stays per zone by day and night; night-heavy zones get a lighting branch |
| Label links | W&B LLM | rationale text; banned words: caused, because, made |
| Critical moves | link degree | starts from the best-linked place people stay |
| Retrieve evidence | search across all cameras | tagged same camera or similar space |
| Branch futures | W&B LLM (templates fallback) | baseline + 2 interventions |
| Verify citations | code | drops invented clip ids, recomputes N, needs N >= 2 |
| Recommend | W&B LLM (rules fallback) | one placement, cited |

## Privacy

Behavior only: no faces, identity, age, gender, race, emotion, clothing, plates, speech or audio.
Licensed challenge footage only. No video files are committed to this repo.

## Deploy on the challenge stack

In Cursor on the VM: "Use deployment/deploy-app-no-registry to deploy this repo's FastAPI app
(app.main:app, serves /app and /app/api) to my team namespace at Ingress path /app. WANDB keys come from
the environment, never from files."
