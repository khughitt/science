"""Containment of the annotation writers (design 2026-07-31, §4.2-§4.4)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from science_model.propositions import PropositionEntity

from science_tool.dag.entity_frontmatter import (
    EntityWriteError,
    Ownership,
    create_entity_file,
    update_entity_file,
)

OWNERSHIP = Ownership(frozenset({"id", "kind", "subject", "object"}), frozenset({"title", "status"}))


def _seed(tmp_path: Path) -> Path:
    # `resolve_path_policy` needs no science.yaml for the default layout -- see
    # test_annotation_promote.py:265, which seeds exactly this and nothing else.
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    return tmp_path


def _prop(**kw) -> PropositionEntity:
    base = dict(id="proposition:p", title="A affects B", subject="concept:a", object="concept:b")
    base.update(kw)
    return PropositionEntity(**base)


def test_create_entity_file_refuses_existing_destination(tmp_path: Path) -> None:
    root = _seed(tmp_path)
    entity = _prop()
    create_entity_file(entity, project_root=root, ownership=OWNERSHIP,
                       create_body="# body\n", as_of=date(2026, 7, 31))

    with pytest.raises(EntityWriteError, match="already exists"):
        create_entity_file(entity, project_root=root, ownership=OWNERSHIP,
                           create_body="# body\n", as_of=date(2026, 7, 31))


def test_create_entity_file_refuses_destination_created_during_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.dag import entity_frontmatter

    root = _seed(tmp_path)
    dest = root / "entities" / "propositions" / "p.md"
    real_render_create = entity_frontmatter.render_create

    def render_then_lose_race(*args, **kwargs):
        text = real_render_create(*args, **kwargs)
        dest.write_text("winner\n", encoding="utf-8")
        return text

    monkeypatch.setattr(entity_frontmatter, "render_create", render_then_lose_race)

    with pytest.raises(EntityWriteError, match="already exists"):
        create_entity_file(
            _prop(), project_root=root, ownership=OWNERSHIP,
            create_body="# body\n", as_of=date(2026, 7, 31),
        )
    assert dest.read_text(encoding="utf-8") == "winner\n"


def test_create_entity_file_removes_partial_stage_after_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seed(tmp_path)
    dest = root / "entities" / "propositions" / "p.md"
    real_open = Path.open

    class FailingWriter:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            self.handle.close()

        def write(self, text):
            self.handle.write(text[:8])
            self.handle.flush()
            raise OSError("injected write failure")

    def fail_exclusive_write(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        return FailingWriter(handle) if mode == "x" else handle

    monkeypatch.setattr(Path, "open", fail_exclusive_write)

    # Mutation caught: writing directly through an exclusive handle on `dest` leaves the
    # partial final file behind and leaks OSError instead of the writer's boundary error.
    with pytest.raises(EntityWriteError, match="could not create.*injected write failure"):
        create_entity_file(
            _prop(), project_root=root, ownership=OWNERSHIP,
            create_body="# body\n", as_of=date(2026, 7, 31),
        )
    assert not dest.exists()


def test_update_entity_file_refuses_missing_destination(tmp_path: Path) -> None:
    root = _seed(tmp_path)
    with pytest.raises(EntityWriteError, match="does not exist"):
        update_entity_file(_prop(), project_root=root, ownership=OWNERSHIP, as_of=date(2026, 7, 31))


def test_update_entity_file_takes_no_create_body(tmp_path: Path) -> None:
    """An update-only writer has no body to supply; the signature must not accept one."""
    root = _seed(tmp_path)
    with pytest.raises(TypeError):
        update_entity_file(_prop(), project_root=root, ownership=OWNERSHIP,
                           create_body="# nope\n")  # type: ignore[call-arg]


def _sidecar(root: Path, *, claim: str = "A affects B") -> Path:
    """A real sidecar with one open statement annotation. `apply_candidates` reads it back
    whenever any candidate produced a backlink, so a stub path will not do."""
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status

    # BARE module import: tests/ has no __init__.py, and pytest puts it on sys.path.
    # `from tests.test_... import` would fail. House convention -- see
    # test_commons_promote_source.py:6 (`from promote_source_fixtures import ...`).
    from test_annotation_promote import _statement_ann

    (root / "papers").mkdir(exist_ok=True)
    md = root / "papers" / "p.source.md"
    md.write_text(f"{claim}.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(
        sp, anno_io.Sidecar(annotations=(_statement_ann("a-1", claim, status=Status.OPEN),))
    )
    return sp


def _mint_candidate():
    """A forced same-slug MINT -- the curator-override shape. `reason` is a required field."""
    from science_tool.annotation.promote import PromotionCandidate

    return PromotionCandidate(
        ref="annotation:papers/p.source#a-1", frag="a-1", claim="A affects B",
        subject="concept:a", object="concept:b", decision="MINT",
        slug="a-affects-b", reason="forced override", kind="proposition",
    )


def test_reminting_identical_claim_accrues_and_destroys_nothing(tmp_path: Path) -> None:
    """§2.4: the live data-loss path. Fails on `main`.

    The source_refs / subject / object assertions are the ones a naive contained-UPDATE
    implementation would still fail -- they are the point of §4.3, not incidental coverage.
    """
    from science_tool.annotation.promote import apply_candidates

    root = _seed(tmp_path)
    dest = root / "entities" / "propositions" / "a-affects-b.md"
    dest.write_text(
        "---\n"
        "id: proposition:a-affects-b\n"
        "kind: proposition\n"
        "title: A affects B\n"
        "status: active\n"
        "subject: concept:a-refined\n"
        "object: concept:b-refined\n"
        "predicate: affects\n"
        "polarity: positive\n"
        "claim_layer: causal_effect\n"
        "reasoning_source: llm-synth:model-x:proposition-synthesize-v1\n"
        "source_refs:\n"
        "  - paper:earlier\n"
        "created: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n"
        "\n"
        "CURATED BODY\n",
        encoding="utf-8",
    )

    report = apply_candidates(
        [_mint_candidate()],
        sidecar_path=_sidecar(root, claim="A affects B"),
        project_root=root,
        paper_ref="paper:new",
        as_of=date(2026, 7, 31),
    )

    text = dest.read_text(encoding="utf-8")
    assert "predicate: affects" in text
    assert "polarity: positive" in text
    assert "claim_layer: causal_effect" in text
    assert "reasoning_source: llm-synth:model-x:proposition-synthesize-v1" in text
    assert "CURATED BODY" in text
    # Provenance ACCRUES; it is not replaced with only the current paper's refs.
    assert "paper:earlier" in text and "paper:new" in text
    # BOTH subject and object refinements owned by synthesize survive the promotion's values.
    assert "subject: concept:a-refined" in text and "subject: concept:a\n" not in text
    assert "object: concept:b-refined" in text and "object: concept:b\n" not in text
    # Accounting: accrual counts as linked, not minted, and names no written path.
    assert report.minted == 0
    assert report.linked == 1
    assert report.written_paths == []


def _accruing_targets():
    """Targets whose proposition mint reports accrual, so each caller's non-created branch is
    exercised directly.

    The fake does NOT delegate to the real mint. Two reasons: the real mint would need an
    existing same-claim record to accrue onto, and creating that record makes `decide_all`
    classify the candidate as LINK -- so the MINT branch under test would never be reached.
    The subject here is the CALLER's branching on `MintOutcome.created`, not the mint itself;
    accrual behaviour proper is covered by the §5.3 and §5.8 tests above.
    """
    from science_tool.annotation.promote import MintOutcome, PromotionTarget, build_targets

    def accruing_mint(c, source_refs, project_root, as_of):
        return MintOutcome(entity_id=f"proposition:{c.slug}", created=False)

    return {**build_targets(), "proposition": PromotionTarget(
        kind="proposition", slug_addressed=True, mint=accruing_mint
    )}


def _write_existing_identical_claim(root: Path) -> Path:
    """The destination `_mint_candidate()` would mint onto, already holding the SAME claim."""
    dest = root / "entities" / "propositions" / "a-affects-b.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "---\n"
        "id: proposition:a-affects-b\n"
        "kind: proposition\n"
        "title: A affects B\n"
        "status: active\n"
        "source_refs:\n"
        "  - paper:earlier\n"
        "created: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n"
        "\n"
        "Existing body.\n",
        encoding="utf-8",
    )
    return dest


def _prose_project_for_mint(tmp_path: Path) -> Path:
    """A prose project whose unit u001 will be decided as MINT.

    Deliberately does NOT pre-write a matching proposition: `decide_all` classifies a claim
    matching an existing title as LINK, which would route around the MINT branch these tests
    exist to exercise. The injected target (`_accruing_targets`) is what makes that MINT report
    accrual, not the state of the entities directory.
    """
    from test_prose_promotion_batch import _persist_artifact

    _persist_artifact(tmp_path)
    return tmp_path


def test_apply_candidates_counts_accrual_as_linked(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation import promote

    root = _seed(tmp_path)
    _write_existing_identical_claim(root)
    report = promote.apply_candidates(
        [_mint_candidate()], sidecar_path=_sidecar(root), project_root=root,
        paper_ref="paper:new", as_of=date(2026, 7, 31), targets=_accruing_targets(),
    )
    assert (report.minted, report.linked, report.written_paths) == (0, 1, [])


def test_prose_promote_counts_accrual_as_linked(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation.prose_promote import promote_prose_unit

    monkeypatch.setattr(
        "science_tool.annotation.prose_promote.build_targets", _accruing_targets
    )
    root = _prose_project_for_mint(tmp_path)
    report = promote_prose_unit(root, "prose-source:example", "u001", apply=True)
    assert (report.minted, report.linked, report.written_paths) == (0, 1, [])


def test_prose_promotion_batch_counts_accrual_as_linked(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation.prose_promotion_batch import (
        apply_prose_promotion_plan,
        plan_prose_promotions,
    )

    monkeypatch.setattr(
        "science_tool.annotation.prose_promotion_batch.build_targets", _accruing_targets
    )
    root = _prose_project_for_mint(tmp_path)
    plan = plan_prose_promotions(root, "example", ["u001"])
    report = apply_prose_promotion_plan(root, plan)
    assert (report.minted, report.linked, report.written_paths) == (0, 1, [])


SKELETON_KEYS = ("datapackage", "local_path", "accessions", "siblings", "parent_dataset", "license")


def test_minted_proposition_carries_no_skeleton_keys(tmp_path: Path) -> None:
    """§5.4. `render_entity_text` full-dumps the model, which is what wrote `datapackage: ''`
    and `accessions: []` onto 391 evidence lines. Rendering from an allowlist is what stops it.
    """
    from science_tool.annotation.promote import apply_candidates

    root = _seed(tmp_path)
    apply_candidates(
        [_mint_candidate()], sidecar_path=_sidecar(root), project_root=root,
        paper_ref="paper:new", as_of=date(2026, 7, 31),
    )
    frontmatter = (root / "entities" / "propositions" / "a-affects-b.md").read_text(
        encoding="utf-8"
    ).split("---\n")[1]
    for key in SKELETON_KEYS:
        assert f"{key}:" not in frontmatter, f"skeleton key {key} leaked into a minted record"


def test_forced_mint_and_link_leave_the_same_state(tmp_path: Path) -> None:
    """§5.8: one behaviour, two routes to it -- file state AND report.

    Asserting only the file state would let the accounting diverge unnoticed, which is exactly
    the hole the unconditional `report.minted += 1` opened.
    """
    from science_tool.annotation.promote import PromotionCandidate, apply_candidates

    mint_root, link_root = _seed(tmp_path / "mint"), _seed(tmp_path / "link")
    mint_dest = _write_existing_identical_claim(mint_root)
    link_dest = _write_existing_identical_claim(link_root)

    link_candidate = PromotionCandidate(
        ref="annotation:papers/p.source#a-1", frag="a-1", claim="A affects B",
        subject="concept:a", object="concept:b", decision="LINK",
        slug="proposition:a-affects-b", reason="existing claim", kind="proposition",
    )

    mint_report = apply_candidates(
        [_mint_candidate()], sidecar_path=_sidecar(mint_root), project_root=mint_root,
        paper_ref="paper:new", as_of=date(2026, 7, 31),
    )
    link_report = apply_candidates(
        [link_candidate], sidecar_path=_sidecar(link_root), project_root=link_root,
        paper_ref="paper:new", as_of=date(2026, 7, 31),
    )

    assert mint_dest.read_text(encoding="utf-8") == link_dest.read_text(encoding="utf-8")
    assert (mint_report.minted, mint_report.linked) == (link_report.minted, link_report.linked)
    assert mint_report.written_paths == link_report.written_paths


def test_synthesize_ownership_is_derived_from_synth_fields() -> None:
    """Derived in code, not retyped: a hand-copied five-element tuple silently diverges the
    first time a field is added."""
    from science_tool.annotation.synthesize import SYNTH_FIELDS, SYNTHESIZE_PROPOSITION

    assert SYNTHESIZE_PROPOSITION.owned == set(SYNTH_FIELDS) | {"reasoning_source"}
    # An update-only writer claims no create-only keys.
    assert SYNTHESIZE_PROPOSITION.create_only == frozenset()


def test_synthesize_refuses_pre_containment_record(tmp_path: Path) -> None:
    """§5.6 + §6: a REJECTION, not a backfill. This slice repairs no existing records."""
    from science_tool.dag.entity_frontmatter import PersistedShapeError
    from science_tool.annotation.synthesize import _write_proposition

    root = _seed(tmp_path)
    dest = root / "entities" / "propositions" / "legacy.md"
    dest.write_text(
        "---\n"
        "id: proposition:legacy\n"
        "kind: proposition\n"
        "title: ''\n"                      # the 697-record defect
        "status: active\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "\n"
        "Body.\n",
        encoding="utf-8",
    )
    # subject/object/polarity are here only to satisfy PropositionEntity's own interlock
    # validator (predicate requires both operands; a sign-meaningful predicate requires a
    # sign). PropositionEntity.title is `str = ""`, so title alone would not stop construction
    # either way -- the point is that the entity CONSTRUCTS fine and the refusal comes from
    # certify_persisted, not from pydantic.
    merged = {"id": "proposition:legacy", "kind": "proposition", "title": "",
              "subject": "concept:a", "object": "concept:b", "predicate": "affects",
              "polarity": "unsigned",
              "reasoning_source": "llm-synth:m:proposition-synthesize-v1"}

    with pytest.raises(PersistedShapeError, match="legacy"):
        _write_proposition("proposition:legacy", merged, root, date(2026, 7, 31))
    assert "title: ''" in dest.read_text(encoding="utf-8")   # untouched
