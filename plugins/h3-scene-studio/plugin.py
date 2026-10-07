"""H3 Scene Studio - a WanGP plugin
---------------------------------
Native Gradio scene builder for MiniMax H3 Ref2VA: reference photos,
randomized timed shots, camera/sound control, and a one-click push of the
finished English prompt (and the attached photos) into the main generator.
UI is Russian; the prompt itself stays English for the model.
"""

import json
import os
import shutil
import time

import gradio as gr

from shared.utils.plugins import WAN2GPPlugin

from . import engine
from . import scene_store
from .vocab import (
    STYLE, INTRO_DO_LINES, TEASE_DO_LINES, HJ_POS_DETAIL, BJ_POS_DETAIL,
    BREAST_KIND_LINES, SEX_POS_DETAIL, CUM_HOW_LINES, CUM_LAND_LINES,
    MAN_HAND_LINES, LOOK_LINES, RELATE_LINES, EXTRA_WATCH_LINES, ANGLELOCK,
    MOVELOCK, FORMAT, MOOD_LINES, FACE_LINES, BJ_DEPTH_LINES, BJ_WET_LINES,
    BJ_TEMPO_LINES, BJ_HANDS_LINES, HJ_GRIP_LINES, HJ_TEMPO_LINES,
    SX_BOUNCE_LINES, MAN_LOOK_WORDS, MAN_BODY_WORDS, MAN_SKIN_WORDS,
    FEM_HEIGHT_WORDS, FEM_FRAME_WORDS,
)
from .engine import RU_CLOTHES, RU_PLACE

PlugIn_Name = "H3 Scene Studio"
PlugIn_Id = "H3SceneStudio"

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(PLUGIN_DIR, "photos")
SCENES_DIR = os.path.join(PLUGIN_DIR, "scenes")

_THEME = """
<style>
.h3ss .wrap, .h3ss { gap: 6px !important; }
.h3ss h2, .h3ss h3 { letter-spacing: .02em; }
.h3ss-acc > .label-wrap > span {
  color: #ff7ab0 !important; font-weight: 700 !important; letter-spacing: .04em;
}
.h3ss-note { color: #c48aa3 !important; font-size: 12px !important; }
.h3ss-out textarea { font-family: ui-monospace, monospace !important; font-size: 12.5px !important; }
.h3ss-btn { background: linear-gradient(180deg,#ff6eae,#ff2d6f) !important;
  color: #1a0a10 !important; font-weight: 700 !important; border: 0 !important; }
.h3ss-btn-green { background: linear-gradient(180deg,#6ee7a0,#1f9d55) !important;
  color: #06210f !important; font-weight: 700 !important; border: 0 !important; }
</style>"""


def _c(keys, ru):
    return [(k, ru.get(k, k)) for k in keys]


# ---------------------------------------------------------------------------
# Russian option labels (value -> display)
# ---------------------------------------------------------------------------
RU = {}

RU["cast"] = [("fm", "1Ж + 1М"), ("ff", "2Ж"), ("mm", "2М"), ("fmm", "1Ж + 2М"),
              ("ffm", "2Ж + 1М"), ("fff", "3Ж"), ("mmm", "3М"), ("ffmm", "2Ж + 2М"),
              ("soloF", "соло девушка"), ("soloM", "соло мужчина")]
RU["relate"] = [("off", "выкл"), ("any", "любые")] + _c(RELATE_LINES, {
    "strangers": "просто знакомые", "couple": "пара", "married": "женаты",
    "ex": "бывшие", "dad": "отец + дочь (взрослые)", "mom": "мать + сын (взрослые)",
    "brother": "брат + сестра (взрослые)", "sister": "сестра + брат (взрослые)"})
RU["mood"] = [("any", "любое")] + _c(MOOD_LINES, {
    "calm": "спокойное", "shy": "застенчивое", "eager": "жаждущее", "hungry": "голодное",
    "playful": "игривое", "needy": "томное", "intense": " напряжённое", "spaced": "в прострации",
    "tired": "усталое", "sweet": "нежное", "brat": "дерзкое", "focused": "сосредоточенное",
    "drunk": "расслабленное", "scared": "нервное", "proud": "выпендрёжное", "angry": "грубое",
    "sleepy": "сонное", "smug": "самодовольное", "lost": "потерянное", "teary": "на слезах",
    "giggle": "хихикающее", "unwilling": "несогласное", "veryunwilling": "категорично против"})
RU["face"] = [("off", "выкл"), ("any", "любое")] + _c(FACE_LINES, {
    "cold": "холодное", "flat": "почти ничего", "held": "сдерживает", "warm": "тихий стон",
    "moan": "стон", "loud": "громкий стон", "gasp": "сбивается на вдох",
    "cryout": "вскрикивает", "scream": "кричит", "orgasm": "кончает"})
RU["exp"] = [("any", "любой"), ("first", "первый раз"), ("new", "неопытный"),
             ("exp", "опытный"), ("master", "мастер")]
