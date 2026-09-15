from pathlib import Path

import pytest
import requests
import responses
import spreadsheet as mod
from openpyxl import Workbook

DATA = Path(__file__).resolve().parents[2] / "data"


def test_reads_the_food_markets_csv_fixture():
    rows = mod.read_csv_file(DATA / "foodmarkets.csv")
    assert len(rows) == 18
    assert rows[0]["Name"] == "Markthal Rotterdam"


def test_sniffs_semicolon_delimited_csv():
    assert mod.read_csv_text('Name;Latitude\n"A";1.5\n') == [{"Name": "A", "Latitude": "1.5"}]


def test_keeps_a_newline_inside_a_quoted_field():
    rows = mod.read_csv_text('Name,Address\n"A","line 1\nline 2"\n')
    assert rows == [{"Name": "A", "Address": "line 1\nline 2"}]


def test_single_column_csv_falls_back_to_the_default_dialect():
    assert mod.read_csv_text("Name\nA\n") == [{"Name": "A"}]


def test_reads_xlsx_first_sheet(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", "Latitude", "Longitude"])
    sheet.append(["Shop", 48.5, 2.0])
    path = tmp_path / "shops.xlsx"
    workbook.save(path)
    assert mod.read_xlsx_file(path, None) == [
        {"Name": "Shop", "Latitude": "48.5", "Longitude": "2"}
    ]


def test_reads_the_named_xlsx_sheet():
    rows = mod.read_xlsx_file(DATA / "foodmarkets.xlsx", "foodmarkets")
    assert len(rows) == 18
    assert rows[0]["Name"] == "Markthal Rotterdam"


def test_google_sheet_url_becomes_a_csv_export_url():
    url = "https://docs.google.com/spreadsheets/d/1abcDEF_-9/edit#gid=42"
    assert mod.google_sheet_export_url(url) == (
        "https://docs.google.com/spreadsheets/d/1abcDEF_-9/export?format=csv&gid=42"
    )


def test_google_sheet_url_without_a_gid():
    url = "https://docs.google.com/spreadsheets/d/1abcDEF_-9/edit"
    assert mod.google_sheet_export_url(url).endswith("export?format=csv")


def test_non_google_url_is_rejected():
    with pytest.raises(ValueError):
        mod.google_sheet_export_url("https://example.com/file.csv")


@responses.activate
def test_read_source_downloads_a_google_sheet():
    responses.get(
        "https://docs.google.com/spreadsheets/d/1abc/export",
        body=b"Name,Latitude\nShop,48.5\n",
    )
    rows = mod.read_source(
        "https://docs.google.com/spreadsheets/d/1abc/edit", None, requests.Session()
    )
    assert rows == [{"Name": "Shop", "Latitude": "48.5"}]


def test_read_source_picks_the_reader_from_the_extension():
    assert mod.read_source(str(DATA / "foodmarkets.xlsx"), None, requests.Session())[0]["City"]
    assert mod.read_source(str(DATA / "foodmarkets.csv"), None, requests.Session())[0]["City"]
