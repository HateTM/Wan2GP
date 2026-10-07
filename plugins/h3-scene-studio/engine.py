"""Prompt assembly engine for H3 Scene Studio.

Takes a flat settings dict (English option values, same keys as the original
HTML tool) and returns (prompt_text, recap_ru). English phrase tables come
from vocab.py; nothing here is translated - the model prompt stays English.

Simplifications vs the original JS engine (documented, deliberate):
- male2/female2 choreography is reduced to watch/assist lines;
- "forced" per-act rewrites and POOL-driven body-random rolls are not
  reimplemented; every menu still honors "any" by rolling its own pool.
"""

import random
import re

from .vocab import (
    PRESET, POS, DIST_NAME, DIST, ANGLE, POV, MOVE, SPEED, STAB, LENS, FOLLOW,
    HEIGHT, ANGLELOCK, MOVELOCK, ACTS, PHASES, STAGE_PHASE_MAP, STAGE_BRIDGES,
    MOOD_LINES, MOOD_LINES_DEFAULT, FACE_LINES, FACE_ORAL_LINES, LOOK_LINES,
    MAN_HAND_LINES, EXP_LINES, RELATE_LINES, FORMAT, STYLE, CLOTHES, CLOTH_MESS,
    MAN_CLOTHES, PLACE, PLACE_LIGHT, AUDIO_STAGE, ARTIFACT_LOCK_LIGHT,
    ARTIFACT_LOCK_FULL_SUFFIX, MAN_JOIN_LINE, FORCE_REF_LINE, CAM_REF_BLOCK,
    INTRO_DO_LINES, INTRO_DO_UNDEF, TEASE_DO_LINES, TEASE_DO_UNDEF,
    HJ_POS_DETAIL, HJ_GRIP_LINES, HJ_GRIP_FALLBACK, HJ_TEMPO_LINES,
    BJ_POS_DETAIL, BJ_DEPTH_LINES, BJ_WET_LINES, BJ_TEMPO_LINES, BJ_HANDS_LINES,
    BREAST_KIND_LINES, BREAST_KIND_UNDEF, BREAST_STANCE_DETAIL,
    SEX_POS_DETAIL, SEX_ACT_TEMPLATE, SEX_HOLE_TEMPLATES, SX_BOUNCE_LINES,
    SX_BOUNCE_DEFAULT, CUM_OPENING, CUM_HOW_LINES, CUM_QTY_LINES,
    CUM_QTY_DEFAULT, CUM_LAND_LINES, CUM_LAND_UNDEF, CUM_FLUID_RULE,
    SHOT_AUDIO_VOICE, SHOT_AUDIO_MOOD, AGE_LOCK_F, AGE_LOCK_M,
    FEMALE_SELECT_WORDS, MAN_SELECT_WORDS, MAN_LOOK_WORDS, MAN_BODY_WORDS,
    MAN_SKIN_WORDS, MAN_LEN_WORDS, MAN_GIRTH_WORDS, COCK_SIZE_LEN_WORDS,
    COCK_SIZE_GIRTH_WORDS, COCK_SIZE_DEFAULT, FEM_BREAST_CLOTHED,
    FEM_BREAST_BARE, FEM_HEIGHT_WORDS, FEM_FRAME_WORDS, FEM_CLOTHED_BIT,
    FIT_LEN_MOUTH, FIT_GIRTH_PUSSY, EXTRA_WATCH_LINES, TALK,
)

TOK = re.compile(r"\{([A-Za-z_0-9]+)\}")


# ---------------------------------------------------------------------------
# tiny pronoun machinery
# ---------------------------------------------------------------------------

class Person:
    def __init__(self, base, pron, tag):
        self.base, self.pron, self.tag = base, pron, tag  # "the female"/"she"

    def s(self, first):
        return self.base if first else self.pron

    @property
    def p(self):  # possessive
        return self.base + "'s" if self.pron.startswith(("it",)) else {
            "she": "her", "he": "his", "they": "their"}[self.pron]

    @property
    def o(self):  # object
        return {"she": "her", "he": "him", "they": "them"}[self.pron]

    @property
    def self_(self):
        return {"she": "herself", "he": "himself", "they": "themselves"}[self.pron]


