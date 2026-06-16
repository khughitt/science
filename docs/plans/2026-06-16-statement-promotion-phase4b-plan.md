# Question/Hypothesis Promotion (Phase 4b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `science annotate promote` so `question`- and `hypothesis`-type statement annotations promote into `question`/`hypothesis` entities (mint-or-link), reusing the Phase-4a proposition spine via a small per-kind `PromotionTarget`.

**Architecture:** A shared, kind-agnostic spine (queue → decide → apply → provenance → idempotency → override) dispatches per-kind work to a frozen-dataclass `PromotionTarget` carrying a `mint` callable and a `slug_addressed` flag. `proposition_target()` is a behavior-neutral extraction of 4a's existing path (slug-addressed `write_entity_file` + never-overwrite guard). `numeric_target("question"|"hypothesis")` mints via atomic numeric reservation + a template-faithful `Renderer` render (claim in the lead section; hypothesis `phase: candidate`) with explicit post-reservation rollback. Dedup is strictly kind-local; duplicate normalized titles in a kind's corpus are a counted `promote-link-ambiguous` skip, never a silent collapse.

**Tech Stack:** Python 3, Pydantic models (`science_model`), Click CLI, `pytest`, `uv` workspace. Spec: `~/d/science/docs/plans/2026-06-16-statement-promotion-phase4b-design.md`.

**Working dir / commands:** All commands run from the worktree root
`~/d/science/.worktrees/sub-article-annotation-phase4b`. The Python package lives under
`science/`; run tests/type/lint via the uv workspace:
- Tests: `cd science && uv run --frozen pytest tests/<file>.py -q` (rely on **exit code 0**; the
  printed summary may not reach piped output).
- Types: `cd science && uv run --frozen pyright src/science_tool/annotation/promote.py`
- Lint: `cd science && uv run --frozen ruff check src/science_tool/annotation/promote.py`

(Bare `pyright`/`grep`/`rg` are shell-aliased and unreliable here — always use `uv run --frozen …`.)

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/annotation/promote.py` | Decision core, targets, mint, apply, override | Heavily extended |
| `science/src/science_tool/annotation/cli.py` | `promote_cmd` — widen to 3 kinds, per-kind override | Modified (one command) |
| `science/tests/test_annotation_promote.py` | Decision/queue/mint/corpus units | Extended + a few 4a constructions updated |
| `science/tests/test_annotate_promote_cli.py` | Proposition CLI round-trip | Regression gate (unchanged) |
| `science/tests/test_promote_numeric_mint.py` | Numeric mint + reservation + rollback units | **Create** |
| `science/tests/test_promote_qh_integration.py` | q/h promote end-to-end (disk + provenance + idempotency) | **Create** |
| `docs/conventions/annotation-tokens.md` | Promotion vocab | Append a 4b note |

**Reused as-is (do not modify):** `science_tool.entity_reservation.reserve_entity`,
`science_model.templates.Renderer`, `science_tool.entities.{slug_for_claim_text,
append_entity_source_ref, write_entity_file, resolve_path_policy, default_status,
_atomic_replace_text, _parse_markdown_file}`, the `graph/materialize` `annotation:` bypass,
`graph/migrate.py` audit skip, and the `sci:promotedTo` io round-trip — all already kind-agnostic.

**Behavior-neutrality contract:** Tasks 1–2 keep proposition promotion identical. The full
pre-existing proposition suite (`test_annotation_promote.py` proposition cases +
`test_annotate_promote_cli.py`) is a **regression gate** at every task. Tasks 4+ intentionally
*widen* the queue (question/hypothesis become promotable) — that is new behavior, not a
regression, and the one queue test asserting the old skip is updated to the new behavior.

---

### Task 1: Generalize the decision core (kind tag, ambiguity, slug-addressing) — behavior-neutral

Add a `kind` tag to the decision dataclasses (defaulting to `proposition` so every existing
construction is unchanged), an `ambiguous_titles` set to the corpus, and a `slug_addressed`
switch + ambiguity branch to `decide_candidates`. Proposition behavior is identical; the new
branches only fire on inputs 4a never constructs.

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py` (dataclasses + `decide_candidates` + `_cand`)
- Test: `science/tests/test_annotation_promote.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_annotation_promote.py`. Update the existing `_corpus` helper to
accept `ambiguous` and add two new tests:

```python
def _corpus(titles_to_slug=None, slugs=None, derived=None, ambiguous=None):
    return PromotionCorpus(
        title_to_ref={normalize_claim(t): s for t, s in (titles_to_slug or {}).items()},
        existing_slugs=set(slugs or []),
        derived_refs=set(derived or []),
        ambiguous_titles={normalize_claim(t) for t in (ambiguous or [])},
    )


def test_ambiguous_title_skips_not_links():
    # Corpus already holds two same-kind entities with the same normalized title.
    p = Promotable(ref="annotation:a#f1", frag="f1", claim="Shared claim text", subject=None, object=None)
    corp = _corpus(titles_to_slug={"Shared claim text": "proposition:shared-claim-text"},
                   ambiguous=["Shared claim text"])
    [c] = decide_candidates([p], corp)
    assert c.decision == "SKIP" and c.reason == "promote-link-ambiguous"


def test_numeric_kind_never_collides():
    # slug_addressed=False: an occupied slug does NOT become a COLLISION (numeric reserves a number).
    p = Promotable(kind="question", ref="annotation:a#f1", frag="f1",
                   claim="Alpha beta", subject=None, object=None)
    corp = _corpus(slugs={"alpha-beta"})
    [c] = decide_candidates([p], corp, slug_addressed=False)
    assert c.decision == "MINT" and c.slug == "alpha-beta" and c.kind == "question"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -k "ambiguous_title or numeric_kind_never" -q`
Expected: FAIL — `PromotionCorpus` has no `ambiguous_titles` field; `Promotable` has no `kind`;
`decide_candidates` has no `slug_addressed` parameter.

- [ ] **Step 3: Add the `kind` tag, `ambiguous_titles`, and `slug_addressed` branch**

In `promote.py`, edit the three dataclasses and `decide_candidates`/`_cand`:

