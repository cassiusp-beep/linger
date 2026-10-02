"""Linger server. Serves the UI at /app and the agent at /app/api.

  uvicorn app.main:app --host 0.0.0.0 --port 8000      then open http://localhost:8000/app/
"""
import asyncio
import json
import pathlib
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import llm  # noqa: E402
from agent import vss  # noqa: E402
from agent.agent import ask  # noqa: E402
from agent.library import summarize  # noqa: E402
from agent.search import search_label  # noqa: E402

DATA = ROOT / "data"
app = FastAPI(title="Linger")
TIMEOUT_S = 20
_SOURCES: dict[str, str] | None = None
_CAMERA_RUNS: dict[str, dict] = {}


def _segments():
    real = DATA / "segments.json"
    return json.loads((real if real.exists() else DATA / "mock_segments.json").read_text())


def _segments_source_name():
    return "segments.json" if (DATA / "segments.json").exists() else "mock_segments.json"


def _cache():
    path = DATA / "cache.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _library_file():
    path = DATA / "library.json"
    return json.loads(path.read_text()) if path.exists() else None


def _sources() -> dict[str, str]:
    global _SOURCES
    if _SOURCES is None:
        path = DATA / "clip_sources.json"
        _SOURCES = json.loads(path.read_text()) if path.exists() else {}
    return _SOURCES


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
    return {
        "ok": True,
        "llm": llm.available(),
        "segments": len(_segments()),
        "clips": len(_sources()),
        "vss": vss.configured(),
        "search": search_label(),
    }


@app.get("/app/api/cached")
def cached():
    return _cache()


@app.get("/app/api/library")
def library():
    segs = _segments()
    lib = summarize(segs)
    lib["source"] = _segments_source_name()
    return lib


@app.get("/app/api/camera/{camera_id}")
def camera(camera_id: str):
    cache = _cache()
    if cache.get("camera_id") == camera_id:
        return cache
    lib_file = _library_file() or {}
    runs = lib_file.get("runs") or {}
    if camera_id in runs:
        return runs[camera_id]
    if camera_id in _CAMERA_RUNS:
        return _CAMERA_RUNS[camera_id]
    segs = _segments()
    if not any(s["camera_id"] == camera_id for s in segs):
        raise HTTPException(404, "camera not found")
    res = ask("Where should seating go on this block?", camera_id, segs, use_llm=False)
    res["source"] = _segments_source_name()
    _CAMERA_RUNS[camera_id] = res
    return res


@app.api_route("/app/api/clip/{segment_id}", methods=["GET", "HEAD"])
def clip(segment_id: str, request: Request):
    """Proxy a segment mp4 from VSS so the browser can play without a JWT."""
    source = _sources().get(segment_id)
    if not source:
        raise HTTPException(404, "clip not found")
    if not vss.configured():
        raise HTTPException(503, "VSS credentials not configured")

    if request.method == "HEAD":
        try:
            probe = vss.open_stream(source, range_header="bytes=0-0")
        except Exception as e:
            raise HTTPException(502, f"clip fetch failed: {type(e).__name__}") from e
        try:
            headers = {"Content-Type": "video/mp4", "Accept-Ranges": "bytes"}
            cr = probe.headers.get("Content-Range") or ""
            if "/" in cr:
                total = cr.rsplit("/", 1)[-1]
                if total.isdigit():
                    headers["Content-Length"] = total
            elif probe.headers.get("Content-Length"):
                headers["Content-Length"] = probe.headers["Content-Length"]
            return Response(status_code=200, headers=headers)
        finally:
            probe.close()

    try:
        upstream = vss.open_stream(source, range_header=request.headers.get("range"))
    except Exception as e:
        raise HTTPException(502, f"clip fetch failed: {type(e).__name__}") from e

    headers = {}
    for key in ("Content-Length", "Content-Range", "Accept-Ranges"):
        val = upstream.headers.get(key)
        if val:
            headers[key] = val
    headers["Content-Type"] = "video/mp4"
    headers.setdefault("Accept-Ranges", "bytes")
    headers["X-Accel-Buffering"] = "no"
    status = getattr(upstream, "status", 200) or 200

    def body():
        try:
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            upstream.close()

    return StreamingResponse(body(), status_code=status, headers=headers, media_type="video/mp4")


@app.post("/app/api/ask")
async def ask_live(body: Ask):
    segs = _segments()
    cache = _cache()
    cam = body.camera_id or cache.get("camera_id")
    try:
        res = await asyncio.wait_for(asyncio.to_thread(ask, body.question, cam, segs), TIMEOUT_S)
        res["fallback"] = False
        return res
    except Exception as e:
        # Prefer a cached/library run for this camera; else the hero cache.
        lib_file = _library_file() or {}
        runs = lib_file.get("runs") or {}
        fallback = runs.get(cam) or cache
        out = dict(fallback)
        out["fallback"] = True
        out["fallback_reason"] = type(e).__name__
        return out


app.mount("/app", StaticFiles(directory=ROOT / "app" / "static", html=True), name="static")
