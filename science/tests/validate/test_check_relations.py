"""`relation.*` — every authored relation must MATERIALIZE, asserted through the runner.

Each test below pairs a corpus `materialize` REFUSES with the finding `validate` must produce. The
pairing is the point: before this check, every one of these corpora validated CLEAN and built no
graph. Several of them `mark_superseded --apply` would then have written into.

☠️ THE HISTORY THIS FILE EXISTS TO PREVENT. These rules were once hand-written in `consolidation.py`,
and six review rounds found six defects in them — every one the same defect, that the hand-written
authority asked a NARROWER question than `materialize` asks. It read entity markdown while the
builder read `relations.yaml` too; it scanned `sci:supersedes` while the builder scanned
`{amends, supersedes}` as one family; it walked the edges it could WRITE while the builder walked the
edges it could RESOLVE; it let an ARCHIVED record author an edge the builder refuses from any
non-live subject. The rules are not written here any more. `audit_relations` asks
`admit_authored_relation` — the builder's own admission — and this check reports what it refuses.

So the tests that matter most are the ones for rules NOBODY WROTE: `test_a_BARE_AMENDS_SELF_EDGE...`
and `test_an_ARCHIVED_SUBJECT...` were both closed by deleting code, not by adding a rule.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate import runner
from science_tool.validate.result import Severity


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: rel\n", encoding="utf-8")


def _write(root: Path, name: str, fm: dict) -> None:
    path = root / "entities" / "interpretations" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump({"title": name, **fm}, sort_keys=False) + "---\n\nbody\n",
        encoding="utf-8",
    )


def _dataset(root: Path, name: str) -> None:
    path = root / "entities" / "datasets" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump({"id": f"dataset:{name}", "kind": "dataset", "title": name}) + "---\n\nbody\n",
        encoding="utf-8",
    )


def _relations_yaml(root: Path, items: list[dict[str, str]]) -> None:
    path = root / "knowledge" / "sources" / "local" / "relations.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"relations": items}), encoding="utf-8")


def _supersedes(target: str) -> dict[str, str]:
    return {"predicate": "sci:supersedes", "target": target}


def _results(root: Path) -> list:
    return list(runner.run(root, strict=False, verbose=False).results)


def _rules(root: Path) -> list[str]:
    return [r.rule_id for r in _results(root)]


def test_a_SELF_SUPERSESSION_is_an_ERROR_through_the_runner(tmp_path: Path) -> None:
    # `materialize` raises `self-referential authored relation` on this corpus, so it does not build
    # a graph -- and before this rule existed, `validate` said NOTHING about it.
    _seed(tmp_path)
    _write(
        tmp_path,
        "i1",
        {"id": "interpretation:i1", "kind": "interpretation", "relations": [_supersedes("interpretation:i1")]},
    )

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.self-referential"]

    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR.value
    assert findings[0].subject.path == "entities/interpretations/i1.md"


def test_an_ILLEGAL_KIND_PAIR_is_an_ERROR_through_the_runner(tmp_path: Path) -> None:
    # `interpretation -> dataset` is not an allowed `sci:supersedes` pair. Reported against the file
    # that AUTHORED the edge -- the superseder -- because that is the line that has to change.
    _seed(tmp_path)
    _write(
        tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation", "relations": [_supersedes("dataset:d")]}
    )
    _dataset(tmp_path, "d")

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.illegal-kind-pair"]

    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR.value
    assert findings[0].subject.path == "entities/interpretations/i1.md"


def test_a_BARE_AMENDS_SELF_EDGE_is_an_ERROR_though_NOBODY_WROTE_THAT_RULE(tmp_path: Path) -> None:
    # ☠️ THE SEAM THAT WAS FLAGGED AS UNCLOSABLE BY HAND, and that closed itself the moment the check
    # started delegating. The old ladder only ever looked at `sci:supersedes` edges per-edge; a bare
    # `sci:amends` self-edge refused to materialize and NOTHING reported it. There is no
    # `amends`-specific rule anywhere in the source tree. The builder rejects it; the audit reports
    # the rejection. That is the whole mechanism, and it generalizes to every predicate in the
    # profile.
    _seed(tmp_path)
    _write(
        tmp_path,
        "i1",
        {
            "id": "interpretation:i1",
            "kind": "interpretation",
            "relations": [{"predicate": "sci:amends", "target": "interpretation:i1"}],
        },
    )

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.self-referential"]

    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR.value
    assert findings[0].subject.path == "entities/interpretations/i1.md"


def test_an_UNSUPPORTED_GRAPH_LAYER_is_REPORTED_and_does_not_CRASH_the_CHECK(tmp_path: Path) -> None:
    # ☠️ DELEGATION IS ONLY AS GOOD AS THE TYPE ON THE REFUSAL. `_graph_uri` refuses an unknown layer
    # with a bare `ValueError`; `audit_relations` catches `RelationRejection`. So this rule -- which
    # nobody wrote, and which arrived with the delegation -- did not reach the report: it propagated
    # out of the check and CRASHED the whole `validate` run. A rule that escapes untyped is not a
    # stricter check, it is a broken one, and only an executed test tells the two apart.
    _seed(tmp_path)
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation"})
    _write(tmp_path, "i2", {"id": "interpretation:i2", "kind": "interpretation"})
    _relations_yaml(
        tmp_path,
        [
            {
                "subject": "interpretation:i1",
                "predicate": "sci:supersedes",
                "object": "interpretation:i2",
                "graph_layer": "graph/not-a-layer",
            },
        ],
    )

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.unsupported-graph-layer"]

    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR.value
    assert findings[0].subject.path == "knowledge/sources/local/relations.yaml"
    assert "graph/not-a-layer" in findings[0].message


def test_an_ARCHIVED_SUBJECT_is_an_ERROR_because_a_FROZEN_record_cannot_AUTHOR(tmp_path: Path) -> None:
    # ☠️ THE ENDPOINTS ARE NOT SYMMETRIC, and generalizing the object's rule to the subject is what
    # let an ARCHIVED record supersede a LIVE one. `materialize` resolves an OBJECT through the
    # archive (`_ArchivedEndpoint`) but requires a SUBJECT to be in `entity_index` -- it raises
    # `Unknown canonical entity`. `mark_superseded --apply` used to stamp
    # `superseded_by: interpretation:gone` onto the live record: a write that succeeds and leaves a
    # corpus whose graph never builds again.
    #
    # Only expressible through `relations.yaml`, which names its subject by id -- an archived entity's
    # own markdown is not a relation carrier. That is why this defect surfaced only once the carrier
    # was read.
    from science_tool.archive import archive_entities

    _seed(tmp_path)
    _write(tmp_path, "live", {"id": "interpretation:live", "kind": "interpretation", "status": "active"})
    _write(tmp_path, "gone", {"id": "interpretation:gone", "kind": "interpretation", "status": "archived"})
    archive_entities(tmp_path, apply=True)
    _relations_yaml(
        tmp_path,
        [
            {"subject": "interpretation:gone", "predicate": "sci:supersedes", "object": "interpretation:live"},
        ],
    )

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.unknown-subject"]

    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR.value
    assert findings[0].subject.path == "knowledge/sources/local/relations.yaml"


def test_an_ARCHIVED_OBJECT_is_FINE_because_a_LIVE_record_MAY_POINT_AT_HISTORY(tmp_path: Path) -> None:
    # THE CONTROL that keeps the asymmetry honest. Reverse the arrow of the test above and the corpus
    # is VALID: superseding a record and then archiving it is the ordinary end of a lineage. If this
    # fired, `relation.unknown-subject` would just be "the archive is radioactive" wearing a rule
    # name.
    from science_tool.archive import archive_entities

    _seed(tmp_path)
    _write(tmp_path, "gone", {"id": "interpretation:gone", "kind": "interpretation", "status": "archived"})
    _write(
        tmp_path,
        "live",
        {
            "id": "interpretation:live",
            "kind": "interpretation",
            "status": "active",
            "relations": [_supersedes("interpretation:gone")],
        },
    )
    archive_entities(tmp_path, apply=True)

    assert not [r for r in _rules(tmp_path) if r.startswith("relation.")]


def test_a_SELF_SUPERSESSION_in_RELATIONS_YAML_is_an_ERROR_at_THAT_FILE(tmp_path: Path) -> None:
    # The check used to read entity markdown only, while `materialize` reads `sources.relations` --
    # which unions `relations.yaml` too. So this corpus refused to build a graph and validated CLEAN.
    #
    # And the finding names `relations.yaml`, NOT `i1.md`: the offending line is in the YAML, and a
    # finding pointing at a file that does not contain the defect cannot be acted on.
    _seed(tmp_path)
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation"})
    _relations_yaml(
        tmp_path,
        [
            {"subject": "interpretation:i1", "predicate": "sci:supersedes", "object": "interpretation:i1"},
        ],
    )

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.self-referential"]

    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR.value
    assert findings[0].subject.path == "knowledge/sources/local/relations.yaml"


def test_an_ILLEGAL_KIND_PAIR_in_RELATIONS_YAML_is_an_ERROR_at_THAT_FILE(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation"})
    _dataset(tmp_path, "d")
    _relations_yaml(
        tmp_path,
        [
            {"subject": "interpretation:i1", "predicate": "sci:supersedes", "object": "dataset:d"},
        ],
    )

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.illegal-kind-pair"]

    assert len(findings) == 1
    assert findings[0].severity == Severity.ERROR.value
    assert findings[0].subject.path == "knowledge/sources/local/relations.yaml"
    assert "interpretation:i1" in findings[0].message  # the SUBJECT, not just the file


def test_a_CYCLE_is_an_ERROR_on_EVERY_EDGE_that_forms_it(tmp_path: Path) -> None:
    # `materialize` raises `cycle in amendment/supersession relations` on this corpus. The builder
    # used to file it as "branched or cyclic" -- a branch's disposition: reported, skipped, and NOT
    # blocking -- and the check said nothing at all.
    #
    # One finding per authored edge: either edge is a place to break the cycle, so both name a file.
    _seed(tmp_path)
    _write(
        tmp_path,
        "a",
        {"id": "interpretation:a", "kind": "interpretation", "relations": [_supersedes("interpretation:b")]},
    )
    _write(
        tmp_path,
        "b",
        {"id": "interpretation:b", "kind": "interpretation", "relations": [_supersedes("interpretation:a")]},
    )

    findings = [r for r in _results(tmp_path) if r.rule_id == "relation.cycle"]

    assert len(findings) == 2
    assert {f.severity for f in findings} == {Severity.ERROR.value}
    assert {f.subject.path for f in findings} == {
        "entities/interpretations/a.md",
        "entities/interpretations/b.md",
    }


def test_a_MIXED_amends_supersedes_CYCLE_is_an_ERROR_through_the_runner(tmp_path: Path) -> None:
    # ☠️ Both edges are LEGAL pairs and neither is a self-edge, so every per-edge rule passes. The
    # corpus still has no graph: `_validate_no_amendment_cycles` walks {sci:amends, sci:supersedes}
    # as ONE relation. A supersedes-only cycle scan reports a clean linear chain here.
    _seed(tmp_path)
    _write(
        tmp_path,
        "a",
        {"id": "interpretation:a", "kind": "interpretation", "relations": [_supersedes("interpretation:b")]},
    )
    _write(
        tmp_path,
        "b",
        {
            "id": "interpretation:b",
            "kind": "interpretation",
            "relations": [{"predicate": "sci:amends", "target": "interpretation:a"}],
        },
    )

    rules = _rules(tmp_path)

    assert rules.count("relation.cycle") == 2
    assert "relation.self-referential" not in rules
    assert "relation.illegal-kind-pair" not in rules  # both pairs are legal -- that is the trap


def test_a_BRANCH_raises_NO_CYCLE_ERROR(tmp_path: Path) -> None:
    # THE CONTROL that keeps the cycle rule from being "any non-linear component is an ERROR". A
    # branch MATERIALIZES: it is a valid corpus, merely ambiguous about which node survives. It is
    # `mark_superseded`'s business to skip it, and none of `validate`'s to fail it.
    _seed(tmp_path)
    _write(tmp_path, "v1", {"id": "interpretation:v1", "kind": "interpretation"})
    _write(
        tmp_path,
        "a",
        {"id": "interpretation:a", "kind": "interpretation", "relations": [_supersedes("interpretation:v1")]},
    )
    _write(
        tmp_path,
        "b",
        {"id": "interpretation:b", "kind": "interpretation", "relations": [_supersedes("interpretation:v1")]},
    )

    assert "relation.cycle" not in _rules(tmp_path)


def test_a_LEGAL_CHAIN_raises_NO_relation_ERROR_AT_ALL(tmp_path: Path) -> None:
    # THE CONTROL that makes every rule in this file falsifiable at once. An ordinary, valid,
    # fully-reconciled chain -- legal pair, no self-edge, acyclic, inverse backed by its edge. If any
    # `relation.*` fires here, the check is "any authored relation is a finding" wearing a better
    # name.
    _seed(tmp_path)
    _write(
        tmp_path,
        "i1",
        {
            "id": "interpretation:i1",
            "kind": "interpretation",
            "status": "superseded",
            "superseded_by": "interpretation:i2",
        },
    )
    _write(
        tmp_path,
        "i2",
        {"id": "interpretation:i2", "kind": "interpretation", "relations": [_supersedes("interpretation:i1")]},
    )

    assert not [r for r in _rules(tmp_path) if r.startswith("relation.")]
