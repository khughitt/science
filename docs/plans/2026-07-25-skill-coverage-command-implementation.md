# `science skills coverage` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `science skills coverage` — a portfolio scan that joins what analyses touch (data-product terms via `dataset_usage` ∪ `related: dataset:*` → dataset `provided_capabilities`) against what the corpus covers (leaf `covers:` via the overlay) and what each plan loaded (reified `skills_loaded`), emitting a `coverage-report` JSON with evidence-backed skill candidates.

**Architecture:** A pure `science-model` engine (`skill_coverage/coverage.py`) owns the input evidence types, the overlay/catalog join, coverage-state classification, cross-project candidate generation, the discriminated-union report, and canonical serialization. A `science-tool` shell (`skills_coverage/`) enumerates the registry, projects each enrolled project's entities into `ProjectEvidence`, calls the engine, and wires the CLI. `science-tool` depends on `science-model`, never the reverse.

**Tech Stack:** Python 3.13, Pydantic v2, click, pytest. Design doc: [`2026-07-25-skill-coverage-command-design.md`](2026-07-25-skill-coverage-command-design.md). Parent: [`2026-07-23-data-product-vocabulary-and-skill-coverage-design.md`](2026-07-23-data-product-vocabulary-and-skill-coverage-design.md).

## Global Constraints

- No AI-attribution trailers/footers on commits.
- Composition over inheritance; explicit over defensive; fail early — no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- `uv`/pytest/ruff run from `science/` (CLI) or `science/model/` (model), never the repo root. Pyright is configured once by the repo-root `pyrightconfig.json`; test dirs are not type-checked.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) for any filepaths written into docs/code.
- Work happens in the existing worktree on branch `skill-coverage-command`. Commit after each task.
- **Grounded facts (verified at `c06e6073`):**
  - Enrollment reader: `science_tool.project_config.domain_enrollment(config, "molecular-measurement") -> EnrollmentStatus | Literal["undeclared"]`; loader `load_project_config(root) -> ProjectConfig`. `EnrollmentStatus` (StrEnum: `ENROLLED="enrolled"`, `OUT_OF_DOMAIN="out-of-domain"`) is in `science_model.skill_coverage`.
  - Registry: `science_tool.registry.config.load_global_config(config_path=None) -> GlobalConfig`; `.projects: list[RegisteredProject]{path, name, id: str|None, ...}`. `science.yaml` path = `science_model.frontmatter.project_config_path(root)`.
  - Loader: `science_tool.graph.sources.load_project_sources(root, include_commons=True) -> ProjectSources` with `.entities`, `.skill_loads: list[SkillLoadRecord]{plan_id, canonical_skill_id, reason}`, `.manual_aliases`, `.archive_alias_tokens`, `.entity_source_adapters: dict[str,str]`.
  - Resolver: `science_tool.graph.reference_resolution.ReferenceResolver.from_entities(entities, manual_aliases=, archive_alias_tokens=, identity_table=)`; `science_tool.graph.identity_table.build_identity_table(sources)`; `resolver.resolve(raw) -> ReferenceResolution{status: str, canonical_id: str|None}` (resolved ⟺ `status == "resolved"`).
  - Capabilities: `science_tool.datasets.capability_shape.parse_gen3_capabilities(value) -> list[Capability]`; `Capability.data_product` keeps the `data-product:` prefix. `provided_capabilities` and `capability_scope` are raw in `entity.model_extra`.
  - Overlay/catalog: `science_model.skill_coverage.build_skill_overlay(inventory, catalog) -> SkillOverlay` (iterates skills in id order; `LeafSkill{id, archetype, covers: tuple, role="leaf"}`); `science_tool.graph.skill_inventory.load_skill_inventory() -> dict`; `science_model.data_products.load_catalog() -> DataProductCatalog` (`.by_id`, `.terms`; `DataProductTerm{id, broader: list[str]}`).
  - Commons discriminator: a dataset is commons-owned iff `sources.entity_source_adapters[id] == "commons-merged"` (the owner adapter). **Never** use `commons_overlay_paths` (borrowers only — inverted).
  - `Entity`: `.kind`, `.canonical_id`, `.model_extra`, `.related: list[str]|None`, `.dataset_usage: list[DatasetUsage]{ref}`.
  - Existing `skills` command group: `science_tool.skills_lint.cli.skills_group` (`@skills_group.command(...)`).

---

### Task 1: Coverage types + canonical serialization (`science-model`)

**Files:**
- Create: `science/model/src/science_model/skill_coverage/coverage.py`
- Modify: `science/model/src/science_model/skill_coverage/__init__.py`
- Test: `science/model/tests/test_coverage_types.py`

