"""Tests for the design layer: payload, HTML rendering, and the local server."""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from cvflow.analysis import AnalysisEngine, CheckConfig, compute_statistics, default_checks
from cvflow.design import (
    Editor,
    EditorError,
    build_payload,
    create_server,
    render_dashboard,
    render_payload,
)
from cvflow.design.server import DashboardServer, pick_port
from cvflow.loaders import load_dataset
from cvflow.model import BoundingBox, Dataset, ImageItem, Issue, Severity

_DATA_BLOCK = re.compile(
    r'<script id="cvflow-data" type="application/json">(.*?)</script>', re.DOTALL
)


def _analyze(path: Path) -> tuple[Dataset, list[Issue]]:
    dataset = load_dataset(path)
    engine = AnalysisEngine(default_checks(CheckConfig()))
    return dataset, engine.run(dataset)


# --------------------------------------------------------------------------- #
# Payload
# --------------------------------------------------------------------------- #


def test_payload_describes_the_dataset(clean_dataset: Path) -> None:
    dataset, issues = _analyze(clean_dataset)
    payload = build_payload(dataset, issues, stats=compute_statistics(dataset), version="9.9.9")

    assert payload["version"] == "9.9.9"
    assert payload["dataset"]["format"] == "YOLO"
    assert payload["dataset"]["images"] == 2
    assert payload["dataset"]["splits"] == ["train"]
    assert payload["dataset"]["emptyImages"] == 1
    assert payload["stats"]["emptyImages"] == 1
    assert payload["issuesTotal"] == len(issues)
    assert payload["issuesTruncated"] == 0


def test_payload_severity_counts_and_types(integrity_dataset: Path) -> None:
    dataset, issues = _analyze(integrity_dataset)
    payload = build_payload(dataset, issues)

    counts = payload["severityCounts"]
    assert set(counts) == {"ERROR", "WARNING", "INFO"}
    assert sum(counts.values()) == len(issues)

    types = payload["issueTypes"]
    assert sum(entry["count"] for entry in types) == len(issues)
    # Most severe first, then most frequent.
    ranks = ["ERROR", "WARNING", "INFO"]
    positions = [ranks.index(entry["severity"]) for entry in types]
    assert positions == sorted(positions)


def test_payload_class_distribution_is_ranked(clean_dataset: Path) -> None:
    dataset, issues = _analyze(clean_dataset)
    classes = build_payload(dataset, issues)["classes"]

    assert classes[0]["name"] == "cat"
    assert classes[0]["annotations"] == 1
    assert classes[0]["images"] == 1
    assert classes[0]["share"] == pytest.approx(1.0)


def test_payload_class_distribution_survives_no_stats(coco_dir_dataset: Path) -> None:
    dataset, issues = _analyze(coco_dir_dataset)
    payload = build_payload(dataset, issues, stats=None)

    assert payload["stats"] is None
    assert [entry["name"] for entry in payload["classes"]] == ["person", "car"]
    assert payload["splits"] == [{"name": "train", "images": 2, "annotations": 3}]


def test_payload_histograms(coco_dir_dataset: Path) -> None:
    dataset, issues = _analyze(coco_dir_dataset)
    payload = build_payload(dataset, issues)

    objects = payload["objectsPerImage"]
    assert [entry["label"] for entry in objects] == ["0", "1", "2"]
    assert sum(entry["count"] for entry in objects) == dataset.num_images

    areas = payload["boxAreas"]
    assert sum(entry["count"] for entry in areas) == dataset.num_annotations
    assert areas[-1]["label"] == ">50"  # short axis label
    assert areas[-1]["range"] == ">50%"  # full range for tooltip/table
    assert areas[-1]["count"] == 1  # the full-frame COCO box


def test_payload_box_shapes(coco_dir_dataset: Path) -> None:
    dataset, issues = _analyze(coco_dir_dataset)
    shapes = build_payload(dataset, issues)["boxShapes"]

    # COCO records image dimensions, so the true pixel aspect is available.
    assert shapes["basis"] == "pixels"
    assert sum(entry["count"] for entry in shapes["bins"]) == dataset.num_annotations
    assert shapes["bins"][0]["label"] == "<0.25"


def test_payload_box_shapes_fall_back_to_frame(clean_dataset: Path) -> None:
    dataset, issues = _analyze(clean_dataset)
    shapes = build_payload(dataset, issues)["boxShapes"]

    # YOLO labels carry no image dimensions; the basis is reported, not faked.
    assert shapes["basis"] == "frame"


