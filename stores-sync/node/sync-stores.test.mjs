import assert from "node:assert/strict";
import { test } from "node:test";

import {
  API_URL,
  WoosmapStores,
  applyPlan,
  buildPlan,
  chunked,
  deleteQuery,
  featureToAsset,
  sameAsset,
  withoutExpiredClosures,
} from "./sync-stores.mjs";

const feature = (store_id, props = {}, [lat, lng] = [48.5, 2.0]) => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: [lng, lat] },
  properties: { store_id, name: "Shop", ...props },
});
const asset = (storeId, extra = {}) => ({ storeId, name: "Shop", location: { lat: 48.5, lng: 2.0 }, ...extra });

function fakeFetch(responses) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url: new URL(url), init });
    const next = responses.shift() ?? {};
    return new Response(JSON.stringify(next.body ?? {}), { status: next.status ?? 200, headers: next.headers });
  };
  return { fetchImpl, calls };
}

test("feature to asset renames snake_case fields", () => {
  const converted = featureToAsset(feature("a", { address: { country_code: "FR" }, user_properties: { k: 1 } }));
  assert.equal(converted.address.countryCode, "FR");
  assert.deepEqual(converted.userProperties, { k: 1 });
  assert.deepEqual(converted.location, { lat: 48.5, lng: 2.0 });
});

test("empty fields, list order and coordinate noise do not count as changes", () => {
  const local = asset("a", { types: ["b", "a"], address: { city: "Paris", lines: [] }, location: { lat: 48.5000000001, lng: 2 } });
  const remote = featureToAsset(feature("a", { types: ["a", "b"], address: { city: "Paris" } }));
  assert.ok(sameAsset(local, remote));
});

test("expired temporary closures are ignored, future ones are kept", () => {
  const local = asset("a", { openingHours: { timezone: "Europe/Paris", temporary_closure: [{ start: "2020-01-01", end: "2020-01-05" }] } });
  const remote = featureToAsset(feature("a", { opening_hours: { timezone: "Europe/Paris", temporary_closure: [] } }));
  assert.ok(sameAsset(local, remote));
  const future = withoutExpiredClosures(
    asset("a", { openingHours: { temporary_closure: [{ start: "2020-01-01", end: "2999-01-01" }] } }),
    new Date("2026-01-01"),
  );
  assert.deepEqual(future.openingHours.temporary_closure, [{ start: "2020-01-01", end: "2999-01-01" }]);
});

test("plan splits create, update and delete", () => {
  const plan = buildPlan(
    [asset("keep"), asset("changed", { name: "New" }), asset("new")],
    [feature("keep"), feature("changed"), feature("gone")],
  );
  assert.deepEqual(plan.create.map((a) => a.storeId), ["new"]);
  assert.deepEqual(plan.update.map((a) => a.storeId), ["changed"]);
  assert.deepEqual(plan.delete, ["gone"]);
});

test("chunked refuses a batch size below one instead of hanging", () => {
  for (const size of [0, -1, Number.NaN]) {
    assert.throws(() => chunked([1, 2, 3], size), /1 or more/);
  }
});

test("delete query uses OR clauses", () => {
  assert.equal(deleteQuery(["a", "b"]), 'idstore:="a" OR idstore:="b"');
});

test("fetchAll follows pagination", async () => {
  const { fetchImpl, calls } = fakeFetch([
    { body: { features: [feature("a")], pagination: { page: 1, pageCount: 2 } } },
    { body: { features: [feature("b")], pagination: { page: 2, pageCount: 2 } } },
  ]);
  const features = await new WoosmapStores("k", fetchImpl).fetchAll();
  assert.deepEqual(features.map((f) => f.properties.store_id), ["a", "b"]);
  assert.equal(calls[1].url.searchParams.get("page"), "2");
  assert.equal(calls[1].url.searchParams.get("stores_by_page"), "300");
});

test("applyPlan issues POST, PUT then DELETE with the private key", async () => {
  const { fetchImpl, calls } = fakeFetch([{}, {}, {}]);
  const plan = { create: [asset("n")], update: [asset("u")], delete: ["d1", "d2"] };
  await applyPlan(new WoosmapStores("k", fetchImpl), plan, 500, true);
  assert.deepEqual(calls.map((c) => c.init.method), ["POST", "PUT", "DELETE"]);
  assert.equal(calls[0].url.origin + calls[0].url.pathname, `${API_URL}/stores`);
  assert.equal(calls[0].url.searchParams.get("private_key"), "k");
  assert.equal(calls[2].url.searchParams.get("query"), 'idstore:="d1" OR idstore:="d2"');
});

test("--no-delete skips DELETE", async () => {
  const { fetchImpl, calls } = fakeFetch([{}]);
  await applyPlan(new WoosmapStores("k", fetchImpl), { create: [asset("n")], update: [], delete: ["d"] }, 500, false);
  assert.deepEqual(calls.map((c) => c.init.method), ["POST"]);
});

test("errors include the API body and 5xx are not retried", async () => {
  const { fetchImpl, calls } = fakeFetch([{ status: 503, body: { detail: "down" } }]);
  const api = new WoosmapStores("k", fetchImpl, async () => {});
  await assert.rejects(api.create([asset("x")]), /down/);
  assert.equal(calls.length, 1);
});

test("429 is retried after Retry-After", async () => {
  const waits = [];
  const { fetchImpl, calls } = fakeFetch([{ status: 429, headers: { "Retry-After": "3" } }, { body: {} }]);
  await new WoosmapStores("k", fetchImpl, async (s) => waits.push(s)).create([asset("x")]);
  assert.equal(calls.length, 2);
  assert.deepEqual(waits, [3]);
});

test("RateLimit's t= wins over the legacy reset header", async () => {
  const waits = [];
  const { fetchImpl } = fakeFetch([
    { status: 429, headers: { RateLimit: '"default";r=0;t=9', "ratelimit-reset": "2" } },
    { body: {} },
  ]);
  await new WoosmapStores("k", fetchImpl, async (s) => waits.push(s)).create([asset("x")]);
  assert.deepEqual(waits, [9]);
});

test("the exhausted policy governs even when it is not first in the header", async () => {
  const waits = [];
  const { fetchImpl } = fakeFetch([
    { status: 429, headers: { RateLimit: '"requests";r=5;t=1, "elements";r=0;t=30' } },
    { body: {} },
  ]);
  await new WoosmapStores("k", fetchImpl, async (s) => waits.push(s)).create([asset("x")]);
  assert.deepEqual(waits, [30]);
});

test("a batch pauses on its own once RateLimit reports no requests left", async () => {
  const waits = [];
  const { fetchImpl, calls } = fakeFetch([
    { body: {}, headers: { RateLimit: '"default";r=0;t=4' } },
    { body: {} },
  ]);
  const api = new WoosmapStores("k", fetchImpl, async (s) => waits.push(s));
  await api.create([asset("a")]);
  await api.create([asset("b")]);
  assert.equal(calls.length, 2);
  assert.deepEqual(waits, [4]);
});
