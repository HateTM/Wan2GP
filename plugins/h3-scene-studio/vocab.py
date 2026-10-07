"""Vocabulary tables for the h3-scene-studio prompt builder.

Extracted 1:1 from the JavaScript of h3_scene_studio.html (script section,
~lines 2632-6453). English prompt phrases are kept verbatim - they are
concatenated into the final video-model prompt. Nothing is translated.
JS ``true/false`` became Python ``True/False``; JS template literals became
Python ``str.format`` placeholders.

Placeholders used inside template strings (produced by the JS ``speak()``
pronoun helper, which emits the person's name on first mention and a plain
pronoun afterwards):

- ``{X_s}``  subject form   (w.s(X))  - "female 1" / "she" / "he" / "they"
- ``{X_p}``  possessive     (w.p(X))  - "female 1's" / "her" / "his" / "their"
- ``{X_o}``  object form    (w.o(X))  - "female 1" / "her" / "him" / "them"
- ``{X_self}`` reflexive   (w.self(X)) - "herself" / "himself" / "themselves"

Role variables: ``M`` = mouth (giving body), ``C`` = cock (penis owner),
``V`` = pussy (vulva owner), ``B`` = bottom/receiver, ``T`` = top/giver,
``X`` = extra (third) subject, ``m1``/``m2`` = male 1 / male 2,
``f1``/``f2`` = female 1 / female 2, ``her``/``him`` = receiver/giver roles.
``X_or_T`` means JS ``X||T`` (fall back to T when X is null).

PROMPT ASSEMBLY FORMAT (from shotText/headerText/footerText in the JS)
----------------------------------------------------------------------

The final prompt is: header + "" + one block per shot + "" + footer,
joined with newlines.

Header (headerText), one line per entry:
  1. "For the target video, at 00:00.000 into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
  2. "Shot 1 begins exactly from the composition of <Picture 1>. Same face, clothes, pose, crop and backdrop. Do not open on a different place."
  3. optional LIGHT LOCK line (forceRefLine) and FIRST FRAME line (firstFrameLine)
  4. "subject_definitions:" then one line per subject:
     - female: "<Subject 1> is one female from <Picture 1>. Same female. <Picture 1> = this person. Keep the <Picture 1> backdrop{femExtra}."
       (femExtra = ", " + comma-joined age / breast / height / frame / ass / clothes phrases)
     - male:   "<Subject 2> is <Picture 2> penis out, 1man, male focus, nude, penis, pubic hair, uncensored, erection, male pubic hair, bara, veins, realistic, veiny penis, leg hair, arm hair, hairy, body hair, {cockSize}{manExtra}. Same man as <Picture 2>. Not the other male."
  5. "<Subject 4> is <Picture 1> backdrop and light. Not a new backdrop."
  6. "summary:" + "[reference generation] {dur}s from <Picture 1>. {act titles joined ' then '}. {Cast: ...}. Same backdrop. One locked take. Camera holds. ..." 
  7. "retention_analysis:" + one "fully_preserved" line per subject
  8. "detailed_description:" + continuity paragraph + cast roster + FORMAT spine +
     CLOTHES / CLOTH_MESS / PLACE / PLACE_LIGHT lines + per-stage "SELECT" recap lines
     (e.g. "BJ SELECT: position {bjPos}, depth {bjDepth}, look {bjLook}, ...").

Shot line (shotText):
  "[Shot {i+1}] At {MM:SS.mmm}, {body}"
  where body = whitespace-collapsed concatenation, in order:
    open            - "<Subject 1> and <Subject 4>, exactly same <Subject 1> frame. "
                      (or "<Subject 1> and <Subject 4>. " when a first frame is set)
    light           - LIGHT LOCK line (optional)
    manJoinLine     - male walk-in line (optional)
    stamp           - user shot-fix text (optional)
    hideM           - MALE 1 FACE OUT OF FRAME line (optional)
    clad            - "CLOTHED. Picture 1 garments stay on. ..." (optional)
    pov             - "POV VIEW, CAMERA MAN POV. " (optional)
    join            - stage bridge (takeBridge) between shots, or "Jump cut. "
    lock            - "exactly same <Subject 1> frame. Same backdrop as <Picture 1>. ..." (shot 0 coherence)
    look            - CONTINUITY line (optional)
    ages            - AGE lock line (shot 0)
    exp             - EXPERIENCE line (optional)
    action          - actLine(): FORMAT beat prefix + position detail + phase
                      sentence + mood/face/relate/fit/body/forced/male2/female2
                      extras (all whitespace-collapsed)
    aud             - " AUDIO: {mic} {act sounds} {voice} {mood voice}"
    meme            - ON-SCREEN TEXT lines (optional)
    cam             - camera sentence block (see below)

Camera sentence (cameraLine), pieces joined with " ", each ended with ".":
  "Camera distance: {DIST_NAME[d]}" | "Camera angle: {ang}" | "{framing}" |
  "Camera does not move." (when static) else "Camera moves: {move}." |
  "Camera speed: {speed}." | "Camera is {stab}." | "Camera lens: {lens}." |
  "Camera follows: {follow}." | "{lock}" | "{style}"
  With a style pack, "CAMERA FROM <Picture 1>. ..." replaces it (refLock).

Audio sentence (shotAudio): " AUDIO: {mic} {act} {voice} {moodV}" where mic is
"Close on her mouth." / "Close on the bodies." / "Room around them." depending
on shot distance, act is per-stage foley text, voice/moodV from the face/mood
selects (SHOT_AUDIO_VOICE / SHOT_AUDIO_MOOD below).

Footer (footerText): artifact line (ARTIFACT_LOCK_LIGHT/_FULL), optional place
reminder, then:
  "overall_soundscape: {style audio}Close-mic unless the style says far. Same room as the picture. {AUDIO_STAGE per stage}. Stereo diegetic only. No crowd. No street unless the place is outside."
  "non_diegetic_music: None."

Time stamps use ts(): "MM:SS.mmm" (e.g. 0s -> "00:00.000", 5s -> "00:05.000").

Concrete example shot lines (reconstructed):
  [Shot 1] At 00:00.000, <Subject 1> and <Subject 4>, exactly same <Subject 1> frame. CLOTHED. Picture 1 garments stay on. Breast and ass lines are shape under fabric. Do not strip her. She is kneeling between his feet. His cock stands still. Her spine is long. Her hands rest on his thighs. Her mouth is at his cock height. She takes half of his shaft into her mouth. Her hand covers the rest. Even bob. She looks up at him. Her mouth is wet on his cock. She keeps an even bob. Her hand stays on the base of his cock. AUDIO: Close on her mouth. Wet lips on skin. Soft suction. Air through her nose. No chew. No crunch. A soft moan. Camera distance: a close-up, face and upper chest readable. Camera angle: eye-level on the faces. Camera moves: slow push-in toward the faces. Camera speed: camera speed slow. Camera is tripod-still.

  [Shot 2] At 00:05.000, <Subject 1> and <Subject 4>. Her mouth leaves him and she takes the same cock in view. She is on her back. Her knees are open. He is between her legs, his weight on his arms. Missionary. He fucks her vaginal. His cock is in her pussy. She takes him. Only this vaginal act. No oral. She bounces with each thrust. Her breasts and her ass lift and fall a clear amount. Skin ripples, then settles, then lifts again. MOOD eager, readable on her face. Her brows lift. Her eyes stay wide on the act. Her mouth opens for the motion. She leans in first and meets the pace, no delay. AUDIO: Close on the bodies. Hip slap. Wet of her pussy, not a mouth. Two breaths. Camera moves: slow pull-out that reveals more body, keep the same backdrop.

Header excerpt (subject_definitions, fm cast):
  <Subject 1> is one female from <Picture 1>. Same female. <Picture 1> = this person. Keep the <Picture 1> backdrop, 20s adult female, medium breasts as shape under her clothes, fabric stays on, not bare, average height, average female frame, normal waist and thighs, clothes from the picture stay on. Body size is shape under fabric. Not already nude.
  <Subject 2> is <Picture 2> penis out, 1man, male focus, nude, penis, pubic hair, uncensored, erection, male pubic hair, bara, veins, realistic, veiny penis, leg hair, arm hair, hairy, body hair, average length average girth hard cock. Same man as <Picture 2>. Not the other male.
  <Subject 4> is <Picture 1> backdrop and light. Not a new backdrop.

Reference block (refBlock) example:
  REF SLOTS:
  Image 1 = <Subject 1> identity, body, hair, skin only (the female, she, vulva/breasts). Do not copy that image's background. Location stays the reference.
  Image 2 = <Subject 2> identity, body, hair, skin only (the man, he, penis). Do not copy that image's background. Location stays the reference.
  If a video reference is attached, use it for rhythm only. Do not copy its room, clothes or faces.
"""

# ---------------------------------------------------------------------------
# Cast presets. Key = cast select value; each row = (who, pronoun, has_penis,
# has_vulva, has_breasts) for subjects S1..Sn. JS 0/1 -> False/True.
# ---------------------------------------------------------------------------
PRESET = {
    "fm":   [("the female", "she", False, True, True), ("the man", "he", True, False, False)],
    "ff":   [("female 1", "she", False, True, True), ("female 2", "she", False, True, True)],
    "mm":   [("the first man", "he", True, False, False), ("the second man", "he", True, False, False)],
    "fmm":  [("the female", "she", False, True, True), ("the first man", "he", True, False, False), ("the second man", "he", True, False, False)],
    "ffm":  [("female 1", "she", False, True, True), ("female 2", "she", False, True, True), ("the man", "he", True, False, False)],
    "fff":  [("female 1", "she", False, True, True), ("female 2", "she", False, True, True), ("female 3", "she", False, True, True)],
    "mmm":  [("the first man", "he", True, False, False), ("the second man", "he", True, False, False), ("the third man", "he", True, False, False)],
    "ffmm": [("female 1", "she", False, True, True), ("female 2", "she", False, True, True), ("the first man", "he", True, False, False), ("the second man", "he", True, False, False)],
    "soloF": [("the female", "she", False, True, True)],
    "soloM": [("the man", "he", True, False, False)],
}

# Position families; key = POS select value, value = list of position phrases.
POS = {
    "missionary": ["missionary, receiver on their back, giver between the legs", "missionary, knees pulled to chest", "missionary, one leg over the giver's shoulder", "ankles on shoulders", "mating press, receiver folded, giver's weight on them", "missionary, legs wrapped around the waist"],
    "doggy": ["doggy, hands and knees, back arched", "face-down ass-up, chest to the surface", "lazy doggy on elbows, face turned to camera", "prone bone, flat on the stomach", "doggy, cheek on the surface, looking back", "both upright on knees, giver flush to the back"],
    "cowgirl": ["cowgirl, facing the giver, sitting on them", "reverse cowgirl, ass toward the giver's face", "cowgirl lean-forward, breasts in the face", "squatting ride, feet planted", "rider laid back against the giver's thighs, being bounced"],
    "standing": ["standing doggy, bent at the waist", "standing face to face, one thigh hiked", "lifted, legs around the waist", "standing, chest to the plane of the frame, giver behind", "standing split, one foot up"],
    "side": ["spooning, giver behind", "facing side-lying, top leg over the hip", "scissor side-lying, legs tangled", "sideways doggy, torso twisted so the face reads"],
    "seated": ["in the lap, facing, full-sink", "in the lap facing away", "straddling one thigh and grinding", "on the edge, giver between the knees"],
    "oralpos": ["kneeling between the feet, mouth working", "sitting on the edge, giver on the surface", "69 stack", "facesitting, thighs either side of the head", "receiver on their back, giver between the thighs to eat", "standing oral, one upright, one kneeling", "side-lying, head in the lap", "feeding a cock down into a mouth on its back"],
    "folded": ["legs-up press, knees by the ears", "happy baby, holding their own thighs open", "folded missionary, pelvis tilted up", "knees to chest, deep angle"],
    "breastpos": ["giver straddling the ribs for a titfuck", "kneeling titfuck, breasts pushed around the shaft", "from behind, hands on the breasts while fucking", "face in the breasts while the hips keep moving", "side-lying, working between the breasts"],
    "grouppos": ["spit-roast line: one at the mouth, one at the hips", "on their back, one at the head, one between the legs", "sandwich: one under, one over, receiver in the middle", "two mouths on one cock or one pussy", "one riding the cock, one sitting on the face", "side-by-side receivers, giver moving between them", "train: three bodies stacked kneeling"],
    "solo": ["standing in front of a mirror, body to camera", "phone selfie hold, arm out, face and chest in frame", "standing full-body, weight on one hip", "on the edge of a surface, knees together then open", "kneeling on the surface facing camera", "bent forward, ass to camera, looking back", "lying on her back on the surface, knees up, showing herself"],
}

# Human names for camera distance keys (used in "Camera distance: ...").
DIST_NAME = {
    "macro": "a very tight detail shot, only a few inches of skin in frame",
    "ecu": "an extreme close-up, one face or one pair of hands filling the frame",
    "cu": "a close-up, face and upper chest readable",
    "mcu": "a medium close-up, heads and torsos in frame",
    "ms": "a medium shot, bodies from about the thighs up",
    "loose": "a wider shot of the full bodies, keep the same backdrop",
}

# Framing phrases per distance key.
DIST = {
    "macro": ["very tight detail on skin or fabric", "very tight detail on an eye or a mouth", "very tight detail on a hand", "very tight detail on hair against a shoulder"],
    "ecu": ["extreme close-up of a face", "extreme close-up of hands", "extreme close-up of the two torsos meeting", "extreme close-up of eyes"],
    "cu": ["close-up of a face", "close-up profile of two bodies", "close-up from behind on the back and hips", "close-up on a mouth"],
    "mcu": ["medium close-up, faces and torsos together", "medium close-up over a shoulder", "medium close-up from the ribs to the hips", "medium close-up two-shot, eye contact"],
    "ms": ["medium shot, both bodies readable from the thighs up", "medium side shot of both bodies", "medium shot from behind", "medium three-quarter, hands and hips in"],
    "loose": ["wider two-body or three-body frame", "knees-to-head, bodies only, same backdrop", "wide enough for the group, still on the people", "full standing or kneeling bodies"],
}

# Camera angle phrases (free camera mode).
ANGLE = ["eye-level on the faces", "eye-level on the nearer face", "slightly high looking down the torso", "high from above the chests", "almost top-down on the laps", "straight down from above", "slightly low looking up the torso", "low from below", "from below between the ankles looking up", "true side profile at 90 degrees", "high profile looking down the face", "low profile looking up the chin", "three-quarter front", "three-quarter rear", "over the shoulder of the first body", "over the shoulder of the second body", "from the far hip across the lap", "between the two bodies", "from below looking up", "a slight 8 degree tilt", "straight into the face", "worm's-eye between the feet", "bird's-eye looking straight down the backs", "hip-height true side", "through the gap of the thighs", "peeking past a shoulder into the act"]

# First-person POV framing phrases.
POV = ["first-person looking down the body", "first-person looking at the other face", "eye-level first-person", "low first-person from the chest", "over-the-shoulder first-person", "first-person looking down at the join"]

# Camera move options: t = move phrase, lock = whether camera is static.
MOVE = [
    {"t": "locked-off static, only bodies move", "lock": True}, {"t": "locked with micro-sway", "lock": True},
    {"t": "very slow push-in toward the faces", "lock": False}, {"t": "slow push-in from a medium close-up into an extreme close-up", "lock": False},
    {"t": "slow pull-out that reveals more body, keep the same backdrop", "lock": False}, {"t": "slow 20° arc around the hips", "lock": False},
    {"t": "slow 30° orbit, distance locked", "lock": False}, {"t": "tilt up from the torso to the face, hold", "lock": False},
    {"t": "tilt down from eyes onto the chest", "lock": False}, {"t": "slow truck a few inches, horizon level", "lock": False},
    {"t": "rack focus hands → eyes", "lock": False}, {"t": "rack focus face → torso", "lock": False},
    {"t": "boom down the spine", "lock": False}, {"t": "boom up from the torso to the face", "lock": False},
    {"t": "vertical follow along the bodies, small travel", "lock": False}, {"t": "controlled handheld, no whip", "lock": False},
    {"t": "dirty handheld, slight shake", "lock": False}, {"t": "static first beat, tiny late push", "lock": False},
    {"t": "slow creep from over a shoulder into a side profile", "lock": False}, {"t": "push past a hip into the two bodies", "lock": False},
    {"t": "slow pan across the two bodies, horizon level", "lock": False}, {"t": "rise along the body from hips to face", "lock": False},
    {"t": "drop along the body from face to hips", "lock": False}, {"t": "creep in a few inches, no cut", "lock": False},
    {"t": "peek out from behind a shoulder into the act", "lock": False}, {"t": "short orbit around the hips, stay close", "lock": False},
]

