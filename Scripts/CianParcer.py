from Scripts.Param import PARAM_SPECS
import urllib.parse
import time
from Scripts.RealEstate import RealEstate
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

def validate_variant(variant, specs=PARAM_SPECS):
    """
    Проверяет, что каждый из переданных параметров удовлетворяет спецификации:
    - Тип данных
    - Допустимые значения (если заданы)
    - Минимальное/максимальное значение (если заданы)

    Если параметр не указан в спецификации, проверка для него не производится.

    Параметры:
      variant (dict): Словарь с параметрами запроса.
      specs (dict): Словарь со спецификацией параметров.

    Выбрасывает исключение ValueError, если найдено несоответствие.
    """
    for key, value in variant.items():
        if key in specs:
            spec = specs[key]
            expected_type = spec.get("type")
            if expected_type and not isinstance(value, expected_type):
                raise ValueError(
                    f"Параметр '{key}' должен быть типа {expected_type.__name__}, получено {type(value).__name__}.")
            if "allowed" in spec:
                if value not in spec["allowed"]:
                    raise ValueError(
                        f"Параметр '{key}' имеет недопустимое значение {value}. Допустимые значения: {spec['allowed']}.")
            if "min" in spec:
                if value < spec["min"]:
                    raise ValueError(
                        f"Параметр '{key}' имеет значение {value}, меньше допустимого минимума {spec['min']}.")
            if "max" in spec:
                if value > spec["max"]:
                    raise ValueError(
                        f"Параметр '{key}' имеет значение {value}, превышающее допустимый максимум {spec['max']}.")
    return True


def generate_cian_url(variant, base_url="https://www.cian.ru/cat.php", page=None):
    """
    Генерирует URL на CIAN.ru из набора GET-параметров.

    Параметры:
      variant (dict): Словарь с параметрами запроса (например, фильтры).
      base_url (str): Базовый URL для формирования запроса.
      page (int или None): Номер страницы для пагинации.
           Если page не равен 1, добавляется параметр 'p'.

    Возвращает:
      str: Сформированный URL.

    Перед генерацией URL производится валидация параметров.
    """
    # Выполняем проверку параметров, если они заданы
    validate_variant(variant)

    params = variant.copy()
    # Если номер страницы задан и не равен 1, добавляем параметр пагинации
    if page is not None and page != 1:
        params["p"] = page
    # Если страница равна 1 — удаляем параметр 'p', если он уже задан
    elif "p" in params:
        del params["p"]

    query_string = urllib.parse.urlencode(params)
    full_url = f"{base_url}?{query_string}"
    return full_url


def generate_urls_with_pagination(variant, max_pages, base_url="https://www.cian.ru/cat.php"):
    """
    Генерирует список URL для заданного набора параметров по всем страницам пагинации.

    Параметры:
      variant (dict): Словарь с параметрами запроса.
      max_pages (int): Общее количество страниц (максимальный номер страницы).
      base_url (str): Базовый URL для формирования запроса.

    Возвращает:
      list[str]: Список сгенерированных URL-ов для каждой страницы от 1 до max_pages.
    """
    if not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("max_pages должен быть целым числом, большим или равным 1")

    urls = []
    for page in range(1, max_pages + 1):
        url = generate_cian_url(variant, base_url, page)
        urls.append(url)
    return urls


import requests
from bs4 import BeautifulSoup


def fetch_rendered_page(
    url,
    wait: float = 1.5,
    fallback_threshold: float = 5.0,  # порог рендеринга в секундах
):
    """
    Пробует отрендерить страницу через Splash; если рендер занимает > fallback_threshold секунд
    или падает, то скачивает её напрямую (без Splash).
    """
    splash_base = "http://localhost:8050"
    headers = {"User-Agent": "Mozilla/5.0 ..."}  # ваш UA

    params = {
        "url": url,
        "wait": wait,
        "images": 0,
        "resource_timeout": 5,
        "timeout": int(fallback_threshold + 1),  # общий таймаут чуть больше порога
    }

    def _direct_fetch():
        print(f"Fetching without renderer: {url}")
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text

    try:
        start = time.monotonic()
        resp = requests.get(
            f"{splash_base}/render.html",
            params=params,
            headers=headers,
            timeout=fallback_threshold + 1
        )
        resp.raise_for_status()
        render_time = time.monotonic() - start

        print(f"Render time for {url}: {render_time:.2f} s")
        if render_time > fallback_threshold:
            print(f"Превысили порог {fallback_threshold}s, фоллбэк на прямую загрузку")
            return _direct_fetch()

    except requests.exceptions.RequestException as e:
        print(f"Splash error ({e}), фоллбэк на прямую загрузку")
        return _direct_fetch()

    return resp.text


