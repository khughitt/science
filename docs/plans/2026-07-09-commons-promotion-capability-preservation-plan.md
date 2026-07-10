# Commons Promotion — Intrinsic Dataset Capability Preservation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science commons promote dataset` preserve the intrinsic dataset fields `provided_capabilities`, `capability_scope`, and `identity_context` on the canonical commons entity, and make the dataset capability-fit gate resolve a promoted dataset's provision from its commons source — so a promoted dataset never silently loses capability-fit credit, without loosening the strict overlay schema.

**Architecture:** Three upstream code changes in `~/d/science` plus a downstream adoption task. P1: declare the three fields in the canonical dataset mixin schema so promotion routes them to the canonical bucket. P4: a fail-early guard in `plan_promote` that makes silent loss structurally impossible. P3: a scoped `effective_dataset_frontmatter` resolver that the capability gate uses to pull a promoted dataset's provision from commons (the overlay itself has no `kind` and is dropped by the gate's `kind` filter today). Adoption: backfill the already-promoted HMCL entity, rescope task t871, correct a stale memory note.

**Tech Stack:** Python 3.12, `science` monorepo (`science/` tool package + `science/model/` schema package), JSON Schema (draft 2020-12), pytest, `uv`.

**Design reference:** `docs/plans/2026-07-09-commons-promotion-capability-preservation-design.md`.

## Global Constraints

- All work is in the `~/d/science` repository. Run every command from that repo root.
- Test runner: `uv run pytest <path> -q` from `~/d/science`.
- Do NOT loosen `overlay-1.1.json` (`additionalProperties: false` stays). Intrinsic fields live on the canonical commons entity only.
- Do NOT re-encode the `capability_scope` valid-value set or the `{assay, modality}` shape in JSON Schema — those stay single-sourced in `science_tool/datasets/capability_scope.py` and the gate's `_capability_shape_issue`.
- No new `MergePolicy` enum value. Preservation uses the existing default `REPLACE` → canonical-bucket routing.
- `INTRINSIC_DATASET_FIELDS = frozenset({"provided_capabilities", "capability_scope", "identity_context"})` is defined exactly once and imported by the promote guard. The resolver relies on the canonical entity as the source of truth and does not need the constant unless it starts filtering/copying intrinsic fields explicitly.
- No AI-attribution trailers in commits.
- Work on a branch (e.g. `t871-commons-capability-preservation`); do not commit on the default branch.

---

### Task 1: Declare intrinsic fields in the canonical dataset mixin schema (P1)

**Files:**
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json` (properties block, lines 7-28)
- Test: `science/model/tests/test_mixin_dataset_intrinsic_fields.py` (create)

**Interfaces:**
- Produces: three new declared properties on the dataset mixin — `provided_capabilities` (array), `capability_scope` (string), `identity_context` (object) — each with no `science:merge` annotation, so `read_merge_policy` assigns them the default `MergePolicy.REPLACE`, which `_classify_entity` routes to the canonical bucket.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_mixin_dataset_intrinsic_fields.py`:

```python
from __future__ import annotations

from science_model.entity_schema import MergePolicy, read_merge_policy
from science_model.entity_schema.profile import parse_profile

_DATASET_PROFILE = "science-entity-base/1.0+dataset/1.0"


def _policy() -> dict[str, MergePolicy]:
    return read_merge_policy(parse_profile(_DATASET_PROFILE))


def test_intrinsic_fields_route_to_canonical_bucket():
    policy = _policy()
    for field in ("provided_capabilities", "capability_scope", "identity_context"):
        assert field in policy, f"{field} not declared in dataset schema"
        # REPLACE / APPEND / FORBIDDEN all route to the canonical bucket in
        # _classify_entity; PROJECT_ONLY is the drop path. Assert non-drop.
        assert policy[field] is not MergePolicy.PROJECT_ONLY


def test_intrinsic_fields_default_to_replace():
    policy = _policy()
    for field in ("provided_capabilities", "capability_scope", "identity_context"):
        assert policy[field] is MergePolicy.REPLACE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science && uv run pytest science/model/tests/test_mixin_dataset_intrinsic_fields.py -q`
Expected: FAIL — `provided_capabilities not declared in dataset schema` (fields absent from `properties`).

- [ ] **Step 3: Add the three property declarations**

In `science/model/src/science_model/schemas/mixin-dataset-1.0.json`, inside `"properties"` (after the `"benchmark"` entry at line 27, before the closing `}` at line 28), add:

```json
    "benchmark": {"$ref": "#/$defs/benchmark"},
    "provided_capabilities": {"type": "array"},
    "capability_scope": {"type": "string"},
    "identity_context": {"type": "object"}
```

