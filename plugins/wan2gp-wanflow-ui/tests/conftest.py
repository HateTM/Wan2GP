"""Skip the graph-runner test modules that need a CUDA-enabled torch.

Importing ``wan2gp-wanflow-ui.graph_runner`` pulls in postprocessing ->
``shared.attention`` -> ``mmgp.offload``, and mmgp touches CUDA at import
time (``torch.cuda.current_device()`` in runtime.py). On a CPU-only torch
build - the CI runner installs one on purpose - those modules cannot even be
collected, so they are skipped with an explicit reason here. A GPU
workstation runs the full suite; that remains the acceptance gate.
"""
import importlib
import sys
from pathlib import Path

_SKIP_WITHOUT_CUDA = [
    "test_graph_runner_multiprompt.py",
    "test_graph_runner_settings.py",
    "test_graph_runner_unload.py",
    "test_lora_stack_run.py",
    "test_preflight.py",
    "test_run_cache.py",
]

collect_ignore = []

# The probe needs the plugins root on sys.path; the test modules bootstrap it
# themselves at import time, which is too late for this conftest.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    importlib.import_module("wan2gp-wanflow-ui.graph_runner")
except Exception as exc:  # noqa: BLE001 - every import failure means the same skip
    sys.stderr.write(
        f"wanflow-ui tests: graph_runner is not importable here ({type(exc).__name__}: {exc});"
        f" skipping {len(_SKIP_WITHOUT_CUDA)} CUDA-dependent modules\n"
    )
    collect_ignore = _SKIP_WITHOUT_CUDA
