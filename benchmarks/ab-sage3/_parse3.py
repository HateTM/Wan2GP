import re
p = r"C:\Wan2GP\benchmarks\ab-sage3\raw_timeline.log"
rows = []
ts = re.compile(r"^\[\s*(\d+\.\d+)\] (.*)$")
for ln in open(p, encoding="utf-8", errors="replace"):
    m = ts.match(ln.rstrip())
    if m: rows.append((float(m.group(1)), m.group(2)))

print("total lines:", len(rows))
print()
print("=== TASK 2 window: 124s..382s, first/last lines and big gaps ===")
task2 = [(t,x) for t,x in rows if 124 <= t <= 383]
prev_t = None
for t, x in task2:
    gap = (t - prev_t) if prev_t is not None else 0
    if prev_t is None or gap >= 5.0:
        print(f"  GAP {gap:6.1f}s -> {t:7.1f}s  {x[:100]}")
    prev_t = t
print()
print("=== phase-ish lines in task2 (denoising/VAE/upsampl/Window) ===")
seen=set()
for t,x in task2:
    if any(k in x for k in ("Denoising","VAE dec","VAE Dec","upsampl","Upsampl","Window","distilled","Distilled","Saving","saved","Preparing","Loading - Finalization Transformer")):
        k=x[:60]
        key=(k,)
        if key in seen: continue
        seen.add(key)
        print(f"  {t:7.1f}s  {x[:110]}")
