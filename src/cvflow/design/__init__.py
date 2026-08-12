"""CVFlow's visual layer — the browser dashboard.

Everything the user *sees* in a browser lives here: the HTML shell, its styles,
its behavior (``design/assets``), the data contract that feeds them
(:mod:`~cvflow.design.payload`), and a small localhost server
(:mod:`~cvflow.design.server`).

The boundary is deliberate. Analysis produces :class:`~cvflow.model.Issue`
values; the design layer only *presents* them. It reads the model and never
writes to it, so the UI can be redesigned freely without touching a single
check — the same reason the text reporter lives apart in :mod:`cvflow.report`.
"""

from __future__ import annotations

from cvflow.design.dashboard import render_dashboard, render_payload
from cvflow.design.editor import Editor, EditorError
from cvflow.design.payload import build_payload
from cvflow.design.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DashboardServer,
    create_server,
    pick_port,
    serve_dashboard,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DashboardServer",
    "Editor",
    "EditorError",
    "build_payload",
    "create_server",
    "pick_port",
    "render_dashboard",
    "render_payload",
    "serve_dashboard",
]
