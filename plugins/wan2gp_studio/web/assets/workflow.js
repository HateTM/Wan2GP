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
      state.events.close();
      state.events = null;
    }
    const source = new EventSource("api/workflow/runs/" + encodeURIComponent(runId) + "/events", { withCredentials: true });
    state.events = source;
    source.onmessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch (_) {
        return;
      }
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
    const finish = () => {
      source.close();
      state.events = null;
      state.runId = null;
      setBusy(false);
    };
    source.addEventListener("end", finish);
    source.onerror = finish;
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
    $("workflow-save").addEventListener("click", () => {
      if (!state.graph) {
        toast("Nothing to save yet.", true);
        return;
      }
      saveGraph(state.graph, (state.graph && state.graph.name) || "Untitled workflow").catch(() => {});
    });
    $("workflow-run").addEventListener("click", () => {
      if (!state.graph) {
        toast("Open or create a workflow first.", true);
        return;
      }
      startRun(state.graph);
    });
    $("workflow-cancel").addEventListener("click", cancelRun);
    window.addEventListener("message", (event) => {
      const data = event && event.data;
      if (!data || data.type !== "WAN2GP_WORKFLOWS_V2") return;
      if (data.action === "save") {
        state.graph = data.graph || state.graph;
        saveGraph(state.graph, (data.graph && data.graph.name) || "Untitled workflow").catch(() => {});
      } else if (data.action === "run") {
        state.graph = data.graph || state.graph;
        startRun(state.graph);
      } else if (data.action === "save_block" || data.action === "delete_block") {
        toast("Reusable blocks are not wired in this build yet.", true);
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
        host.textContent = error.message;
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
