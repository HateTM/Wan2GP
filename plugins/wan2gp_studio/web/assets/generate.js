// V4.5 "Generate": quick model -> native queue submission without building a
// graph. Shares the catalog and helpers exposed by studio.js (window.WanGPStudio)
// and the /api endpoints; it never submits through a second backend.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { filter: "all", query: "", models: [], selectedModel: null, detail: null, presets: [] };
  const S = window.WanGPStudio;

  // Input media slots per model capability. The keys are WanGP's native
  // ATTACHMENT_KEYS (wgp.py): the queue consumes them as-is, so nothing
  // invented here reaches the backend.
  const INPUT_KEY_BY_ROLE = { image: "image_guide", video: "video_guide", audio: "audio_guide" };
  const ACCEPT_BY_ROLE = { image: "image/*", video: "video/*", audio: "audio/*" };

  function modelInputs(detail) {
    const meta = detail.metadata || {};
    const schema = detail.schema || {};
    const inputs = meta.inputs || schema.inputs || [];
    return Array.isArray(inputs) ? inputs.map(String) : [];
  }

  // pure helper (unit/e2e-testable): apply an uploaded media path to settings
  function applyInputPath(settings, role, path) {
    const key = INPUT_KEY_BY_ROLE[role];
    if (!key || !path) return settings;
    const next = Object.assign({}, settings);
    if (path) next[key] = String(path);
    return next;
  }

  function renderInputSlots(detail) {
    const host = $("generate-input-slots");
    const roles = modelInputs(detail).filter((role) => INPUT_KEY_BY_ROLE[role]);
    $("generate-inputs").hidden = roles.length === 0;
    const defaults = detail.defaults || {};
    host.innerHTML = roles.map((role) => {
      const key = INPUT_KEY_BY_ROLE[role];
      const current = defaults[key] ? String(defaults[key]) : "";
      return '<div class="input-slot" data-role="' + role + '">' +
        '<span class="input-slot-label">' + S.esc(role) + ' <small>→ ' + S.esc(key) + '</small></span>' +
        '<button class="button button-quiet input-slot-pick" data-role="' + role + '">' + (current ? "Replace file" : "Pick file") + '</button>' +
        (current ? '<button class="button button-quiet input-slot-clear" data-role="' + role + '" title="Remove">✕</button>' : "") +
        '<span class="input-slot-value" data-role="' + role + '">' + (current ? S.esc(current.split(/[\\/]/).pop()) : "not set") + '</span>' +
        '<input type="file" class="input-slot-file" data-role="' + role + '" accept="' + ACCEPT_BY_ROLE[role] + '" hidden></div>';
    }).join("");
    host.querySelectorAll(".input-slot-pick").forEach((button) => button.addEventListener("click", () => {
      const role = button.dataset.role;
      host.querySelector('.input-slot-file[data-role="' + role + '"]').click();
    }));
    host.querySelectorAll(".input-slot-clear").forEach((button) => button.addEventListener("click", () => {
      const role = button.dataset.role;
      const key = INPUT_KEY_BY_ROLE[role];
      let settings;
      try { settings = JSON.parse($("generate-settings-json").value || "{}"); } catch (_) { settings = {}; }
      delete settings[key];
      $("generate-settings-json").value = JSON.stringify(settings, null, 2);
      const slot = host.querySelector('.input-slot-value[data-role="' + role + '"]');
      if (slot) slot.textContent = "not set";
      const pick = host.querySelector('.input-slot-pick[data-role="' + role + '"]');
      if (pick) pick.textContent = "Pick file";
      button.remove();
      $("generate-state").textContent = "Unsaved edits";
    }));
    host.querySelectorAll(".input-slot-file").forEach((input) => input.addEventListener("change", async () => {
      const role = input.dataset.role;
      const file = input.files && input.files[0];
      if (!file) return;
      $("generate-state").textContent = "Uploading " + file.name + "…";
      const form = new FormData();
      form.append("file", file);
      try {
        const response = await fetch("api/media/upload", { method: "POST", body: form, credentials: "same-origin" });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || "Upload failed (" + response.status + ")");
        const path = body.item && body.item.path;
        if (!path) throw new Error("Upload did not return a file path");
        let settings;
        try { settings = JSON.parse($("generate-settings-json").value || "{}"); }
        catch (error) { throw new Error("Settings JSON is invalid — fix it before attaching media"); }
        $("generate-settings-json").value = JSON.stringify(applyInputPath(settings, role, path), null, 2);
        const value = host.querySelector('.input-slot-value[data-role="' + role + '"]');
        if (value) value.textContent = file.name;
        const pick = host.querySelector('.input-slot-pick[data-role="' + role + '"]');
        if (pick) pick.textContent = "Replace file";
        $("generate-state").textContent = "Input attached · edits are local until submitted";
      } catch (error) {
        $("generate-state").textContent = "Upload failed";
        S.toast(error.message, true);
      }
    }));
  }

  function label(model) {
    const meta = model.metadata || model;
    return String(model.name || meta.name || model.model_type || "");
  }

  function renderModels() {
    const query = state.query.trim().toLowerCase();
    const models = state.models.filter((model) => {
      const type = String(model.model_type || "");
      return (!query || (type + " " + label(model)).toLowerCase().includes(query))
        && (state.filter === "all" || S.modelCategory(model) === state.filter);
    });
    const available = state.models.filter((model) => S.modelAvailability(model) === "available").length;
    $("generate-model-count").textContent = available + "/" + state.models.length;
    if (!models.length) {
      $("generate-model-list").innerHTML = state.models.length
        ? '<div class="empty-state">No matching models.</div>'
        : '<div class="empty-state">Model catalog is not loaded yet.</div>';
      return;
    }
    $("generate-model-list").innerHTML = models.map((model) => {
      const type = String(model.model_type || "");
      const kind = S.modelCategory(model);
      const selected = state.selectedModel === type ? " selected" : "";
      const availability = S.modelAvailability(model);
      const availabilityClass = availability === "available" ? " available" : availability === "partial" ? " partial" : "";
      return '<button class="model-card' + selected + '" data-model="' + S.esc(type) + '">' +
        '<span class="model-card-top"><i class="model-indicator ' + kind + '"></i><span class="model-card-name">' +
        S.esc(label(model)) + '</span><i class="availability' + availabilityClass + '"></i></span>' +
        '<span class="model-card-meta">' + S.esc(type) + '</span></button>';
    }).join("");
    $("generate-model-list").querySelectorAll("[data-model]").forEach((button) =>
      button.addEventListener("click", () => selectModel(button.dataset.model)));
  }

  function renderPresets(detail) {
    const entries = detail.presets && Array.isArray(detail.presets.settings) ? detail.presets.settings : [];
    $("generate-preset-count").textContent = entries.length ? String(entries.length) : "";
    $("generate-preset").innerHTML = entries.length
      ? entries.map((entry) => '<option value="' + S.esc(entry.id) + '">' +
          S.esc(entry.type || "setting") + " · " + S.esc(String(entry.id || "").split("/").pop() || entry.id) + "</option>").join("")
      : '<option value="">No presets available</option>';
    $("generate-preset").disabled = entries.length === 0;
    $("generate-load-preset").disabled = entries.length === 0;
  }

  async function selectModel(modelType) {
    const request = Symbol();
    state.modelRequest = request;
    state.selectedModel = modelType;
    state.detail = null;
    renderModels();
    $("generate-empty").hidden = true;
    $("generate-editor").hidden = true;
    $("generate-submit").disabled = true;
    $("generate-state").textContent = "Loading model definition…";
    $("generate-model-state").textContent = "…";
    try {
      const detail = await S.api("api/models/" + encodeURIComponent(modelType));
      if (state.modelRequest !== request) return;
      state.detail = detail;
      const model = detail.model || {};
      $("generate-model-title").textContent = model.name || modelType;
      $("generate-model-state").textContent = S.modelAvailability({ metadata: detail.metadata }) === "missing" ? "files missing" : "ready";
      $("generate-prompt").value = detail.defaults && detail.defaults.prompt || "";
      $("generate-negative").value = detail.defaults && detail.defaults.negative_prompt || "";
      const settings = Object.assign({}, detail.defaults || { model_type: modelType });
      $("generate-settings-json").value = JSON.stringify(settings, null, 2);
      renderPresets(detail);
      renderInputSlots(detail);
      renderAdvancedAttachments();
      $("generate-editor").hidden = false;
      $("generate-state").textContent = "Native WanGP defaults loaded";
      $("generate-submit").disabled = false;
    } catch (error) {
      if (state.modelRequest !== request) return;
      $("generate-state").textContent = "Could not load model";
      $("generate-model-state").textContent = "error";
      S.toast(error.message, true);
    }
  }

  async function loadPreset() {
    if (!state.selectedModel || !$("generate-preset").value) return;
    const modelType = state.selectedModel;
    const modelRequest = state.modelRequest;
    $("generate-load-preset").disabled = true;
    try {
      const settings = await S.api("api/models/" + encodeURIComponent(modelType) +
        "/settings?setting_id=" + encodeURIComponent($("generate-preset").value));
      if (state.modelRequest !== modelRequest) return;
      $("generate-prompt").value = settings.prompt || "";
      $("generate-negative").value = settings.negative_prompt || "";
      $("generate-settings-json").value = JSON.stringify(settings, null, 2);
      $("generate-state").textContent = "Preset loaded · edits are local until submitted";
    } catch (error) {
      if (state.modelRequest === modelRequest) S.toast(error.message, true);
    } finally {
      if (state.modelRequest === modelRequest) $("generate-load-preset").disabled = !$("generate-preset").value;
    }
  }

  async function submit() {
    if (!state.detail || $("generate-submit").disabled) return;
    const detail = state.detail;
    let settings;
    try {
      settings = JSON.parse($("generate-settings-json").value || "{}");
    } catch (error) {
      return S.toast("Settings JSON is invalid: " + error.message, true);
    }
    if (!settings || typeof settings !== "object" || Array.isArray(settings)) {
      return S.toast("Settings must be a JSON object.", true);
    }
    if (settings.model_type && settings.model_type !== state.selectedModel) {
      return S.toast("To change model_type, pick the model from the list first.", true);
    }
    settings.model_type = state.selectedModel;
    settings.prompt = $("generate-prompt").value;
    if ($("generate-negative").value.trim()) settings.negative_prompt = $("generate-negative").value;
    else delete settings.negative_prompt;
    $("generate-submit").disabled = true;
    try {
      await S.api("api/jobs", { method: "POST", body: JSON.stringify({ settings }) });
      S.toast("Task submitted to the native WanGP queue.");
      if (state.detail === detail && S.getView() === "generate") {
        $("generate-state").textContent = "Submitted · watch progress in Queue";
        S.setView("queue");
      } else S.refreshTasks();
    } catch (error) {
      S.toast(error.message, true);
    } finally {
      if (state.detail === detail) $("generate-submit").disabled = false;
    }
  }

  function activate() {
    state.models = S.getModels();
    renderModels();
  }

  function bind() {
    $("generate-model-search").addEventListener("input", (event) => { state.query = event.target.value; renderModels(); });
    $("generate-model-filters").addEventListener("click", (event) => {
      const button = event.target.closest("[data-filter]");
      if (!button) return;
      state.filter = button.dataset.filter;
      $("generate-model-filters").querySelectorAll(".filter-chip").forEach((chip) =>
        chip.classList.toggle("selected", chip === button));
      renderModels();
    });
    $("generate-load-preset").addEventListener("click", loadPreset);
    $("generate-submit").addEventListener("click", submit);
    $("generate-format-json").addEventListener("click", () => {
      try {
        $("generate-settings-json").value = JSON.stringify(JSON.parse($("generate-settings-json").value), null, 2);
      } catch (error) { S.toast(error.message, true); }
    });
  }

  // V4.5 audit: the three role slots cover image/video/audio inputs; every
  // other native WanGP attachment key stays reachable visually (the JSON
  // editor remains the source of truth).
  const ADVANCED_KEYS = [
    "image_start", "image_end", "image_refs", "image_mask",
    "video_guide2", "video_guide3", "video_mask",
    "audio_guide2", "audio_guide3", "custom_guide"
  ];

  function currentSettings() {
    try { return JSON.parse($("generate-settings-json").value || "{}") || {}; }
    catch (_) { return {}; }
  }

  function updateAdvancedValue() {
    const key = $("generate-advanced-key").value;
    const value = currentSettings()[key];
    $("generate-advanced-value").textContent = value ? String(value).split(/[\/]/).pop() : "not set";
    $("generate-advanced-clear").hidden = !value;
  }

  function renderAdvancedAttachments() {
    const section = $("generate-advanced");
    section.hidden = false;
    $("generate-advanced-key").innerHTML = ADVANCED_KEYS.map((key) =>
      '<option value="' + key + '">' + key + "</option>").join("");
    updateAdvancedValue();
  }

  async function uploadToKey(file) {
    $("generate-state").textContent = "Uploading " + file.name + "…";
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("api/media/upload", { method: "POST", body: form, credentials: "same-origin" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || "Upload failed (" + response.status + ")");
    const path = body.item && body.item.path;
    if (!path) throw new Error("Upload did not return a file path");
    return path;
  }

  function bindAdvancedAttachments() {
    $("generate-advanced-key").addEventListener("change", updateAdvancedValue);
    $("generate-advanced-pick").addEventListener("click", () => $("generate-advanced-file").click());
    $("generate-advanced-file").addEventListener("change", async () => {
      const file = $("generate-advanced-file").files && $("generate-advanced-file").files[0];
      if (!file) return;
      try {
        const path = await uploadToKey(file);
        const settings = currentSettings();
        settings[$("generate-advanced-key").value] = path;
        $("generate-settings-json").value = JSON.stringify(settings, null, 2);
        updateAdvancedValue();
        $("generate-state").textContent = "Input attached · edits are local until submitted";
      } catch (error) {
        $("generate-state").textContent = "Upload failed";
        S.toast(error.message, true);
      } finally {
        $("generate-advanced-file").value = "";
      }
    });
    $("generate-advanced-clear").addEventListener("click", () => {
      const settings = currentSettings();
      delete settings[$("generate-advanced-key").value];
      $("generate-settings-json").value = JSON.stringify(settings, null, 2);
      updateAdvancedValue();
      $("generate-state").textContent = "Unsaved edits";
    });
  }

  bindAdvancedAttachments();

  window.WanGPStudioGenerate = {
    activate,
    // Models page deep link: open Generate with a model already selected
    preset: (modelType) => { activate(); selectModel(modelType); },
    applyInputPath
  };
  bind();
})();
