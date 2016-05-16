import csv
from _csv import QUOTE_ALL
from csv import Dialect
import requests

endpoint_csv = 'france_museum_geocoded.csv'
private_key = '' #your private key here
endpoint_api = 'http://api.woosmap.com/stores'
stores_batch_size = 100
update_location = False


class InvalidGeometry(Exception):
    pass


def get_geometry(store):
    return {
        'lat': store['latitude'],
        'lng': store['longitude']
    }


def get_contact(store):
    return {
        'website': store['SITWEB']
    }


def get_address(store):
    return {
        'lines': [store['ADR']],
        'city': store['VILLE'],
        'zipcode': store['CP'],
    }


def datagov2woosmap(store, id):
    geometry = get_geometry(store)
    address = get_address(store)
    contact = get_contact(store)
    return {
        'storeId': id,
        'name': store['NOM DU MUSEE'],
        'address': address,
        'contact': contact,
        'location': geometry
    }


class data_gov_dialect(Dialect):
    delimiter = ','
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\n'
    quoting = QUOTE_ALL


csv.register_dialect('dg', data_gov_dialect)


def import_batch(batch, use_put=False):
    print('--> Importing batch (%d) locations' % len(batch))
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
        reader = csv.DictReader(f, dialect="dg")

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
        for location in reader:
            id += 1
            try:
                woosmap_location = datagov2woosmap(location, "ID" + str(id))

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
