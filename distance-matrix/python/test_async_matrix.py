import csv

import async_matrix as mod
import pytest
import requests
import responses


def test_read_points_skips_header_and_blank_lines(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text("lat,lng\n48.8,2.3\n\n48.7;2.4\n")
    assert mod.read_points(path) == ["48.8,2.3", "48.7,2.4"]


def test_read_points_rejects_empty_file(tmp_path):
    path = tmp_path / "p.csv"
    path.write_text("lat,lng\n")
    with pytest.raises(ValueError):
        mod.read_points(path)


@responses.activate
def test_submit_posts_pipe_separated_points():
    responses.post(mod.API_URL, json={"matrix_id": "m1", "status": "accepted"})
    matrix_id = mod.AsyncMatrix("k").submit(["1,2", "3,4"], ["5,6"], mode="driving")
    assert matrix_id == "m1"
    body = responses.calls[0].request.body
    assert b'"origins": "1,2|3,4"' in body
    assert b'"destinations": "5,6"' in body
    assert responses.calls[0].request.params["private_key"] == "k"


@responses.activate
def test_wait_polls_until_completed(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    url = f"{mod.API_URL}m1/status"
    responses.get(url, json={"status": "accepted"})
    responses.get(url, json={"status": "inProgress"})
    responses.get(url, json={"status": "completed"})
    assert mod.AsyncMatrix("k").wait("m1", interval=0, timeout=60) == "completed"
    assert len(responses.calls) == 3


@responses.activate
def test_wait_gives_up_after_timeout(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    clock = iter([0.0, 100.0, 200.0])
    monkeypatch.setattr(mod.time, "monotonic", lambda: next(clock))
    responses.get(f"{mod.API_URL}m1/status", json={"status": "inProgress"})
    with pytest.raises(TimeoutError):
        mod.AsyncMatrix("k").wait("m1", interval=0, timeout=50)


@responses.activate
def test_result_follows_the_303_redirect():
    responses.get(
        f"{mod.API_URL}m1", status=303, headers={"Location": "https://files.example/m1.json"}
    )
    responses.get("https://files.example/m1.json", json={"matrix": {}})
    assert mod.AsyncMatrix("k").result("m1") == {"matrix": {}}


def test_flatten_maps_row_major_arrays_to_pairs():
    result = {
        "matrix": {
            "numOrigins": 2,
            "numDestinations": 2,
            "travelTimes": [100, 200, 300, 400],
            "distances": [1000, 2000, 3000, 4000],
            "errorCodes": [0, 0, 3, 0],
        }
    }
    rows = mod.flatten(result)
    assert rows[1] == {
        "origin_index": 0,
        "destination_index": 1,
        "status": "OK",
        "distance_m": 2000,
        "duration_s": 200,
    }
    assert rows[2] == {
        "origin_index": 1,
        "destination_index": 0,
        "status": "ERROR_3",
        "distance_m": "",
        "duration_s": "",
    }
    assert rows[3]["origin_index"] == 1 and rows[3]["destination_index"] == 1


def test_flatten_without_error_codes():
    result = {
        "matrix": {"numOrigins": 1, "numDestinations": 1, "travelTimes": [5], "distances": [9]}
    }
    assert mod.flatten(result)[0]["status"] == "OK"


@responses.activate
def test_main_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    origins, destinations, output = tmp_path / "o.csv", tmp_path / "d.csv", tmp_path / "out.csv"
    origins.write_text("48.8,2.3\n")
    destinations.write_text("48.7,2.4\n48.6,2.5\n")
    responses.post(mod.API_URL, json={"matrix_id": "m1", "status": "accepted"})
    responses.get(f"{mod.API_URL}m1/status", json={"status": "completed"})
    responses.get(
        f"{mod.API_URL}m1",
        json={
            "matrix": {
                "numOrigins": 1,
                "numDestinations": 2,
                "travelTimes": [2, 2],
                "distances": [1, 1],
            }
        },
    )
    args = [str(output), "--origins", str(origins), "--destinations", str(destinations)]
    assert mod.main(args) == 0
    with output.open() as handle:
        rows = list(csv.DictReader(handle))
    assert [r["destination_index"] for r in rows] == ["0", "1"]
    assert rows[0]["distance_m"] == "1"


@responses.activate
def test_main_reports_failed_matrix(tmp_path, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    points = tmp_path / "p.csv"
    points.write_text("48.8,2.3\n")
    responses.post(mod.API_URL, json={"matrix_id": "m1", "status": "accepted"})
    responses.get(f"{mod.API_URL}m1/status", json={"status": "error"})
    args = [str(tmp_path / "out.csv"), "--origins", str(points), "--destinations", str(points)]
    assert mod.main(args) == 1


@responses.activate
def test_main_resumes_an_existing_job(tmp_path, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(f"{mod.API_URL}m9/status", json={"status": "completed"})
    responses.get(
        f"{mod.API_URL}m9",
        json={
            "matrix": {"numOrigins": 1, "numDestinations": 1, "travelTimes": [1], "distances": [2]}
        },
    )
    output = tmp_path / "out.csv"
    assert mod.main([str(output), "--matrix-id", "m9"]) == 0
    assert "0,0,OK,2,1" in output.read_text()
    assert all(c.request.method == "GET" for c in responses.calls)


def test_main_requires_inputs_or_matrix_id(tmp_path, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    with pytest.raises(SystemExit):
        mod.main([str(tmp_path / "out.csv")])


def test_rate_limit_delay_prefers_the_ratelimit_header_over_legacy_ones():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    response.headers["ratelimit-reset"] = "2"
    assert mod.retry_delay(response, 0) == 9.0
