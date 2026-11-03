import csv
rows=list(csv.reader(open(r"C:\Wan2GP\benchmarks\ab-sage3\counters_h3.csv",encoding="utf-8",errors="replace")))
hdr=[h.strip('"') for h in rows[0]]
data=[r for r in rows[1:] if len(r)==len(hdr)]
i_d=[j for j,h in enumerate(hdr) if "Disk Read Bytes" in h][0]
i_a=[j for j,h in enumerate(hdr) if "Available MBytes" in h][0]
iv=[]
for k,r in enumerate(data):
    try: iv.append((k*2, float(r[i_d])/1048576, float(r[i_a])))
    except ValueError: pass
heavy=[t for t,d,a in iv if d>50]
print("=== H3-10Eros, 41 кадр: разметка фаз по диску и RAM ===")
print("  старт задачи            : 28.7 s")
print("  загрузка модели (чтение): %d .. %d s  = ~%d s" % (min(heavy), max(heavy), max(heavy)-min(heavy)))
low=[t for t,d,a in iv if d<=50 and t>max(heavy)]
print("  вычисление (диск молчит): %d .. %d s  = ~%d s" % (min(low), max(low), max(low)-min(low)))
print("  RAM free min            : %.0f MB" % min(a for _,_,a in iv))
print()
print("  ИТОГО прогон ~177 s:  старт 29 + загрузка ~%d + вычисление ~%d + сохранение"
      % (max(heavy)-min(heavy), max(low)-min(low)))