**Interfaces:**
- Produces (input): `SkillCoverageError(ValueError)`; frozen `TermUsage{plan_ref, dataset_ref, term, owned}`, `DatasetUse{plan_ref, dataset_ref}`, `PlanSkills{plan_ref, skill_ids: tuple[str,...]}`, `UnresolvedRef{plan_ref, ref}`, `ProjectEvidence{project, enrollment, term_usages=(), untagged_usages=(), plan_loaded_skills=(), unresolved_related_refs=()}` with `__post_init__` rejecting facts when not enrolled.
- Produces (output): frozen `EvidencePair{plan_ref, dataset_ref}`, `EvidenceTriple{project, plan_ref, dataset_ref}`, `OutOfDomainResult`, `UndeclaredDomainResult`, `UnmappedOccurrence`, `UncoveredOccurrence`, `CoveredNotLoadedOccurrence`, `SkillReferenceDiagnostic`, `DatasetReferenceDiagnostic`, `Candidate`, `ReportScope`, `SkippedProject`, `CoverageReport` (each with `to_dict()`); `serialize_coverage_report(report) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_coverage_types.py
from __future__ import annotations

import json

import pytest

from science_model.skill_coverage import EnrollmentStatus
from science_model.skill_coverage.coverage import (
    Candidate,
    CoverageReport,
    CoveredNotLoadedOccurrence,
    DatasetReferenceDiagnostic,
    EvidencePair,
    EvidenceTriple,
    OutOfDomainResult,
    ProjectEvidence,
    ReportScope,
    SkillCoverageError,
    SkillReferenceDiagnostic,
    SkippedProject,
    TermUsage,
    UncoveredOccurrence,
    UndeclaredDomainResult,
    UnmappedOccurrence,
    serialize_coverage_report,
)


def test_project_evidence_rejects_facts_when_not_enrolled() -> None:
    with pytest.raises(SkillCoverageError, match="non-enrolled"):
        ProjectEvidence(
            project="p", enrollment="undeclared",
            term_usages=(TermUsage("plan:1", "dataset:x", "data-product:t", True),),
        )
    # enrolled with facts is fine; non-enrolled with no facts is fine
    ProjectEvidence(project="p", enrollment=EnrollmentStatus.ENROLLED,
                    untagged_usages=(),)
    ProjectEvidence(project="p", enrollment=EnrollmentStatus.OUT_OF_DOMAIN)


def test_occurrence_to_dict_shapes() -> None:
    assert OutOfDomainResult("p").to_dict() == {"state": "out-of-domain", "project": "p"}
    assert UndeclaredDomainResult("p").to_dict() == {"state": "undeclared-domain", "project": "p"}
    um = UnmappedOccurrence("p", "dataset:x", (EvidencePair("plan:1", "dataset:x"),))
    assert um.to_dict() == {
        "state": "unmapped", "project": "p", "dataset_ref": "dataset:x",
        "observation_level": "analysis-usage",
        "evidence_refs": [{"plan_ref": "plan:1", "dataset_ref": "dataset:x"}],
    }
    cnl = CoveredNotLoadedOccurrence("p", "data-product:t", ("bio-x",),
                                     (EvidencePair("plan:1", "dataset:x"),))
    assert cnl.to_dict()["available_skill_ids"] == ["bio-x"]
    assert cnl.to_dict()["state"] == "covered-not-loaded"


def test_report_orders_deterministically_including_tying_unmapped() -> None:
    # Two unmapped entries in one project tie on (state, project, "") and must fall
    # through to the scalar evidence-pair key without raising (the list-of-dicts guard).
    report = CoverageReport(
        scope=ReportScope("portfolio"),
        coverage_occurrences=(
            UnmappedOccurrence("p", "dataset:b", (EvidencePair("plan:2", "dataset:b"),)),
            UnmappedOccurrence("p", "dataset:a", (EvidencePair("plan:1", "dataset:a"),)),
            UncoveredOccurrence("p", "data-product:t", (EvidencePair("plan:1", "dataset:a"),)),
        ),
        skill_reference_diagnostics=(SkillReferenceDiagnostic("p", "plan:9", "ghost"),),
        dataset_reference_diagnostics=(DatasetReferenceDiagnostic("p", "plan:9", "dataset:gone"),),
        candidates=(
            Candidate("data-product:t", "indeterminate", 0.5,
                      (EvidenceTriple("p", "plan:1", "dataset:a"),)),
        ),
        skipped_projects=(SkippedProject("/x/stale", "path missing or no science.yaml"),),
    )
    text = serialize_coverage_report(report)
    assert text.endswith("\n")
    obj = json.loads(text)
    # unmapped entries sorted by their (plan_ref, dataset_ref) pair key
    unmapped = [o for o in obj["coverage_occurrences"] if o["state"] == "unmapped"]
    assert [o["dataset_ref"] for o in unmapped] == ["dataset:a", "dataset:b"]
    assert obj["scope"] == {"mode": "portfolio"}
    assert obj["skipped_projects"] == [{"path": "/x/stale", "reason": "path missing or no science.yaml"}]
    assert serialize_coverage_report(report) == text  # deterministic


def test_scope_single_project_carries_project() -> None:
    assert ReportScope("single-project", "mm30").to_dict() == {"mode": "single-project", "project": "mm30"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_coverage_types.py -v`
Expected: FAIL — `science_model.skill_coverage.coverage` does not exist.

- [ ] **Step 3: Implement the types + serialization**

```python
# science/model/src/science_model/skill_coverage/coverage.py
"""Pure coverage engine: evidence input types, the overlay/catalog join, coverage-state
classification, cross-project candidates, and the discriminated-union `coverage-report`.

No I/O and no corpus/graph access: `science_tool` projects entities into `ProjectEvidence`
and calls `compute_coverage`. `science_model` never imports `science_tool`.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from science_model.skill_coverage.overlay import LeafSkill, SkillOverlay

if TYPE_CHECKING:
    from science_model.data_products import DataProductCatalog
    from science_model.skill_coverage import EnrollmentStatus


class SkillCoverageError(ValueError):
    """A structural violation in the coverage inputs (e.g. an off-catalog owned term)."""


# --- input evidence types (filled by science_tool's projection) ---

@dataclass(frozen=True, slots=True)
class TermUsage:
    plan_ref: str
    dataset_ref: str
    term: str
    owned: bool


@dataclass(frozen=True, slots=True)
class DatasetUse:
    plan_ref: str
    dataset_ref: str


@dataclass(frozen=True, slots=True)
class PlanSkills:
    plan_ref: str
    skill_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnresolvedRef:
    plan_ref: str
    ref: str


@dataclass(frozen=True, slots=True)
class ProjectEvidence:
    project: str
    # EnrollmentStatus is a StrEnum; compared by value below so this module never imports the
    # skill_coverage package __init__ (which would be a circular import).
    enrollment: "EnrollmentStatus | Literal['undeclared']"
    term_usages: tuple[TermUsage, ...] = ()
    untagged_usages: tuple[DatasetUse, ...] = ()
    plan_loaded_skills: tuple[PlanSkills, ...] = ()
    unresolved_related_refs: tuple[UnresolvedRef, ...] = ()

    def __post_init__(self) -> None:
        if self.enrollment != "enrolled" and (
            self.term_usages or self.untagged_usages
            or self.plan_loaded_skills or self.unresolved_related_refs
        ):
            raise SkillCoverageError(
                f"{self.project}: a non-enrolled ProjectEvidence must carry no facts"
            )


# --- output types ---

@dataclass(frozen=True, slots=True)
class EvidencePair:
    plan_ref: str
    dataset_ref: str

    def to_dict(self) -> dict[str, str]:
        return {"plan_ref": self.plan_ref, "dataset_ref": self.dataset_ref}


@dataclass(frozen=True, slots=True)
class EvidenceTriple:
    project: str
    plan_ref: str
    dataset_ref: str

    def to_dict(self) -> dict[str, str]:
        return {"project": self.project, "plan_ref": self.plan_ref, "dataset_ref": self.dataset_ref}


@dataclass(frozen=True, slots=True)
class OutOfDomainResult:
    project: str

    def to_dict(self) -> dict[str, str]:
        return {"state": "out-of-domain", "project": self.project}


@dataclass(frozen=True, slots=True)
class UndeclaredDomainResult:
    project: str

    def to_dict(self) -> dict[str, str]:
        return {"state": "undeclared-domain", "project": self.project}


@dataclass(frozen=True, slots=True)
class UnmappedOccurrence:
    project: str
    dataset_ref: str
    evidence_refs: tuple[EvidencePair, ...]
    observation_level: str = "analysis-usage"

    def to_dict(self) -> dict[str, object]:
        return {
            "state": "unmapped", "project": self.project, "dataset_ref": self.dataset_ref,
            "observation_level": self.observation_level,
            "evidence_refs": [e.to_dict() for e in self.evidence_refs],
        }


@dataclass(frozen=True, slots=True)
class UncoveredOccurrence:
    project: str
    term: str
    evidence_refs: tuple[EvidencePair, ...]
    observation_level: str = "analysis-usage"

    def to_dict(self) -> dict[str, object]:
        return {
            "state": "uncovered", "project": self.project, "term": self.term,
            "observation_level": self.observation_level,
            "evidence_refs": [e.to_dict() for e in self.evidence_refs],
        }


@dataclass(frozen=True, slots=True)
class CoveredNotLoadedOccurrence:
    project: str
    term: str
    available_skill_ids: tuple[str, ...]
    evidence_refs: tuple[EvidencePair, ...]
    observation_level: str = "analysis-usage"

    def to_dict(self) -> dict[str, object]:
        return {
            "state": "covered-not-loaded", "project": self.project, "term": self.term,
            "observation_level": self.observation_level,
            "available_skill_ids": list(self.available_skill_ids),
            "evidence_refs": [e.to_dict() for e in self.evidence_refs],
        }


Occurrence = (
    OutOfDomainResult | UndeclaredDomainResult | UnmappedOccurrence
    | UncoveredOccurrence | CoveredNotLoadedOccurrence
)


@dataclass(frozen=True, slots=True)
class SkillReferenceDiagnostic:
    project: str
    plan_ref: str
    skill_id: str

    def to_dict(self) -> dict[str, str]:
        return {"project": self.project, "plan_ref": self.plan_ref, "skill_id": self.skill_id}


@dataclass(frozen=True, slots=True)
class DatasetReferenceDiagnostic:
    project: str
    plan_ref: str
    ref: str

    def to_dict(self) -> dict[str, str]:
        return {"project": self.project, "plan_ref": self.plan_ref, "ref": self.ref}


@dataclass(frozen=True, slots=True)
class Candidate:
    proposed_scope: str
    likely_archetype: str  # a catalog archetype, or "indeterminate"
    score: float
    evidence: tuple[EvidenceTriple, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "proposed_scope": self.proposed_scope, "likely_archetype": self.likely_archetype,
            "score": self.score, "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class ReportScope:
    mode: str  # "portfolio" | "single-project"
    project: str | None = None

    def to_dict(self) -> dict[str, str]:
        out = {"mode": self.mode}
        if self.project is not None:
            out["project"] = self.project
        return out


@dataclass(frozen=True, slots=True)
class SkippedProject:
    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason}


def _occurrence_sort_key(occ: Occurrence) -> tuple:
    data = occ.to_dict()
    evidence = getattr(occ, "evidence_refs", ())
    pairs = tuple(sorted((e.plan_ref, e.dataset_ref) for e in evidence))
    return (
        data["state"], getattr(occ, "project", ""), getattr(occ, "term", "") or "",
        getattr(occ, "dataset_ref", "") or "", pairs,
    )


@dataclass(frozen=True, slots=True)
class CoverageReport:
    scope: ReportScope
    coverage_occurrences: tuple[Occurrence, ...]
    skill_reference_diagnostics: tuple[SkillReferenceDiagnostic, ...]
    dataset_reference_diagnostics: tuple[DatasetReferenceDiagnostic, ...]
    candidates: tuple[Candidate, ...]
    skipped_projects: tuple[SkippedProject, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope.to_dict(),
            "coverage_occurrences": [
                o.to_dict() for o in sorted(self.coverage_occurrences, key=_occurrence_sort_key)
            ],
            "skill_reference_diagnostics": [
                d.to_dict() for d in sorted(
                    self.skill_reference_diagnostics,
                    key=lambda d: (d.project, d.plan_ref, d.skill_id),
                )
            ],
            "dataset_reference_diagnostics": [
                d.to_dict() for d in sorted(
                    self.dataset_reference_diagnostics,
                    key=lambda d: (d.project, d.plan_ref, d.ref),
                )
            ],
            "candidates": [
                c.to_dict() for c in sorted(
                    self.candidates, key=lambda c: (-c.score, c.proposed_scope)
                )
            ],
            "skipped_projects": [
                s.to_dict() for s in sorted(self.skipped_projects, key=lambda s: s.path)
            ],
        }


def serialize_coverage_report(report: CoverageReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
```

