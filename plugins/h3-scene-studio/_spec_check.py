# -*- coding: utf-8 -*-
"""Spec conformance check: engine output vs the H3 spec (6 sections).

Run: env_uv/Scripts/python.exe plugins/h3-scene-studio/_spec_check.py
Results -> _spec_check_out.txt next to this file.
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import importlib  # noqa: E402

engine = importlib.import_module("h3-scene-studio.engine")

out = io.StringIO()
ok = True


def check(name, cond, detail=""):
    global ok
    if not cond:
        ok = False
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f" | {detail}"),
          file=out)


base = {
    "cast": "fm", "mode": "sequence", "shotSec": 5,
    "act_intro": "on", "act_tease": "on", "act_bj": "on", "act_sex": "on", "act_cum": "on",
    "camMode": "auto", "camDist": "any", "pov": "off", "camAngle": "any", "camHeight": "any",
    "camMove": "any", "camSpeed": "any", "camStab": "any", "camLens": "any", "camFollow": "any",
    "mood": "eager", "face": "moan", "relate": "couple", "exp": "exp",
    "clothes": "asref", "clothMess": "asref", "place": "asref", "placeLight": "asref",
    "format": "off", "fClothed": "clothed", "fixRef": "on", "manJoin": "on", "inFrame": "off",
    "talk": "on", "talkLevel": "mid", "talkLine": "смотри на меня",
    "introDo": "sit", "introLook": "cam", "introRH": "hip", "introLH": "off",
    "teaseDo": "strap", "teaseRH": "waist", "teaseLH": "off",
    "hjPos": "kneel", "hjGrip": "one", "hjTempo": "even", "hjRH": "any", "hjLH": "off",
    "bjPos": "kneel", "bjDepth": "half", "bjWet": "wet", "bjTempo": "even", "bjHands": "base",
    "breastKind": "titfuck", "sexPos": "missionary", "sexHole": "vaginal", "sexBounce": "medium",
    "cumLand": "mouth", "cumHow": "pulse", "cumQty": "heavy", "artifactFull": "off",
    "fAge": "asref", "fBreast": "asref", "fHeight": "asref", "fFrame": "asref",
    "mAge": "asref", "mLook": "asref", "mBody": "asref", "mSkin": "asref",
    "mLen": "asref", "mGirth": "asref",
    "picWho": "f", "picCount": ["", ""],
}

p, recap = engine.build(base)

# 1. six sections, in order
order = ["subject_definitions:", "summary:", "retention_analysis:",
         "detailed_description:", "overall_soundscape:", "non_diegetic_music:"]
pos = [p.find(x) for x in order]
check("six sections in order", all(x >= 0 for x in pos) and pos == sorted(pos), str(pos))

# 2. subject_definitions with <Subject N> + <Picture N>
sd = p[p.find("subject_definitions:"):p.find("summary:")]
check("<Subject 1> female line", "<Subject 1> is one female from <Picture 1>" in sd)
check("<Subject 2> male line", "<Subject 2> is <Picture 2> penis out" in sd)
check("<Subject 4> backdrop line", "<Subject 4> is <Picture 1> backdrop" in sd)
check("<Picture 1> definition", "<Picture 1> is the attached reference picture" in sd)
check("<Picture 2> definition", "<Picture 2> is the attached reference picture for the man" in sd)

# 3. retention_analysis per subject with shot lists
ret = p[p.find("retention_analysis:"):p.find("detailed_description:")]
check("retention S1 (appears in shots)", "(appears in [Shot 1]" in ret and "fully_preserved" in ret)
check("retention S2 (male cast)", "<Subject 2> (appears in" in ret)

# 4. dialogue in <d>[lang]
check("dialogue <d>[Russian]", '<d>[Russian] смотри на меня</d>' in p)

# 5. summary task type
check("summary [reference generation]", "summary: [reference generation]" in p)

# 6. no unresolved braces
check("no unresolved braces", not re.findall(r"\{[A-Za-z_0-9]+\}", p))

# 7. solo cast: no male artifacts
s2 = dict(base, cast="soloF")
for st in ("hj", "bj", "breast", "sex", "cum"):
    s2["act_" + st] = "off"
p2, _ = engine.build(s2)
ret2 = p2[p2.find("retention_analysis:"):p2.find("detailed_description:")]
check("solo: no Subject 2 retention", "<Subject 2>" not in ret2)
check("solo: no <Picture 2> def", "<Picture 2> is the attached" not in p2)

with open(os.path.join(HERE, "_spec_check_out.txt"), "w", encoding="utf-8") as f:
    f.write(out.getvalue())
print("SPEC", "OK" if ok else "FAILED")
