"""Цены: разбор строк прайса, диапазон, цена одной строкой, признак комбо.

Единственный источник цен — data/prices.json. Здесь нет ни одной цифры и почти ни
одного слова на языке сайта: подпись «от …» и название раздела по умолчанию приходят
от вызывающего, из строк языка. Исключение одно: комбо узнаётся по русскому названию
из prices.json (COMBO_RE).
"""
import re

ADDON_MARK = "+"  # «+350 000 đ» — надбавка к процедуре, а не её самостоятельная цена
PRICE_RE = re.compile(r"^\+?\d[\d ]*đ$")  # единственная допустимая форма записи цены
COMBO_RE = re.compile(r"^(КОМБО|Комбо)")  # признак считается по русскому названию из прайса


def price_value(price):
    """Цена строкой из прайса → число («1 500 000 đ» → 1500000).
    Пустая цена — None (позиция без цены). Любая другая форма — ошибка сборки:
    просто вырезать цифры нельзя, иначе «1 000 000 – 2 000 000 đ» молча уедет
    в разметку как 10000002000000."""
    text = price.strip()
    if not text:
        return None
    if not PRICE_RE.match(text):
        raise ValueError(f"Непонятная цена в prices.json: {price!r}. Допустимые формы — "
                         f"«1 500 000 đ», «+350 000 đ» или пустая строка.")
    return int(re.sub(r"[^\d]", "", text))


def is_addon(item):
    """Позиция, которую нельзя купить как саму услугу: надбавка к процедуре
    или сопутствующий товар. Часть видна по строке цены («+350 000 đ»), часть —
    нет: «Костюм для LPG — 400 000 đ» выглядит обычной ценой, но услугой не
    является. Такие помечены в прайсе флагом addon вручную."""
    return bool(item.get("addon")) or item["price"].strip().startswith(ADDON_MARK)


def price_aggregate(sections, currency):
    """Диапазон цен услуги (min/max/кол-во) для AggregateOffer — из строк прайса.
    Доплаты в диапазон не входят: иначе lowPrice занижает «услуги от» до надбавки,
    которую нельзя купить отдельно. Возвращает None, если цен нет."""
    values = [value for sec in sections for item in sec["items"]
              if not is_addon(item) and (value := price_value(item["price"])) is not None]
    if not values:
        return None
    return {"low": min(values), "high": max(values),
            "count": len(values), "currency": currency}


def price_hint(sections, format_from):
    """Цена услуги одной строкой — для мест вне прайса: сравнительной таблицы,
    подводки к ценам, llms.txt. Одна цена на всю услугу — показываем её, несколько
    разных — «от <минимальной>», как на карточках «Популярное». Доплаты не в счёт:
    надбавку нельзя заплатить вместо услуги. Нет цен — None."""
    values = [item["price"].strip() for sec in sections for item in sec["items"]
              if not is_addon(item) and price_value(item["price"]) is not None]
    if not values:
        return None
    if len(set(values)) == 1:
        return values[0]
    return format_from(min(values, key=price_value))


def compare_rows(rows, services, prices, format_from):
    """Строки сравнительной таблицы: название услуги берётся из content.yml,
    цена — из prices.json. Второго источника цен не появляется, поэтому таблица
    не расходится с прайсом. Неизвестный слаг или услуга без цены — ошибка сборки:
    пустая строка в таблице хуже упавшей сборки."""
    result = []
    for row in rows:
        slug = row["slug"]
        if slug not in services:
            raise ValueError(f"Сравнительная таблица: в content.yml нет услуги {slug!r}")
        hint = price_hint(prices.get(slug, []), format_from)
        if hint is None:
            raise ValueError(f"Сравнительная таблица: у услуги {slug!r} нет цены в прайсе")
        result.append({"title": services[slug]["title"], "task": row["task"], "price": hint})
    return result


def popular_price(prices, slug, name, format_from):
    """Цена для карточки «Популярное» на главной. Одноимённые позиции есть в разных
    разделах прайса с разной ценой (эпиляция у женщин и мужчин) — тогда показываем
    «от <минимальной>»: молча взять первую значит показать мужчине женскую цену.
    Позиции нет в прайсе — ошибка сборки, иначе карточка уедет в прод без цены."""
    matches = [item["price"] for sec in prices.get(slug, []) for item in sec["items"]
               if item["name"] == name]
    if not matches:
        raise ValueError(f"«Популярное»: в прайсе {slug} нет позиции {name!r}")
    if len(set(matches)) == 1:
        return matches[0]
    return format_from(min(matches, key=price_value))


def offer_sections(sections, default_title):
    """Разделы прайса для JSON-LD: цена числом, название и описание — дословно.
    Позиции без цифр в цене пропускаем (нечего утверждать о цене).

    Доплаты и сопутствующие товары в каталог не идут. Раньше шли, и надбавка
    «+350 000 đ» уезжала в разметку как Offer с price 350000: знак «+» теряется,
    остаётся полноценная цена услуги, которой нет. Описание («Дополнительно
    к процедурам») этого не лечит — цену читает машина, а не человек. Заодно
    каталог сходится с AggregateOffer: offerCount считается по тому же отбору."""
    result = []
    for sec in sections:
        items = [{"name": item["name"], "desc": item.get("desc", ""), "price": value}
                 for item in sec["items"] if not is_addon(item)
                 and (value := price_value(item["price"])) is not None]
        if items:
            result.append({"title": sec.get("section") or default_title, "items": items})
    return result


def is_combo(item):
    """Комбо-набор: в прайсе выводится карточкой, а не строкой таблицы."""
    return COMBO_RE.match(item["name"]) is not None


def price_view(sections):
    """Разделы прайса для шаблона: те же позиции с признаком комбо. Признак
    считается здесь, а не регуляркой в шаблоне: шаблон не должен знать язык названий."""
    return [{**sec, "items": [{**item, "is_combo": is_combo(item)} for item in sec["items"]]}
            for sec in sections]