def _tok_roles(ctx):
    """Map template tokens to strings for str-format substitution."""
    r = {}
    for key, person in ctx["people"].items():
        used = id(person) in ctx["said"]
        r[f"{key}_s"] = person.s(not used)
        r[f"{key}_p"], r[f"{key}_o"], r[f"{key}_self"] = person.p, person.o, person.self_
        r[key] = r[f"{key}_o"]
    return r


# pronoun aliases -> (role key, form) ({she}/{he} are subject-form)
ALIAS = {"her": ("M", "o"), "she": ("M", "s"), "herself": ("M", "self"),
         "who": ("M", "s"), "woman": ("M", "s"),
         "him": ("C", "o"), "he": ("C", "s"), "his": ("C", "p"),
         "himself": ("C", "self"), "man": ("C", "s")}


def fmt(template, ctx, mention=()):
    for m in mention:  # pre-mark roles as already introduced
        person = ctx["people"].get(m)
        if person is not None:
            ctx["said"].add(id(person))

    def resolve(tok):
        people = ctx["people"]
        person, form = None, None
        if tok in ALIAS and ALIAS[tok][0] in people:
            role, form = ALIAS[tok]
            person = people[role]
        elif tok in people:
            person, form = people[tok], "o"
        else:
            base, sfx = (tok.rsplit("_", 1) + [""])[0], tok.rsplit("_", 1)[-1] if "_" in tok else None
            if sfx in ("s", "p", "o", "self", "first"):
                if base in people:
                    person = people[base]
                elif base in ALIAS and ALIAS[base][0] in people:
                    person = people[ALIAS[base][0]]
                else:
                    for part in base.split("_or_"):  # {C_or_who_o}: first defined wins
                        if part in people:
                            person = people[part]
                            break
                        if part in ALIAS and ALIAS[part][0] in people:
                            person = people[ALIAS[part][0]]
                            break
                form = sfx
        if person is None:
            if tok == "which":
                return ctx.get("which", "hand")
            return ctx.get(tok, "")
        first = id(person) not in ctx["said"]
        val = {"s": person.s(first), "p": person.p, "o": person.o,
               "self": person.self_, "first": person.base}[form]
        if form == "s" and first:  # only a subject-form mention introduces the person
            ctx["said"].add(id(person))
        return str(val)

    out = TOK.sub(lambda m: str(resolve(m.group(1))), template)
    return re.sub(r"\s{2,}", " ", out).strip()


# ---------------------------------------------------------------------------
# random helpers
# ---------------------------------------------------------------------------

def roll(v, pool):
    """'any' rolls the pool, 'off'/None -> None, else pass through."""
    if v in (None, "", "off"):
        return None
    if v == "any":
        return random.choice(list(pool))
    return v


def _pick(seq):
    return random.choice(seq)


# ---------------------------------------------------------------------------
# subject definition (header)
# ---------------------------------------------------------------------------

def _fem_extra(s):
    bits = []
    if s.get("fAge") not in (None, "asref"):
        bits.append(AGE_LOCK_F.get(s["fAge"], ""))
    if s.get("fBreast") not in (None, "asref"):
        tbl = FEM_BREAST_BARE if s.get("fClothed") == "bare" else FEM_BREAST_CLOTHED
        bits.append(tbl.get(s["fBreast"], ""))
    if s.get("fHeight") not in (None, "asref"):
        bits.append(FEM_HEIGHT_WORDS.get(s["fHeight"], ""))
    if s.get("fFrame") not in (None, "asref"):
        bits.append(FEM_FRAME_WORDS.get(s["fFrame"], ""))
    if s.get("fClothed") == "bare":
        bits.append("she is already nude, no clothes on her")
    else:
        bits.append(FEM_CLOTHED_BIT)
    return ", ".join(b for b in bits if b)


def _man_extra(s):
    bits = []
    if s.get("mAge") not in (None, "asref"):
        bits.append(AGE_LOCK_M.get(s["mAge"], ""))
    if s.get("mLook") not in (None, "asref"):
        bits.append(MAN_LOOK_WORDS.get(s["mLook"], ""))
    if s.get("mBody") not in (None, "asref"):
        bits.append(MAN_BODY_WORDS.get(s["mBody"], ""))
    if s.get("mSkin") not in (None, "asref"):
        bits.append(MAN_SKIN_WORDS.get(s["mSkin"], ""))
    if s.get("mLen") not in (None, "asref") or s.get("mGirth") not in (None, "asref"):
        ln = COCK_SIZE_LEN_WORDS.get(s.get("mLen") or "average", "average length")
        gr = COCK_SIZE_GIRTH_WORDS.get(s.get("mGirth") or "average", "average girth")
        bits.append(f"{ln} {gr} hard cock")
    return ", ".join(b for b in bits if b)


