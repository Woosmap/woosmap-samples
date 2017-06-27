import json
import requests

WOOSMAP_JSON_FILE = 'foodmarkets.json'
WOOSMAP_PRIVATE_API_KEY = '23713926-1af5-4321-ba54-xxxxxxxxxxx'


class Woosmap:
    """A wrapper around the Woosmap Data API."""

    WOOSMAP_API_HOSTNAME = 'api.woosmap.com'

    def __init__(self):
        self.session = requests.Session()

    def delete(self):
        self.session.delete('https://{hostname}/stores/'.format(hostname=self.WOOSMAP_API_HOSTNAME),
                            params={'private_key': WOOSMAP_PRIVATE_API_KEY})

    def post(self, payload):
        return self.session.post('https://{hostname}/stores/'.format(hostname=self.WOOSMAP_API_HOSTNAME),
                                 params={'private_key': WOOSMAP_PRIVATE_API_KEY},
                                 json={'stores': payload})

    def end(self):
        self.session.close()


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


def main():
    with open(WOOSMAP_JSON_FILE, 'rb') as f:
        assets = json.loads(f.read())
        try:
            woosmap_api_helper = Woosmap()
            # /!\ deleting existing assets before posting new ones /!\
            woosmap_api_helper.delete()
            import_assets(assets["stores"], woosmap_api_helper)
            woosmap_api_helper.end()
        except Exception as error:
            print("Unable to import file {0} : {1}".format(WOOSMAP_JSON_FILE, error))


if __name__ == '__main__':
    main()
