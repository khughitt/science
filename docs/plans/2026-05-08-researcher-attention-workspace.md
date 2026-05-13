# Researcher Attention Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V1 Split Attention Workspace in `science-web`: an All Projects researcher-first home view with deterministic attention scoring, findings ledger, 2D graph slice, and research-meaning sidebar.

**Architecture:** Add a backend attention read model derived from existing project scans, analyses, graph data, task metadata, and DAG evidence YAML. Expose it through a read-only `/api/attention` endpoint, then replace the root frontend view with a workspace that consumes the same payload for graph, ledger, sidebar, URL state, and browser-local preferences. Keep the current project/entity/task APIs intact.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, React 19, TypeScript, Vite, React Router for the existing route shell, TanStack Router installed as the planned typed-router migration target, Zustand, Tailwind CSS, `react-force-graph-2d` / `react-force-graph-3d` for V1 graph rendering, existing `science-model` and `science-tool` path packages.

---

All implementation paths below are relative to `~/d/dashboard` unless a path starts with `~/d/science`. The design source is `~/d/science/docs/superpowers/specs/2026-05-08-researcher-attention-workspace-design.md`.

## File Structure

- Create `backend/attention_models.py`: Pydantic API/read-model types for snapshots, findings, graph nodes/edges, scores, and sidebar profiles.
- Create `backend/findings.py`: deterministic finding extraction and deduplication from entities, task findings, graph nodes, and DAG edge YAML.
- Create `backend/attention_scoring.py`: per-project normalization, support-class derivation, composite scores, and score reasons.
- Create `backend/attention.py`: orchestrates snapshot assembly, graph slice selection, cross-project edges, and profile construction.
- Modify `backend/store.py`: cache and expose attention snapshots through the store.
- Create `backend/routes/attention.py`: `/api/attention` endpoint with query state.
- Modify `backend/app.py`: register the attention route.
- Create tests in `tests/test_findings.py`, `tests/test_attention_scoring.py`, `tests/test_attention_api.py`.
- Modify `frontend/src/types/index.ts`: add attention payload types.
- Modify `frontend/src/api/client.ts`: add `api.attention.get`.
- Create `frontend/src/routes/AttentionWorkspace.tsx`: root Split Attention Workspace.
- Create `frontend/src/components/Attention/AttentionGraph.tsx`: deterministic 2D force-graph slice using `react-force-graph-2d`.
- Create `frontend/src/components/Attention/FindingsLedger.tsx`: ranked findings ledger with tabs and score breakdown entry points.
- Create `frontend/src/components/Attention/ResearchMeaningSidebar.tsx`: selected entity/finding profile.
- Create `frontend/src/components/Attention/AttentionControls.tsx`: scope, preset, lens, snapshot, and refresh controls.
- Create `frontend/src/components/Attention/useAttentionState.ts`: URL state plus localStorage preferences.
- Modify `frontend/src/hooks/useKeyboard.ts`: reserve `1`-`4` for attention presets when the workspace is active.

## V1 Scope Decisions

- The first screen is `/` and defaults to `scope=all`, `preset=3`, `lens=semantic`, `tab=attention`.
- V1 graph uses the already-installed `react-force-graph-2d` package for the root attention workspace. Keep existing project graph route unchanged.
- `r3f-forcegraph` + `@react-three/fiber` + `@react-three/drei` is the alternate 3D composition path. Do not add it to V1 unless replacing the React Force Graph renderer in Task 8.
- TanStack Router is added to the dependency set now, but full migration from React Router is a follow-up because the current app has route hooks and links spread across existing screens. Do not partially wrap both routers around the same route tree.
- Findings are derived read-model records; no project files are modified.
- Cross-project edges come from shared source refs and explicit related refs in the configured projects. Peer path resolution issues are surfaced as profile/quality warnings when visible in the read model; full project-peers validation is not implemented here.
- DAG edge YAML extraction handles `doc/figures/dags/*.edges.yaml` when present.
- Search/jump-to-entity is not implemented in this plan, but URL state supports selected IDs.

---

### Task 1: Backend Attention API Models

**Files:**
- Create: `backend/attention_models.py`
- Test: `tests/test_attention_scoring.py` will consume these models in Task 3.

- [ ] **Step 1: Create attention read-model types**

Create `backend/attention_models.py`:

```python
"""Read models for the researcher attention workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


AttentionPreset = Literal["findings", "hypotheses", "mixed", "inquiries"]
AttentionScopeKind = Literal["all", "project"]
AttentionLens = Literal["semantic", "evidence", "fragile", "recent", "projects", "workflows"]
LedgerTab = Literal["attention", "promising", "credible", "fragile", "recent", "actionable", "ruled_out"]
SupportClass = Literal["strongest", "moderate", "weak", "untrustworthy", "still_fragile"]


class AttentionScoreBreakdown(BaseModel):
    importance: float = 0.0
    fragility: float = 0.0
    interestingness: float = 0.0
    recency: float = 0.0
    actionability: float = 0.0
    centrality: float = 0.0
    load_bearingness: float = 0.0
    unresolved_uncertainty: float = 0.0
    credibility: float = 0.0
    composite: float = 0.0


class AttentionScoreReason(BaseModel):
    signal: str
    value: float
    reason: str


class SupportBreakdown(BaseModel):
    internal_workflows: int = 0
    internal_workflows_stale: int = 0
    internal_data_refs: int = 0
    literature_refs: int = 0
    ontology_refs: int = 0
    counterevidence_refs: int = 0


class AttentionFinding(BaseModel):
    id: str
    project_id: str
    claim_text: str
    proposition_refs: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    primary_source: str | None = None
    related_entities: list[str] = Field(default_factory=list)
    evidence_status: str | None = None
    identification_strength: str | None = None
    support_class: SupportClass = "untrustworthy"
    support_breakdown: SupportBreakdown = Field(default_factory=SupportBreakdown)
    scores: AttentionScoreBreakdown = Field(default_factory=AttentionScoreBreakdown)
    score_reasons: list[AttentionScoreReason] = Field(default_factory=list)
    supersession: list[str] = Field(default_factory=list)
    freshness: str = "unavailable"
    updated: str | None = None


class AttentionGraphNode(BaseModel):
    id: str
    project_id: str
    entity_ref: str
    label: str
    entity_type: str
    node_kind: Literal["project", "finding", "hypothesis", "question", "inquiry", "dataset", "workflow", "task", "source", "entity"]
    scores: AttentionScoreBreakdown = Field(default_factory=AttentionScoreBreakdown)
    support_class: SupportClass | None = None
    evidence_status: str | None = None
    identification_strength: str | None = None
    related_finding_ids: list[str] = Field(default_factory=list)


class AttentionGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    evidence_status: str | None = None
    identification_strength: str | None = None
    load_bearingness: float = 0.0
    cross_project: bool = False


class AttentionRelationship(BaseModel):
    ref: str
    project_id: str
    entity_type: str
    title: str
    relation: str
    reason: str


class AttentionProfile(BaseModel):
    id: str
    project_id: str
    title: str
    entity_type: str
    summary: str
    why_it_matters: str
    evidence_state: str
    weak_points: list[str] = Field(default_factory=list)
    key_relationships: list[AttentionRelationship] = Field(default_factory=list)
    score_breakdown: AttentionScoreBreakdown = Field(default_factory=AttentionScoreBreakdown)
    score_reasons: list[AttentionScoreReason] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class AttentionSnapshot(BaseModel):
    snapshot_id: str
    built_at: datetime
    schema_version: str = "1"
    scope_kind: AttentionScopeKind = "all"
    scope_project: str | None = None
    preset: AttentionPreset = "mixed"
    lens: AttentionLens = "semantic"
    ledger_tab: LedgerTab = "attention"
    included_projects: list[str]
    warnings: list[str] = Field(default_factory=list)
    findings: list[AttentionFinding]
    graph_nodes: list[AttentionGraphNode]
    graph_edges: list[AttentionGraphEdge]
    selected_profile: AttentionProfile | None = None
```

- [ ] **Step 2: Run import check**

Run: `uv run --frozen python -c "from backend.attention_models import AttentionSnapshot; print(AttentionSnapshot.model_fields['schema_version'].default)"`

Expected: prints `1`.

- [ ] **Step 3: Commit**

```bash
git add backend/attention_models.py
git commit -m "feat(attention): add workspace read models"
```

---

### Task 2: Finding Extraction And Deduplication

**Files:**
- Create: `backend/findings.py`
- Test: `tests/test_findings.py`

- [ ] **Step 1: Write failing tests for entity, task, DAG, and dedup extraction**

Create `tests/test_findings.py`:

