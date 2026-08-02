from datetime import date

import pytest

from science_tool.annotation.promote import (
    PromotionApplyError,
    PromotionCandidate,
    build_targets,
    numeric_target,
)


def _mint(kind, claim, project_root, slug="claim-slug"):
    """Plan and publish one numeric mint for the template-faithfulness tests."""
    from science_tool.annotation.planned_edits import plan_numeric_create, publish_edit
    from science_tool.entity_reservation import propose_number

    c = PromotionCandidate(
        ref="annotation:papers/p#f1", frag="f1", claim=claim, subject="s", object="o",
        decision="MINT", slug=slug, reason="new entity", kind=kind,
    )
    number = propose_number(project_root, kind)
    planned = numeric_target(kind).plan_mint(
        c, ["paper:p", c.ref], project_root, date(2026, 6, 16), number, None
    )
    assert planned.operation == "create"
    kind_prefix, local_part = planned.entity_id.split(":", 1)
    publish_edit(
        plan_numeric_create(
            planned.path,
            planned.post_image,
            "test",
            kind=kind_prefix,
            local_part=local_part,
            number=planned.claim_number,
        ),
        project_root=project_root,
    )
    return planned.entity_id


def test_mint_question_is_template_faithful(tmp_path):
    eid = _mint("question", "What drives tumor growth?", tmp_path)
    assert eid.startswith("question:0001-")
    text = (tmp_path / "entities" / "questions" / f"{eid.split(':', 1)[1]}.md").read_text()
    # Frontmatter: numeric id, default status, both provenance refs; no phase on questions.
    assert eid in text
    assert "status: active" in text
    assert "paper:p" in text and "annotation:papers/p#f1" in text
    assert "phase:" not in text
    # All required question sections present; claim inserted into the lead Summary section.
    for section in ("## Summary", "## Why It Matters", "## Current Evidence",
                    "## Thoughts", "## Connections to Project", "## Related"):
        assert section in text
    summary = text.split("## Summary", 1)[1].split("## Why It Matters", 1)[0]
    assert "What drives tumor growth?" in summary


def test_mint_hypothesis_is_a_DRAFT(tmp_path):
    eid = _mint("hypothesis", "Drug X inhibits pathway Y", tmp_path)
    assert eid.startswith("hypothesis:0001-")
    text = (tmp_path / "entities" / "hypotheses" / f"{eid.split(':', 1)[1]}.md").read_text()
    # A promoted claim is a TRIAL FRAMING -- `phase: candidate` in the collapsed spelling, and
    # `status: draft` in the lifecycle that replaced it. ONE field says it now.
    assert "status: draft" in text
    assert "phase:" not in text
    for section in ("## Organizing Conjecture", "## Proposition Bundle", "## Predictions",
                    "## Falsifiability", "## Related Work"):
        assert section in text
    conjecture = text.split("## Organizing Conjecture", 1)[1].split("## Proposition Bundle", 1)[0]
    assert "Drug X inhibits pathway Y" in conjecture


def test_mint_assigns_next_number(tmp_path):
    first = _mint("question", "First question?", tmp_path, slug="first-q")
    second = _mint("question", "Second question?", tmp_path, slug="second-q")
    assert first.startswith("question:0001-")
    assert second.startswith("question:0002-")


def test_planning_a_mint_writes_nothing_and_consumes_no_number(tmp_path):
    from science_tool.entity_reservation import propose_number

    (tmp_path / "entities" / "questions").mkdir(parents=True)
    before_number = propose_number(tmp_path, "question")
    c = PromotionCandidate(
        ref="annotation:papers/p#f1",
        frag="f1",
        claim="What drives growth?",
        subject="s",
        object="o",
        decision="MINT",
        slug="what-drives-growth",
        reason="new entity",
        kind="question",
    )

    planned = build_targets()["question"].plan_mint(
        c, ["paper:p", c.ref], tmp_path, date(2026, 6, 16), before_number, None
    )

    assert planned.claim_number == before_number
    assert not any((tmp_path / "entities" / "questions").glob("*.md"))
    assert propose_number(tmp_path, "question") == before_number


def test_plan_mint_rejects_a_malformed_slug(tmp_path):
    from science_tool.entities import EntityCommandError

    c = PromotionCandidate(
        ref="annotation:papers/p#f1",
        frag="f1",
        claim="Q?",
        subject="s",
        object="o",
        decision="MINT",
        slug="Not A Slug!",
        reason="new entity",
        kind="question",
    )

    with pytest.raises(EntityCommandError):
        numeric_target("question").plan_mint(c, ["paper:p"], tmp_path, None, 1, None)


