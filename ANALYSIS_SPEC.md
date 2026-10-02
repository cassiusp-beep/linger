# Linger analysis spec: how a video becomes a recommendation

For the VM teammate and for Cursor on the VM. Every rule here matches the code in `agent/`.
If this file and the code disagree, the code wins; tell the laptop teammate.

## How to use this on the VM

```bash
cd ~ && git clone https://github.com/<owner>/linger.git && cd linger
python3 -m pip install --user fastapi uvicorn openai weave   # or use a venv
```

Then start Cursor (`agent`) in `~/vast-builders-challenge` (that is where the skills are) and paste:

> Read ~/linger/ANALYSIS_SPEC.md. We are doing Stage 1 and Stage 2. Start with Stage 1 step 1.
> Use the skills in this repo for VSS. Write the export to ~/linger/data/segments.json.

After each export, check it before anything else:

```bash
cd ~/linger && python3 scripts/inspect_segments.py              # parse rate, behaviors, zones, day/night
LINGER_LLM=0 python3 scripts/build_cache.py                      # full agent run, rules only, prints every step
```

## The pipeline at a glance

```
VSS (already done by organizers)     parent video -> chunks -> fixed-length segments, each with
                                     reasoning text, perception, object classes (YOLO11)
Stage 1  Re-ingest  (VM)             our prompt -> Cosmos3-Reason rewrites each segment's reasoning text
Stage 2  Export     (VM)             VastDB rows -> data/segments.json
Stage 3  Events     (agent/extract)  each "[t=Xs] ..." caption line -> one event
Stage 4  Links      (agent/links)    pairs of events close in time and space -> scored links
Stage 5  Critical   (agent/agent)    events with the most links; pick one link to branch
Stage 6  Day/night  (agent/branches) stays per zone, split by light
Stage 7  Evidence   (agent/branches) search all cameras for clips that resemble the link
Stage 8  Futures    (agent/branches) baseline + 2 interventions, each citing >= 2 clips
Stage 9  Recommend  (agent/branches) one placement, cited
```

Stages 1 and 2 are VM work. Stages 3 to 9 run anywhere from `data/segments.json`.

---

## Stage 1: Re-ingest (VM only, one person only)

**Scope.** Location `san_francisco`, cameras `sf_streets_cam-*` (92 chunks). Optional extra for evidence:
location `indoor` (30 chunks). Skip `toronto` (dashcam, the camera moves, zones mean nothing),
`nashville` (highway), `warehouse3`.

**Prompt (726 characters, under the 800 limit). Use it exactly.**

```
Describe only how people and vehicles use this street space. Report: people visible; how many walk, stand, sit, or linger (still over 5s, not seated); where they stop, on a 3x3 frame grid: TL, TC, TR, ML, C, MR, BL, BC, BR; groups of 2+ stopping together; path changes (turn, detour, slowdown, waiting to cross) and the nearby feature (bench, ledge, curb, crosswalk, bus stop, doorway, storefront, tree, pole); vehicles that stop, block a crosswalk, or arrive at a stop (car, bus, truck, bicycle), with zone. Give approximate seconds and say day or night. Never describe faces, identity, age, gender, race, emotion, clothing, plates, or speech. If unsure, write unsure. Short lines only: [t=4s] bus arrives, BL, near bus stop.
```

**Steps.**
1. Inventory first:
   > For location san_francisco, list each camera_id with chunk count, time range, and day or night.
   > Show one full row for one SF segment exactly as stored: reasoning text, perception field, object classes.
   > Tell me whether perception has person bounding boxes or track ids, and the segment length in seconds.
2. Re-ingest **10 chunks** of the camera with the most people (scenario `surveillance`, prompt above).
   Wait until done ("is it done yet?"). Export those 10 (Stage 2) and run `inspect_segments.py`.
3. Gate: **parse rate 70% or higher and no banned words** -> re-ingest the rest of SF.
   Below 70% -> look at the worst captions the script prints and see "If the captions don't follow the format".

**Hero camera.** The fixed SF camera with the most stays (stand, sit, linger) in the inspector's behaviors.
Not the one with the most walking.

## Stage 2: Export `data/segments.json`

A JSON list, one object per segment, sorted by `camera_id` then `offset`.

