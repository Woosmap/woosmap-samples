import json, pprint
import requests

origin_public_key = ''
private_key = ''
output_file = 'data.json'
allowed_referer = 'http://localhost/'
api_server_host = 'api.woosmap.com'
geojson_features = []
stores_batch_size = 500


def get_geometry(store):
    return {
        'lat': store['geometry']['coordinates'][1],
        'lng': store['geometry']['coordinates'][0]
    }


def transform_geojson_woosmap(extracted_geojson):
    stores = []
    for feature in extracted_geojson:
        try:
            prop = feature["properties"]
            stores.append({"location": get_geometry(feature),
                           "storeId": prop.get("store_id"),
                           "openingHours": prop.get("opening_hours"),
                           "userProperties": prop.get("user_properties"),
                           "types": prop.get("types"),
                           "address": prop.get("address"),
                           "name": prop.get("name"),
                           "tags": prop.get("tags"),
                           "contact": prop.get("contact")})
        except BaseException as error:
            print('An exception occurred: {}'.format(error))

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


def export_input_json(inputjson):
    with open(output_file, 'w') as outfile:
        json.dump(inputjson, outfile)


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
    batch = []
    try:
        stores_geojson = get_all_stores()
        stores_woosmap = transform_geojson_woosmap(stores_geojson)
        if output_file:
            export_input_json(stores_woosmap)
        if private_key:
            for store in stores_woosmap:
                if len(batch) == stores_batch_size:
                    batch_result = import_location(batch)
                    batch = []
                else:
                    batch.append(store)

            if batch:
                batch_result = import_location(batch)
                batch = []

    except BaseException as error:  # bad bad way!
        print('An exception occurred: {}'.format(error))