```python
from pathlib import Path

import yaml

from backend.findings import extract_project_findings
from backend.indexer import scan_project
from tests.test_indexer import _make_project


def test_extract_project_findings_from_entity_and_task(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    (root / "doc" / "findings").mkdir(parents=True)
    (root / "doc" / "findings" / "f01.md").write_text("""---
id: "finding:f01-internal"
type: finding
title: "Internal workflow supports H1"
status: supported
related: [hypothesis:h01-test, workflow-run:a001-run]
source_refs: [workflow-run:a001-run]
updated: 2026-05-01
---
Internal workflow supports H1.
""")
    (root / "tasks" / "active.md").write_text("""## [t001] Follow up finding
- type: research
- priority: P1
- status: proposed
- aspects: [hypothesis-testing]
- related: [finding:f01-internal]
- findings: [finding:f01-internal]
- created: 2026-05-02

Clarify the internal workflow finding.
""")

    findings = extract_project_findings(scan_project(root), root)

    finding = next(item for item in findings if item.id == "test-project:finding:f01-internal")
    assert finding.claim_text == "Internal workflow supports H1"
    assert "hypothesis:h01-test" in finding.related_entities
    assert "workflow-run:a001-run" in finding.source_refs
    assert "task:t001" in finding.source_refs


def test_extract_project_findings_from_dag_edge_yaml(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    dag_dir = root / "doc" / "figures" / "dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1.edges.yaml").write_text(
        yaml.safe_dump(
            {
                "dag": "h1",
                "edges": [
                    {
                        "id": 7,
                        "source": "a",
                        "target": "b",
                        "source_label": "A",
                        "target_label": "B",
                        "edge_status": "supported",
                        "identification": "observational",
                        "description": "A supports B in the pilot workflow.",
                        "data_support": [{"task": "t001", "description": "Internal run."}],
                        "lit_support": [{"doi": "10.1000/example", "description": "External paper."}],
                    }
                ],
            },
            sort_keys=False,
        )
    )

    findings = extract_project_findings(scan_project(root), root)

    dag_finding = next(item for item in findings if item.primary_source == "doc/figures/dags/h1.edges.yaml#edge-7")
    assert dag_finding.id.startswith("test-project:finding:auto:dag-edge:")
    assert dag_finding.evidence_status == "supported"
    assert dag_finding.identification_strength == "observational"
    assert "task:t001" in dag_finding.source_refs
    assert "doi:10.1000/example" in dag_finding.source_refs


def test_extract_project_findings_deduplicates_by_proposition_ref(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    (root / "doc" / "findings").mkdir(parents=True)
    for slug in ("a", "b"):
        (root / "doc" / "findings" / f"{slug}.md").write_text(f"""---
id: "finding:{slug}"
type: finding
title: "Same proposition"
related: [proposition:p01-shared, workflow-run:{slug}]
source_refs: [workflow-run:{slug}]
created: 2026-05-01
---
Same proposition.
""")

    findings = extract_project_findings(scan_project(root), root)

    merged = [item for item in findings if "proposition:p01-shared" in item.proposition_refs]
    assert len(merged) == 1
    assert {"workflow-run:a", "workflow-run:b"} <= set(merged[0].source_refs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/test_findings.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.findings'`.

- [ ] **Step 3: Implement finding extraction**

Create `backend/findings.py`:

```python
"""Finding extraction for the researcher attention workspace."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from backend.attention_models import AttentionFinding, SupportBreakdown
from backend.entities import entity_kind
from backend.indexer import ProjectScan


def extract_project_findings(scan: ProjectScan, project_root: Path) -> list[AttentionFinding]:
    """Extract and deduplicate finding read models for one project."""
    candidates: list[AttentionFinding] = []
    candidates.extend(_findings_from_entities(scan, project_root))
    candidates.extend(_findings_from_tasks(scan))
    candidates.extend(_findings_from_dag_edges(scan, project_root))
    return _deduplicate_findings(candidates)


def _findings_from_entities(scan: ProjectScan, project_root: Path) -> list[AttentionFinding]:
    findings: list[AttentionFinding] = []
    for entity in scan.entities:
        if entity_kind(entity) != "finding":
            continue
        source_refs = sorted(set(entity.source_refs + [ref for ref in entity.related if _is_source_ref(ref)]))
        related = sorted(set(entity.related))
        proposition_refs = sorted(ref for ref in related if ref.startswith("proposition:"))
        findings.append(
            AttentionFinding(
                id=_canonical_finding_id(scan.project.slug, entity.id),
                project_id=scan.project.slug,
                claim_text=entity.title,
                proposition_refs=proposition_refs,
                source_refs=source_refs,
                primary_source=_relative_path(project_root, entity.file_path),
                related_entities=related,
                evidence_status=entity.status,
                support_breakdown=_support_breakdown(source_refs),
                updated=entity.updated.isoformat() if entity.updated else None,
            )
        )
    return findings


def _findings_from_tasks(scan: ProjectScan) -> list[AttentionFinding]:
    findings_by_id: dict[str, AttentionFinding] = {}
    for task in scan.tasks:
        for ref in task.findings:
            if not ref.startswith("finding:"):
                continue
            finding_id = _canonical_finding_id(scan.project.slug, ref)
            findings_by_id[finding_id] = AttentionFinding(
                id=finding_id,
                project_id=scan.project.slug,
                claim_text=ref.split(":", 1)[1].replace("-", " "),
                source_refs=[f"task:{task.id}"],
                primary_source=f"task:{task.id}",
                related_entities=sorted(set(task.related + [ref])),
                support_breakdown=SupportBreakdown(),
                updated=task.created.isoformat() if task.created else None,
            )
    return list(findings_by_id.values())


def _findings_from_dag_edges(scan: ProjectScan, project_root: Path) -> list[AttentionFinding]:
    findings: list[AttentionFinding] = []
    dag_root = project_root / "doc" / "figures" / "dags"
    if not dag_root.is_dir():
        return findings
    for path in sorted(dag_root.glob("*.edges.yaml")):
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            continue
        edges = data.get("edges", [])
        if not isinstance(edges, list):
            continue
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            edge_id = str(edge.get("id", "")).strip()
            if not edge_id:
                continue
            rel_path = path.relative_to(project_root).as_posix()
            primary_source = f"{rel_path}#edge-{edge_id}"
            claim_text = _dag_claim_text(edge)
            source_refs = _dag_source_refs(edge)
            findings.append(
                AttentionFinding(
                    id=_synthetic_id(scan.project.slug, "dag-edge", primary_source),
                    project_id=scan.project.slug,
                    claim_text=claim_text,
                    source_refs=source_refs,
                    primary_source=primary_source,
                    related_entities=_dag_related_entities(data, edge),
                    evidence_status=_str_or_none(edge.get("edge_status")),
                    identification_strength=_str_or_none(edge.get("identification")),
                    support_breakdown=_support_breakdown(source_refs),
                )
            )
    return findings


def _deduplicate_findings(findings: list[AttentionFinding]) -> list[AttentionFinding]:
    buckets: dict[str, AttentionFinding] = {}
    for finding in findings:
        key = _dedupe_key(finding)
        if key not in buckets:
            buckets[key] = finding
            continue
        existing = buckets[key]
        existing.source_refs = sorted(set(existing.source_refs + finding.source_refs))
        existing.related_entities = sorted(set(existing.related_entities + finding.related_entities))
        existing.proposition_refs = sorted(set(existing.proposition_refs + finding.proposition_refs))
        existing.support_breakdown = _support_breakdown(existing.source_refs)
        if existing.primary_source is None:
            existing.primary_source = finding.primary_source
    return sorted(buckets.values(), key=lambda item: (item.project_id, item.id))


def _dedupe_key(finding: AttentionFinding) -> str:
    if finding.proposition_refs:
        return f"{finding.project_id}:propositions:{'|'.join(sorted(finding.proposition_refs))}"
    normalized_claim = " ".join(finding.claim_text.lower().split())
    related = "|".join(sorted(ref for ref in finding.related_entities if ref.split(":", 1)[0] in {"hypothesis", "question", "inquiry"}))
    return f"{finding.project_id}:claim:{normalized_claim}:{related}"


def _canonical_finding_id(project_id: str, raw_id: str) -> str:
    slug = raw_id.split(":", 1)[1] if raw_id.startswith("finding:") else raw_id
    return f"{project_id}:finding:{slug}"


def _synthetic_id(project_id: str, source_kind: str, stable_value: str) -> str:
    digest = hashlib.sha1(stable_value.encode("utf-8")).hexdigest()[:12]
    return f"{project_id}:finding:auto:{source_kind}:{digest}"


def _dag_claim_text(edge: dict[str, Any]) -> str:
    source = str(edge.get("source_label") or edge.get("source") or "source").strip()
    target = str(edge.get("target_label") or edge.get("target") or "target").strip()
    relation = str(edge.get("relation") or edge.get("original_label") or "bears on").strip()
    return f"{source} {relation} {target}"


def _dag_source_refs(edge: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for item in edge.get("data_support") or []:
        if not isinstance(item, dict):
            continue
        if item.get("task"):
            refs.append(f"task:{item['task']}")
        if item.get("accession"):
            refs.append(f"accession:{item['accession']}")
    for item in edge.get("lit_support") or []:
        if not isinstance(item, dict):
            continue
        if item.get("doi"):
            refs.append(f"doi:{item['doi']}")
        elif item.get("author_year"):
            refs.append(f"literature:{item['author_year']}")
    return sorted(set(refs))


def _dag_related_entities(data: dict[str, Any], edge: dict[str, Any]) -> list[str]:
    related: list[str] = []
    dag = data.get("dag")
    if isinstance(dag, str) and dag:
        related.append(f"inquiry:{dag}")
    for node_key in ("source", "target"):
        node = edge.get(node_key)
        if isinstance(node, str) and node:
            related.append(f"dag-node:{node}")
    return sorted(set(related))


def _support_breakdown(source_refs: list[str]) -> SupportBreakdown:
    return SupportBreakdown(
        internal_workflows=sum(1 for ref in source_refs if ref.startswith(("workflow-run:", "task:", "data-package:"))),
        internal_data_refs=sum(1 for ref in source_refs if ref.startswith(("accession:", "dataset:"))),
        literature_refs=sum(1 for ref in source_refs if ref.startswith(("doi:", "literature:", "paper:", "article:"))),
        ontology_refs=sum(1 for ref in source_refs if ref.startswith("ontology:")),
        counterevidence_refs=sum(1 for ref in source_refs if ref.startswith("disputes:")),
    )


def _is_source_ref(ref: str) -> bool:
    return ref.startswith(("workflow-run:", "task:", "data-package:", "dataset:", "doi:", "paper:", "article:", "accession:"))


def _relative_path(project_root: Path, raw_path: str | None) -> str | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
```