# Sex-act definitions. "need" was a JS predicate over the subject list:
#   hasP(s)=some subject has a penis, hasV(s)=vulva, hasB(s)=breasts,
#   countP/countV=counts, T()=cfg.toys flag, len==n = subject count check.
# start/act = per-band (soft/mid/hard/raw) phrase pools.
ACTS = [
    {"id": "bj", "fam": ["oral", "mixed"], "pos": "oralpos", "min": 2, "need": "hasP(s)", "title": "blowjob", "doer": "mouth on cock",
     "start": {"soft": ["cock on the lower lip"], "mid": ["mouth already sealed on the head"], "hard": ["already sloppy on it"], "raw": ["already buried in the throat"]},
     "act": {"soft": ["long wet licks, tip-only suck"], "mid": ["steady half-shaft bob, hand on the base"], "hard": ["sloppy fast bob, deep every other stroke"], "raw": ["throat on purpose, choke and stay"]}},
    {"id": "cunn", "fam": ["oral", "mixed"], "pos": "oralpos", "min": 2, "need": "hasV(s)", "title": "cunnilingus", "doer": "mouth on pussy",
     "start": {"soft": ["breath on the pussy, not touching"], "mid": ["tongue already on the clit"], "hard": ["face already buried"], "raw": ["mouth open on it, messy"]},
     "act": {"soft": ["flat long licks"], "mid": ["pointed tongue on the clit, two fingers low"], "hard": ["face grinding, sucking"], "raw": ["eating it sloppy, thighs on the ears"]}},
    {"id": "rim", "fam": ["oral"], "pos": "doggy", "min": 2, "need": "always", "title": "rimming", "doer": "mouth on ass",
     "start": {"soft": ["hands spreading the ass"], "mid": ["tongue already on the hole"], "hard": ["face in, spit on the ass"], "raw": ["tongue buried"]},
     "act": {"soft": ["slow circles on the rim"], "mid": ["tongue in the hole, hand working in front"], "hard": ["wet and hungry"], "raw": ["using the hole with the tongue like they will fuck it next"]}},
    {"id": "hj", "fam": ["hands", "mixed"], "pos": "seated", "min": 2, "need": "hasP(s)", "title": "handjob", "doer": "hand on cock",
     "start": {"soft": ["fist resting on the shaft"], "mid": ["already stroking wet"], "hard": ["fast wet stroke"], "raw": ["two-handed, aiming it at a mouth or breasts"]},
     "act": {"soft": ["slow twist, thumb on the ridge"], "mid": ["even stroke, other hand on the balls"], "hard": ["fast and tight"], "raw": ["jerking it to spill now"]}},
    {"id": "finger", "fam": ["hands", "mixed"], "pos": "missionary", "min": 1, "need": "hasV(s)", "title": "fingering", "doer": "fingers in pussy",
     "start": {"soft": ["fingers on the slit"], "mid": ["already inside, slow curl"], "hard": ["finger-fucking, wet"], "raw": ["three fingers, palm slapping the clit"]},
     "act": {"soft": ["slow in-out, thumb on clit"], "mid": ["come-hither curl"], "hard": ["hard wrist"], "raw": ["hand used like a cock"]}},
    {"id": "trib", "fam": ["hands", "vaginal"], "pos": "side", "min": 2, "need": "countV(s) >= 2", "title": "tribbing", "doer": "pussy on pussy or thigh",
     "start": {"soft": ["cunts stacked, still"], "mid": ["already grinding"], "hard": ["wet grind, hips snapping"], "raw": ["riding the other pussy hard"]},
     "act": {"soft": ["slow circular grind"], "mid": ["steady scissor"], "hard": ["wet slap"], "raw": ["grind to wreck"]}},
    {"id": "titfuck", "fam": ["breast"], "pos": "breastpos", "min": 2, "need": "hasB(s) and hasP(s)", "title": "titfuck", "doer": "cock between breasts",
     "start": {"soft": ["cock laid in the cleavage"], "mid": ["already sliding through"], "hard": ["spit-slick cleavage, thrusting"], "raw": ["fucking the tits, head popping toward a tongue"]},
     "act": {"soft": ["slow slide"], "mid": ["even thrust, spit for slick"], "hard": ["fast, head punching out of cleavage"], "raw": ["tits used like a hole, mouth catching the outstroke"]}},
    {"id": "breastplay", "fam": ["breast"], "pos": "breastpos", "min": 1, "need": "hasB(s)", "title": "breast worship", "doer": "mouth and hands on breasts",
     "start": {"soft": ["mouth near a nipple"], "mid": ["already sucking a nipple"], "hard": ["face mashed in the breasts"], "raw": ["using the breasts hard"]},
     "act": {"soft": ["lick and kiss"], "mid": ["suck one, pinch the other"], "hard": ["motorboat, bounce"], "raw": ["rough grip on the breasts while hips slam"]}},
    {"id": "piv", "fam": ["vaginal", "mixed"], "pos": "missionary", "min": 2, "need": "hasV(s) and (hasP(s) or T())", "title": "vaginal sex", "doer": "cock or strap in pussy",
     "start": {"soft": ["head notched in the slit"], "mid": ["already inside, slow grind"], "hard": ["already bottoming out"], "raw": ["buried to the base, hips snapping"]},
     "act": {"soft": ["slow deep strokes, staying in"], "mid": ["full-length in-and-out"], "hard": ["hard fuck, hips slapping"], "raw": ["pounding, no pretty pause"]}},
    {"id": "anal", "fam": ["anal", "mixed"], "pos": "doggy", "min": 2, "need": "hasP(s) or T()", "title": "anal", "doer": "cock or strap in ass",
     "start": {"soft": ["head pressing on the hole"], "mid": ["already in, slow"], "hard": ["seated deep in the ass"], "raw": ["ass full, hips slapping"]},
     "act": {"soft": ["tiny strokes, staying deep"], "mid": ["steady ass-fuck"], "hard": ["hard thrusts, hole gripping the pull-out"], "raw": ["using the ass, deep and mean"]}},
    {"id": "soloM", "fam": ["hands"], "pos": "seated", "min": 1, "max": 1, "need": "len(s) == 1 and s[0].p", "title": "solo male", "doer": "hand on own cock",
     "start": {"soft": ["cock in hand, still"], "mid": ["already stroking"], "hard": ["fast wet stroke"], "raw": ["fucking his own fist"]},
     "act": {"soft": ["slow, watching the head"], "mid": ["even stroke"], "hard": ["hips into the fist"], "raw": ["aiming the head at the lens"]}},
    {"id": "soloF", "fam": ["hands", "breast", "solo"], "pos": "solo", "min": 1, "max": 1, "need": "len(s) == 1 and s[0].v", "title": "solo female", "doer": "hands on own body",
     "start": {"soft": ["hand over the pussy"], "mid": ["fingers circling the clit"], "hard": ["already fingering"], "raw": ["fucking herself with the hand"]},
     "act": {"soft": ["slow clit circles"], "mid": ["two fingers in, palm on clit"], "hard": ["hard and wet"], "raw": ["using herself sloppy"]}},
    {"id": "mirrorF", "fam": ["solo"], "pos": "solo", "min": 1, "max": 1, "need": "len(s) == 1 and s[0].v", "title": "mirror selfie", "doer": "female 1 films herself in a mirror",
     "start": {"soft": ["phone up, looking at her own reflection"], "mid": ["already filming, adjusting the angle"], "hard": ["phone low, body filling the mirror"], "raw": ["phone close, showing pussy and tits in the glass"]},
     "act": {"soft": ["tilts the phone, checks her face and chest"], "mid": ["turns in the mirror, shows ass then tits"], "hard": ["pulls clothes aside for the mirror"], "raw": ["holds the phone and touches herself while watching the reflection"]}},
    {"id": "showcaseF", "fam": ["solo"], "pos": "solo", "min": 1, "max": 1, "need": "len(s) == 1 and s[0].v", "title": "showcasing", "doer": "female 1 presents her body to camera",
     "start": {"soft": ["stands facing camera, still"], "mid": ["already turning, showing a side"], "hard": ["bent or arched, presenting tits and ass"], "raw": ["spread or bent, showing pussy to camera"]},
     "act": {"soft": ["shifts weight, lifts a hand through her hair"], "mid": ["turns slowly, shows chest, then ass"], "hard": ["leans in, pushes breasts together, looks at camera"], "raw": ["spreads herself for camera, no cute posing"]}},
    {"id": "undressF", "fam": ["solo"], "pos": "solo", "min": 1, "max": 1, "need": "len(s) == 1 and s[0].v", "title": "undressing", "doer": "female 1 takes clothes off",
     "start": {"soft": ["fully dressed as the clothing line says, hands on the first garment"], "mid": ["top already coming off"], "hard": ["clothes half off, tits out"], "raw": ["almost naked, last piece coming down"]},
     "act": {"soft": ["unbuttons or slides one strap"], "mid": ["pulls the top off, then the bottoms start down"], "hard": ["yanks clothes down her thighs"], "raw": ["strips the last piece and drops it"]}},
    {"id": "bendF", "fam": ["solo"], "pos": "solo", "min": 1, "max": 1, "need": "len(s) == 1 and s[0].v", "title": "bend and look back", "doer": "female 1 bends for camera",
     "start": {"soft": ["standing, starts to fold forward"], "mid": ["already bent, looking back"], "hard": ["ass high, looking back at camera"], "raw": ["bent, reaches back and spreads"]},
     "act": {"soft": ["bends a little, looks over her shoulder"], "mid": ["holds the bend, ass to camera"], "hard": ["arches harder, looks back"], "raw": ["stays bent and touches herself"]}},
    {"id": "spitroast", "fam": ["group", "mixed", "oral"], "pos": "grouppos", "min": 3, "need": "countP(s) >= 2 or (countP(s) >= 1 and T())", "title": "spit-roast", "doer": "mouth + hole at once",
     "start": {"soft": ["one cock at the lips, one notched at the hips"], "mid": ["already taking both ends slow"], "hard": ["already used at both ends"], "raw": ["mouth and hole full, both moving"]},
     "act": {"soft": ["front lets the mouth work, back grinds"], "mid": ["shared rhythm"], "hard": ["both pumping"], "raw": ["both ends used, middle body taking it"]}},
    {"id": "dp", "fam": ["group", "anal", "vaginal"], "pos": "grouppos", "min": 3, "need": "hasV(s) and (countP(s) >= 2 or T())", "title": "double penetration", "doer": "pussy and ass filled together",
     "start": {"soft": ["one in the pussy, the other pressing the ass"], "mid": ["both inside, tiny moves"], "hard": ["both pumping"], "raw": ["stuffed, both moving"]},
     "act": {"soft": ["alternating tiny strokes"], "mid": ["same-tempo double fuck"], "hard": ["hard DP"], "raw": ["no pause, both holes used"]}},
    {"id": "twoOnOneOral", "fam": ["group", "oral"], "pos": "grouppos", "min": 3, "need": "hasP(s) or hasV(s)", "title": "two mouths on one", "doer": "two mouths, one body",
     "start": {"soft": ["two faces close, not sharing yet"], "mid": ["two tongues already on it"], "hard": ["fighting for it"], "raw": ["both mouths sloppy on the same cock or cunt"]},
     "act": {"soft": ["taking turns"], "mid": ["one on shaft or hole, one on head or clit"], "hard": ["messy share"], "raw": ["both at once"]}},
    {"id": "rideAndSit", "fam": ["group", "mixed"], "pos": "grouppos", "min": 3, "need": "(hasP(s) or T()) and hasV(s)", "title": "ride + facesit", "doer": "one riding, one sitting on a face",
     "start": {"soft": ["one hovering the cock, one hovering the mouth"], "mid": ["already riding and sitting"], "hard": ["bouncing on both ends"], "raw": ["using the body under them"]},
     "act": {"soft": ["slow sit, slow grind"], "mid": ["shared bounce"], "hard": ["face and cock both used"], "raw": ["smother and ride"]}},
    {"id": "watch", "fam": ["group"], "pos": "grouppos", "min": 3, "need": "always", "title": "third watches / holds", "doer": "couple plus a close third",
     "start": {"soft": ["third close, watching"], "mid": ["third already touching"], "hard": ["third holding the receiver open"], "raw": ["third in the hair while the other slams"]},
     "act": {"soft": ["watcher strokes a thigh"], "mid": ["watcher kisses the receiver during"], "hard": ["watcher feeds a cock or breast into the mouth"], "raw": ["watcher pins them so they can get wrecked"]}},
]

# Phase narration headers (prepended context for the phase of a shot).
PHASES = {
    "notch": "PHASE: notched / about to enter or about to take it in the mouth. Almost still. Show the connection before the rhythm.",
    "enter": "PHASE: first real strokes. Sliding in. Depth increasing. Do not jump to pounding.",
    "mid": "PHASE: mid-act. Full rhythm. In-and-out readable.",
    "deep": "PHASE: buried / bottomed out / held deep. Tiny movement, pressure, clench.",
    "wreck": "PHASE: wrecked. Sloppy, noisy, composure gone. Same position as the rest of the scene.",
    "finish": "PHASE: the finish beat. Stay on the bodies. No cutaway.",
    "after": "PHASE: afterglow. Still joined or just pulled out. Breath, leak, hands, no new position.",
}

# Mood adjectives per intensity band.
MOOD = {
    "soft": ["tender, unhurried", "intimate and quiet", "worshipful"],
    "mid": ["focused and filthy", "skilled, mutual", "hungry but paced"],
    "hard": ["urgent, sloppy", "pornographic", "sweaty and loud"],
    "raw": ["obscene on purpose", "mean and wet and wanted", "animal, no dignity in the frame"],
}

# Hand-placement phrases (one picked when cfg.hands is on).
HANDS = ["fist in the hair", "hands spreading ass or thighs", "hand on a throat, shown pressure, air still happening", "hands on breasts from behind", "nails in an ass cheek", "hand reaching back to pull them deeper", "two hands slamming a waist", "fingers in the receiver's mouth", "hand on the clit while a cock works a hole", "holding ankles apart", "pinning wrists", "guiding a head onto a cock"]

# Roughness beats (one picked when cfg.rough is on).
ROUGH = ["spank timed to a thrust", "hair wrapped around a fist", "hand on the throat, wanted", "held down by the back of the neck", "spank and grab"]

# Eye/gaze beats.
EYES = ["eye contact over the act", "looks back over a shoulder", "eyes shut, mouth open", "giver watches the hole take it", "looks into lens / POV on the deep stroke", "eyes wet, still looking up"]

# Kiss beats.
KISS = ["sloppy kiss between strokes", "bite then kiss on a shoulder", "open mouths together while hips keep moving"]

# Dirty-talk phrases per band.
TALK = {"soft": ["stay", "a hum, no words"], "mid": ["look at me", "don't stop"], "hard": ["take it", "again"], "raw": ["fucking take it", "more"]}

# Ambient sound adjectives per band.
AUDIO = {
    "soft": ["breath, faint wet, skin; no music", "soft mouth, one small moan; no score"],
    "mid": ["wet in-out or suction, two breathing patterns; no music", "rhythmic skin, swallowed moan; room tone"],
    "hard": ["hip slap, wet hole or sloppy mouth, a groan; no music", "obscene close wetness; no score"],
    "raw": ["ugly wet: gag or slap, grunt on the shove; no music", "close-mic wreck, then back on it; no score"],
}

# Per-stage foley paragraphs (used in overall_soundscape and per-shot audio).
AUDIO_STAGE = {
    "intro": "Quiet ambient. Soft breath. Light cloth rustle when a hand moves. No sex wet. No mouths eating.",
    "tease": "Quiet ambient. Fabric slide. A small exhale. Skin on cloth. No oral wet. No chew.",
    "hj": "Close-mic hand on cock: skin slide, a wet fist, a soft stroke tick. Breath. No mouth on food. No chew. No crunch.",
    "bj": "Close-mic blowjob foley only: wet lips sealing on skin, saliva strings, a soft suction release when her mouth slides, air through her nose, a muffled hum. The wet is spit on skin, not food. No chewing. No crunch. No biting. No eating. No chips. No jaw grinding. Teeth stay still except to hold a seal.",
    "breast": "Skin on skin. Soft breast-flesh slide. Her breath. A faint wet smear, not a mouth on food.",
    "sex": "Skin slap at the hips. Wet of a hole, not a mouth eating. Two breath patterns. A moan on the thrust. No chew. No crunch.",
    "cum": "A held breath, then wet pulses and drip on skin. If her mouth is on him: saliva and swallow of fluid, not food. No chew. No crunch. Cum sound is a wet pulse and drip, not a gunshot, not a 50 cal.",
}

# Scenario format packs. label is the Russian UI label (kept verbatim; it is
# also echoed into the prompt by formatBeat: "FORMAT {label}. {line}").
# spine goes into the header; intro/tease/hj/bj/breast/sex/cum prefix the
# matching stage's action text; talk/mood are defaults injected into the cfg.
FORMAT = {
    "interview": {
        "label": "interview / casting",
        "spine": "FORMAT interview. She treats the lens as the person asking. Each act is her next answer. He is the other body in frame.",
        "intro": "FORMAT interview. She faces the lens. She nods or talks a short line. Hands stay ordinary. SFW.",
        "tease": "FORMAT interview. The question is her body. She opens or lifts cloth a little, then checks the lens.",
        "hj": "FORMAT interview. She answers with her hands on his cock. She glances at the lens between strokes. No mouth.",
        "bj": "FORMAT interview. She answers with her mouth on his cock. She looks up at the lens, then back to the work.",
        "breast": "FORMAT interview. She answers with her chest on his cock. She still plays to the lens.",
        "sex": "FORMAT interview. She answers by taking him. She throws one look at the lens on a thrust.",
        "cum": "FORMAT interview. Last answer. He cums. She keeps a sliver of lens-awareness.",
        "talk": "dirty", "mood": "focused",
    },
    "bet": {
        "label": "lost bet",
        "spine": "FORMAT lost bet. She lost. He collects. Each act is the next piece of the debt.",
        "intro": "FORMAT bet. She just lost. She scoffs, swallows, looks at him, looks away. SFW. She does not leave.",
        "tease": "FORMAT bet. First pay is showing. She moves cloth like she hates that she has to, then keeps going.",
        "hj": "FORMAT bet. Her fist on his cock is pay. She can glare or smirk. Stroke stays on him. No mouth.",
        "bj": "FORMAT bet. Her mouth on his cock is pay. She can glare up while she works.",
        "breast": "FORMAT bet. Her chest on his cock is pay. She presses because she owes it.",
        "sex": "FORMAT bet. Taking him is pay. She can still look pissed while her hips move.",
        "cum": "FORMAT bet. Last pay. He cums. She takes it because the bet said so.",
        "talk": "orders", "mood": "brat",
    },
    "stuck": {
        "label": "stuck",
        "spine": "FORMAT stuck. She cannot leave the Picture 1 stance. Acts happen from that hold.",
        "intro": "FORMAT stuck. She tests the hold: a pull, a twist, a look down. She cannot step out. SFW.",
        "tease": "FORMAT stuck. Cloth shifts because she twists in place. She cannot cover fully.",
        "hj": "FORMAT stuck. Her hands reach what they can and stroke him from that hold. No mouth.",
        "bj": "FORMAT stuck. Her mouth takes him from that hold. She cannot pull off and walk.",
        "breast": "FORMAT stuck. Her chest is used from that hold. She cannot back out.",
        "sex": "FORMAT stuck. He takes her in that hold. She stays pinned to the stance.",
        "cum": "FORMAT stuck. He cums while she is still held. She cannot leave after.",
        "talk": "protest", "mood": "teary",
    },
    "robbed": {
        "label": "robbed",
        "spine": "FORMAT robbed. He has her. Acts happen because he keeps her in frame.",
        "intro": "FORMAT robbed. She freezes, then tracks his hands. Breath short. SFW.",
        "tease": "FORMAT robbed. He moves her cloth. She flinches, then holds still.",
        "hj": "FORMAT robbed. He puts her hand on his cock. She strokes because he keeps it there. No mouth.",
        "bj": "FORMAT robbed. He puts her mouth on his cock. She works because he holds her there.",
        "breast": "FORMAT robbed. He uses her chest on his cock. She braces.",
        "sex": "FORMAT robbed. He takes her. She stays in his grip.",
        "cum": "FORMAT robbed. He cums on or in her. She stays where he put her.",
        "talk": "protest", "mood": "unwilling",
    },
    "webcam": {
        "label": "paid webcam",
        "spine": "FORMAT webcam. She sells the act to the lens. She angles work so the lens can read it.",
        "intro": "FORMAT webcam. She greets the lens. A small wave or a practiced smile. SFW.",
        "tease": "FORMAT webcam. She shows for the lens. Slow cloth, then a check that the frame still has her.",
        "hj": "FORMAT webcam. She strokes him toward the lens. She looks at the work, then at the lens. No mouth.",
        "bj": "FORMAT webcam. She sucks him for the lens. She turns just enough that the mouth-work reads.",
        "breast": "FORMAT webcam. She puts her chest on him for the lens. She presents the squeeze.",
        "sex": "FORMAT webcam. She takes him for the lens. She sells the bounce.",
        "cum": "FORMAT webcam. He cums for the lens. She holds the finish where it can be seen.",
        "talk": "dirty", "mood": "proud",
    },
    "walkin": {
        "label": "walk-in",
        "spine": "FORMAT walk-in. He is already in her scene. She was not ready. The acts start from that shock.",
        "intro": "FORMAT walk-in. She startles. Eyes go to him. A half-step or a held breath. SFW.",
        "tease": "FORMAT walk-in. Hands find cloth because he is here. She covers, then the cloth still moves.",
        "hj": "FORMAT walk-in. After the shock her hand is on his cock. The stroke starts clumsy, then holds. No mouth.",
        "bj": "FORMAT walk-in. After the shock her mouth is on his cock. She commits mid-take.",
        "breast": "FORMAT walk-in. After the shock her chest is on him. Close and sudden.",
        "sex": "FORMAT walk-in. After the shock he is inside her. The take starts from the surprise.",
        "cum": "FORMAT walk-in. He cums in the same surprise. She is still catching up.",
        "talk": "dirty", "mood": "shy",
    },
    "makeup": {
        "label": "make-up sex",
        "spine": "FORMAT make-up. The fight just ended. Heat is still on their faces. Acts are the make-up.",
        "intro": "FORMAT make-up. Jaw tight. She looks at him like the last word is unfinished. SFW.",
        "tease": "FORMAT make-up. Hands grab cloth, not gentle. She pulls him or he pulls her.",
        "hj": "FORMAT make-up. Her fist on his cock is angry and hungry at once. No mouth.",
        "bj": "FORMAT make-up. Her mouth on his cock is the first yield. Still sharp in the eyes.",
        "breast": "FORMAT make-up. Her chest on him is rough press, not a show.",
        "sex": "FORMAT make-up. He takes her hard to end the fight. She meets it.",
        "cum": "FORMAT make-up. He cums. The fight ends on that pulse.",
        "talk": "dirty", "mood": "angry",
    },
    "firstdeal": {
        "label": "first-time deal",
        "spine": "FORMAT first deal. She agreed. She has not done these acts before. Motion stays unsure.",
        "intro": "FORMAT first deal. She agreed. She looks at him, then down. Hands fidget. SFW.",
        "tease": "FORMAT first deal. Cloth moves slow and awkward. She checks his face after each small reveal.",
        "hj": "FORMAT first deal. First time her hands work his cock. Grip hunts a rhythm. She watches the fist. No mouth.",
        "bj": "FORMAT first deal. First time her mouth is on his cock. Shallow, careful, she learns the depth.",
        "breast": "FORMAT first deal. First time her chest is on him. She adjusts, unsure of the press.",
        "sex": "FORMAT first deal. First time he is inside her. She takes him slow and reads the feeling.",
        "cum": "FORMAT first deal. He cums. She startles at the pulse, then stays.",
        "talk": "off", "mood": "scared",
    },
    "cuck": {
        "label": "someone watches",
        "spine": "FORMAT watched. A third body already in this scene watches. She knows.",
        "intro": "FORMAT watched. Her eyes flick to the watcher, then back. She knows she is seen. SFW.",
        "tease": "FORMAT watched. She shows while being watched. A pause to see if the watcher is still looking.",
        "hj": "FORMAT watched. She strokes him while being watched. She can look at the work or at the watcher. No mouth.",
        "bj": "FORMAT watched. She sucks him while being watched. Shame or heat in the glance aside.",
        "breast": "FORMAT watched. Her chest is on him while being watched. She presents and hides in the same beat.",
        "sex": "FORMAT watched. He takes her while being watched. She feels the extra eyes.",
        "cum": "FORMAT watched. He cums while being watched. She cannot hide the finish.",
        "talk": "dirty", "mood": "shy",
    },
    "blackmail": {
        "label": "blackmail pay",
        "spine": "FORMAT blackmail. She pays. Each act is the next piece of the pay.",
        "intro": "FORMAT blackmail. She knows why she is here. Face goes flat or tight. SFW.",
        "tease": "FORMAT blackmail. She starts to pay. Cloth moves because she has to, not because she wants to.",
        "hj": "FORMAT blackmail. This stroke is pay. Her fist works. Her face stays elsewhere. No mouth.",
        "bj": "FORMAT blackmail. This suck is pay. She keeps her mouth on him because the pay is due.",
        "breast": "FORMAT blackmail. This chest work is pay. She presses because she was told.",
        "sex": "FORMAT blackmail. This fuck is pay. She takes him to close the debt.",
        "cum": "FORMAT blackmail. He cums. Last pay. She stays through it.",
        "talk": "orders", "mood": "unwilling",
    },
}

