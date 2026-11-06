"""Browser tests: gallery paging bounds, scroll-back refetch, uploads, filters.

The page-store memory bounds asserted here are the frontend half of the
1.3.4 scalability criterion: deep scrolling must not grow the in-memory
window or the DOM, and scrolled-back pages must come back on demand.
"""
import json as _json
import re
import time
from pathlib import Path

import pytest


def _debug(page):
    return page.evaluate("window.WanGPStudioGallery.debug()")


def _total(page) -> int:
    return int(_debug(page)["total"])


def _scroll_to(page, y):
    """Scroll and force a synchronous layout+render: programmatic scrolling
    rides the rAF pipeline, which headless runners may not pump while the
    test is waiting. The resize handler renders directly."""
    page.evaluate(f"document.getElementById('gallery-viewport').scrollTop = {y}")
    page.evaluate("window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(150)


def test_gallery_loads_and_reports_corpus(page):
    debug = _debug(page)
    # the corpus is 2800 files; produced files from workflow-run tests may
    # accumulate in the same media roots, so only a floor is asserted
    assert debug["total"] >= 2800
    assert debug["pages"] >= 1
    summary = page.text_content("#gallery-summary")
    assert "items ·" in summary


def test_deep_scroll_keeps_window_and_dom_bounded(page):
    """Scroll to the far end: the page window must stay at the KEEP_PAGES
    bound and the rendered DOM must stay at the virtualization window, no
    matter how deep the library is."""
    # the far end of a date_desc grid holds the OLDEST file: resolve its name
    # from the API instead of assuming corpus file names
    origin = page.url.split("#")[0].rstrip("/") + "/"
    import json as _json
    import urllib.request

    with urllib.request.urlopen(origin + "api/media?sort=date_asc&offset=0&limit=1", timeout=15) as response:
        oldest_name = _json.loads(response.read())["items"][0]["name"]
    total_height = page.evaluate("document.getElementById('gallery-viewport').scrollHeight")
    _scroll_to(page, total_height)
    page.wait_for_function(
        "() => { const d = window.WanGPStudioGallery.debug(); return d.pages > 0 && d.fetching.length === 0; }",
        timeout=15000,
    )
    debug = _debug(page)
    # KEEP_PAGES=6 -> at most 13 pages in memory (viewport +- radius)
    assert debug["pages"] <= 13, debug
    assert debug["cards"] <= 120, debug  # DOM keeps only the virtualization window
    assert debug["domCards"] == debug["cards"]
    page.wait_for_selector(f'text={oldest_name}', timeout=15000)
    # the far end actually rendered: page count and deepest file name
    assert page.locator("#gallery-window .media-card:not(.skeleton)").count() > 0
    # the far end of a date_desc grid holds the OLDEST corpus file
    page.wait_for_selector("text=e2e-00000_seed0_prompt hint 0 batch.png", timeout=15000)


def test_scroll_back_refetches_evicted_pages(page):
    """After eviction, scrolling back to the top must refetch page 0 and
    render its files again. The gallery sorts date_desc, so the top of the
    grid holds the NEWEST corpus file (created last), not the first one."""
    total_height = page.evaluate("document.getElementById('gallery-viewport').scrollHeight")
    _scroll_to(page, total_height)
    page.wait_for_timeout(600)
    _scroll_to(page, 0)
    page.wait_for_selector("text=e2e-02799_seed2799_prompt hint 6 batch.png", timeout=15000)
    debug = _debug(page)
    assert debug["pages"] <= 13, debug


def test_upload_flow_with_progress_and_refresh(page, tmp_path):
    """Three files through the upload queue: per-file Done status, then the
    gallery refreshes and the total grows by three."""
    before = _total(page)
    for index in range(3):
        (tmp_path / f"upload-{index}.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"0" * 64
        )
    page.set_input_files("#gallery-file", [str(tmp_path / f"upload-{i}.png") for i in range(3)])
    page.wait_for_selector("#gallery-uploads:not([hidden])", timeout=10000)
    page.wait_for_function(
        "() => document.querySelectorAll('.upload-status.done').length === 3", timeout=30000
    )
    # the queue drained -> the gallery reloaded and counts the new files
    page.wait_for_function(
        f"() => window.WanGPStudioGallery.debug().total === {before + 3}", timeout=20000
    )


def test_kind_filter_and_search(page):
    # the corpus is all PNGs: the audio chip must yield the empty state
    page.click('#gallery-kinds [data-kind="audio"]')
    page.wait_for_function(
        "() => window.WanGPStudioGallery.debug().total === 0", timeout=15000
    )
    page.wait_for_selector("#gallery-empty:not([hidden])", timeout=10000)
    # search narrows to the 1-in-7 naming bucket
    page.click('#gallery-kinds [data-kind=""]')
    page.fill("#gallery-query", "prompt hint 3")
    page.wait_for_function(
        "() => window.WanGPStudioGallery.debug().total === 400", timeout=15000
    )
    summary = page.text_content("#gallery-summary")
    assert re.search(r"400 items", summary)


def test_long_session_soak(page, tmp_path_factory):
    """Stage-E soak: repeated deep scrolls, filter resets and an upload must
    leave the bounded stores bounded - no growth creep over a long session."""
    # Earlier tests may leave an active search filter and may have uploaded
    # files: clear the filter FIRST, let the unfiltered total settle, and only
    # then capture the base every later wait is relative to.
    page.fill("#gallery-query", "")
    page.wait_for_function(
        "() => { const d = window.WanGPStudioGallery.debug(); return d.fetching.length === 0 && d.pages > 0; }",
        timeout=30000,
    )
    page.wait_for_timeout(500)
    base = _total(page)
    total_height = page.evaluate("document.getElementById('gallery-viewport').scrollHeight")
    for cycle in range(4):
        _scroll_to(page, total_height)
        page.wait_for_timeout(400)
        _scroll_to(page, 0)
        page.wait_for_timeout(200)
    page.click("#gallery-refresh")  # full reset cycle
    page.wait_for_selector(".media-card:not(.skeleton)", timeout=20000)
    page.fill("#gallery-query", "prompt hint 3")
    page.wait_for_function(
        "() => window.WanGPStudioGallery.debug().total === 400", timeout=30000
    )
    page.fill("#gallery-query", "")
    page.wait_for_function(
        f"() => window.WanGPStudioGallery.debug().total === {base}", timeout=30000
    )
    from PIL import Image

    import io as _io
    buffer = _io.BytesIO()
    Image.new("RGB", (8, 8), (90, 140, 220)).save(buffer, format="PNG")
    upload_file = tmp_path_factory.mktemp("soak") / "soak-upload.png"
    upload_file.write_bytes(buffer.getvalue())
    page.set_input_files("#gallery-file", [str(upload_file)])
    # wait on base+1: reading the total after set_input_files races the XHR
    page.wait_for_function(
        f"() => window.WanGPStudioGallery.debug().total === {base + 1}", timeout=30000
    )
    assert _total(page) == base + 1  # the soak upload landed exactly once
    debug = _debug(page)
    heap = page.evaluate(
        "performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1e6) : -1"
    )
    print(f"\nsoak end: {debug}, JS heap ~{heap} MB")
    assert debug["pages"] <= 13, debug
    assert debug["cards"] <= 120, debug
    assert debug["domCards"] == debug["cards"]


def test_empty_upload_panel_is_hidden(page):
    """Live acceptance found the empty uploads panel visible: the panel's
    display:grid overrode the hidden attribute. This pins the fix."""
    panel = page.locator("#gallery-uploads")
    assert panel.count() == 1
    assert not panel.is_visible()


def test_use_in_workflow_adds_input_node(page):
    """1.4.0 flagship: a gallery file lands on the workflow canvas as an
    input node with an explicit path, ready to run through the native queue."""
    # click a card whose file exists on disk: the newest entry per the API,
    # since the first rendered card may be a stale entry for a file a previous
    # test deleted from the media root
    origin = page.url.split("#")[0].rstrip("/") + "/"
    import urllib.request

    with urllib.request.urlopen(origin + "api/media?sort=date_desc&offset=0&limit=1", timeout=15) as response:
        target_name = _json.loads(response.read())["items"][0]["name"]
    card = page.locator("#gallery-window .media-card", has_text=target_name)
    card.first.wait_for(state="attached", timeout=15000)
    card.first.dispatch_event("click")
    page.wait_for_selector("#lightbox[open]", timeout=10000)
    # renderLightbox() runs after the detail fetch: wait for the button to
    # become visible rather than racing it.
    page.wait_for_selector("#lightbox-usewf:not([hidden])", timeout=15000)
    page.click("#lightbox-usewf")
    # the workflow view is the canvas mode: hash + active nav, no section
    page.wait_for_function(
        "() => location.hash === '#workflow'"
        " && document.getElementById('nav-workflow').classList.contains('active')", timeout=10000
    )
    page.wait_for_selector("#workflow-frame", timeout=20000)
    # pending-media flush + graph handshake: the canvas iframe installs its
    # listeners asynchronously, so poll from Python (IAB wait_for_function
    # treats a promise-returning predicate as immediately truthy)
    graph = None
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            graph = page.evaluate(
                "window.WanGPStudioCanvas.getGraph().then((graph) => ({"
                " types: graph.nodes.map((node) => node.type),"
                " paths: graph.nodes.map((node) => (node.params || {}).path || null) }))"
            )
            if "input_image" in graph["types"]:
                break
        except Exception:
            pass
        time.sleep(0.5)
    assert graph is not None and "input_image" in graph["types"]
    assert any(path and "/e2e-" in path.replace("\\", "/") for path in graph["paths"])


def test_run_to_gallery_to_open_workflow_chain(page, tmp_path):
    """The full 1.4.x chain: a real workflow run (input_video + ffmpeg_trim)
    produces a file in the workflow_outputs root, the Gallery indexes it with
    the run reference, and 'Open workflow' restores the graph on the canvas."""
    import json as _json
    import shutil
    import subprocess as _sp
    import time as _time
    import urllib.request

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is not available")

    origin = page.url.split("#")[0].rstrip("/") + "/"

    def _api(path):
        with urllib.request.urlopen(origin + path, timeout=15) as response:
            return _json.loads(response.read())

    work = tmp_path / "chain"
    work.mkdir()
    video = work / "clip.mp4"
    _sp.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=8",
         "-pix_fmt", "yuv420p", str(video)],
        check=True, capture_output=True, timeout=60,
    )
    graph = {
        "name": "E2E chain",
        "nodes": [
            {"id": "n1", "type": "input_video", "params": {"path": str(video)}, "enabled": True},
            {"id": "n2", "type": "ffmpeg_trim", "params": {"start": 0, "duration": 0.5}, "enabled": True},
        ],
        "edges": [{"source": {"node": "n1", "port": "video"}, "target": {"node": "n2", "port": "video"}}],
    }
    request = urllib.request.Request(
        origin + "api/workflow/runs", data=_json.dumps({"graph": graph, "inputs": []}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        run_id = _json.loads(response.read())["run_id"]

    deadline = _time.time() + 45
    record = {"status": "running"}
    while _time.time() < deadline:
        record = _api("api/workflow/runs/" + run_id)
        if record["status"] != "running":
            break
        _time.sleep(0.5)
    assert record["status"] == "completed", record
    produced = [item for item in record["outputs"] if "workflow_outputs" in item]
    assert produced, record["outputs"]
    produced_name = Path(produced[0]).name

    # the Gallery must show the produced file with the run reference
    page.evaluate("window.WanGPStudio.setView('gallery')")
    # the media index refreshes in the background (min interval + scan thread);
    # force a full rescan and wait until the produced file is in the store
    page.evaluate(
        "async () => { await fetch('api/media/roots?force=1'); window.WanGPStudioGallery.reload(); }"
    )
    page.wait_for_function(
        "(name) => { const cards = document.querySelectorAll('#gallery-window .media-card');"
        " for (const card of cards) { if (card.textContent.includes(name)) return true; } return false; }",
        arg=produced_name, timeout=30000
    )
    card = page.locator("#gallery-window .media-card", has_text=produced_name)
    assert card.count() >= 1, f"produced file {produced_name} not in the gallery"
    page.evaluate(
        """(name) => {
            const cards = document.querySelectorAll('#gallery-window .media-card');
            for (const card of cards) {
                if (card.textContent.includes(name)) {
                    card.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    break;
                }
            }
        }""",
        produced_name,
    )
    page.wait_for_selector("#lightbox[open]", timeout=10000)
    page.wait_for_function(
        "() => { const f = document.getElementById('lightbox-facts'); return f && f.textContent.includes('E2E chain'); }",
        timeout=10000,
    )
    open_button = page.locator("#lightbox-openwf")
    assert open_button.is_visible()
    open_button.click()
    page.wait_for_function(
        "() => location.hash === '#workflow'"
        " && document.getElementById('nav-workflow').classList.contains('active')", timeout=10000
    )
    graph_types = None
    deadline = _time.time() + 30
    while _time.time() < deadline:
        try:
            graph_types = page.evaluate(
                "window.WanGPStudioCanvas.getGraph().then((graph) => graph ? graph.nodes.map((node) => node.type) : null)"
            )
            if graph_types and "input_video" in graph_types:
                break
        except Exception:
            pass
        _time.sleep(0.5)
    assert graph_types and "input_video" in graph_types and "ffmpeg_trim" in graph_types
    # the produced file lives in the repo's workflow_outputs root: clean up so
    # repeated e2e sessions do not accumulate gallery entries
    for item in produced:
        Path(item).unlink(missing_ok=True)
        Path(item).with_suffix(".json").unlink(missing_ok=True)

