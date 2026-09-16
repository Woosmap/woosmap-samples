# Keep a project in sync with a source of truth

Compare a Woosmap JSON file with the stores currently in the project, then create, update and delete only
the differences. Meant for a scheduled job fed by your ERP, PIM or master data export.

Produce the input with [stores-import](../stores-import/) (`--dry-run --output stores.json`) or
[stores-export](../stores-export/). The file is `{"stores": [...]}` using the request-body field names
(`storeId`, `countryCode`, `userProperties`, `openingHours`).

## Python

```sh
pip install -r python/requirements.txt
python python/sync_stores.py stores.json --dry-run
python python/sync_stores.py stores.json
python python/sync_stores.py stores.json --no-delete
```

## Node

```sh
node node/sync-stores.mjs stores.json --dry-run
```

## How the diff works

1. Every remote store is fetched through `GET /stores/search`, paginated by 300.
2. Response fields are mapped back to request fields (`store_id` to `storeId`, `country_code` to `countryCode`).
3. Both sides are normalised before comparison: empty values dropped, coordinates rounded to six decimals,
   string lists sorted.
4. Local wins. A store present on both sides but different is sent with `PUT`, whole.
5. Stores absent from the file are deleted with `DELETE /stores?query=idstore:="a" OR idstore:="b"`,
   fifty per request. `--no-delete` turns that off.

Temporary closures that have already ended are dropped by the API, so the comparison ignores them too.

Running the sync twice in a row must report nothing to do. If it does not, a field is not echoed back by
the API the way it was sent; open an issue with the store id.