RU["format"] = [("off", "выкл"), ("any", "любой")] + _c(FORMAT, {
    "interview": "интервью / кастинг", "bet": "спор", "stuck": "застряли",
    "robbed": "обчистили", "webcam": "вебкам-шоу", "walkin": "застукали",
    "makeup": "за макияжем", "firstdeal": "первая сделка", "cuck": "внимает третий",
    "blackmail": "шантаж"})
RU["mode"] = [("sequence", "Последовательность — кадр на акт"), ("single", "Один кадр — первый акт")]
RU["fAge"] = [("asref", "как в референсе"), ("any", "любой")] + \
    [(a, a) for a in ("18", "20", "25", "30", "40", "50", "60", "70", "80", "90")]
RU["fBreast"] = [("asref", "как в референсе"), ("any", "любая"), ("flat", "очень маленькая"),
                 ("small", "маленькая"), ("medium", "средняя"), ("large", "большая"), ("huge", "огромная")]
RU["fHeight"] = [("asref", "как в референсе"), ("any", "любой")] + _c(FEM_HEIGHT_WORDS, {
    "tiny": "очень низкая", "short": "низкая", "average": "средний", "tall": "высокая", "giant": "гигант"})
RU["fFrame"] = [("asref", "как в референсе"), ("any", "любой")] + _c(FEM_FRAME_WORDS, {
    "petite": "миниатюрная", "slim": "худая", "average": "среднее", "thick": "плотная",
    "fat": "толстая", "obese": "очень полная"})
RU["fClothed"] = [("clothed", "одета — формы под тканью"), ("bare", "уже обнажена")]
RU["mAge"] = RU["fAge"]
RU["mLook"] = [("asref", "как в референсе"), ("any", "любой")] + _c(MAN_LOOK_WORDS, {
    "normal": "обычное", "ugly": "некрасивое", "handsome": "красивое", "rough": "грубое"})
RU["mBody"] = [("asref", "как в референсе"), ("any", "любой")] + _c(MAN_BODY_WORDS, {
    "skinny": "худой", "average": "среднее", "fat": "толстый, мягкий живот",
    "obese": "ожирение, большой живот", "muscular": "мускулистый", "stocky": "коренастый"})
RU["mSkin"] = [("asref", "как в референсе"), ("any", "любая")] + _c(MAN_SKIN_WORDS, {
    "pale": "бледная", "fair": "светлая", "light": "светло-бежевая", "olive": "оливковая",
    "tan": "загорелая", "brown": "смуглая", "dark": "тёмная", "deep": "очень тёмная"})
RU["mLen"] = [("asref", "как в референсе"), ("any", "любая"), ("tiny", "очень маленький"),
              ("short", "короткий"), ("average", "средний"), ("long", "длинный"), ("verylong", "очень длинный")]
RU["mGirth"] = [("asref", "как в референсе"), ("any", "любой"), ("thin", "очень тонкий"),
                ("slim", "тонкий"), ("average", "средний"), ("thick", "толстый"), ("enormous", "огромный")]
RU["clothes"] = _c(RU_CLOTHES.keys(), RU_CLOTHES)
RU["clothMess"] = [("asref", "как в референсе"), ("neat", "сидит как надета"),
                   ("displaced", "сбита, задрана, наполовину снята"),
                   ("wrecked", "растянута, в пятнах, сползла")]
RU["place"] = _c(RU_PLACE.keys(), RU_PLACE)
RU["placeLight"] = [("asref", "как в референсе"), ("day", "дневной свет из окна"),
                    ("lamps", "тёплые лампы"), ("dim", "приглушённый свет"),
                    ("neon", "дешёвый неон"), ("night", "ночное помещение"),
                    ("harsh", "жёсткий верхний"), ("candle", "свечи"), ("moon", "лунный свет"),
                    ("storm", "вспышки грозы"), ("red", "красный свет")]
RU["camMode"] = [("auto", "Авто — камера на каждый кадр"), ("style", "Стиль-пак — задаёт всю камеру"),
                 ("ref", "Как Картинка 1 — без новой камеры")]
RU["camStyle"] = [("off", "выкл")] + [(k, STYLE[k].get("label", k)) for k in STYLE]
RU["camDist"] = [("any", "любая"), ("ecu", "сверхкрупный"), ("cu", "крупный"),
                 ("mcu", "средне-крупный"), ("ms", "средний"), ("loose", "общий"), ("macro", "деталь/макро")]
RU["camAngle"] = [("any", "любой")] + _c(ANGLELOCK, {
    "front": "спереди", "profile": "в профиль", "3q": "три четверти", "3qrear": "три четверти сзади",
    "ots": "через плечо от тела", "ots2": "через её плечо", "ots-g": "через плечо от него",
    "ots-r": "через плечо, обратный", "behind": "сзади", "between": "между телами",
    "lowup": "снизу вверх", "highdown": "сверху вниз", "worm": "от самого пола",
    "bird": "сверху, вид с птичьего полёта", "hip": "сбоку на уровне бёдер",
    "dutch": "голландский угол", "throughlegs": "между ног", "pov": "от первого лица"})
