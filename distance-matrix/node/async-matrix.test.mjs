import assert from "node:assert/strict";
import { test } from "node:test";

import { API_URL, AsyncMatrix, flatten, parsePoints, toCsv } from "./async-matrix.mjs";

function fakeFetch(responses) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    const next = responses.shift() ?? {};
    return new Response(JSON.stringify(next.body ?? {}), { status: next.status ?? 200, headers: next.headers });
  };
  return { fetchImpl, calls };
}

test("parsePoints skips headers, blanks and accepts semicolons", () => {
  assert.deepEqual(parsePoints("lat,lng\n48.8,2.3\n\n48.7;2.4\n"), ["48.8,2.3", "48.7,2.4"]);
  assert.throws(() => parsePoints("lat,lng\n"));
});

test("submit posts pipe-separated points with the private key", async () => {
  const { fetchImpl, calls } = fakeFetch([{ body: { matrix_id: "m1", status: "accepted" } }]);
  const id = await new AsyncMatrix("k", fetchImpl).submit(["1,2", "3,4"], ["5,6"], { mode: "driving" });
  assert.equal(id, "m1");
  assert.equal(calls[0].url, `${API_URL}?private_key=k`);
  assert.deepEqual(JSON.parse(calls[0].init.body), { origins: "1,2|3,4", destinations: "5,6", mode: "driving" });
});

test("wait polls until a final status", async () => {
  const { fetchImpl, calls } = fakeFetch([
    { body: { status: "accepted" } },
    { body: { status: "inProgress" } },
    { body: { status: "completed" } },
  ]);
  const api = new AsyncMatrix("k", fetchImpl, async () => {}, () => 0);
  assert.equal(await api.wait("m1", 0, 60), "completed");
  assert.equal(calls.length, 3);
});

test("wait gives up after the timeout", async () => {
  const { fetchImpl } = fakeFetch([{ body: { status: "inProgress" } }, { body: { status: "inProgress" } }]);
  let clock = 0;
  const api = new AsyncMatrix("k", fetchImpl, async () => {}, () => (clock += 100));
  await assert.rejects(api.wait("m1", 0, 50), /still inProgress/);
});

test("flatten maps row-major arrays to origin/destination pairs and toCsv renders it", () => {
  const rows = flatten({
    matrix: { numOrigins: 2, numDestinations: 2, travelTimes: [100, 200, 300, 400], distances: [1000, 2000, 3000, 4000], errorCodes: [0, 0, 3, 0] },
  });
  assert.deepEqual(rows[1], { origin_index: 0, destination_index: 1, status: "OK", distance_m: 2000, duration_s: 200 });
  assert.deepEqual(rows[2], { origin_index: 1, destination_index: 0, status: "ERROR_3", distance_m: "", duration_s: "" });
  assert.equal(toCsv(rows).split("\n")[1], "0,0,OK,1000,100");
});

test("errors fail immediately and carry the body", async () => {
  const { fetchImpl, calls } = fakeFetch([{ status: 502, body: { detail: "gateway" } }]);
  await assert.rejects(new AsyncMatrix("k", fetchImpl, async () => {}).status("m1"), /gateway/);
  assert.equal(calls.length, 1);
});

test("RateLimit's t= wins over the legacy reset header", async () => {
  const waits = [];
  const { fetchImpl } = fakeFetch([
    { status: 429, headers: { RateLimit: '"default";r=0;t=9', "ratelimit-reset": "2" } },
    { body: { status: "accepted" } },
  ]);
  await new AsyncMatrix("k", fetchImpl, async (s) => waits.push(s)).status("m1");
  assert.deepEqual(waits, [9]);
});
