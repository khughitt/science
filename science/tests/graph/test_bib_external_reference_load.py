from __future__ import annotations

from pathlib import Path

from science_tool.graph.identity_table import ParticipationMode, build_identity_table
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nknowledge_profiles: {local: local}\nlayout_version: 3\n"


def _write(root: Path, *, bib: str | None = None) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    if bib is not None:
        (root / "papers").mkdir(parents=True, exist_ok=True)
        (root / "papers" / "references.bib").write_text(bib, encoding="utf-8")


def _write_paper_owner(root: Path, citekey: str) -> None:
    path = root / "entities" / "papers" / f"{citekey}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nid: "paper:{citekey}"\nkind: "paper"\ntitle: "{citekey}"\n'
        'status: "active"\ncreated: "2026-01-01"\nupdated: "2026-01-01"\n---\n',
        encoding="utf-8",
    )


def _load(root: Path, *, strict_identity: bool = False, include_commons: bool = False):
    return load_project_sources(
        root, include_commons=include_commons, strict_core_schema=False, strict_identity=strict_identity
    )


def test_bib_paper_is_external_reference_and_resolves(tmp_path: Path) -> None:
    _write(tmp_path, bib="@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n}\n")
    sources = _load(tmp_path)
    table = build_identity_table(sources)
    rows = [r for r in table.rows if r.canonical_id == "paper:Smith2024"]
    assert rows, "bib paper produced no identity row"
    assert all(r.participation_mode is ParticipationMode.EXTERNAL_REFERENCE for r in rows)
    assert ("bib", "paper:Smith2024") not in table.owners()  # external ref is not an owner
    resolver = ReferenceResolver.from_entities(sources.entities, identity_table=table)
    assert resolver.resolve("paper:Smith2024").status == "resolved"


def test_bib_defers_to_markdown_owner_under_strict_load(tmp_path: Path) -> None:
    # A markdown owner and a BibTeX entry with the same id must not collide; the
    # external-reference adapter defers to the authored owner.
    _write(tmp_path, bib="@article{Smith2024,\n  title = {Cells},\n}\n")
    _write_paper_owner(tmp_path, "Smith2024")
    sources = _load(tmp_path, strict_identity=True)  # would raise if bib emitted a 2nd declaration
    rows = [r for r in build_identity_table(sources).rows if r.canonical_id == "paper:Smith2024"]
    assert rows and all(r.participation_mode is ParticipationMode.OWNER for r in rows)
    assert all(r.adapter == "markdown" for r in rows)


def test_bib_entry_with_out_of_range_year_still_loads_as_entity(tmp_path: Path) -> None:
    # A balanced entry with an out-of-range year (clamped to None by load_bib_entries)
    # must still produce a loadable PaperEntity — proving the "backed -> node" invariant
    # survives schema validation, not just brace balance.
    _write(tmp_path, bib="@article{Old1600,\n  title = {Ancient},\n  year = {1600},\n}\n")
    sources = _load(tmp_path)
    ent = next((e for e in sources.entities if e.canonical_id == "paper:Old1600"), None)
    assert ent is not None, "out-of-range-year bib entry failed to synthesize a node"
    assert ent.kind == "paper"


def test_bib_paper_loads_under_default_commons_path(tmp_path: Path) -> None:
    # SMOKE TEST ONLY: the default include_commons=True load path works (no crash, the
    # bib paper is an external reference). This fixture references no commons ids and
    # declares no commons owner, so the commons resolver is a no-op — it does NOT
    # exercise the stated bib-vs-commons-owner precedence. That precedence is verified
    # in the final holistic review against a project with a real commons paper owner.
    _write(tmp_path, bib="@article{Smith2024,\n  title = {Cells},\n}\n")
    sources = _load(tmp_path, include_commons=True)
    table = build_identity_table(sources)
    rows = [r for r in table.rows if r.canonical_id == "paper:Smith2024"]
    assert rows and all(r.participation_mode is ParticipationMode.EXTERNAL_REFERENCE for r in rows)
