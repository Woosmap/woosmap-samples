// Import stores from a spreadsheet into a Woosmap project. Reading the file is in spreadsheet.mjs.
import { writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

import { readSource } from "./spreadsheet.mjs";

export const API_URL = "https://api.woosmap.com";
const MAX_BODY_BYTES = 15 * 1024 * 1024; // Stores API request body limit

export const DEFAULT_COLUMNS = {
  storeId: "Store ID",
  name: "Name",
  lat: "Latitude",
  lng: "Longitude",
  addressLine: "Address Line",
  city: "City",
  zipcode: "Zipcode",
  countryCode: "Country Code",
  website: "Website",
  phone: "Contact Phone",
  email: "Contact Email",
  types: "Type",
  tags: "Tags",
};

// storeId must match [A-Za-z0-9]+
const slugify = (value) =>
  value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^A-Za-z0-9]+/g, "");
const parseList = (value) => value.split("|").map((v) => v.trim()).filter(Boolean);

function parseCoordinate(value, name) {
  const number = Number.parseFloat(String(value).replace(",", "."));
  if (Number.isNaN(number)) throw new Error(`invalid ${name} '${value}'`);
  return number;
}

function compact(object) {
  const entries = Object.entries(object).filter(([, v]) => v !== "" && v !== undefined && v !== null);
  return entries.length ? Object.fromEntries(entries) : undefined;
}

export function rowToAsset(row, columns = DEFAULT_COLUMNS) {
  const col = (key) => row[columns[key]] ?? "";
  if (!col("name")) throw new Error("missing name");
  const storeId = slugify(col("storeId") || col("name"));
  if (!storeId) throw new Error("no storeId and no name to derive one from");
  const asset = {
    storeId,
    name: col("name"),
    location: { lat: parseCoordinate(col("lat"), "latitude"), lng: parseCoordinate(col("lng"), "longitude") },
  };
  const address = compact({
    lines: col("addressLine") ? [col("addressLine")] : undefined,
    city: col("city"),
    zipcode: col("zipcode"),
    countryCode: col("countryCode").toUpperCase(),
  });
  const contact = compact({ website: col("website"), phone: col("phone"), email: col("email") });
  if (address) asset.address = address;
  if (contact) asset.contact = contact;
  if (col("types")) asset.types = parseList(col("types"));
  if (col("tags")) asset.tags = parseList(col("tags"));
  return asset;
}

export function convertRows(rows, columns = DEFAULT_COLUMNS) {
  const assets = [];
  const errors = [];
  const seen = new Map();
  let derivedIds = 0;
  rows.forEach((row, index) => {
    const line = index + 2;
    try {
      const asset = rowToAsset(row, columns);
      if (seen.has(asset.storeId)) {
        errors.push(`row ${line}: duplicate storeId '${asset.storeId}' (first seen row ${seen.get(asset.storeId)})`);
        return;
      }
      seen.set(asset.storeId, line);
      assets.push(asset);
      if (!row[columns.storeId]) derivedIds += 1;
    } catch (error) {
      errors.push(`row ${line}: ${error.message}`);
    }
  });
  return { assets, errors, derivedIds };
}

const sleep = (seconds) => new Promise((resolve) => setTimeout(resolve, seconds * 1000));

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

function rateLimitRemaining(response) {
  // the tightest policy governs: if any one is at zero, so is the batch's real budget
  const policies = parseRateLimit(response.headers.get("RateLimit") ?? "");
  const remaining = policies.filter((p) => p.r !== undefined).map((p) => p.r);
  if (remaining.length) return Math.min(...remaining);
  const legacy = response.headers.get("RateLimit-Remaining");
  return legacy !== null && Number.isFinite(Number(legacy)) ? Number(legacy) : undefined;
}

export class WoosmapStores {
  constructor(privateKey, fetchImpl = fetch, sleepImpl = sleep) {
    this.privateKey = privateKey;
    this.fetch = fetchImpl;
    this.sleep = sleepImpl;
  }

