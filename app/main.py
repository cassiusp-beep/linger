"""Linger server. Serves the UI at /app and the agent at /app/api.

  uvicorn app.main:app --host 0.0.0.0 --port 8000      then open http://localhost:8000/app/
"""
import asyncio
import json
import pathlib
import sys

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import llm  # noqa: E402
from agent.agent import ask  # noqa: E402

DATA = ROOT / "data"
app = FastAPI(title="Linger")
TIMEOUT_S = 20


def _segments():
    real = DATA / "segments.json"
    return json.loads((real if real.exists() else DATA / "mock_segments.json").read_text())


def _cache():
    return json.loads((DATA / "cache.json").read_text())


class Ask(BaseModel):
    question: str
    camera_id: str | None = None


@app.on_event("startup")
def _startup():
    if llm.available():
        llm.init_tracing()


@app.get("/")
def root():
    return RedirectResponse("/app/")


@app.get("/app/api/health")
def health():
    return {"ok": True, "llm": llm.available(), "segments": len(_segments())}


@app.get("/app/api/cached")
def cached():
    return _cache()


@app.post("/app/api/ask")
async def ask_live(body: Ask):
    segs = _segments()
    cache = _cache()
    cam = body.camera_id or cache.get("camera_id")
    try:
        res = await asyncio.wait_for(asyncio.to_thread(ask, body.question, cam, segs), TIMEOUT_S)
        res["fallback"] = False
        return res
    except Exception as e:  # timeout or any agent failure: serve the recorded run, say so
        cache["fallback"] = True
        cache["fallback_reason"] = type(e).__name__
        return cache


app.mount("/app", StaticFiles(directory=ROOT / "app" / "static", html=True), name="static")
