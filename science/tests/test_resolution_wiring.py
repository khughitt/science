"""The cross-record layer, WIRED — through the REAL loader and the REAL validate run.

`test_resolution.py` (model) proves `check_resolution`'s LOGIC against a stub. It proves **nothing
about the resolver the loader actually builds**, and that construction is where the wiring silently
rots: drop `manual_aliases=` from `ReferenceResolver.from_entities` and every unit test still
passes, because the stub was never wired to it.

Worse, a COUNT-ONLY assertion hides it. Omit `manual_aliases` and an archived successor stops
resolving -- so it becomes an *unresolved* violation instead of a *not-live* one. Still one finding,
still green, wiring defect invisible. The archived test below therefore asserts the MESSAGE, which
is the only thing that distinguishes "the resolver could not find it" from "the resolver found it,
and it is dead".
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from science_model.entity_schema import EntityValidationError, EntityValidator, default_profile_for_kind

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.sources import load_project_sources
from science_tool.validate import runner
from science_tool.validate.checks.hypotheses import RULE_DANGLING_LINEAGE, check_dangling_lineage
from science_tool.validate.context import ValidateContext


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "id": "demo"}), encoding="utf-8"
    )
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    return tmp_path


def write_hypothesis(
    root: Path,
    slug: str,
    *,
    status: str = "active",
    aliases: list[str] | None = None,
    extra: dict[str, object] | None = None,
) -> Path:
    frontmatter: dict[str, object] = {
        "id": f"hypothesis:{slug}",
        "kind": "hypothesis",
        "title": slug,
        "created": "2026-07-13",
        "updated": "2026-07-13",
        "status": status,
    }
    if aliases:
        frontmatter["aliases"] = aliases
    frontmatter.update(extra or {})
    path = root / "entities" / "hypotheses" / f"{slug}.md"
    path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n# {slug}\n", encoding="utf-8"
    )
    return path


def archive_entity(root: Path, canonical_id: str) -> None:
    """Index-only: the archived markdown is NOT loaded as a live entity, but the id stays
    RESOLVABLE (sources.py folds `resolvable_ids()` into `manual_aliases`)."""
    index = root / "entities" / "_archive" / "archive-index.jsonl"
    index.parent.mkdir(parents=True, exist_ok=True)
    row = {"schema_version": 1, "op": "archive", "id": canonical_id, "kind": "hypothesis"}
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def run_validate(root: Path):
    return runner.run(root, strict=False, verbose=False).results


def lineage_violations(root: Path):
    """The check IS the wiring: it builds the REAL resolver over the REAL loaded corpus.

    The resolver is deliberately NOT built inside `load_project_sources` -- see
    `check_dangling_lineage`'s docstring. Doing so makes an alias collision UNLOADABLE rather than
    reportable, and breaks `proposition_archive`, whose whole job is to report them.
    """
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_dangling_lineage(ctx))


def _validate_hypothesis(frontmatter: dict[str, object]) -> None:
    EntityValidator().validate_as(frontmatter, default_profile_for_kind("hypothesis"))


# ---------------------------------------------------------------------------------------------
# through the REAL validate run
# ---------------------------------------------------------------------------------------------


def test_validate_reports_a_dangling_successor(tmp_project: Path) -> None:
    write_hypothesis(
        tmp_project, "0001-x", status="superseded", extra={"superseded_by": "hypothesis:9999-nope"}
    )
    findings = [r for r in run_validate(tmp_project) if r.rule == RULE_DANGLING_LINEAGE]
    assert len(findings) == 1
    # WARN, hard-coded, until the kind is certified. Task 12 routes this emitter through
    # `severity_for_kind` and inverts this exact assertion -- so if that step is skipped, THAT test
    # fails. The promise has a test now, not a comment.
    assert findings[0].severity == "warn"
    assert "9999-nope" in findings[0].message


def test_the_dangling_lineage_rule_is_NOT_GATED_yet() -> None:
    # WARN that fails no build. The rule's absence from every gate tier is the whole content of
    # "ungated" -- and it is the claim Task 12 later inverts, so it needs to be pinned HERE.
    from science_tool.validate.gates import cumulative_rules

    assert RULE_DANGLING_LINEAGE not in cumulative_rules("hygiene")


# ---------------------------------------------------------------------------------------------
# the four resolution cases, through the REAL loader
# ---------------------------------------------------------------------------------------------


def test_a_LIVE_ALIAS_resolves_through_the_REAL_loader(tmp_project: Path) -> None:
    # `aliases:` frontmatter -> `build_alias_map`. Raw membership on a set of ids would call this
    # dangling and REFUSE A CORRECT CORPUS.
    write_hypothesis(tmp_project, "0002-y", aliases=["hypothesis:0002"])
    write_hypothesis(
        tmp_project, "0001-x", status="superseded", extra={"superseded_by": "hypothesis:0002"}
    )
    assert lineage_violations(tmp_project) == []


def test_a_SELF_ALIAS_is_caught_through_the_REAL_loader(tmp_project: Path) -> None:
    # An alias OF the entity, written ON the entity. As a STRING it differs from the id, so a
    # `ref == entity_id` check never fires; it resolves cleanly and reads as a valid successor.
    write_hypothesis(
        tmp_project,
        "0001-x",
        status="superseded",
        aliases=["hypothesis:x-alias"],
        extra={"superseded_by": "hypothesis:x-alias"},
    )
    violations = lineage_violations(tmp_project)
    assert len(violations) == 1
    assert "itself" in violations[0].message


def test_an_ARCHIVED_successor_RESOLVES_and_is_still_a_violation(tmp_project: Path) -> None:
    # ☠️ THE test that pins `manual_aliases=`. Archived ids are folded into `manual_aliases` and are
    # deliberately NOT loaded as live entities -- so an archived successor RESOLVES and is absent
    # from the live-hypothesis set.
    #
    # Assert the MESSAGE, not the count. Omit `manual_aliases=` from `from_entities` and this ref
    # simply fails to resolve: still exactly one violation, still green, and the wiring defect is
    # invisible. The message is the only witness that the resolver FOUND it and found it DEAD.
    write_hypothesis(tmp_project, "0003-gone")
    archive_entity(tmp_project, "hypothesis:0003-gone")
    (tmp_project / "entities" / "hypotheses" / "0003-gone.md").unlink()  # archived: not live
    write_hypothesis(
        tmp_project, "0001-x", status="superseded", extra={"superseded_by": "hypothesis:0003-gone"}
    )
    violations = lineage_violations(tmp_project)
    assert len(violations) == 1
    assert "not a live hypothesis" in violations[0].message  # NOT "does not resolve"


def test_an_UNRESOLVED_token_is_a_violation_through_the_REAL_loader(tmp_project: Path) -> None:
    write_hypothesis(
        tmp_project, "0001-x", status="superseded", extra={"superseded_by": "hypothesis:9999-nope"}
    )
    violations = lineage_violations(tmp_project)
    assert len(violations) == 1
    assert "does not resolve" in violations[0].message


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("superseded_by", "demo:hypothesis:0002-y"),
        ("resynthesized_into", ["demo:hypothesis:0002-y"]),
    ],
)
def test_a_SCOPED_lineage_ref_is_REJECTED_BY_THE_SCHEMA(field: str, value: object) -> None:
    # Lineage is UNSCOPED. Both fields are `pattern: "^hypothesis:"`, so `demo:hypothesis:0002-y`
    # never reaches the resolver -- it fails schema validation first.
    #
    # This test exists because an earlier draft asserted the OPPOSITE: that a scoped successor
    # resolves cleanly through the loader. That test could not have passed. Rather than widen the
    # pattern to keep it alive -- tuning the contract to serve a test -- the ban is made EXPLICIT
    # here, and it is what the corpus already says: ZERO hypotheses author lineage at all, and ZERO
    # scoped refs (`scope:kind:slug`) exist anywhere in the 18 roots.
    with pytest.raises(EntityValidationError):
        _validate_hypothesis(
            {
                "id": "hypothesis:0001-x",
                "kind": "hypothesis",
                "title": "T",
                "created": "2026-07-13",
                "updated": "2026-07-13",
                "status": "superseded",
                field: value,
            }
        )


def test_the_LOADER_can_actually_SEE_the_terminal_fields(tmp_project: Path) -> None:
    # The test that would have caught the inert wiring. `check_resolution` reads PROJECTED entities,
    # and `HypothesisEntity` dropped all four terminal fields until Step 3 -- so the second pass
    # would have inspected a stripped record, found no reference, and reported clean. Assert the
    # SUBSTRATE, not just the finding: a green resolver over a blind loader is the silent instrument
    # this arc exists to abolish.
    from science_model.entities import HypothesisEntity

    for field in ("verdict", "closure_basis", "superseded_by", "resynthesized_into"):
        assert field in HypothesisEntity.model_fields, (
            f"{field}: the check cannot see what the model drops"
        )

    write_hypothesis(
        tmp_project, "0001-x", status="superseded", extra={"superseded_by": "hypothesis:9999-nope"}
    )
    sources = load_project_sources(tmp_project)

    entity = next(e for e in sources.entities if e.id == "hypothesis:0001-x")
    assert isinstance(entity, HypothesisEntity)  # it projected to the TYPED subclass...
    assert entity.superseded_by == "hypothesis:9999-nope"  # ...and the field SURVIVED

    # ...and the check, reading those projected entities through the REAL resolver, SAW it.
    assert ["9999-nope" in v.message for v in lineage_violations(tmp_project)] == [True]


def test_the_LOADER_does_not_build_a_RESOLVER(tmp_path: Path) -> None:
    # ☠️ THE regression that keeps coming back. Putting the lineage resolver inside
    # `load_project_sources` is tempting -- the loader has the whole corpus right there -- and it is
    # wrong, because `ReferenceResolver.from_entities` RAISES `AliasCollisionError` on a corpus with
    # a duplicated alias. Build it in the loader and a REPORTABLE fault becomes an UNLOADABLE
    # project, for every caller of the loader, including the ones that never touch a hypothesis.
    #
    # `annotation/proposition_archive.py` exists to REPORT and unblock exactly these collisions, and
    # it calls `load_project_sources` on a colliding corpus ON PURPOSE. The loader-side pass breaks
    # it. So: the loader must LOAD a colliding corpus without complaint, and resolution -- which is
    # analysis, not loading -- happens in the check.
    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "demo", "id": "demo"}), encoding="utf-8")
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    # two entities claiming ONE alias -> AliasCollisionError the instant a resolver is built
    write_hypothesis(tmp_path, "0001-x", aliases=["hypothesis:shared"])
    write_hypothesis(tmp_path, "0002-y", aliases=["hypothesis:shared"])

    sources = load_project_sources(tmp_path)  # must NOT raise
    assert {e.canonical_id for e in sources.entities} == {"hypothesis:0001-x", "hypothesis:0002-y"}


def write_dataset(root: Path, slug: str, *, aliases: list[str] | None = None) -> None:
    frontmatter: dict[str, object] = {
        "id": f"dataset:{slug}",
        "kind": "dataset",
        "title": slug,
        "created": "2026-07-13",
        "updated": "2026-07-13",
        "status": "active",
    }
    if aliases:
        frontmatter["aliases"] = aliases
    path = root / "entities" / "datasets" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n# {slug}\n", encoding="utf-8"
    )


def write_interpretation(
    root: Path, slug: str, *, status: str = "active", extra: dict[str, object] | None = None
) -> None:
    frontmatter: dict[str, object] = {
        "id": f"interpretation:{slug}",
        "kind": "interpretation",
        "title": slug,
        "created": "2026-07-13",
        "updated": "2026-07-13",
        "status": status,
    }
    frontmatter.update(extra or {})
    path = root / "entities" / "interpretations" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\n\n# {slug}\n", encoding="utf-8"
    )


def test_a_CROSS_KIND_alias_successor_is_a_VIOLATION(tmp_project: Path) -> None:
    # ☠️ THE hole in `live_ids = {every entity}`. The schema constrains only the AUTHORED spelling --
    # `superseded_by` is `pattern: "^hypothesis:"` -- but an ALIAS may point ANYWHERE. So this is a
    # schema-valid `hypothesis:`-shaped ref that RESOLVES to a DATASET.
    #
    # Against the all-entities set it was found, and reported CLEAN: a hypothesis superseded by a
    # dataset, with the check's green on it. The successor population must be LIVE HYPOTHESES.
    write_dataset(tmp_project, "0002", aliases=["hypothesis:looks-valid"])
    write_hypothesis(
        tmp_project, "0001-x", status="superseded", extra={"superseded_by": "hypothesis:looks-valid"}
    )
    violations = lineage_violations(tmp_project)
    assert len(violations) == 1
    assert "dataset:0002" in violations[0].message          # it RESOLVED -- to the wrong kind
    assert "not a live hypothesis" in violations[0].message


def test_a_hypothesis_successor_is_STILL_clean(tmp_project: Path) -> None:
    # The matched control. Without it, a check that rejected EVERY successor would pass the test
    # above -- and the population fix would be indistinguishable from breaking lineage entirely.
    write_dataset(tmp_project, "0002", aliases=["hypothesis:looks-valid"])
    write_hypothesis(tmp_project, "0009-real")
    write_hypothesis(
        tmp_project, "0001-x", status="superseded", extra={"superseded_by": "hypothesis:0009-real"}
    )
    assert lineage_violations(tmp_project) == []


def test_an_INTERPRETATION_with_lineage_is_NOT_a_hypothesis_dangling_finding(
    tmp_project: Path,
) -> None:
    # ☠️ THE mis-scoping control. `check_dangling_lineage` iterated EVERY entity and emitted its
    # hypothesis-scoped rule, but `check_resolution` demands the successor resolve to a LIVE
    # HYPOTHESIS (`live_hypotheses`). An interpretation's successor is another INTERPRETATION, so
    # every interpretation carrying lineage tripped "not a live hypothesis" -- under
    # `hypothesis.dangling-lineage`, the wrong kind's rule, double-covering the
    # `interpretation.unbacked-inverse` supersession.py already owns. Task 12 would have PROMOTED
    # that mis-scoped WARN to a gating ERROR on four live interpretation records.
    #
    # An interpretation superseded by a LIVE interpretation is valid interpretation lineage; the
    # hypothesis dangling-lineage check must be SILENT on it. Interpretation lineage debt is
    # supersession.py's, by kind -- not this check's.
    write_interpretation(tmp_project, "0002-successor")
    write_interpretation(
        tmp_project,
        "0001-x",
        status="superseded",
        extra={"superseded_by": "interpretation:0002-successor"},
    )
    assert lineage_violations(tmp_project) == []


def test_COMMONS_can_never_own_a_hypothesis__which_is_why_KIND_is_enough() -> None:
    # ☠️ The CONTRACT that makes a separate locality filter unnecessary -- and that must FAIL LOUDLY
    # if it ever stops holding.
    #
    # `sources.entities` is local markdown PLUS the commons overlay, so "local" and "hypothesis"
    # look like two independent conditions. They are not: commons derives an entity's kind from its
    # DIRECTORY (`_TYPE_DIR_TO_TYPE`), and there is no `hypotheses/` one -- so a commons entity can
    # never BE a hypothesis. Filtering on kind therefore already excludes every non-local entity, and
    # a locality filter on top would be dead code.
    #
    # That reasoning is only sound while this holds. If commons ever gains `hypotheses/`, a SHARED
    # hypothesis becomes an acceptable-looking successor to a project that does not own it, and this
    # test is what stops that landing silently.
    from science_tool.commons.adapter import _TYPE_DIR_TO_TYPE

    assert "hypothesis" not in set(_TYPE_DIR_TO_TYPE.values()), (
        "commons can now own a hypothesis. `_live_lineage_targets` filters on kind ALONE and "
        "assumed that was impossible -- it now admits a hypothesis this project does not own as a "
        "valid successor. Add the locality filter it deliberately omitted."
    )


def test_a_COMMONS_entity_is_NOT_an_acceptable_successor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The SHARED case, through the REAL commons overlay rather than the contract alone.
    # `topic:single-cell-foundation-models` is a COMMONS-OWNED id, and the overlay puts it in
    # `sources.entities` for real -- so the all-entities population would have ACCEPTED it as a
    # successor via a `hypothesis:`-shaped alias.
    #
    # Precisely what this pins: a commons-owned id, of a commons-ownable kind, reached through the
    # actual overlay, is not an acceptable successor. It does NOT independently pin locality -- the
    # id is co-owned here, and locality cannot be tested at all while commons is unable to own a
    # hypothesis. The test above pins that contract; this one pins the overlay path.
    commons_root = tmp_path / "commons"
    shutil.copytree(Path(__file__).parent / "fixtures" / "commons" / "valid", commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    root = tmp_path / "project"
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "id": "demo"}), encoding="utf-8"
    )
    # a LOCAL alias pointing at the COMMONS-owned topic, in hypothesis clothing
    write_hypothesis(
        root, "0001-x", status="superseded",
        extra={"superseded_by": "hypothesis:shared-alias"},
    )
    (root / "entities" / "topics").mkdir(parents=True)
    (root / "entities" / "topics" / "t.md").write_text(
        "---\n"
        + yaml.safe_dump(
            {
                "id": "topic:single-cell-foundation-models",
                "kind": "topic",
                "title": "SCFM",
                "created": "2026-07-13",
                "updated": "2026-07-13",
                "status": "active",
                "aliases": ["hypothesis:shared-alias"],
            },
            sort_keys=False,
        )
        + "---\n",
        encoding="utf-8",
    )

    sources = load_project_sources(root)
    assert "topic:single-cell-foundation-models" in {e.canonical_id for e in sources.entities}

    violations = lineage_violations(root)
    assert len(violations) == 1
    assert "not a live hypothesis" in violations[0].message
