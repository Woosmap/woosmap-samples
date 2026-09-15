import json
from pathlib import Path

import import_stores as mod
import pytest
import requests
import responses

DATA = Path(__file__).resolve().parents[2] / "data"


def test_row_to_asset_maps_default_columns():
    row = {
        "Name": "Markthal",
        "Latitude": "51.9",
        "Longitude": "4,48",
        "Address Line": "Dominee 298",
        "City": "Rotterdam",
        "Country Code": "nl",
        "Type": "covered|indoor",
    }
    asset = mod.row_to_asset(row, mod.DEFAULT_COLUMNS)
    assert asset == {
        "storeId": "Markthal",
        "name": "Markthal",
        "location": {"lat": 51.9, "lng": 4.48},
        "address": {"lines": ["Dominee 298"], "city": "Rotterdam", "countryCode": "NL"},
        "types": ["covered", "indoor"],
    }


def test_accents_are_transliterated_in_derived_ids():
    row = {"Name": "Le Grand Marché d'Apt", "Latitude": "1", "Longitude": "2"}
    assert mod.row_to_asset(row, mod.DEFAULT_COLUMNS)["storeId"] == "LeGrandMarchedApt"


def test_explicit_store_id_is_slugified():
    row = {"Store ID": "shop-12 a", "Name": "x", "Latitude": "1", "Longitude": "2"}
    assert mod.row_to_asset(row, mod.DEFAULT_COLUMNS)["storeId"] == "shop12a"


def test_missing_coordinates_are_reported_per_row():
    rows = [{"Name": "A", "Latitude": "", "Longitude": "2"}]
    result = mod.convert_rows(rows, mod.DEFAULT_COLUMNS)
    assert result.assets == []
    assert result.errors == ["row 2: invalid latitude ''"]


def test_duplicate_store_ids_are_rejected():
    rows = [
        {"Name": "Same", "Latitude": "1", "Longitude": "2"},
        {"Name": "Same", "Latitude": "3", "Longitude": "4"},
    ]
    result = mod.convert_rows(rows, mod.DEFAULT_COLUMNS)
    assert len(result.assets) == 1
    assert "duplicate storeId 'Same'" in result.errors[0]


def test_column_override_parsing():
    columns = mod.parse_column_overrides(["name=Shop name", "lat=Y"])
    assert columns["name"] == "Shop name"
    assert columns["lat"] == "Y"


def test_unknown_column_override_exits():
    with pytest.raises(SystemExit):
        mod.parse_column_overrides(["colour=Blue"])


def test_rate_limit_delay_prefers_the_ratelimit_reset_header():
    response = requests.Response()
    response.headers["ratelimit-reset"] = "7"
    response.headers["Retry-After"] = "99"
    assert mod.retry_delay(response, 0) == 7.0


def test_rate_limit_delay_falls_back_to_retry_after_then_to_backoff():
    response = requests.Response()
    response.headers["Retry-After"] = "4"
    assert mod.retry_delay(response, 0) == 4.0
    response.headers["Retry-After"] = "Wed, 21 Oct 2026 07:28:00 GMT"
    assert mod.retry_delay(response, 2) == 4.0
    del response.headers["Retry-After"]
    assert mod.retry_delay(response, 3) == 8.0


def test_rate_limit_delay_prefers_the_ratelimit_header_over_legacy_ones():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    response.headers["ratelimit-reset"] = "2"
    response.headers["Retry-After"] = "1"
    assert mod.retry_delay(response, 0) == 9.0


def test_rate_limit_delay_uses_the_exhausted_policy_even_when_not_first():
    response = requests.Response()
    response.headers["RateLimit"] = '"requests";r=5;t=1, "elements";r=0;t=30'
    assert mod.retry_delay(response, 0) == 30.0


def test_rate_limit_remaining_is_the_tightest_policy_even_when_not_first():
    response = requests.Response()
    response.headers["RateLimit"] = '"requests";r=5;t=1, "elements";r=0;t=30'
    assert mod.rate_limit_remaining(response) == 0


