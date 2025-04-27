"""
Старт:
    pip install Flask geopy overpy beautifulsoup4 lxml requests
    export FLASK_APP=app.py
    flask run --reload
"""

from __future__ import annotations

import os, json, hashlib, uuid
from typing import Dict, Any, List, Set

from flask import Flask, render_template, request, jsonify, abort

# ── импорты из пакета Scripts ─────────────────────────────────────────
from Scripts.RealEstate import RealEstate
from Scripts.CianParcer import (
    validate_variant,
    generate_urls_with_pagination,
    fetch_rendered_page,
    extract_cian_ad_links,
    parse_cian_offer,
)

# ── кеш-директория ────────────────────────────────────────────────────
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

app = Flask(__name__)


# ──────────────────────────────────────────────────────────────────────
#  ШАБЛОН
# ──────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", title="Главная")


# ──────────────────────────────────────────────────────────────────────
#  ОСНОВНОЙ GET-эндпоинт
# ──────────────────────────────────────────────────────────────────────
@app.get("/search")
def cian_search() -> Any:
    args = request.args

    # — служебные —
    max_pages  = args.get("max_pages", 1,  int)
    radius     = args.get("radius",    100, int)
    limit      = args.get("limit",     50,  int)
    venue_type = args.get("venue_type","standard", str)

    # — variant —
    skip = {"max_pages", "radius", "limit", "venue_type"}
    variant: Dict[str, Any] = {}
    for k, v in args.items():
        if k in skip: continue
        if v.isdigit():
            variant[k] = int(v)
        else:
            try:       variant[k] = float(v)
            except ValueError:
                        variant[k] = v

    # — валидация —
    try:
        validate_variant(variant)
    except ValueError as e:
        abort(400, str(e))

    # ──────────────────────────────────────────────────────────────────
    #  КЕШ: ключ = md5(variant|others)
    # ──────────────────────────────────────────────────────────────────
    key_src = json.dumps(
        {"variant": variant,
         "max_pages": max_pages,
         "radius": radius,
         "limit": limit,
         "venue_type": venue_type},
        sort_keys=True, ensure_ascii=False
    )
    cache_name = hashlib.md5(key_src.encode()).hexdigest() + ".json"
    cache_path = os.path.join(CACHE_DIR, cache_name)

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))

    # ──────────────────────────────────────────────────────────────────
    #  ПАРСИНГ CIAN
    # ──────────────────────────────────────────────────────────────────
    urls = generate_urls_with_pagination(variant, max_pages)
    estates: List[RealEstate] = []
    seen_links: Set[str] = set()

    for page_url in urls:
        try:
            page_html = fetch_rendered_page(page_url)
        except Exception:
            continue

        for ad_url in extract_cian_ad_links(page_html):
            if len(estates) >= limit: break
            if ad_url in seen_links:  continue
            seen_links.add(ad_url)

            try:
                ad_html = fetch_rendered_page(ad_url)
                est = parse_cian_offer(ad_html)
            except Exception:
                continue

            est.id = est.id or str(uuid.uuid4())

            try:
                if not est.coords:
                    est.geocode_address()
                est.fetch_nearby_objects(radius=radius)
            except Exception:
                pass

            estates.append(est)
        if len(estates) >= limit:
            break

    if not estates:
        abort(502, "Не удалось получить ни одного объявления")

    # ──────────────────────────────────────────────────────────────────
    #  СТАТИСТИКА + ОЦЕНКИ   ——   FLATTEN   ——   УБИРАЕМ nearby_…
    # ──────────────────────────────────────────────────────────────────
    stats = RealEstate.compute_stats(estates, radius=radius)
    enriched: List[Dict[str, Any]] = []

    for est in estates:
        try:
            scores = est.evaluate(stats, venue_type=venue_type)
        except Exception:
            scores = {}

        flat = est.to_dict()

        # удаляем «тяжёлые» поля
        flat.pop("nearby_objects", None)
        flat.pop("nearby_grouped_objects", None)

        # раскладываем оценки
        flat.update(scores)
        enriched.append(flat)

    result = {"count": len(enriched), "estates": enriched}

    # — сохраняем кеш —
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
