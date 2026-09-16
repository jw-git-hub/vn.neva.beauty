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
    """Чистый текст без HTML-тегов и лишних пробелов — для JSON-LD.

    Пробелы схлопываются: intro приходит свёрнутым YAML-скаляром и тащит за собой
    перенос строки в конце, а он уезжал прямо в description разметки."""
    return " ".join(_TAG_RE.sub("", text).split())

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
        # availableLanguage не входит в спецификацию BeautySalon — валидное место
        # для языков обслуживания это узел ContactPoint (иначе предупреждение валидатора).
        business["contactPoint"] = {
            "@type": "ContactPoint",
            "contactType": "customer service",
            "telephone": b["telephone"],
            "availableLanguage": b["language"],
        }
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


def _offer(item, currency):
    """Одна позиция прайса как Offer: цена числом, название и описание — дословно.
    Описание дублируется на самом Offer: у доплат («Дополнительно к процедурам») это
    единственный признак надбавки, и он должен читаться там же, где цена, — иначе
    потребитель разметки примет надбавку за полную стоимость услуги."""
    offered = {"@type": "Service", "name": item["name"]}
    offer = {
        "@type": "Offer",
        "price": item["price"],
        "priceCurrency": currency,
        "itemOffered": offered,
    }
    if item.get("desc"):
        offered["description"] = item["desc"]
        offer["description"] = item["desc"]
    return offer


def offer_catalog_node(name, sections, currency):
    """OfferCatalog — прайс услуги в машиночитаемом виде: связь «позиция → цена»
    задана явно, а не выводится поисковиком из вёрстки. Несколько разделов прайса —
    вложенные каталоги (та же группировка, что у вкладок на странице)."""
    if len(sections) == 1:
        elements = [_offer(item, currency) for item in sections[0]["items"]]
    else:
        elements = [
            {
                "@type": "OfferCatalog",
                "name": sec["title"],
                "itemListElement": [_offer(item, currency) for item in sec["items"]],
            }
            for sec in sections
        ]
    return {"@type": "OfferCatalog", "name": name, "itemListElement": elements}


def _offers_node(aggregate):
    """Цены услуги для Service.offers из {low, high, count, currency}.

    Одна позиция в прайсе — обычный Offer. AggregateOffer с совпадающими
    lowPrice/highPrice и offerCount 1 формально валиден, но утверждает диапазон
    цен там, где цена ровно одна: потребитель разметки читает «от 1 100 000 до
    1 100 000» и «предложений: 1». Диапазон осмысленен от двух позиций."""
    if aggregate["count"] == 1:
        return {
            "@type": "Offer",
            "price": aggregate["low"],
            "priceCurrency": aggregate["currency"],
        }
    return {
        "@type": "AggregateOffer",
        "priceCurrency": aggregate["currency"],
        "lowPrice": aggregate["low"],
        "highPrice": aggregate["high"],
        "offerCount": aggregate["count"],
    }


def service_node(name, description, provider_ref, area_name,
                 aggregate_offer=None, offer_catalog=None,
                 url=None, image=None, service_type=None):
    """Service — профильная услуга страницы. provider ссылается на узел бизнеса,
    areaServed — город. url даёт узлу стабильный @id и адрес страницы, image —
    её главный кадр, service_type — направление из таксономии сайта. Если передан
    aggregate_offer {low, high, count, currency}, добавляются цены (см. _offers_node);
    offer_catalog — готовый узел OfferCatalog с позициями прайса."""
    node = {
        "@type": "Service",
        "name": name,
        "description": _plain(description),
        "provider": provider_ref,
        "areaServed": {"@type": "City", "name": area_name},
    }
    if url:
        # @id делает услугу адресуемой сущностью: на неё можно сослаться из других
        # узлов графа, и потребитель разметки не склеивает одноимённые услуги сайтов.
        node["@id"] = url + "#service"
        node["url"] = url
    if image:
        node["image"] = image
    if service_type:
        node["serviceType"] = service_type
    if aggregate_offer:
        node["offers"] = _offers_node(aggregate_offer)
    if offer_catalog:
        node["hasOfferCatalog"] = offer_catalog
    return node


def render(site, extra_nodes=None):
    """Готовый безопасный JSON-LD для вставки в <script type=application/ld+json>."""
    graph = business_nodes(site)
    if extra_nodes:
        graph.extend(extra_nodes)
    doc = {"@context": "https://schema.org", "@graph": graph}
    return Markup(json.dumps(doc, ensure_ascii=False, indent=2))