def test_payload_center_heatmap(clean_dataset: Path) -> None:
    dataset, issues = _analyze(clean_dataset)
    heat = build_payload(dataset, issues)["boxCenters"]

    assert heat["grid"] == 12
    assert len(heat["cells"]) == 12 * 12
    assert sum(heat["cells"]) == heat["total"] == dataset.num_annotations
    # The single box is centered at (0.5, 0.5) -> the middle cell.
    assert heat["cells"][6 * 12 + 6] == 1
    assert heat["max"] == 1


def test_payload_class_coverage(coco_dir_dataset: Path) -> None:
    dataset, issues = _analyze(coco_dir_dataset)
    # Only two classes here, so the curve is suppressed as uninformative.
    assert build_payload(dataset, issues)["classCoverage"] is None


def test_payload_class_coverage_is_cumulative() -> None:
    dataset = Dataset(name="synthetic", root=".", format="yolo")
    dataset.class_names = {0: "a", 1: "b", 2: "c", 3: "d"}
    for class_id, count in ((0, 6), (1, 2), (2, 1), (3, 1)):
        for _ in range(count):
            dataset.images.append(
                ImageItem(path=f"{class_id}.jpg", boxes=[BoundingBox(class_id, 0.1, 0.1, 0.2, 0.2)])
            )
    coverage = build_payload(dataset, [])["classCoverage"]

    shares = [point["share"] for point in coverage["points"]]
    assert shares == sorted(shares)  # cumulative, so never decreasing
    assert shares[-1] == pytest.approx(1.0)
    assert coverage["milestones"]["50"] == 1  # one class already covers 60%
    assert coverage["classes"] == 4


def test_payload_top_images(integrity_dataset: Path) -> None:
    dataset, issues = _analyze(integrity_dataset)
    rows = build_payload(dataset, issues)["topImages"]

    assert rows, "integrity_dataset should produce image-level findings"
    totals = [row["total"] for row in rows]
    assert totals == sorted(totals, reverse=True)
    assert len(rows) <= 10
    for row in rows:
        assert row["total"] == sum(row["counts"].values())
        assert row["name"] == row["path"].replace("\\", "/").rsplit("/", 1)[-1]


def test_payload_impact_is_ranked_and_capped(integrity_dataset: Path) -> None:
    dataset, issues = _analyze(integrity_dataset)
    impact = build_payload(dataset, issues)["impact"]

    assert impact["items"], "findings should produce impact estimates"
    gains = [item["gain"] for item in impact["items"]]
    assert gains == sorted(gains, reverse=True)
    for item in impact["items"]:
        assert 0 <= item["share"] <= 1
        assert item["scale"] in {"images", "annotations"}
        assert item["gain"] == pytest.approx(item["weight"] * item["share"] ** 0.5, abs=0.01)
    # Diminishing returns: the total never exceeds the cap, nor the naive sum.
    assert 0 < impact["total"] <= impact["cap"]
    assert impact["total"] <= sum(gains) + 0.05


def test_payload_impact_is_empty_without_findings(clean_dataset: Path) -> None:
    dataset, _ = _analyze(clean_dataset)
    impact = build_payload(dataset, [])["impact"]

    assert impact["items"] == []
    assert impact["total"] == 0


def test_payload_impact_weights_known_codes_higher(integrity_dataset: Path) -> None:
    dataset, issues = _analyze(integrity_dataset)
    impact = build_payload(dataset, issues)["impact"]
    weights = {item["code"]: item["weight"] for item in impact["items"]}

    # A corrupt image costs more than a background image, whatever the counts.
    assert weights["corrupt-image"] > weights["empty-image"]


def test_payload_truncates_findings(clean_dataset: Path) -> None:
    dataset, issues = _analyze(clean_dataset)
    payload = build_payload(dataset, issues * 5, max_issues=3)

    assert len(payload["issues"]) == 3
    assert payload["issuesTotal"] == len(issues) * 5
    assert payload["issuesTruncated"] == len(issues) * 5 - 3


def test_payload_evidence_is_json_safe(clean_dataset: Path) -> None:
    dataset, _ = _analyze(clean_dataset)
    issue = Issue(
        code="synthetic",
        severity=Severity.INFO,
        message="synthetic finding",
        evidence={"path": Path("a/b.png"), "pairs": (1, 2), "ratio": 0.5},
    )
    payload = build_payload(dataset, [issue])
    evidence = payload["issues"][0]["evidence"]

    assert evidence["pairs"] == [1, 2]
    assert evidence["ratio"] == 0.5
    assert isinstance(evidence["path"], str)
    json.dumps(payload)  # must not raise


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #


