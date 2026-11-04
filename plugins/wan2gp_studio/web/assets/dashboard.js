(() => {
  "use strict";
  const S = window.WanGPStudio;
  if (!S) return;
  const $ = (id) => document.getElementById(id);
  const state = { active: false, timer: null };

  function text(id, value) {
    const element = $(id);
    if (element) element.textContent = value;
  }

  async function refresh() {
    if (!state.active) return;
    try {
      const [telemetry, media, environment] = await Promise.all([
        S.api("api/telemetry"),
        S.api("api/media/roots"),
        S.api("api/environment")
      ]);
      const core = (environment.core && environment.core.version) || "unknown";
      text("dash-core", core);
      text("dash-runtime", "connected");

      const workflow = (environment.plugins || []).find((plugin) => plugin.id === "wan2gp-wanflow-ui");
      text("dash-workflow", workflow ? workflow.state : "not installed");

      const optional = (environment.plugins || []).filter((plugin) => plugin.integration !== "native");
      const enabled = optional.filter((plugin) => plugin.state === "enabled").length;
      text("dash-plugins", enabled + " / " + optional.length + " enabled");

      const kinds = (media && media.kinds) || {};
      text("dash-media-total", String(media.total || 0) + " items");
      text("dash-images", String(kinds.image || 0));
      text("dash-videos", String(kinds.video || 0));
      text("dash-other", String((kinds.audio || 0) + (kinds.world || 0)));

      const studio = telemetry.studio || {};
      text("dash-jobs", String(studio.active_jobs || 0));
      text("dash-runs", String(studio.active_workflow_runs || 0));
      const job = studio.current_job;
      const run = studio.current_workflow;
      text("dash-activity", job
        ? "Job · " + (job.model_type || "") + " · " + (job.message || job.phase || "")
        : run
          ? "Workflow · " + (run.message || "")
          : "No active work");
      text("dash-updated", telemetry.timestamp
        ? "Updated " + new Date(telemetry.timestamp * 1000).toLocaleTimeString()
        : "—");
      text("dashboard-summary", "Runtime overview · " + (media.total || 0) + " media items · " + enabled + " optional plugins enabled");
    } catch (error) {
      text("dashboard-summary", "Dashboard unavailable: " + error.message);
    }
  }

  function activate() {
    state.active = true;
    refresh();
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(refresh, 5000);
  }

  function deactivate() {
    state.active = false;
    if (state.timer) {
      clearInterval(state.timer);
      state.timer = null;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) deactivate();
    else if (location.hash === "#dashboard") activate();
  });

  [["dash-goto-gallery", "gallery"], ["dash-goto-workflow", "workflow"], ["dash-goto-resources", "resources"]].forEach(([id, view]) => {
    const button = $(id);
    if (button) button.addEventListener("click", () => S.setView(view));
  });
  if ($("dashboard-refresh")) $("dashboard-refresh").addEventListener("click", refresh);

  window.WanGPStudioDashboard = { activate, deactivate, refresh };
  if (location.hash === "#dashboard") S.setView("dashboard");
})();
