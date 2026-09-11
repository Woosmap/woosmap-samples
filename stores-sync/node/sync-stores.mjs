// Synchronise a Woosmap project with a Woosmap JSON file, changing only what differs.
import { readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

export const API_URL = "https://api.woosmap.com";
const PAGE_SIZE = 300; // stores_by_page maximum

const sleep = (seconds) => new Promise((resolve) => setTimeout(resolve, seconds * 1000));

export class WoosmapStores {
  constructor(privateKey, fetchImpl = fetch, sleepImpl = sleep) {
    this.privateKey = privateKey;
    this.fetch = fetchImpl;
    this.sleep = sleepImpl;
  }

  async request(method, path, { params = {}, body } = {}) {
    const query = new URLSearchParams({ private_key: this.privateKey, ...params });
    let response;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      response = await this.fetch(`${API_URL}${path}?${query}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      });
      if (response.status !== 429 || attempt === 2) break;
      // 429 is the only status the API asks to retry, and Retry-After says when
      await this.sleep(Number(response.headers.get("Retry-After") ?? 2 ** attempt));
    }
    if (!response.ok) throw new Error(`${method} ${path} failed (${response.status}): ${await response.text()}`);
    return response.json();
  }

  async fetchAll() {
    const features = [];
    for (let page = 1; ; page += 1) {
      const body = await this.request("GET", "/stores/search", { params: { stores_by_page: PAGE_SIZE, page } });
      features.push(...(body.features ?? []));
      if (page >= (body.pagination?.pageCount ?? 1)) return features;
    }
  }

  create = (stores) => this.request("POST", "/stores", { body: { stores } });
  update = (stores) => this.request("PUT", "/stores", { body: { stores } });
  delete = (storeIds) => this.request("DELETE", "/stores", { params: { query: deleteQuery(storeIds) } });
}

// idstore is the query-language name of storeId
export const deleteQuery = (storeIds) => storeIds.map((id) => `idstore:="${id}"`).join(" OR ");

export function featureToAsset(feature) {
  const props = feature.properties;
  const [lng, lat] = feature.geometry.coordinates;
  const address = props.address ?? {};
  return {
    storeId: props.store_id,
    name: props.name,
    location: { lat, lng },
    address: {
      lines: address.lines,
      city: address.city,
      zipcode: address.zipcode,
      countryCode: address.country_code,
    },
    contact: props.contact,
    types: props.types,
    tags: props.tags,
    userProperties: props.user_properties,
    openingHours: props.opening_hours,
  };
}

const isEmpty = (v) =>
  v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0) || (isPlainObject(v) && Object.keys(v).length === 0);
const isPlainObject = (v) => typeof v === "object" && v !== null && !Array.isArray(v);

export function normalise(value) {
  if (Array.isArray(value)) {
    const items = value.map(normalise);
    return items.every((i) => typeof i === "string") ? [...items].sort() : items;
  }
  if (isPlainObject(value)) {
    const entries = Object.entries(value)
      .map(([k, v]) => [k, normalise(v)])
      .filter(([, v]) => !isEmpty(v))
      .sort(([a], [b]) => a.localeCompare(b));
    return Object.fromEntries(entries);
  }
  if (typeof value === "number" && !Number.isInteger(value)) return Number(value.toFixed(6));
  return value;
}

// the Stores API drops temporary closures once they have ended
export function withoutExpiredClosures(asset, today = new Date()) {
  const closures = asset.openingHours?.temporary_closure;
  if (!closures?.length) return asset;
  const limit = today.toISOString().slice(0, 10);
  const kept = closures.filter((closure) => (closure.end ?? "") >= limit);
  return { ...asset, openingHours: { ...asset.openingHours, temporary_closure: kept } };
}

export const sameAsset = (a, b) =>
  JSON.stringify(normalise(withoutExpiredClosures(a))) === JSON.stringify(normalise(withoutExpiredClosures(b)));

export function buildPlan(localAssets, remoteFeatures) {
  const local = new Map(localAssets.map((a) => [a.storeId, a]));
  const remote = new Map(remoteFeatures.map(featureToAsset).map((a) => [a.storeId, a]));
  const plan = { create: [], update: [], delete: [] };
  for (const [storeId, asset] of local) {
    if (!remote.has(storeId)) plan.create.push(asset);
    else if (!sameAsset(asset, remote.get(storeId))) plan.update.push(asset);
  }
  plan.delete = [...remote.keys()].filter((id) => !local.has(id)).sort();
  return plan;
}

export function chunked(items, size) {
  const chunks = [];
  for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size));
  return chunks;
}

export async function applyPlan(api, plan, batchSize, allowDelete) {
  for (const batch of chunked(plan.create, batchSize)) {
    await api.create(batch);
    console.log(`created ${batch.length}`);
  }
  for (const batch of chunked(plan.update, batchSize)) {
    await api.update(batch);
    console.log(`updated ${batch.length}`);
  }
  if (!allowDelete) return;
  for (const batch of chunked(plan.delete, 50)) {
    await api.delete(batch);
    console.log(`deleted ${batch.length}`);
  }
}

export const describe = (plan) =>
  `${plan.create.length} to create, ${plan.update.length} to update, ${plan.delete.length} to delete`;

async function loadLocalAssets(path) {
  let document;
  try {
    document = JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    throw new Error(error.code === "ENOENT" ? `no such file: ${path}` : `${path}: ${error.message}`);
  }
  const stores = Array.isArray(document?.stores) ? document.stores : null;
  if (!stores) throw new Error(`${path} must be a JSON object with a "stores" array`);
  const withoutId = stores.findIndex((asset) => !asset.storeId);
  if (withoutId >= 0) throw new Error(`store without a storeId at position ${withoutId + 1}`);
  return stores;
}

export async function main(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      "batch-size": { type: "string", default: "500" },
      "no-delete": { type: "boolean", default: false },
      "dry-run": { type: "boolean", default: false },
    },
  });
  const [source] = positionals;
  if (!source) throw new Error("usage: node sync-stores.mjs <woosmap json> [--dry-run] [--no-delete]");
  const privateKey = process.env.WOOSMAP_PRIVATE_KEY;
  if (!privateKey) throw new Error("set WOOSMAP_PRIVATE_KEY in the environment");
  const localAssets = await loadLocalAssets(source);
  const api = new WoosmapStores(privateKey);
  const plan = buildPlan(localAssets, await api.fetchAll());
  console.log(describe(plan));
  plan.delete.forEach((id) => console.log(`  delete ${id}`));
  const empty = !plan.create.length && !plan.update.length && !plan.delete.length;
  if (values["dry-run"] || empty) return 0;
  await applyPlan(api, plan, Number(values["batch-size"]), !values["no-delete"]);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).then((code) => process.exit(code), (error) => {
    console.error(error.message);
    process.exit(1);
  });
}
