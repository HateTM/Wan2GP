import sqlite3
db = r"C:\Wan2GP\benchmarks\ab-sage3\nsys_ltx41.sqlite"
con = sqlite3.connect(db)
cur = con.cursor()
# overall trace time range
cur.execute("SELECT MIN(start), MAX(end) FROM CUPTI_ACTIVITY_KIND_KERNEL")
k = cur.fetchone()
print("kernel activity span : %.2f .. %.2f s  (%.2f s)" % (k[0]/1e9, k[1]/1e9, (k[1]-k[0])/1e9))
try:
    cur.execute("SELECT MIN(start), MAX(end) FROM CUPTI_ACTIVITY_KIND_MEMCPY")
    m = cur.fetchone()
    print("memcpy activity span : %.2f .. %.2f s  (%.2f s)" % (m[0]/1e9, m[1]/1e9, (m[1]-m[0])/1e9))
except Exception as e:
    print("memcpy query:", e)
# overlap: count memcpy bytes per 1-second bucket alongside kernel time
cur.execute("""
 SELECT CAST(start/1000000000 AS INTEGER) AS sec,
        SUM(end-start) AS kern_ns, COUNT(*) AS n
 FROM CUPTI_ACTIVITY_KIND_KERNEL GROUP BY sec ORDER BY sec
""")
buckets = cur.fetchall()
print("\nper-second kernel busy time (first 25 s of activity):")
for sec, kern, n in buckets[:25]:
    print(f"  t={sec:4d}s kernel_busy={kern/1e9:6.3f}s  ({n} launches)")
con.close()
