"""Search adapters.

local_search: keyword overlap over captions in segments.json. Works offline, used as fallback.
vss_search:   hybrid search against the team VSS archive, mapped back to local segment_ids.
"""
import json
import os
import pathlib
import re

from . import vss

SYN = {
    "sit": ["sitting", "seated", "bench", "ledge"], "seating": ["sitting", "bench", "ledge"],
    "linger": ["lingering", "standing", "stops"], "stop": ["stops", "standing", "lingering"],
    "group": ["group"], "detour": ["path change", "detour", "slowdown"], "obstacle": ["pole", "detour"],
    "wait": ["waiting", "crosswalk"], "cross": ["crosswalk", "waiting"],
}

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SOURCE_TO_ID: dict[str, str] | None = None


def _terms(q):
    words = re.findall(r"[a-z]+", q.lower())
    out = set(words)
    for w in words:
        for k, v in SYN.items():
            if w.startswith(k):
                out.update(v)
    return out


def local_search(query, segments, camera_id=None, k=5):
    terms = _terms(query)
    scored = []
    for s in segments:
        if camera_id and s["camera_id"] != camera_id:
            continue
        cap = s.get("caption", "").lower()
        hit = sum(1 for t in terms if t in cap)
        if hit:
            scored.append((hit, s["segment_id"]))
    scored.sort(key=lambda x: -x[0])
    return [sid for _, sid in scored[:k]]


def _source_index():
    global _SOURCE_TO_ID
    if _SOURCE_TO_ID is not None:
        return _SOURCE_TO_ID
    path = _ROOT / "data" / "clip_sources.json"
    if not path.exists():
        _SOURCE_TO_ID = {}
        return _SOURCE_TO_ID
    mapping = json.loads(path.read_text())
    _SOURCE_TO_ID = {src: sid for sid, src in mapping.items()}
    return _SOURCE_TO_ID


def vss_search(query, segments, camera_id=None, k=5):
    """Search VSS, return local segment_ids. Falls back to local_search on any failure."""
    if not vss.configured():
        return local_search(query, segments, camera_id, k)
    try:
        hits = vss.search(query, camera_id=camera_id, top_k=max(k * 3, 15))
    except Exception as e:
        print("vss_search failed, using local:", e)
        return local_search(query, segments, camera_id, k)
    by_src = _source_index()
    known = {s["segment_id"] for s in segments}
    out = []
    for hit in hits:
        sid = by_src.get(hit.get("source"))
        if not sid or sid not in known or sid in out:
            continue
        if camera_id:
            # VSS already filtered; keep a local guard
            seg = next((s for s in segments if s["segment_id"] == sid), None)
            if seg and seg.get("camera_id") != camera_id:
                continue
        out.append(sid)
        if len(out) >= k:
            break
    return out or local_search(query, segments, camera_id, k)


def get_search():
    if os.getenv("LINGER_SEARCH", "vss") == "vss" and vss.configured():
        return vss_search
    return local_search


def search_label():
    if get_search() is vss_search:
        return "VSS search"
    return "local caption search"
