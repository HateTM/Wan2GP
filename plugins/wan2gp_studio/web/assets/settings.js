(() => {
  "use strict";
  const S = window.WanGPStudio;
  if (!S) return;
  const $ = (id) => document.getElementById(id);
  const state = { loading: false };

  function cell(value) {
    return "<span>" + S.esc(value == null || value === "" ? "—" : value) + "</span>";
  }

  async function load() {
    if (state.loading) return;
    state.loading = true;
    try {
      const [environment, media] = await Promise.all([
        S.api("api/environment"),
        S.api("api/media/roots")
      ]);
      const header = '<div class="settings-row header"><span>Plugin</span><span>State</span><span>Version</span><span>Integration</span><span>License</span></div>';
      const rows = (environment.plugins || []).map((plugin) =>
        '<div class="settings-row">' +
        '<span title="' + S.esc(plugin.id) + '">' + S.esc(plugin.id) + "</span>" +
        '<span class="state-' + S.esc(plugin.state) + '">' + S.esc(plugin.state) + "</span>" +
        cell(plugin.version) + cell(plugin.integration) + cell(plugin.license) +
        "</div>"
      ).join("");
      $("settings-plugins").innerHTML = header + rows;
      const roots = media.roots || [];
      $("settings-roots").innerHTML = roots.length
        ? roots.map((root) => '<div class="settings-root">' + S.esc(root) + "</div>").join("")
        : '<span class="field-note">No media roots configured.</span>';
    } catch (error) {
      $("settings-plugins").textContent = "Settings unavailable: " + error.message;
    } finally {
      state.loading = false;
    }
  }

  window.WanGPStudioSettings = { activate: load, refresh: load };
  if (location.hash === "#settings") S.setView("settings");
})();
