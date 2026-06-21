"""GET /api/history?symbol=HBL — daily close history for the price chart."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler  # noqa: E402
from _lib import psx_client as psx  # noqa: E402
from _lib.serverless import send_json, query_param  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        symbol = (query_param(self, "symbol", "") or "").upper().strip()
        if not symbol:
            send_json(self, {"error": "missing ?symbol="}, 400)
            return
        try:
            hist = psx.get_history(symbol)
            pts = [{"t": h["t"], "close": h["close"], "volume": h["volume"]} for h in hist]
            send_json(self, {"symbol": symbol, "points": pts[-400:]})
        except Exception as e:  # noqa: BLE001
            send_json(self, {"error": str(e)}, 500)
