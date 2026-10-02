"""Search adapters.

local_search: keyword overlap over captions in segments.json. Works offline, used as fallback.
vss_search:   wire this to the VSS search API (ask Cursor: "show me the HTTP call the search
              skill makes, then implement vss_search(query, camera_id, k) returning segment_ids").
"""
import os
import re

SYN = {
    "sit": ["sitting", "seated", "bench", "ledge"], "seating": ["sitting", "bench", "ledge"],
    "linger": ["lingering", "standing", "stops"], "stop": ["stops", "standing", "lingering"],
    "group": ["group"], "detour": ["path change", "detour", "slowdown"], "obstacle": ["pole", "detour"],
    "wait": ["waiting", "crosswalk"], "cross": ["crosswalk", "waiting"],
}


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


def vss_search(query, segments, camera_id=None, k=5):
    raise NotImplementedError("Wire vss_search to the VSS search endpoint (see module docstring).")


def get_search():
    return vss_search if os.getenv("LINGER_SEARCH") == "vss" else local_search


def search_label():
    return "VSS search" if os.getenv("LINGER_SEARCH") == "vss" else "local caption search"
