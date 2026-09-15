import json
from datetime import date
from pathlib import Path

import pytest
import requests
import responses
import sync_stores as mod

DATA = Path(__file__).resolve().parents[2] / "data"


def feature(store_id, name="Shop", lat=48.5, lng=2.0, **props):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"store_id": store_id, "name": name, **props},
    }


def asset(store_id, name="Shop", lat=48.5, lng=2.0, **extra):
    return {"storeId": store_id, "name": name, "location": {"lat": lat, "lng": lng}, **extra}


def test_feature_to_asset_maps_snake_case_to_request_fields():
    converted = mod.feature_to_asset(
        feature("a", address={"country_code": "FR", "city": "Paris"}, user_properties={"k": 1})
    )
    assert converted["address"]["countryCode"] == "FR"
    assert converted["userProperties"] == {"k": 1}
    assert converted["location"] == {"lat": 48.5, "lng": 2.0}


def test_identical_assets_compare_equal_despite_empty_fields_and_order():
    local = asset("a", types=["b", "a"], address={"city": "Paris", "lines": []})
    remote = mod.feature_to_asset(feature("a", types=["a", "b"], address={"city": "Paris"}))
    assert mod.same_asset(local, remote)


def test_coordinate_noise_beyond_six_decimals_is_ignored():
    assert mod.same_asset(asset("a", lat=48.5000000001), mod.feature_to_asset(feature("a")))


def test_expired_temporary_closures_are_ignored_in_the_comparison():
    hours = {
        "timezone": "Europe/Paris",
        "temporary_closure": [{"start": "2020-01-01", "end": "2020-01-05"}],
    }
    local = asset("a", openingHours=hours)
    remote = mod.feature_to_asset(
        feature("a", opening_hours={"timezone": "Europe/Paris", "temporary_closure": []})
    )
    assert mod.same_asset(local, remote)


def test_future_temporary_closures_still_count():
    pruned = mod.without_expired_closures(
        asset(
            "a", openingHours={"temporary_closure": [{"start": "2020-01-01", "end": "2999-01-01"}]}
        ),
        today=date(2026, 1, 1),
    )
    assert pruned["openingHours"]["temporary_closure"] == [
        {"start": "2020-01-01", "end": "2999-01-01"}
    ]


def test_loading_reports_bad_input_without_a_traceback(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(SystemExit, match="no such file"):
        mod.load_local_assets(missing)
    bare = tmp_path / "bare.json"
    bare.write_text('[{"storeId": "a"}]')
    with pytest.raises(SystemExit, match='"stores" array'):
        mod.load_local_assets(bare)
    no_id = tmp_path / "noid.json"
    no_id.write_text('{"stores": [{"name": "No id"}]}')
    with pytest.raises(SystemExit, match="without a storeId"):
        mod.load_local_assets(no_id)


def test_loading_accepts_the_food_markets_fixture():
    assert len(mod.load_local_assets(DATA / "foodmarkets.json")) == 18


def test_plan_splits_create_update_delete():
    local = [asset("keep"), asset("changed", name="New name"), asset("new")]
    remote = [feature("keep"), feature("changed"), feature("gone")]
    plan = mod.build_plan(local, remote)
    assert [a["storeId"] for a in plan.create] == ["new"]
    assert [a["storeId"] for a in plan.update] == ["changed"]
    assert plan.delete == ["gone"]


def test_chunked_rejects_a_batch_size_below_one():
    with pytest.raises(ValueError, match="1 or more"):
        mod.chunked([asset("a")], 0)


def test_batch_size_option_rejects_zero():
    with pytest.raises(SystemExit):
        mod.build_parser().parse_args(["stores.json", "--batch-size", "0"])


def test_delete_query_uses_or_clauses():
    assert mod.delete_query(["a", "b"]) == 'idstore:="a" OR idstore:="b"'


@responses.activate
def test_fetch_all_follows_pagination():
    url = f"{mod.API_URL}/stores/search"
    responses.get(url, json={"features": [feature("a")], "pagination": {"page": 1, "pageCount": 2}})
    responses.get(url, json={"features": [feature("b")], "pagination": {"page": 2, "pageCount": 2}})
    features = mod.WoosmapStores("k").fetch_all()
    assert [f["properties"]["store_id"] for f in features] == ["a", "b"]
    assert responses.calls[1].request.params["page"] == "2"
    assert responses.calls[1].request.params["stores_by_page"] == "300"


@responses.activate
def test_apply_plan_issues_expected_requests():
    responses.post(f"{mod.API_URL}/stores", json={})
    responses.put(f"{mod.API_URL}/stores", json={})
    responses.delete(f"{mod.API_URL}/stores", json={})
    plan = mod.Plan(create=[asset("n")], update=[asset("u")], delete=["d1", "d2"])
    mod.apply_plan(mod.WoosmapStores("k"), plan, batch_size=500, allow_delete=True)
    methods = [c.request.method for c in responses.calls]
    assert methods == ["POST", "PUT", "DELETE"]
    assert json.loads(responses.calls[1].request.body)["stores"][0]["storeId"] == "u"
    assert responses.calls[2].request.params["query"] == 'idstore:="d1" OR idstore:="d2"'


@responses.activate
def test_no_delete_skips_delete_requests():
    responses.post(f"{mod.API_URL}/stores", json={})
    plan = mod.Plan(create=[asset("n")], delete=["d"])
    mod.apply_plan(mod.WoosmapStores("k"), plan, batch_size=500, allow_delete=False)
    assert [c.request.method for c in responses.calls] == ["POST"]


@responses.activate
def test_api_errors_surface_with_body():
    responses.post(f"{mod.API_URL}/stores", status=400, body='{"detail":"nope"}')
    with pytest.raises(RuntimeError, match="nope"):
        mod.WoosmapStores("k").create([asset("x")])


def test_rate_limit_delay_prefers_the_ratelimit_header_over_legacy_ones():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    response.headers["ratelimit-reset"] = "2"
    assert mod.retry_delay(response, 0) == 9.0


def test_rate_limit_remaining_reads_ratelimit_then_the_legacy_header():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    assert mod.rate_limit_remaining(response) == 0
    del response.headers["RateLimit"]
    assert mod.rate_limit_remaining(response) is None


@responses.activate
def test_a_batch_pauses_on_its_own_once_the_quota_is_gone(monkeypatch):
    waits = []
    monkeypatch.setattr(mod.time, "sleep", waits.append)
    responses.post(f"{mod.API_URL}/stores", json={}, headers={"RateLimit": '"default";r=0;t=4'})
    responses.post(f"{mod.API_URL}/stores", json={})
    api = mod.WoosmapStores("k")
    api.create([asset("a")])
    api.create([asset("b")])
    assert waits == [4.0]
    assert len(responses.calls) == 2


@responses.activate
def test_main_dry_run_only_reads(monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(f"{mod.API_URL}/stores/search", json={"features": [], "pagination": {}})
    assert mod.main([str(DATA / "foodmarkets.json"), "--dry-run"]) == 0
    assert [c.request.method for c in responses.calls] == ["GET"]
