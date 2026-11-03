import json, os, re
print("=== REDGraft finetune definition (what it actually loads) ===")
p = r"C:\Wan2GP\finetunes\ltx2_25_22B_redgraft_nsfw.json"
d = json.load(open(p, encoding="utf-8"))
print("  model.URLs :", d.get("model", {}).get("URLs"))
print("  architecture:", d.get("model", {}).get("architecture"))
print()
print("=== does the filename mark a dtype? ===")
fn = "ltx-2.5-22b-redgraft-sulphur2_int8_convrot.safetensors"
for tok in ("bf16","fp16","int8","convrot","nvfp4","quanto"):
    print(f"  contains {tok:8}: {tok in fn.lower()}")
print()
print("=== code that picks transformer dtype from the filename (wgp.py:4105-4113) ===")
lines = open(r"C:\Wan2GP\wgp.py", encoding="utf-8").read().splitlines()
for i in range(4100, 4114):
    print(f"  {i+1}: {lines[i]}")