def subject_definitions(s, roster, pics):
    lines = []
    fem_i = next((i for i, p in enumerate(roster) if p[3]), None)   # has vulva
    man_i = next((i for i, p in enumerate(roster) if p[2]), None)   # has penis
    # which attached picture carries which subject (user picks in the UI)
    fem_first = s.get("picWho", "f") != "m"
    fem_pic = "<Picture 1>" if fem_first else "<Picture 2>"
    man_pic = "<Picture 2>" if fem_first else "<Picture 1>"
    if fem_i is not None:
        lines.append(
            f"<Subject 1> is one female from {fem_pic}. Same female. "
            f"{fem_pic} = this person. Keep the {fem_pic} backdrop"
            + ((", " + _fem_extra(s)) if _fem_extra(s) else "") + ".")
    if man_i is not None:
        lines.append(
            f"<Subject 2> is {man_pic} penis out, 1man, male focus, nude, penis, "
            f"pubic hair, uncensored, erection, male pubic hair, bara, veins, "
            f"realistic, veiny penis, leg hair, arm hair, hairy, body hair"
            + ((", " + _man_extra(s)) if _man_extra(s) else "")
            + f". Same man as {man_pic}. Not the other male.")
    if pics:
        lines.append(f"{fem_pic} is the attached reference picture: identity, hair, "
                     "outfit and backdrop reference.")
        if man_i is not None and len(pics) > 1:
            lines.append(f"{man_pic} is the attached reference picture for the man: "
                         "identity and body reference.")
    lines.append("<Subject 4> is <Picture 1> backdrop and light. Not a new backdrop.")
    return lines


# ---------------------------------------------------------------------------
# camera
# ---------------------------------------------------------------------------

def camera_block(s, dist_key):
    if s.get("camMode") == "ref":
        return CAM_REF_BLOCK["cameraLine"]
    style_key = s.get("camStyle")
    if style_key and style_key != "off":
        st = STYLE[style_key]
        return " ".join(x for x in (st.get("cam"), st.get("framing"),
                                    st.get("ang"), st.get("lock")) if x)
    d = dist_key if dist_key in DIST_NAME else _pick(list(DIST_NAME))
    parts = [f"Camera distance: {DIST_NAME[d]}."]
    if s.get("pov") == "on":
        parts.append(f"Camera angle: {_pick(POV)}.")
    elif s.get("camAngle") not in (None, "", "any", "off"):
        parts.append(f"Camera angle: {ANGLELOCK.get(s['camAngle'], '')}.")
    else:
        parts.append(f"Camera angle: {_pick(ANGLE)}.")
    if s.get("camHeight") not in (None, "", "any", "off"):
        parts.append(HEIGHT.get(s["camHeight"], "") + ".")
    mv = s.get("camMove")
    if mv == "static":
        parts.append("Camera does not move.")
    elif mv not in (None, "", "any", "off"):
        parts.append(f"Camera moves: {MOVELOCK.get(mv, mv)}.")
    else:
        m = _pick(MOVE)
        parts.append("Camera does not move." if m.get("lock")
                     else f"Camera moves: {m['t']}.")
    sp = s.get("camSpeed")
    parts.append((SPEED.get(sp, "camera speed slow") + ".") if sp not in (None, "", "any")
                 else _pick(list(SPEED.values())) + ".")
    sb = s.get("camStab")
    parts.append(f"Camera is {STAB.get(sb, _pick(list(STAB.values())))}.")
    ln = s.get("camLens")
    if ln not in (None, "", "any", "off"):
        parts.append(f"Camera lens: {LENS.get(ln, '')}.")
    fl = s.get("camFollow")
    if fl not in (None, "", "any", "off"):
        parts.append(f"Camera follows: {FOLLOW.get(fl, '')}.")
    return " ".join(p for p in parts if p.strip())


# ---------------------------------------------------------------------------
# per-act line builders (return plain sentences, roles already resolved)
# ---------------------------------------------------------------------------

