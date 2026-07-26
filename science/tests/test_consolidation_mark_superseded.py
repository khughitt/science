"""Auto-derive `superseded` — status **and its derived lineage** — from supersedes chains.

Leg 3 of the D4 supersedable gate — proved on `interpretation`, then CLOSED on `hypothesis`.

The generic machinery (the inverse, the kind-pair refusal, the seven-way edge admission, the
acyclicity scan, the reconciliation) is exercised on `interpretation`, which has declared
`superseded` and been an admitted `sci:supersedes` endpoint all along — so leg 3 could be certified
without changing what any existing file means.

`hypothesis` could not be tested here AT ALL until its descriptor declared a `superseded` terminal:
`DECLARED_SUPERSEDABLE` follows that declaration, so every hypothesis member was routed to
`skipped_kinds` and nothing was written. A hypothesis apply-test would not have failed loudly — it
would have reported `to_mark == []`, written nothing, and gone **green over an operation that did
nothing**. That is why the hypothesis tests at the bottom of this file arrive with the descriptor
that makes them executable, and not one task earlier. *A test belongs in the task where its subject
exists.*
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from rdflib import URIRef
from science_model.entities import Entity
from science_model.entity_schema import EntityValidator, default_profile_for_kind
from science_model.entity_schema.resolution import check_resolution
from science_model.profiles.core import CORE_PROFILE

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.consolidation import (
    IdResolution,
    SupersededChain,
    SupersessionError,
    SupersessionInputs,
    build_decision_material,
    build_supersedes_graph,
    load_supersession_inputs,
    mark_superseded,
)
from science_tool.entities import EntityCommandError
from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import AdmittedRelation
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.relation_audit import RelationAudit, RelationDefect
from science_tool.graph.sources import SourceRelation
from science_tool.plan_common import AllSupersessionMembers
from science_tool.supersede_plan import derive_supersede_plan


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


def _seed(root: Path, *, pinned: bool = False) -> None:
    # `pinned=True` declares entity_schema_version: 2. Superseding a HYPOTHESIS writes `status:
    # superseded`, and the write boundary refuses the schema-2 vocabulary on an unmigrated project --
    # so a hypothesis-supersession test runs in the post-fold world, the world where that operation
    # exists. Interpretation supersession is unaffected either way (its kind is not gated).
    body = "name: chain-test\n"
    if pinned:
        body += "entity_schema_version: 2\n"
    (root / "science.yaml").write_text(body, encoding="utf-8")


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
    """Construct the WRITER's populations directly.

    The builder is a pure function of its inputs, so the commons / non-markdown populations — which
    would otherwise need a commons repo on disk — are expressible as the data they actually are.
    `kinds` seeds the resolver only; the builder no longer asks anything about a kind, because
    LEGALITY is the audit's question now and not this module's.
    """
    entities = [_entity(cid, kind) for cid, kind in kinds.items()]
    return IdResolution(
        resolver=ReferenceResolver.from_entities(entities),
        mutable=frozenset(mutable),
        archived=frozenset(archived),
    )


def _admit(subject: str, obj: str, *, kinds: dict[str, str], path: str, name: str = "supersedes") -> AdmittedRelation:
    """One edge `materialize` ADMITTED — the audit's verdict, constructed directly.

    This is what the builder consumes now: not a raw authored relation to be judged, but a relation
    already judged VALID by the graph builder. A test that wants the builder to see an edge says so
    here; a test that wants the builder to see a REFUSAL says so with `_defect`. The two are
    different inputs because they are different facts, and the builder treats them differently —
    which is the whole point of the split.
    """
    relation_kind = next(r for r in CORE_PROFILE.relation_kinds if r.name == name)
    return AdmittedRelation(
        relation=SourceRelation(subject=subject, predicate=f"sci:{name}", object=obj, source_path=path),
        graph_uri=URIRef("https://example.org/graph/knowledge"),
        subject=_entity(subject, kinds[subject]),
        subject_uri=URIRef(f"https://example.org/{subject}"),
        predicate_uri=SCI_NS[name],
        object=_entity(obj, kinds[obj]),
        object_uri=URIRef(f"https://example.org/{obj}"),
        relation_kind=relation_kind,
    )


def _defect(subject: str, obj: str, *, code: str, path: str) -> RelationDefect:
    """One relation `materialize` REFUSED, whatever the rule. The builder must never launder it."""
    return RelationDefect(
        code=code,
        path=path,
        subject=subject,
        predicate="sci:supersedes",
        object=obj,
        message=f"{code}: {subject} -> {obj}",
    )


def _inputs(
    entries: list[tuple[Path, dict[str, Any]]],
    *,
    mutable: set[str],
    archived: set[str],
    kinds: dict[str, str],
    audit: RelationAudit | None = None,
) -> SupersessionInputs:
    """The builder's inputs, constructed DIRECTLY — the writer's populations AND the audit's verdict.

    `audit` defaults to ADMITTING every nested `relations:` entry in `entries`, which is what the
    real audit does for a corpus with no defects. Pass one explicitly to inject a defect, or to
    author an edge in a carrier with no markdown behind it at all.
    """
    if audit is None:
        audit = RelationAudit(
            admitted=tuple(
                _admit(
                    str(fm["id"]),
                    str(rel["target"]),
                    kinds=kinds,
                    path=str(path),
                    name=str(rel["predicate"]).split(":", 1)[1],
                )
                for path, fm in entries
                for rel in fm.get("relations", [])
            ),
            defects=(),
        )
    return SupersessionInputs(
        entries=tuple(entries),
        resolution=_resolution(mutable=mutable, archived=archived, kinds=kinds),
        audit=audit,
    )


def _interp(root: Path, name: str, **fm: Any) -> Path:
    return _write(root, "interpretations", name, {"id": f"interpretation:{name}", "kind": "interpretation", **fm})


def _hypothesis(root: Path, name: str, **fm: Any) -> Path:
    # `created`/`updated` are REQUIRED by entity-base 2.0, and this fixture is validated against the
    # real profile by `test_a_stamped_HYPOTHESIS_satisfies_its_own_schema` -- so a fixture that omits
    # them would fail for a reason having nothing to do with supersession.
    return _write(root, "hypotheses", name, {
        "id": f"hypothesis:{name}", "kind": "hypothesis",
        "created": "2026-07-13", "updated": "2026-07-13", **fm,
    })


def _invalid(report: dict[str, Any], code: str) -> list[dict[str, str]]:
    """The audit's refusals of one kind, off the report.

    ONE key, `invalid_relations`, where there used to be four (`self_referential`,
    `mismatched_kinds`, `cycles`, `unresolved_targets`). Those were hand-maintained buckets, and
    between them they never covered what `materialize` actually refuses — the reason this module no
    longer classifies a refusal at all. It reports the builder's verdict and its `code`.
    """
    return [r for r in report["invalid_relations"] if r["code"] == code]


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


def test_member_omitted_from_the_frozen_policy_is_skipped_not_crashed(tmp_path: Path) -> None:
    # The fixture is a NORMALLY SUPERSEDABLE kind held out of its material's `supported_kinds` --
    # not a "kind lacking the vocabulary", which after S2 cannot be an admitted member at all.
    # Reachable only from stale or hand-built material, so it is built through the material path
    # rather than by hand-constructing a graph: the point is that inconsistent material SURVIVES
    # `build_supersedes_graph_from_material` and is then skipped, and a hand-built graph would
    # bypass that step entirely.
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-old", {"id": "interpretation:i-old", "kind": "interpretation"})
    _write(tmp_path, "interpretations", "i-new", {"id": "interpretation:i-new", "kind": "interpretation",
                                                  "relations": [_supersedes("interpretation:i-old")]})

    material = build_decision_material(tmp_path)
    assert "interpretation" in material.supported_kinds  # the fixture is meaningful only if so
    narrowed = material.model_copy(
        update={"supported_kinds": [k for k in material.supported_kinds if k != "interpretation"]}
    )

    plan = derive_supersede_plan(
        tmp_path,
        narrowed,
        selection=AllSupersessionMembers(kind="all"),
        preview_date="2026-07-26",
    )

    assert plan.preview_report.to_mark == []
    assert {entry.id for entry in plan.preview_report.skipped_kinds} == {"interpretation:i-old"}


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
    bad = _invalid(report, "illegal-kind-pair")
    assert [(b["subject"], b["object"], b["path"]) for b in bad] == [
        ("workflow-run:wr-1", "interpretation:i-v1", "entities/workflow-runs/wr-1.md"),
    ]
    # MATERIALIZE'S OWN WORDS, not a paraphrase of them. The message is the `ValueError` the graph
    # builder raises, verbatim, because it is the graph builder that refused the edge.
    assert "(got workflow-run -> interpretation)" in bad[0]["message"]

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
    assert [m["subject"] for m in _invalid(report, "illegal-kind-pair")] == ["workflow-run:wr-1"]
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
    assert report["invalid_relations"] == []
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

    bad = _invalid(report, "unknown-object")
    assert [(b["subject"], b["object"], b["path"]) for b in bad] == [
        ("interpretation:i-v2", "interpretation:i-GONE", "entities/interpretations/i-v2.md"),
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

    assert report["invalid_relations"] == []                # NOT a dangling edge
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

    assert report["invalid_relations"] == []
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

    assert graph.invalid == ()                             # the audit ADMITTED it: it is a real edge
    assert graph.archived_targets == ()                    # ...and it is NOT archived
    assert [u["id"] for u in graph.unmanaged_targets] == ["report:commons-thing"]
    assert graph.linear == (
        SupersededChain(survivor="interpretation:j-v2", superseded=("interpretation:j-v1",)),
    )


def test_a_REFUSED_edge_is_NEVER_LAUNDERED_into_a_benign_writer_outcome() -> None:
    # THE ORDERING BUG, and why it is now UNREACHABLE rather than merely guarded against.
    #
    # A draft that answered OWNERSHIP first saw "resolves, not mutable" for an illegal edge into a
    # commons target and `continue`d into `unmanaged_targets` -- benign, unstampable, apply proceeds
    # -- WITHOUT EVER ASKING `relation_allows_kinds`. The pair check sat downstream of the corruption
    # it was written to detect.
    #
    # That ordering cannot recur, because the two questions are no longer in the same module. The
    # audit ADMITS (legal? resolvable? acyclic?) and this builder DISPOSES (can we stamp it?), and
    # the builder only ever sees relations that were already admitted. So the test is no longer
    # "does the ladder ask the questions in the right order" -- there is no ladder. It is: a refusal
    # stays a refusal, and is never re-filed as benign debt.
    graph = build_supersedes_graph(_inputs(
        [(Path("i.md"), {"id": "interpretation:new", "kind": "interpretation"})],
        mutable={"interpretation:new"}, archived=set(),
        kinds={"interpretation:new": "interpretation", "dataset:commons-thing": "dataset"},
        audit=RelationAudit(
            admitted=(),
            defects=(_defect("interpretation:new", "dataset:commons-thing",
                             code="illegal-kind-pair", path="i.md"),),
        ),
    ))

    assert graph.unmanaged_targets == ()                   # NOT waved through as benign debt
    assert graph.archived_targets == ()
    assert graph.edges == frozenset()                      # and NOT an edge in the topology
    assert [d.object for d in graph.invalid] == ["dataset:commons-thing"]


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
    assert [m["object"] for m in _invalid(report, "illegal-kind-pair")] == ["dataset:d-old"]

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
    bad = _invalid(report, "illegal-kind-pair")
    assert [m["object"] for m in bad] == ["interpretation:i-old"]
    # The EMPTY kind, in materialize's own words: `(got interpretation -> )`. A prefix fallback would
    # have read `interpretation` off the id and produced a LEGAL pair -- and admitted the edge.
    assert "(got interpretation -> )" in bad[0]["message"]

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
    # `materialize` raises `Unknown canonical entity` on it: the alias resolves, and the id it
    # resolves TO is in no entity index. Same refusal, same words.
    bad = _invalid(report, "unknown-object")
    assert [u["object"] for u in bad] == ["interpretation:ghost"]
    assert "Unknown canonical entity" in bad[0]["message"]

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

    assert report["invalid_relations"] == []      # it RESOLVES. That is the whole point.
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

    assert [s["object"] for s in _invalid(report, "self-referential")] == ["interpretation:i-v1"]
    assert report["chains"] == [] and report["non_linear"] == [] and report["to_mark"] == []
    with pytest.raises(SupersessionError, match="self-referential authored relation"):
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

    # The AUTHORED text says `interpretation:i-old`; the canonical pair is `(i-v1, i-v1)`. The rule
    # runs where `materialize` runs it -- on the resolved ids -- so the alias does not hide it.
    assert [s["object"] for s in _invalid(report, "self-referential")] == ["interpretation:i-old"]
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
    assert len(blocking) == 1
    assert "knowledge/sources/local/relations.yaml" in blocking[0]
    assert "self-referential authored relation" in blocking[0]   # materialize's own words


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
    cycles = _invalid(report, "cycle")
    assert len(cycles) == 2
    assert {c["path"] for c in cycles} == {
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

    cycles = _invalid(report, "cycle")
    assert len(cycles) == 2
    assert any("sci:amends" in c["message"] for c in cycles)
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

    assert _invalid(report, "cycle") == []
    assert len(report["non_linear"]) == 1
    assert report["non_linear"][0]["reason"] == "branched supersedes chain"
    assert report["applied"] == []


def test_a_CYCLE_THROUGH_AN_UNMANAGED_NODE_KEEPS_ITS_COMPONENT_OUT_OF_THE_TOPOLOGY() -> None:
    # THE TWO EDGE SETS ARE DIFFERENT SETS, and this is the test that keeps them apart.
    #
    # The AUDIT walks every edge that RESOLVES -- including `i-live -> i-commons`, into a record this
    # project cannot write. The BUILDER's `edges` is the WRITER's set and drops exactly that one. So
    # the audit sees a 2-cycle where the writer sees a single edge and no cycle at all, and a
    # cycle-scan built from `graph.edges` would have found nothing while `materialize` raised.
    #
    # The builder's job here is only to BELIEVE the audit: a component touching a cyclic node is not
    # a chain, not a branch, and nothing in it is stampable -- even though the one edge it CAN see
    # looks, on its own, like a perfectly ordinary supersession.
    kinds = {"interpretation:i-live": "interpretation", "interpretation:i-commons": "interpretation"}
    graph = build_supersedes_graph(_inputs(
        [(Path("i-live.md"), {"id": "interpretation:i-live", "kind": "interpretation"})],
        mutable={"interpretation:i-live"},          # the commons record is NOT ours to stamp
        archived=set(),
        kinds=kinds,
        audit=RelationAudit(
            admitted=(
                _admit("interpretation:i-live", "interpretation:i-commons",
                       kinds=kinds, path="i-live.md"),
                _admit("interpretation:i-commons", "interpretation:i-live",
                       kinds=kinds, path="commons/i-commons.md"),
            ),
            defects=(
                _defect("interpretation:i-live", "interpretation:i-commons",
                        code="cycle", path="i-live.md"),
                _defect("interpretation:i-commons", "interpretation:i-live",
                        code="cycle", path="commons/i-commons.md"),
            ),
        ),
    ))

    # The writer can only see -- and could only ever stamp -- ONE of the two edges...
    assert graph.edges == frozenset({("interpretation:i-commons", "interpretation:i-live")})
    # ...and it stamps NEITHER, because the audit says both lie on a cycle.
    assert graph.linear == () and graph.non_linear == ()
    assert len(graph.invalid) == 2


def test_a_newly_supersedable_kind_is_actually_stamped(tmp_path: Path) -> None:
    # `topic` gained its endpoint in Task 3 and has always declared the status. If the policy stops
    # following the declaration, this member silently stops being stamped -- which an equality
    # assertion over two currently-identical sets would not catch.
    _seed(tmp_path)
    _write(tmp_path, "topics", "t-old", {"id": "topic:t-old", "kind": "topic", "status": "active"})
    _write(tmp_path, "topics", "t-new", {"id": "topic:t-new", "kind": "topic", "status": "active",
                                         "relations": [_supersedes("topic:t-old")]})

    report = mark_superseded(tmp_path, apply=False)

    assert report["to_mark"] == ["topic:t-old"]
    assert report["skipped_kinds"] == []


def test_the_frozen_policy_equals_the_profile_declaration(tmp_path: Path) -> None:
    # Regression, not the driver: compared against the PROFILE, reached independently of
    # `kind_descriptors`, because `supported_kinds` is BUILT from `DECLARED_SUPERSEDABLE` and
    # comparing it back to that map would be the identity function.
    from science_tool.consolidation import build_decision_material

    _seed(tmp_path)
    (tmp_path / "entities").mkdir()
    material = build_decision_material(tmp_path)
    declared = sorted(ek.name for ek in CORE_PROFILE.entity_kinds if ek.supersedable)
    assert material.supported_kinds == declared


# ---------------------------------------------------------------------------------------------
# hypothesis — EXECUTABLE for the first time
#
# Every test above runs on `interpretation`, and not by preference: `DECLARED_SUPERSEDABLE` was False
# for `hypothesis` until its descriptor declared a `superseded` terminal, so `mark_superseded` routed
# every hypothesis to `skipped_kinds` and wrote nothing. There was no hypothesis apply-test to write.
# These three are the D4 triangle closed, on the kind the whole arc is about.
# ---------------------------------------------------------------------------------------------


def test_a_stamped_HYPOTHESIS_satisfies_its_own_schema(tmp_path: Path) -> None:
    # THE TRIANGLE, CLOSED -- and the first hypothesis this toolkit has ever superseded. All four
    # legs must agree at once: the schema admits the edge, the relation admits the endpoint PAIR, the
    # operation writes a resolvable inverse, and the descriptor makes `superseded` a status the kind
    # can hold. Any one missing and this fails -- which is why a bidirectional gate is one assertion.
    _seed(tmp_path, pinned=True)  # superseding a hypothesis is a schema-2 operation
    _hypothesis(tmp_path, "0001-old", status="active")
    _hypothesis(tmp_path, "0002-new", status="active",
                relations=[_supersedes("hypothesis:0001-old")])

    report = mark_superseded(tmp_path, apply=True)
    fm = read_frontmatter(tmp_path / "entities/hypotheses/0001-old.md")

    assert report["applied"] == ["hypothesis:0001-old"]   # NOT skipped_kinds -- the old failure mode
    assert report["skipped_kinds"] == []
    assert fm is not None
    assert fm["status"] == "superseded"
    assert fm["superseded_by"] == "hypothesis:0002-new"

    # THE STAMPED RECORD VALIDATES. The operation writes frontmatter; the schema is what says that
    # frontmatter is legal. A tool that writes a record its own schema rejects has not migrated the
    # vocabulary, it has broken the corpus -- and nothing else in this file would notice.
    EntityValidator().validate_as(fm, default_profile_for_kind("hypothesis"))

    # ...and the lineage RESOLVES, through the SAME resolver the loader and `materialize` use -- not
    # a raw id set, which would both reject a valid alias and miss a self-alias.
    resolver = load_supersession_inputs(tmp_path).resolution.resolver
    assert check_resolution(
        fm, targets=resolver, live_hypotheses={"hypothesis:0002-new"}
    ) == []


def test_a_hypothesis_CHAIN_records_the_immediate_superseder(tmp_path: Path) -> None:
    # A <- B <- C on the kind that matters. The interpretation test above proves the inversion picks
    # the IMMEDIATE superseder; this proves the descriptor change did not quietly re-route
    # hypotheses back down the skip path, where every assertion about lineage is vacuously true.
    _seed(tmp_path, pinned=True)  # superseding a hypothesis is a schema-2 operation
    _hypothesis(tmp_path, "0003-c", status="active")
    _hypothesis(tmp_path, "0002-b", status="active",
                relations=[_supersedes("hypothesis:0003-c")])
    _hypothesis(tmp_path, "0001-a", status="active",
                relations=[_supersedes("hypothesis:0002-b")])

    report = mark_superseded(tmp_path, apply=True)

    assert set(report["applied"]) == {"hypothesis:0002-b", "hypothesis:0003-c"}
    c = read_frontmatter(tmp_path / "entities/hypotheses/0003-c.md")
    assert c is not None
    assert c["superseded_by"] == "hypothesis:0002-b"      # NOT 0001-a, the survivor


def test_superseding_a_HYPOTHESIS_on_an_UNMIGRATED_project_is_REFUSED(tmp_path: Path) -> None:
    # ☠️ Superseding a hypothesis writes `status: superseded` -- a lifecycle value hypotheses did not
    # admit before the fold -- AND a derived `superseded_by` inverse. Both are schema-2 semantics, so
    # the operation belongs to a MIGRATED project; the write boundary refuses them on an unpinned one.
    # This is NOT the gate being weakened for consolidation: the derived writer goes through the SAME
    # boundary as an authored edit, and pays the SAME pin requirement.
    #
    # And it fails ALL-OR-NONE: the refusal lands in the PREPARE phase, before any `_commit_write`, so
    # the record is byte-unchanged -- a blocked supersession leaves the corpus exactly as it was.
    _seed(tmp_path)  # UNPINNED on purpose
    _hypothesis(tmp_path, "0001-old", status="active")
    _hypothesis(tmp_path, "0002-new", status="active",
                relations=[_supersedes("hypothesis:0001-old")])
    before = (tmp_path / "entities/hypotheses/0001-old.md").read_bytes()

    with pytest.raises(EntityCommandError, match="migrate-hypothesis"):
        mark_superseded(tmp_path, apply=True)

    assert (tmp_path / "entities/hypotheses/0001-old.md").read_bytes() == before


def test_an_INTERPRETATION_may_not_supersede_a_HYPOTHESIS(tmp_path: Path) -> None:
    # The cross-kind case. `interpretation -> hypothesis` is not an allowed pair -- `supersedes`
    # admits `hypothesis -> hypothesis`, and nothing else into a hypothesis. If the operation wrote
    # the edge anyway the record would carry `superseded_by: interpretation:...`, which the mixin's
    # `^hypothesis:` pattern rejects: a record the tool wrote and the schema refuses.
    #
    # The refusal is the relation audit's -- `materialize`'s own admission, asked once -- so the edge
    # is REFUSED rather than filed in a writer-side bucket, and a corpus carrying ANY unbuildable
    # relation gets no derived lineage at all. `apply=True` RAISES.
    _seed(tmp_path)
    _hypothesis(tmp_path, "0001-x", status="active")
    _interp(tmp_path, "i-v1", relations=[_supersedes("hypothesis:0001-x")])
    before = (tmp_path / "entities/hypotheses/0001-x.md").read_bytes()

    report = mark_superseded(tmp_path, apply=False)       # REPORT names the rule that fired...

    assert report["applied"] == []
    bad = _invalid(report, "illegal-kind-pair")
    assert [(b["subject"], b["object"]) for b in bad] == [
        ("interpretation:i-v1", "hypothesis:0001-x"),
    ]
    assert "(got interpretation -> hypothesis)" in bad[0]["message"]

    with pytest.raises(SupersessionError):               # ...and APPLY refuses the whole corpus.
        mark_superseded(tmp_path, apply=True)

    # BYTE-UNCHANGED, not merely "superseded_by absent". A blocked apply must leave the corpus
    # exactly as it found it -- the all-or-none contract is about the FILE, not about one key.
    assert (tmp_path / "entities/hypotheses/0001-x.md").read_bytes() == before