```python
@dataclass(frozen=True)
class Promotable:
    ref: str            # "annotation:<relpath>#<frag>"
    frag: str           # annotation id within its sidecar
    claim: str          # the TextQuoteSelector exact span
    subject: str | None
    object: str | None
    kind: str = "proposition"   # promotable kind: proposition | question | hypothesis


@dataclass(frozen=True)
class PromotionCorpus:
    title_to_ref: dict[str, str]      # normalize_claim(title) -> "<kind>:<local_part>" (first-wins)
    existing_slugs: set[str]          # bare local-parts of existing entities of this kind
    derived_refs: set[str]            # annotation: refs already in some entity's source_refs (global)
    ambiguous_titles: set[str] = field(default_factory=set)  # normalized titles held by >=2 entities


@dataclass(frozen=True)
class PromotionCandidate:
    ref: str
    frag: str
    claim: str
    subject: str | None
    object: str | None
    decision: str           # MINT | LINK | COLLISION | SKIP
    slug: str | None        # MINT: new bare local-part; LINK: "<kind>:<local_part>"; else None
    reason: str             # short explanation / skip reason
    kind: str = "proposition"


def decide_candidates(
    promotables: list[Promotable],
    corpus: PromotionCorpus,
    *,
    slug_addressed: bool = True,
) -> list[PromotionCandidate]:
    """Pure mint-or-link-or-collision decision for one kind's promotables.

    `slug_addressed` True (proposition) keeps the 4a slug-collision detection; False
    (numeric question/hypothesis) skips it — numeric reservation cannot collide.
    """
    out: list[PromotionCandidate] = []
    minted_slugs: set[str] = set()
    for p in promotables:
        key = normalize_claim(p.claim)
        if key in corpus.ambiguous_titles:
            out.append(_cand(p, "SKIP", None, "promote-link-ambiguous"))
            continue
        existing = corpus.title_to_ref.get(key)
        if existing is not None:
            out.append(_cand(p, "LINK", existing, "normalized claim equals existing entity title"))
            continue
        try:
            slug = slug_for_claim_text(p.claim)
        except EntityCommandError:
            out.append(_cand(p, "SKIP", None, "promote-claim-unsluggable"))
            continue
        if slug_addressed:
            if slug in corpus.existing_slugs:
                out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))
                continue
            if slug in minted_slugs:
                out.append(_cand(p, "COLLISION", slug, "promote-slug-collision"))
                continue
            minted_slugs.add(slug)
        out.append(_cand(p, "MINT", slug, "new entity"))
    return out


def _cand(p: Promotable, decision: str, slug: str | None, reason: str) -> PromotionCandidate:
    return PromotionCandidate(
        ref=p.ref, frag=p.frag, claim=p.claim, subject=p.subject, object=p.object,
        decision=decision, slug=slug, reason=reason, kind=p.kind,
    )
```

- [ ] **Step 4: Run the full decision-unit suite to verify pass + no regression**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -q`
Expected: PASS (the two new tests + every pre-existing decision test — `test_novel_claim_mints`,
`test_identical_title_links`, `test_slug_collision_against_corpus`, `test_intra_batch_collision`,
etc. — unchanged behavior).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): kind-tag candidates + slug_addressed + ambiguity skip (behavior-neutral)"
```

---

### Task 2: Introduce `PromotionTarget` + `proposition_target()` + `entity_dest`; dispatch apply by target — behavior-neutral

Factor the per-kind mint behind a frozen dataclass; extract 4a's proposition mint into
`proposition_target().mint`; route `apply_candidates`' MINT/LINK through a `targets` registry
and a shared `entity_dest` path helper. Proposition apply is byte-for-byte identical.

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py`
- Test: `science/tests/test_annotation_promote.py`

- [ ] **Step 1: Write the failing test**

```python
def test_proposition_target_is_default_and_slug_addressed():
    from science_tool.annotation.promote import PROMOTABLE_KINDS, build_targets
    targets = build_targets()
    assert set(PROMOTABLE_KINDS) == {"proposition", "question", "hypothesis"}
    assert targets["proposition"].slug_addressed is True
    assert callable(targets["proposition"].mint)


def test_entity_dest_resolves_by_kind(tmp_path):
    from science_tool.annotation.promote import entity_dest
    # proposition (slug strategy) and question (numeric) resolve under their homes.
    assert entity_dest("proposition:foo-bar", tmp_path).name == "foo-bar.md"
    assert entity_dest("proposition:foo-bar", tmp_path).parent.name == "propositions"
    assert entity_dest("question:0007-foo", tmp_path).name == "0007-foo.md"
    assert entity_dest("question:0007-foo", tmp_path).parent.name == "questions"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -k "proposition_target_is_default or entity_dest_resolves" -q`
Expected: FAIL — `build_targets`, `PromotionTarget`, `entity_dest` do not exist.

- [ ] **Step 3: Add `PromotionTarget`, `entity_dest`, `proposition_target`, `build_targets`, and refactor `apply_candidates`**

Add imports at the top of `promote.py` (extend the existing `from science_tool.entities import (...)`
block to include `default_status`):

```python
from collections.abc import Callable
```

Add the target machinery (after `normalize_claim` / dataclasses, before `apply_candidates`):

```python
PROMOTABLE_KINDS: tuple[str, ...] = ("proposition", "question", "hypothesis")

# (candidate, source_refs, project_root, as_of) -> minted entity id "<kind>:<local_part>"
MintFn = Callable[["PromotionCandidate", list[str], Path, "date | None"], str]


@dataclass(frozen=True)
class PromotionTarget:
    kind: str
    slug_addressed: bool   # proposition True (content-addressed slug); numeric kinds False
    mint: MintFn


def entity_dest(entity_id: str, project_root: Path) -> Path:
    """Canonical file path for `<kind>:<local_part>` (works for slug + numeric kinds)."""
    kind, local_part = entity_id.split(":", 1)
    policy = resolve_path_policy(kind, project_root=project_root)
    return project_root / policy.root / f"{local_part}.md"


