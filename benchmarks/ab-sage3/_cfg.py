import json
c = json.load(open(r"C:\Wan2GP\wgp_config.json", encoding="utf-8"))
keys = ["vram_safety_coefficient","perc_reserved_mem_max","smart_memory_pinning",
        "transformer_quantization","text_encoder_quantization","transformer_dtype_policy",
        "int8_kernels","video_profile","image_profile","vae_precision","read_ahead"]
print("=== relevant config keys ===")
for k in keys:
    mark = "" if k in c else "   <-- ABSENT (code default applies)"
    print("  %-26s = %-8s%s" % (k, repr(c.get(k)), mark))
print()
print("=== the REDGraft checkpoint we profile ===")
import os
p = r"C:\Wan2GP-Models\ckpts\ltx-2.5-22b-redgraft-sulphur2_int8_convrot.safetensors"
print("  file:", os.path.basename(p), "=", round(os.path.getsize(p)/1024**3, 2), "GB")
