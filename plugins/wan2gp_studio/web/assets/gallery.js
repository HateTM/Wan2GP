(() => {
  "use strict";
  const S = window.WanGPStudio;
  if (!S) return;
  const $ = (id) => document.getElementById(id);
  const esc = S.esc;
  const api = S.api;
  const toast = S.toast;

  const PAGE = 200;
  // Memory bound: only this many pages around the viewport stay in memory.
  // Scrolling back refetches evicted pages on demand (see loadPage / render).
  const KEEP_PAGES = 6;
  // Selection ids are small, but the set is capped so a runaway select-all
  // drag cannot grow without limit either.
  const MAX_SELECTION = 1000;
  const GAP = 12;
  const KIND_LABEL = { image: "IMAGE", video: "VIDEO", audio: "AUDIO", world: "WORLD", "3d": "3D", app: "APP" };
  const META_ONLY_KEYS = ["output_role", "model_filename", "generation_time", "creation_date", "creation_timestamp"];

  const state = {
    pages: new Map(),
    fetching: new Set(),
    generation: 0,
    total: 0,
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
    environment: null,
    environmentAt: 0,
    sendTargets: null,
    sendTargetsAt: 0,
    sendBridge: true,
    ticking: false
  };

  function itemAt(index) {
    const page = state.pages.get((index / PAGE) | 0);
    return page ? page[index % PAGE] : null;
  }

  function cachedCount() {
    let count = 0;
    for (const page of state.pages.values()) count += page.length;
    return count;
  }

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
    if (state.fetching.size && !state.total) {
      element.hidden = false;
      element.textContent = "Indexing media roots…";
      return;
    }
    if (!state.total && !state.fetching.size) {
      element.hidden = false;
      element.textContent = state.query || state.kind
        ? "No media matches the current filters."
        : "No media yet. Generate something in WanGP or drop files here.";
      return;
    }
    element.hidden = true;
  }

  function updateSummary() {
    const count = $("gallery-nav-count");
    count.hidden = false;
    count.textContent = String(state.total);
    $("gallery-summary").textContent =
      state.total + " items · " + cachedCount() + " in memory · WanGP output roots";
  }

  async function loadPage(page) {
    if (page < 0 || (state.total && page * PAGE >= state.total)) return;
    if (state.pages.has(page) || state.fetching.has(page)) return;
    const generation = state.generation;
    state.fetching.add(page);
    renderEmpty();
    try {
      const params = new URLSearchParams({ limit: PAGE, offset: page * PAGE, sort: state.sort });
      if (state.kind) params.set("kind", state.kind);
      if (state.query.trim()) params.set("q", state.query.trim());
      const payload = await api("api/media?" + params.toString());
      if (generation !== state.generation) return; // filters changed mid-flight
      state.total = Number(payload.total) || 0;
      state.pages.set(page, payload.items || []);
      state.error = null;
      updateSummary();
      layout();
      render();
    } catch (error) {
      if (generation !== state.generation) return;
      state.error = error.message;
      $("gallery-summary").textContent = "Media API unavailable";
      renderEmpty();
    } finally {
      state.fetching.delete(page);
    }
  }

  async function load(reset) {
    if (!reset) return; // incremental loading is driven by render() -> loadPage()
    state.generation += 1;
    state.pages.clear();
    state.fetching.clear();
    state.total = 0;
    state.error = null;
    state.cards.clear();
    $("gallery-window").replaceChildren();
    $("gallery-spacer").style.height = "0px";
    renderEmpty();
    // The first two screens eagerly; everything else streams in on scroll.
    await Promise.all([loadPage(0), loadPage(1)]);
    renderEmpty();
  }

  function layout() {
    const viewport = $("gallery-viewport");
    const width = Math.max(320, viewport.clientWidth - 28);
    const cardWidth = Math.max(168, Math.min(238, Math.round((width - GAP * 3) / 4)));
    const columns = Math.max(2, Math.floor((width + GAP) / (cardWidth + GAP)));
    state.cardWidth = cardWidth;
    state.columns = columns;
    state.rowHeight = Math.round(cardWidth * 9 / 16) + 40 + GAP;
    const rows = Math.ceil(state.total / columns);
    $("gallery-spacer").style.height = rows * state.rowHeight + "px";
    const windowEl = $("gallery-window");
    windowEl.style.gridTemplateColumns = "repeat(" + columns + ", " + cardWidth + "px)";
    windowEl.style.gap = GAP + "px";
    windowEl.style.setProperty("--card-height", (state.rowHeight - GAP) + "px");
  }

  function calibrate() {
    const card = $("gallery-window").firstElementChild;
    if (!card || card.classList.contains("skeleton")) return;
    const measured = card.getBoundingClientRect().height + GAP;
    if (measured > 60 && Math.abs(measured - state.rowHeight) > 2) {
      state.rowHeight = measured;
      const rows = Math.ceil(state.total / state.columns);
      $("gallery-spacer").style.height = rows * state.rowHeight + "px";
    }
  }

  function skeletonCard() {
    const card = document.createElement("div");
    card.className = "media-card skeleton";
    card.setAttribute("aria-hidden", "true");
    card.innerHTML =
      '<span class="media-thumb"></span><span class="media-caption">' +
      '<span class="media-name">&nbsp;</span><span class="media-meta">&nbsp;</span></span>';
    return card;
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
    const end = Math.min(state.total, start + rowsVisible * state.columns);
    const windowEl = $("gallery-window");
    const nodes = [];
    const keep = new Set();
    for (let index = start; index < end; index += 1) {
      const item = itemAt(index);
      if (!item) {
        nodes.push(skeletonCard());
        continue;
      }
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
    // Fetch (or refetch, after eviction) every page the viewport touches plus
    // one page of head-room in both directions; loadPage() deduplicates.
    if (state.total) {
      const firstPage = Math.max(0, Math.floor(start / PAGE) - 1);
      const lastPage = Math.floor(Math.max(0, end - 1) / PAGE) + 1;
      // Eviction is anchored to the real viewport, never to a fetched page:
      // out-of-order responses would otherwise evict the pages the user is
      // looking at and start a load/evict ping-pong.
      const lowPage = Math.max(0, firstPage - KEEP_PAGES);
      const highPage = lastPage + KEEP_PAGES;
      for (const key of Array.from(state.pages.keys())) {
        if (key < lowPage || key > highPage) state.pages.delete(key);
      }
      for (let page = firstPage; page <= lastPage; page += 1) loadPage(page);
    }
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
    if (!state.selected.has(id) && state.selected.size >= MAX_SELECTION) {
      toast("Selection is capped at " + MAX_SELECTION + " items.", true);
      return;
    }
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

  async function ensureEnvironment() {
    if (state.environment && Date.now() - state.environmentAt < 60000) return state.environment;
    try {
      state.environment = await api("api/environment");
    } catch (_) {
      state.environment = { plugins: [] };
    }
    state.environmentAt = Date.now();
    return state.environment;
  }

  function imageSuitePlugin() {
    return (state.environment && state.environment.plugins || []).find((plugin) => plugin.id === "ImageSuite-Wan2GP") || null;
  }

  async function ensureSendTargets() {
    if (state.sendTargets && Date.now() - state.sendTargetsAt < 60000) return state.sendTargets;
    try {
      const payload = await api("api/sendto/targets");
      state.sendTargets = Array.isArray(payload.targets) ? payload.targets : [];
      state.sendBridge = payload.bridge !== false;
    } catch (_) {
      state.sendTargets = [];
      state.sendBridge = false;
    }
    state.sendTargetsAt = Date.now();
    return state.sendTargets;
  }

  // Targets the current lightbox item can actually use: the plugin must be
  // enabled and its manifest "accepts" list must cover the item kind, so the
  // button never offers a send the server would refuse with HTTP 400.
  function usableSendTargets() {
    const item = state.detail && state.detail.item;
    const kind = item && item.kind;
    return (state.sendTargets || []).filter((target) => {
      if (target.enabled === false) return false;
      const accepts = Array.isArray(target.accepts) ? target.accepts : [];
      return accepts.length === 0 || !kind || accepts.indexOf(kind) !== -1;
    });
  }

  function renderSendTargets() {
    const select = $("lightbox-suite-target");
    const previous = select.value;
    const targets = usableSendTargets();
    select.replaceChildren();
    for (const target of targets) {
      const option = document.createElement("option");
      option.value = target.plugin + "|" + target.slot;
      option.textContent = (target.plugin_label || target.plugin) + " · " + (target.label || target.slot);
      select.appendChild(option);
    }
    if (previous && targets.some((target) => target.plugin + "|" + target.slot === previous)) {
      select.value = previous;
    }
    select.hidden = targets.length === 0;
  }

  function sendBridgeAvailable() {
    return state.sendBridge !== false;
  }

  function updateSuiteButton() {
    const button = $("lightbox-suite");
    const copy = $("lightbox-suite-copy");
    if (!button) return;
    const plugin = imageSuitePlugin();
    const anyTargets = (state.sendTargets || []).length > 0;
    const usable = usableSendTargets();
    button.disabled = usable.length === 0 || !sendBridgeAvailable();
    if (usable.length === 0) {
      button.textContent = !anyTargets
        ? (plugin && plugin.state === "not_installed" ? "No SendTo plugin" : "No SendTo target")
        : "No target for this file";
    } else if (!sendBridgeAvailable()) {
      button.textContent = "Bridge unavailable";
    } else {
      button.textContent = "Send";
    }
    if (copy) copy.hidden = !(state.detail && state.detail.item);
    if (plugin && plugin.state && plugin.state !== "enabled" && usable.length > 0) {
      button.title = plugin.state === "disabled"
        ? "Image Suite is installed but disabled in the WanGP Plugin Manager."
        : "Target plugin state: " + plugin.state;
    } else {
      button.removeAttribute("title");
    }
  }

  async function copySelectedPath() {
    const item = state.detail && state.detail.item;
    if (!item) return;
    try {
      await navigator.clipboard.writeText(item.path || item.name || "");
      toast("File path copied.");
    } catch (_) {
      toast("Clipboard is unavailable.", true);
    }
  }

  async function sendToTarget() {
    const item = state.detail && state.detail.item;
    if (!item) return;
    await ensureSendTargets();
    const select = $("lightbox-suite-target");
    const [plugin, slot] = String(select.value || "").split("|");
    if (!plugin || !slot) {
      const anyTargets = (state.sendTargets || []).length > 0;
      toast(anyTargets
        ? "No installed SendTo target accepts this " + (KIND_LABEL[item.kind] || item.kind) + "."
        : "No SendTo target is installed. Install Image Suite from the WanGP Plugin Manager.", true);
      return;
    }
    // window.open must run inside the user gesture: browsers drop transient
    // activation across the awaits below, and with "noopener" it always
    // returns null, so a blocked popup could not be told from a success.
    const opened = window.open("", "_blank");
    if (!opened) {
      toast("Popup blocked. Allow popups for this page, then retry the send.", true);
      return;
    }
    try { opened.opener = null; } catch (_) {}
    const closeTab = () => { try { opened.close(); } catch (_) {} };
    let payload;
    try {
      payload = await api("api/media/" + encodeURIComponent(item.id) + "/sendto", {
        method: "POST",
        body: JSON.stringify({ plugin, slot })
      });
    } catch (error) {
      closeTab();
      toast(error.message, true);
      return;
    }
    if (payload.bridge === false) {
      closeTab();
      toast("The WanGP SendTo bridge is not loaded. Restart WanGP, then retry.", true);
      return;
    }
    const target = payload.handoff || {};
    const label = (target.plugin_label || plugin) + (target.slot_label ? " · " + target.slot_label : "");
    opened.location.replace(new URL(payload.url, window.location.href).href);
    toast("Opening WanGP to send this frame to " + label + "…");
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
    ensureEnvironment().then(updateSuiteButton).catch(() => {});
    ensureSendTargets()
      .then(() => {
        renderSendTargets();
        updateSuiteButton();
      })
      .catch(() => {});
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

  // -- Upload Center: bounded-parallelism queue with per-file progress,
  // retry and cancel. The backend streams to disk; the frontend only guards
  // against flooding it with a whole drag-and-drop batch at once.
  const UPLOAD_CONCURRENCY = 2;
  const uploadState = { queue: [], running: 0, done: 0 };

  function enqueueUploads(files) {
    const list = Array.from(files || []);
    if (!list.length) return;
    for (const file of list) {
      uploadState.queue.push({ file, status: "queued", percent: 0, error: null, xhr: null, id: Math.random().toString(36).slice(2) });
    }
    renderUploadRows();
    pumpUploads();
  }

  function uploadRow(entry) {
    return $("gallery-upload-rows").querySelector('[data-upload="' + entry.id + '"]');
  }

  function uploadRowHtml(entry) {
    const state_label = { queued: "Queued", uploading: entry.percent + "%", done: "Done", failed: "Failed", cancelled: "Cancelled" }[entry.status] || entry.status;
    const actions =
      entry.status === "uploading"
        ? '<button class="upload-action" data-act="cancel" title="Cancel upload">✕</button>'
        : entry.status === "done"
          ? '<button class="upload-action" data-act="remove" title="Remove from list">✕</button>'
          : '<button class="upload-action" data-act="retry" title="Retry upload">↻</button><button class="upload-action" data-act="remove" title="Remove from list">✕</button>';
    return (
      '<div class="upload-line"><span class="upload-name" title="' + esc(entry.file.name) + '">' + esc(entry.file.name) + "</span>" +
      '<span class="upload-meter"><span class="upload-fill" style="width:' + (entry.status === "done" ? 100 : entry.percent) + '%"></span></span>' +
      '<span class="upload-status ' + entry.status + '">' + esc(state_label) + (entry.error ? " · " + esc(entry.error) : "") + "</span>" + actions + "</div>"
    );
  }

  function renderUploadRows() {
    const rows = $("gallery-upload-rows");
    rows.replaceChildren();
    for (const entry of uploadState.queue) {
      const row = document.createElement("div");
      row.className = "upload-row";
      row.dataset.upload = entry.id;
      row.innerHTML = uploadRowHtml(entry);
      const wire = (action, handler) => {
        const button = row.querySelector('[data-act="' + action + '"]');
        if (button) button.addEventListener("click", handler);
      };
      wire("cancel", () => {
        if (entry.xhr) entry.xhr.abort();
        else { entry.status = "cancelled"; renderUploadRows(); pumpUploads(); }
      });
      wire("retry", () => {
        entry.status = "queued";
        entry.error = null;
        renderUploadRows();
        pumpUploads();
      });
      wire("remove", () => {
        uploadState.queue = uploadState.queue.filter((item) => item !== entry);
        renderUploadRows();
        pumpUploads();
      });
      rows.appendChild(row);
    }
    const panel = $("gallery-uploads");
    panel.hidden = uploadState.queue.length === 0;
    const active = uploadState.queue.filter((item) => item.status === "queued" || item.status === "uploading").length;
    $("gallery-upload-title").textContent =
      "Uploads · " + active + " active · " + uploadState.done + " done";
  }

  function updateUploadRow(entry) {
    const row = uploadRow(entry);
    if (row) row.innerHTML = uploadRowHtml(entry);
    renderUploadRows(); // keep the counters in the panel header honest
  }

  function pumpUploads() {
    while (uploadState.running < UPLOAD_CONCURRENCY) {
      const entry = uploadState.queue.find((item) => item.status === "queued");
      if (!entry) break;
      startUpload(entry);
    }
  }

  function startUpload(entry) {
    entry.status = "uploading";
    entry.percent = 0;
    entry.error = null;
    uploadState.running += 1;
    const xhr = new XMLHttpRequest();
    entry.xhr = xhr;
    xhr.responseType = "json";
    xhr.open("POST", "api/media/upload", true);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        entry.percent = Math.round((event.loaded / event.total) * 100);
        updateUploadRow(entry);
      }
    };
    xhr.onerror = () => finishUpload(entry, new Error("Network error"));
    xhr.onabort = () => finishUpload(entry, new Error("cancelled"), { cancelled: true });
    xhr.onload = () => {
      const payload = xhr.response || {};
      if (xhr.status >= 200 && xhr.status < 300) finishUpload(entry, null);
      else finishUpload(entry, new Error(payload.detail || "Upload failed (" + xhr.status + ")"));
    };
    const body = new FormData();
    body.append("file", entry.file);
    xhr.send(body);
  }

  function finishUpload(entry, error, opts = {}) {
    uploadState.running = Math.max(0, uploadState.running - 1);
    entry.xhr = null;
    if (error) {
      entry.status = opts.cancelled ? "cancelled" : "failed";
      entry.error = opts.cancelled ? null : error.message;
      entry.percent = 0;
    } else {
      entry.status = "done";
      entry.percent = 100;
      uploadState.done += 1;
    }
    updateUploadRow(entry);
    pumpUploads(); // a slot just freed: start the next queued file
    const pending = uploadState.queue.some((item) => item.status === "queued" || item.status === "uploading");
    if (!pending && uploadState.done) {
      toast("Uploaded " + uploadState.done + " file(s).");
      uploadState.done = 0;
      load(true); // the queue drained: bring the new files into the gallery
    }
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
      enqueueUploads(event.target.files);
      event.target.value = "";
    });
    $("gallery-upload-clear").addEventListener("click", () => {
      for (const entry of uploadState.queue) {
        if (entry.xhr) entry.xhr.abort();
      }
      uploadState.queue = uploadState.queue.filter((item) => item.status === "uploading");
      uploadState.done = 0;
      renderUploadRows();
      pumpUploads();
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
      enqueueUploads(event.dataTransfer && event.dataTransfer.files);
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
    $("lightbox-suite").addEventListener("click", () => {
      sendToTarget().catch((error) => toast(error.message, true));
    });
    $("lightbox-suite-copy").addEventListener("click", () => {
      copySelectedPath().catch((error) => toast(error.message, true));
    });
    $("lightbox-delete").addEventListener("click", () => {
      if (state.detail) deleteMedia([state.detail.item.id], state.detail.item.name);
    });
    updateSelectionBar();
  }

  function activate() {
    state.active = true;
    if (!state.pages.size) load(true);
    else {
      layout();
      render();
      renderEmpty();
    }
  }

  bind();
  window.WanGPStudioGallery = {
    activate,
    reload: () => load(true),
    // Small introspection surface for the e2e suite: the memory bounds of the
    // page store are a test contract, not an implementation accident.
    debug: () => ({
      pages: state.pages.size,
      pageKeys: Array.from(state.pages.keys()),
      fetching: Array.from(state.fetching),
      total: state.total,
      cards: state.cards.size,
      domCards: $("gallery-window").children.length,
      scrollTop: $("gallery-viewport").scrollTop
    })
  };
  if (location.hash === "#gallery") S.setView("gallery");
})();
