import pytest
import requests
import responses
import static_map as mod


def test_parse_marker_with_and_without_icon():
    assert mod.parse_marker("48.8,2.3") == {"lat": 48.8, "lng": 2.3}
    assert mod.parse_marker("48.8, 2.3, https://x/y.png") == {
        "lat": 48.8,
        "lng": 2.3,
        "url": "https://x/y.png",
    }


def test_parse_marker_rejects_single_value():
    with pytest.raises(ValueError):
        mod.parse_marker("48.8")


def test_build_params_repeats_markers_as_compact_json():
    args = mod.build_parser().parse_args(
        ["--lat", "1", "--lng", "2", "--marker", "1,2", "--marker", "3,4,https://i.png", "--retina"]
    )
    params = mod.build_params(args)
    assert ("retina", "true") in params
    assert [v for k, v in params if k == "markers"] == [
        '{"lat":1.0,"lng":2.0}',
        '{"lat":3.0,"lng":4.0,"url":"https://i.png"}',
    ]


@responses.activate
def test_fetch_image_returns_image_bytes():
    responses.get(mod.API_URL, body=b"\x89PNG", content_type="image/png")
    png = mod.fetch_image(requests.Session(), "k", [("lat", "1")])
    assert png == b"\x89PNG"
    assert responses.calls[0].request.params["private_key"] == "k"


@responses.activate
def test_fetch_image_rejects_non_image_response():
    responses.get(mod.API_URL, json={"detail": "oops"})
    with pytest.raises(RuntimeError, match="unexpected content type"):
        mod.fetch_image(requests.Session(), "k", [])


@responses.activate
def test_fetch_image_raises_on_http_error():
    responses.get(mod.API_URL, status=401, body='{"detail":"bad key"}')
    with pytest.raises(RuntimeError, match="bad key"):
        mod.fetch_image(requests.Session(), "k", [])


@responses.activate
def test_fetch_image_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    responses.get(mod.API_URL, status=429, headers={"Retry-After": "0"})
    responses.get(mod.API_URL, body=b"img", content_type="image/png")
    assert mod.fetch_image(requests.Session(), "k", []) == b"img"


@responses.activate
def test_fetch_image_does_not_retry_server_errors():
    responses.get(mod.API_URL, status=503, body="down")
    with pytest.raises(RuntimeError, match="down"):
        mod.fetch_image(requests.Session(), "k", [])
    assert len(responses.calls) == 1


def test_public_url_never_contains_the_private_key():
    url = mod.public_url([("lat", "1"), ("lng", "2")])
    assert url.startswith(mod.API_URL)
    assert "key=YOUR_PUBLIC_KEY" in url


@responses.activate
def test_main_writes_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(mod.API_URL, body=b"img", content_type="image/png")
    output = tmp_path / "m.webp"
    assert mod.main(["--lat", "1", "--lng", "2", "--output", str(output)]) == 0
    assert output.read_bytes() == b"img"