def parse_cian_page(html):
    """
    Пример разборки HTML-кода страницы с CIAN.
    В данном примере извлекаются заголовки объектов, указанных на странице.

    Параметры:
      html (str): Рендеренный HTML-код страницы.

    Возвращает:
      list[str]: Список заголовков объектов (названия или другой ключевой текст).
    """
    soup = BeautifulSoup(html, 'lxml')

    # Пример: на CIAN объекты часто оформлены в карточки с определёнными классами.
    # Допустим, мы ищем элементы с классом "c-card__title" для примера.
    # (Класс может отличаться, поэтому его следует проверить в HTML-коде страницы)
    titles = [el.get_text(strip=True) for el in soup.select(".c-card__title")]

    return titles


import os
import requests
from datetime import datetime


def save_html(html_content, pages_dir="pages"):
    """
    Сохраняет HTML-контент в файл с динамически генерируемым именем.

    Args:
        html_content (str): HTML контент для сохранения.
        pages_dir (str, optional): Директория для сохранения файла. По умолчанию "pages".

    Returns:
        str: Полный путь к сохранённому файлу.
    """
    if not os.path.exists(pages_dir):
        os.makedirs(pages_dir)

    # Формирование имени файла с меткой времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"rendered_page_{timestamp}.html"
    file_path = os.path.join(pages_dir, file_name)

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(html_content)

    return file_path


def extract_total_pages(html):
    """
    Определяет количество страниц в пагинации для HTML документа.

    Функция ищет блок пагинации (например, с data-name="PaginationSection") и
    анализирует текстовые элементы, содержащие только цифры, возвращая максимальное число.

    Если блок пагинации не найден или числовых значений нет, возвращает 1.

    Параметры:
        html (str): Строка с HTML кодом страницы.

    Возвращает:
        int: Количество страниц в пагинации.
    """
    soup = BeautifulSoup(html, "html.parser")
    total_pages = 1

    # Поиск блока пагинации по атрибуту data-name (например, "PaginationSection")
    pagination_section = soup.find(attrs={"data-name": "PaginationSection"})

    if pagination_section:
        # Ищем все элементы, текст которых состоит только из цифр
        page_numbers = []
        for element in pagination_section.find_all(string=True):
            text = element.strip()
            if text.isdigit():
                page_numbers.append(int(text))
        if page_numbers:
            total_pages = max(page_numbers)

    return total_pages

import re

def extract_cian_ad_links(html_content: str) -> list[str]:
    """
    Возвращает все уникальные ссылки на объявления CIAN
    (квартиры, коммерческая, офисы и т.д.).

    • Учитывает абсолютные URL с разными поддоменами (www, spb, …).
    • Понимает относительный путь «/sale/...».
    • Типы объектов перечислены в allowed_obj — при необходимости
      расширяйте список.
    """
    from bs4 import BeautifulSoup
    import re, requests

    # ───── локальные переменные, используемые ТОЛЬКО внутри функции ─────
    allowed_obj = r"(?:flat|commercial|office|offices)"
    re_abs = re.compile(
        rf"^https?://(?:[\w\-]+\.)?cian\.ru/sale/{allowed_obj}/\d+/?$",
        re.IGNORECASE,
    )
    re_rel = re.compile(
        rf"^/sale/{allowed_obj}/\d+/?$",
        re.IGNORECASE,
    )
    # ─────────────────────────────────────────────────────────────────────

    soup = BeautifulSoup(html_content, "html.parser")
    links: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"]

        if re_abs.match(href):
            links.add(href)
        elif re_rel.match(href):
            abs_url = requests.compat.urljoin("https://www.cian.ru", href)
            links.add(abs_url)

    return sorted(links)