def _mint_proposition(
    c: PromotionCandidate, source_refs: list[str], project_root: Path, as_of: date | None
) -> str:
    """4a proposition mint: slug-addressed write_entity_file + never-overwrite guard."""
    assert c.slug is not None
    prop_ref = f"proposition:{c.slug}"
    dest = entity_dest(prop_ref, project_root)
    if dest.exists():
        existing_fm, _ = _parse_markdown_file(dest)
        if normalize_claim(str(existing_fm.get("title") or "")) != normalize_claim(c.claim):
            raise PromotionApplyError(
                f"refusing to overwrite {dest.name}: it holds a different proposition"
            )
    prop = PropositionEntity(
        id=prop_ref, title=c.claim, subject=c.subject, object=c.object,
        source_refs=list(source_refs),
    )
    write_entity_file(prop, project_root=project_root, body=_proposition_body(c.claim), as_of=as_of)
    return prop_ref


def proposition_target() -> PromotionTarget:
    return PromotionTarget(kind="proposition", slug_addressed=True, mint=_mint_proposition)


def build_targets() -> dict[str, PromotionTarget]:
    # numeric_target is added in Task 3; until then question/hypothesis raise on mint.
    return {"proposition": proposition_target()}
```

Refactor `apply_candidates` to dispatch MINT/LINK through `entity_dest` + the target registry
(the sidecar-backlink block at the end is unchanged):

```python
def apply_candidates(
    candidates: list[PromotionCandidate],
    *,
    sidecar_path: Path,
    project_root: Path,
    paper_ref: str,
    as_of: date | None = None,
    targets: dict[str, PromotionTarget] | None = None,
) -> ApplyReport:
    """Execute MINT/LINK candidates: mint via the per-kind target, accrue provenance, backlink."""
    targets = targets if targets is not None else build_targets()
    report = ApplyReport()
    backlinks: dict[str, str] = {}  # frag -> "<kind>:<local_part>"

    for c in candidates:
        if c.decision == "MINT":
            new_id = targets[c.kind].mint(c, [paper_ref, c.ref], project_root, as_of)
            report.written_paths.append(str(entity_dest(new_id, project_root)))
            report.minted += 1
            backlinks[c.frag] = new_id
        elif c.decision == "LINK":
            assert c.slug is not None  # "<kind>:<local_part>"
            dest = entity_dest(c.slug, project_root)
            for ref in (paper_ref, c.ref):
                append_entity_source_ref(dest, ref, as_of=as_of)
            report.linked += 1
            backlinks[c.frag] = c.slug
        else:  # COLLISION / SKIP — not applied
            report.skipped[c.reason] += 1

    if backlinks:
        sidecar = read_sidecar_strict(sidecar_path)
        new_anns = tuple(
            dataclasses.replace(a, promoted_to=backlinks[a.id]) if a.id in backlinks else a
            for a in sidecar.annotations
        )
        anno_io.write_sidecar(sidecar_path, dataclasses.replace(sidecar, annotations=new_anns))
    return report
```

Add `default_status` to the existing `from science_tool.entities import (...)` import list (it
is used in Task 3 but importing now keeps the block stable).

- [ ] **Step 4: Run to verify pass + proposition apply regression green**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py tests/test_annotate_promote_cli.py -q`
Expected: PASS — the two new tests plus every pre-existing apply/CLI test (proposition mint, link,
collision, idempotency, provenance) unchanged.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): PromotionTarget + proposition_target extraction + apply dispatch (behavior-neutral)"
```

---

### Task 3: Numeric mint + `numeric_target()` (template-faithful, phase=candidate, lead-section, rollback)

Add the numeric-kind mint: preflight template → reserve number → render template-faithful with
the real id → insert the claim into the lead section → atomic write, with explicit
post-reservation rollback. Wire question/hypothesis into `build_targets`.

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py`
- Test: `science/tests/test_promote_numeric_mint.py` (**create**)

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_promote_numeric_mint.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_promote_numeric_mint.py -q`
Expected: FAIL — `numeric_target` does not exist; `build_targets()` has no question/hypothesis.

- [ ] **Step 3: Implement numeric mint and wire it into `build_targets`**

Add imports near the top of `promote.py`:

```python
from science_model.templates import Renderer
from science_tool.entities import _atomic_replace_text  # canonical atomic writer (also used by 4a path)
from science_tool.entity_reservation import reserve_entity
```

(Add `_atomic_replace_text` to the existing `from science_tool.entities import (...)` block
rather than a second import line; shown separately here for clarity.)

Add the numeric mint + factory (after `proposition_target`, before `build_targets`):

```python
_LEAD_SECTION: dict[str, str] = {
    "question": "Summary",
    "hypothesis": "Organizing Conjecture",
}


def _insert_claim_into_lead(rendered: str, section_name: str, claim: str) -> str:
    """Insert the verbatim claim as the first body line under `## {section_name}`."""
    marker = f"## {section_name}\n"
    idx = rendered.find(marker)
    if idx == -1:
        raise PromotionApplyError(f"rendered template missing lead section '## {section_name}'")
    at = idx + len(marker)
    return f"{rendered[:at]}\n{claim}\n{rendered[at:]}"


def _mint_numeric(kind: str) -> MintFn:
    lead = _LEAD_SECTION[kind]

    def mint(c: PromotionCandidate, source_refs: list[str], project_root: Path, as_of: date | None) -> str:
        assert c.slug is not None
        today = (as_of or date.today()).isoformat()
        # (1) Preflight the template (pure read, no number consumed). Raises EntityTemplateError
        #     if the packaged template is missing/malformed — a loud environment error.
        renderer = Renderer()
        renderer.sections(kind)
        # (2) Reserve the number atomically (empty placeholder .md backs the claimed number).
        reservation = reserve_entity(project_root, kind, title=c.claim, slug=c.slug)
        try:
            # (3) Render template-faithful with the real id, then insert the claim into the lead.
            fields: dict[str, object] = {
                "entity_id": reservation.entity_id,
                "title": c.claim,
                "status": default_status(kind),
                "source_refs": list(source_refs),
                "related": [],
                "created": today,
                "updated": today,
            }
            if kind == "hypothesis":
                fields["phase"] = "candidate"
            rendered = renderer.render(kind, fields=fields)
            rendered = _insert_claim_into_lead(rendered, lead, c.claim)
            # (4) Final write — overwrites the empty placeholder. Last step.
            _atomic_replace_text(reservation.path, rendered)
        except Exception as exc:  # explicit post-reservation rollback, then fail loud
            reservation.path.unlink(missing_ok=True)
            if isinstance(exc, PromotionApplyError):
                raise
            raise PromotionApplyError(
                f"failed to write {kind} {reservation.entity_id}: {exc}"
            ) from exc
        return reservation.entity_id

    return mint


