// V4.5 "Models" (MANAGE): read-only catalog page — availability, capabilities,
// presets and LoRA inventory per model. Generation actions live in Generate /
// Workflow; destructive model operations belong to the bundled Models Manager.
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { filter: "all", query: "", models: [], selectedModel: null };
  const S = window.WanGPStudio;

  function label(model) {
    const meta = model.metadata || model;
    return String(model.name || meta.name || model.model_type || "");
  }

  function family(model) {
    const meta = model.metadata || model;
    return String(meta.family_label || meta.family || "") || "other";
  }

  function render() {
    const query = state.query.trim().toLowerCase();
    const models = state.models.filter((model) => {
      const type = String(model.model_type || "");
      return (!query || (type + " " + label(model) + " " + family(model)).toLowerCase().includes(query))
        && (state.filter === "all" || S.modelCategory(model) === state.filter);
    });
    const available = state.models.filter((model) => S.modelAvailability(model) === "available").length;
    $("models-count").textContent = available + "/" + state.models.length;
    if (!models.length) {
      $("models-list").innerHTML = state.models.length
        ? '<div class="empty-state">No matching models.</div>'
        : '<div class="empty-state">Model catalog is not loaded yet.</div>';
      return;
    }
    $("models-list").innerHTML = models.map((model) => {
      const type = String(model.model_type || "");
      const kind = S.modelCategory(model);
      const selected = state.selectedModel === type ? " selected" : "";
      const availability = S.modelAvailability(model);
      const availabilityClass = availability === "available" ? " available" : availability === "partial" ? " partial" : "";
      const availabilityTitle = availability === "available" ? "Model files available"
        : availability === "partial" ? "Model files partially available"
        : availability === "missing" ? "Model files missing" : "Availability not confirmed";
      return '<button class="model-card' + selected + '" data-model="' + S.esc(type) + '">' +
        '<span class="model-card-top"><i class="model-indicator ' + kind + '"></i><span class="model-card-name">' +
        S.esc(label(model)) + '</span><i class="availability' + availabilityClass + '" title="' + availabilityTitle + '"></i></span>' +
        '<span class="model-card-meta">' + S.esc(family(model)) + ' · ' + S.esc(type) + '</span></button>';
    }).join("");
    $("models-list").querySelectorAll("[data-model]").forEach((button) =>
      button.addEventListener("click", () => selectModel(button.dataset.model)));
  }

  async function selectModel(modelType) {
    state.selectedModel = modelType;
    render();
    $("models-detail-empty").hidden = true;
    $("models-detail").hidden = false;
    $("models-open-generate").disabled = true;
    $("models-detail-note").textContent = "Loading model definition…";
    $("models-detail-availability").textContent = "";
    try {
      const detail = await S.api("api/models/" + encodeURIComponent(modelType));
      if (state.selectedModel !== modelType) return;
      const model = detail.model || {};
      const meta = detail.metadata || {};
      $("models-detail-name").textContent = model.name || modelType;
      $("models-detail-title").textContent = model.name || modelType;
      $("models-detail-type").textContent = modelType;
      const availability = S.modelAvailability({ metadata: meta });
      $("models-detail-availability").textContent = availability === "unknown" ? "" : availability;
      const values = [];
      ["family_label", "base_model_type", "size", "accelerated"].forEach((key) => {
        if (meta[key] !== undefined && meta[key] !== null && meta[key] !== "") values.push(String(meta[key]));
      });
      ["inputs", "main_output", "media_roles", "specialities"].forEach((key) => {
        const value = (detail.schema || {})[key] || meta[key];
        if (Array.isArray(value)) value.forEach((item) => values.push(String(item)));
      });
      const unique = Array.from(new Set(values)).slice(0, 24);
      $("models-capabilities").innerHTML = unique.length
        ? unique.map((value) => '<span class="capability-chip">' + S.esc(value) + '</span>').join("")
        : '<span class="field-note">No capability metadata was returned.</span>';
      const presets = detail.presets && Array.isArray(detail.presets.settings) ? detail.presets.settings : [];
      $("models-preset-count").textContent = presets.length ? String(presets.length) : "";
      $("models-presets").innerHTML = presets.length
        ? presets.map((entry) => '<span class="capability-chip">' +
            S.esc(entry.type || "setting") + " · " + S.esc(String(entry.id || "").split("/").pop() || entry.id) + '</span>').join("")
        : '<span class="field-note">No presets available.</span>';
      const loras = detail.loras && Array.isArray(detail.loras.loras) ? detail.loras.loras : [];
      $("models-lora-count").textContent = detail.loras && detail.loras.supported === false ? "N/A" : String(loras.length);
      $("models-loras").innerHTML = detail.loras && detail.loras.error
        ? '<span class="field-note">' + S.esc(detail.loras.error) + '</span>'
        : detail.loras && detail.loras.supported === false
          ? '<span class="field-note">This model does not support LoRAs.</span>'
          : loras.length
            ? loras.map((name) => '<span class="capability-chip">' + S.esc(name) + '</span>').join("")
            : '<span class="field-note">No LoRAs found in the model folder.</span>';
      $("models-detail-note").textContent = "Read-only · generation runs in Generate or Workflow";
      $("models-open-generate").disabled = false;
    } catch (error) {
      if (state.selectedModel !== modelType) return;
      $("models-detail-note").textContent = "Could not load model";
      S.toast(error.message, true);
    }
  }

  function openInGenerate() {
    if (!state.selectedModel) return;
    S.setView("generate");
    if (window.WanGPStudioGenerate && window.WanGPStudioGenerate.preset) {
      window.WanGPStudioGenerate.preset(state.selectedModel);
    }
  }

  function activate() {
    state.models = S.getModels();
    render();
  }

  function bind() {
    $("models-search").addEventListener("input", (event) => { state.query = event.target.value; render(); });
    $("models-filters").addEventListener("click", (event) => {
      const button = event.target.closest("[data-filter]");
      if (!button) return;
      state.filter = button.dataset.filter;
      $("models-filters").querySelectorAll(".filter-chip").forEach((chip) =>
        chip.classList.toggle("selected", chip === button));
      render();
    });
    $("models-refresh").addEventListener("click", async () => {
      // the shared catalog lives in studio.js: await the real reload, then
      // re-render (a fixed delay races the catalog fetch)
      $("models-refresh").disabled = true;
      try {
        await S.reloadModels();
        activate();
      } finally {
        $("models-refresh").disabled = false;
      }
    });
    $("models-open-generate").addEventListener("click", openInGenerate);
  }

  window.WanGPStudioModels = { activate };
  bind();
})();
