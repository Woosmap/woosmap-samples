// Read rows from a CSV file or a published Google Sheet.
import { readFile } from "node:fs/promises";

export async function readSource(source, fetchImpl = fetch) {
  if (/^https?:\/\//.test(source)) {
    const response = await fetchImpl(googleSheetExportUrl(source));
    if (!response.ok) throw new Error(`Google Sheets export failed (${response.status})`);
    return parseCsv(await response.text());
  }
  try {
    return parseCsv(await readFile(source, "utf8"));
  } catch (error) {
    throw new Error(error.code === "ENOENT" ? `no such file: ${source}` : `${source}: ${error.message}`);
  }
}

export function googleSheetExportUrl(url) {
  const match = url.match(/\/spreadsheets\/d\/([\w-]+)/);
  if (!match) throw new Error(`Not a Google Sheets URL: ${url}`);
  const gid = url.match(/[#&?]gid=(\d+)/);
  return `https://docs.google.com/spreadsheets/d/${match[1]}/export?format=csv${gid ? `&gid=${gid[1]}` : ""}`;
}

export function parseCsv(text, delimiter = detectDelimiter(text)) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  const source = text.replace(/^﻿/, "");
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    if (quoted) {
      if (char === '"' && source[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        cell += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === delimiter) {
      row.push(cell);
      cell = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && source[i + 1] === "\n") i += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell !== "" || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return toRecords(rows.filter((r) => r.some((c) => c.trim() !== "")));
}

function detectDelimiter(text) {
  const firstLine = text.split(/\r?\n/, 1)[0] ?? "";
  const counts = [",", ";", "\t"].map((d) => [d, firstLine.split(d).length]);
  return counts.sort((a, b) => b[1] - a[1])[0][0];
}

function toRecords([header = [], ...lines]) {
  const keys = header.map((h) => h.trim());
  return lines.map((line) =>
    Object.fromEntries(keys.map((key, index) => [key, (line[index] ?? "").trim()]).filter(([k]) => k)),
  );
}
