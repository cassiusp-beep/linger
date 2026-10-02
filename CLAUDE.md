# Linger

A video agent for public-space design: behavior captions from SF street cameras -> events -> linkograph
-> plausible futures -> one placement recommendation. ANALYSIS_SPEC.md is the source of truth for how
videos are broken down; README.md and SETUP_LAPTOP.md cover running and the laptop-to-VM loop.

## Hard rules
- Behavior only. Never add faces, identity, age, gender, race, emotion, clothing, plates, speech or audio.
- Links are associations. Never write "caused", "because" or "made" in UI copy or LLM prompts.
- Every branch must cite >= 2 real segment_ids; keep the verify step in agent/branches.py.
- Never commit secrets (.env, /config, kubeconfig) or video files (app/static/clips is gitignored).
- Every LLM step must keep its rules fallback so the demo never dies.
- No em dashes in any user-facing text.

## Layout
- agent/: extract.py (captions -> events), links.py (scoring), branches.py (evidence, futures, recs),
  agent.py (the loop + trace), llm.py (W&B inference + Weave), search.py (local + vss adapters)
- app/main.py: FastAPI, serves app/static at /app and /app/api/{cached,ask,health}
- app/static/: vanilla JS + SVG UI, no build step
- scripts/: build_cache.py, inspect_segments.py, make_mock.py, check_llm.py

## Commands
make dev | make cache | make cache-rules | make check | make models | make pull-data
python scripts/inspect_segments.py   # check exported captions before running the agent

## Deadline mindset
Feature freeze 3:45pm PT. Prefer small, tested changes. Run `make cache-rules` after any agent change.
