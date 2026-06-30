# Entity Organization & Naming — Implementation Plan 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Design:** `docs/plans/2026-06-03-entity-organization-and-naming-design.md`

**Goal:** Make the policy table the single source of truth for every markdown
entity kind, with a uniform `entities/<kind>/NNNN-slug` layout (citekey for
papers), promote `synthesis` to a first-class kind, and teach graph discovery to
load `entities/` — all **additively**, so existing `layout_version: 2` projects
keep working.

**Architecture:** Replace the two-value `filename` field on `EntityPathPolicy`
with a `strategy` enum (`numeric` | `citekey` | `singleton`) and re-root every
markdown kind under `entities/`. `generate_entity_id` emits width-4 numeric
local-parts with no letter/date prefix. `synthesis` is registered in the core
entity registry. `MarkdownAdapter` gains `entities` as a scan root *in addition
to* the legacy roots, so created entities load immediately and the repo stays
green. The hard cutover (dropping legacy roots, validation errors, the migrate
command) is deferred to Plans 2–3.

**Tech Stack:** Python 3.13, pytest, Click (`CliRunner`), pydantic, PyYAML,
`uv` for env. Tests run from `science/` with `uv run pytest`.

**Scope boundary:** This plan is Phases 0,1,3 of the design (policy SSOT,
synthesis promotion, additive discovery). It does **not** add the five new
validation checks (Plan 2), the migrate command, or the no-fallback cutover
(Plan 3). Papers get a policy entry + create support here; their location
*consolidation* happens in the migrate command (Plan 3).

> **Intermediate-phase disclaimer.** Plan 1 is deliberately **additive** and
> therefore *temporarily violates* the design's steady-state "hard cutover, no
> fallback" decision (design §11): discovery keeps the legacy `doc/`/`specs/`
> roots and the singleton checks fall back to `specs/`. This is a compatibility
> bridge so the repo and downstream projects stay green between landing the
> foundation and running migration. Plan 3 removes every fallback added here and
> restores the steady-state invariant. Do not treat the fallbacks in Tasks 6–7
> as permanent.

**Create support in Plan 1 is "policy + loadable + generic scaffold."** All kinds
become creatable and graph-loadable, but only the seven `MIGRATED_KINDS`
(`science/model/src/science_model/templates.py:14`) have domain-specific
templates; newly-added kinds (finding, inquiry, observation, mechanism,
synthesis, report, plan, search, method, pre-registration, paper, topic) render
with the **generic** scaffold. Authoring domain templates for those kinds is
deferred to Plan 2. Atomic id reservation (design §290) is likewise deferred —
see the deferred list.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/entities.py` | Policy table, id generation, path resolution, `create_entity` | Modify |
| `science/src/science_tool/graph/entity_registry.py` | Core kind registration + `EntityClass` map | Modify |
| `science/src/science_tool/graph/storage_adapters/markdown.py` | Markdown scan roots | Modify |
| `science/src/science_tool/validate/checks/research_scope.py` | `research-question.md` discovery | Modify |
| `science/src/science_tool/verdict/registry.py`, `verdict/cli.py` | `claim-registry.yaml` discovery | Modify |
| `science/model/src/science_model/templates/synthesis.md` | Synthesis template (already `type: synthesis`) | Verify only |
| `science/tests/test_entities_cli.py` | CLI create tests (update to `entities/` layout) | Modify |
| `science/tests/test_entity_policy.py` | New: policy table + id generation unit tests | Create |
| `science/tests/test_synthesis_kind.py` | New: synthesis registration test | Create |

Run all tests from the `science/` directory: `cd science && uv run pytest`.

---

## Task 1: Policy schema — add `strategy`, re-root under `entities/`

**Files:**
- Modify: `science/src/science_tool/entities.py:20-41` (policy types + table)
- Test: `science/tests/test_entity_policy.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_entity_policy.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.entities import resolve_path_policy


def test_question_policy_is_entities_numeric() -> None:
    policy = resolve_path_policy("question")
    assert policy.root == Path("entities/questions")
    assert policy.strategy == "numeric"


def test_hypothesis_policy_moved_out_of_specs() -> None:
    policy = resolve_path_policy("hypothesis")
    assert policy.root == Path("entities/hypotheses")
    assert policy.strategy == "numeric"


