**[UPDATE 31/01/2020]**
The script has moved to a dedicated repository, [woosmap/geopy-googlemaps-batchgeocoder](https://github.com/woosmap/geopy-googlemaps-batchgeocoder), and updated to be compatible with Python3.  
---

# Python Script to batch geocode your csv address file using geopy and GoogleV3 Geocoding service

**input** : csv file with addresses you need to geocode

**output** : same csv with appended following fields
 
- Latitude
- Longitude
- Location_Type
- Formatted_Address 
- Error (if needded, for failed geocoded addresses)

sample usage:

    python google_batch_geocoder.py


**Mandatory parameters you have to set inside the python file**
  
- ADDRESS_COLUMNS_NAME = ["name", "addressline1", "town"]
*used to set a google geocoding query by merging this value into one string with comma separated. it depends on your CSV Input File*

- NEW_COLUMNS_NAME = ["Lat", "Long", "Error", "formatted_address", "location_type"]
*appended columns name to processed data csv*

- DELIMITER = ";"
*delimiter for input csv file*

- INPUT_CSV_FILE = "./hairdresser_sample_addresses_sample.csv"
*path and name for output csv file*

- OUTPUT_CSV_FILE = "./processed.csv"
*path and name for output csv file*

**optional parameters**

- COMPONENTS_RESTRICTIONS_COLUMNS_NAME = {"country": "IsoCode"}
*used to define component restrictions for google geocoding*
*see [Google componentRestrictions doc](https://developers.google.com/maps/documentation/javascript/reference?hl=FR#GeocoderComponentRestrictions) for details* 

- GOOGLE_SECRET_KEY = "1Asfgsdf5vR12XE1A6sfRd7="
*google secret key that allow you to geocode for Google API Premium accounts*

- GOOGLE_CLIENT_ID = "gme-webgeoservicessa1"
*google client ID, used to track and analyse your requests for Google API Premium accounts*



**useful links**

- [geopy](https://github.com/geopy/geopy) : Geocoding library for Python.
- [Google Maps Geocoding API](https://developers.google.com/maps/documentation/geocoding/start)
- [Google Maps Geocoding API Usage Limits](https://developers.google.com/maps/documentation/geocoding/usage-limits)