def collect_and_save_ad_links(variant: dict,
                              base_url: str = "https://www.cian.ru/cat.php",
                              output_file: str = "ad_links.txt"):
    """
    Собирает все ссылки на объявления по заданным параметрам и сохраняет их в файл.

    1. Генерирует URL первой страницы.
    2. Получает общее число страниц через extract_total_pages.
    3. Для каждой страницы загружает HTML, сохраняет локально, извлекает ссылки.
    4. Выводит прогресс в консоль и сохраняет итоговый список в output_file.
    """
    # Первая страница
    first_url = generate_cian_url(variant, base_url, page=1)
    print(f"Загружаю первую страницу: {first_url}")
    html = fetch_rendered_page(first_url)
    save_html(html)

    total_pages = extract_total_pages(html)
    print(f"Всего страниц: {total_pages}")

    all_links = set()
    for page in range(1, total_pages + 1):
        url = generate_cian_url(variant, base_url, page)
        print(f"[{page}/{total_pages}] Загружаю: {url}")
        page_html = fetch_rendered_page(url)
        save_html(page_html)
        links = extract_cian_ad_links(page_html)
        print(f"  Найдено {len(links)} ссылок на странице {page}")
        all_links.update(links)

    print(f"Всего уникальных ссылок: {len(all_links)}")
    with open(output_file, "w", encoding="utf-8") as f:
        for link in sorted(all_links):
            f.write(link + "\n")
    print(f"Ссылки сохранены в {output_file}")


def save_html(url: str, pages_dir: str = "pages", wait: float = 2.0) -> str:
    """
    Получает URL страницы, рендерит её через Splash и сохраняет полученный HTML в директорию pages.
    Возвращает путь к сохранённому файлу.
    """
    # Рендерим страницу
    print(f"Рендеринг страницы: {url}")
    html_content = fetch_rendered_page(url, wait)

    # Создаём директорию, если нужно
    if not os.path.exists(pages_dir):
        os.makedirs(pages_dir)

    # Формируем имя файла с меткой времени
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"rendered_{timestamp}.html"
    file_path = os.path.join(pages_dir, file_name)

    # Сохраняем HTML
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Страница сохранена в: {file_path}")
    return file_path


# Регекс для начала встроенного JSON-блока
_JSON_START = re.compile(r'\{\s*"factoids"\s*:\s*\[')

