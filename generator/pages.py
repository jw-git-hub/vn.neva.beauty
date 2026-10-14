"""Сборка страниц по типам. Каждая функция возвращает готовый HTML одной страницы."""
import re
from dataclasses import dataclass

import contacts
import pricing
import schema
import taxonomy
from routes import HOME, NOT_FOUND, PRIVACY


@dataclass
class BuildContext:
    """Всё, что нужно для сборки страниц одного языка."""
    site: dict
    content: dict
    prices: dict
    locale: object
    routes: object
    env: object
    base_schema: object

    def t(self, key, **params):
        return self.locale.t(key, **params)

    def path(self, page_id):
        return self.routes.path(self.locale, page_id)

    def url(self, page_id):
        return self.routes.url(self.locale, page_id)


PLACEHOLDER_RE = re.compile(r"\{(whatsapp|telegram|instagram|price)\}")


def content_tokens(contacts, price=None):
    """Плейсхолдеры, доступные в текстах content.yml: URL мессенджеров из site.yml
    и цена услуги из prices.json. Единый источник у каждого значения ровно один,
    поэтому текст не может разойтись ни с контактами, ни с прайсом."""
    tokens = {
        "{whatsapp}": contacts["whatsapp_url"],
        "{telegram}": contacts["telegram_url"],
        "{instagram}": contacts["instagram_url"],
    }
    if price:
        tokens["{price}"] = price
    return tokens


def fill_tokens(text, tokens):
    """Подставляет значения плейсхолдеров. Нераскрытый плейсхолдер — ошибка сборки:
    иначе фигурная скобка уезжает в текст страницы и её видит посетитель."""
    for token, value in tokens.items():
        text = text.replace(token, value)
    if PLACEHOLDER_RE.search(text):
        raise ValueError(f"Нераскрытый плейсхолдер в тексте content.yml: {text[:80]!r}")
    return text


def render_faq(ctx, faq, price=None, page_title=None):
    """Финализирует HTML-ответы FAQ: ссылки на мессенджеры получают текст страницы
    и метки (contacts.fill_contact_links), остальные плейсхолдеры подставляются
    (см. content_tokens), внутренние ссылки href="/<идентификатор>/" переводятся
    в адреса языка страницы."""
    site_contacts = ctx.site["contacts"]
    message = contacts.contact_message(ctx.locale, page_title)
    tokens = content_tokens(site_contacts, price)

    def finish(answer):
        answer = contacts.fill_contact_links(answer, site_contacts, message)
        return ctx.routes.localize_links(ctx.locale, fill_tokens(answer, tokens))

    return [{"q": item["q"], "a": finish(item["a"])} for item in faq]


def build_home(ctx):
    home = ctx.content["home"]
    home["faq"] = render_faq(ctx, home.get("faq", []))
    for item in home.get("popular", []):
        item["price"] = pricing.popular_price(ctx.prices, item["slug"], item["name"],
                                              ctx.locale.format_from)
    schema_json = (schema.render(ctx.site, [schema.faq_node(home["faq"])])
                   if home["faq"] else ctx.base_schema)
    page = {"id": HOME, "url": ctx.path(HOME),
            "seo_title": home.get("seo_title", ctx.t("home.seo_title_default")),
            "seo_desc": home.get("seo_desc", ""), "schema_json": schema_json,
            "hero_image": "/assets/img/hero.webp",  # LCP-элемент → preload в base.html.j2
            "hero_stem": "hero", "hero_slot": "home_hero"}
    return ctx.env.get_template("home.html.j2").render(
        site=ctx.site, page=page, home=home, categories=ctx.content["categories"])


def _service_crumbs(ctx, service_id, svc, cat):
    crumbs = [{"name": ctx.t("nav.home"), "url": ctx.url(HOME)}]
    if cat["is_page"]:
        crumbs.append({"name": cat["title"], "url": ctx.url(cat["page_id"])})
    crumbs.append({"name": svc["title"], "url": ctx.url(service_id)})
    return crumbs


def _service_node(ctx, service_id, svc, cat, sections):
    """Узел Service с ценами: диапазон и каталог позиций из прайса."""
    currency = ctx.site["business"].get("currency")
    offers = pricing.offer_sections(sections, ctx.t("service.price_section_default"))
    catalog_name = ctx.t("service.catalog_name", title=svc["title"])
    catalog = schema.offer_catalog_node(catalog_name, offers, currency) if offers else None
    return schema.service_node(
        svc["title"], svc["intro"],
        {"@id": ctx.site["base_url"] + "/" + schema.BUSINESS_ID},
        ctx.site["business"]["address"]["locality"],
        pricing.price_aggregate(sections, currency), catalog,
        url=ctx.url(service_id),
        image=f"{ctx.site['base_url']}/assets/img/{svc['hero_image']}.webp",
        service_type=cat["title"])


