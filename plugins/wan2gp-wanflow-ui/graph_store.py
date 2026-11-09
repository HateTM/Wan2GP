from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from .graph_model import graph_for_json, normalize_graph


class GraphStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slug(value: Any) -> str:
        result = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "workflow").strip()).strip("-_").lower()
        return result[:80] or "workflow"

    def choices(self) -> list[tuple[str, str]]:
        result = []
        for path in sorted(self.root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                result.append((str(payload.get("name") or path.stem), path.stem))
            except (OSError, ValueError, TypeError):
                result.append((path.stem, path.stem))
        return result

    def save(self, graph: dict[str, Any], name: str, *, workflow_id: str | None = None) -> tuple[dict[str, Any], Path]:
        normalized = normalize_graph(graph)
        normalized["name"] = str(name or normalized.get("name") or "Workflow").strip()
        slug = self.slug(normalized["name"]) if workflow_id is None else workflow_id
        if not slug or slug in {".", ".."} or any(char in '/\\<>:"|?*' or ord(char) < 32 for char in slug):
            raise ValueError("Invalid workflow ID.")
        normalized["updated_at"] = int(time.time())
        target = self.root / f"{slug}.json"
        with tempfile.NamedTemporaryFile(dir=self.root, suffix=".tmp", delete=False, mode="w", encoding="utf-8") as handle:
            temporary = Path(handle.name)
            try:
                json.dump(graph_for_json(normalized), handle, indent=2, ensure_ascii=False)
                handle.close()
                temporary.replace(target)
            finally:
                handle.close()
                temporary.unlink(missing_ok=True)
        return normalized, target

    def _resolve(self, value: str) -> Path:
        """Resolve a workflow id: exact file name first (shipped files keep
        pretty names like 'LTX25-I2VA-T2VA-Qwen3.5.json'), then by comparing
        slugified file stems, then the slugified name itself."""
        value = str(value or "").strip()
        if value and "/" not in value and "\\" not in value and value not in {".", ".."}:
            exact = self.root / f"{value}.json"
            if exact.is_file():
                return exact
        wanted = self.slug(value)
        for path in sorted(self.root.glob("*.json")):
            if self.slug(path.stem) == wanted:
                return path
        return self.root / f"{wanted}.json"

    def load(self, slug: str) -> dict[str, Any]:
        target = self._resolve(slug)
        if not target.is_file():
            raise FileNotFoundError(target)
        return normalize_graph(json.loads(target.read_text(encoding="utf-8")))

    def delete(self, slug: str) -> None:
        target = self._resolve(slug)
        if target.is_file():
            target.unlink()

