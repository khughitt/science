"""Auto-derive `superseded` — status **and its derived lineage** — from supersedes chains.

Leg 3 of the D4 supersedable gate. Everything here is on `interpretation`, and deliberately so:
`mark_superseded` CANNOT stamp a `hypothesis` in this task. `_supports_superseded` consults
`_STATUS_VALUES`, and `hypothesis` does not declare `superseded` until Task 8's descriptor — so a
hypothesis member is routed to `skipped_kinds`, nothing is written, and the write boundary's
`_validate_status` would reject the status anyway. A hypothesis apply-test here would not fail
loudly; it would report `to_mark == []`, write nothing, and go **green over an operation that did
nothing**. *A test belongs in the task where its subject exists.*

`interpretation` declares `superseded` AND is an admitted `sci:supersedes` endpoint today, so leg 3
— a generic change: the inverse, the kind-pair refusal, the seven-way edge admission, the acyclicity
scan, the reconciliation — is exercised end to end without changing what any existing file means.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from science_model.entities import Entity

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.consolidation import (
    IdResolution,
    SupersededChain,
    SupersessionError,
    SupersessionInputs,
    build_supersedes_graph,
    mark_superseded,
)
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import SourceRelation


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> Path:
    # `title` is REQUIRED by the entity model. The old builder was a raw frontmatter scan and never
    # noticed; it now resolves through `load_project_sources` -- the SAME authority `materialize`
    # uses -- which hard-fails on an entity that does not satisfy its own model.
    fm = {"title": name, **fm}
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.md"
    path.write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )
    return path


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: chain-test\n", encoding="utf-8")


def _supersedes(target: str) -> dict[str, str]:
    """One canonical supersession edge, in the ONLY spelling the toolkit reads."""
    return {"predicate": "sci:supersedes", "target": target}


def _relate(root: Path, kind_dir: str, name: str, *, supersedes: str) -> None:
    """Append a canonical supersedes edge to an entity written by `_write`."""
    path = root / "entities" / kind_dir / f"{name}.md"
    fm = read_frontmatter(path)
    assert fm is not None
    fm.setdefault("relations", []).append(_supersedes(supersedes))
    _write(root, kind_dir, name, fm)


def _manual_alias(root: Path, alias: str, canonical: str) -> None:
    """Register a project manual alias, which `load_project_sources` folds into the resolver.

    `build_alias_map` registers the mapping UNCONDITIONALLY, so this is how a reference RESOLVES to
    an id that NO RECORD BACKS — a dangling edge, not an unmanaged one.
    """
    path = root / "knowledge" / "sources" / "local" / "mappings.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    aliases = (existing or {}).get("aliases", {})
    aliases[alias] = canonical
    path.write_text(yaml.safe_dump({"aliases": aliases}, sort_keys=False), encoding="utf-8")


def _archive(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    """Write an entity and archive it THROUGH THE REAL OP — never by hand-building the index.

    `archive_entities` selects by status, relocates the file under `entities/_archive/`, and appends
    the index row. A hand-written `_archive/` file with no index row (or the reverse) is a state the
    tool cannot produce, and a fixture that fabricates one tests the fixture.
    """
    from science_tool.archive import archive_entities

    _write(root, kind_dir, name, fm)
    archive_entities(root, apply=True)


def _entity(cid: str, kind: str) -> Entity:
    return Entity(
        id=cid,
        canonical_id=cid,
        kind=kind,
        title=cid,
        project="p",
        file_path=f"{cid}.md",
        content_preview="",
        ontology_terms=[],
        related=[],
        source_refs=[],
    )


def _resolution(*, mutable: set[str], archived: set[str], kinds: dict[str, str]) -> IdResolution:
    """Construct the resolution bundle DIRECTLY.

    The builder is a pure function of its inputs — that is the whole reason it takes an
    `IdResolution` — so the commons / non-markdown populations, which would otherwise need a commons
    repo on disk, are expressible as the data they actually are.
    """
    entities = [_entity(cid, kind) for cid, kind in kinds.items()]
    return IdResolution(
        resolver=ReferenceResolver.from_entities(entities),
        mutable=frozenset(mutable),
        archived=frozenset(archived),
        kind_by_id=kinds,
    )


def _inputs(
    entries: list[tuple[Path, dict[str, Any]]],
    *,
    mutable: set[str],
    archived: set[str],
    kinds: dict[str, str],
    lineage: list[SourceRelation] | None = None,
) -> SupersessionInputs:
    """The builder's inputs, constructed DIRECTLY — resolution AND the edge stream.

    `lineage` defaults to mirroring `sources._entity_nested_relations`: one `SourceRelation` per
    nested `relations:` entry, `source_path` = the entity's file. The builder reads edges from THE
    STREAM now and never from frontmatter, so an edge a test wants has to BE in the stream — which is
    the point. Pass `lineage` explicitly to author an edge in a different carrier, or in a record
    with no markdown at all.
    """
    if lineage is None:
        lineage = [
            SourceRelation(
                subject=str(fm["id"]),
                predicate=str(rel["predicate"]),
                object=str(rel["target"]),
                source_path=str(path),
            )
            for path, fm in entries
            for rel in fm.get("relations", [])
        ]
    return SupersessionInputs(
        entries=tuple(entries),
        resolution=_resolution(mutable=mutable, archived=archived, kinds=kinds),
        lineage=tuple(lineage),
    )


def _interp(root: Path, name: str, **fm: Any) -> Path:
    return _write(root, "interpretations", name, {"id": f"interpretation:{name}", "kind": "interpretation", **fm})


# ---------------------------------------------------------------------------------------------
# topology — the pre-existing contract, unchanged
# ---------------------------------------------------------------------------------------------


def test_report_linear_chain_lists_members(tmp_path: Path) -> None:
    _seed(tmp_path)
    # v3 <- v4 <- v5 : v5 supersedes v4, v4 supersedes v3. Survivor = v5.
    _interp(tmp_path, "i-v3")
    _interp(tmp_path, "i-v4", relations=[_supersedes("interpretation:i-v3")])
    _interp(tmp_path, "i-v5", relations=[_supersedes("interpretation:i-v4")])

    report = mark_superseded(tmp_path, apply=False)

    assert report["applied"] == []
    assert len(report["chains"]) == 1
    chain = report["chains"][0]
    assert chain["survivor"] == "interpretation:i-v5"
    assert chain["linear"] is True
    assert set(chain["members"]) == {"interpretation:i-v3", "interpretation:i-v4"}
    assert set(report["to_mark"]) == {"interpretation:i-v3", "interpretation:i-v4"}
    assert report["non_linear"] == []
    assert report["skipped_kinds"] == []


def test_amends_relation_does_not_mark_superseded(tmp_path: Path) -> None:
    _seed(tmp_path)
    # sci:amends is a revision, NOT a replacement — it must not mark the target.
    _interp(tmp_path, "i-v3")
    _interp(tmp_path, "i-v4", relations=[{"predicate": "sci:amends", "target": "interpretation:i-v3"}])

    report = mark_superseded(tmp_path, apply=False)

    assert report["chains"] == []
    assert report["to_mark"] == []


def test_report_flags_non_linear_chain_and_skips_it(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Branched: both v4a and v4b supersede v3 (v3 has in-degree 2). Ambiguous survivor.
    _interp(tmp_path, "i-v3")
    _interp(tmp_path, "i-v4a", relations=[_supersedes("interpretation:i-v3")])
    _interp(tmp_path, "i-v4b", relations=[_supersedes("interpretation:i-v3")])

    report = mark_superseded(tmp_path, apply=False)

    assert report["chains"] == []
    assert report["to_mark"] == []
    assert len(report["non_linear"]) == 1
    assert set(report["non_linear"][0]["nodes"]) == {
        "interpretation:i-v3",
        "interpretation:i-v4a",
        "interpretation:i-v4b",
    }


def test_member_whose_kind_lacks_superseded_vocab_is_skipped_not_crashed(tmp_path: Path) -> None:
    _seed(tmp_path)
    # workflow-run is a supersedes endpoint but declares NO status vocabulary. The member must be
    # reported under skipped_kinds, never crash. (This is the route a `hypothesis` takes TODAY —
    # which is exactly why no hypothesis apply-test can live in this task.)
    _write(tmp_path, "workflow-runs", "wr-old", {"id": "workflow-run:wr-old", "kind": "workflow-run"})
    _write(tmp_path, "workflow-runs", "wr-new", {"id": "workflow-run:wr-new", "kind": "workflow-run",
                                                 "relations": [_supersedes("workflow-run:wr-old")]})

    report = mark_superseded(tmp_path, apply=False)

    assert report["to_mark"] == []
    assert {entry["id"] for entry in report["skipped_kinds"]} == {"workflow-run:wr-old"}
    assert report["skipped_kinds"][0]["kind"] == "workflow-run"


def test_apply_sets_superseded_status_on_members(tmp_path: Path) -> None:
    _seed(tmp_path)
    _interp(tmp_path, "i-v3")
    _interp(tmp_path, "i-v4", relations=[_supersedes("interpretation:i-v3")])

    report = mark_superseded(tmp_path, apply=True)
    assert report["applied"] == ["interpretation:i-v3"]

    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v3.md")
    assert fm is not None and fm["status"] == "superseded"
    fm_v4 = read_frontmatter(tmp_path / "entities/interpretations/i-v4.md")   # survivor untouched
    assert fm_v4 is not None and fm_v4.get("status") in (None, "active")


def test_cli_mark_superseded_dry_run_emits_json(tmp_path: Path) -> None:
    import json

    from click.testing import CliRunner

    from science_tool.cli import main

    _seed(tmp_path)
    _interp(tmp_path, "i-v3")
    _interp(tmp_path, "i-v4", relations=[_supersedes("interpretation:i-v3")])

    result = CliRunner().invoke(main, ["entities", "mark-superseded", "--project-root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] == []                          # dry run
    assert payload["to_mark"] == ["interpretation:i-v3"]

    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v3.md")
    assert fm is not None and fm.get("status") in (None, "active")


# ---------------------------------------------------------------------------------------------
# THE LINEAGE — the inverse is a projection of the authored edge
# ---------------------------------------------------------------------------------------------


def test_the_stamped_record_CARRIES_its_lineage(tmp_path: Path) -> None:
    # The operation wrote `status` ALONE, so the toolkit's own supersession produced a record with no
    # lineage and no basis -- which Task 10's schema boundary refuses. A tool that cannot satisfy the
    # schema it enforces has not implemented supersession; it has renamed it.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="active")
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:i-v1")])

    mark_superseded(tmp_path, apply=True)
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")

    assert fm is not None
    assert fm["status"] == "superseded"
    assert fm["superseded_by"] == "interpretation:i-v2"


def test_a_CHAIN_records_the_immediate_superseder_not_the_survivor(tmp_path: Path) -> None:
    # A -> B -> C. The survivor is the head, but the edge that closed C was authored by B.
    # `superseded_by` INVERTS the authored edge; it does not summarize the chain. Stamping the
    # survivor onto every member would discard B's supersession entirely -- and a two-node fixture
    # cannot tell the difference, which is the only reason this test exists.
    _seed(tmp_path)
    for name in ("i-v1", "i-v2", "i-v3"):
        _interp(tmp_path, name, status="active")
    _relate(tmp_path, "interpretations", "i-v2", supersedes="interpretation:i-v1")
    _relate(tmp_path, "interpretations", "i-v3", supersedes="interpretation:i-v2")

    mark_superseded(tmp_path, apply=True)

    v1 = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    v2 = read_frontmatter(tmp_path / "entities/interpretations/i-v2.md")
    v3 = read_frontmatter(tmp_path / "entities/interpretations/i-v3.md")
    assert v1 is not None and v2 is not None and v3 is not None
    assert v1["superseded_by"] == "interpretation:i-v2"      # NOT i-v3, the survivor
    assert v2["superseded_by"] == "interpretation:i-v3"
    assert "superseded_by" not in v3


# ---------------------------------------------------------------------------------------------
# EDGE ADMISSION — legality is decided BEFORE topology, and BEFORE ownership
# ---------------------------------------------------------------------------------------------


def test_an_ILLEGAL_kind_pair_is_REFUSED_not_written(tmp_path: Path) -> None:
    # `workflow-run -> interpretation` is not an allowed `sci:supersedes` pair. `materialize` rejects
    # the edge, but this path never calls materialize -- so nothing stopped the topology scan from
    # stamping `superseded_by: workflow-run:...` onto an interpretation.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="active")
    _write(tmp_path, "workflow-runs", "wr-1", {"id": "workflow-run:wr-1", "kind": "workflow-run",
                                               "relations": [_supersedes("interpretation:i-v1")]})

    report = mark_superseded(tmp_path, apply=False)

    assert report["to_mark"] == []
    assert report["mismatched_kinds"] == [
        {"id": "interpretation:i-v1", "superseder": "workflow-run:wr-1",
         "path": "entities/workflow-runs/wr-1.md",
         "reason": "workflow-run -> interpretation is not an allowed sci:supersedes pair"},
    ]

    with pytest.raises(SupersessionError):        # ALL-OR-NONE: apply refuses outright
        mark_superseded(tmp_path, apply=True)
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    assert fm is not None and fm["status"] == "active" and "superseded_by" not in fm   # UNTOUCHED


def test_an_ILLEGAL_edge_does_not_SUPPRESS_a_legal_chain(tmp_path: Path) -> None:
    # THE ORDERING TEST -- and the reason the pair rule lives in the BUILDER, not in the apply loop.
    #
    # An illegal edge is still an EDGE: it joins the component and counts toward in-degree. With the
    # check inside the `linear` loop, `_classify` sees in_deg[i-v1] == 2, calls the component
    # NON-LINEAR, and never reaches that loop at all. So `mismatched_kinds` comes back EMPTY -- the
    # guard never runs -- AND the legal `i-v2 -> i-v1` supersession is silently suppressed, misfiled
    # as "branched or cyclic" when nothing branched: one of its edges was not a supersession.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="active")
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:i-v1")])
    _write(tmp_path, "workflow-runs", "wr-1", {"id": "workflow-run:wr-1", "kind": "workflow-run",
                                               "relations": [_supersedes("interpretation:i-v1")]})

    report = mark_superseded(tmp_path, apply=False)

    # The illegal edge is REPORTED, not absorbed...
    assert [m["superseder"] for m in report["mismatched_kinds"]] == ["workflow-run:wr-1"]
    # ...and dropping it leaves a chain that is perfectly linear.
    assert report["non_linear"] == []
    assert report["chains"] == [
        {"survivor": "interpretation:i-v2", "members": ["interpretation:i-v1"], "linear": True}
    ]
    assert report["to_mark"] == ["interpretation:i-v1"]


def test_a_mixed_corpus_writes_NOTHING_on_apply(tmp_path: Path) -> None:
    # THE ALL-OR-NONE REGRESSION, and a SEPARATE test from the one above on purpose. The dry-run test
    # proves the illegal edge is reported and the legal chain survives; it says nothing about apply,
    # because it never calls it. An implementation that raises AFTER stamping the legal, unaffected
    # member passes every other test in this file.
    #
    # It asserts the BYTES of the legal target, not the report: the report is what the operation
    # SAYS it did.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="active")
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:i-v1")])
    _interp(tmp_path, "i-w1", status="active")
    _write(tmp_path, "workflow-runs", "wr-1", {"id": "workflow-run:wr-1", "kind": "workflow-run",
                                               "relations": [_supersedes("interpretation:i-w1")]})
    legal = tmp_path / "entities/interpretations/i-v1.md"
    before = legal.read_bytes()

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)

    assert legal.read_bytes() == before


def test_an_ARCHIVED_target_is_a_VALID_edge_with_no_live_mutation(tmp_path: Path) -> None:
    # THE MIDDLE STATE. Superseding a record and later archiving it is the NORMAL end of a lineage:
    # the canonical edge is TRUE, the record exists, and it is frozen. The live scan does not read
    # `_archive/`, so before this task the edge was indistinguishable from a typo and dropped in
    # silence. It REPORTS and it does NOT BLOCK.
    _seed(tmp_path)
    _archive(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old",
                                                    "kind": "interpretation", "status": "superseded"})
    _interp(tmp_path, "i-new", relations=[_supersedes("interpretation:i-old")])
    _interp(tmp_path, "j-v1", status="active")
    _interp(tmp_path, "j-v2", relations=[_supersedes("interpretation:j-v1")])

    report = mark_superseded(tmp_path, apply=True)       # does NOT raise

    assert report["archived_targets"] == [
        {"id": "interpretation:i-old", "superseder": "interpretation:i-new",
         "path": "entities/interpretations/i-new.md",
         "reason": "target is archived (frozen); no live record to stamp"},
    ]
    assert report["unresolved_targets"] == []
    # The archived target is not a chain member and is never stamped...
    assert report["chains"] == [
        {"survivor": "interpretation:j-v2", "members": ["interpretation:j-v1"], "linear": True}
    ]
    # ...and the unrelated live chain applies normally. An archived edge is not an error.
    assert report["applied"] == ["interpretation:j-v1"]


def test_an_UNRESOLVED_target_is_REPORTED_and_BLOCKS_apply(tmp_path: Path) -> None:
    # THE STATE THE OLD `if dst not in known: continue` ERASED. A canonical supersession edge
    # pointing at an id that exists NOWHERE is a dangling authored relation. The old filter made
    # "a derived inverse can never dangle" true by DELETING the counterexample: no edge, no chain,
    # no finding, clean report, green apply.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="active")
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:i-v1"),
                                         _supersedes("interpretation:i-GONE")])
    target = tmp_path / "entities/interpretations/i-v1.md"
    before = target.read_bytes()

    report = mark_superseded(tmp_path, apply=False)

    assert report["unresolved_targets"] == [
        {"id": "interpretation:i-GONE", "superseder": "interpretation:i-v2",
         "path": "entities/interpretations/i-v2.md",
         "reason": "sci:supersedes target resolves to nothing"},
    ]
    assert report["archived_targets"] == []
    # Report mode still enumerates EVERYTHING -- diagnosis is never gated on the thing being
    # diagnosable -- so the legal chain is fully described alongside the dangling edge.
    assert report["to_mark"] == ["interpretation:i-v1"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)
    assert target.read_bytes() == before          # all-or-none, again


def test_a_LIVE_ALIAS_target_RESOLVES_and_is_not_called_unresolved(tmp_path: Path) -> None:
    # THE FALSE-POSITIVE GUARD, and the one that would have BROKEN WORKING PROJECTS.
    #
    # `materialize` resolves relation targets through a ReferenceResolver built over live
    # `aliases`/`same_as`, so a supersedes edge authored against an alias materializes perfectly
    # today. A builder that answers "live? archived? nowhere?" by RAW STRING MEMBERSHIP calls that
    # same edge `unresolved` -- and `unresolved` BLOCKS apply. Trading a silent drop for a false
    # refusal is not a fix; it turns a working corpus into a refused one.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="active", aliases=["interpretation:old-name"])
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:old-name")])   # the ALIAS

    report = mark_superseded(tmp_path, apply=True)

    assert report["unresolved_targets"] == []               # NOT a dangling edge
    assert report["applied"] == ["interpretation:i-v1"]     # canonicalized, then stamped
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    assert fm is not None and fm["superseded_by"] == "interpretation:i-v2"


def test_an_ARCHIVED_ALIAS_target_resolves_to_the_ARCHIVE_not_to_nowhere(tmp_path: Path) -> None:
    # Same trap, other population. `ArchiveIndex.resolvable_ids()` maps every archived alias to its
    # canonical id, and `load_project_sources` folds exactly that map into the resolver -- which is
    # why an alias of an ARCHIVED entity resolves in the graph. `active_by_id` is canonical-only and
    # does not, which is precisely the draft that would have reported this edge `unresolved`.
    _seed(tmp_path)
    _archive(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old",
                                                    "kind": "interpretation", "status": "superseded",
                                                    "aliases": ["interpretation:i-ancient"]})
    _interp(tmp_path, "i-new", relations=[_supersedes("interpretation:i-ancient")])

    report = mark_superseded(tmp_path, apply=True)      # does NOT raise

    assert report["unresolved_targets"] == []
    assert report["archived_targets"] == [
        {"id": "interpretation:i-old", "superseder": "interpretation:i-new",   # CANONICAL, not alias
         "path": "entities/interpretations/i-new.md",           # WHERE THE EDGE IS AUTHORED
         "reason": "target is archived (frozen); no live record to stamp"},
    ]


def test_a_RESOLVABLE_LEGAL_target_WE_DO_NOT_OWN_is_reported_and_does_not_BLOCK() -> None:
    # THE SIXTH ROW. An earlier draft's `else` swallowed this one: it classified with
    # `if dst not in live: -> archived`, on the theory that "an id cannot resolve to neither." It
    # can -- the commons overlay and non-markdown sources put ids into the resolver that are in
    # NEITHER the live markdown scan NOR the archive index -- and that draft would have filed this
    # target as a frozen archived record, then indexed `kind_by_id[dst]` for a key never there.
    #
    # NOTE the target is a `report`, not a `dataset`: an unmanaged target must still be a LEGAL
    # endpoint to land here. The illegal one is the next test.
    entries: list[tuple[Path, dict[str, Any]]] = [
        (Path("i-v2.md"), {"id": "interpretation:i-v2", "kind": "interpretation",
                           "relations": [_supersedes("report:commons-thing")]}),
        (Path("j-v1.md"), {"id": "interpretation:j-v1", "kind": "interpretation", "status": "active"}),
        (Path("j-v2.md"), {"id": "interpretation:j-v2", "kind": "interpretation",
                           "relations": [_supersedes("interpretation:j-v1")]}),
    ]
    graph = build_supersedes_graph(_inputs(
        entries,
        mutable={"interpretation:i-v2", "interpretation:j-v1", "interpretation:j-v2"},
        archived=set(),
        kinds={"interpretation:i-v2": "interpretation", "interpretation:j-v1": "interpretation",
               "interpretation:j-v2": "interpretation",
               "report:commons-thing": "report"},   # backed by a source; not live markdown
    ))

    assert graph.unresolved_targets == ()                  # it RESOLVES
    assert graph.archived_targets == ()                    # ...and it is NOT archived
    assert graph.mismatched == ()                          # ...and the pair is LEGAL
    assert [u["id"] for u in graph.unmanaged_targets] == ["report:commons-thing"]
    assert graph.linear == (
        SupersededChain(survivor="interpretation:j-v2", superseded=("interpretation:j-v1",)),
    )


def test_an_ILLEGAL_pair_into_an_UNMANAGED_target_is_MISMATCHED_not_benign() -> None:
    # THE ORDERING BUG, one layer down. `dataset` is not a `supersedes` endpoint at ANY position, so
    # `materialize` RAISES on this edge. But a draft that answered OWNERSHIP first saw "resolves, not
    # mutable" and `continue`d into `unmanaged_targets` -- benign, unstampable, apply proceeds --
    # WITHOUT EVER REACHING `relation_allows_kinds`. The pair check sat downstream of the corruption
    # it was written to detect. Legality first, ON THE RESOLVED ENTITY; ownership after.
    entries: list[tuple[Path, dict[str, Any]]] = [
        (Path("i.md"), {"id": "interpretation:new", "kind": "interpretation",
                        "relations": [_supersedes("dataset:commons-thing")]}),
    ]
    graph = build_supersedes_graph(_inputs(
        entries,
        mutable={"interpretation:new"}, archived=set(),
        kinds={"interpretation:new": "interpretation", "dataset:commons-thing": "dataset"},
    ))

    assert graph.unmanaged_targets == ()                   # NOT waved through as benign debt
    assert [m["id"] for m in graph.mismatched] == ["dataset:commons-thing"]
    assert "interpretation -> dataset" in graph.mismatched[0]["reason"]


def test_an_ILLEGAL_pair_into_the_ARCHIVE_is_MISMATCHED_not_benign(tmp_path: Path) -> None:
    # Same bug, other population, end to end: an archived row carries a KIND, so the pair is
    # answerable -- and it is wrong. "We won't stamp it" was never a licence to skip the edge's own
    # validity. It BLOCKS, exactly as a live illegal pair does.
    _seed(tmp_path)
    _archive(tmp_path, "datasets", "d-old", {"id": "dataset:d-old", "kind": "dataset",
                                             "status": "retired"})
    _interp(tmp_path, "i-new", relations=[_supersedes("dataset:d-old")])

    report = mark_superseded(tmp_path, apply=False)

    assert report["archived_targets"] == []                # NOT a benign historical edge
    assert [m["id"] for m in report["mismatched_kinds"]] == ["dataset:d-old"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


def test_an_ARCHIVE_ROW_WITH_NO_KIND_is_refused_EXACTLY_AS_MATERIALIZE_refuses_it(tmp_path: Path) -> None:
    # `ArchiveRow.kind` is nullable -- a row written before the field existed carries none.
    # Materialize turns that into `kind=arow.kind or ""`, and because `supersedes` declares
    # `allowed_kind_pairs` -- an authoritative allow-list -- `""` matches NO pair, so materialize
    # RAISES on the edge.
    #
    # A draft here derived the kind from the ID PREFIX instead, which would have read
    # `interpretation` off `interpretation:i-old` and ADMITTED the edge: consolidation stamps the
    # file, and the graph then refuses to build. A write that succeeds and leaves the corpus
    # unmaterializable is worse than either authority refusing alone. Both must refuse the SAME
    # corpus, so this mirrors `or ""` verbatim and the row BLOCKS.
    _seed(tmp_path)
    _archive(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old",
                                                    "kind": "interpretation", "status": "superseded"})
    _strip_archive_kind(tmp_path, "interpretation:i-old")
    _interp(tmp_path, "i-new", relations=[_supersedes("interpretation:i-old")])

    report = mark_superseded(tmp_path, apply=False)

    assert report["archived_targets"] == []       # NOT a benign historical edge
    assert [m["id"] for m in report["mismatched_kinds"]] == ["interpretation:i-old"]
    assert "(no kind)" in report["mismatched_kinds"][0]["reason"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


def _strip_archive_kind(root: Path, entity_id: str) -> None:
    """Remove `kind` from an archive INDEX ROW — the nullable-field state `ArchiveRow` allows.

    The entity is archived through the real op first (so the file and the row both exist and agree);
    this then reproduces a row written before `kind` existed. Authoring the entity without a `kind`
    is NOT an option: the model requires it, so `load_project_sources` would refuse the project
    outright and we would never reach the edge under test.

    The index is JSONL — one `ArchiveRow` per line (`archive.py:62`) — so it is rewritten as such.
    """
    import json

    from science_tool.archive import archive_index_path

    path = archive_index_path(root)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if row.get("id") == entity_id:
            row.pop("kind", None)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_an_ALIAS_to_an_id_NOTHING_BACKS_is_DANGLING_and_BLOCKS(tmp_path: Path) -> None:
    # ROW 2. `build_alias_map` registers a manual alias UNCONDITIONALLY, so this token RESOLVES -- to
    # an id that no live entity, no archive row, and no source record backs. A draft that keyed
    # ownership off `mutable`/`archived` alone would have called that `unmanaged`: benign, no block.
    #
    # But with no record there is no KIND, and with no kind the legality question is UNANSWERABLE.
    # An unanswerable guard must not report "benign". Dangling with extra steps, and it blocks.
    _seed(tmp_path)
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:ghost")])
    _manual_alias(tmp_path, "interpretation:ghost", "interpretation:ghost-canonical")

    report = mark_superseded(tmp_path, apply=False)

    assert report["unmanaged_targets"] == []               # NOT benign debt
    assert [u["id"] for u in report["unresolved_targets"]] == ["interpretation:ghost-canonical"]
    assert "no live, archived, or source record backs" in report["unresolved_targets"][0]["reason"]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


# ---------------------------------------------------------------------------------------------
# THE FOURTH OUTCOME — an inverse that RESOLVES and is still groundless
# ---------------------------------------------------------------------------------------------


def test_a_RESOLVABLE_but_GROUNDLESS_inverse_is_REPORTED_and_BLOCKS_apply(tmp_path: Path) -> None:
    # `i-v1.superseded_by = i-v2`, and i-v2 EXISTS. But nobody authored `i-v2 sci:supersedes i-v1`.
    #
    # Schema passes (a non-empty string discharges the `superseded` anyOf). `check_resolution` passes
    # (the id RESOLVES -- it only ever caught DANGLING refs). Reconciliation never looks (i-v1 is in
    # no chain, because there is no edge). The write boundary never sees it. FOUR NETS, ZERO
    # COVERAGE -- for the exact failure `supersedes:` was deleted to prevent: a lineage that is true
    # and grounded in nothing.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="superseded", superseded_by="interpretation:i-v2")
    _interp(tmp_path, "i-v2", status="active")
    target = tmp_path / "entities/interpretations/i-v1.md"
    before = target.read_bytes()

    report = mark_superseded(tmp_path, apply=False)

    assert report["unresolved_targets"] == []     # it RESOLVES. That is the whole point.
    assert report["unbacked_inverses"] == [
        {"id": "interpretation:i-v1", "superseder": "interpretation:i-v2",
         "reason": "authored superseded_by has no canonical sci:supersedes edge behind it"},
    ]

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)
    assert target.read_bytes() == before          # blocks, and does not silently "repair" it either


def test_a_NON_LINEAR_member_is_BACKED_even_though_it_is_never_stamped(tmp_path: Path) -> None:
    # THE CONTROL for the test above, and the reason `unbacked` is computed against `edges` rather
    # than `superseder_by_id`. A member of a BRANCHED component has a real in-edge -- it is grounded
    # -- but it is never stamped, because the survivor is ambiguous. `superseder_by_id` covers LINEAR
    # chains only, so comparing against it would report every non-linear member as unbacked and block
    # apply on a corpus whose only sin is a branch the tool already handles by skipping it.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="superseded", superseded_by="interpretation:i-a")
    for name in ("i-a", "i-b"):     # TWO supersedors -> branched -> non-linear
        _interp(tmp_path, name, relations=[_supersedes("interpretation:i-v1")])

    report = mark_superseded(tmp_path, apply=True)      # does NOT raise

    assert report["unbacked_inverses"] == []            # the edge i-a -> i-v1 was ADMITTED
    assert len(report["non_linear"]) == 1               # ...and the component is still skipped
    assert report["applied"] == []


# ---------------------------------------------------------------------------------------------
# RECONCILIATION — a derived field is reconciled every pass, or it is not derived
# ---------------------------------------------------------------------------------------------


def test_a_STALE_inverse_is_REPAIRED(tmp_path: Path) -> None:
    # The status is already `superseded`, so the old code `continue`d -- conflating "the status is
    # right" with "the projection is right". A record whose `superseded_by` is missing or points at
    # the WRONG entity was then invalid forever, and no re-run touched it.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="superseded", superseded_by="interpretation:i-WRONG")
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:i-v1")])

    report = mark_superseded(tmp_path, apply=True)

    # `repaired`, NOT `applied`. The status was already correct; only the projection moved. Reusing
    # `applied` would silently redefine a documented, JSON-serialized key for every consumer already
    # reading it -- and a key whose MEANING changes under a consumer is worse than one that
    # disappears, because the disappearance is at least loud.
    assert report["applied"] == []
    assert report["repaired"] == ["interpretation:i-v1"]
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    assert fm is not None and fm["superseded_by"] == "interpretation:i-v2"


def test_a_MISSING_inverse_on_an_already_superseded_record_is_REPAIRED(tmp_path: Path) -> None:
    # THE AMENDED SKIP TEST. `test_report_skips_already_superseded_members` pinned the OLD meaning of
    # "already superseded" -- status-only -- and this task splits that into two facts. Its fixture
    # has no `superseded_by`, so under the new rule the member NEEDS the inverse and is correctly
    # queued for repair rather than skipped. The chain is still detected either way.
    _seed(tmp_path)
    _interp(tmp_path, "i-v3", status="superseded")                                  # no inverse
    _interp(tmp_path, "i-v4", relations=[_supersedes("interpretation:i-v3")])

    report = mark_superseded(tmp_path, apply=False)

    assert report["to_mark"] == []                          # the STATUS needs nothing...
    assert report["to_repair"] == ["interpretation:i-v3"]   # ...but the PROJECTION does
    assert len(report["chains"]) == 1
    assert report["chains"][0]["survivor"] == "interpretation:i-v4"
    assert report["chains"][0]["members"] == ["interpretation:i-v3"]


def test_a_RECONCILED_record_is_BYTE_IDENTICAL_afterwards(tmp_path: Path) -> None:
    # THE IDEMPOTENCE CONTROL -- and it asserts the FILE, not the report. This is what preserves the
    # skip that `test_report_skips_already_superseded_members` existed to prove: a record that needs
    # nothing is touched by nothing.
    #
    # Asserting only `to_mark == [] and applied == []` would pass for an implementation that rewrites
    # the file and merely forgets to append to the report -- the more likely bug, and the one with
    # consequences: the write boundary stamps `updated:` unconditionally, so a re-stamping no-op
    # churns `updated:` across every superseded record in the corpus and makes a re-run
    # indistinguishable from a real migration in `git diff`.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", status="superseded", superseded_by="interpretation:i-v2")
    _interp(tmp_path, "i-v2", relations=[_supersedes("interpretation:i-v1")])
    target = tmp_path / "entities/interpretations/i-v1.md"
    before = target.read_bytes()

    report = mark_superseded(tmp_path, apply=True)

    assert target.read_bytes() == before          # NOT ONE BYTE -- `updated:` included
    assert report["to_mark"] == [] and report["applied"] == [] and report["repaired"] == []


# ---------------------------------------------------------------------------------------------
# the edge that is not an edge, and the edge counted twice
# ---------------------------------------------------------------------------------------------


def test_a_SELF_SUPERSESSION_is_REFUSED_and_BLOCKS_apply(tmp_path: Path) -> None:
    # `materialize` RAISES on a self-referential authored relation -- for ANY predicate, on the
    # RESOLVED entity, before it ever asks whether the kind pair is allowed. So this corpus does not
    # build a graph, and `--apply` must not walk over it.
    #
    # THE KIND-PAIR CHECK CANNOT CATCH THIS. `interpretation -> interpretation` is a LEGAL pair --
    # it is the pair every chain in this file is made of -- so a self-edge is admitted, and then a
    # one-node component is dropped by `len(comp) < 2` before classification ever sees it. No
    # mismatch, no non-linear component, no blocker: `--apply` returned CLEAN over an invalid corpus.
    # Legality is a property of the RESOLVED PAIR, and `(x, x)` is illegal whatever `x`'s kind is.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", relations=[_supersedes("interpretation:i-v1")])

    report = mark_superseded(tmp_path, apply=False)

    assert [s["id"] for s in report["self_referential"]] == ["interpretation:i-v1"]
    assert report["chains"] == [] and report["non_linear"] == [] and report["to_mark"] == []
    with pytest.raises(SupersessionError, match="supersedes itself"):
        mark_superseded(tmp_path, apply=True)


def test_a_SELF_SUPERSESSION_THROUGH_AN_ALIAS_is_still_a_SELF_SUPERSESSION(tmp_path: Path) -> None:
    # The self-edge that a string comparison on the AUTHORED text cannot see. `i-old` is a manual
    # alias for `i-v1`, so `i-v1 supersedes interpretation:i-old` reads as an edge between two
    # different ids and resolves to one. The check has to run on the CANONICAL pair -- which is
    # exactly where `materialize` runs it (`subject.canonical_id == object.canonical_id`).
    _seed(tmp_path)
    _interp(tmp_path, "i-v1", relations=[_supersedes("interpretation:i-old")])
    _manual_alias(tmp_path, "interpretation:i-old", "interpretation:i-v1")

    report = mark_superseded(tmp_path, apply=False)

    assert [s["id"] for s in report["self_referential"]] == ["interpretation:i-v1"]
    assert report["to_mark"] == []


def test_the_SAME_EDGE_AUTHORED_TWICE_is_ONE_EDGE_not_a_branch(tmp_path: Path) -> None:
    # An RDF graph is a SET of triples: authoring the identical relation twice adds nothing the
    # second time. Accumulating admitted edges in a LIST and counting degrees off it makes the
    # duplicate a second in-edge and a second out-edge, so a perfectly ordinary one-edge chain is
    # classified "branched or cyclic" and SILENTLY SKIPPED -- the corpus is valid, and the tool
    # refuses to act on it while reporting a defect that does not exist.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1")
    _interp(
        tmp_path,
        "i-v2",
        relations=[_supersedes("interpretation:i-v1"), _supersedes("interpretation:i-v1")],
    )

    report = mark_superseded(tmp_path, apply=False)

    assert report["non_linear"] == []
    assert report["chains"] == [
        {"survivor": "interpretation:i-v2", "members": ["interpretation:i-v1"], "linear": True}
    ]
    assert report["to_mark"] == ["interpretation:i-v1"]


def test_the_SAME_EDGE_IN_TWO_SPELLINGS_is_ONE_EDGE_not_a_branch(tmp_path: Path) -> None:
    # The same collapse, but the duplicate is invisible in the source text: one edge names the
    # canonical id and the other an alias of it. Deduplication therefore has to happen AFTER
    # canonical resolution, not on the authored strings.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1")
    _interp(
        tmp_path,
        "i-v2",
        relations=[_supersedes("interpretation:i-v1"), _supersedes("interpretation:i-old")],
    )
    _manual_alias(tmp_path, "interpretation:i-old", "interpretation:i-v1")

    report = mark_superseded(tmp_path, apply=False)

    assert report["non_linear"] == []
    assert report["to_mark"] == ["interpretation:i-v1"]


def test_TWO_DIFFERENT_TARGETS_from_one_superseder_REMAIN_non_linear(tmp_path: Path) -> None:
    # THE CONTROL THAT KEEPS DEDUPLICATION HONEST. Collapsing duplicate pairs must not collapse
    # DISTINCT pairs: `i-v2` superseding two different records is a genuine branch (out-degree 2),
    # it stays non-linear, and it is still never stamped. Without this, "dedupe the edges" could be
    # implemented as "keep one edge per superseder" and every test above would still pass.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1a")
    _interp(tmp_path, "i-v1b")
    _interp(
        tmp_path,
        "i-v2",
        relations=[_supersedes("interpretation:i-v1a"), _supersedes("interpretation:i-v1b")],
    )

    report = mark_superseded(tmp_path, apply=False)

    assert report["chains"] == [] and report["to_mark"] == []
    assert len(report["non_linear"]) == 1
    assert set(report["non_linear"][0]["nodes"]) == {
        "interpretation:i-v1a",
        "interpretation:i-v1b",
        "interpretation:i-v2",
    }


# ---------------------------------------------------------------------------------------------
# the CARRIER — an edge is an edge wherever it is authored
# ---------------------------------------------------------------------------------------------
#
# The builder used to scan entity markdown for nested `relations:`. `materialize` reads
# `sources.relations`, which ALSO unions `knowledge/sources/<local>/relations.yaml` and the legacy
# models/parameters blocks. So an edge authored in `relations.yaml` was invisible to this authority
# and fully visible to the graph builder: `--apply` walked past a self-edge that refuses to
# materialize. An authority that reads a SUBSET of what it validates does not validate.


def _relations_yaml(root: Path, items: list[dict[str, str]]) -> Path:
    path = root / "knowledge" / "sources" / "local" / "relations.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"relations": items}), encoding="utf-8")
    return path


def _amends(target: str) -> dict[str, str]:
    return {"predicate": "sci:amends", "target": target}


def test_an_edge_authored_in_RELATIONS_YAML_IS_A_REAL_EDGE_and_is_STAMPED(tmp_path: Path) -> None:
    # THE POSITIVE CONTROL, and the load-bearing one. It is not enough for the new carrier to be
    # scanned for DEFECTS -- if it were only wired into the refusal paths, a valid edge authored
    # there would still derive nothing, and "we read relations.yaml" would be a half-truth. The edge
    # lives ONLY in relations.yaml; neither record's frontmatter mentions the other.
    _seed(tmp_path)
    _interp(tmp_path, "i-v1")
    _interp(tmp_path, "i-v2")
    _relations_yaml(tmp_path, [
        {"subject": "interpretation:i-v2", "predicate": "sci:supersedes",
         "object": "interpretation:i-v1"},
    ])

    report = mark_superseded(tmp_path, apply=True)

    assert report["applied"] == ["interpretation:i-v1"]
    fm = read_frontmatter(tmp_path / "entities/interpretations/i-v1.md")
    assert fm is not None
    assert fm["status"] == "superseded"
    assert fm["superseded_by"] == "interpretation:i-v2"   # the inverse, derived from the YAML edge


def test_a_SELF_SUPERSESSION_in_RELATIONS_YAML_BLOCKS_and_names_THAT_FILE(tmp_path: Path) -> None:
    # Same defect, other carrier. And the finding must name `relations.yaml` -- NOT the subject's
    # markdown, which does not contain the offending line and where nothing can be fixed.
    _seed(tmp_path)
    _interp(tmp_path, "i1")
    _relations_yaml(tmp_path, [
        {"subject": "interpretation:i1", "predicate": "sci:supersedes",
         "object": "interpretation:i1"},
    ])

    with pytest.raises(SupersessionError) as excinfo:
        mark_superseded(tmp_path, apply=True)

    blocking = excinfo.value.blocking
    assert [b["id"] for b in blocking] == ["interpretation:i1"]
    assert blocking[0]["path"] == "knowledge/sources/local/relations.yaml"


# ---------------------------------------------------------------------------------------------
# CYCLES — a branch is ambiguous; a cycle is a corpus with NO GRAPH
# ---------------------------------------------------------------------------------------------
#
# `_classify` collapsed both into one `non_linear` outcome, which carries a branch's disposition:
# report, skip, do NOT block. So a cycle -- which `materialize` REFUSES to build
# (`_validate_no_amendment_cycles`) -- was filed as a valid-but-ambiguous chain and `--apply`
# returned clean over it.


def test_a_SUPERSEDES_CYCLE_is_REFUSED_and_BLOCKS_apply(tmp_path: Path) -> None:
    _seed(tmp_path)
    _interp(tmp_path, "a", relations=[_supersedes("interpretation:b")])
    _interp(tmp_path, "b", relations=[_supersedes("interpretation:a")])

    report = mark_superseded(tmp_path, apply=False)

    # ONE FINDING PER AUTHORED EDGE: every edge on the cycle is implicated, and breaking any one of
    # them breaks the cycle. Each names the file it was authored in.
    assert len(report["cycles"]) == 2
    assert {c["path"] for c in report["cycles"]} == {
        "entities/interpretations/a.md",
        "entities/interpretations/b.md",
    }
    assert report["non_linear"] == []    # NOT filed as a branch -- it is not one
    assert report["chains"] == [] and report["to_mark"] == []

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


def test_a_MIXED_amends_supersedes_CYCLE_is_STILL_A_CYCLE(tmp_path: Path) -> None:
    # ☠️ THE ONE A SUPERSEDES-ONLY SCAN CANNOT SEE. `a supersedes b` is, on its own, a perfectly
    # ordinary linear chain -- and `b amends a` closes a cycle through it. Both edges are legal
    # pairs; every per-edge check passes; `materialize` still raises, because
    # `_validate_no_amendment_cycles` walks {sci:amends, sci:supersedes} as ONE relation.
    #
    # Scan `supersedes` alone and this corpus reports a clean chain and OFFERS TO STAMP `b`.
    _seed(tmp_path)
    _interp(tmp_path, "a", relations=[_supersedes("interpretation:b")])
    _interp(tmp_path, "b", relations=[_amends("interpretation:a")])

    report = mark_superseded(tmp_path, apply=False)

    assert len(report["cycles"]) == 2
    assert any("sci:amends" in c["reason"] for c in report["cycles"])
    assert report["chains"] == []        # the supersedes edge is linear -- and it is NOT a chain
    assert report["to_mark"] == []       # nothing inside a cycle is stampable

    with pytest.raises(SupersessionError):
        mark_superseded(tmp_path, apply=True)


def test_a_BRANCH_is_NOT_a_CYCLE(tmp_path: Path) -> None:
    # THE CONTROL that keeps the split honest. A branch is a VALID corpus: it materializes, and it is
    # merely ambiguous about which node survives. It stays `non_linear`, it raises no cycle, and it
    # must NOT block -- or "separate cycles from branches" would just be "block on both".
    _seed(tmp_path)
    _interp(tmp_path, "i-v1")
    _interp(tmp_path, "i-a", relations=[_supersedes("interpretation:i-v1")])
    _interp(tmp_path, "i-b", relations=[_supersedes("interpretation:i-v1")])

    report = mark_superseded(tmp_path, apply=True)   # does NOT raise

    assert report["cycles"] == []
    assert len(report["non_linear"]) == 1
    assert report["non_linear"][0]["reason"] == "branched supersedes chain"
    assert report["applied"] == []


def test_a_CYCLE_THROUGH_AN_UNMANAGED_NODE_is_still_a_CYCLE() -> None:
    # WHY THE CYCLE SCAN RUNS ON EVERY RESOLVED EDGE AND NOT ON THE ADMITTED ONES. `graph.edges` is
    # the WRITER's set: it drops edges into targets we cannot stamp (commons, non-markdown sources).
    # `i-live -> i-commons` is exactly such an edge -- so a scan over `graph.edges` sees ONLY
    # `i-commons -> i-live`, a single edge, no cycle. `materialize` emits both triples and raises.
    #
    # The commons record authors its edge in its own file, which is why the edge is expressible here
    # at all and why `lineage` is passed explicitly: it does not live in this project's markdown.
    entries: list[tuple[Path, dict[str, Any]]] = [
        (Path("i-live.md"), {"id": "interpretation:i-live", "kind": "interpretation"}),
    ]
    graph = build_supersedes_graph(_inputs(
        entries,
        mutable={"interpretation:i-live"},          # the commons record is NOT ours to stamp
        archived=set(),
        kinds={"interpretation:i-live": "interpretation",
               "interpretation:i-commons": "interpretation"},
        lineage=[
            SourceRelation(subject="interpretation:i-live", predicate="sci:supersedes",
                           object="interpretation:i-commons", source_path="i-live.md"),
            SourceRelation(subject="interpretation:i-commons", predicate="sci:supersedes",
                           object="interpretation:i-live", source_path="commons/i-commons.md"),
        ],
    ))

    assert graph.edges == frozenset({("interpretation:i-commons", "interpretation:i-live")})
    assert len(graph.cycles) == 2                   # BOTH edges, though only one was ever admitted
    assert graph.linear == () and graph.non_linear == ()
