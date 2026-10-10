import csv
rows=list(csv.reader(open(r"C:\Wan2GP\benchmarks\ab-sage3\counters.csv",encoding="utf-8",errors="replace")))
hdr=[h.strip('"') for h in rows[0]]
data=[r for r in rows[1:] if len(r)==len(hdr)]
def col(name):
    i=[j for j,h in enumerate(hdr) if name in h][0]
    return [float(r[i]) for r in data if r[i] not in ("","-")]
print("Available MBytes   : avg=%.0f  min=%.0f  max=%.0f" % (sum(col('Available MBytes'))/len(col('Available MBytes')), min(col('Available MBytes')), max(col('Available MBytes'))))
print("Pages Input/sec    : avg=%.0f  max=%.0f   <-- hard faults (paging FROM disk)" % (sum(col('Pages Input'))/len(col('Pages Input')), max(col('Pages Input'))))
print("Disk Read Bytes/sec: avg=%.0f MB/s  max=%.0f MB/s" % (sum(col('Disk Read Bytes'))/len(col('Disk Read Bytes'))/1048576, max(col('Disk Read Bytes'))/1048576))
print("Paging File %% Usage: avg=%.1f  max=%.1f" % (sum(col('Usage'))/len(col('Usage')), max(col('Usage'))))