def test_paper_policy_is_citekey() -> None:
    policy = resolve_path_policy("paper")
    assert policy.root == Path("entities/papers")
    assert policy.strategy == "citekey"


def test_synthesis_and_report_have_policies() -> None:
    assert resolve_path_policy("synthesis").root == Path("entities/synthesis")
    assert resolve_path_policy("report").root == Path("entities/reports")


def test_evidence_line_root_is_not_naive_pluralization() -> None:
    assert resolve_path_policy("evidence-line").root == Path("entities/evidence-lines")
    assert resolve_path_policy("pre-registration").root == Path("entities/pre-registrations")


def test_singletons_are_in_the_policy_table() -> None:
    from science_tool.entities import singleton_path

    assert resolve_path_policy("research-question").strategy == "singleton"
    assert singleton_path("research-question") == Path("entities/research-question.md")
    assert singleton_path("claim-registry") == Path("entities/claim-registry.yaml")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_entity_policy.py -v`
Expected: FAIL — `AttributeError: 'EntityPathPolicy' object has no attribute 'strategy'` and wrong roots.

- [ ] **Step 3: Replace the policy types and table**

In `science/src/science_tool/entities.py`, replace the block at lines 20-41:

```python
EntityFilenameStrategy = Literal["numeric", "citekey", "singleton"]

LOCAL_PART_WIDTH = 4


class EntityCommandError(ValueError):
    """Raised for user-correctable entity CLI errors."""


@dataclass(frozen=True)
class EntityPathPolicy:
    root: Path
    strategy: EntityFilenameStrategy


