(() => {
  "use strict";
  const S = window.WanGPStudio;
  if (!S) return;
  const $ = (id) => document.getElementById(id);
  const esc = S.esc;
  const api = S.api;
  const toast = S.toast;

  const PAGE = 200;
  const GAP = 12;
  const KIND_LABEL = { image: "IMAGE", video: "VIDEO", audio: "AUDIO", world: "WORLD", "3d": "3D", app: "APP" };
  const META_ONLY_KEYS = ["output_role", "model_filename", "generation_time", "creation_date", "creation_timestamp"];

  const state = {
    items: [],
    total: 0,
    offset: 0,
    loading: false,
    loadedOnce: false,
    active: false,
    kind: "",
    query: "",
    sort: "date_desc",
    selected: new Set(),
    selectMode: false,
    detail: null,
    columns: 1,
    cardWidth: 210,
    rowHeight: 180,
    cards: new Map(),
    error: null,
    queryTimer: null,
    ticking: false
  };

  function fmtSize(bytes) {
    const value = Number(bytes) || 0;
    if (value >= 1024 * 1024 * 1024) return (value / 1024 / 1024 / 1024).toFixed(2) + " GB";
    if (value >= 1024 * 1024) return (value / 1024 / 1024).toFixed(1) + " MB";
    if (value >= 1024) return Math.round(value / 1024) + " KB";
    return value + " B";
  }

  function fmtDuration(seconds) {
    const total = Math.max(0, Math.round(Number(seconds) || 0));
    const minutes = Math.floor(total / 60);
    const rest = String(total % 60).padStart(2, "0");
    return minutes + ":" + rest;
  }

  function fmtDate(timestamp) {
    const value = Number(timestamp) || 0;
    if (!value) return "—";
    const date = new Date(value * 1000);
    return date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function metaLine(item) {
    const parts = [];
    if (item.kind === "image" && item.width) parts.push(item.width + "×" + item.height);
    else if (item.kind === "world" && item.resolution) parts.push(item.resolution);
    else if (item.kind === "video" && item.duration) parts.push(fmtDuration(item.duration));
    else if (item.kind === "audio" && item.duration) parts.push(fmtDuration(item.duration));
    if (item.model_type) parts.push(item.model_type);
    parts.push(fmtSize(item.size));
    return parts.join(" · ");
  }

  function renderEmpty() {
    const element = $("gallery-empty");
    if (state.error) {
      element.hidden = false;
      element.textContent = "Media API unavailable: " + state.error;
      return;
    }
    if (state.loading && !state.items.length) {
      element.hidden = false;
      element.textContent = "Indexing media roots…";
      return;
    }
    if (!state.items.length) {
      element.hidden = false;
      element.textContent = state.query || state.kind
        ? "No media matches the current filters."
        : "No media yet. Generate something in WanGP or drop files here.";
      return;
    }
    element.hidden = true;
  }

  async function load(reset) {
    if (state.loading) return;
    state.loading = true;
    if (reset) {
      state.items = [];
      state.total = 0;
      state.offset = 0;
      state.error = null;
      state.cards.clear();
      $("gallery-window").replaceChildren();
      $("gallery-spacer").style.height = "0px";
      renderEmpty();
    }
    try {
      const params = new URLSearchParams({ limit: PAGE, offset: state.offset, sort: state.sort });
      if (state.kind) params.set("kind", state.kind);
      if (state.query.trim()) params.set("q", state.query.trim());
      const page = await api("api/media?" + params.toString());
      state.total = Number(page.total) || 0;
      state.items = reset ? page.items : state.items.concat(page.items);
      state.offset = state.items.length;
      state.loadedOnce = true;
      const count = $("gallery-nav-count");
      count.hidden = false;
      count.textContent = String(state.total);
      $("gallery-summary").textContent = state.total + " items · " + state.items.length + " loaded · WanGP output roots";
      layout();
      render();
    } catch (error) {
      state.error = error.message;
      $("gallery-summary").textContent = "Media API unavailable";
      renderEmpty();
    } finally {
      state.loading = false;
      renderEmpty();
    }
  }

  function layout() {
    const viewport = $("gallery-viewport");
    const width = Math.max(320, viewport.clientWidth - 28);
    const cardWidth = Math.max(168, Math.min(238, Math.round((width - GAP * 3) / 4)));
    const columns = Math.max(2, Math.floor((width + GAP) / (cardWidth + GAP)));
    state.cardWidth = cardWidth;
    state.columns = columns;
    state.rowHeight = Math.round(cardWidth * 9 / 16) + 46 + GAP;
    const rows = Math.ceil(state.items.length / columns);
    $("gallery-spacer").style.height = rows * state.rowHeight + "px";
    const windowEl = $("gallery-window");
    windowEl.style.gridTemplateColumns = "repeat(" + columns + ", " + cardWidth + "px)";
    windowEl.style.gap = GAP + "px";
  }

  function calibrate() {
    const card = $("gallery-window").firstElementChild;
    if (!card) return;
    const measured = card.getBoundingClientRect().height + GAP;
    if (measured > 60 && Math.abs(measured - state.rowHeight) > 2) {
      state.rowHeight = measured;
      const rows = Math.ceil(state.items.length / state.columns);
      $("gallery-spacer").style.height = rows * state.rowHeight + "px";
    }
  }

  function buildCard(item) {
    const card = document.createElement("div");
    card.className = "media-card" + (state.selected.has(item.id) ? " selected" : "");
    card.dataset.id = item.id;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", item.name);
    const duration = (item.kind === "video" || item.kind === "audio") && item.duration
      ? '<span class="media-duration">' + esc(fmtDuration(item.duration)) + "</span>" : "";
    card.innerHTML =
      '<span class="media-thumb"><img alt="" loading="lazy" src="api/media/' + encodeURIComponent(item.id) + '/thumbnail">' +
      '<span class="media-badge">' + esc(KIND_LABEL[item.kind] || item.kind) + "</span>" + duration + "</span>" +
      '<span class="media-caption"><span class="media-name">' + esc(item.name) + "</span>" +
      '<span class="media-meta">' + esc(metaLine(item)) + "</span></span>" +
      '<input type="checkbox" class="media-check" aria-label="Select media"' + (state.selected.has(item.id) ? " checked" : "") + ">";
    const image = card.querySelector("img");
    image.addEventListener("error", () => { card.classList.add("broken"); image.remove(); });
    card.addEventListener("click", (event) => {
      if (event.target.closest(".media-check")) return;
      if (state.selectMode) toggleSelection(item.id, card);
      else openLightbox(item.id);
    });
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        if (state.selectMode) toggleSelection(item.id, card);
        else openLightbox(item.id);
      }
    });
    card.querySelector(".media-check").addEventListener("change", () => toggleSelection(item.id, card));
    return card;
  }

  function render() {
    if (!state.active) return;
    const viewport = $("gallery-viewport");
    const rowHeight = Math.max(1, state.rowHeight);
    const firstRow = Math.max(0, Math.floor(viewport.scrollTop / rowHeight) - 1);
    const rowsVisible = Math.ceil(viewport.clientHeight / rowHeight) + 3;
    const start = firstRow * state.columns;
    const end = Math.min(state.items.length, start + rowsVisible * state.columns);
    const windowEl = $("gallery-window");
    const nodes = [];
    const keep = new Set();
    for (let index = start; index < end; index += 1) {
      const item = state.items[index];
      keep.add(item.id);
      let card = state.cards.get(item.id);
      if (!card) {
        card = buildCard(item);
        state.cards.set(item.id, card);
      }
      nodes.push(card);
    }
    for (const [id, card] of state.cards) {
      if (!keep.has(id)) {
        card.remove();
        state.cards.delete(id);
      }
    }
    windowEl.replaceChildren.apply(windowEl, nodes);
    windowEl.style.transform = "translateY(" + firstRow * rowHeight + "px)";
    calibrate();
    const nearBottom = viewport.scrollTop + viewport.clientHeight > viewport.scrollHeight - 640;
    if (nearBottom && !state.loading && state.items.length < state.total) load(false);
  }

  function onScroll() {
    if (state.ticking) return;
    state.ticking = true;
    requestAnimationFrame(() => {
      state.ticking = false;
      render();
    });
  }

  function toggleSelection(id, card) {
    if (state.selected.has(id)) state.selected.delete(id);
    else state.selected.add(id);
    card.classList.toggle("selected", state.selected.has(id));
    const box = card.querySelector(".media-check");
    if (box) box.checked = state.selected.has(id);
    updateSelectionBar();
  }

  function updateSelectionBar() {
    const bar = $("gallery-selection");
    bar.hidden = !state.selectMode;
    $("gallery-selected-count").textContent = state.selected.size + " selected";
    $("gallery-delete-selected").disabled = state.selected.size === 0;
    $("gallery-clear-selection").disabled = state.selected.size === 0;
  }

  function setSelectMode(enabled) {
    state.selectMode = enabled;
    document.body.classList.toggle("select-mode", enabled);
    $("gallery-select-mode").textContent = enabled ? "Cancel selection" : "Select";
    if (!enabled) {
      state.selected.clear();
      for (const card of state.cards.values()) {
        card.classList.remove("selected");
        const box = card.querySelector(".media-check");
        if (box) box.checked = false;
      }
    }
    updateSelectionBar();
  }

  async function deleteMedia(ids, label) {
    if (!ids.length) return;
    if (!window.confirm("Delete " + (label || ids.length + " file(s)") + " permanently? This cannot be undone.")) return;
    let deleted = 0;
    for (const id of ids) {
      try {
        await api("api/media/" + encodeURIComponent(id) + "?confirm=true", { method: "DELETE" });
        deleted += 1;
      } catch (error) {
        toast(error.message, true);
      }
    }
    if (deleted) toast("Deleted " + deleted + " file(s).");
    if (state.detail && ids.includes(state.detail.item.id)) closeLightbox();
    await load(true);
    setSelectMode(false);
  }

  async function openLightbox(id) {
    const dialog = $("lightbox");
    state.detail = null;
    $("lightbox-stage").innerHTML = '<div class="lightbox-loading">Loading media…</div>';
    $("lightbox-name").textContent = "Loading…";
    $("lightbox-kind").textContent = "MEDIA";
    $("lightbox-facts").innerHTML = "";
    $("lightbox-prompt").textContent = "—";
    $("lightbox-path").textContent = "";
    $("lightbox-download").setAttribute("href", "api/media/" + encodeURIComponent(id) + "/file");
    if (!dialog.open) dialog.showModal();
    try {
      const detail = await api("api/media/" + encodeURIComponent(id));
      state.detail = detail;
      renderLightbox(detail);
    } catch (error) {
      $("lightbox-stage").innerHTML = '<div class="lightbox-loading">' + esc(error.message) + "</div>";
    }
  }

  function factRow(label, value) {
    if (value === undefined || value === null || value === "") return "";
    return "<span>" + esc(label) + "</span><span>" + esc(String(value)) + "</span>";
  }

  function renderLightbox(detail) {
    const item = detail.item || {};
    const metadata = detail.metadata || null;
    const world = detail.world || null;
    const fileUrl = "api/media/" + encodeURIComponent(item.id) + "/file";
    $("lightbox-name").textContent = item.name || "Media";
    $("lightbox-kind").textContent = (KIND_LABEL[item.kind] || "MEDIA") + " · " + (item.kind || "");
    const stage = $("lightbox-stage");
    stage.replaceChildren();
    if (item.kind === "video") {
      const video = document.createElement("video");
      video.controls = true;
      video.playsInline = true;
      video.preload = "metadata";
      video.src = fileUrl;
      video.poster = "api/media/" + encodeURIComponent(item.id) + "/thumbnail";
      stage.appendChild(video);
    } else if (item.kind === "audio") {
      const audio = document.createElement("audio");
      audio.controls = true;
      audio.src = fileUrl;
      stage.appendChild(audio);
    } else {
      const image = document.createElement("img");
      image.alt = item.name || "";
      image.src = item.kind === "world" ? "api/media/" + encodeURIComponent(item.id) + "/thumbnail" : fileUrl;
      stage.appendChild(image);
      if (item.kind === "world") {
        const note = document.createElement("p");
        note.className = "field-note";
        note.textContent = "World preview. Exploration controls live in the WanGP Worlds gallery.";
        stage.appendChild(note);
      }
    }
    const facts = [
      factRow("Type", KIND_LABEL[item.kind] || item.kind),
      factRow("Size", fmtSize(item.size)),
      factRow("Dimensions", item.width ? item.width + "×" + item.height : (item.resolution || "")),
      factRow("Duration", item.duration ? fmtDuration(item.duration) : ""),
      factRow("FPS", item.fps),
      factRow("Segments", item.segment_count),
      factRow("Seed", item.seed !== null && item.seed !== undefined ? item.seed : (metadata && metadata.seed)),
      factRow("Model", (metadata && metadata.model_type) || item.model_type),
      factRow("Created", fmtDate(item.mtime)),
      factRow("Folder", item.relative)
    ].join("");
    $("lightbox-facts").innerHTML = facts || '<span class="field-note">No facts available.</span>';
    const prompt = (metadata && metadata.prompt) || item.prompt_hint || "";
    $("lightbox-prompt").textContent = prompt || "—";
    $("lightbox-path").textContent = item.path || "";
    $("lightbox-reuse").disabled = !((metadata && metadata.model_type) || item.model_type);
    const download = $("lightbox-download");
    download.setAttribute("href", fileUrl);
    download.setAttribute("download", item.name || "media");
    if (world && world.segments) {
      const segments = document.createElement("div");
      segments.className = "lightbox-segments";
      segments.innerHTML = '<div class="section-title"><span>WORLD SEGMENTS</span></div>' +
        world.segments.slice(0, 8).map((segment) => '<div class="segment-row"><span>' +
          esc((segment.start_seconds ?? 0) + "–" + (segment.end_seconds ?? 0) + "s") + "</span><span>" +
          esc(segment.instruction || segment.description || "") + "</span></div>").join("");
      $("lightbox-facts").appendChild(segments);
    }
  }

  function closeLightbox() {
    const dialog = $("lightbox");
    if (dialog.open) dialog.close();
    state.detail = null;
  }

  async function reuseSettings() {
    if (!state.detail) return;
    const item = state.detail.item || {};
    const metadata = state.detail.metadata || {};
    const modelType = metadata.model_type || item.model_type;
    if (!modelType) {
      toast("This file has no model_type metadata.", true);
      return;
    }
    const settings = Object.assign({}, metadata);
    META_ONLY_KEYS.forEach((key) => delete settings[key]);
    settings.model_type = modelType;
    settings.prompt = metadata.prompt || item.prompt_hint || "";
    closeLightbox();
    S.setView("workflow");
    try {
      await S.selectModel(modelType);
    } catch (_) {}
    $("prompt-input").value = settings.prompt;
    $("settings-json").value = JSON.stringify(settings, null, 2);
    $("settings-state").textContent = "Loaded settings from " + (item.name || "media");
    toast("Settings loaded into the workflow inspector.");
  }

  async function uploadFiles(files) {
    const list = Array.from(files || []);
    if (!list.length) return;
    let done = 0;
    for (const file of list) {
      const body = new FormData();
      body.append("file", file);
      try {
        const response = await fetch("api/media/upload", { method: "POST", body, credentials: "same-origin" });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || "Upload failed (" + response.status + ")");
        done += 1;
      } catch (error) {
        toast(file.name + ": " + error.message, true);
      }
    }
    if (done) toast("Uploaded " + done + " file(s).");
    if (done) await load(true);
  }

  function bind() {
    $("gallery-query").addEventListener("input", (event) => {
      window.clearTimeout(state.queryTimer);
      state.queryTimer = window.setTimeout(() => {
        state.query = event.target.value;
        load(true);
      }, 250);
    });
    $("gallery-kinds").addEventListener("click", (event) => {
      const button = event.target.closest("[data-kind]");
      if (!button) return;
      state.kind = button.dataset.kind || "";
      $("gallery-kinds").querySelectorAll(".filter-chip").forEach((chip) => chip.classList.toggle("selected", chip === button));
      load(true);
    });
    $("gallery-sort").addEventListener("change", (event) => {
      state.sort = event.target.value;
      load(true);
    });
    $("gallery-refresh").addEventListener("click", () => load(true));
    $("gallery-select-mode").addEventListener("click", () => setSelectMode(!state.selectMode));
    $("gallery-clear-selection").addEventListener("click", () => setSelectMode(true));
    $("gallery-delete-selected").addEventListener("click", () => deleteMedia(Array.from(state.selected), state.selected.size + " file(s)"));
    $("gallery-viewport").addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", () => {
      if (!state.active) return;
      layout();
      render();
    });
    $("gallery-upload").addEventListener("click", () => $("gallery-file").click());
    $("gallery-file").addEventListener("change", (event) => {
      uploadFiles(event.target.files);
      event.target.value = "";
    });
    const viewport = $("gallery-viewport");
    viewport.addEventListener("dragover", (event) => {
      event.preventDefault();
      $("gallery-drop").hidden = false;
    });
    viewport.addEventListener("dragleave", (event) => {
      if (event.relatedTarget && viewport.contains(event.relatedTarget)) return;
      $("gallery-drop").hidden = true;
    });
    viewport.addEventListener("drop", (event) => {
      event.preventDefault();
      $("gallery-drop").hidden = true;
      uploadFiles(event.dataTransfer && event.dataTransfer.files);
    });
    $("lightbox-close").addEventListener("click", closeLightbox);
    $("lightbox").addEventListener("click", (event) => {
      if (event.target === $("lightbox")) closeLightbox();
    });
    $("lightbox-copy").addEventListener("click", async () => {
      const text = $("lightbox-prompt").textContent || "";
      try {
        await navigator.clipboard.writeText(text);
        toast("Prompt copied.");
      } catch (_) {
        toast("Clipboard is unavailable.", true);
      }
    });
    $("lightbox-reuse").addEventListener("click", reuseSettings);
    $("lightbox-delete").addEventListener("click", () => {
      if (state.detail) deleteMedia([state.detail.item.id], state.detail.item.name);
    });
  }

  function activate() {
    state.active = true;
    if (!state.loadedOnce) load(true);
    else {
      layout();
      render();
      renderEmpty();
    }
  }

  bind();
  window.WanGPStudioGallery = { activate, reload: () => load(true) };
})();
