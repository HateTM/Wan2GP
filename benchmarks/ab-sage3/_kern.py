import csv
p = r"C:\Wan2GP\benchmarks\ab-sage3\nsys_stats_cuda_gpu_kern_sum.csv"
rows=[]
with open(p, encoding="utf-8", errors="replace") as f:
    for r in csv.DictReader(f):
        rows.append(r)
rows.sort(key=lambda r: -float(r["Total Time (ns)"]))
total=sum(float(r["Total Time (ns)"]) for r in rows)
print(f"{'%':>6} {'total_s':>9} {'instances':>10}  kernel")
for r in rows[:12]:
    name=r["Name"]
    short=name.split("cutlass::")[0][:70] if "cutlass" in name else name[:70]
    if "cutlass" in name: short="cutlass gemm (int8/bf16) ..."
    print(f"{float(r['Time (%)']):6.1f} {float(r['Total Time (ns)'])/1e9:9.2f} {int(r['Instances']):10d}  {short}")
print(f"{'======':>6}")
print(f"100.0 {total/1e9:9.2f}  SUM of all kernels")
