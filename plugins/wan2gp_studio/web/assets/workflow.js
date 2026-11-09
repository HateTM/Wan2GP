(() => {
  "use strict";
  const S = window.WanGPStudio;
  if (!S) return;
  const $ = (id) => document.getElementById(id);
  const api = S.api;
  const toast = S.toast;

  const state = {
    active: false,
    started: false,
    catalog: null,
    workflows: [],
    slug: null,
    graph: null,
    frame: null,
    frameReady: null,
    assets: null,
    runId: null,
    runRequestPending: false,
    saving: false,
    submittingRun: false,
    events: null,
    nodeStates: {},
    status: "Workflow canvas"
  };

  // Graph requests are answered by the canvas iframe (see web/assets/canvas.js).
  // Save/Run from the Studio toolbar must never write the cached state.graph:
  // the iframe owns the live graph and only pushes it on its own toolbar actions.
  const pendingGraphRequests = new Map();

  function frameOriginAllowed(origin) {
    // sandbox="allow-scripts" without allow-same-origin gives the srcdoc frame an
    // opaque origin, reported as "null"; location.origin keeps the check working
    // if the sandbox is ever relaxed.
    return origin === "null" || origin === location.origin;
  }

  function requestCanvasGraph(timeoutMs = 4000, update = null) {
    const frameWindow = state.frame && state.frame.contentWindow;
    if (!frameWindow) return Promise.resolve(null);
    const frameReady = state.frameReady;
    const requestId = "graph-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        pendingGraphRequests.delete(requestId);
        resolve(null);
      }, timeoutMs);
      pendingGraphRequests.set(requestId, (graph) => {
        clearTimeout(timer);
        pendingGraphRequests.delete(requestId);
        resolve(graph);
      });
      frameReady.then(() => {
        if (state.frameReady === frameReady && pendingGraphRequests.has(requestId)) {
          frameWindow.postMessage({ type: "WAN2GP_WORKFLOWS_V2", action: "get_graph", request_id: requestId, update }, "*");
        }
      });
    });
  }

  function b64(text) {
    const bytes = new TextEncoder().encode(text);
    let binary = "";
    const chunk = 0x8000;
    for (let index = 0; index < bytes.length; index += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(index, index + chunk));
    }
    return btoa(binary);
  }

  function setStatus(text) {
    state.status = text;
    const element = $("workflow-status");
    if (element) element.textContent = text;
  }

  function setBusy(busy) {
    ["workflow-save", "workflow-save-copy", "run-generation", "workflow-new", "workflow-select", "workflow-template"].forEach((id) => {
      const button = $(id);
      if (button) button.disabled = busy;
    });
    const cancel = $("workflow-cancel");
    if (cancel) cancel.disabled = !state.runId;
  }

  async function loadAssets() {
    if (state.assets) return state.assets;
    const [html, css, js] = await Promise.all([
      fetch("assets/canvas.html", { credentials: "same-origin", cache: "no-cache" }).then((response) => response.text()),
      fetch("assets/canvas.css", { credentials: "same-origin", cache: "no-cache" }).then((response) => response.text()),
      fetch("assets/canvas.js", { credentials: "same-origin", cache: "no-cache" }).then((response) => response.text())
    ]);
    state.assets = { html, css, js };
    return state.assets;
  }

  async function buildFrame(graph) {
    const assets = await loadAssets();
    const safeCss = assets.css.replace(/<\/style/gi, "<\\/style");
    const safeJs = assets.js.replace(/<\/script/gi, "<\\/script");
    const document_ = assets.html
      .replace("/* WORKFLOWS_V2_CSS */", safeCss)
      .replace("/* WORKFLOWS_V2_GRAPH */", b64(JSON.stringify(graph || { nodes: [], edges: [] })))
      .replace("/* WORKFLOWS_V2_CATALOG */", b64(JSON.stringify(state.catalog || { nodes: [], models: [], processes: [], blocks: [] })))
      .replace("/* WORKFLOWS_V2_STATUS */", state.status.replace(/[\r\n]+/g, " "))
      .replace("/* WORKFLOWS_V2_JS */", safeJs);
    const frame = $("workflow-frame");
    S.onNodeSelected(null);
    frame.hidden = false;
    state.frame = frame;
    state.frameReady = new Promise((resolve) => frame.addEventListener("load", resolve, { once: true }));
    frame.srcdoc = document_;
    $("workflow-unavailable").hidden = true;
    if (!await requestCanvasGraph()) throw new Error("The workflow canvas did not initialize.");
    flushPendingMedia();
  }

  async function showGraph(graph) {
    if (!state.frame) return buildFrame(graph);
    await state.frameReady;
    state.frame.contentWindow.postMessage({
      type: "WAN2GP_WORKFLOWS_V2", action: "load_graph", graph
    }, "*");
    if (!await requestCanvasGraph()) throw new Error("The workflow canvas did not load the graph.");
  }

  function flushPendingMedia() {
    if (!state.pendingMedia.length) return;
    const frameWindow = state.frame && state.frame.contentWindow;
    if (!frameWindow) return;
    // A srcdoc iframe installs its message listeners asynchronously; probing
    // with a graph handshake is the only reliable readiness signal. Bounded
    // retries, then the queued nodes are dropped with an honest toast.
    requestCanvasGraph(1500).then((graph) => {
      if (!state.pendingMedia.length) return;
      if (graph === null) {
        state.flushAttempts = (state.flushAttempts || 0) + 1;
        if (state.flushAttempts <= 20) {
          setTimeout(flushPendingMedia, 300);
        } else {
          state.pendingMedia.splice(0);
          toast("Could not deliver the gallery media to the workflow canvas.", true);
        }
        return;
      }
      for (const request of state.pendingMedia.splice(0)) {
        frameWindow.postMessage({
          type: "WAN2GP_WORKFLOWS_V2",
          action: "add_media",
          kind: request.kind,
          path: String(request.path || "")
        }, "*");
      }
    });
  }

  async function rebuildWithCatalog(graph) {
    state.catalog = await api("api/workflow/catalog");
    await buildFrame(graph || state.graph || { name: "Untitled workflow", nodes: [], edges: [] });
  }

  async function uploadDroppedFiles(files) {
    for (const file of Array.from(files || [])) {
      const body = new FormData();
      body.append("file", file);
      try {
        const response = await fetch("api/media/upload", { method: "POST", body, credentials: "same-origin" });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || "Upload failed (" + response.status + ")");
        addMediaInput(payload.item.kind, payload.item.path);
        setStatus("Added " + payload.item.name + " to the canvas");
      } catch (error) {
        toast(file.name + ": " + error.message, true);
      }
    }
  }

  function postNodeStatus() {
    if (!state.frame || !state.frame.contentWindow) return;
    state.frame.contentWindow.postMessage({
      type: "WAN2GP_WORKFLOWS_V2",
      action: "node_status",
      status: { nodes: state.nodeStates }
    }, "*");
  }

  async function refreshWorkflowList(selectSlug) {
    try {
      state.workflows = await api("api/workflow/workflows");
    } catch (error) {
      state.workflows = [];
    }
    const select = $("workflow-select");
    select.innerHTML = '<option value="">' + (state.workflows.length ? "Select saved workflow…" : "No saved workflows") + "</option>" +
      state.workflows.map((item) =>
      '<option value="' + S.esc(item.id) + '">' + S.esc(item.name) + "</option>"
    ).join("");
    select.value = selectSlug || "";
    return state.workflows;
  }

  async function loadWorkflow(slug) {
    if (!slug) return;
    setStatus("Loading workflow…");
    setBusy(true);
    try {
      const graph = await api("api/workflow/workflows/" + encodeURIComponent(slug));
      await showGraph(graph);
      state.slug = slug;
      setStatus((graph.name || slug) + " · " + ((graph.nodes || []).length) + " nodes");
    } catch (error) {
      $("workflow-select").value = state.slug || "";
      toast(error.message, true);
      setStatus("Could not load workflow");
    } finally {
      setBusy(false);
    }
  }

  async function loadTemplates() {
    try {
      const payload = await api("api/workflow/templates");
      const select = $("workflow-template");
      select.innerHTML = '<option value="">Templates…</option>' +
        (payload.templates || []).map((item) =>
          '<option value="' + S.esc(item.id) + '">' + S.esc(item.name) + "</option>").join("");
    } catch (_) {
      $("workflow-template").hidden = true;
    }
  }

  async function loadTemplate(id) {
    if (!id) return;
    setBusy(true);
    try {
      const payload = await api("api/workflow/templates");
      const template = (payload.templates || []).find((item) => item.id === id);
      if (!template) return;
      await showGraph(template.graph);
      state.slug = null;
      setStatus((template.name || "Template") + " loaded · " + ((template.graph.nodes || []).length) + " nodes");
      $("workflow-select").value = "";
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function newWorkflow() {
    setBusy(true);
    try {
      await showGraph({ name: "Untitled workflow", nodes: [], edges: [], groups: [] });
      state.slug = null;
      setStatus("Untitled workflow · 0 nodes");
      $("workflow-select").value = "";
    } catch (error) {
      toast(error.message, true);
    } finally {
      setBusy(false);
    }
  }

  function askWorkflowName(title) {
    const dialog = $("workflow-name-dialog");
    const input = $("workflow-name-input");
    dialog.returnValue = "";
    input.value = title;
    dialog.showModal();
    input.select();
    return new Promise((resolve) => {
      dialog.addEventListener("close", () => resolve(dialog.returnValue === "save" ? input.value : null), { once: true });
    });
  }

  async function saveCurrent(asCopy = false) {
    if (state.saving || $("workflow-save").disabled) return;
    state.saving = true;
    setBusy(true);
    try {
      const graph = await requestCanvasGraph();
      if (!graph) throw new Error("Could not read the current graph from the canvas.");
      const id = asCopy ? null : state.slug;
      const title = graph.name || "Untitled workflow";
      const name = id ? title : await askWorkflowName(title);
      if (name === null) return;
      setStatus("Saving workflow…");
      const saved = await api("api/workflow/workflows" + (id ? "/" + encodeURIComponent(id) : ""), {
        method: id ? "PUT" : "POST",
        body: JSON.stringify({ graph, name: name.trim() || title })
      });
      state.slug = saved.id;
      state.graph = saved.graph || graph;
      state.frame.contentWindow.postMessage({ type: "WAN2GP_WORKFLOWS_V2", action: "rename_graph", name: state.graph.name }, "*");
      await refreshWorkflowList(state.slug);
      toast("Workflow saved: " + state.graph.name);
      setStatus(state.graph.name + " · saved");
    } catch (error) {
      toast(error.message, true);
      setStatus("Save failed");
    } finally {
      state.saving = false;
      setBusy(Boolean(state.runId || state.runRequestPending || state.submittingRun));
    }
  }

  async function runCurrent() {
    if (!state.graph) {
      toast("Open or create a workflow first.", true);
      return;
    }
    if (state.runId || state.runRequestPending || state.submittingRun) {
      toast("A workflow is already starting or running.", true);
      return;
    }
    state.runRequestPending = true;
    setBusy(true);
    try {
      const graph = await requestCanvasGraph();
      if (!graph) {
        toast("Could not read the current graph from the canvas. Run aborted.", true);
        setStatus("Run aborted");
        return;
      }
      state.graph = graph;
      await startRun(graph);
    } finally {
      state.runRequestPending = false;
      if (!state.runId) setBusy(false);
    }
  }

  async function startRun(graph) {
    if (state.runId || state.submittingRun) {
      toast("A workflow is already starting or running.", true);
      return;
    }
    state.submittingRun = true;
    setStatus("Starting workflow…");
    setBusy(true);
    try {
      const run = await api("api/workflow/runs", {
        method: "POST",
        body: JSON.stringify({ graph, inputs: [] })
      });
      state.runId = run.run_id;
      state.nodeStates = {};
      Object.keys(run.nodes || {}).forEach((nodeId) => {
        state.nodeStates[nodeId] = run.nodes[nodeId];
      });
      postNodeStatus();
      setStatus("Running workflow…");
      S.refreshTasks();
      watchRun(state.runId);
    } catch (error) {
      toast(error.message, true);
      setStatus("Run failed");
      state.runId = null;
      setBusy(false);
    } finally {
      state.submittingRun = false;
    }
  }

  function watchRun(runId) {
    if (state.events) {
      state.events.closed = true;
      if (state.events.timer) clearTimeout(state.events.timer);
      state.events = null;
    }
    const session = { runId, lastId: 0, attempts: 0, closed: false, timer: null };
    state.events = session;

    const applyMessage = (message) => {
      if (message.kind === "node" && message.data) {
        state.nodeStates[message.data.node_id] = message.data.state;
        postNodeStatus();
        const total = Object.keys(state.nodeStates).length;
        const done = Object.values(state.nodeStates).filter((value) => value === "done" || value === "skipped" || value === "error").length;
        setStatus("Running · " + done + "/" + total + " nodes");
      } else if (message.kind === "progress" && message.data) {
        setStatus((message.data.message || "Running") + " · " + (message.data.progress || 0) + "%");
      } else if (message.kind === "complete" && message.data) {
        const outputs = (message.data.outputs || []).length;
        setStatus(message.data.status === "completed" ? "Completed · " + outputs + " output(s)" : "Cancelled");
        toast(message.data.status === "completed" ? "Workflow completed." : "Workflow cancelled.");
      } else if (message.kind === "error" && message.data) {
        toast(message.data.message || "Workflow failed", true);
        setStatus("Workflow failed");
      }
    };

    const reconcile = async () => {
      try {
        const snapshot = await api("api/workflow/runs/" + encodeURIComponent(runId));
        if (snapshot && snapshot.nodes) {
          state.nodeStates = Object.assign({}, snapshot.nodes);
          postNodeStatus();
          if (snapshot.status && snapshot.status !== "running") {
            setStatus(snapshot.status === "completed"
              ? "Completed · " + (snapshot.outputs || []).length + " output(s)"
              : snapshot.status.charAt(0).toUpperCase() + snapshot.status.slice(1));
          }
        }
      } catch (_) {}
    };

    const finish = () => {
      session.closed = true;
      if (session.timer) clearTimeout(session.timer);
      if (state.events === session) {
        state.events = null;
        state.runId = null;
        setBusy(false);
      }
    };

    const connect = () => {
      if (session.closed || state.runId !== runId) {
        finish();
        return;
      }
      const source = new EventSource(
        "api/workflow/runs/" + encodeURIComponent(runId) + "/events?cursor=" + session.lastId,
        { withCredentials: true }
      );
      source.onopen = () => {
        session.attempts = 0;
      };
      source.onmessage = (event) => {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch (_) {
          return;
        }
        if (typeof message.id === "number") {
          session.lastId = Math.max(session.lastId, message.id);
        }
        applyMessage(message);
        if (message.kind === "closed") {
          session.closed = true;
          source.close();
          finish();
        }
      };
      source.addEventListener("end", () => {
        session.closed = true;
        source.close();
        finish();
      });
      source.onerror = () => {
        source.close();
        if (session.closed || state.runId !== runId) {
          finish();
          return;
        }
        session.attempts += 1;
        const delay = Math.min(15000, 1000 * Math.pow(2, Math.min(session.attempts, 4)));
        setStatus("Reconnecting… attempt " + session.attempts);
        reconcile();
        session.timer = setTimeout(connect, delay);
      };
    };

    connect();
  }

  async function cancelRun() {
    if (!state.runId) return;
    try {
      await api("api/workflow/runs/" + encodeURIComponent(state.runId) + "/cancel", { method: "POST" });
      setStatus("Cancelling…");
    } catch (error) {
      toast(error.message, true);
    }
  }

  function bind() {
    $("workflow-select").addEventListener("change", (event) => {
      if (event.target.value) loadWorkflow(event.target.value);
    });
    $("workflow-new").addEventListener("click", newWorkflow);
    $("workflow-template").addEventListener("change", (event) => loadTemplate(event.target.value));
    const toolbar = document.querySelector(".canvas-toolbar");
    toolbar.addEventListener("dragover", (event) => {
      event.preventDefault();
      toolbar.classList.add("drop-ready");
    });
    toolbar.addEventListener("dragleave", () => toolbar.classList.remove("drop-ready"));
    toolbar.addEventListener("drop", (event) => {
      event.preventDefault();
      toolbar.classList.remove("drop-ready");
      if (event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files.length) {
        uploadDroppedFiles(event.dataTransfer.files);
      }
    });
    $("workflow-save").addEventListener("click", () => saveCurrent());
    $("workflow-save-copy").addEventListener("click", () => saveCurrent(true));
    $("workflow-cancel").addEventListener("click", cancelRun);
    window.addEventListener("message", (event) => {
      const data = event && event.data;
      if (!data || data.type !== "WAN2GP_WORKFLOWS_V2") return;
      if (!frameOriginAllowed(event.origin)) return;
      const frameWindow = state.frame && state.frame.contentWindow;
      if (!frameWindow || event.source !== frameWindow) return;  // canvas iframe only
      if (data.action === "node_selected") {
        if (window.WanGPStudio && window.WanGPStudio.onNodeSelected) {
          window.WanGPStudio.onNodeSelected(data.node);
        }
        return;
      }
      if (data.action === "graph") {
        const resolve = typeof data.request_id === "string" ? pendingGraphRequests.get(data.request_id) : null;
        if (!resolve) return;
        if (typeof data.graph !== "object") return;
        if (data.graph) state.graph = data.graph;
        resolve(data.graph);
        return;
      }
      const allowed = ["save", "save_block", "delete_block"];
      if (allowed.indexOf(data.action) === -1) return;
      if (data.graph !== undefined && (typeof data.graph !== "object" || data.graph === null)) return;
      if (data.action === "save") {
        saveCurrent();
      } else if (data.action === "save_block") {
        const graph = data.graph || state.graph || {};
        const groupId = (graph.ui || {}).selected_group_id || "";
        const group = (graph.groups || []).find((item) => item.id === groupId);
        api("api/workflow/blocks", { method: "POST", body: JSON.stringify({ graph, name: group ? group.title : undefined }) })
          .then((saved) => {
            toast("Reusable block saved: " + (saved.name || saved.id));
            state.graph = graph;
            return rebuildWithCatalog(graph);
          })
          .catch((error) => toast(error.message, true));
      } else if (data.action === "delete_block") {
        const graph = data.graph || state.graph || {};
        const blockId = (graph.ui || {}).selected_block_id || "";
        if (!blockId) {
          toast("Select a reusable block first.", true);
          return;
        }
        api("api/workflow/blocks/" + encodeURIComponent(blockId), { method: "DELETE" })
          .then(() => {
            toast("Reusable block deleted.");
            state.graph = graph;
            return rebuildWithCatalog(graph);
          })
          .catch((error) => toast(error.message, true));
      }
    });
    setBusy(false);
  }

  async function activate() {
    if (state.active) return;
    state.active = true;
    if (!state.started) {
      state.started = true;
      setBusy(true);
      try {
        state.catalog = await api("api/workflow/catalog");
      loadTemplates().catch(() => {});
        const count = (state.catalog.nodes || []).length;
        const models = (state.catalog.models || []).length;
        setStatus("Catalog ready · " + count + " nodes · " + models + " models");
        $("workflow-node-count").textContent = count + " node types";
        await refreshWorkflowList();
        // activate() races loadGraphIntoCanvas: "Open workflow" in the Gallery
        // fires setView and load in the same tick, so a pending graph must not
        // be overwritten by the empty template - build whichever is newer.
        const pending = state.graph || { name: "Untitled workflow", nodes: [], edges: [], groups: [] };
        await buildFrame(pending);
        setBusy(false);
      } catch (error) {
        const host = $("workflow-unavailable");
        host.hidden = false;
        const fallbackLink = error.fallback
          ? ' <a class="model-link" target="_blank" rel="noopener" href="' + S.esc(error.fallback.href || "/") + '">' + S.esc(error.fallback.label || "Open in WanGP") + " ↗</a>"
          : "";
        host.innerHTML = S.esc(error.message || "Workflow unavailable") + fallbackLink;
        $("workflow-frame").hidden = true;
        setStatus("Workflow unavailable");
        setBusy(true);
      }
    }
  }

  // "Use in workflow" (Gallery lightbox): feed a media file into the canvas
  // as an input node. The runner prefers the node's explicit path over the
  // runtime upload slots (graph_runner params.path). Requests arriving before
  // the canvas exists (the user jumps straight here from the gallery) queue up
  // and are flushed after every buildFrame() - activate() rebuilds the frame
  // from an empty literal, so folding nodes into state.graph would lose them.
  state.pendingMedia = [];

  function addMediaInput(kind, path) {
    const nodeType = { image: "input_image", video: "input_video", audio: "input_audio" }[kind];
    if (!nodeType) return false;
    if (state.frame && state.frame.contentWindow) {
      state.frame.contentWindow.postMessage({
        type: "WAN2GP_WORKFLOWS_V2",
        action: "add_media",
        kind: kind,
        path: String(path || "")
      }, "*");
      return true;
    }
    state.pendingMedia.push({ kind: kind, path: String(path || "") });
    return true;
  }

  async function applyToSelectedNode(payload) {
    return Boolean(await requestCanvasGraph(4000, payload));
  }

  function loadGraphIntoCanvas(graph) {
    if (state.saving || !graph || !Array.isArray(graph.nodes)) return false;
    state.slug = null;
    $("workflow-select").value = "";
    const label = (graph.name || "Workflow") + " · " + graph.nodes.length + " nodes";
    if (state.frame) {
      setBusy(true);
      showGraph(graph).then(() => setStatus(label)).catch((error) => toast(error.message, true))
        .finally(() => setBusy(Boolean(state.runId || state.runRequestPending || state.submittingRun)));
    } else {
      state.graph = graph;
    }
    return true;
  }

  bind();
  window.WanGPStudioCanvas = {
    activate,
    saveCurrent,
    startRun,
    runCurrent,
    newWorkflow,
    addMediaInput,
    applyToSelectedNode,
    loadGraphIntoCanvas,
    getGraph: () => requestCanvasGraph(3000),
    getState: () => ({ slug: state.slug, runId: state.runId, graph: state.graph })
  };
  if (!location.hash || location.hash === "#workflow") S.setView("workflow");
})();
