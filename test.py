import json
import requests

URL = "http://127.0.0.1:5000/search"

# Передаём все параметры через query string
params = {
    "deal_type": "sale",
    "engine_version": 2,
    "offer_type": "offices",
    "office_type[0]": 4,
    "region": 2,
    "max_pages": 1,
    "radius": 150,
    "limit": 5,
    "venue_type": "standard"
}


resp = requests.get(URL, params=params, timeout=120)
resp.raise_for_status()  # бросит исключение, если код != 200
data = resp.json()

print("Всего объектов:", data["count"])
print(json.dumps(data["estates"][0], indent=2, ensure_ascii=False))
