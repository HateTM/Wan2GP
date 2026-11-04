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

  function setBar(id, percent) {
    const element = $(id);
    if (element) element.style.width = Math.max(0, Math.min(100, Number(percent) || 0)) + "%";
  }

  function fmtMb(value) {
    return value == null ? "—" : Math.round(value) + " MB";
  }

  function fmtGb(megabytes) {
    return megabytes == null ? "—" : (megabytes / 1024).toFixed(1) + " GB";
  }

  function render(snapshot) {
    const gpu = snapshot.gpu || {};
    if (gpu.available) {
      text("gpu-name", gpu.name || "GPU");
      text("gpu-util", gpu.utilization_percent + "%");
      setBar("gpu-util-bar", gpu.utilization_percent);
      text("gpu-vram", fmtGb(gpu.vram_used_mb) + " / " + fmtGb(gpu.vram_total_mb) + " (" + gpu.vram_percent + "%)");
      setBar("gpu-vram-bar", gpu.vram_percent);
      text("gpu-temp", gpu.temperature_c != null ? gpu.temperature_c + " °C" : "temp —");
      text("gpu-power", gpu.power_w != null ? gpu.power_w + " W" : "power —");
      text("gpu-fan", gpu.fan_percent != null ? gpu.fan_percent + " % fan" : "fan —");
    } else {
      text("gpu-name", gpu.source === "nvml-error" ? "NVML error" : "NVML unavailable");
      text("gpu-util", "unavailable");
      setBar("gpu-util-bar", 0);
      text("gpu-vram", "unavailable");
      setBar("gpu-vram-bar", 0);
      text("gpu-temp", "—");
      text("gpu-power", "—");
      text("gpu-fan", "—");
    }

    const system = snapshot.system || {};
    text("ram-used", fmtGb(system.ram_used_mb) + " / " + fmtGb(system.ram_total_mb) + " (" + system.ram_percent + "%)");
    setBar("ram-bar", system.ram_percent);

    const process = snapshot.process || {};
    text("proc-rss", fmtMb(process.rss_mb));
    text("proc-cpu", "CPU " + (process.cpu_percent != null ? process.cpu_percent.toFixed(1) + "%" : "—") + " · " + (process.threads || 0) + " thr");
    text("sys-cpu", "System " + (system.cpu_percent != null ? system.cpu_percent.toFixed(1) + "%" : "—"));

    const studio = snapshot.studio || {};
    text("jobs-active", String(studio.active_jobs || 0));
    text("jobs-queue", String(studio.queued_jobs || 0));
    text("runs-active", String(studio.active_workflow_runs || 0));

    const job = studio.current_job;
    const run = studio.current_workflow;
    let activity = "No active work";
    if (job) {
      activity = "Job · " + (job.model_type || "") + " · " + (job.message || job.phase || "") +
        (job.progress != null ? " · " + job.progress + "%" : "");
    } else if (run) {
      activity = "Workflow · " + (run.message || "") + (run.progress != null ? " · " + run.progress + "%" : "");
    }
    text("current-activity", activity);
    text("resource-updated", snapshot.timestamp ? "Updated " + new Date(snapshot.timestamp * 1000).toLocaleTimeString() : "—");
    text("studio-source", (snapshot.sources && snapshot.sources.jobs) || "session");
    const sources = Object.entries(snapshot.sources || {}).map(([key, value]) => key + "=" + value).join(" · ");
    text("resource-sources", "Sources: " + (sources || "unknown"));
  }

  async function refresh() {
    if (!state.active) return;
    try {
      const snapshot = await S.api("api/telemetry");
      render(snapshot);
      text("resource-summary", "Read-only telemetry · updated " + new Date().toLocaleTimeString());
    } catch (error) {
      text("resource-summary", "Telemetry unavailable: " + error.message);
    }
  }

  function activate() {
    state.active = true;
    refresh();
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(refresh, 2000);
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
    else if (location.hash === "#resources") activate();
  });

  window.WanGPStudioTelemetry = { activate, deactivate, refresh };
  if (location.hash === "#resources") S.setView("resources");
})();