(Add a comma after the existing `"benchmark"` line.) Do not add `science:merge`, enums, or item sub-schemas — the value contracts stay owned by the gate and the in-code registry.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science && uv run pytest science/model/tests/test_mixin_dataset_intrinsic_fields.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the model schema suite to confirm no regressions**

Run: `cd ~/d/science && uv run pytest science/model/tests -q`
Expected: PASS (existing dataset-schema tests still green; open `additionalProperties` means previously-valid entities remain valid).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/tests/test_mixin_dataset_intrinsic_fields.py
git commit -m "feat(schema): declare intrinsic dataset capability fields in mixin-dataset-1.0"
```

---

### Task 2: `identity_context` composition regression (P1)

**Files:**
- Test: `science/model/tests/test_mixin_dataset_intrinsic_fields.py` (extend from Task 1)

**Interfaces:**
- Consumes: the mixin declaration from Task 1 and the existing `extension-bio-identity_context-1.0.json` extension.
- Produces: proof that a profile WITHOUT the bio extension preserves a simple `identity_context`, and a profile WITH it still enforces the deep shape (`allOf` composition preserves-without-loosening).

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_mixin_dataset_intrinsic_fields.py`:

```python
import pytest

from science_model.entity_schema import EntityValidator
from science_model.entity_schema.validator import EntityValidationError

_DATASET_PROFILE_STR = "science-entity-base/1.0+dataset/1.0"
_DATASET_PROFILE_WITH_IDENTITY = "science-entity-base/1.0+dataset/1.0+bio.identity_context/1.0"


def _base_dataset_fm(profile: str, **extra) -> dict:
    # schema_profile lives INSIDE the entity; EntityValidator reads it there.
    fm = {
        "schema_profile": profile,
        "id": "dataset:demo",
        "kind": "dataset",
        "title": "Demo dataset",
        "version": "1.0.0",
        "created": "2026-07-09",
        "updated": "2026-07-09",
        "origin": "external",
        "tier": "use-now",
        "dataset_class": "deposit",
        "datapackage": "data/demo/datapackage.json",
        "access": {"level": "public", "verified": True},
    }
    fm.update(extra)
    return fm


def test_identity_context_preserved_without_bio_extension():
    # profile WITHOUT the identity extension: a simple object validates.
    fm = _base_dataset_fm(_DATASET_PROFILE_STR, identity_context={"taxon": 9606})
    EntityValidator().validate(fm)  # must not raise


def test_identity_context_deep_shape_enforced_with_bio_extension():
    # profile WITH the identity extension: a malformed identity_context fails.
    fm = _base_dataset_fm(_DATASET_PROFILE_WITH_IDENTITY, identity_context={"taxon": "not-an-int"})
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(fm)
```

Note for the implementer: confirm the base-required field set (`schema_profile`, `title`, `version`, `created`, `updated`, plus the dataset-required `id`/`kind`/`origin`/`tier`) against `science-entity-base-1.0.json` + `mixin-dataset-1.0.json` `required` lists and adjust `_base_dataset_fm` if anything is missing. The current `extension-bio-identity_context-1.0.json` constrains `identity_context.taxon` as an integer with minimum 1, so `taxon: "not-an-int"` is the intended malformed value. If `EntityValidationError` is not re-exported from `science_model.entity_schema`, import it from `science_model.entity_schema.validator` as shown.

- [ ] **Step 2: Run test to verify it fails (or drives the entry-point fix)**

Run: `cd ~/d/science && uv run pytest science/model/tests/test_mixin_dataset_intrinsic_fields.py -q -k identity_context`
Expected: FAIL initially — the WITH-extension assertion drives you to craft a genuine violation of the extension's declared `identity_context` shape (and to confirm the base-required fields).

- [ ] **Step 3: Fix the test wiring only**

No production change here — this task proves existing composition behavior. Adjust `_base_dataset_fm`'s required fields and the malformed `identity_context` value until both assertions express the intended contract.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science && uv run pytest science/model/tests/test_mixin_dataset_intrinsic_fields.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/model/tests/test_mixin_dataset_intrinsic_fields.py
git commit -m "test(schema): identity_context preserved without bio extension, deep shape enforced with it"
```

---

### Task 3: Fail-early promotion guard + shared `INTRINSIC_DATASET_FIELDS` (P4)

**Files:**
- Create: `science/src/science_tool/datasets/intrinsic.py`
- Modify: `science/src/science_tool/commons/errors.py` (add `PromoteCapabilityDropError` alongside the other promote/commons errors — this is where they live, imported into `promote.py`)
- Modify: `science/src/science_tool/commons/promote.py` (import the new error + `INTRINSIC_DATASET_FIELDS`; add the guard after `_classify_entity` in the dataset branch, ~lines 695-707)
- Test: `science/tests/test_commons_promote_dataset_plan.py` (extend)

**Interfaces:**
- Produces: `INTRINSIC_DATASET_FIELDS: frozenset[str]` in `datasets/intrinsic.py`, imported by `promote.py` for the fail-early guard.
- Produces: `plan_promote` raises `PromoteCapabilityDropError` if a source dataset carries any intrinsic field that did not land in the canonical bucket.

- [ ] **Step 1: Create the shared constant**

Create `science/src/science_tool/datasets/intrinsic.py`:

```python
"""Dataset fields that describe what a dataset *is* (its measurement capability
and identity), independent of any consuming project. Commons promotion must
preserve these on the canonical entity; the capability gate resolves them from
commons for a promoted (overlay) dataset.
"""

