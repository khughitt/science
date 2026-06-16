from datetime import date

import pytest
from science_tool.annotation.promote import (
    PromotionApplyError, PromotionCandidate, build_targets, numeric_target,
)


def _mint(kind, claim, project_root, slug="claim-slug"):
    c = PromotionCandidate(
        ref="annotation:papers/p#f1", frag="f1", claim=claim, subject="s", object="o",
        decision="MINT", slug=slug, reason="new entity", kind=kind,
    )
    target = numeric_target(kind)
    return target.mint(c, ["paper:p", c.ref], project_root, date(2026, 6, 16))


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


def test_mint_hypothesis_is_candidate_phase(tmp_path):
    eid = _mint("hypothesis", "Drug X inhibits pathway Y", tmp_path)
    assert eid.startswith("hypothesis:0001-")
    text = (tmp_path / "entities" / "hypotheses" / f"{eid.split(':', 1)[1]}.md").read_text()
    assert "status: proposed" in text
    assert "phase: candidate" in text
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


def test_mint_rollback_unlinks_placeholder_on_write_failure(tmp_path, monkeypatch):
    # Force the post-reservation write to fail; the reserved placeholder must be removed.
    import science_tool.annotation.promote as promote_mod

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(promote_mod, "_atomic_replace_text", boom)
    with pytest.raises(PromotionApplyError):
        _mint("question", "Doomed question?", tmp_path, slug="doomed-q")
    qdir = tmp_path / "entities" / "questions"
    # No orphaned NNNN-doomed-q.md left behind (rollback removed the placeholder).
    assert not any(p.name.endswith("-doomed-q.md") for p in qdir.glob("*.md"))


def test_build_targets_includes_numeric():
    targets = build_targets()
    assert targets["question"].slug_addressed is False
    assert targets["hypothesis"].slug_addressed is False
