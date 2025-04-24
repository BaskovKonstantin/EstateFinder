from CianParcer import *

# Пример использования:
# Пример использования:
if __name__ == "__main__":
    with open('pages/rendered_20250417_103712.html', 'r', encoding='utf-8') as f:
        html = f.read()

    offer = parse_cian_offer(html)
    print(offer.address)
    offer.geocode_address()
    objects = offer.fetch_nearby_objects()

    # for obj in objects:
    #     print(obj['type'], obj.get('tags', {}))

    for obj in offer.nearby_grouped_objects:
        print( objects[obj] )