- [ ] **Step 4: Export from the package**

In `science/model/src/science_model/skill_coverage/__init__.py`, add (after the existing `EnrollmentStatus`/domain definitions — the coverage import must come after so `TYPE_CHECKING` stays clean and there is no runtime cycle):

```python
from science_model.skill_coverage.coverage import (
    Candidate,
    CoverageReport,
    CoveredNotLoadedOccurrence,
    DatasetReferenceDiagnostic,
    EvidencePair,
    EvidenceTriple,
    OutOfDomainResult,
    PlanSkills,
    ProjectEvidence,
    ReportScope,
    SkillCoverageError,
    SkillReferenceDiagnostic,
    SkippedProject,
    TermUsage,
    DatasetUse,
    UncoveredOccurrence,
    UndeclaredDomainResult,
    UnmappedOccurrence,
    UnresolvedRef,
    serialize_coverage_report,
)
```

and add each of those names to the existing `__all__` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_coverage_types.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/skill_coverage/coverage.py science/model/src/science_model/skill_coverage/__init__.py science/model/tests/test_coverage_types.py
git commit -m "feat(skill-coverage): coverage-report types and canonical serialization"
```

---

### Task 2: `compute_coverage` — join, states, candidates (`science-model`)

**Files:**
- Modify: `science/model/src/science_model/skill_coverage/coverage.py`
- Modify: `science/model/src/science_model/skill_coverage/__init__.py`
- Test: `science/model/tests/test_compute_coverage.py`

**Interfaces:**
- Consumes: all Task 1 types; `SkillOverlay`, `LeafSkill`; `DataProductCatalog` (`.by_id`, `.terms`).
- Produces: `compute_coverage(projects: list[ProjectEvidence], overlay: SkillOverlay, catalog: DataProductCatalog, *, scope: ReportScope, skipped_projects: tuple[SkippedProject, ...] = ()) -> CoverageReport`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_compute_coverage.py
from __future__ import annotations

import pytest

from science_model.data_products import build_catalog
from science_model.skill_coverage import EnrollmentStatus, build_skill_overlay
from science_model.skill_coverage.coverage import (
    DatasetUse,
    PlanSkills,
    ProjectEvidence,
    ReportScope,
    SkillCoverageError,
    TermUsage,
    UnresolvedRef,
    compute_coverage,
)

_SCOPE = ReportScope("portfolio")


def _catalog():
    return build_catalog({
        "schema_version": "1",
        "terms": [
            {"id": "data-product:parent", "label": "P", "assay": "a"},
            {"id": "data-product:child-a", "label": "CA", "assay": "a",
             "broader": ["data-product:parent"]},
            {"id": "data-product:child-b", "label": "CB", "assay": "a",
             "broader": ["data-product:parent"]},
            {"id": "data-product:lonely", "label": "L", "assay": "a"},
        ],
    })


def _overlay(catalog):
    # child-a is covered by a measurement-qa leaf; nothing covers child-b/parent/lonely.
    inv = {"skills": [
        {"id": "bio-ca-qa", "name": "bio-ca-qa", "path": "skills/ca.md", "role": "leaf",
         "description": "d", "archetype": "measurement-qa", "covers": ["data-product:child-a"]},
    ]}
    return build_skill_overlay(inv, catalog)


def test_non_enrolled_single_results() -> None:
    catalog = _catalog()
    report = compute_coverage(
        [ProjectEvidence("p1", EnrollmentStatus.OUT_OF_DOMAIN),
         ProjectEvidence("p2", "undeclared")],
        _overlay(catalog), catalog, scope=_SCOPE,
    )
    states = {o.to_dict()["state"] for o in report.coverage_occurrences}
    assert states == {"out-of-domain", "undeclared-domain"}


def test_uncovered_and_candidate_with_sibling_inference() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    # child-b is touched but uncovered; its sibling child-a is covered by a measurement-qa leaf.
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:child-b", True),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    unc = [o for o in report.coverage_occurrences if o.to_dict()["state"] == "uncovered"]
    assert len(unc) == 1 and unc[0].term == "data-product:child-b"
    assert len(report.candidates) == 1
    cand = report.candidates[0]
    assert cand.proposed_scope == "data-product:child-b"
    assert cand.score == 0.5  # 1 occurrence, 1 project -> 1 - 1/(1+1+0)
    assert cand.likely_archetype == "measurement-qa"  # sibling child-a consensus


def test_exact_term_not_ancestor_aware() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    # A leaf covering child-a does NOT cover the parent term.
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:parent", True),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    assert [o.to_dict()["state"] for o in report.coverage_occurrences] == ["uncovered"]


def test_covered_not_loaded_vs_loaded() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    # plan:1 touches child-a (covered by bio-ca-qa) but loaded nothing -> covered-not-loaded;
    # plan:2 touches child-a and loaded bio-ca-qa -> healthy (nothing emitted).
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        term_usages=(
            TermUsage("plan:1", "dataset:x", "data-product:child-a", True),
            TermUsage("plan:2", "dataset:x", "data-product:child-a", True),
        ),
        plan_loaded_skills=(PlanSkills("plan:2", ("bio-ca-qa",)),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    cnl = [o for o in report.coverage_occurrences if o.to_dict()["state"] == "covered-not-loaded"]
    assert len(cnl) == 1
    assert cnl[0].available_skill_ids == ("bio-ca-qa",)
    assert {(e.plan_ref) for e in cnl[0].evidence_refs} == {"plan:1"}  # only the non-loading plan


def test_unmapped_and_skill_and_dataset_diagnostics() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        untagged_usages=(DatasetUse("plan:1", "dataset:untagged"),),
        plan_loaded_skills=(PlanSkills("plan:1", ("ghost-skill",)),),
        unresolved_related_refs=(UnresolvedRef("plan:1", "dataset:gone"),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    assert [o.to_dict()["state"] for o in report.coverage_occurrences] == ["unmapped"]
    assert report.skill_reference_diagnostics[0].skill_id == "ghost-skill"
    assert report.dataset_reference_diagnostics[0].ref == "dataset:gone"


def test_off_catalog_owned_raises_commons_skips() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    owned = ProjectEvidence("p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:ghost", True),))
    with pytest.raises(SkillCoverageError, match="off-catalog"):
        compute_coverage([owned], overlay, catalog, scope=_SCOPE)
    commons = ProjectEvidence("p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:ghost", False),))
    report = compute_coverage([commons], overlay, catalog, scope=_SCOPE)
    assert report.coverage_occurrences == ()  # commons off-catalog silently skipped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_compute_coverage.py -v`
