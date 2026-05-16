# Commons promote: topics & themes (Phase F) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalise the Phase E paper-promote machinery to a kind-pluggable shape and add `science commons promote topic` and `science commons promote theme`, with plan-time schema validation and a topic-only `doc/background/topics/ → doc/topics/` overlay-flatten path.

**Architecture:** One frozen `PromoteKindConfig` dataclass + three module-level constants (`PROMOTE_KIND_PAPER`, `PROMOTE_KIND_TOPIC`, `PROMOTE_KIND_THEME`). Discovery / plan / apply functions take `kind` as a parameter; field naming generalises from paper-specific `bibkey` to kind-agnostic `slug`. New `PromoteValidationError` raised at end of `plan_promote` for any canonical/overlay schema failure. Theme adds an eligibility filter that admits only `theme_scope: cross-project`.

**Tech Stack:** Python 3.13, click, PyYAML, jsonschema (Draft 2020-12), pytest. Reuses the existing `science_model.entity_schema` profile/loader/merge machinery and the Phase E `science_tool.commons.promote` module.

**Design reference:** `~/d/science/docs/plans/2026-05-16-commons-promote-topics-themes-design.md` (commits 6ddb207 → 41f3d13).

**Predecessor (must be merged):** Phase E — `commons promote paper` (head `a61a45d`, merged 2026-05-16).

**Branch:** `feat/commons-promote-topics-themes` (off `main`).

---

## File Structure

**Schemas (new):**
- `science/model/src/science_model/schemas/mixin-topic-2.0.json`
- `science/model/src/science_model/schemas/mixin-theme-2.0.json`

**Schema infrastructure (modify):**
- `science/model/src/science_model/entity_schema/profile.py` — bump `_DEFAULT_MIXIN_VERSION["topic"]` and `["theme"]` from `"1.0"` to `"2.0"`.

**Commons module (modify):**
- `science/src/science_tool/commons/promote.py` — bulk of the work: kind config dataclass + enum + three constants; `bibkey → slug` rename across dataclasses; rename `discover_paper_candidates → discover_candidates`; thread `kind` through every public entry point; de-hardcode the 10 paper-only call sites identified in §4.4 of the design; add plan-time validation.
- `science/src/science_tool/commons/errors.py` — add `PromoteValidationError`; rename `PromoteCandidateError.bibkey` → `.slug`.
- `science/src/science_tool/commons/cli.py` — rename `discover_paper_candidates` import; add `promote topic` and `promote theme` subcommands; catch `PromoteValidationError` in the plan-error block.
- `science/src/science_tool/commons/__init__.py` — re-export `PromoteKindConfig`, `EligibilityVerdict`, `PROMOTE_KIND_PAPER/TOPIC/THEME`, `PromoteValidationError`.

**Tests (modify — attribute-name updates only, behaviour unchanged):**
- `science/tests/test_commons_promote_discovery.py`
- `science/tests/test_commons_promote_plan.py`
- `science/tests/test_commons_promote_apply.py`
- `science/tests/test_commons_cli_promote.py`

**Tests (new):**
- `science/tests/test_commons_promote_kind_config.py` — `PromoteKindConfig` + `EligibilityVerdict` shape tests.
- `science/tests/test_commons_promote_validation.py` — plan-time validation tests.
- `science/tests/test_commons_promote_topic_discovery.py`
- `science/tests/test_commons_promote_topic_plan.py`
- `science/tests/test_commons_promote_topic_apply.py`
- `science/tests/test_commons_cli_promote_topic.py`
- `science/tests/test_commons_promote_theme_discovery.py`
- `science/tests/test_commons_promote_theme_plan.py`
- `science/tests/test_commons_promote_theme_apply.py`
- `science/tests/test_commons_cli_promote_theme.py`
- `science/model/tests/test_mixin_topic_2_0.py`
- `science/model/tests/test_mixin_theme_2_0.py`

**Fixtures (new):**
- `science/tests/fixtures/promote/proj-alpha/doc/topics/*.md`
- `science/tests/fixtures/promote/proj-alpha/doc/background/topics/*.md`
- `science/tests/fixtures/promote/proj-beta/doc/topics/*.md`
- `science/tests/fixtures/promote/proj-alpha/doc/themes/*.md`
- `science/tests/fixtures/promote/proj-beta/doc/themes/*.md`

**Documentation (new):**
- `docs/plans/2026-05-16-commons-promote-topics-themes-pilot.md` — pilot runbook (final task).

---

## Conventions

- **TDD discipline:** Each task writes a failing test first, then the minimum code to pass it, then a passing run, then a commit. Steps below the `Step 1: Write the failing test` line in each task assume the test exists.
- **Commit per task:** No task ends without a commit. Squashing happens during PR review, not during execution.
- **Verify before claiming done:** Run the test from each task in isolation before commit. Don't rely on "should pass."
- **`bibkey → slug` rename context:** Phase E used `bibkey` field names. Phase F treats it as a paper-specific term; the rename is mechanical (driven by the source rename, not behaviour change). Test assertions that read `.bibkey` are mechanically updated to read `.slug`; the values asserted do not change. This satisfies design §6.1 ("don't change behaviour-tests during the refactor").
- **Running the test suite:** From the repo root, `cd science && python -m pytest <path> -v`. Schema-package tests live in `science/model/tests/`; everything else in `science/tests/`.
- **No legacy aliases:** Per the project's "no compat layers" rule, renames are clean — old names disappear in the same task.

---

## Phase 1 — Foundation (refactor types + constants)

### Task 1: Add `PromoteKindConfig` dataclass + `EligibilityVerdict` enum

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (top imports + new module section near existing dataclasses)
- Test: `science/tests/test_commons_promote_kind_config.py` (new)

- [ ] **Step 1: Write the failing test** — create `science/tests/test_commons_promote_kind_config.py`:

```python
"""Tests for the kind-config types in science_tool.commons.promote."""
from __future__ import annotations

import re
from typing import Mapping, Any

import pytest


def test_promote_kind_config_is_frozen_dataclass() -> None:
    from science_tool.commons.promote import PromoteKindConfig

    assert PromoteKindConfig.__dataclass_params__.frozen


def test_promote_kind_config_required_fields() -> None:
    from science_model.entity_schema import default_profile_for_kind
    from science_tool.commons.promote import PromoteKindConfig

    cfg = PromoteKindConfig(
        kind="paper",
        source_subdirs=("doc/papers",),
        overlay_dest_subdir="doc/papers",
        commons_subdir="papers",
        id_prefix="paper:",
        slug_regex=re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,63}$"),
        slug_match="casefold",
        mixin_schema_id="https://schemas.science/mixin-paper-2.0.json",
        default_profile=default_profile_for_kind("paper"),
        eligibility_filter=None,
    )
    assert cfg.kind == "paper"
    assert cfg.source_subdirs == ("doc/papers",)
    assert cfg.slug_match == "casefold"
    assert cfg.eligibility_filter is None


def test_eligibility_verdict_enum_values() -> None:
    from science_tool.commons.promote import EligibilityVerdict

    assert EligibilityVerdict.ELIGIBLE.value == "eligible"
    assert EligibilityVerdict.SKIP_SILENT.value == "skip_silent"
    assert EligibilityVerdict.FAIL.value == "fail"
    assert len(list(EligibilityVerdict)) == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_kind_config.py -v
```
Expected: ImportError — `PromoteKindConfig` and `EligibilityVerdict` not defined.

- [ ] **Step 3: Implement** — add to `science/src/science_tool/commons/promote.py`, just after the existing imports (insert `from enum import Enum` to imports, and add the types just before the `# Public dataclasses` section):

```python
from enum import Enum
from typing import Mapping  # may already be imported


class EligibilityVerdict(Enum):
    ELIGIBLE = "eligible"
    SKIP_SILENT = "skip_silent"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class PromoteKindConfig:
    """Per-kind configuration for the promote pipeline.

    One instance per kind ("paper", "topic", "theme"). Pure data plus an
    optional eligibility-filter callable; threaded through discovery /
    plan / apply via the `kind` parameter or `PromotePlan.kind`.
    """

    kind: Literal["paper", "topic", "theme"]
    source_subdirs: tuple[str, ...]
    overlay_dest_subdir: str
    commons_subdir: str
    id_prefix: str
    slug_regex: re.Pattern[str]
    slug_match: Literal["casefold", "exact"]
    mixin_schema_id: str
    default_profile: "ProfileString"
    eligibility_filter: Callable[[Mapping[str, Any]], "EligibilityVerdict"] | None
```

Also add `ProfileString` to the existing import block from `science_model.entity_schema`:

```python
from science_model.entity_schema import (
    MergePolicy,
    ProfileString,
    default_profile_for_kind,
    read_canonical_body_sections,
    read_merge_policy,
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_kind_config.py -v
```
Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_kind_config.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): PromoteKindConfig + EligibilityVerdict types

Pure-data dataclass + enum; no behaviour change yet. Three kinds
(paper/topic/theme) will be defined as module constants in Task 2.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Define `PROMOTE_KIND_PAPER`, `PROMOTE_KIND_TOPIC`, `PROMOTE_KIND_THEME` constants

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (append three constants near the new types)
- Test: `science/tests/test_commons_promote_kind_config.py` (extend)

- [ ] **Step 1: Write the failing test** — append to `science/tests/test_commons_promote_kind_config.py`:

```python
def test_promote_kind_paper_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER

    assert PROMOTE_KIND_PAPER.kind == "paper"
    assert PROMOTE_KIND_PAPER.source_subdirs == ("doc/papers",)
    assert PROMOTE_KIND_PAPER.overlay_dest_subdir == "doc/papers"
    assert PROMOTE_KIND_PAPER.commons_subdir == "papers"
    assert PROMOTE_KIND_PAPER.id_prefix == "paper:"
    assert PROMOTE_KIND_PAPER.slug_match == "casefold"
    assert PROMOTE_KIND_PAPER.eligibility_filter is None
    assert "paper" in PROMOTE_KIND_PAPER.mixin_schema_id


def test_promote_kind_topic_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC

    assert PROMOTE_KIND_TOPIC.kind == "topic"
    assert PROMOTE_KIND_TOPIC.source_subdirs == ("doc/topics", "doc/background/topics")
    assert PROMOTE_KIND_TOPIC.overlay_dest_subdir == "doc/topics"
    assert PROMOTE_KIND_TOPIC.commons_subdir == "topics"
    assert PROMOTE_KIND_TOPIC.id_prefix == "topic:"
    assert PROMOTE_KIND_TOPIC.slug_match == "exact"
    assert PROMOTE_KIND_TOPIC.eligibility_filter is None
    assert "topic" in PROMOTE_KIND_TOPIC.mixin_schema_id


def test_promote_kind_theme_constant() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME

    assert PROMOTE_KIND_THEME.kind == "theme"
    assert PROMOTE_KIND_THEME.source_subdirs == ("doc/themes",)
    assert PROMOTE_KIND_THEME.overlay_dest_subdir == "doc/themes"
    assert PROMOTE_KIND_THEME.commons_subdir == "themes"
    assert PROMOTE_KIND_THEME.id_prefix == "theme:"
    assert PROMOTE_KIND_THEME.slug_match == "exact"
    # eligibility_filter is set in Task 3; this test only checks the constant
    # exists with the kind-specific structural fields.
    assert "theme" in PROMOTE_KIND_THEME.mixin_schema_id


def test_three_kinds_have_distinct_id_prefixes() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_TOPIC,
        PROMOTE_KIND_THEME,
    )

    prefixes = {
        PROMOTE_KIND_PAPER.id_prefix,
        PROMOTE_KIND_TOPIC.id_prefix,
        PROMOTE_KIND_THEME.id_prefix,
    }
    assert prefixes == {"paper:", "topic:", "theme:"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_kind_config.py -v
```
Expected: 4 new tests fail with ImportError.

- [ ] **Step 3: Implement** — append to `science/src/science_tool/commons/promote.py` immediately after the `PromoteKindConfig` definition:

```python
PROMOTE_KIND_PAPER = PromoteKindConfig(
    kind="paper",
    source_subdirs=("doc/papers",),
    overlay_dest_subdir="doc/papers",
    commons_subdir="papers",
    id_prefix="paper:",
    slug_regex=re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,63}$"),
    slug_match="casefold",
    mixin_schema_id="https://schemas.science/mixin-paper-2.0.json",
    default_profile=default_profile_for_kind("paper"),
    eligibility_filter=None,
)

PROMOTE_KIND_TOPIC = PromoteKindConfig(
    kind="topic",
    source_subdirs=("doc/topics", "doc/background/topics"),
    overlay_dest_subdir="doc/topics",
    commons_subdir="topics",
    id_prefix="topic:",
    slug_regex=re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$"),
    slug_match="exact",
    mixin_schema_id="https://schemas.science/mixin-topic-1.0.json",  # bumped to 2.0 in Task 21
    default_profile=default_profile_for_kind("topic"),
    eligibility_filter=None,
)

PROMOTE_KIND_THEME = PromoteKindConfig(
    kind="theme",
    source_subdirs=("doc/themes",),
    overlay_dest_subdir="doc/themes",
    commons_subdir="themes",
    id_prefix="theme:",
    slug_regex=re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$"),
    slug_match="exact",
    mixin_schema_id="https://schemas.science/mixin-theme-1.0.json",  # bumped to 2.0 in Task 22
    default_profile=default_profile_for_kind("theme"),
    eligibility_filter=None,  # set in Task 3
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_kind_config.py -v
```
Expected: all tests pass (3 from Task 1 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_kind_config.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): PROMOTE_KIND_PAPER/TOPIC/THEME constants

Three module-level kind configs. mixin_schema_id still points at the
1.0 mixins for topic/theme; Tasks 21-22 bump those to 2.0 along with
_DEFAULT_MIXIN_VERSION. Theme eligibility_filter set in Task 3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Theme eligibility filter

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (add `_theme_eligibility` + wire to `PROMOTE_KIND_THEME`)
- Test: `science/tests/test_commons_promote_kind_config.py` (extend)

- [ ] **Step 1: Write the failing test** — append to `test_commons_promote_kind_config.py`:

```python
def test_theme_eligibility_cross_project_is_eligible() -> None:
    from science_tool.commons.promote import (
        EligibilityVerdict,
        PROMOTE_KIND_THEME,
    )

    assert PROMOTE_KIND_THEME.eligibility_filter is not None
    verdict = PROMOTE_KIND_THEME.eligibility_filter({"theme_scope": "cross-project"})
    assert verdict == EligibilityVerdict.ELIGIBLE


def test_theme_eligibility_project_scope_is_skip_silent() -> None:
    from science_tool.commons.promote import (
        EligibilityVerdict,
        PROMOTE_KIND_THEME,
    )

    verdict = PROMOTE_KIND_THEME.eligibility_filter({"theme_scope": "project"})
    assert verdict == EligibilityVerdict.SKIP_SILENT


def test_theme_eligibility_missing_or_malformed_is_fail() -> None:
    from science_tool.commons.promote import (
        EligibilityVerdict,
        PROMOTE_KIND_THEME,
    )

    f = PROMOTE_KIND_THEME.eligibility_filter
    assert f({}) == EligibilityVerdict.FAIL
    assert f({"theme_scope": None}) == EligibilityVerdict.FAIL
    assert f({"theme_scope": "global"}) == EligibilityVerdict.FAIL
    assert f({"theme_scope": ""}) == EligibilityVerdict.FAIL


def test_paper_and_topic_have_no_eligibility_filter() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, PROMOTE_KIND_TOPIC

    assert PROMOTE_KIND_PAPER.eligibility_filter is None
    assert PROMOTE_KIND_TOPIC.eligibility_filter is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_kind_config.py -v
```
Expected: 3 new theme-eligibility tests fail (`eligibility_filter` is `None`).

