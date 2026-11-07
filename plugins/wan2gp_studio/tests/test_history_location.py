"""Regression: Studio history files must live in workspaces/studio/, never in
the workspaces root - the Deepy WorkspaceStore parses every root-level
workspaces/*.json as a workspace manifest and crashes wgp.py otherwise
(found when a persisted studio_jobs.json broke the app startup)."""
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402


def _make_plugin(tmp_path):
    plugin = WanGPStudioPlugin()
    plugin.server_config = {"workspaces_dir": str(tmp_path / "workspaces")}
    plugin._get_session = lambda: {"_ui_local": None}
    return plugin


def test_history_lives_in_studio_subdir(tmp_path):
    """Serving the app must keep the workspaces root clean of Studio files."""
    plugin = _make_plugin(tmp_path)
    plugin.create_web_app()
    workspaces = tmp_path / "workspaces"
    root_files = [p.name for p in workspaces.glob("*.json")]
    assert not root_files, f"history leaked into the workspaces root: {root_files}"


def test_legacy_history_files_are_migrated(tmp_path):
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    (workspaces / "studio_jobs.json").write_text('[{"id": "legacy-job", "status": "completed"}]', encoding="utf-8")
    (workspaces / "studio_runs.json").write_text('[{"id": "legacy-run", "status": "failed"}]', encoding="utf-8")
    plugin = _make_plugin(tmp_path)
    plugin.create_web_app()
    assert not (workspaces / "studio_jobs.json").exists()
    assert not (workspaces / "studio_runs.json").exists()
    assert (workspaces / "studio" / "studio_jobs.json").is_file()
    assert (workspaces / "studio" / "studio_runs.json").is_file()
    # the records survive the move
    import json
    jobs = json.loads((workspaces / "studio" / "studio_jobs.json").read_text(encoding="utf-8"))
    assert jobs[0]["id"] == "legacy-job"