Expected: FAIL — `compute_coverage` does not exist.

- [ ] **Step 3: Implement `compute_coverage` + helpers**

Append to `science/model/src/science_model/skill_coverage/coverage.py`:

```python
def _covering_leaf_ids(term: str, overlay: SkillOverlay) -> set[str]:
    return {s.id for s in overlay if isinstance(s, LeafSkill) and term in s.covers}


def _infer_archetype(term: str, overlay: SkillOverlay, catalog: "DataProductCatalog") -> str:
    entry = catalog.by_id.get(term)
    if entry is None or not entry.broader:
        return "indeterminate"
    parents = set(entry.broader)
    sibling_ids = {
        t.id for t in catalog.terms if t.id != term and (set(t.broader) & parents)
    }
    archetypes = {
        s.archetype for s in overlay
        if isinstance(s, LeafSkill) and any(cov in sibling_ids for cov in s.covers)
    }
    if len(archetypes) == 1:
        return next(iter(archetypes))
    return "indeterminate"


def _build_candidates(
    uncovered: dict[str, list[EvidenceTriple]], overlay: SkillOverlay, catalog: "DataProductCatalog"
) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for term, triples in uncovered.items():
        unique = sorted({(t.project, t.plan_ref, t.dataset_ref) for t in triples})
        n_occurrences = len(unique)
        n_projects = len({project for project, _, _ in unique})
        score = round(1 - 1 / (1 + n_occurrences + (n_projects - 1)), 3)
        evidence = tuple(EvidenceTriple(p, pl, d) for p, pl, d in unique)
        candidates.append(Candidate(
            proposed_scope=term,
            likely_archetype=_infer_archetype(term, overlay, catalog),
            score=score, evidence=evidence,
        ))
    return tuple(candidates)


def compute_coverage(
    projects: list[ProjectEvidence],
    overlay: SkillOverlay,
    catalog: "DataProductCatalog",
    *,
    scope: ReportScope,
    skipped_projects: tuple[SkippedProject, ...] = (),
) -> CoverageReport:
    catalog_ids = catalog.by_id
    occurrences: list[Occurrence] = []
    skill_diags: list[SkillReferenceDiagnostic] = []
    dataset_diags: list[DatasetReferenceDiagnostic] = []
    uncovered: dict[str, list[EvidenceTriple]] = defaultdict(list)

    for ev in projects:
        if ev.enrollment == "out-of-domain":
            occurrences.append(OutOfDomainResult(ev.project))
            continue
        if ev.enrollment == "undeclared":
            occurrences.append(UndeclaredDomainResult(ev.project))
            continue
        # enrolled
        for unresolved in ev.unresolved_related_refs:
            dataset_diags.append(
                DatasetReferenceDiagnostic(ev.project, unresolved.plan_ref, unresolved.ref)
            )
        for untagged in ev.untagged_usages:
            occurrences.append(UnmappedOccurrence(
                ev.project, untagged.dataset_ref,
                (EvidencePair(untagged.plan_ref, untagged.dataset_ref),),
            ))
        for plan_skills in ev.plan_loaded_skills:
            for skill_id in plan_skills.skill_ids:
                if overlay.get(skill_id) is None:
                    skill_diags.append(
                        SkillReferenceDiagnostic(ev.project, plan_skills.plan_ref, skill_id)
                    )
        loaded_by_plan = {ps.plan_ref: set(ps.skill_ids) for ps in ev.plan_loaded_skills}

        by_term: dict[str, list[TermUsage]] = defaultdict(list)
        for usage in ev.term_usages:
            if usage.term not in catalog_ids:
                if usage.owned:
                    raise SkillCoverageError(
                        f"{ev.project}: dataset {usage.dataset_ref} declares off-catalog "
                        f"data_product {usage.term!r}"
                    )
                continue  # commons off-catalog: skip, not this project's integrity gate
            by_term[usage.term].append(usage)

        for term, usages in by_term.items():
            covering = _covering_leaf_ids(term, overlay)
            all_pairs = tuple(EvidencePair(p, d) for p, d in sorted(
                {(u.plan_ref, u.dataset_ref) for u in usages}
            ))
            if not covering:
                occurrences.append(UncoveredOccurrence(ev.project, term, all_pairs))
                for usage in usages:
                    uncovered[term].append(
                        EvidenceTriple(ev.project, usage.plan_ref, usage.dataset_ref)
                    )
                continue
            plans_touching = {u.plan_ref for u in usages}
            not_loaded = {p for p in plans_touching if not (loaded_by_plan.get(p, set()) & covering)}
            if not_loaded:
                nl_pairs = tuple(EvidencePair(p, d) for p, d in sorted(
                    {(u.plan_ref, u.dataset_ref) for u in usages if u.plan_ref in not_loaded}
                ))
                occurrences.append(CoveredNotLoadedOccurrence(
                    ev.project, term, tuple(sorted(covering)), nl_pairs,
                ))

    return CoverageReport(
        scope=scope,
        coverage_occurrences=tuple(occurrences),
        skill_reference_diagnostics=tuple(skill_diags),
        dataset_reference_diagnostics=tuple(dataset_diags),
        candidates=_build_candidates(uncovered, overlay, catalog),
        skipped_projects=skipped_projects,
    )
```

