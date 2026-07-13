import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import InternetSource, Product

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
CJK_RE = re.compile(r"[\u4E00-\u9FFF]")
HANGUL_RE = re.compile(r"[\uAC00-\uD7AF]")
KANA_RE = re.compile(r"[\u3040-\u30FF]")

# Semantic commodity groups with equivalents per platform language.
COMMODITY_TERM_GROUPS: list[dict[str, list[str]]] = [
    {
        "en": ["urea", "carbamide", "fertilizer", "nitrogen fertilizer"],
        "ru": ["карбамид", "мочевина", "удобрения", "азотные удобрения"],
        "es": ["urea", "carbamida", "fertilizante", "abono"],
        "fr": ["urée", "carbamide", "engrais", "engrais azoté"],
        "ar": ["يوريا", "كرباميد", "أسمدة", "سماد"],
        "hi": ["यूरिया", "उर्वरक", "कारबामाइड"],
        "pt": ["ureia", "carbamida", "fertilizante"],
        "de": ["harnstoff", "carbamid", "düngemittel"],
        "tr": ["üre", "karbamid", "gübre"],
        "zh": ["尿素", "肥料"],
    },
    {
        "en": ["ammonia", "ammonium nitrate", "nitrate"],
        "ru": ["аммиак", "селитра", "аммиачная селитра"],
        "es": ["amoniaco", "nitrato de amonio", "nitrato"],
        "fr": ["ammoniac", "nitrate d'ammonium", "nitrate"],
        "ar": ["أمونيا", "نترات الأمونيوم"],
        "hi": ["अमोनिया", "अमोनियम नाइट्रेट"],
        "pt": ["amônia", "nitrato de amônio"],
        "de": ["ammoniak", "ammoniumnitrat"],
        "tr": ["amonyak", "amonyum nitrat"],
        "zh": ["氨", "硝酸铵"],
    },
    {
        "en": ["wheat", "corn", "maize", "soybean", "sugar"],
        "ru": ["пшеница", "кукуруза", "соя", "сахар"],
        "es": ["trigo", "maíz", "soja", "azúcar"],
        "fr": ["blé", "maïs", "soja", "sucre"],
        "ar": ["قمح", "ذرة", "فول الصويا", "سكر"],
        "hi": ["गेहूं", "मक्का", "सोयाबीन", "चीनी"],
        "pt": ["trigo", "milho", "soja", "açúcar"],
        "de": ["weizen", "mais", "sojabohne", "zucker"],
        "tr": ["buğday", "mısır", "soya", "şeker"],
        "zh": ["小麦", "玉米", "大豆", "糖"],
    },
    {
        "en": ["crude oil", "petroleum", "base oil", "sn500", "sn150"],
        "ru": ["нефть", "базовое масло", "сн500", "сн150"],
        "es": ["petróleo", "aceite base", "crudo"],
        "fr": ["pétrole", "huile de base", "brut"],
        "ar": ["نفط", "زيت خام", "زيت أساسي"],
        "hi": ["कच्चा तेल", "बेस ऑयल"],
        "pt": ["petróleo", "óleo base", "bruto"],
        "de": ["rohöl", "grundöl", "erdöl"],
        "tr": ["ham petrol", "baz yağ"],
        "zh": ["原油", "基础油"],
    },
    {
        "en": ["transformer oil", "insulating oil", "dielectric oil", "mineral insulating oil"],
        "ru": ["трансформаторное масло", "изоляционное масло", "диэлектрическое масло"],
        "es": ["aceite transformador", "aceite aislante", "aceite dieléctrico"],
        "fr": ["huile de transformateur", "huile isolante", "huile diélectrique"],
        "ar": ["زيت المحولات", "زيت عازل"],
        "hi": ["ट्रांसफार्मर ऑयल", "इंसुलेटिंग ऑयल"],
        "pt": ["óleo de transformador", "óleo isolante"],
        "de": ["transformatorenöl", "isolieröl"],
        "tr": ["transformatör yağı", "yalıtım yağı"],
        "zh": ["变压器油", "绝缘油"],
    },
    {
        "en": ["methanol", "ethanol", "coal", "natural gas", "lng", "sulfur", "sulphur"],
        "ru": ["метанол", "этанол", "уголь", "газ", "сера"],
        "es": ["metanol", "etanol", "carbón", "gas natural", "glp", "azufre"],
        "fr": ["méthanol", "éthanol", "charbon", "gaz naturel", "gpl", "soufre"],
        "ar": ["ميثانول", "إيثانول", "فحم", "غاز طبيعي", "كبريت"],
        "hi": ["मेथनॉल", "इथेनॉल", "कोयला", "प्राकृतिक गैस"],
        "pt": ["metanol", "etanol", "carvão", "gás natural", "enxofre"],
        "de": ["methanol", "ethanol", "kohle", "erdgas", "schwefel"],
        "tr": ["metanol", "etanol", "kömür", "doğal gaz", "kükürt"],
        "zh": ["甲醇", "乙醇", "煤", "天然气", "硫"],
    },
    {
        "en": ["phosphate fertilizer", "potash fertilizer"],
        "ru": ["фосфорные удобрения", "калийные удобрения"],
        "es": ["fertilizante fosfatado", "fertilizante potásico"],
        "fr": ["engrais phosphaté", "engrais potassique"],
        "ar": ["سماد فوسفاتي", "سماد بوتاسي"],
        "hi": ["फॉस्फेट उर्वरक", "पोटाश उर्वरक"],
        "pt": ["fertilizante fosfatado", "fertilizante potássico"],
        "de": ["phosphatdünger", "kalidünger"],
        "tr": ["fosfat gübresi", "potasyum gübresi"],
        "zh": ["磷肥", "钾肥"],
    },
    {
        "en": ["gum arabic", "guar gum", "acacia gum", "xanthan gum", "gum resin"],
        "ru": ["камедь", "гуаровая камедь", "арабская камедь", "гуммиарабик", "ксантановая камедь", "смола"],
        "es": ["goma", "goma arábiga", "goma de guar", "goma de acacia", "resina"],
        "fr": ["gomme", "gomme arabique", "gomme de guar", "gomme d'acacia", "résine"],
        "ar": ["صمغ", "صمغ عربي", "صمغ الغوار"],
        "hi": ["गम", "गोंद", "ग्वार गम", "अरबिक गम"],
        "pt": ["goma", "goma arábica", "goma de guar", "resina"],
        "de": ["gummi", "gummi arabicum", "guarkernmehl", "harz"],
        "tr": ["sakız", "akasya sakızı", "guar sakızı", "reçine"],
        "zh": ["胶", "阿拉伯胶", "瓜尔胶", "树脂"],
    },
]

