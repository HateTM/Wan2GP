"""Gate the WanFlow UI test modules that need a CUDA-enabled torch.

Importing ``wan2gp-wanflow-ui.graph_runner`` pulls in postprocessing ->
``shared.attention`` -> ``mmgp.offload``, and mmgp touches CUDA at import
time (``torch.cuda.current_device()`` in runtime.py). The decision lives in
``cuda_gate.collect_ignore_or_raise()`` (see there and test_cuda_gate.py):

- no usable CUDA (CPU-only CI runner) -> the CUDA-dependent modules are
  skipped with an explicit reason;
- CUDA available but the import broken -> the exception propagates so the
  run FAILS; a broken graph_runner must never hide behind a green skip.

A GPU workstation runs the full suite; that remains the acceptance gate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for cuda_gate
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # plugins root: the test modules bootstrap it themselves, too late for this conftest

from cuda_gate import collect_ignore_or_raise

collect_ignore = collect_ignore_or_raise()
