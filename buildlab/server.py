"""A local-only HTTP server for the build UI.

Binds 127.0.0.1 and nothing else. The engine's data is loaded once and held for
the life of the process, so after re-running tools/vendor.py you must restart
the server — /api/health reports which commit is being served.
"""

import http.server
import json
import pathlib

from buildlab import api, sources

UI = sources.ROOT / "ui"

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "buildlab"

    def log_message(self, format, *args):
        """Quiet by default; the test suite should not print a request log."""

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status, payload):
        self._send(
            status,
            json.dumps(payload).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        if self.path == "/api/health":
            problems = sources.verify_all()
            self._send_json(
                200,
                {
                    "commit": sources.load()["sources"][0]["commit"],
                    "hashes_ok": not problems,
                    "problems": problems,
                },
            )
            return
        if self.path == "/api/meta":
            self._send_json(200, api.meta())
            return
        if self.path in STATIC:
            name, content_type = STATIC[self.path]
            path = UI / name
            if not path.exists():
                self._send_json(404, {"error": f"missing {name}"})
                return
            self._send(200, path.read_bytes(), content_type)
            return
        self._send_json(404, {"error": f"no such path {self.path}"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as error:
            self._send_json(400, {"error": f"invalid JSON: {error}"})
            return

        try:
            if self.path == "/api/evaluate":
                result = api.evaluate(payload["values"], int(payload["height"]))
            elif self.path == "/api/ladder":
                result = api.ladder(payload["attribute"], int(payload["height"]))
            else:
                self._send_json(404, {"error": f"no such path {self.path}"})
                return
        except (ValueError, KeyError) as error:
            self._send_json(400, {"error": str(error).strip("'")})
            return

        self._send_json(200, result)


def build(port=8765):
    """An HTTP server bound to localhost. Pass port=0 for an ephemeral one."""
    return http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)


def warm():
    """Precompute the slow lookups so the first slider drag is not sluggish."""
    api.meta()
    api.evaluate([25] * 21, 75)
