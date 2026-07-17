"""Сборка JSON-LD (schema.org) из данных site.yml.

Единый источник разметки бизнеса: один связный граф (@graph) с узлами
Organization + <тип бизнеса> + WebSite, к которому страницы добавляют свои узлы
(Service / FAQPage / BreadcrumbList). JSON собирается в Python, а не в шаблоне,
чтобы не ломаться об autoescape Jinja и оставаться валидным.
"""
import json
import re
from markupsafe import Markup

_TAG_RE = re.compile(r"<[^>]+>")


def _plain(text):
    """Чистый текст без HTML-тегов — для answer в JSON-LD (ссылки в разметке не нужны)."""
    return _TAG_RE.sub("", text)

ORG_ID = "#organization"
BUSINESS_ID = "#business"
WEBSITE_ID = "#website"


def _postal_address(addr):
    node = {
        "@type": "PostalAddress",
        "addressLocality": addr["locality"],
        "addressCountry": addr["country"],
    }
    if addr.get("region"):
        node["addressRegion"] = addr["region"]
    if addr.get("street"):
        node["streetAddress"] = addr["street"]
    if addr.get("postal_code"):
        node["postalCode"] = addr["postal_code"]
    return node


def _opening_hours(hours):
    return [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": spec["days"],
            "opens": spec["opens"],
            "closes": spec["closes"],
        }
        for spec in hours
    ]


def business_nodes(site):
    """Общие узлы бизнеса — одинаковы на всех страницах (entity consistency)."""
    base = site["base_url"]
    brand = site["brand"]
    b = site["business"]
    org_ref = {"@id": base + "/" + ORG_ID}

    organization = {
        "@type": "Organization",
        "@id": base + "/" + ORG_ID,
        "name": brand,
        "url": base + "/",
        "logo": base + b.get("logo", "/favicon.svg"),
    }
    if b.get("same_as"):
        organization["sameAs"] = b["same_as"]

    business = {
        "@type": b.get("type", "BeautySalon"),
        "@id": base + "/" + BUSINESS_ID,
        "name": brand,
        "url": base + "/",
        "image": base + b.get("image", "/assets/img/hero.jpg"),
        "telephone": b["telephone"],
        "address": _postal_address(b["address"]),
        "areaServed": {"@type": "City", "name": b["address"]["locality"]},
        "parentOrganization": org_ref,
    }
    if b.get("price_range"):
        business["priceRange"] = b["price_range"]
    if b.get("currency"):
        business["currenciesAccepted"] = b["currency"]
    if b.get("language"):
        business["availableLanguage"] = b["language"]
    if b.get("same_as"):
        business["sameAs"] = b["same_as"]
    if b.get("geo"):
        business["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": b["geo"]["lat"],
            "longitude": b["geo"]["lng"],
        }
    if b.get("hours"):
        business["openingHoursSpecification"] = _opening_hours(b["hours"])

    website = {
        "@type": "WebSite",
        "@id": base + "/" + WEBSITE_ID,
        "url": base + "/",
        "name": brand,
        "inLanguage": b.get("language_code", "ru"),
        "publisher": org_ref,
    }
    return [organization, business, website]


def breadcrumb_node(items):
    """BreadcrumbList из [{name, url}, ...] — абсолютные URL, порядок = вложенность.

    Адрес звена дублируется в двух полях: `item` — обязательное для Google/schema.org,
    `url` — поле из документации Яндекса (валидно на ListItem как наследнике Thing).
    """
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": item["name"],
                "item": item["url"],
                "url": item["url"],
            }
            for i, item in enumerate(items)
        ],
    }


def item_list_node(name, urls):
    """ItemList из URL услуг категории — связывает раздел с входящими услугами."""
    return {
        "@type": "ItemList",
        "name": name,
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "item": url}
            for i, url in enumerate(urls)
        ],
    }


def faq_node(faq):
    """FAQPage из списка [{q, a}, ...] — только реальные вопросы-ответы."""
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": _plain(item["a"])},
            }
            for item in faq
        ],
    }


def service_node(name, description, provider_ref, area_name, aggregate_offer=None):
    """Service — профильная услуга страницы. provider ссылается на узел бизнеса,
    areaServed — город. Если передан aggregate_offer {low, high, count, currency},
    добавляется AggregateOffer с диапазоном цен (числа считаются из прайса)."""
    node = {
        "@type": "Service",
        "name": name,
        "description": _plain(description),
        "provider": provider_ref,
        "areaServed": {"@type": "City", "name": area_name},
    }
    if aggregate_offer:
        node["offers"] = {
            "@type": "AggregateOffer",
            "priceCurrency": aggregate_offer["currency"],
            "lowPrice": aggregate_offer["low"],
            "highPrice": aggregate_offer["high"],
            "offerCount": aggregate_offer["count"],
        }
    return node


def render(site, extra_nodes=None):
    """Готовый безопасный JSON-LD для вставки в <script type=application/ld+json>."""
    graph = business_nodes(site)
    if extra_nodes:
        graph.extend(extra_nodes)
    doc = {"@context": "https://schema.org", "@graph": graph}
    return Markup(json.dumps(doc, ensure_ascii=False, indent=2))
