# Stores within a travel time

"Which stores can deliver within twenty minutes of this address?" Three API calls chained server-side:

1. Localities geocode turns the address into coordinates (skipped with `--origin lat,lng`).
2. The [Isochrone endpoint](https://developers.woosmap.com/products/distance-api/features/isochrone/) returns
   the reachable area as an encoded polyline.
3. Stores Search fetches candidates in a circle covering that area, and a point-in-polygon test keeps the
   ones inside.

```sh
pip install -r python/requirements.txt
python python/stores_within_isochrone.py --address "Piazza Testaccio, Roma" --country it --value 15
python python/stores_within_isochrone.py --origin 51.92,4.48 --value 30 --mode cycling --query 'type:"covered"'
python python/stores_within_isochrone.py --origin 51.92,4.48 --value 10 --method distance --json
```

`--value` is minutes with `--method time` (default) and kilometres with `--method distance`. The plain
output is one line per store, sorted by road-free distance from the origin; `--json` prints the matching
GeoJSON features.

The polyline decoder and the point-in-polygon test are in the script, so no geospatial dependency is needed.
