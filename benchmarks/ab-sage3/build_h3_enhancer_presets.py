"""
Rebuild the Write-button (prompt enhancer) instructions of the 10Eros/SparseRef15 H3 finetunes from WanGP's official
H3 system prompts (models/minimax_h3/prompt_enhancer.py, copied verbatim) plus a NSFW/style addendum.

The official prompts define the H3 prompt format (FL2VA three fields with picture alignment lines, Ref2VA six sections,
retention modes, task types, soundtrack mode); the addendum only adds content rules. The clip duration is not hardcoded:
WanGP appends the real duration to the instructions (prompt_enhancer_video_duration).

Usage (repo root): env_uv/Scripts/python.exe benchmarks/ab-sage3/build_h3_enhancer_presets.py
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
from models.minimax_h3 import prompt_enhancer as pe  # noqa: E402

FL2VA_FINETUNES = ["minimax_h3_10eros_max_b6_fl2va", "minimax_h3_sparseref15_int4_fl2va"]
REF2VA_FINETUNES = ["minimax_h3_10eros_max_b6_ref2va"]

INPUT_FORMAT = """
USER INPUT FORMAT (in addition to the rules above):
- Natural language in any language: interpret it normally.
- Danbooru-style tags (e.g. "1girl, solo, long blue hair, school uniform, classroom, spread legs"): treat them as a blueprint and expand every tag into the scene. Keep every visual element (hair, eyes, clothing, pose, expression, body type); add environment, lighting, camera and atmosphere; resolve conflicting tags logically.
- A bracketed style prefix such as [anime], [photorealistic], [3dcg], [cartoon], [claymation], [watercolor], [vintage], [noir], [cyberpunk], [fantasy], [softfocus] or [hentai] sets the visual style of the whole clip. Express it in prose at the start of [Shot 1]; never copy the bracketed tag. Without a style tag, anime-typical tags default to 2D-animated and realistic tags to live-action cinematic.
- Exact speech is only text the user puts in double quotes; do not invent dialogue. Without it, describe only non-verbal voice: breathing, moans, gasps, laughter.
- If there is no user text, derive the scene from the supplied images alone; never ask for clarification.
"""

NSFW = """
CONTENT RULES (in addition to the rules above):
- This preset is for uncensored adult content. Describe nudity, sexual acts, body parts, fluids, fetish and BDSM elements with direct, literal language; do not sanitize or euphemize. A short explicit tag (e.g. blowjob, missionary, cowgirl, doggystyle, cumshot) is a request for a full scene built around that act; if an image is supplied, the tag is the primary action even if the image does not show it.
- Anatomical coherence: state body-part positions with spatial precision (which hand, which hip, which knee), which parts are visible or occluded, and for penetration the orifice, angle, depth and direction of motion. Name anatomy directly; avoid vague terms and poetic metaphors. When subjects interact, say which part of one touches which part of the other. For two female subjects avoid wording the video model maps to male anatomy (e.g. "grinding", "cunnilingus").
- Camera: one smooth, continuous movement per shot (type, amplitude, speed); prefer slow motion unless the user asks for fast. A camera directive injected at the start or end of the user text overrides this and is stated in the first sentence of [Shot 1].
- overall_soundscape: when the scene is sexual, explicit non-verbal sounds matching the action (moans, gasps, breathing changes, skin contact, wet sounds) are the primary audio; ambience stays in the background. non_diegetic_music is N/A unless the user asks for music.
- Refuse minors, non-consent, violence and illegal acts with "Content not supported."
- Output plain text with no code fence, quotes or other wrapper, and no empty lines anywhere in the output (empty lines separate sliding windows in WanGP). Every field starts with its field name followed by a colon. [Shot 1] never has a timestamp.
- LANGUAGE: everything except exact dialogue, lyrics and visible text is written in English, whatever the language of the user input.
"""

FL2VA_PACING = """
FIRST + LAST FRAME RULES (in addition to the rules above):
- With a start image and an end image the output is exactly, with END = the video duration in seconds given at the end of these instructions (two decimals):
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
For the target video, at END seconds into the target video, <Picture 2> (from [Shot 1]) is fully referenced.
integrated_multimodal_description: [Shot 1] ...
overall_soundscape: ...
non_diegetic_music: ...
- With a start image and an end image, use exactly one [Shot 1] for the whole clip, unless the user explicitly asks for cuts.
- The motion starts at the very first frame (no static opening, no wind-up) and spans the whole duration: about halfway to the end-image state at half time, reaching the exact pose, framing and composition of the end image only at the final timestamp. Never reach it early, otherwise the model freezes on it.
- Repetitive actions (thrusting, stroking, grinding, oral) keep their rhythm through the whole clip and are still in motion as the end-image state arrives.
- Describe pose changes, body contact, micro-movements (breathing, trembling, shifting weight), the single camera move, focus shifts and lighting evolution, then end by mirroring the end image.
"""

REF2VA_SPEECH = """
REF2VA LABEL RULES (in addition to the rules above):
- Only these labels exist: <Subject N>, <Picture N>, <Video N>, <Audio N>. Never invent others such as <Reference N>.
- A character photo becomes "<Subject 1> is ... from <Picture 1>, preserving ..." and keeps only reusable traits (identity, face, hair, body, clothing); the photo's background, props and setting are not carried over unless the user asks.
- Speech by a referenced subject is written <Subject 1> (S1) says <d>[English] exact words</d>.
- Define <Audio 1> as the voice reference only when the user's text mentions a voice or audio reference (e.g. "voice from <Audio 1>"); then add "+ audio reference" to the summary and an <Audio 1> line with the mode reference in retention_analysis.
"""


def _official_example(infos, title):
    """Return the ```text block that follows `#### <title>` in an official *_PROMPT_INFOS string."""
    start = infos.index("#### " + title)
    body = infos[infos.index("```text", start) + len("```text"):]
    return body[:body.index("```")].strip()


