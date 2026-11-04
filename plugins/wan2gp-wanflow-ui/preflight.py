"""Resource preflight for WanFlow UI graph runs.

Looks at the machine and at the models a graph is about to load, and reports the things that make
a run die half way: too little Windows commit memory for Wan2GP's pinned RAM (the "Memory
allocation failure" / out-of-memory at the first denoising step), too little free RAM or VRAM,
a full disk, several models kept resident, and model files that still have to be downloaded.

It only reports. The graph setting `preflight` chooses what happens next: "warn" (default) shows
the findings in the run's progress text, "block" refuses to start while any warning is open, and
"off" skips the check. A failure inside the check itself is never allowed to stop a run.

The estimates are deliberately simple and conservative (see `estimate_pinned_ram`); they come from
measurements on a 32 GB machine where a 13 GB checkpoint needed about 11 GB of pinned RAM.
"""
from __future__ import annotations

import ctypes
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

GIB = 1024 ** 3
COMMIT_MARGIN_GIB = 4.0  # headroom the rest of the system and the text encoder need on top of the pinned weights
MIN_FREE_VRAM_GIB = 3.0
MIN_FREE_DISK_GIB = 10.0
MODEL_FILE_SUFFIXES = (".safetensors", ".sft", ".gguf", ".pth", ".pt", ".bin", ".ckpt", ".onnx")
GENERATION_TYPES = {"generate_image", "edit_image", "inpaint_image", "generate_video", "edit_video", "inpaint_video", "generate_audio"}


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def system_snapshot(output_root: str | Path | None = None) -> dict[str, float | None]:
    """Bytes: RAM, commit (RAM + page file on Windows), VRAM and free disk. Unknown values are None."""
    snap: dict[str, float | None] = {key: None for key in ("ram_total", "ram_available", "commit_limit", "commit_available", "vram_total", "vram_free", "disk_free")}
    try:
        if os.name == "nt":
            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                snap.update(ram_total=status.ullTotalPhys, ram_available=status.ullAvailPhys, commit_limit=status.ullTotalPageFile, commit_available=status.ullAvailPageFile)
        else:
            import psutil
            memory = psutil.virtual_memory()
            snap.update(ram_total=memory.total, ram_available=memory.available)
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            snap.update(vram_free=free, vram_total=total)
    except Exception:
        pass
    try:
        if output_root is not None:
            folder = Path(output_root)
            while not folder.exists() and folder != folder.parent:
                folder = folder.parent
            snap["disk_free"] = shutil.disk_usage(folder).free
    except Exception:
        pass
    return snap


def reserved_ram_fraction() -> float:
    """Share of RAM Wan2GP may pin: the configured percentage, else mmgp's default (40% Windows, 60% elsewhere)."""
    try:
        percent = float(sys.modules["wgp"].server_config.get("perc_reserved_mem_max", 0) or 0)
    except Exception:
        percent = 0.0
    return percent / 100.0 if percent > 0 else (0.40 if os.name == "nt" else 0.60)


def _file_names(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if isinstance(item, str) and Path(item.split("?")[0]).suffix.lower() in MODEL_FILE_SUFFIXES]


def model_files(model_type: str, get_model_def: Callable[[str], Any], depth: int = 0) -> dict[str, list[str]]:
    """Checkpoint file names of a model: the main weights and the text encoder.

    A definition may point at another model type instead of listing files (for example the LTX VFX
    models reuse ltx2_25_22B_distilled), so such references are followed a few levels deep.
    """
    try:
        model_def = get_model_def(model_type) or {}
    except Exception:
        return {"main": [], "encoder": []}
    main = _file_names(model_def.get("URLs"))
    encoder = _file_names(model_def.get("text_encoder_URLs"))
    reference = model_def.get("URLs")
    if not main and isinstance(reference, str) and reference != model_type and depth < 3:
        return model_files(reference, get_model_def, depth + 1)
    return {"main": main, "encoder": encoder}


def _size(name: str, locate: Callable[[str], str | None]) -> int | None:
    try:
        path = locate(Path(name.split("?")[0]).name if name.startswith(("http://", "https://")) else name)
        return os.path.getsize(path) if path and os.path.isfile(path) else None
    except Exception:
        return None


def estimate_pinned_ram(main_bytes: int, total_ram: float | None, fraction: float) -> int:
    """RAM Wan2GP will try to pin for one model: the weights, capped by the reserved-RAM share."""
    cap = int(total_ram * fraction) if total_ram else main_bytes
    return min(main_bytes, cap)


def _gib(value: float | int | None) -> str:
    return "unknown" if value is None else f"{value / GIB:.1f} GB"