- [ ] **Step 4: Run tests**

Run: `uv run --frozen pytest tests/test_findings.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/findings.py tests/test_findings.py
git commit -m "feat(attention): extract findings from project artifacts"
```

---

### Task 3: Attention Scoring

**Files:**
- Create: `backend/attention_scoring.py`
- Modify: `tests/test_attention_scoring.py`

- [ ] **Step 1: Write failing tests for support class, per-project normalization, and score reasons**

Create `tests/test_attention_scoring.py`:

```python
from backend.attention_models import AttentionFinding, SupportBreakdown
from backend.attention_scoring import score_findings


def _finding(project: str, slug: str, support: SupportBreakdown, *, status: str | None = None) -> AttentionFinding:
    return AttentionFinding(
        id=f"{project}:finding:{slug}",
        project_id=project,
        claim_text=slug,
        evidence_status=status,
        support_breakdown=support,
        source_refs=[],
        related_entities=[],
    )


def test_score_findings_prefers_internal_workflow_support_for_credible() -> None:
    internal = _finding("small", "internal", SupportBreakdown(internal_workflows=2), status="supported")
    literature = _finding("small", "literature", SupportBreakdown(literature_refs=5), status="supported")

    scored = score_findings([literature, internal])
    by_id = {item.id: item for item in scored}

    assert by_id["small:finding:internal"].support_class == "strongest"
    assert by_id["small:finding:literature"].support_class == "weak"
    assert by_id["small:finding:internal"].scores.credibility > by_id["small:finding:literature"].scores.credibility


def test_score_findings_marks_single_internal_workflow_fragile() -> None:
    finding = _finding("p", "single", SupportBreakdown(internal_workflows=1), status="supported")

    scored = score_findings([finding])

    assert scored[0].support_class == "still_fragile"
    assert scored[0].scores.fragility >= 0.6
    assert any(reason.signal == "fragility" and "single internal workflow" in reason.reason for reason in scored[0].score_reasons)


def test_score_findings_normalizes_within_project_before_merge() -> None:
    small_top = _finding("small", "top", SupportBreakdown(internal_workflows=2), status="supported")
    large_top = _finding("large", "top", SupportBreakdown(internal_workflows=2), status="supported")
    large_second = _finding("large", "second", SupportBreakdown(literature_refs=3), status="tentative")

    scored = score_findings([large_second, large_top, small_top])
    by_id = {item.id: item for item in scored}

    assert by_id["small:finding:top"].scores.importance == 1.0
    assert by_id["large:finding:top"].scores.importance == 1.0
    assert by_id["large:finding:second"].scores.importance < 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/test_attention_scoring.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.attention_scoring'`.

- [ ] **Step 3: Implement scoring**

Create `backend/attention_scoring.py`:

```python
"""Attention scoring for researcher workspace read models."""

from __future__ import annotations

from collections import defaultdict

from backend.attention_models import AttentionFinding, AttentionScoreReason


def score_findings(findings: list[AttentionFinding]) -> list[AttentionFinding]:
    """Score findings with project-local normalization and skeptical confidence."""
    grouped: dict[str, list[AttentionFinding]] = defaultdict(list)
    for finding in findings:
        _classify_support(finding)
        _score_rule_signals(finding)
        grouped[finding.project_id].append(finding)

    for project_findings in grouped.values():
        _normalize_project(project_findings, "importance")
        _normalize_project(project_findings, "interestingness")
        _normalize_project(project_findings, "recency")
        _normalize_project(project_findings, "centrality")
        _normalize_project(project_findings, "load_bearingness")

    for finding in findings:
        scores = finding.scores
        scores.composite = round(
            0.22 * scores.importance
            + 0.22 * scores.fragility
            + 0.12 * scores.interestingness
            + 0.10 * scores.recency
            + 0.14 * scores.actionability
            + 0.08 * scores.centrality
            + 0.08 * scores.load_bearingness
            + 0.04 * scores.unresolved_uncertainty,
            4,
        )

    return sorted(
        findings,
        key=lambda item: (
            -item.scores.composite,
            -item.scores.fragility,
            -item.scores.importance,
            item.project_id,
            item.id,
        ),
    )


def _classify_support(finding: AttentionFinding) -> None:
    support = finding.support_breakdown
    if support.internal_workflows_stale > 0:
        finding.support_class = "weak"
        finding.score_reasons.append(AttentionScoreReason(signal="credibility", value=0.25, reason="internal workflow support is stale"))
        finding.scores.credibility = 0.25
        return
    if support.internal_workflows >= 2:
        finding.support_class = "strongest"
        finding.scores.credibility = 1.0
        finding.score_reasons.append(AttentionScoreReason(signal="credibility", value=1.0, reason="multiple internal workflows"))
        return
    if support.internal_workflows == 1 and (support.internal_data_refs > 0 or support.literature_refs > 0):
        finding.support_class = "moderate"
        finding.scores.credibility = 0.7
        finding.score_reasons.append(AttentionScoreReason(signal="credibility", value=0.7, reason="one internal workflow plus corroboration"))
        return
    if support.internal_workflows == 1:
        finding.support_class = "still_fragile"
        finding.scores.credibility = 0.45
        finding.score_reasons.append(AttentionScoreReason(signal="credibility", value=0.45, reason="single internal workflow"))
        return
    if support.literature_refs > 0 or support.ontology_refs > 0:
        finding.support_class = "weak"
        finding.scores.credibility = 0.2
        finding.score_reasons.append(AttentionScoreReason(signal="credibility", value=0.2, reason="external-only support"))
        return
    finding.support_class = "untrustworthy"
    finding.scores.credibility = 0.0
    finding.score_reasons.append(AttentionScoreReason(signal="credibility", value=0.0, reason="no internal data support"))


def _score_rule_signals(finding: AttentionFinding) -> None:
    support = finding.support_breakdown
    if finding.evidence_status == "eliminated":
        finding.scores.fragility = 1.0
        finding.scores.unresolved_uncertainty = 0.0
        finding.score_reasons.append(AttentionScoreReason(signal="fragility", value=1.0, reason="eliminated finding retained for provenance"))
    elif finding.support_class in {"untrustworthy", "still_fragile"}:
        finding.scores.fragility = 0.8 if finding.support_class == "untrustworthy" else 0.65
        reason = "no internal data support" if finding.support_class == "untrustworthy" else "single internal workflow"
        finding.score_reasons.append(AttentionScoreReason(signal="fragility", value=finding.scores.fragility, reason=reason))
    elif finding.evidence_status in {"tentative", "unknown", None}:
        finding.scores.fragility = 0.5
        finding.score_reasons.append(AttentionScoreReason(signal="fragility", value=0.5, reason="tentative or unknown evidence status"))

    finding.scores.interestingness = min(1.0, 0.2 * support.literature_refs + 0.15 * len(finding.related_entities))
    finding.scores.importance = min(1.0, 0.4 + 0.1 * len(finding.related_entities) + 0.1 * support.internal_workflows)
    finding.scores.actionability = 0.6 if any(ref.startswith("task:") for ref in finding.source_refs + finding.related_entities) else 0.0
    finding.scores.unresolved_uncertainty = max(finding.scores.unresolved_uncertainty, 0.5 if finding.evidence_status in {"unknown", None} else 0.0)


def _normalize_project(findings: list[AttentionFinding], field: str) -> None:
    values = [getattr(item.scores, field) for item in findings]
    if not values:
        return
    max_value = max(values)
    if max_value <= 0:
        return
    for finding in findings:
        setattr(finding.scores, field, round(getattr(finding.scores, field) / max_value, 4))
```

