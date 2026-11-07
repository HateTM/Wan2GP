"""Prompt generation through the existing WanGP AI runtime (no new model process)."""
from __future__ import annotations

import json
import re


def mode_name(value: object) -> str:
    mode = str(value or "both").strip().lower()
    if mode not in {"image", "video", "both"}:
        raise ValueError("Prompt Engineer mode must be image, video or both.")
    return mode


def build_instruction(idea: object, mode: object = "both", has_reference: bool = False) -> str:
    mode = mode_name(mode)
    idea = str(idea or "").strip()
    if not idea and not has_reference:
        raise ValueError("Prompt Engineer needs an idea or a connected reference image.")
    if len(idea) > 12000:
        raise ValueError("Prompt Engineer idea is too long (maximum 12000 characters).")
    ref = (
        "Reference image(s) are attached: preserve identity and existing visible details; "
        "do not invent unseen reference details. "
        if has_reference else "No image reference: construct the scene from the idea. "
    )
    prefix = (
        "You are a Wan2GP visual prompt engineer. Write precise English prompts with natural "
        "anatomy, camera positioning, cinematic continuity and clear actions. "
        "Avoid contradictions, excessive adjectives and unsupported syntax. "
    )
    still = (
        "IMAGE: describe the final still composition for T2I/I2I: subject, body pose, "
        "framing, lens angle, setting, lighting and appearance. "
    )
    motion = (
        "VIDEO: describe action and temporal progression for T2V/I2V: subject movement, "
        "camera movement, gesture timing and continuity. With a reference image, "
        "describe motion from the initial frame instead of repeating its static description. "
    )
    if mode == "both":
        task = still + motion
        fmt = 'Return ONLY valid JSON with nonempty string fields "image_prompt" and "video_prompt"; no Markdown. '
    elif mode == "image":
        task, fmt = still, "Return ONLY the finished image prompt, plain text, no heading. "
    else:
        task, fmt = motion, "Return ONLY the finished video prompt, plain text, no heading. "
    return f"{prefix}{ref}{task}{fmt}\nUSER IDEA:\n{idea or 'Describe the attached reference accurately.'}"


def parse_response(answer: object, mode: object = "both") -> dict[str, str]:
    mode = mode_name(mode)
    text = str(answer or "").strip()
    if not text:
        raise ValueError("Prompt Engineer AI returned an empty response.")
    if mode != "both":
        return {"image_prompt" if mode == "image" else "video_prompt": text}
    cleaned = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", text, flags=re.IGNORECASE).strip()
    try:
        value = json.loads(cleaned)
    except (ValueError, TypeError):
        match = re.search(
            r"(?is)^\s*(?:IMAGE PROMPT|image_prompt)\s*:\s*(.+?)\s*(?:VIDEO PROMPT|video_prompt)\s*:\s*(.+?)\s*$",
            cleaned,
        )
        if match is None:
            raise ValueError("Prompt Engineer expected JSON image_prompt and video_prompt; retry or change AI model.") from None
        value = {"image_prompt": match.group(1), "video_prompt": match.group(2)}
    if not isinstance(value, dict):
        raise ValueError("Prompt Engineer expected an object with two fields.")
    result = {}
    for key in ("image_prompt", "video_prompt"):
        entry = value.get(key)
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"Prompt Engineer returned no {key}.")
        result[key] = entry.strip()
    return result
