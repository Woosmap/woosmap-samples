# Geocode a CSV

Add coordinates to a file of addresses, or addresses to a file of coordinates, with the
[Localities geocode endpoint](https://developers.woosmap.com/products/localities/features/geocoding/).
Every input column is kept; six `geocode_*` columns are appended: lat, lng, formatted address, location
type (`ROOFTOP`, `GEOMETRIC_CENTER`, `APPROXIMATE`), public id and error.

```sh
pip install -r python/requirements.txt

# forward: pick the columns that make up the address, and the country when you know it
python python/geocode_csv.py ../data/addresses_au.csv out.csv \
  --address-columns addressline1,postalcode,town --country-column IsoCode

# reverse
python python/geocode_csv.py ../data/coordinates.csv out.csv --reverse --lat-column lat --lng-column lng
```

Pass `--country fr` for a single country, `--language` for the output language and `--delay 0.1` to
pace requests. Rows that fail keep their input and get the reason in `geocode_error`, the run continues.
Always restrict the country when you can, it is the single biggest accuracy lever.

Check `geocode_location_type` before trusting a result: `GEOMETRIC_CENTER` on a street-level input means
the house number was not found.