def numeric_target(kind: str) -> PromotionTarget:
    if kind not in ("question", "hypothesis"):
        raise ValueError(f"numeric_target supports question/hypothesis, got {kind!r}")
    return PromotionTarget(kind=kind, slug_addressed=False, mint=_mint_numeric(kind))
```

Update `build_targets`:

```python
def build_targets() -> dict[str, PromotionTarget]:
    return {
        "proposition": proposition_target(),
        "question": numeric_target("question"),
        "hypothesis": numeric_target("hypothesis"),
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_promote_numeric_mint.py -q`
Expected: PASS (all five tests — template-faithful question, candidate-phase hypothesis,
next-number, rollback, registry).

- [ ] **Step 5: Type-check and commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b/science && uv run --frozen pyright src/science_tool/annotation/promote.py
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add science/src/science_tool/annotation/promote.py science/tests/test_promote_numeric_mint.py
git commit -m "feat(promote): numeric template-faithful mint + numeric_target (phase=candidate, rollback)"
```

---

### Task 4: Widen `collect_promotable` to all promotable kinds; rename the skip reason

The queue now admits `proposition`/`question`/`hypothesis` (tagging each with its kind) and
skips everything else as `promote-non-promotable-type`. This **changes** the queue's behavior
by design (question/hypothesis are no longer skipped), so the one pre-existing queue test is
updated to the new behavior.

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py` (`collect_promotable`)
- Test: `science/tests/test_annotation_promote.py` (update `test_promotable_filters_queue`)

- [ ] **Step 1: Update the queue test to the new behavior (it now fails)**

Replace `test_promotable_filters_queue` in `science/tests/test_annotation_promote.py` with:

```python
def test_promotable_filters_queue(tmp_path):
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Status
    from science_tool.annotation.promote import collect_promotable

    md = tmp_path / "paper.md"
    md.write_text("x\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anns = (
        _statement_ann("a-1", "Open proposition claim", status=Status.OPEN, subject="cells"),
        _statement_ann("a-2", "Already promoted", status=Status.OPEN, promoted_to="proposition:x"),
        _statement_ann("a-3", "A question", status=Status.OPEN, atype="question"),
        _statement_ann("a-5", "A hypothesis", status=Status.OPEN, atype="hypothesis"),
        _statement_ann("a-6", "A metaphor", status=Status.OPEN, atype="metaphor"),
        _statement_ann("a-4", "Dismissed claim", status=Status.DISMISSED),
    )
    sidecar = anno_io.Sidecar(annotations=anns)

    promotable, skipped = collect_promotable(sidecar, sidecar_path, tmp_path, derived_refs=set())
    # proposition + question + hypothesis are now all promotable, tagged with their kind.
    assert [(p.frag, p.kind) for p in promotable] == [
        ("a-1", "proposition"), ("a-3", "question"), ("a-5", "hypothesis"),
    ]
    assert skipped["promote-already-promoted"] == 1
    assert skipped["promote-non-promotable-type"] == 1   # the metaphor
    assert skipped["promote-inactive-status"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -k promotable_filters_queue -q`
Expected: FAIL — current `collect_promotable` skips question/hypothesis as
`promote-not-proposition-type` and does not tag `kind`.

- [ ] **Step 3: Widen `collect_promotable`**

Replace the kind gate and `Promotable` construction in `collect_promotable`:

```python
def collect_promotable(sidecar, sidecar_path: Path, root: Path, *, derived_refs: set[str]) -> tuple[list[Promotable], Counter]:
    """Filter a sidecar to the promotable statement queue (all promotable kinds), counting skips."""
    out: list[Promotable] = []
    skipped: Counter = Counter()
    for ann in sidecar.annotations:
        if ann.annotation_type not in PROMOTABLE_KINDS:
            skipped["promote-non-promotable-type"] += 1
            continue
        if ann.status not in (Status.OPEN, Status.ACK):
            skipped["promote-inactive-status"] += 1
            continue
        ref = _annotation_ref(sidecar_path, root, ann.id)
        if ann.promoted_to is not None or ref in derived_refs:
            skipped["promote-already-promoted"] += 1
            continue
        subject, object_ = _statement_subject_object(ann)
        out.append(Promotable(
            kind=ann.annotation_type, ref=ref, frag=ann.id,
            claim=ann.target.selector.exact, subject=subject, object=object_,
        ))
    return out, skipped
```

(`_statement_subject_object` is unchanged: every statement kind carries the JSON body, so
subject/object resolve to their values or `None`; a missing body is still a hard
`PromotionReadError`.)

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -q`
Expected: PASS (updated queue test + all decision units).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): widen queue to question/hypothesis; rename skip -> promote-non-promotable-type"
```

---

### Task 5: Per-kind corpora + global derived-refs (`load_corpora`)

Replace the proposition-only `load_corpus` with `load_corpora`, which builds one
`PromotionCorpus` per promotable kind (title index first-wins, ambiguous-title set, slug set)
plus a single global `derived_refs` set (annotation refs already carried by *any* promoted
entity — kind-independent idempotency).

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py` (replace `load_corpus`)
- Test: `science/tests/test_annotation_promote.py`

- [ ] **Step 1: Write the failing test**

```python
def test_load_corpora_indexes_each_kind(tmp_path):
    from science_tool.annotation.promote import PROMOTABLE_KINDS, load_corpora

    # Two questions sharing a normalized title -> ambiguous; one hypothesis; one proposition.
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "hypotheses").mkdir(parents=True)
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    q1 = "---\nid: \"question:0001-dup\"\ntype: question\ntitle: \"Same question\"\nstatus: active\n---\n# Same question\n"
    q2 = "---\nid: \"question:0002-dup\"\ntype: question\ntitle: \"same QUESTION\"\nstatus: active\n---\n# same QUESTION\n"
    (tmp_path / "entities" / "questions" / "0001-dup.md").write_text(q1, encoding="utf-8")
    (tmp_path / "entities" / "questions" / "0002-dup.md").write_text(q2, encoding="utf-8")
    hyp = ("---\nid: \"hypothesis:0001-h\"\ntype: hypothesis\ntitle: \"A hypothesis\"\nstatus: proposed\n"
           "source_refs: [\"annotation:papers/p#fx\"]\n---\n# A hypothesis\n")
    (tmp_path / "entities" / "hypotheses" / "0001-h.md").write_text(hyp, encoding="utf-8")
    prop = "---\nid: \"proposition:a-claim\"\ntype: proposition\ntitle: \"A claim\"\nstatus: draft\n---\n# A claim\n"
    (tmp_path / "entities" / "propositions" / "a-claim.md").write_text(prop, encoding="utf-8")

    corpora, derived = load_corpora(tmp_path)
    assert set(corpora) == set(PROMOTABLE_KINDS)
    assert normalize_claim("Same question") in corpora["question"].ambiguous_titles
    assert corpora["hypothesis"].title_to_ref[normalize_claim("A hypothesis")] == "hypothesis:0001-h"
    assert "0001-h" in corpora["hypothesis"].existing_slugs
    # derived_refs are global (annotation ref from the hypothesis is visible kind-independently).
    assert "annotation:papers/p#fx" in derived
    assert "annotation:papers/p#fx" in corpora["question"].derived_refs
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -k load_corpora_indexes -q`
Expected: FAIL — `load_corpora` does not exist.

- [ ] **Step 3: Replace `load_corpus` with `load_corpora`**

Remove the existing `load_corpus` function and add:

```python
def load_corpora(project_root: Path) -> tuple[dict[str, PromotionCorpus], set[str]]:
    """Build a per-kind corpus for every promotable kind + a single global derived-refs set.

    `derived_refs` (annotation refs already in some entity's source_refs) is global: an
    annotation is "already promoted" if ANY entity carries its ref, independent of kind.
    """
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root.resolve())
    title_first: dict[str, dict[str, str]] = {k: {} for k in PROMOTABLE_KINDS}
    title_seen: dict[str, set[str]] = {k: set() for k in PROMOTABLE_KINDS}
    ambiguous: dict[str, set[str]] = {k: set() for k in PROMOTABLE_KINDS}
    slugs: dict[str, set[str]] = {k: set() for k in PROMOTABLE_KINDS}
    derived: set[str] = set()
    for entity in sources.entities:
        kind = entity.kind
        if kind in PROMOTABLE_KINDS:
            ref = entity.canonical_id  # "<kind>:<local_part>"
            slugs[kind].add(ref.split(":", 1)[1])
            title = (entity.title or "").strip()
            if title:
                key = normalize_claim(title)
                if key in title_seen[kind]:
                    ambiguous[kind].add(key)
                else:
                    title_seen[kind].add(key)
                    title_first[kind][key] = ref
        for sref in entity.source_refs:
            if isinstance(sref, str) and sref.startswith("annotation:"):
                derived.add(sref)
    corpora = {
        k: PromotionCorpus(
            title_to_ref=title_first[k], existing_slugs=slugs[k],
            derived_refs=derived, ambiguous_titles=ambiguous[k],
        )
        for k in PROMOTABLE_KINDS
    }
    return corpora, derived
```

- [ ] **Step 4: Migrate the three proposition apply-tests off the removed `load_corpus`**

`load_corpus` is gone, so the three pre-existing proposition tests that import it
(`test_apply_mints_proposition_and_backlinks`, `test_apply_links_to_existing_appends_both_refs_preserves_prose`,
`test_apply_is_idempotent`) must be repointed to `load_corpora` + `decide_all` — a mechanical
swap that preserves every assertion (proposition behavior is unchanged). In each test:

- change the import line `apply_candidates, collect_promotable, decide_candidates, load_corpus,`
  → `apply_candidates, build_targets, collect_promotable, decide_all, load_corpora,`
- replace `corpus = load_corpus(tmp_path)` →
  `corpora, derived = load_corpora(tmp_path)`
- replace `collect_promotable(..., derived_refs=corpus.derived_refs)` →
  `collect_promotable(..., derived_refs=derived)`
- replace `decide_candidates(promotable, corpus)` →
  `decide_all(promotable, corpora, build_targets())`

For `test_apply_is_idempotent`, the same swap inside its local `run()`:

```python
    def run():
        corpora, derived = load_corpora(tmp_path)
        pr, _ = collect_promotable(read_sidecar_strict(sp), sp, tmp_path, derived_refs=derived)
        return apply_candidates(decide_all(pr, corpora, build_targets()), sidecar_path=sp,
                                project_root=tmp_path, paper_ref="paper:p", as_of=date(2026, 6, 16))
```

(These tests still assert identical proposition outcomes — mint at `cells-divide-rapidly.md`,
link appends both refs + preserves prose, second run mints 0 — so they remain the proposition
regression gate, now exercised through the generalized loader/orchestrator.)

- [ ] **Step 5: Run to verify pass + no other unit regressed**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -q`
Expected: PASS (the `load_corpora` unit + the three migrated proposition apply-tests + all
decision units). A leftover `load_corpus` import anywhere → `ImportError` here.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add science/src/science_tool/annotation/promote.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): load_corpora (per-kind index + global derived-refs); migrate proposition tests"
```

---

### Task 6: Orchestration (`decide_all`) + per-kind override; rewrite `promote_cmd`

Add `decide_all` (group by kind, decide with each target's `slug_addressed`, preserve sidecar
order); generalize `apply_overrides` to enforce **same-kind** LINK targets and strip any
`<kind>:` prefix on MINT; rewrite `promote_cmd` to use `load_corpora` + `decide_all` and a
union all-kind `existing_refs`.

**Files:**
- Modify: `science/src/science_tool/annotation/promote.py` (`decide_all`, `apply_overrides`)
- Modify: `science/src/science_tool/annotation/cli.py` (`promote_cmd`)
- Test: `science/tests/test_annotation_promote.py`, `science/tests/test_annotate_promote_cli.py`

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_annotation_promote.py`:

```python
def test_decide_all_preserves_order_and_kind_local_dedup():
    from science_tool.annotation.promote import build_targets, decide_all
    promotables = [
        Promotable(kind="question", ref="annotation:a#q", frag="q", claim="Shared text", subject=None, object=None),
        Promotable(kind="proposition", ref="annotation:a#p", frag="p", claim="Shared text", subject=None, object=None),
    ]
    corpora = {
        "question": _corpus(titles_to_slug={"Shared text": "question:0001-shared-text"}),
        "hypothesis": _corpus(),
        "proposition": _corpus(),  # proposition corpus does NOT contain "Shared text"
    }
    out = decide_all(promotables, corpora, build_targets())
    # order preserved; question LINKs (its corpus has the title), proposition MINTs (its does not)
    assert [c.frag for c in out] == ["q", "p"]
    assert out[0].decision == "LINK" and out[0].slug == "question:0001-shared-text"
    assert out[1].decision == "MINT" and out[1].kind == "proposition"


def test_override_link_must_be_same_kind():
    from science_tool.annotation.promote import apply_overrides
    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="Q text", subject=None,
                               object=None, decision="MINT", slug="q-text", reason="new entity",
                               kind="question")]
    rows = [{"annotation": "annotation:a#f1", "decision": "LINK", "slug": "proposition:q-text"}]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(base, rows, existing_refs={"proposition:q-text", "question:0001-q-text"})


