(() => {
  "use strict";
  const state = { models: [], selectedModel: null, modelDetail: null, currentSettings: null, filter: "all", query: "", jobs: new Map(), eventSources: new Map(), zoom: 100, view: "workflow" };
  const $ = (id) => document.getElementById(id);
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
      heading.innerHTML = '<div class="inspector-empty-icon">☑</div><strong>Node: ' + S.esc(node.title || node.type) +
        '</strong><span>' + S.esc(node.type) + (node.params && node.params.path ? " · " + S.esc(node.params.path) : "") + "</span>";
    }
    const modelType = node.params && node.params.model_type;
    if (modelType) {
      selectModel(modelType).then(() => {
        const promptBox = document.getElementById("prompt-input");
        if (promptBox && node.params && node.params.prompt) promptBox.value = node.params.prompt;
        state.nodeSelected = node;
        const apply = document.getElementById("apply-to-node");
        if (apply) apply.hidden = false;
      }).catch(() => {});
    } else {
      // input/ffmpeg nodes: no model settings, but expose the path
      const editor = document.getElementById("inspector-editor");
      const json = document.getElementById("settings-json");
      if (editor && json) {
        editor.hidden = false;
        json.value = JSON.stringify(node.params || {}, null, 2);
      }
      state.nodeSelected = node;
      const apply = document.getElementById("apply-to-node");
      if (apply) apply.hidden = false;
    }
  }

  async function applyToNode() {
    const node = state.nodeSelected;
    if (!node) return;
    let settings = null;
    try {
      settings = JSON.parse(document.getElementById("settings-json").value || "{}");
    } catch (error) {
      toast("Settings JSON is invalid.", true);
      return;
    }
    const prompt = document.getElementById("prompt-input").value;
    const modelType = settings.model_type || (node.params && node.params.model_type) || null;
    const applied = window.WanGPStudioCanvas.applyToSelectedNode({
      settings: settings,
      prompt: prompt,
      model_type: modelType
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
      $("runtime-state").textContent = "API ready";
      $("canvas-model-count").textContent = state.models.length + " models available";
    } catch (error) {
      $("api-status").textContent = "WanGP API unavailable";
      $("runtime-state").textContent = "Not ready";
      toast(error.message, true);
      $("model-list").innerHTML = '<div class="empty-state">' + esc(error.message) + '</div>';
    }
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

  function renderJobs() {
    const records = Array.from(state.jobs.values()).sort((a, b) => b.created_at - a.created_at);
    $("queue-count").textContent = String(records.length);
    if (!records.length) {
      $("queue-list").innerHTML = '<div class="queue-empty">No Studio jobs yet. Run a model to see execution progress here.</div>';
      return;
    }
    $("queue-list").innerHTML = records.slice(0, 20).map((job) => {
      const status = String(job.status || "queued");
      const cls = status === "completed" || status === "failed" ? " " + status : "";
      const cancel = status === "completed" || status === "failed" || status === "cancelled" ? "" : '<button class="cancel-job" data-cancel="' + esc(job.id) + '">Cancel</button>';
      // Generation History: a finished job can be repeated with its original settings
      const repeat = status === "completed" || status === "failed" ? '<button class="cancel-job" data-repeat="' + esc(job.id) + '">Repeat</button>' : "";
      const files = (job.generated_files || []).slice(0, 3);
      const filesHtml = files.length
        ? '<div class="queue-files"><button class="queue-file" data-open-gallery="' + esc(job.id) + '">View ' + files.length +
          ' result(s) in Gallery</button></div>' : "";
      return '<article class="queue-card"><div class="queue-card-top"><span class="queue-card-title">' + esc(job.model_type) +
        '</span><span class="queue-state' + cls + '">' + esc(status) + '</span></div><div class="queue-card-message">' +
        esc(job.message || job.prompt || "") + '</div><div class="queue-progress"><span style="width:' +
        Math.max(0, Math.min(100, Number(job.progress) || 0)) + '%"></span></div>' + filesHtml + repeat + cancel + '</article>';
    }).join("");
    $("queue-list").querySelectorAll("[data-cancel]").forEach((button) => button.addEventListener("click", () => cancelJob(button.dataset.cancel)));
    $("queue-list").querySelectorAll("[data-repeat]").forEach((button) => button.addEventListener("click", () => repeatJob(button.dataset.repeat)));
    $("queue-list").querySelectorAll("[data-open-gallery]").forEach((button) => button.addEventListener("click", () => setView("gallery")));
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
    gallery: { nav: "nav-gallery", hash: "#gallery", label: "Gallery", section: "gallery-view", mode: "gallery-mode", activate: "WanGPStudioGallery" },
    resources: { nav: "nav-resources", hash: "#resources", label: "Resources", section: "resource-view", mode: "resources-mode", activate: "WanGPStudioTelemetry" },
    plugins: { nav: "nav-plugins", hash: "#plugins", label: "Plugins", section: "plugins-view", mode: "plugins-mode", activate: "WanGPStudioPlugins" },
    settings: { nav: "nav-settings", hash: "#settings", label: "Settings", section: "settings-view", mode: "settings-mode", activate: "WanGPStudioSettings" }
  };

  function setView(view) {
    const config = VIEW_CONFIG[view] || VIEW_CONFIG.workflow;
    state.view = view;
    document.body.classList.toggle("workspace-hidden", Boolean(config.section));
    Object.keys(VIEW_CONFIG).forEach((name) => {
      const item = VIEW_CONFIG[name];
      if (item.section) $(item.section).hidden = name !== view;
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
    document.querySelectorAll(".library-item").forEach((button) => button.addEventListener("click", () => setFilter(button.dataset.filter)));
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
    $("nav-models").addEventListener("click", () => $("model-search").focus());
    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
        event.preventDefault();
        if (state.view === "gallery") $("gallery-query").focus();
        else $("model-search").focus();
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
    getView: () => state.view
  };

  async function init() {
    bindEvents();
    if (location.hash === "#gallery") setView("gallery");
    await loadModels();
    await refreshJobs();
    window.setInterval(refreshJobs, 5000);
  }
  init();
})();