def test_a_refused_batch_consumes_no_number(tmp_path, monkeypatch):
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import apply_candidates
    from science_tool.entities import EntityDegradationError
    from science_tool.entity_reservation import propose_number

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "propositions" / "bad.md").write_text(
        '---\nid: proposition:bad\nkind: proposition\ntitle: Bad\nstatus: draft\n'
        'source_refs: []\ncreated: "2026-06-01"\nupdated: "2026-06-01"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    before = propose_number(tmp_path, "question")

    def refuse(*_a, entity_path, **_k):
        raise EntityDegradationError(f"{entity_path} would be degraded")

    monkeypatch.setattr(promote_mod, "render_entity_source_refs", refuse)

    with pytest.raises(PromotionApplyError):
        apply_candidates(
            [
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-1",
                    frag="a-1",
                    claim="Q?",
                    subject="s",
                    object="o",
                    decision="MINT",
                    slug="a-question",
                    reason="new",
                    kind="question",
                ),
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-2",
                    frag="a-2",
                    claim="Bad",
                    subject="s",
                    object="o",
                    decision="LINK",
                    slug="proposition:bad",
                    reason="existing",
                    kind="proposition",
                ),
            ],
            sidecar_path=sp,
            project_root=tmp_path,
            paper_ref="paper:p",
        )

    assert propose_number(tmp_path, "question") == before
    assert not any((tmp_path / "entities" / "questions").glob("*.md"))


def test_a_write_stage_failure_reports_what_was_already_written(tmp_path, monkeypatch):
    import science_tool.annotation.promote as promote_mod
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import apply_candidates
    from science_tool.entity_reservation import LOCAL_PART_WIDTH, claim_number_in_dir

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "propositions" / "existing.md").write_text(
        '---\nid: proposition:existing\nkind: proposition\ntitle: Existing\nstatus: draft\n'
        'source_refs: []\ncreated: "2026-06-01"\nupdated: "2026-06-01"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))
    real_publish = promote_mod.publish_edit

    def steal_the_number(edit, *, project_root):
        if edit.claim_number is not None:
            claim_number_in_dir(
                project_root,
                "question",
                edit.claim_number,
                f"{edit.claim_number:0{LOCAL_PART_WIDTH}d}-other",
                "---\nid: question:x\n---\n",
            )
        return real_publish(edit, project_root=project_root)

    monkeypatch.setattr(promote_mod, "publish_edit", steal_the_number)

    with pytest.raises(PromotionApplyError) as excinfo:
        apply_candidates(
            [
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-1",
                    frag="a-1",
                    claim="Existing",
                    subject="s",
                    object="o",
                    decision="LINK",
                    slug="proposition:existing",
                    reason="existing",
                    kind="proposition",
                ),
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-2",
                    frag="a-2",
                    claim="Q?",
                    subject="s",
                    object="o",
                    decision="MINT",
                    slug="a-question",
                    reason="new",
                    kind="question",
                ),
            ],
            sidecar_path=sp,
            project_root=tmp_path,
            paper_ref="paper:p",
        )

    message = str(excinfo.value)
    assert "stage=write" in message
    assert "files_written=1" in message
    assert "existing.md" in message


def test_a_malformed_kind_template_aborts_before_any_write(tmp_path, monkeypatch):
    from science_model.templates import EntityTemplateError, Renderer

    from science_tool.annotation import io as anno_io
    from science_tool.annotation.promote import apply_candidates

    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    existing = tmp_path / "entities" / "propositions" / "existing.md"
    existing.write_text(
        '---\nid: proposition:existing\nkind: proposition\ntitle: Existing\nstatus: draft\n'
        'source_refs: []\ncreated: "2026-06-01"\nupdated: "2026-06-01"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    existing_before = existing.read_text(encoding="utf-8")
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text("Body.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=()))

    def malformed_sections(self, kind):
        raise EntityTemplateError(f"packaged template for {kind} is malformed")

    monkeypatch.setattr(Renderer, "sections", malformed_sections)

    with pytest.raises(EntityTemplateError):
        apply_candidates(
            [
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-1",
                    frag="a-1",
                    claim="Existing",
                    subject="s",
                    object="o",
                    decision="LINK",
                    slug="proposition:existing",
                    reason="existing",
                    kind="proposition",
                ),
                PromotionCandidate(
                    ref="annotation:papers/p.source#a-2",
                    frag="a-2",
                    claim="Q?",
                    subject="s",
                    object="o",
                    decision="MINT",
                    slug="a-question",
                    reason="new",
                    kind="question",
                ),
            ],
            sidecar_path=sp,
            project_root=tmp_path,
            paper_ref="paper:p",
        )

    assert existing.read_text(encoding="utf-8") == existing_before


def test_build_targets_includes_numeric():
    targets = build_targets()
    assert targets["question"].slug_addressed is False
    assert targets["hypothesis"].slug_addressed is False
