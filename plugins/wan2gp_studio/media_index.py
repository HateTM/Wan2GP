# Copyright (c) 2026 WanGP Studio contributors - part of WanGP, WanGP Community License 2.0 (see LICENSE.txt)
"""Media Center discovery index for WanGP Studio.

Indexes the four WanGP output roots (plus dedicated workspace folders and optional
workflow outputs) without importing the heavy WanGP media stack at module level:
kinds are classified by extension here, and the core parsers (embedded metadata,
World summaries) are imported lazily per request.

Design constraints (Roadmap v3, M1):
- the index stores file facts only (name, size, mtime); metadata is extracted on demand;
- facts are cached per (mtime_ns, size) and invalidated when a file changes;
- nothing keeps image/video bytes in memory: thumbnails are produced by the shared
  Deepy thumbnail engine from ``shared.deepy.thumbnails``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import zipfile
from typing import Any, Callable, Iterable

logger = logging.getLogger("wangp.studio")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac"}
MESH_EXTENSIONS = {".glb", ".ply"}
WORLD_EXTENSIONS = {".wgpworld"}
APP_EXTENSIONS = {".wgpapp"}

#: Directory names never scanned: caches, archives, temporary folders, thumbnails.
SKIPPED_DIRECTORIES = {"_tmp", "archives", "__pycache__", ".wanflow-cache"}

SORT_MODES = {"date_desc", "date_asc", "name_asc", "name_desc", "size_desc", "size_asc"}


def media_kind(filename: str) -> str | None:
    """Return ``image``/``video``/``audio``/``3d``/``world``/``app`` or None."""
    suffix = os.path.splitext(filename)[1].lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in WORLD_EXTENSIONS:
        return "world"
    if suffix in MESH_EXTENSIONS:
        return "3d"
    if suffix in APP_EXTENSIONS:
        return "app"
    return None


def media_id_for(path: str) -> str:
    """Stable id of a media file: short sha1 of its normalized absolute path."""
    digest = hashlib.sha1(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()
    return digest[:16]


def parse_filename(name: str) -> dict[str, Any]:
    """Extract the seed and the prompt hint from WanGP's default file name pattern."""
    stem = os.path.splitext(name)[0]
    seed = None
    prompt = stem
    if "_seed" in stem:
        _head, tail = stem.split("_seed", 1)
        digits = ""
        for char in tail:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            seed = int(digits)
            remainder = tail[len(digits):].lstrip("_- ")
            if remainder:
                prompt = remainder
    return {"seed": seed, "prompt_hint": prompt[:240]}


def _image_facts(path: str) -> dict[str, Any]:
    from PIL import Image

    with Image.open(path) as image:
        return {"width": image.width, "height": image.height, "format": image.format}


def _video_facts(path: str) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    try:
        from mutagen.mp4 import MP4

        info = MP4(path).info
        facts["duration"] = round(float(info.length), 3)
        width = getattr(info, "width", None)
        height = getattr(info, "height", None)
        if width and height:
            facts.update({"width": width, "height": height})
        return facts
    except Exception:
        pass
    try:
        from mutagen import File as MutagenFile

        info = MutagenFile(path).info
        length = getattr(info, "length", None)
        if length:
            facts["duration"] = round(float(length), 3)
        width = getattr(info, "width", None)
        height = getattr(info, "height", None)
        if width and height:
            facts.update({"width": width, "height": height})
    except Exception:
        pass
    return facts


def _audio_facts(path: str) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    try:
        from mutagen import File as MutagenFile

        info = MutagenFile(path).info
        length = getattr(info, "length", None)
        if length:
            facts["duration"] = round(float(length), 3)
        bitrate = getattr(info, "bitrate", None)
        if bitrate:
            facts["bitrate"] = int(bitrate)
        sample_rate = getattr(info, "sample_rate", None)
        if sample_rate:
            facts["sample_rate"] = int(sample_rate)
    except Exception:
        pass
    return facts


def _world_facts(path: str) -> dict[str, Any]:
    """Read the world manifest and the sibling video link from the zip header."""
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
    except Exception:
        return {}
    frames = sum(int(segment.get("video_frames") or 0) for segment in manifest.get("segments") or [])
    fps = manifest.get("fps") or 0
    facts = {
        "model_type": manifest.get("model_type"),
        "resolution": f"{manifest.get('width')}x{manifest.get('height')}",
        "fps": fps,
        "segment_count": len(manifest.get("segments") or []),
    }
    if fps:
        facts["duration"] = round(frames / fps, 3)
    video = os.path.splitext(path)[0] + ".mp4"
    if os.path.isfile(video):
        facts["video_filename"] = os.path.basename(video)
    return facts


