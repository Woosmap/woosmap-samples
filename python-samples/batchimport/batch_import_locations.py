import csv
from _csv import QUOTE_ALL
from csv import Dialect
import requests

endpoint_csv = 'bar_and_pub_in_paris.csv'
private_key = '' #your woosmap_api_private_key here
endpoint_api = 'http://api.woosmap.com/stores'
stores_batch_size = 100
update_location = False


class osm_dialect(Dialect):
    delimiter = ','
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\n'
    quoting = QUOTE_ALL


csv.register_dialect('osm', osm_dialect)


class InvalidGeometry(Exception):
    pass


def get_geometry(store):
    return {
        'lat': store['Latitude'],
        'lng': store['Longitude']
    }


def osm2woosmap(store):
    geometry = get_geometry(store)
    return {
        'storeId': store['osmid'],
        'name': store['name'],
        'location': geometry,
    }


def import_batch(batch, use_put=False):
    print('--> Importing batch (%d)' % len(batch))
    if use_put:
        response = session.put(endpoint_api,
                               params={'private_key': private_key},
                               json={'stores': batch})
    else:
        response = session.post(endpoint_api,
                                params={'private_key': private_key},
                                json={'stores': batch})

    print('<-- Total time:', response.elapsed.total_seconds())
    if response.status_code >= 400:
        print('Failed batch')
        print(response.text)
        return False

    return True


if __name__ == '__main__':
    with open(endpoint_csv, 'r') as f:
        reader = csv.DictReader(f, dialect="osm")

        data = []
        for row in reader:
            data.append(row)

        failed = []
        session = requests.Session()
        if not update_location:
            response = session.delete(endpoint_api, params={'private_key': private_key})

            if response.status_code >= 400:
                print(response.text)
                exit(-1)

        batch = []
        batch_size = stores_batch_size
        id = 0
        for location in data:
            id += 1
            try:
                woosmap_location = osm2woosmap(location)

                if len(batch) == batch_size:
                    batch_result = import_batch(batch, use_put=update_location)
                    batch = []
                else:
                    batch.append(woosmap_location)

            except InvalidGeometry:
                pass

        if batch:
            batch_result = import_batch(batch, use_put=update_location)
            batch = []
