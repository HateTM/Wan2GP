import json, os, glob
targets = {
    "BigLoveKlein4_nvfp4": 5.23,
    "Krea2RedMix3.0-ComfyUI-nvfp4": 7.15,
    "10Eros_Max_h3_TURBO-hybrid_beta5_w4a8_14gb_optimized": 13.04,
}
for name, gb in targets.items():
    found = None
    for d in ("finetunes", "defaults"):
        for f in glob.glob(os.path.join(r"C:\Wan2GP", d, "*.json")):
            try:
                j = json.load(open(f, encoding="utf-8"))
            except Exception:
                continue
            urls = j.get("model", {}).get("URLs", [])
            if isinstance(urls, list) and any(name in str(u) for u in urls):
                found = (d, os.path.basename(f), j.get("model", {}).get("architecture"))
                break
        if found: break
    print(f"  {name[:44]:46s} {gb:>5} GB -> {found}")
