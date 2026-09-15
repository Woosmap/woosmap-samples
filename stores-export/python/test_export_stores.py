import json

import export_stores as mod
import pytest
import requests
import responses


def feature(store_id, **props):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [2.0, 48.5]},
        "properties": {"store_id": store_id, "name": "Shop", **props},
    }


def test_feature_to_asset_drops_empty_fields_and_renames_keys():
    asset = mod.feature_to_asset(
        feature("a", address={"country_code": "FR", "lines": []}, contact=None, tags=[])
    )
    assert asset == {
        "storeId": "a",
        "name": "Shop",
        "location": {"lat": 48.5, "lng": 2.0},
        "address": {"countryCode": "FR"},
    }


@responses.activate
def test_fetch_all_walks_every_page_and_passes_query():
    url = f"{mod.API_URL}/stores/search"
    responses.get(url, json={"features": [feature("a")], "pagination": {"pageCount": 2}})
    responses.get(url, json={"features": [feature("b")], "pagination": {"pageCount": 2}})
    features = mod.fetch_all(requests.Session(), "k", 'type:"grocery"')
    assert [f["properties"]["store_id"] for f in features] == ["a", "b"]
    assert responses.calls[0].request.params["query"] == 'type:"grocery"'


@responses.activate
def test_server_errors_fail_immediately_with_body():
    responses.get(f"{mod.API_URL}/stores/search", status=503, body="down")
    with pytest.raises(RuntimeError, match="down"):
        mod.fetch_all(requests.Session(), "k", None)
    assert len(responses.calls) == 1


@responses.activate
def test_rate_limit_is_retried_with_retry_after(monkeypatch):
    waits = []
    monkeypatch.setattr(mod.time, "sleep", waits.append)
    responses.get(f"{mod.API_URL}/stores/search", status=429, headers={"Retry-After": "7"})
    responses.get(f"{mod.API_URL}/stores/search", json={"features": []})
    assert mod.fetch_all(requests.Session(), "k", None) == []
    assert waits == [7.0]


@responses.activate
def test_main_writes_geojson_file(tmp_path, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(f"{mod.API_URL}/stores/search", json={"features": [feature("a")]})
    output = tmp_path / "stores.geojson"
    assert mod.main(["--format", "geojson", "--output", str(output)]) == 0
    document = json.loads(output.read_text())
    assert document["type"] == "FeatureCollection"
    assert document["features"][0]["properties"]["store_id"] == "a"


def test_rate_limit_delay_prefers_the_ratelimit_header_over_legacy_ones():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    response.headers["ratelimit-reset"] = "2"
    assert mod.retry_delay(response, 0) == 9.0
