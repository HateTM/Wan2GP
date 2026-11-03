import csv
rows=[]
with open(r"C:\Wan2GP\benchmarks\ab-sage3\nsys_stats_cuda_gpu_kern_sum.csv", encoding="utf-8", errors="replace") as f:
    for r in csv.DictReader(f):
        rows.append((r["Name"], float(r["Total Time (ns)"]), int(r["Instances"])))
kern_total = sum(t for _,t,_ in rows)
GPU_ACTIVITY = 27.42e9

attn = [r for r in rows if "attn" in r[0].lower() or "attention" in r[0].lower()]
attn_t = sum(t for _,t,_ in attn)
print(f"total kernel time      : {kern_total/1e9:6.2f} s over {sum(i for _,_,i in rows):,} launches")
print(f"attention kernels      : {attn_t/1e9:6.2f} s  = {attn_t/kern_total*100:4.1f}% of kernels, {attn_t/GPU_ACTIVITY*100:4.1f}% of GPU activity")
print(f"  ({len(attn)} distinct attention kernels, {sum(i for _,_,i in attn):,} launches)")
print()
groups = {
 "attention":      [r for r in rows if "attn" in r[0].lower()],
 "dequant (w4a8)": [r for r in rows if "decode_w4a8" in r[0]],
 "int8 gemm":      [r for r in rows if "scaled_int8_gemm" in r[0]],
 "cutlass gemm":   [r for r in rows if "cutlass" in r[0]],
 "cudnn conv":     [r for r in rows if "cudnn" in r[0]],
 "elementwise":    [r for r in rows if "elementwise" in r[0]],
}
print(f"{'group':16s} {'seconds':>8s} {'% kernels':>10s}")
print("-"*38)
for name, rs in sorted(groups.items(), key=lambda kv: -sum(t for _,t,_ in kv[1])):
    t = sum(x[1] for x in rs)
    print(f"{name:16s} {t/1e9:8.2f} {t/kern_total*100:9.1f}%")
other = kern_total - sum(sum(x[1] for x in rs) for rs in groups.values())
print(f"{'(other)':16s} {other/1e9:8.2f} {other/kern_total*100:9.1f}%")
print()
print(f"H2D weight transfers   : 11.00 s = {11.0e9/GPU_ACTIVITY*100:.1f}% of GPU activity")
print(f"dequant + H2D          : {(11.0e9+[t for n,t,i in rows if 'decode_w4a8' in n][0])/GPU_ACTIVITY*100:.1f}% of GPU activity")