def test_override_numeric_mint_slug_strips_kind_prefix():
    from science_tool.annotation.promote import apply_overrides
    base = [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="Q text", subject=None,
                               object=None, decision="MINT", slug="q-text", reason="new entity",
                               kind="question")]
    rows = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "question:better-slug"}]
    [c] = apply_overrides(base, rows, existing_refs=set())
    assert c.decision == "MINT" and c.slug == "better-slug" and c.kind == "question"


def _q_mint_base():
    return [PromotionCandidate(ref="annotation:a#f1", frag="f1", claim="Q text", subject=None,
                               object=None, decision="MINT", slug="q-text", reason="new entity",
                               kind="question")]


def test_override_mint_wrong_kind_prefix_fails():
    from science_tool.annotation.promote import apply_overrides
    rows = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "hypothesis:foo"}]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(_q_mint_base(), rows, existing_refs=set())


def test_override_mint_invalid_slug_fails():
    # A slug that can't pass validate_slug must fail as a clean PromotionOverrideError,
    # not leak EntityCommandError from reserve_entity at apply time.
    from science_tool.annotation.promote import apply_overrides
    rows = [{"annotation": "annotation:a#f1", "decision": "MINT", "slug": "Not A Slug!"}]
    with pytest.raises(PromotionOverrideError):
        apply_overrides(_q_mint_base(), rows, existing_refs=set())
