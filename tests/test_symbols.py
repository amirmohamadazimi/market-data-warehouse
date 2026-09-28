"""`symbols --add` without a database: lookup, validation, and the csv append."""

import pandas as pd
import pytest

from warehouse.symbols import append_to_csv, build_row

# A fixed two-symbol csv, so the tests don't depend on today's real symbols.csv.
CSV = (
    '"ticker","name","market","sector","currency","slug","vendor_id","is_active"\r\n'
    "فولاد,فولاد مبارکه اصفهان,TSE,فلزات اساسی,IRR,foolad,\"46348559193224090\",true\r\n"
    "SPY,SPDR S&P 500 ETF Trust,GLOBAL,ETF,USD,spy,SPY,true\r\n"
)


@pytest.fixture
def csv_copy(tmp_path):
    path = tmp_path / "symbols.csv"
    path.write_bytes(CSV.encode("utf-8"))
    return path


def test_tse_lookup_is_offline_and_matches_the_verified_inscode():
    row = build_row("فولاد", "TSE", "foolad_test")
    assert row["vendor_id"] == "46348559193224090"  # checked live on TSETMC on 2026-09-26
    assert row["currency"] == "IRR"


def test_arabic_letters_in_a_ticker_are_normalised_before_lookup():
    # فملي typed with Arabic yeh (as TSE's own site writes it) must still be found (D11).
    assert build_row("فملي", "TSE", "fameli")["vendor_id"] == "35425587644337450"


def test_unknown_tse_ticker_is_refused():
    with pytest.raises(ValueError, match="not found"):
        build_row("نیست", "TSE", "nist")


@pytest.mark.parametrize("slug", ["Fameli", "fa meli", "2fameli", ""])
def test_bad_slug_is_refused(slug):
    with pytest.raises(ValueError, match="slug"):
        build_row("GLD", "GLOBAL", slug)


def test_global_ticker_is_its_own_id():
    row = build_row("gld", "GLOBAL", "gld", name="SPDR Gold Shares")
    assert (row["ticker"], row["vendor_id"], row["currency"]) == ("GLD", "GLD", "USD")


def test_append_adds_one_line_and_keeps_the_existing_ones(csv_copy):
    before = csv_copy.read_bytes()
    append_to_csv(csv_copy, build_row("GLD", "GLOBAL", "gld", name="SPDR Gold Shares"))
    after = csv_copy.read_bytes()
    assert after.startswith(before)  # old lines untouched
    assert pd.read_csv(csv_copy, dtype=str)["slug"].tolist() == ["foolad", "spy", "gld"]


def test_duplicate_slug_or_id_is_refused(csv_copy):
    with pytest.raises(ValueError, match="slug 'foolad'"):
        append_to_csv(csv_copy, build_row("فملی", "TSE", "foolad"))
    with pytest.raises(ValueError, match="already in .* as 'foolad'"):
        append_to_csv(csv_copy, build_row("فولاد", "TSE", "foolad2"))
