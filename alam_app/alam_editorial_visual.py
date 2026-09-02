import base64
import hashlib
import html
import re

from alam_core import category_meta

ALLOWED_MOTIFS = {
    "yen", "chip", "robot", "factory", "train", "family", "shield", "document",
    "market", "policy", "home", "earthquake", "car", "weather", "globe", "battery",
}


def _clamp(value, default):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def _editorial(record):
    content = record.get("content") or {}
    raw = record.get("editorial_visual") or content.get("editorial_visual") or {}
    return raw if isinstance(raw, dict) else {}


def _infer_motif(record):
    text = " ".join(
        [
            str(record.get("title", "")),
            str(record.get("summary", "")),
            " ".join(str(x) for x in (record.get("tags") or [])),
        ]
    ).lower()
    tokens = set(re.findall(r"[a-z0-9¥]+", text))
    rules = [
        (("yen", "price", "cost", "inflation", "saving", "subsid", "salary", "tax", "fee"), "yen"),
        (("chip", "semiconductor", "wafer", "gpu", "inference", "datacenter"), "chip"),
        (("robot", "automation", "android", "cobot"), "robot"),
        (("factory", "manufacturing", "plant", "production"), "factory"),
        (("train", "rail", "shinkansen", "station"), "train"),
        (("family", "child", "spouse", "household", "parent"), "family"),
        (("insurance", "risk", "safety", "scam", "warning", "recall"), "shield"),
        (("document", "visa", "residence", "paperwork", "application", "pension"), "document"),
        (("market", "nikkei", "topix", "stocks", "equity", "bond", "yield", "fx"), "market"),
        (("policy", "government", "ministry", "regulation", "law", "rule"), "policy"),
        (("home", "housing", "rent", "mortgage", "electricity", "utility"), "home"),
        (("earthquake", "quake", "tsunami", "seismic"), "earthquake"),
        (("car", "vehicle", "driving", "road", "toll"), "car"),
        (("weather", "typhoon", "rain", "heat", "snow", "storm"), "weather"),
        (("global", "world", "trade", "export", "import"), "globe"),
        (("battery", "energy", "power", "storage", "ev"), "battery"),
    ]
    for words, motif in rules:
        if any(word in text for word in words):
            return motif
    if "ai" in tokens:
        return "chip"
    category = str(record.get("_category") or "discover")
    return {"discover": "globe", "practical": "shield", "reflection": "market", "trend": "market"}.get(category, "globe")


