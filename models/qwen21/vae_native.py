"""State-dict converter for native-layout Qwen Image 2.1 VAE checkpoints.

The official Qwen/Qwen-Image-2.1 VAE (shipped as `qwen_image_21_vae.safetensors`)
already matches the `AutoencoderKLQwenImage21` module naming. Community
checkpoints of the same architecture - e.g. the RedCraft vendor texture-fix VAE
(`qwen_image_21_vae_texturefix_bf16.safetensors`) - carry the very same 238
tensors under the original Wan-style module names (`conv1` / `conv2` /
`encoder.conv1` / `*.middle` / `*.downsamples` / `*.upsamples` / `*.head` /
`residual.*` / `shortcut.*`), with 3D-conv weights that hold a single temporal
kernel position (`[out, in, 1, k, k]`) and 4D RMSNorm `gamma`. This converter
renames the tensors into the class layout and drops the degenerate temporal
axis / ones dimensions. Values and dtypes are never touched.

Structure correspondence (native -> AutoencoderKLQwenImage21):
    conv1.*                             -> quant_conv.*
    conv2.*                             -> post_quant_conv.*
    <branch>.conv1.*                    -> <branch>.conv_in.*
    <branch>.head.0.gamma               -> <branch>.norm_out.gamma
    <branch>.head.2.{weight,bias}       -> <branch>.conv_out.{weight,bias}
    <branch>.middle.{0|2}.residual.*    -> <branch>.mid_block.resnets.{0|1}.*
    <branch>.middle.1.{norm,proj,to_qkv}.* -> <branch>.mid_block.attentions.0.*
    encoder.downsamples.<b>.downsamples.{0,1}.residual.* -> encoder.down_blocks.<b>.resnets.{0,1}.*
    encoder.downsamples.<b>.downsamples.2.{resample,time_conv}.* -> encoder.down_blocks.<b>.downsampler.*
    decoder.upsamples.<b>.upsamples.{0,1,2}.residual.*  -> decoder.up_blocks.<b>.resnets.{0,1,2}.*
    decoder.upsamples.<b>.upsamples.3.{resample,time_conv}.* -> decoder.up_blocks.<b>.upsampler.*
    residual.{0,3}.gamma                -> norm{1,2}.gamma
    residual.{2,6}.{weight,bias}        -> conv{1,2}.{weight,bias}
    shortcut.*                          -> conv_shortcut.*
"""

RESIDUAL_IDX = {"0": "norm1", "2": "conv1", "3": "norm2", "6": "conv2"}


def is_native_layout(filename):
    """True for checkpoint-native (Wan-style) Qwen Image 2.1 VAE tensors
    (e.g. the RedCraft texture-fix VAE), False for the converted official file."""
    import os
    if not os.path.isfile(filename):
        return False
    from safetensors import safe_open
    with safe_open(filename, framework="pt", device="cpu") as f:
        return any(key.startswith("conv1.") or (".downsamples." in key and ".residual." in key)
                   for key in f.keys())


def _residual_parts(parts, start):
    """Map `residual.<idx>.<param>` starting at `index start` inside `parts`.
    Returns the <module name>.<param> pair or None."""
    if len(parts) - start >= 3 and parts[start] == "residual" and parts[start + 1] in RESIDUAL_IDX:
        return f"{RESIDUAL_IDX[parts[start + 1]]}.{parts[start + 2]}"
    return None


def _rename(key):
    parts = key.split(".")
    head = parts[0]
    branch = None
    if head in ("encoder", "decoder"):
        branch, rest = head, parts[1:]
    elif head in ("conv1", "conv2"):
        top = "quant_conv" if head == "conv1" else "post_quant_conv"
        return f"{top}.{parts[1]}"  # .weight or .bias
    else:
        return None

    module, tail = rest[0], rest[1:]

    if module == "conv1":
        return f"{branch}.conv_in.{tail[0]}"

    if module == "head":
        if tail[0] == "0" and tail[1] == "gamma":
            return f"{branch}.norm_out.gamma"
        if tail[0] == "2" and tail[1] in ("weight", "bias"):
            return f"{branch}.conv_out.{tail[1]}"
        return None

    mapped = _residual_parts((module,) + tuple(tail), 0)
    if mapped is not None:
        return f"{branch}.{mapped}"

    if module == "middle":
        # middle.{0|2}.residual.<idx>.<param> | middle.1.{norm,proj,to_qkv}.<param>
        block = tail[0]
        if block in ("0", "2"):
            mapped = _residual_parts(tail, 1)
            if mapped is not None:
                res = "0" if block == "0" else "1"
                return f"{branch}.mid_block.resnets.{res}.{mapped}"
        if block == "1" and len(tail) == 3 and tail[1] in ("norm", "proj", "to_qkv"):
            return f"{branch}.mid_block.attentions.0.{tail[1]}.{tail[2]}"
        return None

    if module in ("downsamples", "upsamples"):
        # native nesting: <branch>.{downsamples|upsamples}.<b>.{downsamples|upsamples}.<j>.<rest...>
        resample_kind = "downsampler" if module == "downsamples" else "upsampler"
        if len(tail) < 5 or tail[1] != module:
            return None
        b = tail[0]
        if not tail[2].isdigit():
            return None
        j = int(tail[2])
        inner = tail[3:]
        if resample_kind == "downsampler":
            if j in (0, 1):
                mapped = _residual_parts(inner, 0)
                if mapped is not None:
                    return f"{branch}.down_blocks.{b}.resnets.{j}.{mapped}"
                if len(inner) == 2 and inner[0] == "shortcut":
                    return f"{branch}.down_blocks.{b}.resnets.{j}.conv_shortcut.{inner[1]}"
                return None
            # j == 2: resample / time_conv of the downsampler module
            return f"{branch}.down_blocks.{b}.downsampler." + ".".join(inner)
        # decoder up blocks: sub-list indices 0/1/2 are resnets, 3 is the upsampler
        if j in (0, 1, 2):
            mapped = _residual_parts(inner, 0) if inner else None
            if mapped is not None:
                return f"{branch}.up_blocks.{b}.resnets.{j}.{mapped}"
            if len(inner) == 2 and inner[0] == "shortcut":
                return f"{branch}.up_blocks.{b}.resnets.{j}.conv_shortcut.{inner[1]}"
            return None
        if j == 3:
            return f"{branch}.up_blocks.{b}.upsampler." + ".".join(inner)
        return None

    return None


def convert_native_qwen21_vae_state_dict(sd):
    """Rename a native-layout Qwen Image 2.1 VAE checkpoint into the
    AutoencoderKLQwenImage21 layout. Returns a new dict; the input is untouched."""
    out = {}
    for key, tensor in sd.items():
        new_key = _rename(key)
        if new_key is None:
            raise KeyError(f"unmapped native Qwen 2.1 VAE tensor: {key}")
        if tensor.dim() == 5:
            if tensor.shape[2] != 1:
                raise ValueError(f"unexpected temporal kernel on {key}: {tuple(tensor.shape)}")
            tensor = tensor.squeeze(2)
        out[new_key] = tensor
    return out
