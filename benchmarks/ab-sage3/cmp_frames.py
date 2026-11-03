from PIL import Image
import numpy as np
a = Image.open(r"C:\Wan2GP\benchmarks\ab-sage3\frames\frame_sage2.png").convert("RGB")
b = Image.open(r"C:\Wan2GP\benchmarks\ab-sage3\frames\frame_sage3.png").convert("RGB")
print("sizes:", a.size, b.size)
if a.size != b.size: b = b.resize(a.size)
A = np.asarray(a).astype(np.float64); B = np.asarray(b).astype(np.float64)
mse = ((A-B)**2).mean()
psnr = 10*np.log10(255.0**2/mse) if mse > 0 else float("inf")
print(f"MSE={mse:.2f}  MAE={np.abs(A-B).mean():.2f}  PSNR={psnr:.2f} dB")
print(f"max abs diff={np.abs(A-B).max():.0f}")
print(f"pixels with >16 diff: {(np.abs(A-B).max(axis=2)>16).mean()*100:.2f}%")