  async send(method, path, stores) {
    const body = JSON.stringify({ stores });
    if (Buffer.byteLength(body) > MAX_BODY_BYTES) throw new Error("request body is above the 15MB limit");
    let response;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      response = await this.fetch(`${API_URL}${path}?private_key=${encodeURIComponent(this.privateKey)}`, {
        method,
        headers: { "Content-Type": "application/json" },
        body,
      });
      if (response.status !== 429 || attempt === 2) break;
      await this.sleep(retryDelay(response, attempt));
    }
    if (!response.ok) throw new Error(`${method} ${path} failed (${response.status}): ${await response.text()}`);
    // the quota is gone for this window; wait it out now instead of 429ing the next batch
    if (rateLimitRemaining(response) === 0) await this.sleep(retryDelay(response, 0));
    return response.json();
  }

  replaceAll = (stores) => this.send("POST", "/stores/replace", stores);
  // POST rejects the whole batch if one storeId already exists, PUT if one is missing
  create = (stores) => this.send("POST", "/stores", stores);
  update = (stores) => this.send("PUT", "/stores", stores);
}

export const MODES = ["replace", "create", "update"];

export function positiveInt(value, name) {
  const number = Number(value);
  if (!Number.isInteger(number) || number < 1) {
    throw new Error(`${name} must be a whole number of 1 or more, got '${value}'`);
  }
  return number;
}

export function chunked(items, size) {
  if (!Number.isInteger(size) || size < 1) throw new Error(`batch size must be 1 or more, got ${size}`);
  const chunks = [];
  for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size));
  return chunks;
}

export async function upload(api, assets, mode, batchSize) {
  if (!MODES.includes(mode)) throw new Error(`--mode must be one of ${MODES.join(", ")}, got '${mode}'`);
  if (mode === "replace") {
    await api.replaceAll(assets);
    console.log(`replaced the project with ${assets.length} stores`);
    return;
  }
  const action = mode === "create" ? api.create : api.update;
  for (const batch of chunked(assets, batchSize)) {
    await action(batch);
    console.log(`${mode}d ${batch.length} stores`);
  }
}

export function parseColumnOverrides(values, base = DEFAULT_COLUMNS) {
  const columns = { ...base };
  for (const value of values) {
    const [key, ...rest] = value.split("=");
    const header = rest.join("=");
    if (!(key in columns) || !header) throw new Error(`--column expects FIELD=HEADER with FIELD in ${Object.keys(columns).join(", ")}`);
    columns[key] = header;
  }
  return columns;
}

export async function main(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      column: { type: "string", multiple: true, default: [] },
      mode: { type: "string", default: "replace" },
      "batch-size": { type: "string", default: "500" },
      output: { type: "string" },
      "dry-run": { type: "boolean", default: false },
      strict: { type: "boolean", default: false },
    },
  });
  const [source] = positionals;
  if (!source) throw new Error("usage: node import-stores.mjs <csv path | Google Sheets URL> [options]");
  if (!MODES.includes(values.mode)) throw new Error(`--mode must be one of ${MODES.join(", ")}, got '${values.mode}'`);
  const batchSize = positiveInt(values["batch-size"], "--batch-size");
  const rows = await readSource(source);
  const { assets, errors, derivedIds } = convertRows(rows, parseColumnOverrides(values.column));
  errors.forEach((error) => console.error(error));
  console.log(`${assets.length} stores ready, ${errors.length} rows skipped`);
  if (derivedIds) console.error(`storeId derived from the name for ${derivedIds} stores; add a Store ID column before relying on stores-sync`);
  if (values.strict && errors.length) return 1;
  if (values.output) await writeFile(values.output, JSON.stringify({ stores: assets }, null, 2));
  if (values["dry-run"] || !assets.length) return 0;
  const privateKey = process.env.WOOSMAP_PRIVATE_KEY;
  if (!privateKey) throw new Error("set WOOSMAP_PRIVATE_KEY in the environment");
  await upload(new WoosmapStores(privateKey), assets, values.mode, batchSize);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).then((code) => process.exit(code), (error) => {
    console.error(error.message);
    process.exit(1);
  });
}
