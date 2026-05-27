from __future__ import annotations

import csv
import io

from science_tool.commons.protein_crosswalk import _parse_crosswalk_rows, make_protein_key
from science_tool.commons.protein_crosswalk_build import (
    build_rows,
    fetch_text,
    parse_idmapping,
    parse_secondary,
)

_IDMAPPING = (
    "P04217\tUniProtKB-ID\tA1BG_HUMAN\n"
    "P04217\tEnsembl_PRO\tENSP00000263100\n"
    "P04217\tRefSeq\tNP_570602\n"
    "P04217\tHGNC\tHGNC:5\n"
    "P31946\tUniProtKB-ID\t1433B_HUMAN\n"
    "P31946\tEnsembl_PRO\tENSP00000300161\n"
    "P31946\tEnsembl_PRO\tENSP00000493072\n"
    "P31946\tHGNC\tHGNC:12849\n"
)

_SECONDARY = (
    "This is a header preamble line that must be ignored.\n"
    "Secondary AC     Primary AC\n"
    "P99999       P04217\n"
    "Q88888       Q00000\n"  # primary not in the reviewed set -> dropped
)


def test_make_protein_key_is_pipe_delimited_opaque_composite() -> None:
    assert make_protein_key(9606, "P04217") == "9606|uniprot|P04217"


def test_parse_idmapping_groups_by_accession_and_builds_gene_key() -> None:
    rows = parse_idmapping(_IDMAPPING)
    p31946 = next(r for r in rows if r["protein_key"] == "9606|uniprot|P31946")
    assert p31946["entry_name"] == "1433B_HUMAN"
    assert p31946["ensembl_protein"] == "ENSP00000300161;ENSP00000493072"  # multi-value joined on ';'
    assert p31946["status"] == "approved"
    p04217 = next(r for r in rows if r["protein_key"] == "9606|uniprot|P04217")
    assert p04217["refseq_protein"] == "NP_570602"
    assert p04217["gene_key"] == "9606|hgnc|HGNC:5"  # built from the HGNC xref via make_gene_key


def test_parse_secondary_emits_merged_rows_for_known_primaries_only() -> None:
    primary_keys = {"9606|uniprot|P04217"}
    rows = parse_secondary(_SECONDARY, primary_keys=primary_keys)
    assert len(rows) == 1
    merged = rows[0]
    assert merged["protein_key"] == "9606|uniprot|P99999"
    assert merged["status"] == "merged"
    assert merged["replacement_protein_keys"] == "9606|uniprot|P04217"


def test_build_rows_round_trips_through_the_resolver_parser() -> None:
    # The build output must parse cleanly back through the resolver's row parser
    # (same protein_key column, same ';' multi-value separator) — shared contract.
    rows = build_rows(idmapping_text=_IDMAPPING, secondary_text=_SECONDARY)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    parsed = _parse_crosswalk_rows(csv.DictReader(buf))
    assert len(parsed) == len(rows) == 3  # 2 primary + 1 merged


def test_fetch_text_is_callable_without_network() -> None:
    # Importing the module does not require a network call.
    assert callable(fetch_text)