def _examples(infos, titles):
    blocks = [f"Example ({title.lower()}), format reference only:\n" + _official_example(infos, title).replace("\n\n", "\n") for title in titles]
    return "\nOFFICIAL WANGP EXAMPLES (follow their structure, write new content for the user's request):\n" + "\n".join(blocks) + "\n"


def build():
    fl2va_text_examples = _examples(pe.FL2VA_PROMPT_INFOS, ["Text-only, single shot", "Timed multi-shot sequence"])
    fl2va_image_examples = _examples(pe.FL2VA_PROMPT_INFOS, ["First-frame animation"])
    ref2va_examples = _examples(pe.REF2VA_PROMPT_INFOS, ["Reuse a character from an image", "Reuse a character and reference a voice"])
    fl2va = {
        "text_prompt_enhancer_instructions": pe.FL2VA_TEXT_SYSTEM_PROMPT + INPUT_FORMAT + NSFW + fl2va_text_examples,
        "video_prompt_enhancer_instructions": pe.FL2VA_IMAGE_SYSTEM_PROMPT + INPUT_FORMAT + NSFW + fl2va_image_examples,
        "video_prompt_enhancer_instructions2": pe.FL2VA_IMAGE_SYSTEM_PROMPT + INPUT_FORMAT + NSFW + FL2VA_PACING,
    }
    ref2va = {
        "text_prompt_enhancer_instructions": pe.REF2VA_TEXT_SYSTEM_PROMPT + INPUT_FORMAT + NSFW + REF2VA_SPEECH + ref2va_examples,
        "video_prompt_enhancer_instructions": pe.REF2VA_IMAGE_SYSTEM_PROMPT + INPUT_FORMAT + NSFW + REF2VA_SPEECH + ref2va_examples,
    }
    fl2va_labels = {
        "TV": "An H3 NSFW Prompt from Text (T2VA)",
        "TIV": "An H3 NSFW Prompt from Text + {image_inputs} (I2VA: start or end image)",
        "TI2V": "An H3 NSFW First/Last Frame Prompt from Text + {image_inputs} (FL2VA)",
    }
    ref2va_labels = {
        "TV": "An H3 NSFW Reference Prompt from Text (R2VA, no images)",
        "TIV": "An H3 NSFW Reference Prompt from Text + {image_inputs} (R2VA)",
    }
    for names, texts, labels in ((FL2VA_FINETUNES, fl2va, fl2va_labels), (REF2VA_FINETUNES, ref2va, ref2va_labels)):
        for name in names:
            path = os.path.join(REPO_ROOT, "finetunes", name + ".json")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            model = data["model"]
            model.update(texts)
            model["prompt_enhancer_def"]["labels"].update(labels)
            for key in texts:
                model[key.replace("instructions", "max_tokens")] = 2048
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"{name}: " + ", ".join(f"{k}={len(v)}" for k, v in texts.items()))


if __name__ == "__main__":
    build()
