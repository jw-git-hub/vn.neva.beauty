"""Псевдоперевод для тестов: «EN » перед каждой русской строкой. Даёт полную накладку
и полный словарь прайса той же формы, что настоящий перевод, — сборка английского
каркаса проверяется без настоящего перевода."""
import overlay
import price_translation as pt

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
