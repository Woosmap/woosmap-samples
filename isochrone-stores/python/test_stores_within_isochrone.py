import pytest
import responses
import stores_within_isochrone as mod

# Google's documented polyline example
EXAMPLE_POLYLINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
SQUARE = [(48.0, 2.0), (48.0, 3.0), (49.0, 3.0), (49.0, 2.0)]


def test_decode_polyline_matches_reference_points():
    assert mod.decode_polyline(EXAMPLE_POLYLINE) == [
        (38.5, -120.2),
        (40.7, -120.95),
        (43.252, -126.453),
    ]


def test_haversine_paris_to_london_is_about_344_km():
    assert mod.haversine_m((48.8566, 2.3522), (51.5074, -0.1278)) == pytest.approx(
        343_500, rel=0.01
    )


def test_point_in_polygon_inside_and_outside():
    assert mod.point_in_polygon((48.5, 2.5), SQUARE)
    assert not mod.point_in_polygon((47.5, 2.5), SQUARE)
    assert not mod.point_in_polygon((48.5, 3.5), SQUARE)


def test_covering_radius_wraps_the_farthest_vertex():
    origin = (48.5, 2.5)
    radius = mod.covering_radius_m(origin, SQUARE)
    farthest = max(mod.haversine_m(origin, v) for v in SQUARE)
    assert radius > farthest


def feature(store_id, lat, lng, distance=0):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"store_id": store_id, "name": store_id, "distance": distance},
    }


@responses.activate
def test_stores_within_keeps_only_features_inside_the_polygon():
    responses.get(
        f"{mod.API_URL}/stores/search",
        json={"features": [feature("in", 48.5, 2.5), feature("out", 47.0, 2.5)], "pagination": {}},
    )
    matches = mod.stores_within(mod.Woosmap("k"), (48.5, 2.5), SQUARE, 'type:"grocery"')
    assert [f["properties"]["store_id"] for f in matches] == ["in"]
    params = responses.calls[0].request.params
    assert params["query"] == 'type:"grocery"'
    assert params["stores_by_page"] == "300"


@responses.activate
def test_geocode_returns_first_result_location():
    responses.get(
        f"{mod.API_URL}/localities/geocode/",
        json={"results": [{"geometry": {"location": {"lat": 48.8, "lng": 2.3}}}]},
    )
    assert mod.Woosmap("k").geocode("Paris", "fr") == (48.8, 2.3)
    assert responses.calls[0].request.params["components"] == "country:fr"


@responses.activate
def test_geocode_without_results_raises():
    responses.get(f"{mod.API_URL}/localities/geocode/", json={"results": []})
    with pytest.raises(RuntimeError, match="no geocoding result"):
        mod.Woosmap("k").geocode("nowhere", None)


@responses.activate
def test_distance_api_errors_carry_the_status_despite_http_200():
    responses.get(
        f"{mod.API_URL}/distance/isochrone/json/",
        json={
            "status": "INVALID_REQUEST",
            "message": "value: Input should be less than or equal to 120",
        },
    )
    with pytest.raises(RuntimeError, match="INVALID_REQUEST: value"):
        mod.Woosmap("k").isochrone((48.8, 2.3), 300, "time", "driving")


@responses.activate
def test_stores_search_has_no_status_field_and_still_works():
    responses.get(f"{mod.API_URL}/stores/search", json={"features": [], "pagination": {}})
    assert mod.Woosmap("k").stores_around((48.8, 2.3), 1000, None) == []


@responses.activate
def test_get_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    responses.get(f"{mod.API_URL}/stores/search", status=429, headers={"Retry-After": "0"})
    responses.get(f"{mod.API_URL}/stores/search", json={"features": [], "pagination": {}})
    assert mod.Woosmap("k").stores_around((48.8, 2.3), 1000, None) == []


@responses.activate
def test_get_does_not_retry_server_errors():
    responses.get(f"{mod.API_URL}/stores/search", status=503, body="down")
    with pytest.raises(RuntimeError, match="down"):
        mod.Woosmap("k").stores_around((48.8, 2.3), 1000, None)
    assert len(responses.calls) == 1


@responses.activate
def test_isochrone_decodes_the_isoline_geometry():
    responses.get(
        f"{mod.API_URL}/distance/isochrone/json/",
        json={"status": "OK", "isoline": {"geometry": EXAMPLE_POLYLINE}},
    )
    polygon = mod.Woosmap("k").isochrone((38.5, -120.2), 20, "time", "driving")
    assert polygon[0] == (38.5, -120.2)
    assert responses.calls[0].request.params["origin"] == "38.5,-120.2"


@responses.activate
def test_main_prints_matching_stores(capsys, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(
        f"{mod.API_URL}/distance/isochrone/json/",
        json={"isoline": {"geometry": EXAMPLE_POLYLINE}},
    )
    responses.get(
        f"{mod.API_URL}/stores/search",
        json={
            "features": [feature("far", 0.0, 0.0, 10), feature("near", 40.0, -122.0, 5)],
            "pagination": {},
        },
    )
    assert mod.main(["--origin", "40.0,-122.0", "--value", "30"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("near\t")
    assert "far" not in out