from __future__ import annotations

INTRINSIC_DATASET_FIELDS: frozenset[str] = frozenset(
    {"provided_capabilities", "capability_scope", "identity_context"}
)
```

- [ ] **Step 2: Write the failing test**

In `science/tests/test_commons_promote_dataset_plan.py`, add concrete plan-level regression tests that parse the rendered canonical and overlay frontmatter from the current `PromoteDecision` shape (`canonical_artifacts` + `overlays`):

```python
def _frontmatter_from_text(markdown: str) -> dict:
    import yaml

    assert markdown.startswith("---\n")
    _prefix, raw, _body = markdown.split("---\n", 2)
    parsed = yaml.safe_load(raw)
    assert isinstance(parsed, dict)
    return parsed


def _artifact_frontmatter(decision, relpath: str) -> dict:
    [artifact] = [a for a in decision.canonical_artifacts if a.path.as_posix() == relpath]
    return _frontmatter_from_text(artifact.content)


def _overlay_frontmatter(decision, project_slug: str) -> dict:
    return _frontmatter_from_text(decision.overlays[project_slug].after_content)


def _single_dataset_plan(tmp_path, monkeypatch, frontmatter: str):
    from science_tool.commons.promote import PROMOTE_KIND_DATASET, discover_candidates, plan_promote

    proj, commons = _setup(tmp_path, monkeypatch)
    _replace_single_dataset(proj, "demo", frontmatter)
    _commit_all(proj, "dataset intrinsic fixture")
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    return plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )


def test_plan_promote_routes_intrinsic_fields_to_canonical(tmp_path, monkeypatch):
    plan = _single_dataset_plan(
        tmp_path,
        monkeypatch,
        "id: dataset:demo\n"
        "kind: dataset\n"
        "title: Demo\n"
        "origin: external\n"
        "tier: use-now\n"
        "dataset_class: deposit\n"
        "datapackage: data/demo/datapackage.json\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "provided_capabilities:\n"
        "- {assay: drug-sensitivity, modality: cell-line-viability}\n"
        "identity_context: {taxon: 9606}\n",
    )

    [decision] = plan.decisions
    canonical = _artifact_frontmatter(decision, "datasets/demo/entity.md")
    overlay = _overlay_frontmatter(decision, "proj-dataset")
    assert canonical["provided_capabilities"] == [
        {"assay": "drug-sensitivity", "modality": "cell-line-viability"}
    ]
    assert canonical["identity_context"] == {"taxon": 9606}
    assert "provided_capabilities" not in overlay
    assert "identity_context" not in overlay


def test_plan_promote_routes_capability_scope_alone_to_canonical(tmp_path, monkeypatch):
    # capability_scope is mutually exclusive with provided_capabilities, so it
    # needs its own fixture to prove the third intrinsic field is preserved too.
    plan = _single_dataset_plan(
        tmp_path,
        monkeypatch,
        "id: dataset:demo\n"
        "kind: dataset\n"
        "title: Demo\n"
        "origin: external\n"
        "tier: use-now\n"
        "dataset_class: deposit\n"
        "datapackage: data/demo/datapackage.json\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "capability_scope: clinical-outcome\n"
        "identity_context: {taxon: 9606}\n",
    )

    [decision] = plan.decisions
    canonical = _artifact_frontmatter(decision, "datasets/demo/entity.md")
    overlay = _overlay_frontmatter(decision, "proj-dataset")
    assert canonical["capability_scope"] == "clinical-outcome"
    assert canonical["identity_context"] == {"taxon": 9606}
    assert "capability_scope" not in overlay
    assert "identity_context" not in overlay


