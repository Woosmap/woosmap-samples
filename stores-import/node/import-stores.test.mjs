import assert from "node:assert/strict";
import { test } from "node:test";

import {
  API_URL,
  DEFAULT_COLUMNS,
  WoosmapStores,
  chunked,
  convertRows,
  parseColumnOverrides,
  positiveInt,
  rowToAsset,
  upload,
} from "./import-stores.mjs";

function fakeFetch(responses) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    const next = responses.shift() ?? { status: 200, body: "{}" };
    return new Response(next.body ?? "{}", { status: next.status ?? 200, headers: next.headers });
  };
  return { fetchImpl, calls };
}

test("row to asset maps default columns", () => {
  const asset = rowToAsset({
    Name: "Markthal",
    Latitude: "51.9",
    Longitude: "4,48",
    City: "Rotterdam",
    "Country Code": "nl",
    Type: "covered|indoor",
  });
  assert.deepEqual(asset, {
    storeId: "Markthal",
    name: "Markthal",
    location: { lat: 51.9, lng: 4.48 },
    address: { city: "Rotterdam", countryCode: "NL" },
    types: ["covered", "indoor"],
  });
});

test("accents are transliterated in derived ids", () => {
  assert.equal(rowToAsset({ Name: "Le Grand Marché d'Apt", Latitude: "1", Longitude: "2" }).storeId, "LeGrandMarchedApt");
});

test("bad coordinates and duplicate ids are reported per row", () => {
  const { assets, errors } = convertRows([
    { Name: "A", Latitude: "", Longitude: "2" },
    { Name: "B", Latitude: "1", Longitude: "2" },
    { Name: "B", Latitude: "1", Longitude: "2" },
  ]);
  assert.equal(assets.length, 1);
  assert.deepEqual(errors, ["row 2: invalid latitude ''", "row 4: duplicate storeId 'B' (first seen row 3)"]);
});

test("column overrides validate the field name", () => {
  assert.equal(parseColumnOverrides(["name=Shop name"]).name, "Shop name");
  assert.equal(parseColumnOverrides([]).lat, DEFAULT_COLUMNS.lat);
  assert.throws(() => parseColumnOverrides(["colour=Blue"]));
});

test("an unknown mode is refused instead of falling through to update", async () => {
  const { fetchImpl, calls } = fakeFetch([{}]);
  await assert.rejects(
    upload(new WoosmapStores("k", fetchImpl), [{ storeId: "a" }], "replcae", 500),
    /--mode must be one of/,
  );
  assert.equal(calls.length, 0);
});

test("chunked refuses a batch size below one instead of hanging", () => {
  for (const size of [0, -1, Number.NaN]) {
    assert.throws(() => chunked([1, 2, 3], size), /1 or more/);
  }
  assert.deepEqual(chunked([1, 2, 3], 2), [[1, 2], [3]]);
});

test("positiveInt rejects text, zero and fractions", () => {
  for (const value of ["abc", "0", "-2", "1.5", ""]) {
    assert.throws(() => positiveInt(value, "--batch-size"), /1 or more/);
  }
  assert.equal(positiveInt("300", "--batch-size"), 300);
});

test("a date in Retry-After falls back to backoff instead of retrying at once", async () => {
  const waits = [];
  const { fetchImpl } = fakeFetch([
    { status: 429, headers: { "Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT" } },
    { status: 429, headers: { "ratelimit-reset": "5" } },
    { status: 200 },
  ]);
  await new WoosmapStores("k", fetchImpl, async (s) => waits.push(s)).create([{ storeId: "a" }]);
  assert.deepEqual(waits, [1, 5]);
});

test("replace posts every store once with the private key", async () => {
  const { fetchImpl, calls } = fakeFetch([{ status: 200, body: '{"status":"OK"}' }]);
  await upload(new WoosmapStores("secret", fetchImpl), [{ storeId: "a" }, { storeId: "b" }], "replace", 1);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, `${API_URL}/stores/replace?private_key=secret`);
  assert.equal(JSON.parse(calls[0].init.body).stores.length, 2);
});

test("create mode batches and retries on 429", async () => {
  const { fetchImpl, calls } = fakeFetch([
    { status: 429, headers: { "Retry-After": "0" } },
    { status: 200 },
    { status: 200 },
  ]);
  const api = new WoosmapStores("k", fetchImpl, async () => {});
  await upload(api, [{ storeId: "1" }, { storeId: "2" }, { storeId: "3" }], "create", 2);
  assert.equal(calls.length, 3);
  assert.equal(calls[0].init.method, "POST");
});

test("api errors carry the response body", async () => {
  const { fetchImpl } = fakeFetch([{ status: 400, body: '{"detail":"bad storeId"}' }]);
  await assert.rejects(new WoosmapStores("k", fetchImpl).create([{ storeId: "a b" }]), /bad storeId/);
});
