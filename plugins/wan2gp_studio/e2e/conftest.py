"""Browser (Playwright) tests for the Studio frontend.

This is a separate harness on purpose: it drives a REAL uvicorn server with
headless Chromium instead of TestClient, so layout, virtualization, uploads
and the page-store memory bounds are exercised the way a browser sees them.

Run with the repo venv:

    env_uv/Scripts/python.exe -m playwright install chromium
    env_uv/Scripts/python.exe -m pytest plugins/wan2gp_studio/e2e -q

Everything here skips when playwright or its browser is not installed; the
`Studio E2E` workflow installs both. SendTo and workflow execution need the
live WanGP host (Gradio bridge) - those belong to the manual production
acceptance pass, not to this harness.
"""
import importlib
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
for _path in (PLUGINS_ROOT, REPO_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

CORPUS_FILES = 2800  # 14 pages of 200: larger than the KEEP_PAGES window


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def server_url(tmp_path_factory):
    from fastapi import FastAPI  # noqa: F401 - ensures fastapi is present early

    import uvicorn

    from wan2gp_studio.plugin import WanGPStudioPlugin

    root = tmp_path_factory.mktemp("e2e-media")
    (root / "images").mkdir()
    for index in range(CORPUS_FILES):
        name = f"e2e-{index:05d}_seed{index}_prompt hint {index % 7} batch.png"
        (root / "images" / name).write_bytes(b"0")
    plugin = WanGPStudioPlugin()
    plugin.server_config = {
        "image_save_path": str(root / "images"),
        "save_path": str(root / "videos"),
        "audio_save_path": str(root / "audio"),
    }
    app = plugin.create_web_app()
    # The Studio app warms the thumbnail engine in a background thread, but
    # this harness opens the gallery within seconds - before that import
    # (about 20 s cold) finishes, its import lock would stall the first
    # thumbnail volley and starve the browser's connection pool. Warm it
    # synchronously so the tests exercise steady state.
    importlib.import_module("shared.deepy.thumbnails")
    config = uvicorn.Config(app, host="127.0.0.1", port=_free_port(), log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    assert server.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture()
def page(browser, server_url):
    browser_page = browser.new_page(viewport={"width": 1440, "height": 900})
    browser_page.goto(server_url + "/#gallery")
    browser_page.wait_for_selector("#gallery-view:not([hidden])", timeout=15000)
    browser_page.wait_for_selector(".media-card:not(.skeleton)", timeout=20000)
    yield browser_page
    browser_page.close()
