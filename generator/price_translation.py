"""Перевод строк прайса: заголовки разделов, названия и описания позиций.

Цен здесь нет по построению: ключ словаря — русская строка из prices.json, значение —
её перевод. Числа в описаниях («5 сеансов — … 560 000 đ») переводчик видит масками
{0}, {1}…, а сборка подставляет их из русской строки, поэтому новая цена в prices.json
перевод не трогает. Цифры перед валютой (đ, VND, dong) в переводе — ошибка: так в перевод
не попадёт сумма.
Признак комбо считается по русскому названию до перевода (pricing.price_view).
"""
import re

KINDS = ("sections", "names", "descs")
OVERRIDES = "overrides"
NUMBER_RE = re.compile(r"\d+(?: \d{3})*")
MASK_RE = re.compile(r"\{(\d+)\}")
DIGIT_RE = re.compile(r"\d")
# Цифры перед обозначением донга: «500 000 đ», «500000VND», «500000 dong». Латинские
# обозначения — целым словом, чтобы «3 dongles» не считалось ценой.
DIGIT_BEFORE_DONG_RE = re.compile(r"\d\s*(?:đ|(?:vnd|dong)\b)", re.IGNORECASE)
FIELD_OF_KIND = {"names": "name", "descs": "desc"}


def mask_numbers(text):
    numbers = NUMBER_RE.findall(text)
    counter = iter(range(len(numbers)))
    return NUMBER_RE.sub(lambda _: "{%d}" % next(counter), text), numbers


def _masks(text):
    return sorted({int(index) for index in MASK_RE.findall(text)})


def _lookup_key(kind, source):
    return mask_numbers(source)[0] if kind == "descs" else source


def required_keys(prices):
    """(услуга, вид, ключ) для каждой строки прайса, которой нужен перевод."""
    for service_id, sections in prices.items():
        for sec in sections:
            if sec.get("section"):
                yield service_id, "sections", sec["section"]
            for item in sec["items"]:
                yield service_id, "names", item["name"]
                if item.get("desc"):
                    yield service_id, "descs", _lookup_key("descs", item["desc"])


def _value_problems(kind, key, value):
    label = f"prices {kind} «{key}»"
    if not (isinstance(value, str) and value.strip()):
        return [f"{label}: перевод должен быть непустой строкой"]
    if DIGIT_BEFORE_DONG_RE.search(value):
        return [f"{label}: в переводе цифры перед валютой (đ, VND, dong) — цены в переводе нет"]
    if kind != "descs":
        return []
    if DIGIT_RE.search(MASK_RE.sub("", value)):
        return [f"{label}: в переводе описания цифры — числа подставляются масками {{0}}, {{1}}…"]
    if _masks(value) != _masks(key):
        return [f"{label}: маски перевода {_masks(value)} не совпадают с масками ключа {_masks(key)}"]
    return []


def _clean_map(value):
    """Словарь «русская строка: перевод» без ключей-не-строк; не словарь — пустой."""
    return {key: text for key, text in value.items() if isinstance(key, str)} \
        if isinstance(value, dict) else {}


def _clean_kinds(kinds):
    """Переопределения одной услуги: виды чистятся, неизвестный вид остаётся — его называет
    _structure_problems."""
    unknown = {kind: value for kind, value in kinds.items() if kind not in KINDS}
    return {**unknown, **{kind: _clean_map(kinds.get(kind)) for kind in KINDS}}


def sanitized(catalog):
    """Словарь перевода только из верных частей: кривая часть (список вместо словаря,
    ключ-число) выпадает, а catalog_problems называет её отдельной строкой. Дальше
    сборка и проверки работают с чистым словарём и не падают трейсбеком."""
    if not isinstance(catalog, dict):
        return {}
    cleaned = {kind: _clean_map(catalog.get(kind)) for kind in KINDS}
    overrides = catalog.get(OVERRIDES)
    cleaned[OVERRIDES] = {service_id: _clean_kinds(kinds)
                          for service_id, kinds in (overrides.items() if isinstance(overrides, dict) else ())
                          if isinstance(kinds, dict)}
    unknown = {key: value for key, value in catalog.items() if key not in cleaned}
    return {**unknown, **cleaned}


def _bad_map(label, value):
    """Строка о значении, которое должно быть словарём «русская строка: перевод»."""
    if value is None or isinstance(value, dict):
        return []
    return [f"{label}: должен быть словарём «русская строка: перевод», а не {_kind_name(value)}"]


def _kind_name(value):
    return {list: "списком", str: "строкой"}.get(type(value), type(value).__name__)


