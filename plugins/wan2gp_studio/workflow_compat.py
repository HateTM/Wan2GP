# Copyright (c) 2026 WanGP Studio contributors - part of WanGP, WanGP Community License 2.0 (see LICENSE.txt)
"""Adapter over the optional wanflow-ui plugin (Workflow Integration, variant B).

Everything that touches wanflow-ui's modules or WanGP's private session state
lives here, so a wanflow-ui update or removal degrades the Studio workflow
section instead of breaking the rest of the app.

Public surface is deliberately small: availability info, catalog, workflow
storage, validation, runs (start / snapshot / events / cancel).
"""
from __future__ import annotations

import copy
import importlib
import json
import logging
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("wangp.studio")

PLUGIN_ID = "wan2gp-wanflow-ui"

# Run bookkeeping limits (M7 hardening): never drop an active run,
# keep a bounded terminal history with a TTL.
MAX_ACTIVE_RUNS = 3
MAX_TERMINAL_RUNS = 47
TERMINAL_RUN_TTL_SECONDS = 2 * 3600


class WorkflowUnavailable(RuntimeError):
    """Raised when the optional wanflow-ui plugin cannot serve the request."""


class WorkflowImportError(ValueError):
    """Raised when an imported workflow cannot be mapped to the canonical schema."""

    def __init__(self, message: str, *, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.report = report or {}


class WorkflowLimitError(RuntimeError):
    """Raised when too many workflow runs are active at once."""


def _model_defs(host: Any) -> dict[str, dict[str, Any]]:
    """Same enrichment wanflow-ui applies for its own node library."""
    try:
        records = host.list_model_defs() or []
    except Exception:
        records = []
    result: dict[str, dict[str, Any]] = {}
    resolve_base = getattr(host, "get_base_model_type", None)
    resolve_parent = getattr(host, "get_parent_model_type", None)
    resolve_family = getattr(host, "get_model_family", None)
    get_default_settings = getattr(host, "get_default_settings", None)

    def resolve(function: Any, key: str, **kwargs: Any) -> str:
        if not callable(function):
            return ""
        try:
            value = function(key, **kwargs)
        except TypeError:
            try:
                value = function(key)
            except Exception:
                value = ""
        except Exception:
            value = ""
        return str(value or "").strip()

    for record in records:
        if not isinstance(record, dict):
            continue
        key = str(record.get("model_type") or record.get("architecture") or "").strip()
        if not key:
            continue
        enriched = copy.deepcopy(record)
        base = resolve(resolve_base, key)
        parent = resolve(resolve_parent, key)
        family = resolve(resolve_family, key, for_ui=True)
        raw_base = str(record.get("base_model_type") or record.get("architecture") or key).strip()
        enriched["base_model_type"] = base or raw_base
        enriched["parent_model_type"] = parent or str(record.get("parent_model_type") or "").strip()
        enriched["lora_family"] = family or str(record.get("lora_family") or record.get("family") or parent or base or raw_base)
        enriched["lora_family_name"] = str(
            record.get("lora_family_name")
            or record.get("family_name")
            or record.get("model_family_name")
            or enriched["lora_family"]
        ).strip()
        if callable(get_default_settings):
            try:
                defaults = get_default_settings(key)
            except Exception:
                defaults = None
            if isinstance(defaults, dict):
                merged = copy.deepcopy(enriched.get("default_settings") or {})
                merged.update(copy.deepcopy(defaults))
                enriched["default_settings"] = merged
        result[key] = enriched
    return result


def _processes() -> list[dict[str, Any]]:
    """Postprocessors discovered from the installed WanGP catalog."""
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    try:
        from postprocessing.catalog import query_processes
    except Exception:
        return result
    for media_type in ("image", "video", "audio"):
        try:
            values = query_processes(media_type, enabled_only=False)
        except Exception:
            values = []
        for value in values:
            key = (str(value.get("type") or ""), str(value.get("id") or ""))
            if key not in seen:
                seen.add(key)
                result.append(value)
    return result


def _loras(host: Any, model_defs: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    get_lora_dir = getattr(host, "get_lora_dir", None)
    if not callable(get_lora_dir):
        return result
    for model_type, model_def in model_defs.items():
        if model_def.get("no_lora", False):
            continue
        try:
            root = Path(get_lora_dir(model_type))
            if not root.is_dir():
                continue
            result[model_type] = sorted(
                {
                    str(path.relative_to(root)).replace("\\", "/")
                    for suffix in ("*.safetensors", "*.sft")
                    for path in root.rglob(suffix)
                    if path.is_file()
                },
                key=str.casefold,
            )
        except Exception:
            continue
    return result


class WorkflowCompat:
    """Variant-B facade: Studio talks to wanflow-ui in-process, never duplicating it."""

    def __init__(
        self,
        host: Any,
        plugins_root: str | Path | None = None,
        loader: Callable[[], dict[str, Any]] | None = None,
        output_root: str | Path | None = None,
        enabled_provider: Callable[[], bool] | None = None,
        min_version: str = "0.0.0",
    ) -> None:
        self.host = host
        self.plugins_root = Path(plugins_root) if plugins_root else Path(__file__).resolve().parents[1]
        self.plugin_dir = self.plugins_root / PLUGIN_ID
        self._loader = loader
        self._enabled_provider = enabled_provider
        self.min_version = str(min_version)
        self._modules: dict[str, Any] | None = None
        self._lock = threading.RLock()
        self._catalog: dict[str, Any] | None = None
        self._catalog_at = 0.0
        self._runs: dict[str, dict[str, Any]] = {}
        self._run_order: list[str] = []
        self._output_root = Path(output_root) if output_root else self.plugin_dir / "workflow_outputs"
        self._meta_cache: dict[str, Any] | None = None

    # -- discovery -----------------------------------------------------
    @staticmethod
    def _version_tuple(value: Any) -> tuple[int, ...]:
        parts: list[int] = []
        for chunk in str(value or "0").replace("-", ".").split("."):
            digits = ""
            for character in chunk:
                if character.isdigit():
                    digits += character
                else:
                    break
            parts.append(int(digits) if digits else 0)
        return tuple(parts[:4]) or (0,)

    def _meta(self) -> dict[str, Any]:
        if self._meta_cache is not None:
            return self._meta_cache
        info_path = self.plugin_dir / "plugin_info.json"
        if info_path.is_file():
            try:
                self._meta_cache = json.loads(info_path.read_text(encoding="utf-8"))
            except Exception:
                self._meta_cache = {}
        return self._meta_cache or {}

    def version(self) -> str:
        return str(self._meta().get("version") or "0")

    def version_ok(self) -> bool:
        return self._version_tuple(self.version()) >= self._version_tuple(self.min_version)

    def enabled(self) -> bool:
        if self._enabled_provider is None:
            return True
        try:
            return bool(self._enabled_provider())
        except Exception:
            return False

    def state(self) -> str:
        installed = self._loader is not None or (self.plugin_dir / "plugin.py").is_file()
        if not installed:
            return "not_installed"
        if not self.enabled():
            return "disabled"
        if not self.version_ok():
            return "incompatible"
        return "available"

    def available(self) -> bool:
        return self.state() == "available"

    def info(self) -> dict[str, Any]:
        meta = self._meta()
        return {
            "id": PLUGIN_ID,
            "name": meta.get("name") or "WanGP WanFlow UI",
            "version": meta.get("version"),
            "min_version": self.min_version,
            "installed": self.state() != "not_installed",
            "integration": "L2",
            "license": "Apache-2.0",
            "state": self.state(),
            "path": str(self.plugin_dir),
        }

    def _load_modules(self) -> dict[str, Any]:
        if self._modules is not None:
            return self._modules
        with self._lock:
            if self._modules is not None:
                return self._modules
            if self._loader is not None:
                modules = dict(self._loader())
            else:
                state = self.state()
                if state != "available":
                    raise WorkflowUnavailable(f"WanFlow UI is {state} (plugins/wan2gp-wanflow-ui).")
                if str(self.plugins_root) not in sys.path:
                    sys.path.insert(0, str(self.plugins_root))
                modules = {}
                for name in ("graph_model", "graph_store", "block_store", "node_registry", "graph_runner"):
                    try:
                        modules[name] = importlib.import_module(f"{PLUGIN_ID}.{name}")
                    except Exception as exc:  # noqa: BLE001 - reported per module
                        modules[name] = exc
                if isinstance(modules.get("graph_model"), Exception):
                    raise WorkflowUnavailable(
                        f"WanFlow UI cannot be imported: {modules['graph_model']}"
                    )
            self._modules = modules
            return modules

    def _module(self, name: str) -> Any:
        module = self._load_modules().get(name)
        if module is None or isinstance(module, Exception):
            raise WorkflowUnavailable(f"WanFlow UI module '{name}' is unavailable: {module}")
        return module

    # -- catalog -------------------------------------------------------
    def catalog(self, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if not refresh and self._catalog is not None and time.time() - self._catalog_at < 60:
                return self._catalog
            registry = self._module("node_registry")
            model_defs = _model_defs(self.host)
            catalog = registry.build_catalog(model_defs, _processes(), _loras(self.host, model_defs), None)
            try:
                blocks = self._module("block_store").BlockStore(self.plugin_dir / "blocks")
                catalog["blocks"] = blocks.catalog()
            except Exception:
                catalog["blocks"] = []
            self._catalog = catalog
            self._catalog_at = time.time()
            return catalog

    # -- workflow storage ---------------------------------------------
    def _graph_store(self) -> Any:
        return self._module("graph_store").GraphStore(self.plugin_dir / "workflows")

    def workflows(self) -> list[dict[str, Any]]:
        store = self._graph_store()
        return [{"id": slug, "name": name} for name, slug in store.choices()]

    def load(self, slug: str) -> dict[str, Any]:
        return self._graph_store().load(slug)

    def save(self, graph: dict[str, Any], name: str | None = None) -> dict[str, Any]:
        title = name or str(graph.get("name") or "Workflow")
        normalized, path = self._graph_store().save(graph, title)
        return {"graph": normalized, "id": path.stem}

    def delete(self, slug: str) -> None:
        self._graph_store().delete(slug)

    def save_block(self, graph: dict[str, Any], name: str | None = None) -> dict[str, Any]:
        """Persist the selected group as a reusable block (same semantics as wanflow-ui)."""
        blocks = self._module("block_store").BlockStore(self.plugin_dir / "blocks")
        group_id = str((graph.get("ui") or {}).get("selected_group_id") or "")
        if not group_id:
            raise ValueError("Select a group before saving it as a reusable block.")
        group = next((item for item in graph.get("groups") or [] if item.get("id") == group_id), None)
        if not group:
            raise ValueError("The selected group does not exist.")
        path = blocks.save_group(graph, group_id, name or group.get("title"))
        self._catalog = None
        return {"id": path.stem, "name": str(name or group.get("title") or path.stem)}

    def delete_block(self, block_id: str) -> dict[str, Any]:
        blocks = self._module("block_store").BlockStore(self.plugin_dir / "blocks")
        try:
            path = blocks.delete(block_id)
        except FileNotFoundError as exc:
            raise KeyError(f"Reusable block not found: {block_id}") from exc
        self._catalog = None
        return {"id": path.stem}

    def node_types(self) -> set[str]:
        try:
            catalog = self.catalog()
            return {str(node.get("type")) for node in catalog.get("nodes") or [] if node.get("type")}
        except Exception:
            return set()

    def export_workflow(self, slug: str, fmt: str = "wanflow") -> dict[str, Any]:
        graph = self.load(slug)
        if str(fmt).lower() in ("comfyui-ui", "ui"):
            return self._export_comfyui_ui(graph)
        model = self._module("graph_model")
        if str(fmt).lower() in ("comfyui", "comfyui-api"):
            node_keys = {}
            for node in graph.get("nodes") or []:
                comfy = (node.get("params") or {}).get("comfyui") if isinstance(node.get("params"), dict) else None
                if isinstance(comfy, dict) and comfy.get("key"):
                    node_keys[node.get("id")] = str(comfy["key"])
            prompt: dict[str, Any] = {}
            for node in graph.get("nodes") or []:
                params = node.get("params") if isinstance(node.get("params"), dict) else {}
                comfy = params.get("comfyui")
                if not isinstance(comfy, dict) or not comfy.get("key"):
                    continue
                inputs = copy.deepcopy(comfy.get("inputs") or {})
                for value in inputs.values():
                    if isinstance(value, list) and value and node_keys.get("c" + str(value[0])):
                        value[0] = node_keys["c" + str(value[0])]
                prompt[str(comfy["key"])] = {
                    "class_type": comfy.get("class_type"),
                    "inputs": inputs,
                    "_meta": {"title": node.get("title") or comfy.get("class_type")},
                }
            if not prompt:
                raise WorkflowImportError(
                    "Workflow has no ComfyUI nodes to export.",
                    report={"format": "comfyui", "nodes": 0},
                )
            return {"format": "comfyui-api", "prompt": prompt}
        return {
            "schema": getattr(model, "SCHEMA", "wan2gp-wanflow-ui"),
            "version": getattr(model, "VERSION", 1),
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "graph": graph,
        }

    @staticmethod
    def _looks_like_comfyui(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        if "links" in payload and isinstance(payload.get("nodes"), list):
            return True
        prompt = payload.get("prompt")
        if isinstance(prompt, dict) and prompt:
            return all(isinstance(value, dict) and "class_type" in value for value in prompt.values())
        return False

    @staticmethod
    def _comfy_map(payload: Any) -> dict[str, Any] | None:
        """Return a ComfyUI API prompt map (class_type entries) when present."""
        if not isinstance(payload, dict):
            return None
        candidates = [payload]
        prompt = payload.get("prompt")
        if isinstance(prompt, dict):
            candidates.insert(0, prompt)
        for candidate in candidates:
            if candidate and all(isinstance(value, dict) and "class_type" in value for value in candidate.values()):
                return candidate
        return None

    def _import_comfyui(self, prompt: dict[str, Any], name: str | None) -> dict[str, Any]:
        """Preserve a ComfyUI API graph as opaque nodes (import/export adapter, no execution)."""
        model = self._module("graph_model")
        title = str(name or "ComfyUI import")
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for key, spec in prompt.items():
            node_id = "c" + str(key)
            inputs = copy.deepcopy(spec.get("inputs") or {})
            for value in inputs.values():
                if isinstance(value, list) and value and str(value[0]) in prompt and str(value[0]) != str(key):
                    edges.append({
                        "id": uuid.uuid4().hex,
                        "source": {"node": "c" + str(value[0]), "port": "out"},
                        "target": {"node": node_id, "port": "in"},
                        "type": "",
                    })
            nodes.append({
                "id": node_id,
                "type": "comfyui_node",
                "title": str(spec.get("class_type") or key),
                "params": {"comfyui": {"key": str(key), "class_type": spec.get("class_type"), "inputs": inputs}},
                "enabled": True,
            })
        graph = {"name": title, "nodes": nodes, "edges": edges, "groups": []}
        normalized = model.normalize_graph(graph)
        normalized["name"] = title
        known = self.node_types()
        unknown = ["comfyui_node"] if known and "comfyui_node" not in known else []
        saved = self.save(normalized, title)
        return {
            "id": saved["id"],
            "name": normalized.get("name") or title,
            "legacy": False,
            "unknown_nodes": unknown,
            "warnings": ["ComfyUI nodes are preserved as opaque nodes; they are not executable in WanGP yet."],
            "node_count": len(nodes),
            "report": {"format": "comfyui", "opaque": True, "executable": False},
        }

    @staticmethod
    def _looks_like_comfyui_ui(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        nodes = payload.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            return False
        if "edges" in payload or not isinstance(payload.get("links"), list):
            return False
        return any(isinstance(node, dict) and node.get("type") for node in nodes)

    def _import_comfyui_ui(self, payload: dict[str, Any], name: str | None) -> dict[str, Any]:
        """Import ComfyUI UI-format JSON: layout, values and links are preserved as opaque nodes."""
        model = self._module("graph_model")
        raw_links = copy.deepcopy(payload.get("links")) if isinstance(payload.get("links"), list) else []
        ui_meta = {
            "links": raw_links,
            "groups": copy.deepcopy(payload.get("groups") or []),
            "config": copy.deepcopy(payload.get("config") or {}),
            "extra": copy.deepcopy(payload.get("extra") or {}),
            "last_node_id": payload.get("last_node_id"),
            "last_link_id": payload.get("last_link_id"),
        }
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for spec in payload.get("nodes") or []:
            if not isinstance(spec, dict) or "id" not in spec:
                continue
            key = str(spec.get("id"))
            pos = spec.get("pos") or [0, 0]
            comfy = {
                "format": "ui",
                "key": key,
                "class_type": str(spec.get("type") or ""),
                "mode": spec.get("mode"),
                "properties": copy.deepcopy(spec.get("properties") or {}),
                "widgets_values": copy.deepcopy(spec.get("widgets_values")),
                "inputs": copy.deepcopy(spec.get("inputs") or []),
                "outputs": copy.deepcopy(spec.get("outputs") or []),
                "pos": list(pos),
                "flags": copy.deepcopy(spec.get("flags") or {}),
                "order": spec.get("order"),
                "size": copy.deepcopy(spec.get("size")),
            }
            nodes.append({
                "id": "c" + key,
                "type": "comfyui_node",
                "title": str(spec.get("title") or comfy["class_type"] or key),
                "position": {"x": float(pos[0]) if len(pos) > 0 else 0, "y": float(pos[1]) if len(pos) > 1 else 0},
                "params": {"comfyui": comfy},
                "enabled": spec.get("mode", 0) != 4,
            })
        for link in raw_links:
            if not isinstance(link, list) or len(link) < 5:
                continue
            link_id, src, src_slot, tgt, tgt_slot = link[0], link[1], link[2], link[3], link[4]
            ltype = str(link[5]) if len(link) > 5 else ""
            edges.append({
                "id": "l" + str(link_id),
                "source": {"node": "c" + str(src), "port": "out" + str(src_slot)},
                "target": {"node": "c" + str(tgt), "port": "in" + str(tgt_slot)},
                "type": ltype,
            })
        graph = {
            "name": str(name or "ComfyUI UI import"),
            "nodes": nodes,
            "edges": edges,
            "groups": [],
            # ComfyUI canvas metadata belongs to the whole workflow, not to every
            # node: duplicating it per node multiplied large link/group payloads.
            "ui": {"comfyui_ui": copy.deepcopy(ui_meta)},
        }
        normalized = model.normalize_graph(graph)
        normalized["name"] = str(name or "ComfyUI UI import")
        known = self.node_types()
        unknown = ["comfyui_node"] if known and "comfyui_node" not in known else []
        title = str(name or normalized.get("name") or "ComfyUI UI import")
        saved = self.save(normalized, title)
        return {
            "id": saved["id"],
            "name": normalized.get("name") or title,
            "legacy": False,
            "unknown_nodes": unknown,
            "warnings": [
                "ComfyUI UI-format imported as opaque nodes: layout and values are preserved, execution is not supported yet."
            ],
            "node_count": len(nodes),
            "report": {"format": "comfyui-ui", "opaque": True, "executable": False, "links": len(edges)},
        }

    def _export_comfyui_ui(self, graph: dict[str, Any]) -> dict[str, Any]:
        """Export an editable graph back to ComfyUI UI format.

        Nodes keep their current Studio position, while ``links``,
        ``inputs[].link`` and ``outputs[].links`` are rebuilt from
        ``graph.edges`` so deleting or re-wiring nodes cannot leave dangling
        references. Canvas metadata (groups/config/extra) lives on the graph
        (``graph.ui.comfyui_ui``); older workflows that still carry a per-node
        ``ui_meta`` copy are read as a fallback.
        """
        graph_ui = graph.get("ui") if isinstance(graph.get("ui"), dict) else {}
        graph_ui_meta = graph_ui.get("comfyui_ui") if isinstance(graph_ui.get("comfyui_ui"), dict) else None
        comfy_nodes: list[tuple[dict[str, Any], dict[str, Any], int]] = []
        legacy_ui_meta: dict[str, Any] | None = None
        for node in graph.get("nodes") or []:
            params = node.get("params") if isinstance(node.get("params"), dict) else {}
            comfy = params.get("comfyui")
            if not (isinstance(comfy, dict) and comfy.get("format") == "ui"):
                continue
            try:
                key = int(comfy.get("key"))
            except (TypeError, ValueError):
                continue
            comfy_nodes.append((node, comfy, key))
            if legacy_ui_meta is None and isinstance(comfy.get("ui_meta"), dict):
                legacy_ui_meta = comfy["ui_meta"]
        if not comfy_nodes:
            raise WorkflowImportError(
                "Workflow has no ComfyUI UI nodes to export.",
                report={"format": "comfyui-ui", "nodes": 0},
            )
        ui_meta = graph_ui_meta or legacy_ui_meta or {}
        node_key = {str(node.get("id")): key for node, _, key in comfy_nodes}
        by_key = {key: comfy for _, comfy, key in comfy_nodes}

        def slot_index(port: Any) -> int | None:
            text = str(port or "").strip()
            for prefix in ("out", "in"):
                if text.startswith(prefix):
                    text = text[len(prefix):]
                    break
            try:
                value = int(text)
            except (TypeError, ValueError):
                return None
            return value if value >= 0 else None

        def slot_count(comfy: dict[str, Any], field: str) -> int:
            items = comfy.get(field)
            return len(items) if isinstance(items, list) else 0

        original_links = [link for link in (ui_meta.get("links") or []) if isinstance(link, list) and len(link) >= 5]
        original_by_connection: dict[tuple[int, int, int, int, str], int] = {}
        try:
            next_link_id = int(ui_meta.get("last_link_id") or 0)
        except (TypeError, ValueError):
            next_link_id = 0
        for link in original_links:
            try:
                link_id = int(link[0])
                signature = (
                    int(link[1]), int(link[2]), int(link[3]), int(link[4]),
                    "" if len(link) < 6 or link[5] is None else str(link[5]),
                )
            except (TypeError, ValueError):
                continue
            next_link_id = max(next_link_id, link_id)
            original_by_connection.setdefault(signature, link_id)

        links: list[list[Any]] = []
        incoming: dict[tuple[int, int], int] = {}
        outgoing: dict[tuple[int, int], list[int]] = {}
        used_link_ids: set[int] = set()
        for edge in graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            source = edge.get("source") if isinstance(edge.get("source"), dict) else {}
            target = edge.get("target") if isinstance(edge.get("target"), dict) else {}
            source_key = node_key.get(str(source.get("node") or ""))
            target_key = node_key.get(str(target.get("node") or ""))
            source_slot = slot_index(source.get("port"))
            target_slot = slot_index(target.get("port"))
            if source_key is None or target_key is None or source_slot is None or target_slot is None:
                continue
            if source_slot >= slot_count(by_key[source_key], "outputs"):
                continue
            if target_slot >= slot_count(by_key[target_key], "inputs"):
                continue
            link_type = "" if edge.get("type") is None else str(edge.get("type"))
            link_id = original_by_connection.get((source_key, source_slot, target_key, target_slot, link_type))
            if link_id is None or link_id in used_link_ids:
                next_link_id += 1
                link_id = next_link_id
            used_link_ids.add(link_id)
            links.append([link_id, source_key, source_slot, target_key, target_slot, link_type])
            incoming[(target_key, target_slot)] = link_id
            outgoing.setdefault((source_key, source_slot), []).append(link_id)

        node_specs: list[dict[str, Any]] = []
        last_node_id = int(ui_meta.get("last_node_id") or 0)
        for node, comfy, key in comfy_nodes:
            last_node_id = max(last_node_id, key)
            position = node.get("position") or {}
            spec = {
                "id": key,
                "type": comfy.get("class_type"),
                "title": node.get("title"),
                "mode": comfy.get("mode") if comfy.get("mode") is not None else 0,
                "pos": [float(position.get("x", 0)) if isinstance(position, dict) else 0,
                        float(position.get("y", 0)) if isinstance(position, dict) else 0],
                "properties": copy.deepcopy(comfy.get("properties") or {}),
                "widgets_values": copy.deepcopy(comfy.get("widgets_values")),
                "inputs": copy.deepcopy(comfy.get("inputs") or []),
                "outputs": copy.deepcopy(comfy.get("outputs") or []),
                "order": comfy.get("order") if comfy.get("order") is not None else 0,
                "flags": copy.deepcopy(comfy.get("flags") or {}),
            }
            if comfy.get("size") is not None:
                spec["size"] = copy.deepcopy(comfy["size"])
            if isinstance(spec["inputs"], list):
                for index, item in enumerate(spec["inputs"]):
                    if isinstance(item, dict):
                        item["link"] = incoming.get((key, index))
            if isinstance(spec["outputs"], list):
                for index, item in enumerate(spec["outputs"]):
                    if isinstance(item, dict):
                        item["links"] = list(outgoing.get((key, index), []))
            node_specs.append(spec)

        return {
            "format": "comfyui-ui",
            "last_node_id": last_node_id,
            "last_link_id": next_link_id,
            "nodes": node_specs,
            "links": links,
            "groups": copy.deepcopy(ui_meta.get("groups") or []),
            "config": copy.deepcopy(ui_meta.get("config") or {}),
            "extra": copy.deepcopy(ui_meta.get("extra") or {}),
            "version": 0.4,
        }

    def import_workflow(self, payload: Any, name: str | None = None) -> dict[str, Any]:
        """Import a canonical or legacy JSON workflow; unknown nodes stay in the graph."""
        if not isinstance(payload, dict):
            raise WorkflowImportError("Import payload must be a JSON object.")
        graph = payload.get("graph") if isinstance(payload.get("graph"), dict) else payload
        comfy = self._comfy_map(payload) or self._comfy_map(graph)
        if comfy is not None:
            return self._import_comfyui(comfy, name)
        if self._looks_like_comfyui_ui(payload) or self._looks_like_comfyui_ui(graph):
            return self._import_comfyui_ui(graph if self._looks_like_comfyui_ui(graph) else payload, name)
        if self._looks_like_comfyui(payload) or self._looks_like_comfyui(graph):
            raise WorkflowImportError(
                "Unsupported ComfyUI graph: neither API (prompt) nor UI-format could be recognised.",
                report={"format": "comfyui", "supported": False},
            )
        model = self._module("graph_model")
        schema = str(graph.get("schema") or "")
        legacy_schema = str(getattr(model, "LEGACY_SCHEMA", "wan2gp-workflows-v2"))
        legacy = schema == legacy_schema or isinstance(graph.get("stages"), list)
        try:
            source = graph
            if legacy and hasattr(model, "migrate_v1_workflow"):
                source = model.migrate_v1_workflow(graph)
            normalized = model.normalize_graph(source)
            validation = self.validate(normalized)
        except Exception as exc:
            raise WorkflowImportError(f"Invalid workflow JSON: {exc}") from exc
        known = self.node_types()
        unknown = sorted({
            str(node.get("type"))
            for node in normalized.get("nodes") or []
            if node.get("type") and known and str(node.get("type")) not in known
        })
        if not validation["ok"]:
            raise WorkflowImportError(
                "; ".join(validation["errors"]) or "Invalid workflow",
                report={"errors": validation["errors"], "legacy": legacy, "unknown_nodes": unknown},
            )
        title = str(name or normalized.get("name") or "Imported workflow")
        saved = self.save(normalized, title)
        return {
            "id": saved["id"],
            "name": normalized.get("name") or title,
            "legacy": legacy,
            "unknown_nodes": unknown,
            "warnings": validation["warnings"],
            "node_count": len(normalized.get("nodes") or []),
        }

    def validate(self, graph: dict[str, Any]) -> dict[str, Any]:
        model = self._module("graph_model")
        normalized = model.normalize_graph(graph)
        errors: list[str] = []
        order: list[str] | None = None
        try:
            model.validate_graph(normalized)
            order = list(model.topological_order(normalized))
        except Exception as exc:
            errors.append(str(exc))
        return {
            "ok": not errors,
            "errors": errors,
            "order": order,
            "warnings": list(normalized.get("warnings") or []),
        }

    # -- runs ----------------------------------------------------------
    def _emit(self, record: dict[str, Any], kind: str, data: Any = None) -> None:
        with self._lock:
            record["events"].append({
                "id": record["next_event"],
                "kind": kind,
                "data": data,
                "timestamp": time.time(),
            })
            record["next_event"] += 1
            record["updated_at"] = time.time()

    def _bind_session(self, session: Any) -> None:
        """GradioWanGPSession keeps its request binding in a thread-local."""
        local = getattr(session, "_ui_local", None)
        if local is None:
            return
        context = {
            name: getattr(local, name, None)
            for name in ("call_id", "defer_load_queue_trigger", "bound_state", "bound_gradio_context")
        }
        for name, value in context.items():
            try:
                setattr(local, name, value)
            except Exception:
                pass

    def start_run(self, graph: dict[str, Any], inputs: list[str] | None = None) -> dict[str, Any]:
        modules = self._load_modules()
        model = self._module("graph_model")
        normalized = model.normalize_graph(graph)
        validation = self.validate(normalized)
        if not validation["ok"]:
            raise ValueError("; ".join(validation["errors"]) or "Invalid workflow")
        with self._lock:
            active = sum(1 for record in self._runs.values() if record["status"] not in {"completed", "failed", "cancelled"})
            if active >= MAX_ACTIVE_RUNS:
                raise WorkflowLimitError(
                    f"Too many active workflow runs ({active}/{MAX_ACTIVE_RUNS}). Cancel one first."
                )
            run_id = uuid.uuid4().hex
            record = {
                "id": run_id,
                "status": "running",
                "progress": 0,
                "message": "Starting workflow…",
                "nodes": {
                    node["id"]: ("queued" if node.get("enabled", True) else "skipped")
                    for node in normalized.get("nodes") or []
                },
                "outputs": [],
                "variables": {},
                "errors": [],
                "cancel_requested": False,
                "created_at": time.time(),
                "updated_at": time.time(),
                "events": deque(maxlen=400),
                "next_event": 1,
            }
            self._runs[run_id] = record
            self._run_order.append(run_id)
            self._prune_runs()
        thread = threading.Thread(
            target=self._run_worker,
            args=(record, normalized, list(inputs or []), modules.get("graph_runner")),
            name=f"studio-workflow-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return {"run_id": run_id, "status": "running", "nodes": dict(record["nodes"])}

    def _run_worker(self, record: dict[str, Any], graph: dict[str, Any], inputs: list[str], runner: Any) -> None:
        release = None
        honoring_release = getattr(runner, "release_workflow_models", None)
        graph_types = {node.get("id"): node.get("type") for node in (graph.get("nodes") or [])}
        try:
            if runner is None or isinstance(runner, Exception):
                raise WorkflowUnavailable(f"WanFlow UI runner is unavailable: {runner}")
            session = self.host.get_session()
            self._bind_session(session)

            def progress(status: str, value: float) -> None:
                try:
                    record["progress"] = max(0, min(100, int(float(value or 0))))
                except Exception:
                    record["progress"] = 0
                record["message"] = f"{status} ({record['progress']}%)" if status else record["message"]
                self._emit(record, "progress", {"progress": record["progress"], "message": status})

            def node_event(node_id: str, state: str, result: Any) -> None:
                record["nodes"][node_id] = state
                self._emit(record, "node", {"node_id": node_id, "state": state})

            outputs, variables = runner.run_graph(
                self.host,
                session,
                {},
                graph,
                inputs,
                output_root=self._output_root,
                callback=progress,
                cancel_check=lambda: record["cancel_requested"],
                node_callback=node_event,
            )
            record["outputs"] = list(outputs or [])
            for output in outputs or []:
                self._write_output_sidecar(output, record["id"], str(graph.get("name") or "Workflow"), graph)
            record["variables"] = dict(variables or {})
            # Cancellation always wins, even with partial outputs on disk:
            # the record keeps them, but the status is unambiguous.
            record["status"] = "cancelled" if record["cancel_requested"] else "completed"
            record["partial"] = bool(record["cancel_requested"] and outputs)
            record["progress"] = 100 if record["status"] == "completed" else record["progress"]
            record["message"] = record["status"].capitalize()
            self._emit(record, "complete", {"status": record["status"], "outputs": record["outputs"]})
        except InterruptedError:
            record["status"] = "cancelled"
            record["message"] = "Cancelled"
            for node_id, node_state in list(record["nodes"].items()):
                if node_state == "running":
                    record["nodes"][node_id] = "cancelled"
            self._emit(record, "complete", {"status": "cancelled", "outputs": []})
        except Exception as exc:  # noqa: BLE001 - any failure becomes a run error
            record["status"] = "failed"
            record["errors"].append(f"{type(exc).__name__}: {exc}")
            record["message"] = str(exc)
            for node_id, node_state in list(record["nodes"].items()):
                if node_state == "running":
                    record["nodes"][node_id] = "error"
            self._emit(record, "error", {"message": str(exc)})
        finally:
            try:
                # A failed or cancelled generation run must not leave a stale
                # model in VRAM; a completed run honors the graph's unload
                # flags. A release never fires while another workflow is still
                # running, so it cannot interfere with concurrent work.
                generation_ran = any(
                    str(graph_types.get(node_id, "")).startswith(("generate", "edit_", "inpaint_"))
                    and node_state in ("running", "done")
                    for node_id, node_state in record["nodes"].items()
                )
                others_active = any(
                    other is not record and other.get("status") == "running"
                    for other in self._runs.values()
                )
                if not others_active:
                    if record["status"] in ("failed", "cancelled") and generation_ran:
                        always = getattr(runner, "release_loaded_model", None)
                        if callable(always):
                            always(self.host)
                    elif callable(honoring_release):
                        honoring_release(self.host, graph)
            except Exception as exc:
                logger.warning("model release failed for run %s: %s", record["id"], exc)
            self._emit(record, "closed", {"run_id": record["id"]})

    def _write_output_sidecar(self, path: str | Path, run_id: str, graph_name: str, graph: dict[str, Any] | None = None) -> None:
        """Link a produced file back to its workflow run.

        Only files inside this plugin's output root get a sidecar (imported
        inputs must not be touched). An existing sidecar - WanGP's own
        settings JSON - is merged, not replaced."""
        try:
            file_path = Path(path)
            if self._output_root not in file_path.parents:
                return
            sidecar = file_path.with_suffix(".json")
            data: dict[str, Any] = {}
            if sidecar.is_file():
                try:
                    loaded = json.loads(sidecar.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        data = loaded
                except ValueError:
                    data = {}
            workflow = data.get("workflow") if isinstance(data.get("workflow"), dict) else {}
            workflow.update({"run_id": str(run_id), "graph_name": str(graph_name)})
            # V4.3: keep the full normalized graph so the Gallery can re-open
            # the run's workflow even after a host restart.
            if isinstance(graph, dict) and graph.get("nodes"):
                workflow["nodes"] = copy.deepcopy(graph.get("nodes") or [])
                workflow["edges"] = copy.deepcopy(graph.get("edges") or [])
                workflow["settings"] = copy.deepcopy(graph.get("settings") or {})
            data["workflow"] = workflow
            sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def templates(self) -> list[dict[str, Any]]:
        """Built-in starter graphs (T2V, I2V, T2I) for the workflow toolbar.

        Built with the plugin's own graph_model so they always match the
        schema; validation runs in the tests."""
        model = self._module("graph_model")
        counter = {"i": 0}

        def node(node_type: str, **params: Any) -> dict[str, Any]:
            counter["i"] += 1
            return model.new_node(node_type, params=params)

        def text_body(body: str) -> dict[str, Any]:
            return node("text", text=body)

        resolution = node("resolution_config", resolution_tier="auto")
        prompt = text_body("Describe the shot: subject, motion, light, lens.")
        t2v = model.new_graph("Text → Video")
        gen_video = node("generate_video", model_type="wan2.1")
        t2v["nodes"] = [prompt, resolution, gen_video]
        t2v["edges"] = [
            {"source": {"node": prompt["id"], "port": "text"}, "target": {"node": gen_video["id"], "port": "prompt"}},
            {"source": {"node": resolution["id"], "port": "settings"}, "target": {"node": gen_video["id"], "port": "settings"}},
        ]

        i2v = model.new_graph("Image → Video")
        image_in = node("input_image", path="")
        gen_i2v = node("generate_video", model_type="wan2.1")
        i2v["nodes"] = [image_in, prompt, resolution, gen_i2v]
        i2v["edges"] = [
            {"source": {"node": image_in["id"], "port": "image"}, "target": {"node": gen_i2v["id"], "port": "image"}},
            {"source": {"node": prompt["id"], "port": "text"}, "target": {"node": gen_i2v["id"], "port": "prompt"}},
            {"source": {"node": resolution["id"], "port": "settings"}, "target": {"node": gen_i2v["id"], "port": "settings"}},
        ]

        t2i = model.new_graph("Text → Image")
        gen_image = node("generate_image", model_type="qwen_image")
        t2i["nodes"] = [prompt, resolution, gen_image]
        t2i["edges"] = [
            {"source": {"node": prompt["id"], "port": "text"}, "target": {"node": gen_image["id"], "port": "prompt"}},
            {"source": {"node": resolution["id"], "port": "settings"}, "target": {"node": gen_image["id"], "port": "settings"}},
        ]

        return [
            {"id": "template-t2v", "name": "Text → Video", "graph": t2v},
            {"id": "template-i2v", "name": "Image → Video", "graph": i2v},
            {"id": "template-t2i", "name": "Text → Image", "graph": t2i},
        ]

    def snapshot(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            return {
                "id": record["id"],
                "status": record["status"],
                "progress": record["progress"],
                "message": record["message"],
                "nodes": dict(record["nodes"]),
                "outputs": list(record["outputs"]),
                "variables": dict(record["variables"]),
                "errors": list(record["errors"]),
                "created_at": record["created_at"],
                "updated_at": record["updated_at"],
            }

    def events_after(self, run_id: str, cursor: int) -> tuple[list[dict[str, Any]], int] | None:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            events = [event for event in record["events"] if event["id"] > cursor]
            return events, record["next_event"] - 1

    def recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._run_order[-max(1, int(limit)):]
        runs = []
        for run_id in reversed(ids):
            snapshot = self.snapshot(run_id)
            if snapshot is not None:
                runs.append(snapshot)
        return runs

    def cancel(self, run_id: str) -> bool:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return False
            record["cancel_requested"] = True
            record["message"] = "Cancelling…"
        self._emit(record, "cancel_requested", {"run_id": run_id})
        return True

    def _prune_runs(self) -> None:
        """Drop expired terminal runs, cap terminal history, never touch active runs."""
        now = time.time()
        terminal = {"completed", "failed", "cancelled"}
        active: list[str] = []
        terminal_ids: list[str] = []
        for run_id in self._run_order:
            record = self._runs.get(run_id)
            if record is None:
                continue
            if record["status"] in terminal:
                if now - float(record.get("updated_at") or 0) <= TERMINAL_RUN_TTL_SECONDS:
                    terminal_ids.append(run_id)
                else:
                    self._runs.pop(run_id, None)
            else:
                active.append(run_id)
        terminal_ids = terminal_ids[-MAX_TERMINAL_RUNS:]
        self._run_order = active + terminal_ids
        self._runs = {run_id: self._runs[run_id] for run_id in self._run_order if run_id in self._runs}
