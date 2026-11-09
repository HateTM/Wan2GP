# Copyright (c) 2026 WanGP Studio contributors - part of WanGP, WanGP Community License 2.0 (see LICENSE.txt)
"""SendTo hand-off between WanGP Studio and other plugins.

Studio runs as its own web app, so it cannot write into another Gradio session:
the ``state`` dict a plugin drains (``state[inbox_key]``) only exists inside the
browser session that renders the WanGP UI. A send therefore takes two steps.

1. Studio validates the target against the plugin's ``sendto.json`` manifest -
   the same contract the standalone SendTo plugin uses - and parks a one-shot
   hand-off id in memory (``SendToRegistry``).
2. Studio answers with a WanGP URL carrying that id. The tab opened from it runs
   the Studio bridge (a hidden Gradio control injected next to the generation
   status): the bridge receives the real session state, appends
   ``{"path", "slot"}`` to the manifest's ``inbox_key``, and Studio's injected JS
   selects the target plugin tab, which drains its inbox into the slot.

Only the documented manifest is read: no code is imported from the target plugin,
so a missing or disabled plugin degrades to an error the UI can explain.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("wangp.studio")

MANIFEST_FILENAME = "sendto.json"
PLUGIN_INFO_FILENAME = "plugin_info.json"

#: A hand-off is valid for a couple of minutes: long enough to open a tab and
#: click through, short enough that a forgotten id cannot fire much later.
DEFAULT_TTL_SECONDS = 120.0
#: Bounded queues: the payload is only a path, but ids must not pile up on a
#: long-running server.
DEFAULT_MAX_HANDOFFS = 64
CONSUMED_HISTORY = 32
MANIFEST_CACHE_SECONDS = 5.0

DEFAULT_INBOX_LIMIT = 200

MEDIA_KINDS = ("image", "video", "audio", "world", "3d", "app")


class SendToError(Exception):
    """A refused send. ``status_code`` maps onto the Studio HTTP answer."""

    def __init__(self, status_code: int, detail: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = str(detail)
        self.extra = dict(extra or {})

    def payload(self) -> dict[str, Any]:
        payload = {"message": self.detail}
        payload.update(self.extra)
        return payload


@dataclass(frozen=True)
class SendToTarget:
    """One selectable destination of a plugin (a ``targets[]`` entry)."""

    plugin: str
    plugin_label: str
    slot: str
    label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "plugin": self.plugin,
            "plugin_label": self.plugin_label,
            "slot": self.slot,
            "label": self.label,
        }


@dataclass(frozen=True)
class SendToManifest:
    """A validated ``sendto.json`` plus the plugin folder that declares it."""

    plugin: str
    plugin_label: str
    tab: str
    inbox_key: str
    accepts: tuple[str, ...]
    targets: tuple[SendToTarget, ...] = field(default_factory=tuple)

    def accepts_kind(self, kind: str) -> bool:
        return not self.accepts or kind in self.accepts

    def slot_label(self, slot: str) -> str | None:
        for target in self.targets:
            if target.slot == slot:
                return target.label
        return None

    def slots(self) -> tuple[str, ...]:
        return tuple(target.slot for target in self.targets)

    def as_dict(self) -> dict[str, Any]:
        return {
            "plugin": self.plugin,
            "label": self.plugin_label,
            "tab": self.tab,
            "inbox_key": self.inbox_key,
            "accepts": list(self.accepts),
            "targets": [target.as_dict() for target in self.targets],
        }


@dataclass
class Handoff:
    """A parked frame waiting for the Gradio bridge of one browser tab."""

    handoff_id: str
    path: str
    name: str
    kind: str
    plugin: str
    plugin_label: str
    slot: str
    slot_label: str
    tab: str
    inbox_key: str
    created_at: float
    expires_at: float

    def as_dict(self, *, include_path: bool = True) -> dict[str, Any]:
        payload = {
            "handoff_id": self.handoff_id,
            "name": self.name,
            "kind": self.kind,
            "plugin": self.plugin,
            "plugin_label": self.plugin_label,
            "slot": self.slot,
            "slot_label": self.slot_label,
            "tab": self.tab,
            "inbox_key": self.inbox_key,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }
        if include_path:
            payload["path"] = self.path
        return payload


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _plugin_dirs(plugins_root: str | os.PathLike[str] | None) -> list[Path]:
    if plugins_root is None:
        return []
    try:
        root = Path(plugins_root)
    except (TypeError, ValueError):
        return []
    if not root.is_dir():
        return []
    try:
        return sorted((entry for entry in root.iterdir() if entry.is_dir()), key=lambda item: item.name.casefold())
    except OSError:
        return []


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_manifest(plugin_dir: Path) -> SendToManifest | None:
    """Parse one plugin's ``sendto.json``. Returns None when unusable."""
    plugin_dir = Path(plugin_dir)
    manifest_path = plugin_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    data = _read_json(manifest_path)
    if not data:
        logger.warning("Ignoring unreadable SendTo manifest: %s", manifest_path)
        return None
    inbox_key = _clean(data.get("inbox_key"))
    if not inbox_key:
        logger.warning("Ignoring SendTo manifest without inbox_key: %s", manifest_path)
        return None
    plugin_id = plugin_dir.name
    info = _read_json(plugin_dir / PLUGIN_INFO_FILENAME) or {}
    plugin_label = _clean(info.get("name")) or _clean(data.get("tab")) or plugin_id
    tab = _clean(data.get("tab")) or plugin_label
    accepts = tuple(
        value for value in (_clean(item).lower() for item in (data.get("accepts") or [])) if value
    )
    targets: list[SendToTarget] = []
    for item in data.get("targets") or []:
        if not isinstance(item, dict):
            continue
        slot = _clean(item.get("slot"))
        if not slot:
            continue
        targets.append(
            SendToTarget(
                plugin=plugin_id,
                plugin_label=plugin_label,
                slot=slot,
                label=_clean(item.get("label")) or slot,
            )
        )
    return SendToManifest(
        plugin=plugin_id,
        plugin_label=plugin_label,
        tab=tab,
        inbox_key=inbox_key,
        accepts=accepts,
        targets=tuple(targets),
    )


