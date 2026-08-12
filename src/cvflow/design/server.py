"""A tiny localhost server for the dashboard.

Standard library only. The rendered page is held in memory and served at ``/``.
When an :class:`~cvflow.design.editor.Editor` is attached, three JSON endpoints
are added so the page can open an image and correct its boxes:

``GET  /api/editor``       what the browser may offer (writable? which classes?)
``GET  /api/image``        the image bytes for one dataset image
``GET  /api/annotations``  that image's boxes
``POST /api/annotations``  write edited boxes back to disk

Everything else 404s. The editor confines every path to the dataset root, so
there is no directory listing and no arbitrary file read. Bound to loopback by
default.
"""

from __future__ import annotations

import json
import socket
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from cvflow.design.editor import Editor, EditorError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

#: How many ports to try after ``DEFAULT_PORT`` before giving up on a free one.
_PORT_SCAN = 25

#: Refuse absurd payloads outright rather than buffering them.
_MAX_BODY = 4 * 1024 * 1024


class DashboardServer(ThreadingHTTPServer):
    """An HTTP server that serves a single in-memory HTML page (plus the API)."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], html: str, editor: Editor | None = None) -> None:
        self.page = html.encode("utf-8")
        self.editor = editor
        super().__init__(address, _Handler)

    @property
    def url(self) -> str:
        host, port = self.server_address[0], self.server_address[1]
        display = "localhost" if host in {"0.0.0.0", "127.0.0.1", "::"} else str(host)
        return f"http://{display}:{port}"


class _Handler(BaseHTTPRequestHandler):
    server_version = "CVFlow"
    protocol_version = "HTTP/1.1"

    # -- plumbing ---------------------------------------------------------- #

    @property
    def _server(self) -> DashboardServer:
        return cast(DashboardServer, self.server)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _not_found(self) -> None:
        self._send(404, b"", "text/plain; charset=utf-8")

    def log_message(self, format: str, *args: object) -> None:
        """Silence per-request logging; the CLI prints what matters."""

    # -- routes ------------------------------------------------------------ #

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in {"/", "/index.html"}:
            self._send(200, self._server.page, "text/html; charset=utf-8")
            return

        editor = self._server.editor
        if path == "/api/editor":
            self._json(200, editor.info() if editor else {"enabled": False})
            return

        if path in {"/api/image", "/api/annotations"}:
            if editor is None:
                self._json(404, {"error": "editing is not available for this dataset"})
                return
            target = (query.get("path") or [""])[0]
            try:
                if path == "/api/image":
                    body, content_type = editor.image_bytes(target)
                    self._send(200, body, content_type)
                else:
                    self._json(200, editor.annotations(target))
            except EditorError as exc:
                self._json(400, {"error": str(exc)})
            except OSError as exc:
                self._json(500, {"error": f"could not read the file: {exc}"})
            return

        self._not_found()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/annotations":
            self._not_found()
            return

        editor = self._server.editor
        if editor is None:
            self._json(404, {"error": "editing is not available for this dataset"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > _MAX_BODY:
            self._json(400, {"error": "missing or oversized request body"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            written = editor.save(str(payload["path"]), list(payload["boxes"]))
        except (KeyError, TypeError, ValueError) as exc:
            self._json(400, {"error": f"malformed request: {exc}"})
        except EditorError as exc:
            self._json(400, {"error": str(exc)})
        except OSError as exc:
            self._json(500, {"error": f"could not write the label file: {exc}"})
        else:
            self._json(200, {"ok": True, "written": written})


def _echo(message: str) -> None:
    """Print immediately — the URL must appear even when stdout is a pipe."""
    print(message, flush=True)


def is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def pick_port(host: str, start: int = DEFAULT_PORT, attempts: int = _PORT_SCAN) -> int:
    """First free port at or after ``start``; ``0`` (let the OS choose) if none."""
    for port in range(start, start + attempts):
        if is_port_free(host, port):
            return port
    return 0


def create_server(
    html: str,
    *,
    host: str = DEFAULT_HOST,
    port: int = 0,
    editor: Editor | None = None,
) -> DashboardServer:
    """Bind a dashboard server without serving it yet (used by tests)."""
    return DashboardServer((host, port), html, editor)


def serve_dashboard(
    html: str,
    *,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    open_browser: bool = True,
    editor: Editor | None = None,
    echo: Callable[[str], None] = _echo,
) -> None:
    """Serve the dashboard until interrupted.

    Args:
        html: The rendered page.
        host: Interface to bind. Loopback by default.
        port: Port to bind. ``None`` picks the first free port from 8000.
        open_browser: Open the URL in the default browser once bound.
        editor: Enables the image/annotation endpoints when given.
        echo: Where to write the status lines.
    """
    chosen = pick_port(host) if port is None else port
    server = create_server(html, host=host, port=chosen, editor=editor)
    echo(f"Open {server.url} for the detail: every finding, its image, and the fix.")
    if open_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
