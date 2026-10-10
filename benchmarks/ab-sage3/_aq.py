import json, os
print("=== auto_quantize flag for LTX-2.5 (decides quantizeTransformer) ===")
for f in ["defaults/ltx2_25_22B.json", "finetunes/ltx2_25_22B_redgraft_nsfw.json"]:
    p = os.path.join(r"C:\Wan2GP", f)
    if not os.path.exists(p):
        print("  (missing)", f); continue
    d = json.load(open(p, encoding="utf-8"))
    m = d.get("model", {})
    print(f"  {f}: auto_quantize={m.get('auto_quantize', '(unset)')}  quantizeTransformer_would_be_True={m.get('auto_quantize', False) is True}")
print()
print("=== W4A8 docstring (what this qtype actually is) ===")
src = open(r"C:\Wan2GP\shared\qtypes\asym_w4a8_int8.py", encoding="utf-8").read().splitlines()
for i, ln in enumerate(src[:14], 1):
    print(f"  {i}: {ln}")