- [ ] **Step 4: Export `compute_coverage`**

Add `compute_coverage` to the `from science_model.skill_coverage.coverage import (...)` block and `__all__` in `science/model/src/science_model/skill_coverage/__init__.py`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_compute_coverage.py tests/test_coverage_types.py -v`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
cd science/model && uv run ruff check src/science_model/skill_coverage/coverage.py tests/test_compute_coverage.py
cd ../.. && git add science/model/src/science_model/skill_coverage/coverage.py science/model/src/science_model/skill_coverage/__init__.py science/model/tests/test_compute_coverage.py
git commit -m "feat(skill-coverage): compute_coverage join, states, and candidates"
```

---

### Task 3: Evidence projection (`science-tool`)

**Files:**
- Create: `science/src/science_tool/skills_coverage/__init__.py`
- Create: `science/src/science_tool/skills_coverage/evidence.py`
- Test: `science/tests/skills_coverage/test_evidence.py`

**Interfaces:**
- Consumes: `ProjectSources`; `ReferenceResolver`, `build_identity_table`, `parse_gen3_capabilities`; the Task 1 input types; `EnrollmentStatus`.
- Produces: `SkillCoverageScanError(Exception)`; `project_evidence(project: str, sources: ProjectSources) -> ProjectEvidence`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/skills_coverage/test_evidence.py
from __future__ import annotations

from pathlib import Path

from science_model.skill_coverage import EnrollmentStatus

from science_tool.graph.sources import load_project_sources
from science_tool.skills_coverage.evidence import project_evidence


def _gen3_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project, write_markdown_entity
    seed_project(root)
    # Pin gen-3 so provided_capabilities validates and skills_loaded reifies.
    cfg = root / "science.yaml"
    cfg.write_text(cfg.read_text() + "\nentity_schema_version: 3\n", encoding="utf-8")
    write_markdown_entity(root, "entities/datasets/tagged.md", {
        "id": "dataset:tagged", "kind": "dataset",
        "provided_capabilities": [{"data_product": "data-product:child-a"}],
    }, "A tagged dataset.")
    write_markdown_entity(root, "entities/datasets/bare.md", {
        "id": "dataset:bare", "kind": "dataset",
    }, "An untagged dataset.")
    write_markdown_entity(root, "entities/datasets/scoped.md", {
        "id": "dataset:scoped", "kind": "dataset", "capability_scope": "reference-only",
    }, "A dataset whose empty capabilities are intentional.")
    write_markdown_entity(root, "entities/plans/0001-p.md", {
        "id": "plan:0001-p", "kind": "plan",
        "related": ["dataset:tagged", "dataset:bare", "dataset:scoped"],
        "skills_loaded": [{"id": "bio-ca-qa", "reason": "QA the scRNA measurement."}],
    }, "A plan that relates to three datasets.")


def test_project_evidence_union_edge_and_untagged(tmp_path: Path) -> None:
    _gen3_project(tmp_path)
    sources = load_project_sources(tmp_path, include_commons=True)
    ev = project_evidence("proj", sources)
    assert ev.enrollment == EnrollmentStatus.ENROLLED
    # related:dataset:tagged -> a term usage (via the union edge, no dataset_usage authored)
    assert any(t.dataset_ref == "dataset:tagged" and t.term == "data-product:child-a" and t.owned
               for t in ev.term_usages)
    # related:dataset:bare -> untagged usage (owned, no capability_scope)
    assert any(u.dataset_ref == "dataset:bare" for u in ev.untagged_usages)
    # related:dataset:scoped -> NOT untagged debt (capability_scope honored)
    assert all(u.dataset_ref != "dataset:scoped" for u in ev.untagged_usages)
    # skills_loaded grouped per plan
    assert ev.plan_loaded_skills[0].skill_ids == ("bio-ca-qa",)


def test_project_evidence_unresolved_related_is_diagnostic(tmp_path: Path) -> None:
    from _fixtures.entity_helpers import write_markdown_entity
    _gen3_project(tmp_path)
    write_markdown_entity(tmp_path, "entities/plans/0002-q.md", {
        "id": "plan:0002-q", "kind": "plan", "related": ["dataset:does-not-exist"],
    }, "A plan relating to a missing dataset.")
    sources = load_project_sources(tmp_path, include_commons=True)
    ev = project_evidence("proj", sources)
    assert any(u.ref == "dataset:does-not-exist" for u in ev.unresolved_related_refs)
```

Note: `project_evidence` is only called for enrolled projects by the scan; the test builds a gen-3 project and asserts `enrollment == ENROLLED` (set unconditionally by `project_evidence`, since the scan only invokes it after confirming enrollment).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_evidence.py -v`
Expected: FAIL — module does not exist. (Create `science/tests/skills_coverage/__init__.py` if the test layout needs it; mirror the sibling test packages.)

- [ ] **Step 3: Implement the projection**

```python
# science/src/science_tool/skills_coverage/__init__.py
"""The `science skills coverage` portfolio scan: evidence projection, scan, and CLI."""
```