def test_plan_promote_guard_raises_when_intrinsic_field_would_drop(monkeypatch, tmp_path):
    # Simulate the drop by forcing the merge policy to omit the field, proving the
    # guard is a real backstop independent of the schema declaration.
    from science_tool.commons.errors import PromoteCapabilityDropError
    import science_tool.commons.promote as promote

    orig = promote.read_merge_policy
    monkeypatch.setattr(
        promote,
        "read_merge_policy",
        lambda profile: {
            k: v for k, v in orig(profile).items() if k != "provided_capabilities"
        },
    )
    with pytest.raises(PromoteCapabilityDropError):
        _single_dataset_plan(
            tmp_path,
            monkeypatch,
            "id: dataset:demo\n"
            "kind: dataset\n"
            "title: Demo\n"
            "origin: external\n"
            "tier: use-now\n"
            "dataset_class: deposit\n"
            "datapackage: data/demo/datapackage.json\n"
            "access:\n"
            "  level: public\n"
            "  verified: true\n"
            "provided_capabilities:\n"
            "- {assay: drug-sensitivity, modality: cell-line-viability}\n",
        )
```

Implementer note: keep the assertions against `decision.canonical_artifacts` and `decision.overlays`; `PromoteDecision` does not expose `canonical_frontmatter` or `overlay_frontmatter` attributes.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/d/science && uv run pytest science/tests/test_commons_promote_dataset_plan.py -q -k "intrinsic or capability_scope"`
Expected: FAIL — `PromoteCapabilityDropError` does not exist / guard not implemented.

- [ ] **Step 4: Implement the guard**

In `science/src/science_tool/commons/errors.py`, add the error class alongside the other promote/commons errors (match the base class the siblings use — `CommonsError` or its promote subclass):

```python
class PromoteCapabilityDropError(CommonsError):
    """A source dataset's intrinsic field would be dropped by promotion."""

    def __init__(self, slug: str, project_slug: str, fields: list[str]) -> None:
        self.slug = slug
        self.project_slug = project_slug
        self.fields = fields
        super().__init__(
            f"promote would drop intrinsic dataset field(s) {sorted(fields)} from "
            f"{slug!r} (project {project_slug!r}); these must land on the canonical "
            f"commons entity. Declare them in the dataset schema or fix the merge policy."
        )
```

In `science/src/science_tool/commons/promote.py`, add to the existing imports:

```python
from science_tool.commons.errors import PromoteCapabilityDropError  # add to the errors import group
from science_tool.datasets.intrinsic import INTRINSIC_DATASET_FIELDS
```

Inside the dataset branch, immediately after the `proj_f` overlay filter (after line 702), before `_dataset_dropped_fields`:

```python
                if kind.kind == "dataset":
                    proj_f = {k: v for k, v in proj_f.items() if k in overlay_field_keys}
                    dropped_intrinsic = sorted(
                        f for f in INTRINSIC_DATASET_FIELDS
                        if f in raw_fm and f not in can_f
                    )
                    if dropped_intrinsic:
                        raise PromoteCapabilityDropError(
                            c.slug, c.project_slug, dropped_intrinsic
                        )
                    dataset_dropped_by_project[c.project_slug] = _dataset_dropped_fields(
                        raw_fm,
                        canonical_fields=can_f,
                        project_only_fields=proj_f,
                    )
```

The raise is inside the per-candidate `try` (line 676), but that `try` catches only `PromoteConflictAbort` — every other exception propagates. So `PromoteCapabilityDropError` is a **hard stop** that aborts the promotion, which is exactly the fail-early intent for this invariant. Do not add a handler for it; let it propagate to the CLI's `CommonsError → ClickException` path.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/d/science && uv run pytest science/tests/test_commons_promote_dataset_plan.py -q -k "intrinsic or capability_scope"`
Expected: PASS.

- [ ] **Step 6: Run the full promote plan suite**

Run: `cd ~/d/science && uv run pytest science/tests/test_commons_promote_dataset_plan.py science/tests/test_commons_promote_plan.py -q`
Expected: PASS (guard does not fire for normal datasets, which either lack intrinsic fields or now route them to canonical via Task 1).

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/datasets/intrinsic.py science/src/science_tool/commons/errors.py science/src/science_tool/commons/promote.py science/tests/test_commons_promote_dataset_plan.py
git commit -m "feat(promote): fail-early guard preserves intrinsic dataset fields to canonical"
```

---

### Task 4: `effective_dataset_frontmatter` resolver (P3 core)

**Files:**
- Create: `science/src/science_tool/validate/_effective_frontmatter.py`
- Test: `science/tests/validate/test_effective_frontmatter.py` (create)

**Interfaces:**
- Consumes: `resolve_entity` (`science_tool.commons.overlay`) and the commons error classes (`science_tool.commons.errors`).
- Produces:
  - `class CommonsUnavailable(Exception)` — environmental "defer" signal.
  - `class OverlayResolutionError(Exception)` — structural "explicit failure" signal.
  - `effective_dataset_frontmatter(overlay_fm: dict, *, resolver=resolve_entity) -> dict` — for a dataset overlay descriptor, returns the canonical commons frontmatter (carrying `kind: dataset` and the intrinsic fields) with `_path` re-injected and `related` unioned.

- [ ] **Step 1: Write the failing test**

Create `science/tests/validate/test_effective_frontmatter.py`:

```python
from __future__ import annotations

