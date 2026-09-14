# Woosmap samples

Server-side scripts that show how to do one job with the [Woosmap APIs](https://developers.woosmap.com).
Each folder is a use case. Inside, one folder per language. Copy the folder you need, every script stands alone.

| Use case | What it does | Python | Node |
| --- | --- | --- | --- |
| [stores-import](stores-import/) | Load a CSV, XLSX or Google Sheet into a project with one atomic replace | ✓ | ✓ (CSV, Sheets) |
| [stores-sync](stores-sync/) | Nightly sync: create, update and delete only the stores that changed | ✓ | ✓ |
| [stores-export](stores-export/) | Dump a project as re-importable Woosmap JSON or GeoJSON | ✓ | |
| [opening-hours](opening-hours/) | Turn a weekday-per-column spreadsheet into the `openingHours` object | ✓ | |
| [batch-geocoding](batch-geocoding/) | Geocode or reverse geocode a CSV with Localities | ✓ | |
| [distance-matrix](distance-matrix/) | Large matrices with the async endpoint, small ones in Java | ✓ | ✓ |
| [isochrone-stores](isochrone-stores/) | Which stores are within N minutes of an address | ✓ | |
| [datasets](datasets/) | Declare, import and query a Datasets API dataset | ✓ | |
| [static-map](static-map/) | Render a map image server-side for an e-mail or a PDF | ✓ | |
| [geolocation-stores](geolocation-stores/) | Nearest stores from a visitor's IP address | ✓ | |

Front-end samples for Map JS live in [js-samples](https://github.com/Woosmap/js-samples).

## Running a sample

Every script reads the private key from the `WOOSMAP_PRIVATE_KEY` environment variable and never
writes it to disk. Get one from the Console, on a project you can afford to overwrite.

```sh
export WOOSMAP_PRIVATE_KEY=...
cd stores-import/python
pip install -r requirements.txt
python import_stores.py ../../data/foodmarkets.csv --dry-run
```

Node samples need Node 20 or later and no dependency:

```sh
cd stores-import/node
node import-stores.mjs ../../data/foodmarkets.csv --dry-run
```

Test data lives in [data/](data/). The food markets set is small enough to import into any project.

## Conventions

- Python 3.10+, type hints everywhere, `requests` as the only HTTP dependency.
- Node 20+, ES modules, the built-in `fetch`, no dependency.
- One retry policy: 429 waits for `ratelimit-reset`, the header the API actually sends, then retries.
  Anything else fails with the response body.
- Write operations use `/stores/replace` or explicit create, update and delete, never delete-then-post.
- Each sample ships its tests. `pytest` and `node --test` run offline against mocked responses.
- Where a sample needs plumbing that is not about Woosmap, it sits in its own module next to the main one.

## Contributing

Run the checks before opening a pull request:

```sh
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
(cd stores-import/python && python -m pytest)
(cd stores-import/node && node --test)
```

CI runs the same for every sample, plus a compile of the Java client. When the repository secret
`WOOSMAP_PRIVATE_KEY` is set, it also runs the read-only samples against a real project.

## Licence

[MIT](LICENSE).