# Camera style packs. label is the Russian UI label (kept verbatim; it is
# echoed into the prompt by formatBeat). d = default distance key;
# pov = force-POV flag; perShot (cinematic, interview) = per-shot-index camera
# overrides with keys d/framing/ang/move/speed/stab/lock/join ("join" is a cut
# transition sentence).
STYLE = {
    "home": {
        "label": "домашняя ручная съёмка",
        "d": "mcu",
        "cam": "STYLE homemade handheld. Same cheap phone or camcorder for every shot. Dirty handheld, small shake. Autofocus hunts once. Frame is a little late. Not a studio. Not a trip to a new angle.",
        "framing": "medium close-up on the female. About one arm away from her. Her face and chest fill the frame. The backdrop barely reads.",
        "ang": "same homemade angle on her every shot: eye-level or a little high, slightly crooked, aimed at her face then her chest. Do not switch to a new side of her.",
        "lock": "CAMERA LOCK: stay on the female. Same distance, about an arm away. Same high-or-eye homemade angle. Do not jump to a wide new backdrop.",
        "stab": "dirty handheld, slight shake",
        "move": "controlled handheld, no whip, keep her face in frame",
        "speed": "camera speed slow",
        "audio": "Phone mic close. Ambient hiss. Handling noise. Uneven level. No studio mix.",
    },
    "set": {
        "label": "порносъёмка (сет)",
        "d": "mcu",
        "cam": "STYLE porn set. Same clean paid camera for every shot. Tripod or slider. Skin lit on purpose. Not a phone. Not security-cam.",
        "framing": "medium close-up on the female. About two metres from her. Her torso and face composed in the center.",
        "ang": "same set angle on her every shot: eye-level, straight-on or a mild three-quarter on her face. Do not drop the camera low unless written. Do not go behind her unless the act already faces that way.",
        "lock": "CAMERA LOCK: stay on the female. Same medium-close distance. Same eye-level set angle. Do not change lens or side mid-take.",
        "stab": "tripod-still",
        "move": "locked-off static, only bodies move",
        "speed": "camera speed slow",
        "audio": "Clean close-mic. No extra hiss. No phone handling. Still no music.",
    },
    "selfie": {
        "label": "селфи на телефон",
        "d": "cu",
        "cam": "STYLE phone selfie. She holds the phone. Front camera. Arm-length. Same phone, same hand, every shot. Not a third-person crew.",
        "framing": "close-up front camera on the female. Arm-length from her face. Her face is large. Her body falls off the bottom.",
        "ang": "same selfie angle on her every shot: phone at her eye line or a little above, pointed back at her face. The lens stays in front of her. Do not flip to a rear crew shot.",
        "lock": "CAMERA LOCK: stay on the female's face from the phone she holds. Arm-length. Front camera. Same angle every shot.",
        "stab": "controlled handheld",
        "move": "micro-sway only, keep her face centered",
        "speed": "camera speed very slow",
        "pov": True,
        "audio": "Phone mic at arm length. Voice and wet are close and clipped. No boom mic.",
    },
    "sec": {
        "label": "камера наблюдения",
        "d": "loose",
        "cam": "STYLE security camera. Same high corner for every shot. Wide, a little soft. Static lock. No HUD text invented. Not handheld. Not selfie.",
        "framing": "loose wide from the high corner. The female is readable in the same backdrop, not a face close-up. Bodies small in the frame.",
        "ang": "same security angle every shot: high corner looking down on her, about three to four metres away, slightly wide. Do not come down to her face. Do not move the box.",
        "lock": "CAMERA LOCK: same high corner. Same distance from her. Looking down on the female. Static. No new camera.",
        "stab": "tripod-still",
        "move": "locked-off static, only bodies move",
        "speed": "camera speed very slow",
        "audio": "Thin distant mic. Bodies a bit far. No close spit. No music.",
    },
    "webcam": {
        "label": "стрим с веб-камеры ПК",
        "d": "mcu",
        "cam": "STYLE PC webcam livestream. Same laptop webcam for every shot. Fixed laptop webcam. Do not invent furniture. No chat UI invented.",
        "framing": "medium close-up from the laptop on the female. About an arm from her face. Face and torso.",
        "ang": "same webcam angle on her every shot: slightly high, looking down at her face and chest. The lens stays in front of her. Do not walk around her.",
        "lock": "CAMERA LOCK: stay on the female from the laptop. Same distance. Same slight-high front angle. Fixed cam.",
        "stab": "webcam-still, cheap digital",
        "move": "locked-off static, only bodies move",
        "speed": "camera speed very slow",
        "audio": "Laptop mic close. Room hiss. Keyboard click optional. Voice and wet close and thin. No studio mix. No music. No stream stinger.",
    },
    "mirror": {
        "label": "съёмка через зеркало",
        "d": "mcu",
        "cam": "STYLE mirror filming. Same phone filming the same mirror. The female is the reflection. Phone rectangle stays in the glass. Same backdrop as Picture 1.",
        "framing": "medium close-up on the female in the mirror. About two arms from the glass. Phone rectangle visible. Her face and chest in the reflection.",
        "ang": "same mirror angle every shot: straight into the glass at her chest height. The lens looks at her reflection, not a second camera behind her.",
        "lock": "CAMERA LOCK: stay on the female in the mirror. Same distance to the glass. Same chest-height angle. Do not leave the mirror.",
        "stab": "controlled handheld, the phone hand shakes a little",
        "move": "micro-sway only, keep her reflection centered",
        "speed": "camera speed very slow",
        "pov": True,
        "audio": "Phone mic close. Room bounce. Voice and wet bounce. No music. No crew.",
    },
    "nightcam": {
        "label": "дешёвая камера, ночь",
        "d": "cu",
        "cam": "STYLE cheap camcorder night. Same on-camera light. Near skin is hot. Background crushed black. Same camcorder every shot.",
        "framing": "close-up on the female. About one metre from her. Hot face and chest. The backdrop falls off in the dark.",
        "ang": "same nightcam angle on her every shot: slightly high from the light, aimed at her face. Do not swing around her. Do not go wide.",
        "lock": "CAMERA LOCK: stay on the female. About one metre. Same slightly-high lit angle. Same camcorder.",
        "stab": "dirty handheld, slight shake",
        "move": "controlled handheld, no whip, keep her face in the light",
        "speed": "camera speed slow",
        "audio": "On-camera mic. Room hiss. Light handling noise. Wet and breath close. No music. No boom.",
    },
    "camcorder": {
        "label": "дешёвая камера",
        "d": "cu",
        "cam": "STYLE cheap camcorder. Same handheld camcorder every shot. Tape grain. Autofocus hunts once. White balance a little off. On-camera mic. Do not add extra light. Do not crush the image to night. Not a phone selfie. Not security-cam. Not cinema.",
        "framing": "close-up on the female. About one metre from her. Face and chest.",
        "ang": "same camcorder angle on her every shot: slightly high handheld, aimed at her face. Do not swing around her. Do not go wide.",
        "lock": "CAMERA LOCK: stay on the female. About one metre. Same slightly-high camcorder angle. Same tape.",
        "stab": "dirty handheld, slight shake",
        "move": "controlled handheld, no whip, keep her face in frame",
        "speed": "camera speed slow",
        "audio": "On-camera mic. Room hiss. Handling noise. Wet and breath close. No music. No boom.",
    },
    "vertical": {
        "label": "вертикальный сторис-кроп",
        "d": "cu",
        "cam": "STYLE vertical story / TikTok crop. Same tall center column every shot. Head and torso first. No like count. No username. No sticker UI.",
        "framing": "close-up tall crop on the female. About an arm from her. Face and torso stacked in the center. Sides empty or dark.",
        "ang": "same story angle on her every shot: slightly high phone, pointed down a little at her face, center-weighted. Do not cut to a wide side view.",
        "lock": "CAMERA LOCK: stay on the female in the tall center. Arm-length. Same slightly-high phone angle. Do not change crop.",
        "stab": "controlled handheld",
        "move": "micro-sway only, stay locked on her center stack",
        "speed": "camera speed very slow",
        "pov": True,
        "audio": "Phone mic close. Voice and wet clipped. Room small. No music. No UI sounds.",
    },
    "cinematic": {
        "label": "кинематографичная съёмка",
        "d": "ms",
        "cam": "STYLE cinematic coverage. Paid cinema camera. Soft key light. Shallow focus. Each shot is a new setup on the female. Not a phone. Not security-cam. Not a locked webcam.",
        "framing": "medium shot on the female, backdrop falls soft",
        "ang": "eye-level three-quarter on her face",
        "stab": "steadicam-smooth",
        "move": "slow push-in toward her",
        "speed": "camera speed slow",
        "lock": "CAMERA: cinematic. New angle each shot. Stay on the female.",
        "audio": "Close boom. Clean breath and skin. Ambient low. No music. No phone hiss.",
        "perShot": [
            {"d": "ms", "framing": "medium shot on the female, about two metres from her, same backdrop soft behind her", "ang": "eye-level three-quarter on her face", "move": "slow push-in toward her face", "speed": "camera speed slow", "stab": "steadicam-smooth", "lock": "SHOT CAMERA: open on her. Push in from medium to medium-close. Do not cut yet.", "join": "Cinematic open. Camera closes in on her. "},
            {"d": "cu", "framing": "close-up on the female's face only, about half a metre, shoulders fall off", "ang": "eye-level, straight on her eyes", "move": "locked-off static, only her face moves", "speed": "camera speed very slow", "stab": "tripod-still", "lock": "SHOT CAMERA: cut to her face. Tight. Hold.", "join": "Cut to her face. Close-up. "},
            {"d": "mcu", "framing": "medium close-up on her chest and the act, her face in the top of frame", "ang": "slightly low, looking up her torso", "move": "slow rise up her body to her face", "speed": "camera speed slow", "stab": "slider-smooth", "lock": "SHOT CAMERA: from her body up to her face. Same female.", "join": "Cut. Camera travels up her. "},
            {"d": "cu", "framing": "close-up profile of her face, ear and cheek, the act at the edge", "ang": "true 90° profile on her, eye-level", "move": "slow orbit a few degrees around her face, stop", "speed": "camera speed very slow", "stab": "steadicam-smooth", "lock": "SHOT CAMERA: profile on her. Short orbit. Stay on her face.", "join": "Cut to her profile. Camera creeps. "},
            {"d": "ms", "framing": "medium shot from behind her shoulder, looking past her at him, her cheek in the foreground", "ang": "over her shoulder, her face in the near edge", "move": "locked-off static, only bodies move", "speed": "camera speed slow", "stab": "tripod-still", "lock": "SHOT CAMERA: over her shoulder. She stays the near subject.", "join": "Cut over her shoulder. "},
            {"d": "ecu", "framing": "extreme close-up on her mouth or eyes, skin fills the frame", "ang": "eye-level, centimetres from her face", "move": "locked-off static, only her skin moves", "speed": "camera speed very slow", "stab": "tripod-still", "lock": "SHOT CAMERA: extreme close on her. Do not pull out.", "join": "Cut. Extreme close on her. "},
        ],
    },
    "bodycam": {
        "label": "бодикамера / нагрудная GoPro",
        "d": "mcu",
        "cam": "STYLE bodycam. Chest-mounted action cam. Wide. Low. Shakes with his walk. Same mount every shot. Not a crew. Not a phone selfie.",
        "framing": "wide bodycam on the female. She fills most of the frame. Horizon tilts with his chest.",
        "ang": "same bodycam angle every shot: from his chest, looking slightly down at her. Lens close. Do not lift off his body.",
        "lock": "CAMERA LOCK: stay on the female from the chest cam. Same wide close distance. Same down-angle. Mounted. Shake is his body.",
        "stab": "dirty handheld, chest-mounted shake",
        "move": "camera follows his chest, small bounce, no whip",
        "speed": "camera speed medium",
        "pov": True,
        "audio": "On-cam mic on his chest. Breath close. Bodies thud. Harsh. No music.",
    },
    "gif": {
        "label": "порно-GIF-луп",
        "d": "cu",
        "cam": "STYLE porn GIF. Tight crop. Tiny move. Same frame every shot like a loop. No new angle. Keep the same backdrop tight.",
        "framing": "close-up on the join and her. Tight. Almost no background.",
        "ang": "same GIF angle every shot: locked on her at the act. Do not reframe.",
        "lock": "CAMERA LOCK: same tight crop on the female. Same distance. Same angle. Loop energy. Do not pull out.",
        "stab": "tripod-still",
        "move": "micro-sway only, keep the same crop",
        "speed": "camera speed very slow",
        "audio": "Close wet and breath only. Keep the same backdrop tight. No music.",
    },
    "interview": {
        "label": "интервью, потом действие",
        "d": "mcu",
        "cam": "STYLE interview then drop. Shot 1 is a talking-head on her. Later shots drop to the act. Same camera family. Same backdrop.",
        "framing": "medium close-up on the female face first",
        "ang": "eye-level on her face",
        "stab": "tripod-still",
        "move": "locked-off static, only she moves",
        "speed": "camera speed slow",
        "lock": "CAMERA: interview first, then drop to the act. Stay on the female.",
        "audio": "Close voice first. Then close wet. No music.",
        "perShot": [
            {"d": "mcu", "framing": "medium close-up on her face and shoulders. Talking-head. The act is not the frame yet.", "ang": "eye-level, straight on her face", "move": "locked-off static, only her face moves", "speed": "camera speed very slow", "stab": "tripod-still", "lock": "SHOT CAMERA: interview on her face. Hold.", "join": "Interview on her face. "},
            {"d": "cu", "framing": "close-up drop to the act on her. Face still readable at the top.", "ang": "slightly high on her", "move": "slow drop along her body to the act", "speed": "camera speed slow", "stab": "slider-smooth", "lock": "SHOT CAMERA: drop from her face to the act.", "join": "Drop to the act. "},
            {"d": "mcu", "framing": "medium close-up on her and the act. Face and body.", "ang": "eye-level three-quarter on her", "move": "locked-off static, only bodies move", "speed": "camera speed slow", "stab": "tripod-still", "lock": "SHOT CAMERA: hold on her and the act.", "join": "Hold on the act. "},
            {"d": "cu", "framing": "close-up on her face while the act continues below", "ang": "eye-level on her eyes", "move": "locked-off static, only her face moves", "speed": "camera speed very slow", "stab": "tripod-still", "lock": "SHOT CAMERA: back to her face. Act still going.", "join": "Back to her face. "},
        ],
    },
    "flash": {
        "label": "вспышка клубного телефона",
        "d": "mcu",
        "cam": "STYLE club-phone flash. Phone camera. On-camera flash pops. Do not rewrite the place light. Flash is the phone, not a lamp, not a window.",
        "framing": "medium close-up on the female. Phone distance. Harsh flash on her skin. Background falls.",
        "ang": "same phone angle every shot: eye-level or a little high on her face. Front. Do not walk around her.",
        "lock": "CAMERA LOCK: stay on the female from the phone. Same distance. Flash pops. Do not invent a new light.",
        "stab": "dirty handheld, slight shake",
        "move": "controlled handheld, no whip, keep her in frame",
        "speed": "camera speed medium",
        "audio": "Phone mic. Harsh. Ambient noise. Flash is picture only. No music.",
    },
    "hidden": {
        "label": "скрытая камера",
        "d": "ms",
        "cam": "STYLE hidden cam. Low secret camera. Dirty. A bit of foreground blocks the edge. Same lock every shot. Not a high corner. Not a phone in a hand. Not security HUD.",
        "framing": "medium shot from low, looking at the female. She is readable. A dark edge or object sits in the near foreground and does not move. Same backdrop.",
        "ang": "same hidden angle every shot: low, slightly off to one side, looking up or level at her. Do not rise to her face as a new camera. Do not walk around her.",
        "lock": "CAMERA LOCK: stay on the female from the hidden low cam. Same distance. Same side. Same obstruction. Do not replace the backdrop.",
        "stab": "cheap static, tiny noise",
        "move": "locked-off static, only bodies move",
        "speed": "camera speed very slow",
        "audio": "Thin distant mic. Bodies a bit far. No close spit. No music. No HUD beep.",
    },
}

# Finish-beat phrases, keyed by the finish select value.
FINISH = {
    "creampie": ["come inside, stay buried and pulse", "hold after the spill, slow pull, it leaks"],
    "pullout": ["pull out and finish on ass, back or stomach", "ropes across breasts or an open mouth"],
    "facial": ["facial on lips and cheeks, mouth open", "cum on the tongue held to camera / POV"],
    "swallow": ["in the mouth, visible swallow, lick clean", "come in the mouth, giver stays on"],
    "mutual": ["receiver comes first, clench drags the other over", "one comes on a tongue while the other spills inside"],
}

# Her clothing / wardrobe lines, keyed by the clothes select value.
CLOTHES = {
    "asref": "CLOTHING: keep the exact garments from Picture 1. Same fabric, same color, same neckline, same hem. Do not redesign the wardrobe. Do not add a second outfit.",
    "aside": "CLOTHING: same garments as Picture 1. Only pull fabric aside at the crotch or breasts as far as this act needs. Seams and color stay. Do not swap the outfit.",
    "half": "CLOTHING: sex through the Picture 1 clothes. Same garments stay on the body. Fly, hem or crotch panel is the only opening. Fabric bunches. Do not strip her naked.",
    "off": "CLOTHING: already naked. Bare skin only. No new shirt. No new pants. Do not dress her mid-clip.",
    "underwear": "CLOTHING: bra and panties only. Everyday cotton or simple lace. Straps on her shoulders. Waistband on her hips. No outer clothes.",
    "bralette": "CLOTHING: a soft bralette and boyshorts. Thin straps. Boyshorts sit high on the hip. No jeans. No dress.",
    "lingerie": "CLOTHING: a matching lingerie set still on while they fuck. Visible straps, lace edges, underwire or elastic. Garters only if already in this look. Do not add a dress over it.",
    "longline": "CLOTHING: a longline bra that sits down her ribs and matching panties. Band is wide. Cups hold. No outer clothes.",
    "sheer": "CLOTHING: sheer fabric over her body. Nipples and the join readable through the weave. Seams still there. Not invisible.",
    "meshtop": "CLOTHING: an open mesh top over underwear. Holes show skin. Bra or nipples readable through the mesh. Bottoms still on under it.",
    "stockings": "CLOTHING: stockings clipped to a garter belt. Crotch free. Garter straps on her thighs. No pants.",
    "thighhighs": "CLOTHING: thigh-high stockings only. Elastic holds on her thighs. Nothing else on her torso or hips.",
    "fishnet": "CLOTHING: fishnet tights or a fishnet bodystocking. A hole at the crotch or the weave ripped there. Diamond pattern readable on her legs.",
    "robe": "CLOTHING: a robe hanging open off her shoulders. Belt undone. Inner lining shows. She is bare or in underwear under it.",
    "kimono": "CLOTHING: a kimono or wrap robe open down the front. Sleeves hang. The sash is loose. Bare skin in the gap.",
    "towel": "CLOTHING: one towel wrapped once and slipping. A hand may hold the top. The tuck is failing. Bare thigh and chest show.",
    "shirtup": "CLOTHING: her top is pulled up above her breasts. Breasts out. The rest of the garment bunches under her arms. Bottoms can stay.",
    "dressup": "CLOTHING: her dress is shoved up around her waist in a thick ring of fabric. Hips and the join are bare. The bodice can stay on.",
    "skirtnone": "CLOTHING: skirt still on. No underwear. The skirt can lift. Bare under it.",
    "jeanszip": "CLOTHING: jeans or trousers still on her hips. Fly open. Cock or pussy out the zipper. Belt maybe hanging. The rest of the jeans stay.",
    "jeansthigh": "CLOTHING: jeans shoved to mid-thigh. Denim bunched. Cock or pussy out. She cannot kick them off in this beat.",
    "pantsdown": "CLOTHING: pants or shorts around her ankles. She is hobbled by them. Bare from the waist down except that puddle of fabric.",
    "cargodown": "CLOTHING: cargo pants shoved down. Pockets and side bags still readable. Fabric at her thighs or knees. The join is out.",
    "hoodie": "CLOTHING: an oversized hoodie only. Hem hits upper thigh. Hood can sit on her back. No pants.",
    "hoodiesocks": "CLOTHING: an oversized hoodie and ankle socks only. Hoodie hem on her thighs. Socks wrinkled. No pants.",
    "croptop": "CLOTHING: a short crop top, midriff bare, no bottoms. The hem sits under her bust or on her ribs.",
    "tankpanty": "CLOTHING: a tank top and panties only. Tank straps on her shoulders. Panty waistband on her hips.",
    "unbutton": "CLOTHING: a button shirt open down the front. Buttons undone. Panels hang. Bra or bare chest in the gap. Bottoms can stay.",
    "night": "CLOTHING: a sleep shirt or nightgown ridden up her hips. Soft fabric bunched. Bare under it.",
    "gym": "CLOTHING: gym kit yanked aside. Sports bra or workout shorts still in frame. Elastic and logos readable. The join is open.",
    "sportsbra": "CLOTHING: a sports bra and tight shorts. One cup or the crotch is yanked aside. Compression fabric still on.",
    "jersey": "CLOTHING: an oversized sports jersey and nothing under it. Hem on her thighs. Number or stripes readable.",
    "bikini": "CLOTHING: a bikini. The bottom is pulled aside at the join or the top is tugged off a breast. Ties and triangles stay.",
    "microkini": "CLOTHING: a micro bikini. Tiny triangles. Strings on her hips. Fabric barely covers. Can be pulled aside.",
    "slingkini": "CLOTHING: a sling bikini. One strip of fabric between her breasts and between her legs. Most of her torso is bare.",
    "swim": "CLOTHING: a one-piece swimsuit peeled off her shoulders, bunched at her waist. The join can be pulled aside.",
    "latex": "CLOTHING: latex or wet-look. Shine on the rubber. A zipper or panel is open at the crotch. It still grips her body.",
    "leather": "CLOTHING: leather straps or a harness over bare skin. Buckles and rings readable. No full catsuit unless already this look.",
    "cagebra": "CLOTHING: a strap cage or harness bra. Straps frame her breasts. Bottoms optional. Metal rings readable.",
    "bodysuit": "CLOTHING: a bodysuit still on. Crotch snapped or pulled aside. Shoulder straps stay. Fabric stretched on her torso.",
    "pantyhose": "CLOTHING: pantyhose ripped open at the crotch. Runs on her thighs. The waistband still on.",
    "tights": "CLOTHING: opaque tights ripped open at the crotch. Thick fabric. A hole with frayed edges. Waistband on.",
    "socks": "CLOTHING: naked except socks. Ankle or crew socks. Bare everything else.",
    "heels": "CLOTHING: naked except heels. Straps or pumps still on her feet. Bare body.",
    "office": "CLOTHING: office blouse open, buttons undone, and a pencil or straight skirt hiked to her hips. She still looks dressed from far away.",
    "suit": "CLOTHING: suit trousers open at the fly or shoved down. A dress shirt can stay. Belt hanging.",
    "tie": "CLOTHING: a button shirt and a loose tie. Tie still around her neck. Shirt open. Bottoms out of the way.",
    "scrubs": "CLOTHING: medical scrubs. Drawstring pants yanked down or aside. Top can stay. No new hospital set.",
    "waitapron": "CLOTHING: a short wait dress and an apron. Skirt and apron hiked. Ties at her waist still knotted.",
    "coat": "CLOTHING: a coat or jacket on, bare underneath. Lapels open. No shirt. No pants.",
    "winterbare": "CLOTHING: a heavy winter coat on, bare underneath. Coat hangs open. Boots optional. No street added.",
    "apron": "CLOTHING: an apron only. Neck strap and waist ties. Bare back and sides. No dress under it.",
    "teejeans": "CLOTHING: a cotton tee tucked or hanging, and closed jeans. Belt done. Fly zipped. Everyday casual. No skin at the crotch yet.",
    "tankshorts": "CLOTHING: a tank top and closed shorts. Straps on her shoulders. Shorts buttoned. Casual.",
    "bandtee": "CLOTHING: a printed band tee and closed jeans. Graphic readable. Casual. Fly zipped.",
    "tiedtee": "CLOTHING: a tee knotted at her waist, midriff showing, and closed bottoms. Knot sits at her ribs.",
    "sundress": "CLOTHING: a simple sundress, closed. Thin straps. Hem on her thighs. No underwear rule unless the mess select says so.",
    "slipdress": "CLOTHING: a bias slip dress, closed. Thin satin or silk. Spaghetti straps. Hem moves when she does.",
    "sweater": "CLOTHING: a knit sweater and closed pants. Ribbing at the cuffs. Casual, covered.",
    "offshoulder": "CLOTHING: an off-shoulder sweater. One or both shoulders bare. Knit slouch. Bottoms closed.",
    "cardigan": "CLOTHING: a cardigan over a top and a skirt. Buttons maybe undone. Casual covered look.",
    "flannel": "CLOTHING: an open flannel shirt over a tank, and closed bottoms. Plaid readable. Sleeves can be rolled.",
    "sweats": "CLOTHING: a sweatshirt and sweatpants or a lounge set. Soft fleece. Drawstring. Closed.",
    "satinpj": "CLOTHING: a satin pajama set. Piping on the collar. Button top and matching pants. Soft sheen.",
    "buttoned": "CLOTHING: a shirt buttoned to the collar or chest and slacks with the fly closed. Neat.",
    "polo": "CLOTHING: a polo shirt and a skirt. Collar sits. Skirt closed. Casual neat.",
    "denimskirt": "CLOTHING: a denim skirt and a tank. Skirt buttoned. Tank straps on.",
    "overalls": "CLOTHING: denim overalls. One strap dropped off her shoulder. Bib hangs. Can be open at the hip.",
    "jumpsuit": "CLOTHING: a jumpsuit zipped or buttoned. One piece from chest to ankle. Closed.",
    "jumpsuitopen": "CLOTHING: a jumpsuit unzipped to her navel or lower. The join can be reached. Sleeves still on.",
    "raincoat": "CLOTHING: a raincoat over ordinary clothes. Plastic or coated fabric. Hood down. Clothes under it stay.",
    "bootscoat": "CLOTHING: a long coat and boots, fully dressed. Coat closed or half-open over real clothes. No bare-under unless the mess select wrecks it.",
    "yoga": "CLOTHING: a matching yoga set. Crop or tank and leggings. Compression fabric. Closed at the waist.",
    "bikeshorts": "CLOTHING: tight bike shorts pulled aside at the crotch. Waistband still on. A top can stay.",
    "rippedtee": "CLOTHING: a ripped tee. Holes show skin. Collar stretched. Bottoms can stay.",
    "wetshirt": "CLOTHING: a wet light shirt clinging. Fabric translucent on her breasts. Seams dark with water. Bottoms can stay.",
    "wetjeans": "CLOTHING: wet jeans, fly open. Dark denim clinging to her thighs. The join is out the zipper.",
    "thongonly": "CLOTHING: a thong only. Thin waistband. Back string. Nothing on her chest.",
    "crotchless": "CLOTHING: crotchless panties. The hole is built in. A bra can stay. No pants.",
    "openbra": "CLOTHING: an open or unhooked bra, nothing else. Cups hang. Straps slack.",
    "cupless": "CLOTHING: a cupless bra that frames her breasts and does not cover nipples. Bottoms optional.",
    "pasties": "CLOTHING: pasties on her nipples and almost no other fabric. Bare hips.",
    "jock": "CLOTHING: a jock or pouch only. Straps on her hips. The rest bare.",
    "minidress": "CLOTHING: a tiny minidress riding up. Hem at her hips or higher. Tight fabric.",
    "bodycon": "CLOTHING: a tight bodycon dress shoved up her waist. Stretch fabric. Bodice still on.",
    "cocktaildress": "CLOTHING: a cocktail dress shoved up. Fancy fabric, maybe sequins or satin. Hiked for the act. Same backdrop.",
    "cutoutdress": "CLOTHING: a dress with cutouts at the waist, chest or hips. Skin in the holes. Can be hiked.",
    "wrapdress": "CLOTHING: a wrap dress falling open. The tie is loose. Inner lining and bare skin in the gap.",
    "pvc": "CLOTHING: pvc or vinyl. Hard shine. Zipper open at the crotch. It still holds her shape.",
    "corset": "CLOTHING: a corset cinched on her waist. Crotch free. Laces or hooks on the back. No pants.",
    "bustier": "CLOTHING: a bustier only. Structured cups and boning. No bottoms.",
    "collaronly": "CLOTHING: a collar on her neck, otherwise bare. Buckle or ring readable.",
    "chokerheels": "CLOTHING: a choker and heels only. Bare body between them.",
    "bodychain": "CLOTHING: a body chain only. Thin metal on her torso and hips. Otherwise bare.",
    "maid": "CLOTHING: an adult maid dress hiked. Short skirt and apron. White trim. The join is reachable. Not a child costume.",
    "bunny": "CLOTHING: a bunny-style bodysuit. Panel open at the crotch. Straps and cuffs can stay. No new club.",
    "silkwrap": "CLOTHING: a silk wrap slipping off her shoulder. Thin cloth. Bare skin under the slide.",
    "velvetgown": "CLOTHING: a heavy velvet gown shoved up. Thick pile. Hiked at the waist. Bodice can stay.",
    "ritualrobe": "CLOTHING: a ritual robe open down the front. Long cloth. Bare in the gap. No new temple.",
    "travelercloak": "CLOTHING: a travel cloak still on. Clothes under it yanked aside. Cloak hangs.",
    "chainmail": "CLOTHING: ornamental mail or metal scales over bare skin. Gaps show flesh. Not full armor.",
    "elfsilk": "CLOTHING: thin otherworld silk. Almost sheer. Draped, not a modern tee.",
    "priestess": "CLOTHING: a priestess wrap. One shoulder bare. Cloth knotted. No new temple.",
    "goddess": "CLOTHING: a goddess drape. Cloth over one shoulder and around her hips. A lot of skin. No new hall.",
    "sari": "CLOTHING: a sari slipping. Pleats and a pallu. Midriff can show. Fabric still wrapped, not a new room.",
    "cheongsam": "CLOTHING: a cheongsam or tight collar dress hiked. Side slit open high. Fabric still on her torso.",
    "coinbelt": "CLOTHING: a coin belt on her hips and a thin veil or top. Bare midriff. Coins readable.",
    "hospitalgown": "CLOTHING: a thin hospital gown, open at the back or hiked. Ties at the neck. No new ward.",
    "tornnight": "CLOTHING: a torn nightgown hanging off one shoulder. Ripped hem. Soft fabric wrecked.",
    "dirtyshirt": "CLOTHING: one dirty oversized shirt only. Stains. Hem on her thighs. No pants.",
    "ragged": "CLOTHING: ragged clothes hanging off her. Torn edges. Not a full new outfit.",
    "occult": "CLOTHING: a black occult robe, open. Dark cloth. Bare in the gap. No new chapel.",
    "wetblack": "CLOTHING: soaked black fabric clinging to her. Dark, heavy with water. Shape of her body through it.",
    "widow": "CLOTHING: a black dress ripped at the chest or hiked. Formal fabric wrecked. Same backdrop.",
    "jewelry": "CLOTHING: jewelry only. Necklace, earrings, maybe a bracelet. Otherwise bare.",
    "socksandshirt": "CLOTHING: an oversized shirt and socks only. Shirt hem on her thighs. No pants.",
    "boytee": "CLOTHING: an oversized boyfriend tee only. Shoulders slouch. Hem mid-thigh. No pants.",
    "onesie": "CLOTHING: a onesie or romper unzipped down the front. The zipper is low. Bare in the gap.",
}

