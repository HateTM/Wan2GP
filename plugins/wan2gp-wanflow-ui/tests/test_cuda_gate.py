"""Regressions for the CUDA skip gate (see cuda_gate.py / conftest.py).

The gate must never turn a broken import into a green skip: a missing or
unusable CUDA is the only legitimate skip reason. These tests are pure - they
run on every machine, CPU runner included.
"""
import importlib
import sys
import types

import pytest

from cuda_gate import CUDA_DEPENDENT_MODULES, cuda_ready, runner_import_or_none


def _install_torch(monkeypatch, *, build_cuda, device_available, device_works=True):
    fake = types.SimpleNamespace(
        version=types.SimpleNamespace(cuda="12.8" if build_cuda else None),
        cuda=types.SimpleNamespace(
            is_available=lambda: device_available,
            get_device_capability=lambda device: {"major": 8} if device_works else (_ for _ in ()).throw(AssertionError("Invalid device id")),
        ),
    )
    monkeypatch.setitem(sys.modules, "torch", fake)


def test_no_torch_at_all_is_not_cuda_ready(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)  # "import torch" raises ImportError
    assert cuda_ready() is False


def test_cpu_build_is_not_cuda_ready(monkeypatch):
    _install_torch(monkeypatch, build_cuda=False, device_available=True)
    assert cuda_ready() is False


def test_cuda_build_without_usable_device_is_not_cuda_ready(monkeypatch):
    _install_torch(monkeypatch, build_cuda=True, device_available=False)
    assert cuda_ready() is False


def test_cuda_build_with_device_is_ready(monkeypatch):
    _install_torch(monkeypatch, build_cuda=True, device_available=True)
    assert cuda_ready() is True


def test_nvml_visible_but_unusable_device_is_not_ready(monkeypatch):
    """Some torch builds answer is_available() via NVML, which ignores
    CUDA_VISIBLE_DEVICES; mmgp then dies resolving device properties. The
    gate must catch that and skip, not error."""
    _install_torch(monkeypatch, build_cuda=True, device_available=True, device_works=False)
    assert cuda_ready() is False


def test_runner_import_reports_failure_without_raising(monkeypatch):
    """A broken graph_runner must be REPORTED, not swallowed silently."""
    def broken_import(name, *args, **kwargs):
        if name.endswith("graph_runner"):
            raise RuntimeError("regression in graph_runner")
        return importlib.import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", broken_import)
    failure = runner_import_or_none()
    assert isinstance(failure, RuntimeError)
    assert "regression" in str(failure)


def test_runner_import_success_reports_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "wan2gp-wanflow-ui.graph_runner", types.ModuleType("stub"))
    assert runner_import_or_none() is None


def test_gate_skips_modules_when_cuda_unavailable(monkeypatch):
    monkeypatch.setattr(sys.modules["cuda_gate"], "cuda_ready", lambda: False)
    import cuda_gate

    assert cuda_gate.collect_ignore_or_raise() == list(cuda_gate.CUDA_DEPENDENT_MODULES)


def test_gate_fails_when_cuda_ready_but_import_broken(monkeypatch):
    """The acceptance-gate contract: with CUDA present, a broken graph_runner
    propagates as an error instead of becoming a skip."""
    monkeypatch.setattr(sys.modules["cuda_gate"], "cuda_ready", lambda: True)
    monkeypatch.setattr(
        sys.modules["cuda_gate"], "runner_import_or_none", lambda: RuntimeError("regression in graph_runner")
    )
    import cuda_gate

    with pytest.raises(RuntimeError, match="regression"):
        cuda_gate.collect_ignore_or_raise()


def test_require_cuda_refuses_to_skip_without_gpu(monkeypatch):
    """WANFLOW_REQUIRE_CUDA=1: a missing GPU is a configuration error, not a
    legitimate skip - the strict acceptance run must fail loudly."""
    monkeypatch.setattr(sys.modules["cuda_gate"], "cuda_ready", lambda: False)
    monkeypatch.setenv("WANFLOW_REQUIRE_CUDA", "1")
    import cuda_gate

    with pytest.raises(RuntimeError, match="WANFLOW_REQUIRE_CUDA"):
        cuda_gate.collect_ignore_or_raise()


def test_require_cuda_runs_normally_when_ready(monkeypatch):
    monkeypatch.setattr(sys.modules["cuda_gate"], "cuda_ready", lambda: True)
    monkeypatch.setattr(sys.modules["cuda_gate"], "runner_import_or_none", lambda: None)
    monkeypatch.setenv("WANFLOW_REQUIRE_CUDA", "1")
    import cuda_gate

    assert cuda_gate.collect_ignore_or_raise() == []


def test_gate_ignores_nothing_when_cuda_ready_and_import_ok(monkeypatch):
    monkeypatch.setattr(sys.modules["cuda_gate"], "cuda_ready", lambda: True)
    monkeypatch.setattr(sys.modules["cuda_gate"], "runner_import_or_none", lambda: None)
    import cuda_gate

    assert cuda_gate.collect_ignore_or_raise() == []


def test_skip_list_is_non_empty_and_test_named():
    assert CUDA_DEPENDENT_MODULES
    for name in CUDA_DEPENDENT_MODULES:
        assert name.startswith("test_") and name.endswith(".py")
