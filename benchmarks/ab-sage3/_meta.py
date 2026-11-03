import json, os
meta = r"C:\Wan2GP-Models\ckpts\ltx-2.5-22b-redgraft-sulphur2_int8_convrot.metadata.json"
if os.path.exists(meta):
    d = json.load(open(meta, encoding="utf-8"))
    print(json.dumps(d, indent=1)[:1500])
else:
    print("no metadata file")
