# -*- coding: utf-8 -*-
import json
import requests

private_key = ''  # your private key here
endpoint_api = 'http://api.woosmap.com/stores'
files_path = ['add_list_of_file_path_here.json']
stores_batch_size = 100
update_location = False

store_ids = []


class InvalidGeometry(Exception):
    pass


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
    for file in files_path:
        with open(file, 'rb') as f:
            data = json.loads(f.read())

            failed = []
            session = requests.Session()

            batch = []
            batch_size = stores_batch_size
            for store in data["stores"]:
                if store['storeId'] not in store_ids:
                    store_ids.append(store['storeId'])
                    try:
                        if len(batch) == batch_size:
                            batch_result = import_batch(batch, use_put=update_location)
                            batch = []
                        else:
                            batch.append(store)

                    except InvalidGeometry:
                        pass

        if batch:
            batch_result = import_batch(batch, use_put=update_location)
            batch = []
