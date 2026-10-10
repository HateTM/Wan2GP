import json
c = json.load(open(r"C:\Wan2GP\wgp_config.json", encoding="utf-8"))
for k in ("read_ahead", "smart_memory_pinning", "perc_reserved_mem_max",
          "video_preload_mode", "video_preload_in_VRAM", "prefetch_window",
          "video_profile", "preload_model_policy"):
    mark = "" if k in c else "   <-- НЕТ в конфиге (действует дефолт)"
    print("  %-26s = %-12s%s" % (k, repr(c.get(k)), mark))
