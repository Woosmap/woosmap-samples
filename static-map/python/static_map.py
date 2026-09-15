"""Render a Static Map image server-side, ready to attach to an e-mail or a PDF."""

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

API_URL = "https://api.woosmap.com/maps/static"


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


def parse_marker(text: str) -> dict[str, Any]:
    parts = [part.strip() for part in text.split(",", 2)]
    if len(parts) < 2:
        raise ValueError(f"marker {text!r} must be lat,lng[,icon-url]")
    marker: dict[str, Any] = {"lat": float(parts[0]), "lng": float(parts[1])}
    if len(parts) == 3 and parts[2]:
        marker["url"] = parts[2]
    return marker


def build_params(args: argparse.Namespace) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [
        ("lat", str(args.lat)),
        ("lng", str(args.lng)),
        ("zoom", str(args.zoom)),
        ("width", str(args.width)),
        ("height", str(args.height)),
    ]
    if args.retina:
        params.append(("retina", "true"))
    if args.language:
        params.append(("language", args.language))
    params.extend(
        ("markers", json.dumps(parse_marker(m), separators=(",", ":"))) for m in args.marker
    )
    return params


def fetch_image(
    session: requests.Session, private_key: str, params: list[tuple[str, str]]
) -> bytes:
    for attempt in range(3):
        response = session.get(API_URL, params=[*params, ("private_key", private_key)], timeout=60)
        if response.status_code != 429 or attempt == 2:
            break
        time.sleep(retry_delay(response, attempt))
    if response.status_code >= 400:
        raise RuntimeError(f"static map failed ({response.status_code}): {response.text}")
    if not response.headers.get("Content-Type", "").startswith("image/"):
        raise RuntimeError(f"unexpected content type {response.headers.get('Content-Type')!r}")
    return response.content


def public_url(params: list[tuple[str, str]]) -> str:
    return (
        requests.Request("GET", API_URL, params=[*params, ("key", "YOUR_PUBLIC_KEY")]).prepare().url
        or ""
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lng", type=float, required=True)
    parser.add_argument("--zoom", type=int, default=15)
    parser.add_argument("--width", type=int, default=600)
    parser.add_argument("--height", type=int, default=400)
    parser.add_argument("--retina", action="store_true")
    parser.add_argument("--language", help="labels language, e.g. fr")
    parser.add_argument(
        "--marker", action="append", default=[], metavar="LAT,LNG[,ICON_URL]", help="repeatable"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("map.webp"), help="the API returns WebP"
    )
    return parser


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    params = build_params(args)
    png = fetch_image(requests.Session(), private_key_from_env(), params)
    args.output.write_bytes(png)
    print(f"wrote {len(png)} bytes to {args.output}", file=sys.stderr)
    print(f"same map with a public key: {public_url(params)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
