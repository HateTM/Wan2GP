import sqlite3
con = sqlite3.connect(r"C:\Wan2GP\benchmarks\ab-sage3\nsys_ltx41.sqlite")
cur = con.cursor()

def spans(table, cols="start,end"):
    cur.execute(f"SELECT start, end FROM {table} WHERE end > start")
    return cur.fetchall()

try:
    ker = spans("CUPTI_ACTIVITY_KIND_KERNEL")
    mem = spans("CUPTI_ACTIVITY_KIND_MEMCPY")
except Exception as e:
    print("table names differ:", e); raise SystemExit

def union_len(rows):
    rows = sorted(rows)
    total = 0; cs, ce = rows[0]
    for s, e in rows[1:]:
        if s <= ce: ce = max(ce, e)
        else: total += ce - cs; cs, ce = s, e
    total += ce - cs
    return total

def inter_len(a, b):
    a = sorted(a); b = sorted(b)
    total = 0; i = j = 0
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0]); e = min(a[i][1], b[j][1])
        if s < e: total += e - s
        if a[i][1] < b[j][1]: i += 1
        else: j += 1
    return total

ku = union_len(ker); mu = union_len(mem)
ov = inter_len(ker, mem)
union_all = union_len(ker + mem)
print(f"kernel busy (union, non-overlapping) : {ku/1e9:7.2f} s")
print(f"memcpy busy (union)                  : {mu/1e9:7.2f} s")
print(f"overlap kernel AND memcpy            : {ov/1e9:7.2f} s  ({ov/max(ku,1)*100:5.1f}% of kernel time)")
print(f"GPU busy with ANY work (union of both): {union_all/1e9:7.2f} s")
print()
span = max(max(e for _, e in ker), max(e for _, e in mem)) - min(min(s for s, _ in ker), min(s for s, _ in mem))
print(f"profile span                          : {span/1e9:7.2f} s")
print(f"=> GPU occupied with something        : {union_all/span*100:5.1f}% of span")
print(f"=> GPU fully idle                     : {(span-union_all)/span*100:5.1f}% of span")
con.close()