_BUILTIN_MARKDOWN_POLICIES: dict[str, EntityPathPolicy] = {
    "question": EntityPathPolicy(Path("entities/questions"), "numeric"),
    "hypothesis": EntityPathPolicy(Path("entities/hypotheses"), "numeric"),
    "proposition": EntityPathPolicy(Path("entities/propositions"), "numeric"),
    "interpretation": EntityPathPolicy(Path("entities/interpretations"), "numeric"),
    "discussion": EntityPathPolicy(Path("entities/discussions"), "numeric"),
    "finding": EntityPathPolicy(Path("entities/findings"), "numeric"),
    "inquiry": EntityPathPolicy(Path("entities/inquiries"), "numeric"),
    "theme": EntityPathPolicy(Path("entities/themes"), "numeric"),
    "topic": EntityPathPolicy(Path("entities/topics"), "numeric"),
    "evidence-line": EntityPathPolicy(Path("entities/evidence-lines"), "numeric"),
    "observation": EntityPathPolicy(Path("entities/observations"), "numeric"),
    "mechanism": EntityPathPolicy(Path("entities/mechanisms"), "numeric"),
    "synthesis": EntityPathPolicy(Path("entities/synthesis"), "numeric"),
    "report": EntityPathPolicy(Path("entities/reports"), "numeric"),
    "plan": EntityPathPolicy(Path("entities/plans"), "numeric"),
    "search": EntityPathPolicy(Path("entities/searches"), "numeric"),
    "method": EntityPathPolicy(Path("entities/methods"), "numeric"),
    "pre-registration": EntityPathPolicy(Path("entities/pre-registrations"), "numeric"),
    "paper": EntityPathPolicy(Path("entities/papers"), "citekey"),
    # Singletons: `root` is the file path itself, not a directory.
    "research-question": EntityPathPolicy(Path("entities/research-question.md"), "singleton"),
    "claim-registry": EntityPathPolicy(Path("entities/claim-registry.yaml"), "singleton"),
}
```

Delete the now-unused `EntityFilenamePolicy = Literal[...]` line (was line 20).
Keep `_SLUG_RE`, `_LOCAL_PART_RE`, etc. as-is. Add `_CITEKEY_RE` and the
numeric-local-part validator near them, plus a `singleton_path` helper so the
policy table is the authoritative source for singleton locations (consumed by
Task 7):

```python
_CITEKEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.-]*$")
_NUMERIC_LOCAL_PART_RE = re.compile(r"^\d{4}-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def singleton_path(kind: str) -> Path:
    policy = resolve_path_policy(kind)
    if policy.strategy != "singleton":
        raise EntityCommandError(f"{kind} is not a singleton kind")
    return policy.root
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_entity_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_entity_policy.py
git commit -m "feat(entities): policy table SSOT with strategy enum, rooted at entities/"
```

---

## Task 2: Numeric id generation — width-4, no letter/date

**Files:**
- Modify: `science/src/science_tool/entities.py:171-213` (`generate_entity_id`, `path_for_entity`)
- Test: `science/tests/test_entity_policy.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_entity_policy.py`:

```python
from datetime import date

from science_tool.entities import generate_entity_id, path_for_entity


def test_first_numeric_entity_starts_at_0001(tmp_path) -> None:
    eid = generate_entity_id(tmp_path, "question", "Model Granularity", None, None)
    assert eid == "question:0001-model-granularity"


def test_numeric_increments_from_siblings(tmp_path) -> None:
    d = tmp_path / "entities" / "questions"
    d.mkdir(parents=True)
    (d / "0001-existing.md").write_text("x", encoding="utf-8")
    (d / "0007-other.md").write_text("x", encoding="utf-8")
    eid = generate_entity_id(tmp_path, "question", "New One", None, None)
    assert eid == "question:0008-new-one"


def test_numeric_scan_tolerates_legacy_letter_prefix(tmp_path) -> None:
    d = tmp_path / "entities" / "hypotheses"
    d.mkdir(parents=True)
    (d / "h03-legacy.md").write_text("x", encoding="utf-8")
    eid = generate_entity_id(tmp_path, "hypothesis", "Next", None, None)
    assert eid == "hypothesis:0004-next"


def test_citekey_requires_explicit_id(tmp_path) -> None:
    import pytest
    from science_tool.entities import EntityCommandError

    with pytest.raises(EntityCommandError):
        generate_entity_id(tmp_path, "paper", "Some Title", None, None)
    eid = generate_entity_id(tmp_path, "paper", "", "paper:Adams2025", None)
    assert eid == "paper:Adams2025"


def test_explicit_numeric_id_must_be_canonical(tmp_path) -> None:
    import pytest
    from science_tool.entities import EntityCommandError

    # Legacy letter-prefixed and wrong-width ids must be rejected, so --id
    # cannot reintroduce drift under entities/questions/.
    # signature: generate_entity_id(project_root, kind, title, entity_id, slug)
    with pytest.raises(EntityCommandError):
        generate_entity_id(tmp_path, "question", "", "question:q01-old-shape", None)
    with pytest.raises(EntityCommandError):
        generate_entity_id(tmp_path, "question", "", "question:5-too-short", None)
    ok = generate_entity_id(tmp_path, "question", "", "question:0005-good", None)
    assert ok == "question:0005-good"


def test_path_for_entity_uses_policy_root(tmp_path) -> None:
    p = path_for_entity("question", "question:0008-new-one", date(2026, 6, 3))
    assert p == Path("entities/questions/0008-new-one.md")
    pp = path_for_entity("paper", "paper:Adams2025", date(2026, 6, 3))
    assert pp == Path("entities/papers/Adams2025.md")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_policy.py -v`
Expected: FAIL — current `generate_entity_id` errors "No existing siblings" and uses letter/date logic.

- [ ] **Step 3: Rewrite `generate_entity_id` and helpers**

Replace `generate_entity_id` (lines 171-206) and adjust `path_for_entity`
(209-213) in `science/src/science_tool/entities.py`:

```python
_NUMERIC_SCAN_RE = re.compile(r"^(?:[A-Za-z])?(\d+)")


def _next_numeric_local_part(project_root: Path, kind: str, slug: str) -> str:
    root = project_root / resolve_path_policy(kind).root
    max_n = 0
    if root.is_dir():
        for path in root.glob("*.md"):
            match = _NUMERIC_SCAN_RE.match(path.stem)
            if match is not None:
                max_n = max(max_n, int(match.group(1)))
    return f"{max_n + 1:0{LOCAL_PART_WIDTH}d}-{slug}"


def generate_entity_id(
    project_root: Path,
    kind: str,
    title: str,
    entity_id: str | None,
    slug: str | None,
    today: date | None = None,
) -> str:
    del today  # dates live in frontmatter, not the id
    if entity_id is not None:
        return validate_entity_id(kind, entity_id)

    strategy = resolve_path_policy(kind).strategy
    if strategy == "citekey":
        raise EntityCommandError(f"{kind} requires an explicit --id (citekey), e.g. {kind}:Adams2025")
    if strategy == "singleton":
        raise EntityCommandError(f"{kind} is a singleton; it is not created via this path")

    slug_value = validate_slug(slug) if slug is not None else derive_slug(title)
    return f"{kind}:{_next_numeric_local_part(project_root, kind, slug_value)}"
```

Update `validate_entity_id` to validate citekey local-parts. Replace lines
161-168:

```python
def validate_entity_id(kind: str, entity_id: str) -> str:
    prefix = f"{kind}:"
    if not entity_id.startswith(prefix):
        raise EntityCommandError(f"Entity id must use prefix {prefix}")
    local_part = entity_id[len(prefix) :]
    strategy = resolve_path_policy(kind).strategy
    if strategy == "singleton":
        raise EntityCommandError(f"{kind} is a singleton and has no per-instance id")
    if strategy == "citekey":
        if not _CITEKEY_RE.fullmatch(local_part):
            raise EntityCommandError(f"Invalid citekey local part: {entity_id}")
        return entity_id
    # numeric: an explicit --id must already be canonical, so it cannot
    # reintroduce drift (e.g. question:q01-... or question:5-...).
    if not _NUMERIC_LOCAL_PART_RE.fullmatch(local_part):
        raise EntityCommandError(
            f"Non-canonical numeric id {entity_id!r}; expected <kind>:NNNN-slug (4-digit number)"
        )
    return entity_id
```

`path_for_entity` keeps its existing body — `resolve_path_policy(kind).root /
f"{local_part}.md"` already yields the right path for numeric and citekey. Leave
it as-is aside from confirming it reads `.root`.

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_entity_policy.py
git commit -m "feat(entities): width-4 numeric ids, no letter/date; citekey ids for papers"
```

---

## Task 2.5: Shortform resolution for zero-padded ids

`q5` / `h3` input sugar must resolve to `…:0005-…` / `…:0003-…`. The current
matcher (`_entity_ref_matches`, `science/src/science_tool/entities.py:232`)
compares the bare number `5` against `local_part.startswith("5-")`, which never
matches `0005-`. Fix it to also try the width-padded form.

**Files:**
- Modify: `science/src/science_tool/entities.py:232-244` (`_entity_ref_matches`)
- Test: `science/tests/test_entity_policy.py` (unit) + `science/tests/test_entities_cli.py` (integration)

- [ ] **Step 1: Write failing tests**

Append to `science/tests/test_entity_policy.py`:

```python
from science_tool.entities import _entity_ref_matches


def test_shortform_resolves_zero_padded_id() -> None:
    assert _entity_ref_matches("question:0005-model-granularity", "q5")
    assert _entity_ref_matches("hypothesis:0003-attractor", "h3")
    assert not _entity_ref_matches("question:0005-model-granularity", "h5")  # wrong kind


def test_shortform_still_matches_legacy_unpadded_id() -> None:
    # during transition, legacy ids like question:5-foo must still resolve
    assert _entity_ref_matches("question:5-foo", "q5")
```

Append to `science/tests/test_entities_cli.py`:

```python
def test_entity_show_resolves_shortform() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0005-granularity.md",
            {"id": "question:0005-granularity", "type": "question", "title": "Granularity", "status": "active"},
        )
        result = runner.invoke(main, ["entity", "show", "q5"])
        assert result.exit_code == 0, result.output
        assert "question:0005-granularity" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_policy.py -k shortform tests/test_entities_cli.py::test_entity_show_resolves_shortform -v`
Expected: FAIL — `q5` does not match `0005-…`.

- [ ] **Step 3: Pad the number when matching**

In `science/src/science_tool/entities.py`, add a helper and rewrite
`_entity_ref_matches` to try both the raw and width-padded number variants:

```python
def _numeric_variants(token: str) -> set[str]:
    """Return {token, zero-padded-to-width(token)} when token starts with digits."""
    match = re.match(r"^(\d+)(.*)$", token)
    if match is None:
        return {token}
    digits, rest = match.group(1), match.group(2)
    return {token, f"{int(digits):0{LOCAL_PART_WIDTH}d}{rest}"}


def _entity_ref_matches(entity_id: str, ref: str) -> bool:
    kind, local_part = entity_id.split(":", 1)
    for variant in _numeric_variants(ref):
        if local_part == variant or local_part.startswith(f"{variant}-"):
            return True

    shortform = _SHORTFORM_REF_RE.fullmatch(ref)
    if shortform is None:
        return False
    if _SHORTFORM_ENTITY_KINDS.get(shortform.group("prefix").lower()) != kind:
        return False

    unprefixed_ref = shortform.group("number") + shortform.group("suffix")
    for variant in _numeric_variants(unprefixed_ref):
        if local_part == variant or local_part.startswith(f"{variant}-"):
            return True
    return False
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_policy.py -k shortform tests/test_entities_cli.py::test_entity_show_resolves_shortform -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_entity_policy.py science/tests/test_entities_cli.py
git commit -m "fix(entities): resolve q5/h3 shortforms against zero-padded ids"
```

---

## Task 3: Promote `synthesis` to a core kind

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py:48-91` (`_CORE_KIND_CLASSES`) and `105+` (`with_core_types`)
- Test: `science/tests/test_synthesis_kind.py` (create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_synthesis_kind.py`:

```python
from __future__ import annotations

from science_model.entities import EntityClass
from science_tool.graph.entity_registry import EntityRegistry


def test_synthesis_is_registered_epistemic() -> None:
    registry = EntityRegistry.with_core_types()
    classes = registry.all_kind_classes()
    assert "synthesis" in classes
    assert classes["synthesis"] == EntityClass.EPISTEMIC


def test_report_remains_epistemic() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.all_kind_classes()["report"] == EntityClass.EPISTEMIC
```

> Confirm the accessor name: if `all_kind_classes()` returns a set rather than a
> mapping, adjust the assertion to use the registry's class-lookup method
> (grep `def all_kind_classes` / `entity_class_for` in `entity_registry.py`).

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_synthesis_kind.py -v`
Expected: FAIL — `synthesis` not registered.

- [ ] **Step 3: Register synthesis**

In `science/src/science_tool/graph/entity_registry.py`, add to
`_CORE_KIND_CLASSES` (in the alphabetized generic block):

```python
    "synthesis": EntityClass.EPISTEMIC,
```

Then in `with_core_types()`, where generic `ProjectEntity` kinds are registered
in a loop (the `for kind in (...)` block around line 136), add `"synthesis"` to
that tuple so it registers as a `ProjectEntity` with the class above. `report`
is already in that loop; leave it.

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_synthesis_kind.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/entity_registry.py science/tests/test_synthesis_kind.py
git commit -m "feat(model): register synthesis as a first-class epistemic kind"
```

---

## Task 4: CLI status maps for all numeric kinds

**Files:**
- Modify: `science/src/science_tool/entities.py:55-91` (`_DEFAULT_STATUS`, `_STATUS_VALUES`)
- Test: `science/tests/test_entity_policy.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_policy.py`:

```python
from science_tool.entities import _BUILTIN_MARKDOWN_POLICIES, _DEFAULT_STATUS, _STATUS_VALUES


def test_every_policy_kind_has_status_config() -> None:
    for kind in _BUILTIN_MARKDOWN_POLICIES:
        assert kind in _DEFAULT_STATUS, f"{kind} missing default status"
        assert kind in _STATUS_VALUES, f"{kind} missing status values"
        assert _DEFAULT_STATUS[kind] in _STATUS_VALUES[kind]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entity_policy.py::test_every_policy_kind_has_status_config -v`
Expected: FAIL — only 7 kinds covered.

- [ ] **Step 3: Extend the status maps**

In `science/src/science_tool/entities.py`, add entries to `_DEFAULT_STATUS` and
`_STATUS_VALUES` for every kind now in the policy table. Reuse the existing
status vocabularies where a kind already has an analog; for new kinds use:

```python
# add to _DEFAULT_STATUS
    "finding": "active",
    "inquiry": "active",
    "topic": "active",
    "observation": "active",
    "mechanism": "active",
    "synthesis": "active",
    "report": "active",
    "plan": "active",
    "search": "active",
    "method": "active",
    "pre-registration": "active",
    "paper": "active",

# add to _STATUS_VALUES (use this shared set for the kinds without a bespoke vocabulary)
    "finding": frozenset({"active", "superseded", "retired"}),
    "inquiry": frozenset({"active", "complete", "superseded"}),
    "topic": frozenset({"active", "superseded", "retired"}),
    "observation": frozenset({"active", "superseded", "retired"}),
    "mechanism": frozenset({"active", "superseded", "retired"}),
    "synthesis": frozenset({"active", "superseded", "retired"}),
    "report": frozenset({"active", "superseded", "retired"}),
    "plan": frozenset({"active", "complete", "superseded", "retired"}),
    "search": frozenset({"active", "complete", "retired"}),
    "method": frozenset({"active", "superseded", "retired"}),
    "pre-registration": frozenset({"active", "amended", "superseded", "retired"}),
    "paper": frozenset({"active", "retired"}),
```

> These status vocabularies are first-pass defaults; if a downstream profile
> already defines stricter statuses for a kind, reconcile in Plan 2's validation
> work. They are intentionally permissive here so create does not over-constrain.

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entity_policy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_entity_policy.py
git commit -m "feat(entities): default/allowed statuses for all markdown kinds"
```

---

## Task 5: `create` writes to `entities/` — update CLI tests

**Files:**
- Modify: `science/tests/test_entities_cli.py` (existing assertions reference `doc/questions/q02-…`)
- Test: same file (the create tests are the tests)

- [ ] **Step 1: Update the existing create tests to the new layout**

In `science/tests/test_entities_cli.py`, update `test_entity_create_question_writes_source`:

```python
def test_entity_create_question_writes_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-existing.md",
            {"id": "question:0001-existing", "type": "question", "title": "Existing", "status": "active"},
        )

        result = runner.invoke(main, ["entity", "create", "question", "New Question"])

        assert result.exit_code == 0, result.output
        assert "question:0002-new-question" in result.output
        assert Path("entities/questions/0002-new-question.md").is_file()
