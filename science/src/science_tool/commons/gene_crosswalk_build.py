"""No-FASTA, mostly-no-network HGNC parsing for the gene crosswalk (Pillar C, C2).

Parses the HGNC 'complete set' (approved genes) and 'withdrawn' (withdrawn /
merged / split entries) release files into crosswalk rows keyed by the opaque
composite ``gene_key`` (see ``gene_crosswalk.make_gene_key``). HGNC's native
within-cell ``|`` separators are re-emitted as ``;`` so they never collide with
the ``|`` inside a ``gene_key``. ``fetch_text`` is the only network call
(build-time only); all parsing is pure. See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/C-D3).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from science_tool.commons.gene_crosswalk import make_gene_key

_HUMAN_TAXON = 9606
_OUT_SEP = ";"  # within-cell multi-value separator; NOT '|' (gene_key uses '|')


def _recode(cell: str) -> str:
    """HGNC separates within-cell multi-values with '|'; re-emit as ';' so the
    crosswalk never reuses the gene_key field delimiter."""
    return _OUT_SEP.join(part for part in (cell or "").split("|") if part)


def parse_complete_set(tsv_text: str) -> list[dict[str, Any]]:
    """Parse hgnc_complete_set.txt (tab-separated) into approved crosswalk rows."""
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    rows: list[dict[str, Any]] = []
    for rec in reader:
        hgnc_id = (rec.get("hgnc_id") or "").strip()
        if not hgnc_id:
            continue
        rows.append(
            {
                "gene_key": make_gene_key(_HUMAN_TAXON, hgnc_id),
                "symbol": (rec.get("symbol") or "").strip(),
                "entrez_id": (rec.get("entrez_id") or "").strip(),
                "ensembl_gene_id": (rec.get("ensembl_gene_id") or "").strip(),
                "alias_symbol": _recode(rec.get("alias_symbol", "")),
                "prev_symbol": _recode(rec.get("prev_symbol", "")),
                "status": "approved",
                "replacement_gene_keys": "",
            }
        )
    return rows


def parse_withdrawn(tsv_text: str) -> list[dict[str, Any]]:
    """Parse withdrawn.txt into withdrawn/merged/split rows with forward pointers.

    ``MERGED_INTO_REPORT(S)`` is a comma-separated list of ``HGNC_ID|SYMBOL|STATUS``
    entries; we keep each target's HGNC id and build its gene_key.
    ``STATUS == 'Entry Withdrawn'`` -> ``withdrawn`` (no replacement);
    ``'Merged/Split'`` -> ``merged`` (one target) or ``split`` (>1 target).
    """
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    rows: list[dict[str, Any]] = []
    for rec in reader:
        hgnc_id = (rec.get("HGNC_ID") or "").strip()
        if not hgnc_id:
            continue
        raw_status = (rec.get("STATUS") or "").strip()
        targets: list[str] = []
        for entry in (rec.get("MERGED_INTO_REPORT(S)") or "").split(","):
            entry = entry.strip()
            if not entry:
                continue
            target_id = entry.split("|")[0].strip()
            if target_id.startswith("HGNC:"):
                targets.append(make_gene_key(_HUMAN_TAXON, target_id))
        # Classify by resolvable-target count so the row always satisfies the
        # resolver's status<->count contract (merged == 1, split >= 2). A
        # 'Merged/Split' entry with no resolvable HGNC target is an anomaly; treat
        # it as a dead 'withdrawn' entry rather than emit an invalid 'merged' row.
        if raw_status == "Entry Withdrawn" or not targets:
            status = "withdrawn"
        elif len(targets) >= 2:
            status = "split"
        else:
            status = "merged"
        rows.append(
            {
                "gene_key": make_gene_key(_HUMAN_TAXON, hgnc_id),
                "symbol": (rec.get("WITHDRAWN_SYMBOL") or "").strip(),
                "entrez_id": "",
                "ensembl_gene_id": "",
                "alias_symbol": "",
                "prev_symbol": "",
                "status": status,
                "replacement_gene_keys": _OUT_SEP.join(targets),
            }
        )
    return rows


def build_rows(*, complete_set_text: str, withdrawn_text: str) -> list[dict[str, Any]]:
    """Merge approved + withdrawn rows into the full crosswalk row list."""
    return parse_complete_set(complete_set_text) + parse_withdrawn(withdrawn_text)


def fetch_text(url: str) -> str:
    """Fetch a text release file (build-time only; never called at resolve time)."""
    import httpx

    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text
