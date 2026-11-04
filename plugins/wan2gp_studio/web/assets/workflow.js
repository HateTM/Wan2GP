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
    assets: null,
    runId: null,
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

  function requestCanvasGraph(timeoutMs = 4000) {
    const frameWindow = state.frame && state.frame.contentWindow;
    if (!frameWindow) return Promise.resolve(null);
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
      frameWindow.postMessage({ type: "WAN2GP_WORKFLOWS_V2", action: "get_graph", request_id: requestId }, "*");
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

  function slugify(value) {
    return String(value || "workflow")
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80) || "workflow";
  }

  function setStatus(text) {
    state.status = text;
    const element = $("workflow-status");
    if (element) element.textContent = text;
  }

  function setBusy(busy) {
    ["workflow-save", "workflow-run", "workflow-new"].forEach((id) => {
      const button = $(id);
      if (button) button.disabled = busy;
    });
    const cancel = $("workflow-cancel");
    if (cancel) cancel.disabled = !state.runId;
  }

  async function loadAssets() {
    if (state.assets) return state.assets;
    const [html, css, js] = await Promise.all([
      fetch("assets/canvas.html", { credentials: "same-origin" }).then((response) => response.text()),
      fetch("assets/canvas.css", { credentials: "same-origin" }).then((response) => response.text()),
      fetch("assets/canvas.js", { credentials: "same-origin" }).then((response) => response.text())
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
    frame.hidden = false;
    frame.srcdoc = document_;
    state.frame = frame;
    $("workflow-unavailable").hidden = true;
  }

  async function rebuildWithCatalog(graph) {
    state.catalog = await api("api/workflow/catalog");
    await buildFrame(graph || state.graph || { name: "Untitled workflow", nodes: [], edges: [] });
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
    select.innerHTML = state.workflows.map((item) =>
      '<option value="' + S.esc(item.id) + '">' + S.esc(item.name) + "</option>"
    ).join("") || '<option value="">No saved workflows</option>';
    if (selectSlug) select.value = selectSlug;
    return state.workflows;
  }

  async function loadWorkflow(slug) {
    if (!slug) return;
    setStatus("Loading workflow…");
    setBusy(true);
    try {
      const graph = await api("api/workflow/workflows/" + encodeURIComponent(slug));
      state.slug = slug;
      state.graph = graph;
      await buildFrame(graph);
      setStatus((graph.name || slug) + " · " + ((graph.nodes || []).length) + " nodes");
    } catch (error) {
      toast(error.message, true);
      setStatus("Could not load workflow");
    } finally {
      setBusy(false);
    }
  }

  function newWorkflow() {
    state.slug = null;
    state.graph = { name: "Untitled workflow", nodes: [], edges: [], groups: [] };
    buildFrame(state.graph).then(() => {
      setStatus("Untitled workflow · 0 nodes");
      $("workflow-select").value = "";
    }).catch((error) => toast(error.message, true));
  }

  async function saveGraph(graph, name) {
    const title = String(name || (graph && graph.name) || "Untitled workflow").trim() || "Untitled workflow";
    const slug = slugify(title);
    setStatus("Saving workflow…");
    try {
      const saved = await api("api/workflow/workflows/" + encodeURIComponent(slug), {
        method: "PUT",
        body: JSON.stringify({ graph, name: title })
      });
      state.slug = saved.id || slug;
      state.graph = saved.graph || graph;
      await refreshWorkflowList(state.slug);
      toast("Workflow saved: " + title);
      setStatus(title + " · saved");
      return saved;
    } catch (error) {
      toast(error.message, true);
      setStatus("Save failed");
      throw error;
    }
  }

  async function startRun(graph) {
    if (state.runId) {
      toast("A workflow is already running.", true);
      return;
    }
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
      watchRun(state.runId);
    } catch (error) {
      toast(error.message, true);
      setStatus("Run failed");
      state.runId = null;
      setBusy(false);
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
    $("workflow-save").addEventListener("click", async () => {
      if (!state.graph) {
        toast("Nothing to save yet.", true);
        return;
      }
      setBusy(true);  // no re-click while the handshake is in flight
      const graph = await requestCanvasGraph();
      if (!graph) {
        setBusy(false);
        toast("Could not read the current graph from the canvas. Save aborted.", true);
        setStatus("Save aborted");
        return;
      }
      state.graph = graph;
      saveGraph(graph, (graph && graph.name) || "Untitled workflow")
        .catch(() => {})
        .finally(() => setBusy(false));
    });
    $("workflow-run").addEventListener("click", async () => {
      if (!state.graph) {
        toast("Open or create a workflow first.", true);
        return;
      }
      if (state.runId) {  // checked synchronously, before the handshake await
        toast("A workflow is already running.", true);
        return;
      }
      setBusy(true);
      const graph = await requestCanvasGraph();
      if (!graph) {
        setBusy(false);
        toast("Could not read the current graph from the canvas. Run aborted.", true);
        setStatus("Run aborted");
        return;
      }
      state.graph = graph;
      if (state.runId) return;  // re-check after the await; startRun re-checks too
      startRun(graph);
    });
    $("workflow-cancel").addEventListener("click", cancelRun);
    window.addEventListener("message", (event) => {
      const data = event && event.data;
      if (!data || data.type !== "WAN2GP_WORKFLOWS_V2") return;
      if (!frameOriginAllowed(event.origin)) return;
      const frameWindow = state.frame && state.frame.contentWindow;
      if (!frameWindow || event.source !== frameWindow) return;  // canvas iframe only
      if (data.action === "graph") {
        const resolve = typeof data.request_id === "string" ? pendingGraphRequests.get(data.request_id) : null;
        if (!resolve) return;
        if (typeof data.graph !== "object" || data.graph === null) return;
        state.graph = data.graph;
        resolve(data.graph);
        return;
      }
      const allowed = ["save", "run", "save_block", "delete_block"];
      if (allowed.indexOf(data.action) === -1) return;
      if (data.graph !== undefined && (typeof data.graph !== "object" || data.graph === null)) return;
      if (data.action === "save") {
        state.graph = data.graph || state.graph;
        saveGraph(state.graph, (data.graph && data.graph.name) || "Untitled workflow").catch(() => {});
      } else if (data.action === "run") {
        state.graph = data.graph || state.graph;
        startRun(state.graph);
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
      bind();
      try {
        state.catalog = await api("api/workflow/catalog");
        const count = (state.catalog.nodes || []).length;
        const models = (state.catalog.models || []).length;
        setStatus("Catalog ready · " + count + " nodes · " + models + " models");
        $("workflow-node-count").textContent = count + " node types";
        await refreshWorkflowList();
        await buildFrame({ name: "Untitled workflow", nodes: [], edges: [], groups: [] });
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
        ["workflow-save", "workflow-run", "workflow-cancel"].forEach((id) => { $(id).disabled = true; });
      }
    }
  }

  bind();
  window.WanGPStudioCanvas = {
    activate,
    saveGraph,
    startRun,
    newWorkflow,
    getState: () => ({ slug: state.slug, runId: state.runId, graph: state.graph })
  };
  if (!location.hash || location.hash === "#workflow") S.setView("workflow");
})();
