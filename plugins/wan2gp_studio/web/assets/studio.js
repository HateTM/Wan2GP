(() => {
  "use strict";
  const state = { models: [], selectedModel: null, modelDetail: null, currentSettings: null, filter: "all", query: "", jobs: new Map(), eventSources: new Map(), zoom: 100, view: "workflow" };
  const $ = (id) => document.getElementById(id);
  const S_ = (prefix, value) => esc(String(value == null ? "" : value));
  const esc = (value) => String(value == null ? "" : value).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  function toast(message, error) {
    const item = document.createElement("div");
    item.className = error ? "toast error" : "toast";
    item.textContent = message;
    $("toast-region").appendChild(item);
    window.setTimeout(() => item.remove(), 3600);
  }

  async function api(path, options) {
    options = options || {};
    const response = await fetch(path, Object.assign({
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" }
    }, options));
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = body.detail != null ? body.detail : body.message;
      const message = typeof detail === "string"
        ? detail
        : (detail && (detail.message || JSON.stringify(detail))) || "Request failed (" + response.status + ")";
      const error = new Error(message);
      if (detail && typeof detail === "object") {
        error.state = detail.state;
        error.fallback = detail.fallback;
      }
      throw error;
    }
    return body;
  }

  function category(model) {
    const meta = model.metadata || model;
    const outputs = meta.main_output || meta.outputs || [];
    const text = (Array.isArray(outputs) ? outputs : [outputs]).join(" ").toLowerCase();
    if (text.includes("video")) return "video";
    if (text.includes("image")) return "image";
    if (text.includes("audio")) return "audio";
    if (text.includes("3d") || text.includes("mesh")) return "3d";
    return "other";
  }

  function availabilityStatus(model) {
    const value = model.availability || model.metadata && model.metadata.availability;
    if (typeof value === "boolean") return value ? "available" : "missing";
    if (value && typeof value === "object") {
      const status = String(value.status || "").toLowerCase();
      if (status === "available" || value.available === true || value.ready === true) return "available";
      if (status === "partial") return "partial";
      if (status === "missing" || value.available === false) return "missing";
    }
    return "unknown";
  }

  function renderModels() {
    const query = state.query.trim().toLowerCase();
    const models = state.models.filter((model) => {
      const type = String(model.model_type || "");
      const name = String(model.name || model.metadata && model.metadata.name || type);
      const meta = model.metadata || model;
      const family = String(meta.family_label || meta.family || "");
      return (!query || (type + " " + name + " " + family).toLowerCase().includes(query))
        && (state.filter === "all" || category(model) === state.filter);
    });
    $("model-count").textContent = state.models.filter((model) => availabilityStatus(model) === "available").length + "/" + state.models.length;
    if (!models.length) {
      $("model-list").innerHTML = '<div class="empty-state">No matching models.</div>';
      return;
    }
    $("model-list").innerHTML = models.map((model) => {
      const type = String(model.model_type || "");
      const name = String(model.name || model.metadata && model.metadata.name || type);
      const kind = category(model);
      const family = model.family || model.metadata && (model.metadata.family_label || model.metadata.family) || kind;
      const selected = state.selectedModel === type ? " selected" : "";
      const availability = availabilityStatus(model);
      const availabilityClass = availability === "available" ? " available" : availability === "partial" ? " partial" : "";
      const availabilityTitle = availability === "available" ? "Model files available" : availability === "partial" ? "Model files partially available" : availability === "missing" ? "Model files missing" : "Availability not confirmed";
      return '<button class="model-card' + selected + '" data-model="' + esc(type) + '">' +
        '<span class="model-card-top"><i class="model-indicator ' + kind + '"></i><span class="model-card-name">' + esc(name) +
        '</span><i class="availability' + availabilityClass + '" title="' + availabilityTitle + '"></i></span>' +
        '<span class="model-card-meta">' + esc(family) + ' · ' + esc(type) + '</span></button>';
    }).join("");
    $("model-list").querySelectorAll("[data-model]").forEach((button) => button.addEventListener("click", () => selectModel(button.dataset.model)));
  }

  const NATIVE_TOOLS = { "wan2gp-lora-manager": "LoRA Manager", "wan2gp-queue-editor": "Queue Editor", "ImageSuite-Wan2GP": "Image Suite", "models_manager": "Models Manager" };

  async function renderModelLinks() {
    const host = $("model-links");
    if (!host) return;
    try {
      const environment = await api("api/environment");
      const entries = (environment.plugins || []).filter((plugin) => NATIVE_TOOLS[plugin.id] && plugin.state !== "not_installed");
      host.innerHTML = entries.length
        ? '<span class="field-note">Native tools:</span>' + entries.map((plugin) =>
            '<a class="model-link" href="/" target="_blank" rel="noopener" title="Open the WanGP UI tab">' +
            esc(NATIVE_TOOLS[plugin.id]) + (plugin.state === "enabled" ? "" : " · disabled") + " ↗</a>")
            .join("")
        : '<span class="field-note">No optional native tools installed.</span>';
    } catch (_) {
      host.innerHTML = "";
    }
  }

  function renderPresets(detail) {
    const entries = detail.presets && Array.isArray(detail.presets.settings) ? detail.presets.settings : [];
    const select = $("preset-select");
    $("preset-count").textContent = entries.length ? String(entries.length) : "";
    select.innerHTML = entries.length
      ? entries.map((entry) => {
          const label = String(entry.id || "").split("/").pop() || entry.id;
          return '<option value="' + esc(entry.id) + '">' + esc(entry.type || "setting") + " · " + esc(label) + "</option>";
        }).join("")
      : '<option value="">No presets available</option>';
    select.disabled = entries.length === 0;
    $("load-preset").disabled = entries.length === 0;
  }

  function renderLoras(detail) {
    const data = detail.loras || {};
    const loras = Array.isArray(data.loras) ? data.loras : [];
    $("lora-count").textContent = data.supported === false ? "N/A" : String(loras.length);
    $("lora-list").innerHTML = data.error
      ? '<span class="field-note">' + esc(data.error) + '</span>'
      : data.supported === false
        ? '<span class="field-note">This model does not support LoRAs.</span>'
        : loras.length
          ? loras.map((name) => '<span class="capability-chip">' + esc(name) + '</span>').join("")
          : '<span class="field-note">No LoRAs found in the model folder.</span>';
  }

  function renderCapabilities(detail) {
    const schema = detail.schema && detail.schema.metadata ? detail.schema.metadata : (detail.schema || {});
    const meta = detail.metadata || schema;
    const values = [];
    ["family_label", "base_model_type", "model_type", "size", "accelerated"].forEach((key) => {
      if (meta[key] !== undefined && meta[key] !== null && meta[key] !== "") values.push(String(meta[key]));
    });
    ["inputs", "main_output", "media_roles", "specialities"].forEach((key) => {
      const value = schema[key] || meta[key];
      if (Array.isArray(value)) value.forEach((item) => values.push(String(item)));
    });
    const unique = Array.from(new Set(values)).slice(0, 24);
    $("capability-list").innerHTML = unique.length
      ? unique.map((value) => '<span class="capability-chip">' + esc(value) + '</span>').join("")
      : '<span class="field-note">No additional capability metadata was returned.</span>';
  }

  // V4.1: canvas node selection drives the right panel. The panel keeps its
  // native model-settings editor; the node contributes model_type + prompt.
  function onNodeSelected(node) {
    const heading = document.getElementById("inspector-empty");
    if (!node) return;
    if (heading) {
      heading.hidden = false;
      heading.innerHTML = '<div class="inspector-empty-icon">☑</div><strong>Node: ' + esc(node.title || node.type) +
        '</strong><span>' + esc(node.type) + (node.params && node.params.path ? " · " + esc(node.params.path) : "") + "</span>";
    }
    const modelType = node.params && node.params.model_type;
    if (modelType) {
      selectModel(modelType).then(() => {
        const promptBox = document.getElementById("prompt-input");
        // restore exactly what the node carries - including an EMPTY prompt
        if (promptBox) promptBox.value = node.params && typeof node.params.prompt === "string" ? node.params.prompt : "";
        state.nodeSelected = node;
        const apply = document.getElementById("apply-to-node");
        if (apply) apply.hidden = false;
      }).catch(() => {});
    } else {
      // input/ffmpeg nodes: no model settings. Any previously selected model
      // must be fully forgotten, or "Run this model" would submit the old
      // model's settings from behind a plain node (audit P2).
      state.selectedModel = null;
      state.modelDetail = null;
      state.currentSettings = null;
      state.nodeSelected = node;
      const editor = document.getElementById("inspector-editor");
      const json = document.getElementById("settings-json");
      const promptBox = document.getElementById("prompt-input");
      if (promptBox) promptBox.value = "";  // prompts belong to model nodes only
      if (editor && json) {
        editor.hidden = false;
        json.value = JSON.stringify(node.params || {}, null, 2);
      }
      const run = document.getElementById("run-from-inspector");
      if (run) run.disabled = true;
      const apply = document.getElementById("apply-to-node");
      if (apply) apply.hidden = false;
    }
  }

  async function applyToNode() {
    const node = state.nodeSelected;
    if (!node) return;
    let parsed = null;
    try {
      parsed = JSON.parse(document.getElementById("settings-json").value || "{}");
    } catch (error) {
      toast("Settings JSON is invalid.", true);
      return;
    }
    const modelType = parsed.model_type || (node.params && node.params.model_type) || null;
    // Model nodes take native WanGP settings (prompt included); plain nodes
    // (inputs, ffmpeg) edit their own params (path, slot, ...) - never mix
    // the two, and never push a stale editor prompt into a plain node.
    const isModelNode = Boolean(node.params && (node.params.model_type || node.params.settings));
    const applied = window.WanGPStudioCanvas.applyToSelectedNode({
      prompt: isModelNode ? document.getElementById("prompt-input").value : null,
      model_type: isModelNode ? modelType : null,
      settings: isModelNode ? parsed : null,
      params: isModelNode ? null : parsed
    });
    toast(applied ? "Applied to the selected node." : "The canvas is unavailable.", !applied);
  }

  async function selectModel(modelType) {
    state.selectedModel = modelType;
    renderModels();
    $("inspector-empty").hidden = true;
    $("inspector-editor").hidden = false;
    $("run-from-inspector").disabled = true;
    $("settings-state").textContent = "Loading model definition…";
    $("node-status").textContent = "Loading…";
    $("generation-node").hidden = false;
    $("canvas-hint").hidden = true;
    $("node-model").textContent = modelType;
    try {
      const detail = await api("api/models/" + encodeURIComponent(modelType));
      if (state.selectedModel !== modelType) return;
      state.modelDetail = detail;
      const model = detail.model || {};
      const name = model.name || detail.metadata && detail.metadata.name || modelType;
      $("selected-model-name").textContent = name;
      $("selected-model-type").textContent = modelType;
      $("node-model").textContent = name;
      $("prompt-input").value = detail.defaults && detail.defaults.prompt || "";
      state.currentSettings = detail.defaults || { model_type: modelType };
      $("settings-json").value = JSON.stringify(state.currentSettings, null, 2);
      renderPresets(detail);
      renderLoras(detail);
      $("settings-state").textContent = "Native WanGP defaults loaded";
      $("run-from-inspector").disabled = false;
      $("canvas-model-count").textContent = name;
      $("node-status").textContent = "Ready";
      const selected = state.models.find((item) => item.model_type === modelType);
      if (selected && detail.metadata) selected.metadata = detail.metadata;
      renderModels();
      renderCapabilities(detail);
    } catch (error) {
      if (state.selectedModel !== modelType) return;
      $("settings-state").textContent = "Could not load model";
      $("node-status").textContent = "Error";
      toast(error.message, true);
    }
  }

  // V4.5: runtime status is derived from API health, never hardcoded. The
  // sidebar card, footer and topbar pill all reflect the last probe outcome.
  function applyRuntimeHealth(ok, detail) {
    const session = detail && detail.session ? detail.session : null;
    $("runtime-dot").classList.toggle("down", !ok);
    $("runtime-label").textContent = ok ? "WanGP connected" : "WanGP unreachable";
    $("runtime-state").textContent = ok ? (session === "ready" ? "Session ready" : "Lazy session") : "No API";
    $("sidebar-runtime-text").textContent = ok ? "Connected to WanGP" : "WanGP API unreachable";
    $("runtime-pill-text").textContent = ok ? "WanGP runtime · " + (session === "ready" ? "session ready" : "lazy") : "Runtime unreachable";
    document.body.classList.toggle("runtime-down", !ok);
  }

  async function probeHealth() {
    try {
      applyRuntimeHealth(true, await api("api/health"));
    } catch (_) {
      applyRuntimeHealth(false, null);
    }
  }

  async function loadModels() {
    $("api-status").textContent = "Loading model catalog…";
    $("runtime-state").textContent = "Loading…";
    try {
      state.models = await api("api/models?limit=500&availability=1");
      renderModels();
      renderModelLinks();
      const available = state.models.filter((model) => availabilityStatus(model) === "available").length;
      const partial = state.models.filter((model) => availabilityStatus(model) === "partial").length;
      $("api-status").textContent = state.models.length + " models · " + available + " available" +
        (partial ? " · " + partial + " partial" : "") + " · WanGP API connected";
      $("canvas-model-count").textContent = state.models.length + " models available";
    } catch (error) {
      $("api-status").textContent = "WanGP API unavailable";
      toast(error.message, true);
      $("model-list").innerHTML = '<div class="empty-state">' + esc(error.message) + '</div>';
    }
    // health status is independent of the catalog: a catalog error does not
    // mean the runtime is down (and vice versa)
    await probeHealth();
  }

  function settingsFromEditor() {
    let settings;
    try { settings = JSON.parse($("settings-json").value); }
    catch (error) { throw new Error("Settings JSON is invalid: " + error.message); }
    if (!settings || typeof settings !== "object" || Array.isArray(settings)) throw new Error("Settings must be a JSON object.");
    if (settings.model_type && settings.model_type !== state.selectedModel) {
      throw new Error("To change model_type, select the model from the library first.");
    }
    settings.model_type = state.selectedModel;
    settings.prompt = $("prompt-input").value;
    return settings;
  }

  async function loadPreset() {
    if (!state.selectedModel || !$("preset-select").value) return;
    const modelType = state.selectedModel;
    const settingId = $("preset-select").value;
    $("load-preset").disabled = true;
    $("settings-state").textContent = "Loading native preset…";
    try {
      const settings = await api(
        "api/models/" + encodeURIComponent(modelType) + "/settings?setting_id=" + encodeURIComponent(settingId)
      );
      if (state.selectedModel !== modelType) return;
      state.currentSettings = settings;
      $("prompt-input").value = settings.prompt || "";
      $("settings-json").value = JSON.stringify(settings, null, 2);
      $("settings-state").textContent = "Preset loaded · edits are local until submitted";
      toast("Preset loaded into the settings editor.");
    } catch (error) {
      $("settings-state").textContent = "Could not load preset";
      toast(error.message, true);
    } finally {
      if (state.selectedModel === modelType) {
        $("load-preset").disabled = !$("preset-select").value;
      }
    }
  }

  async function runGeneration() {
    if (!state.selectedModel) return toast("Select a model first.", true);
    let settings;
    try { settings = settingsFromEditor(); }
    catch (error) { return toast(error.message, true); }
    $("run-generation").disabled = true;
    $("run-from-inspector").disabled = true;
    try {
      const result = await api("api/jobs", { method: "POST", body: JSON.stringify({ settings }) });
      toast("Task submitted to the native WanGP queue.");
      await refreshJobs();
      watchJob(result.job_id);
    } catch (error) {
      toast(error.message, true);
    } finally {
      $("run-generation").disabled = false;
      $("run-from-inspector").disabled = !(state.selectedModel && state.modelDetail);
    }
  }

  function jobCard(job) {
    const status = String(job.status || "queued");
    const cls = status === "completed" || status === "failed" ? " " + status : "";
    const cancel = status === "completed" || status === "failed" || status === "cancelled" ? "" : '<button class="cancel-job" data-cancel="' + esc(job.id) + '">Cancel</button>';
    // Generation History: a finished job can be repeated with its original settings
    const repeat = status === "completed" || status === "failed" ? '<button class="cancel-job" data-repeat="' + esc(job.id) + '">Repeat</button>' : "";
    const files = (job.generated_files || []).slice(0, 3);
    const filesHtml = files.length
      ? '<div class="queue-files"><button class="queue-file" data-open-gallery="' + esc(job.id) + '">View ' + files.length +
        ' result(s) in the Media Center</button></div>' : "";
    const date = job.created_at ? new Date(job.created_at * 1000).toLocaleString() : "";
    return '<article class="queue-card"><div class="queue-card-top"><span class="queue-card-title">' + esc(job.model_type) +
      (date ? ' <small class="queue-date">' + esc(date) + "</small>" : "") +
      '</span><span class="queue-state' + cls + '">' + esc(status) + '</span></div><div class="queue-card-message">' +
      esc(job.message || job.prompt || "") + '</div><div class="queue-progress"><span style="width:' +
      Math.max(0, Math.min(100, Number(job.progress) || 0)) + '%"></span></div>' + filesHtml + repeat + cancel + '</article>';
  }

  function bindJobActions(host) {
    host.querySelectorAll("[data-cancel]").forEach((button) => button.addEventListener("click", () => cancelJob(button.dataset.cancel)));
    host.querySelectorAll("[data-repeat]").forEach((button) => button.addEventListener("click", () => repeatJob(button.dataset.repeat)));
    host.querySelectorAll("[data-open-gallery]").forEach((button) => button.addEventListener("click", () => setView("gallery")));
  }

  function taskCard(task) {
    const status = String(task.status || "queued");
    const cls = status === "completed" || status === "failed" ? " " + status : "";
    const kindBadge = task.kind === "workflow"
      ? '<span class="task-kind">workflow</span>'
      : '<span class="task-kind">generation</span>';
    const date = task.created_at ? new Date(task.created_at * 1000).toLocaleString() : "";
    let actions = "";
    if (task.kind === "generation") {
      if (!["completed", "failed", "cancelled"].includes(status)) {
        actions += '<button class="cancel-job" data-cancel="' + S_("task", task.id) + '">Cancel</button>';
      } else if (status !== "cancelled") {
        actions += '<button class="cancel-job" data-repeat="' + S_("task", task.id) + '">Repeat</button>';
      }
    } else {
      if (!["completed", "failed", "cancelled"].includes(status)) {
        actions += '<button class="cancel-job" data-cancel-run="' + S_("task", task.id) + '">Cancel</button>';
      }
      if (task.has_graph && status !== "running") {
        actions += '<button class="cancel-job" data-open-graph="' + S_("task", task.id) + '">Open workflow</button>';
      }
    }
    const files = (task.outputs || []).slice(0, 3);
    const filesHtml = files.length
      ? '<div class="queue-files"><button class="queue-file" data-open-media="' + S_("task", task.id) + '">View ' + files.length +
        ' result(s) in the Media Center</button></div>' : "";
    return '<article class="queue-card" data-task="' + S_("task", task.id) + '"><div class="queue-card-top"><span class="queue-card-title">' +
      kindBadge + " " + esc(task.name || "") +
      (date ? ' <small class="queue-date">' + esc(date) + "</small>" : "") +
      '</span><span class="queue-state' + cls + '">' + esc(status) + '</span></div><div class="queue-card-message">' +
      esc(task.message || "") + '</div><div class="queue-progress"><span style="width:' +
      Math.max(0, Math.min(100, Number(task.progress) || 0)) + '%"></span></div>' + filesHtml + actions + '</article>';
  }

  // registry id -> task record, so action handlers can reach the graph
  state.tasks = new Map();

  function renderTasks() {
    const records = Array.from(state.tasks.values());
    const active = records.filter((task) => !["completed", "failed", "cancelled"].includes(String(task.status || "queued"))).length;
    const badge = $("queue-nav-count");
    badge.textContent = String(active);
    badge.hidden = active === 0;
    if (!records.length) {
      $("queue-view-list").innerHTML = '<div class="queue-empty">No tasks yet. Run a model in Generate or a workflow on the canvas to see progress here.</div>';
      return;
    }
    $("queue-view-list").innerHTML = records.map(taskCard).join("");
    $("queue-view-list").querySelectorAll("[data-cancel]").forEach((button) => button.addEventListener("click", () => cancelJob(button.dataset.cancel)));
    $("queue-view-list").querySelectorAll("[data-repeat]").forEach((button) => button.addEventListener("click", () => repeatJob(button.dataset.repeat)));
    $("queue-view-list").querySelectorAll("[data-cancel-run]").forEach((button) => button.addEventListener("click", async () => {
      try {
        await api("api/workflow/runs/" + encodeURIComponent(button.dataset.cancelRun) + "/cancel", { method: "POST" });
        toast("Cancellation requested.");
      } catch (error) { toast(error.message, true); }
      window.setTimeout(refreshTasks, 600);
    }));
    $("queue-view-list").querySelectorAll("[data-open-graph]").forEach((button) => button.addEventListener("click", () => {
      const task = state.tasks.get(button.dataset.openGraph);
      if (!task || !task.graph || !window.WanGPStudioCanvas) return;
      setView("workflow");
      window.WanGPStudioCanvas.loadGraphIntoCanvas(task.graph);
    }));
    $("queue-view-list").querySelectorAll("[data-open-media]").forEach((button) => button.addEventListener("click", () => {
      const task = state.tasks.get(button.dataset.openMedia);
      window.WanGPStudioGallery.openResults(task ? task.outputs : []);
    }));
  }

  async function refreshTasks() {
    try {
      const tasks = await api("api/tasks");
      state.tasks.clear();
      tasks.forEach((task) => state.tasks.set(task.id, task));
      renderTasks();
    } catch (error) {
      console.warn("task registry unavailable:", error && error.message);
    }
  }

  function renderJobs() {
    const records = Array.from(state.jobs.values()).sort((a, b) => b.created_at - a.created_at);
    $("queue-count").textContent = String(records.length);
    const active = records.filter((job) => !["completed", "failed", "cancelled"].includes(String(job.status || "queued"))).length;
    const badge = $("queue-nav-count");
    badge.textContent = String(active);
    badge.hidden = active === 0;
    if (!records.length) {
      $("queue-list").innerHTML = '<div class="queue-empty">No Studio jobs yet. Run a model to see execution progress here.</div>';
      return;
    }
    $("queue-list").innerHTML = records.slice(0, 20).map(jobCard).join("");
    bindJobActions($("queue-list"));
    // the Queue PAGE is owned by the unified registry (renderTasks, /api/tasks):
    // it shows generation jobs AND workflow runs; the drawer stays jobs-only
  }

  async function refreshJobs() {
    try {
      const records = await api("api/jobs");
      state.jobs.clear();
      records.forEach((record) => state.jobs.set(record.id, record));
      renderJobs();
    } catch (_) {}
  }

  async function repeatJob(jobId) {
    try {
      await api("api/jobs/" + encodeURIComponent(jobId) + "/repeat", { method: "POST" });
    } catch (error) {
      toast(error.message, true);
    }
    await refreshJobs();
  }

  async function cancelJob(jobId) {
    try {
      await api("api/jobs/" + encodeURIComponent(jobId) + "/cancel", { method: "POST" });
      toast("Cancellation requested.");
      await refreshJobs();
    } catch (error) { toast(error.message, true); }
  }

  function watchJob(jobId) {
    if (!jobId || state.eventSources.has(jobId)) return;
    const source = new EventSource("api/jobs/" + encodeURIComponent(jobId) + "/events", { withCredentials: true });
    state.eventSources.set(jobId, source);
    source.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const previous = state.jobs.get(jobId) || { id: jobId };
        if (message.kind === "progress") {
          state.jobs.set(jobId, Object.assign({}, previous, {
            progress: message.data.progress, phase: message.data.phase, message: message.data.status, status: "running"
          }));
          renderJobs();
        } else if (message.kind === "status") {
          state.jobs.set(jobId, Object.assign({}, previous, { message: message.data.message || previous.message }));
          renderJobs();
        }
      } catch (_) {}
    };
    source.addEventListener("end", () => {
      source.close(); state.eventSources.delete(jobId); refreshJobs();
    });
    source.onerror = () => {
      source.close(); state.eventSources.delete(jobId); refreshJobs();
    };
  }

  function setFilter(filter) {
    state.filter = filter;
    document.querySelectorAll(".filter-chip").forEach((button) => button.classList.toggle("selected", button.dataset.filter === filter));
    renderModels();
  }

  const VIEW_CONFIG = {
    workflow: { nav: "nav-workflow", hash: "#workflow", label: "Workflow", section: null },
    dashboard: { nav: "nav-dashboard", hash: "#dashboard", label: "Dashboard", section: "dashboard-view", mode: "dashboard-mode", activate: "WanGPStudioDashboard" },
    generate: { nav: "nav-generate", hash: "#generate", label: "Generate", section: "generate-view", mode: "generate-mode", activate: "WanGPStudioGenerate" },
    gallery: { nav: "nav-gallery", hash: "#gallery", label: "Media Center", section: "gallery-view", mode: "gallery-mode", activate: "WanGPStudioGallery" },
    imageeditor: { nav: "nav-imageeditor", hash: "#imageeditor", label: "Image Editor", section: "imageeditor-view", mode: "imageeditor-mode", activate: "WanGPStudioImageEditor" },
    models: { nav: "nav-models", hash: "#models", label: "Models", section: "models-view", mode: "models-mode", activate: "WanGPStudioModels" },
    queue: { nav: "nav-queue", hash: "#queue", label: "Queue", section: "queue-view", mode: "queue-mode" },
    resources: { nav: "nav-resources", hash: "#resources", label: "Resource Center", section: "resource-view", mode: "resources-mode", activate: "WanGPStudioTelemetry" },
    plugins: { nav: "nav-plugins", hash: "#plugins", label: "Plugins", section: "plugins-view", mode: "plugins-mode", activate: "WanGPStudioPlugins" },
    settings: { nav: "nav-settings", hash: "#settings", label: "Settings", section: "settings-view", mode: "settings-mode", activate: "WanGPStudioSettings" }
  };

  // pre-V4.5 hashes keep working: the old views were renamed, not removed
  const HASH_ALIASES = { "#library": "gallery", "#media": "gallery", "#history": "queue" };

  function viewFromHash(hash) {
    const canonical = Object.keys(VIEW_CONFIG).find((name) => VIEW_CONFIG[name].hash === hash);
    return canonical || HASH_ALIASES[hash] || null;
  }

  function setView(view) {
    const config = VIEW_CONFIG[view] || VIEW_CONFIG.workflow;
    state.view = view;
    document.body.classList.toggle("workspace-hidden", Boolean(config.section));
    Object.keys(VIEW_CONFIG).forEach((name) => {
      const item = VIEW_CONFIG[name];
      if (item.section) {
        const section = $(item.section);
        if (section) section.hidden = name !== view;
      }
      if (item.mode) document.body.classList.toggle(item.mode, name === view);
      const nav = $(item.nav);
      if (nav) nav.classList.toggle("active", name === view);
    });
    $("breadcrumb-current").textContent = config.label;
    try { history.replaceState(null, "", config.hash); } catch (_) {}
    if (config.activate && window[config.activate]) window[config.activate].activate();
    if (!config.section && window.WanGPStudioCanvas) window.WanGPStudioCanvas.activate();
  }

  function bindEvents() {
    $("model-search").addEventListener("input", (event) => { state.query = event.target.value; renderModels(); });
    $("model-filters").addEventListener("click", (event) => {
      const button = event.target.closest("[data-filter]");
      if (button) setFilter(button.dataset.filter);
    });
    $("refresh-models").addEventListener("click", loadModels);
    $("refresh-queue").addEventListener("click", refreshJobs);
    $("load-preset").addEventListener("click", loadPreset);
    $("run-generation").addEventListener("click", () => {
      if (window.WanGPStudioCanvas && window.WanGPStudioCanvas.runCurrent) {
        window.WanGPStudioCanvas.runCurrent();
      } else {
        toast("Workflow editor is not ready.", true);
      }
    });
    $("run-from-inspector").addEventListener("click", runGeneration);
    $("apply-to-node").addEventListener("click", applyToNode);
    $("prompt-input").addEventListener("input", () => {
      $("settings-state").textContent = "Unsaved edits";
      try {
        const settings = JSON.parse($("settings-json").value || "{}");
        settings.prompt = $("prompt-input").value;
        $("settings-json").value = JSON.stringify(settings, null, 2);
      } catch (_) {}
    });
    $("settings-json").addEventListener("input", () => {
      try {
        const settings = JSON.parse($("settings-json").value || "{}");
        $("prompt-input").value = typeof settings.prompt === "string" ? settings.prompt : "";
        $("settings-state").textContent = "Unsaved edits";
      } catch (_) {
        $("settings-state").textContent = "Invalid settings JSON";
      }
    });
    $("format-json").addEventListener("click", () => {
      try { $("settings-json").value = JSON.stringify(JSON.parse($("settings-json").value), null, 2); toast("Settings JSON formatted."); }
      catch (error) { toast(error.message, true); }
    });
    $("reset-settings").addEventListener("click", () => {
      if (!state.modelDetail || !state.modelDetail.defaults) return;
      state.currentSettings = state.modelDetail.defaults;
      $("prompt-input").value = state.currentSettings.prompt || "";
      $("settings-json").value = JSON.stringify(state.currentSettings, null, 2);
      $("settings-state").textContent = "Native defaults restored";
    });
    $("clear-selection").addEventListener("click", () => {
      state.selectedModel = null; state.modelDetail = null; state.currentSettings = null;
      $("inspector-empty").hidden = false; $("inspector-editor").hidden = true;
      $("preset-select").innerHTML = '<option>No presets available</option>';
      $("preset-select").disabled = true; $("load-preset").disabled = true;
      $("preset-count").textContent = ""; $("lora-count").textContent = "";
      $("lora-list").innerHTML = '<span class="field-note">Select a model to inspect its LoRAs.</span>';
      $("capability-list").innerHTML = "";
      $("generation-node").hidden = true; $("canvas-hint").hidden = false;
      $("run-from-inspector").disabled = true; $("canvas-model-count").textContent = "No node selected";
      $("settings-state").textContent = "No model selected"; renderModels();
    });
    $("nav-workflow").addEventListener("click", () => setView("workflow"));
    $("nav-gallery").addEventListener("click", () => setView("gallery"));
    $("nav-resources").addEventListener("click", () => setView("resources"));
    $("nav-plugins").addEventListener("click", () => setView("plugins"));
    $("nav-dashboard").addEventListener("click", () => setView("dashboard"));
    $("nav-settings").addEventListener("click", () => setView("settings"));
    $("nav-generate").addEventListener("click", () => setView("generate"));
    $("nav-queue").addEventListener("click", () => setView("queue"));
    $("nav-imageeditor").addEventListener("click", () => setView("imageeditor"));
    $("nav-models").addEventListener("click", () => setView("models"));
    // V4.5 drawers (1024–1439px): the library collapses, the inspector opens
    // as an overlay so the canvas keeps the visual priority
    $("library-toggle").addEventListener("click", () => {
      const collapsed = document.body.classList.toggle("library-collapsed");
      $("library-toggle").setAttribute("aria-pressed", collapsed ? "false" : "true");
    });
    $("inspector-toggle").addEventListener("click", () => {
      const open = document.body.classList.toggle("inspector-open");
      $("inspector-toggle").setAttribute("aria-pressed", open ? "true" : "false");
    });
    $("queue-refresh").addEventListener("click", refreshTasks);
    $("drawer-toggle").addEventListener("click", () => {
      const drawer = $("execution-drawer");
      const collapsed = drawer.classList.toggle("collapsed");
      $("drawer-toggle").setAttribute("aria-expanded", collapsed ? "false" : "true");
      $("drawer-toggle").textContent = collapsed ? "▾" : "▴";
    });
    // V4.5 Image Editor bridge: dependency state from the plugin registry,
    // never a duplicated editor.
    async function refreshImageEditor() {
      try {
        const environment = await api("api/environment");
        const suite = (environment.plugins || []).find((plugin) => plugin.id === "ImageSuite-Wan2GP");
        const state_ = suite ? suite.state : "not_installed";
        $("imageeditor-plugin-state").textContent = state_;
        $("imageeditor-open").hidden = state_ !== "enabled";
        $("imageeditor-goto-plugins").hidden = state_ === "enabled";
        $("imageeditor-message").textContent = state_ === "enabled"
          ? "ImageSuite is installed and enabled. Send images from the Media Center lightbox."
          : state_ === "disabled"
            ? "ImageSuite is installed but disabled — enable it in the Plugins view."
            : "ImageSuite is not installed. Install it with the Plugin Manager, or edit images in the native WanGP UI.";
      } catch (error) {
        $("imageeditor-plugin-state").textContent = "unreachable";
        $("imageeditor-message").textContent = "Could not read the plugin registry: " + error.message;
        $("imageeditor-open").hidden = true;
        $("imageeditor-goto-plugins").hidden = false;
      }
    }
    $("imageeditor-goto-plugins").addEventListener("click", () => setView("plugins"));
    window.WanGPStudioImageEditor = { activate: refreshImageEditor };
    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
        event.preventDefault();
        if (state.view === "gallery") $("gallery-query").focus();
        else $("model-search").focus();
      }
      if ((event.ctrlKey || event.metaKey) && (event.key === "s" || event.key === "S")) {
        if (state.view === "workflow" && window.WanGPStudioCanvas) {
          event.preventDefault();
          window.WanGPStudioCanvas.saveGraph();
        }
      }
    });
  }

  function updateZoom(delta) {
    state.zoom = Math.max(70, Math.min(130, state.zoom + delta));
  }

  window.WanGPStudio = {
    api, esc, toast, setView,
    onNodeSelected,
    selectModel: (modelType) => selectModel(modelType),
    getView: () => state.view,
    getModels: () => state.models.slice(),
    reloadModels: () => loadModels(),
    modelCategory: category,
    modelAvailability: availabilityStatus
  };

  async function init() {
    bindEvents();
    const view = viewFromHash(location.hash);
    if (view) setView(view);
    await loadModels();
    await refreshJobs();
    await refreshTasks();
    window.setInterval(refreshJobs, 5000);
    window.setInterval(refreshTasks, 5000);
    window.setInterval(probeHealth, 30000);
  }
  init();
})();