def test_render_dashboard_is_self_contained(integrity_dataset: Path) -> None:
    dataset, issues = _analyze(integrity_dataset)
    html = render_dashboard(dataset, issues, stats=compute_statistics(dataset), version="1.2.3")

    assert html.startswith("<!doctype html>")
    assert "{{DATA}}" not in html and "{{TITLE}}" not in html
    assert "/*{{STYLES}}*/" not in html and "/*{{SCRIPT}}*/" not in html
    assert "--sev-error" in html  # styles inlined
    assert "renderFindings" in html  # script inlined
    assert "Chart.js" in html  # charting library inlined
    assert "data:font/woff2;base64," in html  # fonts inlined
    # Nothing is fetched at runtime: no remote resource references anywhere.
    # (URLs do appear in the vendored library's license banner and in the SVG
    # namespace of the inline favicon — neither is a request.)
    for pattern in ('src="http', "src='http", 'href="http', "href='http", "url(http", "@import"):
        assert pattern not in html, f"external resource reference: {pattern}"


def test_render_dashboard_embeds_parsable_payload(integrity_dataset: Path) -> None:
    dataset, issues = _analyze(integrity_dataset)
    html = render_dashboard(dataset, issues)

    match = _DATA_BLOCK.search(html)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["issuesTotal"] == len(issues)
    assert payload["dataset"]["name"] == dataset.name


def test_render_escapes_markup_in_data() -> None:
    payload = {
        "dataset": {"name": "</script><img src=x>", "root": "", "format": "YOLO", "splits": []},
        "issues": [],
    }
    html = render_payload(payload)

    assert "</script><img" not in html
    assert "\\u003c/script>" in html
    assert "&lt;/script&gt;" in html  # the <title> copy is entity-escaped
    match = _DATA_BLOCK.search(html)
    assert match is not None
    assert json.loads(match.group(1))["dataset"]["name"] == "</script><img src=x>"


# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Editor
# --------------------------------------------------------------------------- #


def test_editor_reads_boxes_and_image(clean_dataset: Path) -> None:
    dataset = load_dataset(clean_dataset)
    editor = Editor(dataset)

    assert editor.info() == {
        "enabled": True,
        "writable": True,
        "format": "yolo",
        "task": "detect",
        "classes": {"0": "cat"},
    }
    labeled = next(item for item in dataset.images if item.boxes)
    payload = editor.annotations(labeled.path)
    assert payload["writable"] is True
    assert len(payload["boxes"]) == 1
    assert payload["boxes"][0]["class_id"] == 0

    body, content_type = editor.image_bytes(labeled.path)
    assert body[:4] == b"\x89PNG"
    assert content_type == "image/png"


def test_editor_writes_yolo_labels(clean_dataset: Path) -> None:
    dataset = load_dataset(clean_dataset)
    editor = Editor(dataset)
    labeled = next(item for item in dataset.images if item.boxes)

    written = editor.save(
        labeled.path,
        [
            {"class_id": 0, "x_min": 0.1, "y_min": 0.2, "x_max": 0.3, "y_max": 0.6},
            {"class_id": 0, "x_min": 0.5, "y_min": 0.5, "x_max": 0.9, "y_max": 0.9},
        ],
    )

    label_file = clean_dataset / written
    lines = label_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    class_id, cx, cy, w, h = lines[0].split()
    assert class_id == "0"
    assert float(cx) == pytest.approx(0.2)
    assert float(cy) == pytest.approx(0.4)
    assert float(w) == pytest.approx(0.2)
    assert float(h) == pytest.approx(0.4)
    # The in-memory dataset follows what is now on disk.
    assert len(labeled.boxes) == 2

    # And the loader reads back exactly what was written.
    assert len(next(i for i in load_dataset(clean_dataset).images if i.boxes).boxes) == 2


def test_editor_clamps_and_orders_boxes(clean_dataset: Path) -> None:
    dataset = load_dataset(clean_dataset)
    editor = Editor(dataset)
    labeled = next(item for item in dataset.images if item.boxes)

    # Dragged past the edge and backwards; saved as a valid in-frame box.
    editor.save(
        labeled.path, [{"class_id": 0, "x_min": 0.9, "y_min": 1.4, "x_max": 0.4, "y_max": -0.2}]
    )
    box = labeled.boxes[0]
    assert box.x_min == pytest.approx(0.4)
    assert box.x_max == pytest.approx(0.9)
    assert box.y_min == pytest.approx(0.0)
    assert box.y_max == pytest.approx(1.0)