- [ ] **Step 4: Run scoring tests**

Run: `uv run --frozen pytest tests/test_attention_scoring.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/attention_scoring.py tests/test_attention_scoring.py
git commit -m "feat(attention): score findings with skeptical support"
```

---

### Task 4: Attention Snapshot Builder

**Files:**
- Create: `backend/attention.py`
- Modify: `tests/test_attention_api.py`

- [ ] **Step 1: Write failing snapshot tests**

Create `tests/test_attention_api.py`:

```python
from pathlib import Path

from backend.attention import build_attention_snapshot
from backend.indexer import scan_project
from backend.analysis import analyze_project_scan
from tests.test_indexer import _make_project


def _scan_bundle(root: Path):
    scan = scan_project(root)
    return scan, analyze_project_scan(scan, root)


def test_build_attention_snapshot_defaults_to_all_projects_mixed(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    scan, analysis = _scan_bundle(root)

    snapshot = build_attention_snapshot({"test-project": scan}, {"test-project": analysis}, preset="mixed")

    assert snapshot.scope_kind == "all"
    assert snapshot.preset == "mixed"
    assert snapshot.included_projects == ["test-project"]
    assert snapshot.findings
    assert 1 <= len(snapshot.graph_nodes) <= 50
    assert snapshot.snapshot_id.startswith("attention:")


def test_build_attention_snapshot_selected_profile_has_score_breakdown(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    (root / "doc" / "findings").mkdir(parents=True)
    (root / "doc" / "findings" / "f01.md").write_text("""---
id: "finding:f01"
type: finding
title: "Workflow-backed finding"
status: supported
related: [hypothesis:h01-test, workflow-run:a001-run]
source_refs: [workflow-run:a001-run]
created: 2026-05-01
---
Workflow-backed finding.
""")
    scan, analysis = _scan_bundle(root)

    snapshot = build_attention_snapshot(
        {"test-project": scan},
        {"test-project": analysis},
        preset="findings",
        selected_id="test-project:finding:f01",
    )

    assert snapshot.selected_profile is not None
    assert snapshot.selected_profile.id == "test-project:finding:f01"
    assert snapshot.selected_profile.score_reasons
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/test_attention_api.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.attention'`.

- [ ] **Step 3: Implement snapshot builder**

Create `backend/attention.py`:

```python
"""Attention snapshot assembly for the researcher workspace."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from backend.analysis import ProjectAnalysis
from backend.attention_models import (
    AttentionFinding,
    AttentionGraphEdge,
    AttentionGraphNode,
    AttentionLens,
    AttentionPreset,
    AttentionProfile,
    AttentionRelationship,
    AttentionSnapshot,
    LedgerTab,
)
from backend.entities import entity_kind
from backend.findings import extract_project_findings
from backend.indexer import ProjectScan
from backend.attention_scoring import score_findings


def build_attention_snapshot(
    scans: dict[str, ProjectScan],
    analyses: dict[str, ProjectAnalysis],
    *,
    preset: AttentionPreset = "mixed",
    lens: AttentionLens = "semantic",
    ledger_tab: LedgerTab = "attention",
    scope_project: str | None = None,
    selected_id: str | None = None,
) -> AttentionSnapshot:
    """Build an all-project or one-project attention snapshot."""
    active_scans = _scope_scans(scans, scope_project)
    findings = _all_findings(active_scans)
    scored_findings = score_findings(findings)
    nodes = _graph_nodes(active_scans, scored_findings, preset)
    edges = _graph_edges(nodes, scored_findings)
    selected_profile = _selected_profile(selected_id, scored_findings, nodes)
    built_at = datetime.now(timezone.utc)
    return AttentionSnapshot(
        snapshot_id=_snapshot_id(active_scans, preset, lens, ledger_tab, built_at),
        built_at=built_at,
        scope_kind="project" if scope_project else "all",
        scope_project=scope_project,
        preset=preset,
        lens=lens,
        ledger_tab=ledger_tab,
        included_projects=sorted(active_scans),
        warnings=_snapshot_warnings(active_scans, analyses),
        findings=_filter_ledger(scored_findings, ledger_tab),
        graph_nodes=nodes,
        graph_edges=edges,
        selected_profile=selected_profile,
    )


def _scope_scans(scans: dict[str, ProjectScan], scope_project: str | None) -> dict[str, ProjectScan]:
    if scope_project is None:
        return dict(sorted(scans.items()))
    if scope_project not in scans:
        raise KeyError(scope_project)
    return {scope_project: scans[scope_project]}


def _all_findings(scans: dict[str, ProjectScan]) -> list[AttentionFinding]:
    findings: list[AttentionFinding] = []
    for scan in scans.values():
        findings.extend(extract_project_findings(scan, Path(scan.project.path)))
    if findings:
        return findings
    # Ensure a fresh project still has something to orient around.
    for scan in scans.values():
        for entity in scan.entities:
            if entity_kind(entity) in {"hypothesis", "question", "inquiry"}:
                findings.append(
                    AttentionFinding(
                        id=f"{scan.project.slug}:finding:auto:orientation:{_stable_hash(entity.id)}",
                        project_id=scan.project.slug,
                        claim_text=entity.title,
                        related_entities=[entity.id],
                        primary_source=entity.file_path,
                        evidence_status=entity.status,
                        updated=entity.updated.isoformat() if entity.updated else None,
                    )
                )
    return findings


def _graph_nodes(
    scans: dict[str, ProjectScan],
    findings: list[AttentionFinding],
    preset: AttentionPreset,
) -> list[AttentionGraphNode]:
    candidates: list[AttentionGraphNode] = []
    if preset in {"findings", "mixed"}:
        for finding in findings:
            candidates.append(
                AttentionGraphNode(
                    id=finding.id,
                    project_id=finding.project_id,
                    entity_ref=finding.id,
                    label=finding.claim_text,
                    entity_type="finding",
                    node_kind="finding",
                    scores=finding.scores,
                    support_class=finding.support_class,
                    evidence_status=finding.evidence_status,
                    identification_strength=finding.identification_strength,
                    related_finding_ids=[finding.id],
                )
            )
    if preset in {"hypotheses", "mixed"}:
        candidates.extend(_entity_nodes(scans, {"hypothesis"}))
    if preset in {"inquiries", "mixed"}:
        candidates.extend(_entity_nodes(scans, {"inquiry"}))
    if preset == "mixed":
        candidates.extend(_entity_nodes(scans, {"question", "dataset", "workflow", "workflow-run"}))
        candidates.extend(_task_nodes(scans))

    candidates.sort(key=lambda node: (-node.scores.composite, node.project_id, node.id))
    deduped = {node.id: node for node in candidates}
    return list(deduped.values())[:50]


def _entity_nodes(scans: dict[str, ProjectScan], kinds: set[str]) -> list[AttentionGraphNode]:
    nodes: list[AttentionGraphNode] = []
    for scan in scans.values():
        for entity in scan.entities:
            kind = entity_kind(entity)
            if kind not in kinds:
                continue
            node_kind = "entity"
            if kind in {"hypothesis", "question", "inquiry", "dataset", "workflow"}:
                node_kind = kind
            if kind == "workflow-run":
                node_kind = "workflow"
            nodes.append(
                AttentionGraphNode(
                    id=f"{scan.project.slug}:{entity.id}",
                    project_id=scan.project.slug,
                    entity_ref=entity.id,
                    label=entity.title,
                    entity_type=kind,
                    node_kind=node_kind,
                )
            )
    return nodes


def _task_nodes(scans: dict[str, ProjectScan]) -> list[AttentionGraphNode]:
    nodes: list[AttentionGraphNode] = []
    for scan in scans.values():
        for task in scan.tasks:
            if task.status in {"done", "completed", "retired"}:
                continue
            nodes.append(
                AttentionGraphNode(
                    id=f"{scan.project.slug}:task:{task.id}",
                    project_id=scan.project.slug,
                    entity_ref=f"task:{task.id}",
                    label=task.title,
                    entity_type="task",
                    node_kind="task",
                )
            )
    return nodes


def _graph_edges(nodes: list[AttentionGraphNode], findings: list[AttentionFinding]) -> list[AttentionGraphEdge]:
    node_ids = {node.id for node in nodes}
    edges: list[AttentionGraphEdge] = []
    for finding in findings:
        if finding.id not in node_ids:
            continue
        for related in finding.related_entities:
            target = f"{finding.project_id}:{related}"
            if target not in node_ids:
                continue
            edges.append(
                AttentionGraphEdge(
                    id=f"{finding.id}->{target}",
                    source=finding.id,
                    target=target,
                    relation="related",
                    evidence_status=finding.evidence_status,
                    identification_strength=finding.identification_strength,
                    load_bearingness=finding.scores.load_bearingness,
                    cross_project=False,
                )
            )
    return edges


def _filter_ledger(findings: list[AttentionFinding], ledger_tab: LedgerTab) -> list[AttentionFinding]:
    if ledger_tab == "credible":
        return [finding for finding in findings if finding.support_class in {"strongest", "moderate"}]
    if ledger_tab == "fragile":
        return sorted(findings, key=lambda finding: (-finding.scores.fragility, finding.id))
    if ledger_tab == "recent":
        return sorted(findings, key=lambda finding: (finding.updated is None, finding.updated or "", finding.id), reverse=True)
    if ledger_tab == "actionable":
        return sorted(findings, key=lambda finding: (-finding.scores.actionability, finding.id))
    if ledger_tab == "ruled_out":
        return [finding for finding in findings if finding.evidence_status in {"eliminated", "falsified", "superseded"}]
    if ledger_tab == "promising":
        return sorted(findings, key=lambda finding: (-finding.scores.interestingness, -finding.scores.importance, finding.id))
    return findings


def _selected_profile(
    selected_id: str | None,
    findings: list[AttentionFinding],
    nodes: list[AttentionGraphNode],
) -> AttentionProfile | None:
    if selected_id is None:
        return None
    finding = next((item for item in findings if item.id == selected_id), None)
    if finding is not None:
        return AttentionProfile(
            id=finding.id,
            project_id=finding.project_id,
            title=finding.claim_text,
            entity_type="finding",
            summary=finding.claim_text,
            why_it_matters=_why_finding_matters(finding),
            evidence_state=f"{finding.support_class}; evidence={finding.evidence_status or 'unclassified'}; identification={finding.identification_strength or 'unavailable'}",
            weak_points=_weak_points(finding),
            key_relationships=[
                AttentionRelationship(ref=ref, project_id=finding.project_id, entity_type=ref.split(":", 1)[0], title=ref, relation="related", reason="finding provenance")
                for ref in finding.related_entities[:8]
            ],
            score_breakdown=finding.scores,
            score_reasons=finding.score_reasons,
            source_refs=finding.source_refs,
        )
    node = next((item for item in nodes if item.id == selected_id), None)
    if node is None:
        return None
    return AttentionProfile(
        id=node.id,
        project_id=node.project_id,
        title=node.label,
        entity_type=node.entity_type,
        summary=node.label,
        why_it_matters="Selected because it is part of the current attention slice.",
        evidence_state=node.evidence_status or "unclassified",
        score_breakdown=node.scores,
    )


def _why_finding_matters(finding: AttentionFinding) -> str:
    if finding.scores.fragility >= 0.6 and finding.scores.importance >= 0.5:
        return "Important and fragile; future work could clarify it."
    if finding.scores.credibility >= 0.7:
        return "Credible internal support makes this load-bearing."
    return "Potential lead; uncertainty remains visible."


def _weak_points(finding: AttentionFinding) -> list[str]:
    points: list[str] = []
    if finding.support_class in {"untrustworthy", "weak"}:
        points.append("No strong internal workflow-backed support.")
    if finding.support_class == "still_fragile":
        points.append("Only one internal workflow supports this finding.")
    if finding.identification_strength in {None, "none", "observational"}:
        points.append("Causal identification is limited or unavailable.")
    return points


def _snapshot_warnings(scans: dict[str, ProjectScan], analyses: dict[str, ProjectAnalysis]) -> list[str]:
    warnings: list[str] = []
    for project_id in sorted(scans):
        if project_id not in analyses:
            warnings.append(f"{project_id}: analysis unavailable")
        elif not analyses[project_id].graph.nodes:
            warnings.append(f"{project_id}: graph unavailable")
    return warnings


def _snapshot_id(scans: dict[str, ProjectScan], preset: str, lens: str, ledger_tab: str, built_at: datetime) -> str:
    raw = "|".join(sorted(scans)) + f"|{preset}|{lens}|{ledger_tab}|{built_at.isoformat()}"
    return f"attention:{_stable_hash(raw)}"


def _stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
```