RU["camHeight"] = [("any", "любая"), ("floor", "у пола"), ("hip", "уровень бёдер"),
                   ("chest", "уровень груди"), ("eye", "уровень глаз"), ("above", "сверху"),
                   ("overhead", "строго сверху")]
RU["camMove"] = [("any", "любое")] + _c(MOVELOCK, {
    "static": "статика", "push": "медленный наезд", "pull": "медленный отъезд",
    "arc": "медленная дуга", "orbit": "облёт", "pan": "панорама", "tilt": "наклон от лица к телу",
    "truck": "сдвиг влево/вправо", "boom": "подъём/спуск камеры", "rise": "подъём вдоль тела",
    "drop": "спуск вдоль тела", "rack": "перевод фокуса", "follow": "следование за движением",
    "creep": "подкрадывание", "peek": "подглядывание из-за тела", "hand": "с рук",
    "shake": "грубая тряска с рук"})
RU["camSpeed"] = [("any", "любая"), ("vslow", "очень медленно"), ("slow", "медленно"),
                  ("medium", "средне"), ("fast", "быстро"), ("vfast", "очень быстро"), ("absurd", "бешено")]
RU["camStab"] = [("any", "любая"), ("locked", "штатив"), ("micro", "микро-покачивание"),
                 ("hand", "ровно с рук"), ("dirty", "грязная тряска с рук")]
RU["camLens"] = [("any", "любой"), ("tight", "длинный, сжатая перспектива"),
                 ("normal", "нормальный"), ("wide", "широкий, тела в кадре")]
RU["camFollow"] = [("any", "любое"), ("join", "держать оба тела в кадре"),
                   ("face", "держать лицо в кадре"), ("hips", "держать бёдра в кадре"),
                   ("both", "лицо и торс в кадре")]
RU["look"] = _c(LOOK_LINES, {"cam": "в камеру", "him": "на него", "up": "вверх на него",
                             "cock": "на его член", "down": "вниз", "shut": "глаза закрыты",
                             "side": "в сторону", "back": "назад через плечо", "body": "на своё тело"})
RU["hand"] = [("off", "нет в кадре"), ("any", "любое")] + _c(MAN_HAND_LINES, {
    "none": "у бедра", "hip": "на её бедре", "waist": "на её талии", "ass": "на её заднице",
    "breast": "на её груди", "thigh": "на её ляжке", "head": "на её голове", "hair": "в её волосах",
    "face": "на её подбородке", "shoulder": "на её плече", "back": "на её спине",
    "cock": "на его члене", "surface": "на поверхности"})
RU["introDo"] = [("undef", "не задано — только действие"), ("any", "любое")] + _c(INTRO_DO_LINES, {
    "look": "смотрит в камеру", "wave": "машет", "sit": "садится", "walk": "заходит", "turn": "поворачивается",
    "talk": "здоровается", "lean": "наклоняется", "hair": "поправляет волосы", "smile": "улыбается",
    "stand": "просто стоит", "sitedge": "садится на край", "cross": "закидывает ногу", "stretch": "потянулась",
    "yawn": "зевает", "phone": "с телефоном, потом поднимает взгляд", "door": "входит и замирает",
    "mirror": "смотрится в зеркало", "fixcloth": "поправляет одежду", "sitclose": "садится ближе к нему",
    "nod": "кивает в камеру", "point": "показывает на что-то", "drink": "делает глоток",
    "wait": "ждёт, переминается", "kneelsoft": "встает на колени, SFW", "tiehair": "собирает волосы",
    "kickshoes": "снимает туфли", "sitfloor": "садится на пол", "leanwall": "опирается на стену",
    "lookhim": "смотрит сначала на него", "shrug": "пожимает плечами", "adjustsit": "пересаживается",
    "foldhands": "складывает руки на коленях", "rubeyes": "трёт глаза",
    "comein": "заходит с улыбкой", "takehand": "берёт его за руку", "sitwith": "садится с ним",
    "leanhim": "опирается на него", "kisscheek": "целует в щёку", "callhim": "подзывает его",
    "patseat": "хлопает по месту рядом", "hugbrief": "короткие объятия",
    "turnaway": "отворачивает лицо", "stepback": "отступает от него", "pushhand": "сбрасывает его руку",
    "armsx": "скрещивает руки", "lookdoor": "смотрит к выходу", "sitfar": "садится подальше",
    "shakehead": "качает головой «нет»", "holdcloth": "придерживает одежду", "glare": "смотрит со злостью",
    "scoff": "фыркает", "snaptalk": "огрызается", "argue": "спорит, тычет в него пальцем",
    "shove": "толкает его в грудь", "slaphand": "отбивает его руку", "staredown": "сверлит взглядом",
    "block": "преграждает путь", "turnback": "поворачивается спиной", "refusesit": "отказывается садиться",
    "finger": "указывает на дверь", "jaw": "сжимает челюсть, враждебно"})
