"""Fork-guard and version-compare regressions for shared.utils.plugins.

The core app has no test suite of its own; this lives in the plugin_manager
plugin so the established per-plugin pytest pattern covers the shared code
its UI drives.
"""
import json
import os
import subprocess
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGINS_ROOT = os.path.dirname(PLUGIN_DIR)
REPO_ROOT = os.path.dirname(PLUGINS_ROOT)
sys.path.insert(0, PLUGINS_ROOT)
sys.path.insert(0, REPO_ROOT)

from shared.utils.plugins import (  # noqa: E402
    PluginManager,
    compare_release_metadata,
)


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _commit_all(repo, message, version):
    (repo / "plugin_info.json").write_text(json.dumps({"name": "MyPlug", "version": version}), encoding="utf-8")
    _git("add", "-A", cwd=repo)
    _git("commit", "-m", message, cwd=repo)


@pytest.fixture()
def plugin_repo(tmp_path, monkeypatch):
    """A bare 'origin' repo and a clean clone of it under plugins_dir."""
    monkeypatch.chdir(tmp_path)  # PluginManager derives repo_root from cwd
    origin = tmp_path / "origin" / "MyPlug"
    origin.mkdir(parents=True)
    _git("init", "-b", "main", str(origin), cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=origin)
    _git("config", "user.name", "Test", cwd=origin)
    _commit_all(origin, "base release", "1.0.0")
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    clone = plugins_dir / "MyPlug"
    _git("clone", "-q", str(origin), str(clone), cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=clone)
    _git("config", "user.name", "Test", cwd=clone)
    return origin, clone


def _manager(tmp_path):
    return PluginManager(plugins_dir=str(tmp_path / "plugins"))


# -- compare_release_metadata -------------------------------------------------


def test_newer_version_wins_over_newer_date():
    """A version bump must beat a stale date string (maintainers forget dates)."""
    left = {"version": "1.3.1", "date": "2026-08-15"}
    right = {"version": "1.2.1", "date": "2026-11-03"}
    assert compare_release_metadata(left, right) == 1
    assert compare_release_metadata(right, left) == -1


def test_equal_version_falls_back_to_date():
    """Fixes can ship without a version bump: the date is the tiebreaker."""
    old = {"version": "0.3.0", "date": "2026-06-14"}
    fixed = {"version": "0.3.0", "date": "2026-08-08"}
    assert compare_release_metadata(fixed, old) == 1
    assert compare_release_metadata(old, fixed) == -1
    assert compare_release_metadata(old, old) == 0


def test_missing_version_compares_by_date():
    entry_with_date = {"version": "", "date": "2026-09-01"}
    entry_without = {"version": "1.2.1"}
    assert compare_release_metadata(entry_with_date, entry_without) == 1
    assert compare_release_metadata(entry_without, entry_with_date) == -1


def test_missing_version_with_no_dates_is_equal():
    assert compare_release_metadata({"version": ""}, {"date": ""}) == 0


def test_missing_date_does_not_invent_newness_for_equal_versions():
    """Same version, only one side carries a date: an absent date must not be
    read as 'older' and ring a false update bell."""
    assert compare_release_metadata({"version": "1.1.0", "date": "2026-02-13"}, {"version": "1.1.0"}) == 1
    assert compare_release_metadata({"version": "1.1.0"}, {"version": "1.1.0", "date": "2026-02-13"}) == -1


# -- update_plugin fork guard -------------------------------------------------


def test_update_pulls_clean_clone(plugin_repo, tmp_path):
    origin, clone = plugin_repo
    _commit_all(origin, "upstream fix", "1.1.0")
    manager = _manager(tmp_path)
    result = manager.update_plugin("MyPlug")
    assert "[Success]" in result, result
    assert json.loads((clone / "plugin_info.json").read_text(encoding="utf-8"))["version"] == "1.1.0"


def test_update_reports_up_to_date(plugin_repo, tmp_path):
    manager = _manager(tmp_path)
    assert "up to date" in manager.update_plugin("MyPlug")


def test_update_refuses_local_commits(plugin_repo, tmp_path):
    """The exact WanFlow/Finetune-Manager situation: local commits must not be
    silently folded into a merge by a blind pull."""
    origin, clone = plugin_repo
    (clone / "local_feature.py").write_text("# keep me\n", encoding="utf-8")
    _git("add", "-A", cwd=clone)
    _git("commit", "-m", "Add local feature", cwd=clone)
    _commit_all(origin, "upstream fix", "1.1.0")  # upstream also moved
    result = _manager(tmp_path).update_plugin("MyPlug")
    assert "[Error] Update refused" in result, result
    assert "1 local commit" in result
    assert "Add local feature" in result
    # the working tree is untouched: still the fork, still on its own head
    assert (clone / "local_feature.py").exists()


def test_update_refuses_unrelated_history(plugin_repo, tmp_path):
    origin, clone = plugin_repo
    orphan = tmp_path / "orphan" / "MyPlug"
    orphan.mkdir(parents=True)
    _git("init", "-b", "main", str(orphan), cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=orphan)
    _git("config", "user.name", "Test", cwd=orphan)
    _commit_all(orphan, "unrelated baseline", "9.9.9")
    _git("remote", "set-url", "origin", str(orphan), cwd=clone)
    result = _manager(tmp_path).update_plugin("MyPlug")
    assert "[Error] Update refused" in result, result
    assert "no commit history" in result


def test_update_refuses_missing_remote(plugin_repo, tmp_path):
    origin, clone = plugin_repo
    _git("remote", "remove", "origin", cwd=clone)
    result = _manager(tmp_path).update_plugin("MyPlug")
    assert "[Error]" in result and "no git remote" in result
