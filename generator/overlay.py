"""Накладка перевода на русский мастер content.yml.

Перевод хранит только переводимые поля и повторяет пути мастера. Всё остальное —
идентификаторы, картинки, состав разделов, ключи позиций прайса — берётся из мастера,
поэтому структура языков не может разойтись. Проблемы собираются все сразу: список
целиком — это задание на перевод, чинить по одной ошибке за сборку нельзя.
"""
import copy

TRANSLATABLE_FIELDS = frozenset({
    "seo_title", "seo_desc", "title", "nav_label", "intro", "booking_title",
    "hero_kicker", "hero_title_lines", "hero_sub", "about_lead", "q", "a", "text",
    "benefits_eyebrow", "benefits_title", "price_title", "price_lead", "label",
    "eyebrow", "lead", "caption", "task", "category",
})
LINE_SEPARATOR = "\n"  # строки H1 в source_strings склеиваются в один текст


def _join(path, key):
    return f"{path}.{key}" if path else str(key)


def is_container(value):
    """Словарь или непустой список словарей: внутрь накладка заходит по той же форме."""
    return isinstance(value, dict) or (
        isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value))


def _is_text(value):
    return isinstance(value, str) and bool(value.strip())


def _leaf_problem(source, translation, path):
    if isinstance(source, list):
        if isinstance(translation, list) and translation and all(map(_is_text, translation)):
            return None
        return f"{path}: перевод должен быть непустым списком строк"
    return None if _is_text(translation) else f"{path}: перевод должен быть непустой строкой"


def _merge_leaf(source, overlay, key, path, problems):
    if key not in overlay:
        problems.append(f"{path}: нет перевода")
        return copy.deepcopy(source)
    problem = _leaf_problem(source, overlay[key], path)
    if problem:
        problems.append(problem)
        return copy.deepcopy(source)
    return copy.deepcopy(overlay[key])


def _merge_field(key, value, overlay, path, problems):
    if key in TRANSLATABLE_FIELDS:
        return _merge_leaf(value, overlay, key, path, problems)
    if is_container(value):
        return _merge_node(value, overlay.get(key), path, problems)
    if key in overlay:
        problems.append(f"{path}: поле не переводится, в переводе его быть не должно")
    return copy.deepcopy(value)


def _merge_dict(master, overlay, path, problems):
    if not isinstance(overlay, dict):
        if overlay is not None:
            problems.append(f"{path}: в переводе должен быть словарь")
        overlay = {}
    problems += [f"{_join(path, key)}: лишний ключ — в мастере его нет"
                 for key in sorted(set(overlay) - set(master), key=str)]
    return {key: _merge_field(key, value, overlay, _join(path, key), problems)
            for key, value in master.items()}


def _merge_list(master, overlay, path, problems):
    if overlay is None:
        overlay = [None] * len(master)
    elif not isinstance(overlay, list) or len(overlay) != len(master):
        size = len(overlay) if isinstance(overlay, list) else "не список"
        problems.append(f"{path}: в мастере {len(master)} элементов, в переводе {size}")
        overlay = [None] * len(master)
    return [_merge_node(item, patch, f"{path}[{index}]", problems)
            for index, (item, patch) in enumerate(zip(master, overlay))]


def _merge_node(master, overlay, path, problems):
    if isinstance(master, list):
        return _merge_list(master, overlay, path, problems)
    return _merge_dict(master, overlay, path, problems)


def merge_translation(master, overlay):
    """Мастер + накладка → (тексты языка, все проблемы перевода). Мастер не меняется."""
    problems = []
    merged = _merge_node(master, overlay, "", problems)
    return merged, problems


def _collect_sources(node, path, result):
    items = node.items() if isinstance(node, dict) else enumerate(node)
    for key, value in items:
        key_path = _join(path, key) if isinstance(node, dict) else f"{path}[{key}]"
        if isinstance(node, dict) and key in TRANSLATABLE_FIELDS:
            result[key_path] = (LINE_SEPARATOR.join(value) if isinstance(value, list)
                                else value)
        elif is_container(value):
            _collect_sources(value, key_path, result)


def source_strings(master):
    """Русские тексты всех переводимых полей мастера: {путь: текст}. Для замка."""
    result = {}
    _collect_sources(master, "", result)
    return result
