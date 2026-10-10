import csv
kern=[]; 
with open(r"C:\Wan2GP\benchmarks\ab-sage3\nsys_stats_cuda_gpu_sum.csv", encoding="utf-8", errors="replace") as f:
    for r in csv.DictReader(f):
        try: kern.append((r["Category"], r["Operation"][:40], float(r["Total Time (ns)"]), int(r["Instances"])))
        except: pass
# bytes: separate
k = [x for x in kern if x[0]=="CUDA_KERNEL"]
m = [x for x in kern if x[0]!="CUDA_KERNEL"]
kt = sum(x[2] for x in k); mt = sum(x[2] for x in m)
print(f"kernels      : {kt/1e9:6.2f} s  ({sum(x[3] for x in k)} calls)")
for c,o,t,i in sorted(m, key=lambda x:-x[2]):
    print(f"{c:12s} : {t/1e9:6.2f} s  ({i} calls)  {o}")
tot = kt+mt
print(f"GPU activity : {tot/1e9:6.2f} s total")
print()
print(f"H2D share of GPU activity : {[t for c,o,t,i in m if 'Host-to-Device' in o][0]/tot*100:.1f}%")
print(f"dequant kernel share      : {[t for c,o,t,i in k if 'decode_w4a8' in o][0]/tot*100:.1f}%")
