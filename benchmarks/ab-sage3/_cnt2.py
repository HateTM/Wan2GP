import csv
rows=list(csv.reader(open(r"C:\Wan2GP\benchmarks\ab-sage3\counters.csv",encoding="utf-8",errors="replace")))
hdr=[h.strip('"') for h in rows[0]]
data=[r for r in rows[1:] if len(r)==len(hdr)]
def vals(name):
    i=[j for j,h in enumerate(hdr) if name in h][0]
    out=[]
    for r in data:
        s=r[i].strip().strip('"')
        try: out.append(float(s))
        except ValueError: pass
    return out
for name, scale, unit in (
    ("Available MBytes", 1, "MB"),
    ("Pages Input", 1, "pages/s"),
    ("Disk Read Bytes", 1/1048576, "MB/s"),
    ("Disk Reads/sec", 1, "/s"),
    ("Usage", 1, "%"),
):
    v = vals(name)
    if not v: continue
    print("%-18s avg=%10.1f  min=%10.1f  max=%10.1f  %s" % (name, sum(v)/len(v)*scale, min(v)*scale, max(v)*scale, unit))
