"""LOCAL DEV web server: static grid + on-demand trends collection.

DEV/TESTER ONLY. This is the one place a browser can trigger a SerpApi
collection (via the collector), so it deliberately reopens the cost channel —
but LOCALLY only. It is NOT shipped, NOT the read-only MCP server, and must
never be exposed publicly. The production surfaces (the static grid and the MCP
server) stay read-only; this server is just the HTTP sibling of the dev admin
CLI (`collector/admin.py`). The grid degrades gracefully when served by a plain
static server (no `/api` endpoint): it shows the equivalent admin command.

Run (replaces `python -m http.server` for the tester):
    python -m collector.serve            # serves repo root on 127.0.0.1:8000
    #   open http://127.0.0.1:8000/web/index.html

Endpoints:
    GET  /api/keywords                      -> {"keywords": [...]}
    POST /api/keywords  {"keywords":[...]}  -> set keywords (<=5) + re-collect
                                               trends, returns {ok, keywords, updated_at}
"""

from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import trends
from .admin import _read_overrides, _write_overrides
from .config import load_config

ROOT = Path(__file__).resolve().parent.parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/keywords":
            self._json(200, {"keywords": list(load_config().keywords)})
            return
        super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/keywords":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            kws = [str(k).strip() for k in (data.get("keywords") or []) if str(k).strip()][:5]
            if not kws:
                self._json(400, {"error": "no keywords"})
                return
            overrides = _read_overrides()
            overrides["keywords"] = kws
            _write_overrides(overrides)
            # collector call — the only SerpApi caller. LOCAL DEV trigger only.
            doc = trends.build(load_config())
            trends._write_atomic(doc)
            self._json(200, {"ok": True, "keywords": kws,
                             "updated_at": doc["meta"]["updated_at"]})
        except trends.FetchError as exc:
            self._json(502, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"error": str(exc)})

    def log_message(self, *args):  # keep the console quiet
        pass


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[dev] serving {ROOT} on http://127.0.0.1:{port}  (open /web/index.html)")
    print("[dev] POST /api/keywords triggers a SerpApi collection -- LOCAL DEV ONLY.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[dev] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