RU["teaseDo"] = [("undef", "не задано — только действие"), ("any", "любое")] + _c(TEASE_DO_LINES, {
    "strap": "стягивает бретель", "hem": "приподнимает подол", "turn": "поворачивается спиной",
    "lift": "задирает топ", "bend": "наклоняется, смотрит назад", "touch": "гладит себя поверх одежды",
    "unzip": "расстёгивает молнию", "thigh": "ведёт рукой по бедру", "neck": "трогает шею и грудь",
    "sitopen": "садится, раскрывает колени", "flash": "на секунду показывает грудь",
    "waist": "засовывает пальцы за пояс", "asidep": "отводит ткань в сторону", "hips": "качает бёдрами",
    "grind": "трётся одетая", "lap": "садится на него сверху, одетая", "crawl": "подползает ближе",
    "lieback": "ложится, колени подняты", "squeeze": "сжимает грудь поверх одежды",
    "ass": "показывает зад, смотрит назад", "licklips": "облизывает губы",
    "hairtoss": "отбрасывает волосы, грудь вперёд", "pullhim": "тянет его за рубашку",
    "trace": "ведёт пальцем по его ширинке", "kissneck": "целует шею", "ear": "шепчет на ухо",
    "straddle": "садится на него верхом, одетая", "pushdown": "кладёт его на спину",
    "guidehand": "кладёт его руку себе на талию", "bitelip": "прикусывает губу",
    "skirtup": "задирает юбку и держит", "braoff": "спускает бретель, лифчик ещё на",
    "peek": "заглядывает под свой топ", "spin": "медленно крутится", "onallfours": "на четвереньках, смотрит назад",
    "foot": "кладёт ногу ему на бедро", "undobelt": "расстёгивает его ремень и останавливается",
    "shirtuphim": "задирает его футболку", "closehips": "прижимается бёдрами к нему",
    "whisper": "наклоняется прошептать", "mirrorpose": "позирует у зеркала",
    "hippop": "выпячивает бедро", "slowundress": "снимает одну вещь и замирает",
    "braopen": "расстёгивает лифчик, не снимая", "pantypeel": "спускает трусики на сантиметр",
    "wetfinger": "смачивает палец, ведёт по губе", "sitonthigh": "садится на его бедро",
    "handswalk": "идёт руками по его груди", "lookbackcrawl": "уползает, оглядываясь",
    "rubclothed": "трётся между ног поверх одежды", "showpanties": "задирает подол, показывает бельё",
    "kneesqueeze": "сжимает колени и раскрывает", "startundress": "начинает раздеваться для него",
    "puthishand": "кладёт его руку себе на грудь", "openforhim": "раскрывает колени для него",
    "pullhip": "тянет его за бёдра", "showhim": "показывает себя нарочно",
    "kissdown": "целует вниз по его груди", "climbhim": "взбирается на него",
    "beglook": "смотрит так, что хочет этого", "coverup": "прикрывается, он смотрит",
    "holdhem": "прижимает подол", "twistaway": "выкручивается в сторону",
    "pushchest": "упирается ему в грудь", "clampknees": "сжимает колени",
    "fixstrap": "ставит бретель на место", "turnface": "отворачивается, пока он дразнит",
    "grabwrist": "хватает его запястье"})
RU["hjPos"] = [("any", "любая")] + _c(HJ_POS_DETAIL, {
    "kneel": "на коленях у его бёдер", "lap": "рядом, рука у него на коленях", "sit": "сидит, он стоит",
    "side": "сбоку", "himlie": "он лежит", "stand": "он стоит, она рядом", "between": "между его ног",
    "proneglute": "он на животе, она сзади", "behind": "сзади него", "spoon": "на боку, сзади",
    "sitspread": "он сидит, ноги шире", "shestand": "она стоит", "bothkneel": "оба на коленях",
    "shelie": "она лежит рядом", "thighsit": "сидит на его бедре", "fly": "стоя, лицом к нему",
    "under": "снизу", "overhand": "сверху захватом"})
RU["hjGrip"] = [("any", "любой")] + _c(HJ_GRIP_LINES, {
    "one": "одна ладонь", "two": "две руки", "twist": "с выкрутом", "head": "ладонь на головке",
    "balls": "вторая рука на яйцах"})
RU["hjTempo"] = RU["bjTempo"] = [("any", "любой"), ("slow", "медленно"), ("even", "ровно"), ("fast", "быстро")]
RU["bjPos"] = [("any", "любая")] + _c(BJ_POS_DETAIL, {
    "kneel": "на коленях между ног", "edge": "он у края поверхности, она сидит",
    "stand": "она стоит перед ним", "lap": "сверху на нём", "floor": "на полу",
    "side": "лёжа на боку", "lyingback": "он лежит, она сверху ртом", "edgehead": "она с запрокинутой головой с края",
    "himlie": "он лежит на спине", "sitbetween": "он сидит, она между ног",
    "wall": "у стены", "bededge": "у края кровати", "allfours": "на четвереньках",
    "squat": "на корточках", "sidelie": "оба на боку", "sixty": "69",
    "under": "он стоит над ней", "chair": "он в кресле"})
