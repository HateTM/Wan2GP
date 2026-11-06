// V4.5 "Generate": quick model -> native queue submission without building a
// graph. Shares the catalog and helpers exposed by studio.js (window.WanGPStudio)
// and the /api endpoints; it never submits through a second backend.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { filter: "all", query: "", models: [], selectedModel: null, detail: null, presets: [] };
  const S = window.WanGPStudio;

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
    state.selectedModel = modelType;
    renderModels();
    $("generate-empty").hidden = true;
    $("generate-editor").hidden = false;
    $("generate-submit").disabled = true;
    $("generate-state").textContent = "Loading model definition…";
    $("generate-model-state").textContent = "…";
    try {
      const detail = await S.api("api/models/" + encodeURIComponent(modelType));
      if (state.selectedModel !== modelType) return;
      state.detail = detail;
      const model = detail.model || {};
      $("generate-model-title").textContent = model.name || modelType;
      $("generate-model-state").textContent = S.modelAvailability({ metadata: detail.metadata }) === "missing" ? "files missing" : "ready";
      $("generate-prompt").value = detail.defaults && detail.defaults.prompt || "";
      $("generate-negative").value = detail.defaults && detail.defaults.negative_prompt || "";
      const settings = Object.assign({}, detail.defaults || { model_type: modelType });
      $("generate-settings-json").value = JSON.stringify(settings, null, 2);
      renderPresets(detail);
      $("generate-state").textContent = "Native WanGP defaults loaded";
      $("generate-submit").disabled = false;
    } catch (error) {
      if (state.selectedModel !== modelType) return;
      $("generate-state").textContent = "Could not load model";
      $("generate-model-state").textContent = "error";
      S.toast(error.message, true);
    }
  }

  async function loadPreset() {
    if (!state.selectedModel || !$("generate-preset").value) return;
    const modelType = state.selectedModel;
    $("generate-load-preset").disabled = true;
    try {
      const settings = await S.api("api/models/" + encodeURIComponent(modelType) +
        "/settings?setting_id=" + encodeURIComponent($("generate-preset").value));
      if (state.selectedModel !== modelType) return;
      $("generate-prompt").value = settings.prompt || "";
      $("generate-negative").value = settings.negative_prompt || "";
      $("generate-settings-json").value = JSON.stringify(settings, null, 2);
      $("generate-state").textContent = "Preset loaded · edits are local until submitted";
    } catch (error) {
      S.toast(error.message, true);
    } finally {
      if (state.selectedModel === modelType) $("generate-load-preset").disabled = !$("generate-preset").value;
    }
  }

  async function submit() {
    if (!state.selectedModel) return;
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
      $("generate-state").textContent = "Submitted · watch progress in Queue";
      S.setView("queue");
    } catch (error) {
      S.toast(error.message, true);
    } finally {
      $("generate-submit").disabled = false;
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
    $("generate-run").addEventListener("click", submit);
    $("generate-format-json").addEventListener("click", () => {
      try {
        $("generate-settings-json").value = JSON.stringify(JSON.parse($("generate-settings-json").value), null, 2);
      } catch (error) { S.toast(error.message, true); }
    });
  }

  window.WanGPStudioGenerate = { activate };
  bind();
})();
