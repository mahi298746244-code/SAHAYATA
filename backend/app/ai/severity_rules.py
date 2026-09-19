"""Transparent rule layer for severity, urgency, safety risk and subcategory.

These are explainable keyword/lexicon rules (bilingual: English + romanized
Hindi) applied on top of the ML classifier. Every score can be traced back to
the matched keywords.
"""

# --- Subcategory detection: (category_slug, subcategory, keywords) -----------
SUBCATEGORY_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("roads", "Pothole", ("pothole", "gadha", "gaddha", "hole in the road", "crater")),
    ("roads", "Damaged road surface", ("damaged road", "broken road", "road damaged", "cracks", "tuta", "sadak tooti")),
    ("roads", "Road cave-in", ("caved", "cave in", "sink", "sunk", "collapsed road")),
    ("roads", "Open road cut", ("road cut", "digging not closed", "open trench")),
    ("water", "No water supply", ("no water", "water not coming", "pani nahi", "paani nahi", "shortage", "supply stopped")),
    ("water", "Pipeline leak / burst", ("pipeline leak", "pipe burst", "pipe leaked", "leakage", "toot gayi")),
    ("water", "Contaminated water", ("contaminated", "dirty water", "smell", "muddy water", "ganda paani")),
    ("water", "Low pressure", ("low pressure", "slow supply")),
    ("electricity", "Power outage", ("power cut", "outage", "no electricity", "bijli nahi", "current nahi")),
    ("electricity", "Transformer fault", ("transformer",)),
    ("electricity", "Hanging / fallen wire", ("wire fell", "loose wire", "hanging wire", "taar gir", "live wire")),
    ("electricity", "Damaged pole", ("pole leaning", "khamba", "broken pole")),
    ("garbage", "Not collected", ("not collected", "garbage not", "kachra nahi", "uthaya nahi")),
    ("garbage", "Open dump", ("dump", "dher", "kachre ka dher")),
    ("garbage", "Debris on road", ("debris", "malba", "construction waste")),
    ("drainage", "Blocked drain", ("blocked", "jam", "choked", "clogged")),
    ("drainage", "Drain overflow", ("overflow", "nali", "naali", "gandaa paani", "sewage overflow")),
    ("drainage", "Waterlogging", ("water logging", "waterlogging", "stagnant", "paani bhar")),
    ("street_lighting", "Light not working", ("not working", "jal nahi", "batti nahi", "dead lights", "nahi jal")),
    ("street_lighting", "Dark zone", ("dark stretch", "dark area", "unsafe at night", "andhera")),
    ("healthcare", "Doctor unavailable", ("no doctor", "doctor absent", "doctor nahi")),
    ("healthcare", "Medicine shortage", ("medicine", "dawair", "dawai", "out of stock")),
    ("healthcare", "Ambulance unavailable", ("ambulance",)),
    ("education", "Staff shortage", ("teachers", "shikshak", "staff")),
    ("education", "Building repair", ("roof", "walls cracked", "building repair", "classroom")),
    ("education", "Toilets broken", ("toilets", "toilet kharab")),
    ("public_safety", "Stray animals", ("stray dog", "stray cattle", "kutta", "dogs attacking")),
    ("public_safety", "Crime hotspot", ("snatching", "theft", "lutere", "patrolling")),
    ("sanitation", "Public toilet dirty/broken", ("toilet", "shauchalay", "urinal")),
    ("sanitation", "Open defecation", ("open defecation",)),
    ("sanitation", "Cleaning missed", ("safai", "cleaning not", "not cleaned")),
    ("public_transport", "Bus service gap", ("bus service", "no buses", "route stopped", "frequency")),
    ("public_transport", "Shelter damaged", ("bus stop", "shelter", "adda")),
    ("environment", "Illegal tree cutting", ("tree cut", "ped kaat")),
    ("environment", "Water body pollution", ("lake", "pond", "jheel", "fish dying")),
    ("environment", "Air/noise pollution", ("smoke", "noise pollution", "chemical smell")),
]

# --- Severity lexicon --------------------------------------------------------
SEVERITY_BOOSTS: dict[str, int] = {
    # +2 strong danger signals
    "accident": 2, "injured": 2, "fell": 1, "fallen": 1, "collapse": 2,
    "electrocut": 3, "live wire": 3, "shock": 2, "fire": 3, "exploded": 3,
    "sparking": 2, "dangerously": 2, "child": 2, "children": 2, "school": 1,
    "hospital": 1, "ambulance": 2, "dying": 3, "death": 3, "drowning": 3,
    "poison": 2, "contaminated drinking": 2, "fish dying": 2, "attack": 2,
    # +1 moderate signals
    "deep": 1, "huge": 1, "flood": 2, "overflowing": 1, "sewage": 1,
    "mosquitoes": 1, "dengue": 2, "malaria": 2, "unsafe": 1, "dangerous": 1,
}

URGENCY_KEYWORDS = (
    "since", "days", "week", "month", "daily", "every day", "everyday",
    "immediately", "urgent", "emergency", "night", "abhi", "roz",
)

# Safety-risk lexicon used by the priority engine component.
SAFETY_KEYWORDS = (
    "accident", "injured", "fell", "fallen", "collapse", "electrocut",
    "live wire", "shock", "fire", "sparking", "child", "children", "school",
    "hospital", "ambulance", "dengue", "malaria", "attack", "unsafe",
    "night", "dark", "dangerous", "deep", "drowning",
)


def detect_subcategory(category_slug: str | None, text: str) -> str | None:
    t = text.lower()
    best: tuple[int, str] | None = None
    for slug, subcat, kws in SUBCATEGORY_RULES:
        if category_slug and slug != category_slug:
            continue
        hits = sum(1 for kw in kws if kw in t)
        if hits and (best is None or hits > best[0]):
            best = (hits, subcat)
    return best[1] if best else None


def score_severity(text: str, base_by_category: dict[str, int], category_slug: str | None) -> int:
    """Return 1..5 severity from base category level boosted by danger lexicon."""
    t = text.lower()
    base = base_by_category.get(category_slug or "", 2)
    boost = 0
    for kw, add in SEVERITY_BOOSTS.items():
        if kw in t:
            boost += add
    return max(1, min(5, base + (boost // 2)))


def score_urgency(text: str) -> int:
    t = text.lower()
    hits = sum(1 for kw in URGENCY_KEYWORDS if kw in t)
    return max(1, min(5, 1 + hits // 2))


def safety_hits(text: str) -> int:
    t = text.lower()
    return sum(1 for kw in SAFETY_KEYWORDS if kw in t)
