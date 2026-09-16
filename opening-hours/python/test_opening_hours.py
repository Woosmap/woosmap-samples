import json
from pathlib import Path

import opening_hours as mod
import pytest

DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.mark.parametrize("text", ["", "closed", "Fermé", "-"])
def test_closed_words_give_an_empty_day(text):
    assert mod.parse_cell(text) == []


@pytest.mark.parametrize("text", ["24/7", "all-day", "24h"])
def test_all_day_words(text):
    assert mod.parse_cell(text) == [{"all-day": True}]


def test_two_slices_with_flexible_separators_and_hours_format():
    assert mod.parse_cell("9h00-12h00; 14:00 - 19:00") == [
        {"start": "09:00", "end": "12:00"},
        {"start": "14:00", "end": "19:00"},
    ]


def test_overnight_slice_is_kept_as_is():
    assert mod.parse_cell("22:00-02:00") == [{"start": "22:00", "end": "02:00"}]


@pytest.mark.parametrize("text", ["25:00-26:00", "10:60-11:00", "10:00-10:00", "morning"])
def test_invalid_slices_raise(text):
    with pytest.raises(mod.HoursError):
        mod.parse_cell(text)


def test_identical_week_collapses_to_default():
    row = {day: "09:00-18:00" for day in mod.DAY_COLUMNS}
    assert mod.weekly_hours(row) == {"default": [{"start": "09:00", "end": "18:00"}]}


def test_varying_week_lists_every_day_with_numeric_keys():
    row = {day: "09:00-18:00" for day in mod.DAY_COLUMNS}
    row["sunday"] = "closed"
    hours = mod.weekly_hours(row)
    assert hours["7"] == []
    assert hours["1"] == [{"start": "09:00", "end": "18:00"}]
    assert "default" not in hours


def test_convert_uses_timezone_column_then_default():
    rows = [
        {"store_id": "a", "timezone": "Europe/Rome", "monday": "24/7"},
        {"store_id": "b", "monday": "24/7"},
    ]
    result = mod.convert(rows, [], [], "Europe/Paris")
    assert result.hours["a"]["timezone"] == "Europe/Rome"
    assert result.hours["b"]["timezone"] == "Europe/Paris"


def test_missing_timezone_is_an_error():
    result = mod.convert([{"store_id": "a", "monday": "24/7"}], [], [], None)
    assert result.hours == {}
    assert "no timezone" in result.errors[0]


def test_special_and_closures_attach_to_their_store():
    result = mod.convert(
        [{"store_id": "a", "timezone": "Europe/Paris", "monday": "09:00-18:00"}],
        [{"store_id": "a", "date": "2026-12-25", "hours": "closed"}],
        [{"store_id": "a", "start": "2026-08-01", "end": "2026-08-15"}],
        None,
    )
    assert result.hours["a"]["special"] == {"2026-12-25": []}
    assert result.hours["a"]["temporary_closure"] == [{"start": "2026-08-01", "end": "2026-08-15"}]


def test_special_for_unknown_store_and_bad_date_are_reported():
    result = mod.convert(
        [{"store_id": "a", "timezone": "Europe/Paris"}],
        [
            {"store_id": "zz", "date": "2026-12-25", "hours": ""},
            {"store_id": "a", "date": "25/12/2026", "hours": ""},
        ],
        [],
        None,
    )
    assert len(result.errors) == 2
    assert "unknown store_id 'zz'" in result.errors[0]
    assert "invalid date" in result.errors[1]


def test_closure_ending_before_start_is_rejected():
    result = mod.convert(
        [{"store_id": "a", "timezone": "Europe/Paris"}],
        [],
        [{"store_id": "a", "start": "2026-08-15", "end": "2026-08-01"}],
        None,
    )
    assert "before it starts" in result.errors[0]


def test_fixture_converts_without_errors():
    result = mod.convert(
        mod.read_csv(DATA / "opening_hours.csv"),
        mod.read_csv(DATA / "special_hours.csv"),
        mod.read_csv(DATA / "closures.csv"),
        None,
    )
    assert result.errors == []
    assert result.hours["allhours"]["usual"] == {"default": [{"all-day": True}]}
    assert result.hours["nightmarket"]["usual"]["4"] == [{"start": "18:00", "end": "02:00"}]
    assert result.hours["bistro"]["special"]["2026-12-31"] == [{"start": "18:00", "end": "01:00"}]


def test_merge_sets_opening_hours_on_matching_stores():
    stores = [{"storeId": "a"}, {"storeId": "b"}]
    assert mod.merge_into_stores(stores, {"a": {"timezone": "Europe/Paris"}}) == 1
    assert stores[0]["openingHours"] == {"timezone": "Europe/Paris"}
    assert "openingHours" not in stores[1]


def test_main_merges_into_the_food_markets_file(tmp_path):
    output = tmp_path / "stores.json"
    code = mod.main(
        [
            str(DATA / "opening_hours.csv"),
            "--merge",
            str(DATA / "foodmarkets.json"),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    stores = {s["storeId"]: s for s in json.loads(output.read_text())["stores"]}
    assert stores["markthalrotterdam"]["openingHours"]["usual"]["1"] == []


def test_merge_target_must_be_a_stores_document(tmp_path):
    bare = tmp_path / "bare.json"
    bare.write_text("[]")
    with pytest.raises(SystemExit, match='"stores" array'):
        mod.load_stores_document(bare)


def test_main_strict_fails_on_bad_rows(tmp_path):
    hours = tmp_path / "h.csv"
    hours.write_text("store_id,timezone,monday\na,Europe/Paris,noon\n")
    assert mod.main([str(hours), "--output", str(tmp_path / "o.json"), "--strict"]) == 1
