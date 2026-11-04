(() => {
  "use strict";
  const S = window.WanGPStudio;
  if (!S) return;
  const $ = (id) => document.getElementById(id);

  // state key -> [label, badge tone]; "needs attention" states drive the nav badge.
  const STATES = {
    "current": ["Up to date", "ok"],
    "behind": ["Update available", "warn"],
    "fork": ["Local fork", "warn"],
    "fork-diverged": ["Fork diverged", "warn"],
    "fork-detached": ["Local fork · upstream gone", "warn"],
    "fork-unavailable": ["Local fork · remote unavailable", "warn"],
    "upstream-gone": ["Upstream gone", "error"],
    "stale-refs": ["Stale refs", "error"],
    "unreachable": ["Remote unreachable", "error"],
    "no-remote": ["No remote", "muted"],
    "no-upstream-ref": ["No upstream ref", "muted"],
    "built-in": ["Built-in", "muted"]
  };
  const ATTENTION_STATES = ["behind", "fork", "fork-diverged", "fork-detached", "fork-unavailable", "upstream-gone", "stale-refs", "unreachable"];

  function render(payload) {
    const rows = $("plugins-rows");
    const plugins = payload.plugins || [];
    if (!rows) return;
    if (!plugins.length) {
      rows.innerHTML = '<tr><td colspan="5" class="plugin-empty">No plugins found under the plugins folder.</td></tr>';
    } else {
      rows.innerHTML = plugins.map((item) => {
        const [label, tone] = STATES[item.state] || [item.state, "muted"];
        const detail = [];
        if (item.branch) detail.push("branch " + item.branch + " · ↑" + (item.ahead || 0) + " ↓" + (item.behind || 0));
        if (item.local_commits && item.local_commits.length) detail.push("Local: " + item.local_commits.join("; "));
        if (item.error) detail.push(item.error);
        if (item.wangp_compatible === false) {
          detail.push("Requires WanGP " + (item.wan2gp_version || "?") + " - this host may be incompatible");
        }
        return "<tr>" +
          '<td class="plugin-name">' + S.esc(item.name || item.id) + '<span class="plugin-id">' + S.esc(item.id) + "</span></td>" +
          "<td>" + S.esc(item.version || "—") + (item.date ? '<span class="plugin-date">' + S.esc(item.date) + "</span>" : "") + "</td>" +
          "<td>" + S.esc(item.upstream_version || "—") + (item.upstream_date ? '<span class="plugin-date">' + S.esc(item.upstream_date) + "</span>" : "") + "</td>" +
          '<td><span class="plugin-state ' + tone + '">' + S.esc(label) + "</span></td>" +
          '<td class="plugin-details">' + S.esc(detail.join(" · ") || "—") + "</td>" +
          "</tr>";
      }).join("");
    }
    const attention = plugins.filter(
      (item) => ATTENTION_STATES.includes(item.state) || item.wangp_compatible === false
    ).length;
    const badge = $("plugins-nav-count");
    if (badge) {
      badge.textContent = String(attention);
      badge.hidden = attention === 0;
    }
    const status = payload.status || {};
    $("plugins-summary").textContent = !plugins.length
      ? "No plugins found under the plugins folder."
      : (attention
        ? attention + " of " + plugins.length + " installed plugins need attention."
        : "All " + plugins.length + " installed plugins are healthy.");
    const stamp = status.finished_at || status.started_at;
    $("plugins-updated").textContent = status.fetched && stamp
      ? "Upstream checked " + new Date(stamp * 1000).toLocaleTimeString()
      : "Offline snapshot";
    $("plugins-note").textContent = status.state === "error" && status.error
      ? "Last scan failed: " + status.error
      : "";
  }

  async function load() {
    try {
      render(await S.api("api/plugins/health"));
    } catch (error) {
      $("plugins-summary").textContent = "Plugin health unavailable: " + error.message;
    }
  }

  async function refresh() {
    const button = $("plugins-refresh");
    if (button) button.disabled = true;
    try {
      let payload = await S.api("api/plugins/health/refresh", { method: "POST" });
      render(payload);
      for (let poll = 0; payload.status && payload.status.state === "running" && poll < 120; poll += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        payload = await S.api("api/plugins/health");
        render(payload);
      }
    } catch (error) {
      $("plugins-summary").textContent = "Refresh failed: " + error.message;
    } finally {
      if (button) button.disabled = false;
    }
  }

  function activate() {
    load();
  }

  $("plugins-refresh").addEventListener("click", refresh);
  window.WanGPStudioPlugins = { activate, refresh, load };
  if (location.hash === "#plugins") S.setView("plugins");
})();