RU["bjDepth"] = [("any", "любая")] + _c(BJ_DEPTH_LINES, {
    "lick": "только языком", "lips": "только головка в губах", "half": "наполовину",
    "full": "до основания", "deep": "в горло"})
RU["bjWet"] = [("any", "любая"), ("clean", "сухо, чисто"), ("wet", "мокро"), ("sloppy", "слюни по стволу")]
RU["bjHands"] = [("any", "любое")] + _c(BJ_HANDS_LINES, {
    "base": "рука у основания", "two": "обе руки на стволе", "balls": "вторая на яйцах",
    "thighs": "руки на его бёдрах", "none": "только рот"})
RU["breastKind"] = [("any", "любой")] + _c(BREAST_KIND_LINES, {
    "titfuck": "между грудей", "worship": "ртом по её груди", "squeeze": "сжимает её грудь",
    "lick": "лижет её грудь", "reverse": "она сверху, грудью вниз", "under": "он снизу между грудей",
    "spit": "плюёт на грудь", "slaphead": "головкой по соскам", "presswalk": "прижимает её грудь к себе",
    "nipplesuck": "сосёт соски", "facepress": "она прижимает грудь к его лицу",
    "oil": "масло на груди", "holdout": "держит грудь ладонями", "sideboob": "боком между грудей"})
RU["sexPos"] = [("any", "любая")] + _c(SEX_POS_DETAIL, {
    "missionary": "наездница наоборот — она на спине", "doggy": "сзади на четвереньках",
    "cowgirl": "она сверху", "standing": "стоя", "side": "на боку", "seated": "он сидит, она сверху",
    "folded": "сложенная", "prone": "она на животе, он сверху"})
RU["sexHole"] = [("vaginal", "вагинальный"), ("anal", "анальный")]
RU["sexBounce"] = [("any", "любая")] + _c(SX_BOUNCE_LINES, {
    "none": "почти без движения", "small": "небольшая", "medium": "заметная", "hard": "сильная"})
RU["cumHow"] = [("any", "любой")] + _c(CUM_HOW_LINES, {
    "pulse": "пульсация", "leak": "вытекает", "dribble": "по капле", "ropes": "струями", "spray": "фонтаном"})
RU["cumQty"] = [("any", "любое")] + _c([k for k in ("drops", "little", "normal", "heavy", "huge", "gallons")], {
    "drops": "пара капель", "little": "немного", "normal": "обычно", "heavy": "много",
    "huge": "очень много", "gallons": "нереально много"})
RU["cumLand"] = [("any", "любое")] + _c(CUM_LAND_LINES, {
    "mouth": "в рот", "swallow": "в рот, она глотает", "tongue": "на язык", "face": "на лицо",
    "lips": "на губы", "breasts": "на грудь", "stomach": "на живот", "back": "на спину",
    "ass": "на задницу", "hand": "на руку", "inside": "внутрь", "pullout": "вытаскивает и кончает"})
RU["inFrame"] = [("off", "выкл")] + _c(EXTRA_WATCH_LINES, {
    "bf": "парень смотрит", "gf": "подруга смотрит", "strangerM": "незнакомец смотрит",
    "strangerF": "незнакомка смотрит", "two": "двое смотрят", "few": "несколько человек смотрят",
    "crowd": "толпа сзади"})
RU["picWho"] = [("f", "девушка (субъект 1)"), ("m", "мужчина (субъект 2)")]
RU["introLookName"] = RU["look"]
RU["teaseLookName"] = RU["look"]
for _h in ("introRH", "introLH", "teaseRH", "teaseLH"):
    RU[_h] = RU["hand"]


def _choices(name):
    return RU.get(name, [])


# ---------------------------------------------------------------------------
# plugin
# ---------------------------------------------------------------------------

