import csv
def load(p):
    rows=list(csv.reader(open(p,encoding="utf-8",errors="replace")))
    hdr=[h.strip('"') for h in rows[0]]
    return hdr,[r for r in rows[1:] if len(r)==len(hdr)]

for label,path,task_start in (("H3-10Eros", r"C:\Wan2GP\benchmarks\ab-sage3\counters_h3.csv", 28.7),
                              ("LTX-2.5",   r"C:\Wan2GP\benchmarks\ab-sage3\counters.csv", 38.4)):
    hdr,data = load(path)
    i_d=[j for j,h in enumerate(hdr) if "Disk Read Bytes" in h][0]
    i_a=[j for j,h in enumerate(hdr) if "Available MBytes" in h][0]
    iv=[]
    for k,r in enumerate(data):
        try: iv.append((k*2, float(r[i_d])/1048576, float(r[i_a])))
        except ValueError: pass
    # момент окончания "тяжёлого" чтения = конец загрузки
    heavy=[t for t,d,a in iv if d>50]
    low_after=[t for t,d,a in iv if d<=50]
    print(f"=== {label} ===")
    print(f"  активное чтение с диска: с {min(heavy)} по {max(heavy)} s")
    idle = [t for t in low_after if t>max(heavy)]
    print(f"  после последнего чтения: с {min(idle)} s до конца ({max(low_after)} s) — рабочая фаза")
    print(f"  RAM free min: {min(a for _,_,a in iv):.0f} MB")
    print()
