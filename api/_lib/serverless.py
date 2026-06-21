"""Shared helpers for the Vercel serverless functions in /api.

These functions run on a stateless, time-limited host, so the behaviour differs
from the local http.server app in two honest ways:

  * No background scan job. /api/scan runs SYNCHRONOUSLY and must finish inside
    the platform time limit (60s on Vercel's Hobby tier), so it scans a much
    smaller, most-liquid universe — a "lite scan". The full 120-stock scan still
    lives in the local desktop app (run.py).
  * No persistent cache. The disk cache points at /tmp and is wiped between cold
    starts, so most requests re-fetch from PSX. The in-memory cache still helps
    within a single warm invocation.
"""
from __future__ import annotations

import copy
import json
import os

_CFG = None
_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# How many of the most-liquid names the hosted "lite scan" deep-analyses. Kept
# small so the whole scan finishes inside the serverless time budget. Override
# with the PSX_LITE_MAX env var on Vercel if your plan allows longer functions.
LITE_MAX_SYMBOLS = int(os.environ.get("PSX_LITE_MAX", "12"))


def load_config():
    """Load (and memoise) config.json bundled alongside the analysis library."""
    global _CFG
    if _CFG is None:
        with open(_CFG_PATH, encoding="utf-8") as fh:
            _CFG = json.load(fh)
    return _CFG


def lite_config():
    """A copy of the config with the universe shrunk to fit the time budget."""
    cfg = copy.deepcopy(load_config())
    u = cfg.setdefault("universe", {})
    u["max_symbols_full_scan"] = LITE_MAX_SYMBOLS
    # Focus the lite scan on liquid, non-penny names so the short list is useful.
    u["min_daily_volume"] = max(u.get("min_daily_volume", 0), 50000)
    return cfg


def send_json(handler, obj, status=200):
    """Write a JSON response from a BaseHTTPRequestHandler-style Vercel handler."""
    body = json.dumps(obj, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def query_param(handler, name, default=""):
    """Pull a single query-string value off the request path."""
    from urllib.parse import urlparse, parse_qs

    qs = parse_qs(urlparse(handler.path).query)
    return qs.get(name, [default])[0]
