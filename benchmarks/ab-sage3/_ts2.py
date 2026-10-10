import csv
rows = list(csv.reader(open(r"C:\Wan2GP\benchmarks\ab-sage3\counters_h3.csv", encoding="utf-8", errors="replace")))
hdr = [h.strip('"') for h in rows[0]]
data = [r for r in rows[1:] if len(r) == len(hdr)]
i_disk = [j for j, h in enumerate(hdr) if "Disk Read Bytes" in h][0]
i_pg = [j for j, h in enumerate(hdr) if "Pages Input" in h][0]
i_av = [j for j, h in enumerate(hdr) if "Available MBytes" in h][0]
print("=== H3-10Eros: чтение по времени (генерация ~91..153 s) ===")
print("  t(s)   disk(MB/s)   hard_faults/s   free_RAM(MB)")
busy = 0
for k, r in enumerate(data):
    try:
        d = float(r[i_disk]) / 1048576; p = float(r[i_pg]); a = float(r[i_av])
    except ValueError:
        continue
    if d > 50: busy += 1
    flag = "  <-- читает с диска" if d > 50 else ""
    print("  %4d   %9.1f   %12.0f   %10.0f%s" % (k*2, d, p, a, flag))
print()
print("сэмплов с чтением >50 MB/s: %d из %d" % (busy, len(data)))
