"""Compute a large distance matrix with the asynchronous Distance API and save it as CSV."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api.woosmap.com/distance/matrix/async/"
FINAL_STATUSES = {"completed", "timeout", "error"}
OUTPUT_COLUMNS = ["origin_index", "destination_index", "status", "distance_m", "duration_s"]


def retry_delay(response: requests.Response, attempt: int) -> float:
    # Woosmap sends ratelimit-reset, in seconds; Retry-After only comes from proxies
    for header in ("ratelimit-reset", "Retry-After"):
        try:
            return max(0.0, float(response.headers[header]))
        except (KeyError, ValueError):
            continue
    return float(2**attempt)


def read_points(path: Path) -> list[str]:
    points: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        cells = [cell.strip() for cell in line.replace(";", ",").split(",")]
        if len(cells) < 2 or not cells[0] or not cells[1]:
            continue
        try:
            float(cells[0]), float(cells[1])
        except ValueError:
            continue
        points.append(f"{cells[0]},{cells[1]}")
    if not points:
        raise ValueError(f"no coordinates found in {path}")
    return points


class AsyncMatrix:
    def __init__(self, private_key: str, session: requests.Session | None = None) -> None:
        self.private_key = private_key
        self.session = session or requests.Session()

    def _call(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        for attempt in range(3):
            response = self.session.request(
                method, url, params={"private_key": self.private_key}, timeout=60, **kwargs
            )
            if response.status_code != 429 or attempt == 2:
                break
            time.sleep(retry_delay(response, attempt))
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {url} failed ({response.status_code}): {response.text}")
        return response

    def submit(self, origins: list[str], destinations: list[str], **options: str) -> str:
        body = {"origins": "|".join(origins), "destinations": "|".join(destinations), **options}
        return self._call("POST", API_URL, json=body).json()["matrix_id"]

    def status(self, matrix_id: str) -> str:
        return self._call("GET", f"{API_URL}{matrix_id}/status").json()["status"]

    def result(self, matrix_id: str) -> dict[str, Any]:
        return self._call("GET", f"{API_URL}{matrix_id}").json()

    def wait(self, matrix_id: str, interval: float, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        while True:
            status = self.status(matrix_id)
            print(f"{matrix_id}: {status}", file=sys.stderr)
            if status in FINAL_STATUSES:
                return status
            if time.monotonic() >= deadline:
                raise TimeoutError(f"matrix {matrix_id} still {status} after {timeout}s")
            time.sleep(interval)


def flatten(result: dict[str, Any]) -> list[dict[str, Any]]:
    # The async result is not the synchronous rows/elements shape: travelTimes and distances
    # are flat row-major arrays, errorCodes is present only when some pairs failed.
    matrix = result.get("matrix") or {}
    destinations = matrix.get("numDestinations") or 0
    times, distances = matrix.get("travelTimes") or [], matrix.get("distances") or []
    errors = matrix.get("errorCodes") or []
    rows: list[dict[str, Any]] = []
    for index in range(matrix.get("numOrigins", 0) * destinations):
        error = errors[index] if index < len(errors) else 0
        rows.append(
            {
                "origin_index": index // destinations,
                "destination_index": index % destinations,
                "status": "OK" if not error else f"ERROR_{error}",
                "distance_m": distances[index] if index < len(distances) and not error else "",
                "duration_s": times[index] if index < len(times) and not error else "",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="CSV to write, one row per origin/destination pair"
    )
    parser.add_argument("--origins", type=Path, help="CSV with one lat,lng per line")
    parser.add_argument("--destinations", type=Path, help="CSV with one lat,lng per line")
    parser.add_argument("--matrix-id", help="resume polling a job submitted earlier instead")
    parser.add_argument(
        "--mode", default="driving", help="driving (default), walking, cycling or truck"
    )
    parser.add_argument("--method", choices=("time", "distance"), default="time")
    parser.add_argument("--elements", default="duration_distance")
    parser.add_argument(
        "--poll-interval", type=float, default=5.0, help="seconds between status checks"
    )
    parser.add_argument("--timeout", type=float, default=1800.0, help="seconds before giving up")
    return parser


def private_key_from_env() -> str:
    key = os.environ.get("WOOSMAP_PRIVATE_KEY")
    if not key:
        raise SystemExit("set WOOSMAP_PRIVATE_KEY in the environment")
    return key


def submit_from_files(api: AsyncMatrix, args: argparse.Namespace) -> str:
    if not (args.origins and args.destinations):
        raise SystemExit("pass --origins and --destinations, or --matrix-id to resume a job")
    origins, destinations = read_points(args.origins), read_points(args.destinations)
    matrix_id = api.submit(
        origins, destinations, mode=args.mode, method=args.method, elements=args.elements
    )
    # the job outlives this process: keep the id to resume with --matrix-id if polling is cut
    print(f"submitted {len(origins)}x{len(destinations)} matrix {matrix_id}", file=sys.stderr)
    return matrix_id


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api = AsyncMatrix(private_key_from_env())
    matrix_id = args.matrix_id or submit_from_files(api, args)
    status = api.wait(matrix_id, args.poll_interval, args.timeout)
    if status != "completed":
        print(f"matrix {matrix_id} ended with status {status}", file=sys.stderr)
        return 1
    rows = flatten(api.result(matrix_id))
    write_csv(args.output, rows)
    print(f"wrote {len(rows)} elements to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
