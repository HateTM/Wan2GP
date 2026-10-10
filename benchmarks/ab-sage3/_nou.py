import json
p = r"C:\Wan2GP\wgp_config.json"
c = json.load(open(p, encoding="utf-8"))
before = c.get("preload_model_policy")
c["preload_model_policy"] = []          # без выгрузки модели между задачами
json.dump(c, open(p, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
print("preload_model_policy: %r -> %r" % (before, c["preload_model_policy"]))
