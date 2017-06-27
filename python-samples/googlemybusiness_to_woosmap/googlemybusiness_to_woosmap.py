import httplib2
import json
import os
import requests

from apiclient import discovery
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client import tools

from timezonefinder import TimezoneFinder

tf = TimezoneFinder()

WOOSMAP_PRIVATE_API_KEY = 'eafb8805-3743-4cb9-abff-xxxxxxxxxxxx'

GOOGLE_ACCOUNT_NAME = "accounts/123456789101112131415"  # The Account Manager
GOOGLE_CREDENTIALS_PATH = "client_secret_xxxxxxx-xxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com.json"


class GoogleMyBusiness(object):
    """A wrapper around the Google My Business API."""

    API_NAME = 'mybusiness'
    API_VERSION = 'v3'
    DISCOVERY_URI = 'https://developers.google.com/my-business/samples/{api}_google_rest_{apiVersion}.json'
    SCOPE = "https://www.googleapis.com/auth/plus.business.manage"
    REDIRECT_URI = 'http://localshot:8080'

    def __init__(self, credentials_path, account_name=''):
        self.credentials_path = credentials_path
        self.account_name = account_name
        self.credentials = self.get_credentials()
        self.http = self.credentials.authorize(httplib2.Http())
        if self.credentials is not None and self.credentials.access_token_expired:
            self.credentials.refresh(self.http)

        self.service = self.build_service()
        if not self.account_name:
            # If GOOGLE_ACCOUNT_NAME constant is not set, we pick the first in account listing
            self.account_name = self.list_accounts()['accounts'][0]['name']

    def build_service(self):
        return discovery.build(self.API_NAME, self.API_VERSION, http=self.http,
                               discoveryServiceUrl=self.DISCOVERY_URI)

    def get_credentials(self):
        storage_path = '.' + os.path.splitext(os.path.basename(__file__))[0] + '.credentials'
        storage = Storage(storage_path)

        credentials = storage.get() if os.path.exists(storage_path) else None

        if credentials is None or credentials.invalid:
            flow = flow_from_clientsecrets(self.credentials_path,
                                           scope=self.SCOPE,
                                           redirect_uri=self.REDIRECT_URI)

            flow.params['access_type'] = 'offline'
            flow.params['approval_prompt'] = 'force'
            credentials = tools.run_flow(flow, storage)

        return credentials

    def list_accounts(self):
        return self.service.accounts().list().execute()

    def list_locations(self):
        return self.service.accounts().locations().list(name=self.account_name).execute()


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
    return asset.get('locationName')


def get_id(asset):
    return asset.get('name').rsplit('/', 1)[1]


def get_contact(asset):
    return {
        'website': asset.get('websiteUrl', ''),
        'phone': asset.get('primaryPhone', '')
    }


def get_tags(asset):
    return asset.get('labels', [])


def get_primary_category(asset):
    primary_type = []
    primary_category = asset.get('primaryCategory', {})
    if primary_category:
        primary_type.append(primary_category.get('name', ''))

    return primary_type


def get_additional_categories(asset):
    additional_types = []
    additional_categories = asset.get('additionalCategories', [])
    if additional_categories:
        for category in additional_categories:
            additional_types.append(category.get('name', ''))

    return additional_types


def get_types(asset):
    types = []
    types.extend(get_primary_category(asset))
    types.extend(get_additional_categories(asset))
    return types


def get_user_properties(asset):
    # return all other useful attributes to store in "userProperties" property
    return {
        'photos': asset.get('photos', {}),
        'metadata': asset.get('metadata', {}),
        'storeCode': asset.get('storeCode', ''),
        'languageCode': asset.get('languageCode', ''),
        'attributes': asset.get('attributes', []),
        'serviceArea': asset.get('serviceArea', {}),
        'locationKey': asset.get('locationKey', {}),
        'priceLists': asset.get('priceLists', []),
        'locationState': asset.get('locationState', {}),
        'additionalPhones': asset.get('locationState', []),
        'adWordsLocationExtensions': asset.get('adWordsLocationExtensions', {}),
    }


