// Compute a large distance matrix with the asynchronous Distance API and save it as CSV.
import { readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

export const API_URL = "https://api.woosmap.com/distance/matrix/async/";
const FINAL_STATUSES = new Set(["completed", "timeout", "error"]);
const OUTPUT_COLUMNS = ["origin_index", "destination_index", "status", "distance_m", "duration_s"];

const sleep = (seconds) => new Promise((resolve) => setTimeout(resolve, seconds * 1000));

export function parsePoints(text) {
  const points = [];
  for (const line of text.replace(/^﻿/, "").split(/\r?\n/)) {
    const [lat, lng] = line.replace(/;/g, ",").split(",").map((c) => c.trim());
    if (lat && lng && !Number.isNaN(Number(lat)) && !Number.isNaN(Number(lng))) points.push(`${lat},${lng}`);
  }
  if (!points.length) throw new Error("no coordinates found");
  return points;
}

// IETF RateLimit header: comma-separated "policy";r=<remaining>;t=<reset-seconds> entries
function parseRateLimit(value) {
  return value
    .split(",")
    .filter((policy) => policy.trim())
    .map((policy) => {
      const result = {};
      for (const match of policy.matchAll(/\b([rt])=(\d+)/g)) result[match[1]] = Number(match[2]);
      return result;
    });
}

// a 429 is bound by whichever policy hit zero, not necessarily the first one in the header;
// ratelimit-reset is a compat header pending removal, Retry-After only ever comes from a proxy
function retryDelay(response, attempt) {
  const policies = parseRateLimit(response.headers.get("RateLimit") ?? "");
  const exhausted = policies.filter((p) => p.r === 0 && p.t !== undefined).map((p) => p.t);
  if (exhausted.length) return Math.max(...exhausted);
  for (const header of ["ratelimit-reset", "retry-after"]) {
    const raw = response.headers.get(header);
    const value = raw?.trim() ? Number(raw) : Number.NaN;
    if (Number.isFinite(value) && value >= 0) return value;
  }
  return 2 ** attempt;
}

export class AsyncMatrix {
  constructor(privateKey, fetchImpl = fetch, sleepImpl = sleep, now = () => Date.now() / 1000) {
    this.privateKey = privateKey;
    this.fetch = fetchImpl;
    this.sleep = sleepImpl;
    this.now = now;
  }

  async call(method, url, body) {
    const target = `${url}?private_key=${encodeURIComponent(this.privateKey)}`;
    let response;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      response = await this.fetch(target, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
        redirect: "follow",
      });
      if (response.status !== 429 || attempt === 2) break;
      await this.sleep(retryDelay(response, attempt));
    }
    if (!response.ok) throw new Error(`${method} ${url} failed (${response.status}): ${await response.text()}`);
    return response.json();
  }

  async submit(origins, destinations, options = {}) {
    const body = { origins: origins.join("|"), destinations: destinations.join("|"), ...options };
    return (await this.call("POST", API_URL, body)).matrix_id;
  }

  status = async (matrixId) => (await this.call("GET", `${API_URL}${matrixId}/status`)).status;
  result = (matrixId) => this.call("GET", `${API_URL}${matrixId}`);

  async wait(matrixId, interval, timeout) {
    const deadline = this.now() + timeout;
    for (;;) {
      const status = await this.status(matrixId);
      console.error(`${matrixId}: ${status}`);
      if (FINAL_STATUSES.has(status)) return status;
      if (this.now() >= deadline) throw new Error(`matrix ${matrixId} still ${status} after ${timeout}s`);
      await this.sleep(interval);
    }
  }
}

export function flatten(result) {
  // The async result is not the synchronous rows/elements shape: travelTimes and distances
  // are flat row-major arrays, errorCodes is present only when some pairs failed.
  const matrix = result.matrix ?? {};
  const destinations = matrix.numDestinations ?? 0;
  const { travelTimes = [], distances = [], errorCodes = [] } = matrix;
  const rows = [];
  for (let index = 0; index < (matrix.numOrigins ?? 0) * destinations; index += 1) {
    const error = errorCodes[index] ?? 0;
    rows.push({
      origin_index: Math.floor(index / destinations),
      destination_index: index % destinations,
      status: error ? `ERROR_${error}` : "OK",
      distance_m: error ? "" : distances[index] ?? "",
      duration_s: error ? "" : travelTimes[index] ?? "",
    });
  }
  return rows;
}

export const toCsv = (rows) =>
  [OUTPUT_COLUMNS.join(","), ...rows.map((row) => OUTPUT_COLUMNS.map((c) => row[c]).join(","))].join("\n") + "\n";

async function submitFromFiles(api, values) {
  if (!values.origins || !values.destinations) throw new Error("pass --origins and --destinations, or --matrix-id to resume a job");
  const origins = parsePoints(await readFile(values.origins, "utf8"));
  const destinations = parsePoints(await readFile(values.destinations, "utf8"));
  const matrixId = await api.submit(origins, destinations, { mode: values.mode, method: values.method, elements: values.elements });
  // the job outlives this process: keep the id to resume with --matrix-id if polling is cut
  console.error(`submitted ${origins.length}x${destinations.length} matrix ${matrixId}`);
  return matrixId;
}

export async function main(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      mode: { type: "string", default: "driving" },
      method: { type: "string", default: "time" },
      elements: { type: "string", default: "duration_distance" },
      "poll-interval": { type: "string", default: "5" },
      timeout: { type: "string", default: "1800" },
      origins: { type: "string" },
      destinations: { type: "string" },
      "matrix-id": { type: "string" },
    },
  });
  const [outputPath] = positionals;
  if (!outputPath) throw new Error("usage: node async-matrix.mjs <output.csv> --origins o.csv --destinations d.csv | --matrix-id ID");
  const privateKey = process.env.WOOSMAP_PRIVATE_KEY;
  if (!privateKey) throw new Error("set WOOSMAP_PRIVATE_KEY in the environment");
  const api = new AsyncMatrix(privateKey);
  const matrixId = values["matrix-id"] ?? (await submitFromFiles(api, values));
  const status = await api.wait(matrixId, Number(values["poll-interval"]), Number(values.timeout));
  if (status !== "completed") {
    console.error(`matrix ${matrixId} ended with status ${status}`);
    return 1;
  }
  const rows = flatten(await api.result(matrixId));
  await writeFile(outputPath, toCsv(rows));
  console.error(`wrote ${rows.length} elements to ${outputPath}`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).then((code) => process.exit(code), (error) => {
    console.error(error.message);
    process.exit(1);
  });
}