```

Apply the same `doc/questions/q0…` → `entities/questions/000…` and
`q02-` → `0002-` updates to `test_questions_create_uses_plural_group_and_singular_is_removed`
and any other create/show test in the file that hard-codes the old path or
`q##`/`h##` ids. Grep within the file:

Run: `cd science && grep -n "doc/questions\|doc/hypotheses\|specs/hypotheses\|q0[0-9]\|h0[0-9]" tests/test_entities_cli.py`

Update each hit to the `entities/<kind>/NNNN-slug` form.

- [ ] **Step 2: Run to verify the create flow works end-to-end**

Run: `cd science && uv run pytest tests/test_entities_cli.py -v`
Expected: PASS (create now writes `entities/questions/0002-new-question.md`).

- [ ] **Step 3: Add a citekey-paper create test**

Append to `science/tests/test_entities_cli.py`:

```python
def test_entity_create_paper_uses_citekey() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        result = runner.invoke(
            main, ["entity", "create", "paper", "Some Paper", "--id", "paper:Adams2025"]
        )
        assert result.exit_code == 0, result.output
        assert Path("entities/papers/Adams2025.md").is_file()


def test_entity_create_newly_added_kind_uses_generic_scaffold() -> None:
    # A non-MIGRATED_KIND (no domain template) must still create successfully
    # with valid required frontmatter (generic scaffold). Domain templates for
    # these kinds are deferred to Plan 2.
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        result = runner.invoke(main, ["entity", "create", "finding", "A Finding"])
        assert result.exit_code == 0, result.output
        path = Path("entities/findings/0001-a-finding.md")
        assert path.is_file()
        fm = yaml.safe_load(path.read_text().split("---")[1])
        assert fm["id"] == "finding:0001-a-finding"
        assert fm["type"] == "finding"
        assert {"title", "status", "created", "updated"} <= set(fm)
```

