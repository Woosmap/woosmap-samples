# Import stores from a spreadsheet

Turn a CSV, an Excel workbook or a Google Sheet into Woosmap assets and load them with one atomic
`POST /stores/replace`. The previous dataset stays online until the new one is accepted, and a rejected
batch leaves the project untouched.

Ask yourself first whether you need [stores-sync](../stores-sync/) instead: replace is right for a first
load or a small dataset; a nightly refresh of thousands of stores should only send what changed.

## Input

One row per store. Default column headers, override any of them with `--column FIELD=HEADER`:

| Field | Header | Notes |
| --- | --- | --- |
| `name` | Name | required |
| `lat`, `lng` | Latitude, Longitude | required, decimal comma accepted |
| `storeId` | Store ID | optional, derived from the name when absent, kept to `[A-Za-z0-9]` |
| `addressLine`, `city`, `zipcode`, `countryCode` | Address Line, City, Zipcode, Country Code | |
| `website`, `phone`, `email` | Website, Contact Phone, Contact Email | |
| `types`, `tags` | Type, Tags | `|`-separated lists |

Give every store a stable `Store ID` before anything beyond a one-off load. An id derived from the
name changes when the name does, and [stores-sync](../stores-sync/) then sees a deletion and a creation.

Google Sheets: share the sheet with "anyone with the link" and pass the browser URL. The script downloads
the CSV export, no OAuth involved. Excel files are read with openpyxl (Python only).

## Layout

Reading the file is one module, `spreadsheet.py` (`spreadsheet.mjs` in Node): CSV sniffing, XLSX, and the
Google Sheets export URL. Everything Woosmap is in `import_stores.py` (`import-stores.mjs`): rows to assets,
assets to the API. Swap the reader for your own source and the rest still applies.

## Python

```sh
pip install -r python/requirements.txt
python python/import_stores.py ../data/foodmarkets.csv --dry-run --output stores.json
python python/import_stores.py ../data/foodmarkets.xlsx --sheet foodmarkets
python python/import_stores.py "https://docs.google.com/spreadsheets/d/<id>/edit#gid=0" --column name="Shop name"
python python/import_stores.py new_stores.csv --mode create --batch-size 300
```

`--dry-run` validates and prints what would be sent. `--output` writes the converted Woosmap JSON, which
is the input format of [stores-sync](../stores-sync/). `--strict` fails on the first bad row instead of
skipping it. `--mode create` and `--mode update` batch `POST` and `PUT /stores` for incremental loads.

## Node

```sh
node node/import-stores.mjs ../data/foodmarkets.csv --dry-run --output stores.json
```

Same flags. Reads CSV and Google Sheets, not XLSX.

## Behaviour worth knowing

- Duplicate `storeId` values in the source are reported and only the first row is kept.
- Requests above the 15MB body limit are refused locally before reaching the API.
- 429 responses are retried after `Retry-After`; any other error stops with the API message.
- Bad input stops with one line, not a traceback.