- [ ] **Step 4: Run snapshot tests**

Run: `uv run --frozen pytest tests/test_attention_api.py::test_build_attention_snapshot_defaults_to_all_projects_mixed tests/test_attention_api.py::test_build_attention_snapshot_selected_profile_has_score_breakdown -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/attention.py tests/test_attention_api.py
git commit -m "feat(attention): build workspace snapshots"
```

---

### Task 5: Attention Store And API Route

**Files:**
- Modify: `backend/store.py`
- Create: `backend/routes/attention.py`
- Modify: `backend/app.py`
- Modify: `tests/test_attention_api.py`

- [ ] **Step 1: Add API route tests**

Append to `tests/test_attention_api.py`:

```python
from fastapi.testclient import TestClient
from backend.app import create_app
from science_model import DashboardConfig


def test_get_attention_endpoint_returns_snapshot(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    cfg = DashboardConfig(projects=[str(root)])
    client = TestClient(create_app(cfg))

    response = client.get("/api/attention?preset=3&tab=attention")

    assert response.status_code == 200
    data = response.json()
    assert data["preset"] == "mixed"
    assert data["scope_kind"] == "all"
    assert data["included_projects"] == ["test-project"]
    assert "snapshot_id" in data


def test_get_attention_endpoint_rejects_unknown_project_scope(tmp_path: Path) -> None:
    root = _make_project(tmp_path)
    cfg = DashboardConfig(projects=[str(root)])
    client = TestClient(create_app(cfg))

    response = client.get("/api/attention?project=missing")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/test_attention_api.py::test_get_attention_endpoint_returns_snapshot tests/test_attention_api.py::test_get_attention_endpoint_rejects_unknown_project_scope -v`

Expected: FAIL with 404 for `/api/attention`.

- [ ] **Step 3: Extend store protocol and implementation**

Modify `backend/store.py`:

```python
# add imports near existing imports
from backend.attention import build_attention_snapshot
from backend.attention_models import AttentionLens, AttentionPreset, AttentionSnapshot, LedgerTab
```

Add to `DataStore` protocol:

```python
    def get_attention(
        self,
        *,
        preset: AttentionPreset,
        lens: AttentionLens,
        ledger_tab: LedgerTab,
        project: str | None,
        selected_id: str | None,
    ) -> AttentionSnapshot: ...
```

Add to `FileSystemStore`:

```python
    def get_attention(
        self,
        *,
        preset: AttentionPreset,
        lens: AttentionLens,
        ledger_tab: LedgerTab,
        project: str | None = None,
        selected_id: str | None = None,
    ) -> AttentionSnapshot:
        return build_attention_snapshot(
            self._scans,
            self._analyses,
            preset=preset,
            lens=lens,
            ledger_tab=ledger_tab,
            scope_project=project,
            selected_id=selected_id,
        )
```

- [ ] **Step 4: Add route**

Create `backend/routes/attention.py`:

```python
"""Attention workspace API route."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.attention_models import AttentionLens, AttentionPreset, AttentionSnapshot, LedgerTab

router = APIRouter(tags=["attention"])

PRESET_ALIASES: dict[str, AttentionPreset] = {
    "1": "findings",
    "findings": "findings",
    "2": "hypotheses",
    "hypotheses": "hypotheses",
    "3": "mixed",
    "mixed": "mixed",
    "4": "inquiries",
    "inquiries": "inquiries",
}


@router.get("/attention", response_model=AttentionSnapshot)
async def get_attention(
    request: Request,
    preset: str = Query(default="3"),
    lens: AttentionLens = "semantic",
    tab: LedgerTab = "attention",
    project: str | None = None,
    selected: str | None = None,
) -> AttentionSnapshot:
    store = request.app.state.store
    resolved_preset = PRESET_ALIASES.get(preset)
    if resolved_preset is None:
        raise HTTPException(status_code=422, detail=f"Unknown attention preset: {preset}")
    try:
        return store.get_attention(
            preset=resolved_preset,
            lens=lens,
            ledger_tab=tab,
            project=project,
            selected_id=selected,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project {project} not found")
```

Modify `backend/app.py` to import and include the new router next to the other routers:

```python
from backend.routes.attention import router as attention_router

# inside create_app, next to existing include_router calls:
app.include_router(attention_router, prefix="/api")
```

- [ ] **Step 5: Run API tests**