> If `create_entity` hard-rejects kinds outside `MIGRATED_KINDS` (rather than
> falling back to the generic scaffold), add a minimal step here to allow the
> generic path for any kind whose policy `strategy` is `numeric`/`citekey`. Grep
> `MIGRATED_KINDS` usage in `create_entity` / `templates.py` to confirm the
> current behavior before assuming fallback.

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/test_entities_cli.py::test_entity_create_paper_uses_citekey -v`
Expected: PASS. (If `create_entity` rejects `paper`, ensure `paper` is reachable
— it has a policy entry now, so `resolve_path_policy("paper")` succeeds; the only
remaining guard is the `concept` reject at `entities.py:359`, which stays.)

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_entities_cli.py
git commit -m "test(entities): create writes entities/ layout; citekey papers"
```

---

## Task 6: Discovery — add `entities` scan root (additive)

**Files:**
- Modify: `science/src/science_tool/graph/storage_adapters/markdown.py:20`
- Test: `science/tests/test_entities_cli.py` (add a load-roundtrip test)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entities_cli.py`:

```python
def test_entities_dir_is_discovered_by_graph() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/questions/0001-loadable.md",
            {"id": "question:0001-loadable", "type": "question", "title": "Loadable", "status": "active"},
        )
        sources = load_project_sources(root)
        ids = {doc.frontmatter.get("id") for doc in sources.markdown_documents}
        assert "question:0001-loadable" in ids
