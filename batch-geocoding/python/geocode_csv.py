"""Geocode (or reverse geocode) every row of a CSV file with the Woosmap Localities API."""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.woosmap.com/localities/geocode/"
OUTPUT_COLUMNS = [
    "geocode_lat",
    "geocode_lng",
    "geocode_formatted_address",
    "geocode_location_type",
    "geocode_public_id",
    "geocode_error",
]

Row = dict[str, str]


def retry_delay(response: requests.Response, attempt: int) -> float:
    # Woosmap sends ratelimit-reset, in seconds; Retry-After only comes from proxies
    for header in ("ratelimit-reset", "Retry-After"):
        try:
            return max(0.0, float(response.headers[header]))
        except (KeyError, ValueError):
            continue
    return float(2**attempt)


@dataclass(frozen=True)
class Options:
    address_columns: list[str]
    country_column: str | None
    country: str | None
    reverse: bool
    lat_column: str
    lng_column: str
    language: str | None
    delay: float


def address_from(row: Row, columns: list[str]) -> str:
    return ", ".join(part for part in (row.get(column, "").strip() for column in columns) if part)


def components_for(row: Row, options: Options) -> str | None:
    country = row.get(options.country_column, "") if options.country_column else options.country
    return f"country:{country.strip().lower()}" if country and country.strip() else None


def params_for(row: Row, options: Options) -> dict[str, str]:
    params: dict[str, str] = {}
    if options.reverse:
        params["latlng"] = f"{row[options.lat_column].strip()},{row[options.lng_column].strip()}"
    else:
        params["address"] = address_from(row, options.address_columns)
        components = components_for(row, options)
        if components:
            params["components"] = components
    if options.language:
        params["language"] = options.language
    return params


class Geocoder:
    def __init__(self, private_key: str, session: requests.Session | None = None) -> None:
        self.private_key = private_key
        self.session = session or requests.Session()

    def call(self, params: dict[str, str]) -> dict[str, Any]:
        for attempt in range(3):
            response = self.session.get(
                API_URL, params={"private_key": self.private_key, **params}, timeout=30
            )
            if response.status_code != 429 or attempt == 2:
                break
            time.sleep(retry_delay(response, attempt))
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        return response.json()


def first_result(body: dict[str, Any]) -> dict[str, str]:
    results = body.get("results") or []
    if not results:
        return {"geocode_error": "ZERO_RESULTS"}
    best = results[0]
    location = (best.get("geometry") or {}).get("location") or {}
    return {
        "geocode_lat": str(location.get("lat", "")),
        "geocode_lng": str(location.get("lng", "")),
        "geocode_formatted_address": best.get("formatted_address", ""),
        "geocode_location_type": (best.get("geometry") or {}).get("location_type", ""),
        "geocode_public_id": best.get("public_id", ""),
        "geocode_error": "",
    }


def geocode_row(geocoder: Geocoder, row: Row, options: Options) -> Row:
    try:
        params = params_for(row, options)
        if not params.get("address") and not params.get("latlng"):
            raise ValueError("empty address")
        result = first_result(geocoder.call(params))
    except (KeyError, ValueError, RuntimeError, requests.RequestException) as error:
        result = {"geocode_error": str(error)}
    return {**row, **{column: result.get(column, "") for column in OUTPUT_COLUMNS}}


def read_rows(path: Path) -> tuple[list[str], list[Row]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return list(reader.fieldnames or []), list(reader)


def process(geocoder: Geocoder, rows: list[Row], options: Options) -> list[Row]:
    output: list[Row] = []
    for index, row in enumerate(rows, start=1):
        geocoded = geocode_row(geocoder, row, options)
        status = geocoded["geocode_error"] or geocoded["geocode_location_type"]
        print(f"{index}/{len(rows)} {status}", file=sys.stderr)
        output.append(geocoded)
        if options.delay:
            time.sleep(options.delay)
    return output


def write_rows(path: Path, fieldnames: list[str], rows: list[Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames + OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--address-columns",
        default="address",
        help="comma-separated columns joined into the address (forward mode)",
    )
    parser.add_argument("--country-column", help="column holding an ISO 3166-1 country code")
    parser.add_argument("--country", help="fixed ISO 3166-1 country code for every row")
    parser.add_argument("--reverse", action="store_true", help="reverse geocode lat/lng columns")
    parser.add_argument("--lat-column", default="lat")
    parser.add_argument("--lng-column", default="lng")
    parser.add_argument("--language", help="response language, e.g. fr")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to wait between rows")
    return parser


def options_from(args: argparse.Namespace) -> Options:
    return Options(
        address_columns=[c.strip() for c in args.address_columns.split(",") if c.strip()],
        country_column=args.country_column,
        country=args.country,
        reverse=args.reverse,
        lat_column=args.lat_column,
        lng_column=args.lng_column,
        language=args.language,
        delay=args.delay,
    )


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fieldnames, rows = read_rows(args.input)
    geocoded = process(Geocoder(private_key_from_env()), rows, options_from(args))
    write_rows(args.output, fieldnames, geocoded)
    failed = sum(1 for row in geocoded if row["geocode_error"])
    print(f"{len(geocoded) - failed} geocoded, {failed} failed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