# How rumpled her clothes are, keyed by the clothMess select value.
CLOTH_MESS = {
    "asref": "CLOTHING MESS: keep the same rumple as Picture 1. Do not suddenly wreck or neat the clothes.",
    "neat": "CLOTHING MESS: clothes still sit on her the way they were put on. Hems even. Nothing bunched around her knees. Fabric is worn, not a pile.",
    "displaced": "CLOTHING MESS: clothes are shoved and bunched. One shoulder bare or one thigh stripped. Fabric in a roll at her waist or under her breasts. Still the same garments.",
    "wrecked": "CLOTHING MESS: clothes are wrecked. Stretched neck, spit on the fabric, waistband around her thighs or knees. Same garments, ruined on her body.",
}

# His clothing lines, keyed by the manCloth select value.
MAN_CLOTHES = {
    "asref": "MAN CLOTHING: like the reference. Do not redesign his clothes.",
    "nude": "MAN CLOTHING: he is nude. No shirt. No pants. Cock out.",
    "jeanszip": "MAN CLOTHING: his jeans or trousers are open. His cock is out the fly. The rest of the jeans stay on.",
    "jeansdown": "MAN CLOTHING: his jeans are shoved to mid-thigh. Cock out. Shirt may stay.",
    "pantsdown": "MAN CLOTHING: his pants are at his ankles. Cock out.",
    "underwear": "MAN CLOTHING: underwear only. Cock out or tenting.",
    "boxers": "MAN CLOTHING: boxers. His cock is out the fly or the waist.",
    "briefs": "MAN CLOTHING: briefs pulled aside. Cock out.",
    "jock": "MAN CLOTHING: jock only. Cock out the pouch.",
    "tee": "MAN CLOTHING: a tee still on. Bottom off. Cock out.",
    "shirtopen": "MAN CLOTHING: shirt open. Cock out. No closed fly.",
    "suit": "MAN CLOTHING: suit trousers open, shirt still on. Cock out the fly.",
    "sweats": "MAN CLOTHING: sweats shoved down. Cock out.",
    "shorts": "MAN CLOTHING: shorts pulled aside. Cock out.",
    "robe": "MAN CLOTHING: open robe. Cock out.",
    "towel": "MAN CLOTHING: a towel slipping. Cock out.",
    "hoodie": "MAN CLOTHING: hoodie still on. Cock out. No closed fly.",
    "tank": "MAN CLOTHING: tank top on. Bottom off. Cock out.",
    "belt": "MAN CLOTHING: belt open. Pants shoved. Cock out.",
    "cargo": "MAN CLOTHING: cargo pants open. Cock out.",
    "leather": "MAN CLOTHING: leather pants open. Cock out.",
    "track": "MAN CLOTHING: tracksuit pants shoved down. Cock out.",
    "socks": "MAN CLOTHING: socks only. Cock out.",
    "apron": "MAN CLOTHING: apron only. Cock out.",
    "raincoat": "MAN CLOTHING: raincoat open. Bare under. Cock out.",
    "uniform": "MAN CLOTHING: uniform shirt on. Fly open. Cock out.",
    "wettee": "MAN CLOTHING: wet tee clinging. Bottom off. Cock out.",
    "coat": "MAN CLOTHING: coat on. Nothing under. Cock out.",
    "tie": "MAN CLOTHING: shirt and tie on. Fly open. Cock out.",
}

# Location lines, keyed by the place select value.
PLACE = {
    "asref": "LOCATION: like the reference. Do not invent a new place. Do not copy a different room from another image.",
    "bedroom": "LOCATION: bedroom, rumpled bed. No house tour.",
    "sheets": "LOCATION: crumpled sheets only. No room tour.",
    "hotel": "LOCATION: hotel bed, one lamp, anonymous.",
    "motel": "LOCATION: cheap motel, dark wood, a mirror if it helps the frame.",
    "sofa": "LOCATION: living-room sofa.",
    "floor": "LOCATION: on a carpet or rug. Camera stays on the bodies.",
    "wall": "LOCATION: up against an interior wall.",
    "door": "LOCATION: against a closed door.",
    "kitchen": "LOCATION: kitchen counter or table edge.",
    "bath": "LOCATION: bathroom, tile and a mirror fragment.",
    "shower": "LOCATION: shower, steam, wet tile.",
    "tub": "LOCATION: edge of a bathtub.",
    "desk": "LOCATION: desk or office table.",
    "office": "LOCATION: empty office after hours. No extra workers.",
    "chair": "LOCATION: armchair or dining chair.",
    "stairs": "LOCATION: indoor stair landing.",
    "window": "LOCATION: interior in front of a window.",
    "closet": "LOCATION: tight closet or dressing space.",
    "fitting": "LOCATION: fitting room, mirror, curtain. No shoppers.",
    "car": "LOCATION: back seat of a car.",
    "frontseat": "LOCATION: front seat, console in the way.",
    "garage": "LOCATION: parked garage, dim.",
    "hallway": "LOCATION: apartment hallway. Empty.",
    "balcony": "LOCATION: private balcony at night.",
    "rooftop": "LOCATION: rooftop terrace at night.",
    "pool": "LOCATION: pool edge or sun lounger.",
    "hot tub": "LOCATION: hot tub rim.",
    "gym": "LOCATION: empty gym or locker bench. No crowd.",
    "sauna": "LOCATION: sauna bench, wood slats.",
    "studio": "LOCATION: seamless studio, dark paper.",
    "loft": "LOCATION: loft, big windows, mattress on the floor.",
    "penthouse": "LOCATION: penthouse glass. City only as bokeh.",
    "cabin": "LOCATION: cabin bedroom, wood walls.",
    "tent": "LOCATION: tent interior.",
    "woods": "LOCATION: woods. No path tour. Bodies stay the frame.",
    "beach": "LOCATION: beach towel at dusk.",
    "alley": "LOCATION: alley wall at night. No crowd.",
    "clubbath": "LOCATION: club bathroom stall. Empty.",
    "greenroom": "LOCATION: backstage couch.",
    "van": "LOCATION: cargo van interior.",
    "laundry": "LOCATION: laundry room, machines in the background, no tour.",
    "porch": "LOCATION: back porch at night. No street.",
    "diner": "LOCATION: empty diner booth at night. No staff.",
    "castlebed": "LOCATION: castle bed, heavy drapes, stone behind. No castle tour.",
    "stonehall": "LOCATION: stone hall, torch light. Empty.",
    "dungeon": "LOCATION: stone chamber, furs on the floor. Empty.",
    "temple": "LOCATION: temple interior, candles. Empty.",
    "throne": "LOCATION: throne dais, empty court.",
    "tavernloft": "LOCATION: tavern loft, wood beams. No patrons in frame.",
    "tower": "LOCATION: high tower room, one night window.",
    "faegrove": "LOCATION: glowing grove. No path tour. Bodies stay the frame.",
    "icehall": "LOCATION: pale ice hall. Empty.",
    "ruins": "LOCATION: overgrown ruins at night. No tour.",
    "abandoned": "LOCATION: abandoned house, peeling paper. Empty.",
    "attic": "LOCATION: attic, low beams, dust light.",
    "basement": "LOCATION: basement, one bulb. Empty.",
    "chapel": "LOCATION: empty chapel at night.",
    "greenhouse": "LOCATION: dead greenhouse, glass and dry plants.",
    "morgue": "LOCATION: empty tiled back room. No staff.",
    "theater": "LOCATION: dark unused theater room. Empty.",
    "graveedge": "LOCATION: cemetery edge at night. No crowd.",
    "flooded": "LOCATION: flooded room, standing water.",
    "redroom": "LOCATION: spare room in red light. Empty.",
    "warehouse": "LOCATION: empty warehouse corner.",
}

# Lighting lines, keyed by the placeLight select value.
PLACE_LIGHT = {
    "asref": "Light stays as the reference.",
    "day": "Daylight from a window.",
    "lamps": "Warm lamps.",
    "dim": "Dim, practicals only.",
    "neon": "Cheap neon / sign spill.",
    "night": "Night interior.",
    "harsh": "Harsh overhead.",
    "candle": "Candle light, warm flicker.",
    "moon": "Cold moonlight through a window.",
    "storm": "Storm light, brief flashes.",
    "red": "Red practical light.",
}

# Random-pick pools: for every cfg key listed here, value "any" means pick a
# random member of the pool (resolveAnys). Lists are transcribed verbatim.
POOL = {
    "introDo": ["look", "wave", "sit", "walk", "turn", "talk", "lean", "hair", "smile", "stand", "sitedge", "cross", "stretch", "yawn", "phone", "door", "mirror", "fixcloth", "sitclose", "nod", "point", "drink", "wait", "kneelsoft", "tiehair", "kickshoes", "sitfloor", "leanwall", "lookhim", "shrug", "adjustsit", "foldhands", "rubeyes", "comein", "takehand", "sitwith", "leanhim", "kisscheek", "callhim", "patseat", "hugbrief", "turnaway", "stepback", "pushhand", "armsx", "lookdoor", "sitfar", "shakehead", "holdcloth", "glare", "scoff", "snaptalk", "argue", "shove", "slaphand", "staredown", "block", "turnback", "refusesit", "finger", "jaw"],
    "teaseDo": ["strap", "hem", "turn", "lift", "bend", "touch", "unzip", "thigh", "neck", "sitopen", "flash", "waist", "asidep", "hips", "grind", "lap", "crawl", "lieback", "squeeze", "ass", "licklips", "hairtoss", "pullhim", "trace", "kissneck", "ear", "straddle", "pushdown", "guidehand", "bitelip", "skirtup", "braoff", "peek", "spin", "onallfours", "foot", "undobelt", "shirtuphim", "closehips", "whisper", "mirrorpose", "hippop", "slowundress", "braopen", "pantypeel", "wetfinger", "sitonthigh", "handswalk", "lookbackcrawl", "rubclothed", "showpanties", "kneesqueeze", "startundress", "puthishand", "openforhim", "pullhip", "showhim", "kissdown", "climbhim", "beglook", "coverup", "holdhem", "twistaway", "pushchest", "clampknees", "fixstrap", "turnface", "grabwrist"],
    "hjPos": ["kneel", "lap", "sit", "side", "himlie", "stand", "between", "proneglute", "behind", "spoon", "sitspread", "shestand", "bothkneel", "shelie", "thighsit", "fly", "under", "overhand"],
    "hjGrip": ["one", "two", "twist", "head", "balls"],
    "hjLook": ["cam", "him", "cock", "down", "shut", "side"],
    "hjTempo": ["slow", "even", "fast"],
    "hjExp": ["first", "new", "exp", "master"],
    "bjExp": ["first", "new", "exp", "master"],
    "brExp": ["first", "new", "exp", "master"],
    "sxExp": ["first", "new", "exp", "master"],
    "bjPos": ["kneel", "edge", "stand", "lap", "floor", "side", "lyingback", "edgehead", "himlie", "sitbetween", "wall", "bededge", "allfours", "squat", "sidelie", "sixty", "under", "chair", "desk", "coucharm", "table", "reverse", "pronehim", "liftleg", "doublehand", "betweenlegs", "standing69", "proneglute"],
    "bjDepth": ["lick", "lips", "half", "full", "deep"],
    "bjLook": ["up", "cam", "him", "cock", "down", "shut", "side"],
    "bjWet": ["clean", "wet", "sloppy"],
    "bjTempo": ["slow", "even", "fast"],
    "bjHands": ["base", "two", "balls", "thighs", "none"],
    "brKind": ["titfuck", "worship", "squeeze", "lick", "reverse", "under", "spit", "slaphead", "presswalk", "nipplesuck", "facepress", "oil", "holdout", "sideboob"],
    "sxKind": ["vaginal", "anal"],
    "sxPos": ["missionary", "doggy", "cowgirl", "standing", "side", "seated", "folded", "prone"],
    "sxBounce": ["none", "small", "medium", "hard"],
    "cumWhere": ["mouth", "swallow", "tongue", "face", "lips", "breasts", "stomach", "back", "ass", "hand", "inside", "pullout"],
    "mood": ["calm", "shy", "eager", "hungry", "playful", "needy", "intense", "spaced", "tired", "sweet", "brat", "focused", "drunk", "scared", "proud", "angry", "sleepy", "smug", "lost", "teary", "giggle", "unwilling", "veryunwilling"],
    "fPleasure": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "inFace": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "teFace": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "hjFace": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "bjFace": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "brFace": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "sxFace": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "cuFace": ["cold", "flat", "held", "warm", "moan", "loud", "gasp", "cryout", "scream", "orgasm"],
    "manLook": ["asref", "normal", "ugly", "handsome", "rough"],
    "manBody": ["asref", "skinny", "average", "fat", "obese", "muscular", "stocky"],
    "manMood": ["calm", "hungry", "rough", "gentle", "smug", "focused", "eager"],
    "manAge": ["18", "20", "25", "30", "40", "50", "60", "70", "80", "90"],
    "manSkin": ["pale", "fair", "light", "olive", "tan", "brown", "dark", "deep"],
    "manCloth": ["nude", "jeanszip", "jeansdown", "pantsdown", "underwear", "boxers", "briefs", "jock", "tee", "shirtopen", "suit", "sweats", "shorts", "robe", "towel", "hoodie", "tank", "belt", "cargo", "leather", "track", "socks", "apron", "raincoat", "uniform", "wettee", "coat", "tie"],
    "fAge": ["18", "20", "25", "30", "40", "50", "60", "70", "80", "90"],
    "relate": ["strangers", "couple", "married", "ex", "dad", "mom", "brother", "sister"],
    "manLen": ["tiny", "short", "average", "long", "verylong"],
    "manGirth": ["thin", "slim", "average", "thick", "enormous"],
    "inLook": ["cam", "him", "down", "shut", "side", "body"],
    "teLook": ["cam", "him", "down", "shut", "side", "back", "body"],
    "brLook": ["cam", "him", "cock", "down", "shut", "side", "body"],
    "sxLook": ["cam", "him", "down", "shut", "side", "back", "body"],
    "cuLook": ["cam", "him", "cock", "down", "shut", "side"],
    "cuQty": ["drops", "little", "normal", "heavy", "huge", "gallons"],
    "cuFinish": ["pulse", "leak", "dribble", "ropes", "spray"],
    "stylePack": ["home", "set", "selfie", "sec", "webcam", "mirror", "nightcam", "camcorder", "vertical", "cinematic", "bodycam", "gif", "interview", "flash", "hidden"],
    "sceneFormat": ["interview", "bet", "stuck", "robbed", "webcam", "walkin", "makeup", "firstdeal", "cuck", "blackmail"],
    "m2Do": ["watch", "holdhair", "holdhips", "cockface", "shoulder", "beside", "guidehead", "off"],
    "f2Do": ["watch", "holdbreast", "holdhand", "kisscheek", "kneelbeside", "help", "off"],
    "fBreast": ["flat", "small", "medium", "large", "huge"],
    "fHeight": ["tiny", "short", "average", "tall", "giant"],
    "fFrame": ["petite", "slim", "average", "thick", "fat", "obese"],
    "fAss": ["flat", "small", "round", "big", "huge"],
    "inRH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "inLH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "teRH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "teLH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "bjRH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "bjLH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "brRH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "brLH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "sxRH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "sxLH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "cuRH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "cuLH": ["none", "hip", "waist", "ass", "breast", "thigh", "head", "hair", "face", "shoulder", "back", "cock", "surface"],
    "inDist": ["ecu", "cu", "mcu", "ms", "loose", "macro"],
    "teDist": ["ecu", "cu", "mcu", "ms", "loose", "macro"],
    "hjDist": ["ecu", "cu", "mcu", "ms", "loose", "macro"],
    "bjDist": ["ecu", "cu", "mcu", "ms", "loose", "macro"],
    "brDist": ["ecu", "cu", "mcu", "ms", "loose", "macro"],
    "sxDist": ["ecu", "cu", "mcu", "ms", "loose", "macro"],
    "cuDist": ["ecu", "cu", "mcu", "ms", "loose", "macro"],
    "inHeight": ["floor", "hip", "chest", "eye", "above"],
    "teHeight": ["floor", "hip", "chest", "eye", "above"],
    "hjHeight": ["floor", "hip", "chest", "eye", "above"],
    "bjHeight": ["floor", "hip", "chest", "eye", "above"],
    "brHeight": ["floor", "hip", "chest", "eye", "above"],
    "sxHeight": ["floor", "hip", "chest", "eye", "above"],
    "cuHeight": ["floor", "hip", "chest", "eye", "above"],
    "inAngle": ["front", "profile", "3q", "3qrear", "behind", "ots", "ots2", "between", "lowup", "highdown", "worm", "bird", "hip", "dutch", "throughlegs", "pov"],
    "teAngle": ["front", "profile", "3q", "3qrear", "behind", "ots", "ots2", "between", "lowup", "highdown", "worm", "bird", "hip", "dutch", "throughlegs", "pov"],
    "hjAngle": ["front", "profile", "3q", "3qrear", "behind", "ots", "ots2", "between", "lowup", "highdown", "worm", "bird", "hip", "dutch", "throughlegs", "pov"],
    "bjAngle": ["front", "profile", "3q", "3qrear", "behind", "ots", "ots2", "between", "lowup", "highdown", "worm", "bird", "hip", "dutch", "throughlegs", "pov"],
    "brAngle": ["front", "profile", "3q", "3qrear", "behind", "ots", "ots2", "between", "lowup", "highdown", "worm", "bird", "hip", "dutch", "throughlegs", "pov"],
    "sxAngle": ["front", "profile", "3q", "3qrear", "behind", "ots", "ots2", "between", "lowup", "highdown", "worm", "bird", "hip", "dutch", "throughlegs", "pov"],
    "cuAngle": ["front", "profile", "3q", "3qrear", "behind", "ots", "ots2", "between", "lowup", "highdown", "worm", "bird", "hip", "dutch", "throughlegs", "pov"],
    "inMove": ["static", "push", "pull", "arc", "orbit", "pan", "tilt", "truck", "boom", "rise", "drop", "rack", "follow", "creep", "peek", "hand", "shake"],
    "teMove": ["static", "push", "pull", "arc", "orbit", "pan", "tilt", "truck", "boom", "rise", "drop", "rack", "follow", "creep", "peek", "hand", "shake"],
    "hjMove": ["static", "push", "pull", "arc", "orbit", "pan", "tilt", "truck", "boom", "rise", "drop", "rack", "follow", "creep", "peek", "hand", "shake"],
    "bjMove": ["static", "push", "pull", "arc", "orbit", "pan", "tilt", "truck", "boom", "rise", "drop", "rack", "follow", "creep", "peek", "hand", "shake"],
    "brMove": ["static", "push", "pull", "arc", "orbit", "pan", "tilt", "truck", "boom", "rise", "drop", "rack", "follow", "creep", "peek", "hand", "shake"],
    "sxMove": ["static", "push", "pull", "arc", "orbit", "pan", "tilt", "truck", "boom", "rise", "drop", "rack", "follow", "creep", "peek", "hand", "shake"],
    "cuMove": ["static", "push", "pull", "arc", "orbit", "pan", "tilt", "truck", "boom", "rise", "drop", "rack", "follow", "creep", "peek", "hand", "shake"],
    "inSpeed": ["vslow", "slow", "medium", "fast", "vfast", "absurd"],
    "teSpeed": ["vslow", "slow", "medium", "fast", "vfast", "absurd"],
    "hjSpeed": ["vslow", "slow", "medium", "fast", "vfast", "absurd"],
    "bjSpeed": ["vslow", "slow", "medium", "fast", "vfast", "absurd"],
    "brSpeed": ["vslow", "slow", "medium", "fast", "vfast", "absurd"],
    "sxSpeed": ["vslow", "slow", "medium", "fast", "vfast", "absurd"],
    "cuSpeed": ["vslow", "slow", "medium", "fast", "vfast", "absurd"],
}

