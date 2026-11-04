# Copyright (c) 2026 WanGP Studio contributors - part of WanGP, WanGP Community License 2.0 (see LICENSE.txt)
"""Lightweight full-screen Studio frontend backed by WanGP's in-process web session.

The plugin deliberately does not call shared.api.init(): Deepy's web_session()
binds this plugin to the already-running WanGP WebUI queue and runtime.
"""
import asyncio
import json
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from shared.utils.plugins import WAN2GPPlugin

from .media_index import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    MediaIndex,
    media_id_for,
    thumbnail_bytes,
)
from .workflow_compat import WorkflowCompat, WorkflowImportError, WorkflowLimitError, WorkflowUnavailable
from .telemetry import Telemetry
from .sendto import SendToError, SendToRegistry, inbox_append


#: Injected into the WanGP UI. It turns ``?studio_sendto=<handoff id>`` into a real
#: hand-off: the hidden Studio bridge receives the live Gradio session state, adds
#: the frame to the target plugin's inbox, and this script then selects that
#: plugin's tab so the plugin drains the inbox into the picked slot.
SENDTO_BRIDGE_JS = r"""
(() => {
  const STYLE_ID = "studio-sendto-style";
  function appRoot(){return window.gradioApp ? window.gradioApp() : (document.querySelector("gradio-app")?.shadowRoot || document);}
  function field(id){return appRoot().querySelector(`#${id} textarea, #${id} input`);}
  function button(id){return appRoot().querySelector(`#${id} button, #${id}`);}
  function sleep(ms){return new Promise((resolve) => setTimeout(resolve, ms));}
  function toast(text, bad){
    let host = document.getElementById("studio-sendto-toast");
    if(!host){
      host = document.createElement("div");
      host.id = "studio-sendto-toast";
      host.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:2147483000;max-width:420px;padding:12px 16px;border-radius:10px;background:#1b2430;color:#f4f7fb;font:13px/1.45 system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.35);opacity:0;transition:opacity .18s ease";
      document.body.appendChild(host);
    }
    host.textContent = text;
    host.style.background = bad ? "#5a1f24" : "#1b2430";
    host.style.opacity = "1";
  }
  function installStyle(){
    if(document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = "#studio-sendto-bridge{display:none !important;}";
    document.head.appendChild(style);
  }
  async function waitFor(check, timeout = 15000, step = 150){
    const deadline = Date.now() + timeout;
    while(Date.now() < deadline){
      try{ const value = await check(); if(value) return value; }catch(_error){}
      await sleep(step);
    }
    return null;
  }
  function tabByName(name){
    const wanted = String(name || "").replace(/[^a-z0-9]/gi, "").toLowerCase();
    if(!wanted) return null;
    const candidates = appRoot().querySelectorAll('[role="tab"], button');
    for(const candidate of candidates){
      const text = String(candidate.textContent || "").replace(/[^a-z0-9]/gi, "").toLowerCase();
      if(text === wanted) return candidate;
    }
    return null;
  }
  async function statusOf(handoffId){
    const response = await fetch("studio/api/sendto/" + encodeURIComponent(handoffId), {credentials: "same-origin"});
    if(!response.ok) throw new Error("status " + response.status);
    return response.json();
  }
  function dropTokenFromAddress(){
    try{
      const url = new URL(window.location.href);
      if(!url.searchParams.has("studio_sendto")) return;
      url.searchParams.delete("studio_sendto");
      window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    }catch(_error){}
  }
  async function run(handoffId){
    let info = null;
    try{ info = await statusOf(handoffId); }catch(error){ toast("Send to plugin: " + error.message, true); dropTokenFromAddress(); return; }
    if(!info || info.status !== "pending"){
      toast("Send to plugin: this hand-off is no longer pending. Send it again from Studio.", true);
      dropTokenFromAddress();
      return;
    }
    const handoff = info.handoff || {};
    const element = await waitFor(() => field("studio_sendto_token"));
    const trigger = await waitFor(() => button("studio_sendto_trigger"));
    if(!element || !trigger){
      toast("Send to plugin: the WanGP bridge is not installed. Restart WanGP after updating Studio.", true);
      dropTokenFromAddress();
      return;
    }
    element.value = handoffId;
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
    await sleep(80);
    trigger.click();
    const consumed = await waitFor(async () => (await statusOf(handoffId)).status === "consumed", 12000, 250);
    if(!consumed){
      toast("Send to plugin: WanGP did not accept the frame. Retry from Studio.", true);
      dropTokenFromAddress();
      return;
    }
    const label = (handoff.plugin_label || "plugin") + (handoff.slot_label ? " · " + handoff.slot_label : "");
    const tab = await waitFor(() => tabByName(handoff.tab), 8000, 250);
    if(tab){ tab.click(); toast("Sent to " + label); }
    else { toast("Sent to " + label + " — switch to that tab to load the frame."); }
    dropTokenFromAddress();
  }
  installStyle();
  const pendingSend = new URLSearchParams(window.location.search).get("studio_sendto");
  if(pendingSend) run(pendingSend);
})();
"""