def test_rate_limit_remaining_reads_ratelimit_then_the_legacy_header():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    assert mod.rate_limit_remaining(response) == 0
    del response.headers["RateLimit"]
    response.headers["RateLimit-Remaining"] = "3"
    assert mod.rate_limit_remaining(response) == 3
    del response.headers["RateLimit-Remaining"]
    assert mod.rate_limit_remaining(response) is None


@responses.activate
def test_a_batch_pauses_on_its_own_once_the_quota_is_gone(monkeypatch):
    waits = []
    monkeypatch.setattr(mod.time, "sleep", waits.append)
    responses.post(
        f"{mod.API_URL}/stores", json={"status": "OK"}, headers={"RateLimit": '"default";r=0;t=4'}
    )
    responses.post(f"{mod.API_URL}/stores", json={"status": "OK"})
    api = mod.WoosmapStores("k")
    api.create([{"storeId": "a"}])
    api.create([{"storeId": "b"}])
    assert waits == [4.0]
    assert len(responses.calls) == 2


def test_chunked_rejects_a_batch_size_below_one():
    for size in (0, -1):
        with pytest.raises(ValueError, match="1 or more"):
            mod.chunked([{"storeId": "a"}], size)


def test_batch_size_option_rejects_zero_and_text():
    for value in ("0", "-3", "abc"):
        with pytest.raises(SystemExit):
            mod.build_parser().parse_args(["x.csv", "--batch-size", value])


@responses.activate
def test_replace_posts_all_stores_once():
    responses.post(f"{mod.API_URL}/stores/replace", json={"status": "OK"})
    api = mod.WoosmapStores("secret")
    mod.upload(api, [{"storeId": "a"}, {"storeId": "b"}], "replace", 1)
    assert len(responses.calls) == 1
    assert responses.calls[0].request.params["private_key"] == "secret"
    assert json.loads(responses.calls[0].request.body)["stores"][1]["storeId"] == "b"


@responses.activate
def test_create_mode_batches_requests():
    responses.post(f"{mod.API_URL}/stores", json={"status": "OK"})
    mod.upload(mod.WoosmapStores("k"), [{"storeId": str(i)} for i in range(5)], "create", 2)
    assert len(responses.calls) == 3


@responses.activate
def test_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    responses.post(f"{mod.API_URL}/stores", status=429, headers={"Retry-After": "0"})
    responses.post(f"{mod.API_URL}/stores", json={"status": "OK"})
    mod.WoosmapStores("k").create([{"storeId": "a"}])
    assert len(responses.calls) == 2


@responses.activate
def test_server_errors_are_not_retried():
    responses.post(f"{mod.API_URL}/stores", status=503, body="down")
    with pytest.raises(RuntimeError, match="down"):
        mod.WoosmapStores("k").create([{"storeId": "a"}])
    assert len(responses.calls) == 1


@responses.activate
def test_api_error_is_raised_with_body():
    responses.post(f"{mod.API_URL}/stores", status=400, body='{"detail":"bad storeId"}')
    with pytest.raises(RuntimeError, match="bad storeId"):
        mod.WoosmapStores("k").create([{"storeId": "a b"}])


def test_body_above_15mb_is_refused():
    api = mod.WoosmapStores("k")
    with pytest.raises(ValueError, match="15MB"):
        api.send("POST", "/stores", [{"storeId": "x" * (16 * 1024 * 1024)}])


@responses.activate
def test_main_dry_run_writes_json_and_skips_api(tmp_path):
    output = tmp_path / "stores.json"
    code = mod.main([str(DATA / "foodmarkets.csv"), "--dry-run", "--output", str(output)])
    assert code == 0
    assert len(json.loads(output.read_text())["stores"]) == 18
    assert len(responses.calls) == 0


def test_main_strict_fails_on_bad_rows(tmp_path):
    source = tmp_path / "bad.csv"
    source.write_text("Name,Latitude,Longitude\nA,,2\n")
    assert mod.main([str(source), "--dry-run", "--strict"]) == 1
