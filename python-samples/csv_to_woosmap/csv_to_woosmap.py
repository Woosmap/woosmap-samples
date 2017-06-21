import csv
import json
import os
import time
import requests
from hashlib import sha1

YOUR_INPUT_CSV_FILE = 'foodmarkets.csv'
WOOSMAP_PRIVATE_API_KEY = '23713926-1af5-4321-ba54-032966f6e95d'
WOOSMAP_API_HOSTNAME = 'api.woosmap.com'
BATCH_SIZE = 5


class MyCSVDialect(csv.Dialect):
    delimiter = ','
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\n'
    quoting = csv.QUOTE_ALL


class WoosmapAPIHelper:
    def __init__(self):
        self.session = requests.Session()

    def delete(self):
        self.session.delete('https://{hostname}/stores/'.format(hostname=WOOSMAP_API_HOSTNAME),
                            params={'private_key': WOOSMAP_PRIVATE_API_KEY})

    def post(self, payload):
        return self.session.post('https://{hostname}/stores/'.format(hostname=WOOSMAP_API_HOSTNAME),
                                 params={'private_key': WOOSMAP_PRIVATE_API_KEY},
                                 json={'stores': payload})

    def end(self):
        self.session.close()


def get_name(asset):
    name = asset.get('Name', '')
    if name:
        return name
    else:
        raise ValueError('Unable to get the Name')


def generate_id(asset):
    asset_id = sha1(get_name(asset)).hexdigest()
    return asset_id


def get_contact(asset):
    return {
        'website': asset.get('Website', ''),
        'phone': asset.get('Contact Phone', ''),
        'email': asset.get('Contact Email', '')
    }


def get_geometry(asset):
    latitude = asset.get('Latitude', None)
    longitude = asset.get('Longitude', None)
    if latitude is not None and longitude is not None:
        return {
            'lat': float(latitude),
            'lng': float(longitude)
        }
    else:
        raise ValueError('Unable to get the location')


def get_address(asset):
    return {
        'lines': [asset.get('Address Line', '')],
        'city': asset.get('City', ''),
        'zipcode': asset.get('Zipcode', '')
    }


def convert_to_woosmap(asset):
    converted_asset = {}
    try:
        converted_asset.update({
            'storeId': generate_id(asset),
            'name': get_name(asset),
            'address': get_address(asset),
            'contact': get_contact(asset),
            'location': get_geometry(asset)
        })
    except ValueError as ve:
        print('ValueError Raised {0} for Asset {1}'.format(ve, json.dumps(asset, indent=2)))

    return converted_asset


def import_assets(assets_data, woosmap_api_helper):
    try:
        print('Batch import {count} Assets...'.format(count=len(assets_data)))
        response = woosmap_api_helper.post(assets_data)
        if response.status_code >= 400:
            response.raise_for_status()

    except requests.exceptions.HTTPError as http_exception:
        if http_exception.response.status_code >= 400:
            print('Woosmap API Import Error: {0}'.format(http_exception.response.text))
        else:
            print('Error requesting the API: {0}'.format(http_exception))
        return False
    except Exception as exception:
        print('Failed importing Assets! {0}'.format(exception))
        return False

    print('Successfully imported in {0} seconds'.format(response.elapsed.total_seconds()))
    return True


def batch(assets_data, n=1):
    l = len(assets_data)
    for ndx in range(0, l, n):
        yield assets_data[ndx:min(ndx + n, l)]


def main():
    start = time.time()
    print('Start parsing and importing your data...')
    with open(file_path, 'r') as csv_file:
        try:
            reader = csv.DictReader(csv_file, dialect=MyCSVDialect())
            woosmap_assets = []
            for asset in reader:
                converted_asset = convert_to_woosmap(asset)
                if converted_asset:
                    woosmap_assets.append(converted_asset)

            print('{0} Assets converted from source file'.format(len(woosmap_assets)))

            woosmap_api_helper = WoosmapAPIHelper()
            # /!\ deleting existing assets before posting new ones /!\
            woosmap_api_helper.delete()

            count_imported_assets = 0
            for chunk in batch(woosmap_assets, BATCH_SIZE):
                imported_success = import_assets(chunk, woosmap_api_helper)
                if imported_success:
                    count_imported_assets += len(chunk)

            woosmap_api_helper.end()
            print("{0} Assets successfully imported".format(count_imported_assets))

        except csv.Error as csv_error:
            print('Error in CSV file found: {0}'.format(csv_error))
        except Exception as exception:
            print("Script Failed! {0}".format(exception))
        finally:
            end = time.time()
            print('...Script ended in {0} seconds'.format(end - start))


if __name__ == '__main__':
    file_path = os.path.join(os.getcwd(), YOUR_INPUT_CSV_FILE)
    if os.path.exists(file_path):
        main()
    else:
        print('File not found: {0} '.format(file_path))