TERM_LANGUAGE_INDEX: dict[str, set[str]] = {}
GENERIC_SOURCE_TAGS = {"commodities", "chemicals", "polymers", "procurement", "food ingredients"}
for group in COMMODITY_TERM_GROUPS:
    for language, terms in group.items():
        for term in terms:
            TERM_LANGUAGE_INDEX.setdefault(term.lower(), set()).add(language)


def _normalize_term(value: str) -> str:
    return value.strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _normalize_term(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def detect_term_language(term: str) -> str:
    if CYRILLIC_RE.search(term):
        return "ru"
    if ARABIC_RE.search(term):
        return "ar"
    if DEVANAGARI_RE.search(term):
        return "hi"
    if HANGUL_RE.search(term):
        return "ko"
    if KANA_RE.search(term):
        return "ja"
    if CJK_RE.search(term):
        return "zh"

    indexed = TERM_LANGUAGE_INDEX.get(term.lower())
    if indexed:
        if len(indexed) == 1:
            return next(iter(indexed))
        # Shared latin spellings (e.g. "urea") are valid for several languages.
        if "en" in indexed:
            return "en"
        return sorted(indexed)[0]
    return "en"


def _source_languages(source: InternetSource) -> list[str]:
    languages = [str(lang).strip().lower() for lang in (source.languages or []) if str(lang).strip()]
    if not languages:
        return ["en"]
    return languages


def _term_matches_keyword(term: str, keyword: str) -> bool:
    term_lower = term.lower()
    keyword_lower = keyword.lower()
    return term_lower == keyword_lower or term_lower in keyword_lower or keyword_lower in term_lower


def _find_groups_for_term(term: str) -> list[dict[str, list[str]]]:
    matched: list[dict[str, list[str]]] = []
    for group in COMMODITY_TERM_GROUPS:
        for terms in group.values():
            if any(_term_matches_keyword(term, candidate) for candidate in terms):
                matched.append(group)
                break
    return matched


def terms_semantically_related(term_a: str, term_b: str) -> bool:
    if _term_matches_keyword(term_a, term_b):
        return True
    groups_a = {id(group) for group in _find_groups_for_term(term_a)}
    groups_b = {id(group) for group in _find_groups_for_term(term_b)}
    return bool(groups_a and groups_b and groups_a & groups_b)


def hit_matches_assignment(text: str, user_keywords: list[str]) -> tuple[bool, str]:
    haystack = text.lower()
    if not user_keywords:
        return True, "Ключевые слова не заданы"

    for keyword in user_keywords:
        keyword_lower = keyword.lower().strip()
        if not keyword_lower:
            continue
        if keyword_lower in haystack:
            return True, f"Совпадение с «{keyword}»"

        group_terms: list[str] = []
        for group in _find_groups_for_term(keyword):
            for terms in group.values():
                group_terms.extend(terms)
        for term in _dedupe(group_terms):
            if term.lower() in haystack:
                return True, f"Совпадение с «{keyword}» через «{term}»"

    return False, "Предмет тендера не соответствует заданию"


def source_keyword_matches(keyword: str, source: InternetSource) -> bool:
    keyword_lower = keyword.lower().strip()
    if not keyword_lower:
        return False

    tags = [str(tag).lower() for tag in (source.product_tags or [])]
    haystack = " ".join([source.name.lower(), source.description or "", *tags])
    if keyword_lower in haystack:
        return True
    if any(keyword_lower in tag or tag in keyword_lower for tag in tags):
        return True
    for tag in source.product_tags or []:
        if terms_semantically_related(keyword, str(tag)):
            return True
    if _find_groups_for_term(keyword) and any(
        str(tag).strip().lower() in GENERIC_SOURCE_TAGS for tag in (source.product_tags or [])
    ):
        return True
    return False


def equivalent_terms_for_languages(term: str, target_languages: list[str]) -> list[str]:
    localized: list[str] = []
    for group in _find_groups_for_term(term):
        for language in target_languages:
            localized.extend(group.get(language, []))
    return _dedupe(localized)


def _terms_for_language(terms: list[str], language: str) -> list[str]:
    return [term for term in terms if detect_term_language(term) == language]


def _related_source_tags(source: InternetSource, user_keywords: list[str]) -> list[str]:
    tags = [str(tag).strip() for tag in (source.product_tags or []) if str(tag).strip()]
    if not tags:
        return []

    related: list[str] = []
    for tag in tags:
        if any(_term_matches_keyword(tag, keyword) for keyword in user_keywords):
            related.append(tag)
            continue
        for keyword in user_keywords:
            if _find_groups_for_term(keyword) and _find_groups_for_term(tag):
                keyword_groups = {id(group) for group in _find_groups_for_term(keyword)}
                tag_groups = {id(group) for group in _find_groups_for_term(tag)}
                if keyword_groups & tag_groups:
                    related.append(tag)
                    break
    return related


def expand_product_keywords(db: Session, user_keywords: list[str]) -> list[str]:
    expanded = list(user_keywords)

    for keyword in user_keywords:
        for group in _find_groups_for_term(keyword):
            for terms in group.values():
                expanded.extend(terms)

    keyword_lowers = [keyword.lower() for keyword in user_keywords if keyword.strip()]
    for product in db.scalars(select(Product)):
        names = [product.normalized_name, *(product.aliases or [])]
        name_lowers = [str(name).lower() for name in names if name]
        if not any(
            keyword in name_lower or name_lower in keyword
            for keyword in keyword_lowers
            for name_lower in name_lowers
        ):
            continue
        expanded.append(product.normalized_name)
        expanded.extend(str(alias) for alias in (product.aliases or []) if alias)

    return _dedupe(expanded)


@dataclass(frozen=True)
class KeywordSearchSet:
    original: list[str]
    expanded: list[str]

    def match_terms(self) -> list[str]:
        return self.expanded


def build_keyword_search_set(db: Session, user_keywords: list[str]) -> KeywordSearchSet:
    original = _dedupe(user_keywords)
    expanded = expand_product_keywords(db, original)
    return KeywordSearchSet(original=original, expanded=expanded)


def _filter_terms_for_source_languages(terms: list[str], source_langs: list[str]) -> list[str]:
    filtered: list[str] = []
    for term in terms:
        term_lang = detect_term_language(term)
        if term_lang in source_langs:
            filtered.append(term)
    return _dedupe(filtered)


def localize_keywords_for_source(
    search_set: KeywordSearchSet,
    *,
    source: InternetSource,
) -> list[str]:
    source_langs = _source_languages(source)
    localized: list[str] = []

    for language in source_langs:
        localized.extend(_terms_for_language(search_set.expanded, language))
        for keyword in search_set.original:
            localized.extend(equivalent_terms_for_languages(keyword, [language]))

    for keyword in search_set.original:
        localized.extend(equivalent_terms_for_languages(keyword, source_langs))

    for tag in _related_source_tags(source, search_set.original):
        localized.append(tag)
    for tag in _related_source_tags(source, search_set.expanded):
        localized.append(tag)

    localized = _filter_terms_for_source_languages(_dedupe(localized), source_langs)
    if localized:
        return localized

    for language in source_langs:
        fallback = equivalent_terms_for_languages(search_set.original[0], [language])
        if fallback:
            return fallback

    return search_set.original