# Camera height option phrases (keyed by camHeight / per-stage Height selects).
HEIGHT = {
    "floor": "camera height on the surface plane",
    "hip": "camera at hip height",
    "chest": "camera at chest height",
    "eye": "camera at eye level",
    "above": "camera above the bodies looking down",
    "overhead": "true overhead, looking straight down",
}

# Locked camera angle option phrases (keyed by camAngle selects).
ANGLELOCK = {
    "front": "straight-on front angle",
    "profile": "true 90° profile",
    "3q": "three-quarter front angle",
    "3qrear": "three-quarter rear angle",
    "ots": "over-the-shoulder from body A",
    "ots2": "over-the-shoulder from her, looking at him",
    "ots-g": "over-the-shoulder from body A",
    "ots-r": "over-the-shoulder from body B",
    "behind": "from behind the hips",
    "between": "between the two bodies, center of frame",
    "lowup": "low angle looking up the body",
    "highdown": "high angle looking down the torso",
    "worm": "worm's-eye from below looking up the bodies",
    "bird": "bird's-eye looking straight down",
    "hip": "hip-height true side angle",
    "dutch": "slight dutch tilt, horizon a few degrees off",
    "throughlegs": "camera shoots through the gap of the thighs",
    "pov": "point of view, first person, looking through these eyes at the other body",
}

# Camera move option phrases (keyed by camMove selects).
MOVELOCK = {
    "static": "locked-off static, only bodies move",
    "push": "slow push-in toward the faces",
    "pull": "slow pull-out that reveals more body, keep the same backdrop",
    "arc": "slow 25° arc around the hips, distance locked",
    "orbit": "slow orbit around the two bodies, stay close, keep the same backdrop",
    "pan": "slow pan across the bodies, horizon level",
    "tilt": "tilt between the face and the torso, then hold",
    "truck": "slow truck a few inches left or right, horizon level",
    "boom": "boom along the body, small travel",
    "rise": "rise along the body from hips to face",
    "drop": "drop along the body from face to hips",
    "rack": "rack focus between face and torso",
    "follow": "camera follows the body motion, small travel, no whip",
    "creep": "slow creep in a few inches, no cut",
    "peek": "peek out from behind a shoulder into the act",
    "hand": "controlled handheld, no whip",
    "shake": "dirty handheld, slight shake, no whip",
}

# Camera speed option phrases (keyed by camSpeed selects).
SPEED = {"vslow": "camera speed very slow, almost crawling", "veryslow": "camera speed very slow, almost crawling", "slow": "camera speed slow", "medium": "camera speed medium, even", "fast": "camera speed fast", "vfast": "camera speed very fast", "absurd": "camera speed absurdly fast, whip-quick"}

# Camera stability option phrases.
STAB = {"locked": "tripod-still", "micro": "micro-sway only", "hand": "controlled handheld", "dirty": "dirty handheld, slight shake"}

# Lens option phrases.
LENS = {"tight": "tight long-lens compression", "normal": "normal lens, natural scale", "wide": "wide enough to read the bodies, keep the same backdrop"}

# Camera follow/subject option phrases.
FOLLOW = {"join": "keep the two bodies centered", "face": "keep the face readable", "hips": "keep the hips readable", "both": "keep face and torso both in frame"}

# Ordered stage list (intro -> cum).
STAGES = ["intro", "tease", "hj", "bj", "breast", "sex", "cum"]

# Stage -> phase mapping used when building the shot list.
STAGE_PHASE_MAP = {"intro": "notch", "tease": "enter", "hj": "mid", "bj": "mid", "breast": "mid", "sex": "mid", "cum": "finish"}

# Stage -> FORMAT slot name (formatBeat: introF->intro, teaseF->tease,
# titfuck/breastplay->breast, piv/anal->sex, cumF->cum).
STAGE_FORMAT_SLOT = {"introF": "intro", "teaseF": "tease", "hj": "hj", "bj": "bj", "titfuck": "breast", "breastplay": "breast", "piv": "sex", "anal": "sex", "cumF": "cum"}

# Stage -> per-stage camera select prefix (stageCam reads "{prefix}Dist" etc).
STAGE_CAM_PREFIX = {"intro": "in", "tease": "te", "hj": "hj", "bj": "bj", "breast": "br", "sex": "sx", "cum": "cu"}

# Arc name -> phase progression for a multi-shot scene (phaseFor).
PHASE_ARCS = {
    "build": ["notch", "enter", "mid", "wreck", "finish", "after"],
    "oral2sex": ["notch", "enter", "mid", "mid", "finish", "after"],
    "hold": ["mid", "mid", "deep", "mid", "wreck", "finish"],
    "wreck": ["mid", "deep", "wreck", "wreck", "finish", "after"],
    "after": ["mid", "wreck", "finish", "after", "after", "after"],
    "stripsex": ["notch", "enter", "mid", "mid", "wreck", "finish"],
    "teaseonly": ["notch", "enter", "mid", "mid", "deep", "mid"],
    "onehold": ["mid", "mid", "mid", "deep", "mid", "mid"],
    "closer": ["mid", "mid", "deep", "deep", "wreck", "finish"],
    "facebody": ["notch", "enter", "mid", "deep", "wreck", "finish"],
    "mirror": ["notch", "enter", "mid", "deep", "mid", "after"],
    "selfie": ["notch", "enter", "mid", "mid", "deep", "after"],
    "undress": ["notch", "enter", "mid", "mid", "deep", "after"],
    "showcase": ["notch", "enter", "mid", "mid", "deep", "after"],
}

# Phase -> intensity band when the intensity select is "any" (bandForPhase).
PHASE_BAND = {"notch": "soft", "enter": "mid", "mid": "mid", "deep": "mid", "wreck": "hard", "finish": "raw", "after": "soft"}

# Fixed action overrides for certain phases (makeShot).
PHASE_OVERRIDE_DOING = {
    "notch": "almost still. Show the join. Tiny movement only.",
    "deep": "stay buried. Grind or clench. Do not turn it into a pounding montage.",
    "after": "no new thrusting. Breath, hands, leak or spit, bodies still in the same position.",
}

# Fixed solo position lines for the intro/tease stages (posForStage).
STAGE_POS_LINES = {
    "intro": "standing or sitting, SFW, facing camera",
    "tease": "standing, teasing clothes, no sex",
}

# Meme/caption slot position wording (memeForShot).
MEME_POS_WORDS = {
    "top": "at the top center of the frame",
    "topleft": "at the top left of the frame",
    "topright": "at the top right of the frame",
    "center": "in the center of the frame",
    "bottom": "at the bottom center of the frame",
    "bottomleft": "at the bottom left of the frame",
    "bottomright": "at the bottom right of the frame",
}

# ON-SCREEN TEXT templates (memeForShot). Placeholders: {n} = slot number,
# {at} = "MM:SS.mmm" stamp, {where} = MEME_POS_WORDS entry, {txt} = caption
# (max 80 chars, double quotes replaced by single quotes), {fill}/{stroke} =
# hex colors.
MEME_TEMPLATES = {
    "appears": " ON-SCREEN TEXT {n} appears at {at} {where}: \"{txt}\". Fill {fill}. Outline {stroke}. Hard caption on the picture. Not an app UI.",
    "stays": " ON-SCREEN TEXT {n} stays {where}: \"{txt}\". Fill {fill}. Outline {stroke}.",
}

# Anti-artifact lock lines (footer; artifactFix select).
ARTIFACT_LOCK_LIGHT = "ARTIFACT LOCK: Each person keeps two arms, two legs, one head. Hands stay attached to the same wrists. When a hand is readable: five separate fingers, a firm grip or a flat palm, knuckles bend. Weight on planted feet. Joints stay in normal range. Bodies do not melt into each other or into the furniture."
ARTIFACT_LOCK_FULL_SUFFIX = " Faces stay the same count of eyes, one nose, one mouth. No extra limb growing mid-shot. No face smear. No motion-blur smear that turns a hand into a paddle. Skin stays skin, not wax. Hair stays hair, not a smear. If a hand reaches at the lens, keep it just off the near corners rather than a giant foreshortened claw."

# Male walk-in line (per-stage ManJoin checkbox).
MAN_JOIN_LINE = "The male walks into this same <Picture 1> frame from the edge. His feet take steps. He arrives in her scene. The camera does not cut. Do not spawn him. Do not switch to his picture. "

# Light lock line (lockLight checkbox, prepended to shots and header).
FORCE_REF_LINE = "LIGHT LOCK this shot. Same lighting as <Picture 1> on <Subject 1>. Same light direction. Same color grade. Same shadow side. Same brightness on her skin as the start frame. Ignore lighting from any other picture. Do not relight. Do not add a new key light. "

# Camera-from-reference block (per-stage CamRef checkbox; replaces the camera
# sentence entirely).
CAM_REF_BLOCK = {
    "framing": "same distance as <Picture 1>. Same crop size. Do not push in. Do not pull out. Do not go wider.",
    "ang": "same camera angle as <Picture 1>. Same height. Same side. Do not orbit. Do not flip to a new view.",
    "move": "locked-off static, only bodies move",
    "speed": "camera speed very slow",
    "stab": "same stability as Picture 1",
    "follow": "keep the Picture 1 crop",
    "lock": "CAMERA FROM PICTURE 1. No new distance. No new angle. Hold the reference frame.",
    "cameraLine": "CAMERA FROM <Picture 1>. Same distance as the reference still. Same angle. Same height. Same side of her. Do not push in. Do not pull out. Do not orbit. Do not cut to a new view. Only bodies move. Category camera selects are off for this shot",
}

# Subject preservation variants (preserve(), rotated by shot index).
PRESERVE_OPTS = [
    "{tag} fully preserved from {img}",
    "{tag} identity fully preserved, body and hair unchanged from {img}",
    "{tag} fully preserved",
]

# Stage transition bridges for "one locked take" flow mode (takeBridge,
# keyed "prevStage>nextStage").
STAGE_BRIDGES = {
    "intro>tease": "From that same stance she starts to tease. She stays in the Picture 1 crop.",
    "intro>hj": "From that same stance she reaches to him. She lowers in view.",
    "intro>bj": "From that same stance she goes down to his cock in view.",
    "intro>breast": "From that same stance she brings her chest to him in view.",
    "intro>sex": "From that same stance she takes him in view.",
    "intro>cum": "From that same stance he finishes on her in view.",
    "tease>hj": "From the tease her hand finds him. She does not leave the frame.",
    "tease>bj": "From the tease she lowers her mouth to him in view.",
    "tease>breast": "From the tease she presses her chest to him in view.",
    "tease>sex": "From the tease she takes him in view.",
    "tease>cum": "From the tease he finishes on her in view.",
    "hj>bj": "Her fist is still on him. She brings her mouth to the same cock in view.",
    "hj>breast": "Her hand leaves the stroke and she brings her chest to him in view.",
    "hj>sex": "Her hand leaves the stroke and she takes him in view.",
    "hj>cum": "Her fist is still on him when he finishes in view.",
    "bj>breast": "Her mouth leaves him and she brings her chest to the same cock in view.",
    "bj>sex": "Her mouth leaves him and she takes the same cock in view.",
    "bj>cum": "Her mouth is still on him when he finishes in view.",
    "breast>sex": "Her chest leaves the shaft and she takes him in view.",
    "breast>cum": "Her chest is still on him when he finishes in view.",
    "sex>cum": "He stays in that same fuck and finishes in view.",
    "bj>hj": "Her mouth slides off and her hand stays on the same cock in view.",
    "sex>bj": "He pulls back in view and her mouth takes the same cock.",
}

# Rhythm ownership line (drive select).
DRIVE_LINES = {
    "receiver": "the receiving body owns depth and tempo",
    "giver": "the penetrating or oral-giving body owns the rhythm",
    "fight": "they fight the rhythm — one wants slower, one wants deeper",
}

# Screen direction lines (screen select).
SCREEN_DIRECTION_LINES = {
    "L": "SCREEN DIRECTION: giver / top stays on camera left. Do not flip.",
    "R": "SCREEN DIRECTION: giver / top stays on camera right. Do not flip.",
}

# Extra onlooker "IN FRAME" lines (frameWho select values that add people).
FRAME_EXTRA_LINES = {
    "bf": "IN FRAME: a boyfriend stands in the same backdrop and watches. He is not male 1. Clothes on. No second sex act. Faces of extras stay generic, not a reference face.",
    "gf": "IN FRAME: a girlfriend stands in the same backdrop and watches. She is not female 1. Clothes on. No second sex act. Faces of extras stay generic, not a reference face.",
    "strangerM": "IN FRAME: a stranger male stands in the same backdrop and watches. He is not male 1. Clothes on. No second sex act. Generic face, not a reference.",
    "strangerF": "IN FRAME: a stranger female stands in the same backdrop and watches. She is not female 1. Clothes on. No second sex act. Generic face, not a reference.",
    "two": "IN FRAME: two extra people stand in the same backdrop and watch. Clothes on. No second sex act. Generic faces, not reference faces.",
    "few": "IN FRAME: a few extra people in the same backdrop, mid-ground, watching. Clothes on. No second sex act. Faces soft, not reference faces.",
    "crowd": "IN FRAME: a crowd in the back of the same backdrop. Soft faces. No extra sex. Do not invent a new backdrop.",
}

# Group framing lines for scenes with 3+ subjects (frameWho = main/off/all).
FRAME_GROUP_LINES = {
    "main": "IN FRAME: S1 and S2 fully readable. Anyone else only as hands, a chest at the edge, or a mouth at the edge. Do not go wide to fit everyone.",
    "off": "IN FRAME: main pairing only. Additional subjects are offscreen, implied by a hand or a voice at most.",
    "all": "IN FRAME: all subjects readable without changing the backdrop.",
}

# Watcher sentences appended to the action line for frameWho extras.
EXTRA_WATCH_LINES = {
    "bf": " A boyfriend stands a step back in the same backdrop and watches. He does not join. He is not male 1.",
    "gf": " A girlfriend stands a step back in the same backdrop and watches. She does not join. She is not female 1.",
    "strangerM": " A stranger male stands a step back in the same backdrop and watches. He does not join. He is not male 1.",
    "strangerF": " A stranger female stands a step back in the same backdrop and watches. She does not join. She is not female 1.",
    "two": " Two extra people stand a step back in the same backdrop and watch. They do not join.",
    "few": " A few extra people watch from the mid-ground of the same backdrop. They do not join.",
    "crowd": " A crowd stays in the back of the same backdrop. Soft, out of focus. Nobody from the crowd joins the act.",
}

# Relationship flavor lines (relate select), appended to the action line.
RELATE_LINES = {
    "strangers": " RELATE strangers. They just met. No pet names. Hands are new on each other. A little stiff, then the act.",
    "couple": " RELATE couple. They already know each other's bodies. Easy hands. Familiar mouth. They look like they have done this.",
    "married": " RELATE married. Wedding-familiar. They touch like they own the habit. No stranger nerves.",
    "ex": " RELATE exes. Old heat. They know the body and still fight it. A sharp look, then the act.",
    "dad": " RELATE adult father and adult daughter. Both 18 or older. He is her dad. She is his daughter. The act stays. She may say dad. He treats her as his girl. Not a child. Adult bodies only.",
    "mom": " RELATE adult mother and adult son. Both 18 or older. She is his mom. He is her son. The act stays. He may say mom. She treats him as her boy. Not a child. Adult bodies only.",
    "brother": " RELATE adult brother and adult sister. Both 18 or older. He is her brother. She is his sister. The act stays. Sibling heat, not a child. Adult bodies only.",
    "sister": " RELATE adult sister and adult brother. Both 18 or older. She is his sister. He is her brother. The act stays. Sibling heat, not a child. Adult bodies only.",
}

# Intro (SFW opener) action lines, keyed by the introDo select value.
# Placeholders: {T_s}/{T_p}/{T_o} = subject/top, {C_or_T_o}/{C_or_T_p} =
# the cock owner (or the top when there is none).
INTRO_DO_LINES = {
    "look": "{T_s} stands or sits in the reference place. {T_s} looks into camera. {T_p} face is calm. {T_p} hands stay at {T_p} sides or in {T_p} lap. SFW. No sex.",
    "wave": "{T_s} lifts {T_p} hand and waves at camera. {T_s} smiles. {T_p} other hand stays still. SFW. No sex.",
    "sit": "{T_s} sits down. {T_p} knees close or easy. {T_s} settles and looks at camera. SFW. No sex.",
    "walk": "{T_s} walks into frame a few steps. {T_p} arms hang natural. {T_s} stops and looks at camera. SFW. No sex.",
    "turn": "{T_s} turns for camera, slow. {T_s} shows {T_p} front, then {T_p} side, then {T_p} back. SFW. No sex.",
    "talk": "{T_s} looks at camera and says a short hi. {T_p} mouth moves. SFW. No dirty talk. No sex.",
    "lean": "{T_s} leans a little toward camera. {T_p} shoulders come forward. {T_s} looks at camera. SFW. No sex.",
    "hair": "{T_s} lifts {T_p} hand and fixes {T_p} hair. {T_s} looks at camera while {T_p} fingers move through it. SFW. No sex.",
    "smile": "{T_s} stays still and smiles at camera. {T_p} hands do not wave. SFW. No sex.",
    "stand": "{T_s} just stands in the reference place. {T_p} weight on one hip. {T_s} looks at camera, then away. SFW. No sex.",
    "sitedge": "{T_s} sits on the edge of the surface. {T_p} feet hang. {T_s} looks at camera. SFW. No sex.",
    "cross": "{T_s} sits and crosses {T_p} legs. {T_s} adjusts and looks at camera. SFW. No sex.",
    "stretch": "{T_s} stretches {T_p} arms up, then drops them. {T_s} looks at camera. SFW. No sex.",
    "yawn": "{T_s} yawns and covers {T_p} mouth with one hand. Then {T_s} looks at camera. SFW. No sex.",
    "phone": "{T_s} holds a phone, looks at it, then looks up at camera. SFW. No sex.",
    "door": "{T_s} comes in and stops in the same backdrop. {T_s} looks at camera. SFW. No sex.",
    "mirror": "{T_s} checks {T_p} self in a mirror, then turns to camera. SFW. No sex.",
    "fixcloth": "{T_s} straightens {T_p} clothes with both hands. {T_s} looks at camera. SFW. No sex.",
    "sitclose": "{T_s} sits closer to {C_or_T_o}. Clothes stay on. {T_s} looks at camera or at {C_or_T_o}. SFW. No sex.",
    "nod": "{T_s} nods once at camera. {T_p} hands stay still. SFW. No sex.",
    "point": "{T_s} points at something off frame, then drops {T_p} hand. SFW. No sex.",
    "drink": "{T_s} takes a sip from a glass or bottle, then looks at camera. SFW. No sex.",
    "wait": "{T_s} waits. {T_s} shifts {T_p} weight from one foot to the other. SFW. No sex.",
    "kneelsoft": "{T_s} kneels on the surface, upright, clothes on. {T_s} looks at camera. SFW. No sex.",
    "tiehair": "{T_s} gathers {T_p} hair and ties it back. {T_s} looks at camera. SFW. No sex.",
    "kickshoes": "{T_s} kicks off {T_p} shoes and leaves them. {T_s} looks at camera. SFW. No sex.",
    "sitfloor": "{T_s} sits on the surface of the same backdrop. {T_p} knees easy. {T_s} looks at camera. SFW. No sex.",
    "leanwall": "{T_s} leans {T_p} back or shoulder on the backdrop. {T_s} looks at camera. SFW. No sex.",
    "lookhim": "{T_s} looks at {C_or_T_o} first, then at camera. Clothes on. SFW. No sex.",
    "shrug": "{T_s} shrugs once, then smiles at camera. SFW. No sex.",
    "adjustsit": "{T_s} scoots back and sits proper. {T_s} settles. SFW. No sex.",
    "foldhands": "{T_s} folds {T_p} hands in {T_p} lap and looks at camera. SFW. No sex.",
    "rubeyes": "{T_s} rubs {T_p} eyes, then looks up at camera. SFW. No sex.",
    "comein": "{T_s} comes in smiling. {T_s} wants to be here. {T_s} walks toward {C_or_T_o}. SFW. No sex.",
    "takehand": "{T_s} takes {C_or_T_p} hand on purpose. {T_s} keeps it. Willing. SFW. No sex.",
    "sitwith": "{T_s} sits with {C_or_T_o} on purpose, close. {T_s} chose the spot. SFW. No sex.",
    "leanhim": "{T_s} leans on {C_or_T_o}. {T_p} weight is on {C_or_T_o}. Willing. SFW. No sex.",
    "kisscheek": "{T_s} kisses {C_or_T_p} cheek. One kiss. Faces close. SFW. No sex.",
    "callhim": "{T_s} calls {C_or_T_o} over with a hand. {T_s} waits for {C_or_T_o}. SFW. No sex.",
    "patseat": "{T_s} pats the seat beside {T_o}. {T_s} wants {C_or_T_o} there. SFW. No sex.",
    "hugbrief": "{T_s} gives {C_or_T_o} a short hug and stays close. Willing. SFW. No sex.",
    "turnaway": "{T_s} turns {T_p} face away from {C_or_T_o} and from camera. {T_s} does not want to look. SFW. No sex.",
    "stepback": "{T_s} steps back from {C_or_T_o}. Space opens. {T_s} does not come closer. SFW. No sex.",
    "pushhand": "{T_s} pushes {C_or_T_p} hand off {T_o}. {T_s} does not want the touch. SFW. No sex.",
    "armsx": "{T_s} crosses {T_p} arms over {T_p} chest. Closed. Unwilling. SFW. No sex.",
    "lookdoor": "{T_s} looks toward the way out. {T_s} does not look at {C_or_T_o}. SFW. No sex.",
    "sitfar": "{T_s} sits far from {C_or_T_o}. A gap stays. {T_s} does not close it. SFW. No sex.",
    "shakehead": "{T_s} shakes {T_p} head no. Clear refuse. SFW. No sex.",
    "holdcloth": "{T_s} holds {T_p} clothes closed with both hands. {T_s} does not open them. SFW. No sex.",
    "glare": "{T_s} glares at {C_or_T_o}. Hard eyes. No smile. Hostile. SFW. No sex.",
    "scoff": "{T_s} scoffs at {C_or_T_o}. Short ugly sound. {T_p} mouth curls. SFW. No sex.",
    "snaptalk": "{T_s} snaps words at {C_or_T_o}. Sharp mouth. {T_s} does not come closer. SFW. No sex.",
    "argue": "{T_s} argues. {T_s} points at {C_or_T_o}. Faces tight. SFW. No sex.",
    "shove": "{T_s} shoves {C_or_T_p} chest with both hands. Space opens. Hostile. SFW. No sex.",
    "slaphand": "{T_s} slaps {C_or_T_p} hand away. Fast. {T_s} does not want the touch. SFW. No sex.",
    "staredown": "{T_s} stares {C_or_T_o} down. {T_p} chin is up. {T_s} does not look away first. SFW. No sex.",
    "block": "{T_s} blocks {C_or_T_p} path with {T_p} body. {T_s} will not let {C_or_T_o} past. SFW. No sex.",
    "turnback": "{T_s} turns {T_p} whole back on {C_or_T_o}. {T_s} will not face {C_or_T_o}. SFW. No sex.",
    "refusesit": "{T_s} stays on {T_p} feet when {C_or_T_s} sits or waits. {T_s} refuses the seat. SFW. No sex.",
    "finger": "{T_s} points {C_or_T_o} off, out of frame. Get out. SFW. No sex.",
    "jaw": "{T_s} sets {T_p} jaw. Hostile face. {T_p} eyes stay hard on {C_or_T_o}. SFW. No sex.",
}

