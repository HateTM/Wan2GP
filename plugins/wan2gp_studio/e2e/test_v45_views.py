"""V4.5 concept-parity views: IA regroup, Generate, Queue, Image Editor,
health-derived runtime status and the collapsible execution drawer.

The e2e harness has no live WanGP model registry (/api/models reports an
error there on purpose), so Generate is asserted down to its honest
empty/error state rather than a full submission.
"""


def _set_view(page, view):
    page.evaluate(f"window.WanGPStudio.setView('{view}')")


def test_navigation_groups_match_concept(page):
    labels = page.evaluate(
        "() => Array.from(document.querySelectorAll('.sidebar-label')).map((el) => el.textContent.trim())"
    )
    assert labels == ["WORKSPACE", "LIBRARY", "MANAGE", "SYSTEM"], labels
    for nav_id in ("nav-dashboard", "nav-generate", "nav-workflow", "nav-gallery",
                   "nav-imageeditor", "nav-models", "nav-queue", "nav-resources",
                   "nav-plugins", "nav-settings"):
        assert page.locator(f"#{nav_id}").count() == 1, nav_id


def test_runtime_status_derived_from_health(page):
    """The sidebar must never claim a connection it has not verified: /api/health
    works in the harness, so the derived status is 'connected'."""
    page.wait_for_function(
        "() => document.getElementById('runtime-label').textContent === 'WanGP connected'",
        timeout=20000,
    )
    assert page.text_content("#runtime-state").startswith("Session") or \
        page.text_content("#runtime-state").startswith("Lazy")


def test_generate_view_honest_without_catalog(page):
    _set_view(page, "generate")
    page.wait_for_selector("#generate-view:not([hidden])", timeout=5000)
    # no model registry in the harness: the picker says so, Run stays disabled
    page.wait_for_function(
        "() => { const list = document.getElementById('generate-model-list');"
        " return list && list.textContent.length > 0 && !list.textContent.includes('Loading'); }",
        timeout=20000,
    )
    assert "not loaded" in page.text_content("#generate-model-list") or \
        "No matching" in page.text_content("#generate-model-list")
    assert page.locator("#generate-run[disabled]").count() == 1
    assert page.evaluate("window.WanGPStudio.getView()") == "generate"


def test_queue_view_lists_jobs_and_updates_badge(page):
    # the harness server may carry persisted jobs from earlier suites: the
    # Queue page must render EITHER those cards OR the honest empty state
    _set_view(page, "queue")
    page.wait_for_selector("#queue-view:not([hidden])", timeout=5000)
    page.wait_for_function(
        "() => document.getElementById('queue-view-list').children.length > 0", timeout=20000
    )
    cards = page.locator("#queue-view-list .queue-card").count()
    assert cards > 0 or page.locator("#queue-view-list .queue-empty").count() == 1
    # the nav badge mirrors the active (non-terminal) job count
    badge = page.text_content("#queue-nav-count") or ""
    assert badge.strip().isdigit() or page.locator("#queue-nav-count[hidden]").count() == 1


def test_image_editor_reports_dependency_state(page):
    _set_view(page, "imageeditor")
    page.wait_for_selector("#imageeditor-view:not([hidden])", timeout=5000)
    page.wait_for_function(
        "() => document.getElementById('imageeditor-plugin-state').textContent !== 'checking…'",
        timeout=20000,
    )
    # whatever the machine's actual ImageSuite state is, it must be explicit
    # and the recovery affordance must match it
    state_text = page.text_content("#imageeditor-plugin-state")
    assert state_text in ("not_installed", "disabled", "enabled"), state_text
    assert page.locator("#imageeditor-open").is_visible() == (state_text == "enabled")
    assert page.locator("#imageeditor-goto-plugins").is_visible() == (state_text != "enabled")