import pytest

from science_tool.commons.errors import CommonsEntityError, CommonsRootNotFoundError
from science_tool.validate._effective_frontmatter import (
    CommonsUnavailable,
    OverlayResolutionError,
    effective_dataset_frontmatter,
)


class _Merged:
    def __init__(self, fm: dict):
        self.merged_frontmatter = fm


def _overlay_fm(**kw) -> dict:
    base = {
        "id": "dataset:demo",
        "overlay_of": "dataset:demo",
        "_path": "overlays/datasets/demo.md",
        "related": ["hypothesis:0025-x"],
    }
    base.update(kw)
    return base


def test_resolves_canonical_intrinsic_fields_and_injects_path():
    canonical = {
        "id": "dataset:demo",
        "kind": "dataset",
        "provided_capabilities": [{"assay": "drug-sensitivity", "modality": "cell-line-viability"}],
        "related": ["topic:mm"],
    }
    eff = effective_dataset_frontmatter(_overlay_fm(), resolver=lambda cid, project=None: _Merged(canonical))
    assert eff["kind"] == "dataset"
    assert eff["provided_capabilities"] == canonical["provided_capabilities"]
    assert eff["_path"] == "overlays/datasets/demo.md"
    # related unioned (canonical + overlay), overlay reach preserved
    assert set(eff["related"]) == {"topic:mm", "hypothesis:0025-x"}


def test_commons_root_absent_raises_commons_unavailable():
    def _boom(cid, project=None):
        raise CommonsRootNotFoundError(__import__("pathlib").Path("/nope"))

    with pytest.raises(CommonsUnavailable):
        effective_dataset_frontmatter(_overlay_fm(), resolver=_boom)


def test_dangling_overlay_of_raises_overlay_resolution_error():
    def _boom(cid, project=None):
        raise CommonsEntityError(__import__("pathlib").Path("/x"), canonical_id=cid, cause=ValueError("unknown"))

    with pytest.raises(OverlayResolutionError):
        effective_dataset_frontmatter(_overlay_fm(), resolver=_boom)
```

Implementer note: confirm the `CommonsEntityError` / `CommonsRootNotFoundError` constructor signatures in `science_tool/commons/errors.py` and adjust the test's raises accordingly.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science && uv run pytest science/tests/validate/test_effective_frontmatter.py -q`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the resolver**

Create `science/src/science_tool/validate/_effective_frontmatter.py`:

```python
"""Scoped overlay→commons resolver for validate checks that need intrinsic
dataset truth (currently only the capability-fit gate).

`entity_frontmatters` deliberately stays the raw project-local view; this helper
is the ONE place that reaches across to the commons canonical, and only for
dataset overlays. See docs/plans/2026-07-09-commons-promotion-capability-preservation-design.md.
"""

from __future__ import annotations

from typing import Any, Callable

from science_tool.commons.errors import CommonsError, CommonsRootNotFoundError
from science_tool.commons.overlay import resolve_entity


class CommonsUnavailable(Exception):
    """The commons store is not reachable at validate time — defer, do not warn."""


class OverlayResolutionError(Exception):
    """A dataset overlay could not be resolved to its commons canonical — a defect."""


def effective_dataset_frontmatter(
    overlay_fm: dict[str, Any],
    *,
    resolver: Callable[..., Any] = resolve_entity,
) -> dict[str, Any]:
    """Return the effective frontmatter for a dataset overlay descriptor.

    The three intrinsic fields are canonical-only (the overlay cannot carry
    them), so the canonical view IS the effective provision — no overlay merge,
    hence `project=None`. `_path` is re-injected from the overlay for actionable
    WARN paths; `related` is unioned so dataset-side reach is preserved.

    Raises CommonsUnavailable (environmental) or OverlayResolutionError (defect).
    """
    canonical_id = overlay_fm.get("overlay_of")
    if not isinstance(canonical_id, str) or not canonical_id:
        # Not an overlay — caller should not pass these, but be total.
        return overlay_fm
    try:
        merged = resolver(canonical_id, project=None).merged_frontmatter
    except CommonsRootNotFoundError as exc:
        raise CommonsUnavailable(str(exc)) from exc
    except CommonsError as exc:  # unknown id, malformed canonical, etc.
        raise OverlayResolutionError(f"{canonical_id}: {exc}") from exc

    eff = dict(merged)
    path = overlay_fm.get("_path")
    if path is not None:
        eff["_path"] = path
    related = list(
        dict.fromkeys(
            [*(merged.get("related") or []), *(overlay_fm.get("related") or [])]
        )
    )
    if related:
        eff["related"] = related
    return eff
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science && uv run pytest science/tests/validate/test_effective_frontmatter.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/_effective_frontmatter.py science/tests/validate/test_effective_frontmatter.py
git commit -m "feat(validate): scoped overlay->commons effective-frontmatter resolver"
```

