import httplib2
import os
import json
import requests
from hashlib import sha1

from apiclient import discovery
from oauth2client.client import flow_from_clientsecrets
from oauth2client import tools
from oauth2client.file import Storage

GOOGLE_CREDENTIALS_PATH = 'client_secret_xxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com.json'
GOOGLE_SPREADSHEET_ID = '1bRQubfDVmFg53ohzY_SLSJRahf04kDtV2O0Ql28hP7U'
GOOGLE_RANGE_NAME = 'foodmarkets'

WOOSMAP_PRIVATE_API_KEY = 'eafb8805-3743-4cb9-abff-xxxxxxxxxxx'


class GoogleSheets(object):
    """A wrapper around the Google Sheets API."""

    API_NAME = 'sheets'
    API_VERSION = 'v4'
    DISCOVERY_URI = 'https://sheets.googleapis.com/$discovery/rest?version={apiVersion}'
    SCOPES = 'https://www.googleapis.com/auth/spreadsheets.readonly'
    APPLICATION_NAME = 'Google Sheets To Woosmap'
    REDIRECT_URI = 'http://localhost:8080'

    def __init__(self, credentials_path, spreadsheet_id, range_name=''):
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.credentials = self.get_credentials()
        self.http = self.credentials.authorize(httplib2.Http())
        if self.credentials is not None and self.credentials.access_token_expired:
            self.credentials.refresh(self.http)

        self.service = self.build_service()
        self.range_name = range_name if range_name else self.get_first_sheetname()

    def build_service(self):
        return discovery.build(self.API_NAME, self.API_VERSION, http=self.http,
                               discoveryServiceUrl=self.DISCOVERY_URI)

    def get_credentials(self):
        storage_path = '.' + os.path.splitext(os.path.basename(__file__))[0] + '.credentials'
        storage = Storage(storage_path)
        credentials = storage.get() if os.path.exists(storage_path) else None
        if credentials is None or credentials.invalid:
            flow = flow_from_clientsecrets(self.credentials_path, self.SCOPES, redirect_uri=self.REDIRECT_URI)
            flow.user_agent = self.APPLICATION_NAME
            credentials = tools.run_flow(flow, storage)

        return credentials

    def get_values(self):
        return self.service.spreadsheets().values().get(spreadsheetId=self.spreadsheet_id,
                                                        range=self.range_name).execute()

    def get_first_sheetname(self):
        sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        return sheet_metadata.get('sheets', '')[0].get("properties", {}).get("title", "Sheet1")


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


def get_name(asset):
    name = asset.get('Name', '')
    if name:
        return name
    else:
        raise ValueError('Unable to get the Name')


def generate_id(asset):
    asset_id = sha1(get_name(asset).encode('utf-8')).hexdigest()
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
    google_sheets = GoogleSheets(GOOGLE_CREDENTIALS_PATH, GOOGLE_SPREADSHEET_ID)

    sheet_data = google_sheets.get_values().get('values', [])
    header = sheet_data.pop(0)
    assets_as_dict = [dict(zip(header, item)) for item in sheet_data]

    woosmap_assets = []
    for asset in assets_as_dict:
        converted_asset = convert_to_woosmap(asset)
        if bool(converted_asset):
            woosmap_assets.append(converted_asset)

    print('{0} Assets converted from source file'.format(len(woosmap_assets)))

    woosmap_api_helper = Woosmap()
    # /!\ deleting existing assets before posting new ones /!\
    woosmap_api_helper.delete()

    count_imported_assets = 0
    for chunk in batch(woosmap_assets):
        imported_success = import_assets(chunk, woosmap_api_helper)
        if imported_success:
            count_imported_assets += len(chunk)

    woosmap_api_helper.end()


if __name__ == '__main__':
    main()
