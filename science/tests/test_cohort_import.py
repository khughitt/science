from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.entity_import import (
    AttributedWarning,
    CohortImportPlan,
    EntityImportError,
    ImportMember,
    RefDependentCohortError,
    _source_digest,
    _validate_cohort_plan_for_apply,
    apply_cohort_import,
    parse_cohort_import_plan,
    plan_cohort_import,
)
from science_tool.reference_rewrite import plan_reference_rewrite


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8"
    )
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _loose(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _member(n: int) -> ImportMember:
    return ImportMember(
        source_rel=f"doc/plans/x{n}.md",
        source_sha256="0" * 64,
        entity_id=f"plan:{n:04d}-x{n}",
        number=n,
        dest_rel=f"entities/plans/{n:04d}-x{n}.md",
        title=f"X{n}",
        status="proposed",
        frontmatter={"id": f"plan:{n:04d}-x{n}", "kind": "plan"},
        rendered_text="body",
    )


def test_cohort_plan_defaults_and_discriminator():
    plan = CohortImportPlan(
        project_root="/r", kind="plan", members=[_member(1), _member(2)]
    )
    assert plan.plan_type == "cohort-import"
    assert plan.schema_version == 1


def test_cohort_plan_forbids_extra_fields():
    with pytest.raises(Exception):
        CohortImportPlan(
            project_root="/r",
            kind="plan",
            members=[_member(1), _member(2)],
            bogus=1,
        )


def test_member_forbids_extra_fields():
    with pytest.raises(Exception):
        ImportMember(
            source_rel="s",
            source_sha256="0" * 64,
            entity_id="plan:0001-x",
            number=1,
            dest_rel="d",
            title="t",
            status="proposed",
            frontmatter={},
            rendered_text="b",
            kind="plan",
        )


def test_parse_cohort_round_trips():
    plan = CohortImportPlan(
        project_root="/r",
        kind="plan",
        members=[_member(1), _member(2)],
        warnings=[
            AttributedWarning(source_rel="doc/plans/x1.md", message="w")
        ],
    )
    raw = plan.model_dump_json().encode("utf-8")
    assert parse_cohort_import_plan(raw) == plan


def test_parse_cohort_rejects_garbage():
    with pytest.raises(EntityImportError):
        parse_cohort_import_plan(b'{"not": "a plan"}')


def test_parse_cohort_rejects_non_integer_schema_version():
    """StrictInt: a boolean or string schema_version must NOT coerce to 1."""
    base = CohortImportPlan(
        project_root="/r", kind="plan", members=[_member(1), _member(2)]
    )
    payload = base.model_dump(mode="json")
    for bad in (True, "1"):
        raw = json.dumps({**payload, "schema_version": bad}).encode("utf-8")
        with pytest.raises(EntityImportError):
            parse_cohort_import_plan(raw)


def test_ref_dependent_error_is_import_error():
    assert issubclass(RefDependentCohortError, EntityImportError)


def test_cohort_assigns_contiguous_number_block(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    c = _loose(root, "doc/plans/c.md", "# Gamma\n\nbody\n")
    plan = plan_cohort_import(root, [a, b, c], kind="plan")
    assert [m.number for m in plan.members] == [1, 2, 3]
    assert [m.entity_id for m in plan.members] == [
        "plan:0001-alpha",
        "plan:0002-beta",
        "plan:0003-gamma",
    ]
    assert [m.source_rel for m in plan.members] == [
        "doc/plans/a.md",
        "doc/plans/b.md",
        "doc/plans/c.md",
    ]


def test_cohort_one_combined_inbound_rewrite(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    _loose(
        root,
        "doc/notes.md",
        "see [a](plans/a.md) and [b](plans/b.md)\n",
    )
    plan = plan_cohort_import(root, [a, b], kind="plan")
    edited = [e.rel_path for e in plan.ref_report.edits]
    assert "doc/notes.md" in edited
    news = {h.new for h in plan.ref_report.hits if h.rel_path == "doc/notes.md"}
    assert any("0001-alpha" in new for new in news)
    assert any("0002-beta" in new for new in news)


def test_cohort_rejects_member_linking_member(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nsee [b](b.md)\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    msg = str(excinfo.value)
    assert "doc/plans/a.md" in msg and "doc/plans/b.md" in msg


def test_cohort_rejects_bare_path_mention_of_member(tmp_path):
    root = _project(tmp_path)
    a = _loose(
        root,
        "doc/plans/a.md",
        "# Alpha\n\nmentions doc/plans/b.md inline\n",
    )
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    assert "doc/plans/a.md" in str(excinfo.value)
    assert "doc/plans/b.md" in str(excinfo.value)


def test_cohort_rejects_self_link(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nsee [me](a.md)\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    assert "doc/plans/a.md -> doc/plans/a.md" in str(excinfo.value)


def test_cohort_pair_attribution_disambiguates_shared_basenames(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/a/x.md", "# Alpha\n\nsee [t](../../draft/x.md)\n")
    b = _loose(root, "draft/x.md", "# Beta\n\nbody\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [a, b], kind="plan")
    msg = str(excinfo.value)
    assert "doc/a/x.md -> draft/x.md" in msg
    assert "doc/a/x.md -> doc/a/x.md" not in msg


def test_cohort_runs_one_combined_scan_with_cached_overrides(tmp_path, monkeypatch):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    import science_tool.entity_import as ei

    calls: list[dict] = []
    real = ei.plan_reference_rewrite

    def spy(project_root, **kwargs):
        calls.append(kwargs)
        return real(project_root, **kwargs)

    monkeypatch.setattr(ei, "plan_reference_rewrite", spy)
    plan_cohort_import(root, [a, b], kind="plan")
    assert len(calls) == 1
    overrides = calls[0]["source_overrides"]
    assert set(overrides) == {"doc/plans/a.md", "doc/plans/b.md"}
    assert overrides["doc/plans/a.md"] == "# Alpha\n\nbody\n"


def test_cohort_preserves_external_manual_finding(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    _loose(root, "doc/notes.md", "the file doc/plans/a.md is worth reading\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    assert any(man.rel_path == "doc/notes.md" for man in plan.ref_report.manual)


def test_cohort_requires_two_sources(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    with pytest.raises(EntityImportError):
        plan_cohort_import(root, [a], kind="plan")


def test_cohort_rejects_duplicate_sources(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    with pytest.raises(EntityImportError):
        plan_cohort_import(root, [a, a], kind="plan")


def test_cohort_rejects_excluding_a_member_from_independence_scan(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nsee [me](a.md)\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    with pytest.raises(EntityImportError, match="exclude.*member"):
        plan_cohort_import(root, [a, b], kind="plan", exclude=frozenset({a}))


def test_cohort_manual_pair_attribution_uses_exact_overlapping_path(tmp_path):
    root = _project(tmp_path)
    short = _loose(root, "a.md", "# Alpha\n\nbody\n")
    nested = _loose(root, "docs/a.md", "# Beta\n\nbody\n")
    referrer = _loose(root, "member.md", "# Gamma\n\nmentions docs/a.md\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [short, nested, referrer], kind="plan")
    message = str(excinfo.value)
    assert "member.md -> docs/a.md" in message
    assert "member.md -> a.md" not in message


def test_cohort_manual_pair_attribution_handles_symbol_prefix(tmp_path):
    root = _project(tmp_path)
    short = _loose(root, "a.md", "# Alpha\n\nbody\n")
    symbol = _loose(root, "@a.md", "# Beta\n\nbody\n")
    referrer = _loose(root, "member.md", "# Gamma\n\nmentions @a.md\n")
    with pytest.raises(RefDependentCohortError) as excinfo:
        plan_cohort_import(root, [short, symbol, referrer], kind="plan")
    message = str(excinfo.value)
    assert "member.md -> @a.md" in message
    assert "member.md -> a.md" not in message


def _valid_plan(root: Path) -> CohortImportPlan:
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    return plan_cohort_import(root, [a, b], kind="plan")


def test_validate_accepts_a_fresh_plan(tmp_path):
    root = _project(tmp_path)
    sources = _validate_cohort_plan_for_apply(root, _valid_plan(root))
    assert sources == [
        (root / "doc/plans/a.md").resolve(),
        (root / "doc/plans/b.md").resolve(),
    ]


def test_validate_rejects_fewer_than_two_members(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members.pop()
    with pytest.raises(EntityImportError, match="fewer than 2"):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_non_contiguous_numbers(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[1].number = 9
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_duplicate_entity_ids(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[1].entity_id = plan.members[0].entity_id
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


@pytest.mark.parametrize("field", ["source_rel", "dest_rel"])
def test_validate_rejects_duplicate_source_or_destination(tmp_path, field):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    setattr(plan.members[1], field, getattr(plan.members[0], field))
    with pytest.raises(EntityImportError, match=field):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_source_dest_overlap(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[0].dest_rel = plan.members[1].source_rel
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_tampered_destination(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[0].dest_rel = "entities/plans/9999-evil.md"
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_translates_unknown_kind(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.kind = "notarealkind"
    for number, member in enumerate(plan.members, start=1):
        member.entity_id = f"notarealkind:{number:04d}-x"
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_rendered_kind_tamper(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    member = plan.members[0]
    member.rendered_text = member.rendered_text.replace("kind: plan", "kind: question")
    with pytest.raises(EntityImportError):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_stored_frontmatter_tamper(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[0].frontmatter["kind"] = "question"
    with pytest.raises(EntityImportError, match="frontmatter"):
        _validate_cohort_plan_for_apply(root, plan)


def test_validate_rejects_sources_with_the_same_resolved_identity(tmp_path):
    root = _project(tmp_path)
    plan = _valid_plan(root)
    plan.members[1].source_rel = "doc/plans//a.md"

    with pytest.raises(EntityImportError, match="same resolved source"):
        _validate_cohort_plan_for_apply(root, plan)


def test_cohort_apply_consumes_validated_source_behind_symlink_alias(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    alias = root / "doc/plans/alias.md"
    alias.symlink_to("a.md")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    plan.members[0].source_rel = "doc/plans/alias.md"
    source_paths = {alias, b}
    destinations = {root / member.dest_rel for member in plan.members}
    plan.ref_report = plan_reference_rewrite(
        root,
        id_substitutions={
            member.source_rel: member.entity_id for member in plan.members
        },
        path_substitutions={
            member.source_rel: member.dest_rel for member in plan.members
        },
        exclude=frozenset(source_paths | destinations),
    )

    apply_cohort_import(root, plan)

    assert not a.exists(), "validated source bytes were not consumed"
    assert not alias.is_symlink(), "lexical source alias was not consumed"
    assert not b.exists()


def test_cohort_planner_rejects_outside_source_before_reading(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    root = _project(project_dir)
    inside = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    outside = _loose(tmp_path, "outside.md", "# Outside\n\nbody\n")
    real_read_text = Path.read_text

    def guarded_read_text(path, *args, **kwargs):
        if path == outside:
            pytest.fail("outside source was read before containment validation")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    with pytest.raises(EntityImportError, match="outside project root"):
        plan_cohort_import(root, [outside, inside], kind="plan")


def test_cohort_planner_outside_excluded_source_has_domain_error(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    root = _project(project_dir)
    inside = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    outside = _loose(tmp_path, "outside.md", "# Outside\n\nbody\n")

    with pytest.raises(EntityImportError, match="outside project root"):
        plan_cohort_import(
            root, [outside, inside], kind="plan", exclude=frozenset({outside})
        )


def test_source_digest_translates_invalid_utf8(tmp_path):
    source = tmp_path / "bad.md"
    source.write_bytes(b"\xff")
    with pytest.raises(EntityImportError, match="valid UTF-8"):
        _source_digest(source, "bad.md")


def test_source_digest_translates_missing_file(tmp_path):
    with pytest.raises(EntityImportError, match="could not be read"):
        _source_digest(tmp_path / "missing.md", "missing.md")


def test_cohort_apply_happy_path(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    notes = _loose(root, "doc/notes.md", "see [a](plans/a.md) and [b](plans/b.md)\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    assert apply_cohort_import(root, plan) == ["plan:0001-alpha", "plan:0002-beta"]
    assert not a.exists() and not b.exists()
    assert (root / "entities/plans/0001-alpha.md").exists()
    assert (root / "entities/plans/0002-beta.md").exists()
    rewritten = notes.read_text(encoding="utf-8")
    assert "0001-alpha.md" in rewritten and "0002-beta.md" in rewritten


def test_cohort_apply_rolls_back_on_preclaimed_number(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    notes = _loose(root, "doc/notes.md", "see [b](plans/b.md)\n")
    before = notes.read_text(encoding="utf-8")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    (root / "entities/plans/0002-someone.md").write_text(
        "---\nkind: plan\ntitle: Someone\nstatus: proposed\n"
        "created: '2026-07-19'\nupdated: '2026-07-19'\n"
        "id: plan:0002-someone\n---\n# Someone\n",
        encoding="utf-8",
    )
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()
    assert not (root / "entities/plans/0001-alpha.md").exists()
    assert notes.read_text(encoding="utf-8") == before


def test_cohort_apply_survives_mid_claim_source_edit(tmp_path, monkeypatch):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    import science_tool.entity_import as ei

    real_claim = ei.claim_number_in_dir
    claims = 0

    def hooked_claim(*args, **kwargs):
        nonlocal claims
        path = real_claim(*args, **kwargs)
        claims += 1
        if claims == 1:
            b.write_text("# Beta EDITED\n\nnew body\n", encoding="utf-8")
        return path

    monkeypatch.setattr(ei, "claim_number_in_dir", hooked_claim)
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert b.read_text(encoding="utf-8") == "# Beta EDITED\n\nnew body\n"
    assert a.exists()
    assert not (root / "entities/plans/0001-alpha.md").exists()
    assert not (root / "entities/plans/0002-beta.md").exists()


def test_cohort_apply_refuses_tampered_report_before_snapshot(tmp_path, monkeypatch):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    from science_tool.reference_rewrite import FileEdit

    plan.ref_report.edits.append(
        FileEdit(rel_path="doc/evil.md", preimage_sha256="0" * 64, postimage="x")
    )
    import science_tool.entity_import as ei

    monkeypatch.setattr(ei, "_snapshot", lambda _paths: pytest.fail("snapshot reached"))
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)


def test_cohort_apply_refuses_report_map_mismatch_before_snapshot(tmp_path, monkeypatch):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    plan.ref_report.path_substitutions[plan.members[0].source_rel] = "entities/plans/9999-wrong.md"
    import science_tool.entity_import as ei

    monkeypatch.setattr(ei, "_snapshot", lambda _paths: pytest.fail("snapshot reached"))
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)


def test_cohort_apply_refuses_initial_source_drift(tmp_path):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    a.write_text("# Alpha CHANGED\n\nbody\n", encoding="utf-8")
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()


def test_cohort_apply_cleans_up_on_claim_path_mismatch(tmp_path, monkeypatch):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    import science_tool.entity_import as ei

    real_claim = ei.claim_number_in_dir

    def wrong_claim(project_root, kind, number, local_part, text):
        canonical = real_claim(project_root, kind, number, local_part, text)
        canonical.unlink()
        rogue = root / "entities/plans" / f"{number:04d}-rogue.md"
        rogue.write_text(text, encoding="utf-8")
        return rogue

    monkeypatch.setattr(ei, "claim_number_in_dir", wrong_claim)
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert not (root / "entities/plans/0001-rogue.md").exists()
    assert a.exists() and b.exists()


def test_cohort_apply_rolls_back_on_inbound_rewrite_failure(tmp_path, monkeypatch):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    notes = _loose(root, "doc/notes.md", "see [a](plans/a.md)\n")
    before = notes.read_text(encoding="utf-8")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    import science_tool.entity_import as ei
    from science_tool.reference_rewrite import ReferenceDriftError

    monkeypatch.setattr(
        ei,
        "apply_reference_rewrite",
        lambda *args, **kwargs: (_ for _ in ()).throw(ReferenceDriftError("boom")),
    )
    with pytest.raises(ReferenceDriftError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()
    assert not (root / "entities/plans/0001-alpha.md").exists()
    assert not (root / "entities/plans/0002-beta.md").exists()
    assert notes.read_text(encoding="utf-8") == before


def test_cohort_apply_rolls_back_real_referrer_on_audit_failure(tmp_path, monkeypatch):
    root = _project(tmp_path)
    a = _loose(root, "doc/plans/a.md", "# Alpha\n\nbody\n")
    b = _loose(root, "doc/plans/b.md", "# Beta\n\nbody\n")
    notes = _loose(root, "doc/notes.md", "see [a](plans/a.md)\n")
    before = notes.read_text(encoding="utf-8")
    plan = plan_cohort_import(root, [a, b], kind="plan")
    assert any(edit.rel_path == "doc/notes.md" for edit in plan.ref_report.edits)
    import science_tool.entity_import as ei

    monkeypatch.setattr(ei, "audit_moved_references", lambda *args, **kwargs: ["dangling"])
    with pytest.raises(EntityImportError):
        apply_cohort_import(root, plan)
    assert a.exists() and b.exists()
    assert not (root / "entities/plans/0001-alpha.md").exists()
    assert not (root / "entities/plans/0002-beta.md").exists()
    assert notes.read_text(encoding="utf-8") == before