```

> Confirm the `load_project_sources` return shape (`.markdown_documents` and the
> per-doc `.frontmatter`) against `science/src/science_tool/graph/sources.py`; the
> existing top-of-file import in this test module already pulls in
> `load_project_sources`.

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/test_entities_cli.py::test_entities_dir_is_discovered_by_graph -v`
Expected: FAIL — `entities/` is not in `scan_roots`.

- [ ] **Step 3: Add `entities` to the default scan roots (keep legacy roots)**

In `science/src/science_tool/graph/storage_adapters/markdown.py:20`:

```python
        self._scan_roots = scan_roots or ["entities", "doc", "specs", "research/packages"]
```

Keeping `doc`/`specs` here is deliberate for this plan — it makes the change
additive so un-migrated projects still load. Plan 3 removes them at cutover.

- [ ] **Step 4: Run to verify pass + no regressions**

Run: `cd science && uv run pytest tests/test_entities_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/storage_adapters/markdown.py science/tests/test_entities_cli.py
git commit -m "feat(graph): discover entities/ markdown root (additive)"
```

---

## Task 7: Singleton discovery — `research-question.md` & `claim-registry.yaml` (prefer `entities/`)

**Files:**
- Modify: `science/src/science_tool/validate/checks/research_scope.py:28`
- Modify: `science/src/science_tool/verdict/registry.py:113`, `science/src/science_tool/verdict/cli.py:131`
- Test: `science/tests/validate/test_checks_research_documents.py` (extend) and a verdict test

