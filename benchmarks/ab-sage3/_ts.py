import csv, os
for label, path in (("LTX-2.5", r"C:\Wan2GP\benchmarks\ab-sage3\counters_ltx.csv"),
                    ("H3-10Eros", r"C:\Wan2GP\benchmarks\ab-sage3\counters_h3.csv")):
    if not os.path.exists(path):
        print("--- %s: нет файла (LTX-счётчики были в counters.csv)" % label)
        alt = r"C:\Wan2GP\benchmarks\ab-sage3\counters.csv"
        if label == "LTX-2.5" and os.path.exists(alt):
            path = alt
        else:
            continue
    rows = list(csv.reader(open(path, encoding="utf-8", errors="replace")))
    hdr = [h.strip('"') for h in rows[0]]
    data = [r for r in rows[1:] if len(r) == len(hdr)]
    i_disk = [j for j, h in enumerate(hdr) if "Disk Read Bytes" in h][0]
    i_pg = [j for j, h in enumerate(hdr) if "Pages Input" in h][0]
    print("=== %s : чтение по времени (2 с/сэмпл) ===" % label)
    print("  t(s)   disk(MB/s)   hard_faults/s")
    for k, r in enumerate(data):
        try:
            d = float(r[i_disk]) / 1048576
            p = float(r[i_pg])
        except ValueError:
            continue
        print("  %4d   %9.1f   %12.0f" % (k * 2, d, p))
    print()
