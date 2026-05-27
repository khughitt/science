from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.assembly import (
    AssemblyEntry,
    available_assembly_keys,
    load_assembly_registry,
    resolve_assembly,
)

_FIX = Path(__file__).parent / "fixtures" / "commons" / "assembly"
_COMMONS = _FIX  # entity store
_DATA = Path(__file__).parent / "fixtures" / "commons" / "assembly-data"  # data root


def _kw() -> dict:
    return {"commons_root": _COMMONS, "data_root": _DATA}


def test_load_returns_entries() -> None:
    entries = load_assembly_registry(**_kw())
    assert all(isinstance(e, AssemblyEntry) for e in entries)
    assert {e.label for e in entries} == {"GRCh38", "GRCh37"}


def test_available_keys_are_the_seqcol_digests() -> None:
    keys = available_assembly_keys(**_kw())
    assert "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp" in keys
    assert "5K4odB173rjao1Cnbk5BnvLt9V7aPAa2" in keys
    assert len(keys) == 2


def test_resolve_by_exact_digest() -> None:
    entry = resolve_assembly("g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp", **_kw())
    assert entry is not None and entry.label == "GRCh38"


def test_resolve_by_label_alias() -> None:
    entry = resolve_assembly("GRCh37", **_kw())
    assert entry is not None and entry.seqcol_digest == "5K4odB173rjao1Cnbk5BnvLt9V7aPAa2"


def test_resolve_unknown_returns_none() -> None:
    assert resolve_assembly("not-a-real-key", **_kw()) is None


# --- registry row validation (pure, no I/O) — finding 5 ---


def test_parse_rejects_duplicate_member_key() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    rows = [
        {"seqcol_digest": "DUP", "label": "A", "accession": ""},
        {"seqcol_digest": "DUP", "label": "B", "accession": ""},
    ]
    with pytest.raises(AssemblyRegistryError, match="duplicate member key"):
        _parse_registry_rows(rows)


def test_parse_rejects_blank_digest() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    with pytest.raises(AssemblyRegistryError, match="blank seqcol_digest"):
        _parse_registry_rows([{"seqcol_digest": "  ", "label": "A", "accession": ""}])


def test_parse_rejects_missing_column() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    with pytest.raises(AssemblyRegistryError, match="missing required column"):
        _parse_registry_rows([{"label": "A", "accession": ""}])
