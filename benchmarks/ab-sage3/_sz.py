import json
p = r"C:\Wan2GP-Models\ckpts\ltx-2.5-22b-distilled_diffusion_model_nvfp4.metadata.json"
d = json.load(open(p, encoding="utf-8"))
sz = d.get("size")
print("  size bytes:", sz)
print("  = %.2f GB (%.2f GiB)" % (sz/1e9, sz/1024**3))
print()
print("  для сравнения:")
print("    REDGraft int8 (наш)      = 15.86 GB")
print("    distilled int8 (локально) = 18.15 GB")
print("    distilled nvfp4 (запись)  = %.2f GB" % (sz/1e9))
print()
print("  разница REDGraft -> distilled nvfp4: %+.2f GB" % (sz/1e9 - 15.86))
