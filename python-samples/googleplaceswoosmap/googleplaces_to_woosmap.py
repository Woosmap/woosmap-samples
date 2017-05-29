# -*- coding: utf-8 -*-
import sys
import codecs
import json
import time

from googleplaces import GooglePlaces, types, GooglePlacesAttributeError, GooglePlacesError
from tzwhere import tzwhere

sys.stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stderr = codecs.getwriter('utf8')(sys.stderr)

YOUR_API_KEY = "AIzaSyDRcaVMH1F_XXXXXX-kqnyeaNhBA3iQQ"  # YOUR GOOGLE_API_KEY
KEYWORD_SEARCH = ''  # Your Search
COUNTRY = "France"
OUTPUT_JSON = "_".join(KEYWORD_SEARCH.split()).lower() + "_" + COUNTRY.lower() + "_google_places_data.json"
GRID_CITY_PATH = "grid_city.json"
EXACT_MATCH = False
RETRY_COUNTER_CONST = 3  # for get_timezone due to some failure

tz = tzwhere.tzwhere()
stores = []
placesId = []

google_places = GooglePlaces(YOUR_API_KEY)


def get_location(places_location):
    return {
        'lat': float(places_location['geometry']['location']['lat']),
        'lng': float(places_location['geometry']['location']['lng'])
    }


def get_id(places_location):
    return places_location.get('place_id').translate({ord(c): None for c in '-_!@#$'})


def get_timezone(lat, long, retry_counter=0):
    timezone = tz.tzNameAt(lat, long, True)
    if timezone is None and retry_counter < RETRY_COUNTER_CONST:
        time.sleep(0.5)
        return get_timezone(lat, long, retry_counter + 1)

    return timezone


# TODO : Update for multi opening and closing in a day
def get_hours(places_location):
    weekdays = [1, 2, 3, 4, 5, 6, 0]
    day_index = 1
    usual = {}
    day_hours = places_location.get('opening_hours', {})

    try:
        timezone = get_timezone(float(places_location['geometry']['location']['lat']),
                                float(places_location['geometry']['location']['lng']))
        for day in weekdays:
            hours = []
            start_hour = ""
            end_hour = ""
            if len(day_hours['periods']) == 1:
                hours.append({"all-day": True})
            else:
                for period in day_hours['periods']:
                    if period['open']['day'] and period['open']['day'] == day:
                        if period['open']['time'] == "0000":
                            start_hour = "23:59"
                        else:
                            start_hour = period['open']['time'][:2] + ":" + period['open']['time'][-2:]
                        if period['close']:
                            if period['close']['time'] == "0000":
                                end_hour = "23:59"
                            else:
                                end_hour = period['close']['time'][:2] + ":" + period['close']['time'][-2:]
                            break
                if start_hour and end_hour:
                    hours.append({'start': start_hour, 'end': end_hour})

            usual[day_index] = hours
            day_index += 1

    except Exception as error:
        return {}

    return {
        'timezone': timezone,
        'usual': usual
    }


def get_name(places_location):
    print places_location.get('name')
    return places_location.get('name')


def get_contact(places_location):
    return {
        'website': places_location.get('url'),
        'phone': places_location.get('formatted_phone_number')
    }


def get_address(places_location):
    return {
        'lines': [places_location.get('formatted_address')]
    }


def export_input_json(input_json):
    data_places = {"stores": input_json}
    with codecs.open(OUTPUT_JSON, 'w', encoding='utf8') as outfile:
        json.dump(data_places, outfile, indent=2, ensure_ascii=False)


def google2woosmap(places_location):
    place_id = get_id(places_location)
    geometry = get_location(places_location)
    address = get_address(places_location)
    contact = get_contact(places_location)
    name = get_name(places_location)
    hours = get_hours(places_location)
    return {
        'storeId': place_id,
        'name': name,
        'address': address,
        'contact': contact,
        'location': geometry,
        'openingHours': hours
    }


if __name__ == '__main__':
    with codecs.open(GRID_CITY_PATH, 'rb') as grid_city_file:
        cities = json.loads(grid_city_file.read())

    for city_location in cities[COUNTRY]:
        print city_location
        time.sleep(1)
        try:
            query_result = google_places.radar_search(
                location=city_location, keyword=KEYWORD_SEARCH,
                radius=500000)

            for place in query_result.places:
                if place.place_id not in placesId:
                    placesId.append(place.place_id)
                    # The following method has to make a further API call.
                    place.get_details()
                    if EXACT_MATCH and KEYWORD_SEARCH in place.name:
                        stores.append(google2woosmap(place.details))
                    elif not EXACT_MATCH:
                        stores.append(google2woosmap(place.details))

            # Are there any additional pages of results?
            if query_result.has_next_page_token:
                query_result_next_page = google_places.nearby_search(
                    pagetoken=query_result.next_page_token)

        except (GooglePlacesError, GooglePlacesAttributeError) as error_detail:
            print error_detail
            pass

        except Exception:
            time.sleep(5)
            print "Exception  for : " + city_location
            pass

    export_input_json(stores)
    print "{} google places extracted".format(len(placesId))
