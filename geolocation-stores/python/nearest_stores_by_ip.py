"""Find the stores closest to a visitor from their IP address, server-side."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

API_URL = "https://api.woosmap.com/geolocation/stores"


def locate(session: requests.Session, private_key: str, ip: str, **params: Any) -> dict[str, Any]:
    response = session.get(
        API_URL,
        params={
            "private_key": private_key,
            "ip_address": ip,
            **{k: v for k, v in params.items() if v},
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"geolocation failed ({response.status_code}): {response.text}")
    return response.json()


def describe_location(body: dict[str, Any]) -> str:
    place = ", ".join(part for part in (body.get("city"), body.get("country_name")) if part)
    accuracy = body.get("accuracy")
    return f"{place or 'unknown location'} (accuracy {accuracy} km)" if accuracy else place


def store_lines(body: dict[str, Any]) -> list[str]:
    features = (body.get("stores") or {}).get("features") or []
    return [
        f"{f['properties'].get('store_id')}\t{f['properties'].get('name')}\t{f['properties'].get('distance')}"
        for f in features
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ip", help="public IPv4 or IPv6 address of the visitor")
    parser.add_argument("--limit", type=int, default=3, help="number of stores to return")
    parser.add_argument("--radius", type=int, help="search radius in metres")
    parser.add_argument("--query", help='optional Stores API query, e.g. type:"grocery"')
    parser.add_argument("--json", action="store_true", help="print the raw response")
    return parser


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    body = locate(
        requests.Session(),
        private_key_from_env(),
        args.ip,
        limit=args.limit,
        radius=args.radius,
        query=args.query,
    )
    if args.json:
        print(json.dumps(body, indent=2))
        return 0
    print(describe_location(body))
    lines = store_lines(body)
    print("\n".join(lines) if lines else "no store found near this IP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
