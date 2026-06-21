"""GET /api/deepdive?symbol=HBL — institutional single-stock deep-dive (serverless)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler  # noqa: E402
from _lib import deepdive  # noqa: E402
from _lib.serverless import send_json, query_param, load_config  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        symbol = (query_param(self, "symbol", "") or "").upper().strip()
        if not symbol:
            send_json(self, {"error": "missing ?symbol="}, 400)
            return
        try:
            # sector_median_pe is None on the hosted side (no cached full scan);
            # the deep-dive degrades gracefully to config-clamped relative valuation.
            report = deepdive.build_deepdive(symbol, load_config(), sector_median_pe=None)
            send_json(self, report)
        except Exception as e:  # noqa: BLE001
            send_json(self, {"error": str(e)}, 500)