---

### Task 5: Wire the resolver into the capability gate (P3 adoption)

**Files:**
- Modify: `science/src/science_tool/validate/_helpers.py` (add `overlay_dataset_frontmatters`)
- Modify: `science/src/science_tool/validate/checks/dataset_capabilities.py` (`check_dataset_capabilities`)
- Test: `science/tests/validate/test_checks_dataset_capabilities.py` (extend)

**Interfaces:**
- Consumes: `overlay_dataset_frontmatters(ctx)`, `effective_dataset_frontmatter`, `CommonsUnavailable`, `OverlayResolutionError`, `Result`, `Severity`.
- Produces: `check_dataset_capabilities` appends resolved overlay dataset records to `entity_frontmatters(ctx)`; defers on `CommonsUnavailable`; emits a `Severity.ERROR` `dataset-capabilities.overlay-unresolved` result on `OverlayResolutionError`.

- [ ] **Step 1: Add the overlay discovery helper (with its own test)**

In `science/src/science_tool/validate/_helpers.py`, add (mirroring the overlay scan in `dataset_frontmatters`, but WITHOUT the `kind` filter — overlays have no `kind` — and keyed on `overlay_of` being a dataset ref):

```python
def overlay_dataset_frontmatters(ctx: ValidateContext) -> list[dict[str, Any]]:
    """Raw frontmatter for every project *dataset overlay* descriptor.

    Overlays carry no `kind` (overlay-1.1 forbids it), so entity_frontmatters
    drops them. This surfaces them for the capability gate, which resolves each
    to its commons canonical. De-duped by id (first wins). Each carries `_path`.
    """
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for ref in MarkdownAdapter(scan_roots=["overlays/datasets"]).discover(ctx.project_root):
        abs_path = ctx.project_root / ref.path
        if not abs_path.is_file():
            continue
        fm = raw_frontmatter(abs_path)
        overlay_of = fm.get("overlay_of")
        if not (isinstance(overlay_of, str) and overlay_of.startswith("dataset:")):
            continue
        ident = fm.get("id")
        if isinstance(ident, str) and ident:
            if ident in seen_ids:
                continue
            seen_ids.add(ident)
        fm["_path"] = ref.path
        out.append(fm)
    return out
```

Add a test in `science/tests/validate/test_checks_dataset_capabilities.py` (or a `_helpers` test file) that, given a temp project with one `overlays/datasets/x.md` (`overlay_of: dataset:x`), `overlay_dataset_frontmatters` returns one record with `_path` set and `overlay_of` present.

- [ ] **Step 2: Write the failing gate test**

Append to `science/tests/validate/test_checks_dataset_capabilities.py` a test that drives `check_dataset_capabilities` (not just `evaluate_dataset_capabilities`) with a monkeypatched `overlay_dataset_frontmatters` and `effective_dataset_frontmatter`. `Severity` is already imported at the top of this test file (line 5); if you split these into a new file, add `from science_tool.validate.result import Severity`.

```python
def test_overlay_dataset_with_commons_provision_emits_no_missing(monkeypatch, tmp_path):
    import science_tool.validate.checks.dataset_capabilities as mod

    overlay = {"id": "dataset:demo", "overlay_of": "dataset:demo",
               "_path": "overlays/datasets/demo.md",
               "related": ["hypothesis:0025-live"]}
    hypo = {"id": "hypothesis:0025-live", "kind": "hypothesis", "status": "open",
            "_path": "entities/hypotheses/0025.md",
            "related": ["dataset:demo"], "required_capabilities":
            [{"assay": "drug-sensitivity", "modality": "cell-line-viability"}]}
    resolved = {"id": "dataset:demo", "kind": "dataset",
                "_path": "overlays/datasets/demo.md",
                "provided_capabilities":
                [{"assay": "drug-sensitivity", "modality": "cell-line-viability"}],
                "related": ["hypothesis:0025-live"]}

    monkeypatch.setattr(mod, "entity_frontmatters", lambda ctx: [hypo])
    monkeypatch.setattr(mod, "overlay_dataset_frontmatters", lambda ctx: [overlay])
    monkeypatch.setattr(mod, "effective_dataset_frontmatter", lambda fm: resolved)

    results = list(mod.check_dataset_capabilities(ctx=object()))
    rules = [r.rule for r in results]
    assert "dataset-capabilities.provided-missing" not in rules


def test_overlay_unresolved_emits_error(monkeypatch):
    import science_tool.validate.checks.dataset_capabilities as mod
    from science_tool.validate._effective_frontmatter import OverlayResolutionError

    overlay = {"id": "dataset:demo", "overlay_of": "dataset:gone",
               "_path": "overlays/datasets/demo.md"}

    def _boom(fm):
        raise OverlayResolutionError("dataset:gone: unknown")

    monkeypatch.setattr(mod, "entity_frontmatters", lambda ctx: [])
    monkeypatch.setattr(mod, "overlay_dataset_frontmatters", lambda ctx: [overlay])
    monkeypatch.setattr(mod, "effective_dataset_frontmatter", _boom)

    results = list(mod.check_dataset_capabilities(ctx=object()))
    assert any(r.rule == "dataset-capabilities.overlay-unresolved"
               and r.severity is Severity.ERROR for r in results)


def test_overlay_commons_unavailable_defers(monkeypatch):
    import science_tool.validate.checks.dataset_capabilities as mod
    from science_tool.validate._effective_frontmatter import CommonsUnavailable

    overlay = {"id": "dataset:demo", "overlay_of": "dataset:demo",
               "_path": "overlays/datasets/demo.md"}

    def _defer(fm):
        raise CommonsUnavailable("no commons root")

    monkeypatch.setattr(mod, "entity_frontmatters", lambda ctx: [])
    monkeypatch.setattr(mod, "overlay_dataset_frontmatters", lambda ctx: [overlay])
    monkeypatch.setattr(mod, "effective_dataset_frontmatter", _defer)

    results = list(mod.check_dataset_capabilities(ctx=object()))
    assert results == []  # deferred: no warning, no error
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/d/science && uv run pytest science/tests/validate/test_checks_dataset_capabilities.py -q -k "overlay"`
Expected: FAIL — `check_dataset_capabilities` does not yet consult overlays.

