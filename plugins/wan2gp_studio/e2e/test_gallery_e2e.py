"""Browser tests: gallery paging bounds, scroll-back refetch, uploads, filters.

The page-store memory bounds asserted here are the frontend half of the
1.3.4 scalability criterion: deep scrolling must not grow the in-memory
window or the DOM, and scrolled-back pages must come back on demand.
"""
import re


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
    assert debug["total"] == 2800
    assert debug["pages"] >= 1
    summary = page.text_content("#gallery-summary")
    assert "2800 items" in summary


def test_deep_scroll_keeps_window_and_dom_bounded(page):
    """Scroll to the far end: the page window must stay at the KEEP_PAGES
    bound and the rendered DOM must stay at the virtualization window, no
    matter how deep the library is."""
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
    before = _total(page)
    page.wait_for_function(
        f"() => window.WanGPStudioGallery.debug().total === {before + 1}", timeout=20000
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
