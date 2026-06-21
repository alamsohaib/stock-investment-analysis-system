"""GET /api/search?q=hbl — symbol/name search over the PSX universe."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler  # noqa: E402
from _lib import psx_client as psx  # noqa: E402
from _lib.serverless import send_json, query_param  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = (query_param(self, "q", "") or "").strip().upper()
        out = []
        try:
            if q:
                for s in psx.get_symbols():
                    if q in (s["symbol"] or "").upper() or q in (s["name"] or "").upper():
                        if not s.get("is_debt"):
                            out.append(s)
                    if len(out) >= 20:
                        break
            send_json(self, {"results": out})
        except Exception as e:  # noqa: BLE001
            send_json(self, {"error": str(e)}, 500)