# Fallback intro line when introDo is "undef".
INTRO_DO_UNDEF = "{T_s} looks. {T_p} face is calm. SFW. No sex."

# Tease action lines, keyed by the teaseDo select value.
TEASE_DO_LINES = {
    "strap": "{T_s} hooks a finger under a strap and pulls it off {T_p} shoulder. {T_p} other hand stays on {T_p} hip. No blowjob. No sex.",
    "hem": "{T_s} lifts a hem with {T_p} fingers. The fabric rides up {T_p} thigh. {T_s} holds it there. No blowjob. No sex.",
    "turn": "{T_s} turns and shows {T_p} back. {T_s} looks over {T_p} shoulder at camera. Clothes stay on. No blowjob. No sex.",
    "lift": "{T_s} lifts {T_p} top with both hands. {T_p} stomach and chest come into frame. {T_s} holds the lift. No blowjob. No sex.",
    "bend": "{T_s} bends at the waist and looks back. {T_p} hands find {T_p} knees or the surface. No blowjob. No sex.",
    "touch": "{T_s} runs {T_p} hands over {T_p} own body on top of the clothes. Chest, waist, thigh. No blowjob. No sex.",
    "unzip": "{T_s} opens a zip or a button. {T_p} fingers work it slow. The garment loosens. No blowjob. No sex.",
    "thigh": "{T_s} slides {T_p} hand down {T_p} own thigh. {T_s} watches {T_p} hand. No blowjob. No sex.",
    "neck": "{T_s} touches {T_p} own neck, then the top of {T_p} chest. Slow. No blowjob. No sex.",
    "sitopen": "{T_s} sits and opens {T_p} knees. {T_p} hands rest on {T_p} thighs. Clothes stay. No blowjob. No sex.",
    "flash": "{T_s} pulls {T_p} top down for a second. {T_p} chest shows, then {T_s} covers again. No blowjob. No sex.",
    "waist": "{T_s} hooks both thumbs in {T_p} waistband and tugs it down a little, then stops. No blowjob. No sex.",
    "asidep": "{T_s} pulls fabric aside at the join and holds it. No mouth on him. No penetration. No blowjob. No sex.",
    "hips": "{T_s} rolls {T_p} hips slow. Clothes stay on. The motion is the tease. No blowjob. No sex.",
    "grind": "{T_s} grinds on {C_or_T_o} over clothes. Hips press and slide. Nothing goes in. No blowjob. No sex.",
    "lap": "{T_s} sits across {C_or_T_p} lap, clothes on. {T_s} settles and shifts {T_p} weight. No blowjob. No sex.",
    "crawl": "{T_s} crawls closer on hands and knees. {T_s} stops in front of {C_or_T_o}. No mouth on him yet. No blowjob. No sex.",
    "lieback": "{T_s} lies back and brings {T_p} knees up. Clothes stay. {T_s} holds that open shape. No blowjob. No sex.",
    "squeeze": "{T_s} squeezes {T_p} breasts over the clothes with both hands. No blowjob. No sex.",
    "ass": "{T_s} turns, shows {T_p} ass, and looks back. {T_s} may tug the fabric up a little. No blowjob. No sex.",
    "licklips": "{T_s} licks {T_p} lips slow and stays close. No mouth on him. No blowjob. No sex.",
    "hairtoss": "{T_s} tosses {T_p} hair and leans {T_p} chest forward. Pause. No blowjob. No sex.",
    "pullhim": "{T_s} grabs {C_or_T_p} shirt or waist and pulls {C_or_T_o} in. Faces close. No kiss stacked. No blowjob. No sex.",
    "trace": "{T_s} traces {C_or_T_p} zipper with one finger. {T_s} does not take {C_or_T_o} in {T_p} mouth. No blowjob. No sex.",
    "kissneck": "{T_s} puts {T_p} mouth on {C_or_T_p} neck. One kiss. Faces close. No blowjob. No sex.",
    "ear": "{T_s} puts {T_p} mouth at {C_or_T_p} ear and stays there. No blowjob. No sex.",
    "straddle": "{T_s} straddles {C_or_T_o}, clothes on. {T_s} sits across {C_or_T_p} lap and holds still. Nothing goes in. No blowjob. No sex.",
    "pushdown": "{T_s} pushes {C_or_T_o} back onto the surface with both hands. {T_s} stays over {C_or_T_o}. Clothes on. No blowjob. No sex.",
    "guidehand": "{T_s} takes {C_or_T_p} hand and puts it on {T_p} waist. Holds it there. No blowjob. No sex.",
    "bitelip": "{T_s} bites {T_p} own lower lip and looks at {C_or_T_o} or camera. Pause. No blowjob. No sex.",
    "skirtup": "{T_s} hikes {T_p} skirt or hem with both hands and holds it. No blowjob. No sex.",
    "braoff": "{T_s} slides one strap down {T_p} shoulder. The bra stays on. No blowjob. No sex.",
    "peek": "{T_s} lifts {T_p} own top and peeks down, then looks at camera. No blowjob. No sex.",
    "spin": "{T_s} turns a slow full spin in place. Clothes stay on. {T_s} stops facing camera. No blowjob. No sex.",
    "onallfours": "{T_s} gets on hands and knees and looks back. Clothes stay. No blowjob. No sex.",
    "foot": "{T_s} sets one foot on {C_or_T_p} thigh and holds that pose. Clothes on. No blowjob. No sex.",
    "undobelt": "{T_s} undoes {C_or_T_p} belt or button and stops. {T_s} does not take {C_or_T_o} in {T_p} mouth. No blowjob. No sex.",
    "shirtuphim": "{T_s} lifts {C_or_T_p} shirt with both hands. No mouth on him. No blowjob. No sex.",
    "closehips": "{T_s} presses {T_p} hips to {C_or_T_o}, clothes on. A grind, nothing goes in. No blowjob. No sex.",
    "whisper": "{T_s} leans in like {T_s} whispers at {C_or_T_p} ear. Mouth close. No blowjob. No sex.",
    "mirrorpose": "{T_s} poses for a mirror, one hip out, then looks back at camera. Clothes on. No blowjob. No sex.",
    "hippop": "{T_s} pops one hip out and holds it. Clothes on. No blowjob. No sex.",
    "slowundress": "{T_s} takes one piece of clothing off and stops. The rest stays. No blowjob. No sex.",
    "braopen": "{T_s} opens {T_p} bra in front and keeps it on {T_p} shoulders. No blowjob. No sex.",
    "pantypeel": "{T_s} peels {T_p} underwear down an inch and holds it. No blowjob. No sex.",
    "wetfinger": "{T_s} wets a finger and traces {T_p} lower lip. No mouth on him. No blowjob. No sex.",
    "sitonthigh": "{T_s} sits on {C_or_T_p} thigh, clothes on. {T_s} balances there. No blowjob. No sex.",
    "handswalk": "{T_s} walks {T_p} hands up {C_or_T_p} chest. Stops at the collar. No blowjob. No sex.",
    "lookbackcrawl": "{T_s} crawls a step away and looks back over {T_p} shoulder. Clothes on. No blowjob. No sex.",
    "rubclothed": "{T_s} rubs {T_self} over the clothes, slow. No fingers in. No blowjob. No sex.",
    "showpanties": "{T_s} lifts a hem and shows {T_p} underwear, then holds it. No blowjob. No sex.",
    "kneesqueeze": "{T_s} squeezes {T_p} knees together, then opens them. Clothes on. No blowjob. No sex.",
    "startundress": "{T_s} starts to take a garment off for {C_or_T_o}. Willing. Stops before nude if that is the beat. No blowjob. No sex.",
    "puthishand": "{T_s} takes {C_or_T_p} hand and puts it on {T_p} chest over clothes. {T_s} keeps it there. Willing. No blowjob. No sex.",
    "openforhim": "{T_s} opens {T_p} knees toward {C_or_T_o} on purpose. Clothes stay. Willing. No blowjob. No sex.",
    "pullhip": "{T_s} pulls {C_or_T_p} hips in. Clothes on. Nothing goes in. Willing. No blowjob. No sex.",
    "showhim": "{T_s} turns {T_p} body to show {C_or_T_o}. {T_s} wants {C_or_T_o} to look. No blowjob. No sex.",
    "kissdown": "{T_s} kisses down {C_or_T_p} chest. Stops above the belt. Willing. No blowjob. No sex.",
    "climbhim": "{T_s} climbs onto {C_or_T_o}, clothes on. {T_s} chose it. Nothing goes in. No blowjob. No sex.",
    "beglook": "{T_s} looks at {C_or_T_o} like {T_s} wants the next act. Mouth parted. Still only a tease. No blowjob. No sex.",
    "coverup": "{T_s} covers {T_p} chest or lap with both hands. {T_s} does not want the tease. Clothes stay. No blowjob. No sex.",
    "holdhem": "{T_s} holds {T_p} hem down so it cannot lift. {T_s} fights the tease. No blowjob. No sex.",
    "twistaway": "{T_s} twists {T_p} body away from {C_or_T_o}. {T_s} does not present. No blowjob. No sex.",
    "pushchest": "{T_s} pushes on {C_or_T_p} chest to make space. {T_s} does not pull {C_or_T_o} in. No blowjob. No sex.",
    "clampknees": "{T_s} clamps {T_p} knees shut. {T_s} does not open. Clothes on. No blowjob. No sex.",
    "fixstrap": "{T_s} puts a strap or hem back in place. {T_s} covers what was shown. No blowjob. No sex.",
    "turnface": "{T_s} turns {T_p} face away while the tease happens. {T_s} will not look. No blowjob. No sex.",
    "grabwrist": "{T_s} grabs {C_or_T_p} wrist and stops {C_or_T_p} hand. {T_s} does not want that touch. No blowjob. No sex.",
}

# Fallback tease line when teaseDo is "undef".
TEASE_DO_UNDEF = "{T_s} teases. Hands on clothes. No blowjob. No sex."

# Handjob position lines for the select (posForStage; plain text, no pronoun
# substitution in the JS).
HJ_POS_LINES = {
    "kneel": "she kneels at his hips",
    "lap": "she is beside him, her hand in his lap",
    "sit": "she sits, he stands",
    "side": "she is at his hip from the side",
    "himlie": "he lies back, she over his hips",
    "stand": "both stand",
    "between": "she is between his knees",
    "proneglute": "she lies on her stomach, glutes visible",
    "behind": "she is behind him and reaches around",
    "spoon": "they lie spooned, her hand back on him",
    "sitspread": "he sits, she between his knees",
    "shestand": "he sits, she stands over his lap",
    "bothkneel": "both kneel",
    "shelie": "she lies on her back, he kneels over her",
    "thighsit": "she sits on his thighs",
    "fly": "his fly is open, her hand through it",
    "under": "she is below him while he stands",
    "overhand": "she faces him and uses an overhand stroke",
}

# Blowjob position lines for the select (posForStage).
BJ_POS_LINES = {
    "kneel": "kneeling between the feet, mouth at hip height",
    "edge": "sitting on the edge, mouth at hip height",
    "stand": "one standing, one kneeling at the hips",
    "lap": "head in the lap",
    "floor": "kneeling on the surface between the feet",
    "side": "at the side of the hip, mouth on the shaft",
    "lyingback": "she on her back, head at his hips",
    "edgehead": "her head off the surface edge, he standing",
    "himlie": "he lies back, she over his hips",
    "sitbetween": "he sits, she between his knees",
    "wall": "he against the backdrop, she kneels",
    "bededge": "he at the surface edge, she kneels",
    "allfours": "she on all fours, mouth to his cock",
    "squat": "she squats in front of him",
    "sidelie": "both on their sides, her mouth at his cock",
    "sixty": "69 stack, her mouth on his cock only",
    "under": "she under him, he stands over her face",
    "chair": "he sits, she between his knees",
    "desk": "he sits at a surface, she lower, mouth at his cock",
    "coucharm": "she leans over a surface edge, mouth at his cock",
    "table": "she sits on a surface edge, he stands, her mouth at his cock",
    "reverse": "she faces away from him, head turned back, mouth on his cock",
    "pronehim": "he lies on his stomach, she at his hip from the side, mouth on his cock",
    "liftleg": "she kneels, one of her legs lifted or hooked, mouth on his cock",
    "doublehand": "she kneels, both hands on his shaft, mouth on the head",
    "betweenlegs": "he sits with his knees open, she on the surface between his legs, mouth on his cock",
    "standing69": "he lifts her, her mouth on his cock, 69 standing, oral only",
    "proneglute": "she lies on her stomach. Her glutes are visible behind her. Her mouth is on his cock at her face.",
}

# Detailed blowjob body-position sentences (posDetail), keyed by bjPos.
BJ_POS_DETAIL = {
    "kneel": "{M_s} is kneeling between {C_p} feet. {C_s} stands still. {M_p} spine is long. {M_p} hands rest on {C_p} thighs. {M_p} mouth is at {C_p} cock height.",
    "edge": "{C_s} stands at the edge of a surface. {M_s} sits on that edge, {M_p} feet down. {M_p} head is at {C_p} hips.",
    "stand": "{C_s} stands. {M_s} kneels in front of {C_o}. {M_p} mouth is at {C_p} cock height.",
    "lap": "{C_s} sits. {M_s} has {M_p} head in {C_p} lap. {M_p} cheek or {M_p} mouth is on {C_p} thighs. {M_p} body lies or sits beside {C_o}, {M_p} head down in {C_p} lap.",
    "floor": "{M_s} kneels on the surface between {C_p} feet. {C_s} stands over {M_o}. {M_p} mouth is at {C_p} cock height.",
    "side": "{M_s} is at the side of {C_p} hip, not between {C_p} feet. {C_s} sits or stands. {M_p} mouth comes at {C_p} cock from the side.",
    "lyingback": "{M_s} lies on {M_p} back. {M_p} head is at {C_p} hips. {C_s} stands or kneels over {M_p} face. {M_p} mouth is at {C_p} cock.",
    "edgehead": "{M_s} lies on a surface with {M_p} head off the edge. {C_s} stands at that edge. {C_p} cock is at {M_p} mouth from above.",
    "himlie": "{C_s} lies on {C_p} back. {M_s} is over {C_p} hips, {M_p} mouth on {C_p} cock. {M_s} may be on {M_p} elbows between {C_p} legs.",
    "sitbetween": "{C_s} sits. {C_p} knees are open. {M_s} is between {C_p} knees, {M_p} mouth on {C_p} cock.",
    "wall": "{C_s} stands upright. {M_s} kneels in front of {C_o}. {M_p} mouth is at {C_p} cock.",
    "bededge": "{C_s} stands at the surface edge. {M_s} kneels at that edge. {M_p} mouth is at {C_p} cock.",
    "allfours": "{M_s} is on {M_p} hands and knees. {C_s} stands or kneels in front of {M_p} face. {M_p} mouth is on {C_p} cock.",
    "squat": "{M_s} squats in front of {C_o}. {C_s} stands. {M_p} mouth is at {C_p} cock height.",
    "sidelie": "{M_s} and {C_s} lie on their sides. {M_p} head is at {C_p} hips. {M_p} mouth is on {C_p} cock.",
    "sixty": "{M_s} and {C_s} stack 69. {M_p} mouth is on {C_p} cock only. No second sex. No pussy on his mouth written as a second act.",
    "under": "{M_s} is under {C_o}. {C_s} stands over {M_p} face. {M_p} mouth is on {C_p} cock from below.",
    "chair": "{C_s} sits. {M_s} is between {C_p} knees. {M_p} mouth is on {C_p} cock.",
}

# Detailed handjob body-position sentences (posDetail), keyed by hjPos.
HJ_POS_DETAIL = {
    "kneel": "{M_s} kneels at {C_p} hips. {C_s} stands or sits still. {M_p} hands are on {C_p} cock. No mouth on him.",
    "lap": "{C_s} sits. {M_s} is beside {C_o}, {M_p} hand is in {C_p} lap on {C_p} cock.",
    "sit": "{M_s} sits. {C_s} stands in front of {M_o}. {M_p} hands reach {C_p} cock at her face height.",
    "side": "{M_s} is at the side of {C_p} hip. {M_p} hands come at {C_p} cock from the side.",
    "himlie": "{C_s} lies on his back. {M_s} is over {C_p} hips. {M_p} hands work {C_p} cock. He is the one on his back.",
    "stand": "{M_s} and {C_s} both stand. {M_p} hands are on {C_p} cock between them.",
    "between": "{C_s} sits with his knees open. {M_s} is between {C_p} knees. {M_p} hands are on {C_p} cock.",
    "proneglute": "{M_s} lies on her stomach. Her glutes are visible behind her. {M_p} hands work {C_p} cock at her face.",
    "behind": "{M_s} stands or kneels behind {C_o}. {M_p} arms reach around his hips. {M_p} hands stroke {C_p} cock from behind. He faces away from her.",
    "spoon": "{M_s} and {C_s} lie on their sides, spooned. {M_s} is behind or against him. {M_p} hand reaches {C_p} cock. They stay on their sides.",
    "sitspread": "{C_s} sits. His knees are open. {M_s} sits or kneels between {C_p} knees. {M_p} hands are on {C_p} cock.",
    "shestand": "{C_s} sits. {M_s} stands over his lap. She bends at the waist. {M_p} hands stroke {C_p} cock from above.",
    "bothkneel": "{M_s} and {C_s} both kneel, facing each other or slightly offset. {M_p} hands are on {C_p} cock. Nobody is standing.",
    "shelie": "{M_s} lies on her back. {C_s} kneels over her ribs or hips. {M_p} hands reach up and stroke {C_p} cock above her.",
    "thighsit": "{C_s} sits or lies back. {M_s} sits on {C_p} thighs, not on his cock. {M_p} hands stroke {C_p} cock between them. No penetration.",
    "fly": "{C_s} still has pants or jeans on. The fly is open. {M_p} hand works {C_p} cock through the fly. The rest of his clothes stay.",
    "under": "{C_s} stands. {M_s} is below him, sitting or kneeling so her hands come up onto {C_p} cock from underneath.",
    "overhand": "{M_s} faces {C_o}. {M_p} fist is overhand on {C_p} cock, wrist on top, stroking toward herself.",
}

# Detailed sex-position sentences (posDetail), keyed by sxPos.
SEX_POS_DETAIL = {
    "missionary": "{B_s} is on {B_p} back. {B_p} knees are open. {T_s} is between {B_p} legs, {T_p} weight on {T_p} arms. Missionary.",
    "doggy": "{B_s} is on {B_p} hands and {B_p} knees. {B_p} back is arched. {T_s} is behind {B_o}, {T_p} hands on {B_p} hips. Doggy.",
    "cowgirl": "{B_s} sits on {T_o}. {T_s} is on {T_p} back. {B_p} knees are outside {T_p} hips. {B_p} hands on {T_p} chest. Cowgirl. She is on top.",
    "standing": "{B_s} and {T_s} are standing. {T_s} is behind or against {B_o}. {T_p} hips lock to {B_p} hips.",
    "side": "{B_s} and {T_s} lie on their sides. {T_p} hips tuck behind {B_o}. {B_p} top leg is open. Spoon / side.",
    "seated": "{T_s} sits. {B_s} sits in {T_p} lap, {B_p} weight down on {T_o}. Seated.",
    "folded": "{B_s} is on {B_p} back with {B_p} knees toward {B_p} chest. {T_s} presses {B_o} folded.",
    "prone": "{B_s} is flat on {B_p} stomach. {T_s} is on top of {B_p} back. Prone.",
}