Run: `uv run --frozen pytest tests/test_attention_api.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/store.py backend/routes/attention.py backend/app.py tests/test_attention_api.py
git commit -m "feat(attention): expose workspace snapshot API"
```

---

### Task 6: Frontend Library Baseline And Router Package

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1: Install TanStack Router**

Run:

```bash
cd frontend && npm install @tanstack/react-router
```

Expected: `frontend/package.json` includes `@tanstack/react-router` under dependencies and `frontend/package-lock.json` updates.

- [ ] **Step 2: Confirm graph renderer dependency choice**

Run:

```bash
cd frontend && npm ls react-force-graph-2d react-force-graph-3d
```

Expected: both packages are present. V1 uses `react-force-graph-2d` for the attention workspace and keeps the existing `react-force-graph-3d` dependency available for the existing project graph route.

Do not install `r3f-forcegraph`, `@react-three/fiber`, or `@react-three/drei` in V1 unless the implementation intentionally replaces the React Force Graph renderer. If choosing that alternate path instead, run:

```bash
cd frontend && npm install r3f-forcegraph @react-three/fiber @react-three/drei
```

Then update Task 9 to implement an R3F `<Canvas>` graph component instead of the `react-force-graph-2d` component.

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add tanstack router dependency"
```

---

### Task 7: Frontend Attention Types And API Client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add TypeScript attention types**

Append to `frontend/src/types/index.ts`:

```ts
export type AttentionPreset = 'findings' | 'hypotheses' | 'mixed' | 'inquiries'
export type AttentionLens = 'semantic' | 'evidence' | 'fragile' | 'recent' | 'projects' | 'workflows'
export type LedgerTab = 'attention' | 'promising' | 'credible' | 'fragile' | 'recent' | 'actionable' | 'ruled_out'
export type SupportClass = 'strongest' | 'moderate' | 'weak' | 'untrustworthy' | 'still_fragile'

export interface AttentionScoreBreakdown {
  importance: number
  fragility: number
  interestingness: number
  recency: number
  actionability: number
  centrality: number
  load_bearingness: number
  unresolved_uncertainty: number
  credibility: number
  composite: number
}

export interface AttentionScoreReason {
  signal: string
  value: number
  reason: string
}

export interface SupportBreakdown {
  internal_workflows: number
  internal_workflows_stale: number
  internal_data_refs: number
  literature_refs: number
  ontology_refs: number
  counterevidence_refs: number
}

export interface AttentionFinding {
  id: string
  project_id: string
  claim_text: string
  proposition_refs: string[]
  source_refs: string[]
  primary_source: string | null
  related_entities: string[]
  evidence_status: string | null
  identification_strength: string | null
  support_class: SupportClass
  support_breakdown: SupportBreakdown
  scores: AttentionScoreBreakdown
  score_reasons: AttentionScoreReason[]
  supersession: string[]
  freshness: string
  updated: string | null
}

export interface AttentionGraphNode {
  id: string
  project_id: string
  entity_ref: string
  label: string
  entity_type: string
  node_kind: string
  scores: AttentionScoreBreakdown
  support_class: SupportClass | null
  evidence_status: string | null
  identification_strength: string | null
  related_finding_ids: string[]
}

export interface AttentionGraphEdge {
  id: string
  source: string
  target: string
  relation: string
  evidence_status: string | null
  identification_strength: string | null
  load_bearingness: number
  cross_project: boolean
}

export interface AttentionRelationship {
  ref: string
  project_id: string
  entity_type: string
  title: string
  relation: string
  reason: string
}

export interface AttentionProfile {
  id: string
  project_id: string
  title: string
  entity_type: string
  summary: string
  why_it_matters: string
  evidence_state: string
  weak_points: string[]
  key_relationships: AttentionRelationship[]
  score_breakdown: AttentionScoreBreakdown
  score_reasons: AttentionScoreReason[]
  source_refs: string[]
}

export interface AttentionSnapshot {
  snapshot_id: string
  built_at: string
  schema_version: string
  scope_kind: 'all' | 'project'
  scope_project: string | null
  preset: AttentionPreset
  lens: AttentionLens
  ledger_tab: LedgerTab
  included_projects: string[]
  warnings: string[]
  findings: AttentionFinding[]
  graph_nodes: AttentionGraphNode[]
  graph_edges: AttentionGraphEdge[]
  selected_profile: AttentionProfile | null
}
```

- [ ] **Step 2: Add API client method**

Modify imports in `frontend/src/api/client.ts`:

```ts
  AttentionLens,
  AttentionSnapshot,
  LedgerTab,
```

Add to `api`:

```ts
  attention: {
    get: (params?: { preset?: string; lens?: AttentionLens; tab?: LedgerTab; project?: string; selected?: string }) => {
      const qs = new URLSearchParams()
      if (params?.preset) qs.set('preset', params.preset)
      if (params?.lens) qs.set('lens', params.lens)
      if (params?.tab) qs.set('tab', params.tab)
      if (params?.project) qs.set('project', params.project)
      if (params?.selected) qs.set('selected', params.selected)
      const suffix = qs.size > 0 ? `?${qs}` : ''
      return get<AttentionSnapshot>(`/attention${suffix}`)
    },
  },
```

- [ ] **Step 3: Run frontend build type check**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts
git commit -m "feat(attention): add frontend API types"
```

---

### Task 8: URL State And Preferences Hook

**Files:**
- Create: `frontend/src/components/Attention/useAttentionState.ts`

- [ ] **Step 1: Create state hook**

Create `frontend/src/components/Attention/useAttentionState.ts`:

```ts
import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import type { AttentionLens, LedgerTab } from '../../types'

const PREF_KEY = 'science-web.attention.preferences.v1'

export interface AttentionPreferences {
  lens: AttentionLens
  tab: LedgerTab
  labels: boolean
}

export interface AttentionUrlState {
  preset: string
  lens: AttentionLens
  tab: LedgerTab
  project: string | null
  selected: string | null
}

const DEFAULT_PREFS: AttentionPreferences = {
  lens: 'semantic',
  tab: 'attention',
  labels: true,
}

export function loadAttentionPreferences(): AttentionPreferences {
  try {
    const raw = window.localStorage.getItem(PREF_KEY)
    if (!raw) return DEFAULT_PREFS
    return { ...DEFAULT_PREFS, ...JSON.parse(raw) }
  } catch {
    return DEFAULT_PREFS
  }
}

export function saveAttentionPreferences(preferences: AttentionPreferences) {
  window.localStorage.setItem(PREF_KEY, JSON.stringify(preferences))
}

export function useAttentionState() {
  const location = useLocation()
  const navigate = useNavigate()
  const preferences = loadAttentionPreferences()

  const state = useMemo<AttentionUrlState>(() => {
    const qs = new URLSearchParams(location.search)
    return {
      preset: qs.get('preset') ?? '3',
      lens: (qs.get('lens') as AttentionLens | null) ?? preferences.lens,
      tab: (qs.get('tab') as LedgerTab | null) ?? preferences.tab,
      project: qs.get('project'),
      selected: qs.get('selected'),
    }
  }, [location.search, preferences.lens, preferences.tab])

  function setState(patch: Partial<AttentionUrlState>) {
    const next = { ...state, ...patch }
    const qs = new URLSearchParams()
    if (next.preset !== '3') qs.set('preset', next.preset)
    if (next.lens !== 'semantic') qs.set('lens', next.lens)
    if (next.tab !== 'attention') qs.set('tab', next.tab)
    if (next.project) qs.set('project', next.project)
    if (next.selected) qs.set('selected', next.selected)
    saveAttentionPreferences({ ...preferences, lens: next.lens, tab: next.tab })
    navigate({ pathname: '/', search: qs.toString() ? `?${qs}` : '' })
  }

  return { state, setState, preferences, savePreferences: saveAttentionPreferences }
}
```

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Attention/useAttentionState.ts
git commit -m "feat(attention): manage workspace URL state"
```

---

### Task 9: Attention Workspace Components

**Files:**
- Create: `frontend/src/components/Attention/AttentionGraph.tsx`
- Create: `frontend/src/components/Attention/FindingsLedger.tsx`
- Create: `frontend/src/components/Attention/ResearchMeaningSidebar.tsx`
- Create: `frontend/src/components/Attention/AttentionControls.tsx`
- Create: `frontend/src/routes/AttentionWorkspace.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create React Force Graph component**

Create `frontend/src/components/Attention/AttentionGraph.tsx`:

