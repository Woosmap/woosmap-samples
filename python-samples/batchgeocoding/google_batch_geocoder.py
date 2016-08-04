import csv
from _csv import QUOTE_MINIMAL
from csv import Dialect
from geopy.geocoders import GoogleV3

# used to set a google geocoding query by merging this value into one string with comma separated
ADDRESS_COLUMNS_NAME = ["name", "addressline1", "town"]

# used to define component restrictions for google geocoding
COMPONENT_RESTRICTIONS_COLUMNS_NAME = {"country": "IsoCode"}

# appended columns name to processed data csv
NEW_COLUMNS_NAME = ["Lat", "Long", "Error", "formatted_address", "location_type"]

# delimiter for input csv file
DELIMITER = ";"

# path and name for output csv file
INPUT_CSV_FILE = "./hairdresser_sample_addresses.csv"

# path and name for output csv file
OUTPUT_CSV_FILE = "./processed.csv"

# google keys - see https://blog.woosmap.com for more details
GOOGLE_SECRET_KEY = "" # important !! this key must stay private. TODO : pass this variable as a parameter to this script
GOOGLE_CLIENT_ID = "" # if used, you must provide secret_key


# dialect to manage different format of CSV
class CustomDialect(Dialect):
    delimiter = DELIMITER
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = '\n'
    quoting = QUOTE_MINIMAL


csv.register_dialect('ga', CustomDialect)


def process_addresses_from_csv():
    geo_locator = GoogleV3(client_id=GOOGLE_CLIENT_ID, secret_key=GOOGLE_SECRET_KEY)

    with open(INPUT_CSV_FILE, 'r') as csvinput:
        with open(OUTPUT_CSV_FILE, 'w') as csvoutput:

            # new csv based on same dialect as input csv
            writer = csv.writer(csvoutput, dialect="ga")

            # create a proper header with stripped fieldnames for new CSV
            header = [h.strip() for h in csvinput.next().split(DELIMITER)]

            # read Input CSV as Dict of Dict
            reader = csv.DictReader(csvinput, dialect="ga", fieldnames=header)

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
                location = geocode_address(geo_locator, line_address, component_restrictions)

                # build a new temp_row for each csv entry to append to process_data Array
                temp_row = []

                # append existing fieldnames value to this temp_row
                for column_name in reader.fieldnames:
                    temp_row.append(record[column_name])

                # append geocoded field value to this temp_row
                for column_name in NEW_COLUMNS_NAME:
                    try:
                        if isinstance(location[column_name], str):
                            temp_row.append(location[column_name].encode('utf-8'))
                        else:
                            temp_row.append(location[column_name])
                    except BaseException as error:
                        print(error)
                        temp_row.append('')

                # to manage more precisely errors, you could use csvwriter.writerow(item)
                # instead of build the processed_data array
                processed_data.append(temp_row)

            try:
                # finally write all rows once a time to the output CSV.
                writer.writerows(processed_data)
            except BaseException as error:
                print(error)


def geocode_address(geo_locator, line_address, component_restrictions=None):
    try:
        # the geopy GoogleV3 geocoding call
        location = geo_locator.geocode(line_address, components=component_restrictions)
        # build a dict to append to output CSV
        location_result = {"Lat": location.latitude, "Long": location.longitude, "Error": "",
                           "formatted_address": location.raw['formatted_address'],
                           "location_type": location.raw['geometry']['location_type']}

    except BaseException as error:
        location_result = {"Lat": 0, "Long": 0, "Error": error.message, "formatted_address": "", "location_type": ""}

    print("address line     : %s" % line_address)
    print("geocoded address : %s" % location_result["formatted_address"])
    print("location type    : %s" % location_result["location_type"])

    return location_result


if __name__ == '__main__':
    process_addresses_from_csv()
