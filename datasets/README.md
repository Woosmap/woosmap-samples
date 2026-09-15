# Datasets API, end to end

The [Datasets API](https://developers.woosmap.com/products/datasets-api/get-started/) stores your own
polygons, lines and points and answers spatial questions about them. It is activated per organisation, ask
support first. Data is loaded from a zipped Shapefile that you host on a URL Woosmap can fetch.

```sh
pip install -r python/requirements.txt

python python/manage_dataset.py create --name countries --url https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip --title-key NAME
python python/manage_dataset.py import <dataset_id> --wait
python python/manage_dataset.py status <dataset_id>
python python/manage_dataset.py list

python python/manage_dataset.py query <dataset_id> --operator contains --geometry "48.8566,2.3522"
python python/manage_dataset.py query <dataset_id> --operator within --geometry @paris.geojson --where "population:>1000"
python python/manage_dataset.py query <dataset_id> --operator intersects --geometry "LINESTRING(2.3 48.8, 2.4 48.9)" --buffer 200
```

`import --wait` polls the status endpoint, treating the 404 the API returns until the worker has picked
the job up as "not started yet", and prints each step (`fetch`, `import`) until success or failure; the
exit code follows. Import triggers are rate limited to one per 90 seconds per dataset, status checks to one
per 5 seconds, so keep `--poll-interval` at 5 or more.

Geometries can be WKT, a bare `lat,lng`, or `@file.geojson` holding a Feature or a geometry. A bare point
is sent as WKT `POINT(lng lat)`: the spec lists `lat,lng` as accepted, but the API matches nothing with it.
Results are paginated twenty per page by the API and gathered into one list.

`nearby` has no distance cut-off: it returns every feature of the dataset sorted by distance to the
geometry, and `--buffer` does not apply to it. Take the first results rather than expecting a radius.
`--buffer` widens the input geometry for `intersects` only; the other operators ignore it.

Each result is `{id, attributes, geometry}`. Attributes are the Shapefile fields as loaded. The geometry in
search results is the feature's bounding box; fetch `GET /datasets/{dataset_id}/features/{feature_id}` for
the full shape.

To refresh on a schedule, keep the `reimport_key` returned by `create` and call
`POST /datasets/hooks/reimport/{reimport_key}` from your pipeline.