def discover_manifests(plugins_root: str | os.PathLike[str] | None) -> dict[str, SendToManifest]:
    """Map plugin id -> manifest for every installed plugin that declares one."""
    manifests: dict[str, SendToManifest] = {}
    for plugin_dir in _plugin_dirs(plugins_root):
        manifest = read_manifest(plugin_dir)
        if manifest is not None:
            manifests[manifest.plugin] = manifest
    return manifests


def inbox_append(state: Any, inbox_key: str, path: str, slot: str | None, *, limit: int = DEFAULT_INBOX_LIMIT) -> bool:
    """Append one frame to a plugin inbox the way the SendTo contract says.

    ``state`` is the live Gradio session dict, so this runs inside the bridge
    callback, never from a Studio HTTP handler.
    """
    if not isinstance(state, dict) or not inbox_key:
        return False
    box = state.get(inbox_key)
    if not isinstance(box, list):
        box = []
    box.append({"path": str(path), "slot": slot})
    state[inbox_key] = box[-max(1, int(limit)):]
    return True


class SendToRegistry:
    """Bounded, thread-safe store of park-and-claim SendTo hand-offs."""

    def __init__(
        self,
        plugins_root: Callable[[], str | os.PathLike[str] | None],
        *,
        is_enabled: Callable[[str], bool] | None = None,
        ttl: float = DEFAULT_TTL_SECONDS,
        limit: int = DEFAULT_MAX_HANDOFFS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._plugins_root = plugins_root
        self._is_enabled = is_enabled
        self._ttl = max(1.0, float(ttl))
        self._limit = max(1, int(limit))
        self._clock = clock
        self._lock = threading.RLock()
        self._handoffs: dict[str, Handoff] = {}
        self._consumed: dict[str, str | None] = {}
        self._manifest_cache: dict[str, SendToManifest] = {}
        self._manifest_cache_at = 0.0

    # -- manifests ------------------------------------------------------
    def manifests(self, *, refresh: bool = False) -> dict[str, SendToManifest]:
        now = self._clock()
        with self._lock:
            fresh = now - self._manifest_cache_at < MANIFEST_CACHE_SECONDS
            if self._manifest_cache and fresh and not refresh:
                return dict(self._manifest_cache)
        try:
            root = self._plugins_root()
        except Exception:
            root = None
        manifests = discover_manifests(root)
        with self._lock:
            self._manifest_cache = manifests
            self._manifest_cache_at = now
        return dict(manifests)

    def manifest(self, plugin_id: str, *, refresh: bool = False) -> SendToManifest | None:
        return self.manifests(refresh=refresh).get(str(plugin_id or "").strip())

    def targets(self) -> list[dict[str, Any]]:
        """Every slot of every installed SendTo-capable plugin."""
        out: list[dict[str, Any]] = []
        for manifest in sorted(self.manifests().values(), key=lambda item: item.plugin_label.casefold()):
            for target in manifest.targets:
                out.append({
                    "plugin": manifest.plugin,
                    "plugin_label": manifest.plugin_label,
                    "slot": target.slot,
                    "label": target.label,
                    "tab": manifest.tab,
                    "accepts": list(manifest.accepts),
                    "enabled": self._plugin_enabled(manifest.plugin),
                })
        return out

    def _plugin_enabled(self, plugin_id: str) -> bool:
        # No registry context (tests, CLI) means installed-and-usable is the best
        # answer we have; the bridge re-checks at delivery time.
        if self._is_enabled is None:
            return True
        try:
            return bool(self._is_enabled(plugin_id))
        except Exception:
            return False

    # -- hand-offs ------------------------------------------------------
    def create(self, path: str, kind: str, plugin_id: str, slot: str) -> Handoff:
        manifest = self.manifest(plugin_id)
        if manifest is None:
            raise SendToError(409, f"Plugin '{plugin_id}' is not installed or does not accept sends.")
        # The API listing may already know the plugin is disabled, but the
        # choice arrives from the client: refuse here instead of parking a
        # hand-off whose bridge delivery can only fail.
        if not self._plugin_enabled(manifest.plugin):
            raise SendToError(409, f"{manifest.plugin_label} is disabled in the WanGP Plugin Manager.")
        slot_label = manifest.slot_label(slot)
        if slot_label is None:
            raise SendToError(
                400,
                f"Slot '{slot}' is not offered by {manifest.plugin_label}.",
                extra={"slots": list(manifest.slots())},
            )
        if not manifest.accepts_kind(kind):
            raise SendToError(
                400,
                f"{manifest.plugin_label} accepts {', '.join(manifest.accepts) or 'nothing'} - not {kind}.",
                extra={"accepts": list(manifest.accepts), "kind": kind},
            )
        if not os.path.isfile(path):
            raise SendToError(404, "The media file no longer exists.")
        now = self._clock()
        handoff = Handoff(
            handoff_id=secrets.token_urlsafe(18),
            path=os.path.abspath(path),
            name=os.path.basename(path),
            kind=kind,
            plugin=manifest.plugin,
            plugin_label=manifest.plugin_label,
            slot=slot,
            slot_label=slot_label,
            tab=manifest.tab,
            inbox_key=manifest.inbox_key,
            created_at=now,
            expires_at=now + self._ttl,
        )
        with self._lock:
            self._prune(now)
            self._handoffs[handoff.handoff_id] = handoff
            while len(self._handoffs) > self._limit:
                oldest = min(self._handoffs.values(), key=lambda item: item.created_at)
                self._handoffs.pop(oldest.handoff_id, None)
        return handoff

    def peek(self, handoff_id: str) -> Handoff | None:
        with self._lock:
            self._prune(self._clock())
            return self._handoffs.get(str(handoff_id or "").strip())

    def take(self, handoff_id: str) -> Handoff | None:
        """Claim a hand-off exactly once (the bridge's side of the contract)."""
        handoff_id = str(handoff_id or "").strip()
        now = self._clock()
        with self._lock:
            self._prune(now)
            handoff = self._handoffs.pop(handoff_id, None)
            if handoff is None:
                return None
            self._consumed[handoff_id] = None
            if len(self._consumed) > CONSUMED_HISTORY:
                self._consumed.pop(next(iter(self._consumed)))
            return handoff

    def finish(self, handoff_id: str, result: str) -> None:
        with self._lock:
            if handoff_id in self._consumed:
                self._consumed[handoff_id] = result

    def delivery(self, handoff_id: str) -> str | None:
        with self._lock:
            return self._consumed.get(handoff_id)

    def status(self, handoff_id: str) -> str:
        handoff_id = str(handoff_id or "").strip()
        if not handoff_id:
            return "unknown"
        with self._lock:
            self._prune(self._clock())
            if handoff_id in self._handoffs:
                return "pending"
            return "consumed" if handoff_id in self._consumed else "expired"

    def pending(self) -> int:
        with self._lock:
            self._prune(self._clock())
            return len(self._handoffs)

    def _prune(self, now: float) -> None:
        for key in [key for key, item in self._handoffs.items() if item.expires_at <= now]:
            self._handoffs.pop(key, None)