def _act_common(s, ctx, stage):
    """mood/face/relate/experience extras shared by all acts."""
    out = []
    mood = s.get("mood")
    if mood and mood != "off":
        key = _roll_into(mood, MOOD_LINES)
        out.append(fmt(MOOD_LINES.get(key, MOOD_LINES_DEFAULT), ctx, mention=("M", "C")))
    face = s.get("face")
    if face and face != "off":
        tbl = FACE_ORAL_LINES if stage in ("bj",) else FACE_LINES
        key = _roll_into(face, tbl)
        out.append(fmt(tbl.get(key, ""), ctx, mention=("M",)))
    rel = s.get("relate")
    if rel and rel != "off":
        out.append(fmt(RELATE_LINES.get(rel, ""), ctx, mention=("M", "C")))
    exp = s.get("exp") if s.get("exp") not in (None, "any", "off") else None
    if exp and stage in EXP_LINES:
        out.append(EXP_LINES[stage][exp])
    return out


def _roll_into(v, pool):
    return random.choice(list(pool)) if v in (None, "any") else v


def _hands(s, ctx, prefix):
    out = []
    for side, key in (("right", s.get(prefix + "RH")), ("left", s.get(prefix + "LH"))):
        if key and key != "off":
            ctx["which"] = side + " hand"
            out.append(fmt(MAN_HAND_LINES.get(key, ""), ctx, mention=("C",)))
    return out


def act_line(stage, s, ctx):
    """One action sentence block for a shot."""
    ctx = dict(ctx)
    parts = []

    if stage in ("intro", "tease"):
        # the acting person in intro/tease templates is {T_*}; she is the actor
        ctx["people"] = dict(ctx["people"], T=ctx["people"]["M"])
        prefix = "intro" if stage == "intro" else "tease"
        table = INTRO_DO_LINES if stage == "intro" else TEASE_DO_LINES
        undef = INTRO_DO_UNDEF if stage == "intro" else TEASE_DO_UNDEF
        do = s.get(prefix + "Do", "undef")
        tpl = undef if do == "undef" else table.get(_roll_into(do, table), undef)
        parts.append(fmt(tpl, ctx, mention=("T", "C")))
        look = s.get(prefix + "Look")
        if look and look != "any":
            parts.append(fmt(LOOK_LINES.get(look, ""), ctx, mention=("M",)))
        parts += _hands(s, ctx, prefix)

    elif stage == "hj":
        pos = _roll_into(s.get("hjPos", "any"), HJ_POS_DETAIL)
        parts.append(fmt(HJ_POS_DETAIL.get(pos, HJ_GRIP_FALLBACK), ctx, mention=("M", "C")))
        grip = _roll_into(s.get("hjGrip", "any"), HJ_GRIP_LINES)
        parts.append(fmt(HJ_GRIP_LINES.get(grip, HJ_GRIP_FALLBACK), ctx, mention=("M", "C")))
        tempo = _roll_into(s.get("hjTempo", "any"), HJ_TEMPO_LINES)
        parts.append(fmt(HJ_TEMPO_LINES.get(tempo, ""), ctx))
        parts += _hands(s, ctx, "hj")

    elif stage == "bj":
        pos = _roll_into(s.get("bjPos", "any"), BJ_POS_DETAIL)
        parts.append(fmt(BJ_POS_DETAIL.get(pos, ""), ctx, mention=("M", "C")))
        depth = _roll_into(s.get("bjDepth", "any"), BJ_DEPTH_LINES)
        parts.append(fmt(BJ_DEPTH_LINES.get(depth, ""), ctx, mention=("M", "C")))
        wet = _roll_into(s.get("bjWet", "any"), BJ_WET_LINES)
        parts.append(fmt(BJ_WET_LINES.get(wet, ""), ctx))
        tempo = _roll_into(s.get("bjTempo", "any"), BJ_TEMPO_LINES)
        parts.append(fmt(BJ_TEMPO_LINES.get(tempo, ""), ctx))
        hand = _roll_into(s.get("bjHands", "any"), BJ_HANDS_LINES)
        parts.append(fmt(BJ_HANDS_LINES.get(hand, ""), ctx, mention=("M", "C")))

    elif stage == "breast":
        kind = _roll_into(s.get("breastKind", "any"), BREAST_KIND_LINES)
        parts.append(fmt(BREAST_STANCE_DETAIL, ctx, mention=("M", "C")))
        parts.append(fmt(BREAST_KIND_LINES.get(kind, BREAST_KIND_UNDEF), ctx, mention=("M", "C")))

    elif stage == "sex":
        kind = "anal" if s.get("sexHole") == "anal" else "vaginal"
        pos = _roll_into(s.get("sexPos", "any"), SEX_POS_DETAIL)
        parts.append(fmt(SEX_POS_DETAIL.get(pos, ""), ctx, mention=("B", "T")))
        ctx["kind"] = kind
        ctx["hole_p"] = fmt(SEX_HOLE_TEMPLATES[kind], ctx, mention=("B", "V"))
        parts.append(fmt(SEX_ACT_TEMPLATE, ctx, mention=("C", "B", "T")))
        pos_bits = POS.get(pos) or [""]
        parts.append(fmt(pos_bits[0], ctx, mention=("B", "T")) + ".")
        bounce = _roll_into(s.get("sexBounce", "any"), SX_BOUNCE_LINES)
        parts.append(fmt(SX_BOUNCE_LINES.get(bounce, SX_BOUNCE_DEFAULT), ctx, mention=("B",)))

    elif stage == "cum":
        parts.append(fmt(CUM_OPENING, ctx, mention=("C",)))
        how = _roll_into(s.get("cumHow", "any"), CUM_HOW_LINES)
        parts.append(fmt(CUM_HOW_LINES.get(how, ""), ctx, mention=("C",)))
        qty = _roll_into(s.get("cumQty", "any"), CUM_QTY_LINES)
        parts.append(fmt(CUM_QTY_LINES.get(qty, CUM_QTY_DEFAULT), ctx))
        land = _roll_into(s.get("cumLand", "any"), CUM_LAND_LINES)
        parts.append(fmt(CUM_LAND_LINES.get(land, CUM_LAND_UNDEF), ctx, mention=("C", "M")))
        parts.append(CUM_FLUID_RULE.strip())

    parts += _act_common(s, ctx, stage)
    extras = s.get("inFrame")
    if extras and extras != "off" and stage != "intro":
        parts.append(fmt(EXTRA_WATCH_LINES.get(extras, ""), ctx))
    block = " ".join(p for p in parts if p)
    return block[:1].upper() + block[1:] if block else block