```python
# science/src/science_tool/skills_coverage/evidence.py
"""Project a loaded ProjectSources into the pure `ProjectEvidence` the coverage engine consumes.

This is the only place `provided_capabilities`, `dataset_usage`, `related`, and `skill_loads`
are read off entities. The plan->dataset edge is `dataset_usage` UNION `related: dataset:*`,
resolved through the same ReferenceResolver semantics materialization uses; a commons-owned
dataset is identified by its owner adapter (`entity_source_adapters[id] == "commons-merged"`).
"""

from __future__ import annotations

from collections import defaultdict

from science_model.skill_coverage import EnrollmentStatus
from science_model.skill_coverage.coverage import (
    DatasetUse,
    PlanSkills,
    ProjectEvidence,
    TermUsage,
    UnresolvedRef,
)

from science_tool.datasets.capability_shape import parse_gen3_capabilities
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import ProjectSources

_COMMONS_ADAPTER = "commons-merged"


class SkillCoverageScanError(Exception):
    """A coverage scan cannot proceed (bad registry entry, dangling typed usage, etc.)."""


def _resolve_dataset(ref: str, resolver: ReferenceResolver) -> str | None:
    resolution = resolver.resolve(ref)
    if (
        resolution.status == "resolved"
        and resolution.canonical_id is not None
        and resolution.canonical_id.startswith("dataset:")
    ):
        return resolution.canonical_id
    return None


def project_evidence(project: str, sources: ProjectSources) -> ProjectEvidence:
    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
        identity_table=build_identity_table(sources),
    )
    adapters = sources.entity_source_adapters

    # dataset canonical_id -> (terms, owned, scoped)
    dataset_terms: dict[str, frozenset[str]] = {}
    dataset_owned: dict[str, bool] = {}
    dataset_scoped: dict[str, bool] = {}
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        extra = entity.model_extra or {}
        raw_caps = extra.get("provided_capabilities")
        terms = (
            frozenset(cap.data_product for cap in parse_gen3_capabilities(raw_caps))
            if raw_caps else frozenset()
        )
        dataset_terms[entity.canonical_id] = terms
        dataset_owned[entity.canonical_id] = adapters.get(entity.canonical_id) != _COMMONS_ADAPTER
        dataset_scoped[entity.canonical_id] = bool(extra.get("capability_scope"))

    loaded: dict[str, list[str]] = defaultdict(list)
    for record in sources.skill_loads:
        loaded[record.plan_id].append(record.canonical_skill_id)

    term_usages: list[TermUsage] = []
    untagged_usages: list[DatasetUse] = []
    unresolved: list[UnresolvedRef] = []

    for entity in sources.entities:
        if entity.kind != "plan":
            continue
        plan_ref = entity.canonical_id
        edges: set[str] = set()
        # typed dataset_usage: a dangling ref is a hard error
        for usage in getattr(entity, "dataset_usage", None) or []:
            resolved = _resolve_dataset(str(usage.ref), resolver)
            if resolved is None:
                raise SkillCoverageScanError(
                    f"{project}: plan {plan_ref} dataset_usage ref {usage.ref!r} does not resolve"
                )
            edges.add(resolved)
        # related dataset refs: a dangling ref is a reported diagnostic, not an abort
        for raw in entity.related or []:
            if not raw.startswith("dataset:"):
                continue
            resolved = _resolve_dataset(raw, resolver)
            if resolved is None:
                unresolved.append(UnresolvedRef(plan_ref, raw))
                continue
            edges.add(resolved)

        for dataset_ref in edges:
            terms = dataset_terms.get(dataset_ref)
            if terms is None:
                raise SkillCoverageScanError(
                    f"{project}: plan {plan_ref} references {dataset_ref!r}, "
                    "which resolved but is not a loaded dataset entity"
                )
            if terms:
                for term in terms:
                    term_usages.append(
                        TermUsage(plan_ref, dataset_ref, term, dataset_owned[dataset_ref])
                    )
            elif dataset_owned[dataset_ref] and not dataset_scoped[dataset_ref]:
                untagged_usages.append(DatasetUse(plan_ref, dataset_ref))

    plan_loaded_skills = tuple(
        PlanSkills(plan_ref, tuple(sorted(set(skill_ids))))
        for plan_ref, skill_ids in loaded.items()
    )

    return ProjectEvidence(
        project=project,
        enrollment=EnrollmentStatus.ENROLLED,
        term_usages=tuple(term_usages),
        untagged_usages=tuple(untagged_usages),
        plan_loaded_skills=plan_loaded_skills,
        unresolved_related_refs=tuple(unresolved),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_evidence.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Lint + commit**

```bash
cd science && uv run ruff check src/science_tool/skills_coverage/
cd .. && git add science/src/science_tool/skills_coverage/ science/tests/skills_coverage/
git commit -m "feat(skill-coverage): project entities into ProjectEvidence (union edge, commons owner)"
```

---

### Task 4: Portfolio scan (`science-tool`)

**Files:**
- Create: `science/src/science_tool/skills_coverage/scan.py`
- Test: `science/tests/skills_coverage/test_scan.py`

**Interfaces:**
- Consumes: `load_global_config`, `project_config_path`, `load_project_config`, `domain_enrollment`, `load_project_sources`, `load_skill_inventory`, `build_skill_overlay`, `load_catalog`; `project_evidence`, `SkillCoverageScanError`; Task 1/2 types + `compute_coverage`.
- Produces: `COVERAGE_DOMAIN`; `scan_portfolio(config_path: Path | None = None, *, only: str | None = None) -> CoverageReport`; `write_report_atomically(path: Path, text: str) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/skills_coverage/test_scan.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.skills_coverage.scan import (
    SkillCoverageScanError,
    scan_portfolio,
    write_report_atomically,
)


def _enrolled_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nentity_schema_version: 3\nskill_coverage:\n  domains:\n    molecular-measurement: enrolled\n",
        encoding="utf-8",
    )


def _out_of_domain_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nskill_coverage:\n  domains:\n    molecular-measurement: out-of-domain\n",
        encoding="utf-8",
    )


def _registry(tmp_path: Path, entries: list[dict]) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"projects": entries}), encoding="utf-8")
    return config_path


def test_scan_classifies_and_skips(tmp_path: Path) -> None:
    enrolled = tmp_path / "enrolled"
    _enrolled_project(enrolled)
    ood = tmp_path / "ood"
    _out_of_domain_project(ood)
    config_path = _registry(tmp_path, [
        {"path": str(enrolled), "name": "enrolled", "id": "enrolled", "registered": "2026-07-25"},
        {"path": str(ood), "name": "ood", "id": "ood", "registered": "2026-07-25"},
        {"path": str(tmp_path / "gone"), "name": "gone", "id": "gone", "registered": "2026-07-25"},
    ])
    report = scan_portfolio(config_path)
    states = {o.to_dict().get("state") for o in report.coverage_occurrences}
    assert "out-of-domain" in states
    assert [s.path for s in report.skipped_projects] == [str(tmp_path / "gone")]
    assert report.scope.mode == "portfolio"


def test_scan_empty_registry_is_hard_error(tmp_path: Path) -> None:
    config_path = _registry(tmp_path, [])
    with pytest.raises(SkillCoverageScanError, match="no registered projects"):
        scan_portfolio(config_path)


def test_scan_duplicate_identifier_is_hard_error(tmp_path: Path) -> None:
    a = tmp_path / "a"; _enrolled_project(a)
    b = tmp_path / "b"; _enrolled_project(b)
    config_path = _registry(tmp_path, [
        {"path": str(a), "name": "dup", "id": "dup", "registered": "2026-07-25"},
        {"path": str(b), "name": "dup", "id": "dup", "registered": "2026-07-25"},
    ])
    with pytest.raises(SkillCoverageScanError, match="duplicate project identifier"):
        scan_portfolio(config_path)


