# test_cian_parcer.py

import os
from urllib.parse import urlparse, parse_qs
from Scripts.CianParcer import (
    validate_variant,
    generate_urls_with_pagination,
    fetch_rendered_page,
    extract_cian_ad_links,
)

# Ваша базовая конфигурация
VARIANT = {
    "deal_type": "sale",
    "engine_version": 2,
    "offer_type": "offices",
    "office_type[0]": 4,
    "region": 2,
}

# Директория для сохранения «пустых» страниц
DEBUG_DIR = "debug_pages"
os.makedirs(DEBUG_DIR, exist_ok=True)

print("=== validate_variant ===")
try:
    ok = validate_variant(VARIANT)
    print(" validate_variant returned:", ok)
except Exception as e:
    print(" validate_variant raised:", e)

print("\n=== generate_urls_with_pagination (3 pages) ===")
urls = generate_urls_with_pagination(VARIANT, max_pages=3)
for i, u in enumerate(urls, 1):
    print(f" Page {i}: {u}")

print("\n=== extract_cian_ad_links by fetching real pages ===")
all_links = []
for idx, page_url in enumerate(urls, 1):
    print(f"\n-- Page {idx} URL: {page_url}")
    try:
        page_html = fetch_rendered_page(page_url)
        print(" Fetched HTML, length:", len(page_html))
    except Exception as exc:
        print(" Failed to fetch/render page:", exc)
        continue

    links = extract_cian_ad_links(page_html)
    print(" Extracted links:", links)

    if not links:
        # сохраняем HTML для отладки
        fname = os.path.join(DEBUG_DIR, f"page_{idx}_empty.html")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f" Saved empty-page HTML to {fname}")

    all_links.extend(links)

# Убираем дубликаты
unique_links = sorted(set(all_links))
print("\n=== All unique collected links ===")
for link in unique_links:
    print(" ", link)

print("\nЗапуск: python test_cian_parcer.py")
