"""Report the CUDA-dependent modules as explicit test outcomes.

The six graph-runner modules are excluded from collection wholesale when no
CUDA-enabled torch is available (see cuda_gate.py / conftest.py) - ``pytest``
would otherwise not mention them at all. These placeholders make the
exclusion visible: on a CPU-only runner each module shows up as a skip
naming the reason (visible with ``-rs``), and on a CUDA machine they pass as
a confirmation that the whole gate allowed collection.
"""
import pytest

from cuda_gate import CUDA_DEPENDENT_MODULES, cuda_ready

_EXCLUDED = not cuda_ready()
_REASON = (
    "module not collected on this runner: no CUDA-enabled torch "
    "(the graph-runner import chain reaches mmgp, which asserts CUDA)"
)


@pytest.mark.skipif(_EXCLUDED, reason=_REASON)
@pytest.mark.parametrize("module", CUDA_DEPENDENT_MODULES)
def test_cuda_dependent_module_allowed_for_collection(module):
    """The real tests for this module run elsewhere in the suite; this
    placeholder only documents that the gate let it through (or, when
    skipped, exactly why it did not)."""
    assert module in CUDA_DEPENDENT_MODULES
