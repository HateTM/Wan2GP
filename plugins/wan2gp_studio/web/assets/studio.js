(() => {
  "use strict";
  const state = { models: [], selectedModel: null, modelDetail: null, currentSettings: null, filter: "all", query: "", jobs: new Map(), eventSources: new Map(), zoom: 100 };
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
    if (!response.ok) throw new Error(body.detail || body.message || "Request failed (" + response.status + ")");
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

  function available(model) {
    const value = model.availability || model.metadata && model.metadata.availability;
    if (typeof value === "boolean") return value;
    if (value && typeof value === "object") {
      if ("available" in value) return Boolean(value.available);
      if ("ready" in value) return Boolean(value.ready);
      const entries = Object.values(value);
      if (entries.length && entries.every((entry) => typeof entry === "boolean")) return entries.every(Boolean);
    }
    return false;
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
    $("model-count").textContent = String(state.models.length);
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
      const ready = available(model) ? " available" : "";
      return '<button class="model-card' + selected + '" data-model="' + esc(type) + '">' +
        '<span class="model-card-top"><i class="model-indicator ' + kind + '"></i><span class="model-card-name">' + esc(name) +
        '</span><i class="availability' + ready + '" title="' + (ready ? "Available" : "Availability not confirmed") + '"></i></span>' +
        '<span class="model-card-meta">' + esc(family) + ' · ' + esc(type) + '</span></button>';
    }).join("");
    $("model-list").querySelectorAll("[data-model]").forEach((button) => button.addEventListener("click", () => selectModel(button.dataset.model)));
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
    $("lora-list").innerHTML = data.supported === false
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
      $("settings-state").textContent = "Could not load model";
      $("node-status").textContent = "Error";
      toast(error.message, true);
    }
  }

  async function loadModels() {
    $("api-status").textContent = "Loading model catalog…";
    $("runtime-state").textContent = "Loading…";
    try {
      state.models = await api("api/models?limit=300");
      renderModels();
      $("api-status").textContent = state.models.length + " models · WanGP API connected";
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
    settings.prompt = $("prompt-input").value;
    if (!settings.model_type && state.selectedModel) settings.model_type = state.selectedModel;
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
      $("load-preset").disabled = false;
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
      $("run-from-inspector").disabled = false;
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
      return '<article class="queue-card"><div class="queue-card-top"><span class="queue-card-title">' + esc(job.model_type) +
        '</span><span class="queue-state' + cls + '">' + esc(status) + '</span></div><div class="queue-card-message">' +
        esc(job.message || job.prompt || "") + '</div><div class="queue-progress"><span style="width:' +
        Math.max(0, Math.min(100, Number(job.progress) || 0)) + '%"></span></div>' + cancel + '</article>';
    }).join("");
    $("queue-list").querySelectorAll("[data-cancel]").forEach((button) => button.addEventListener("click", () => cancelJob(button.dataset.cancel)));
  }

  async function refreshJobs() {
    try {
      const records = await api("api/jobs");
      records.forEach((record) => state.jobs.set(record.id, record));
      renderJobs();
    } catch (_) {}
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
        if (message.kind === "progress") {
          const previous = state.jobs.get(jobId) || { id: jobId };
          state.jobs.set(jobId, Object.assign({}, previous, {
            progress: message.data.progress, phase: message.data.phase, message: message.data.status, status: "running"
          }));
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
    $("run-generation").addEventListener("click", runGeneration);
    $("run-from-inspector").addEventListener("click", runGeneration);
    $("prompt-input").addEventListener("input", () => {
      $("settings-state").textContent = "Unsaved edits";
      try {
        const settings = JSON.parse($("settings-json").value || "{}");
        settings.prompt = $("prompt-input").value;
        $("settings-json").value = JSON.stringify(settings, null, 2);
      } catch (_) {}
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
    $("zoom-in").addEventListener("click", () => updateZoom(10));
    $("zoom-out").addEventListener("click", () => updateZoom(-10));
    $("nav-models").addEventListener("click", () => $("model-search").focus());
    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
        event.preventDefault(); $("model-search").focus();
      }
    });
  }

  function updateZoom(delta) {
    state.zoom = Math.max(70, Math.min(130, state.zoom + delta));
    $("zoom-value").textContent = state.zoom + "%";
    $("workflow-canvas").style.backgroundSize = (18 * state.zoom / 100) + "px " + (18 * state.zoom / 100) + "px";
  }

  async function init() {
    bindEvents();
    await loadModels();
    await refreshJobs();
    window.setInterval(refreshJobs, 5000);
  }
  init();
})();
