# Copyright (c) 2026 WanGP Studio contributors - part of WanGP, WanGP Community License 2.0 (see LICENSE.txt)
"""Lightweight full-screen Studio frontend backed by WanGP's in-process web session.

The plugin deliberately does not call shared.api.init(): Deepy's web_session()
binds this plugin to the already-running WanGP WebUI queue and runtime.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from shared.utils.plugins import WAN2GPPlugin


class _JobRecord:
    """Small, bounded in-memory view of a WanGP SessionJob."""

    def __init__(self, job_id: str, model_type: str, prompt: str) -> None:
        self.id = job_id
        self.model_type = model_type
        self.prompt = prompt[:240]
        self.status = "submitting"
        self.progress = 0
        self.phase = "queued"
        self.message = "Submitting to WanGP queue"
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.generated_files: list[str] = []
        self.errors: list[str] = []
        self.session_job = None
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=100)
        self._next_event_id = 1

    def emit(self, kind: str, data: Any = None) -> None:
        if is_dataclass(data):
            data = asdict(data)
        with self._lock:
            self._events.append({
                "id": self._next_event_id,
                "kind": kind,
                "data": data,
                "timestamp": time.time(),
            })
            self._next_event_id += 1
            self.updated_at = time.time()

    def update_progress(self, update: Any) -> None:
        progress = max(0, min(100, int(getattr(update, "progress", 0) or 0)))
        phase = str(getattr(update, "phase", "") or "running")
        status = str(getattr(update, "status", "") or phase)
        with self._lock:
            self.progress = progress
            self.phase = phase
            self.message = status
            self.status = "running"
            self.updated_at = time.time()
        self.emit("progress", {
            "progress": progress,
            "phase": phase,
            "status": status,
            "current_step": getattr(update, "current_step", None),
            "total_steps": getattr(update, "total_steps", None),
            "task_index": getattr(update, "task_index", None),
            "task_count": getattr(update, "task_count", None),
        })

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "id": self.id,
                "model_type": self.model_type,
                "prompt": self.prompt,
                "status": self.status,
                "progress": self.progress,
                "phase": self.phase,
                "message": self.message,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "generated_files": list(self.generated_files),
                "errors": list(self.errors),
            }

    def events_after(self, event_id: int) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            events = [event for event in self._events if event["id"] > event_id]
            latest = self._next_event_id - 1
        return events, latest


class _StudioCallbacks:
    def __init__(self, record: _JobRecord) -> None:
        self.record = record

    def on_status(self, status: str) -> None:
        message = str(status or "").strip()
        if message:
            with self.record._lock:
                self.record.message = message
                self.record.updated_at = time.time()
            self.record.emit("status", {"message": message})

    def on_progress(self, update: Any) -> None:
        self.record.update_progress(update)

    def on_preview(self, preview: Any) -> None:
        # Never retain PIL images or MP4 preview bytes in browser/backend memory.
        self.record.emit("preview", {
            "phase": str(getattr(preview, "phase", "") or ""),
            "progress": int(getattr(preview, "progress", 0) or 0),
            "has_image": getattr(preview, "image", None) is not None,
            "has_video": getattr(preview, "video", None) is not None,
        })

    def on_error(self, error: Any) -> None:
        message = str(getattr(error, "message", error) or "WanGP reported an error")
        with self.record._lock:
            self.record.errors.append(message)
            self.record.updated_at = time.time()
        self.record.emit("error", {"message": message})


class WanGPStudioPlugin(WAN2GPPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.name = "WanGP Studio"
        self.version = "0.1.0"
        self.description = "Lightweight full-screen workspace for WanGP models, generation and workflows."
        self.type = ["app"]
        self._session = None
        self._session_lock = threading.Lock()

    def setup_ui(self) -> None:
        self.register_web_app("/studio", self.create_web_app)

    def _get_session(self):
        """Return one cached session bound to the existing WanGP WebUI queue."""
        if self._session is not None:
            return self._session
        with self._session_lock:
            if self._session is None:
                # Do not initialize another runtime. Join the already-running WebUI queue.
                self._session = self.deepy.web_session()
        return self._session

    def create_web_app(self):
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import FileResponse, StreamingResponse
        from fastapi.staticfiles import StaticFiles

        web_dir = Path(__file__).resolve().parent / "web"
        assets_dir = web_dir / "assets"
        app = FastAPI(
            title="WanGP Studio",
            version=self.version,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        jobs: dict[str, _JobRecord] = {}
        jobs_lock = threading.Lock()

        def session_or_503():
            try:
                return self._get_session()
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"WanGP web session is not ready: {exc}") from exc

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(web_dir / "index.html")

        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="studio-assets")

        @app.get("/api/health")
        def health():
            return {
                "status": "ok",
                "application": "WanGP Studio",
                "version": self.version,
                "runtime": "WanGP WebUI",
                "session": "ready" if self._session is not None else "lazy",
            }

        @app.get("/api/models")
        def list_models(
            q: str = "",
            family: str | None = None,
            inputs: str | None = None,
            output: str | None = None,
            limit: int = 300,
            offset: int = 0,
        ):
            session = session_or_503()
            try:
                return session.list_model_metadata(
                    include_availability=True,
                    include_selection=True,
                    query=q or None,
                    family=family or None,
                    inputs=inputs or None,
                    main_output=output or None,
                    limit=max(1, min(int(limit), 500)),
                    offset=max(0, int(offset)),
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not read model catalog: {exc}") from exc

        @app.get("/api/models/{model_type}")
        def get_model(model_type: str):
            session = session_or_503()
            try:
                model_def = session.get_model_def(model_type)
                if model_def is None:
                    raise HTTPException(status_code=404, detail=f"Unknown model_type: {model_type}")
                try:
                    presets = session.get_model_settings(model_type)
                except Exception as exc:
                    presets = {"error": str(exc), "settings": []}
                try:
                    loras = session.list_loras(model_type)
                except Exception as exc:
                    loras = {"error": str(exc)}
                metadata_records = session.list_model_metadata(
                    include_availability=True,
                    model_type=model_type,
                    limit=1,
                )
                metadata = metadata_records[0] if metadata_records else session.get_model_metadata(model_type)
                return {
                    "model": model_def,
                    "metadata": metadata,
                    "schema": session.get_model_schema(model_type),
                    "defaults": session.get_default_settings(model_type),
                    "presets": presets,
                    "loras": loras,
                }
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not inspect model {model_type}: {exc}") from exc

        @app.get("/api/jobs")
        def list_jobs():
            with jobs_lock:
                records = list(jobs.values())
            records.sort(key=lambda item: item.created_at, reverse=True)
            return [record.snapshot() for record in records[:50]]

        @app.post("/api/jobs")
        async def submit_job(request: Request):
            payload = await request.json()
            settings = payload.get("settings") if isinstance(payload, dict) else None
            if not isinstance(settings, dict):
                raise HTTPException(status_code=400, detail="Request must contain a settings object.")
            model_type = str(settings.get("model_type") or "").strip()
            if not model_type:
                raise HTTPException(status_code=400, detail="settings.model_type is required.")

            session = session_or_503()
            try:
                if session.get_model_def(model_type) is None:
                    raise HTTPException(status_code=400, detail=f"Unknown model_type: {model_type}")
                prompt = str(settings.get("prompt") or "")
                job_id = uuid.uuid4().hex
                record = _JobRecord(job_id, model_type, prompt)
                with jobs_lock:
                    jobs[job_id] = record
                    if len(jobs) > 50:
                        finished = [
                            key for key, value in sorted(jobs.items(), key=lambda pair: pair[1].created_at)
                            if value.snapshot()["status"] in {"completed", "failed", "cancelled"}
                        ]
                        for key in finished[: max(0, len(jobs) - 50)]:
                            jobs.pop(key, None)

                job = session.submit_task(settings, callbacks=_StudioCallbacks(record))
                record.session_job = job
                record.status = "queued"
                record.message = "Waiting in WanGP queue"
                record.emit("queued", {"job_id": job_id, "model_type": model_type})

                def collect_result():
                    try:
                        result = job.result()
                        with record._lock:
                            record.generated_files = list(result.generated_files or [])
                            record.errors.extend(str(error) for error in (result.errors or []))
                            record.status = "completed" if result.success else ("cancelled" if result.cancelled else "failed")
                            record.progress = 100 if result.success else record.progress
                            record.phase = record.status
                            record.message = record.status.capitalize()
                            record.updated_at = time.time()
                        record.emit("complete", record.snapshot())
                    except Exception as exc:
                        with record._lock:
                            record.status = "failed"
                            record.errors.append(str(exc))
                            record.message = str(exc)
                            record.updated_at = time.time()
                        record.emit("error", {"message": str(exc)})
                    finally:
                        record.emit("closed", {"job_id": job_id})

                threading.Thread(
                    target=collect_result,
                    name=f"WanGP-Studio-{job_id[:8]}",
                    daemon=True,
                ).start()
                return {"job_id": job_id, "status": record.status}
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"WanGP rejected the job: {exc}") from exc

        @app.post("/api/jobs/{job_id}/cancel")
        def cancel_job(job_id: str):
            with jobs_lock:
                record = jobs.get(job_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Studio job not found.")
            if record.session_job is None:
                raise HTTPException(status_code=409, detail="Job has not been admitted by WanGP yet.")
            try:
                record.session_job.cancel()
                record.emit("cancel_requested", {"job_id": job_id})
                return {"job_id": job_id, "status": "cancellation_requested"}
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not cancel job: {exc}") from exc

        @app.get("/api/jobs/{job_id}")
        def get_job(job_id: str):
            with jobs_lock:
                record = jobs.get(job_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Studio job not found.")
            return record.snapshot()

        @app.get("/api/jobs/{job_id}/events")
        async def job_events(job_id: str):
            with jobs_lock:
                record = jobs.get(job_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Studio job not found.")

            async def stream_events():
                cursor = 0
                while True:
                    events, latest = record.events_after(cursor)
                    for event in events:
                        cursor = event["id"]
                        yield f"id: {cursor}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                    snapshot = record.snapshot()
                    if snapshot["status"] in {"completed", "failed", "cancelled"} and cursor >= latest:
                        yield "event: end\ndata: {}\n\n"
                        break
                    await asyncio.sleep(0.35)

            return StreamingResponse(
                stream_events(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        return app