- [ ] **Step 4: Implement the wiring**

In `science/src/science_tool/validate/checks/dataset_capabilities.py`, update imports and the check:

```python
from science_tool.validate._helpers import entity_frontmatters, overlay_dataset_frontmatters
from science_tool.validate._effective_frontmatter import (
    CommonsUnavailable,
    OverlayResolutionError,
    effective_dataset_frontmatter,
)
```

Replace `check_dataset_capabilities`:

```python
@Check(section="dataset capabilities", order=33)
def check_dataset_capabilities(ctx: ValidateContext) -> Iterator[Result]:
    records = list(entity_frontmatters(ctx))
    for overlay_fm in overlay_dataset_frontmatters(ctx):
        try:
            records.append(effective_dataset_frontmatter(overlay_fm))
        except CommonsUnavailable:
            continue  # environmental: defer, do not warn
        except OverlayResolutionError as exc:
            path = overlay_fm.get("_path")
            yield Result(
                Severity.ERROR,
                Path(path) if isinstance(path, str) else None,
                None,
                str(exc),
                "dataset-capabilities.overlay-unresolved",
                None,
            )
    yield from evaluate_dataset_capabilities(records)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science && uv run pytest science/tests/validate/test_checks_dataset_capabilities.py -q`
Expected: PASS (existing 24 + new tests; `_load_checks_with_dataset_capabilities_fresh` registration test still green).

- [ ] **Step 6: Run the full validate suite**

Run: `cd ~/d/science && uv run pytest science/tests/validate -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/_helpers.py science/src/science_tool/validate/checks/dataset_capabilities.py science/tests/validate/test_checks_dataset_capabilities.py
git commit -m "feat(validate): capability gate resolves promoted-dataset provision from commons"
```

---

### Task 6: Promote-apply end-to-end preservation test (P1 + P4 integration)

**Files:**
- Test: `science/tests/test_commons_promote_dataset_apply.py` (extend)

**Interfaces:**
- Consumes: the full promote apply path with Task 1 (schema) + Task 3 (guard) in place.
- Produces: proof that `apply_promote` writes the intrinsic fields to the commons `entity.md` and none to the overlay.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_commons_promote_dataset_apply.py`, reusing `_replace_single_dataset` (line 77) to author a source dataset carrying `provided_capabilities` and `identity_context`, then run the same apply flow as `test_dataset_apply_writes_three_artifacts_commit_tag_override_overlay`:

```python
def test_dataset_apply_preserves_intrinsic_capability_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.frontmatter import raw_frontmatter
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj, commons = _setup(tmp_path, monkeypatch)
    _replace_single_dataset(
        proj,
        "demo",
        "id: dataset:demo\n"
        "kind: dataset\n"
        "title: Demo\n"
        "origin: external\n"
        "tier: use-now\n"
        "dataset_class: deposit\n"
        "datapackage: data/demo/datapackage.json\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "provided_capabilities:\n"
        "- {assay: drug-sensitivity, modality: cell-line-viability}\n"
        "identity_context: {taxon: 9606}\n",
    )
    _commit_all(proj, "dataset intrinsic fixture")

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )
    apply_promote(
        plan,
        commons_root=commons,
        invocation="science commons promote dataset --from proj-dataset --apply",
    )

    commons_fm = raw_frontmatter(commons / "datasets" / "demo" / "entity.md")
    assert commons_fm["provided_capabilities"] == [
        {"assay": "drug-sensitivity", "modality": "cell-line-viability"}
    ]
    assert commons_fm["identity_context"] == {"taxon": 9606}

    overlay_fm = raw_frontmatter(proj / "overlays" / "datasets" / "demo.md")
    assert overlay_fm["overlay_of"] == "dataset:demo"
    assert "provided_capabilities" not in overlay_fm
    assert "identity_context" not in overlay_fm
