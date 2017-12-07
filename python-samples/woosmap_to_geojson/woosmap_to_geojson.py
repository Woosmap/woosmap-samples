import codecs
import json

import requests

origin_public_key = 'woos-3886aa76-xxxxxxxxxx'
output_file = origin_public_key + '.json'
allowed_referer = 'http://localhost/'
api_server_host = 'api.woosmap.com'
geojson_features = []


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


def export_input_geojson(inputjson):
    with codecs.open(output_file, 'w', encoding='utf8') as outfile:
        woosmap_geojson = {'type': 'FeatureCollection', 'features': inputjson}
        json.dump(woosmap_geojson, outfile, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    session = requests.Session()
    batch = []
    try:
        stores_geojson = get_all_stores()
        export_input_geojson(stores_geojson)

    except BaseException as error:  # bad bad way!
        print('An exception occurred: {}'.format(error))
