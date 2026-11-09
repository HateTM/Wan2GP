"""V4.5 concept-parity views: IA regroup, Generate, Queue, Image Editor,
health-derived runtime status and the collapsible execution drawer.

The e2e harness has no live WanGP model registry (/api/models reports an
error there on purpose), so Generate is asserted down to its honest
empty/error state rather than a full submission.
"""
import pytest


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
    assert page.locator("#generate-submit[disabled]").count() == 1
    assert page.evaluate("window.WanGPStudio.getView()") == "generate"


def test_queue_view_lists_jobs_and_updates_badge(page):
    # the harness server may carry persisted jobs from earlier suites: the
    # Queue page must render EITHER those cards OR the honest empty state
    _set_view(page, "queue")
    page.wait_for_selector("#queue-view:not([hidden])", timeout=5000)
    # wait for the REGISTRY render (not the static pre-init markup): after
    # renderTasks the list holds cards or the registry's own empty state
    page.wait_for_function(
        "() => { const l = document.getElementById('queue-view-list');"
        " return l.children.length > 0 && !l.textContent.includes('No Studio jobs yet'); }",
        timeout=20000,
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
    initial_height = page.locator("#workflow-canvas-host").bounding_box()["height"]
    page.click("#drawer-toggle")
    page.wait_for_function(
        "() => document.getElementById('execution-drawer').classList.contains('collapsed')", timeout=5000
    )
    assert page.get_attribute("#drawer-toggle", "aria-expanded") == "false"
    assert page.locator("#workflow-canvas-host").bounding_box()["height"] > initial_height
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
    _set_view(page, "generate")
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
    assert not page.locator("#generate-empty").is_visible()
    assert page.locator("#generate-submit").is_enabled()
    for width, height in [(1440, 900), (1366, 768), (1024, 800), (390, 844)]:
        page.set_viewport_size({"width": width, "height": height})
        submit = page.locator("#generate-submit").bounding_box()
        assert submit and submit["width"] > 200 and submit["y"] + submit["height"] <= height
        assert page.locator("#nav-queue").is_visible()


@pytest.mark.parametrize("width,height", [(1024, 800), (768, 900), (390, 844)])
def test_inspector_is_reachable_on_small_screens(page, width, height):
    """Audit P1: at <=1439 the inspector is a drawer and at <=1024 it stacks
    below the canvas - but the pane toggles must stay usable at every width,
    otherwise the inspector is unreachable."""
    page.set_viewport_size({"width": width, "height": height})
    page.evaluate("window.WanGPStudio.setView('workflow')")
    page.wait_for_selector("#workflow-canvas-host", timeout=10000)
    assert page.locator("#inspector-toggle").is_visible(), f"toggle hidden at {width}px"
    assert page.locator("#library-toggle").is_visible(), f"library toggle hidden at {width}px"
    # inspector starts closed on narrow screens and opens via the toggle
    page.wait_for_timeout(300)
    panel = page.locator(".inspector-panel")
    initially_visible = panel.is_visible()
    page.click("#inspector-toggle")
    page.wait_for_timeout(300)
    assert panel.is_visible(), f"inspector did not open at {width}px"
    page.click("#inspector-toggle")
    page.wait_for_timeout(300)
    if not initially_visible:
        assert not panel.is_visible(), f"inspector did not close at {width}px"


def test_queue_view_shows_workflow_runs_in_unified_registry(page):
    """Audit P1: the Queue must show BOTH task kinds. A run that fails fast
    (missing input file) still enters the registry with its graph."""
    import json as _json
    import time as _time
    import urllib.request

    origin = page.url.split("#")[0].rstrip("/") + "/"
    graph = {"name": "E2E registry", "nodes": [
        {"id": "n1", "type": "input_video", "params": {"path": "Z:/definitely-missing.mp4"}, "enabled": True}],
        "edges": []}
    request = urllib.request.Request(
        origin + "api/workflow/runs", data=_json.dumps({"graph": graph, "inputs": []}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            run_id = _json.loads(response.read())["run_id"]
    except Exception:
        pytest.skip("workflow runner unavailable in this environment")
    deadline = _time.time() + 30
    while _time.time() < deadline:
        with urllib.request.urlopen(origin + "api/tasks", timeout=15) as response:
            tasks = _json.loads(response.read())
        entry = next((task for task in tasks if task["id"] == run_id), None)
        if entry is not None and entry["status"] != "running":
            break
        _time.sleep(0.5)
    assert entry is not None, "workflow run never reached the unified registry"
    assert entry["kind"] == "workflow"
    assert entry["has_graph"] is True
    saved_graph = page.evaluate("(id) => window.WanGPStudio.api('api/tasks/' + id + '/graph')", run_id)
    assert saved_graph["name"] == graph["name"]
    page.evaluate("window.WanGPStudio.setView('queue')")
    page.wait_for_function(
        "(runId) => Array.from(document.querySelectorAll('#queue-view-list .queue-card'))"
        ".some((card) => card.textContent.includes('E2E registry'))",
        arg=run_id, timeout=20000,
    )
    assert page.locator("#queue-view-list .task-kind").count() >= 1
    repeat = page.locator(f'#queue-view-list [data-task="{run_id}"] button[data-repeat-run]')
    with page.expect_response(lambda response: response.url.endswith(f"/{run_id}/repeat")) as result:
        repeat.click()
    assert result.value.ok and result.value.json()["run_id"] != run_id


def test_inspector_resets_state_for_plain_nodes(page):
    """Audit P2: after a generation node, selecting a plain node must forget
    the model (Run disabled) and never carry the stale prompt."""
    page.evaluate("window.WanGPStudio.setView('workflow')")
    page.wait_for_selector("#workflow-canvas-host", timeout=10000)
    # simulate what the canvas bridge delivers: first a model node, then a plain one
    page.evaluate(
        "window.WanGPStudio.selectModel('stub-model-for-inspector').catch(() => {})"
    )
    page.wait_for_timeout(400)
    page.evaluate(
        "window.WanGPStudio.onNodeSelected({ id: 'plain1', type: 'input_image', title: 'Input Image', params: { path: 'C:/x/a.png' } })"
    )
    page.wait_for_timeout(200)
    assert page.locator("#run-from-inspector[disabled]").count() == 1
    assert page.text_content("#prompt-input") == ""
    # an empty prompt on the node restores as empty (not the previous text)
    page.evaluate(
        "window.WanGPStudio.onNodeSelected({ id: 'm1', type: 'generate_video', title: 'Generate', params: { model_type: 'stub-model-for-inspector', prompt: '' } })"
    )
    page.wait_for_timeout(600)
    assert page.text_content("#prompt-input") == ""


def test_canvas_selection_and_apply_reach_the_inspector(page):
    page.evaluate("window.WanGPStudio.setView('workflow')")
    page.evaluate("window.WanGPStudioCanvas.addMediaInput('image', 'C:/test.png')")
    page.wait_for_function("document.querySelector('#inspector-heading').textContent !== 'Parameters'")
    page.locator("#settings-json").fill('{"path":"C:/test.png","slot":7}')
    page.locator("#apply-to-node").click()
    page.wait_for_function("document.querySelector('#toast-region').textContent.includes('Applied')")
    graph = page.evaluate("window.WanGPStudioCanvas.getGraph()")
    assert graph["nodes"][0]["params"]["slot"] == 7
    page.frame_locator("#workflow-frame").locator("#nodeSearch").press("Escape")
    page.locator("#inspector-empty").wait_for(state="visible")


def test_canvas_save_and_shortcut_use_the_live_graph(page):
    requests = []

    def save(route):
        request = route.request
        if request.method not in {"POST", "PUT"}:
            route.continue_()
            return
        data = request.post_data_json
        requests.append((request.method, data))
        route.fulfill(json={"id": "test-graph", "graph": {**data["graph"], "name": data["name"]}})

    page.route("**/api/workflow/workflows**", save)
    _set_view(page, "workflow")
    page.evaluate("window.WanGPStudioCanvas.addMediaInput('image', 'C:/test.png')")
    page.locator("#apply-to-node").wait_for()
    page.locator("#workflow-save").click()
    page.get_by_role("textbox", name="Workflow name").fill("Граф")
    page.get_by_role("button", name="Save graph").click()
    page.wait_for_function("document.querySelector('#workflow-status').textContent === 'Граф · saved'")
    with page.expect_response(lambda response: response.request.method == "PUT" and response.url.endswith("/test-graph")):
        page.frame_locator("#workflow-frame").locator("#nodeSearch").press("Control+s")
    assert requests[0][0] == "POST"
    assert requests[1][0] == "PUT"
    assert requests[1][1]["graph"]["nodes"][0]["type"] == "input_image"


def test_run_after_opening_saved_workflow_uses_loaded_graph(page):
    graph = {
        "name": "Saved workflow",
        "nodes": [{"id": "saved-text", "type": "text", "title": "Text", "params": {"text": "live graph"},
                   "position": {"x": 120, "y": 80}}],
        "edges": [],
        "groups": [],
    }
    page.route("**/api/workflow/workflows", lambda route: route.fulfill(json=[{"id": "saved", "name": graph["name"]}]))
    page.route("**/api/workflow/workflows/saved", lambda route: route.fulfill(json=graph))
    page.route("**/api/workflow/runs", lambda route: route.fulfill(json={"run_id": "test-run", "nodes": {}}))
    _set_view(page, "workflow")
    page.locator("#workflow-select").select_option("saved")
    with page.expect_request(lambda request: request.method == "POST" and request.url.endswith("/api/workflow/runs")) as run:
        page.locator("#run-generation").click()
    submitted = run.value.post_data_json["graph"]
    assert submitted["name"] == graph["name"]
    assert submitted["nodes"][0]["id"] == "saved-text"


def test_task_results_open_by_id_even_with_a_gallery_filter(page):
    results = page.evaluate("""
        async () => (await window.WanGPStudio.api('api/media?limit=2')).items
            .map(({id, name}) => ({id, name}))
    """)
    assert len(results) == 2
    page.locator('#gallery-kinds [data-kind="video"]').click()
    page.evaluate("(results) => window.WanGPStudioGallery.openResults(results)", results)
    page.wait_for_function("(name) => document.querySelector('#lightbox-name').textContent === name", arg=results[0]["name"])
    page.locator("#lightbox-task-results").select_option(results[1]["id"])
    page.wait_for_function("(name) => document.querySelector('#lightbox-name').textContent === name", arg=results[1]["name"])