def test_scan_single_project_scope(tmp_path: Path) -> None:
    enrolled = tmp_path / "enrolled"; _enrolled_project(enrolled)
    broken = tmp_path / "broken"; _enrolled_project(broken)
    (broken / "science.yaml").write_text("entity_schema_version: not-an-int\n", encoding="utf-8")
    config_path = _registry(tmp_path, [
        {"path": str(enrolled), "name": "enrolled", "id": "enrolled", "registered": "2026-07-25"},
        {"path": str(broken), "name": "broken", "id": "broken", "registered": "2026-07-25"},
    ])
    # --project isolates the good project even though 'broken' has invalid config
    report = scan_portfolio(config_path, only="enrolled")
    assert report.scope.mode == "single-project" and report.scope.project == "enrolled"
    with pytest.raises(SkillCoverageScanError, match="matched no registered project"):
        scan_portfolio(config_path, only="nope")


def test_atomic_write_leaves_target_untouched_on_prior_content(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    target.write_text("PRIOR", encoding="utf-8")
    write_report_atomically(target, "NEW\n")
    assert target.read_text(encoding="utf-8") == "NEW\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_scan.py -v`
Expected: FAIL — `scan.py` does not exist.

- [ ] **Step 3: Implement the scan**

```python
# science/src/science_tool/skills_coverage/scan.py
"""Enumerate the registry, classify/project each project, and assemble the coverage report."""

from __future__ import annotations

import os
from pathlib import Path

from science_model.data_products import load_catalog
from science_model.frontmatter import project_config_path
from science_model.skill_coverage import EnrollmentStatus, build_skill_overlay
from science_model.skill_coverage.coverage import (
    CoverageReport,
    ProjectEvidence,
    ReportScope,
    SkippedProject,
    compute_coverage,
)

from science_tool.graph.skill_inventory import load_skill_inventory
from science_tool.graph.sources import load_project_sources
from science_tool.project_config import domain_enrollment, load_project_config
from science_tool.registry.config import load_global_config
from science_tool.skills_coverage.evidence import SkillCoverageScanError, project_evidence

# v1 ships exactly the molecular-measurement domain (GENERATION_3_DOMAINS).
COVERAGE_DOMAIN = "molecular-measurement"


def scan_portfolio(config_path: Path | None = None, *, only: str | None = None) -> CoverageReport:
    config = load_global_config(config_path)
    projects = list(config.projects)
    if not projects:
        raise SkillCoverageScanError("no registered projects (empty or absent registry)")

    if only is not None:
        projects = [rp for rp in projects if (rp.id or rp.name) == only]
        if not projects:
            raise SkillCoverageScanError(f"--project {only!r} matched no registered project")

    catalog = load_catalog()
    overlay = build_skill_overlay(load_skill_inventory(), catalog)

    skipped: list[SkippedProject] = []
    selected: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for rp in projects:
        identifier = rp.id or rp.name
        root = Path(rp.path).expanduser()
        if not root.exists() or not project_config_path(root).is_file():
            skipped.append(SkippedProject(str(rp.path), "path missing or no science.yaml"))
            continue
        if identifier in seen:
            raise SkillCoverageScanError(
                f"duplicate project identifier {identifier!r} in the registry"
            )
        seen.add(identifier)
        selected.append((identifier, root))

    evidences: list[ProjectEvidence] = []
    for identifier, root in selected:
        try:
            project_config = load_project_config(root)
        except Exception as exc:  # present-but-invalid config -> abort (never reclassify)
            raise SkillCoverageScanError(f"{identifier}: invalid science.yaml: {exc}") from exc
        status = domain_enrollment(project_config, COVERAGE_DOMAIN)
        if status == EnrollmentStatus.ENROLLED:
            try:
                sources = load_project_sources(root, include_commons=True)
            except Exception as exc:
                raise SkillCoverageScanError(f"{identifier}: sources failed to load: {exc}") from exc
            evidences.append(project_evidence(identifier, sources))
        else:
            evidences.append(ProjectEvidence(identifier, status))

    scope = ReportScope("single-project", only) if only is not None else ReportScope("portfolio")
    return compute_coverage(
        evidences, overlay, catalog,
        scope=scope,
        skipped_projects=tuple(sorted(skipped, key=lambda s: s.path)),
    )


def write_report_atomically(path: Path, text: str) -> None:
    # Serialize-then-replace: a plain write_text truncates before it can fail on I/O, which would
    # leave a stale report half-overwritten. os.replace onto the target is atomic on the same fs.
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_scan.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint + commit**

```bash
cd science && uv run ruff check src/science_tool/skills_coverage/scan.py tests/skills_coverage/test_scan.py
cd .. && git add science/src/science_tool/skills_coverage/scan.py science/tests/skills_coverage/test_scan.py
git commit -m "feat(skill-coverage): portfolio scan with skip-and-report and atomic output"
```

---

### Task 5: CLI command (`science-tool`)

**Files:**
- Create: `science/src/science_tool/skills_coverage/cli.py`
- Modify: `science/src/science_tool/skills_lint/cli.py` (register the `coverage` subcommand)
- Test: `science/tests/skills_coverage/test_cli.py`

**Interfaces:**
- Consumes: `scan_portfolio`, `write_report_atomically`, `SkillCoverageScanError`; `serialize_coverage_report`; `SkillCoverageError`.
- Produces: `coverage_command` (click command, registered as `science skills coverage`).

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/skills_coverage/test_cli.py
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.skills_lint.cli import skills_group


def _enrolled_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nentity_schema_version: 3\nskill_coverage:\n  domains:\n    molecular-measurement: enrolled\n",
        encoding="utf-8",
    )


def _registry(tmp_path: Path, entries: list[dict]) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"projects": entries}), encoding="utf-8")
    return config_path


def test_coverage_cli_stdout_json(tmp_path: Path, monkeypatch) -> None:
    enrolled = tmp_path / "enrolled"; _enrolled_project(enrolled)
    # SCIENCE_CONFIG_DIR -> get_default_config_path() == tmp_path/config.yaml, which _registry writes.
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    _registry(tmp_path, [
        {"path": str(enrolled), "name": "enrolled", "id": "enrolled", "registered": "2026-07-25"},
    ])
    runner = CliRunner()
    result = runner.invoke(skills_group, ["coverage"])
    assert result.exit_code == 0, result.output
    obj = json.loads(result.output)
    assert obj["scope"]["mode"] == "portfolio"


def test_coverage_cli_output_file_and_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    _registry(tmp_path, [])  # empty registry -> hard error
    out = tmp_path / "report.json"
    out.write_text("PRIOR", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(skills_group, ["coverage", "--output", str(out)])
    assert result.exit_code != 0  # empty registry -> hard error
    assert out.read_text(encoding="utf-8") == "PRIOR"  # untouched on failure
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_cli.py -v`
Expected: FAIL — no `coverage` subcommand on `skills_group`.

- [ ] **Step 3: Implement the CLI**

```python
# science/src/science_tool/skills_coverage/cli.py
"""`science skills coverage` — portfolio skill-coverage scan."""

from __future__ import annotations

from pathlib import Path

import click

from science_model.skill_coverage.coverage import SkillCoverageError, serialize_coverage_report

from science_tool.skills_coverage.scan import (
    SkillCoverageScanError,
    scan_portfolio,
    write_report_atomically,
)


@click.command(name="coverage")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Write the coverage-report JSON to PATH (atomically). Default: stdout.")
@click.option("--project", "project", default=None,
              help="Restrict the scan to the one registered project with this identifier.")
def coverage_command(output: Path | None, project: str | None) -> None:
    """Scan the registered portfolio for skill-coverage gaps."""
    try:
        report = scan_portfolio(only=project)
    except (SkillCoverageScanError, SkillCoverageError) as exc:
        raise click.ClickException(str(exc)) from exc
    text = serialize_coverage_report(report)
    if output is not None:
        write_report_atomically(output, text)
    else:
        click.echo(text, nl=False)
```

- [ ] **Step 4: Register the subcommand**

In `science/src/science_tool/skills_lint/cli.py`, after the `skills_group` definition, add the import and registration (mirror how `lint` is attached):

```python
from science_tool.skills_coverage.cli import coverage_command

skills_group.add_command(coverage_command)
```

(Place the import at the top with the other imports if the file groups them there; keep `add_command` beside the existing subcommand registrations.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_coverage/test_cli.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Full verification gate**

```bash
cd science && uv run --frozen pytest tests/skills_coverage/ && uv run ruff check src/science_tool/skills_coverage/ && uv run pyright
cd model && uv run --frozen pytest tests/test_coverage_types.py tests/test_compute_coverage.py && uv run ruff check src/science_model/skill_coverage/
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/skills_coverage/cli.py science/src/science_tool/skills_lint/cli.py science/tests/skills_coverage/test_cli.py
git commit -m "feat(skill-coverage): science skills coverage CLI command"
```

---

### Task 6: Enrollment + coverage documentation

**Files:**
- Create: `docs/conventions/skill-coverage.md`
- Modify: `docs/user-guide/index.md` (link the new page)

**Interfaces:** none (docs only).

- [ ] **Step 1: Write the convention page**

Create `docs/conventions/skill-coverage.md` covering:

```markdown
# Skill coverage

`science skills coverage` scans the registered project portfolio and reports, per
enrolled project, where analyses touch a data-product term that no skill covers
(`uncovered`), where a covering skill exists but the plan did not load it
(`covered-not-loaded`), and where analysis touches a dataset tagged against no term
(`unmapped`). It emits evidence-backed skill candidates for uncovered terms.

## Enrolling a project

Enrollment is a closed declaration in `science.yaml`:

```yaml
skill_coverage:
  domains:
    molecular-measurement: enrolled   # or: out-of-domain
```

- The only domain in v1 is `molecular-measurement`. An unknown domain key is a hard
  config error.
- Absence of the block, or of a domain key, means **undeclared** for that domain — it
  is never inferred as `out-of-domain`, which a project must author explicitly.
- `molecular-measurement: enrolled` **requires** `entity_schema_version: 3` (coverage
  reads the generation-3 capability shape); enrolling without it is a config error.

## Running the scan

```bash
science skills coverage                 # portfolio scan -> coverage-report JSON on stdout
science skills coverage --output report.json
science skills coverage --project mm30  # restrict to one registered project
```

A registered path that is missing or has no `science.yaml` is skipped and listed under
`skipped_projects`; a path that exists with invalid config aborts the scan (nonzero
exit, no partial report). Coverage findings are not failures — a scan that surfaces
`uncovered` occurrences still exits 0.

## The report

`coverage-report` is a JSON object: `scope`, `coverage_occurrences[]` (a discriminated
union keyed by `state`), `skill_reference_diagnostics[]`, `dataset_reference_diagnostics[]`,
`candidates[]`, and `skipped_projects[]`. See the design doc
`docs/plans/2026-07-25-skill-coverage-command-design.md` for the field-level schema.
```

- [ ] **Step 2: Link from the user guide**

Add a bullet under the conventions/reference links in `docs/user-guide/index.md` pointing to `../conventions/skill-coverage.md` (match the surrounding link style; read the file first to place it consistently).

- [ ] **Step 3: Commit**

```bash
git add docs/conventions/skill-coverage.md docs/user-guide/index.md
git commit -m "docs(skill-coverage): enrollment + coverage command convention page"
```

---

## Self-review notes (for the executor)

- **Spec coverage:** T1 = design §5 report types + serialization/ordering + `ProjectEvidence.__post_init__`; T2 = §3 states + §4 candidates (score `[0.5,1)`, sibling inference, owned-vs-commons off-catalog); T3 = §2 projection (union edge, resolver, `commons-merged` owner discriminator, `capability_scope`, `owned` flag, dangling `related` → diagnostic vs dangling `dataset_usage` → hard error); T4 = §6 scan (skip-and-report, absent-registry error, duplicate-id guard, `--project`, atomic write, present-but-invalid abort); T5 = §6 CLI (stdout default, `--output`, exit codes); T6 = §7 docs.
- **Package boundary:** `science_model` (T1/T2) never imports `science_tool`; `coverage.py` avoids the package `__init__` at runtime (string enrollment compare + `TYPE_CHECKING` import) so there is no import cycle. `science_tool` (T3–T5) supplies the projection and I/O.
- **Discriminator:** commons-owned iff `entity_source_adapters[id] == "commons-merged"` — never `commons_overlay_paths` (T3, round-4 must-fix). A commons-owned dataset only exists after a real commons merge, so the projection's `owned=False` branch is not exercisable in a bare tmp project; the T3 tests cover the owned path (`capability_scope` + untagged), and the model's owned-vs-commons off-catalog behavior is tested directly in T2. A full commons-ownership assertion belongs in a `real_projects` test against health-meta (whose `dataset:reactome` etc. are commons-owned) and is not built here.
- **Type consistency:** `compute_coverage(projects, overlay, catalog, *, scope, skipped_projects=())` (T2) is called with exactly those keyword args by the scan (T4). `project_evidence(project, sources) -> ProjectEvidence` (T3) is consumed by the scan (T4). `ProjectEvidence` field names/order match across T1/T2/T3.
- **Out of scope (do not implement):** `observation_level: project-demand`; feedback-recurrence ranking; a `--strict` flag; additional domains; any migration authoring `dataset_usage` on plans.
- **Fixture note:** tool-side tests use the real `_fixtures.entity_helpers.seed_project` + `write_markdown_entity` helpers and enable gen-3 via `entity_schema_version: 3`. If `seed_project`'s default `science.yaml` already pins a generation, append/override rather than duplicating the key (read the seeded file first). The RED step will surface any fixture-shape mismatch before the implementation is written.
