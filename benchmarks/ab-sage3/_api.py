import sys, time
sys.path.insert(0, r"C:\Wan2GP")
t0 = time.time()
try:
    from shared.api import init
    session = init(console_output=False)
    print("API init OK in %.1fs" % (time.time()-t0))
    metas = session.list_model_metadata(query="minimax_h3_10eros")
    print("H3 models found:", len(metas))
    for m in metas[:3]:
        print("  model_type:", getattr(m, "model_type", "?"))
        caps = getattr(m, "capabilities", None)
        print("  capabilities:", caps)
        out = getattr(m, "outputs", None)
        print("  outputs:", out)
except Exception as e:
    print("API init FAILED:", type(e).__name__, str(e)[:300])
