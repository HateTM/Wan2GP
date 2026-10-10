import re
log = r"C:\Wan2GP\.zwork\background\2026-10-09T16-18-18-822Z-2dthva.log"
lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
ts = re.compile(r"^\[ *(\d+\.\d+)s\] *(.*)$")
rows = [(float(m.group(1)), m.group(2)) for ln in lines if (m := ts.match(ln))]
print("=== TASK 2 timeline (142.5s .. 545s), dedup consecutive ===")
prev = None
for t, txt in rows:
    if t < 142 or t > 546:
        continue
    key = txt[:70]
    if key == prev:
        continue
    prev = key
    print(f"{t:8.1f}s  {txt[:118]}")