```tsx
import { useMemo, useRef } from 'react'
import ForceGraph2D, { type ForceGraphMethods, type NodeObject, type LinkObject } from 'react-force-graph-2d'
import type { AttentionGraphEdge, AttentionGraphNode } from '../../types'

interface AttentionForceNode extends NodeObject {
  id: string
  label: string
  source: AttentionGraphNode
  color: string
  stroke: string
  radius: number
  fx: number
  fy: number
}

interface AttentionForceLink extends LinkObject<AttentionForceNode> {
  id: string
  source: string
  target: string
  color: string
  width: number
  dashed: boolean
}

export function AttentionGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
}: {
  nodes: AttentionGraphNode[]
  edges: AttentionGraphEdge[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const graphRef = useRef<ForceGraphMethods<AttentionForceNode, AttentionForceLink> | undefined>(undefined)
  const graphData = useMemo(() => buildGraphData(nodes, edges), [nodes, edges])

  return (
    <div className="h-full w-full rounded border border-neutral-800 bg-neutral-950">
      <ForceGraph2D<AttentionForceNode, AttentionForceLink>
        ref={graphRef}
        graphData={graphData}
        backgroundColor="#0a0a0a"
        cooldownTicks={0}
        nodeRelSize={1}
        linkColor={(link) => link.color}
        linkWidth={(link) => link.width}
        linkLineDash={(link) => (link.dashed ? [4, 4] : undefined)}
        nodeCanvasObject={(node, ctx, globalScale) => drawNode(node, ctx, globalScale, node.id === selectedId)}
        nodePointerAreaPaint={(node, color, ctx) => {
          ctx.fillStyle = color
          ctx.beginPath()
          ctx.arc(node.fx, node.fy, node.radius + 8, 0, Math.PI * 2)
          ctx.fill()
        }}
        onNodeClick={(node) => onSelect(node.id)}
      />
    </div>
  )
}

function buildGraphData(nodes: AttentionGraphNode[], edges: AttentionGraphEdge[]) {
  const positioned = layoutNodes(nodes)
  const nodeIds = new Set(positioned.map((node) => node.id))
  return {
    nodes: positioned,
    links: edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        color: edge.cross_project ? '#818cf8' : edgeColor(edge.evidence_status),
        width: 1 + edge.load_bearingness * 3,
        dashed: edge.evidence_status === 'eliminated' || edge.cross_project,
      })),
  }
}

function layoutNodes(nodes: AttentionGraphNode[]): AttentionForceNode[] {
  const radius = 160
  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(1, nodes.length) - Math.PI / 2
    const scoreRadius = radius * (0.45 + 0.55 * (1 - Math.min(1, node.scores.composite)))
    return {
      id: node.id,
      label: node.label,
      source: node,
      color: nodeColor(node),
      stroke: supportStroke(node.support_class),
      radius: 7 + node.scores.composite * 12,
      fx: Math.cos(angle) * scoreRadius,
      fy: Math.sin(angle) * scoreRadius,
    }
  })
}

function drawNode(node: AttentionForceNode, ctx: CanvasRenderingContext2D, globalScale: number, selected: boolean) {
  ctx.save()
  ctx.fillStyle = node.color
  ctx.strokeStyle = selected ? '#f8fafc' : node.stroke
  ctx.lineWidth = selected ? 2.5 : 1.5
  ctx.beginPath()
  ctx.arc(node.fx, node.fy, node.radius + (selected ? 4 : 0), 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = '#d4d4d4'
  ctx.font = `${Math.max(9, 12 / globalScale)}px sans-serif`
  ctx.textAlign = 'center'
  ctx.fillText(truncate(node.label, 28), node.fx, node.fy + node.radius + 14)
  ctx.restore()
}

function nodeColor(node: AttentionGraphNode): string {
  if (node.node_kind === 'finding') return '#38bdf8'
  if (node.node_kind === 'hypothesis') return '#a78bfa'
  if (node.node_kind === 'inquiry') return '#34d399'
  if (node.node_kind === 'task') return '#f59e0b'
  return '#94a3b8'
}

function supportStroke(support: string | null): string {
  if (support === 'strongest') return '#22c55e'
  if (support === 'moderate') return '#84cc16'
  if (support === 'weak') return '#f59e0b'
  if (support === 'still_fragile') return '#fb923c'
  if (support === 'untrustworthy') return '#ef4444'
  return '#475569'
}

function edgeColor(status: string | null): string {
  if (status === 'supported') return '#22c55e'
  if (status === 'tentative') return '#f59e0b'
  if (status === 'eliminated') return '#64748b'
  if (status === 'unknown') return '#fb7185'
  return '#525252'
}

function truncate(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`
}
```

- [ ] **Step 2: Create ledger component**

Create `frontend/src/components/Attention/FindingsLedger.tsx`:

```tsx
import type { AttentionFinding, LedgerTab } from '../../types'

const TABS: Array<{ id: LedgerTab; label: string }> = [
  { id: 'attention', label: 'Attention' },
  { id: 'promising', label: 'Promising' },
  { id: 'credible', label: 'Credible' },
  { id: 'fragile', label: 'Fragile' },
  { id: 'recent', label: 'Recent' },
  { id: 'actionable', label: 'Actionable' },
  { id: 'ruled_out', label: 'Ruled Out' },
]