# Breast-act stance sentences (posDetail / posForStage).
BREAST_STANCE_DETAIL = "{B_s} is in front of {C_or_T_o}. {B_p} chest is to {C_or_T_p} torso. {B_p} hands hold {B_p} breasts."
BREAST_STANCE_LINE = "she is in front of him, her chest to his torso, her hands on her breasts"

# Handjob grip sentences, keyed by hjGrip.
HJ_GRIP_LINES = {
    "one": "{M_s} strokes {C_p} cock with one wet fist. {M_p} thumb works the ridge. No mouth on him. No penetration.",
    "two": "{M_s} uses both hands on {C_p} cock. One fist over the other. Both slide. No mouth on him. No penetration.",
    "twist": "{M_s} strokes {C_p} cock and twists her wrist on the upstroke. The fist turns around the shaft. No mouth on him.",
    "head": "{M_s} works the head of {C_p} cock with her fist and thumb. Short strokes on the glans. No mouth on him.",
    "balls": "{M_s} strokes {C_p} shaft with one hand. Her other hand holds {C_p} balls. No mouth on him.",
}
HJ_GRIP_FALLBACK = "{M_s} gives {C_o} a handjob. {M_p} hands work {C_p} cock. No mouth on him. No sex."

# Handjob tempo sentences (leading space; appended to the grip line).
HJ_TEMPO_LINES = {
    "slow": " She strokes slow. Long pull. Pause at the head.",
    "even": " She keeps an even stroke. Same speed up and down.",
    "fast": " She jerks fast. Short tight strokes. Wrist snaps.",
}

# Blowjob depth sentences, keyed by bjDepth.
BJ_DEPTH_LINES = {
    "lick": "{M_s} licks {C_p} cock only. {M_p} tongue works the head and the underside. {M_p} mouth does not take {C_o} in yet.",
    "lips": "{M_s} keeps {M_p} lips on the head of {C_p} cock. Short sucks. {M_p} tongue under the ridge. No deep take.",
    "half": "{M_s} takes half of {C_p} shaft into {M_p} mouth. {M_p} hand covers the rest. Even bob.",
    "full": "{M_s} strokes {C_p} cock with {M_p} whole mouth, base to head and back. {M_p} lips stay sealed.",
    "deep": "{M_s} takes {C_p} cock deep and holds. {M_p} throat works. {C_s} stays still.",
}

# Blowjob wetness sentences (leading space).
BJ_WET_LINES = {
    "clean": " {M_p} lips stay clean.",
    "wet": " {M_p} mouth is wet on {C_p} cock.",
    "sloppy": " {M_p} spit runs on {C_p} shaft and on {M_p} chin.",
}

# Blowjob tempo sentences (leading space).
BJ_TEMPO_LINES = {
    "slow": " {M_s} moves {M_p} mouth slow.",
    "even": " {M_s} keeps an even bob.",
    "fast": " {M_s} bobs fast.",
}

# Blowjob hands sentences (leading space).
BJ_HANDS_LINES = {
    "base": " {M_p} hand stays on the base of {C_p} cock.",
    "two": " {M_s} uses both of {M_p} hands on {C_p} shaft.",
    "balls": " {M_p} other hand is on {C_p} balls.",
    "thighs": " {M_p} hands stay on {C_p} thighs.",
    "none": " {M_s} uses {M_p} mouth only. {M_p} hands stay off {C_p} cock.",
}

# Breast-act sentences, keyed by brKind.
BREAST_KIND_LINES = {
    "titfuck": "{C_s} slides {C_p} cock between {B_p} breasts. {B_s} presses {B_p} breasts around {C_p} shaft with {B_p} hands. The head of {C_p} cock shows at {B_p} sternum. No oral. No penetration.",
    "worship": "{T_s} puts {T_p} mouth on {B_p} breast. {T_p} lips and tongue work one nipple. {T_p} hand holds the other breast. No blowjob. No penetration.",
    "squeeze": "{T_s} squeezes {B_p} breasts with both hands. {B_p} flesh moves under {T_p} fingers. {B_s} arches into it. No oral. No penetration.",
    "lick": "{T_s} licks {B_p} nipple, slow. {T_p} tongue stays on that breast. {T_p} hand supports {B_p} breast from below. No blowjob. No penetration.",
    "reverse": "{B_s} leans {B_p} chest toward {C_o}. {C_s} fucks down through {B_p} cleavage from above. The head of {C_p} cock shows at {B_p} sternum. No oral. No penetration.",
    "under": "{C_s} lays {C_p} cock under {B_p} breasts. {B_s} presses {B_p} breasts down onto the shaft. The shaft slides under the flesh. No oral. No penetration.",
    "spit": "{B_s} spits into {B_p} cleavage. {C_s} slides {C_p} cock through that wet. Spit shines on the shaft. No oral. No penetration.",
    "slaphead": "{B_s} presses {B_p} breasts around {C_p} cock. The head of {C_p} cock taps {B_p} sternum on each stroke. No oral. No penetration.",
    "presswalk": "{B_s} walks {B_p} breasts up and down {C_p} shaft with both hands. Long slide, then back. No oral. No penetration.",
    "nipplesuck": "{T_s} sucks one of {B_p} nipples. {T_p} hand holds the other breast. No blowjob. No penetration.",
    "facepress": "{T_s} presses {T_p} face between {B_p} breasts. {B_s} holds {T_p} head there. No blowjob. No penetration.",
    "oil": "{B_p} breasts are slick. {C_s} slides {C_p} cock between them slow. Skin shine only. No oral. No penetration.",
    "holdout": "{B_s} holds {B_p} breasts out toward {C_o} with both hands. {C_s} may put {C_p} cock or {C_p} mouth there. No penetration.",
    "sideboob": "Side-on. {C_s} slides {C_p} cock along one of {B_p} breasts. {B_s} presses that breast in with one hand. No oral. No penetration.",
}
BREAST_KIND_UNDEF = "{B_or_T_s} works {B_or_T_p} breasts around {C_p} cock or {T_p} mouth on a nipple. No oral on his cock. No penetration."

# Sex bounce sentences (leading space), keyed by sxBounce.
SX_BOUNCE_LINES = {
    "none": " {B_s} barely moves. {B_p} body stays planted. Almost no bounce.",
    "small": " {B_s} bounces a little. {B_p} breasts and {B_p} ass shift a short way and drop back. Soft jiggle only.",
    "medium": " {B_s} bounces with each thrust. {B_p} breasts and {B_p} ass lift and fall a clear amount. Skin ripples, then settles, then lifts again.",
    "hard": " {B_s} bounces hard. {B_p} breasts slap and rebound. {B_p} ass and {B_p} thighs shake on every hit. The bounce is big and readable.",
}
SX_BOUNCE_DEFAULT = "medium"

# Sex act sentence templates (actLine piv/anal). {kind} = "vaginal"|"anal",
# {hole_p} = "{B_p} ass" or "{V_or_B_p} pussy".
SEX_ACT_TEMPLATE = "{C_or_T_s} fucks {B_o} {kind}. {C_or_T_p} cock is in {hole_p}. {B_s} takes {C_or_T_o}. Only this {kind} act. No oral."
SEX_HOLE_TEMPLATES = {"anal": "{B_p} ass", "vaginal": "{V_or_B_p} pussy"}

# Cum emission sentences (FINISH TYPE), keyed by cuFinish.
CUM_HOW_LINES = {
    "pulse": " FINISH TYPE pulse. Cause: {C_p} cock hitch-pulses at the base. Effect: thick viscous opaque white cum leaves the slit in short pumps, not a water burst. Material: dense, pearlescent, ropey, not watery. Sound: a wet pulse and a breath, not a gunshot. End: cum already on or in the target, sagging under gravity.",
    "leak": " FINISH TYPE leak. Cause: {C_p} cock stays almost still. Effect: viscous cum oozes and folds from the slit in a slow heave. Material: thick, glossy, clings to the glans. Sound: almost silent wet. End: a hanging bead stretches, then drops.",
    "dribble": " FINISH TYPE dribble. Cause: small pulses. Effect: beads of viscous cum well at the slit and run, no mid-air burst. Material: creamy, clotted, sticks. Sound: tiny wet ticks. End: beads cling, then slide.",
    "ropes": " FINISH TYPE ropes. Cause: {C_p} cock pulses hard. Effect: long elastic ligaments of thick white cum travel, then land. Material: dense ropey viscous, holds shape mid-air, not juice, not yogurt splash. Sound: wet pulses matched to each rope. End: ropes sit raised on skin, then sag and drip.",
    "spray": " FINISH TYPE spray. Cause: a hard pulse at the slit. Effect: a short burst of viscous strands, then they fall. Material: still thick white cum, not water crowning. Sound: one wet burst, then drip. End: strands collapse onto skin and run.",
}

# Cum quantity sentences, keyed by cuQty.
CUM_QTY_LINES = {
    "drops": " Quantity: small drops only. One or two beads. Not a flood.",
    "little": " Quantity: a little. One or two short pulses.",
    "normal": " Quantity: a normal load. Three or four thick pulses.",
    "heavy": " Quantity: a heavy load. Many pulses. It keeps pumping.",
    "huge": " Quantity: a huge load. Pulse after pulse. Pools and overflows.",
    "gallons": " Quantity: gallons. Unreal pour. It sheets and keeps coming.",
}
CUM_QTY_DEFAULT = "normal"

# Cum landing sentences, keyed by cumWhere.
CUM_LAND_LINES = {
    "mouth": "Land: inside {M_p} mouth. {C_s} cums. {C_p} cock stays between {M_p} lips. Cum hits {M_p} tongue and pools. {M_p} lips stay sealed so it does not spray out. Extra cum leaks at the corner, hangs, drips to {M_p} chin.",
    "swallow": "Land: inside {M_p} mouth. {C_s} cums. {M_s} swallows. {M_p} throat moves once per pulse. A viscous string stays on {C_p} cock when {M_p} lips ease back.",
    "tongue": "Land: {M_p} tongue. {M_s} holds {M_p} mouth open. Cum travels from the slit onto the flat tongue and sits glossy. Gravity pulls it toward {M_p} lip.",
    "face": "Land: {M_p} face. First contact cheek or lip. Next pulses streak nose and the other cheek. Cum sits in raised lines, then sags to {M_p} jaw and hangs from {M_p} chin.",
    "lips": "Land: {M_p} lips. {M_s} stays close to the head of {C_p} cock. Cum paints both lips. A ligament stretches from lip to slit, then breaks.",
    "breasts": "Land: {B_or_M_p} breasts. Cum hits the sternum or a nipple first, then slides into the cleavage. It stays visible and sags.",
    "stomach": "Land: {B_or_M_p} stomach. Cum pools in the belly dip and runs toward the navel.",
    "back": "Land: {B_or_M_p} back. Cum lands on the lower back and the top of {B_or_M_p} ass, sits, then slides.",
    "ass": "Land: {B_or_M_p} ass. Cum streaks a cheek and the cleft, then drips down the thigh.",
    "hand": "Land: {M_p} palm. {M_s} holds {C_p} cock. Cum fills the hand and leaks between {M_p} fingers.",
    "inside": "Land: inside {V_or_B_or_M_o}. {C_s} stays buried. Hips hitch with each pulse. When he eases back, viscous cum leaks around {C_p} cock and runs down the thigh. No mid-air burst while he is inside.",
    "pullout": "Land: first pulse still inside, then he pulls out. The rest travels from the slit onto {B_or_M_p} skin. A string hangs from the head of {C_p} cock to her body, then drops.",
}
CUM_LAND_UNDEF = "He cums. The load lands on the nearest skin or in the hole already in use."

# Cum shot opener and fluid rule (cumF).
CUM_OPENING = "{C_s} cums. Only the finish."
CUM_FLUID_RULE = " FLUID RULE: viscous white cum, oozing or folding, not water splash, not food, not yogurt. Cause then travel then land then settle."

# Full mood narration lines (actLine moodLine), keyed by the mood select.
# {her} = possessive of the featured body (w.p), {she} = subject form (w.s).
MOOD_LINES = {
    "calm": " MOOD calm, readable on {her} face. {her} brows stay even. {her} eyes stay open and still. {her} mouth is soft, not tight. {she} moves slow and small, even pace, no sudden jerks.",
    "shy": " MOOD shy, readable on {her} face. {her} brows lift a little. {her} eyes flick away then back. {her} mouth stays small. {she} hesitates on the first move, then stays in the act with short careful motion.",
    "eager": " MOOD eager, readable on {her} face. {her} brows lift. {her} eyes stay wide on the act. {her} mouth opens for the motion. {she} leans in first and meets the pace, no delay.",
    "hungry": " MOOD hungry, readable on {her} face. {her} brows pull in. {her} eyes stay locked on the act. {her} mouth stays open. {she} pulls closer and keeps a greedy repeating motion, no pause.",
    "playful": " MOOD playful, readable on {her} face. {her} brows tick up. {her} eyes tease, then look back at the act. {her} mouth almost smiles. {she} breaks the rhythm once on purpose, then returns to the same act.",
    "needy": " MOOD needy, readable on {her} face. {her} brows pinch. {her} eyes stay wet-looking without tears. {her} mouth stays open. {she} pulls in and does not ease off. Motion stays tight and repeating.",
    "intense": " MOOD intense, readable on {her} face. {her} brows knit. {her} eyes stay hard on the act. {her} jaw is set. {she} moves tight and controlled. No extra play. No wasted motion.",
    "spaced": " MOOD spaced out, readable on {her} face. {her} brows are slack. {her} eyes are unfocused, slow to track. {her} mouth hangs a little open. {she} moves late and loose, a beat behind the pace.",
    "tired": " MOOD tired, readable on {her} face. {her} lids are heavy. {her} brows droop. {her} mouth stays slack. {she} still does the act, but the motion is heavy and slow.",
    "sweet": " MOOD sweet, readable on {her} face. {her} brows stay soft. {her} eyes stay kind on the other body. {her} mouth is easy. {she} moves gentle and even, no snap.",
    "brat": " MOOD bratty, readable on {her} face. {her} brows lift like a challenge. {her} eyes test him. {her} mouth smirks. {she} slows or pulls the pace on purpose, then gives the act back.",
    "focused": " MOOD focused, readable on {her} face. {her} brows are still. {her} eyes stay on the work. {her} mouth is set. {she} keeps a steady work rhythm only. No tease.",
    "drunk": " MOOD loose, readable on {her} face. {her} brows lag. {her} eyes blink slow. {her} mouth is slack. {she} moves unsteady, delayed, still on the same act.",
    "scared": " MOOD nervous, readable on {her} face. {her} brows lift and stay high. {her} eyes are wide and dart. {her} mouth is tight. {she} uses short tight moves, then stays on the act.",
    "proud": " MOOD showing off, readable on {her} face. {her} chin lifts. {her} eyes hold the camera or him. {her} mouth is composed. {she} holds a pose between moves on purpose.",
    "angry": " MOOD rough heat, readable on {her} face. {her} brows slam down. {her} eyes stay hard. {her} mouth is a grimace. {she} uses hard sharp moves, no softness.",
    "sleepy": " MOOD sleepy, readable on {her} face. {her} lids keep dropping. {her} brows are slack. {her} mouth is half open. {she} moves slow and drooping, still in the act.",
    "smug": " MOOD smug, readable on {her} face. {her} brows sit high. {her} eyes look pleased. {her} mouth holds a small smirk. {she} moves slow and controlled like {she} sets the pace.",
    "lost": " MOOD lost in it, readable on {her} face. {her} brows go slack. {her} eyes roll or lose focus. {her} mouth stays open. {she} keeps an automatic rolling motion, no extra thought.",
    "teary": " MOOD overwhelmed, readable on {her} face. {her} brows pinch. {her} eyes shine and blink hard. {her} mouth shakes on the breath. {she} hitches, then stays on the same act.",
    "giggle": " MOOD giggly, readable on {her} face. {her} eyes crease. {her} mouth breaks into a short laugh shape. {she} loses the rhythm for one beat, then returns to the same act.",
    "unwilling": " MOOD unwilling, readable on {her} face. {her} brows pull tight. {her} eyes look away or shut. {her} mouth is a hard line, then a held breath. {she} turns {her} face aside. {her} body stays in the act but the motion is resisting: short, stiff, late, like {she} does not give the pace.",
    "veryunwilling": " MOOD very unwilling, readable on {her} face. {her} brows slam down. {her} eyes squeeze shut or stare off, wide and hard. {her} mouth is clenched, then a short sound of protest. {she} twists {her} face away and keeps it away. {her} body fights the motion: she pulls back, she stiffens, she tries to close. The act still happens because he holds the shape. She does not give the pace.",
}
MOOD_LINES_DEFAULT = "calm"

# Short mood lines used when a stage has a bypass text (actLine moodPack).
MOOD_LINES_BYPASS = {
    "calm": " MOOD calm, readable on {her} face. {she} keeps an even motion.",
    "shy": " MOOD shy, readable on {her} face. {she} looks down then back.",
    "eager": " MOOD eager, readable on {her} face. {she} leans in first.",
    "hungry": " MOOD hungry, readable on {her} face. {she} keeps a greedy repeating motion.",
    "playful": " MOOD playful, readable on {her} face. {she} breaks the rhythm once then returns.",
    "needy": " MOOD needy, readable on {her} face. {she} does not ease off.",
    "intense": " MOOD intense, readable on {her} face. Tight controlled motion.",
    "spaced": " MOOD spaced out, readable on {her} face. Late loose motion.",
    "tired": " MOOD tired, readable on {her} face. Heavy slow motion.",
    "sweet": " MOOD sweet, readable on {her} face. Gentle even motion.",
    "brat": " MOOD bratty, readable on {her} face. {she} pulls the pace then gives it back.",
    "focused": " MOOD focused, readable on {her} face. Steady work rhythm.",
    "drunk": " MOOD loose, readable on {her} face. Unsteady delayed motion.",
    "scared": " MOOD nervous, readable on {her} face. Short tight moves.",
    "proud": " MOOD showing off, readable on {her} face.",
    "angry": " MOOD rough heat, readable on {her} face. Hard sharp moves.",
    "sleepy": " MOOD sleepy, readable on {her} face. Slow drooping motion.",
    "smug": " MOOD smug, readable on {her} face. Slow controlled pace.",
    "lost": " MOOD lost in it, readable on {her} face. Automatic motion.",
    "teary": " MOOD overwhelmed, readable on {her} face.",
    "giggle": " MOOD giggly, readable on {her} face.",
    "unwilling": " MOOD unwilling, readable on {her} face. Stiff late motion.",
    "veryunwilling": " MOOD very unwilling, readable on {her} face. {she} fights the motion.",
}

# Facial-expression lines, keyed by the per-stage Face selects (faceLine,
# non-oral variant).
FACE_LINES = {
    "cold": " FACE cold. {her} mouth stays a hard line. No moan. {her} eyes stay flat. {her} face does not open for pleasure.",
    "flat": " FACE almost nothing. {her} mouth barely moves. No moan. {her} eyes stay even.",
    "held": " FACE holding it in. {her} lips press. {her} jaw is tight. A sound stays in {her} throat. {she} does not let the mouth open wide.",
    "warm": " FACE warm. {her} mouth parts. A soft moan. {her} brows lift a little.",
    "moan": " FACE moan. {her} mouth opens. A clear moan. {her} brows pinch. {her} eyes go soft.",
    "loud": " FACE loud moan. {her} mouth stays open. The moan is loud. {her} brows knit. {her} jaw drops.",
    "gasp": " FACE gasp. {her} mouth snaps open. A sharp inhale. {her} eyes widen. Then the mouth stays open.",
    "cryout": " FACE crying out. {her} mouth opens wide. A cry on the breath. {her} brows slam. {her} eyes squeeze.",
    "scream": " FACE screaming. {her} mouth is wide. A scream. {her} eyes squeeze shut or fly open. {her} face is all mouth and sound.",
    "orgasm": " FACE orgasming. {her} mouth hangs open. The sound breaks. {her} eyes roll or squeeze. {her} face shakes on the peak. {she} cannot hold a still mouth.",
}

# Facial-expression lines for oral acts (faceLine oral variant).
FACE_ORAL_LINES = {
    "cold": " FACE cold. Around {her} mouth on him there is no moan. {her} eyes stay flat. {her} brows do not lift.",
    "flat": " FACE almost nothing. No moan around his cock. {her} eyes stay even.",
    "held": " FACE holding it in. A sound stays in {her} throat around his cock. {her} brows pinch. {she} does not let a moan out.",
    "warm": " FACE warm. A soft moan in {her} throat around his cock. {her} brows lift a little.",
    "moan": " FACE moan. A moan leaks around {her} lips on him. {her} brows pinch. {her} eyes go soft.",
    "loud": " FACE loud moan. A loud moan around {her} lips on him. {her} brows knit.",
    "gasp": " FACE gasp. {she} pulls off just enough to gasp, mouth open, then returns. {her} eyes widen.",
    "cryout": " FACE crying out. {she} breaks the seal to cry out, mouth wide, then the act continues.",
    "scream": " FACE screaming. {her} mouth leaves him for a scream, wide open, then she can return. {her} eyes squeeze.",
    "orgasm": " FACE orgasming. {her} mouth shakes on him or comes off. The sound breaks. {her} eyes roll or squeeze. {she} cannot hold a still face.",
}

# Gaze lines (fLook), keyed by the per-stage Look selects.
# {who_s}/{who_p} = subject/possessive of the looker, {C_or_who_o}/{C_or_who_p}
# = the cock owner with fallback to the looker (JS w.o(C||who) / w.p(C||who)).
LOOK_LINES = {
    "cam": " {who_s} looks at camera. {who_p} eyes stay on the lens.",
    "him": " {who_s} looks at {C_or_who_o}. {who_p} eyes stay on {C_or_who_p} face.",
    "up": " {who_s} looks up at {C_or_who_o}.",
    "cock": " {who_s} looks at {C_or_who_p} cock.",
    "down": " {who_s} looks down.",
    "shut": " {who_p} eyes stay shut.",
    "side": " {who_s} looks to the side. {who_p} face turns away from camera a little.",
    "back": " {who_s} looks back over {who_p} shoulder.",
    "body": " {who_s} looks at {who_p} own body.",
}

