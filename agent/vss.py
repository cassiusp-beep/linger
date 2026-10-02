"""VSS retrieval helpers: login, search, and authenticated clip streaming.

Credentials from env (injected on the VM / in the linger-env Secret):
  VSS_URL, VSS_USERNAME, VSS_PASSWORD
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_token: str | None = None
_token_at = 0.0
_TOKEN_TTL_S = 25 * 60


def configured() -> bool:
    return bool(os.getenv("VSS_URL") and os.getenv("VSS_USERNAME") and os.getenv("VSS_PASSWORD"))


def base_url() -> str:
    return os.environ["VSS_URL"].rstrip("/")


def token(force: bool = False) -> str:
    global _token, _token_at
    if not force and _token and (time.time() - _token_at) < _TOKEN_TTL_S:
        return _token
    body = json.dumps({
        "username": os.environ["VSS_USERNAME"],
        "password": os.environ["VSS_PASSWORD"],
    }).encode()
    req = urllib.request.Request(
        f"{base_url()}/api/v1/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    _token = data["access_token"]
    _token_at = time.time()
    return _token


def search(query: str, camera_id: str | None = None, top_k: int = 15) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "query": query,
        "top_k": max(1, min(top_k, 100)),
        "llm_top_n": 1,
        "min_similarity": 0.2,
        "include_public": True,
        "time_filter": "all",
    }
    if camera_id:
        payload["metadata_filters"] = {"camera_id": camera_id}
    return _post_json("/api/v1/search", payload).get("results") or []


def open_stream(source: str, range_header: str | None = None):
    """Open a readable HTTP response for a segment clip. Retries once on 401."""
    last_err: Exception | None = None
    for force in (False, True):
        tok = token(force=force)
        qs = urllib.parse.urlencode({"source": source, "token": tok})
        req = urllib.request.Request(f"{base_url()}/api/v1/videos/stream?{qs}", method="GET")
        if range_header:
            req.add_header("Range", range_header)
        try:
            return urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code != 401:
                raise
    raise last_err  # type: ignore[misc]


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    last_err: Exception | None = None
    for force in (False, True):
        req = urllib.request.Request(
            f"{base_url()}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token(force=force)}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code != 401:
                raise
    raise last_err  # type: ignore[misc]