# ---------------------------------------------------------------------------
# audio
# ---------------------------------------------------------------------------

def _say(line):
    """Wrap a spoken line per the H3 spec: <d>[language] text</d>."""
    lang = "Russian" if any("\u0400" <= c <= "\u04FF" for c in line) else "English"
    return f'<d>[{lang}] {line}</d>'


def audio_line(stage, dist_key, s, ctx):
    mic = "Close on her mouth." if dist_key in ("cu", "ecu", "macro") else "Close on the bodies."
    act = AUDIO_STAGE.get(stage, "")
    voice = SHOT_AUDIO_VOICE.get(_roll_into(s.get("face", "off"), SHOT_AUDIO_VOICE), "")
    moodv = SHOT_AUDIO_MOOD.get(s.get("mood"), "")
    talk = s.get("talkLine", "").strip()
    bits = f" AUDIO: {mic} {act} {voice} {moodv}".rstrip()
    if s.get("talk") == "on":
        line = talk if talk else _pick(TALK.get(s.get("talkLevel", "mid"), TALK["mid"]))
        bits += f" She says: {_say(line)}. Lipsync matches the words."
    return bits


# ---------------------------------------------------------------------------
# main build
# ---------------------------------------------------------------------------

def _ts(sec):
    return f"{sec // 60:02d}:{sec % 60:06.3f}"