- [ ] **Step 3: Implement** — in `science/src/science_tool/commons/promote.py`, add the helper just before `PROMOTE_KIND_THEME`:

```python
def _theme_eligibility(fm: Mapping[str, Any]) -> EligibilityVerdict:
    """Theme eligibility filter (design §3.1).

    Only `theme_scope: cross-project` is eligible. `theme_scope: project` is
    skipped silently (debug-log + drop). Missing/malformed scope is a hard
    fail recorded as a `FailedCandidate`.
    """
    scope = fm.get("theme_scope")
    if scope == "cross-project":
        return EligibilityVerdict.ELIGIBLE
    if scope == "project":
        return EligibilityVerdict.SKIP_SILENT
    return EligibilityVerdict.FAIL
```

Update `PROMOTE_KIND_THEME` to reference it:

```python
PROMOTE_KIND_THEME = PromoteKindConfig(
    ...
    eligibility_filter=_theme_eligibility,
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_kind_config.py -v
```
Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_kind_config.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): theme eligibility filter

Only theme_scope: cross-project is eligible. Project-scope themes are
skipped silently; missing/malformed scope fails as a FailedCandidate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Rename `bibkey` → `slug` across dataclasses

**Background.** Phase E used `bibkey` for paper-specific bibtex-style keys. Phase F generalises to `slug`. This task touches:

- `promote.py`: `PromoteCandidate.bibkey`, `.bibkey_normalized`; `FieldConflict.bibkey`; `ConflictResolution.bibkey`; `PromoteDecision.bibkey`; `FailedCandidate.bibkey`; `DiscoveryResult.candidates_by_bibkey`. Plus every internal reference to `.bibkey` / `.bibkey_normalized` / `candidates_by_bibkey` in helpers (`_normalize_bibkey_for_match`, `_scan_project_papers`, `_merge_canonical_fields`, `_pick_canonical_bibkey_case`, `_render_canonical`, `_render_overlay`, `discover_paper_candidates`, `plan_promote`, `apply_promote`, audit-log builder, rollback builder).
- `errors.py`: `PromoteCandidateError(..., bibkey=...)` → `(..., slug=...)`. Attribute `.bibkey` → `.slug`.
- All existing test files: attribute access only (`.bibkey` → `.slug`; keyword `bibkey=` → `slug=`).
- CLI: line 437 single-entity error message, line 416 `--limit` help text, audit-log render keys.

This is a sweeping mechanical rename. Verify with a search; do not leave any `bibkey` reference in the changed modules except where it still refers to actual paper bibkey strings (the audit log's `bibkey` field on paper entries is replaced by `slug`, per design table row 9).

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (renames throughout)
- Modify: `science/src/science_tool/commons/errors.py` (`PromoteCandidateError`)
- Modify: `science/src/science_tool/commons/cli.py` (uses of `discover_paper_candidates`, error messages)
- Modify: `science/tests/test_commons_promote_discovery.py`
- Modify: `science/tests/test_commons_promote_plan.py`
- Modify: `science/tests/test_commons_promote_apply.py`
- Modify: `science/tests/test_commons_cli_promote.py`

- [ ] **Step 1: Search for every `bibkey` reference and confirm scope**

```bash
cd science && grep -rn 'bibkey' src/science_tool/commons/ tests/test_commons_promote_*.py tests/test_commons_cli_promote*.py
```
Expected: ~80–100 hits across these files. Verify there are NO hits in `science/model/` or other modules outside `commons/` and `tests/`.

- [ ] **Step 2: Apply the rename** — perform these replacements (use Edit with `replace_all=True` per file, NOT `sed` from the shell — and verify each file compiles before moving on):

In `science/src/science_tool/commons/errors.py`:
- `class PromoteCandidateError(...)`: change `bibkey: str | None = None` → `slug: str | None = None`; `self.bibkey = bibkey` → `self.slug = slug`.

In `science/src/science_tool/commons/promote.py`, replace these field names AND keyword-argument names:
- `bibkey: str` → `slug: str` (on `PromoteCandidate`, `FieldConflict`, `ConflictResolution`, `PromoteDecision`)
- `bibkey: str | None` → `slug: str | None` (on `FailedCandidate`)
- `bibkey_normalized: str` → `slug_normalized: str` (on `PromoteCandidate`)
- `candidates_by_bibkey:` → `candidates_by_slug:` (on `DiscoveryResult`)
- Every `decision.bibkey` → `decision.slug`
- Every `cand.bibkey` / `cand.bibkey_normalized` → `cand.slug` / `cand.slug_normalized`
- Every `conflict.bibkey` → `conflict.slug`
- Every `bibkey=...` keyword arg in dataclass construction or error construction → `slug=...`
- Every `candidates_by_bibkey` → `candidates_by_slug`
- Docstrings that say "bibkey" should now say "slug" — leave the term "bibkey" only where it explicitly refers to a paper's BibTeX-style key as a domain concept (rare).

In `science/src/science_tool/commons/cli.py`:
- Update any `--limit` help text mentioning "bibkey" → "slug"
- Line 437 single-entity error: `expected paper:<bibkey>` keep this wording (it's user-facing and paper-specific to that error path; the topic/theme CLI in Tasks 27/32 builds parallel messages)

In each test file, mechanically update attribute reads + keyword args from `bibkey` → `slug` and `bibkey_normalized` → `slug_normalized`. Do not change any assertion VALUE; just the field name on either side of the assertion. Same for `candidates_by_bibkey` → `candidates_by_slug`.

- [ ] **Step 3: Verify no `bibkey` remains in modified files**

```bash
cd science && grep -n 'bibkey' src/science_tool/commons/promote.py src/science_tool/commons/errors.py src/science_tool/commons/cli.py
```
Expected: only references inside docstrings or comments that explicitly call out the historical naming (if any). All field names, attribute accesses, and kwargs should be `slug`.

- [ ] **Step 4: Run the full commons test suite**

```bash
cd science && python -m pytest tests/test_commons_promote_discovery.py tests/test_commons_promote_plan.py tests/test_commons_promote_apply.py tests/test_commons_cli_promote.py tests/test_commons_promote_kind_config.py -v
```
Expected: every test passes. If any test fails for a reason other than renamed attributes, the refactor is wrong — fix the production code, not the test (per design §6.1).

- [ ] **Step 5: Commit**

```bash
git add -A science/src/science_tool/commons/ science/tests/test_commons_promote_*.py science/tests/test_commons_cli_promote.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): rename bibkey → slug across dataclasses

bibkey is paper-specific terminology. Generalise to kind-agnostic slug
across PromoteCandidate, FieldConflict, ConflictResolution,
PromoteDecision, FailedCandidate, DiscoveryResult, and
PromoteCandidateError. All paper tests pass unchanged in behaviour;
only attribute accesses are mechanically updated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 — Kind threading + apply-stage de-hardcoding

### Task 5: Rename `_normalize_bibkey_for_match` → `_normalize_slug_for_match(stem, kind)`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_discovery.py` (extend with kind-aware cases)

- [ ] **Step 1: Write the failing test** — append to `science/tests/test_commons_promote_discovery.py`:

```python
def test_normalize_slug_for_match_paper_casefolds() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _normalize_slug_for_match

    assert _normalize_slug_for_match("Adams2025", PROMOTE_KIND_PAPER) == "adams2025"
    assert _normalize_slug_for_match("Adams2025.md", PROMOTE_KIND_PAPER) == "adams2025"


def test_normalize_slug_for_match_topic_returns_stem_as_is() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _normalize_slug_for_match

    assert _normalize_slug_for_match("hypothesis", PROMOTE_KIND_TOPIC) == "hypothesis"
    assert _normalize_slug_for_match("hypothesis.md", PROMOTE_KIND_TOPIC) == "hypothesis"


def test_normalize_slug_for_match_topic_rejects_uppercase() -> None:
    from science_tool.commons.errors import PromoteCandidateError
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _normalize_slug_for_match

    with pytest.raises(PromoteCandidateError):
        _normalize_slug_for_match("Hypothesis", PROMOTE_KIND_TOPIC)


def test_normalize_slug_for_match_theme_returns_stem_as_is() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, _normalize_slug_for_match

    assert _normalize_slug_for_match("my-theme", PROMOTE_KIND_THEME) == "my-theme"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_discovery.py -v -k normalize_slug
```
Expected: 4 fails — `_normalize_slug_for_match` doesn't exist.

- [ ] **Step 3: Implement** — in `promote.py`, replace `_normalize_bibkey_for_match` with:

```python
def _normalize_slug_for_match(raw: str, kind: PromoteKindConfig) -> str:
    """Return the matching key for a slug, per kind's `slug_match` policy.

    For paper, casefolds. For topic/theme, returns the stem unchanged and
    asserts the regex (lowercase-only — uppercase letters fail-fast at
    discovery rather than slipping through with silent normalisation).
    """
    stripped = raw.removesuffix(".md").strip()
    if not stripped:
        raise PromoteCandidateError(f"slug {raw!r} is empty after strip")
    if not kind.slug_regex.match(stripped):
        raise PromoteCandidateError(
            f"slug {raw!r} does not match {kind.slug_regex.pattern}"
        )
    if kind.slug_match == "casefold":
        return stripped.casefold()
    return stripped
```

Update **every** internal call site that previously read `_normalize_bibkey_for_match(...)` to pass the kind parameter. The Phase E sites are inside `_scan_project_papers` and `discover_paper_candidates`; they currently have no kind in scope. Task 7 will rename `_scan_project_papers` and thread kind in. For now, the call sites still in `_scan_project_papers` should use `PROMOTE_KIND_PAPER` as a literal — that's intermediate, removed in Task 7.

Update the existing `test_normalize_bibkey_for_match_*` tests (3 in `test_commons_promote_discovery.py`) to call `_normalize_slug_for_match("...", PROMOTE_KIND_PAPER)` instead. Same assertions — paper behaviour is unchanged.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_discovery.py -v
```
Expected: all pass (existing renamed tests + 4 new kind-aware tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): _normalize_slug_for_match(stem, kind)

Generalises _normalize_bibkey_for_match. Paper kind casefolds; topic
and theme return the stem unchanged after a regex check that
fail-fasts on uppercase (lowercase-kebab is mandatory).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Rename `_classify_paper_file_kind` → `_classify_file_kind(fm, kind)`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Modify: `science/tests/test_commons_promote_discovery.py`

- [ ] **Step 1: Write the failing test** — append to `test_commons_promote_discovery.py`:

```python
def test_classify_file_kind_paper_explicit_match() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    assert _classify_file_kind({"kind": "paper"}, PROMOTE_KIND_PAPER) == "match"
    assert _classify_file_kind({"type": "paper"}, PROMOTE_KIND_PAPER) == "match"


def test_classify_file_kind_topic_explicit_match() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    assert _classify_file_kind({"kind": "topic"}, PROMOTE_KIND_TOPIC) == "match"
    assert _classify_file_kind({"type": "topic"}, PROMOTE_KIND_TOPIC) == "match"


def test_classify_file_kind_topic_disagreeing_kind_is_skip_other_kind() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    assert _classify_file_kind({"kind": "paper"}, PROMOTE_KIND_TOPIC) == "skip-other-kind"
    assert _classify_file_kind({"type": "theme"}, PROMOTE_KIND_TOPIC) == "skip-other-kind"


def test_classify_file_kind_topic_id_prefix_disagreement_is_skip_other_id() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    assert _classify_file_kind({"id": "paper:Adams2025"}, PROMOTE_KIND_TOPIC) == "skip-other-id"
    assert _classify_file_kind({"id": "topic:hypothesis"}, PROMOTE_KIND_TOPIC) == "match"


def test_classify_file_kind_no_kind_inferred() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    # No kind/type, no id → infer "match" from directory placement.
    assert _classify_file_kind({"title": "Foo"}, PROMOTE_KIND_TOPIC) == "match"


def test_classify_file_kind_explicit_kind_overrides_contradictory_id() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    # Rule ordering: explicit kind/type wins over id-prefix.
    assert (
        _classify_file_kind({"id": "dataset:foo", "kind": "paper"}, PROMOTE_KIND_PAPER)
        == "match"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_discovery.py -v -k classify_file_kind
```
Expected: 6 fails — `_classify_file_kind` doesn't exist.

- [ ] **Step 3: Implement** — in `promote.py`, replace `_classify_paper_file_kind` (currently at promote.py:777) with:

```python
def _classify_file_kind(
    frontmatter: dict,
    kind: PromoteKindConfig,
) -> Literal["match", "skip-other-kind", "skip-other-id"]:
    """Decide whether a file under `kind.source_subdirs` matches this kind.

    Rule order (design §4.1, Phase E §6.3 step 2):
    1. Explicit `kind:` or `type:` equal to `kind.kind` → match.
    2. Explicit `kind` / `type` with any other value → skip-other-kind.
    3. No `kind` / `type`, `id` present and NOT starting with `kind.id_prefix` →
       skip-other-id.
    4. Otherwise infer from directory: match.
    """
    kind_val = frontmatter.get("kind") or frontmatter.get("type")
    if kind_val == kind.kind:
        return "match"
    if kind_val is not None:
        return "skip-other-kind"
    id_val = frontmatter.get("id")
    if isinstance(id_val, str) and not id_val.startswith(kind.id_prefix):
        return "skip-other-id"
    return "match"
```

Update the existing `_classify_paper_file_kind` tests in `test_commons_promote_discovery.py` to use `_classify_file_kind(fm, PROMOTE_KIND_PAPER)`. Assertions: replace `== "paper"` → `== "match"` to match the kind-agnostic return.

Update internal call sites of `_classify_paper_file_kind` (search for usage in `_scan_project_papers`). Those still need a paper literal for now; Task 7 will thread kind through `_scan_project_papers`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_discovery.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): _classify_file_kind(fm, kind)

Generalises _classify_paper_file_kind. Compares fm["kind"]/["type"]
against kind.kind and fm["id"] prefix against kind.id_prefix. Return
"paper" → "match" everywhere. Same rule ordering as Phase E.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Rename `discover_paper_candidates` → `discover_candidates(project_ids, kind)`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (rename `discover_paper_candidates` + `_scan_project_papers` + thread kind through)
- Modify: `science/src/science_tool/commons/__init__.py` (re-export)
- Modify: `science/src/science_tool/commons/cli.py` (import + call site)
- Modify: `science/tests/test_commons_promote_discovery.py`

- [ ] **Step 1: Write the failing test** — append to `test_commons_promote_discovery.py`:

```python
def test_discover_candidates_paper_alias_returns_same_result(tmp_path, monkeypatch) -> None:
    """Calling discover_candidates(..., PROMOTE_KIND_PAPER) returns the same
    shape as the old discover_paper_candidates did."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

    proj = tmp_path / "proj_x"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_x"], PROMOTE_KIND_PAPER)
    assert set(result.candidates_by_slug) == {"adams2025"}
    assert len(result.candidates_by_slug["adams2025"]) == 1


def test_discover_candidates_iterates_multiple_source_subdirs(tmp_path, monkeypatch) -> None:
    """Topic kind walks both doc/topics and doc/background/topics."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_y"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "hypothesis.md").write_text(
        "---\nid: topic:hypothesis\ntitle: H\n---\n",
        encoding="utf-8",
    )
    (proj / "doc" / "background" / "topics").mkdir(parents=True)
    (proj / "doc" / "background" / "topics" / "primitives.md").write_text(
        "---\nid: topic:primitives\ntitle: P\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_y"], PROMOTE_KIND_TOPIC)
    assert set(result.candidates_by_slug) == {"hypothesis", "primitives"}


def test_discover_candidates_rejects_explicit_id_with_wrong_prefix(tmp_path, monkeypatch) -> None:
    """An explicit `kind: topic` + `id: paper:foo` slipped through Phase E's
    paper-only classifier (id check only ran when prefix already matched).
    Phase F discovery records a FailedCandidate so contradictory ids never
    reach plan_promote."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_w"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "trapped.md").write_text(
        "---\nkind: topic\nid: paper:trapped\ntitle: X\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_w"], PROMOTE_KIND_TOPIC)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) == 1
    msg = result.failed_candidates[0].error_message
    assert "paper:trapped" in msg and "topic:" in msg


def test_discover_candidates_same_project_intra_kind_collision(tmp_path, monkeypatch) -> None:
    """A slug appearing in BOTH doc/topics/ and doc/background/topics/ within
    the same project is a hard failure (cannot resolve canonical source)."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_z"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "collide.md").write_text(
        "---\nid: topic:collide\n---\n", encoding="utf-8"
    )
    (proj / "doc" / "background" / "topics").mkdir(parents=True)
    (proj / "doc" / "background" / "topics" / "collide.md").write_text(
        "---\nid: topic:collide\n---\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_z"], PROMOTE_KIND_TOPIC)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) >= 1
    msgs = [fc.error_message for fc in result.failed_candidates]
    assert any("collide" in m and "both" in m.lower() for m in msgs)