- [ ] **Step 1: Write the failing test (research scope)**

Add to `science/tests/validate/test_checks_research_documents.py` (match the
module's existing fixture/ctx-building style; grep the file for how it constructs
`ValidateContext`):

```python
def test_research_question_found_in_entities(tmp_path) -> None:
    # build a research-profile project with entities/research-question.md and NO specs/
    ...  # follow existing helper in this module to seed ctx
    results = list(check_research_scope(ctx))
    assert not any(r.severity is Severity.ERROR for r in results)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run pytest tests/validate/test_checks_research_documents.py -k research_question_found_in_entities -v`
Expected: FAIL — check only looks in `specs/`.

- [ ] **Step 3: Prefer `entities/`, fall back to `specs/` (fallback removed in Plan 3)**

In `science/src/science_tool/validate/checks/research_scope.py`, replace the
hard-coded path (line 28) — resolve the canonical location from the policy table
via `singleton_path`, then fall back to `specs/` (fallback removed in Plan 3):

```python
    from science_tool.entities import singleton_path

    entities_rq = ctx.project_root / singleton_path("research-question")
    legacy_rq = ctx.specs_dir / "research-question.md"
    research_question = entities_rq if entities_rq.is_file() else legacy_rq
    if not research_question.is_file():
        yield _result(
            Severity.ERROR,
            "entities/research-question.md",
            "research-question.md not found — every project needs a research question",
        )
        return
```

