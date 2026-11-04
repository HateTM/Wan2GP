# Copyright (c) 2026 WanGP Studio contributors - part of WanGP, WanGP Community License 2.0 (see LICENSE.txt)
"""Plugin Health: installed-vs-upstream state for every folder under ``plugins/``.

Answers, per plugin, the questions a manual audit used to: which version is
installed, what does upstream publish, does the checkout carry local commits
(a fork), is it behind, and is the remote even alive. Facts come from the
local git metadata (no network) unless ``fetch=True`` asks for an upstream
look; the fetch scan runs in a background thread so the view always answers
instantly with the last known state.

States (``entry["state"]``):
- ``built-in``: not a git checkout (bundled with WanGP or hand-placed);
- ``no-remote``: a checkout without an ``origin`` remote;
- ``unreachable``: the remote could not be fetched (deleted upstream, offline);
- ``stale-refs``: the fetch failed but old origin refs allow a best-effort answer;
- ``fork-detached``: local commits on top of an unreachable remote - a locally
  maintained fork (deleted upstream), not a broken plugin;
- ``current`` / ``behind`` / ``fork`` / ``fork-diverged``: relative to ``origin/<default>``.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("wangp.studio")

FETCH_TIMEOUT_SECONDS = 60.0
#: Refuse to hammer every plugin's remote more often than this.
REFRESH_COOLDOWN_SECONDS = 120.0
LOCAL_COMMIT_PREVIEW = 5


def _read_plugin_info(folder: str) -> dict[str, Any]:
    try:
        with open(os.path.join(folder, "plugin_info.json"), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _git(args: list[str], cwd: str, timeout: float = 20.0) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()
    return True, proc.stdout.strip()


def _default_remote_branch(folder: str) -> str | None:
    ok, out = _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], folder)
    if ok and out.startswith("origin/"):
        return out[len("origin/"):]
    for candidate in ("main", "master"):
        if _git(["rev-parse", "--verify", "-q", f"origin/{candidate}"], folder)[0]:
            return candidate
    return None


def collect_plugin_health(
    plugins_root: str | os.PathLike[str] | None,
    *,
    fetch: bool = False,
    fetch_timeout: float = FETCH_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """One snapshot over ``plugins_root``. ``fetch=True`` contacts remotes."""
    root = str(plugins_root or "")
    if not root or not os.path.isdir(root):
        return []
    plugins: list[dict[str, Any]] = []
    for name in sorted(os.listdir(root), key=str.casefold):
        folder = os.path.join(root, name)
        if not os.path.isdir(folder) or name.startswith("."):
            continue
        info = _read_plugin_info(folder)
        entry: dict[str, Any] = {
            "id": name,
            "name": info.get("name") or name,
            "version": info.get("version"),
            "date": info.get("date"),
            "wan2gp_version": info.get("wan2gp_version"),
            "state": "built-in",
            "remote_url": None,
            "branch": None,
            "ahead": 0,
            "behind": 0,
            "upstream_version": None,
            "upstream_date": None,
            "local_commits": [],
            "error": None,
        }
        is_checkout = os.path.isdir(os.path.join(folder, ".git")) or os.path.isfile(os.path.join(folder, ".git"))
        if not is_checkout:
            plugins.append(entry)
            continue
        ok, url = _git(["config", "--get", "remote.origin.url"], folder)
        if not ok or not url:
            entry["state"] = "no-remote"
            plugins.append(entry)
            continue
        entry["remote_url"] = url
        fetch_error: str | None = None
        if fetch:
            ok, out = _git(["fetch", "origin", "--quiet"], folder, timeout=fetch_timeout)
            if not ok:
                fetch_error = out or "fetch failed"
        branch = _default_remote_branch(folder)
        if branch is None:
            entry["state"] = "unreachable" if (fetch_error or fetch) else "no-upstream-ref"
            entry["error"] = fetch_error
            plugins.append(entry)
            continue
        entry["branch"] = branch
        behind_ok, behind = _git(["rev-list", "--count", f"HEAD..origin/{branch}"], folder)
        ahead_ok, ahead = _git(["rev-list", "--count", f"origin/{branch}..HEAD"], folder)
        if not (behind_ok and ahead_ok):
            entry["state"] = "unreachable"
            entry["error"] = fetch_error or behind or ahead
            plugins.append(entry)
            continue
        entry["ahead"] = int(ahead or 0)
        entry["behind"] = int(behind or 0)
        uok, uout = _git(["show", f"origin/{branch}:plugin_info.json"], folder)
        if uok:
            try:
                upstream = json.loads(uout)
                if isinstance(upstream, dict):
                    entry["upstream_version"] = upstream.get("version")
                    entry["upstream_date"] = upstream.get("date")
            except ValueError:
                pass
        if entry["ahead"]:
            lok, lout = _git(["log", "--format=%s", f"origin/{branch}..HEAD"], folder)
            if lok and lout:
                entry["local_commits"] = lout.splitlines()[:LOCAL_COMMIT_PREVIEW]
        if fetch_error:
            # Local work on top of a dead remote is a maintained fork, not a
            # broken plugin; without local commits the answer is just stale.
            entry["state"] = "fork-detached" if entry["ahead"] else "stale-refs"
            entry["error"] = fetch_error
        elif entry["ahead"] and entry["behind"]:
            entry["state"] = "fork-diverged"
        elif entry["ahead"]:
            entry["state"] = "fork"
        elif entry["behind"]:
            entry["state"] = "behind"
        else:
            entry["state"] = "current"
        plugins.append(entry)
    return plugins


class PluginHealthService:
    """Cached health snapshot plus a background upstream refresh."""

    def __init__(self, plugins_root: Callable[[], str], clock: Callable[[], float] = time.time) -> None:
        self._plugins_root = plugins_root
        self._clock = clock
        self._lock = threading.RLock()
        self._items: list[dict[str, Any]] = []
        self._last_fetch_at = 0.0
        self._status: dict[str, Any] = {
            "state": "idle",
            "started_at": None,
            "finished_at": None,
            "fetched": False,
            "error": None,
        }

    def snapshot(self) -> dict[str, Any]:
        """Current knowledge; the first read builds a local-only (offline) view."""
        with self._lock:
            if not self._items:
                items = collect_plugin_health(self._plugins_root(), fetch=False)
                self._items = items
                self._status["finished_at"] = self._clock()
        return {"status": dict(self._status), "plugins": [dict(item) for item in self._items]}

    def refresh(self, *, wait: bool = False, force: bool = False) -> dict[str, Any]:
        """Ask every remote for its latest state.

        Runs in a background thread unless ``wait=True``; a scan already in
        flight is never duplicated, and the remote is left alone within the
        cooldown window unless ``force=True``.
        """
        now = self._clock()
        with self._lock:
            running = self._status["state"] == "running"
            cooled = now - self._last_fetch_at >= REFRESH_COOLDOWN_SECONDS
            if running and not wait:
                return self.snapshot()
            if not (cooled or force or wait):
                return self.snapshot()
            self._status = {
                "state": "running",
                "started_at": now,
                "finished_at": None,
                "fetched": True,
                "error": None,
            }
        if wait:
            return self._run_scan()
        threading.Thread(target=self._run_scan, name="studio-plugin-health", daemon=True).start()
        return self.snapshot()

    def _run_scan(self) -> dict[str, Any]:
        started = self._clock()
        error: str | None = None
        items: list[dict[str, Any]] = []
        try:
            items = collect_plugin_health(self._plugins_root(), fetch=True)
        except Exception as exc:  # a broken repo must not kill the service
            logger.warning("Plugin health scan failed: %s", exc)
            error = f"{type(exc).__name__}: {exc}"
        with self._lock:
            if items:
                self._items = items
            elif not self._items:
                self._items = collect_plugin_health(self._plugins_root(), fetch=False)
            self._last_fetch_at = started
            self._status = {
                "state": "error" if error else "done",
                "started_at": started,
                "finished_at": self._clock(),
                "fetched": True,
                "error": error,
            }
        return {"status": dict(self._status), "plugins": [dict(item) for item in self._items]}