| Field | Type | How to fill it |
|---|---|---|
| `segment_id` | string | the VastDB row / segment id, unique |
| `video_id` | string | parent video id |
| `camera_id` | string | e.g. `sf_streets_cam-2` |
| `offset` | number, seconds | segment absolute start time minus the earliest start time **for that camera**. If absolute times are missing, use `chunk_index * chunk_len + segment_start_within_chunk`. This puts all of a camera's segments on one timeline so links can cross segment boundaries. |
| `t0`, `t1` | number, seconds | segment start and end within its own clip (usually 0 and the segment length) |
| `light` | `day`, `night`, `unknown` | from the reasoning text ("Day." / "Night." / "nighttime"); `unknown` if absent. The agent also infers it from the caption. |
| `caption` | string | the reasoning text from our re-ingest, unedited |
| `clip_url` | string or null | null in git. On the VM before deploy: download to `app/static/clips/<segment_id>.mp4` and set `clips/<segment_id>.mp4`. That folder is gitignored; never commit video. |
| `persons` | optional list | only if perception has boxes: `[{"t": 1.5, "zone": "BL", "box": [x, y, w, h]}]`. Zone = 3x3 cell of the box centre: `col = min(2, int(3*cx/W))`, `row = min(2, int(3*cy/H))`, zones in row order `TL TC TR / ML C MR / BL BC BR`. Not used by the agent yet; export it if it is easy. |

Example row:

```json
{"segment_id": "cam2_s10", "video_id": "sf-streets/2", "camera_id": "sf_streets_cam-2",
 "offset": 100, "t0": 0, "t1": 10, "light": "night",
 "caption": "Night. [t=2s] bus arrives, BL, near bus stop. [t=4s] 3 standing, BL, group, near bus stop.",
 "clip_url": null}
```

Push it: `git add data/segments.json && git commit -m "SF segments" && git push`.

---

## Stage 3: Events (`agent/extract.py`)

Each caption is split into lines with the regex `\[t=(\d+(?:\.\d+)?)s\]\s*([^\[]+)`.
Each line becomes at most one event. Lines that match no behavior are skipped (this is the parse rate).

**Behavior, first match wins. Vehicle phrases are checked before people phrases** (so "bus stops" is a bus, not a person stopping).

| Behavior | Actor | Matched phrases (lowercase, substring) |
|---|---|---|
| `crosswalk_block` | vehicle | blocks crosswalk, blocks the crosswalk, blocking (the) crosswalk, in (the) crosswalk |
| `bus_arrive` | vehicle | bus arrives, bus stops, bus pulls, bus arriving, bus stopped |
| `vehicle_stop` | vehicle | car/truck/vehicle/bicycle stops, car/truck stopped, car parks, double parked |
| `path_change` | person | path change, detour, slowdown, slows, turns |
| `sit` | person | sitting, seated, sits |
| `linger` | person | lingering, lingers |
| `stop` | person | stops, stopped, stopping |
| `stand` | person | standing, waiting |
| `walk` | person | walking, walks, passing |

"Stays" = `stop`, `stand`, `sit`, `linger`. Seating and lighting decisions are built on stays.

**Other fields per event.**

| Field | Rule |
|---|---|
| `t` | `offset + line seconds` (camera timeline) |
| `zone` | first token among `TL TC TR ML C MR BL BC BR` in the line. Missing -> `C` with `zone_guessed: true` (the inspector counts these) |
| `count` | first integer in the line; vehicles are always 1; 0 people -> line skipped |
| `group` | the word "group" appears |
| `near` | text after "near" up to a comma or period (e.g. `bus stop`) |
| `vehicle` | bus, truck, bicycle, car or vehicle (vehicle events only) |
| `light` | from the segment |
| `confidence` | 0.75, or 0.4 if the line says "unsure" |

## Stage 4: Links (`agent/links.py`)

A link is an **association** between two events, never a cause. Candidates are pairs (A before B) where:
same `camera_id`; `0 <= t_B - t_A <= 60s`; zones are the same or share an edge; not walk-to-walk;
not vehicle-to-vehicle.

```
score = 0.5 * exp(-dt / 20)  +  0.3 * zone_prox  +  0.2 * type_compat
zone_prox:  same zone 1.0, adjacent 0.6   (far pairs are dropped)
keep score >= 0.5, at most 6 outgoing links per event (highest scores)
```

**type_compat (A -> B).** Any pair not listed is 0.3.

| A | B | compat |
|---|---|---|
| sit | linger | 1.0 |
| linger | sit | 1.0 |
| linger | stop / stand | 0.9 |
| stop | linger | 0.9 |
| stand | linger | 0.8 |
| stop | stand | 0.8 |
| stop / stand / linger | path_change | 0.8 |
| sit | stop | 0.8 |
| stop | stop | 0.7 |
| stand | stand | 0.6 |
| walk | path_change | 0.5 |
| walk | walk | 0.2 (and skipped anyway) |
| bus_arrive | stand | 1.0 |
| bus_arrive | linger / stop | 0.9 |
| bus_arrive | walk | 0.5 |
| stand / linger | bus_arrive | 0.7 |
| crosswalk_block | path_change | 1.0 |
| crosswalk_block | stand / stop | 0.8 |
| vehicle_stop | path_change | 0.8 |
| vehicle_stop | stand | 0.6 |

