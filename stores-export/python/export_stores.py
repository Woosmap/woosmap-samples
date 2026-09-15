"""Export every store of a Woosmap project as re-importable Woosmap JSON or as GeoJSON."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.woosmap.com"
PAGE_SIZE = 300  # stores_by_page maximum

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


def fetch_page(
    session: requests.Session, private_key: str, page: int, query: str | None
) -> dict[str, Any]:
    params: dict[str, Any] = {"private_key": private_key, "stores_by_page": PAGE_SIZE, "page": page}
    if query:
        params["query"] = query
    for attempt in range(3):
        response = session.get(f"{API_URL}/stores/search", params=params, timeout=60)
        if response.status_code != 429 or attempt == 2:
            break
        time.sleep(retry_delay(response, attempt))
    if response.status_code >= 400:
        raise RuntimeError(f"search failed ({response.status_code}): {response.text}")
    return response.json()


def fetch_all(
    session: requests.Session, private_key: str, query: str | None
) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    page = 1
    while True:
        body = fetch_page(session, private_key, page, query)
        features.extend(body.get("features", []))
        if page >= body.get("pagination", {}).get("pageCount", 1):
            return features
        page += 1


def strip_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {k: strip_empty(v) for k, v in value.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, {}, [], "")}
    return value


def feature_to_asset(feature: dict[str, Any]) -> Asset:
    props = feature["properties"]
    lng, lat = feature["geometry"]["coordinates"]
    address = props.get("address") or {}
    return strip_empty(
        {
            "storeId": props["store_id"],
            "name": props.get("name"),
            "location": {"lat": lat, "lng": lng},
            "address": {
                "lines": address.get("lines"),
                "city": address.get("city"),
                "zipcode": address.get("zipcode"),
                "countryCode": address.get("country_code"),
            },
            "contact": props.get("contact"),
            "types": props.get("types"),
            "tags": props.get("tags"),
            "userProperties": props.get("user_properties"),
            "openingHours": props.get("opening_hours"),
        }
    )


def to_geojson(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def to_woosmap_json(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"stores": [feature_to_asset(feature) for feature in features]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("woosmap", "geojson"), default="woosmap")
    parser.add_argument("--query", help='optional Stores API query, e.g. type:"grocery"')
    parser.add_argument("--output", type=Path, help="output file (default: stdout)")
    return parser


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    features = fetch_all(requests.Session(), private_key_from_env(), args.query)
    document = to_geojson(features) if args.format == "geojson" else to_woosmap_json(features)
    text = json.dumps(document, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {len(features)} stores to {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