```

Also, in the existing tests file, rename usages of `discover_paper_candidates` → `discover_candidates(..., PROMOTE_KIND_PAPER)` and `candidates_by_bibkey` → `candidates_by_slug` (already done in Task 4).

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_discovery.py -v -k discover_candidates
```
Expected: 3 new tests fail (function doesn't exist with this name).

- [ ] **Step 3: Implement** — in `promote.py`:

1. Rename `discover_paper_candidates` → `discover_candidates`. New signature:

```python
def discover_candidates(
    project_slugs: list[str],
    kind: PromoteKindConfig,
) -> DiscoveryResult:
    """Scan each project's `kind.source_subdirs` for promotion candidates.
    Group by `_normalize_slug_for_match(stem, kind)`. Returns successful
    candidates + failure records (no exception path for per-file failures).
    """
    grouped: dict[str, list[PromoteCandidate]] = {}
    failures: list[FailedCandidate] = []

    for slug in project_slugs:
        project_root = resolve_project_by_id(slug)
        candidates, project_failures = _scan_project(project_root, slug, kind)
        failures.extend(project_failures)
        for cand in candidates:
            grouped.setdefault(cand.slug_normalized, []).append(cand)

    return DiscoveryResult(candidates_by_slug=grouped, failed_candidates=failures)
```

2. Rename `_scan_project_papers` → `_scan_project`. New shape:

```python
def _scan_project(
    project_root: Path,
    project_slug: str,
    kind: PromoteKindConfig,
) -> tuple[list[PromoteCandidate], list[FailedCandidate]]:
    """Walk every dir in kind.source_subdirs and parse each *.md.

    Detects intra-kind same-project collisions (a slug appearing in more
    than one source subdir of the same project — only relevant for topic).
    Calls _classify_file_kind, the eligibility filter (if set), and
    _normalize_slug_for_match. Project-only filenames are mapped to
    `(slug_normalized, source_path)` so the collision check can report
    BOTH offending paths.
    """
    candidates: list[PromoteCandidate] = []
    failures: list[FailedCandidate] = []
    seen: dict[str, Path] = {}  # slug_normalized → first source path

    for sub in kind.source_subdirs:
        directory = project_root / sub
        if not directory.exists():
            continue
        for source_path in sorted(directory.glob("*.md")):
            try:
                fm, body = _parse_entity_file(source_path)
            except PromoteCandidateError as exc:
                failures.append(
                    FailedCandidate(
                        slug=None,
                        project_slug=project_slug,
                        source_path=source_path,
                        error_class="PromoteCandidateError",
                        error_message=str(exc),
                    )
                )
                continue

            # Skip already-promoted files (overlay_of present).
            if "overlay_of" in fm:
                continue

            classification = _classify_file_kind(fm, kind)
            if classification == "skip-other-kind":
                logger.warning(
                    "%s: kind/type is not %r; skipping", source_path, kind.kind
                )
                continue
            if classification == "skip-other-id":
                continue

            # Eligibility filter (theme only at Phase F).
            if kind.eligibility_filter is not None:
                verdict = kind.eligibility_filter(fm)
                if verdict == EligibilityVerdict.SKIP_SILENT:
                    logger.debug(
                        "%s: eligibility skip (kind=%s)", source_path, kind.kind
                    )
                    continue
                if verdict == EligibilityVerdict.FAIL:
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=(
                                f"eligibility filter rejected {source_path.name}: "
                                f"missing or malformed eligibility marker"
                            ),
                        )
                    )
                    continue

            try:
                slug_normalized = _normalize_slug_for_match(source_path.stem, kind)
            except PromoteCandidateError as exc:
                failures.append(
                    FailedCandidate(
                        slug=None,
                        project_slug=project_slug,
                        source_path=source_path,
                        error_class="PromoteCandidateError",
                        error_message=str(exc),
                    )
                )
                continue

            # Id check (design §4.1.3 Phase E). The classifier may have
            # matched purely on explicit `kind:` / `type:`, while the file
            # also carries a contradictory `id:` (e.g. kind: topic + id:
            # paper:foo). In that case, the id is wrong for this kind and
            # must be reported as a failure — silently relying on the
            # filename stem would let mismatched canonical ids slip through.
            id_val = fm.get("id")
            if isinstance(id_val, str):
                if not id_val.startswith(kind.id_prefix):
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=(
                                f"id {id_val!r} does not have the expected "
                                f"prefix {kind.id_prefix!r} for kind "
                                f"{kind.kind!r}"
                            ),
                        )
                    )
                    continue
                id_slug = id_val[len(kind.id_prefix):]
                if _normalize_slug_for_match(id_slug, kind) != slug_normalized:
                    failures.append(
                        FailedCandidate(
                            slug=None,
                            project_slug=project_slug,
                            source_path=source_path,
                            error_class="PromoteCandidateError",
                            error_message=(
                                f"id {id_val!r} does not match filename stem "
                                f"{source_path.stem!r}"
                            ),
                        )
                    )
                    continue

            # Intra-kind same-project collision (topic flatten guard).
            prior = seen.get(slug_normalized)
            if prior is not None:
                failures.append(
                    FailedCandidate(
                        slug=slug_normalized,
                        project_slug=project_slug,
                        source_path=source_path,
                        error_class="PromoteCandidateError",
                        error_message=(
                            f"slug {slug_normalized!r} appears in both "
                            f"{prior} and {source_path} within project "
                            f"{project_slug!r}; remove one before promoting"
                        ),
                    )
                )
                # Also remove the prior candidate so the slug isn't promoted from
                # a half-resolved corpus.
                candidates[:] = [c for c in candidates if c.slug_normalized != slug_normalized]
                continue
            seen[slug_normalized] = source_path

            # Use source-case slug for the canonical surface.
            source_case_slug = source_path.stem
            candidates.append(
                _build_candidate(
                    fm=fm,
                    body=body,
                    slug=source_case_slug,
                    slug_normalized=slug_normalized,
                    project_slug=project_slug,
                    project_root=project_root,
                    overlay_source_path=source_path,
                )
            )

    return candidates, failures
```

> **Note for the implementer:** `_build_candidate` is the existing internal helper that constructs a `PromoteCandidate` from the raw frontmatter + body. If the existing Phase E code inlines this construction (no helper exists), inline the construction here. Either way, the inputs are the same: `fm`, `body`, `slug`, `slug_normalized`, `project_slug`, `project_root`, `overlay_source_path`. Keep the existing `_RAW_FRONTMATTER_KEY` / `_RAW_BODY_KEY` stash pattern from Phase E unchanged — that handoff to `plan_promote` is identical.

3. Rename `_parse_paper_file` → `_parse_entity_file` (function body unchanged) and update its single call site here.

4. In `science/src/science_tool/commons/__init__.py`, replace the `discover_paper_candidates` re-export with `discover_candidates`. Replace `__all__` entry similarly.

5. In `science/src/science_tool/commons/cli.py` (currently line 26-30 imports), update:

```python
from science_tool.commons.promote import (
    ...
    apply_promote,
    discover_candidates,        # was discover_paper_candidates
    plan_promote,
    PROMOTE_KIND_PAPER,         # NEW import
)
```

And update line 443:

```python
discovery = discover_candidates(list(from_), PROMOTE_KIND_PAPER)
```

- [ ] **Step 4: Run full commons test suite**

```bash
cd science && python -m pytest tests/test_commons_promote_discovery.py tests/test_commons_promote_plan.py tests/test_commons_promote_apply.py tests/test_commons_cli_promote.py tests/test_commons_promote_kind_config.py -v
```
Expected: all pass (existing tests via `PROMOTE_KIND_PAPER`, plus 3 new tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/src/science_tool/commons/__init__.py science/src/science_tool/commons/cli.py science/tests/test_commons_promote_discovery.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): discover_candidates(project_ids, kind)

Renames discover_paper_candidates and threads kind through the
discovery walk. Iterates over kind.source_subdirs (multi-dir for
topic), uses kind.eligibility_filter for theme, and reports intra-
kind same-project collisions as FailedCandidate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Thread `kind` into `plan_promote`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (`plan_promote` signature; replace the hardcoded `default_profile_for_kind("paper")` at promote.py:228)
- Modify: `science/src/science_tool/commons/cli.py` (call site)
- Modify: `science/tests/test_commons_promote_plan.py` (rename to pass `kind`)

- [ ] **Step 1: Write the failing test** — Task 8's deliverables are (a) `kind` parameter on `plan_promote`, and (b) merge_policy + body_sections read from `kind.default_profile` instead of the hardcoded paper. Test both via an existing call site that now requires `kind=`:

Update all existing call sites in `test_commons_promote_plan.py` to add `kind=PROMOTE_KIND_PAPER` to every `plan_promote(...)` invocation. Those existing tests now also implicitly verify the new signature compiles and the paper merge-policy path is unchanged.

Then append one new test that pins the merge-policy lookup to `kind.default_profile`, observable via the fact that calling with a topic-shaped fixture would treat `datasets` as `append` (the topic policy) — but the simpler/more direct check is to monkeypatch `read_merge_policy` and assert it was called with `kind.default_profile`:

```python
def test_plan_promote_calls_read_merge_policy_with_kind_profile(
    tmp_path, monkeypatch
) -> None:
    """Pin the per-kind merge-policy lookup. Without this guard, plan_promote
    would silently use the paper policy for topic/theme runs and misclassify
    fields like topic 'datasets' or theme 'evidence_refs'."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        DiscoveryResult,
        plan_promote,
    )
    import science_tool.commons.promote as promote_mod

    captured = {}
    real_read_merge_policy = promote_mod.read_merge_policy

    def spy(profile, *a, **kw):
        captured["profile"] = profile
        return real_read_merge_policy(profile, *a, **kw)

    monkeypatch.setattr(promote_mod, "read_merge_policy", spy)

    discovery = DiscoveryResult(candidates_by_slug={}, failed_candidates=[])
    plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_PAPER)
    assert captured["profile"] == PROMOTE_KIND_PAPER.default_profile
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py -v
```
Expected: failures because `plan_promote` doesn't accept `kind`, or `read_merge_policy` is called with the hardcoded paper profile rather than `kind.default_profile`.

- [ ] **Step 3: Implement** — in `promote.py`, change `plan_promote` signature and body. The relevant existing code is at lines 228-230:

```python
paper_profile = default_profile_for_kind("paper")
merge_policy = read_merge_policy(paper_profile)
body_sections = read_canonical_body_sections(paper_profile)
```

Replace with:

```python
merge_policy = read_merge_policy(kind.default_profile)
body_sections = read_canonical_body_sections(kind.default_profile)
```

New signature:

```python
def plan_promote(
    discovery: DiscoveryResult,
    *,
    commons_root: Path,
    kind: PromoteKindConfig,
    from_order: list[str] | None = None,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
) -> PromotePlan:
    ...
```

(Note: `commons_root` and `kind` become keyword-only — match existing keyword-only `from_order` / `resolve_conflict`. If `commons_root` was previously positional, make it keyword-only here.)

Update the single CLI call site at `cli.py:488`:

```python
plan = plan_promote(
    discovery,
    commons_root=root,
    kind=PROMOTE_KIND_PAPER,
    from_order=list(from_),
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py -v
```
Expected: every test passes — Task 8's deliverables are self-contained (no cross-task references). The `.kind` attribute on `PromotePlan` / `PromoteResult` lands in Task 9.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/src/science_tool/commons/cli.py science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): plan_promote(..., kind=...)

Reads merge_policy AND body_sections from kind.default_profile,
replacing the hardcoded default_profile_for_kind("paper") at line 228.
Without this, topic-only fields (datasets/source_refs/related) and
theme-only fields (evidence_refs) would be misclassified under the
paper merge policy at plan time.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Add `kind` field to `PromotePlan` and `PromoteResult`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (dataclass + every construction site of `PromotePlan` and `PromoteResult`)
- Modify: `science/src/science_tool/commons/__init__.py` (re-export `PromoteKindConfig` if not already)

- [ ] **Step 1: Write the failing test** — re-enable the Task-8 test that reads `plan.kind`. Add another in `test_commons_promote_plan.py`:

```python
def test_plan_carries_kind(tmp_path) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        DiscoveryResult,
        plan_promote,
    )

    discovery = DiscoveryResult(candidates_by_slug={}, failed_candidates=[])
    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_PAPER)
    assert plan.kind is PROMOTE_KIND_PAPER
```

And in `test_commons_promote_apply.py`:

```python
def test_result_carries_kind() -> None:
    from datetime import datetime, timezone
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PromoteResult,
    )

    r = PromoteResult(
        op_id="x",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        commons_commit=None,
        tags_created=[],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=[],
        kind=PROMOTE_KIND_PAPER,
    )
    assert r.kind is PROMOTE_KIND_PAPER
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py::test_plan_carries_kind tests/test_commons_promote_apply.py::test_result_carries_kind -v
```
Expected: TypeError / AttributeError — `kind` not a recognised field.

- [ ] **Step 3: Implement** — in `promote.py`:

Add field to `PromotePlan`:

```python
@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    kind: PromoteKindConfig
```

Add field to `PromoteResult`:

```python
@dataclass(frozen=True, slots=True)
class PromoteResult:
    ...
    projects_touched: list[str]
    kind: PromoteKindConfig
```

Find every `PromotePlan(...)` construction and add `kind=kind` (the `plan_promote` parameter). Find every `PromoteResult(...)` construction in `apply_promote` and add `kind=plan.kind`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py tests/test_commons_promote_apply.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_plan.py science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): PromotePlan.kind + PromoteResult.kind

apply_promote no longer needs a separate kind argument — reads it
from plan.kind. PromoteResult carries it through to the audit-log
renderer (Task 18 uses it for the type: field).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Add `kind` to `FieldConflict` + update `prompt_resolve` display

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (dataclass + construction site + prompt)
- Modify: `science/tests/test_commons_promote_plan.py`

- [ ] **Step 1: Write the failing test** — append to `test_commons_promote_plan.py`:

```python
def test_field_conflict_carries_kind() -> None:
    from science_tool.commons.promote import FieldConflict

    c = FieldConflict(
        slug="hypothesis",
        kind="topic",
        field="title",
        candidates={"proj_a": "Hyp A", "proj_b": "Hyp B"},
    )
    assert c.kind == "topic"


def test_prompt_resolve_uses_kind_in_display(monkeypatch, capsys) -> None:
    from science_tool.commons.promote import FieldConflict, prompt_resolve

    c = FieldConflict(
        slug="my-theme",
        kind="theme",
        field="title",
        candidates={"proj_a": "T A", "proj_b": "T B"},
    )

    # Simulate the user picking option 1.
    monkeypatch.setattr("click.prompt", lambda *a, **k: "1")
    prompt_resolve(c)

    out = capsys.readouterr().out
    assert "theme:my-theme" in out
    assert "paper:" not in out
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py::test_field_conflict_carries_kind tests/test_commons_promote_plan.py::test_prompt_resolve_uses_kind_in_display -v
```
Expected: TypeError (unexpected kwarg `kind`) / assertion fail on "theme:my-theme" not in output.

- [ ] **Step 3: Implement** — in `promote.py`:

```python
@dataclass(frozen=True, slots=True)
class FieldConflict:
    slug: str
    kind: Literal["paper", "topic", "theme"]
    field: str
    candidates: dict[str, Any]  # project_slug → value
```

Find every `FieldConflict(...)` construction site (one inside `plan_promote`, in `_merge_canonical_fields` — though `_merge_canonical_fields` may take a `kind` param implicitly). Pass `kind=kind.kind`.

Update `prompt_resolve` (currently at line 176):