**Link type (rules; the LLM may rewrite type and rationale, never `is_causal`).**
vehicle -> path_change = `blocks`; bus_arrive -> stay = `attracts`; stay -> path_change = `blocks`;
stay -> stay = `attracts`; same behavior = `follows`; otherwise `co-occurs`.

**Rationale template:** "2 people standing at BL near the bus stop, 2s after a bus arriving at BL near the bus stop."
Banned words in any rationale: caused, because, made.

**Healthy numbers:** 2 to 4 links per event. Above 5 the linkograph is unreadable (raise the threshold to 0.55).
Below 1 the captions are too sparse (check `offset`; segments may not share a timeline).

## Stage 5: Critical moves and the branched link

Degree = number of links touching an event. The top 5 by degree are **critical moves** (ringed in the UI).
The agent branches one link: among links touching the highest-degree **stay** event, it prefers
bus_arrive -> stay, then stay -> stay, then the highest score.

## Stage 6: Day and night

For the hero camera, people's stays are summed per zone, split by `light`.
`night_share` for the branched zone = night stays / all stays there.

## Stage 7: Evidence

Searches across **all cameras** (local caption search now; `vss_search` once wired on the VM):
`people <B verb> near <B near>`, `people sitting on a bench or ledge`, `people walking around an obstacle`,
`group <A verb> at <A zone>`, `people waiting at night`, `bus arrives at the stop`. Top 4 each, deduped, max 10.
Each clip is tagged `same_space` (hero camera) or `similar_space` (any other camera).

## Stage 8: Futures

| Branch | When | Cites clips with |
|---|---|---|
| b1 No change (baseline) | always | stays in the branched zone, hero camera |
| b2 Bench at the zone, beside the feature, facing the crosswalk | always | sitting anywhere + stays in the zone |
| b3 Pedestrian lighting | `night_share >= 0.3` | night stays + stays in the zone |
| b3 Move the bus stop marker | else, if the link involves a bus or any bus arrival was seen | bus arrivals + detours |
| b3 Clear the walking path | otherwise | detours + vehicle blocks |

**Verify (code, after the LLM or templates):** drop any cited clip not in the evidence list, recompute
`plausibility_n` from what is left, drop any branch with fewer than 2 clips. Label: "plausible, based on N clips".

## Stage 9: Recommendation

The bench branch if it survived, else the first surviving intervention. The reason given is the branched
zone and its stay count on the hero camera. Cites that branch's clips.

With W&B available (`LINGER_LLM=1`), Stages 1 to 9 keep the same structure, but the search plan, link
rationales, futures and recommendation are written by the LLM and then pass the same verify step.
If any LLM step fails, that step falls back to the rules above and the trace says so.

---

## If the captions don't follow the format

| Symptom in `inspect_segments.py` | Likely cause | Fix |
|---|---|---|
| Many segments with no `[t=Xs]` lines | Cosmos wrote prose | Re-ingest 3 chunks with the same prompt plus "Use only the line format shown." Do not change anything else. |
| Lines parse but zones defaulted to C | Cosmos used words like "left side" | Keep the prompt; ask Cursor to add a mapping (left/centre/right x near/middle/far) in `agent/extract.py` |
| Behaviors are all `walk` | That camera has no stays | Pick another SF camera as hero |
| Banned words found | Clothing or gender leaked | Note which; the parser ignores them, but do not show those captions in the demo |
| `light` all unknown | No "day"/"night" in captions | Ask Cursor to set `light` from the segment's timestamp hour (19:00 to 06:00 = night) during export |
| Links per event below 1 | `offset` wrong (all zeros) | Recompute offsets per camera from absolute start times |

## Things to try once real data is in

> Using vss search on sf_streets_cam-<hero>, find the 5 segments where a bus arrives and people then gather.
> Show their captions and timestamps.

> Compare day vs night: run scripts/inspect_segments.py --camera <hero>, then tell me which zone has the
> biggest night share of stays.

> Implement vss_search in ~/linger/agent/search.py using the HTTP call the search skill makes. Signature:
> vss_search(query, segments, camera_id=None, k=5) -> list of segment_ids that exist in segments.
> Then run LINGER_SEARCH=vss LINGER_LLM=0 python3 scripts/build_cache.py and show the trace.
