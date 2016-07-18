import json
import requests

endpoint_json = 'foodmarkets.json'
private_key = ''
api_server_host = 'api.woosmap.com'


class InvalidGeometry(Exception):
    pass


def import_location(locations):
    print('Importing locations (%d) ...' % len(locations))
    response = session.post(
        'http://{api_server_host}/stores'.format(
            api_server_host=api_server_host),
        params={'private_key': private_key},
        json={'stores': locations})

    print('...Import time:', response.elapsed.total_seconds())
    if response.status_code >= 400:
        print('Import Failed')
        print(response.text)
        return False

    return True


if __name__ == '__main__':
    with open(endpoint_json, 'rb') as f:
        data = json.loads(f.read())
        failed = []
        session = requests.Session()
        response = session.delete(
            'http://{api_server_host}/stores'.format(
                api_server_host=api_server_host),
            params={'private_key': private_key})

        if response.status_code >= 400:
            print(response.text)
            exit(-1)

        try:
            import_location(data["stores"])

        except InvalidGeometry:
            pass
