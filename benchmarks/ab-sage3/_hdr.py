import json, struct
p = r"C:\Wan2GP-Models\ckpts\ltx-2.5-22b-redgraft-sulphur2_int8_convrot.safetensors"
with open(p, "rb") as f:
    n = struct.unpack("<Q", f.read(8))[0]
    hdr = json.loads(f.read(n).decode("utf-8"))
keys = [k for k in hdr if k != "__metadata__"]
print("tensors:", len(keys))
print()
# markers of each format
w4a8 = [k for k in keys if k.endswith(".weight_s_rel")]
convrot = [k for k in keys if "convrot" in k.lower()]
scale = [k for k in keys if k.endswith(".weight_scale")]
print("  .weight_s_rel  (W4A8 marker) :", len(w4a8))
print("  'convrot' in name            :", len(convrot))
print("  .weight_scale                :", len(scale))
print()
import collections
suf = collections.Counter(k.rsplit(".",1)[-1] for k in keys)
print("top tensor suffixes:")
for s, c in suf.most_common(10):
    print(f"   {s:24s} {c}")
print()
if w4a8:
    print("sample w4a8 entry:", w4a8[0], hdr[w4a8[0]].get("dtype"), hdr[w4a8[0]].get("shape"))
    base = w4a8[0].removesuffix(".weight_s_rel")
    for cand in (base+".weight", base+".weight_s_channel", base+".qdata"):
        if cand in hdr:
            print("   companion:", cand.rsplit('.',1)[-1], hdr[cand].get("dtype"), hdr[cand].get("shape"))
