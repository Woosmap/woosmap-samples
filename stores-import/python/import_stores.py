"""Import stores from a spreadsheet into a Woosmap project. The reader lives in spreadsheet.py."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from spreadsheet import Row, read_source

API_URL = "https://api.woosmap.com"
MAX_BODY_BYTES = 15 * 1024 * 1024  # Stores API request body limit

DEFAULT_COLUMNS = {
    "storeId": "Store ID",
    "name": "Name",
    "lat": "Latitude",
    "lng": "Longitude",
    "addressLine": "Address Line",
    "city": "City",
    "zipcode": "Zipcode",
    "countryCode": "Country Code",
    "website": "Website",
    "phone": "Contact Phone",
    "email": "Contact Email",
    "types": "Type",
    "tags": "Tags",
}

Asset = dict[str, Any]


def parse_ratelimit(header: str) -> dict[str, int]:
    # IETF RateLimit header: "policy";r=<remaining>;t=<reset-seconds>; first policy only
    first_policy = header.split(",", 1)[0]
    return {key: int(value) for key, value in re.findall(r"\b([rt])=(\d+)", first_policy)}


def retry_delay(response: requests.Response, attempt: int) -> float:
    # RateLimit's t= is current; ratelimit-reset is a compat header pending removal;
    # Retry-After only ever comes from a proxy
    reset = parse_ratelimit(response.headers.get("RateLimit", "")).get("t")
    if reset is not None:
        return float(reset)
    for header in ("ratelimit-reset", "Retry-After"):
        try:
            return max(0.0, float(response.headers[header]))
        except (KeyError, ValueError):
            continue
    return float(2**attempt)


def rate_limit_remaining(response: requests.Response) -> int | None:
    remaining = parse_ratelimit(response.headers.get("RateLimit", "")).get("r")
    if remaining is not None:
        return remaining
    try:
        return int(response.headers["RateLimit-Remaining"])
    except (KeyError, ValueError):
        return None


@dataclass
class Conversion:
    assets: list[Asset] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    derived_ids: int = 0


def slugify(value: str) -> str:
    # storeId must match [A-Za-z0-9]+
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "", ascii_text)


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def parse_coordinate(value: str, name: str) -> float:
    try:
        return float(value.replace(",", "."))
    except ValueError as error:
        raise ValueError(f"invalid {name} {value!r}") from error


def store_id_for(row: Row, columns: dict[str, str]) -> str:
    explicit = row.get(columns["storeId"], "")
    store_id = slugify(explicit or row.get(columns["name"], ""))
    if not store_id:
        raise ValueError("no storeId and no name to derive one from")
    return store_id


def optional_object(pairs: dict[str, Any]) -> dict[str, Any] | None:
    cleaned = {key: value for key, value in pairs.items() if value}
    return cleaned or None


def row_to_asset(row: Row, columns: dict[str, str]) -> Asset:
    def col(key: str) -> str:
        return row.get(columns[key], "")

    name = col("name")
    if not name:
        raise ValueError("missing name")
    asset: Asset = {
        "storeId": store_id_for(row, columns),
        "name": name,
        "location": {
            "lat": parse_coordinate(col("lat"), "latitude"),
            "lng": parse_coordinate(col("lng"), "longitude"),
        },
    }
    address = optional_object(
        {
            "lines": [col("addressLine")] if col("addressLine") else None,
            "city": col("city"),
            "zipcode": col("zipcode"),
            "countryCode": col("countryCode").upper(),
        }
    )
    contact = optional_object(
        {"website": col("website"), "phone": col("phone"), "email": col("email")}
    )
    for key, value in (("address", address), ("contact", contact)):
        if value:
            asset[key] = value
    for key in ("types", "tags"):
        if col(key):
            asset[key] = parse_list(col(key))
    return asset


def convert_rows(rows: list[Row], columns: dict[str, str]) -> Conversion:
    result = Conversion()
    seen: dict[str, int] = {}
    for index, row in enumerate(rows, start=2):
        try:
            asset = row_to_asset(row, columns)
        except ValueError as error:
            result.errors.append(f"row {index}: {error}")
            continue
        if asset["storeId"] in seen:
            result.errors.append(
                f"row {index}: duplicate storeId {asset['storeId']!r} "
                f"(first seen row {seen[asset['storeId']]})"
            )
            continue
        seen[asset["storeId"]] = index
        result.assets.append(asset)
        if not row.get(columns["storeId"]):
            result.derived_ids += 1
    return result


class WoosmapStores:
    def __init__(self, private_key: str, session: requests.Session | None = None) -> None:
        self.private_key = private_key
        self.session = session or requests.Session()

    def send(self, method: str, path: str, stores: list[Asset]) -> dict[str, Any]:
        body = json.dumps({"stores": stores}).encode()
        if len(body) > MAX_BODY_BYTES:
            raise ValueError(f"request body is {len(body)} bytes, above the 15MB limit")
        for attempt in range(3):
            response = self.session.request(
                method,
                f"{API_URL}{path}",
                params={"private_key": self.private_key},
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=120,
            )
            if response.status_code != 429 or attempt == 2:
                break
            time.sleep(retry_delay(response, attempt))
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} failed ({response.status_code}): {response.text}")
        if rate_limit_remaining(response) == 0:
            # the quota is gone for this window; wait it out now instead of 429ing the next batch
            time.sleep(retry_delay(response, 0))
        return response.json()

    def replace_all(self, stores: list[Asset]) -> None:
        self.send("POST", "/stores/replace", stores)

    # POST rejects the whole batch if one storeId already exists, PUT if one is missing
    def create(self, stores: list[Asset]) -> None:
        self.send("POST", "/stores", stores)

    def update(self, stores: list[Asset]) -> None:
        self.send("PUT", "/stores", stores)


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a whole number of 1 or more")
    return number


def chunked(items: list[Asset], size: int) -> list[list[Asset]]:
    if size < 1:
        raise ValueError(f"batch size must be 1 or more, got {size}")
    return [items[i : i + size] for i in range(0, len(items), size)]


def upload(api: WoosmapStores, assets: list[Asset], mode: str, batch_size: int) -> None:
    if mode == "replace":
        api.replace_all(assets)
        print(f"replaced the project with {len(assets)} stores")
        return
    action = api.create if mode == "create" else api.update
    for batch in chunked(assets, batch_size):
        action(batch)
        print(f"{mode}d {len(batch)} stores")


def parse_column_overrides(values: list[str]) -> dict[str, str]:
    columns = dict(DEFAULT_COLUMNS)
    for value in values:
        key, _, column = value.partition("=")
        if key not in columns or not column:
            raise SystemExit(f"--column expects one of {sorted(columns)}=<header>, got {value!r}")
        columns[key] = column
    return columns


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        help="CSV or XLSX path, or a Google Sheets URL shared with 'anyone with the link'",
    )
    parser.add_argument("--sheet", help="worksheet name for XLSX sources (default: first sheet)")
    parser.add_argument(
        "--column",
        action="append",
        default=[],
        metavar="FIELD=HEADER",
        help="override a column mapping",
    )
    parser.add_argument("--mode", choices=("replace", "create", "update"), default="replace")
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=500,
        help="stores per request in create/update mode",
    )
    parser.add_argument(
        "--output", type=Path, help="also write the converted stores as Woosmap JSON"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="convert and validate without calling the API"
    )
    parser.add_argument("--strict", action="store_true", help="stop if any row fails to convert")
    return parser


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session = requests.Session()
    try:
        rows = read_source(args.source, args.sheet, session)
    except FileNotFoundError:
        raise SystemExit(f"no such file: {args.source}") from None
    conversion = convert_rows(rows, parse_column_overrides(args.column))
    for error in conversion.errors:
        print(error, file=sys.stderr)
    print(f"{len(conversion.assets)} stores ready, {len(conversion.errors)} rows skipped")
    if conversion.derived_ids:
        print(
            f"storeId derived from the name for {conversion.derived_ids} stores; "
            "add a Store ID column before relying on stores-sync",
            file=sys.stderr,
        )
    if args.strict and conversion.errors:
        return 1
    if args.output:
        args.output.write_text(
            json.dumps({"stores": conversion.assets}, indent=2, ensure_ascii=False)
        )
    if args.dry_run or not conversion.assets:
        return 0
    upload(
        WoosmapStores(private_key_from_env(), session),
        conversion.assets,
        args.mode,
        args.batch_size,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
