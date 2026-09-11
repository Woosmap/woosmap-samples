"""Synchronise a Woosmap project with a Woosmap JSON file, changing only what differs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.woosmap.com"
PAGE_SIZE = 300  # stores_by_page maximum

Asset = dict[str, Any]


@dataclass
class Plan:
    create: list[Asset] = field(default_factory=list)
    update: list[Asset] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.create or self.update or self.delete)


class WoosmapStores:
    def __init__(self, private_key: str, session: requests.Session | None = None) -> None:
        self.private_key = private_key
        self.session = session or requests.Session()

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        params = {"private_key": self.private_key, **kwargs.pop("params", {})}
        for attempt in range(3):
            response = self.session.request(
                method, f"{API_URL}{path}", params=params, timeout=120, **kwargs
            )
            if response.status_code != 429 or attempt == 2:
                break
            # 429 is the only status the API asks to retry, and Retry-After says when
            time.sleep(float(response.headers.get("Retry-After", 2**attempt)))
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {path} failed ({response.status_code}): {response.text}")
        return response.json()

    def fetch_all(self) -> list[dict[str, Any]]:
        features: list[dict[str, Any]] = []
        page = 1
        while True:
            body = self.request(
                "GET", "/stores/search", params={"stores_by_page": PAGE_SIZE, "page": page}
            )
            features.extend(body.get("features", []))
            pagination = body.get("pagination", {})
            if page >= pagination.get("pageCount", 1):
                return features
            page += 1

    def create(self, stores: list[Asset]) -> None:
        self.request("POST", "/stores", json={"stores": stores})

    def update(self, stores: list[Asset]) -> None:
        self.request("PUT", "/stores", json={"stores": stores})

    def delete(self, store_ids: list[str]) -> None:
        self.request("DELETE", "/stores", params={"query": delete_query(store_ids)})


def delete_query(store_ids: list[str]) -> str:
    # idstore is the query-language name of storeId
    return " OR ".join(f'idstore:="{store_id}"' for store_id in store_ids)


def feature_to_asset(feature: dict[str, Any]) -> Asset:
    props = feature["properties"]
    lng, lat = feature["geometry"]["coordinates"]
    address = props.get("address") or {}
    return {
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


def normalise(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {k: normalise(v) for k, v in value.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, {}, [], "")}
    if isinstance(value, list):
        items = [normalise(v) for v in value]
        return sorted(items, key=json.dumps) if all(isinstance(i, str) for i in items) else items
    if isinstance(value, float):
        return round(value, 6)
    return value


def without_expired_closures(asset: Asset, today: date | None = None) -> Asset:
    # the Stores API drops temporary closures once they have ended
    hours = asset.get("openingHours") or {}
    closures = hours.get("temporary_closure")
    if not closures:
        return asset
    limit = (today or date.today()).isoformat()
    kept = [closure for closure in closures if closure.get("end", "") >= limit]
    return {**asset, "openingHours": {**hours, "temporary_closure": kept}}


def same_asset(local: Asset, remote: Asset) -> bool:
    left = json.dumps(normalise(without_expired_closures(local)), sort_keys=True)
    right = json.dumps(normalise(without_expired_closures(remote)), sort_keys=True)
    return left == right


def load_local_assets(path: Path) -> list[Asset]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"no such file: {path}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path} is not valid JSON: {error}") from None
    stores = document.get("stores") if isinstance(document, dict) else None
    if stores is None:
        raise SystemExit(f'{path} must be a JSON object with a "stores" array')
    without_id = [index for index, asset in enumerate(stores, start=1) if not asset.get("storeId")]
    if without_id:
        raise SystemExit(f"stores without a storeId at position {without_id[:5]}")
    return stores


def build_plan(local_assets: list[Asset], remote_features: list[dict[str, Any]]) -> Plan:
    local = {asset["storeId"]: asset for asset in local_assets}
    remote = {asset["storeId"]: asset for asset in map(feature_to_asset, remote_features)}
    plan = Plan()
    for store_id, asset in local.items():
        if store_id not in remote:
            plan.create.append(asset)
        elif not same_asset(asset, remote[store_id]):
            plan.update.append(asset)
    plan.delete = sorted(set(remote) - set(local))
    return plan


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def apply_plan(api: WoosmapStores, plan: Plan, batch_size: int, allow_delete: bool) -> None:
    for batch in chunked(plan.create, batch_size):
        api.create(batch)
        print(f"created {len(batch)}")
    for batch in chunked(plan.update, batch_size):
        api.update(batch)
        print(f"updated {len(batch)}")
    if not allow_delete:
        return
    for batch in chunked(plan.delete, 50):
        api.delete(batch)
        print(f"deleted {len(batch)}")


def describe(plan: Plan) -> str:
    return (
        f"{len(plan.create)} to create, {len(plan.update)} to update, {len(plan.delete)} to delete"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help='Woosmap JSON file: {"stores": [...]}')
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--no-delete", action="store_true", help="never delete remote stores")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    return parser


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    local_assets = load_local_assets(args.source)
    api = WoosmapStores(private_key_from_env())
    plan = build_plan(local_assets, api.fetch_all())
    print(describe(plan))
    for store_id in plan.delete:
        print(f"  delete {store_id}")
    if args.dry_run or plan.is_empty():
        return 0
    apply_plan(api, plan, args.batch_size, allow_delete=not args.no_delete)
    return 0


if __name__ == "__main__":
    sys.exit(main())
