"""Result cache and resume checkpoints for WanFlow UI graph runs.

Two mechanisms share one signature scheme:

* Resume: every heavy node stores its result in a checkpoint as soon as it finishes. A run that
  fails or is cancelled leaves the checkpoint behind, so running the same graph again reuses the
  nodes that already completed (any seed, including random ones) instead of regenerating them.
  A run that finishes successfully clears the checkpoint. Entries expire after RESUME_TTL_SECONDS.
* Cache: a result is also kept across runs, but only when it is reproducible: a generation node
  with a fixed seed, or a deterministic media operation whose whole upstream chain is reproducible.

A node's signature covers its type and parameters, the graph settings, the current workflow
variables and the signatures of the nodes feeding it. Files are identified by path, size and mtime,
so replacing an input file invalidates everything below it. Set WANFLOW_NO_CACHE=1 to disable both.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

CACHE_DIR_NAME = ".wanflow-cache"
RESUME_TTL_SECONDS = 6 * 3600
CACHE_MAX_ENTRIES = 300
CACHE_MAX_AGE_SECONDS = 30 * 86400

# Nodes whose result is expensive enough to checkpoint.
GENERATION_TYPES = {"generate_image", "edit_image", "inpaint_image", "generate_video", "edit_video", "inpaint_video", "generate_audio"}
DETERMINISTIC_MEDIA_TYPES = {"last_frame", "extract_frame", "image_sequence", "ffmpeg_trim", "ffmpeg_concat", "ffmpeg_mux_audio", "ffmpeg_remove_audio", "ffmpeg_resize", "ffmpeg_fps"}
NONDETERMINISTIC_HEAVY_TYPES = {"prompt_enhancer", "ai_analyze", "magic_mask", "postprocess"}
HEAVY_TYPES = GENERATION_TYPES | DETERMINISTIC_MEDIA_TYPES | NONDETERMINISTIC_HEAVY_TYPES


def enabled() -> bool:
    return os.environ.get("WANFLOW_NO_CACHE", "").strip().lower() not in {"1", "true", "yes", "on"}


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))


def digest(*parts: Any) -> str:
    return hashlib.sha256(_canon(list(parts)).encode("utf-8")).hexdigest()


def file_fingerprint(path: str | Path) -> str | None:
    """path|size|mtime_ns of an existing file, else None."""
    try:
        stat = os.stat(path)
    except (OSError, ValueError):
        return None
    if not os.path.isfile(path):
        return None
    return f"{os.path.abspath(path)}|{stat.st_size}|{stat.st_mtime_ns}"


def _looks_like_path(value: str) -> bool:
    return 0 < len(value) < 520 and "\n" not in value and "\r" not in value


def fingerprint_value(value: Any) -> Any:
    """Replace existing file paths inside a result by their fingerprint so that content changes show."""
    if isinstance(value, str):
        if _looks_like_path(value):
            fingerprint = file_fingerprint(value)
            if fingerprint is not None:
                return "file:" + fingerprint
        return value
    if isinstance(value, dict):
        return {str(key): fingerprint_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [fingerprint_value(item) for item in value]
    return value


def _collect_files(value: Any, found: list[list[Any]]) -> None:
    if isinstance(value, str):
        if _looks_like_path(value) and os.path.isfile(value):
            stat = os.stat(value)
            found.append([value, stat.st_size, stat.st_mtime_ns])
    elif isinstance(value, dict):
        for item in value.values():
            _collect_files(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_files(item, found)


def seed_is_fixed(node: dict[str, Any], graph: dict[str, Any]) -> bool:
    """A generation is reproducible only when its seed is an explicit non-negative number."""
    params = node.get("params") or {}
    settings = params.get("settings") if isinstance(params.get("settings"), dict) else {}
    for source in (settings, params, graph.get("settings") or {}):
        if "seed" in source:
            try:
                return int(source["seed"]) >= 0
            except (TypeError, ValueError):
                return False
    return False


def node_is_deterministic(node: dict[str, Any], graph: dict[str, Any]) -> bool:
    node_type = node.get("type")
    if node_type in GENERATION_TYPES:
        return seed_is_fixed(node, graph)
    return node_type in DETERMINISTIC_MEDIA_TYPES


# Workflow settings and variables that never change what a node produces: they steer how the run
# behaves (resource checks, unloading models) or report on it, and must not invalidate results.
IGNORED_SETTINGS = {"preflight", "unload_on_model_change", "unload_around_heavy_processing"}
IGNORED_VARIABLES = {"preflight"}


def node_key(node: dict[str, Any], graph: dict[str, Any], variables: dict[str, str], upstream: list[Any]) -> str:
    # The node id and workflow name keep distinct nodes (and distinct workflows sharing an output
    # folder) from picking up each other's results when their configuration happens to be identical.
    settings = {key: value for key, value in (graph.get("settings") or {}).items() if key not in IGNORED_SETTINGS}
    relevant = {key: value for key, value in variables.items() if key not in IGNORED_VARIABLES}
    return digest("node", graph.get("name"), node.get("id"), node.get("type"), node.get("params") or {}, settings, relevant, upstream)


class RunStore:
    """Checkpoint (resume) and cross-run cache stored below `<output_root>/.wanflow-cache`."""

    def __init__(self, root: str | Path):
        self.dir = Path(root) / CACHE_DIR_NAME
        self.cache_dir = self.dir / "cache"
        self.resume_path = self.dir / "resume.json"
        self._resume: dict[str, dict[str, Any]] = self._load_resume()

    # -- validation ---------------------------------------------------------------------------
    @staticmethod
    def _files_valid(entry: dict[str, Any]) -> bool:
        for path, size, mtime_ns in entry.get("files") or []:
            try:
                stat = os.stat(path)
            except OSError:
                return False
            if stat.st_size != size or stat.st_mtime_ns != mtime_ns:
                return False
        return True

    def _fresh(self, entry: Any, max_age: float) -> bool:
        return isinstance(entry, dict) and "result" in entry and (time.time() - float(entry.get("t", 0))) <= max_age and self._files_valid(entry)

    def _load_resume(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.resume_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {key: entry for key, entry in data.items() if self._fresh(entry, RESUME_TTL_SECONDS)}

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=True, default=str)
            os.replace(temp, path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise

    # -- API ----------------------------------------------------------------------------------
    def get(self, key: str, *, cross_run: bool) -> dict[str, Any] | None:
        entry = self._resume.get(key)
        if entry is not None and self._fresh(entry, RESUME_TTL_SECONDS):
            return entry
        if cross_run:
            try:
                entry = json.loads((self.cache_dir / f"{key}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
            if self._fresh(entry, CACHE_MAX_AGE_SECONDS):
                return entry
        return None

    def put(self, key: str, result: dict[str, Any], variables_delta: dict[str, str], *, cross_run: bool) -> None:
        files: list[list[Any]] = []
        _collect_files(result, files)
        entry = {"t": time.time(), "result": result, "vars": variables_delta, "files": files}
        try:
            self._resume[key] = entry
            self._write_json(self.resume_path, self._resume)
            if cross_run:
                self._write_json(self.cache_dir / f"{key}.json", entry)
        except OSError:
            pass  # a cache failure must never fail the run

    def finish(self) -> None:
        """Successful run: the checkpoint has served its purpose."""
        self._resume = {}
        try:
            self.resume_path.unlink(missing_ok=True)
        except OSError:
            pass

    def prune(self) -> None:
        try:
            entries = sorted(self.cache_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            return
        now = time.time()
        for index, path in enumerate(entries):
            try:
                if index >= CACHE_MAX_ENTRIES or now - path.stat().st_mtime > CACHE_MAX_AGE_SECONDS:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