class MediaIndex:
    """Lazy, thread-safe index over the configured media roots."""

    def __init__(
        self,
        roots_provider: Callable[[], Iterable[str]],
        extra_roots: Iterable[str] = (),
        min_refresh_interval: float = 3.0,
    ) -> None:
        self._roots_provider = roots_provider
        self._extra_roots = tuple(extra_roots)
        self._min_refresh_interval = float(min_refresh_interval)
        self._lock = threading.RLock()
        self._scan_lock = threading.Lock()
        self._first_scan = threading.Event()
        self._entries: dict[str, dict[str, Any]] = {}
        self._fact_cache: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}
        self._scanned_at = 0.0

    # -- roots ---------------------------------------------------------
    def roots(self) -> list[str]:
        values: list[str] = []
        try:
            values.extend(self._roots_provider() or [])
        except Exception:
            pass
        values.extend(self._extra_roots)
        roots: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value.strip():
                continue
            path = os.path.abspath(os.path.expanduser(value.strip()))
            if os.path.isdir(path) and path not in roots:
                roots.append(path)
        return roots

    # -- scanning ------------------------------------------------------
    def refresh(self, force: bool = False, wait: bool | None = None) -> dict[str, Any]:
        """Schedule a rescan. The first scan and explicit ``wait=True`` block so
        callers see data; every later rescan runs in a background thread and
        gallery reads keep serving the previous index without blocking."""
        with self._lock:
            now = time.time()
            need_first = not self._first_scan.is_set()
            stale = force or need_first or now - self._scanned_at >= self._min_refresh_interval
        if not stale:
            return self.stats()
        if wait is None:
            wait = need_first or force
        if wait:
            with self._scan_lock:
                self._do_scan()
            return self.stats()
        if not self._scan_lock.acquire(blocking=False):
            return self.stats()  # a rescan is already running; reads keep serving the current index
        threading.Thread(target=self._scan_then_release, name="studio-media-scan", daemon=True).start()
        return self.stats()

    def _scan_then_release(self) -> None:
        try:
            self._do_scan()
        finally:
            self._scan_lock.release()

    def _do_scan(self) -> None:
        entries: dict[str, dict[str, Any]] = {}
        scan_started_ns = time.time_ns()
        for root in self.roots():
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(
                    name for name in dirnames
                    if not name.startswith(".") and name not in SKIPPED_DIRECTORIES
                )
                for name in filenames:
                    kind = media_kind(name)
                    if kind is None:
                        continue
                    path = os.path.join(dirpath, name)
                    try:
                        stat = os.stat(path)
                    except OSError:
                        continue
                    entry_id = media_id_for(path)
                    entries[entry_id] = {
                        "id": entry_id,
                        "path": path,
                        "name": name,
                        "relative": os.path.relpath(path, root).replace(os.sep, "/"),
                        "root": root,
                        "kind": kind,
                        "size": int(stat.st_size),
                        "mtime": float(stat.st_mtime),
                        "mtime_ns": int(stat.st_mtime_ns),
                    }
        with self._lock:
            # A file indexed while this walk was in flight (e.g. index_file
            # after an upload) may postdate the walk's visit of its directory;
            # keep live entries that appeared after the scan started.
            for media_id, entry in self._entries.items():
                if media_id not in entries and entry["mtime_ns"] >= scan_started_ns:
                    entries[media_id] = entry
            self._entries = entries
            self._scanned_at = time.time()
            for stale in [key for key in self._fact_cache if key not in entries]:
                self._fact_cache.pop(stale, None)
        self._first_scan.set()

    def index_file(self, path: str) -> dict[str, Any] | None:
        """Index one file without walking every media root.

        Upload handlers call this instead of a blocking ``refresh(force=True)``
        so a single new file never stalls the request on a full rescan. Returns
        ``None`` when the path is outside the roots or is not a media file.
        """
        path = os.path.abspath(os.path.expanduser(path))
        root = self._matching_root(path)
        if root is None:
            return None
        kind = media_kind(os.path.basename(path))
        if kind is None:
            return None
        try:
            stat = os.stat(path)
        except OSError:
            return None
        entry_id = media_id_for(path)
        entry = {
            "id": entry_id,
            "path": path,
            "name": os.path.basename(path),
            "relative": os.path.relpath(path, root).replace(os.sep, "/"),
            "root": root,
            "kind": kind,
            "size": int(stat.st_size),
            "mtime": float(stat.st_mtime),
            "mtime_ns": int(stat.st_mtime_ns),
        }
        with self._lock:
            self._entries[entry_id] = entry
            self._fact_cache.pop(entry_id, None)
        return entry

    def stats(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for entry in self._entries.values():
            kinds[entry["kind"]] = kinds.get(entry["kind"], 0) + 1
        return {
            "total": len(self._entries),
            "kinds": kinds,
            "roots": self.roots(),
            "scanned_at": self._scanned_at,
        }

    # -- lookup --------------------------------------------------------
    def get(self, media_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._entries.get(media_id)

    # -- facts ---------------------------------------------------------
    def facts(self, entry: dict[str, Any]) -> dict[str, Any]:
        stamp = (entry["mtime_ns"], entry["size"])
        with self._lock:
            cached = self._fact_cache.get(entry["id"])
            if cached and cached[0] == stamp:
                return dict(cached[1])
        facts: dict[str, Any] = {}
        kind = entry["kind"]
        try:
            if kind == "image":
                facts = _image_facts(entry["path"])
            elif kind == "video":
                facts = _video_facts(entry["path"])
            elif kind == "audio":
                facts = _audio_facts(entry["path"])
            elif kind == "world":
                facts = _world_facts(entry["path"])
        except Exception as exc:
            logger.warning("Media facts failed for %s: %s", entry["path"], exc)
            facts = {}
        with self._lock:
            self._fact_cache[entry["id"]] = (stamp, dict(facts))
        return facts

    # -- read models ---------------------------------------------------
    def card(self, entry: dict[str, Any]) -> dict[str, Any]:
        payload = {
            key: entry[key]
            for key in ("id", "kind", "name", "relative", "root", "size", "mtime", "path")
        }
        payload.update(parse_filename(entry["name"]))
        payload.update(self.facts(entry))
        return payload

    def query(
        self,
        kind: str | None = None,
        q: str = "",
        sort: str = "date_desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        kind = (kind or "").strip().lower() or None
        if kind in ("all", "any", "*"):
            kind = None
        needle = (q or "").strip().casefold()
        with self._lock:
            items = [entry for entry in self._entries.values() if kind is None or entry["kind"] == kind]
        if needle:
            items = [
                entry for entry in items
                if needle in entry["name"].casefold()
                or needle in parse_filename(entry["name"])["prompt_hint"].casefold()
            ]
        if sort == "date_asc":
            items.sort(key=lambda entry: (entry["mtime"], entry["name"]))
        elif sort == "name_asc":
            items.sort(key=lambda entry: entry["name"].casefold())
        elif sort == "name_desc":
            items.sort(key=lambda entry: entry["name"].casefold(), reverse=True)
        elif sort == "size_desc":
            items.sort(key=lambda entry: (entry["size"], entry["name"]), reverse=True)
        elif sort == "size_asc":
            items.sort(key=lambda entry: (entry["size"], entry["name"]))
        else:
            items.sort(key=lambda entry: (entry["mtime"], entry["name"]), reverse=True)
        total = len(items)
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [self.card(entry) for entry in items[offset:offset + limit]],
        }

    def detail(self, entry: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {"item": self.card(entry), "metadata": None, "world": None, "links": []}
        kind = entry["kind"]
        path = entry["path"]
        try:
            if kind == "image":
                from shared.utils.audio_video import read_image_metadata

                payload["metadata"] = read_image_metadata(path)
            elif kind == "video":
                from shared.utils.video_metadata import read_metadata_from_video

                payload["metadata"] = read_metadata_from_video(path)
            elif kind == "audio":
                from shared.utils.audio_metadata import read_audio_metadata

                payload["metadata"] = read_audio_metadata(path)
            elif kind == "world":
                from shared.utils.world_outputs import read_world_metadata, video_path, world_summary

                payload["metadata"] = read_world_metadata(path)
                payload["world"] = world_summary(path, segments=True)
                sibling = video_path(path)
                if os.path.isfile(sibling):
                    payload["links"].append({
                        "kind": "video",
                        "path": sibling,
                        "id": media_id_for(sibling),
                        "name": os.path.basename(sibling),
                    })
            elif kind == "3d":
                from shared.utils.mesh_outputs import read_mesh_metadata

                payload["metadata"] = read_mesh_metadata(path)
            elif kind == "app":
                from shared.utils.app_outputs import read_app_metadata

                payload["metadata"] = read_app_metadata(path)
        except Exception as exc:  # broken or truncated files must not fail the API
            payload["metadata_error"] = f"{type(exc).__name__}: {exc}"
        return payload

    # -- actions -------------------------------------------------------
    def _matching_root(self, path: str) -> str | None:
        # realpath resolves symlinks/junctions, otherwise a link inside a media
        # root could serve (or delete) a file that lives outside of it.
        normalized = os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(path))))
        for root in self.roots():
            base = os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(root))))
            if normalized == base or normalized.startswith(base + os.sep):
                return root
        return None

    def _inside_roots(self, path: str) -> bool:
        return self._matching_root(path) is not None

    def delete(self, media_id: str, *, remove_sidecar: bool = True) -> bool:
        entry = self.get(media_id)
        if entry is None:
            return False
        path = entry["path"]
        if not self._inside_roots(path):
            raise ValueError("Refusing to delete a file outside the media roots.")
        os.remove(path)
        if remove_sidecar:
            sidecar = os.path.splitext(path)[0] + ".json"
            if os.path.isfile(sidecar):
                try:
                    os.remove(sidecar)
                except OSError:
                    pass
        with self._lock:
            self._entries.pop(media_id, None)
            self._fact_cache.pop(media_id, None)
        self.refresh(force=True, wait=False)
        return True


def thumbnail_bytes(path: str) -> bytes | None:
    """Small JPEG preview from the shared Deepy thumbnail engine (lazy import)."""
    from shared.deepy.thumbnails import thumbnail

    return thumbnail(path)
