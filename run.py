"""PSX Investment Analysis System — launcher.

Just run:   python run.py
It starts the local web dashboard and opens your browser. No installation needed.
"""
from __future__ import annotations

import sys
import threading
import webbrowser

from src import server

HOST = "127.0.0.1"
PORT = 8800


def main():
    port = PORT
    for arg in sys.argv[1:]:
        if arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])

    httpd = server.run(HOST, port)
    url = f"http://{HOST}:{port}/"
    print("=" * 64)
    print("  PSX Investment Analysis System")
    print("  Dashboard:  " + url)
    print("  Data source: PSX Data Portal (public, DELAYED data)")
    print("  Press Ctrl+C to stop.")
    print("=" * 64)

    # open the browser a moment after the server is up
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down…")
        httpd.shutdown()


if __name__ == "__main__":
    main()