MEDIA_UPLOAD_MAX_BYTES = 512 * 1024 * 1024
_ILLEGAL_FILENAME_CHARACTERS = str.maketrans({character: "_" for character in '\\/:*?"<>|'})
_MEDIA_MIME_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff",
    ".mp4": "video/mp4", ".m4v": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm",
    ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".flac": "audio/flac", ".ogg": "audio/ogg",
    ".opus": "audio/opus", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".wgpworld": "application/zip", ".wgpapp": "application/zip",
}


def _safe_upload_name(filename: str, extension: str) -> str:
    name = os.path.basename((filename or "").replace("\\", "/"))
    stem = os.path.splitext(name)[0] or "upload"
    stem = stem.translate(_ILLEGAL_FILENAME_CHARACTERS)
    stem = "".join(character for character in stem if ord(character) >= 32).strip(" .")
    if not stem:
        stem = "upload"
    return stem[:120] + extension


def _unique_destination(directory: str, name: str) -> str:
    candidate = os.path.join(directory, name)
    if not os.path.exists(candidate):
        return candidate
    stem, extension = os.path.splitext(name)
    counter = 1
    while True:
        candidate = os.path.join(directory, f"{stem} ({counter}){extension}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


KNOWN_PLUGINS = {
    "wan2gp-wanflow-ui": {"integration": "L2", "capabilities": ["workflow.catalog", "workflow.run"], "license": "Apache-2.0"},
    "wan2gp-status-pro": {"integration": "L2 (data)", "capabilities": ["telemetry.sources"], "license": "public-domain"},
    "models_manager": {"integration": "L2 (bundled)", "capabilities": ["models.inventory"], "license": "project"},
    "ImageSuite-Wan2GP": {"integration": "L1", "capabilities": [], "license": "WanGP-Community-2.0"},
    "wan2gp-lora-manager": {"integration": "L1", "capabilities": [], "license": "none"},
    "wan2gp-queue-editor": {"integration": "L1", "capabilities": [], "license": "none"},
}


def _dedupe_messages(values: list[str]) -> list[str]:
    """Remove duplicate messages while keeping their original order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


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
        self.version = "1.3.0"
        self.description = "Lightweight full-screen workspace for WanGP models, generation and workflows."
        self.type = ["app"]
        self._session = None
        self._session_lock = threading.Lock()
        self._sendto = SendToRegistry(self._plugins_root, is_enabled=self._plugin_enabled)
        #: True once the hidden Gradio bridge is wired into the main UI. Without
        #: it Studio still serves every route, but a send has nowhere to land.
        self._sendto_bridge_installed = False

    def setup_ui(self) -> None:
        self.request_global("server_config")
        self.request_global("app")
        for name in (
            "list_model_defs",
            "get_model_def",
            "get_base_model_type",
            "get_parent_model_type",
            "get_model_family",
            "get_default_settings",
            "get_lora_dir",
            "get_resolution_choices",
        ):
            self.request_global(name)
        self.register_web_app("/studio", self.create_web_app)
        # SendTo needs the session state and a hidden control in the main UI: a
        # Studio request has no Gradio session of its own.
        self.request_component("state")
        self.add_custom_js(SENDTO_BRIDGE_JS)
        try:
            self.insert_after("gen_status", self._build_sendto_bridge)
        except Exception as exc:  # a missing anchor must not break startup
            print(f"[Studio] SendTo bridge could not be registered: {exc}")

    def _get_session(self):
        """Return one cached session bound to the existing WanGP WebUI queue."""
        if self._session is not None:
            return self._session
        with self._session_lock:
            if self._session is None:
                # Do not initialize another runtime. Join the already-running WebUI queue.
                self._session = self.deepy.web_session()
        return self._session

    def get_session(self):
        return self._get_session()

    def _wanflow_enabled(self) -> bool:
        """WanFlow UI counts as enabled only when the Plugin Manager loaded it."""
        manager = getattr(getattr(self, "app", None), "plugin_manager", None)
        if manager is None:
            return True  # no registry context (tests): assume installed means usable
        try:
            return "wan2gp-wanflow-ui" in (manager.get_all_plugins() or {})
        except Exception:
            return False

    @staticmethod
    def _plugins_root() -> str:
        """Folder that holds installed plugins (overridable for tests)."""
        override = os.environ.get("STUDIO_PLUGINS_ROOT")
        if override:
            return override
        return str(Path(__file__).resolve().parents[1])

    def _plugin_enabled(self, plugin_id: str) -> bool:
        manager = getattr(getattr(self, "app", None), "plugin_manager", None)
        if manager is None:
            return True  # no registry context (tests): installed is the best answer we have
        try:
            return plugin_id in (manager.get_all_plugins() or {})
        except Exception:
            return False

    # -- SendTo bridge (Gradio side) ------------------------------------
    def _build_sendto_bridge(self):
        """Hidden Gradio controls the Studio web app cannot own itself.

        A Studio HTTP handler never sees a Gradio session, so the frame cannot be
        written into another plugin's inbox from there. This control lives in the
        main UI: the injected JS fills the token and clicks it, the callback below
        receives the real ``state`` dict and performs the inbox append.
        """
        import gradio as gr

        state_component = getattr(self, "state", None)
        with gr.Row(visible=True, elem_id="studio-sendto-bridge", elem_classes=["studio-sendto-bridge"]) as container:
            handoff_box = gr.Textbox(
                value="",
                show_label=False,
                container=False,
                interactive=True,
                elem_id="studio_sendto_token",
            )
            trigger = gr.Button("Send", elem_id="studio_sendto_trigger", visible=True)
            result = gr.Textbox(
                value="",
                show_label=False,
                container=False,
                interactive=False,
                elem_id="studio_sendto_result",
            )
        if state_component is None:
            print("[Studio] SendTo bridge is inactive: the host 'state' component was not found.")
            return container
        trigger.click(
            fn=self._apply_sendto_handoff,
            inputs=[state_component, handoff_box],
            outputs=[state_component, result],
            queue=False,
            show_progress="hidden",
            api_name=False,
            show_api=False,
        )
        self._sendto_bridge_installed = True
        return container

    def _apply_sendto_handoff(self, state, handoff_id):
        """Claim a parked hand-off and append it to the target plugin's inbox."""
        handoff_id = str(handoff_id or "").strip()
        if not handoff_id:
            return state, "missing"
        handoff = self._sendto.take(handoff_id)
        if handoff is None:
            return state, "expired"
        # Delivery-time re-check: the plugin may have been disabled (or
        # uninstalled) between create() and the bridge firing.
        if not self._plugin_enabled(handoff.plugin):
            return state, "disabled"
        if not os.path.isfile(handoff.path):
            return state, "missing-file"
        if not inbox_append(state, handoff.inbox_key, handoff.path, handoff.slot):
            return state, "no-state"
        return state, f"sent:{handoff.slot}"

    def _media_roots(self) -> list[str]:
        """Output roots of the installed WanGP plus optional media folders."""
        config = getattr(self, "server_config", None)
        if not isinstance(config, dict):
            config = {}
            try:
                config_path = Path(__file__).resolve().parents[2] / "wgp_config.json"
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                config = {}
        roots = []
        for key in ("save_path", "image_save_path", "audio_save_path", "mesh_save_path"):
            value = config.get(key)
            if isinstance(value, str) and value.strip():
                roots.append(value)
        repo = Path(__file__).resolve().parents[2]
        workspaces = repo / "workspaces"
        if workspaces.is_dir():
            for record_path in sorted(workspaces.glob("*.json")):
                try:
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(record, dict) or record.get("storage_mode") != "dedicated":
                    continue
                folder = record.get("folder")
                if isinstance(folder, str) and folder.strip():
                    folder_path = Path(folder)
                    if not folder_path.is_absolute():
                        folder_path = workspaces / folder_path
                    roots.append(str(folder_path))
        workflow_outputs = repo / "plugins" / "wan2gp-wanflow-ui" / "workflow_outputs"
        if workflow_outputs.is_dir():
            roots.append(str(workflow_outputs))
        return roots

    def create_web_app(self):
        from fastapi import FastAPI, File, HTTPException, Request, UploadFile
        from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
        from fastapi.staticfiles import StaticFiles
        from starlette.concurrency import run_in_threadpool

        web_dir = Path(__file__).resolve().parent / "web"
        assets_dir = web_dir / "assets"
        app = FastAPI(
            title="WanGP Studio",
            version=self.version,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        @app.middleware("http")
        async def studio_security_headers(request: Request, call_next):
            response = await call_next(request)
            response.headers["X-Frame-Options"] = "DENY"
            if "content-security-policy" not in {key.lower() for key in response.headers}:
                response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
            return response

        jobs: dict[str, _JobRecord] = {}
        jobs_lock = threading.Lock()
        media_index = MediaIndex(self._media_roots)
        from .plugin_health import PluginHealthService

        plugin_health = PluginHealthService(lambda: self._plugins_root())

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
            availability: int = 0,
            limit: int = 300,
            offset: int = 0,
        ):
            session = session_or_503()
            try:
                return session.list_model_metadata(
                    include_availability=bool(availability),
                    include_selection=False,
                    query=q or None,
                    family=family or None,
                    inputs=inputs or None,
                    main_output=output or None,
                    limit=max(1, min(int(limit), 500)),
                    offset=max(0, int(offset)),
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not read model catalog: {exc}") from exc

        @app.get("/api/models/summary")
        def models_summary():
            session = session_or_503()
            try:
                records = session.list_model_metadata(include_availability=True, limit=1000)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not summarize the model catalog: {exc}") from exc

            def is_available(record: dict) -> bool:
                value = record.get("availability")
                if isinstance(value, bool):
                    return value
                if isinstance(value, dict):
                    status = str(value.get("status") or "").lower()
                    if value.get("available") is True or value.get("ready") is True or status == "partial":
                        return True
                    if status == "missing" or value.get("available") is False:
                        return False
                return False

            by_output: dict[str, dict[str, int]] = {}
            by_family: dict[str, dict[str, int]] = {}
            available = 0
            for record in records:
                outputs = record.get("outputs") or [record.get("main_output") or "other"]
                if not isinstance(outputs, list):
                    outputs = [outputs]
                family = str(record.get("family_label") or record.get("family") or "other")
                if is_available(record):
                    available += 1
                for output in outputs:
                    key = str(output or "other")
                    bucket = by_output.setdefault(key, {"total": 0, "available": 0})
                    bucket["total"] += 1
                    if is_available(record):
                        bucket["available"] += 1
                family_bucket = by_family.setdefault(family, {"total": 0, "available": 0})
                family_bucket["total"] += 1
                if is_available(record):
                    family_bucket["available"] += 1
            return {
                "total": len(records),
                "available": available,
                "unavailable": len(records) - available,
                "by_output": by_output,
                "by_family": by_family,
            }

        @app.get("/api/models/{model_type}")
        def get_model(model_type: str):
            session = session_or_503()
            try:
                model_def = session.get_model_def(model_type)
                if model_def is None:
                    raise HTTPException(status_code=404, detail=f"Unknown model_type: {model_type}")
                try:
                    presets = session.get_model_settings(model_type, include_selection=True)
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
                if metadata is not None:
                    metadata.update(session.get_model_selection_metadata(model_type))
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

        @app.get("/api/models/{model_type}/settings")
        def get_model_setting(model_type: str, setting_id: str):
            session = session_or_503()
            try:
                selected = session.get_model_settings(
                    model_type,
                    setting_id=setting_id,
                    include_selection=True,
                )
                settings = selected.get("content")
                if not isinstance(settings, dict):
                    raise HTTPException(status_code=422, detail="The selected preset does not contain a settings object.")
                settings.setdefault("model_type", model_type)
                return session.merge_settings_with_defaults(settings)
            except HTTPException:
                raise
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not load model settings: {exc}") from exc

        @app.get("/api/media")
        def list_media(
            kind: str | None = None,
            q: str = "",
            sort: str = "date_desc",
            limit: int = 50,
            offset: int = 0,
        ):
            media_index.refresh()
            return media_index.query(kind=kind, q=q, sort=sort, limit=limit, offset=offset)

        @app.get("/api/media/roots")
        def media_roots():
            media_index.refresh()
            return media_index.stats()

        @app.get("/api/media/{media_id}")
        def media_detail(media_id: str):
            media_index.refresh()
            entry = media_index.get(media_id)
            if entry is None:
                raise HTTPException(status_code=404, detail="Media item not found.")
            return media_index.detail(entry)

        @app.get("/api/media/{media_id}/thumbnail")
        def media_thumbnail(media_id: str):
            media_index.refresh()
            entry = media_index.get(media_id)
            if entry is None:
                raise HTTPException(status_code=404, detail="Media item not found.")
            try:
                data = thumbnail_bytes(entry["path"])
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Media file no longer exists.") from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not render thumbnail: {exc}") from exc
            if not data:
                raise HTTPException(status_code=404, detail="No thumbnail available for this item.")
            return Response(
                content=data,
                media_type="image/jpeg",
                headers={"Cache-Control": "private, max-age=120"},
            )

        @app.delete("/api/media/{media_id}")
        def delete_media(media_id: str, confirm: bool = False):
            media_index.refresh()
            entry = media_index.get(media_id)
            if entry is None:
                raise HTTPException(status_code=404, detail="Media item not found.")
            if not confirm:
                raise HTTPException(status_code=400, detail="Deletion requires confirm=true.")
            try:
                media_index.delete(media_id)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not delete the media file: {exc}") from exc
            return {"deleted": media_id, "name": entry["name"]}

        @app.post("/api/media/upload")
        async def upload_media(file: UploadFile = File(...)):
            extension = os.path.splitext(file.filename or "")[1].lower()
            if extension in IMAGE_EXTENSIONS:
                kind = "image"
            elif extension in VIDEO_EXTENSIONS:
                kind = "video"
            elif extension in AUDIO_EXTENSIONS:
                kind = "audio"
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported media type: {extension or 'unknown'}")
            config = getattr(self, "server_config", None)
            if not isinstance(config, dict):
                config = {}
            folder_key = {"image": "image_save_path", "video": "save_path", "audio": "audio_save_path"}[kind]
            target_dir = config.get(folder_key) or config.get("save_path")
            if not isinstance(target_dir, str) or not target_dir.strip():
                raise HTTPException(status_code=500, detail="WanGP output folder is not configured.")
            target_dir = os.path.abspath(os.path.expanduser(target_dir.strip()))
            os.makedirs(target_dir, exist_ok=True)
            destination = _unique_destination(target_dir, _safe_upload_name(file.filename, extension))
            temp_path = os.path.join(target_dir, f".upload-{uuid.uuid4().hex}.tmp")
            written = 0
            handle = None
            try:
                handle = await run_in_threadpool(open, temp_path, "wb")
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MEDIA_UPLOAD_MAX_BYTES:
                        raise HTTPException(status_code=413, detail="File is larger than 512 MB")
                    await run_in_threadpool(handle.write, chunk)
                await run_in_threadpool(handle.close)
                handle = None
                await run_in_threadpool(os.replace, temp_path, destination)
            except HTTPException:
                if handle is not None:
                    await run_in_threadpool(handle.close)
                if os.path.exists(temp_path):
                    await run_in_threadpool(os.remove, temp_path)
                raise
            except Exception as exc:
                if handle is not None:
                    await run_in_threadpool(handle.close)
                if os.path.exists(temp_path):
                    await run_in_threadpool(os.remove, temp_path)
                raise HTTPException(status_code=500, detail=f"Could not store the uploaded file: {exc}") from exc
            entry = media_index.index_file(destination)
            if entry is None:
                raise HTTPException(status_code=500, detail="Uploaded file was not indexed.")
            return {"item": media_index.card(entry, include_path=True)}

        @app.get("/api/media/{media_id}/file")
        def media_file(media_id: str):
            media_index.refresh()
            entry = media_index.get(media_id)
            if entry is None:
                raise HTTPException(status_code=404, detail="Media item not found.")
            path = entry["path"]
            if not media_index._inside_roots(path):
                raise HTTPException(status_code=403, detail="Media file is outside the indexed roots.")
            extension = os.path.splitext(path)[1].lower()
            media_type = _MEDIA_MIME_TYPES.get(extension, "application/octet-stream")
            return FileResponse(
                path,
                media_type=media_type,
                filename=entry["name"],
                content_disposition_type="inline",
            )

        # -- SendTo ----------------------------------------------------
        @app.get("/api/sendto/targets")
        def sendto_targets():
            return {
                "targets": self._sendto.targets(),
                "bridge": bool(self._sendto_bridge_installed),
            }

        # -- Plugin health ----------------------------------------------
        @app.get("/api/plugins/health")
        def plugins_health(wait: bool = False):
            """Installed-vs-upstream state per plugin. The first read is an
            offline snapshot; ``?wait=1`` also contacts the remotes once."""
            if wait:
                return plugin_health.refresh(wait=True)
            return plugin_health.snapshot()

        @app.post("/api/plugins/health/refresh")
        def plugins_health_refresh():
            return plugin_health.refresh(wait=False, force=True)

        @app.post("/api/media/{media_id}/sendto")
        async def sendto_media(media_id: str, request: Request):
            media_index.refresh()
            entry = media_index.get(media_id)
            if entry is None:
                raise HTTPException(status_code=404, detail="Media item not found.")
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            plugin_id = str(payload.get("plugin") or "").strip()
            slot = str(payload.get("slot") or "").strip()
            try:
                if not plugin_id:
                    manifests = self._sendto.manifests()
                    if len(manifests) != 1:
                        raise SendToError(
                            400,
                            "Choose the plugin this frame goes to.",
                            extra={"plugins": sorted(manifests)},
                        )
                    plugin_id = next(iter(manifests))
                handoff = self._sendto.create(entry["path"], entry["kind"], plugin_id, slot)
            except SendToError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.payload()) from exc
            return {
                "handoff_id": handoff.handoff_id,
                "url": f"/?studio_sendto={handoff.handoff_id}",
                "bridge": bool(self._sendto_bridge_installed),
                "handoff": handoff.as_dict(include_path=False),
            }

        @app.get("/api/sendto/{handoff_id}")
        def sendto_status(handoff_id: str):
            payload = {"status": self._sendto.status(handoff_id)}
            handoff = self._sendto.peek(handoff_id)
            if handoff is not None:
                payload["handoff"] = handoff.as_dict(include_path=False)
            return payload

        workflow = WorkflowCompat(
            self,
            plugins_root=os.environ.get("STUDIO_PLUGINS_ROOT") or None,
            enabled_provider=self._wanflow_enabled,
            min_version="0.1.0",
        )
        telemetry = Telemetry(
            jobs_provider=lambda: [record.snapshot() for record in list(jobs.values())],
            workflow_provider=lambda: workflow.recent_runs(),
        )

        def workflow_gate():
            state = workflow.state()
            if state != "available":
                messages = {
                    "not_installed": "WanFlow UI is not installed. Install it from the WanGP Plugin Manager, then restart.",
                    "disabled": "WanFlow UI is installed but disabled. Enable it in the Plugin Manager and restart WanGP.",
                    "incompatible": f"WanFlow UI {workflow.version()} is older than the supported minimum {workflow.min_version}. Update the plugin.",
                }
                raise HTTPException(status_code=503, detail={
                    "state": state,
                    "plugin": "wan2gp-wanflow-ui",
                    "message": messages[state],
                    "fallback": {"href": "/", "label": "Open WanFlow UI (native tab)"},
                })
            return workflow

        @app.get("/api/environment")
        def environment():
            registry = {}
            manager = getattr(getattr(self, "app", None), "plugin_manager", None)
            if manager is not None:
                try:
                    registry = manager.get_all_plugins() or {}
                except Exception:
                    registry = {}
            plugins_root = Path(self._plugins_root())
            manifests = self._sendto.manifests()
            entries = []
            for plugin_id, meta in KNOWN_PLUGINS.items():
                plugin = registry.get(plugin_id)
                installed = (plugins_root / plugin_id).is_dir()
                manifest = manifests.get(plugin_id)
                capabilities = list(meta["capabilities"])
                if manifest is not None:
                    capabilities.append("sendto.inbox")
                entry = {
                    "id": plugin_id,
                    "state": "enabled" if plugin is not None else ("disabled" if installed else "not_installed"),
                    "version": getattr(plugin, "version", None),
                    "integration": meta["integration"],
                    "capabilities": capabilities,
                    "license": meta["license"],
                }
                if manifest is not None:
                    entry["sendto"] = manifest.as_dict()
                entries.append(entry)
            for plugin_id, plugin in sorted(registry.items()):
                if plugin_id in KNOWN_PLUGINS:
                    continue
                entries.append({
                    "id": plugin_id,
                    "state": "enabled",
                    "version": getattr(plugin, "version", None),
                    "integration": "native",
                    "capabilities": [],
                    "license": None,
                })
            return {
                "core": {"version": getattr(self, "wan2gp_version", None) or "unknown", "runtime": "WanGP WebUI"},
                "plugins": entries,
            }

        @app.get("/api/telemetry")
        def telemetry_snapshot():
            try:
                return telemetry.snapshot()
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Telemetry unavailable: {exc}") from exc

        @app.get("/api/workflow/status")
        def workflow_status():
            return workflow.info()

        @app.get("/api/workflow/catalog")
        def workflow_catalog():
            workflow_gate()
            try:
                return workflow.catalog()
            except WorkflowUnavailable as exc:
                raise HTTPException(status_code=503, detail={"state": "unavailable", "message": str(exc)}) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not build the workflow catalog: {exc}") from exc

        @app.get("/api/workflow/workflows")
        def workflow_list():
            workflow_gate()
            return workflow.workflows()

        @app.get("/api/workflow/workflows/{slug}/export")
        def workflow_export(slug: str, format: str = "wanflow"):
            workflow_gate()
            try:
                payload = workflow.export_workflow(slug, format)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"Workflow not found: {slug}") from None
            except WorkflowImportError as exc:
                raise HTTPException(status_code=400, detail={"message": str(exc), "report": exc.report}) from exc
            suffix = "comfyui" if str(format).lower().startswith("comfyui") else "wanflow"
            return JSONResponse(
                payload,
                headers={"Content-Disposition": f'attachment; filename="{slug}.{suffix}.json"'},
            )

        @app.post("/api/workflow/import")
        async def workflow_import(request: Request):
            workflow_gate()
            payload = await request.json()
            name = payload.get("name") if isinstance(payload, dict) else None
            try:
                return workflow.import_workflow(payload, name)
            except WorkflowImportError as exc:
                raise HTTPException(status_code=422, detail={"message": str(exc), "report": exc.report}) from exc
            except WorkflowUnavailable as exc:
                raise HTTPException(status_code=503, detail={"state": "unavailable", "message": str(exc)}) from exc

        @app.post("/api/workflow/blocks")
        async def workflow_save_block(request: Request):
            workflow_gate()
            payload = await request.json()
            graph = payload.get("graph") if isinstance(payload, dict) else None
            if not isinstance(graph, dict):
                raise HTTPException(status_code=400, detail="Request must contain a graph object.")
            try:
                return workflow.save_block(graph, payload.get("name"))
            except WorkflowUnavailable as exc:
                raise HTTPException(status_code=503, detail={"state": "unavailable", "message": str(exc)}) from exc
            except (ValueError, KeyError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.delete("/api/workflow/blocks/{block_id}")
        def workflow_delete_block(block_id: str):
            workflow_gate()
            try:
                return workflow.delete_block(block_id)
            except WorkflowUnavailable as exc:
                raise HTTPException(status_code=503, detail={"state": "unavailable", "message": str(exc)}) from exc
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

        @app.get("/api/workflow/workflows/{slug}")
        def workflow_get(slug: str):
            workflow_gate()
            try:
                return workflow.load(slug)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"Workflow not found: {slug}") from None

        @app.put("/api/workflow/workflows/{slug}")
        async def workflow_save(slug: str, request: Request):
            workflow_gate()
            payload = await request.json()
            graph = payload.get("graph") if isinstance(payload, dict) else None
            if not isinstance(graph, dict):
                raise HTTPException(status_code=400, detail="Request must contain a graph object.")
            try:
                return workflow.save(graph, payload.get("name") or slug)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid workflow: {exc}") from exc

        @app.delete("/api/workflow/workflows/{slug}")
        def workflow_delete(slug: str):
            workflow_gate()
            workflow.delete(slug)
            return {"deleted": slug}

        @app.post("/api/workflow/validate")
        async def workflow_validate(request: Request):
            workflow_gate()
            payload = await request.json()
            graph = payload.get("graph") if isinstance(payload, dict) else None
            if not isinstance(graph, dict):
                raise HTTPException(status_code=400, detail="Request must contain a graph object.")
            try:
                return workflow.validate(graph)
            except WorkflowUnavailable as exc:
                raise HTTPException(status_code=503, detail={"state": "unavailable", "message": str(exc)}) from exc

        @app.post("/api/workflow/runs")
        async def workflow_run(request: Request):
            payload = await request.json()
            graph = payload.get("graph") if isinstance(payload, dict) else None
            if not isinstance(graph, dict):
                raise HTTPException(status_code=400, detail="Request must contain a graph object.")
            inputs = payload.get("inputs")
            if not isinstance(inputs, list):
                inputs = []
            workflow_gate()
            try:
                return workflow.start_run(graph, inputs)
            except WorkflowLimitError as exc:
                raise HTTPException(status_code=429, detail={"state": "limit", "message": str(exc)}) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except WorkflowUnavailable as exc:
                raise HTTPException(status_code=503, detail={"state": "unavailable", "message": str(exc)}) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Could not start the workflow: {exc}") from exc

        @app.get("/api/workflow/runs/{run_id}")
        def workflow_run_snapshot(run_id: str):
            snapshot = workflow.snapshot(run_id)
            if snapshot is None:
                raise HTTPException(status_code=404, detail="Workflow run not found.")
            return snapshot

        @app.get("/api/workflow/runs/{run_id}/events")
        async def workflow_run_events(run_id: str, request: Request):
            if workflow.snapshot(run_id) is None:
                raise HTTPException(status_code=404, detail="Workflow run not found.")
            try:
                cursor = int(request.query_params.get("cursor") or request.headers.get("last-event-id") or 0)
            except ValueError:
                cursor = 0

            async def stream():
                position = max(0, cursor)
                last_beat = time.monotonic()
                while True:
                    bundle = workflow.events_after(run_id, position)
                    if bundle is None:
                        yield "event: end\ndata: {}\n\n"
                        return
                    events, latest = bundle
                    for event in events:
                        position = event["id"]
                        yield f"id: {position}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                    snapshot = workflow.snapshot(run_id)
                    if snapshot is None or (snapshot["status"] in {"completed", "failed", "cancelled"} and position >= latest):
                        yield "event: end\ndata: {}\n\n"
                        return
                    if time.monotonic() - last_beat >= 15:
                        yield ": keep-alive\n\n"
                        last_beat = time.monotonic()
                    await asyncio.sleep(0.35)

            return StreamingResponse(
                stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        @app.post("/api/workflow/runs/{run_id}/cancel")
        def workflow_run_cancel(run_id: str):
            if not workflow.cancel(run_id):
                raise HTTPException(status_code=404, detail="Workflow run not found.")
            return {"run_id": run_id, "status": "cancellation_requested"}

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
                model_def = await run_in_threadpool(session.get_model_def, model_type)
                if model_def is None:
                    raise HTTPException(status_code=400, detail=f"Unknown model_type: {model_type}")
                prompt = str(settings.get("prompt") or "")
                job_id = uuid.uuid4().hex
                record = _JobRecord(job_id, model_type, prompt)
                with jobs_lock:
                    terminal = {"completed", "failed", "cancelled"}
                    finished = [
                        key for key, value in sorted(jobs.items(), key=lambda pair: pair[1].created_at)
                        if value.snapshot()["status"] in terminal
                    ]
                    for key in finished[: max(0, len(jobs) - 49)]:
                        jobs.pop(key, None)
                    active_count = sum(
                        value.snapshot()["status"] not in terminal
                        for value in jobs.values()
                    )
                    if active_count >= 50:
                        raise HTTPException(status_code=429, detail="WanGP Studio already has 50 queued or running jobs.")
                    jobs[job_id] = record

                record.status = "queued"
                record.message = "Waiting in WanGP queue"
                record.emit("queued", {"job_id": job_id, "model_type": model_type})
                try:
                    job = await run_in_threadpool(
                        session.submit_task,
                        settings,
                        callbacks=_StudioCallbacks(record),
                    )
                except Exception as exc:
                    with record._lock:
                        record.status = "failed"
                        record.errors.append(str(exc))
                        record.message = str(exc)
                        record.updated_at = time.time()
                    record.emit("error", {"message": str(exc)})
                    raise
                with record._lock:
                    record.session_job = job

                def collect_result():
                    try:
                        result = job.result()
                        with record._lock:
                            record.generated_files = list(result.generated_files or [])
                            record.errors.extend(str(error) for error in (result.errors or []))
                            record.errors = _dedupe_messages(record.errors)
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
                        # SessionJob may retain GenerationResult artifacts (including large tensors).
                        # Drop the handle once completion has been reduced to lightweight metadata.
                        with record._lock:
                            record.session_job = None
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
            with record._lock:
                session_job = record.session_job
            if session_job is None:
                raise HTTPException(status_code=409, detail="Job has not been admitted by WanGP yet.")
            try:
                session_job.cancel()
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
        async def job_events(job_id: str, request: Request):
            with jobs_lock:
                record = jobs.get(job_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Studio job not found.")

            try:
                cursor = int(request.query_params.get("cursor") or request.headers.get("last-event-id") or 0)
            except ValueError:
                cursor = 0

            async def stream_events():
                position = max(0, cursor)
                last_heartbeat = time.monotonic()
                while True:
                    events, latest = record.events_after(position)
                    for event in events:
                        position = event["id"]
                        yield f"id: {position}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                    snapshot = record.snapshot()
                    if snapshot["status"] in {"completed", "failed", "cancelled"} and position >= latest:
                        yield "event: end\ndata: {}\n\n"
                        break
                    if time.monotonic() - last_heartbeat >= 15:
                        yield ": keep-alive\n\n"
                        last_heartbeat = time.monotonic()
                    await asyncio.sleep(0.35)

            return StreamingResponse(
                stream_events(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        return app
