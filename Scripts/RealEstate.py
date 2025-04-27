"""
Полностью обновлённый класс RealEstate

• Улучшено геокодирование ― умеет «чистить» строку адреса и
  пробует несколько вариантов запроса к Nominatim.
• compute_stats автоматически дотягивает nearby-данные для объектов,
  у которых их ещё нет.
"""

from __future__ import annotations

import re
from functools import lru_cache
from statistics import mean, stdev
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, ClassVar

import overpy
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError, GeocoderUnavailable


# ────────────────────────────────────────────────────────────────────────────────
#  EVENTS
# ────────────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class PriceEvent:
    date: datetime
    price: float
    diff: Optional[float] = None

    # для краткого отладочного вывода
    def __repr__(self) -> str:                # pragma: no cover
        diff = f", diff={self.diff}" if self.diff is not None else ""
        return f"PriceEvent(date={self.date:%Y-%m-%d}, price={self.price}{diff})"


# ────────────────────────────────────────────────────────────────────────────────
#  CORE MODEL
# ────────────────────────────────────────────────────────────────────────────────
@dataclass
class RealEstate:
    # — Основная идентификация —
    id: Optional[str] = None
    address: Optional[str] = None
    coords: Optional[Tuple[float, float]] = None          # (lat, lon)

    # — Цены —
    price: Optional[float] = None
    currency: Optional[str] = None
    price_per_sqm: Optional[float] = None
    price_history: List[PriceEvent] = field(default_factory=list)

    # — Параметры объекта —
    rooms: Optional[int] = None
    total_area: Optional[float] = None
    living_area: Optional[float] = None
    kitchen_area: Optional[float] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    year_built: Optional[int] = None
    building_material: Optional[str] = None
    ceiling_height: Optional[float] = None
    bathrooms: Optional[int] = None
    is_furnished: Optional[bool] = None
    renovation: Optional[str] = None
    window_view: Optional[str] = None
    nearby_objects: List[Dict[str, Any]] = field(default_factory=list)

    # — Инфраструктура —
    transport_nearby: Dict[str, int] = field(default_factory=dict)

    # — Контакты —
    contact_phone: Optional[str] = None

    # — Медиа —
    photos: List[str] = field(default_factory=list)
    videos: List[str] = field(default_factory=list)

    # — Прочее —
    special_features: List[str] = field(default_factory=list)
    seller_type: Optional[str] = None
    listing_status: Optional[str] = None
    extra_attributes: Dict[str, Any] = field(default_factory=dict)

    # ────────────────────────────────────────────────
    #  SERIALISATION / REPRESENTATION
    # ────────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self):                          # pragma: no cover
        return "\n".join(f"{k}: {v}" for k, v in self.to_dict().items())

    def __repr__(self):                         # pragma: no cover
        return f"<RealEstate id={self.id or 'N/A'} address={self.address or 'N/A'}>"

    # ────────────────────────────────────────────────
    #  ADDRESS PARSING & GEOCODING
    # ────────────────────────────────────────────────
    _GEOLOCATOR: ClassVar[Optional[Nominatim]] = None

    @classmethod
    def _get_geolocator(cls) -> Nominatim:
        if cls._GEOLOCATOR is None:
            cls._GEOLOCATOR = Nominatim(user_agent="real_estate_geocoder", timeout=10)
        return cls._GEOLOCATOR

    # -------- helpers -------------------------------------------------
    @staticmethod
    def _normalize_address(addr: str) -> str:
        """Убирает 'р-н', 'м.', 'метро', раскрывает распространённые сокращения."""
        addr = re.split(r"\s+м\.|\s+метро|\s+р-?н|\s+район|\s+•|\(", addr, 1)[0]

        reps = {
            r"\bул\.": r"улица",
            r"\bпер\.": r"переулок",
            r"\bпросп\.?": r"проспект",
            r"\bпр-т": r"проспект",
            r"\bнаб\.": r"набережная",
            r"\bш\.": r"шоссе",
            r"\bпл\.": r"площадь",
        }
        for pat, repl in reps.items():
            addr = re.sub(pat, repl, addr, flags=re.IGNORECASE)

        addr = re.sub(r"\s+", " ", addr)
        addr = re.sub(r",\s*,", ",", addr)
        return addr.strip(" ,")

    @staticmethod
    @lru_cache(maxsize=256)
    def _make_query_variants(addr: str) -> List[str]:
        """Формирует список адресных вариантов для Nominatim."""
        clean = RealEstate._normalize_address(addr)
        parts = [p.strip() for p in clean.split(",") if p.strip()]

        if len(parts) >= 3:
            street_house = ", ".join(parts[:2])     # улица, дом
            city = parts[2]
            variants = [
                clean,
                f"{street_house}, {city}",
                street_house,
                addr,                               # оригинал
            ]
        else:
            variants = [clean, addr]

        seen, uniq = set(), []
        for v in variants:
            if v not in seen:
                uniq.append(v)
                seen.add(v)
        return uniq

    # -------- основной метод ------------------------------------------
    def geocode_address(self, force: bool = False) -> Tuple[float, float]:
        if self.coords and not force:
            return self.coords
        if not self.address:
            raise ValueError("Поле address пусто — геокодирование невозможно")

        geo = self._get_geolocator()
        last_error: Optional[Exception] = None

        for query in self._make_query_variants(self.address):
            try:
                loc = geo.geocode(query, language="ru", exactly_one=True)
                if loc:
                    self.coords = (loc.latitude, loc.longitude)
                    return self.coords
            except (GeocoderServiceError, GeocoderUnavailable) as exc:
                last_error = exc
                break   # нет смысла продолжать, сервис недоступен

        if last_error:
            raise ConnectionError(f"Сервис геокодирования недоступен: {last_error}")
        raise ValueError(f"Не удалось получить координаты для адреса: {self.address}")

    # ────────────────────────────────────────────────
    #  OSM NEARBY OBJECTS
    # ────────────────────────────────────────────────
    def fetch_nearby_objects(self, radius: int = 100) -> List[Dict[str, Any]]:
        if not self.coords:
            raise ValueError("Координаты объекта отсутствуют")

        lat, lon = self.coords
        api = overpy.Overpass()

        query = f"""
        (
          node(around:{radius},{lat},{lon});
          way(around:{radius},{lat},{lon});
          relation(around:{radius},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """

        try:
            result = api.query(query)
        except overpy.exception.OverpassTooManyRequests:
            raise ConnectionError("Слишком много запросов к Overpass API. Попробуйте позже.")
        except Exception as exc:
            raise RuntimeError(f"Ошибка запроса Overpass API: {exc}")

        raw: List[Dict[str, Any]] = []

        for node in result.nodes:
            if node.tags:
                raw.append({"type": "node", "id": node.id, "lat": node.lat,
                            "lon": node.lon, "tags": node.tags})
        for way in result.ways:
            if way.tags and way.nodes:
                nodes = [(n.lat, n.lon) for n in way.nodes]
                raw.append({"type": "way", "id": way.id, "nodes": nodes, "tags": way.tags})
        for rel in result.relations:
            if rel.tags:
                raw.append({"type": "relation", "id": rel.id, "tags": rel.tags})

        self.nearby_objects = raw

        # группируем по ключевому тегу
        from collections import defaultdict

        def primary_tag(tags: Dict[str, str]) -> str:
            for key in ("amenity", "shop", "building", "highway",
                        "leisure", "tourism", "public_transport", "office"):
                if key in tags:
                    return f"{key}={tags[key]}"
            return "other"

        grouped = defaultdict(list)
        for obj in raw:
            grouped[primary_tag(obj["tags"])].append(obj)

        self.nearby_grouped_objects = dict(grouped)
        return raw

    # ────────────────────────────────────────────────
    #  ОЦЕНКА ЛОКАЦИИ / ЦЕНЫ
    # ────────────────────────────────────────────────
    def evaluate(
        self,
        stats: Dict[str, Tuple[float, float]],
        *,
        venue_type: str = "standard",
    ) -> Dict[str, float]:
        z = lambda raw, m: (raw - stats[m][0]) / stats[m][1] if stats[m][1] else 0

        raw_price = (self.price / self.total_area) if (self.price and self.total_area) else 0
        raw_transport = self.transport_nearby.get("stops", 0) + sum(
            len(v) for k, v in self.nearby_grouped_objects.items() if k.startswith("public_transport")
        )
        raw_competition = sum(
            len(v) for k, v in self.nearby_grouped_objects.items()
            if any(k.startswith(t) for t in ("amenity=restaurant", "amenity=cafe", "amenity=bar"))
        )
        raw_infra = sum(
            len(v) for k, v in self.nearby_grouped_objects.items()
            if any(k.startswith(t) for t in ("shop=", "office=", "leisure=", "amenity=", "tourism="))
        )
        raw_demo = self.extra_attributes.get("population_density", 0)
        raw_income = self.extra_attributes.get("avg_income", 0)

        price_z, transport_z = -z(raw_price, "price_psqm"), z(raw_transport, "transport")
        comp_z = -z(raw_competition, "competition")
        infra_z = z(raw_infra, "infrastructure")
        demo_z, income_z = z(raw_demo, "population_density"), z(raw_income, "avg_income")

        weights = {
            "fast_food":  dict(top=dict(price=.5, location=.5),
                               sub=dict(transport=.5, competition=.2, infrastructure=.2, demo=.1)),
            "premium":    dict(top=dict(price=.3, location=.7),
                               sub=dict(transport=.2, competition=.3, infrastructure=.3, demo=.2)),
            "casual":     dict(top=dict(price=.4, location=.6),
                               sub=dict(transport=.3, competition=.3, infrastructure=.3, demo=.1)),
            "standard":   dict(top=dict(price=.4, location=.6),
                               sub=dict(transport=.4, competition=.3, infrastructure=.3, demo=.0)),
        }[venue_type]

        loc_z = (
            transport_z * weights["sub"]["transport"]
            + comp_z   * weights["sub"]["competition"]
            + infra_z  * weights["sub"]["infrastructure"]
            + demo_z   * weights["sub"]["demo"]
        )
        composite_z = price_z * weights["top"]["price"] + loc_z * weights["top"]["location"]
        to_score = lambda x: 50 + 10 * x

        return dict(
            price_score=to_score(price_z),
            transport_score=to_score(transport_z),
            competition_score=to_score(comp_z),
            infrastructure_score=to_score(infra_z),
            demographic_score=to_score(demo_z),
            location_score=to_score(loc_z),
            composite_score=to_score(composite_z),
            income_score=to_score(income_z),
        )

    # ────────────────────────────────────────────────
    #  AGGREGATED STATS  (class-level helper)
    # ────────────────────────────────────────────────
    @staticmethod
    def compute_stats(
        estates: List["RealEstate"],
        *,
        radius: int = 100,
    ) -> Dict[str, Tuple[float, float]]:
        for est in estates:
            if not getattr(est, "nearby_grouped_objects", None):
                try:
                    if not est.coords:
                        est.geocode_address()
                    est.fetch_nearby_objects(radius=radius)
                except Exception as exc:
                    est.nearby_grouped_objects = {}
                    print(f"[compute_stats] skip fetch_nearby for {est.id}: {exc}")

        price = [est.price / est.total_area for est in estates
                 if est.price and est.total_area]

        transport = [
            est.transport_nearby.get("stops", 0) + sum(
                len(v) for k, v in est.nearby_grouped_objects.items()
                if k.startswith("public_transport")
            ) for est in estates
        ]

        competition = [
            sum(
                len(v) for k, v in est.nearby_grouped_objects.items()
                if any(k.startswith(t) for t in ("amenity=restaurant", "amenity=cafe", "amenity=bar"))
            )
            for est in estates
        ]

        infrastructure = [
            sum(
                len(v) for k, v in est.nearby_grouped_objects.items()
                if any(k.startswith(t) for t in ("shop=", "office=", "leisure=", "amenity=", "tourism="))
            )
            for est in estates
        ]

        population = [est.extra_attributes.get("population_density", 0) for est in estates]
        income     = [est.extra_attributes.get("avg_income", 0)          for est in estates]

        def safe(arr: List[float]) -> Tuple[float, float]:
            μ = mean(arr) if arr else 0.0
            σ = stdev(arr) if len(arr) > 1 else 1.0
            return μ, σ

        return dict(
            price_psqm=safe(price),
            transport=safe(transport),
            competition=safe(competition),
            infrastructure=safe(infrastructure),
            population_density=safe(population),
            avg_income=safe(income),
        )