def _extract_embedded_json(html: str) -> Optional[dict]:
    """Находит и парсит большой JSON-блок CIAN внутри HTML."""
    m = _JSON_START.search(html)
    if not m:
        return None
    start = m.start()
    level = 0
    in_str = False
    esc = False
    for i, ch in enumerate(html[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                level += 1
            elif ch == '}':
                level -= 1
                if level == 0:
                    try:
                        return json.loads(html[start:i+1])
                    except json.JSONDecodeError:
                        return None
    return None

def parse_cian_offer(html: str) -> 'RealEstate':
    """Parse a CIAN offer page (HTML) and return a filled RealEstate instance.

    Key change ➜ the address is now extracted *without* marketing fluff:
      • We try <meta property="og:description">, which holds just the location.
      • Otherwise we fall back to a cleaned <meta name="description"> value.

    The function is self‑contained (no canvas / external state required).
    """
    soup = BeautifulSoup(html, 'lxml')

    # --- embedded JSON produced by CIAN in <script> ---
    data: dict = _extract_embedded_json(html) or {}

    # Helper to safely dig into the JSON by dotted path
    def get(path: str, default=None):
        cur = data
        for key in path.split('.'):  # type: ignore[arg-type]
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key)
        return cur if cur is not None else default

    # ------------------------------------------------------------------
    # Address extractor -------------------------------------------------
    # ------------------------------------------------------------------
    def _extract_address() -> str | None:
        """Return a location string like «Москва, Щербинка, Южный квартал, 7»."""
        # 1️⃣ Prefer the concise OG description if it exists
        og_meta = soup.find('meta', property='og:description')
        if og_meta and og_meta.get('content'):
            return og_meta['content'].strip()

        # 2️⃣ Otherwise clean the verbose meta description
        desc_meta = soup.find('meta', {'name': 'description'})
        if desc_meta and desc_meta.get('content'):
            text = desc_meta['content']

            # Cut everything after «. Цена» (marketing & price info)
            text = re.split(r'\.\s*Цена', text, 1)[0]

            # Drop leading arrow/emoji and marketing verbs like «Купите» / «Продам»
            text = re.sub(r'^\s*[\W_\d»«➜]*\s*(Куп(ите|ить)|Прод(ам|айте|ажа))[^А-ЯA-Z]*', '', text, flags=re.IGNORECASE)

            return text.strip()

        # 3️⃣ As a last‑resort build address from JSON chunks
        addr_parts = [
            get('geo.city'),
            get('geo.subzone'),
            get('geo.street'),
            get('geo.houseNumber'),
        ]
        addr_parts = [p for p in addr_parts if p]
        return ', '.join(addr_parts) if addr_parts else None

    # ------------------------------------------------------------------
    # Model population --------------------------------------------------
    # ------------------------------------------------------------------
    re_obj = RealEstate()

    # Identity ----------------------------------------------------------
    id_meta = soup.find('meta', {'name': 'ca-offer-id'})
    re_obj.id = id_meta['content'] if id_meta else None
    re_obj.address = _extract_address()

    # Price -------------------------------------------------------------
    price_el = soup.select_one('[data-testid="price-amount"]')
    if price_el:
        price_num = re.sub(r'[^0-9]', '', price_el.get_text())
        re_obj.price = float(price_num) if price_num else None
        re_obj.currency = 'RUB'
    re_obj.price_per_sqm = get('priceInfo.pricePerSquareValue')

    # Layout ------------------------------------------------------------
    re_obj.rooms        = get('roomsCount')
    re_obj.total_area   = float(get('totalArea')   or 0)
    re_obj.living_area  = float(get('livingArea')  or 0)
    re_obj.kitchen_area = float(get('kitchenArea') or 0)

    # Building ----------------------------------------------------------
    re_obj.floor             = get('floorNumber')
    re_obj.floors_total      = get('building.floorsCount')
    re_obj.year_built        = get('building.buildYear')
    re_obj.building_material = get('building.materialType')
    ch = get('building.ceilingHeight')
    re_obj.ceiling_height    = float(ch or 0)

    # Comfort -----------------------------------------------------------
    re_obj.bathrooms    = (get('separateWcsCount', 0) or 0) + (get('combinedWcsCount', 0) or 0)
    re_obj.is_furnished = get('hasFurniture')
    re_obj.renovation   = get('repairType')
    re_obj.window_view  = get('windowsViewType')

    # Transport ---------------------------------------------------------
    if data.get('undergrounds'):
        u = data['undergrounds'][0]
        re_obj.transport_nearby[u.get('name')] = u.get('travelTime', 0)

    # Contacts ----------------------------------------------------------
    if data.get('phones'):
        p = data['phones'][0]
        re_obj.contact_phone = f"{p.get('countryCode')} {p.get('number')}"

    # Media -------------------------------------------------------------
    re_obj.photos = [ph['fullUrl'] for ph in data.get('photos', []) if ph.get('fullUrl')]
    re_obj.videos = [vd['url']    for vd in data.get('videos', []) if vd.get('url')]

    # Price history -----------------------------------------------------
    history = data.get('priceHistory', {}).get('history', [])
    for ev in history:
        date_str = ev.get('eventDate', '')
        try:
            dt = datetime.fromisoformat(date_str)  # noqa: F841 – kept for future use
        except ValueError:
            continue

    # Coordinates -------------------------------------------------------
    coords = data.get('coordinates')
    if coords:
        re_obj.coords = (coords.get('lat'), coords.get('lng'))

    # Misc --------------------------------------------------------------
    excluded = {
        'factoids', 'priceHistory', 'photos', 'videos',
        'building', 'priceInfo', 'undergrounds', 'phones', 'coordinates'
    }
    re_obj.extra_attributes = {k: v for k, v in data.items() if k not in excluded}

    return re_obj
