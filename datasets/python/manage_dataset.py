"""Declare, import and query a Woosmap dataset built from a hosted zipped Shapefile."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.woosmap.com/datasets/"
FINAL_STATUSES = {"success", "failed"}
PAGE_SIZE = 20  # per_page maximum
OPERATORS = ("within", "intersects", "contains", "nearby")


class Datasets:
    def __init__(self, private_key: str, session: requests.Session | None = None) -> None:
        self.private_key = private_key
        self.session = session or requests.Session()

    def call(self, method: str, path: str = "", **kwargs: Any) -> dict[str, Any]:
        params = {"private_key": self.private_key, **kwargs.pop("params", {})}
        response = self.session.request(
            method, f"{API_URL}{path}", params=params, timeout=60, **kwargs
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"{method} {path or '/'} failed ({response.status_code}): {response.text}"
            )
        return response.json() if response.content else {}

    def create(self, name: str, url: str, title_key: str | None) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name, "url": url}
        if title_key:
            body["schema_mapping"] = [{"schema_key": "title", "data_key": title_key}]
        return self.call("POST", json=body)

    def list(self) -> list[dict[str, Any]]:
        return self.call("GET").get("datasets", [])

    def trigger_import(self, dataset_id: str) -> None:
        # rate limited to one import per dataset every 90 seconds
        self.call("POST", f"{dataset_id}/import")

    def status(self, dataset_id: str) -> dict[str, Any]:
        # 404 "No dataset status available" for a few seconds after the import is triggered
        response = self.session.get(
            f"{API_URL}{dataset_id}/status", params={"private_key": self.private_key}, timeout=60
        )
        if response.status_code == 404:
            return {"status": "pending", "steps": []}
        if response.status_code >= 400:
            raise RuntimeError(
                f"GET {dataset_id}/status failed ({response.status_code}): {response.text}"
            )
        return response.json()

    def wait(self, dataset_id: str, interval: float, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            status = self.status(dataset_id)
            print(describe_status(status), file=sys.stderr)
            if status.get("status") in FINAL_STATUSES:
                return status
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"dataset {dataset_id} still {status.get('status')} after {timeout}s"
                )
            time.sleep(interval)

    def query(
        self, dataset_id: str, operator: str, geometry: Any, where: str | None, buffer: float | None
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"geometry": geometry}
        if where:
            body["where"] = where
        if buffer is not None:
            body["buffer"] = buffer
        features: list[dict[str, Any]] = []
        page: int | None = 1
        while page:
            result = self.call(
                "POST",
                f"{dataset_id}/features/{operator}/",
                params={"page": page, "per_page": PAGE_SIZE},
                json=body,
            )
            features.extend(result.get("features", []))
            page = (result.get("pagination") or {}).get("next")
        return features


def describe_status(status: dict[str, Any]) -> str:
    steps = ", ".join(f"{step['name']}={step.get('status')}" for step in status.get("steps", []))
    return f"{status.get('status')} [{steps}]"


def load_geometry(text: str) -> Any:
    if text.startswith("@"):
        document = json.loads(Path(text[1:]).read_text(encoding="utf-8"))
        return document.get("geometry", document)
    # the spec accepts a bare "lat,lng" but the API matches nothing with it, WKT does
    parts = text.split(",")
    if len(parts) == 2 and all(is_number(part) for part in parts):
        return f"POINT({parts[1].strip()} {parts[0].strip()})"
    return text


def is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="declare a dataset from a hosted zipped Shapefile")
    create.add_argument("--name", required=True)
    create.add_argument("--url", required=True, help="public URL of the .zip Shapefile")
    create.add_argument("--title-key", help="attribute to expose as the feature title")
    commands.add_parser("list", help="list datasets of the project")
    imp = commands.add_parser("import", help="trigger an import and optionally wait for it")
    imp.add_argument("dataset_id")
    imp.add_argument("--wait", action="store_true")
    imp.add_argument("--poll-interval", type=float, default=10.0)
    imp.add_argument("--timeout", type=float, default=1800.0)
    status = commands.add_parser("status", help="show the last import status")
    status.add_argument("dataset_id")
    query = commands.add_parser("query", help="run a spatial query")
    query.add_argument("dataset_id")
    query.add_argument("--operator", choices=OPERATORS, default="within")
    query.add_argument(
        "--geometry",
        required=True,
        help="WKT, lat,lng or @file.geojson holding a Feature or a geometry",
    )
    query.add_argument("--where", help="attribute filter, e.g. population:>1000")
    query.add_argument("--buffer", type=float, help="buffer applied to the geometry, in metres")
    return parser


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def run(api: Datasets, args: argparse.Namespace) -> Any:
    if args.command == "create":
        return api.create(args.name, args.url, args.title_key)
    if args.command == "list":
        return api.list()
    if args.command == "status":
        return api.status(args.dataset_id)
    if args.command == "import":
        api.trigger_import(args.dataset_id)
        return (
            api.wait(args.dataset_id, args.poll_interval, args.timeout)
            if args.wait
            else {"scheduled": True}
        )
    return api.query(
        args.dataset_id, args.operator, load_geometry(args.geometry), args.where, args.buffer
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run(Datasets(private_key_from_env()), args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.command == "import" and args.wait and result.get("status") != "success":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