def build(s):
    """s: settings dict -> (prompt, recap_lines_ru)"""
    cast_key = s.get("cast", "fm")
    roster = PRESET.get(cast_key, PRESET["fm"])
    pics = s.get("picCount") or []
    n_pics = len(pics)

    # role people: M = first female, C = first male, B/V/T follow fm shape
    people = {}
    fem = next((p for p in roster if p[3]), roster[0])
    man = next((p for p in roster if p[2]), None)
    people["M"] = Person(fem[0], fem[1], "f")
    if man:
        people["C"] = Person(man[0], man[1], "m")
    # B = receiver, T = giver default to the fm pair
    people.setdefault("B", people["M"])
    people.setdefault("T", people.get("C", people["M"]))
    people.setdefault("V", people["M"])

    ctx = {"people": people, "said": set()}

    stages = [st for st in STAGES_ORDER if s.get("act_" + st) == "on"]
    if not stages:
        stages = ["intro"]

    seq = s.get("mode", "sequence") == "sequence"
    per = int(s.get("shotSec") or 5)
    t = 0
    shots = []
    dist_first = None
    for i, stage in enumerate(stages):
        body = []
        if i == 0:
            body.append("<Subject 1> and <Subject 4>, exactly same <Subject 1> frame.")
            if s.get("fixRef") == "on":
                body.append(FORCE_REF_LINE.strip())
            if s.get("manJoin") == "on" and man:
                body.append(MAN_JOIN_LINE.strip())
            if s.get("fClothed") != "bare":
                body.append("CLOTHED. Picture 1 garments stay on. Breast and ass lines "
                            "are shape under fabric. Do not strip her.")
        else:
            bridge = STAGE_BRIDGES.get(f"{stages[i-1]}>{stage}")
            body.append(bridge or "Jump cut.")
        dist_key = None
        if s.get("camMode") == "auto":
            dist_key = _roll_into(s.get("camDist", "any"), DIST_NAME)
            dist_first = dist_first or dist_key
        body.append(act_line(stage, s, ctx))
        body.append(audio_line(stage, dist_key or dist_first or "ms", s, ctx))
        body.append(camera_block(s, dist_key))
        shots.append(f"[Shot {i+1}] At {_ts(t)}, " + re.sub(r"\s{2,}", " ", " ".join(body)))
        t += per if (seq or i < len(stages) - 1) else per

    total = per * len(stages)
    header = []
    header.append(f"For the target video, at 00:00.000 into the target video, "
                  f"<Picture 1> (from [Shot 1]) is fully referenced.")
    header.append("Shot 1 begins exactly from the composition of <Picture 1>. Same face, "
                  "clothes, pose, crop and backdrop. Do not open on a different place.")
    header.append("subject_definitions:")
    header += subject_definitions(s, roster, pics)
    titles = " then ".join(ACT_TITLES.get(st, st) for st in stages)
    header.append(f"summary: [reference generation] {total}s from <Picture 1>. {titles}. "
                  f"Same backdrop. One locked take. Camera holds.")
    header.append("retention_analysis:")
    shot_ids = ", ".join(f"[Shot {i+1}]" for i in range(len(shots)))
    header.append(f"<Subject 1> (appears in {shot_ids}): fully_preserved - "
                  "identity, face, hair, outfit from <Picture 1>.")
    if any(p[2] for p in roster):  # a male is in the cast
        header.append(f"<Subject 2> (appears in {shot_ids}): fully_preserved - "
                      "identity, face, body from <Picture 2>.")
    header.append("detailed_description:")
    cloth = CLOTHES.get(s.get("clothes", "asref"), "")
    if cloth:
        header.append(cloth)
    mess = CLOTH_MESS.get(s.get("clothMess", "asref"), "")
    if mess:
        header.append(mess)
    pl = PLACE.get(s.get("place", "asref"), "")
    if pl:
        header.append(pl)
    lt = PLACE_LIGHT.get(s.get("placeLight", "asref"), "")
    if lt:
        header.append(lt)
    fmt_key = s.get("format")
    if fmt_key and fmt_key != "off":
        f = FORMAT.get(fmt_key, {})
        if f.get("spine"):
            header.append(f["spine"])
        slot = {"intro": "intro", "tease": "tease", "hj": "hj", "bj": "bj",
                "breast": "breast", "sex": "sex", "cum": "cum"}
        for st in stages:
            line = f.get(slot.get(st, ""), "")
            if line:
                header.append(line)

    footer = [ARTIFACT_LOCK_LIGHT.strip()]
    if s.get("artifactFull") == "on":
        footer.append(ARTIFACT_LOCK_FULL_SUFFIX.strip())
    snd = " ".join(AUDIO_STAGE.get(st, "") for st in stages)
    footer.append(
        "overall_soundscape: Close-mic unless the style says far. Same room as the picture. "
        f"{snd} Stereo diegetic only. No crowd. No street unless the place is outside.")
    footer.append("non_diegetic_music: None.")

    prompt = "\n".join(header + [""] + shots + [""] + footer)

    # Russian recap for the user
    ru_cast = RU_CAST.get(cast_key, cast_key)
    recap = [
        f"Состав: {ru_cast}",
        f"Кадры: {len(shots)} × ~{per}s (всего ~{total}s)",
        f"Активность: {', '.join(RU_STAGE.get(st, st) for st in stages)}",
        f"Одежда: {RU_CLOTHES.get(s.get('clothes'), s.get('clothes'))}",
        f"Место: {RU_PLACE.get(s.get('place'), s.get('place'))}",
        f"Камера: {RU_CAM_MODE.get(s.get('camMode'), 'авто')}"
        + (f" ({STYLE.get(s.get('camStyle'), {}).get('label', '')})" if s.get("camMode") == "style" else ""),
    ]
    if not pics:
        recap.append("⚠ Фото не выбраны — прикрепите референсы в генераторе.")
    return prompt, "\n".join(recap)


