import re
log = r"C:\Wan2GP\.zwork\background\2026-10-09T16-18-18-822Z-2dthva.log"
lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
ts = re.compile(r"^\[ *(\d+\.\d+)s\] *(.*)$")
rows = []
for ln in lines:
    m = ts.match(ln)
    if m:
        rows.append((float(m.group(1)), m.group(2)))
# task boundaries
for t, txt in rows:
    if "TASK" in txt or "upsampling complete" in txt or "Queue completed" in txt:
        print(f"{t:8.1f}s  {txt[:110]}")
print()
# loading phases of the upsampler (they all say "Loading - ")
load = [t for t, txt in rows if txt.startswith("Loading - ")]
if load:
    print(f"upsampler model load: {load[0]:.1f}s .. {load[-1]:.1f}s = {load[-1]-load[0]:.1f}s")
w1 = [t for t, txt in rows if "Window 1 / 2" in txt]
w2 = [t for t, txt in rows if "Window 2 / 2" in txt]
if w1: print(f"Window 1 phases: {w1[0]:.1f}s .. {w1[-1]:.1f}s")
if w2: print(f"Window 2 phases: {w2[0]:.1f}s .. {w2[-1]:.1f}s")
