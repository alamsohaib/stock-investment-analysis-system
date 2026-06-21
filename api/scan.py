"""GET /api/scan?top=20 — synchronous "lite" market scan (serverless).

Unlike the desktop app (background thread, ~120 stocks), this must finish inside
the platform time limit, so it deep-analyses only the most-liquid handful of names
and returns the ranked result in one response. The shape matches the desktop API's
scan result so the frontend renders it identically.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler  # noqa: E402
from _lib import pipeline  # noqa: E402
from _lib.serverless import send_json, query_param, lite_config, LITE_MAX_SYMBOLS  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            top = int(query_param(self, "top", "20") or "20")
        except ValueError:
            top = 20
        try:
            result = pipeline.run_universe(lite_config(), top_n=top)
            result["meta"]["lite_scan"] = True
            result["meta"]["lite_max_symbols"] = LITE_MAX_SYMBOLS
            send_json(self, {"ready": True, "result": result})
        except Exception as e:  # noqa: BLE001
            send_json(self, {"error": str(e)}, 500)