```

Also add to the import at the top of the test file:
`from science_tool.annotation.promote import PromotionCandidate, PromotionOverrideError` (extend
the existing import).

- [ ] **Step 2: Run to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py -k "decide_all or override_" -q`
Expected: FAIL — `decide_all` missing; `apply_overrides` lacks same-kind/kind-prefix/slug-validation handling.

- [ ] **Step 3: Add `decide_all` and generalize `apply_overrides`**

Add `decide_all` (after `decide_candidates`):

```python
def decide_all(
    promotables: list[Promotable],
    corpora: dict[str, PromotionCorpus],
    targets: dict[str, PromotionTarget],
) -> list[PromotionCandidate]:
    """Decide every promotable, grouped by kind (for intra-batch collision), order preserved."""
    groups: dict[str, list[tuple[int, Promotable]]] = {}
    for i, p in enumerate(promotables):
        groups.setdefault(p.kind, []).append((i, p))
    results: dict[int, PromotionCandidate] = {}
    for kind, group in groups.items():
        cands = decide_candidates(
            [p for _, p in group], corpora[kind], slug_addressed=targets[kind].slug_addressed
        )
        for (i, _), c in zip(group, cands):
            results[i] = c
    return [results[i] for i in range(len(promotables))]
```

Generalize the LINK/MINT branches of `apply_overrides` (the `decision == "LINK"` and
`decision == "MINT"` arms):

```python
        if decision == "LINK":
            if not slug or slug not in existing_refs:
                raise PromotionOverrideError(f"LINK target {slug!r} is not an existing entity")
            if slug.split(":", 1)[0] != c.kind:
                raise PromotionOverrideError(
                    f"LINK target {slug!r} is not a {c.kind} (kind-local dedup)"
                )
            out.append(dataclasses.replace(c, decision="LINK", slug=slug, reason="curator override: link"))
        elif decision == "MINT":
            bare = slug
            if isinstance(slug, str) and ":" in slug:
                pfx, rest = slug.split(":", 1)
                if pfx != c.kind:
                    raise PromotionOverrideError(
                        f"MINT override slug {slug!r} has the wrong kind prefix for a {c.kind}"
                    )
                bare = rest
            if not bare:
                raise PromotionOverrideError(f"MINT override for {c.ref!r} requires a slug")
            # Validate eagerly here so a bad curator slug fails as a clean ClickException,
            # not an uncaught EntityCommandError from reserve_entity(..., slug=...) at apply time.
            try:
                validate_slug(bare)
            except EntityCommandError as exc:
                raise PromotionOverrideError(f"MINT override slug {bare!r} is invalid: {exc}") from exc
            out.append(dataclasses.replace(c, decision="MINT", slug=bare, reason="curator override: mint"))
```

Add `validate_slug` to the existing `from science_tool.entities import (...)` block at the top of
`promote.py` (`EntityCommandError` is already imported).

- [ ] **Step 4: Rewrite `promote_cmd` to use the orchestration**

In `science/src/science_tool/annotation/cli.py`, update the import block and body of
`promote_cmd`. Replace the `from science_tool.annotation.promote import (...)` import with:

