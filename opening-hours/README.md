# Convert opening hours

Retailers keep hours in spreadsheets with one column per weekday. The Stores API wants an
[`openingHours` object](https://developers.woosmap.com/products/stores-api/concepts/opening-hours/) with
numeric day keys, time slices, special dates and temporary closures. This script does the conversion and
validates as it goes.

## Input

`hours.csv`: `store_id`, optional `timezone`, then `monday` … `sunday`. A cell can be:

| Cell | Result |
| --- | --- |
| empty, `closed`, `-` | closed that day |
| `24/7`, `all-day`, `24h` | `[{"all-day": true}]` |
| `09:00-12:00, 14:00-19:00` | two slices, `;` or `,` between them, `9h00` accepted |
| `22:00-02:00` | one slice crossing midnight, kept as is, the API handles it |

Optional `special.csv` (`store_id`, `date`, `hours`, same cell grammar, ISO dates) and
`closures.csv` (`store_id`, `start`, `end`, inclusive ISO dates).

When all seven days are identical the output uses the `default` key. Closures that have already ended are
accepted but the API discards them on import.

## Usage

```sh
python python/opening_hours.py ../data/opening_hours.csv \
  --special ../data/special_hours.csv --closures ../data/closures.csv \
  --output hours.json

python python/opening_hours.py hours.csv --timezone Europe/Paris \
  --merge stores.json --output stores_with_hours.json
```

The first form writes `{store_id: openingHours}`. The second injects the hours into a Woosmap JSON file
so [stores-sync](../stores-sync/) can push them. Invalid rows are reported and skipped; `--strict` fails
instead. No dependency beyond the standard library.

Timezones are not derived from coordinates here; put them in the CSV or pass a single `--timezone`.
