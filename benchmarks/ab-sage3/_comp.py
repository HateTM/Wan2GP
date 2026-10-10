import glob, os
groups = {"трансформер REDGraft (int8)": 0, "transformer (int8)": 0, "текстовый энкодер": 0, "VAE/vocoder": 0, "соединители/проекции": 0}
files = glob.glob(r"C:\Wan2GP-Models\ckpts\*ltx-2.5*.safetensors")
tf, te, vae, conn = 0, 0, 0, 0
for f in files:
    n = os.path.basename(f).lower(); sz = os.path.getsize(f)
    if "redgraft" in n: tf += sz
    elif "distilled_diffusion" in n: tf += sz
    elif "text_encoder" in n or "gemma" in n: te += sz
    elif "vae" in n or "vocoder" in n: vae += sz
    elif "connector" in n or "projection" in n: conn += sz
print("  трансформер (REDGraft + distilled) : %6.2f GB" % (tf/1024**3))
print("  текстовые энкодеры                 : %6.2f GB" % (te/1024**3))
print("  VAE / vocoder                      : %6.2f GB" % (vae/1024**3))
print("  соединители / проекции             : %6.2f GB" % (conn/1024**3))
print()
print("  один прогон (REDGraft) = трансформер + текст.энкодер + VAE/конн.")
