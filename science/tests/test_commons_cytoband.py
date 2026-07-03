from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.cytoband import CytobandError, CytobandRow, bands_for_interval, load_cytobands

_FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_COMMONS_ROOT = _FIXTURES / "cytoband"
_DATA_ROOT = _FIXTURES / "cytoband-data"


def test_load_cytobands_reads_hash_verified_commons_fixture() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    assert rows[:2] == [
        CytobandRow(chrom="chr1", start=0, end=2300000, name="p36.33", gie_stain="gneg"),
        CytobandRow(chrom="chr1", start=2300000, end=5300000, name="p36.32", gie_stain="gpos25"),
    ]


def test_bands_for_interval_returns_all_overlaps_in_artifact_order() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    assert bands_for_interval(rows, chrom="chr1", start=2200000, end=5400000) == [
        CytobandRow(chrom="chr1", start=0, end=2300000, name="p36.33", gie_stain="gneg"),
        CytobandRow(chrom="chr1", start=2300000, end=5300000, name="p36.32", gie_stain="gpos25"),
        CytobandRow(chrom="chr1", start=5300000, end=7100000, name="p36.31", gie_stain="gneg"),
    ]


def test_bands_for_interval_allows_known_chromosome_no_overlap() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    assert bands_for_interval(rows, chrom="chr1", start=7100000, end=7200000) == []


def test_bands_for_interval_rejects_unknown_chromosome() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    with pytest.raises(CytobandError, match="unknown chromosome"):
        bands_for_interval(rows, chrom="1", start=0, end=1)


@pytest.mark.parametrize(("start", "end"), [(-1, 1), (1, 1), (2, 1)])
def test_bands_for_interval_rejects_invalid_interval(start: int, end: int) -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    with pytest.raises(CytobandError, match="invalid interval"):
        bands_for_interval(rows, chrom="chr1", start=start, end=end)


def test_parse_rejects_duplicate_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons import cytoband

    duplicate = [
        {"chrom": "chr1", "start": "0", "end": "1", "name": "p", "gie_stain": "new_stain"},
        {"chrom": "chr1", "start": "0", "end": "1", "name": "p", "gie_stain": "new_stain"},
    ]

    monkeypatch.setattr(cytoband, "_load_csv_rows", lambda *args, **kwargs: duplicate)

    with pytest.raises(CytobandError, match="duplicate cytoband row"):
        load_cytobands()


def test_runtime_accepts_new_non_empty_stain_value(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons import cytoband

    monkeypatch.setattr(
        cytoband,
        "_load_csv_rows",
        lambda *args, **kwargs: [{"chrom": "chr1", "start": "0", "end": "1", "name": "p", "gie_stain": "future"}],
    )

    assert load_cytobands() == [CytobandRow(chrom="chr1", start=0, end=1, name="p", gie_stain="future")]
