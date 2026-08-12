"""Render the dashboard as one self-contained HTML page.

The page shell, its styles, and its behavior live as plain assets next to this
module (``design/assets``) so the UI can be edited as a *design* artifact — no
Python quoting, no template engine, no build step. This module inlines those
assets and the JSON payload into a single file that works offline, over
``file://``, or from the local server.
"""

from __future__ import annotations

import base64
import json
from importlib.resources import files
from typing import Any

from cvflow.design.payload import build_payload
from cvflow.model import Dataset, DatasetStatistics, Issue

#: Asset directory, addressed through the package (not as a namespace package
#: of its own) so it resolves the same way on every supported Python.
_ASSETS = "assets"

#: Vendored, inlined so the page needs no network and no build step. See
#: ``assets/vendor/README.md`` for versions and licenses.
#: Archivo is the Ultralytics corporate typeface (ultralytics.com/brand) and
#: carries the whole UI; Geist Mono is kept for the monospaced role only —
#: paths, codes, and the tabular figures in stat values.
_FONTS = (
    ("Archivo", "Archivo-Variable.woff2"),
    ("Archivo", "Archivo-Variable-ext.woff2"),
    ("Geist Mono", "GeistMono-Variable.woff2"),
)
_CHART_JS = "chart.umd.min.js"


def _asset(name: str) -> str:
    return (files("cvflow.design") / _ASSETS / name).read_text(encoding="utf-8")


def _vendor_text(name: str) -> str:
    return (files("cvflow.design") / _ASSETS / "vendor" / name).read_text(encoding="utf-8")


def _font_face_rules() -> str:
    """``@font-face`` rules with the woff2 payloads embedded as data URIs."""
    rules = []
    for family, filename in _FONTS:
        blob = (files("cvflow.design") / _ASSETS / "vendor" / filename).read_bytes()
        encoded = base64.b64encode(blob).decode("ascii")
        rules.append(
            f'@font-face{{font-family:"{family}";'
            f"src:url(data:font/woff2;base64,{encoded}) format('woff2');"
            "font-weight:100 900;font-style:normal;font-display:swap}"
        )
    return "\n".join(rules)


def render_dashboard(
    dataset: Dataset,
    issues: list[Issue],
    *,
    stats: DatasetStatistics | None = None,
    version: str = "",
) -> str:
    """Render a complete, dependency-free HTML dashboard for one dataset."""
    payload = build_payload(dataset, issues, stats=stats, version=version)
    return render_payload(payload)


def render_payload(payload: dict[str, Any]) -> str:
    """Render an already-built payload. Useful for tests and reuse."""
    name = payload.get("dataset", {}).get("name", "dataset")
    page = _asset("dashboard.html")
    # Styles first: the font-face placeholder lives inside the stylesheet.
    page = page.replace("/*{{STYLES}}*/", _asset("dashboard.css"))
    page = page.replace("/*{{FONTS}}*/", _font_face_rules())
    page = page.replace("/*{{CHARTJS}}*/", _vendor_text(_CHART_JS))
    page = page.replace("/*{{SCRIPT}}*/", _asset("dashboard.js"))
    page = page.replace("{{DATA}}", _encode(payload))
    return page.replace("{{TITLE}}", _escape(f"{name} · CVFlow"))


def _encode(payload: dict[str, Any]) -> str:
    """Serialize the payload for embedding inside a ``<script>`` element.

    ``<`` is escaped so no string in the data can close the script tag early.
    """
    return json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