STAGES_ORDER = ["intro", "tease", "hj", "bj", "breast", "sex", "cum"]
ACT_TITLES = {"intro": "SFW intro", "tease": "tease", "hj": "handjob", "bj": "blowjob",
              "breast": "breast play", "sex": "sex", "cum": "the finish"}
RU_STAGE = {"intro": "Интро", "tease": "Прелюдия", "hj": "Ручной", "bj": "Минет",
            "breast": "Грудь", "sex": "Секс", "cum": "Финал"}
RU_CAST = {"fm": "1Ж + 1М", "ff": "2Ж", "mm": "2М", "fmm": "1Ж + 2М", "ffm": "2Ж + 1М",
           "fff": "3Ж", "mmm": "3М", "ffmm": "2Ж + 2М", "soloF": "соло Ж", "soloM": "соло М"}
RU_CAM_MODE = {"auto": "авто", "style": "стиль-пак", "ref": "как Картинка 1"}

RU_CLOTHES = {
    "asref": "как в референсе", "any": "любая", "teejeans": "футболка и джинсы",
    "tankshorts": "майка и шорты", "bandtee": "футболка группы и джинсы",
    "tiedtee": "футболка узлом на талии", "sundress": "сарафан", "slipdress": "платье-комбинация",
    "sweater": "свитер и штаны", "offshoulder": "свитер с открытыми плечами",
    "cardigan": "кардиган и юбка", "flannel": "фланель на майке", "sweats": "домашний комплект",
    "satinpj": "атласная пижама", "buttoned": "рубашка и брюки", "polo": "поло и юбка",
    "denimskirt": "джинсовая юбка и топ", "overalls": "комбинезон", "jumpsuit": "комбинезон на молнии",
    "raincoat": "дождевик", "bootscoat": "пальто и сапоги", "yoga": "йога-комплект",
    "aside": "ткань отведена в сторону", "half": "секс сквозь одежду", "shirtup": "топ задран",
    "dressup": "платье задрано к талии", "skirtnone": "юбка без трусиков",
    "jeanszip": "джинсы расстёгнуты", "jeansthigh": "джинсы до середины бёдер",
    "pantsdown": "штаны у щиколоток", "cargodown": "карго спущены",
    "unbutton": "рубашка расстёгнута", "rippedtee": "рваная футболка",
    "wetshirt": "мокрая липняя рубашка", "wetjeans": "мокрые джинсы, ширинка открыта",
    "jumpsuitopen": "комбинезон расстёгнут до пупа", "bikeshorts": "велосипедки отведены",
    "hoodie": "только худи", "hoodiesocks": "худи и носки", "croptop": "кроп-топ без низа",
    "tankpanty": "майка и трусики", "night": "ночная рубашка задралась", "robe": "халат распахнут",
    "kimono": "кимоно распахнуто", "towel": "полотенце сползает", "socksandshirt": "рубашка оверсайз и носки",
    "boytee": "его футболка оверсайз", "apron": "только фартук", "socks": "только носки",
    "onesie": "onesie расстёгнут", "underwear": "только бельё", "bralette": "бралетка и шорты",
    "lingerie": "комплект белья", "longline": "длинный бюстгальтер и трусики",
    "sheer": "прозрачное", "meshtop": "сетка, бельё под ней", "thongonly": "только стринги",
    "crotchless": "трусики с прорезью", "openbra": "открытый бюстгальтер", "cupless": "бюстгальтер без чашек",
    "pasties": "только наклейки", "stockings": "чулки с подвязками", "thighhighs": "только чулки",
    "fishnet": "сетка-рыбка", "pantyhose": "колготки в стрелках", "tights": "плотные колготки порваны",
    "bikini": "бикини отведено", "microkini": "микробикини", "slingkini": "слинг-бикини",
    "swim": "купальник стянут", "gym": "спортивная форма отведена",
    "sportsbra": "спортивный топ и шорты стянуты", "jersey": "джерси без белья",
    "jock": "только джок", "office": "блузка открыта, юбка задрана", "suit": "брюки костюма открыты",
    "tie": "рубашка и галстук", "scrubs": "медформа отведена", "waitapron": "платье официантки и фартук задраны",
    "coat": "пальто на голое тело", "winterbare": "зимнее пальто на голое тело",
    "minidress": "мини-платье задирается", "bodycon": "облегающее платье задрано",
    "cocktaildress": "коктейльное платье задрано", "cutoutdress": "платье с вырезами",
    "heels": "только каблуки", "wrapdress": "запáхнутое платье расходится",
    "latex": "латекс", "pvc": "ПВХ/винил", "leather": "кожаная сбруя", "cagebra": "сбруя-клетка",
    "corset": "корсет без низа", "bustier": "бюсье без низа", "bodysuit": "боди отведено",
    "bodychain": "только цепочка на теле", "collaronly": "только ошейник",
    "chokerheels": "чокер и каблуки", "maid": "горничная, платье задрано",
    "bunny": "костюм кролика с открытой панелью", "silkwrap": "шёлк сползает",
    "velvetgown": "бархатное платье задрано", "ritualrobe": "ритуальная мантия открыта",
    "travelercloak": "плащ, одежда сдёрнута", "chainmail": "кольчуга на голом теле",
    "elfsilk": "тонкая иномировая ткань", "priestess": "облачение жрицы",
    "goddess": "драпировка богини", "sari": "сари сползает", "cheongsam": "цюпAO задран",
    "coinbelt": "пояс с монетами и вуаль", "hospitalgown": "больничная рубашка открыта сзади",
    "tornnight": "порванная ночная сорочка", "dirtyshirt": "грязная огромная рубашка",
    "ragged": "лохмотья сползают", "occult": "чёрная оккультная мантия открыта",
    "wetblack": "мокрая чёрная ткань", "widow": "чёрное платье разорвано",
    "off": "уже обнажена", "jewelry": "только украшения",
}
RU_PLACE = {
    "asref": "как в референсе", "any": "любое", "bedroom": "спальня, смятая кровать",
    "sheets": "только смятые простыни", "sofa": "диван в гостиной", "floor": "ковёр",
    "wall": "стена в комнате", "door": "закрытая дверь", "kitchen": "кухонная стойка",
    "chair": "кресло или стул", "stairs": "лестничная площадка", "window": "у окна",
    "closet": "гардеробная", "laundry": "прачечная", "porch": "заднее крыльцо, ночь",
    "hallway": "коридор квартиры", "bath": "ванная", "shower": "душ, пар",
    "tub": "край ванны", "sauna": "полка в сауне", "pool": "край бассейна",
    "hot tub": "джакузи", "desk": "письменный стол", "office": "пустой офис вечером",
    "fitting": "примерочная", "gym": "пустой тренажёрный зал", "studio": "студия на нейтральном фоне",
    "loft": "матрас в лофте", "penthouse": "пентхаус со стеклом, ночь",
    "greenroom": "кулисный диван", "clubbath": "кабинка клубного туалета",
    "diner": "пустая закусочная, ночь", "hotel": "гостиничная кровать", "motel": "дешёвый мотель",
    "car": "заднее сиденье машины", "frontseat": "переднее сиденье", "van": "грузовой фургон",
    "garage": "парковочный гараж", "balcony": "балкон, ночь", "rooftop": "крыша, ночь",
    "cabin": "спальня в домике", "tent": "внутри палатки", "woods": "лес",
    "beach": "полотенце на пляже, сумерки", "alley": "стена в переулке, ночь",
    "warehouse": "угол пустого склада", "castlebed": "кровать в замке",
    "stonehall": "каменный зал с факелами", "dungeon": "каменная камера со шкурами",
    "temple": "храм со свечами", "throne": "постамент с троном", "tavernloft": "второй этаж таверны",
    "tower": "башенная комната", "faegrove": "светящаяся роща", "icehall": "ледяной зал",
    "ruins": "заросшие руины", "abandoned": "заброшенный дом", "attic": "чердак",
    "basement": "подвал с одной лампочкой", "chapel": "пустая часовня ночью",
    "greenhouse": "мёртвая оранжерея", "morgue": "пустая кафельная комната",
    "theater": "неиспользуемый кинозал", "graveedge": "край кладбища ночью",
    "flooded": "затопленная комната", "redroom": "красная подсветка в комнате",
}
