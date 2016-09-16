import json, pprint
import requests

origin_public_key = ''
private_key = ''
allowed_referer = 'http://localhost/'
api_server_host = 'api.woosmap.com'
geojson_features = []


class InvalidGeometry(Exception):
    pass


def get_geometry(store):
    return {
        'lat': store['geometry']['coordinates'][1],
        'lng': store['geometry']['coordinates'][0]
    }


def transform_geojson_woosmap(stores_geojson):
    stores = []
    for feature in stores_geojson:
        feature["properties"]["location"] = get_geometry(feature)
        feature["properties"]["storeId"] = feature['properties']['store_id']
        feature["properties"]["openingHours"] = feature["properties"]["opening_hours"]
        stores.append(feature["properties"])

    return stores


def get_all_stores(page=1):
    params = dict(key=origin_public_key, page=page)
    ref_header = {'referer': allowed_referer}

    response = session.get(url='http://{api_server_host}/stores'.format(
        api_server_host=api_server_host),
        params=params,
        headers=ref_header)

    temp_json = response.json()
    for feature in temp_json['features']:
        geojson_features.append(feature)

    if temp_json['pagination']['page'] != temp_json['pagination']['pageCount']:
        get_all_stores(temp_json['pagination']['page'] + 1)

    return geojson_features


def import_location(locations):
    print('Importing locations (%d) ...' % len(locations))
    response = session.post(
        'http://{api_server_host}/stores/replace'.format(
            api_server_host=api_server_host),
        params={'private_key': private_key},
        json={'stores': locations})

    print('Import time:', response.elapsed.total_seconds())
    if response.status_code >= 400:
        print('Import Failed')
        print(response.text)
        return False

    return True


if __name__ == '__main__':
    session = requests.Session()
    stores_geojson = get_all_stores()
    try:
        stores_woosmap = transform_geojson_woosmap(stores_geojson)
        import_location(stores_woosmap)
    except BaseException:
        pass
