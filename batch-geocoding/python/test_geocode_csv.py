import csv
from pathlib import Path

import geocode_csv as mod
import requests
import responses

DATA = Path(__file__).resolve().parents[2] / "data"


def options(**overrides):
    base = dict(
        address_columns=["addressline1", "postalcode", "town"],
        country_column="IsoCode",
        country=None,
        reverse=False,
        lat_column="lat",
        lng_column="lng",
        language=None,
        delay=0.0,
    )
    return mod.Options(**{**base, **overrides})


def geocode_body(lat=48.8, lng=2.3, location_type="ROOFTOP"):
    return {
        "results": [
            {
                "public_id": "abc",
                "types": ["address"],
                "formatted_address": "1 Rue de Rivoli, 75001 Paris",
                "geometry": {"location": {"lat": lat, "lng": lng}, "location_type": location_type},
            }
        ]
    }


def test_address_joins_non_empty_columns_in_order():
    row = {"addressline1": "20 Jull Street", "postalcode": "", "town": "Armadale"}
    assert (
        mod.address_from(row, ["addressline1", "postalcode", "town"]) == "20 Jull Street, Armadale"
    )


def test_forward_params_include_country_component_from_column():
    params = mod.params_for({"addressline1": "x", "IsoCode": "AU"}, options())
    assert params == {"address": "x", "components": "country:au"}


def test_fixed_country_and_language_are_passed():
    params = mod.params_for(
        {"addressline1": "x"}, options(country_column=None, country="FR", language="fr")
    )
    assert params == {"address": "x", "components": "country:fr", "language": "fr"}


def test_reverse_params_use_latlng():
    params = mod.params_for({"lat": "48.8", "lng": "2.3"}, options(reverse=True))
    assert params == {"latlng": "48.8,2.3"}


def test_first_result_extracts_the_output_columns():
    result = mod.first_result(geocode_body())
    assert result["geocode_lat"] == "48.8"
    assert result["geocode_location_type"] == "ROOFTOP"
    assert result["geocode_public_id"] == "abc"
    assert result["geocode_error"] == ""


def test_empty_results_flag_zero_results():
    assert mod.first_result({"results": []}) == {"geocode_error": "ZERO_RESULTS"}


def test_empty_address_is_reported_without_calling_the_api():
    row = mod.geocode_row(mod.Geocoder("k"), {"addressline1": ""}, options(country_column=None))
    assert row["geocode_error"] == "empty address"


@responses.activate
def test_geocode_row_appends_result_columns():
    responses.get(mod.API_URL, json=geocode_body())
    row = mod.geocode_row(
        mod.Geocoder("k"), {"addressline1": "1 rue de Rivoli", "IsoCode": "FR"}, options()
    )
    assert row["geocode_formatted_address"] == "1 Rue de Rivoli, 75001 Paris"
    assert responses.calls[0].request.params["private_key"] == "k"
    assert responses.calls[0].request.params["components"] == "country:fr"


@responses.activate
def test_http_errors_land_in_the_error_column(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    for _ in range(3):
        responses.get(mod.API_URL, status=429, body="slow down")
    row = mod.geocode_row(mod.Geocoder("k"), {"addressline1": "x"}, options(country_column=None))
    assert row["geocode_error"].startswith("HTTP 429")
    assert len(responses.calls) == 3


@responses.activate
def test_server_errors_are_not_retried():
    responses.get(mod.API_URL, status=502, body="gateway")
    row = mod.geocode_row(mod.Geocoder("k"), {"addressline1": "x"}, options(country_column=None))
    assert row["geocode_error"].startswith("HTTP 502")
    assert len(responses.calls) == 1


def test_reads_semicolon_fixture_with_header():
    fieldnames, rows = mod.read_rows(DATA / "addresses_au.csv")
    assert fieldnames[:2] == ["country", "name"]
    assert rows[0]["town"] == "Ipswich"


@responses.activate
def test_main_writes_input_columns_plus_geocode_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(mod.API_URL, json=geocode_body())
    output = tmp_path / "out.csv"
    code = mod.main(
        [
            str(DATA / "coordinates.csv"),
            str(output),
            "--reverse",
        ]
    )
    assert code == 0
    with output.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["id"] == "markthalrotterdam"
    assert rows[0]["geocode_lat"] == "48.8"
    assert responses.calls[0].request.params["latlng"] == "51.919948,4.486843"


def test_rate_limit_delay_prefers_the_ratelimit_header_over_legacy_ones():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    response.headers["ratelimit-reset"] = "2"
    assert mod.retry_delay(response, 0) == 9.0
