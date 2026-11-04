"""Статические проверки фронтенда Studio: JS-синтаксис, id-связность, ассеты."""
import json
import os
import re
import shutil
import subprocess

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
WEB = os.path.join(PLUGIN_DIR, "web")

HTML = os.path.join(WEB, "index.html")
ASSETS = os.path.join(WEB, "assets")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def test_index_references_only_existing_assets():
    html = _read(HTML)
    for match in re.findall(r'(?:src|href)="(assets/[^"]+|canvas\.html)"', html):
        assert os.path.isfile(os.path.join(WEB, match)), f"missing asset: {match}"


def test_every_js_id_exists_in_html():
    html = _read(HTML)
    canvas_html = _read(os.path.join(ASSETS, "canvas.html"))
    ids = set(re.findall(r'id="([^"]+)"', html)) | set(re.findall(r'id="([^"]+)"', canvas_html))
    missing = []
    for name in os.listdir(ASSETS):
        if not name.endswith(".js"):
            continue
        source = _read(os.path.join(ASSETS, name))
        for used in set(re.findall(r'\$\("([^"]+)"\)', source)):
            if used not in ids:
                missing.append(f"{name}: {used}")
    assert not missing, missing


def test_canvas_placeholders_are_present_for_host():
    canvas = _read(os.path.join(ASSETS, "canvas.html"))
    for placeholder in (
        "/* WORKFLOWS_V2_CSS */",
        "/* WORKFLOWS_V2_GRAPH */",
        "/* WORKFLOWS_V2_CATALOG */",
        "/* WORKFLOWS_V2_STATUS */",
        "/* WORKFLOWS_V2_JS */",
    ):
        assert placeholder in canvas


def test_js_files_pass_node_syntax_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")
    for name in sorted(os.listdir(ASSETS)):
        if not name.endswith(".js"):
            continue
        result = subprocess.run(
            [node, "--check", os.path.join(ASSETS, name)],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"{name}: {result.stderr[:400]}"


def test_catalog_shape_documented_in_workflow_host():
    host = _read(os.path.join(ASSETS, "workflow.js"))
    for token in ("api/workflow/catalog", "api/workflow/runs", "api/workflow/blocks"):
        assert token in host, f"workflow.js must reference {token}"


def test_studio_toolbar_requests_live_graph_from_canvas():
    host = _read(os.path.join(ASSETS, "workflow.js"))
    canvas = _read(os.path.join(ASSETS, "canvas.js"))
    assert "requestCanvasGraph" in host
    assert 'action: "get_graph"' in host
    assert "data.action==='get_graph'" in canvas
    assert "action:'graph'" in canvas


def test_canvas_accepts_host_media_additions():
    """Studio's second documented canvas patch: the host can push 'add_media'
    so the Gallery can drop media files into the workflow as input nodes."""
    host = _read(os.path.join(ASSETS, "workflow.js"))
    canvas = _read(os.path.join(ASSETS, "canvas.js"))
    assert "addMediaInput" in host
    assert "action==='add_media'" in canvas
    assert "addMediaNode" in canvas


def test_canvas_messages_are_origin_checked():
    host = _read(os.path.join(ASSETS, "workflow.js"))
    canvas = _read(os.path.join(ASSETS, "canvas.js"))
    assert "frameOriginAllowed" in host
    assert "event.origin" in host
    assert "event.source!==window.parent" in canvas


def test_version_strings_are_consistent():
    info = json.loads(_read(os.path.join(PLUGIN_DIR, "plugin_info.json")))
    html = _read(HTML)
    version = info["version"]
    assert f'WanGP Studio <b>{version}</b>' in html  # footer
    assert f'<span class="user-button">{version}</span>' in html  # topbar