# His hand placement lines (fManHand), keyed by the per-stage RH/LH selects.
# {man_p} = his possessive, {which} = "right hand"/"left hand",
# {her_p}/{her_o} = her possessive/object.
MAN_HAND_LINES = {
    "none": " {man_p} {which} stays at {man_p} side.",
    "hip": " {man_p} {which} is on {her_p} hip.",
    "waist": " {man_p} {which} is on {her_p} waist.",
    "ass": " {man_p} {which} is on {her_p} ass.",
    "breast": " {man_p} {which} is on {her_p} breast.",
    "thigh": " {man_p} {which} is on {her_p} thigh.",
    "head": " {man_p} {which} is on {her_p} head.",
    "hair": " {man_p} {which} is in {her_p} hair.",
    "face": " {man_p} {which} is on {her_p} jaw.",
    "shoulder": " {man_p} {which} is on {her_p} shoulder.",
    "back": " {man_p} {which} is on {her_p} back.",
    "cock": " {man_p} {which} is on {man_p} cock.",
    "surface": " {man_p} {which} is on the surface next to {her_o}.",
}

# Experience narration lines (expLineForShot), keyed by stage then exp select.
EXP_LINES = {
    "hj": {
        "first": "EXPERIENCE first time. Her hands do not know the grip yet. She misses the stroke, stops, starts again. Uneven. She watches her own fist like she is learning.",
        "new": "EXPERIENCE inexperienced. Her stroke is clumsy. The rhythm breaks. She corrects the grip mid-move. Trying, not clean.",
        "exp": "EXPERIENCE experienced. Her fist knows the shaft. Even stroke. She adjusts pressure without thinking.",
        "master": "EXPERIENCE master. Her hands run him. Tight, exact, no wasted motion. She sets the pace.",
    },
    "bj": {
        "first": "EXPERIENCE first time. Her mouth is unsure. She takes too little, then too much. She pulls off to breathe. Teeth almost catch. She learns the angle as she goes.",
        "new": "EXPERIENCE inexperienced. The bob is uneven. She loses the seal and finds it again. She uses her hand more than her mouth when she gets lost.",
        "exp": "EXPERIENCE experienced. Her mouth stays sealed. She knows the depth. Even bob. She breathes through her nose and stays on him.",
        "master": "EXPERIENCE master. Her mouth works him on purpose. She controls depth and tempo. No panic. No wasted motion.",
    },
    "breast": {
        "first": "EXPERIENCE first time. She does not know how to hold her breasts yet. The shaft slips out. She pushes them back together and starts again.",
        "new": "EXPERIENCE inexperienced. The slide is clumsy. She squeezes too hard, then too light. She keeps the act but the rhythm is messy.",
        "exp": "EXPERIENCE experienced. She keeps her breasts around him. Even slide. She knows when to press.",
        "master": "EXPERIENCE master. She works her chest like a grip. Exact pressure. The shaft stays in the cleavage.",
    },
    "sex": {
        "first": "EXPERIENCE first time. Her hips do not know the timing. She tenses, then moves late. Short unsure rolls. She follows him more than she leads.",
        "new": "EXPERIENCE inexperienced. Her bounce is uneven. She loses the angle and finds it. Trying to match him.",
        "exp": "EXPERIENCE experienced. Her hips meet him on time. She knows how to take the stroke. Clean motion.",
        "master": "EXPERIENCE master. She rides or takes him on purpose. She sets the grind. No wasted hip.",
    },
}

# Per-shot audio voice lines (shotAudio), keyed by the active Face select value.
SHOT_AUDIO_VOICE = {
    "cold": "Almost no voice.",
    "flat": "Almost no voice.",
    "held": "A sound stays in her throat.",
    "warm": "A soft moan.",
    "moan": "She moans.",
    "loud": "A loud moan.",
    "gasp": "She gasps.",
    "cryout": "She cries out.",
    "scream": "She screams.",
    "orgasm": "Her voice breaks.",
}

# Per-shot audio voice lines driven by the mood select (shotAudio moodV).
SHOT_AUDIO_MOOD = {
    "unwilling": "A short refuse sound.",
    "veryunwilling": "A protest sound.",
    "shy": "A small sound.",
    "scared": "A tight scared sound.",
    "teary": "A wet hitch in her breath.",
    "giggle": "A short laugh.",
    "needy": "A needy sound.",
    "hungry": "A hungry sound.",
}

# ---------------------------------------------------------------------------
# Size-fit vocabulary (sizeFitLine). Appended as " FIT: {size}. ..." where
# size = ", ".join of the length and girth words below.
# ---------------------------------------------------------------------------
GIRTH_WORDS = {"thin": "very thin", "slim": "slim", "average": "average girth", "thick": "thick", "enormous": "enormous girth"}
LEN_WORDS = {"tiny": "very tiny", "short": "short", "average": "average length", "long": "long", "verylong": "very long"}

# {her_p} = her possessive, {him_p}/{him_s} = his possessive/subject.
FIT_GIRTH_LIPS = {
    "thin": "{her_p} lips close easy around {him_p} cock with slack. The seal is loose.",
    "slim": "{her_p} lips wrap {him_p} cock clean. A normal seal.",
    "average": "{her_p} lips stretch to take {him_p} girth and stay sealed.",
    "thick": "{her_p} lips go thin and pale around {him_p} cock. They barely meet.",
    "enormous": "{her_p} lips cannot close. They stretch white around {him_p} cock. Spit leaks at the corners.",
}
FIT_GIRTH_PUSSY = {
    "thin": "{her_p} pussy takes {him_o} easy. The rim stays soft, almost no stretch.",
    "slim": "{her_p} pussy wraps {him_p} cock with a light stretch.",
    "average": "{her_p} pussy stretches around {him_p} cock. The rim is tight and wet.",
    "thick": "{her_p} pussy rim is pulled wide around {him_p} cock. The lips of {her_p} pussy flatten on the shaft.",
    "enormous": "{her_p} pussy is forced open around {him_p} cock. The rim is white-stretched. She cannot close on it.",
}
FIT_GIRTH_ASS = {
    "thin": "{her_p} anus takes {him_o} with little gape.",
    "slim": "{her_p} anus stretches a little around {him_p} cock.",
    "average": "{her_p} anus is tight around {him_p} cock. The ring holds.",
    "thick": "{her_p} anus is pulled wide. The ring is thin around {him_p} cock.",
    "enormous": "{her_p} anus is forced open. The ring cannot close. A thick gape around {him_p} cock.",
}
FIT_LEN_MOUTH = {
    "tiny": "Only the head sits in {her_p} mouth.",
    "short": "{him_p} cock fills the front of {her_p} mouth, not the throat.",
    "average": "{him_p} cock reaches the back of {her_p} tongue.",
    "long": "{him_p} cock hits {her_p} throat. {her_s} has to work to keep it.",
    "verylong": "{him_p} cock is too long for {her_p} mouth. It drives past {her_p} comfort. {her_s} cannot take the base.",
}
FIT_LEN_HOLE = {
    "tiny": "Only the head is in her.",
    "short": "Shallow. Not buried.",
    "average": "A normal depth. Hips can meet.",
    "long": "Deep. {him_p} cock runs out of room inside her.",
    "verylong": "Too long. {him_s} cannot bury the base. Her body stops the last inches.",
}
FIT_EXTRA_M2 = " This size is {him_p} cock. {m2_s} is a different cock. Do not copy this girth onto {m2_o}."

# ---------------------------------------------------------------------------
# Age lines. Three variants exist in the JS: ageLockLine (header/footer lock),
# headerText subject-definitions, and the BODY: builder (bodyInteractLine).
# ---------------------------------------------------------------------------
AGE_LOCK_F = {
    "18": "female 1 is 18, young adult female, adult body",
    "20": "female 1 is early 20s adult",
    "25": "female 1 is mid 20s adult",
    "30": "female 1 is in her 30s, adult",
    "40": "female 1 is in her 40s, mature adult",
    "50": "female 1 is in her 50s, older adult",
    "60": "female 1 is in her 60s, senior adult",
    "70": "female 1 is in her 70s, old adult",
    "80": "female 1 is in her 80s, elderly adult",
    "90": "female 1 is 90, granny, very old adult",
}
AGE_LOCK_M = {
    "18": "male 1 is 18, young adult man, adult body",
    "20": "male 1 is early 20s adult",
    "25": "male 1 is mid 20s adult",
    "30": "male 1 is in his 30s, adult",
    "40": "male 1 is in his 40s, mature adult",
    "50": "male 1 is in his 50s, older adult",
    "60": "male 1 is in his 60s, senior adult",
    "70": "male 1 is in his 70s, old adult",
    "80": "male 1 is in his 80s, elderly adult",
    "90": "male 1 is 90, grandpa, very old adult",
}
BODY_AGE_LINES_M = {
    "18": "{him_s} is 18, a young adult man. Smooth young-adult face. Adult body.",
    "20": "{him_s} is in his early 20s. Young adult man. Fresh adult face.",
    "25": "{him_s} is in his mid 20s. Adult man. Settled young-adult face.",
    "30": "{him_s} is in his 30s. Adult man. Light lines. Full grown body.",
    "40": "{him_s} is in his 40s. Mature adult man. Age lines. Not young.",
    "50": "{him_s} is in his 50s. Older adult man. Deeper lines.",
    "60": "{him_s} is in his 60s. Senior adult man. Lined skin. Older body.",
    "70": "{him_s} is in his 70s. Old adult man. Thin aged skin.",
    "80": "{him_s} is in his 80s. Elderly adult man. Deep wrinkles. Old body.",
    "90": "{him_s} is 90. Grandpa. Very old adult man. Heavy wrinkles. Frail old body.",
}
BODY_AGE_LINES_F = {
    "18": "{her_s} is 18, a young adult female. Smooth young-adult face. Adult body.",
    "20": "{her_s} is in her early 20s. Young adult female. Fresh adult face.",
    "25": "{her_s} is in her mid 20s. Adult female. Settled young-adult face.",
    "30": "{her_s} is in her 30s. Adult female. Light lines. Full grown body.",
    "40": "{her_s} is in her 40s. Mature adult female. Age lines. Not young.",
    "50": "{her_s} is in her 50s. Older adult female. Deeper lines.",
    "60": "{her_s} is in her 60s. Senior adult female. Lined skin. Older body.",
    "70": "{her_s} is in her 70s. Old adult female. Thin aged skin.",
    "80": "{her_s} is in her 80s. Elderly adult female. Deep wrinkles. Old body.",
    "90": "{her_s} is 90. Granny. Very old adult female. Heavy wrinkles. Frail old body.",
}

# ---------------------------------------------------------------------------
# Subject-definition word maps (headerText).
# ---------------------------------------------------------------------------
MAN_LOOK_WORDS = {
    "asref": "same face as the picture",
    "normal": "ordinary male face, not ugly, not model-handsome",
    "ugly": "ugly male face, uneven, heavy features, not handsome",
    "handsome": "handsome male face, clear jaw, good features",
    "rough": "rough male face, lined, hard mouth, short stubble",
}
MAN_BODY_WORDS = {
    "asref": "same body as the picture",
    "skinny": "skinny male body, thin frame, little fat, narrow waist, lean arms and legs, hip bones and ribs readable, light weight",
    "average": "average male body, not skinny, not fat, normal belly, normal weight",
    "fat": "fat male body, soft thick belly that hangs a little, heavy chest, thick arms and thighs, real extra weight when he leans on her",
    "obese": "obese male body, very large and very fat, huge hanging belly, thick rolls at the waist and back, wide heavy hips and thighs, dense weight that pins and presses, breath heavy",
    "muscular": "muscular male body, thick chest and arms, visible muscle, tight hard stomach, heavy in a hard way not a soft belly",
    "stocky": "stocky male body, short thick torso, wide shoulders, heavy limbs, dense compact weight, not tall, not skinny",
}
MAN_MOOD_WORDS = {"calm": "calm man", "hungry": "hungry man", "rough": "rough heavy-handed man", "gentle": "gentle man", "smug": "smug man", "focused": "focused man", "eager": "eager man"}
MAN_LEN_WORDS = {"tiny": "very tiny short cock", "short": "short cock", "average": "average length cock", "long": "long cock", "verylong": "very long cock"}
MAN_GIRTH_WORDS = {"thin": "very thin cock", "slim": "slim cock", "average": "average girth cock", "thick": "thick girthy cock", "enormous": "enormous girth cock"}
MAN_AGE_WORDS = {
    "18": "18 year old adult man. Young adult face. Smooth skin. Adult body, not a boy.",
    "20": "early 20s adult man. Young adult face. Fresh skin. Adult frame.",
    "25": "mid 20s adult man. Settled young adult face. Adult body.",
    "30": "30s adult man. Adult face. Light lines at the eyes. Adult body, full grown.",
    "40": "40s adult man. Mature face. Clear age lines. Adult body. Not young.",
    "50": "50s adult man. Older adult face. Deeper lines. Adult body with age on it.",
    "60": "60s adult man. Senior adult face. Grey in the hair if it shows. Lined skin. Older adult body.",
    "70": "70s older adult man. Aged face. Thin skin. Visible age. Old adult body.",
    "80": "80s old adult man. Elderly face. Deep wrinkles. Thin old skin. Old adult body.",
    "90": "90 year old grandpa. Very old adult man. Heavy wrinkles. Loose old skin. Frail old adult body. Not young.",
}
MAN_SKIN_WORDS = {"pale": "pale white skin", "fair": "fair skin", "light": "light skin", "olive": "olive skin", "tan": "tan skin", "brown": "brown skin", "dark": "dark skin", "deep": "deep dark skin"}
COCK_SIZE_LEN_WORDS = {"tiny": "very tiny", "short": "short", "average": "average length", "long": "long", "verylong": "very long"}
COCK_SIZE_GIRTH_WORDS = {"thin": "very thin", "slim": "slim", "average": "average girth", "thick": "thick", "enormous": "enormous girth"}
COCK_SIZE_DEFAULT = "hard veiny cock"

FEM_BREAST_CLOTHED = {
    "flat": "very small flat chest as shape under her clothes, fabric stays on",
    "small": "small breasts as shape under her clothes, fabric stays on, not bare",
    "medium": "medium breasts as shape under her clothes, fabric stays on, not bare",
    "large": "large heavy breasts as shape under her clothes, fabric stays on, not bare",
    "huge": "huge heavy breasts as shape under her clothes, fabric stays on, not bare",
}
FEM_BREAST_BARE = {
    "flat": "very small flat chest, almost no breast, no bounce",
    "small": "small light breasts, little bounce",
    "medium": "medium breasts, clear shape, moderate bounce",
    "large": "large heavy breasts, visible weight, they bounce and flatten",
    "huge": "huge heavy breasts, a lot of mass, they swing, spill and press",
}
FEM_ASS_CLOTHED = {
    "flat": "flat ass as shape under her clothes, fabric stays on",
    "small": "small ass as shape under her clothes, fabric stays on",
    "round": "round ass as shape under her clothes, fabric stays on",
    "big": "big ass as shape under her clothes, fabric stays on, not bare",
    "huge": "huge ass as shape under her clothes, fabric stays on, not bare",
}
FEM_ASS_BARE = {
    "flat": "flat ass, little meat",
    "small": "small ass",
    "round": "round ass, clear shape",
    "big": "big ass, heavy, it slaps and spreads",
    "huge": "huge heavy ass, a lot of mass, it shakes and flattens",
}
FEM_HEIGHT_WORDS = {"tiny": "very short height, small against him", "short": "short height", "average": "average height", "tall": "tall height, long limbs", "giant": "giant height, she towers"}
FEM_FRAME_WORDS = {
    "petite": "very petite frame, small bones, thin limbs, little weight",
    "slim": "slim frame, narrow waist, little fat, light body",
    "average": "average female frame, normal waist and thighs",
    "thick": "thick frame, wide hips, heavy thighs, soft waist, meat on the motion",
    "fat": "fat frame, soft belly, thick arms and thighs, flesh jiggles, extra weight",
    "obese": "obese heavy frame, very large, thick rolls, big belly, heavy arms and thighs, real mass that moves slow",
}
FEM_AGE_WORDS = {
    "18": "18 year old adult female. Young adult face. Smooth skin. Adult body, not a child.",
    "20": "early 20s adult female. Young adult face. Fresh skin. Adult frame.",
    "25": "mid 20s adult female. Settled young adult face. Adult body.",
    "30": "30s adult female. Adult face. Light lines at the eyes. Adult body, full grown.",
    "40": "40s adult female. Mature face. Clear age lines. Adult body. Not young.",
    "50": "50s adult female. Older adult face. Deeper lines. Adult body with age on it.",
    "60": "60s adult female. Senior adult face. Age in the hair if it shows. Lined skin. Older adult body.",
    "70": "70s older adult female. Aged face. Thin skin. Visible age. Old adult body.",
    "80": "80s old adult female. Elderly face. Deep wrinkles. Thin old skin. Old adult body.",
    "90": "90 year old granny. Very old adult female. Heavy wrinkles. Loose old skin. Frail old adult body. Not young.",
}
FEM_CLOTHED_BIT = "clothes from the picture stay on. Body size is shape under fabric. Not already nude"

# Short word maps used by the header's SELECT recap lines ("FEMALE SELECT: ...",
# "MAN SELECT: ..."). asref reads "like the picture"; missing keys fall back to
# the raw select value.
FEMALE_SELECT_WORDS = {
    "breast": {"asref": "like the picture", "flat": "very small flat", "small": "small", "medium": "medium", "large": "large", "huge": "huge"},
    "height": {"asref": "like the picture", "tiny": "very small", "short": "short", "average": "average", "tall": "tall", "giant": "giant"},
    "frame": {"asref": "like the picture", "petite": "very petite", "slim": "slim", "average": "average", "thick": "thick", "fat": "fat", "obese": "obese heavy"},
    "ass": {"asref": "like the picture", "flat": "flat", "small": "small", "round": "round", "big": "big", "huge": "huge"},
}
MAN_SELECT_WORDS = {
    "look": {"asref": "like the picture", "normal": "normal face", "ugly": "ugly face", "handsome": "handsome face", "rough": "rough face"},
    "body": {"asref": "like the picture", "skinny": "skinny thin frame", "average": "average build", "fat": "fat soft belly", "obese": "obese heavy hanging belly", "muscular": "muscular defined", "stocky": "stocky thick torso"},
    "mood": {"calm": "calm", "hungry": "hungry", "rough": "rough", "gentle": "gentle", "smug": "smug", "focused": "focused", "eager": "eager"},
}

# ---------------------------------------------------------------------------
# Not extracted (remain JS logic in h3_scene_studio.html, not select-keyed
# data): the per-act/per-phase action sentence generator (actLine "dyn" map),
# the male-2 / female-2 choreography line builders (male2LineCore /
# female2LineCore and their bj/sx position maps), the BODY: builder
# (bodyInteractLine), the FORCED: lines (forcedActLine), the physics() map and
# the subject_definitions/refBlock header templates. All of them are plain
# concatenations of the phrases above with the pronoun placeholders described
# in the module docstring.
# ---------------------------------------------------------------------------

__all__ = [
    "PRESET", "POS", "DIST_NAME", "DIST", "ANGLE", "POV", "MOVE", "ACTS",
    "PHASES", "MOOD", "HANDS", "ROUGH", "EYES", "KISS", "TALK", "AUDIO",
    "AUDIO_STAGE", "FORMAT", "STYLE", "FINISH", "CLOTHES", "CLOTH_MESS",
    "MAN_CLOTHES", "PLACE", "PLACE_LIGHT", "POOL",
    "HEIGHT", "ANGLELOCK", "MOVELOCK", "SPEED", "STAB", "LENS", "FOLLOW",
    "STAGES", "STAGE_PHASE_MAP", "STAGE_FORMAT_SLOT", "STAGE_CAM_PREFIX",
    "PHASE_ARCS", "PHASE_BAND", "PHASE_OVERRIDE_DOING", "STAGE_POS_LINES",
    "MEME_POS_WORDS", "MEME_TEMPLATES",
    "ARTIFACT_LOCK_LIGHT", "ARTIFACT_LOCK_FULL_SUFFIX",
    "MAN_JOIN_LINE", "FORCE_REF_LINE", "CAM_REF_BLOCK", "PRESERVE_OPTS",
    "STAGE_BRIDGES", "DRIVE_LINES", "SCREEN_DIRECTION_LINES",
    "FRAME_EXTRA_LINES", "FRAME_GROUP_LINES", "EXTRA_WATCH_LINES",
    "RELATE_LINES",
    "INTRO_DO_LINES", "INTRO_DO_UNDEF", "TEASE_DO_LINES", "TEASE_DO_UNDEF",
    "HJ_POS_LINES", "BJ_POS_LINES", "BJ_POS_DETAIL", "HJ_POS_DETAIL",
    "SEX_POS_DETAIL", "BREAST_STANCE_DETAIL", "BREAST_STANCE_LINE",
    "HJ_GRIP_LINES", "HJ_GRIP_FALLBACK", "HJ_TEMPO_LINES",
    "BJ_DEPTH_LINES", "BJ_WET_LINES", "BJ_TEMPO_LINES", "BJ_HANDS_LINES",
    "BREAST_KIND_LINES", "BREAST_KIND_UNDEF",
    "SX_BOUNCE_LINES", "SX_BOUNCE_DEFAULT",
    "SEX_ACT_TEMPLATE", "SEX_HOLE_TEMPLATES",
    "CUM_HOW_LINES", "CUM_QTY_LINES", "CUM_QTY_DEFAULT",
    "CUM_LAND_LINES", "CUM_LAND_UNDEF", "CUM_OPENING", "CUM_FLUID_RULE",
    "MOOD_LINES", "MOOD_LINES_DEFAULT", "MOOD_LINES_BYPASS",
    "FACE_LINES", "FACE_ORAL_LINES", "LOOK_LINES", "MAN_HAND_LINES",
    "EXP_LINES", "SHOT_AUDIO_VOICE", "SHOT_AUDIO_MOOD",
    "GIRTH_WORDS", "LEN_WORDS", "FIT_GIRTH_LIPS", "FIT_GIRTH_PUSSY",
    "FIT_GIRTH_ASS", "FIT_LEN_MOUTH", "FIT_LEN_HOLE", "FIT_EXTRA_M2",
    "AGE_LOCK_F", "AGE_LOCK_M", "BODY_AGE_LINES_M", "BODY_AGE_LINES_F",
    "MAN_LOOK_WORDS", "MAN_BODY_WORDS", "MAN_MOOD_WORDS", "MAN_LEN_WORDS",
    "MAN_GIRTH_WORDS", "MAN_SKIN_WORDS", "COCK_SIZE_LEN_WORDS",
    "COCK_SIZE_GIRTH_WORDS", "COCK_SIZE_DEFAULT",
    "FEM_BREAST_CLOTHED", "FEM_BREAST_BARE", "FEM_ASS_CLOTHED",
    "FEM_ASS_BARE", "FEM_HEIGHT_WORDS", "FEM_FRAME_WORDS", "FEM_CLOTHED_BIT",
    "FEMALE_SELECT_WORDS", "MAN_SELECT_WORDS",
]
