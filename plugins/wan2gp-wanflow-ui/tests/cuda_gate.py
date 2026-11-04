"""Shared CUDA gate for the WanFlow UI test suite (see conftest.py).

Importing the graph-runner chain reaches mmgp, which asserts a CUDA-enabled
torch at import time. The gate must distinguish two very different situations:

- no usable CUDA -> the heavy modules are skipped (expected on the CPU-only
  CI runner, which installs CPU torch on purpose);
- CUDA available but the import broken -> a real regression that MUST fail
  the run; callers raise the reported exception instead of skipping.
"""
from __future__ import annotations

import importlib
import os

#: Test modules whose import chain reaches mmgp; only skipped when CUDA is
#: genuinely unavailable.
CUDA_DEPENDENT_MODULES = [
    "test_graph_runner_multiprompt.py",
    "test_graph_runner_settings.py",
    "test_graph_runner_unload.py",
    "test_lora_stack_run.py",
    "test_preflight.py",
    "test_run_cache.py",
]


def cuda_ready() -> bool:
    """True only when torch is a CUDA build AND a device is actually usable.

    ``is_available()`` alone lies in one direction: some torch builds answer
    via NVML, which ignores ``CUDA_VISIBLE_DEVICES``. mmgp's import chain
    resolves device properties (``get_device_capability``), so that exact
    call is what the gate verifies."""
    try:
        import torch
    except Exception:
        return False
    if not torch.version.cuda or not torch.cuda.is_available():
        return False
    try:
        torch.cuda.get_device_capability(0)
        return True
    except Exception:
        return False


def runner_import_or_none() -> Exception | None:
    """Import the heavy runner chain; report the exception instead of raising.

    Callers may only swallow the result when ``cuda_ready()`` is False - on a
    CUDA machine a raised import error is a regression, not a skip."""
    try:
        importlib.import_module("wan2gp-wanflow-ui.graph_runner")
        return None
    except Exception as exc:  # noqa: BLE001 - reported to the caller, see above
        return exc


def collect_ignore_or_raise() -> list[str]:
    """The conftest decision, in one testable function.

    - no usable CUDA -> the CUDA-dependent modules are ignored (skipped),
      unless ``WANFLOW_REQUIRE_CUDA=1``: the strict GPU acceptance run then
      refuses to skip - a missing GPU there is a configuration error;
    - CUDA available -> the import must succeed; a failure is re-raised so
      the run fails instead of hiding behind green skips."""
    if not cuda_ready():
        if os.environ.get("WANFLOW_REQUIRE_CUDA") == "1":
            raise RuntimeError(
                "WANFLOW_REQUIRE_CUDA=1 but no CUDA-enabled torch with a usable "
                "device is available; the strict GPU acceptance run refuses to "
                "skip the heavy modules."
            )
        return list(CUDA_DEPENDENT_MODULES)
    failure = runner_import_or_none()
    if failure is not None:
        raise failure
    return []
