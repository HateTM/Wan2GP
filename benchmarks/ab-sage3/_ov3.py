import sqlite3
con = sqlite3.connect(r"C:\Wan2GP\benchmarks\ab-sage3\nsys_ltx41.sqlite")
cur = con.cursor()
cur.execute("SELECT start, end FROM CUPTI_ACTIVITY_KIND_KERNEL WHERE end>start")
ker = cur.fetchall()
cur.execute("SELECT start, end FROM CUPTI_ACTIVITY_KIND_MEMCPY WHERE end>start")
mem = cur.fetchall()

# generation window = from the first second with dense kernels (denoising) to the end
import collections
per_sec = collections.Counter()
for s, e in ker:
    per_sec[int(s/1e9)] += (e-s)
dense_start = min(sec for sec, ns in per_sec.items() if ns > 0.05e9)
end = max(e for _, e in ker + mem)
print(f"dense (generation) window: {dense_start}s .. {end/1e9:.1f}s = {end/1e9-dense_start:.1f}s")

gw_ker = [(s, e) for s, e in ker if e > dense_start*1e9]
gw_mem = [(s, e) for s, e in mem if e > dense_start*1e9]

def union(rows):
    rows = sorted(rows); tot = 0; cs, ce = rows[0]
    for s, e in rows[1:]:
        if s <= ce: ce = max(ce, e)
        else: tot += ce-cs; cs, ce = s, e
    return tot + ce - cs

ku, mu = union(gw_ker), union(gw_mem)
allu = union(gw_ker + gw_mem)
span = end - dense_start*1e9
print(f"  kernel busy : {ku/1e9:6.2f} s")
print(f"  memcpy busy : {mu/1e9:6.2f} s")
print(f"  any activity: {allu/1e9:6.2f} s  => {allu/span*100:5.1f}% of generation window")
print(f"  GPU idle    : {(span-allu)/1e9:6.2f} s  => {(span-allu)/span*100:5.1f}%")
con.close()