def _issue(level: str, code: str, message: str) -> dict[str, str]:
    return {"level": level, "code": code, "message": message}


def check(
    graph: dict[str, Any],
    get_model_def: Callable[[str], Any],
    *,
    locate: Callable[[str], str | None],
    snapshot: dict[str, float | None] | None = None,
    fraction: float | None = None,
    release_models: bool = False,
) -> list[dict[str, str]]:
    """Findings for a graph, each {"level": "warning"|"info", "code", "message"}."""
    snap = snapshot if snapshot is not None else system_snapshot()
    fraction = reserved_ram_fraction() if fraction is None else fraction
    issues: list[dict[str, str]] = []

    models: dict[str, dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        if node.get("type") not in GENERATION_TYPES or not node.get("enabled", True):
            continue
        params = node.get("params") or {}
        settings = params.get("settings") if isinstance(params.get("settings"), dict) else {}
        model_type = str(params.get("model_type") or settings.get("model_type") or "")
        if not model_type or model_type in models:
            continue
        files = model_files(model_type, get_model_def)
        main_sizes = [(name, _size(name, locate)) for name in files["main"]]
        encoder_sizes = [(name, _size(name, locate)) for name in files["encoder"]]
        models[model_type] = {
            "main_bytes": max([size for _, size in main_sizes if size] or [0]),
            "encoder_bytes": max([size for _, size in encoder_sizes if size] or [0]),
            # the file lists are alternatives (bf16, int8, ...): only a group with none of them on disk needs a download
            # Only the main weights: text encoders are stored in a sub folder chosen by the model handler, so
            # looking them up by bare file name would report downloads that are not needed.
            "missing": [name for name, _ in main_sizes] if main_sizes and all(size is None for _, size in main_sizes) else [],
        }

    # 1. pinned RAM against the Windows commit limit and physical RAM
    pinned = [estimate_pinned_ram(info["main_bytes"], snap.get("ram_total"), fraction) for info in models.values()]
    peak = (max(pinned) if release_models else sum(pinned)) if pinned else 0
    if peak:
        needed = peak + COMMIT_MARGIN_GIB * GIB
        commit_available = snap.get("commit_available")
        if commit_available is not None and commit_available < needed:
            issues.append(_issue(
                "warning", "commit",
                f"Windows has {_gib(commit_available)} of commit memory left (RAM + page file), but this graph will pin about {_gib(peak)} of model weights "
                f"and needs roughly {_gib(needed)} with a safety margin. Loading can fail with 'Memory allocation failure' or an out-of-memory error even though RAM looks free. "
                f"Enlarge the page file (System > Advanced > Performance > Virtual memory), or lower 'perc_reserved_mem_max' in Configuration, or close programs that hold memory (for example WSL: `wsl --shutdown`)."))
        ram_available = snap.get("ram_available")
        if ram_available is not None and ram_available < peak:
            issues.append(_issue(
                "warning", "ram",
                f"Only {_gib(ram_available)} of RAM is free and about {_gib(peak)} will be pinned. Close other programs first, or lower 'perc_reserved_mem_max' (less pinning is slower but safer)."))

    # 2. several models resident at once
    if len(models) > 1 and not release_models:
        issues.append(_issue(
            "warning", "resident",
            f"The graph uses {len(models)} different models and 'Unload on model change' is off, so they stay in memory together (about {_gib(sum(pinned))} pinned). Turn on the workflow setting 'unload_on_model_change' to load them one at a time."))

    # 3. VRAM already taken by other programs
    vram_free = snap.get("vram_free")
    if vram_free is not None and vram_free < MIN_FREE_VRAM_GIB * GIB:
        issues.append(_issue("warning", "vram", f"Only {_gib(vram_free)} of VRAM is free ({_gib(snap.get('vram_total'))} in total). Another program or a model left loaded is using it."))

    # 4. disk space for outputs and downloads
    disk_free = snap.get("disk_free")
    if disk_free is not None and disk_free < MIN_FREE_DISK_GIB * GIB:
        issues.append(_issue("warning", "disk", f"Only {_gib(disk_free)} of disk space is free where the outputs are written."))

    # 5. files that will be downloaded
    for model_type, info in models.items():
        if info["missing"]:
            names = ", ".join(Path(name).name for name in info["missing"][:3]) + (" ..." if len(info["missing"]) > 3 else "")
            issues.append(_issue("info", "download", f"Model '{model_type}' has none of these weights on disk yet ({names}); Wan2GP will download the variant that matches your settings on the first run."))
    return issues


def format_issues(issues: list[dict[str, str]]) -> str:
    return "\n".join(f"[{issue['level']}] {issue['message']}" for issue in issues)
