import json, os
for f in ("defaults/ltx2_25_22B.json", "finetunes/ltx2_25_22B_redgraft_nsfw.json"):
    p = os.path.join(r"C:\Wan2GP", f)
    if not os.path.exists(p): continue
    j = json.load(open(p, encoding="utf-8"))
    m = j.get("model", {})
    print(f"--- {f} ---")
    for k in ("URLs", "text_encoder_URLs", "text_encoder_URL", "VAE_URLs", "text_encoder_filename"):
        if k in m:
            v = m[k]
            print(f"  {k}: {v if not isinstance(v,list) else v}")