def test_editor_rejects_unknown_and_degenerate(clean_dataset: Path) -> None:
    dataset = load_dataset(clean_dataset)
    editor = Editor(dataset)
    labeled = next(item for item in dataset.images if item.boxes)

    with pytest.raises(EditorError, match="not part of this dataset"):
        editor.annotations("../../etc/passwd")
    with pytest.raises(EditorError, match="zero width or height"):
        editor.save(
            labeled.path, [{"class_id": 0, "x_min": 0.5, "y_min": 0.5, "x_max": 0.5, "y_max": 0.9}]
        )
    with pytest.raises(EditorError, match="malformed box"):
        editor.save(labeled.path, [{"class_id": 0, "x_min": "left"}])


def test_editor_is_read_only_for_coco(coco_dir_dataset: Path) -> None:
    dataset = load_dataset(coco_dir_dataset)
    editor = Editor(dataset)

    assert editor.writable is False
    assert editor.info()["writable"] is False
    with pytest.raises(EditorError, match="read-only"):
        editor.save(dataset.images[0].path, [])


def test_editor_endpoints_over_http(clean_dataset: Path) -> None:
    dataset = load_dataset(clean_dataset)
    labeled = next(item for item in dataset.images if item.boxes)
    server = create_server(
        "<!doctype html><p>x</p>", host="127.0.0.1", port=0, editor=Editor(dataset)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(server.url + "/api/editor", timeout=5) as response:
            assert json.loads(response.read())["writable"] is True

        query = urllib.parse.urlencode({"path": labeled.path})
        with urllib.request.urlopen(
            server.url + "/api/annotations?" + query, timeout=5
        ) as response:
            assert len(json.loads(response.read())["boxes"]) == 1

        body = json.dumps(
            {
                "path": labeled.path,
                "boxes": [{"class_id": 0, "x_min": 0.2, "y_min": 0.2, "x_max": 0.4, "y_max": 0.4}],
            }
        ).encode()
        request = urllib.request.Request(
            server.url + "/api/annotations", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert json.loads(response.read())["ok"] is True
        assert len(labeled.boxes) == 1

        # A path outside the dataset is refused, not served.
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(server.url + "/api/image?path=/etc/passwd", timeout=5)
        assert exc.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_editor_endpoints_absent_without_editor(running_server: DashboardServer) -> None:
    with urllib.request.urlopen(running_server.url + "/api/editor", timeout=5) as response:
        assert json.loads(response.read()) == {"enabled": False}


@pytest.fixture
def running_server() -> Iterator[DashboardServer]:
    server = create_server("<!doctype html><p>hello cvflow</p>", host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_server_serves_the_page(running_server: DashboardServer) -> None:
    with urllib.request.urlopen(running_server.url + "/", timeout=5) as response:
        assert response.status == 200
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"hello cvflow" in response.read()


def test_server_404s_everything_else(running_server: DashboardServer) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(running_server.url + "/../etc/passwd", timeout=5)
    assert exc.value.code == 404


def test_server_url_is_loopback(running_server: DashboardServer) -> None:
    assert running_server.url.startswith("http://localhost:")


def test_pick_port_returns_a_bindable_port() -> None:
    port = pick_port("127.0.0.1")
    assert port == 0 or 8000 <= port < 8025


def test_payload_lists_the_images_a_finding_covers(integrity_dataset: Path) -> None:
    """Every finding can be looked at, not just read.

    Box-level findings name one file; aggregated ones carry their files in
    evidence; class-level ones resolve back to the images holding that class.
    """
    dataset, issues = _analyze(integrity_dataset)
    payload = build_payload(dataset, issues)
    by_code = {issue["code"]: issue for issue in payload["issues"]}

    # Image-level: the one file it points at.
    corrupt = by_code["corrupt-image"]
    assert corrupt["images"] == [corrupt["path"]]

    # Aggregated over several files, with no single location: still openable.
    duplicate = by_code["duplicate-filename"]
    assert duplicate["path"] is None
    assert len(duplicate["images"]) > 1
    assert all(image.endswith((".png", ".jpg")) for image in duplicate["images"])


def test_payload_resolves_class_level_findings_to_images() -> None:
    dataset = Dataset(name="d", root=".", format="yolo")
    dataset.class_names = {0: "cat", 1: "rare"}
    dataset.images.append(ImageItem(path="a.jpg", boxes=[BoundingBox(0, 0.1, 0.1, 0.2, 0.2)]))
    dataset.images.append(ImageItem(path="b.jpg", boxes=[BoundingBox(1, 0.1, 0.1, 0.2, 0.2)]))
    issue = Issue(
        code="rare-class",
        severity=Severity.INFO,
        message="Class 'rare' represents only 1% of annotations.",
        evidence={"class_id": 1, "count": 1},
    )

    images = build_payload(dataset, [issue])["issues"][0]["images"]

    assert images == ["b.jpg"]
