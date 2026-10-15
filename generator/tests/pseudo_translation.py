"""Псевдоперевод для тестов: «EN » перед каждой русской строкой. Даёт полную накладку
и полный словарь прайса той же формы, что настоящий перевод, — сборка английского
каркаса проверяется без настоящего перевода."""
import overlay
import price_translation as pt
from locales import site_strings

PREFIX = "EN "


def _pseudo_leaf(value):
    return [PREFIX + line for line in value] if isinstance(value, list) else PREFIX + value


def pseudo_content(node):
    if isinstance(node, list):
        return [pseudo_content(item) for item in node]
    result = {}
    for key, value in node.items():
        if key in overlay.TRANSLATABLE_FIELDS:
            result[key] = _pseudo_leaf(value)
        elif overlay.is_container(value):
            result[key] = pseudo_content(value)
    return result


def pseudo_prices(prices):
    catalog = {kind: {} for kind in pt.KINDS}
    for _, kind, key in pt.required_keys(prices):
        catalog[kind][key] = PREFIX + key
    return catalog


def pseudo_site(site):
    """Переопределения site для языка: «EN » перед каждой строкой site_strings."""
    strings = site_strings(site)
    result = {path: PREFIX + text for path, text in strings.items() if "[" not in path}
    result["locations"] = [{field: PREFIX + place[field] for field in ("city", "country")}
                           for place in site["locations"]]
    return result