```

- [ ] **Step 2: Run test to verify it fails, then passes**

Run: `cd ~/d/science && uv run pytest science/tests/test_commons_promote_dataset_apply.py -q -k intrinsic`
Expected: with Tasks 1 + 3 already merged, this should PASS on first run (it is a regression lock, not a driver). If it FAILS, the failure localizes whether the schema declaration (Task 1) or classification routing is off — fix there, not here.

- [ ] **Step 3: Commit**

```bash
cd ~/d/science
git add science/tests/test_commons_promote_dataset_apply.py
git commit -m "test(promote): apply preserves intrinsic capability fields on commons, not overlay"
```

---

### Task 7: Backfill HMCL + rescope t871 + fix stale memory (adoption)

**Files:**
- Modify: `~/d/science-commons/datasets/hmcl-drug-screen/entity.md` (add the two intrinsic fields)
- Modify: MM30 `tasks/active.md` (t871 done note) — in `~/d/cancer/cancer-types/multiple-myeloma`
- Modify: MM30 auto-memory `reference_commons_dataset_promotion.md`, the capability-fit gate memory, and `MEMORY.md` (under the memory dir for the MM30 project)

**Interfaces:**
- Consumes: the merged upstream fix (Tasks 1-6).

- [ ] **Step 1: Backfill the HMCL commons entity**

Prefer re-promotion if the overlay can be reverted to a source entity cleanly; otherwise patch directly. Direct patch: add to `~/d/science-commons/datasets/hmcl-drug-screen/entity.md` frontmatter:

```yaml
provided_capabilities:
- {assay: drug-sensitivity, modality: cell-line-viability}
identity_context: {taxon: 9606}
```

- [ ] **Step 2: Verify the gate now credits HMCL**

From the MM30 repo:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
uv run --frozen science validate --profile full 2>&1 | grep -iE "hmcl|overlay-unresolved|provided-missing" || echo "clean"
```

Expected: `clean` (no `overlay-unresolved`, no HMCL `provided-missing`). Confirm the resolver reaches the commons store from MM30's config.

- [ ] **Step 3: Commit the commons backfill**

```bash
cd ~/d/science-commons
git add datasets/hmcl-drug-screen/entity.md
git commit -m "fix: backfill hmcl-drug-screen intrinsic capability + identity fields"
```

- [ ] **Step 4: Rescope t871 and correct the stale memory note**

- Mark t871 done in MM30 `tasks/active.md` with a note pointing at this design/plan and the merged upstream commits; drop the stale clinical-warning framing.
- Correct `reference_commons_dataset_promotion.md` (the capability-stripping gotcha is now fixed upstream; note the preservation contract + the P3 resolver) and update the `MEMORY.md` one-liner.
- Correct the `capability_fit_gate` memory line that still says "8 clinical-only warns standing pending user decision" — those were cleared by t856's `capability_scope` adoption.

- [ ] **Step 5: Commit MM30 docs**

Auto-memory files live outside the repo tree (under the Claude project memory dir), so they are updated in place and are NOT part of this git commit — only `tasks/active.md` is version-controlled here:

```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
git add tasks/active.md
git commit -m "docs(t871): close — upstream commons capability-preservation fix landed"
```

---

## Self-Review

- **Spec coverage:** P1 (Task 1), P1 identity_context composition (Task 2), P4 guard + shared constant (Task 3), P3 resolver (Task 4), P3 gate wiring incl. defer/error split (Task 5), P1+P4 apply integration (Task 6), adoption/backfill/rescope (Task 7). All design sections mapped.
- **P2:** intentionally absent — folded into P1 per the design (canonical-only fields surface through `merge_entity` automatically).
- **Type consistency:** `INTRINSIC_DATASET_FIELDS` single-sourced in `datasets/intrinsic.py` and imported by promote (Task 3). `CommonsUnavailable`/`OverlayResolutionError` defined in Task 4, imported in Task 5. `effective_dataset_frontmatter(overlay_fm, *, resolver=...)` signature identical across Tasks 4-5.
- **Open implementer confirmations (flagged inline, not placeholders):** commons error constructor signatures (Task 4) must be read from the current code before running — the step says so and names where to look.
