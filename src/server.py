"""Web server + JSON API — standard library only (http.server).

Routes
  GET  /                         -> dashboard (web/index.html)
  GET  /static/<file>            -> static assets (css/js)
  GET  /api/status               -> health + data freshness
  GET  /api/scan                 -> latest ranked opportunities (kicks off a
                                    background scan if none is fresh)
  GET  /api/scan/status          -> progress of the running/last scan
  GET  /api/analyze/<SYMBOL>     -> full deep-dive report for one stock
  GET  /api/history/<SYMBOL>     -> daily close history (for charts)
  GET  /api/search?q=<text>      -> symbol search
"""
from __future__ import annotations

import json
import os
import threading
import time
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import pipeline
from . import deepdive
from . import psx_client as psx
from . import cache as cachemod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

_CFG = {}


def load_config():
    global _CFG
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as fh:
        _CFG = json.load(fh)
    return _CFG


# --------------------------------------------------------------------------- #
# Background scan job (so the browser never blocks on a long first run)
# --------------------------------------------------------------------------- #
class ScanJob:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.progress = []
        self.result = None
        self.sector_pe = None
        self.started_at = None
        self.finished_at = None
        self.error = None

    def _log(self, msg):
        ts = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S")
        self.progress.append(f"[{ts}] {msg}")
        self.progress = self.progress[-50:]

    def start(self, top_n=20):
        with self.lock:
            if self.running:
                return False
            self.running = True
            self.progress = []
            self.error = None
            self.started_at = time.time()
        threading.Thread(target=self._run, args=(top_n,), daemon=True).start()
        return True

    def _run(self, top_n):
        try:
            self._log("Starting PSX universe scan…")
            res = pipeline.run_universe(_CFG, top_n=top_n, progress=self._log)
            # recompute & stash sector P/E for fast single-symbol calls
            candidates = pipeline.screen_universe(_CFG)
            limit = _CFG.get("universe", {}).get("max_symbols_full_scan", 120)
            deep = candidates[:limit]
            snap_by = {c["symbol"]: c for c in deep}
            comps = {s: psx.get_company(s) for s in snap_by}
            self.sector_pe = pipeline._sector_median_pe(comps, snap_by)
            self.result = res
            self._log(f"Done. Ranked {res['meta']['deep_analysed']} stocks.")
        except Exception as e:  # noqa
            self.error = str(e)
            self._log(f"ERROR: {e}")
        finally:
            self.running = False
            self.finished_at = time.time()


_JOB = ScanJob()


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "PSXAnalyst/1.0"

    def log_message(self, fmt, *args):  # quieter console
        pass

    # ---- helpers ----
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self._send_json({"error": "not found"}, 404)
            return
        ext = os.path.splitext(path)[1].lower()
        ctype = _CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(path, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- routing ----
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            if path == "/" or path == "/index.html":
                return self._send_file(os.path.join(WEB, "index.html"))
            if path.startswith("/static/"):
                rel = path[len("/static/"):].replace("..", "")
                return self._send_file(os.path.join(WEB, "static", rel))
            if path == "/api/status":
                return self._api_status()
            if path == "/api/scan":
                return self._api_scan(qs)
            if path == "/api/scan/status":
                return self._send_json(self._scan_state())
            if path.startswith("/api/analyze/"):
                return self._api_analyze(path.rsplit("/", 1)[-1].upper())
            if path.startswith("/api/deepdive/"):
                return self._api_deepdive(path.rsplit("/", 1)[-1].upper())
            if path.startswith("/api/history/"):
                return self._api_history(path.rsplit("/", 1)[-1].upper())
            if path == "/api/search":
                return self._api_search(qs.get("q", [""])[0])
            self._send_json({"error": "unknown route"}, 404)
        except BrokenPipeError:
            pass
        except Exception as e:  # never 500 silently — tell the client
            self._send_json({"error": str(e)}, 500)

    # ---- endpoints ----
    def _api_status(self):
        age = cachemod.cached_age_seconds("market_snapshot")
        self._send_json({
            "ok": True,
            "version": "1.0.0",
            "server_time_utc": dt.datetime.now(dt.timezone.utc)
                .strftime("%Y-%m-%d %H:%M:%S UTC"),
            "snapshot_age_seconds": round(age) if age is not None else None,
            "scan": self._scan_state(include_result=False),
            "data_source": "PSX Data Portal (dps.psx.com.pk) — public, DELAYED data",
        })

    def _scan_state(self, include_result=True):
        st = {
            "running": _JOB.running,
            "progress": _JOB.progress,
            "error": _JOB.error,
            "has_result": _JOB.result is not None,
            "started_at": _JOB.started_at,
            "finished_at": _JOB.finished_at,
        }
        if include_result and _JOB.result is not None:
            st["result"] = _JOB.result
        return st

    def _api_scan(self, qs):
        top = int(qs.get("top", ["20"])[0])
        force = qs.get("force", ["0"])[0] in ("1", "true", "yes")
        if force or (_JOB.result is None and not _JOB.running):
            _JOB.start(top_n=top)
        if _JOB.result is not None and not force:
            return self._send_json({"ready": True, "result": _JOB.result,
                                    "running": _JOB.running})
        return self._send_json({"ready": False, "running": _JOB.running,
                                "progress": _JOB.progress})

    def _api_analyze(self, symbol):
        report = pipeline.build_report(symbol, _CFG, sector_median_pe=_JOB.sector_pe)
        self._send_json(report)

    def _api_deepdive(self, symbol):
        report = deepdive.build_deepdive(symbol, _CFG, sector_median_pe=_JOB.sector_pe)
        self._send_json(report)

    def _api_history(self, symbol):
        hist = psx.get_history(symbol)
        pts = [{"t": h["t"], "close": h["close"], "volume": h["volume"]} for h in hist]
        # keep last ~400 points for a snappy chart
        self._send_json({"symbol": symbol, "points": pts[-400:]})

    def _api_search(self, q):
        q = (q or "").strip().upper()
        out = []
        if q:
            for s in psx.get_symbols():
                if q in s["symbol"].upper() or q in (s["name"] or "").upper():
                    if not s.get("is_debt"):
                        out.append(s)
                if len(out) >= 20:
                    break
        self._send_json({"results": out})


def run(host="127.0.0.1", port=8800):
    load_config()
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd
