import assert from "node:assert/strict";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { googleSheetExportUrl, parseCsv, readSource } from "./spreadsheet.mjs";

const DATA = fileURLToPath(new URL("../../data/", import.meta.url));

test("parses the food markets fixture", async () => {
  const rows = await readSource(`${DATA}foodmarkets.csv`);
  assert.equal(rows.length, 18);
  assert.equal(rows[0].Name, "Markthal Rotterdam");
});

test("handles quotes, embedded delimiters, CRLF and semicolons", () => {
  assert.deepEqual(parseCsv('Name;City\r\n"Shop; ""Le"" Coin";Paris\r\n'), [
    { Name: 'Shop; "Le" Coin', City: "Paris" },
  ]);
});

test("keeps a newline inside a quoted field", () => {
  assert.deepEqual(parseCsv('Name,Address\n"A","line 1\nline 2"\n'), [
    { Name: "A", Address: "line 1\nline 2" },
  ]);
});

test("google sheet url becomes a csv export url", () => {
  assert.equal(
    googleSheetExportUrl("https://docs.google.com/spreadsheets/d/1abc_-9/edit#gid=7"),
    "https://docs.google.com/spreadsheets/d/1abc_-9/export?format=csv&gid=7",
  );
  assert.throws(() => googleSheetExportUrl("https://example.com/x.csv"));
});

test("a missing file reports its path, not a stack", async () => {
  await assert.rejects(readSource(`${DATA}nope.csv`), /no such file/);
});

test("downloads a google sheet through the export url", async () => {
  const calls = [];
  const rows = await readSource("https://docs.google.com/spreadsheets/d/1abc/edit", async (url) => {
    calls.push(url);
    return new Response("Name,Latitude\nShop,48.5\n");
  });
  assert.match(calls[0], /export\?format=csv$/);
  assert.deepEqual(rows, [{ Name: "Shop", Latitude: "48.5" }]);
});
