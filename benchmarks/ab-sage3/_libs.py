import importlib
for m in ("cupy","cudf","cuml","cugraph","cucim","cuvs","numba","warp","kvikio","raft","triton"):
    try:
        mod = importlib.import_module(m)
        print("%-10s OK      %s" % (m, getattr(mod, "__version__", "?")))
    except Exception:
        print("%-10s MISSING" % m)
