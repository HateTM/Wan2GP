import sys
sys.path.insert(0, r"C:\Wan2GP")
from shared.api import init
session = init(console_output=False)
metas = session.list_model_metadata(query="minimax_h3_10eros")
m = metas[0]
print("type:", type(m))
if isinstance(m, dict):
    import json
    print(json.dumps(m, indent=1, ensure_ascii=False, default=str)[:2500])
else:
    print("attrs:", [a for a in dir(m) if not a.startswith("_")])
    for a in ("model_type","name","family","base_model_type","main_output","outputs","capabilities"):
        if hasattr(m, a): print(f"  {a} = {getattr(m, a)}")