def get_geometry(asset):
    # latlng can be empty {} if you did'nt moved the pushpin location was created on Google
    # Thus you need to geocode address location to get lat/lng
    latlng = asset.get('latlng', {})
    if latlng:
        return {
            'lat': latlng.get('latitude'),
            'lng': latlng.get('longitude')
        }
    else:
        # TODO: geocode address
        raise ValueError('Unable to get the latlng')


def get_address(asset):
    address = asset.get('address', {})
    if address:
        return {
            'lines': address.get('addressLines', []),
            'city': address.get('locality', ''),
            'zipcode': address.get('postalCode', ''),
            'countryCode': address.get('country', '')
        }
    else:
        raise ValueError('Unable to get the Address')


def find_timezone(asset):
    latlng = get_geometry(asset)
    timezone_name = ''
    try:
        lat = float(latlng['lat'])
        lng = float(latlng['lng'])
        timezone_name = tf.timezone_at(lng=lng, lat=lat)
        if timezone_name is None:
            timezone_name = tf.closest_timezone_at(lng=lng, lat=lat)
        return timezone_name

    except ValueError:
        print('Unable to Get the timezone for {latlng}'.format(latlng=latlng))
        timezone_name = 'Europe/Paris'

    finally:
        return {'timezone': timezone_name}


def get_regular_hours(asset):
    # TODO: manage regular hours that take longer than 24hours (e.g. open monday 9am and close Tuesday 9pm)
    regular_hours = asset.get('regularHours', {})
    periods = regular_hours.get('periods', [])

    usual = {}
    week_days = [{'MONDAY': '1'}, {'TUESDAY': '2'}, {'WEDNESDAY': '3'}, {'THURSDAY': '4'}, {'FRIDAY': '5'},
                 {'SATURDAY': '6'},
                 {'SUNDAY': '7'}]
    if periods:
        for period in periods:
            for day in week_days:
                for key in day:
                    if period['openDay'] == key:
                        usual.setdefault(day[key], []).append({'start': period['openTime'], 'end': period['closeTime']})

    return {'usual': usual}


def get_special_hours(asset):
    # TODO: manage special hours that take longer than 24hours (e.g. open monday 9am and close Tuesday 9pm)
    special_hours = asset.get('specialHours', {})
    periods = special_hours.get('specialHourPeriods', [])

    special = {}
    if periods:
        for period in periods:
            start_date = period.get('startDate', '')
            if start_date:
                key = str(start_date.get('year')) + '-' + str(start_date.get('month')) + '-' + str(
                    start_date.get('day'))
                if period.get('isClosed', False):
                    special.setdefault(key, [])
                else:
                    special.setdefault(key, []).append({'start': period['openTime'], 'end': period['closeTime']})

    return {'special': special}


def get_hours(asset):
    return dict(find_timezone(asset).items() + get_regular_hours(asset).items() + get_special_hours(asset).items())


def convert_mybusiness_to_woosmap(data):
    converted_asset = {}
    try:
        converted_asset.update({
            'storeId': get_id(data),
            'name': get_name(data),
            'address': get_address(data),
            'contact': get_contact(data),
            'location': get_geometry(data),
            'openingHours': get_hours(data),
            'tags': get_tags(data),
            'types': get_types(data),
            'userProperties': get_user_properties(data)
        })
    except ValueError as ve:
        print('ValueError Raised {0} for MyBusiness location {1}'.format(ve, json.dumps(data, indent=2)))

    return converted_asset


def import_assets(assets_data, woosmap_api):
    try:
        print('Batch import {count} Assets to Woosmap...'.format(count=len(assets_data)))
        response = woosmap_api.post(assets_data)
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
    google_my_business = GoogleMyBusiness(GOOGLE_CREDENTIALS_PATH, GOOGLE_ACCOUNT_NAME)
    extracted_my_business = google_my_business.list_locations()
    woosmap_assets = []
    for location in extracted_my_business["locations"]:
        converted_asset = convert_mybusiness_to_woosmap(location)
        if bool(converted_asset):
            woosmap_assets.append(converted_asset)

    woosmap_api = Woosmap()
    woosmap_api.delete()

    for chunk in batch(woosmap_assets):
        import_assets(chunk, woosmap_api)


if __name__ == '__main__':
    main()
