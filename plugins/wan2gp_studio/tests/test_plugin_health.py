"""Plugin Health: installed-vs-upstream state per plugin folder."""
import json
import os
import subprocess
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT_DIR = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT_DIR)
sys.path.insert(0, PLUGINS_ROOT_DIR)
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from wan2gp_studio.plugin import WanGPStudioPlugin  # noqa: E402
from wan2gp_studio.plugin_health import (  # noqa: E402
    PluginHealthService,
    collect_plugin_health,
)


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _commit(repo, message, version):
    (repo / "plugin_info.json").write_text(
        json.dumps({"name": repo.name, "version": version, "date": "2026-01-01"}), encoding="utf-8"
    )
    _git("add", "-A", cwd=repo)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", message, cwd=repo)


@pytest.fixture()
def health_root(tmp_path):
    """A plugins folder exercising every state except unreachable-on-fetch."""
    root = tmp_path / "plugins"
    root.mkdir()

    builtin = root / "Builtin-Plugin"
    builtin.mkdir()
    (builtin / "plugin_info.json").write_text(
        json.dumps({"name": "Builtin-Plugin", "version": "2.0.0", "date": "2026-01-01"}), encoding="utf-8"
    )

    noremote = root / "NoRemote-Plugin"
    noremote.mkdir()
    _git("init", "-b", "main", str(noremote), cwd=root)
    _commit(noremote, "local only", "1.0.0")

    upstream = root / "Current-Plugin"
    upstream.mkdir()
    _git("init", "-b", "main", str(upstream), cwd=root)
    _commit(upstream, "base", "1.0.0")
    _git("clone", "-q", str(upstream), str(root / "Current-Clone"), cwd=root)

    fork_origin = root / "Fork-Plugin"
    fork_origin.mkdir()
    _git("init", "-b", "main", str(fork_origin), cwd=root)
    _commit(fork_origin, "base", "0.1.0")
    _git("clone", "-q", str(fork_origin), str(root / "Fork-Clone"), cwd=root)
    (root / "Fork-Clone" / "extra.py").write_text("# local\n", encoding="utf-8")
    _git("add", "-A", cwd=root / "Fork-Clone")
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "Add local feature", cwd=root / "Fork-Clone")

    behind_origin = root / "Behind-Plugin"
    behind_origin.mkdir()
    _git("init", "-b", "main", str(behind_origin), cwd=root)
    _commit(behind_origin, "base", "1.0.0")
    _git("clone", "-q", str(behind_origin), str(root / "Behind-Clone"), cwd=root)
    _commit(behind_origin, "upstream fix", "1.1.0")

    dead = root / "Dead-Clone"
    _git("clone", "-q", str(upstream), str(dead), cwd=root)
    _git("remote", "set-url", "origin", str(tmp_path / "nowhere"), cwd=dead)

    for clone in ("Current-Clone", "Fork-Clone", "Behind-Clone", "Dead-Clone"):
        _git("config", "user.email", "t@t", cwd=root / clone)
        _git("config", "user.name", "t", cwd=root / clone)
    return root


def _states(root, fetch):
    items = collect_plugin_health(root, fetch=fetch)
    return {item["id"]: item for item in items}


def test_offline_snapshot_classifies_local_facts(health_root):
    states = _states(health_root, fetch=False)
    assert states["Builtin-Plugin"]["state"] == "built-in"
    assert states["Builtin-Plugin"]["version"] == "2.0.0"
    assert states["NoRemote-Plugin"]["state"] == "no-remote"
    assert states["Current-Clone"]["state"] == "current"
    assert states["Fork-Clone"]["state"] == "fork"
    assert states["Fork-Clone"]["ahead"] == 1
    assert "Add local feature" in states["Fork-Clone"]["local_commits"]


def test_fetch_report_upstream_versions_and_behind(health_root):
    states = _states(health_root, fetch=True)
    assert states["Current-Clone"]["state"] == "current"
    assert states["Current-Clone"]["upstream_version"] == "1.0.0"
    assert states["Behind-Clone"]["state"] == "behind"
    assert states["Behind-Clone"]["behind"] == 1
    assert states["Behind-Clone"]["upstream_version"] == "1.1.0"
    assert states["Fork-Clone"]["state"] == "fork"
    # a dead remote answers from the refs it still has, flagged as stale
    assert states["Dead-Clone"]["state"] == "stale-refs"
    assert states["Dead-Clone"]["error"]
    assert states["Dead-Clone"]["upstream_version"] == "1.0.0"


def test_diverged_fork_is_flagged(health_root):
    root = health_root
    _commit(root / "Fork-Plugin", "upstream move", "0.2.0")
    states = _states(root, fetch=True)
    assert states["Fork-Clone"]["state"] == "fork-diverged"
    assert states["Fork-Clone"]["ahead"] == 1 and states["Fork-Clone"]["behind"] == 1


def test_service_first_snapshot_is_offline_then_refresh(health_root):
    service = PluginHealthService(lambda: str(health_root))
    first = service.snapshot()
    assert first["status"]["fetched"] is False
    assert {item["id"] for item in first["plugins"]} >= {"Builtin-Plugin", "Current-Clone"}
    final = service.refresh(wait=True)
    assert final["status"]["state"] == "done"
    by_id = {item["id"]: item for item in final["plugins"]}
    assert by_id["Current-Clone"]["upstream_version"] == "1.0.0"


def test_health_routes_serve_snapshot_and_refresh(tmp_path, monkeypatch):
    root = tmp_path / "plugins"
    builtin = root / "Builtin-Plugin"
    builtin.mkdir(parents=True)
    (builtin / "plugin_info.json").write_text(json.dumps({"name": "B", "version": "1.0"}), encoding="utf-8")
    monkeypatch.setenv("STUDIO_PLUGINS_ROOT", str(root))
    plugin = WanGPStudioPlugin()
    plugin.server_config = {}
    client = TestClient(plugin.create_web_app())
    payload = client.get("/api/plugins/health").json()
    assert payload["status"]["state"] in ("idle", "done")
    assert payload["plugins"][0]["state"] == "built-in"
    refreshed = client.post("/api/plugins/health/refresh").json()
    assert refreshed["status"]["state"] in ("running", "done")
