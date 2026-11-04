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
- ``unreachable``: no usable origin refs at all;
- ``stale-refs``: the fetch failed (network/auth trouble) but old origin refs
  allow a best-effort answer;
- ``upstream-gone``: the remote itself reports the repository no longer exists;
- ``fork-detached``: local commits on top of a remote that no longer exists -
  a locally maintained fork, not a broken plugin;
- ``fork-unavailable``: local commits, remote temporarily unreachable;
- ``current`` / ``behind`` / ``fork`` / ``fork-diverged``: relative to ``origin/<default>``.

With a ``wangp_version`` provider each entry also carries
``wangp_compatible`` (``None`` when the plugin declares no requirement).
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("wangp.studio")

FETCH_TIMEOUT_SECONDS = 60.0
#: Refuse to hammer every plugin's remote more often than this.
REFRESH_COOLDOWN_SECONDS = 120.0
LOCAL_COMMIT_PREVIEW = 5

#: States that mean "the remote no longer exists" as opposed to transient
#: network trouble (a failed fetch alone cannot tell them apart).
_GONE_MARKERS = ("not found", "does not appear to be a git repository")


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


def _remote_gone(folder: str) -> bool:
    """True when the remote itself reports it no longer exists (deleted or
    renamed repository, dead path). A bare ``git fetch`` failure cannot tell
    this from DNS trouble, timeouts or auth prompts - ``ls-remote`` can,
    because its stderr carries the server's own answer."""
    ok, out = _git(["ls-remote", "origin", "HEAD"], folder, timeout=15.0)
    if ok:
        return False
    text = (out or "").lower()
    return any(marker in text for marker in _GONE_MARKERS)


def host_wan2gp_version(repo_root: str | None = None) -> str | None:
    """Version of the running WanGP host, read from ``wgp.py``'s module
    constant (importing wgp would start the whole application)."""
    root = repo_root or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        with open(os.path.join(root, "wgp.py"), encoding="utf-8") as handle:
            head = handle.read(8192)
    except OSError:
        return None
    match = re.search(r'^WanGP_version\s*=\s*"([^"]+)"', head, re.MULTILINE)
    return match.group(1) if match else None


def collect_plugin_health(
    plugins_root: str | os.PathLike[str] | None,
    *,
    fetch: bool = False,
    fetch_timeout: float = FETCH_TIMEOUT_SECONDS,
    wangp_version: str | None = None,
) -> list[dict[str, Any]]:
    """One snapshot over ``plugins_root``. ``fetch=True`` contacts remotes;
    ``wangp_version`` enables the per-plugin compatibility verdict."""
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
            # A failed fetch is not proof of a deleted upstream: probe the
            # remote once so "upstream gone" is only claimed when the server
            # itself says so (404/not found). Local work on top of a dead
            # remote is a maintained fork, not a broken plugin.
            gone = _remote_gone(folder)
            if gone and entry["ahead"]:
                entry["state"] = "fork-detached"
            elif gone:
                entry["state"] = "upstream-gone"
            elif entry["ahead"]:
                entry["state"] = "fork-unavailable"
            else:
                entry["state"] = "stale-refs"
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
    if wangp_version:
        from shared.utils.plugins import is_wangp_compatible

        for entry in plugins:
            required = entry.get("wan2gp_version")
            entry["wangp_compatible"] = (
                is_wangp_compatible(str(required), str(wangp_version)) if required else None
            )
    return plugins


class PluginHealthService:
    """Cached health snapshot plus a background upstream refresh."""

    def __init__(
        self,
        plugins_root: Callable[[], str],
        clock: Callable[[], float] = time.time,
        wangp_version: Callable[[], str | None] | None = None,
    ) -> None:
        self._plugins_root = plugins_root
        self._clock = clock
        self._wangp_version = wangp_version
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
                items = collect_plugin_health(self._plugins_root(), fetch=False, wangp_version=self._host_version())
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

    def _host_version(self) -> str | None:
        try:
            return self._wangp_version() if self._wangp_version else None
        except Exception:
            return None

    def _run_scan(self) -> dict[str, Any]:
        started = self._clock()
        error: str | None = None
        items: list[dict[str, Any]] = []
        try:
            items = collect_plugin_health(self._plugins_root(), fetch=True, wangp_version=self._host_version())
        except Exception as exc:  # a broken repo must not kill the service
            logger.warning("Plugin health scan failed: %s", exc)
            error = f"{type(exc).__name__}: {exc}"
        with self._lock:
            if items:
                self._items = items
            elif not self._items:
                self._items = collect_plugin_health(self._plugins_root(), fetch=False, wangp_version=self._host_version())
            self._last_fetch_at = started
            self._status = {
                "state": "error" if error else "done",
                "started_at": started,
                "finished_at": self._clock(),
                "fetched": True,
                "error": error,
            }
        return {"status": dict(self._status), "plugins": [dict(item) for item in self._items]}
