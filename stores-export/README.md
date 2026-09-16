# Export a project

Dump every store as Woosmap JSON, which [stores-sync](../stores-sync/) and the Stores API accept as input,
or as GeoJSON for QGIS, a BI tool or a backup.

```sh
pip install -r python/requirements.txt
python python/export_stores.py --output stores.json
python python/export_stores.py --format geojson --output stores.geojson
python python/export_stores.py --query 'type:"grocery"' --output grocery.json
```

The export walks `GET /stores/search` page by page. The `--query` filter uses the
[Stores API query syntax](https://developers.woosmap.com/products/stores-api/concepts/query-syntax/).
Response-only fields such as `open`, `weekly_opening` and `last_updated` are dropped from the Woosmap
JSON output so the file can be re-imported as is.