def _motif_svg(name):
    name = name if name in ALLOWED_MOTIFS else "globe"
    shapes = {
        "yen": '<circle r="112" fill="white" opacity=".18"/><text y="45" text-anchor="middle" font-family="Arial" font-size="150" font-weight="900" fill="white">¥</text>',
        "chip": '<rect x="-105" y="-86" width="210" height="172" rx="24" fill="white" opacity=".20" stroke="white" stroke-width="8"/><rect x="-58" y="-40" width="116" height="80" rx="10" fill="white" opacity=".42"/><path d="M-130-60h25 M-130-20h25 M-130 20h25 M-130 60h25 M105-60h25 M105-20h25 M105 20h25 M105 60h25 M-60-111v25 M-20-111v25 M20-111v25 M60-111v25 M-60 86v25 M-20 86v25 M20 86v25 M60 86v25" stroke="white" stroke-width="10" stroke-linecap="round"/>',
        "robot": '<rect x="-108" y="-82" width="216" height="164" rx="38" fill="white" opacity=".20" stroke="white" stroke-width="8"/><circle cx="-42" cy="-10" r="19" fill="#FFD35A"/><circle cx="42" cy="-10" r="19" fill="#FFD35A"/><path d="M-50 42Q0 76 50 42M0-82v-48" fill="none" stroke="white" stroke-width="10" stroke-linecap="round"/><circle cy="-142" r="15" fill="#FFD35A"/>',
        "factory": '<path d="M-135 92V-20L-50 25V-20L35 25V-20L120 25V92Z" fill="white" opacity=".22" stroke="white" stroke-width="8"/><rect x="70" y="-105" width="42" height="110" fill="white" opacity=".32"/>',
        "train": '<rect x="-145" y="-78" width="290" height="156" rx="58" fill="white" opacity=".21" stroke="white" stroke-width="8"/><rect x="-90" y="-40" width="55" height="48" rx="9" fill="white" opacity=".46"/><rect x="-20" y="-40" width="55" height="48" rx="9" fill="white" opacity=".46"/><circle cx="-78" cy="92" r="23" fill="white"/><circle cx="78" cy="92" r="23" fill="white"/>',
        "family": '<circle cy="-70" r="50" fill="white" opacity=".32"/><circle cx="-95" cy="-20" r="38" fill="white" opacity=".26"/><circle cx="95" cy="-20" r="38" fill="white" opacity=".26"/><path d="M-75 115q10-120 75-120t75 120M-155 115q8-85 60-85M155 115q-8-85-60-85" fill="none" stroke="white" stroke-width="24" stroke-linecap="round"/>',
        "shield": '<path d="M0-145L120-95V0Q105 100 0 150Q-105 100-120 0V-95Z" fill="white" opacity=".20" stroke="white" stroke-width="9"/><path d="M-55 5l38 38 78-92" fill="none" stroke="#FFD35A" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>',
        "document": '<path d="M-95-145H45L105-85V145H-95Z" fill="white" opacity=".21" stroke="white" stroke-width="8"/><path d="M45-145v60h60M-55-30h110M-55 15h110M-55 60h80" fill="none" stroke="#FFD35A" stroke-width="10" stroke-linecap="round"/>',
        "market": '<path d="M-145 110H145M-115 90V5M-55 45V-45M5 70V-5M65 15V-85M125-35V-125" stroke="white" stroke-width="16" stroke-linecap="round"/><path d="M-130 65L-65 20L0 48L68-30L135-95" fill="none" stroke="#FFD35A" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>',
        "policy": '<rect x="-105" y="35" width="210" height="45" rx="10" fill="white" opacity=".24"/><path d="M-65-75L35 25M-20-120L80-20" stroke="white" stroke-width="32" stroke-linecap="round"/><path d="M65-55l80 80" stroke="#FFD35A" stroke-width="14" stroke-linecap="round"/>',
        "home": '<path d="M-145 5L0-120L145 5V135H45V55H-45V135H-145Z" fill="white" opacity=".22" stroke="white" stroke-width="9"/><circle cx="90" cy="-85" r="27" fill="#FFD35A"/>',
        "earthquake": '<path d="M-150-95L-65-30L-15-80L35-5L95-55L150 25" fill="none" stroke="white" stroke-width="18" stroke-linecap="round"/><path d="M5-140L-28-35L22-20L-38 135" fill="none" stroke="#FFD35A" stroke-width="16"/>',
        "car": '<path d="M-145 45L-105-45H75L135 10V75H-145Z" fill="white" opacity=".22" stroke="white" stroke-width="9"/><circle cx="-85" cy="82" r="29" fill="white"/><circle cx="80" cy="82" r="29" fill="white"/>',
        "weather": '<path d="M-110 10q0-60 60-60 25-70 95-42 62 0 72 62 52 8 52 60 0 48-54 48H-90q-55 0-55-48 0-34 35-50" fill="white" opacity=".25" stroke="white" stroke-width="8"/><path d="M-75 105l-20 42M0 105l-20 42M75 105l-20 42" stroke="#FFD35A" stroke-width="13" stroke-linecap="round"/>',
        "globe": '<circle r="135" fill="white" opacity=".18" stroke="white" stroke-width="8"/><ellipse rx="62" ry="135" fill="none" stroke="white" stroke-width="6" opacity=".65"/><path d="M-125-42H125M-135 20H135M-110 78H110" stroke="white" stroke-width="6" opacity=".65"/>',
        "battery": '<rect x="-125" y="-85" width="235" height="170" rx="26" fill="white" opacity=".20" stroke="white" stroke-width="9"/><rect x="110" y="-30" width="28" height="60" rx="8" fill="white"/><path d="M-20-55L-72 20H-18L-48 70L60-25H5L35-55Z" fill="#FFD35A"/>',
    }
    return shapes[name]


