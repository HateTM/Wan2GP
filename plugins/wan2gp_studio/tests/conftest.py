"""Shared pytest setup for the Studio test suite.

The WanFlow UI plugin is vendored at ``plugins/wan2gp-wanflow-ui`` (the
reconciled fork - see that folder's RECONCILIATION.md), so the workflow tests
run in every environment. ``WANFLOW_UI_REQUIRED=1`` remains for the opt-in CI
integration job that checks out an *alternate* WanFlow version: a missing
import there fails the session instead of turning the suite into skips.
"""
import importlib
import os
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)

for path in (REPO_ROOT, PLUGINS_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


def wanflow_available() -> bool:
    try:
        importlib.import_module("wan2gp-wanflow-ui.graph_model")
    except Exception:
        return False
    return True


def pytest_sessionstart(session):
    if os.environ.get("WANFLOW_UI_REQUIRED") != "1":
        return
    if wanflow_available():
        return
    raise pytest.UsageError(
        "WANFLOW_UI_REQUIRED=1 but 'wan2gp-wanflow-ui' cannot be imported; "
        "install the WanFlow UI plugin before running the integration suite."
    )
