"""Relative error of the MMQ path vs FP32 reference for small / normal / huge activations (Q4_K and Q4_0)."""
import sys
import numpy as np
import torch
import gguf
import llamacpp_gguf_cuda as m

IN_F, OUT_F, ROWS = 4096, 1024, 64
rng = np.random.default_rng(0)


def make(qtype):
    if qtype == "Q4_K":
        nb = 144
        raw = rng.integers(0, 256, size=(OUT_F * IN_F // 256, nb), dtype=np.uint8)
        raw[:, 0:2] = np.frombuffer(np.float16(0.002).tobytes(), dtype=np.uint8)
        raw[:, 2:4] = np.frombuffer(np.float16(0.001).tobytes(), dtype=np.uint8)
    else:
        nb = 18
        raw = rng.integers(0, 256, size=(OUT_F * IN_F // 32, nb), dtype=np.uint8)
        raw[:, 0:2] = np.frombuffer(np.float16(0.002).tobytes(), dtype=np.uint8)
    raw = raw.reshape(OUT_F, -1)
    wd = torch.from_numpy(gguf.quants.dequantize(raw, getattr(gguf.GGMLQuantizationType, qtype))).cuda().float()
    return torch.from_numpy(raw.reshape(-1)).cuda(), wd


print("module:", getattr(m, "__version__", "?"))
for qtype in ("Q4_K", "Q4_0"):
    raw, wd = make(qtype)
    for label, scale, big in (("tiny 1e-4", 1e-4, None), ("small 1e-2", 1e-2, None), ("normal 1", 1.0, None),
                              ("mean-shift 1e-3+1e-4", None, None), ("huge 3e5", 1.0, 3e5)):
        torch.manual_seed(0)
        if scale is None:
            x = torch.randn(ROWS, IN_F, device="cuda") * 1e-4 + 1e-3   # non-zero mean: the sum term matters
        else:
            x = torch.randn(ROWS, IN_F, device="cuda") * scale
        if big:
            x[:, ::32] = big
        x = x.to(torch.bfloat16)
        out = m.linear(raw, qtype, (OUT_F, IN_F), x, None, torch.float32).float()
        ref = x.float() @ wd.t()
        bad = (~torch.isfinite(out)).sum().item()
        err = ((out - ref).norm() / ref.norm()).item() if bad == 0 else float("nan")
        print(f"{qtype} {label:22} nonfinite={bad:6d} rel_l2_err={err:.5f}")
sys.exit(0)
