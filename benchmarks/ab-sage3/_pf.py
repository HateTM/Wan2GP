import json
p = r"C:\Wan2GP\wgp_config.json"
c = json.load(open(p, encoding="utf-8"))
c["prefetch_window"] = 0          # синхронный шаттл: минимум RAM под блоки
json.dump(c, open(p, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
print("prefetch_window =", c["prefetch_window"])
