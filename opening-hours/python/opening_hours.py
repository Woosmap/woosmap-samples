"""Convert tabular opening hours (one column per weekday) into the Woosmap openingHours object."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

DAY_COLUMNS = {
    "monday": "1",
    "tuesday": "2",
    "wednesday": "3",
    "thursday": "4",
    "friday": "5",
    "saturday": "6",
    "sunday": "7",
}
CLOSED_WORDS = {"", "closed", "close", "ferme", "fermé", "-", "x"}
ALL_DAY_WORDS = {"24/7", "all-day", "allday", "24h", "24h/24", "open 24 hours"}
SLICE_PATTERN = re.compile(r"^(\d{1,2})[:h](\d{2})\s*-\s*(\d{1,2})[:h](\d{2})$")

Slices = list[dict[str, Any]]


class HoursError(ValueError):
    pass


@dataclass
class Conversion:
    hours: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def parse_time(hours: str, minutes: str) -> str:
    hour, minute = int(hours), int(minutes)
    if hour > 23 or minute > 59:
        raise HoursError(f"invalid time {hours}:{minutes}")
    return f"{hour:02d}:{minute:02d}"


def parse_slice(text: str) -> dict[str, str]:
    match = SLICE_PATTERN.match(text.strip())
    if not match:
        raise HoursError(f"cannot read time slice {text!r}, expected HH:MM-HH:MM")
    start, end = parse_time(match[1], match[2]), parse_time(match[3], match[4])
    # end before start is a slice crossing midnight, which the Stores API accepts as is
    if start == end:
        raise HoursError(f"slice {text!r} starts and ends at the same time")
    return {"start": start, "end": end}


def parse_cell(text: str) -> Slices:
    lowered = text.strip().lower()
    if lowered in CLOSED_WORDS:
        return []
    if lowered in ALL_DAY_WORDS:
        return [{"all-day": True}]
    return [parse_slice(part) for part in re.split(r"[,;]", text) if part.strip()]


def weekly_hours(row: dict[str, str]) -> dict[str, Slices]:
    per_day = {key: parse_cell(row.get(column, "")) for column, key in DAY_COLUMNS.items()}
    values = list(per_day.values())
    if all(value == values[0] for value in values):
        return {"default": values[0]}
    return per_day


def parse_iso_date(text: str) -> str:
    try:
        return date.fromisoformat(text.strip()).isoformat()
    except ValueError as error:
        raise HoursError(f"invalid date {text!r}, expected YYYY-MM-DD") from error


def parse_closure(row: dict[str, str]) -> dict[str, str]:
    start, end = parse_iso_date(row["start"]), parse_iso_date(row["end"])
    if end < start:
        raise HoursError(f"closure ends ({end}) before it starts ({start})")
    return {"start": start, "end": end}


def convert(
    hours_rows: list[dict[str, str]],
    special_rows: list[dict[str, str]],
    closure_rows: list[dict[str, str]],
    default_timezone: str | None,
) -> Conversion:
    result = Conversion()
    for index, row in enumerate(hours_rows, start=2):
        try:
            result.hours[row["store_id"]] = base_hours(row, default_timezone)
        except (HoursError, KeyError) as error:
            result.errors.append(f"hours row {index}: {error}")
    add_special(result, special_rows)
    add_closures(result, closure_rows)
    return result


def base_hours(row: dict[str, str], default_timezone: str | None) -> dict[str, Any]:
    timezone = row.get("timezone", "").strip() or default_timezone
    if not timezone:
        raise HoursError("no timezone column and no --timezone default")
    return {"timezone": timezone, "usual": weekly_hours(row)}


def add_special(result: Conversion, rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows, start=2):
        hours = result.hours.get(row.get("store_id", ""))
        if hours is None:
            result.errors.append(f"special row {index}: unknown store_id {row.get('store_id')!r}")
            continue
        try:
            hours.setdefault("special", {})[parse_iso_date(row["date"])] = parse_cell(row["hours"])
        except (HoursError, KeyError) as error:
            result.errors.append(f"special row {index}: {error}")


def add_closures(result: Conversion, rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows, start=2):
        hours = result.hours.get(row.get("store_id", ""))
        if hours is None:
            result.errors.append(f"closure row {index}: unknown store_id {row.get('store_id')!r}")
            continue
        try:
            hours.setdefault("temporary_closure", []).append(parse_closure(row))
        except (HoursError, KeyError) as error:
            result.errors.append(f"closure row {index}: {error}")


def merge_into_stores(stores: list[dict[str, Any]], hours: dict[str, dict[str, Any]]) -> int:
    merged = 0
    for store in stores:
        if store.get("storeId") in hours:
            store["openingHours"] = hours[store["storeId"]]
            merged += 1
    return merged


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            {k.strip(): (v or "").strip() for k, v in row.items() if k}
            for row in csv.DictReader(handle)
        ]


def load_stores_document(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"no such file: {path}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path} is not valid JSON: {error}") from None
    if not isinstance(document, dict) or not isinstance(document.get("stores"), list):
        raise SystemExit(f'{path} must be a JSON object with a "stores" array')
    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hours", type=Path, help="CSV: store_id, [timezone], monday … sunday")
    parser.add_argument("--special", type=Path, help="CSV: store_id, date, hours")
    parser.add_argument("--closures", type=Path, help="CSV: store_id, start, end")
    parser.add_argument("--timezone", help="fallback IANA timezone when the CSV has none")
    parser.add_argument("--merge", type=Path, help="Woosmap JSON file to inject openingHours into")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strict", action="store_true", help="fail if any row is invalid")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = convert(
        read_csv(args.hours), read_csv(args.special), read_csv(args.closures), args.timezone
    )
    for error in result.errors:
        print(error, file=sys.stderr)
    if args.strict and result.errors:
        return 1
    document: dict[str, Any] = result.hours
    if args.merge:
        document = load_stores_document(args.merge)
        merged = merge_into_stores(document["stores"], result.hours)
        print(f"opening hours set on {merged} of {len(document['stores'])} stores", file=sys.stderr)
    args.output.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{len(result.hours)} stores converted, {len(result.errors)} errors", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
