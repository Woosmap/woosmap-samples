import codecs
import time
from hashlib import sha1

import simplejson as json  # useful to deal with Decimal(x.x) potential errors
from googleplaces import GooglePlaces, GooglePlacesAttributeError, GooglePlacesError
from timezonefinder import TimezoneFinder

GOOGLE_API_KEY = 'AIzaSyDRcaVMH1F_H3pIbm1T-XXXXXXXXXXX'
WOOSMAP_OUTPUT_JSON = 'woosmap_output.json'
SEARCH_DATA_PATH = 'search_data.json'

tf = TimezoneFinder()


def get_location(places_location):
    return {
        'lat': float(places_location['geometry']['location']['lat']),
        'lng': float(places_location['geometry']['location']['lng'])
    }


def get_id(places_location):
    return sha1(places_location.get('place_id')).hexdigest()


def find_timezone(places_location):
    latlng = get_location(places_location)
    timezone_name = ''
    try:
        lat = latlng['lat']
        lng = latlng['lng']
        timezone_name = tf.timezone_at(lng=lng, lat=lat)
        if timezone_name is None:
            timezone_name = tf.closest_timezone_at(lng=lng, lat=lat)
        return timezone_name

    except ValueError:
        print('Unable to Get the timezone for {latlng}'.format(latlng=latlng))
        timezone_name = 'Europe/Paris'

    finally:
        return {'timezone': timezone_name}


# TODO : Update for multi opening and closing in a day
def get_regular_hours(places_location):
    weekdays = [1, 2, 3, 4, 5, 6, 0]
    day_index = 1
    usual = {}
    day_hours = places_location.get('opening_hours', {})

    if bool(day_hours):
        try:
            for day in weekdays:
                hours = []
                start_hour = ''
                end_hour = ''
                if len(day_hours['periods']) == 1:
                    hours.append({'all-day': True})
                else:
                    for period in day_hours['periods']:
                        if period['open']['day'] and period['open']['day'] == day:
                            start_hour = period['open']['time'][:2] + ':' + period['open']['time'][-2:]
                            if period['close']:
                                end_hour = period['close']['time'][:2] + ':' + period['close']['time'][-2:]
                                break
                    if start_hour and end_hour:
                        hours.append({'start': start_hour, 'end': end_hour})

                usual[day_index] = hours
                day_index += 1

        except Exception as error:
            raise ValueError('Unable to get the OpeningHours: {0}'.format(error))

    return {'usual': usual}


def get_contact(places_location):
    website = places_location.get('website', '') if places_location.get('website', '') else places_location.get('url')
    return {
        'website': website,
        'phone': places_location.get('formatted_phone_number')
    }


def get_address(places_location):
    return {
        'lines': [places_location.get('formatted_address')]
    }


def get_name(places_location):
    return places_location.get('name')


def get_types(places_location):
    return places_location.get('types', [])


def get_hours(places_location):
    return dict(find_timezone(places_location).items() + get_regular_hours(places_location).items())


def google_places_to_woosmap(places_location):
    converted_asset = {}
    try:
        converted_asset.update({
            'storeId': get_id(places_location),
            'name': get_name(places_location),
            'address': get_address(places_location),
            'contact': get_contact(places_location),
            'location': get_location(places_location),
            'openingHours': get_hours(places_location),
            'types': get_types(places_location)
        })
    except ValueError as ve:
        print('ValueError Raised {0} for Places Location {1}'.format(ve, json.dumps(places_location, indent=2)))

    return converted_asset


def export_to_woosmap_json(input_json):
    data_places = {'stores': input_json}
    with codecs.open(WOOSMAP_OUTPUT_JSON, 'w', encoding='utf8') as outfile:
        json.dump(data_places, outfile, indent=2, ensure_ascii=False)


def main():
    woosmap_converted_asset = []
    with codecs.open(SEARCH_DATA_PATH, 'rb', encoding='utf8') as search_data_file:
        search_data = json.loads(search_data_file.read())
        google_places = GooglePlaces(GOOGLE_API_KEY)
        for place_id in search_data['places_ids']:
            try:
                place = google_places.get_place(place_id)
                converted_asset = google_places_to_woosmap(place.details)
                if bool(converted_asset):
                    print("... {place_name} ...converted to Wosmap OK".format(place_name=place.name.encode('utf-8')))
                    woosmap_converted_asset.append(converted_asset)

            except (GooglePlacesError, GooglePlacesAttributeError) as error_detail:
                print('Google Returned an Error : {0} for Place ID : {1}'.format(error_detail, place_id))
                pass

            except Exception as exception:
                print('Exception Returned {0} for Place ID : {1}'.format(exception, place_id))
                time.sleep(1)
                pass

        export_to_woosmap_json(woosmap_converted_asset)
        print('{0} google places extracted for {1} places_ids found '.format(len(woosmap_converted_asset),
                                                                             len(search_data['places_ids'])))


if __name__ == '__main__':
    main()