In `science/src/science_tool/verdict/registry.py` (`has_registry`, ~line 113) and
`science/src/science_tool/verdict/cli.py` (`_load_registry_for_rollup`, ~line
131), update the default candidate to prefer `entities/claim-registry.yaml` then
fall back to `specs/claim-registry.yaml`:

```python
    # cli.py _load_registry_for_rollup
    if path is None:
        for rel in ("entities/claim-registry.yaml", "specs/claim-registry.yaml"):
            candidate = root / rel
            if candidate.is_file():
                path = candidate
                break
```

```python
    # registry.py has_registry: check both locations
    root = Path(project_root)
    if alt_filename is not None:
        return (root / alt_filename).is_file()
    return (root / "entities" / "claim-registry.yaml").is_file() or (
        root / "specs" / "claim-registry.yaml"
    ).is_file()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run pytest tests/validate/test_checks_research_documents.py tests/test_verdict_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/research_scope.py science/src/science_tool/verdict/registry.py science/src/science_tool/verdict/cli.py science/tests/validate/test_checks_research_documents.py
git commit -m "feat(validate,verdict): discover singletons under entities/ (fallback to specs/)"
```

---

## Task 8: Full suite + lint

**Files:** none (verification task)

- [ ] **Step 1: Run the full test suite**

Run: `cd science && uv run pytest -q`
Expected: PASS. If any test outside the files above fails, it is almost certainly
asserting the old `doc/`/`specs/` layout or `q##`/`h##` ids — update those
assertions to the `entities/` + `NNNN-slug` form. Do **not** weaken a test to
pass; fix the assertion to the new expected behavior.

- [ ] **Step 2: Lint**

Run: `cd science && uv run ruff check src tests`
Expected: clean (fix any unused-import from the removed `EntityFilenamePolicy`).

- [ ] **Step 3: Commit any test fixups**

```bash
git add -A
git commit -m "test: align remaining suites with entities/ layout"
```

---

## Self-review notes (coverage against the design)

- Policy SSOT + per-kind strategy (incl. singleton rows) → Tasks 1, 4. ✅
- Width-4 numeric, no letter/date; citekey papers; canonical explicit `--id` → Task 2. ✅
- Shortform `q5`/`h3` → zero-padded id → Task 2.5. ✅
- Synthesis promotion → Task 3. ✅
- Discovery loads `entities/` → Task 6. ✅
- Singleton discovery driven by the policy table → Tasks 1 (`singleton_path`), 7. ✅
- Additive (repo stays green; no cutover) → Tasks 6, 7 keep legacy roots/fallback;
  see the intermediate-phase disclaimer at the top. ✅

**Deferred to later plans (intentionally not in this plan):**
- **Atomic id reservation (design §290).** Plan 1 keeps the non-atomic
  "scan-max-then-write" flow, so parallel agents can collide on `000N`. Deferred
  to Plan 2: generalize `questions.reserve`'s `O_CREAT|O_EXCL` loop
  (`science/src/science_tool/questions.py:175`) into a kind-agnostic
  `reserve_entity` for all numeric kinds. Acceptable in Plan 1 because
  single-author create is the common path.
- **Domain templates for newly-added kinds.** Only the seven `MIGRATED_KINDS`
  have domain templates; finding/inquiry/observation/mechanism/synthesis/report/
  plan/search/method/pre-registration/topic/paper render generically in Plan 1.
  Plan 2 authors their templates + per-kind required-section tests.
- **Plan 2 — Validation & legacy checks:** the five new checks (location
  coherence, filename conformance, frontmatter completeness, number hygiene,
  stray-file); repoint `discussions.py`, `document_structure.py`, `papers.py`,
  `hypotheses.py` (drop `h*` glob); make `id_prefixes.PREFIX_RULES` a derived
  view of the policy table; `layout_version` awareness (WARN).
- **Plan 3 — Migrate command & cutover:** `science entities migrate [--apply]`
  (frontmatter synthesis → id-map → raw frontmatter/prose rewrite → `git mv` →
  re-validate), the migration guide, pilot on one project, then the irreversible
  no-fallback cutover (scan roots → `entities` only, drop `specs/` fallbacks,
  `_ALLOWED_EXPLICIT_ROOTS` → `entities`, validation ERROR for `layout_version < 3`,
  WARN→ERROR on the new checks).
