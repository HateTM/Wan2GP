import os
def gb(p):
    return os.path.getsize(p)/1024**3 if os.path.exists(p) else 0
C = r"C:\Wan2GP-Models\ckpts"
stack = {
    "трансформер REDGraft (int8)": "ltx-2.5-22b-redgraft-sulphur2_int8_convrot.safetensors",
    "текстовый энкодер gemma4-12b (int8)": "gemma4-12b-ltx-v1_int8_convrot.safetensors",
    "video VAE": "ltx-2.5-22b_video_vae_bf16.safetensors",
    "audio VAE": "ltx-2.5-audio-vae-bf16.safetensors",
    "vocoder": "ltx-2.5-22b_vocoder_bf16.safetensors",
    "video embeddings connector (int8)": "ltx-2.5-22b_video_embeddings_connector_int8_convrot.safetensors",
    "audio embeddings connector (int8)": "ltx-2.5-22b_audio_embeddings_connector_int8_convrot.safetensors",
    "text embedding projection": "ltx-2.5-22b_text_embedding_projection_bf16.safetensors",
}
tot = 0
print(f"{'компонент':42s} {'GB':>7s}")
print("-"*52)
for label, fn in stack.items():
    p = os.path.join(C, fn)
    v = gb(p); tot += v
    print(f"{label:42s} {v:7.2f}" + ("" if os.path.exists(p) else "   <-- НЕТ"))
print("-"*52)
print(f"{'ИТОГО рабочий набор':42s} {tot:7.2f}")
print()
print(f"  RAM в системе           : 31.40 GB")
print(f"  дефицит только на веса  : {tot-31.4:+.2f} GB")
print()
print("  плюс буферы стриминга, pagefile, ОС, браузер -> и есть тот самый 1 MB free")
