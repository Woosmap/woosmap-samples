import csv
import os
import requests
from _csv import QUOTE_MINIMAL
from csv import Dialect

# used to set a google geocoding query by merging this value into one string with comma separated
ADDRESS_COLUMNS_NAME = ["name", "AddressLine1", "AddressLine2", "AddressLine3", "City", "Postcode"]

# used to define component restrictions for google geocoding
COMPONENT_RESTRICTIONS_COLUMNS_NAME = {}

# appended columns name to processed data csv
NEW_COLUMNS_NAME = ["Lat", "Long", "Error", "formatted_address", "location_type"]

# delimiter for input csv file
DELIMITER = ","

# Automatically retry X times when GeocoderErrors occur (sometimes the API Service return intermittent failures).
RETRY_COUNTER_CONST = 5

dir = os.path.dirname(__file__)

# path and name for output csv file
INPUT_CSV_FILE = os.path.join(dir, "input1.csv")

# path and name for output csv file
OUTPUT_CSV_FILE = os.path.join(dir, "processed_test.csv")

# Add your Woosmap Private Key here
WOOSMAP_PRIVATE_API_KEY = "XXXX"


# dialect to manage different format of CSV
class CustomDialect(Dialect):
    delimiter = DELIMITER
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\n'
    quoting = QUOTE_MINIMAL


csv.register_dialect('ga', CustomDialect)


class WoosmapLocalities:
    """A wrapper around the Woosmap Localities API."""

    WOOSMAP_API_HOSTNAME = 'api.woosmap.com'

    def __init__(self):
        self.session = requests.Session()

    def get_details(self, public_id):
        return self.session.get(
            'https://{hostname}/localities/details/'.format(hostname=self.WOOSMAP_API_HOSTNAME),
            params={'private_key': WOOSMAP_PRIVATE_API_KEY,
                    'public_id': public_id}).json()

    def autocomplete(self, text_input):
        return self.session.get(
            'https://{hostname}/localities/autocomplete/'.format(hostname=self.WOOSMAP_API_HOSTNAME),
            params={'private_key': WOOSMAP_PRIVATE_API_KEY,
                    'input': text_input,
                    'types': 'address'}).json()

    def end(self):
        self.session.close()


def process_addresses_from_csv():
    woosmap_localities = WoosmapLocalities()
    with open(INPUT_CSV_FILE, 'r') as csvinput:
        with open(OUTPUT_CSV_FILE, 'w') as csvoutput:

            # new csv based on same dialect as input csv
            writer = csv.writer(csvoutput, dialect="ga")

            # create a proper header with stripped fieldnames for new CSV
            # header = [h.strip() for h in next(csvinput).split(DELIMITER)]

            # read Input CSV as Dict of Dict
            reader = csv.DictReader(csvinput, dialect="ga")

            # 2-dimensional data variable used to write the new CSV
            processed_data = []

            # append new columns, to receive geocoded information, to the header of the new CSV
            header = list(reader.fieldnames)
            for column_name in NEW_COLUMNS_NAME:
                header.append(column_name.strip())
            processed_data.append(header)

            # iterate through each row of input CSV
            for record in reader:
                # build a line address based on the merge of multiple field values to pass to Google Geocoder
                line_address = ','.join(
                    str(val) for val in (record[column_name] for column_name in ADDRESS_COLUMNS_NAME))

                # if you want to use componentRestrictions feature,
                # build a matching dict {'googleComponentRestrictionField' : 'yourCSVFieldValue'}
                # to pass to Google Geocoder
                component_restrictions = {}
                if COMPONENT_RESTRICTIONS_COLUMNS_NAME:
                    for key, value in COMPONENT_RESTRICTIONS_COLUMNS_NAME.items():
                        component_restrictions[key] = record[value]

                # geocode the built line_address and passing optional componentRestrictions
                location = geocode_address(woosmap_localities, line_address, component_restrictions)

                # build a new temp_row for each csv entry to append to process_data Array
                # first, append existing fieldnames value to this temp_row
                temp_row = [record[column_name] for column_name in reader.fieldnames]

                # then, append geocoded field value to this temp_row
                for column_name in NEW_COLUMNS_NAME:
                    try:
                        temp_row.append(location[column_name])
                    except BaseException as error:
                        print(error)
                        temp_row.append('')

                # to manage more precisely errors, you could use csvwriter.writerow(item)
                # instead of build the processed_data array
                processed_data.append(temp_row)

            woosmap_localities.end()

            try:
                # finally write all rows once a time to the output CSV.
                writer.writerows(processed_data)
            except BaseException as error:
                print(error)


def geocode_address(woosmap_localities, line_address, component_restrictions=None, retry_counter=0):
    try:
        suggestions = woosmap_localities.autocomplete(line_address)
        if suggestions is not None:
            location = woosmap_localities.get_details(suggestions['localities'][0].get('public_id', ''))['result']
        if location is not None:
            location_geom = location.get('geometry')
            # build a dict to append to output CSV
            location_result = {"Lat": location['geometry']['location']['lat'],
                               "Long": location['geometry']['location']['lng'],
                               "Error": "",
                               "formatted_address": location['formatted_address'],
                               "location_type": location['geometry']['accuracy']}
        else:
            raise ValueError("None location found, please verify your address line")

    # To catch generic geocoder errors. TODO : Handle finer-grained exceptions
    except (ValueError) as error:
        location_result = {"Lat": 0, "Long": 0, "Error": error.message, "formatted_address": "", "location_type": ""}

    print("address line     : %s" % line_address)
    print("geocoded address : %s" % location_result["formatted_address"])
    print("location type    : %s" % location_result["location_type"])
    print("--------------------------------------------------------")

    return location_result


if __name__ == '__main__':
    process_addresses_from_csv()