export function FindingsLedger({
  findings,
  tab,
  selectedId,
  onTab,
  onSelect,
}: {
  findings: AttentionFinding[]
  tab: LedgerTab
  selectedId: string | null
  onTab: (tab: LedgerTab) => void
  onSelect: (id: string) => void
}) {
  return (
    <section className="flex min-h-0 flex-col border-l border-neutral-800 bg-neutral-950">
      <div className="flex flex-wrap gap-1 border-b border-neutral-800 p-2">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onTab(item.id)}
            className={`rounded px-2 py-1 text-xs ${tab === item.id ? 'bg-sky-500/20 text-sky-200' : 'text-neutral-400 hover:bg-neutral-800'}`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {findings.length === 0 ? (
          <p className="p-3 text-sm text-neutral-500">No findings match this view.</p>
        ) : (
          findings.map((finding) => (
            <button
              key={finding.id}
              type="button"
              onClick={() => onSelect(finding.id)}
              className={`mb-2 block w-full rounded border p-3 text-left ${selectedId === finding.id ? 'border-sky-500 bg-sky-500/10' : 'border-neutral-800 bg-neutral-900/70 hover:bg-neutral-900'}`}
            >
              <div className="flex items-center gap-2 text-[11px] text-neutral-500">
                <span>{finding.project_id}</span>
                <span className="rounded bg-neutral-800 px-1.5 py-0.5">{finding.support_class.replace('_', ' ')}</span>
                <span>score {finding.scores.composite.toFixed(2)}</span>
              </div>
              <p className="mt-2 text-sm font-medium text-neutral-100">{finding.claim_text}</p>
              <p className="mt-1 text-xs text-neutral-400">
                credible {finding.scores.credibility.toFixed(2)} · fragile {finding.scores.fragility.toFixed(2)} · interesting {finding.scores.interestingness.toFixed(2)}
              </p>
              {finding.score_reasons[0] && <p className="mt-2 text-xs text-neutral-500">{finding.score_reasons[0].reason}</p>}
            </button>
          ))
        )}
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Create sidebar and controls**

Create `frontend/src/components/Attention/ResearchMeaningSidebar.tsx`:

```tsx
import type { AttentionProfile } from '../../types'

export function ResearchMeaningSidebar({ profile }: { profile: AttentionProfile | null }) {
  if (!profile) {
    return (
      <aside className="border-t border-neutral-800 bg-neutral-950 p-4 text-sm text-neutral-500">
        Select a node or finding to inspect its research meaning.
      </aside>
    )
  }
  return (
    <aside className="border-t border-neutral-800 bg-neutral-950 p-4">
      <div className="text-xs text-neutral-500">{profile.project_id} · {profile.entity_type}</div>
      <h2 className="mt-1 text-lg font-semibold text-neutral-100">{profile.title}</h2>
      <p className="mt-3 text-sm text-neutral-300">{profile.summary}</p>
      <section className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Why It Matters</h3>
        <p className="mt-1 text-sm text-neutral-300">{profile.why_it_matters}</p>
      </section>
      <section className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Evidence State</h3>
        <p className="mt-1 text-sm text-neutral-300">{profile.evidence_state}</p>
      </section>
      {profile.weak_points.length > 0 && (
        <section className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Weak Points</h3>
          <ul className="mt-1 space-y-1 text-sm text-neutral-300">
            {profile.weak_points.map((point) => <li key={point}>{point}</li>)}
          </ul>
        </section>
      )}
      <section className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-neutral-500">Score Breakdown</h3>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-neutral-300">
          {Object.entries(profile.score_breakdown).map(([key, value]) => (
            <div key={key} className="rounded bg-neutral-900 p-2">
              <div className="text-neutral-500">{key.replaceAll('_', ' ')}</div>
              <div>{typeof value === 'number' ? value.toFixed(2) : value}</div>
            </div>
          ))}
        </div>
      </section>
    </aside>
  )
}
```

Create `frontend/src/components/Attention/AttentionControls.tsx`:

```tsx
import type { AttentionLens } from '../../types'

export function AttentionControls({
  preset,
  lens,
  builtAt,
  warnings,
  onPreset,
  onLens,
  onRefresh,
}: {
  preset: string
  lens: AttentionLens
  builtAt: string | null
  warnings: string[]
  onPreset: (preset: string) => void
  onLens: (lens: AttentionLens) => void
  onRefresh: () => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-800 bg-neutral-950 px-4 py-3">
      <div className="flex items-center gap-2">
        {['1', '2', '3', '4'].map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onPreset(item)}
            className={`h-8 w-8 rounded border ${preset === item ? 'border-sky-400 bg-sky-400/15 text-sky-100' : 'border-neutral-800 text-neutral-400 hover:bg-neutral-900'}`}
          >
            {item}
          </button>
        ))}
      </div>
      <select
        value={lens}
        onChange={(event) => onLens(event.target.value as AttentionLens)}
        className="rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-sm text-neutral-200"
      >
        <option value="semantic">Semantic</option>
        <option value="evidence">Evidence</option>
        <option value="fragile">Fragile</option>
        <option value="recent">Recent</option>
        <option value="projects">Projects</option>
        <option value="workflows">Workflows</option>
      </select>
      <div className="flex items-center gap-3 text-xs text-neutral-500">
        <span>{builtAt ? `Built ${new Date(builtAt).toLocaleTimeString()}` : 'No snapshot'}</span>
        {warnings.length > 0 && <span>{warnings.length} warnings</span>}
        <button type="button" onClick={onRefresh} className="rounded border border-neutral-800 px-2 py-1 text-neutral-300 hover:bg-neutral-900">Refresh</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create workspace route and wire root route**

Create `frontend/src/routes/AttentionWorkspace.tsx`:

```tsx
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AttentionSnapshot, LedgerTab } from '../types'
import { AttentionControls } from '../components/Attention/AttentionControls'
import { AttentionGraph } from '../components/Attention/AttentionGraph'
import { FindingsLedger } from '../components/Attention/FindingsLedger'
import { ResearchMeaningSidebar } from '../components/Attention/ResearchMeaningSidebar'
import { useAttentionState } from '../components/Attention/useAttentionState'

export function AttentionWorkspace() {
  const { state, setState } = useAttentionState()
  const [snapshot, setSnapshot] = useState<AttentionSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSnapshot = useCallback(() => {
    setLoading(true)
    setError(null)
    api.attention.get({
      preset: state.preset,
      lens: state.lens,
      tab: state.tab,
      project: state.project ?? undefined,
      selected: state.selected ?? undefined,
    })
      .then(setSnapshot)
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'Failed to load attention workspace.'))
      .finally(() => setLoading(false))
  }, [state.lens, state.preset, state.project, state.selected, state.tab])

  useEffect(() => {
    fetchSnapshot()
  }, [fetchSnapshot])

  return (
    <div className="flex h-[calc(100vh-40px)] flex-col bg-neutral-950 text-neutral-100">
      <AttentionControls
        preset={state.preset}
        lens={state.lens}
        builtAt={snapshot?.built_at ?? null}
        warnings={snapshot?.warnings ?? []}
        onPreset={(preset) => setState({ preset })}
        onLens={(lens) => setState({ lens })}
        onRefresh={fetchSnapshot}
      />
      {error && <div className="border-b border-red-900 bg-red-950/40 px-4 py-2 text-sm text-red-200">{error}</div>}
      {loading && !snapshot ? (
        <div className="p-6 text-sm text-neutral-400">Loading attention workspace...</div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_420px] grid-rows-[minmax(0,1fr)_320px]">
          <main className="min-h-0 p-4">
            <AttentionGraph
              nodes={snapshot?.graph_nodes ?? []}
              edges={snapshot?.graph_edges ?? []}
              selectedId={state.selected}
              onSelect={(selected) => setState({ selected })}
            />
          </main>
          <FindingsLedger
            findings={snapshot?.findings ?? []}
            tab={state.tab}
            selectedId={state.selected}
            onTab={(tab: LedgerTab) => setState({ tab })}
            onSelect={(selected) => setState({ selected })}
          />
          <div className="col-span-2 min-h-0 overflow-y-auto">
            <ResearchMeaningSidebar profile={snapshot?.selected_profile ?? null} />
          </div>
        </div>
      )}
    </div>
  )
}
```

Modify `frontend/src/App.tsx`:

```tsx
const AttentionWorkspace = lazy(() => import('./routes/AttentionWorkspace').then((module) => ({ default: module.AttentionWorkspace })))
```

Change the root route:

```tsx
<Route path="/" element={<AttentionWorkspace />} />
```

- [ ] **Step 5: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Attention frontend/src/routes/AttentionWorkspace.tsx frontend/src/App.tsx
git commit -m "feat(attention): add split workspace UI"
```

---

### Task 10: Keyboard Presets And Browser Behavior

**Files:**
- Modify: `frontend/src/hooks/useKeyboard.ts`

- [ ] **Step 1: Update keyboard handler for workspace presets**

Modify `frontend/src/hooks/useKeyboard.ts`:

```ts
// add near current imports
import { useLocation } from 'react-router-dom'
```

Inside `useKeyboard`:

```ts
  const location = useLocation()
```

Inside the handler, before current `2`/`3` graph dimension handling:

```ts
      if (location.pathname === '/' && ['1', '2', '3', '4'].includes(e.key)) {
        const qs = new URLSearchParams(location.search)
        if (e.key === '3') qs.delete('preset')
        else qs.set('preset', e.key)
        navigate({ pathname: '/', search: qs.toString() ? `?${qs}` : '' })
        return
      }
```

Change the effect dependency list to include `location.pathname` and `location.search`.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useKeyboard.ts
git commit -m "feat(attention): add workspace preset shortcuts"
```

---

### Task 11: Verification Sweep

**Files:**
- Modify if needed: files touched by prior tasks only.

- [ ] **Step 1: Run backend tests for the new surface**

Run: `uv run --frozen pytest tests/test_findings.py tests/test_attention_scoring.py tests/test_attention_api.py -v`

Expected: PASS.

- [ ] **Step 2: Run existing project API regression tests**

Run: `uv run --frozen pytest tests/test_api_projects.py tests/test_analysis.py tests/test_store.py -v`

Expected: PASS.

- [ ] **Step 3: Run Python lint and type checks**

Run: `uv run --frozen ruff check .`

Expected: PASS.

Run: `uv run --frozen pyright`

Expected: PASS.

- [ ] **Step 4: Run frontend checks**

Run: `cd frontend && npm run build`

Expected: PASS.

Run: `cd frontend && npm run lint`

Expected: PASS.

- [ ] **Step 5: Manual smoke test**

Run: `make dev`

Expected:

- Frontend opens at `http://localhost:5173`.
- `/` renders the Split Attention Workspace.
- The default URL has no required query string and displays Mixed Attention.
- Pressing `1`, `2`, `3`, and `4` changes the graph preset through URL state.
- Selecting a graph node or ledger row updates `selected=` in the URL and fills the sidebar.
- The ledger shows Attention, Promising, Credible, Fragile, Recent, Actionable, and Ruled Out tabs.
- Snapshot build time is visible in the controls.

- [ ] **Step 6: Commit verification fixes if any**

If verification required fixes:

```bash
git add <changed-files>
git commit -m "fix(attention): address workspace verification issues"
```

If no fixes were needed, do not create an empty commit.

---

## Spec Coverage Self-Review

- Multi-project model: Tasks 4 and 5 build All Projects snapshots; Task 11 verifies root first-open behavior.
- Finding data model: Tasks 1 and 2 define stable IDs, extraction, deduplication, and provenance.
- Skeptical confidence: Task 3 implements support classes, fragile single-workflow treatment, and score reasons.
- Evidence semantics: Tasks 2 and 3 carry `edge_status`, `identification`, and ruled-out state into read models; Task 9 renders them in graph/ledger/sidebar text.
- Graph encoding and deterministic layout: Task 9 implements deterministic fixed-position `react-force-graph-2d` rendering and non-color support cues.
- Attention scoring and transparency: Tasks 3 and 8 expose composite scores and score breakdowns.
- State and persistence: Task 8 handles URL state and `localStorage`; Task 10 adds keyboard preset state.
- Build/freshness: Tasks 4 and 5 create snapshot IDs/build timestamps; Task 9 shows built time; deeper file-watch incremental refresh remains through existing rescan/watch behavior.
- Error/degraded states: Tasks 4 and 9 preserve warnings and empty results; Task 11 smoke-tests default rendering.

## Implementation Notes

- Keep commits small and in the order above.
- The implementation plan intentionally does not modify project source files outside `science-web`.
- Existing `/projects/:slug/graph` behavior should remain unchanged.
- If `pyright` objects to Pydantic mutation in Tasks 2 or 3, replace in-place mutation with `model_copy(update={...})` and keep the same external behavior.
