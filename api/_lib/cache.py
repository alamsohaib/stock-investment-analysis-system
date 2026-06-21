"""Tiny on-disk + in-memory TTL cache. Standard library only.

Keeps PSX from being hammered and makes the dashboard feel fast. Cached payloads
are stored as JSON files under data/cache/ so they survive restarts.
"""
from __future__ import annotations

import json
import hashlib
import os
import tempfile
import time
import threading

_LOCK = threading.Lock()
_MEM: dict[str, tuple[float, object]] = {}

# On a normal machine we cache next to the code (data/cache/). On a serverless
# host (Vercel) the bundle is read-only — only the system temp dir (/tmp) is
# writable, and it's ephemeral, so the disk cache is best-effort only. Honour an
# explicit override via PSX_CACHE_DIR, else use the temp dir when set, else local.
_DEFAULT_LOCAL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache"
)
_CACHE_DIR = os.environ.get("PSX_CACHE_DIR") or os.path.join(
    tempfile.gettempdir(), "psx_cache"
)
_DISK_OK = True
try:
    os.makedirs(_CACHE_DIR, exist_ok=True)
except OSError:
    _DISK_OK = False  # in-memory cache still works for the life of the process


def _path_for(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return os.path.join(_CACHE_DIR, f"{digest}.json")


def get(key: str, ttl_seconds: float):
    """Return cached value if present and fresh, else None."""
    now = time.time()
    with _LOCK:
        hit = _MEM.get(key)
        if hit and now - hit[0] <= ttl_seconds:
            return hit[1]
    if not _DISK_OK:
        return None
    # fall back to disk
    path = _path_for(key)
    try:
        if os.path.exists(path) and now - os.path.getmtime(path) <= ttl_seconds:
            with open(path, "r", encoding="utf-8") as fh:
                value = json.load(fh)
            with _LOCK:
                _MEM[key] = (os.path.getmtime(path), value)
            return value
    except (OSError, ValueError):
        return None
    return None


def set(key: str, value) -> None:
    now = time.time()
    with _LOCK:
        _MEM[key] = (now, value)
    if not _DISK_OK:
        return
    try:
        with open(_path_for(key), "w", encoding="utf-8") as fh:
            json.dump(value, fh)
    except (OSError, TypeError):
        pass  # caching is best-effort; never crash the app over it


def cached_age_seconds(key: str):
    """How old the freshest cached copy is, or None if not cached."""
    with _LOCK:
        hit = _MEM.get(key)
        if hit:
            return time.time() - hit[0]
    path = _path_for(key)
    if os.path.exists(path):
        return time.time() - os.path.getmtime(path)
    return None
