"""Roadmap v3 M1 acceptance benchmark: 10k files, first screen under 2 s.

Writes thousands of small files, so it is skipped by default. Run it with:

    STUDIO_MEDIA_BENCH=1 env_uv/Scripts/python.exe -m pytest plugins/wan2gp_studio/tests/test_media_index_perf.py -q -s
"""
import os
import sys
import time

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from wan2gp_studio.media_index import MediaIndex  # noqa: E402

TOTAL_FILES = 10_000
SUBDIRS = 10
FIRST_SCREEN_BUDGET_SECONDS = 2.0


pytestmark = pytest.mark.skipif(
    os.environ.get("STUDIO_MEDIA_BENCH") != "1",
    reason="set STUDIO_MEDIA_BENCH=1 to run the 10k-file benchmark",
)


def _build_corpus(root):
    """10 subdirs x 1000 tiny files: creation dominates the runtime, so keep
    the payload at one byte - the index only stats files, facts are lazy."""
    for sub in range(SUBDIRS):
        folder = root / f"batch{sub:02d}"
        folder.mkdir(parents=True)
        for index in range(TOTAL_FILES // SUBDIRS):
            (folder / f"2026-11-04-00h00m00s_seed{index:05d}_prompt hint {sub} {index}.png").write_bytes(b"0")


def test_first_screen_is_fast_on_10k_files(tmp_path):
    root = tmp_path / "outputs"
    _build_corpus(root)

    index = MediaIndex(lambda: [str(root)], min_refresh_interval=0.0)
    warm_start = time.perf_counter()
    index.refresh(force=True)  # the warm-up the criterion allows before timing
    warm_seconds = time.perf_counter() - warm_start
    assert index.stats()["total"] == TOTAL_FILES

    screen_start = time.perf_counter()
    page = index.query(limit=50)
    first_screen_seconds = time.perf_counter() - screen_start

    scan = index.stats()["scan"]
    print(
        f"\n10k benchmark: warm-up {warm_seconds:.2f}s "
        f"(full scan {scan['duration_ms']:.0f} ms, "
        f"{scan['directories']} dirs), first screen {first_screen_seconds * 1000:.1f} ms"
    )
    assert page["total"] == TOTAL_FILES
    assert len(page["items"]) == 50
    assert first_screen_seconds < FIRST_SCREEN_BUDGET_SECONDS, (
        f"first screen took {first_screen_seconds:.2f}s, budget is {FIRST_SCREEN_BUDGET_SECONDS:.0f}s"
    )


def test_scan_modes_and_memory_on_10k_files(tmp_path):
    """1.3.4 scalability metrics: cold scan, incremental reuse, a real
    incremental change, full reconcile, query variants and backend RSS.
    Budgets are generous - the point is catching order-of-magnitude
    regressions, not micro-timing the runner."""
    import psutil

    root = tmp_path / "outputs"
    _build_corpus(root)
    process = psutil.Process()
    rss_before = process.memory_info().rss

    index = MediaIndex(lambda: [str(root)], min_refresh_interval=0.0)

    cold_start = time.perf_counter()
    index.refresh(force=True)
    cold_seconds = time.perf_counter() - cold_start

    incremental_start = time.perf_counter()
    index.refresh(wait=True)  # nothing changed: every directory must be reused
    incremental_seconds = time.perf_counter() - incremental_start
    assert index.stats()["scan"]["reused_directories"] == SUBDIRS + 1  # + the root

    (root / "batch00" / "late-arrival.png").write_bytes(b"0")
    changed_start = time.perf_counter()
    index.refresh(wait=True)  # only batch00 is re-listed
    changed_seconds = time.perf_counter() - changed_start

    reconcile_start = time.perf_counter()
    index.refresh(force=True)
    reconcile_seconds = time.perf_counter() - reconcile_start

    page_start = time.perf_counter()
    page = index.query(limit=50)
    first_screen_seconds = time.perf_counter() - page_start

    search_start = time.perf_counter()
    index.query(limit=50, q="prompt hint 3")
    search_seconds = time.perf_counter() - search_start

    sort_start = time.perf_counter()
    index.query(limit=50, sort="name_asc")
    sort_seconds = time.perf_counter() - sort_start

    rss_after = process.memory_info().rss
    print(
        f"\n10k scan modes: cold {cold_seconds:.2f}s, incremental-noop "
        f"{incremental_seconds * 1000:.0f} ms, incremental-change "
        f"{changed_seconds * 1000:.0f} ms, reconcile {reconcile_seconds:.2f}s; "
        f"first page {first_screen_seconds * 1000:.1f} ms, search "
        f"{search_seconds * 1000:.1f} ms, sort {sort_seconds * 1000:.1f} ms; "
        f"backend RSS {rss_before / 1e6:.0f} -> {rss_after / 1e6:.0f} MB"
    )
    assert index.stats()["total"] == TOTAL_FILES + 1
    assert len(page["items"]) == 50
    assert first_screen_seconds < FIRST_SCREEN_BUDGET_SECONDS
    assert search_seconds < 2.0
    assert sort_seconds < 2.0
    assert incremental_seconds < 2.0
    assert cold_seconds < 15.0
    assert reconcile_seconds < 15.0