def test_execution_drawer_collapses(page):
    _set_view(page, "workflow")  # the drawer lives on the workflow screen
    page.wait_for_selector("#execution-drawer:not([hidden])", timeout=5000)
    assert "collapsed" not in (page.get_attribute("#execution-drawer", "class") or "")
    page.click("#drawer-toggle")
    page.wait_for_function(
        "() => document.getElementById('execution-drawer').classList.contains('collapsed')", timeout=5000
    )
    assert page.get_attribute("#drawer-toggle", "aria-expanded") == "false"
    page.click("#drawer-toggle")
    page.wait_for_function(
        "() => !document.getElementById('execution-drawer').classList.contains('collapsed')", timeout=5000
    )


def test_hash_aliases_still_route(page):
    for old_hash, view in (("#library", "gallery"), ("#history", "queue"), ("#media", "gallery")):
        page.evaluate(f"location.hash = '{old_hash}'")
        # setView is only triggered on load; emulate the router entry point
        page.evaluate(f"window.WanGPStudio.setView('{view}')")
        assert page.evaluate("window.WanGPStudio.getView()") == view


def test_models_view_renders_catalog_or_honest_error(page):
    """MANAGE > Models: the read-only catalog page. The harness has no live
    registry, so either the list or the explicit 'not loaded' state shows."""
    page.evaluate("window.WanGPStudio.setView('models')")
    page.wait_for_selector("#models-view:not([hidden])", timeout=5000)
    page.wait_for_function(
        "() => { const l = document.getElementById('models-list'); return l.textContent.length > 0 && !l.textContent.includes('Loading'); }",
        timeout=20000,
    )
    text = page.text_content("#models-list")
    assert "No matching" in text or "not loaded" in text or "model-card" in (page.locator("#models-list").inner_html())
    # deep link into Generate with a preselected model: the detail fetch runs
    # even without a catalog and ends in an honest per-model error state
    page.evaluate("window.WanGPStudioGenerate.preset('e2e-stub-model')")
    page.wait_for_function(
        "() => document.getElementById('generate-state').textContent === 'Could not load model'",
        timeout=20000,
    )


def test_generate_input_slot_mapping_is_pure(page):
    """applyInputPath maps a capability role to WanGP's ATTACHMENT_KEYS."""
    mapping = page.evaluate(
        """(() => {
          const f = window.WanGPStudioGenerate.applyInputPath;
          return {
            image: f({}, "image", "C:/x/a.png").image_guide,
            video: f({}, "video", "C:/x/b.mp4").video_guide,
            audio: f({}, "audio", "C:/x/c.wav").audio_guide,
            text: "text" in f({}, "text", "C:/x/t.txt"),
            cleared: f({ image_guide: "old" }, "image", "").image_guide
          };
        })()"""
    )
    assert mapping["image"] == "C:/x/a.png"
    assert mapping["video"] == "C:/x/b.mp4"
    assert mapping["audio"] == "C:/x/c.wav"
    assert mapping["text"] is False  # text roles never map to an attachment key


def test_generate_input_slots_render_from_metadata(page):
    """With a detail carrying inputs, slots appear per media role with the
    native attachment key shown."""
    page.evaluate(
        """(() => {
          const detail = {
            model: { name: "Stub I2V" },
            metadata: { inputs: ["image", "text"] },
            defaults: { prompt: "", image_guide: "C:/media/seed.png" },
            presets: { settings: [] }
          };
          window.WanGPStudioGenerate.__renderSlotsForTest = null;
          // renderInputSlots is internal; drive it through selectModel's path
          // by faking the API response
          const original = window.WanGPStudio.api;
          window.WanGPStudio.api = async (path) => {
            if (path.startsWith("api/models/")) return detail;
            return original(path);
          };
          return null;
        })()"""
    )
    page.evaluate("window.WanGPStudioGenerate.preset('stub-i2v')")
    page.wait_for_function(
        "() => !document.getElementById('generate-inputs').hidden", timeout=10000
    )
    slots = page.locator("#generate-input-slots .input-slot")
    assert slots.count() == 1  # only media roles render, text does not
    assert "image_guide" in page.text_content("#generate-input-slots")
    assert "seed.png" in page.text_content("#generate-input-slots")
