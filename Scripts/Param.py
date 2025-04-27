PARAM_SPECS = {
    "deal_type": {
        "type": str,
        "allowed": ["sale", "rent"]  # например, продажа или аренда
    },
    "engine_version": {
        "type": int,
        "allowed": [1, 2]
    },
    "object_type[0]": {
        "type": int,
        "allowed": [1]  # в примере только 1 (квартира)
    },
    "offer_type": {
        "type": str,
        "allowed": ["flat", "house", "commercial","offices"]
    },
    "region": {
        "type": int
        # Допустимые коды регионов задаются на стороне пользователя
    },
    "room1": {"type": int, "min": 1, "max": 10},
    "room2": {"type": int, "min": 1, "max": 10},
    "room3": {"type": int, "min": 1, "max": 10},
    "room4": {"type": int, "min": 1, "max": 10},
    "room5": {"type": int, "min": 1, "max": 10},
    "room6": {"type": int, "min": 1, "max": 10},
    "room7": {"type": int, "min": 1, "max": 10},
    "room9": {"type": int, "min": 1, "max": 10},
    "currency": {
        "type": int,
        "allowed": [1, 2]
    },
    "electronic_trading": {
        "type": int,
        "allowed": [1, 2]
    },
    "flat_share": {
        "type": int,
        "allowed": [1, 2]
    },
    "has_video": {
        "type": int,
        "allowed": [0, 1]
    },
    "house_material[0]": {
        "type": int,
        "allowed": [1, 2, 3, 4]  # допустимые значения материала дома
    },
    "lift_service": {
        "type": int,
        "allowed": [0, 1]
    },
    "loggia": {
        "type": int,
        "allowed": [0, 1]
    },
    "max_house_year": {"type": int, "min": 1000, "max": 2023},
    "maxfloor": {"type": int, "min": 1},
    "maxfloorn": {"type": int, "min": 1},
    "maxkarea": {"type": int, "min": 0},
    "maxlarea": {"type": int, "min": 0},
    "maxprice": {"type": int, "min": 0},
    "maxtarea": {"type": int, "min": 0},
    "min_ceiling_height": {"type": float, "min": 0.0},
    "min_house_year": {"type": int, "min": 1000, "max": 2023},
    "minfloor": {"type": int, "min": 1},
    "minfloorn": {"type": int, "min": 1},
    "minkarea": {"type": int, "min": 0},
    "minlarea": {"type": int, "min": 0},
    "minprice": {"type": int, "min": 0},
    "minsu_r": {"type": int, "min": 0},
    "mintarea": {"type": int, "min": 0},
    "offer_seller_type[0]": {
        "type": int,
        "allowed": [1, 2, 3]
    },
    "only_flat": {
        "type": int,
        "allowed": [0, 1]
    },
    "parking_type[0]": {
        "type": int,
        "allowed": [1, 2, 3]
    },
    "repair[0]": {
        "type": int,
        "allowed": [1, 2, 3]
    },
    "repair[1]": {
        "type": int,
        "allowed": [1, 2, 3]
    },
    "room_type": {
        "type": int,
        "allowed": [1, 2]
    },
    "sost_type[0]": {
        "type": int,
        "allowed": [1, 2]
    }
}
