import json, os
p = r"C:\Wan2GP\finetunes\minimax_h3_10eros_max_b5_fl2va.json"
j = json.load(open(p, encoding="utf-8"))
print("  architecture:", j.get("model", {}).get("architecture"))
print("  URLs:", j.get("model", {}).get("URLs"))
print("  keys:", list(j.keys())[:10])
print()
print("=== какие ещё H3-компоненты нужны (текст. энкодер и т.п.) ===")
import glob
for f in glob.glob(r"C:\Wan2GP\defaults\minimax_h3*.json"):
    d = json.load(open(f, encoding="utf-8"))
    m = d.get("model", {})
    urls = m.get("URLs", [])
    print(f"  {os.path.basename(f)}: arch={m.get('architecture')}")
    if isinstance(urls, list):
        for u in urls: print("      ", os.path.basename(str(u)))
