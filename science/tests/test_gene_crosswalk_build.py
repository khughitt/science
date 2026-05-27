from __future__ import annotations

import csv
import io

from science_tool.commons.gene_crosswalk import _parse_crosswalk_rows, make_gene_key
from science_tool.commons.gene_crosswalk_build import (
    build_rows,
    fetch_text,
    parse_complete_set,
    parse_withdrawn,
)

_COMPLETE = (
    "hgnc_id\tsymbol\tstatus\talias_symbol\tprev_symbol\tentrez_id\tensembl_gene_id\n"
    "HGNC:5\tA1BG\tApproved\t\t\t1\tENSG00000121410\n"
    "HGNC:37133\tA1BG-AS1\tApproved\tFLJ23569|XYZ\tNCRNA00181|A1BGAS\t503538\tENSG00000268895\n"
)

_WITHDRAWN = (
    "HGNC_ID\tSTATUS\tWITHDRAWN_SYMBOL\tMERGED_INTO_REPORT(S)\n"
    "HGNC:99991\tMerged/Split\tOLDA\tHGNC:5|A1BG|Approved\n"
    "HGNC:99992\tMerged/Split\tSPLITME\tHGNC:5|A1BG|Approved, HGNC:37133|A1BG-AS1|Approved\n"
    "HGNC:99993\tEntry Withdrawn\tGONE\t\n"
)


def test_make_gene_key_is_pipe_delimited_opaque_composite() -> None:
    assert make_gene_key(9606, "HGNC:5") == "9606|hgnc|HGNC:5"


def test_parse_complete_set_recodes_multivalue_to_semicolon() -> None:
    rows = parse_complete_set(_COMPLETE)
    a1bgas = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:37133")
    assert a1bgas["symbol"] == "A1BG-AS1"
    assert a1bgas["entrez_id"] == "503538"
    assert a1bgas["alias_symbol"] == "FLJ23569;XYZ"  # HGNC '|' re-coded to ';'
    assert a1bgas["prev_symbol"] == "NCRNA00181;A1BGAS"
    assert a1bgas["status"] == "approved"


def test_parse_withdrawn_merged_has_single_forward_pointer() -> None:
    rows = parse_withdrawn(_WITHDRAWN)
    merged = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:99991")
    assert merged["status"] == "merged"
    assert merged["replacement_gene_keys"] == "9606|hgnc|HGNC:5"


def test_parse_withdrawn_split_has_multiple_forward_pointers() -> None:
    rows = parse_withdrawn(_WITHDRAWN)
    split = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:99992")
    assert split["status"] == "split"
    assert split["replacement_gene_keys"] == "9606|hgnc|HGNC:5;9606|hgnc|HGNC:37133"


def test_parse_withdrawn_entry_withdrawn_has_no_replacement() -> None:
    rows = parse_withdrawn(_WITHDRAWN)
    gone = next(r for r in rows if r["gene_key"] == "9606|hgnc|HGNC:99993")
    assert gone["status"] == "withdrawn"
    assert gone["replacement_gene_keys"] == ""


def test_build_rows_round_trips_through_the_resolver_parser() -> None:
    # The build output must parse cleanly back through the resolver's row parser
    # (same gene_key column, same ';' multi-value separator) — they share a contract.
    rows = build_rows(complete_set_text=_COMPLETE, withdrawn_text=_WITHDRAWN)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    parsed = _parse_crosswalk_rows(csv.DictReader(buf))
    assert len(parsed) == len(rows) == 5


def test_fetch_text_is_callable_without_network() -> None:
    # Importing the module does not require a network call.
    assert callable(fetch_text)