```python
    from science_tool.annotation.promote import (
        PromotionApplyError, PromotionOverrideError, PromotionReadError, apply_candidates,
        apply_overrides, build_targets, collect_promotable, decide_all, load_corpora,
    )
```

Replace the corpus/decision/override section (the lines from `corpus = load_corpus(project_root)`
through the `apply_overrides(...)` block) with:

```python
    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar_strict(sidecar_path)
    corpora, derived_refs = load_corpora(project_root)
    targets = build_targets()
    try:
        promotable, skipped = collect_promotable(sidecar, sidecar_path, project_root, derived_refs=derived_refs)
    except PromotionReadError as exc:
        raise click.ClickException(str(exc)) from exc
    candidates = decide_all(promotable, corpora, targets)

    if do_apply and input_path is not None:
        try:
            raw = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
        edited_rows = raw.get("candidates") if isinstance(raw, dict) else raw
        if not isinstance(edited_rows, list):
            raise click.ClickException("--input must be the read-only output object or a candidates list")
        existing_refs = {
            f"{kind}:{slug}" for kind, corp in corpora.items() for slug in corp.existing_slugs
        }
        try:
            candidates = apply_overrides(candidates, edited_rows, existing_refs=existing_refs)
        except PromotionOverrideError as exc:
            raise click.ClickException(str(exc)) from exc
```

Add `kind` to the emitted candidate rows (so the curator can see/keep it) — update the `rows`
list comprehension:

```python
    rows = [{"annotation": c.ref, "kind": c.kind, "decision": c.decision, "slug": c.slug,
             "claim": c.claim[:80], "reason": c.reason} for c in candidates]
```

The `apply_candidates(...)` call is unchanged (it already builds `build_targets()` internally
when `targets` is omitted). Update its table-mode line to show the kind:

```python
            for r in rows:
                click.echo(f"{r['kind']:11} {r['decision']:9} {r['slug'] or '-':40} {r['annotation']}  {r['claim']}")
```

Also remove the now-unused `load_corpus` reference in the docstring; change the `promote_cmd`
docstring first line to:
`"""Promote statement annotations (proposition/question/hypothesis) into entities (mint-or-link)."""`

- [ ] **Step 5: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/test_annotation_promote.py tests/test_annotate_promote_cli.py -q`
Expected: PASS — new orchestration/override units + all pre-existing proposition CLI round-trips.

- [ ] **Step 6: Type-check and commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b/science && uv run --frozen pyright src/science_tool/annotation/promote.py src/science_tool/annotation/cli.py
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add science/src/science_tool/annotation/promote.py science/src/science_tool/annotation/cli.py science/tests/test_annotation_promote.py
git commit -m "feat(promote): decide_all orchestration + same-kind override + promote_cmd widening"
```

---

### Task 7: End-to-end q/h promotion (disk + backlink + provenance + idempotency + ambiguity)

Integration tests through the public `science annotate promote` command: question and
hypothesis annotations mint entities on disk with both provenance refs + sidecar backlink;
a second `--apply` is a no-op; an ambiguous corpus skips; the materialized graph emits
`wasDerivedFrom` for the annotation ref of a promoted question/hypothesis.

**Files:**
- Test: `science/tests/test_promote_qh_integration.py` (**create**)

- [ ] **Step 1: Write the failing integration tests**

Create `science/tests/test_promote_qh_integration.py`. The scaffold below mirrors the **actual**
`_setup` helper in `science/tests/test_annotate_promote_cli.py` (a `papers/p.source.md` sidecar
with one OPEN statement annotation under project root `tmp_path`), parameterized by kind:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Namespace

from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.model import (
    Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
)
from science_tool.annotation.query import read_sidecar_strict
from science_tool.graph.materialize import _annotation_uri, materialize_graph

PROJECT_NS = Namespace("http://example.org/project/")
PROV = Namespace("http://www.w3.org/ns/prov#")


def _setup_statement(tmp_path: Path, *, atype: str, exact: str, frag: str = "s1"):
    """Minimal project: a papers/p.source.md sidecar with one OPEN statement annotation."""
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text(f"{exact}.\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = Annotation(
        id=frag,
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"abstract","stance":"asserted"}', format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64,  # required for llm-annot: source
    )
    anno_io.write_sidecar(sp, anno_io.Sidecar(annotations=(ann,)))
    return md, sp


def test_question_promote_round_trip(tmp_path):
    md, sp = _setup_statement(tmp_path, atype="question", exact="What regulates X", frag="q1")
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output

    qdir = tmp_path / "entities" / "questions"
    minted = list(qdir.glob("*.md"))                # count ALL question files, not just 0001-*
    assert len(minted) == 1
    text = minted[0].read_text(encoding="utf-8")
    assert minted[0].name.startswith("0001-")
    assert "status: active" in text and "phase:" not in text
    assert "paper:p" in text
    assert "annotation:papers/p.source#q1" in text
    assert "## Summary" in text and "What regulates X" in text
    # provenance: the annotation ref mints a stable wasDerivedFrom URI (same minter 4a uses)
    assert str(_annotation_uri("annotation:papers/p.source#q1")).endswith("#q1")
    # backlink set, status untouched
    ann = read_sidecar_strict(sp).annotations[0]
    assert ann.promoted_to is not None and ann.promoted_to.startswith("question:0001-")
    assert ann.status == Status.OPEN
    # graph provenance: the promoted question points back to the exact source annotation.
    trig_path = materialize_graph(tmp_path)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    question_local_part = ann.promoted_to.split(":", 1)[1]
    question_uri = PROJECT_NS[f"question/{question_local_part}"]
    assert (question_uri, PROV.wasDerivedFrom, _annotation_uri("annotation:papers/p.source#q1")) in provenance

    # second --apply is a no-op (idempotent): still exactly one question entity total
    r2 = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r2.exit_code == 0, r2.output
    assert len(list(qdir.glob("*.md"))) == 1