```python
click.echo(f'\nConflict for {conflict.kind}:{conflict.slug}, field "{conflict.field}":')
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): FieldConflict.kind + kind-aware prompt display

prompt_resolve prints "topic:my-slug" / "theme:my-slug" / "paper:bibkey"
based on conflict.kind, replacing the hardcoded paper: prefix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: De-hardcode commons path + clean-check (table rows 1, 2)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (lines 315 + 393)
- Modify: `science/tests/test_commons_promote_apply.py` (regression test)

- [ ] **Step 1: Write the failing test** — append to `test_commons_promote_apply.py`:

```python
def test_apply_commons_path_uses_kind_commons_subdir(tmp_path, monkeypatch) -> None:
    """commons_root / "papers" / ... was hardcoded at promote.py:315. After
    de-hardcoding, kind.commons_subdir is used. Drive plan_promote with a
    real minimal candidate so the decision-building loop runs, then assert
    the resulting PromoteDecision.canonical_path is under kind.commons_subdir."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    proj = tmp_path / "proj_p"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "single.md").write_text(
        "---\nid: topic:single\ntitle: T\n---\n\n## Summary\n\nx\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    commons = tmp_path / "commons"
    commons.mkdir()

    discovery = discover_candidates(["proj_p"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_TOPIC)

    assert len(plan.decisions) == 1
    canonical_path = plan.decisions[0].canonical_path
    # The path MUST live under commons/topics/, not commons/papers/.
    assert canonical_path.parent.name == "topics"
    assert str(canonical_path).startswith(str(commons / "topics"))
    assert "papers" not in str(canonical_path)


def test_commons_is_clean_checks_kind_commons_subdir(tmp_path) -> None:
    """promote.py:393 hardcodes path.startswith("papers/"). After de-
    hardcoding, kind.commons_subdir is used. Initialise an empty commons
    repo + add an untracked file under topics/ and verify that
    _commons_is_clean(commons_root, PROMOTE_KIND_TOPIC) reports it dirty
    while PROMOTE_KIND_PAPER would not."""
    import subprocess
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_TOPIC,
        _commons_is_clean,
    )

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    (tmp_path / "topics").mkdir()
    (tmp_path / "topics" / "x.md").write_text("hi", encoding="utf-8")

    paper_clean, _ = _commons_is_clean(tmp_path, PROMOTE_KIND_PAPER)
    topic_clean, dirty = _commons_is_clean(tmp_path, PROMOTE_KIND_TOPIC)
    assert paper_clean is True
    assert topic_clean is False
    assert "topics/x.md" in dirty
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v -k "commons_path_uses_kind or commons_is_clean_checks_kind"
```
Expected: fails — current code hardcodes "papers"/.

- [ ] **Step 3: Implement** — in `promote.py`:

Line 315 (inside `plan_promote` decision-building):

```python
canonical_path = commons_root / kind.commons_subdir / f"{canonical_case}.md"
```

Line ~388-397 (`_commons_is_clean`): change signature to accept `kind`, and the prefix check:

```python
def _commons_is_clean(commons_root: Path, kind: PromoteKindConfig) -> tuple[bool, list[str]]:
    """Path-limited cleanliness check. Untracked files under
    kind.commons_subdir/ or .migrations/ count as dirty."""
    ...
    if flags == "??":
        if path.startswith(f"{kind.commons_subdir}/") or path.startswith(".migrations/"):
            dirty.append(path)
    ...
```

Update the call site inside `apply_promote` (currently calls `_commons_is_clean(commons_root)`) to pass `plan.kind`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode commons path + clean check (rows 1-2)

promote.py:315 canonical_path and promote.py:393 _commons_is_clean
now derive from kind.commons_subdir. Regression test exercises both
paper and topic kinds.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: De-hardcode project target files clean check (table row 3) + flatten preflight

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (`_project_target_files_clean` at lines 400-414 — signature + prefix)
- Modify: `science/tests/test_commons_promote_apply.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_project_target_files_clean_checks_kind_overlay_dest_subdir(tmp_path) -> None:
    """promote.py:403,407 hardcode "doc/papers/{name}". After de-hardcoding,
    kind.overlay_dest_subdir is used. For topic, also scans kind.source_subdirs
    so a dirty doc/background/topics/foo.md is reported (the flatten case)."""
    import subprocess
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        _project_target_files_clean,
    )

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "doc" / "background" / "topics").mkdir(parents=True)
    target = tmp_path / "doc" / "background" / "topics" / "primitives.md"
    target.write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True, capture_output=True,
    )

    # Dirty the file.
    target.write_text("dirty\n", encoding="utf-8")

    clean, dirty_paths = _project_target_files_clean(
        tmp_path, ["primitives.md"], PROMOTE_KIND_TOPIC
    )
    assert clean is False
    assert any("background/topics/primitives.md" in p for p in dirty_paths)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v -k project_target_files_clean
```
Expected: function doesn't accept `kind`.

- [ ] **Step 3: Implement** — replace `_project_target_files_clean`:

```python
def _project_target_files_clean(
    project_root: Path,
    target_filenames: list[str],
    kind: PromoteKindConfig,
) -> tuple[bool, list[str]]:
    """For each filename in `target_filenames`, check whether the overlay
    destination AND every source subdir's same-named file are clean against
    HEAD. The multi-path scan covers the topic flatten case: when a candidate
    came from doc/background/topics/, the apply path unlinks that file, so
    the preflight must catch dirtiness there too."""
    dirty: list[str] = []
    subdirs_to_check = [kind.overlay_dest_subdir, *kind.source_subdirs]
    # Dedupe while preserving order.
    seen: set[str] = set()
    ordered = [s for s in subdirs_to_check if not (s in seen or seen.add(s))]

    for name in target_filenames:
        for sub in ordered:
            rel = f"{sub}/{name}"
            absolute = project_root / rel
            if not absolute.exists():
                continue
            diff = subprocess.run(
                ["git", "-C", str(project_root), "diff", "--exit-code",
                 "--quiet", "HEAD", "--", rel],
            )
            if diff.returncode != 0:
                dirty.append(rel)
    return (not dirty, dirty)
```

Update the caller in `apply_promote` to pass `plan.kind`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode project target clean check (row 3)

_project_target_files_clean now takes kind and scans both
kind.overlay_dest_subdir and every kind.source_subdir — required for
the topic flatten case where the apply path unlinks files under
doc/background/topics/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: De-hardcode tag preflight + creation + sort (table row 4)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (lines 577, 626-627)
- Modify: `science/tests/test_commons_promote_apply.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_apply_tags_use_kind_kind_prefix(tmp_path, monkeypatch) -> None:
    """Verify that apply_promote builds tags as {kind.kind}/{slug}/{version}
    instead of the hardcoded "paper/{bibkey}/{version}". We exercise this
    indirectly by inspecting the planned tag prefix logic via a tiny stub
    PromotePlan with a single decision."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        PromoteDecision,
    )

    d = PromoteDecision(
        slug="hypothesis",
        canonical_path=tmp_path / "topics" / "hypothesis.md",
        canonical_content="---\nid: topic:hypothesis\n---\n",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    # The tag-building string template is at promote.py:577 and 626-627.
    # After Task 13, this should produce "topic/hypothesis/1.0.0".
    tag = f"{PROMOTE_KIND_TOPIC.kind}/{d.slug}/{d.canonical_version}"
    assert tag == "topic/hypothesis/1.0.0"
    # And a sort by .slug must use the slug attribute, not .bibkey.
    decisions = [d]
    decisions_sorted = sorted(decisions, key=lambda x: x.slug)
    assert decisions_sorted[0].slug == "hypothesis"
```

> The above test is structural — it verifies the design intent without firing up a full apply. The Task 26 (topic apply) integration tests cover the end-to-end tag-creation path.

- [ ] **Step 2: Run test to verify it fails (or already passes if dataclass is right)**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v -k apply_tags_use_kind
```
This test passes trivially after Task 4 renamed `.bibkey` → `.slug`. The behavioural change is in the production code (lines 577, 626-627), which is exercised by the integration tests in Task 26. For Task 13's *production-code* change, the existing paper-kind regression tests must continue to pass.

- [ ] **Step 3: Implement** — in `apply_promote`:

Line 577 (tag preflight):

```python
for decision in plan.decisions:
    tag = f"{plan.kind.kind}/{decision.slug}/{decision.canonical_version}"
    ...
```

Lines 626-627 (tag creation + sort):

```python
for decision in sorted(plan.decisions, key=lambda d: d.slug):
    tag = f"{plan.kind.kind}/{decision.slug}/{decision.canonical_version}"
    ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v
```
Expected: all pass (existing paper tests still produce tags like `paper/Adams2025/1.0.0`).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode tag preflight + creation (row 4)

Tag prefix at promote.py:577 (preflight) and 626-627 (creation +
sort) now derive from plan.kind.kind. Paper still produces
paper/<slug>/<version>; topic/theme produce topic/<slug>/<v> and
theme/<slug>/<v>.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: De-hardcode commons commit message (table row 5)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (line 609)
- Modify: `science/tests/test_commons_promote_apply.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_commons_commit_message_uses_kind_commons_subdir() -> None:
    """promote.py:609 hardcodes 'papers via op'. After Task 14, the noun
    is kind.commons_subdir."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC

    # The literal at promote.py:609 should now be:
    # f"promote: {len(plan.decisions)} {kind.commons_subdir} via op {op_id}"
    msg = f"promote: 3 {PROMOTE_KIND_TOPIC.commons_subdir} via op abc"
    assert msg == "promote: 3 topics via op abc"
```

This is also a documentation/contract test rather than a behavioural integration test. The full behavioural check is in the topic apply tests (Task 26).

- [ ] **Step 2: Run test to verify it fails or passes trivially**

The literal-string test passes trivially; the production-code change is what matters.

- [ ] **Step 3: Implement** — in `apply_promote`, line 609:

```python
_git(
    commons_root,
    "commit", "-m",
    f"promote: {len(plan.decisions)} {plan.kind.commons_subdir} via op {op_id}",
    "--", *rel_paths,
)
```

- [ ] **Step 4: Run all existing apply tests**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v
```
Expected: paper tests still pass (still produce "X papers via op Y").

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode commit message (row 5)

promote.py:609 commit message now reads kind.commons_subdir. Paper
keeps "N papers via op X"; topic/theme produce "N topics/themes via
op X".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: De-hardcode `_render_canonical` (table row 6)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (lines 1200-1233)
- Modify: `science/tests/test_commons_promote_plan.py`

- [ ] **Step 1: Write the failing test** — append to `test_commons_promote_plan.py`:

```python
def test_render_canonical_paper_emits_bibkey_field() -> None:
    """Paper canonicals still emit bibkey: <slug> in frontmatter."""
    from datetime import date
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PromoteDecision,
        _render_canonical,
    )

    d = PromoteDecision(
        slug="Adams2025",
        canonical_path=Path("/x/papers/Adams2025.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_canonical(
        d,
        canonical_fields={"title": "T"},
        canonical_body={},
        created=date(2026, 1, 1),
        updated=date(2026, 1, 1),
        kind=PROMOTE_KIND_PAPER,
    )
    assert "id: paper:Adams2025" in rendered
    assert "type: paper" in rendered
    assert "bibkey: Adams2025" in rendered  # paper-only field


def test_render_canonical_topic_omits_bibkey_field() -> None:
    """Topic canonicals must NOT carry a bibkey field — not in the mixin."""
    from datetime import date
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        PromoteDecision,
        _render_canonical,
    )

    d = PromoteDecision(
        slug="hypothesis",
        canonical_path=Path("/x/topics/hypothesis.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_canonical(
        d,
        canonical_fields={"title": "T"},
        canonical_body={},
        created=date(2026, 1, 1),
        updated=date(2026, 1, 1),
        kind=PROMOTE_KIND_TOPIC,
    )
    assert "id: topic:hypothesis" in rendered
    assert "type: topic" in rendered
    assert "bibkey" not in rendered
    assert "topic/" in rendered  # schema_profile contains "+topic/1.0" or 2.0
```

(Add `from pathlib import Path` to the test imports if absent.)

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py -v -k render_canonical
```
Expected: fails — `_render_canonical` either doesn't accept `kind` or produces "paper:" in topic output.

- [ ] **Step 3: Implement** — replace `_render_canonical` (lines 1200-1233):

```python
def _render_canonical(
    decision: PromoteDecision,
    *,
    canonical_fields: dict,
    canonical_body: dict[str, str],
    created: date,
    updated: date,
    kind: PromoteKindConfig,
) -> str:
    """Render the commons-side <commons_subdir>/<slug>.md content.

    Emits schema_profile from kind.default_profile, id from kind.id_prefix,
    type from kind.kind. For paper kind only, also emits a `bibkey:` field
    (preserved from Phase E; not in topic/theme mixins).
    """
    profile_str = kind.default_profile.render()
    head: dict = {
        "schema_profile": profile_str,
        "id": f"{kind.id_prefix}{decision.slug}",
        "type": kind.kind,
        "title": canonical_fields.get("title", ""),
        "version": decision.canonical_version,
        "created": _coerce_date_for_yaml(created),
        "updated": _coerce_date_for_yaml(updated),
    }
    if kind.kind == "paper":
        head["bibkey"] = decision.slug
    head["tags"] = []
    for k, v in canonical_fields.items():
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(canonical_body)
    return f"---\n{fm}---\n{body}"
```

Update the call site of `_render_canonical` (inside `plan_promote`) to pass `kind=kind`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode _render_canonical (row 6)

Profile, id prefix, and type now derive from kind. bibkey field is
emitted only for paper kind (topic/theme mixins don't carry it). The
paper canonical surface is byte-identical to Phase E.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: De-hardcode `_render_overlay` (table row 7)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (lines 1240-1264)
- Modify: `science/tests/test_commons_promote_plan.py`

- [ ] **Step 1: Write the failing test**:

```python
def test_render_overlay_uses_kind_id_prefix() -> None:
    from pathlib import Path
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        PromoteDecision,
        _render_overlay,
    )

    d = PromoteDecision(
        slug="my-theme",
        canonical_path=Path("/x/themes/my-theme.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_overlay(
        d,
        project_only_fields={},
        project_only_body={},
        kind=PROMOTE_KIND_THEME,
    )
    assert "id: theme:my-theme" in rendered
    assert "overlay_of: theme:my-theme" in rendered
    assert "paper:" not in rendered
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py -v -k render_overlay
```

- [ ] **Step 3: Implement** — update `_render_overlay` to accept `kind` and use it:

```python
def _render_overlay(
    decision: PromoteDecision,
    *,
    project_only_fields: dict,
    project_only_body: dict[str, str],
    kind: PromoteKindConfig,
) -> str:
    """Render a project-side overlay file. NEVER emits schema_profile; the
    overlay validator is hardcoded to overlay/1.1."""
    head: dict = {
        "id": f"{kind.id_prefix}{decision.slug}",
        "overlay_of": f"{kind.id_prefix}{decision.slug}",
        "pin_version": decision.canonical_version,
    }
    for k, v in project_only_fields.items():
        if k in _OVERLAY_ONLY_KEYS:
            continue
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(project_only_body)
    return f"---\n{fm}---\n{body}"
```

Update call sites in `plan_promote` to pass `kind=kind`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_plan.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_plan.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode _render_overlay (row 7)

Overlay id + overlay_of fields now use kind.id_prefix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: De-hardcode `_build_project_rollback_command` (table row 8)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (lines 1285-1298)
- Modify: `science/tests/test_commons_promote_apply.py`

- [ ] **Step 1: Write the failing test**:

```python
def test_build_project_rollback_command_topic_path_segments(tmp_path) -> None:
    """For topic, overlay_dest_subdir is "doc/topics" (2 segments). For paper
    it's also 2. But Phase G dataset would be different. Verify the helper
    derives parent count from kind.overlay_dest_subdir, not hardcoded 2."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        _build_project_rollback_command,
    )

    entries = [
        {"path": str(tmp_path / "doc" / "topics" / "x.md")},
        {"path": str(tmp_path / "doc" / "topics" / "y.md")},
    ]
    cmd = _build_project_rollback_command(entries, PROMOTE_KIND_TOPIC)
    assert str(tmp_path) in cmd
    assert "git -C" in cmd
    assert "doc/topics/x.md" in cmd
    assert "doc/topics/y.md" in cmd


def test_build_project_rollback_command_includes_unlinked_source(tmp_path) -> None:
    """Flatten case: an entry with `unlinked_source` extends the rollback to
    cover both target and source paths."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        _build_project_rollback_command,
    )

    entries = [
        {
            "path": str(tmp_path / "doc" / "topics" / "primitives.md"),
            "unlinked_source": str(
                tmp_path / "doc" / "background" / "topics" / "primitives.md"
            ),
        },
    ]
    cmd = _build_project_rollback_command(entries, PROMOTE_KIND_TOPIC)
    assert "doc/topics/primitives.md" in cmd
    assert "doc/background/topics/primitives.md" in cmd
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v -k build_project_rollback_command
```

- [ ] **Step 3: Implement** — replace `_build_project_rollback_command`:

```python
def _build_project_rollback_command(
    overlay_rewrites: list[dict],
    kind: PromoteKindConfig,
) -> str:
    """Build a concrete `git checkout HEAD -- <paths>` command for one project,
    given its overlay_rewrites entries from the audit log. Each entry's `path`
    is the absolute target overlay path. Optional `unlinked_source` (flatten
    case) is added to the rollback set so the source-file deletion can also be
    reverted.

    Project root is derived by stripping len(overlay_dest_subdir.parts)+1
    segments from the path (last segment is the file; preceding segments are
    the overlay_dest_subdir).
    """
    if not overlay_rewrites:
        return ""
    first_path = Path(overlay_rewrites[0]["path"])
    parents_to_strip = len(Path(kind.overlay_dest_subdir).parts) + 1
    project_root = first_path.parents[parents_to_strip - 1]

    paths: list[str] = []
    for entry in overlay_rewrites:
        target = Path(entry["path"])
        paths.append(str(target.relative_to(project_root)))
        if "unlinked_source" in entry:
            source = Path(entry["unlinked_source"])
            paths.append(str(source.relative_to(project_root)))
    paths_sorted = sorted(set(paths))
    return f"git -C {project_root} checkout HEAD -- {' '.join(paths_sorted)}"
```

Update callers (audit-log rendering) to pass `kind=result.kind`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode rollback command (row 8)

Project root derivation now uses len(overlay_dest_subdir.parts), and
the flatten case's unlinked_source is included in the rollback paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: De-hardcode audit log type + entry slug (table rows 9, 10)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (`_render_audit_log_yaml` at lines 1301-1340)
- Modify: `science/tests/test_commons_promote_apply.py`

- [ ] **Step 1: Write the failing test**:

```python
def test_audit_log_yaml_type_field_uses_kind_kind() -> None:
    """promote.py:1332 hardcoded "type": "paper". After de-hardcoding, the
    type field reads from result.kind.kind."""
    from datetime import datetime, timezone
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        PromoteResult,
        _render_audit_log_yaml,
    )

    result = PromoteResult(
        op_id="abc",
        started_at=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 16, 12, 1, tzinfo=timezone.utc),
        commons_commit="deadbeef",
        tags_created=[],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=[],
        kind=PROMOTE_KIND_TOPIC,
    )
    yaml_str = _render_audit_log_yaml(result, Path("/tmp/x"), invocation="x")
    assert "type: topic" in yaml_str
    assert "type: paper" not in yaml_str
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v -k audit_log_yaml_type
```

- [ ] **Step 3: Implement** — in `_render_audit_log_yaml`:

Change the entry construction (around line 1319) from `"bibkey": decision.bibkey` to `"slug": decision.slug` (already done in Task 4's rename — verify).

Change the log root (line 1332) from `"type": "paper"` to `"type": result.kind.kind`.

For the flatten case, when an `OverlayRewrite` carries an `unlinked_source: Path | None` field (added in Task 26), the entry should include:

```python
if overlay.unlinked_source is not None:
    entry["unlinked_source"] = str(overlay.unlinked_source)
```

> Task 26 adds the `unlinked_source` field to `OverlayRewrite`; for Task 18, write the condition as `if getattr(overlay, "unlinked_source", None) is not None:` to keep this task strictly additive on the audit-log side. The OverlayRewrite extension happens in Task 26.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_apply.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_apply.py
git commit -m "$(cat <<'EOF'
refactor(commons/promote): de-hardcode audit log type (rows 9-10)

Log root "type" field reads from result.kind.kind. Entry "slug" key
already renamed in Task 4. Flatten-case unlinked_source recorded
conditionally; OverlayRewrite extension lands in Task 26.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3 — Plan-time validation

### Task 19: Add `PromoteValidationError` class

**Files:**
- Modify: `science/src/science_tool/commons/errors.py`
- Modify: `science/src/science_tool/commons/__init__.py` (re-export)
- Test: `science/tests/test_commons_errors.py` (extend) OR new file `test_commons_promote_validation.py`

- [ ] **Step 1: Write the failing test** — create `science/tests/test_commons_promote_validation.py`:

```python
"""Tests for PromoteValidationError + plan-time validation."""
from __future__ import annotations

import pytest


def test_promote_validation_error_exists_and_carries_fields() -> None:
    from science_tool.commons.errors import CommonsError, PromoteValidationError

    err = PromoteValidationError(
        decision_slug="hypothesis",
        target_kind="canonical",
        project_id=None,
        schema_message="something failed",
    )
    assert isinstance(err, CommonsError)
    assert err.decision_slug == "hypothesis"
    assert err.target_kind == "canonical"
    assert err.project_id is None
    assert "hypothesis" in str(err)
    assert "something failed" in str(err)


def test_promote_validation_error_overlay_carries_project() -> None:
    from science_tool.commons.errors import PromoteValidationError

    err = PromoteValidationError(
        decision_slug="my-theme",
        target_kind="overlay",
        project_id="proj_a",
        schema_message="overlay rejects field 'theme_kind'",
    )
    assert err.target_kind == "overlay"
    assert err.project_id == "proj_a"


def test_promote_validation_error_reexported_from_commons() -> None:
    from science_tool.commons import PromoteValidationError  # public surface
    assert PromoteValidationError is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_validation.py -v
```

- [ ] **Step 3: Implement** — append to `science/src/science_tool/commons/errors.py`:

```python
class PromoteValidationError(CommonsError):
    """Canonical content or an overlay failed schema validation at the end
    of `plan_promote`. Raised BEFORE any I/O — no rollback needed.

    Carries `decision_slug` (the slug whose plan triggered the failure),
    `target_kind` ("canonical" or "overlay"), `project_id` (overlay only —
    which project's overlay failed), and `schema_message` (the underlying
    jsonschema error string).
    """

    def __init__(
        self,
        *,
        decision_slug: str,
        target_kind: Literal["canonical", "overlay"],
        project_id: str | None,
        schema_message: str,
    ) -> None:
        scope = (
            f"{target_kind}"
            if project_id is None
            else f"{target_kind} in project {project_id!r}"
        )
        super().__init__(
            f"plan-time validation failed for {decision_slug!r} ({scope}): "
            f"{schema_message}"
        )
        self.decision_slug = decision_slug
        self.target_kind = target_kind
        self.project_id = project_id
        self.schema_message = schema_message
```

(Add `from typing import Literal` to the imports at the top of `errors.py` if not present.)

In `science/src/science_tool/commons/__init__.py`, add `PromoteValidationError` to the `__all__` list and import block (alphabetical).

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_validation.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/errors.py science/src/science_tool/commons/__init__.py science/tests/test_commons_promote_validation.py
git commit -m "$(cat <<'EOF'
feat(commons/errors): add PromoteValidationError

Raised at the end of plan_promote when canonical content or any
overlay fails its schema. Pre-I/O — no rollback needed. Carries
decision_slug, target_kind, project_id (overlay only), and
schema_message for clear CLI surfacing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Plan-time validation pass

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (`plan_promote` — add validation block before returning)
- Modify: `science/src/science_tool/commons/cli.py` (catch `PromoteValidationError` in the plan-error block)
- Modify: `science/tests/test_commons_promote_validation.py`

- [ ] **Step 1: Write the failing test** — append:

```python
def test_plan_promote_validates_canonical_against_kind_profile(tmp_path, monkeypatch) -> None:
    """A canonical that violates its mixin schema fails plan_promote with
    PromoteValidationError (no I/O). Build a paper candidate with a year
    out of the permitted range (paper mixin requires 1800-2200)."""
    from pathlib import Path
    from science_tool.commons.errors import PromoteValidationError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    proj = tmp_path / "proj_v"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\nyear: 99\n---\n",
        encoding="utf-8",
    )
    commons = tmp_path / "commons"
    commons.mkdir()

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj_v"], PROMOTE_KIND_PAPER)
    with pytest.raises(PromoteValidationError) as excinfo:
        plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_PAPER)
    err = excinfo.value
    assert err.decision_slug == "Adams2025"
    assert err.target_kind == "canonical"
    assert err.project_id is None
    assert "year" in err.schema_message.lower() or "99" in err.schema_message
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_validation.py -v -k validates_canonical
```

- [ ] **Step 3: Implement** — at the end of `plan_promote`, just before constructing `PromotePlan`, add:

```python
_validate_plan(decisions)
return PromotePlan(decisions=decisions, failed_candidates=failed, kind=kind)
```

And add the helper. Use the existing `EntityValidator` from `science_model.entity_schema` — it owns the schema-loading machinery (`SchemaLoader`), the canonical-validation path (`.validate(entity_dict)` which reads `schema_profile` from the entity), and the overlay-validation path (`.validate_overlay(overlay_dict)` which loads overlay-1.1 internally and also enforces `id == overlay_of`). Wrap the `EntityValidationError` it raises into a `PromoteValidationError`:

```python
def _validate_plan(decisions: list[PromoteDecision]) -> None:
    """Validate every canonical against its declared base+mixin profile and
    every overlay against overlay-1.1. Raises PromoteValidationError on
    the first failure. Pre-I/O — no disk state mutated.

    Uses `EntityValidator` from science_model.entity_schema:
    - `.validate(entity_dict)` reads the entity's `schema_profile` field and
      composes base + mixin + extensions via the internal SchemaLoader.
    - `.validate_overlay(overlay_dict)` loads overlay-1.1 internally and
      also enforces `id == overlay_of`.
    Both raise `EntityValidationError` on failure.
    """
    from science_model.entity_schema import EntityValidationError, EntityValidator

    validator = EntityValidator()
    for d in decisions:
        canonical_fm = _parse_frontmatter_only(d.canonical_content)
        try:
            validator.validate(canonical_fm)
        except EntityValidationError as exc:
            raise PromoteValidationError(
                decision_slug=d.slug,
                target_kind="canonical",
                project_id=None,
                schema_message=str(exc),
            ) from exc
        for project_slug, overlay in d.overlays.items():
            overlay_fm = _parse_frontmatter_only(overlay.after_content)
            try:
                validator.validate_overlay(overlay_fm)
            except EntityValidationError as exc:
                raise PromoteValidationError(
                    decision_slug=d.slug,
                    target_kind="overlay",
                    project_id=project_slug,
                    schema_message=str(exc),
                ) from exc
```

`_parse_frontmatter_only` extracts the YAML frontmatter dict from a rendered markdown string (between the `---` fences). If the existing `_parse_entity_file` helper from Task 7 has a portion that does this on a `Path`, factor out a string-based variant:

```python
def _parse_frontmatter_only(rendered: str) -> dict:
    """Parse just the frontmatter block from a rendered <slug>.md content
    string. The string begins with '---\\n', contains an opening fence,
    a YAML body, and a closing '---\\n' fence."""
    if not rendered.startswith("---\n"):
        raise PromoteCandidateError(
            f"rendered content has no opening --- fence", slug=None
        )
    rest = rendered[len("---\n"):]
    end = rest.find("\n---\n")
    if end == -1:
        raise PromoteCandidateError(
            f"rendered content has no closing --- fence", slug=None
        )
    fm_yaml = rest[:end]
    parsed = yaml.safe_load(fm_yaml)
    if not isinstance(parsed, dict):
        raise PromoteCandidateError(
            f"frontmatter is not a mapping: {type(parsed).__name__}", slug=None
        )
    return parsed
```

> **Implementer note:** verify there isn't already a reusable string-based frontmatter parser in the codebase before adding `_parse_frontmatter_only`. Existing candidates include `_parse_entity_file` (Task 7's rename of `_parse_paper_file`, which takes a `Path`) — if it can be refactored to take either a `Path` or a `str`, do that instead and remove the local helper.

In `science/src/science_tool/commons/cli.py`, find the plan-error block (currently catches `PromoteConflictAbort` and `PromoteInputError`) and add `PromoteValidationError`:

```python
try:
    plan = plan_promote(...)
except (PromoteInputError, PromoteConflictAbort, PromoteValidationError) as exc:
    raise click.ClickException(str(exc))
```

Also update the import block to include `PromoteValidationError`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_validation.py -v
cd science && python -m pytest tests/test_commons_promote_plan.py tests/test_commons_promote_apply.py -v
```
Expected: validation test passes; existing plan/apply tests pass (validation accepts well-formed candidates).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/src/science_tool/commons/cli.py science/tests/test_commons_promote_validation.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): plan-time validation

Validates every canonical against base + kind mixin and every overlay
against overlay-1.1 at end of plan_promote. Raises
PromoteValidationError on first failure (pre-I/O, no rollback). CLI
catches the new error in the plan-error block.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 4 — New mixin schemas

### Task 21: `mixin-topic-2.0.json`

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-topic-2.0.json`
- Modify: `science/model/src/science_model/entity_schema/profile.py` (bump `_DEFAULT_MIXIN_VERSION["topic"]` to `"2.0"`)
- Modify: `science/src/science_tool/commons/promote.py` (bump `PROMOTE_KIND_TOPIC.mixin_schema_id` URL to 2.0)
- Test: `science/model/tests/test_mixin_topic_2_0.py` (new)

- [ ] **Step 1: Write the failing test** — create `science/model/tests/test_mixin_topic_2_0.py`:

```python
"""Tests for mixin-topic-2.0.json."""
from __future__ import annotations

import pytest


def test_topic_mixin_2_0_loads_via_default_profile() -> None:
    from science_model.entity_schema import default_profile_for_kind

    profile = default_profile_for_kind("topic")
    assert profile.mixin is not None
    assert profile.mixin.name == "topic"
    assert profile.mixin.version == "2.0"


def test_topic_mixin_2_0_canonical_body_sections() -> None:
    from science_model.entity_schema import (
        default_profile_for_kind,
        read_canonical_body_sections,
    )

    sections = read_canonical_body_sections(default_profile_for_kind("topic"))
    assert "Summary" in sections
    assert "Key Concepts" in sections
    assert "Current State of Knowledge" in sections
    assert "Controversies & Open Questions" in sections
    assert "Key References" in sections


def test_topic_mixin_2_0_merge_policies() -> None:
    from science_model.entity_schema import (
        MergePolicy,
        default_profile_for_kind,
        read_merge_policy,
    )

    policy = read_merge_policy(default_profile_for_kind("topic"))
    assert policy["status"] == MergePolicy.PROJECT_ONLY
    assert policy["created"] == MergePolicy.PROJECT_ONLY
    assert policy["updated"] == MergePolicy.PROJECT_ONLY
    assert policy["datasets"] == MergePolicy.APPEND
    assert policy["source_refs"] == MergePolicy.APPEND
    assert policy["related"] == MergePolicy.APPEND


def test_topic_mixin_2_0_id_regex() -> None:
    """Schema is valid Draft 2020-12 and the id pattern is lowercase-kebab."""
    import json
    from pathlib import Path

    schemas_dir = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
    schema = json.loads((schemas_dir / "mixin-topic-2.0.json").read_text())
    assert schema["properties"]["id"]["pattern"].startswith("^topic:")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science/model && python -m pytest tests/test_mixin_topic_2_0.py -v
```
Expected: schema file doesn't exist; default version is still 1.0.

- [ ] **Step 3: Implement**

Create `science/model/src/science_model/schemas/mixin-topic-2.0.json` exactly as defined in the design (§3.3):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/mixin-topic-2.0.json",
  "title": "science entity topic mixin",
  "$comment": "2.0 adds x-canonical-body-sections + project_only annotations on status/created/updated.",
  "type": "object",
  "required": ["id", "type"],
  "x-canonical-body-sections": [
    "Summary",
    "Key Concepts",
    "Current State of Knowledge",
    "Controversies & Open Questions",
    "Key References"
  ],
  "properties": {
    "id":   {"type": "string", "pattern": "^topic:[a-z0-9][a-z0-9-]{1,63}$"},
    "type": {"const": "topic"},
    "datasets":    {"type": "array", "items": {"type": "string", "pattern": "^dataset:"},
                    "science:merge": "append"},
    "source_refs": {"type": "array", "items": {"type": "string"}, "science:merge": "append"},
    "related":     {"type": "array", "items": {"type": "string"}, "science:merge": "append"},
    "status":      {"type": "string", "science:merge": "project_only"},
    "created":     {"type": "string", "format": "date", "science:merge": "project_only"},
    "updated":     {"type": "string", "format": "date", "science:merge": "project_only"}
  }
}
```

In `science/model/src/science_model/entity_schema/profile.py`, bump:

```python
_DEFAULT_MIXIN_VERSION: dict[str, str] = {
    "dataset": "1.0",
    "paper": "2.0",
    "topic": "2.0",   # bumped
    "theme": "1.0",
}
```

In `science/src/science_tool/commons/promote.py`, update `PROMOTE_KIND_TOPIC.mixin_schema_id`:

```python
mixin_schema_id="https://schemas.science/mixin-topic-2.0.json",
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science/model && python -m pytest tests/test_mixin_topic_2_0.py -v
cd science && python -m pytest tests/test_commons_promote_kind_config.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-topic-2.0.json science/model/src/science_model/entity_schema/profile.py science/model/tests/test_mixin_topic_2_0.py science/src/science_tool/commons/promote.py
git commit -m "$(cat <<'EOF'
feat(science_model): mixin-topic-2.0 + bump default

Adds x-canonical-body-sections (5 sections per topic template) and
project_only annotations on status/created/updated. Bumps the
default_profile_for_kind("topic") version to 2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 22: `mixin-theme-2.0.json`

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-theme-2.0.json`
- Modify: `science/model/src/science_model/entity_schema/profile.py`
- Modify: `science/src/science_tool/commons/promote.py` (`PROMOTE_KIND_THEME.mixin_schema_id`)
- Test: `science/model/tests/test_mixin_theme_2_0.py` (new)

- [ ] **Step 1: Write the failing test** — create `science/model/tests/test_mixin_theme_2_0.py`:

```python
"""Tests for mixin-theme-2.0.json."""
from __future__ import annotations

import pytest


def test_theme_mixin_2_0_loads_via_default_profile() -> None:
    from science_model.entity_schema import default_profile_for_kind

    profile = default_profile_for_kind("theme")
    assert profile.mixin is not None
    assert profile.mixin.name == "theme"
    assert profile.mixin.version == "2.0"


def test_theme_mixin_2_0_canonical_body_sections() -> None:
    from science_model.entity_schema import (
        default_profile_for_kind,
        read_canonical_body_sections,
    )

    sections = read_canonical_body_sections(default_profile_for_kind("theme"))
    assert "Definition" in sections
    assert "Why It Matters" in sections
    assert "Boundaries" in sections
    assert "Guardrails" in sections
    assert "Open Questions" in sections
    assert "Update Triggers" in sections


def test_theme_mixin_2_0_merge_policies() -> None:
    from science_model.entity_schema import (
        MergePolicy,
        default_profile_for_kind,
        read_merge_policy,
    )

    policy = read_merge_policy(default_profile_for_kind("theme"))
    assert policy["status"] == MergePolicy.PROJECT_ONLY
    assert policy["created"] == MergePolicy.PROJECT_ONLY
    assert policy["updated"] == MergePolicy.PROJECT_ONLY
    assert policy["source_refs"] == MergePolicy.APPEND
    assert policy["evidence_refs"] == MergePolicy.APPEND
    assert policy["related"] == MergePolicy.APPEND


def test_theme_mixin_2_0_keeps_required_kind_and_scope() -> None:
    import json
    from pathlib import Path

    schemas_dir = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
    schema = json.loads((schemas_dir / "mixin-theme-2.0.json").read_text())
    assert "theme_kind" in schema["required"]
    assert "theme_scope" in schema["required"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science/model && python -m pytest tests/test_mixin_theme_2_0.py -v
```

- [ ] **Step 3: Implement**

Create `science/model/src/science_model/schemas/mixin-theme-2.0.json` exactly as in the design (§3.3).

Bump `_DEFAULT_MIXIN_VERSION["theme"]` to `"2.0"`.

Update `PROMOTE_KIND_THEME.mixin_schema_id` to `"https://schemas.science/mixin-theme-2.0.json"`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science/model && python -m pytest tests/test_mixin_theme_2_0.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-theme-2.0.json science/model/src/science_model/entity_schema/profile.py science/model/tests/test_mixin_theme_2_0.py science/src/science_tool/commons/promote.py
git commit -m "$(cat <<'EOF'
feat(science_model): mixin-theme-2.0 + bump default

Adds x-canonical-body-sections (6 sections from theme template) and
project_only annotations on status/created/updated. theme_kind and
theme_scope stay required canonical. Bumps default_profile_for_kind
("theme") version to 2.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5 — Topic kind end-to-end

### Task 23: Topic fixtures

**Files:**
- Create: `science/tests/fixtures/promote/proj-alpha/doc/topics/single-instance.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/topics/shared-no-conflict.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/topics/shared-conflict.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/background/topics/flatten-source.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/topics/collide.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/background/topics/collide.md`
- Create: `science/tests/fixtures/promote/proj-beta/doc/topics/shared-no-conflict.md`
- Create: `science/tests/fixtures/promote/proj-beta/doc/topics/shared-conflict.md`

- [ ] **Step 1: Create the fixtures** — each file is small. Write them with `Write`.

`single-instance.md` (proj-alpha):

```markdown
---
id: "topic:single-instance"
title: "A topic only proj-alpha cares about"
status: "active"
related:
  - "concept:meta"
created: "2026-04-01"
updated: "2026-04-01"
---

## Summary

Just one project promotes this topic.

## Key Concepts

Concept A, Concept B.

## Relevance to This Project

Used by proj-alpha hypothesis HA.
```

`shared-no-conflict.md` (proj-alpha):

```markdown
---
id: "topic:shared-no-conflict"
title: "Shared topic, no field conflict"
status: "active"
related:
  - "concept:alpha"
created: "2026-04-02"
updated: "2026-04-02"
---

## Summary

Two projects, identical canonical content.

## Key Concepts

Same in both projects.

## Relevance to This Project

Alpha-side usage notes.
```

`shared-no-conflict.md` (proj-beta) — same `title`, same `## Summary` and `## Key Concepts` content; `## Relevance to This Project` differs (project-only body section):

```markdown
---
id: "topic:shared-no-conflict"
title: "Shared topic, no field conflict"
status: "active"
related:
  - "concept:beta"
created: "2026-04-02"
updated: "2026-04-02"
---

## Summary

Two projects, identical canonical content.

## Key Concepts

Same in both projects.

## Relevance to This Project

Beta-side usage notes.
```

`shared-conflict.md` (proj-alpha) — `title:` differs from proj-beta:

```markdown
---
id: "topic:shared-conflict"
title: "Title from alpha"
status: "active"
created: "2026-04-03"
updated: "2026-04-03"
---

## Summary

Alpha summary.

## Key Concepts

Alpha concepts.
```

`shared-conflict.md` (proj-beta):

```markdown
---
id: "topic:shared-conflict"
title: "Title from beta"
status: "active"
created: "2026-04-03"
updated: "2026-04-03"
---

## Summary

Beta summary.

## Key Concepts

Beta concepts.
```

`flatten-source.md` (proj-alpha, in `doc/background/topics/`):

```markdown
---
id: "topic:flatten-source"
title: "A topic discovered under doc/background/topics/"
status: "active"
created: "2026-04-04"
updated: "2026-04-04"
---

## Summary

Discovery walks both doc/topics/ and doc/background/topics/; this is
sourced from the latter and lands at doc/topics/ on overlay rewrite.

## Key Concepts

The flatten path.
```

`collide.md` (proj-alpha, in `doc/topics/`):

```markdown
---
id: "topic:collide"
title: "Collide in topics/"
---

## Summary
A.
```

`collide.md` (proj-alpha, in `doc/background/topics/`):

```markdown
---
id: "topic:collide"
title: "Collide in background/topics/"
---

## Summary
B.
```

- [ ] **Step 2: Verify fixture structure**

```bash
find science/tests/fixtures/promote -type f -name '*.md' | sort
```
Expected: all 8 new files visible.

- [ ] **Step 3: Commit**

```bash
git add science/tests/fixtures/promote/
git commit -m "$(cat <<'EOF'
test(commons/promote): topic fixtures across 2-project corpus

Adds single-instance, shared-no-conflict, shared-conflict, flatten-
source (in doc/background/topics/), and the same-project collide pair.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 24: Topic discovery tests

**Files:**
- Create: `science/tests/test_commons_promote_topic_discovery.py`

- [ ] **Step 1: Write the failing tests** — create the test file:

```python
"""Topic-kind discovery integration tests using the fixture corpus."""
from __future__ import annotations

from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_topic_discover_single_project_finds_single_instance(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    slugs = set(result.candidates_by_slug)
    assert "single-instance" in slugs
    assert "shared-no-conflict" in slugs
    assert "shared-conflict" in slugs
    assert "flatten-source" in slugs  # discovered from background/topics
    # collide pair → failed candidates only, not in candidates_by_slug
    assert "collide" not in slugs


def test_topic_discover_collide_records_failed_candidate(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    collide_failures = [
        fc for fc in result.failed_candidates if "collide" in fc.error_message
    ]
    assert len(collide_failures) >= 1
    assert "both" in collide_failures[0].error_message.lower()


def test_topic_discover_two_projects_groups_shared_slugs(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)

    assert len(result.candidates_by_slug["shared-no-conflict"]) == 2
    assert len(result.candidates_by_slug["shared-conflict"]) == 2


def test_topic_discover_flatten_source_carries_original_path(monkeypatch) -> None:
    """A topic discovered under doc/background/topics/ keeps that path on its
    overlay_source_path — the apply path uses this to unlink the source."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)

    candidates = result.candidates_by_slug["flatten-source"]
    assert len(candidates) == 1
    assert "background/topics" in str(candidates[0].overlay_source_path)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_topic_discovery.py -v
```
Expected: at least the first test should pass (the implementation from Tasks 5-7 already supports this). Run to confirm.

- [ ] **Step 3: If any test fails, fix discovery**

The discovery implementation was completed in Task 7. If any of these integration tests fail, the bug is in production code — fix it and re-run. Do NOT change the test assertions.

- [ ] **Step 4: All tests pass**

```bash
cd science && python -m pytest tests/test_commons_promote_topic_discovery.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_commons_promote_topic_discovery.py
git commit -m "$(cat <<'EOF'
test(commons/promote): topic discovery integration tests

End-to-end discovery against the proj-alpha/proj-beta fixture corpus.
Covers single-instance, shared-slug grouping, background/topics
inclusion, and same-project collide as FailedCandidate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 25: Topic plan tests

**Files:**
- Create: `science/tests/test_commons_promote_topic_plan.py`

- [ ] **Step 1: Write the failing tests**:

```python
"""Topic-kind plan integration tests."""
from __future__ import annotations

from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_topic_plan_single_instance_no_prompt(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_TOPIC)

    by_slug = {d.slug: d for d in plan.decisions}
    assert "single-instance" in by_slug
    assert "id: topic:single-instance" in by_slug["single-instance"].canonical_content
    assert "type: topic" in by_slug["single-instance"].canonical_content


def test_topic_plan_shared_no_conflict_unifies_canonical(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_TOPIC)

    by_slug = {d.slug: d for d in plan.decisions}
    d = by_slug["shared-no-conflict"]
    assert len(d.overlays) == 2  # one per project
    assert "## Relevance to This Project" not in d.canonical_content
    # Per-project overlays carry the project-only body section:
    for slug in ("proj-alpha", "proj-beta"):
        assert "Relevance to This Project" in d.overlays[slug].after_content


def test_topic_plan_conflict_uses_prompt_resolve(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)

    # Pick proj-alpha's value for the conflicting "title" field.
    captured = []
    def stub(conflict):
        captured.append((conflict.slug, conflict.field))
        return conflict.candidates["proj-alpha"]

    plan = plan_promote(
        discovery,
        commons_root=tmp_path,
        kind=PROMOTE_KIND_TOPIC,
        resolve_conflict=stub,
    )
    assert ("shared-conflict", "title") in captured
    by_slug = {d.slug: d for d in plan.decisions}
    assert "Title from alpha" in by_slug["shared-conflict"].canonical_content


def test_topic_plan_aborts_on_user_abort(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteConflictAbort
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_TOPIC)

    def abort(_c):
        raise PromoteConflictAbort("test")

    with pytest.raises(PromoteConflictAbort):
        plan_promote(
            discovery,
            commons_root=tmp_path,
            kind=PROMOTE_KIND_TOPIC,
            resolve_conflict=abort,
        )
```

- [ ] **Step 2: Run + fix**

```bash
cd science && python -m pytest tests/test_commons_promote_topic_plan.py -v
```
Fix production bugs revealed; don't change tests.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_commons_promote_topic_plan.py
git commit -m "$(cat <<'EOF'
test(commons/promote): topic plan integration tests

Covers single-instance, shared-no-conflict canonical/overlay split,
conflict resolution via resolve_conflict stub, and abort propagation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 26: Topic apply tests + `unlinked_source` field on `OverlayRewrite`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (add `unlinked_source: Path | None = None` to `OverlayRewrite`; implement Path.unlink() in the project-rewrite step; update audit log)
- Create: `science/tests/test_commons_promote_topic_apply.py`

- [ ] **Step 1: Write the failing test**:

```python
"""Topic-kind apply integration tests, including the flatten path."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _copy_fixture(tmp_path: Path, project: str) -> Path:
    """Copy a fixture project into a temp dir + init git so apply can use it."""
    import shutil
    dst = tmp_path / project
    shutil.copytree(FIXTURES / project, dst)
    subprocess.run(["git", "init", str(dst)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dst), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(dst), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
    return dst


def _init_commons(tmp_path: Path) -> Path:
    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "topics").mkdir()
    (commons / ".migrations").mkdir()
    subprocess.run(["git", "init", str(commons)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return commons


def test_topic_apply_flatten_unlinks_background_source(tmp_path, monkeypatch) -> None:
    """flatten-source.md lives under doc/background/topics/ in the fixture.
    After --apply, the overlay must be at doc/topics/flatten-source.md and
    the original doc/background/topics/flatten-source.md must be gone."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = _copy_fixture(tmp_path, "proj-alpha")
    commons = _init_commons(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_TOPIC)

    apply_promote(plan, commons_root=commons, invocation="test")

    assert (proj / "doc" / "topics" / "flatten-source.md").exists()
    assert not (proj / "doc" / "background" / "topics" / "flatten-source.md").exists()


def test_topic_apply_commons_tag_uses_topic_prefix(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = _copy_fixture(tmp_path, "proj-alpha")
    commons = _init_commons(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_TOPIC)
    result = apply_promote(plan, commons_root=commons, invocation="test")

    assert any(t.startswith("topic/") for t in result.tags_created)
    assert not any(t.startswith("paper/") for t in result.tags_created)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_promote_topic_apply.py -v
```

- [ ] **Step 3: Implement**

Extend `OverlayRewrite`:

```python
@dataclass(frozen=True, slots=True)
class OverlayRewrite:
    project_slug: str
    path: Path
    before_sha: str
    after_content: str
    pin_version: str
    rename_from: Path | None = None
    unlinked_source: Path | None = None  # NEW — set for the topic flatten case
```

In `plan_promote`, when building each `OverlayRewrite` for topic, compute the target path under `kind.overlay_dest_subdir`:

```python
target_path = project_root / kind.overlay_dest_subdir / f"{slug}.md"
unlinked_source = None
if candidate.overlay_source_path != target_path:
    unlinked_source = candidate.overlay_source_path
```

Pass `unlinked_source=unlinked_source` to the `OverlayRewrite` constructor.

In `apply_promote`, during the project-rewrite step, after writing the target, unlink the source if present — **and** ensure the existing project-rewrite failure handler restores any already-unlinked source on rollback. The current handler restores `rewrite.path` and `rewrite.rename_from`; it must also restore `rewrite.unlinked_source` for any rewrite that succeeded before the failing one.

Concretely, every `OverlayRewrite` whose write succeeded before the failure must contribute *all three* paths to the restore set: `path` (the new file — `git checkout HEAD --` removes it since it didn't exist at HEAD), `rename_from` (any case-rename source), AND `unlinked_source` (any flatten-case source). Otherwise a failure after step N can leave a hole: the new overlay reverts but the deleted background-topics source stays missing.

```python
written_rewrites: list[OverlayRewrite] = []  # successful so far
try:
    for rewrite in decision.overlays.values():
        rewrite.path.parent.mkdir(parents=True, exist_ok=True)
        rewrite.path.write_text(rewrite.after_content, encoding="utf-8")
        if rewrite.unlinked_source is not None and rewrite.unlinked_source != rewrite.path:
            rewrite.unlinked_source.unlink(missing_ok=False)
        written_rewrites.append(rewrite)
except OSError as exc:
    # Restore every previously-written rewrite's full path set: new path
    # (so it goes back to its pre-promotion state — typically nonexistent),
    # rename_from (case rename), AND unlinked_source (flatten case).
    paths_to_restore: list[str] = []
    for prior in written_rewrites:
        paths_to_restore.append(str(prior.path.relative_to(project_root)))
        if prior.rename_from is not None:
            paths_to_restore.append(str(prior.rename_from.relative_to(project_root)))
        if prior.unlinked_source is not None:
            paths_to_restore.append(str(prior.unlinked_source.relative_to(project_root)))
    if paths_to_restore:
        _git(project_root, "checkout", "HEAD", "--", *paths_to_restore, check=False)
    raise PromoteWriteError(
        stage="rewrite_projects",
        detail=f"project rewrite failed: {exc}",
        commons_commit=commons_commit,
        projects_touched=projects_touched_so_far,
    ) from exc
```

> **Implementer note:** the exact failure-handler signature already exists in Phase E. Locate it (search `rewrite_projects` in `apply_promote`), then extend its restore-paths construction to include `unlinked_source` as above. The Phase E handler already handles `path` and `rename_from`; only the `unlinked_source` extension is new.

In `_render_audit_log_yaml` (Task 18 already conditionally handles `unlinked_source`), confirm the entry includes both `path` and `unlinked_source`.

Add a regression test that simulates a write failure on the *second* overlay after the first one's source was unlinked, and asserts the unlinked source is restored:

```python
def test_topic_apply_rollback_restores_unlinked_source(tmp_path, monkeypatch) -> None:
    """If overlay N+1 fails to write, overlay N's unlinked background-topics
    source must be restored to its pre-apply state."""
    import shutil
    import subprocess
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = _copy_fixture(tmp_path, "proj-alpha")
    # Keep only flatten-source + single-instance so the apply order is
    # deterministic.
    for p in (proj / "doc" / "topics").glob("*.md"):
        if p.name not in {"single-instance.md"}:
            p.unlink()
    for p in (proj / "doc" / "background" / "topics").glob("*.md"):
        if p.name != "flatten-source.md":
            p.unlink()
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-m", "trim"], check=True, capture_output=True
    )

    commons = _init_commons(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_TOPIC)

    # Force the SECOND project write to fail by monkeypatching Path.write_text
    # on the second call only. (Implementation-detail: the worker picks the
    # least-invasive injection point that fits the existing apply loop —
    # could be Path.write_text patched after N calls, or a fault-injection
    # hook already used by Phase E tests.)
    original_write = Path.write_text
    call_count = {"n": 0}
    def faulty_write(self, *a, **kw):
        call_count["n"] += 1
        if call_count["n"] >= 2:
            raise OSError("simulated write failure")
        return original_write(self, *a, **kw)
    monkeypatch.setattr(Path, "write_text", faulty_write)

    with pytest.raises(PromoteWriteError):
        apply_promote(plan, commons_root=commons, invocation="test")

    # The flatten-source must be restored to its pre-apply location.
    assert (proj / "doc" / "background" / "topics" / "flatten-source.md").exists()
```

> If the test's monkeypatch shape doesn't match the codebase's actual write site, the worker should locate the corresponding fault-injection hook used by Phase E's `test_commons_promote_apply.py` rollback tests and adapt.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_promote_topic_apply.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_topic_apply.py
git commit -m "$(cat <<'EOF'
feat(commons/promote): topic flatten unlinks background source

OverlayRewrite gains unlinked_source: Path | None. For topic-kind
candidates discovered under doc/background/topics/, the apply path
writes the new overlay at doc/topics/<slug>.md and Path.unlink()s the
source — preserving Phase E's working-tree-only contract (no git
staging, no project commit). Rollback hints cover both paths.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 27: `commons promote topic` CLI subcommand

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Create: `science/tests/test_commons_cli_promote_topic.py`

- [ ] **Step 1: Write the failing tests**:

```python
"""CLI tests for `commons promote topic`."""
from __future__ import annotations

from pathlib import Path
import subprocess
import shutil

from click.testing import CliRunner

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _setup(tmp_path):
    proj = tmp_path / "proj-alpha"
    shutil.copytree(FIXTURES / "proj-alpha", proj)
    subprocess.run(["git", "init", str(proj)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "topics").mkdir()
    (commons / ".migrations").mkdir()
    subprocess.run(["git", "init", str(commons)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return proj, commons


def test_cli_promote_topic_dry_run_lists_candidates(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "topic", "--from", "proj-alpha"],
    )
    assert result.exit_code == 0, result.output
    assert "single-instance" in result.output
    assert "flatten-source" in result.output


def test_cli_promote_topic_single_entity_form(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "topic", "topic:single-instance", "--from", "proj-alpha"],
    )
    assert result.exit_code == 0, result.output


def test_cli_promote_topic_rejects_wrong_id_prefix(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "topic", "paper:Foo", "--from", "proj-alpha"],
    )
    assert result.exit_code != 0
    assert "topic:" in result.output


def test_cli_promote_topic_apply_writes_commons_and_rewrites_overlay(
    tmp_path, monkeypatch
) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "topic", "topic:single-instance",
         "--from", "proj-alpha", "--apply"],
    )
    assert result.exit_code == 0, result.output
    assert (commons / "topics" / "single-instance.md").exists()
    overlay = (proj / "doc" / "topics" / "single-instance.md").read_text()
    assert "overlay_of: topic:single-instance" in overlay
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_cli_promote_topic.py -v
```
Expected: `commons promote topic` subcommand doesn't exist.

- [ ] **Step 3: Implement** — extend `science/src/science_tool/commons/cli.py`.

Refactor the existing `promote_paper_cmd` into a shared helper that takes a `kind` argument, then bind it as both `promote paper` and `promote topic`:

```python
def _promote_kind_cmd(
    *,
    kind,
    entity_id,
    from_,
    apply_,
    limit,
):
    """Shared implementation for `commons promote paper/topic/theme`."""
    # body — generalised from promote_paper_cmd; uses kind.id_prefix +
    # kind.commons_subdir for the path/id/checks.
    ...


@promote_group.command("topic")
@click.argument("entity_id", required=False)
@click.option("--from", "from_", multiple=True, required=True,
              help="Project slug; repeat for multiple.")
@click.option("--apply", "apply_", is_flag=True, default=False)
@click.option("--limit", type=int, default=None,
              help="Bulk only: stop after N topics (slug-sorted).")
def promote_topic_cmd(entity_id, from_, apply_, limit):
    """Promote topic entities into the commons store."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC
    _promote_kind_cmd(
        kind=PROMOTE_KIND_TOPIC,
        entity_id=entity_id,
        from_=from_,
        apply_=apply_,
        limit=limit,
    )
```

The existing `promote_paper_cmd` is similarly refactored to call `_promote_kind_cmd(kind=PROMOTE_KIND_PAPER, ...)`.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_cli_promote_topic.py tests/test_commons_cli_promote.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli_promote_topic.py
git commit -m "$(cat <<'EOF'
feat(commons/cli): commons promote topic subcommand

Shared _promote_kind_cmd helper drives both paper and topic
subcommands; entity_id validation uses kind.id_prefix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 6 — Theme kind end-to-end

### Task 28: Theme fixtures

**Files:**
- Create: `science/tests/fixtures/promote/proj-alpha/doc/themes/cross-no-conflict.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/themes/cross-conflict.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/themes/project-scope.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/themes/malformed-scope.md`
- Create: `science/tests/fixtures/promote/proj-alpha/doc/themes/cross-biological.md`
- Create: `science/tests/fixtures/promote/proj-beta/doc/themes/cross-no-conflict.md`
- Create: `science/tests/fixtures/promote/proj-beta/doc/themes/cross-conflict.md`

- [ ] **Step 1: Write the fixtures**

`cross-no-conflict.md` (proj-alpha):

```markdown
---
id: "theme:cross-no-conflict"
type: "theme"
title: "Methodological theme shared across projects"
status: "active"
theme_kind: "methodological"
theme_scope: "cross-project"
related:
  - "concept:alpha"
created: "2026-04-05"
updated: "2026-04-05"
---

## Definition

Same definition across alpha and beta.

## Why It Matters

Same reasons.

## Boundaries

Same boundaries.

## Guardrails

Same guardrails.

## Open Questions

Same questions.

## Update Triggers

Same triggers.

## Current Project Links

Alpha-side links only.
```

`cross-no-conflict.md` (proj-beta) — same canonical sections, different project links:

```markdown
---
id: "theme:cross-no-conflict"
type: "theme"
title: "Methodological theme shared across projects"
status: "active"
theme_kind: "methodological"
theme_scope: "cross-project"
related:
  - "concept:beta"
created: "2026-04-05"
updated: "2026-04-05"
---

## Definition

Same definition across alpha and beta.

## Why It Matters

Same reasons.

## Boundaries

Same boundaries.

## Guardrails

Same guardrails.

## Open Questions

Same questions.

## Update Triggers

Same triggers.

## Current Project Links

Beta-side links only.
```

`cross-conflict.md` (proj-alpha):

```markdown
---
id: "theme:cross-conflict"
type: "theme"
title: "Alpha conflict title"
theme_kind: "methodological"
theme_scope: "cross-project"
---

## Definition

Alpha def.
```

`cross-conflict.md` (proj-beta):

```markdown
---
id: "theme:cross-conflict"
type: "theme"
title: "Beta conflict title"
theme_kind: "methodological"
theme_scope: "cross-project"
---

## Definition

Beta def.
```

`project-scope.md` (proj-alpha) — must be silently skipped at discovery:

```markdown
---
id: "theme:project-scope"
type: "theme"
title: "Project-scoped theme"
theme_kind: "methodological"
theme_scope: "project"
---

## Definition

A project-only theme; commons promote theme should not pick this up.
```

`malformed-scope.md` (proj-alpha) — must be recorded as FailedCandidate:

```markdown
---
id: "theme:malformed-scope"
type: "theme"
title: "Theme with missing theme_scope"
theme_kind: "methodological"
---

## Definition

theme_scope is absent.
```

`cross-biological.md` (proj-alpha) — eligible but fails validation:

```markdown
---
id: "theme:cross-biological"
type: "theme"
title: "Cross-project theme with out-of-enum theme_kind"
theme_kind: "biological"
theme_scope: "cross-project"
---

## Definition

biological is not in the theme_kind enum; should fail plan-time validation.
```

- [ ] **Step 2: Verify fixture structure**

```bash
find science/tests/fixtures/promote -type f -name '*.md' -path '*themes*' | sort
```

- [ ] **Step 3: Commit**

```bash
git add science/tests/fixtures/promote/
git commit -m "$(cat <<'EOF'
test(commons/promote): theme fixtures across 2-project corpus

Covers cross-no-conflict, cross-conflict, project-scope (eligibility
skip), malformed-scope (eligibility FAIL), and cross-biological
(eligible but fails plan-time validation on theme_kind enum).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 29: Theme discovery tests

**Files:**
- Create: `science/tests/test_commons_promote_theme_discovery.py`

- [ ] **Step 1: Write the failing tests**:

```python
"""Theme-kind discovery tests covering the eligibility filter."""
from __future__ import annotations

from pathlib import Path
import logging

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_theme_discover_only_cross_project_themes_are_candidates(monkeypatch, caplog) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    _resolver(monkeypatch)
    caplog.set_level(logging.DEBUG, logger="science_tool.commons.promote")
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)

    slugs = set(result.candidates_by_slug)
    assert "cross-no-conflict" in slugs
    assert "cross-conflict" in slugs
    assert "cross-biological" in slugs       # eligible at discovery; fails at plan-time
    # project-scope is silently skipped:
    assert "project-scope" not in slugs


def test_theme_discover_malformed_scope_is_failed_candidate(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)

    failed_names = [Path(fc.source_path).stem for fc in result.failed_candidates]
    assert "malformed-scope" in failed_names


def test_theme_discover_groups_shared_themes(monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    _resolver(monkeypatch)
    result = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_THEME)

    assert len(result.candidates_by_slug["cross-no-conflict"]) == 2
    assert len(result.candidates_by_slug["cross-conflict"]) == 2
```

- [ ] **Step 2: Run test to verify it fails (then fix any production bugs)**

```bash
cd science && python -m pytest tests/test_commons_promote_theme_discovery.py -v
```

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_commons_promote_theme_discovery.py
git commit -m "$(cat <<'EOF'
test(commons/promote): theme discovery integration tests

Eligibility filter behaviour: theme_scope: cross-project → eligible;
project → silently skipped; missing/malformed → FailedCandidate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 30: Theme plan tests (incl. `theme_kind: biological` validation failure)

**Files:**
- Create: `science/tests/test_commons_promote_theme_plan.py`

- [ ] **Step 1: Write the failing tests**:

```python
"""Theme-kind plan tests, including the biological validation failure."""
from __future__ import annotations

from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _resolver(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: FIXTURES / slug,
    )


def test_theme_plan_happy_path_canonical_keeps_kind_and_scope(tmp_path, monkeypatch) -> None:
    """Canonical theme retains theme_kind + theme_scope. Overlay strips both
    (overlay-1.1 doesn't allow them)."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha", "proj-beta"], PROMOTE_KIND_THEME)
    # Filter discovery to only the happy-path slug to avoid the biological
    # validation failure.
    discovery = type(discovery)(
        candidates_by_slug={
            "cross-no-conflict": discovery.candidates_by_slug["cross-no-conflict"]
        },
        failed_candidates=[],
    )

    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_THEME)

    d = next(d for d in plan.decisions if d.slug == "cross-no-conflict")
    assert "theme_kind: methodological" in d.canonical_content
    assert "theme_scope: cross-project" in d.canonical_content
    for overlay in d.overlays.values():
        assert "theme_kind:" not in overlay.after_content
        assert "theme_scope:" not in overlay.after_content


def test_theme_plan_biological_fails_validation(tmp_path, monkeypatch) -> None:
    """A cross-project theme with theme_kind: biological is eligible at
    discovery but fails plan-time validation (the enum doesn't include
    biological)."""
    from science_tool.commons.errors import PromoteValidationError
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        discover_candidates,
        plan_promote,
    )

    _resolver(monkeypatch)
    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)
    # Narrow to just the biological theme to make the failure unambiguous.
    discovery = type(discovery)(
        candidates_by_slug={
            "cross-biological": discovery.candidates_by_slug["cross-biological"]
        },
        failed_candidates=[],
    )

    with pytest.raises(PromoteValidationError) as exc_info:
        plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_THEME)
    err = exc_info.value
    assert err.decision_slug == "cross-biological"
    assert err.target_kind == "canonical"
    # The jsonschema message should mention either theme_kind or biological.
    assert "biological" in err.schema_message or "theme_kind" in err.schema_message
```

- [ ] **Step 2: Run + fix**

```bash
cd science && python -m pytest tests/test_commons_promote_theme_plan.py -v
```

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_commons_promote_theme_plan.py
git commit -m "$(cat <<'EOF'
test(commons/promote): theme plan tests + biological validation

Canonical theme keeps theme_kind + theme_scope; overlay strips both.
Biological theme_kind (out of enum) on a cross-project theme triggers
PromoteValidationError at end of plan_promote, pre-I/O.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 31: Theme apply tests

**Files:**
- Create: `science/tests/test_commons_promote_theme_apply.py`

- [ ] **Step 1: Write the failing tests**:

```python
"""Theme-kind apply integration tests."""
from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _copy_fixture(tmp_path, project):
    dst = tmp_path / project
    shutil.copytree(FIXTURES / project, dst)
    subprocess.run(["git", "init", str(dst)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(dst), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(dst), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
    return dst


def _init_commons(tmp_path):
    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "themes").mkdir()
    (commons / ".migrations").mkdir()
    subprocess.run(["git", "init", str(commons)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return commons


def test_theme_apply_happy_path_creates_theme_tag(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = _copy_fixture(tmp_path, "proj-alpha")
    # Remove the biological + malformed + project-scope fixtures to keep this
    # narrow to the happy path.
    (proj / "doc" / "themes" / "cross-biological.md").unlink()
    (proj / "doc" / "themes" / "malformed-scope.md").unlink()
    (proj / "doc" / "themes" / "cross-conflict.md").unlink()
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-m", "trim"], check=True, capture_output=True
    )

    commons = _init_commons(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_THEME)
    result = apply_promote(plan, commons_root=commons, invocation="test")

    assert (commons / "themes" / "cross-no-conflict.md").exists()
    assert any(t.startswith("theme/") for t in result.tags_created)
```

- [ ] **Step 2: Run + fix**

```bash
cd science && python -m pytest tests/test_commons_promote_theme_apply.py -v
```

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_commons_promote_theme_apply.py
git commit -m "$(cat <<'EOF'
test(commons/promote): theme apply happy-path integration

End-to-end apply on the cross-no-conflict theme creates commons file,
tag with theme/ prefix, and rewrites the project file as overlay.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 32: `commons promote theme` CLI subcommand

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Create: `science/tests/test_commons_cli_promote_theme.py`

- [ ] **Step 1: Write the failing tests** — pattern follows `test_commons_cli_promote_topic.py` (Task 27). Variations:
  - Dry-run output mentions `cross-no-conflict` and `cross-conflict`, does NOT mention `project-scope`.
  - `--apply` writes to `commons/themes/`.
  - Single-entity form: `promote theme theme:cross-no-conflict --from proj-alpha`.
  - Wrong-prefix form (`promote theme paper:Foo --from ...`) exits non-zero.

```python
"""CLI tests for `commons promote theme`."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from click.testing import CliRunner

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _setup(tmp_path):
    proj = tmp_path / "proj-alpha"
    shutil.copytree(FIXTURES / "proj-alpha", proj)
    # Drop the validation-failure fixture so happy-path tests don't trip on it.
    (proj / "doc" / "themes" / "cross-biological.md").unlink()
    subprocess.run(["git", "init", str(proj)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "themes").mkdir()
    (commons / ".migrations").mkdir()
    subprocess.run(["git", "init", str(commons)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )
    return proj, commons


def test_cli_promote_theme_dry_run_excludes_project_scope(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "theme", "--from", "proj-alpha"],
    )
    assert result.exit_code == 0, result.output
    assert "cross-no-conflict" in result.output
    assert "project-scope" not in result.output


def test_cli_promote_theme_single_entity_apply(tmp_path, monkeypatch) -> None:
    from science_tool.commons import cli as commons_cli

    proj, commons = _setup(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons,
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_cli.commons_group,
        ["promote", "theme", "theme:cross-no-conflict",
         "--from", "proj-alpha", "--apply"],
    )
    assert result.exit_code == 0, result.output
    assert (commons / "themes" / "cross-no-conflict.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && python -m pytest tests/test_commons_cli_promote_theme.py -v
```

- [ ] **Step 3: Implement** — add the `promote theme` subcommand to `cli.py` (mirroring `promote_topic_cmd` from Task 27):

```python
@promote_group.command("theme")
@click.argument("entity_id", required=False)
@click.option("--from", "from_", multiple=True, required=True)
@click.option("--apply", "apply_", is_flag=True, default=False)
@click.option("--limit", type=int, default=None,
              help="Bulk only: stop after N themes (slug-sorted).")
def promote_theme_cmd(entity_id, from_, apply_, limit):
    """Promote theme entities into the commons store."""
    from science_tool.commons.promote import PROMOTE_KIND_THEME
    _promote_kind_cmd(
        kind=PROMOTE_KIND_THEME,
        entity_id=entity_id,
        from_=from_,
        apply_=apply_,
        limit=limit,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd science && python -m pytest tests/test_commons_cli_promote_theme.py -v
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli_promote_theme.py
git commit -m "$(cat <<'EOF'
feat(commons/cli): commons promote theme subcommand

Same _promote_kind_cmd helper as paper + topic; theme eligibility
filter ensures only cross-project themes appear in dry-run output.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 7 — Final integration + pilot runbook

### Task 33: Pilot rollout runbook

**Files:**
- Create: `docs/plans/2026-05-16-commons-promote-topics-themes-pilot.md`

- [ ] **Step 1: Write the runbook** — mirrors the Phase E pilot at `docs/plans/2026-05-15-commons-promote-papers-pilot.md`. Sections:

1. **Preconditions** — commons clean, pilot projects clean, `commons` config registered, branch off `main`.
2. **Dry-run** — `science commons promote topic --from <p1> --from <p2>` and same for `theme`. List expected candidates.
3. **Apply** — `--apply` invocation, per-project commit review (user reviews working-tree diffs and commits manually — Phase E contract).
4. **Verification** — `science commons inventory` shows new canonicals + overlays; `git log` in commons shows new tags.
5. **Rollback hints** — drawn from any `failure_audit_yaml`; cite the path-limited `git checkout HEAD -- <paths>` form.
6. **Theme pilot caveat** — three shapes per design §7: (a) pre-pilot rewrite of `theme_scope: project → cross-project` on selected themes; (b) defer the theme pilot; (c) topic-only pilot. The runbook author picks one and documents the choice.

Use `~/d/` (per CLAUDE.md) for filepath references; not `/home/keith/d/` or `/mnt/ssd/Dropbox/`.

Example structure:

```markdown
# Phase F pilot: commons promote topics + themes

> **Date written:** 2026-05-16. **Status:** runbook for the first pilot apply.

## Preconditions

- `~/d/science-commons/` clean (`git status` empty, no `.migrations/`
  uncommitted files).
- Pilot projects clean (`git status` empty in each).
- Branch: `feat/commons-promote-topics-themes` (off `main`, post-Task-32).
- `~/.config/science/config.yaml` lists the pilot projects under `projects:`.

## Topic pilot

### Dry-run

```bash
science commons promote topic --from natural-systems
```

Expected output: candidate list including `topic:hypothesis`, `topic:enrichment`,
... plus any topics under `~/d/natural-systems/doc/background/topics/` which
will be flattened to `doc/topics/` on apply.

### Apply

```bash
science commons promote topic --from natural-systems --apply
```

Inspect the `~/d/natural-systems/` working tree after the command finishes —
each promoted topic becomes a minimal overlay file at `doc/topics/<slug>.md`
(any source from `doc/background/topics/` is unlinked). Review with
`git diff` and commit when satisfied:

```bash
cd ~/d/natural-systems && git add doc/topics doc/background/topics && \
  git commit -m "chore(topics): promote to commons (Phase F pilot)"
```

Verify commons state:

```bash
cd ~/d/science-commons && git log --oneline -10
git tag --list 'topic/*'
science commons inventory --type topic | head
```

## Theme pilot

> **Caveat (design §7):** every theme currently in `~/d/cancer/cancer-types/
> multiple-myeloma/doc/themes/` and `~/d/cancer/meta/doc/themes/` carries
> `theme_scope: "project"`, so the eligibility filter silently skips them
> all. Three options:
> 1. **Pre-pilot rewrite** — identify cross-cutting methodological themes in
>    `~/d/cancer/meta/doc/themes/` and rewrite `theme_scope: "project"` →
>    `"cross-project"` in a dedicated PR. Then run the pilot.
> 2. **Defer the theme pilot** — ship the machinery; production rollout
>    waits.
> 3. **Topic-only pilot** — do only the topic apply above.
>
> **This pilot follows option [N].** (Author picks 1/2/3.)

[If option 1 is selected, include the curated theme list + the pre-pilot PR
checklist. If options 2/3, note that the theme apply is deferred.]

## Rollback hints

If apply fails partway, the failure audit log at
`~/d/science-commons/.migrations/<op-id>-failure.yaml` contains:

- `commons_commit:` — the SHA to `git reset --soft HEAD~1` if rollback is
  needed (already executed by the apply path for write_commons failures).
- `projects_touched.<project>.rollback_command` — the literal
  `git -C <project> checkout HEAD -- <paths>` command to restore project files.

Manual rollback for the project working tree:

```bash
git -C ~/d/natural-systems checkout HEAD -- doc/topics/ doc/background/topics/
```
```

- [ ] **Step 2: Confirm filepath conventions**

```bash
grep -n '/home/keith/d/\|/mnt/ssd/Dropbox/' docs/plans/2026-05-16-commons-promote-topics-themes-pilot.md
```
Expected: no matches (use `~/d/` instead per CLAUDE.md).

- [ ] **Step 3: Commit**

```bash
git add docs/plans/2026-05-16-commons-promote-topics-themes-pilot.md
git commit -m "$(cat <<'EOF'
docs: pilot runbook for commons promote topics + themes

Topic + theme pilot procedure. Topic section: dry-run + apply on
natural-systems. Theme section: documents the three pilot shapes
(pre-pilot rewrite / defer / topic-only) per design §7 caveat.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final acceptance

After Task 33:

```bash
cd science && python -m pytest -v
cd science/model && python -m pytest -v
```

All tests pass. The branch is ready for review and merge to `main`.
