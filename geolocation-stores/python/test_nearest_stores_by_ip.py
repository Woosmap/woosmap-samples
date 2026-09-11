import nearest_stores_by_ip as mod
import pytest
import requests
import responses


def body(**extra):
    return {
        "city": "Paris",
        "country_name": "France",
        "accuracy": 5,
        "stores": {
            "features": [
                {"properties": {"store_id": "a", "name": "Shop A", "distance": 1200}},
            ]
        },
        **extra,
    }


@responses.activate
def test_locate_passes_ip_and_optional_params_only_when_set():
    responses.get(mod.API_URL, json=body())
    mod.locate(requests.Session(), "k", "1.2.3.4", limit=3, radius=None, query=None)
    params = responses.calls[0].request.params
    assert params["ip_address"] == "1.2.3.4"
    assert params["limit"] == "3"
    assert "radius" not in params


@responses.activate
def test_locate_raises_on_error():
    responses.get(mod.API_URL, status=403, body='{"detail":"denied"}')
    with pytest.raises(RuntimeError, match="denied"):
        mod.locate(requests.Session(), "k", "1.2.3.4")


def test_describe_location_includes_city_country_and_accuracy():
    assert mod.describe_location(body()) == "Paris, France (accuracy 5 km)"


def test_store_lines_are_tab_separated():
    assert mod.store_lines(body()) == ["a\tShop A\t1200"]


def test_store_lines_empty_when_no_stores_key():
    assert mod.store_lines({"city": "Paris"}) == []


@responses.activate
def test_main_prints_location_and_stores(capsys, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(mod.API_URL, json=body())
    assert mod.main(["1.2.3.4", "--limit", "1"]) == 0
    out = capsys.readouterr().out
    assert "Paris, France" in out
    assert "Shop A" in out