def _shape_problems(catalog):
    """Форма файла prices.yml: словари там, где нужны словари, и строковые ключи."""
    if not isinstance(catalog, dict):
        return [f"prices: файл должен быть словарём с ключами {', '.join(KINDS)}, а не "
                f"{_kind_name(catalog)}"]
    problems = []
    for kind in KINDS:
        problems += _bad_map(f"prices {kind}", catalog.get(kind))
    overrides = catalog.get(OVERRIDES)
    problems += _bad_map(f"prices {OVERRIDES}", overrides)
    for service_id, kinds in sorted((overrides if isinstance(overrides, dict) else {}).items(),
                                    key=lambda pair: str(pair[0])):
        problems += _bad_map(f"prices {OVERRIDES} «{service_id}»", kinds)
        for kind in KINDS:
            problems += _bad_map(f"prices {OVERRIDES} «{service_id}» {kind}",
                                 kinds.get(kind) if isinstance(kinds, dict) else None)
    return problems


def _dictionaries(catalog, prices):
    """[(название для сообщений, вид, словарь)] — общие словари и переопределения услуг."""
    found = [(None, kind, catalog.get(kind) or {}) for kind in KINDS]
    for service_id, kinds in (catalog.get(OVERRIDES) or {}).items():
        if service_id in prices:
            found += [(service_id, kind, kinds.get(kind) or {}) for kind in KINDS]
    return found


def _structure_problems(prices, catalog):
    problems = [f"prices «{key}»: неизвестный раздел словаря"
                for key in sorted(set(catalog) - set(KINDS) - {OVERRIDES})]
    for service_id, kinds in sorted((catalog.get(OVERRIDES) or {}).items()):
        if service_id not in prices:
            problems.append(f"prices overrides «{service_id}»: такой услуги в прайсе нет")
            continue
        problems += [f"prices overrides «{service_id}» «{kind}»: неизвестный вид, ожидался один из {KINDS}"
                     for kind in sorted(set(kinds) - set(KINDS))]
    return problems


def _coverage_problems(prices, catalog):
    """Недостающие и лишние ключи. Ключ переопределения услуги закрывает строку только в ней."""
    problems, used = [], set()
    overrides = catalog.get(OVERRIDES) or {}
    for service_id, kind, key in required_keys(prices):
        if key in ((overrides.get(service_id) or {}).get(kind) or {}):
            used.add((service_id, kind, key))
        elif key in (catalog.get(kind) or {}):
            used.add((None, kind, key))
        else:
            problems.append(f"prices {kind} «{key}»: нет перевода ({service_id})")
    for owner, kind, dictionary in _dictionaries(catalog, prices):
        problems += [f"prices {kind} «{key}»: лишний ключ — в прайсе такой строки нет"
                     + (f" ({owner})" if owner else "")
                     for key in dictionary if (owner, kind, key) not in used]
    return problems


def catalog_problems(prices, raw_catalog):
    """Все проблемы словаря перевода прайса — одним списком. Принимает словарь как он
    прочитан из файла: кривую форму называет строкой, остальное проверяет по чистой части."""
    catalog = sanitized(raw_catalog)
    problems = _shape_problems(raw_catalog)
    problems += _structure_problems(prices, catalog)
    problems += list(dict.fromkeys(_coverage_problems(prices, catalog)))  # без повторов
    for _, kind, dictionary in _dictionaries(catalog, prices):
        for key, value in dictionary.items():
            problems += _value_problems(kind, key, value)
    return problems


class PriceTranslation:
    """Переводчик строк прайса одного языка. Для основного языка — тождественный."""

    def __init__(self, catalog):
        self._catalog = catalog

    @classmethod
    def identity(cls):
        return cls(None)

    def _lookup(self, service_id, kind, key):
        override = ((self._catalog.get(OVERRIDES) or {}).get(service_id) or {}).get(kind) or {}
        if key in override:
            return override[key]
        return self._catalog[kind][key]

    def text(self, service_id, kind, source):
        """Перевод одной строки прайса. Пустая строка и основной язык — как есть."""
        if self._catalog is None or not source:
            return source
        if kind != "descs":
            return self._lookup(service_id, kind, source)
        masked, numbers = mask_numbers(source)
        return self._lookup(service_id, kind, masked).format(*numbers)

    def _item(self, service_id, item):
        translated = {field: self.text(service_id, kind, item[field])
                      for kind, field in FIELD_OF_KIND.items() if field in item}
        return {**item, **translated}

    def translate_sections(self, service_id, sections):
        """Разделы прайса с переведёнными строками; цены, флаги и порядок — как в источнике."""
        if self._catalog is None:
            return sections
        return [{**sec, **({"section": self.text(service_id, "sections", sec["section"])}
                           if sec.get("section") else {}),
                 "items": [self._item(service_id, item) for item in sec["items"]]}
                for sec in sections]