def test_hypothesis_promote_is_candidate_phase(tmp_path):
    md, sp = _setup_statement(tmp_path, atype="hypothesis", exact="X drives Y", frag="h1")
    r = CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    minted = list((tmp_path / "entities" / "hypotheses").glob("*.md"))
    assert len(minted) == 1
    text = minted[0].read_text(encoding="utf-8")
    assert "status: proposed" in text and "phase: candidate" in text
    assert "## Organizing Conjecture" in text and "X drives Y" in text


def test_idempotent_second_apply_via_json(tmp_path):
    md, sp = _setup_statement(tmp_path, atype="question", exact="What regulates X", frag="q1")
    CliRunner().invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    res = CliRunner().invoke(annotate_group,
                             ["promote", str(md), "--root", str(tmp_path), "--apply", "--format", "json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["minted"] == 0 and payload["linked"] == 0
    assert payload["skipped"].get("promote-already-promoted") == 1
```

> **Implementer note:** This scaffold is copied from the real `_setup` in
> `test_annotate_promote_cli.py` (verify it still matches before relying on it). `_annotation_uri`
> is imported from `science_tool.graph.materialize` exactly as the 4a CLI test
> `test_minted_proposition_materializes_wasderivedfrom` does.

- [ ] **Step 2: Run the integration tests**

Run: `cd science && uv run --frozen pytest tests/test_promote_qh_integration.py -q`
Expected: **PASS** — Tasks 1–6 already implement this behavior, so these acceptance tests are
green-by-construction. They are not a fail-first TDD pair; they pin the end-to-end contract. If
any assertion is red, it pinpoints a real gap — fix it in `promote.py` (or the graph layer) and
note the fix in the commit message rather than weakening the assertion.

- [ ] **Step 3: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add science/tests/test_promote_qh_integration.py
git commit -m "test(promote): end-to-end question/hypothesis promotion (disk, provenance, idempotency)"
```

---

### Task 8: Docs + full-suite regression gate

Document the widened command in the conventions file and run the proposition regression gate +
the broader annotation/graph suite on the finished feature.

**Files:**
- Modify: `docs/conventions/annotation-tokens.md`
- (No code change)

- [ ] **Step 1: Append a Phase 4b note to `docs/conventions/annotation-tokens.md`**

Under the existing "Statement promotion (Phase 4a)" section, append:

```markdown
### Question / hypothesis promotion (Phase 4b)

`science annotate promote` also promotes `question`- and `hypothesis`-type statement
annotations into `question` / `hypothesis` entities, alongside `proposition`:

- **Mint-or-link is kind-local.** A claim links only to an existing entity *of the same kind*
  with an equal normalized title; otherwise it mints. A normalized title held by ≥2 same-kind
  entities is skipped `promote-link-ambiguous` (resolve with an explicit id via `--apply --input`).
- **Numeric identity.** Question/hypothesis entities are minted at `entities/questions/NNNN-slug.md`
  / `entities/hypotheses/NNNN-slug.md` via atomic number reservation (no slug-collision case).
- **Template-faithful.** A minted entity carries every required section (claim text in the lead
  section — question `## Summary`, hypothesis `## Organizing Conjecture`) and the descriptor
  default status (`active` / `proposed`). A promoted **hypothesis** is minted `phase: candidate`
  (a literature-sourced framing the project has not committed to).
- **Provenance & idempotency** match Phase 4a: `source_refs` carry `paper:<id>` +
  `annotation:<relpath>#<frag>`; the annotation gains `sci:promotedTo "<kind>:<id>"`; a second
  `--apply` is a no-op.
- **Non-promotable:** metaphor/analogy and entity/relation seeder annotations are skipped
  `promote-non-promotable-type` (no truth/inquiry-apt target).
```

- [ ] **Step 2: Run the regression gate + broader suite**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b/science
uv run --frozen pytest tests/test_annotation_promote.py tests/test_annotate_promote_cli.py \
  tests/test_promote_numeric_mint.py tests/test_promote_qh_integration.py \
  tests/test_graph_materialize.py tests/test_annotation_io.py -q
```
Expected: exit code 0 (the full proposition regression gate + all new q/h tests).

- [ ] **Step 3: Lint + type-check the touched modules**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b/science
uv run --frozen ruff check src/science_tool/annotation/promote.py src/science_tool/annotation/cli.py
uv run --frozen pyright src/science_tool/annotation/promote.py src/science_tool/annotation/cli.py
```
Expected: clean (or only the 2 pre-existing unrelated `cli.py` F401s noted in the 4a memory —
do not "fix" unrelated inherited warnings).

- [ ] **Step 4: Commit**

```bash
cd ~/d/science/.worktrees/sub-article-annotation-phase4b
git add docs/conventions/annotation-tokens.md
git commit -m "doc(promote): document Phase 4b question/hypothesis promotion in annotation-tokens"
```

---

## Self-Review notes (for the executor)

- **Spec coverage:** Decision 1 (extend `promote`) → Tasks 4/6/8; Decision 2 (`PromotionTarget`) →
  Tasks 2/3; Decision 3 (numeric template-faithful mint + rollback) → Task 3; Decision 4 (kind-local
  dedup + ambiguity) → Tasks 1/5/6; Decision 5 (provenance/idempotency) → Tasks 2/7; Decision 6
  (fail-loud reasons incl. `promote-non-promotable-type`, `promote-link-ambiguous`, proposition-only
  `promote-slug-collision`) → Tasks 1/4/6.
- **Behavior-neutral gate:** the pre-existing proposition tests in `test_annotation_promote.py`
  and `test_annotate_promote_cli.py` must stay green through Tasks 1–6; only the single queue test
  (`test_promotable_filters_queue`) is intentionally updated (Task 4) for the widened queue.
- **Type consistency:** `Promotable.kind` / `PromotionCandidate.kind` default `"proposition"`;
  `decide_candidates(..., slug_addressed=True)`; `MintFn = (candidate, source_refs, project_root,
  as_of) -> entity_id`; LINK `slug` is the full `<kind>:<local_part>`, MINT `slug` is the bare
  local-part; `entity_dest` consumes a full `<kind>:<local_part>`. These are used consistently
  across Tasks 1–7.
- **No placeholders:** Task 7 now inlines its concrete project/sidecar scaffold and graph
  provenance assertion instead of depending on private helpers from another test module.
