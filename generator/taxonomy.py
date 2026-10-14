"""Таксономия сайта: разделы, связанные услуги, навигация.

Единственный источник — content.yml: из него строятся меню, крошки, страницы
разделов и блок «Смотрите также», поэтому они не могут разойтись между собой.
"""
from routes import HOME

RELATED_COUNT = 3  # сколько карточек «Смотрите также» показываем на странице услуги


def has_own_page(cat):
    """Раздел из одной услуги своей страницы не имеет: он ведёт на страницу услуги."""
    return len(cat["services"]) > 1


def page_ids(content):
    """Идентификаторы страниц сайта: услуги и разделы, у которых есть своя страница."""
    category_pages = [cat["slug"] for cat in content["categories"] if has_own_page(cat)]
    return list(content["services"]) + category_pages


def enrich_categories(content, routes, locale):
    """Дописывает разделам адрес и признак своей страницы, услугам — название раздела.
    Раздел без своей страницы (см. has_own_page) ведёт на страницу услуги."""
    title_by_service = {}
    for cat in content["categories"]:
        cat["is_page"] = has_own_page(cat)
        cat["page_id"] = cat["slug"] if cat["is_page"] else cat["services"][0]
        cat["url"] = routes.path(locale, cat["page_id"])
        cat["href"] = routes.href(locale, cat["page_id"])
        for service_id in cat["services"]:
            title_by_service[service_id] = cat["title"]
    for service_id, svc in content["services"].items():
        svc["category"] = title_by_service[service_id]


def category_of(content, service_id):
    """Раздел, в котором стоит услуга."""
    return next(cat for cat in content["categories"] if service_id in cat["services"])


def _top_up(related, slug, pool):
    """Добирает из пула в конец списка, пока не наберётся RELATED_COUNT.
    Сама услуга и уже выбранные пропускаются."""
    for candidate in pool:
        if len(related) >= RELATED_COUNT:
            return
        if candidate != slug and candidate not in related:
            related.append(candidate)


def fill_related(content):
    """Гарантирует ровно RELATED_COUNT связанных услуг: кураторский список,
    затем соседи по категории, затем прочие услуги — чтобы блок «Смотрите также»
    никогда не был короче остальных страниц."""
    services = content["services"]
    siblings_by_slug = {
        slug: [s for s in cat["services"] if s != slug]
        for cat in content["categories"] for slug in cat["services"]
    }
    for slug, svc in services.items():
        related = [r for r in dict.fromkeys(svc.get("related", [])) if r != slug and r in services]
        for pool in (siblings_by_slug.get(slug, []), services):
            _top_up(related, slug, pool)
        svc["related"] = related[:RELATED_COUNT]


def _nav_item(cat, content, routes, locale):
    item = {"label": cat.get("nav_label", cat["title"]), "title": cat["title"],
            "href": cat["href"], "is_home": False}
    if cat["is_page"]:
        item["children"] = [{"label": content["services"][service_id]["title"],
                             "href": routes.href(locale, service_id)}
                            for service_id in cat["services"]]
    return item


def build_nav(content, routes, locale):
    """Меню сайта. label — короткая подпись для верхней панели, title — полное
    название для мобильного меню и страниц."""
    home = {"label": locale.t("nav.home"), "title": locale.t("nav.home"),
            "href": routes.href(locale, HOME), "is_home": True}
    return [home] + [_nav_item(cat, content, routes, locale) for cat in content["categories"]]