class H3SceneStudioPlugin(WAN2GPPlugin):
    def setup_ui(self):
        self.request_component("prompt")
        self.request_component("image_refs")
        self.add_tab(tab_id=PlugIn_Id, label=PlugIn_Name, component_constructor=self.create_tab)

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _sets_list():
        os.makedirs(PHOTOS_DIR, exist_ok=True)
        return sorted(d for d in os.listdir(PHOTOS_DIR)
                      if os.path.isdir(os.path.join(PHOTOS_DIR, d)) and not d.startswith("_"))

    @staticmethod
    def _set_paths(setname):
        folder = os.path.join(PHOTOS_DIR, setname)
        exts = (".jpg", ".jpeg", ".png", ".webp")
        return [os.path.join(folder, f) for f in sorted(os.listdir(folder))
                if f.lower().endswith(exts)] if os.path.isdir(folder) else []

    # -- tab --------------------------------------------------------------
    def create_tab(self, api_session):
        gr.HTML(_THEME)
        S = {}  # component registry, in collect order
        global_prompt = {"text": ""}  # last built prompt, stored into scene snapshots
        chain = []  # story chain: [{"settings", "photo_set", "photos"}], in-memory by design

        def add(key, comp):
            S[key] = comp
            return comp

        def dd(label, name, value=None, choices=None, **kw):
            raw = choices if choices is not None else _choices(name)
            # RU tables are (value, ru-label); gradio wants (label, value)
            chs = [(lab, val) for val, lab in raw]
            return add(name, gr.Dropdown(chs, label=label,
                                         value=value or (raw[0][0] if raw else None), **kw))

        with gr.Column(elem_classes="h3ss"):
            with gr.Row():
                build_btn = gr.Button("🎲 Новая сцена", elem_classes="h3ss-btn")
                push_btn = gr.Button("➡️ Вставить в генератор", elem_classes="h3ss-btn-green")
                status = gr.Textbox(label="", show_label=False, max_lines=1, interactive=False)

            with gr.Accordion("📷 Референсы — фото и привязка", open=True, elem_classes="h3ss-acc"):
                gr.HTML("<div class='h3ss-note'>Фото 1 обычно — девушка, фото 2 — мужчина. "
                        "Одежда и комната берутся с первого фото.</div>")
                files = add("files", gr.Files(label="Загрузить фото", file_count="multiple",
                                              file_types=["image"]))
                with gr.Row():
                    dd("Кто на первом фото", "picWho")
                    dd("Сколько референсов в промпте", "picCountN",
                       choices=[("2", "2 — она и он"), ("1", "1 — только она"),
                                ("3", "3 — она, он, место"), ("4", "4")], value="2")
                gallery = gr.Gallery(label="Загруженные фото", columns=6, height=140,
                                     interactive=False)
                with gr.Row():
                    setname = gr.Textbox(label="Имя набора", scale=2)
                    save_btn = gr.Button("💾 Сохранить набор", scale=1)
                    del_btn = gr.Button("🗑 Удалить набор", scale=1)
                sets_dd = gr.Dropdown(label="Сохранённые наборы",
                                      choices=[(s, s) for s in self._sets_list()],
                                      interactive=True)
                with gr.Row():
                    load_btn = gr.Button("📂 Загрузить набор")
                    attach_btn = gr.Button("🖼 Прикрепить фото к генератору",
                                           elem_classes="h3ss-btn")

            with gr.Accordion("💾 Сцены", open=False, elem_classes="h3ss-acc"):
                gr.HTML("<div class='h3ss-note'>Сцена = все настройки вкладки + фото-набор. "
                        "Загрузка восстанавливает и настройки, и фото.</div>")
                with gr.Row():
                    scene_name = gr.Textbox(label="Имя сцены", scale=2)
                    scene_save_btn = gr.Button("💾 Сохранить сцену", scale=1)
                    scene_del_btn = gr.Button("🗑 Удалить сцену", scale=1)
                scene_dd = gr.Dropdown(label="Сохранённые сцены",
                                       choices=[(s, s) for s in scene_store.list_scenes()],
                                       interactive=True)
                scene_load_btn = gr.Button("📂 Загрузить сцену")

            with gr.Accordion("👥 Сцена и люди", open=False, elem_classes="h3ss-acc"):
                with gr.Row():
                    dd("Состав", "cast")
                    dd("Кто друг другу", "relate")
                    dd("Сценарий-пак", "format")
                with gr.Row():
                    dd("Настроение", "mood")
                    dd("Лицо удовольствия", "face")
                    dd("Опыт", "exp")
                with gr.Row():
                    _mode = [(lab, val) for val, lab in _choices("mode")]
                    add("mode", gr.Radio(_mode, label="Режим кадров",
                                         value="sequence"))
                    add("shotSec", gr.Slider(3, 10, value=5, step=1,
                                             label="Секунд на кадр"))
                    dd("Третьи в кадре", "inFrame")

            with gr.Accordion("👩 Девушка", open=False, elem_classes="h3ss-acc"):
                with gr.Row():
                    dd("Возраст", "fAge")
                    dd("Грудь", "fBreast")
                with gr.Row():
                    dd("Рост", "fHeight")
                    dd("Комплексция", "fFrame")
                dd("Одета", "fClothed")

            with gr.Accordion("👨 Мужчина", open=False, elem_classes="h3ss-acc"):
                with gr.Row():
                    dd("Возраст", "mAge")
                    dd("Лицо", "mLook")
                with gr.Row():
                    dd("Телосложение", "mBody")
                    dd("Кожа", "mSkin")
                with gr.Row():
                    dd("Длина", "mLen")
                    dd("Толщина", "mGirth")

            with gr.Accordion("👕 Одежда и место", open=False, elem_classes="h3ss-acc"):
                dd("Одежда", "clothes")
                dd("Состояние одежды", "clothMess")
                with gr.Row():
                    dd("Место", "place")
                    dd("Свет", "placeLight")

            with gr.Accordion("🔞 Активность", open=False, elem_classes="h3ss-acc"):
                with gr.Row():
                    add("act_intro", gr.Checkbox(value=True, label="Интро (SFW)"))
                    add("act_tease", gr.Checkbox(label="Прелюдия"))
                    add("act_hj", gr.Checkbox(label="Ручной"))
                    add("act_bj", gr.Checkbox(label="Минет"))
                    add("act_breast", gr.Checkbox(label="Грудь"))
                    add("act_sex", gr.Checkbox(label="Секс"))
                    add("act_cum", gr.Checkbox(label="Финал"))
                with gr.Accordion("Интро", open=False):
                    with gr.Row():
                        dd("Что делает", "introDo")
                        dd("Смотрит", "introLookName")
                    with gr.Row():
                        dd("Его правая рука", "introRH")
                        dd("Его левая рука", "introLH")
                with gr.Accordion("Прелюдия", open=False):
                    with gr.Row():
                        dd("Что делает", "teaseDo")
                        dd("Смотрит", "teaseLookName")
                    with gr.Row():
                        dd("Его правая рука", "teaseRH")
                        dd("Его левая рука", "teaseLH")
                with gr.Accordion("Ручной", open=False):
                    with gr.Row():
                        dd("Поза", "hjPos")
                        dd("Захват", "hjGrip")
                        dd("Темп", "hjTempo")
                with gr.Accordion("Минет", open=False):
                    with gr.Row():
                        dd("Поза", "bjPos")
                        dd("Глубина", "bjDepth")
                    with gr.Row():
                        dd("Влажность", "bjWet")
                        dd("Темп", "bjTempo")
                        dd("Руки", "bjHands")
                with gr.Accordion("Грудь", open=False):
                    dd("Что делает", "breastKind")
                with gr.Accordion("Секс", open=False):
                    with gr.Row():
                        dd("Поза", "sexPos")
                        dd("Лоно", "sexHole")
                    dd("Отдача", "sexBounce")
                with gr.Accordion("Финал", open=False):
                    with gr.Row():
                        dd("Куда", "cumLand")
                        dd("Как", "cumHow")
                    dd("Сколько", "cumQty")

            with gr.Accordion("🎥 Камера", open=False, elem_classes="h3ss-acc"):
                dd("Режим камеры", "camMode")
                dd("Стиль-пак (при ручном режиме)", "camStyle", value="off")
                with gr.Row():
                    dd("Дистанция", "camDist")
                    dd("Ракурс", "camAngle")
                    dd("Высота", "camHeight")
                with gr.Row():
                    dd("Движение", "camMove")
                    dd("Скорость", "camSpeed")
                    dd("Стабилизация", "camStab")
                with gr.Row():
                    dd("Объектив", "camLens")
                    dd("Слежение", "camFollow")
                add("pov", gr.Checkbox(value=False, label="Вид от первого лица (POV)"))

            with gr.Accordion("🔊 Звук и реплики", open=False, elem_classes="h3ss-acc"):
                add("talk", gr.Checkbox(value=True, label="Реплики (включает липсинк)"))
                dd("Уровень реплик", "talkLevel",
                   choices=[("soft", "тихо"), ("mid", "средне"), ("hard", "жёстко"),
                            ("raw", "грязно")], value="mid")
                add("talkLine", gr.Textbox(label="Своя реплика (пусто — случайная)"))
                add("fixRef", gr.Checkbox(value=True, label="Кадр 1 = ровно референс (свет и поза)"))
                add("manJoin", gr.Checkbox(value=True, label="Мужчина заходит в кадр 1"))
                add("artifactFull", gr.Checkbox(value=False, label="Полный артефакт-лок (жёстче)"))

            out_prompt = gr.Textbox(label="Промпт (английский — вставлять в H3 как есть)",
                                    lines=16, max_lines=40, elem_classes="h3ss-out",
                                    show_copy_button=True)
            out_recap = gr.Textbox(label="Коротко (по-русски)", lines=5, max_lines=8,
                                   interactive=False)

        # ---------------- events ------------------------------------------
        keys = list(S.keys())
        comps = [S[k] for k in keys]

        def collect(*vals):
            s = dict(zip(keys, vals))
            s.pop("files", None)
            s["picCount"] = []
            n = int(s.get("picCountN") or "2")
            s["picCount"] = [""] * n
            s.pop("picCountN", None)
            for k in ("introLookName", "teaseLookName"):
                v = s.pop(k, None)
                if k == "introLookName":
                    s["introLook"] = v
                else:
                    s["teaseLook"] = v
            s["talkLevel"] = s.get("talkLevel") or "mid"
            for st in ("intro", "tease", "hj", "bj", "breast", "sex", "cum"):
                s[f"act_{st}"] = "on" if s.get(f"act_{st}") else "off"
            for k in ("talk", "fixRef", "manJoin", "artifactFull", "pov"):
                s[k] = "on" if s.get(k) else "off"
            s["pov"] = "on" if s.get("pov") == "on" else "off"
            return s

        def do_build(*vals):
            s = collect(*vals)
            prompt, recap = engine.build(s)
            global_prompt["text"] = prompt
            return prompt, recap, "Промпт собран. Кнопка «Вставить в генератор» перенесёт его в основную форму."

        def do_push(current):
            if not current or not current.strip():
                raise gr.Error("Сначала соберите промпт.")
            return current, "Промпт вставлен в основную форму. Выберите модель MiniMax H3 Ref2VA."

        def do_attach(files_list):
            if not files_list:
                raise gr.Error("Сначала загрузите фото.")
            dst = os.path.join(PHOTOS_DIR, "_current")
            os.makedirs(dst, exist_ok=True)
            saved = []
            for i, f in enumerate(list(files_list)[:4], 1):
                ext = os.path.splitext(f.name if hasattr(f, "name") else str(f))[1] or ".jpg"
                path = os.path.join(dst, f"ref{i}{ext}")
                src = f.name if hasattr(f, "name") else str(f)
                shutil.copyfile(src, path)
                saved.append(path)
            return saved, f"Прикреплено {len(saved)} фото к генератору (референсы)."

        def do_save_set(name, files_list):
            name = (name or "").strip() or f"набор-{time.strftime('%Y%m%d-%H%M%S')}"
            folder = os.path.join(PHOTOS_DIR, name)
            os.makedirs(folder, exist_ok=True)
            for i, f in enumerate(list(files_list or [])[:4], 1):
                ext = os.path.splitext(f.name if hasattr(f, "name") else str(f))[1] or ".jpg"
                shutil.copyfile(f.name if hasattr(f, "name") else str(f),
                                os.path.join(folder, f"ref{i}{ext}"))
            sets = self._sets_list()
            return gr.update(choices=[(s, s) for s in sets], value=name), \
                f"Набор «{name}» сохранён."

        def do_load_set(name):
            paths = self._set_paths(name or "")
            if not paths:
                raise gr.Error("Набор пуст или не найден.")
            return paths, paths

        def do_del_set(name):
            folder = os.path.join(PHOTOS_DIR, name or "")
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
            sets = self._sets_list()
            return gr.update(choices=[(s, s) for s in sets], value=None), \
                gr.update(value=[]), gr.update(value=[]), f"Набор удалён."

        def show_files(files_list):
            return [f.name if hasattr(f, "name") else str(f)
                    for f in (files_list or [])[:4]]

        def do_save_scene(scene_name_text, setname_value, *vals):
            s = collect(*vals)
            name, _ = scene_store.save_scene(
                scene_name_text, s,
                photo_set=(setname_value or ""),
                prompt=global_prompt.get("text", "") or "")
            sets = scene_store.list_scenes()
            return gr.update(choices=[(x, x) for x in sets], value=name), \
                f"Сцена «{name}» сохранена."

        def do_load_scene(scene_choice):
            if not scene_choice:
                raise gr.Error("Выберите сцену в списке.")
            doc = scene_store.load_scene(scene_choice)
            s = doc.get("settings") or {}
            photo_set = doc.get("photo_set") or ""
            paths = self._set_paths(photo_set) if photo_set else []
            if photo_set and not paths:
                gr.Warning(f"Фото-набор «{photo_set}» не найден — загрузите фото вручную.")
            updates = []
            for k in keys:  # keys == list(S.keys()), defined where comps is built
                if k == "files":
                    updates.append(paths)  # photos come from the linked set
                    continue
                v = s.get(k)
                updates.append(gr.update(value=v) if v is not None else gr.update())
            return updates + [paths]  # trailing: gallery

        def do_del_scene(scene_choice):
            if not scene_choice:
                raise gr.Error("Выберите сцену в списке.")
            scene_store.delete_scene(scene_choice)
            sets = scene_store.list_scenes()
            return gr.update(choices=[(x, x) for x in sets], value=None), \
                f"Сцена «{scene_choice}» удалена."

        build_btn.click(do_build, inputs=comps, outputs=[out_prompt, out_recap, status])
        push_btn.click(do_push, inputs=[out_prompt], outputs=[self.prompt, status])
        attach_btn.click(do_attach, inputs=[files], outputs=[self.image_refs, status])
        files.change(show_files, inputs=[files], outputs=[gallery])
        save_btn.click(do_save_set, inputs=[setname, files], outputs=[sets_dd, status])
        load_btn.click(do_load_set, inputs=[sets_dd], outputs=[gallery, files])
        del_btn.click(do_del_set, inputs=[sets_dd], outputs=[sets_dd, gallery, files, status])
        scene_save_btn.click(do_save_scene,
                             inputs=[scene_name, setname] + comps,
                             outputs=[scene_dd, status])
        scene_load_btn.click(do_load_scene, inputs=[scene_dd],
                             outputs=comps + [gallery])
        scene_del_btn.click(do_del_scene, inputs=[scene_dd], outputs=[scene_dd, status])

        return {}
