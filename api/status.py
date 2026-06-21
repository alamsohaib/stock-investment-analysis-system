"""GET /api/status — health + data freshness (serverless)."""
import os
import sys
import datetime as dt

sys.path.insert(0, os.path.dirname(__file__))
from http.server import BaseHTTPRequestHandler  # noqa: E402
from _lib import cache as cachemod  # noqa: E402
from _lib.serverless import send_json, LITE_MAX_SYMBOLS  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            age = cachemod.cached_age_seconds("market_snapshot")
            send_json(self, {
                "ok": True,
                "version": "1.0.0",
                "hosted": True,
                "lite_scan_symbols": LITE_MAX_SYMBOLS,
                "server_time_utc": dt.datetime.now(dt.timezone.utc)
                    .strftime("%Y-%m-%d %H:%M:%S UTC"),
                "snapshot_age_seconds": round(age) if age is not None else None,
                "data_source": "PSX Data Portal (dps.psx.com.pk) — public, DELAYED data",
            })
        except Exception as e:  # noqa: BLE001
            send_json(self, {"error": str(e)}, 500)