def editorial_data_uri(record):
    meta = category_meta(record)
    editorial = _editorial(record)
    motif = str(editorial.get("motif") or _infer_motif(record)).lower()
    if motif not in ALLOWED_MOTIFS:
        motif = _infer_motif(record)
    secondary = str(editorial.get("secondary_motif") or "").lower()
    if secondary not in ALLOWED_MOTIFS:
        secondary = ""

    silliness = _clamp(editorial.get("silliness"), 18)
    exaggeration = _clamp(editorial.get("exaggeration"), 42)
    scene = str(editorial.get("scene") or "")
    caption = str(editorial.get("caption") or scene or "Topic-specific editorial illustration")
    accent = meta.get("accent", "#5968F2")
    soft = meta.get("soft", "#EEF0FF")
    digest = hashlib.sha256(str(record.get("id", record.get("title", "alam"))).encode("utf-8")).digest()
    scale = 0.88 + exaggeration / 180.0
    angle = (silliness - 50) / 8.0
    bob = int((silliness / 100.0) * 34)
    main = _motif_svg(motif)
    side = _motif_svg(secondary) if secondary else ""
    side_svg = ""
    if side:
        side_svg = f'<g transform="translate(690 448) rotate({-angle / 2:.1f}) scale(.62)">{side}</g>'

    tags = [str(x) for x in (record.get("tags") or []) if x][:2]
    label = (tags[0] if tags else meta.get("label", "ALAM")).upper()[:24]
    sub = caption[:54]
    mood = "PLAYFUL" if silliness >= 60 else ("BOLD" if exaggeration >= 65 else "EDITORIAL")
    silly_marks = ""
    if silliness >= 45:
        silly_marks = '<path d="M790 150q35-38 70 0M1025 135q35-38 70 0" fill="none" stroke="#FFD35A" stroke-width="10" stroke-linecap="round" opacity=".85"/>'
    if silliness >= 75:
        silly_marks += '<circle cx="1120" cy="510" r="28" fill="#FFD35A"/><circle cx="1110" cy="503" r="5" fill="#112B4A"/><circle cx="1130" cy="503" r="5" fill="#112B4A"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{soft}"/><stop offset=".44" stop-color="{accent}"/><stop offset="1" stop-color="#112B4A"/></linearGradient><filter id="blur"><feGaussianBlur stdDeviation="34"/></filter></defs>
<rect width="1200" height="675" fill="url(#g)"/>
<circle cx="{760 + digest[0] % 250}" cy="{100 + digest[1] % 190}" r="{150 + digest[2] % 120}" fill="white" opacity=".09" filter="url(#blur)"/>
<circle cx="{180 + digest[3] % 280}" cy="{390 + digest[4] % 120}" r="170" fill="#FFD35A" opacity=".10" filter="url(#blur)"/>
<path d="M76 548L220 270L364 548H300L220 395L140 548Z" fill="white" opacity=".12"/>
<g transform="translate(930 {342 - bob}) rotate({angle:.1f}) scale({scale:.2f})">{main}</g>
{side_svg}
{silly_marks}
<text x="72" y="82" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="25" font-weight="850" letter-spacing="4" fill="white" opacity=".78">ALAM {mood}</text>
<text x="72" y="155" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="58" font-weight="900" letter-spacing="-2" fill="white">{html.escape(label)}</text>
<text x="76" y="205" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="25" font-weight="650" fill="white" opacity=".88">{html.escape(sub)}</text>
<text x="74" y="618" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="23" font-weight="700" fill="white" opacity=".72">Editorial illustration · See · Understand · Act</text>
</svg>'''
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
