import json

import manage_dataset as mod
import pytest
import requests
import responses

DATASET = "11111111-2222-3333-4444-555555555555"


@responses.activate
def test_create_sends_name_url_and_title_mapping():
    responses.post(mod.API_URL, json={"id": DATASET, "name": "zones"})
    created = mod.Datasets("k").create("zones", "https://files.example/zones.zip", "ZONE_NAME")
    assert created["id"] == DATASET
    body = json.loads(responses.calls[0].request.body)
    assert body == {
        "name": "zones",
        "url": "https://files.example/zones.zip",
        "schema_mapping": [{"schema_key": "title", "data_key": "ZONE_NAME"}],
    }


@responses.activate
def test_import_then_wait_until_success(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    responses.post(f"{mod.API_URL}{DATASET}/import", json={"dataset_id": DATASET})
    status_url = f"{mod.API_URL}{DATASET}/status"
    responses.get(
        status_url,
        json={"status": "in_progress", "steps": [{"name": "fetch", "status": "success"}]},
    )
    responses.get(status_url, json={"status": "success", "steps": []})
    api = mod.Datasets("k")
    api.trigger_import(DATASET)
    assert api.wait(DATASET, interval=0, timeout=60)["status"] == "success"
    assert len(responses.calls) == 3


@responses.activate
def test_wait_times_out(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    clock = iter([0.0, 5000.0])
    monkeypatch.setattr(mod.time, "monotonic", lambda: next(clock))
    responses.get(f"{mod.API_URL}{DATASET}/status", json={"status": "in_progress", "steps": []})
    with pytest.raises(TimeoutError):
        mod.Datasets("k").wait(DATASET, interval=0, timeout=10)


@responses.activate
def test_status_is_pending_while_the_api_answers_404(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    status_url = f"{mod.API_URL}{DATASET}/status"
    responses.get(status_url, status=404, json={"detail": "No dataset status available."})
    responses.get(status_url, json={"status": "success", "steps": []})
    assert mod.Datasets("k").wait(DATASET, interval=0, timeout=60)["status"] == "success"
    assert len(responses.calls) == 2


def test_describe_status_lists_steps():
    status = {
        "status": "in_progress",
        "steps": [{"name": "fetch", "status": "success"}, {"name": "import"}],
    }
    assert mod.describe_status(status) == "in_progress [fetch=success, import=None]"


@responses.activate
def test_query_follows_next_pages_and_sends_filters():
    url = f"{mod.API_URL}{DATASET}/features/within/"
    responses.post(url, json={"features": [{"id": "1"}], "pagination": {"page": 1, "next": 2}})
    responses.post(url, json={"features": [{"id": "2"}], "pagination": {"page": 2, "next": None}})
    features = mod.Datasets("k").query(
        DATASET, "within", "POLYGON((0 0,1 0,1 1,0 0))", "pop:>10", 50.0
    )
    assert [f["id"] for f in features] == ["1", "2"]
    body = json.loads(responses.calls[0].request.body)
    assert body == {"geometry": "POLYGON((0 0,1 0,1 1,0 0))", "where": "pop:>10", "buffer": 50.0}
    assert responses.calls[1].request.params["page"] == "2"
    assert responses.calls[1].request.params["per_page"] == "20"


def test_load_geometry_reads_geojson_feature_files(tmp_path):
    path = tmp_path / "zone.geojson"
    path.write_text(
        json.dumps({"type": "Feature", "geometry": {"type": "Point", "coordinates": [2, 48]}})
    )
    assert mod.load_geometry(f"@{path}") == {"type": "Point", "coordinates": [2, 48]}
    assert mod.load_geometry("48.8,2.3") == "POINT(2.3 48.8)"
    assert mod.load_geometry("POLYGON((0 0,1 0,1 1,0 0))") == "POLYGON((0 0,1 0,1 1,0 0))"


@responses.activate
def test_errors_include_the_api_body():
    responses.get(mod.API_URL, status=403, body='{"detail":"not activated"}')
    with pytest.raises(RuntimeError, match="not activated"):
        mod.Datasets("k").list()


@responses.activate
def test_call_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    responses.get(mod.API_URL, status=429, headers={"Retry-After": "0"})
    responses.get(mod.API_URL, json={"datasets": [{"id": DATASET}]})
    assert mod.Datasets("k").list() == [{"id": DATASET}]


@responses.activate
def test_call_does_not_retry_server_errors():
    responses.get(mod.API_URL, status=503, body="down")
    with pytest.raises(RuntimeError, match="down"):
        mod.Datasets("k").list()
    assert len(responses.calls) == 1


@responses.activate
def test_status_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    status_url = f"{mod.API_URL}{DATASET}/status"
    responses.get(status_url, status=429, headers={"Retry-After": "0"})
    responses.get(status_url, json={"status": "success", "steps": []})
    assert mod.Datasets("k").status(DATASET)["status"] == "success"


@responses.activate
def test_main_import_wait_returns_1_on_failure(monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    responses.post(f"{mod.API_URL}{DATASET}/import", json={"dataset_id": DATASET})
    responses.get(f"{mod.API_URL}{DATASET}/status", json={"status": "failed", "steps": []})
    assert mod.main(["import", DATASET, "--wait"]) == 1


@responses.activate
def test_main_list_prints_json(capsys, monkeypatch):
    monkeypatch.setenv("WOOSMAP_PRIVATE_KEY", "k")
    responses.get(mod.API_URL, json={"datasets": [{"id": DATASET}], "pagination": {"page": 1}})
    assert mod.main(["list"]) == 0
    assert DATASET in capsys.readouterr().out


def test_rate_limit_delay_prefers_the_ratelimit_header_over_legacy_ones():
    response = requests.Response()
    response.headers["RateLimit"] = '"default";r=0;t=9'
    response.headers["ratelimit-reset"] = "2"
    assert mod.retry_delay(response, 0) == 9.0
