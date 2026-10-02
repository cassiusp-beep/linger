# Laptop setup (Mac) and the laptop-to-VM loop

Split of work: the **laptop** runs the Linger app, the agent, W&B inference and Weave, and owns the repo.
The **VM teammate** runs VSS (search, re-ingest, export) and deploys. Git is the only bridge.
Team credentials (`/config/<team>.config`, kubeconfig) never leave the VM.

## 1. One-time installs (10 minutes)

```bash
# Homebrew, if missing: https://brew.sh
brew install python@3.12 git gh
gh auth login                      # GitHub.com, HTTPS, browser login
```
Install the Cursor desktop app (cursor.com) and sign in with the personal email you applied with, so the
challenge credits apply. Python 3.10 or newer is required.

## 2. Repo

```bash
unzip linger.zip && cd linger
git init && git add . && git commit -m "Linger: working slice"
gh repo create linger --public --source=. --push
gh repo edit --add-collaborator <vm-teammate-github>     # or add them in GitHub settings
```

## 3. Python env and W&B

```bash
make setup          # creates .venv, installs deps, creates .env from .env.example
```
Edit `.env`:
- `WANDB_API_KEY`: from https://wandb.ai/authorize, signed in with the account the organizers credited
- `WANDB_TEAM`: your W&B entity (shown in your W&B URL)

```bash
make models         # lists serverless models; paste one instruction model id into LINGER_MODEL in .env
make check          # one live JSON call + Weave init. A 401/402 means credits: ask the W&B team.
```

## 4. Run it

```bash
make cache          # agent run with the LLM (make cache-rules = no W&B), writes the demo cache
make dev            # http://localhost:8000/app/
```
Weave traces: https://wandb.ai/<WANDB_TEAM>/linger/weave

## 5. Open in Cursor (laptop)

Open the `linger` folder in Cursor. Good first prompts:
- "Read agent/agent.py and agent/branches.py. Run make cache and tell me if any step fell back to rules and why."
- "Tighten the branch prompt in agent/branches.py so interventions are specific to the camera's features."

Optional: clone https://github.com/vast-data/vast-builders-challenge next to this repo and point Cursor at
`.cursor/skills/retrieval/search` to write `vss_search` in `agent/search.py`. It only runs on the VM (that is
where the credentials are), so the VM teammate tests it.

## 6. The loop with the VM teammate

| Who | Does | Command |
|---|---|---|
| VM | Re-ingest SF chunks with the prompt in the README | Cursor on the VM |
| VM | Export `data/segments.json`, push | prompt below, then `git add data/segments.json && git commit -m data && git push` |
| Laptop | Pull, run the agent with the LLM, review the UI | `make pull-data && make dev` |
| Laptop | Push the cache and any UI changes | `git add -A && git commit -m cache && git push` |
| VM | Pull, fetch clips, deploy | `git pull`, then the deploy prompt in the README |

Clips stay on the VM (`app/static/clips/` is gitignored, licensing covers use, not redistribution).
Locally, "Show in view" shows the caption instead of video. That is expected.

### Export prompt for the VM teammate (paste into Cursor on the VM)

> Using vastdb-read and the videos skill, export every segment for location san_francisco, camera_id <HERO>,
> plus sf_streets_cam-* others and the indoor location, to data/segments.json as a JSON list. Each row:
> segment_id, video_id, camera_id, offset (seconds from the start of that camera's first segment, using the
> absolute start time), t0, t1, light ("day" or "night" from the reasoning text, else "unknown"), caption
> (the reasoning text), clip_url (null for now). Sort by camera_id then offset. Print 3 rows and the count.
> Then download the clips for the hero camera into app/static/clips/<segment_id>.mp4 and set clip_url to
> clips/<segment_id>.mp4 (that folder is gitignored).
