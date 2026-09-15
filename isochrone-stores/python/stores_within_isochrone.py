"""List the stores reachable within a travel time, combining Isochrone and Stores Search."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from typing import Any

import requests

API_URL = "https://api.woosmap.com"
PAGE_SIZE = 300  # stores_by_page maximum
EARTH_RADIUS_M = 6_371_000

LatLng = tuple[float, float]


def parse_ratelimit(header: str) -> list[dict[str, int]]:
    # IETF RateLimit header: comma-separated "policy";r=<remaining>;t=<reset-seconds> entries
    return [
        {key: int(value) for key, value in re.findall(r"\b([rt])=(\d+)", policy)}
        for policy in header.split(",")
        if policy.strip()
    ]


def retry_delay(response: requests.Response, attempt: int) -> float:
    # a 429 is bound by whichever policy hit zero, not necessarily the first one in the header;
    # ratelimit-reset is a compat header pending removal, Retry-After only ever comes from a proxy
    policies = parse_ratelimit(response.headers.get("RateLimit", ""))
    exhausted = [policy["t"] for policy in policies if policy.get("r") == 0 and "t" in policy]
    if exhausted:
        return float(max(exhausted))
    for header in ("ratelimit-reset", "Retry-After"):
        try:
            return max(0.0, float(response.headers[header]))
        except (KeyError, ValueError):
            continue
    return float(2**attempt)


def decode_polyline(encoded: str, precision: int = 5) -> list[LatLng]:
    factor = 10**precision
    points: list[LatLng] = []
    index, lat, lng = 0, 0, 0
    while index < len(encoded):
        for coordinate in ("lat", "lng"):
            shift, result = 0, 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if coordinate == "lat":
                lat += delta
            else:
                lng += delta
        points.append((lat / factor, lng / factor))
    return points


def haversine_m(a: LatLng, b: LatLng) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def point_in_polygon(point: LatLng, polygon: list[LatLng]) -> bool:
    lat, lng = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        (lat1, lng1), (lat2, lng2) = previous, current
        crosses = (lat1 > lat) != (lat2 > lat)
        if crosses and lng < (lng2 - lng1) * (lat - lat1) / (lat2 - lat1) + lng1:
            inside = not inside
        previous = current
    return inside


def covering_radius_m(origin: LatLng, polygon: list[LatLng]) -> int:
    return int(max(haversine_m(origin, vertex) for vertex in polygon) * 1.05) + 100


class Woosmap:
    def __init__(self, private_key: str, session: requests.Session | None = None) -> None:
        self.private_key = private_key
        self.session = session or requests.Session()

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        request_params = {"private_key": self.private_key, **params}
        for attempt in range(3):
            response = self.session.get(f"{API_URL}{path}", params=request_params, timeout=60)
            if response.status_code != 429 or attempt == 2:
                break
            time.sleep(retry_delay(response, attempt))
        if response.status_code >= 400:
            raise RuntimeError(f"GET {path} failed ({response.status_code}): {response.text}")
        body = response.json()
        # the Distance API reports errors in `status` with HTTP 200, unlike the other APIs
        status = body.get("status")
        if status not in (None, "OK"):
            detail = body.get("message") or body.get("error_message") or ""
            raise RuntimeError(f"GET {path} returned {status}: {detail}".strip())
        return body

    def geocode(self, address: str, country: str | None) -> LatLng:
        params = {"address": address}
        if country:
            params["components"] = f"country:{country.lower()}"
        results = self.get("/localities/geocode/", **params).get("results") or []
        if not results:
            raise RuntimeError(f"no geocoding result for {address!r}")
        location = results[0]["geometry"]["location"]
        return location["lat"], location["lng"]

    def isochrone(self, origin: LatLng, value: int, method: str, mode: str) -> list[LatLng]:
        body = self.get(
            "/distance/isochrone/json/",
            origin=f"{origin[0]},{origin[1]}",
            value=value,
            method=method,
            mode=mode,
        )
        # the isoline is an encoded polyline, not GeoJSON
        return decode_polyline(body["isoline"]["geometry"])

    def stores_around(
        self, origin: LatLng, radius_m: int, query: str | None
    ) -> list[dict[str, Any]]:
        features: list[dict[str, Any]] = []
        page = 1
        while True:
            params: dict[str, Any] = {
                "lat": origin[0],
                "lng": origin[1],
                "radius": radius_m,
                "stores_by_page": PAGE_SIZE,
                "page": page,
            }
            if query:
                params["query"] = query
            body = self.get("/stores/search", **params)
            features.extend(body.get("features", []))
            if page >= body.get("pagination", {}).get("pageCount", 1):
                return features
            page += 1


def store_point(feature: dict[str, Any]) -> LatLng:
    lng, lat = feature["geometry"]["coordinates"]
    return lat, lng


# Stores Search filters by circle, polyline or zone, not by polygon: fetch a covering
# circle, then clip to the isochrone locally.
def stores_within(
    api: Woosmap, origin: LatLng, polygon: list[LatLng], query: str | None
) -> list[dict[str, Any]]:
    candidates = api.stores_around(origin, covering_radius_m(origin, polygon), query)
    return [feature for feature in candidates if point_in_polygon(store_point(feature), polygon)]


def summarise(feature: dict[str, Any]) -> dict[str, Any]:
    props = feature["properties"]
    return {
        "storeId": props.get("store_id"),
        "name": props.get("name"),
        "city": (props.get("address") or {}).get("city"),
        "distance_m": props.get("distance"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    origin = parser.add_mutually_exclusive_group(required=True)
    origin.add_argument("--origin", help="lat,lng")
    origin.add_argument("--address", help="address to geocode with Localities")
    parser.add_argument("--country", help="ISO country code to restrict geocoding, e.g. fr")
    parser.add_argument(
        "--value", type=int, default=20, help="minutes (method time) or km (method distance)"
    )
    parser.add_argument("--method", choices=("time", "distance"), default="time")
    parser.add_argument("--mode", default="driving", help="driving, walking or cycling")
    parser.add_argument("--query", help='optional Stores API query, e.g. type:"grocery"')
    parser.add_argument("--json", action="store_true", help="print the matching GeoJSON features")
    return parser


def parse_latlng(text: str) -> LatLng:
    lat, lng = (float(part) for part in text.split(","))
    return lat, lng


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api = Woosmap(private_key_from_env())
    origin = parse_latlng(args.origin) if args.origin else api.geocode(args.address, args.country)
    polygon = api.isochrone(origin, args.value, args.method, args.mode)
    matches = stores_within(api, origin, polygon, args.query)
    matches.sort(key=lambda f: f["properties"].get("distance", 0))
    if args.json:
        print(json.dumps({"type": "FeatureCollection", "features": matches}, indent=2))
    else:
        for store in map(summarise, matches):
            print(f"{store['storeId']}\t{store['name']}\t{store['city']}\t{store['distance_m']}")
    print(f"{len(matches)} stores within the isochrone", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