def _prepare_service_texts(ctx, svc, hint):
    """Подставляет цену и контакты в тексты услуги, собирает сравнительную таблицу."""
    if svc.get("price_lead"):
        svc["price_lead"] = fill_tokens(svc["price_lead"],
                                        content_tokens(ctx.site["contacts"], hint))
    if svc.get("compare"):
        svc["compare"]["rows"] = pricing.compare_rows(
            svc["compare"]["rows"], ctx.content["services"], ctx.prices, ctx.locale.format_from)
    if svc.get("faq"):
        svc["faq"] = render_faq(ctx, svc["faq"], hint, svc["title"])


def build_service(ctx, service_id):
    svc = ctx.content["services"][service_id]
    cat = taxonomy.category_of(ctx.content, service_id)
    sections = ctx.prices.get(service_id, [])
    nodes = [schema.breadcrumb_node(_service_crumbs(ctx, service_id, svc, cat)),
             _service_node(ctx, service_id, svc, cat, sections)]
    _prepare_service_texts(ctx, svc, pricing.price_hint(sections, ctx.locale.format_from))
    if svc.get("faq"):
        nodes.append(schema.faq_node(svc["faq"]))
    page = {"id": service_id, "url": ctx.path(service_id), "contact_title": svc["title"],
            "seo_title": svc["seo_title"], "seo_desc": svc["seo_desc"],
            "schema_json": schema.render(ctx.site, nodes),
            "hero_image": f"/assets/img/{svc['hero_image']}.webp",  # LCP → preload
            "hero_stem": svc["hero_image"], "hero_slot": "service_hero"}
    return ctx.env.get_template("service.html.j2").render(
        site=ctx.site, page=page, svc=svc, slug=service_id, category=cat,
        sections=pricing.price_view(sections), services=ctx.content["services"])


def build_category(ctx, cat):
    crumbs = [{"name": ctx.t("nav.home"), "url": ctx.url(HOME)},
              {"name": cat["title"], "url": ctx.url(cat["page_id"])}]
    service_urls = [ctx.url(service_id) for service_id in cat["services"]]
    nodes = [schema.breadcrumb_node(crumbs), schema.item_list_node(cat["title"], service_urls)]
    if cat.get("faq"):
        cat["faq"] = render_faq(ctx, cat["faq"], page_title=cat["title"])
        nodes.append(schema.faq_node(cat["faq"]))
    page = {"id": cat["page_id"], "url": cat["url"], "contact_title": cat["title"],
            "seo_title": cat["seo_title"],
            "seo_desc": cat["seo_desc"], "schema_json": schema.render(ctx.site, nodes)}
    return ctx.env.get_template("category.html.j2").render(
        site=ctx.site, page=page, cat=cat, services=ctx.content["services"],
        categories=ctx.content["categories"])


def _noindex_page(ctx, page_id, title_key):
    """Служебная страница: закрыта от индексации, разметка — только общий граф бизнеса."""
    return {"id": page_id, "url": ctx.path(page_id), "seo_title": ctx.t(title_key),
            "seo_desc": "", "schema_json": ctx.base_schema, "noindex": True}


def build_privacy(ctx, privacy_body):
    page = _noindex_page(ctx, PRIVACY, "privacy.seo_title")
    return ctx.env.get_template("privacy.html.j2").render(
        site=ctx.site, page=page, privacy_body=privacy_body)


def build_not_found(ctx):
    page = _noindex_page(ctx, NOT_FOUND, "not_found.seo_title")
    return ctx.env.get_template("404.html.j2").render(site=ctx.site, page=page)


def build_all(ctx, privacy_body):
    """Все страницы языка: пары (идентификатор, HTML) в порядке сборки."""
    yield HOME, build_home(ctx)
    for service_id in ctx.content["services"]:
        yield service_id, build_service(ctx, service_id)
    for cat in ctx.content["categories"]:
        if cat["is_page"]:
            yield cat["page_id"], build_category(ctx, cat)
    yield PRIVACY, build_privacy(ctx, privacy_body)
    yield NOT_FOUND, build_not_found(ctx)
