# Copyright (c) 2026 WanGP Studio contributors - part of WanGP, WanGP Community License 2.0 (see LICENSE.txt)
"""Read-only telemetry for the Studio Resource Center (M3).

Sources are the ones WanGP already owns: psutil for RAM/CPU, NVML for GPU
facts (optional - the panel degrades to "unavailable"), and the Studio session
registries for jobs and workflow runs. Nothing here allocates GPU memory,
polls heavily or drives offloading.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("wangp.studio")


class Telemetry:
    def __init__(
        self,
        jobs_provider: Callable[[], list[dict[str, Any]]],
        workflow_provider: Callable[[], list[dict[str, Any]]],
        cache_seconds: float = 1.5,
    ) -> None:
        self._jobs_provider = jobs_provider
        self._workflow_provider = workflow_provider
        self._cache_seconds = float(cache_seconds)
        self._lock = threading.Lock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0
        self._nvml_ready = False
        self._nvml: Any = None

    # -- GPU -----------------------------------------------------------
    def _gpu(self) -> dict[str, Any]:
        if not self._nvml_ready:
            self._nvml_ready = True
            try:
                import pynvml

                pynvml.nvmlInit()
                if pynvml.nvmlDeviceGetCount() <= 0:
                    self._nvml = None
                else:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", "replace")
                    self._nvml = {"pynvml": pynvml, "handle": handle, "name": name}
            except Exception:
                self._nvml = None
        if not self._nvml:
            return {"available": False, "source": "unavailable"}
        pynvml = self._nvml["pynvml"]
        handle = self._nvml["handle"]
        try:
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            payload: dict[str, Any] = {
                "available": True,
                "source": "nvml",
                "name": self._nvml["name"],
                "utilization_percent": int(utilization.gpu),
                "vram_total_mb": round(memory.total / 1048576),
                "vram_used_mb": round(memory.used / 1048576),
                "vram_percent": round(100 * memory.used / memory.total, 1) if memory.total else 0,
            }
            try:
                payload["temperature_c"] = int(
                    pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                )
            except Exception:
                pass
            try:
                payload["power_w"] = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
            except Exception:
                pass
            try:
                payload["fan_percent"] = int(pynvml.nvmlDeviceGetFanSpeed(handle))
            except Exception:
                pass
            return payload
        except Exception as exc:
            logger.warning("NVML read failed: %s", exc)
            return {"available": False, "source": "nvml-error"}

    # -- snapshot ------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            if self._cached is not None and now - self._cached_at < self._cache_seconds:
                return self._cached

        import psutil

        process = psutil.Process(os.getpid())
        memory = psutil.virtual_memory()
        process_memory = process.memory_info()
        jobs = list(self._jobs_provider() or [])
        runs = list(self._workflow_provider() or [])

        terminal = {"completed", "failed", "cancelled"}
        active_jobs = [job for job in jobs if str(job.get("status")) not in terminal]
        queued = [job for job in jobs if str(job.get("status")) in {"queued", "submitting"}]
        active_runs = [run for run in runs if str(run.get("status")) not in terminal]

        current_job = None
        if active_jobs:
            latest = max(active_jobs, key=lambda job: float(job.get("created_at") or 0))
            current_job = {
                "id": latest.get("id"),
                "model_type": latest.get("model_type"),
                "status": latest.get("status"),
                "phase": latest.get("phase"),
                "progress": latest.get("progress"),
                "message": latest.get("message"),
            }
        current_run = None
        if active_runs:
            latest_run = max(active_runs, key=lambda run: float(run.get("created_at") or 0))
            current_run = {
                "id": latest_run.get("id"),
                "status": latest_run.get("status"),
                "progress": latest_run.get("progress"),
                "message": latest_run.get("message"),
            }

        gpu = self._gpu()
        snapshot = {
            "timestamp": now,
            "gpu": gpu,
            "system": {
                "ram_total_mb": round(memory.total / 1048576),
                "ram_used_mb": round((memory.total - memory.available) / 1048576),
                "ram_percent": round(memory.percent, 1),
                "cpu_percent": psutil.cpu_percent(interval=None),
            },
            "process": {
                "pid": os.getpid(),
                "rss_mb": round(process_memory.rss / 1048576),
                "cpu_percent": process.cpu_percent(interval=None),
                "threads": process.num_threads(),
            },
            "studio": {
                "jobs_total": len(jobs),
                "active_jobs": len(active_jobs),
                "queued_jobs": len(queued),
                "workflow_runs": len(runs),
                "active_workflow_runs": len(active_runs),
                "current_job": current_job,
                "current_workflow": current_run,
            },
            "sources": {
                "ram": "psutil",
                "cpu": "psutil",
                "gpu": gpu.get("source", "unavailable"),
                "jobs": "studio-session",
                "workflows": "workflow-compat",
            },
        }
        with self._lock:
            self._cached = snapshot
            self._cached_at = now
        return snapshot
