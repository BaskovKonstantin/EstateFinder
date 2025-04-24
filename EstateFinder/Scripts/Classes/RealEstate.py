from __future__ import annotations

import overpy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, ClassVar, Union

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError, GeocoderUnavailable


# ────────────────────────────────────────────────────────────────────────────────
#  EVENTS
# ────────────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class PriceEvent:
    """Запись об изменении цены объекта."""
    date: datetime
    price: float                   # Цена в базовой валюте
    diff: Optional[float] = None   # Дельта относительно предыдущего значения

    def __repr__(self) -> str:                # pragma: no cover
        diff = f", diff={self.diff}" if self.diff is not None else ""
        return f"PriceEvent(date={self.date:%Y-%m-%d}, price={self.price}{diff})"


# ────────────────────────────────────────────────────────────────────────────────
#  CORE MODEL
# ────────────────────────────────────────────────────────────────────────────────
@dataclass()
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
    nearby_objects: List[Dict[str, Any]] = field(default_factory=list)  # новое поле

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

    # ────────────────────────────────────────────────────────
    #  SERIALISATION / REPRESENTATION
    # ────────────────────────────────────────────────────────
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __str__(self):                       # pragma: no cover
        return "\n".join(f"{k}: {v}" for k, v in self.to_dict().items())

    def __repr__(self):                      # pragma: no cover
        return f"<RealEstate id={self.id or 'N/A'} address={self.address or 'N/A'}>"

    # ────────────────────────────────────────────────────────
    #  ADDRESS PARSING & GEOCODING
    # ────────────────────────────────────────────────────────
    _GEOLOCATOR: ClassVar[Optional[Nominatim]] = None

    @staticmethod
    def _parse_address(raw: str) -> Dict[str, str]:
        """
        Разбирает строку адреса компонентов, разделенных запятыми:
          - country      — всегда "Россия"
          - state, county, amenity, postalcode — пустые
          - city         — первое слово первой части
          - street       — часть после третьей запятой
          - house_number — часть после четвёртой запятой
        """
        parts = [p.strip() for p in raw.split(',')]
        city = parts[0].split()[0] if parts and parts[0] else ''
        street = parts[3] if len(parts) > 3 else ''
        house_number = parts[4] if len(parts) > 4 else ''

        return {
            'country': 'Россия',
            'state': '',
            'county': '',
            'city': city,
            'street': street,
            'house_number': house_number,
            'amenity': '',
            'postalcode': ''
        }

    @classmethod
    def _get_geolocator(cls) -> Nominatim:
        if cls._GEOLOCATOR is None:
            cls._GEOLOCATOR = Nominatim(user_agent='real_estate_geocoder', timeout=10)
        return cls._GEOLOCATOR

    def geocode_address(self, force: bool = False) -> Tuple[float, float]:
        """
        Выполняет геокодирование через Nominatim.
        Если coords уже установлены и force=False, возвращает их.
        Иначе парсит address и запрашивает координаты.
        """
        if self.coords and not force:
            return self.coords
        if not self.address:
            raise ValueError('Поле address пусто — геокодирование невозможно')

        params = self._parse_address(self.address)
        geolocator = self._get_geolocator()

        try:
            location = geolocator.geocode(params, language='ru', exactly_one=True)
            if not location:
                # fallback на строковый формат
                formatted = ', '.join(v for v in params.values() if v)
                location = geolocator.geocode(formatted, language='ru', exactly_one=True)
        except (GeocoderServiceError, GeocoderUnavailable) as e:
            raise ConnectionError(f'Сервис геокодирования недоступен: {e}')

        if not location:
            raise ValueError(f'Не удалось получить координаты для адреса: {self.address}')

        self.coords = (location.latitude, location.longitude)
        return self.coords

    def fetch_nearby_objects(self, radius: int = 100) -> List[Dict[str, Any]]:
        """
        Загружает объекты OSM в радиусе `radius` метров от текущих координат.
        Сохраняет их в полях `nearby_objects` и `nearby_grouped_objects`, и возвращает список объектов.
        """
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
        except Exception as e:
            raise RuntimeError(f"Ошибка запроса Overpass API: {e}")

        raw_objects = []

        for node in result.nodes:
            if not node.tags:
                continue
            raw_objects.append({
                "type": "node",
                "id": node.id,
                "lat": node.lat,
                "lon": node.lon,
                "tags": node.tags
            })

        for way in result.ways:
            try:
                nodes = [(n.lat, n.lon) for n in way.nodes]
            except AttributeError:
                nodes = []
            if not way.tags or not nodes:
                continue
            raw_objects.append({
                "type": "way",
                "id": way.id,
                "nodes": nodes,
                "tags": way.tags
            })

        for rel in result.relations:
            if not rel.tags:
                continue
            raw_objects.append({
                "type": "relation",
                "id": rel.id,
                "tags": rel.tags
            })

        self.nearby_objects = raw_objects

        # ─────────────────────────────────────────────────────
        # ГРУППИРОВКА ПО ОСНОВНОМУ ТЕГУ
        # ─────────────────────────────────────────────────────
        from collections import defaultdict

        def extract_primary_tag(tags: Dict[str, str]) -> str:
            # Порядок приоритетов
            priority_keys = ["amenity", "shop", "building", "highway", "leisure", "tourism", "public_transport",
                             "office"]
            for key in priority_keys:
                if key in tags:
                    return f"{key}={tags[key]}"
            return "other"

        grouped = defaultdict(list)
        for obj in raw_objects:
            tag_label = extract_primary_tag(obj["tags"])
            grouped[tag_label].append(obj)

        self.nearby_grouped_objects = dict(grouped)
        return raw_objects

