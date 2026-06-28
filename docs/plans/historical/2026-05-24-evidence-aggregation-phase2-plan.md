# Evidence Aggregation Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the log-odds belief scalar, append-only belief snapshots, and three QA checks on top of the Phase 1 ordinal aggregator, plus unify `query_uncertainty`'s contested signal — all behavior-additive.

**Architecture:** A new `belief_scalar.py` computes a deterministic `(support, dispute, net)` band from the *already-reduced* units `aggregate_belief` returns (no re-deriving independence). `belief_snapshot.py` + a `science belief snapshot` CLI write per-claim records to `knowledge/belief-snapshots.jsonl`. A `belief-scalar` opt-in (an active `core/decisions.md` decision carrying a `Feature flag` line) gates scalar *display* only; the ordinal state, snapshots, and checks are framework-wide. Three checks join the existing evidence-line check module.

**Tech Stack:** Python 3.12, rdflib, click, pytest, `uv`. Package root: `science/` (run tests with `cd science && uv run pytest`).

---

## Execution preamble (read once)

- **Worktree.** Execute in a dedicated worktree on branch `evidence-belief-phase2` (the controller creates it via `superpowers:using-git-worktrees`). Every subagent prompt MUST `cd` to the worktree path and confirm `git branch --show-current` is `evidence-belief-phase2` before editing, and use **explicit `git add <paths>`** (never `git add -A`/`.`) so nothing leaks to `main`.
- **Constraints.** No AI attribution / no `Co-Authored-By` in commits. Commit locally only; do **not** push. Composition > inheritance; explicit > defensive; fail early.
- **Test commands.** Per task: `cd science && uv run pytest tests/<file> -q`. After Task 11: full `cd science && uv run pytest -q` and `cd science/model && uv run pytest -q`.
- **Dependency order.** Tasks are ordered so each imports only code from earlier tasks. Do them in sequence.
- **Spec:** `docs/plans/historical/2026-05-24-evidence-aggregation-phase2-design.md` (rev c). Do not re-read it during a task — this plan carries all needed content.
- **Determinism note.** All scalar floats are rounded to 6 decimals in `belief_scalar`; tests compute expected values with `math.tanh(...)` rather than hardcoding, to stay arithmetic-error-free.

---

### Task 1: Numeric step helpers + constants (`belief_weights.py`)

**Files:**
- Modify: `science/src/science_tool/graph/belief_weights.py`
- Test: `science/tests/test_belief_weights.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_belief_weights.py`:

```python
def test_steps_are_rank_minus_one_floored_at_zero():
    from science_tool.graph.belief_weights import type_steps, role_steps, strength_steps
    assert type_steps("empirical_data_evidence") == 3   # rank 4 normalized - 1
    assert type_steps("literature") == 1                # rank 2 - 1
    assert role_steps("direct_test") == 2               # rank 3 - 1
    assert role_steps("background_constraint") == 0     # rank 1 - 1
    assert strength_steps("strong") == 2
    assert strength_steps("weak") == 0
    # Unknown / missing -> 0 (graceful), never negative
    assert type_steps("nonsense") == 0
    assert role_steps(None) == 0
    assert strength_steps("") == 0

def test_phase2_constants_present():
    from science_tool.graph import belief_weights as bw
    assert bw.PROXY_STEP_PENALTY == 2
    assert bw.DELTA_ENVELOPE == (0.3, 1.0)
    assert bw.CONFIG_VERSION == "belief-logodds-v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_belief_weights.py -q`
Expected: FAIL with `ImportError`/`AttributeError` (names not defined).

- [ ] **Step 3: Write minimal implementation** — append to `belief_weights.py`:

```python
PROXY_STEP_PENALTY = 2          # gated proxy counts two ordinal steps lower (logic, not a cliff)
DELTA_ENVELOPE = (0.3, 1.0)     # log-odds per ordinal step; OR ~1.35..2.72; SWEPT, not chosen
CONFIG_VERSION = "belief-logodds-v1"   # part of the golden #8 input set; bump on any change here


def type_steps(evidence_type: str | None) -> int:
    return max(0, EVIDENCE_TYPE_RANK.get(normalize_evidence_type(evidence_type), 0) - 1)


def role_steps(evidence_role: str | None) -> int:
    return max(0, EVIDENCE_ROLE_RANK.get(evidence_role or "", 0) - 1)


def strength_steps(strength: str | None) -> int:
    return max(0, STRENGTH_RANK.get(strength or "", 0) - 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_belief_weights.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_weights.py science/tests/test_belief_weights.py
git commit -m "feat(belief): add ordinal step helpers + Phase 2 scalar constants"
```

---

### Task 2: Scalar engine (`belief_scalar.py`)

**Files:**
- Create: `science/src/science_tool/graph/belief_scalar.py`
- Test: `science/tests/test_belief_scalar.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_belief_scalar.py`:

```python
import math

from science_tool.graph.belief import EvidenceUnit, aggregate_belief
from science_tool.graph.belief_scalar import BeliefScalar, belief_scalar, unit_score


def _u(stance="supports", **kw):
    base = dict(line_uri="x", stance=stance, strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test",
                evidence_type="empirical_data_evidence", dispute_scope=None,
                proxy_directness=None, has_measurement_model=False, source=None,
                observability_keys=())
    base.update(kw)
    return EvidenceUnit(**base)


def _r6(x):
    return round(x, 6)


def test_unit_score_is_sum_of_steps():
    assert unit_score(_u()) == 7                      # 3 (empirical) + 2 (direct) + 2 (strong)
    assert unit_score(_u(evidence_role="background_constraint", strength="weak",
                         evidence_type="literature")) == 1   # 1 + 0 + 0


def test_proxy_gate_lowers_score_by_two():
    gated = _u(proxy_directness="indirect", has_measurement_model=False)  # is_proxy_gated -> True
    assert unit_score(gated) == 5                     # 7 - 2


def test_single_support_band_matches_tanh():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1")])     # S=7, D=0
    s = belief_scalar(r)
    assert s.massed_support_score == 7 and s.massed_dispute_score == 0
    assert s.massed_support_band == (_r6(math.tanh(0.5 * 0.3 * 7)), _r6(math.tanh(0.5 * 1.0 * 7)))
    assert s.net_band == s.massed_support_band         # D=0 -> net == support
    assert s.net_robust is True


def test_balanced_evidence_is_not_net_robust():
    # Comparable support and dispute mass -> the adversarial corners straddle 0.
    r = aggregate_belief([
        _u(line_uri="a", independence_group="g1", evidence_role="proxy_support"),
        _u(line_uri="b", independence_group="g2", evidence_role="proxy_support"),
        _u(stance="disputes", line_uri="d", independence_group="g3",
           dispute_scope="mechanism", strength="moderate"),
    ])
    s = belief_scalar(r)
    assert s.net_band[0] < 0 < s.net_band[1]
    assert s.net_robust is False


def test_diagnostic_dispute_excluded_from_mass_but_counted():
    # model_criticism dispute is diagnostic: D=0, but contested + diagnostic_dispute_count=1
    r = aggregate_belief([
        _u(line_uri="yang", independence_group="g1"),
        _u(stance="disputes", line_uri="simeonov", independence_group="g2",
           evidence_role="model_criticism", dispute_scope="generalization"),
    ])
    s = belief_scalar(r)
    assert s.massed_dispute_score == 0
    assert s.diagnostic_dispute_count == 1
    assert s.contested is True
    assert isinstance(s, BeliefScalar)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_belief_scalar.py -q`
Expected: FAIL with `ModuleNotFoundError: ...belief_scalar`.

- [ ] **Step 3: Write minimal implementation** — create `belief_scalar.py`:

```python
"""Log-odds belief scalar (design §1/§2, Phase 2). Reads the reduced units that
aggregate_belief already produced; never re-derives independence."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .belief import BeliefResult, EvidenceUnit, is_proxy_gated
from .belief_weights import (
    DELTA_ENVELOPE, PROXY_STEP_PENALTY, role_steps, strength_steps, type_steps,
)


def unit_score(u: EvidenceUnit) -> int:
    s = type_steps(u.evidence_type) + role_steps(u.evidence_role) + strength_steps(u.strength)
    if is_proxy_gated(u):
        s = max(0, s - PROXY_STEP_PENALTY)
    return s


@dataclass(frozen=True)
class BeliefScalar:
    massed_support_score: int
    massed_dispute_score: int
    massed_support_band: tuple[float, float]
    massed_dispute_band: tuple[float, float]
    net_band: tuple[float, float]
    net_robust: bool
    contested: bool
    diagnostic_dispute_count: int


def _t(x: float) -> float:
    return round(math.tanh(0.5 * x), 6)


def belief_scalar(result: BeliefResult) -> BeliefScalar:
    d_lo, d_hi = DELTA_ENVELOPE
    s_score = sum(unit_score(u) for u in result.support_units)
    d_score = sum(unit_score(u) for u in result.dispute_units)
    net_lo = _t(d_lo * s_score - d_hi * d_score)   # support down, dispute up
    net_hi = _t(d_hi * s_score - d_lo * d_score)   # support up, dispute down
    net_robust = (net_lo > 0 and net_hi > 0) or (net_lo < 0 and net_hi < 0)
    diag_disputes = sum(1 for u in result.diagnostics if u.stance == "disputes")
    return BeliefScalar(
        massed_support_score=s_score,
        massed_dispute_score=d_score,
        massed_support_band=(_t(d_lo * s_score), _t(d_hi * s_score)),
        massed_dispute_band=(_t(d_lo * d_score), _t(d_hi * d_score)),
        net_band=(net_lo, net_hi),
        net_robust=net_robust,
        contested=result.contested,
        diagnostic_dispute_count=diag_disputes,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_belief_scalar.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_scalar.py science/tests/test_belief_scalar.py
git commit -m "feat(belief): log-odds scalar with adversarial net band"
```

---

### Task 3: Opt-in detection (`active_decision_sections` + `belief_scalar_enabled`)

**Files:**
- Modify: `science/src/science_tool/curate/agents_md.py`
- Modify: `science/src/science_tool/graph/belief_scalar.py`
- Test: `science/tests/test_belief_scalar.py`, `science/tests/test_agents_md_decisions.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_agents_md_decisions.py`:

```python
from pathlib import Path

from science_tool.curate.agents_md import active_decision_sections, parse_active_decision_ids

_DOC = """# Decisions

## D-001: Live one
- **Status:** active
- **Decision:** x

## D-002: Dead one
- **Status:** superseded
- **Decision:** y
"""


def test_active_decision_sections_returns_only_active(tmp_path: Path):
    p = tmp_path / "decisions.md"
    p.write_text(_DOC, encoding="utf-8")
    sections = active_decision_sections(p)
    assert [sid for sid, _ in sections] == ["D-001"]
    assert "Live one" in sections[0][1]
    # parse_active_decision_ids still works (refactored onto the same helper)
    assert parse_active_decision_ids(p) == ["D-001"]


def test_active_decision_sections_missing_file(tmp_path: Path):
    assert active_decision_sections(tmp_path / "nope.md") == []
```

Append to `science/tests/test_belief_scalar.py`:

```python
def _decisions(root, body):
    (root / "core").mkdir(parents=True, exist_ok=True)
    (root / "core" / "decisions.md").write_text(body, encoding="utf-8")


def test_belief_scalar_enabled_true_when_active_flag(tmp_path):
    from science_tool.graph.belief_scalar import belief_scalar_enabled
    _decisions(tmp_path, "# Decisions\n\n## D-014: Enable scalar\n"
                         "- **Status:** active\n- **Feature flag:** belief-scalar\n")
    assert belief_scalar_enabled(tmp_path) is True


def test_belief_scalar_enabled_false_when_superseded(tmp_path):
    from science_tool.graph.belief_scalar import belief_scalar_enabled
    _decisions(tmp_path, "# Decisions\n\n## D-014: Enable scalar\n"
                         "- **Status:** superseded\n- **Feature flag:** belief-scalar\n")
    assert belief_scalar_enabled(tmp_path) is False


def test_belief_scalar_enabled_false_when_no_flag(tmp_path):
    from science_tool.graph.belief_scalar import belief_scalar_enabled
    _decisions(tmp_path, "# Decisions\n\n## D-001: Other\n- **Status:** active\n- **Decision:** x\n")
    assert belief_scalar_enabled(tmp_path) is False
    assert belief_scalar_enabled(tmp_path / "no-project") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_agents_md_decisions.py tests/test_belief_scalar.py -q`
Expected: FAIL (`active_decision_sections` / `belief_scalar_enabled` undefined).

- [ ] **Step 3: Write minimal implementation**

In `curate/agents_md.py`, add `active_decision_sections` and refactor `parse_active_decision_ids` to use it (DRY — replace the existing function body):

```python
def active_decision_sections(decisions_md: Path) -> list[tuple[str, str]]:
    """(decision_id, section_body) for sections whose Status line is exactly `active`."""
    if not decisions_md.is_file():
        return []
    text = decisions_md.read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for decision_id, body in _split_decision_sections(text):
        match = _STATUS_LINE.search(body)
        if match is not None and match.group(1).strip().lower() == "active":
            out.append((decision_id, body))
    return out


def parse_active_decision_ids(decisions_md: Path) -> list[str]:
    """Return the IDs of decisions whose Status line is exactly `active`."""
    return [decision_id for decision_id, _ in active_decision_sections(decisions_md)]
```

In `graph/belief_scalar.py`, add at the top (imports) and a new function:

```python
import re
from pathlib import Path

from science_tool.curate.agents_md import active_decision_sections

_FEATURE_FLAG_BELIEF_SCALAR = re.compile(
    r"^-\s+\*\*Feature flag:\*\*\s*belief-scalar\s*$", re.MULTILINE
)


def belief_scalar_enabled(project_root: Path) -> bool:
    """True iff core/decisions.md has an ACTIVE decision carrying the belief-scalar flag."""
    decisions = project_root / "core" / "decisions.md"
    return any(
        _FEATURE_FLAG_BELIEF_SCALAR.search(body)
        for _id, body in active_decision_sections(decisions)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_agents_md_decisions.py tests/test_belief_scalar.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/curate/agents_md.py science/src/science_tool/graph/belief_scalar.py science/tests/test_agents_md_decisions.py science/tests/test_belief_scalar.py
git commit -m "feat(belief): belief-scalar opt-in via active core/decisions.md feature flag"
```

---

### Task 4: Display contract + attention wiring

**Files:**
- Modify: `science/src/science_tool/graph/belief_scalar.py` (add `format_belief_weight`)
- Modify: `science/src/science_tool/graph/attention.py`
- Test: `science/tests/test_belief_scalar.py`, `science/tests/test_attention_sampling.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_belief_scalar.py`:

```python
def test_format_belief_weight_suppresses_net_for_fragile():
    from science_tool.graph.belief_scalar import belief_scalar, format_belief_weight
    r = aggregate_belief([_u(line_uri="a", independence_group="g1")])   # single -> fragile
    bw = format_belief_weight(r, belief_scalar(r))
    assert bw["net"] is None
    assert "single-unit ceiling applies" in bw["notes"]
    assert bw["massed_support"] == list(belief_scalar(r).massed_support_band)


def test_format_belief_weight_shows_net_when_robust_and_supported():
    from science_tool.graph.belief_scalar import belief_scalar, format_belief_weight
    r = aggregate_belief([_u(line_uri="a", independence_group="g1"),
                          _u(line_uri="b", independence_group="g2")])   # well_supported
    s = belief_scalar(r)
    bw = format_belief_weight(r, s)
    assert bw["net"] == list(s.net_band)
    assert bw["notes"] == []


def test_format_belief_weight_diagnostic_caveat():
    from science_tool.graph.belief_scalar import belief_scalar, format_belief_weight
    r = aggregate_belief([
        _u(line_uri="a", independence_group="g1"),
        _u(line_uri="b", independence_group="g2"),
        _u(stance="disputes", line_uri="c", independence_group="g3",
           evidence_role="model_criticism", dispute_scope="generalization"),
    ])
    bw = format_belief_weight(r, belief_scalar(r))
    assert "contested (diagnostic)" in bw["notes"]
```

Append to the existing `tests/test_attention_sampling.py`:

```python
def test_format_attention_candidate_belief_weight_defaults_none():
    import inspect

    from science_tool.graph.attention import format_attention_candidate

    sig = inspect.signature(format_attention_candidate)
    assert "belief_weight" in sig.parameters
    assert sig.parameters["belief_weight"].default is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/test_belief_scalar.py tests/test_attention_sampling.py -q`
Expected: FAIL (`format_belief_weight` undefined; `belief_weight` not a parameter).

- [ ] **Step 3: Write minimal implementation**

Add to `belief_scalar.py` (import `BeliefMagnitude` from `.belief`):

```python
from typing import Any

from .belief import BeliefMagnitude  # add to existing belief import line


def format_belief_weight(result: BeliefResult, scalar: BeliefScalar) -> dict[str, Any]:
    """Display contract (design §3): net annotates, never overrides, the ordinal headline."""
    ceiling_binds = result.magnitude == BeliefMagnitude.FRAGILE or result.capped_by_refutation
    notes: list[str] = []
    if result.magnitude == BeliefMagnitude.FRAGILE:
        notes.append("single-unit ceiling applies")
    if result.capped_by_refutation:
        notes.append("refutation cap applies")
    if not scalar.net_robust:
        notes.append("net not robust")
    if scalar.contested and scalar.massed_dispute_score == 0:
        notes.append("contested (diagnostic)")
    show_net = scalar.net_robust and not ceiling_binds
    return {
        "massed_support": list(scalar.massed_support_band),
        "massed_dispute": list(scalar.massed_dispute_band),
        "net": list(scalar.net_band) if show_net else None,
        "contested": scalar.contested,
        "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
        "notes": notes,
    }
```

In `attention.py`: (a) change `format_attention_candidate` signature and the `belief_weight` line; (b) compute the scalar in `query_attention_sample` when enabled.

Add imports near the top of `attention.py`:

```python
from science_tool.graph.belief import aggregate_belief, collect_evidence_units
from science_tool.graph.belief_scalar import belief_scalar, belief_scalar_enabled, format_belief_weight
from science_tool.graph.io import project_root_from_graph_path
from science_tool.graph.store import _evidence_targets_for_uri, _graph_uri
```

Change the function signature and the placeholder line:

```python
def format_attention_candidate(
    candidate: AttentionCandidate, belief_weight: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Format a candidate for CLI table / JSON output."""
    components = candidate.components
    return {
        "id": candidate.entity_id,
        "kind": candidate.kind,
        "label": candidate.label,
        "freshness_state": candidate.freshness_state,
        "attention_weight": f"{candidate.weight:.4f}",
        "belief_weight": belief_weight,          # was: None
        "influence_weight": None,
        # ... rest unchanged ...
```

In `query_attention_sample`, after `sample = ...` and before the return, replace the return:

```python
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    enabled = belief_scalar_enabled(project_root_from_graph_path(graph_path))

    def _belief_weight(candidate: AttentionCandidate) -> dict[str, Any] | None:
        if not enabled:
            return None
        units = collect_evidence_units(
            knowledge, provenance, _evidence_targets_for_uri(knowledge, URIRef(candidate.uri))
        )
        result = aggregate_belief(units)
        return format_belief_weight(result, belief_scalar(result))

    return [format_attention_candidate(c, belief_weight=_belief_weight(c)) for c in sample]
```

(Use `candidate.uri` — the full graph URI — not `entity_id`, which is the canonical CURIE.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_belief_scalar.py tests/test_attention_sampling.py -q`
Expected: PASS. The existing attention tests use `tmp_path/knowledge/graph.trig`, so `project_root_from_graph_path` returns `tmp_path` (pure path arithmetic, never raises) and `belief_scalar_enabled` returns False (no `core/decisions.md`) → `belief_weight` stays `None`, preserving current output.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_scalar.py science/src/science_tool/graph/attention.py science/tests/test_belief_scalar.py science/tests/test_attention_sampling.py
git commit -m "feat(belief): display contract + attention belief_weight (opt-in)"
```

---

### Task 5: Snapshots (`belief_snapshot.py`)

**Files:**
- Create: `science/src/science_tool/graph/belief_snapshot.py`
- Test: `science/tests/test_belief_snapshot.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_belief_snapshot.py`:

```python
from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef
from rdflib.namespace import PROV

from science_tool.graph.belief_snapshot import (
    append_snapshots, read_snapshots, snapshot_records,
)
from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import _graph_uri

PROP = URIRef("https://example.org/prop/p1")
LINE = URIRef("https://example.org/el/yang")
EVIDENCE_LINE_CLASS = SCI_NS.EvidenceLine


def _graphs():
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    k.add((PROP, RDF.type, SCI_NS.Proposition))
    k.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    k.add((LINE, CITO_NS.supports, PROP))
    p.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((LINE, SCI_NS.evidenceIndependence, Literal("independent")))
    p.add((LINE, SCI_NS.independenceGroup, Literal("g1")))
    p.add((LINE, SCI_NS.evidenceRole, Literal("direct_test")))
    p.add((LINE, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    return k, p


def test_snapshot_records_basic_shape():
    k, p = _graphs()
    rows = snapshot_records(k, p, scalar_enabled=False, as_of="2026-05-24")
    assert len(rows) == 1
    row = rows[0]
    assert row["claim"] == str(PROP)
    assert row["belief_state"] == "fragile"
    assert row["scalar_enabled"] is False
    assert row["net_band"] is None                 # scalar fields null when disabled
    assert row["massed_support_score"] is None
    assert row["input_hashes"] and all(h.startswith("sha256:") for h in row["input_hashes"])
    assert row["config_version"] == "belief-logodds-v1"


def test_snapshot_records_scalar_enabled_fills_scores():
    k, p = _graphs()
    row = snapshot_records(k, p, scalar_enabled=True, as_of="2026-05-24")[0]
    assert row["scalar_enabled"] is True
    assert row["massed_support_score"] == 7
    assert row["net_band"] is not None


def test_append_is_idempotent_then_grows_on_change(tmp_path: Path):
    k, p = _graphs()
    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    rows = snapshot_records(k, p, scalar_enabled=False, as_of="2026-05-24")
    assert append_snapshots(out, rows) == 1
    assert append_snapshots(out, rows) == 0          # idempotent no-op
    # Same day, opt-in toggled -> distinct scalar_enabled key -> new row
    rows_on = snapshot_records(k, p, scalar_enabled=True, as_of="2026-05-24")
    assert append_snapshots(out, rows_on) == 1
    stored = read_snapshots(out)
    assert len(stored) == 2
    assert {r["scalar_enabled"] for r in stored} == {True, False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_belief_snapshot.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation** — create `belief_snapshot.py`:

```python
"""Append-only belief snapshots (design §4, Phase 2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rdflib import RDF, URIRef

from .belief import aggregate_belief, collect_evidence_units
from .belief_scalar import belief_scalar, belief_scalar_enabled
from .belief_weights import CONFIG_VERSION
from .io import SCI_NS
from .store import _evidence_targets_for_uri, _graph_uri, _load_dataset
from .io import project_root_from_graph_path


def _line_content_hash(knowledge, provenance, line: URIRef) -> str:
    parts: list[str] = []
    for graph in (knowledge, provenance):
        for _, predicate, obj in graph.triples((line, None, None)):
            parts.append(f"{predicate}\t{obj}")
    digest = hashlib.sha256("\n".join(sorted(parts)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _claim_uris(knowledge):
    seen: set[URIRef] = set()
    for ctype in (SCI_NS.Proposition, SCI_NS.Hypothesis):
        for subj, _, _ in knowledge.triples((None, RDF.type, ctype)):
            if isinstance(subj, URIRef) and subj not in seen:
                seen.add(subj)
                yield subj


def snapshot_records(knowledge, provenance, *, scalar_enabled: bool, as_of: str) -> list[dict]:
    rows: list[dict] = []
    for claim in _claim_uris(knowledge):
        units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, claim))
        if not units:
            continue                                  # nothing to reproduce; skip
        result = aggregate_belief(units)
        scalar = belief_scalar(result)
        input_hashes = sorted({_line_content_hash(knowledge, provenance, URIRef(u.line_uri)) for u in units})
        rows.append({
            "as_of": as_of,
            "claim": str(claim),
            "belief_state": result.magnitude.value,
            "contested": result.contested,
            "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
            "scalar_enabled": scalar_enabled,
            "massed_support_score": scalar.massed_support_score if scalar_enabled else None,
            "massed_dispute_score": scalar.massed_dispute_score if scalar_enabled else None,
            "massed_support_band": list(scalar.massed_support_band) if scalar_enabled else None,
            "massed_dispute_band": list(scalar.massed_dispute_band) if scalar_enabled else None,
            "net_band": list(scalar.net_band) if scalar_enabled else None,
            "net_robust": scalar.net_robust if scalar_enabled else None,
            "input_hashes": input_hashes,
            "config_version": CONFIG_VERSION,
        })
    rows.sort(key=lambda r: r["claim"])
    return rows


def make_snapshots(graph_path: Path, *, as_of: str) -> list[dict]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    enabled = belief_scalar_enabled(project_root_from_graph_path(graph_path))
    return snapshot_records(knowledge, provenance, scalar_enabled=enabled, as_of=as_of)


def _key(row: dict):
    return (row["as_of"], row["claim"], tuple(row["input_hashes"]),
            row["config_version"], row["scalar_enabled"])


def _dump(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_snapshots(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_snapshots(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = {_key(r) for r in read_snapshots(path)}
    added = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            if _key(row) in seen:
                continue
            handle.write(_dump(row) + "\n")
            seen.add(_key(row))
            added += 1
    return added
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_belief_snapshot.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_snapshot.py science/tests/test_belief_snapshot.py
git commit -m "feat(belief): append-only JSONL snapshots with idempotent per-key append"
```

---

### Task 6: `science belief snapshot` CLI

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_belief_cli.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_belief_cli.py`:

```python
from pathlib import Path

from click.testing import CliRunner

from science_tool import cli
from science_tool.graph import belief_snapshot


def test_belief_snapshot_writes_jsonl(tmp_path: Path, monkeypatch):
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n", encoding="utf-8")
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "graph.trig").write_text("", encoding="utf-8")

    canned = [{
        "as_of": "2026-05-24", "claim": "prop:p1", "belief_state": "fragile",
        "contested": False, "diagnostic_dispute_count": 0, "scalar_enabled": False,
        "massed_support_score": None, "massed_dispute_score": None,
        "massed_support_band": None, "massed_dispute_band": None,
        "net_band": None, "net_robust": None,
        "input_hashes": ["sha256:abc"], "config_version": "belief-logodds-v1",
    }]
    monkeypatch.setattr(belief_snapshot, "make_snapshots", lambda *a, **k: canned)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["belief", "snapshot", "--path", str(tmp_path / "knowledge" / "graph.trig"),
         "--as-of", "2026-05-24"],
    )
    assert result.exit_code == 0, result.output
    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    assert out.is_file()
    assert "prop:p1" in out.read_text(encoding="utf-8")
    assert "1 new rows" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_belief_cli.py -q`
Expected: FAIL (`No such command 'belief'`).

- [ ] **Step 3: Write minimal implementation**

In `cli.py`, add `from .graph import belief_snapshot` near the other graph imports, and add a new group + command (place after the `graph` command block):

```python
@main.group("belief")
def belief_group() -> None:
    """Derived belief scalar and append-only snapshots."""


@belief_group.command("snapshot")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True,
    type=click.Path(path_type=Path),
)
@click.option("--as-of", "as_of", default=None, help="Snapshot date YYYY-MM-DD (default: today).")
def belief_snapshot_cmd(graph_path: Path, as_of: str | None) -> None:
    """Append per-claim belief snapshots to knowledge/belief-snapshots.jsonl."""
    from datetime import date

    from .graph.io import project_root_from_graph_path

    as_of_value = as_of or date.today().isoformat()
    records = belief_snapshot.make_snapshots(graph_path, as_of=as_of_value)
    out_path = project_root_from_graph_path(graph_path) / "knowledge" / "belief-snapshots.jsonl"
    added = belief_snapshot.append_snapshots(out_path, records)
    click.echo(f"belief snapshot {as_of_value}: {len(records)} claims, {added} new rows -> {out_path}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_belief_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_belief_cli.py
git commit -m "feat(belief): science belief snapshot CLI command"
```

---

### Task 7: Unify `query_uncertainty` contested onto `aggregate_belief`

**Files:**
- Modify: `science/src/science_tool/graph/store/summary.py` (`query_uncertainty`, ~lines 858–867)
- Test: `science/tests/test_query_uncertainty_contested.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_query_uncertainty_contested.py`:

```python
from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.graph.io import CITO_NS, SCHEMA_NS, SCI_NS
from science_tool.graph.store import _graph_uri, query_uncertainty

PROP = URIRef("https://example.org/prop/p1")
SUP = URIRef("https://example.org/el/sup")
DIS = URIRef("https://example.org/el/circular-dispute")


def _write_graph(tmp_path: Path) -> Path:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    k.add((PROP, RDF.type, SCI_NS.Proposition))
    k.add((PROP, SCHEMA_NS.text, Literal("claim text")))
    # one support line
    k.add((SUP, RDF.type, SCI_NS.EvidenceLine))
    k.add((SUP, CITO_NS.supports, PROP))
    p.add((SUP, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((SUP, SCI_NS.evidenceIndependence, Literal("independent")))
    p.add((SUP, SCI_NS.independenceGroup, Literal("g1")))
    p.add((SUP, SCI_NS.evidenceRole, Literal("direct_test")))
    p.add((SUP, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    # one CIRCULAR dispute line: count-based logic would mark contested; belief excludes it
    k.add((DIS, RDF.type, SCI_NS.EvidenceLine))
    k.add((DIS, CITO_NS.disputes, PROP))
    p.add((DIS, SCI_NS.evidenceIndependence, Literal("circular")))
    p.add((DIS, SCI_NS.independenceGroup, Literal("g1")))
    out = tmp_path / "graph.trig"
    ds.serialize(destination=str(out), format="trig")
    return out


def test_contested_signal_is_belief_derived_not_count_based(tmp_path: Path):
    graph_path = _write_graph(tmp_path)
    rows = query_uncertainty(graph_path=graph_path, top=10)
    row = next(r for r in rows if r["entity"] == str(PROP))
    # A circular dispute must NOT make the claim contested (belief excludes circular lines),
    # even though support_count>0 and dispute_count>0 under the old count-based rule.
    assert "contested" not in row["signals"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_query_uncertainty_contested.py -q`
Expected: FAIL — old code appends "contested" from `support_count>0 and dispute_count>0`.

- [ ] **Step 3: Write minimal implementation**

In `store/summary.py::query_uncertainty`, after `evidence_summary = _collect_evidence_signals(...)` and the three count reads, compute belief and use it for the contested signal. Replace:

```python
            if support_count > 0 and dispute_count > 0:
                signals.append("contested")
                risk_score += 3.0
```

with:

```python
            belief = aggregate_belief(
                collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, uri))
            )
            if belief.contested:
                signals.append("contested")
                risk_score += 3.0
```

No new imports needed: `aggregate_belief` and `collect_evidence_units` are imported at `summary.py:11`, and `_evidence_targets_for_uri` at `summary.py:28` (from `.evidence_signals`). `knowledge`, `provenance`, and the loop variable `uri` are already in scope at this point in `query_uncertainty`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_query_uncertainty_contested.py -q`
Then regression: `cd science && uv run pytest tests/ -k uncertainty -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/store/summary.py science/tests/test_query_uncertainty_contested.py
git commit -m "fix(belief): query_uncertainty contested derives from aggregate_belief"
```

---

### Task 8: QA check `evidence.unscored-line`

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py`
- Test: `science/tests/validate/test_checks_evidence_lines.py`

- [ ] **Step 1: Write the failing test** — append to `tests/validate/test_checks_evidence_lines.py` (reuses the file's `_ctx` / `_write` helpers):

```python
def test_unscored_line_warns_for_unrecognized_type(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: made_up\nevidence_role: direct_test\nstrength: strong\n---\n")
    results = list(check_evidence_unscored_line(_ctx(tmp_path)))
    assert len(results) == 1 and results[0].severity is Severity.WARN


def test_unscored_line_clean_for_fully_specified(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: empirical_data\nevidence_role: direct_test\nstrength: strong\n---\n")
    assert list(check_evidence_unscored_line(_ctx(tmp_path))) == []


def test_unscored_line_skips_diagnostic_roles(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    # model_criticism is recognized-but-non-massed: outside EVIDENCE_ROLE_RANK, never flagged.
    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: disputes\ntarget: proposition:p1\nevidence_role: model_criticism\n---\n")
    assert list(check_evidence_unscored_line(_ctx(tmp_path))) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/validate/test_checks_evidence_lines.py -k unscored -q`
Expected: FAIL (`check_evidence_unscored_line` undefined).

- [ ] **Step 3: Write minimal implementation** — add to `validate/checks/evidence_lines.py` (extend the `belief_weights` import to include the rank tables + `normalize_evidence_type`, and `DIAGNOSTIC_ROLES`):

```python
from science_tool.graph.belief_weights import (
    DIAGNOSTIC_ROLES, EVIDENCE_ROLE_RANK, EVIDENCE_TYPE_RANK, STRENGTH_RANK,
    normalize_evidence_type,
)


@Check(section="evidence lines", order=28)
def check_evidence_unscored_line(ctx: ValidateContext) -> Iterator[Result]:
    """A massable (non-diagnostic) support/dispute line that cannot be scored — surfaces an
    authored-metadata gap. Diagnostic roles (model_criticism/negative_control) are
    recognized-but-non-massed and never flagged."""
    for path, fm in _ev_lines(ctx):
        stance = fm.get("stance")
        if stance not in ("supports", "disputes"):
            continue
        role = fm.get("evidence_role") or ""
        if role in DIAGNOSTIC_ROLES:
            continue
        missing: list[str] = []
        if normalize_evidence_type(fm.get("evidence_type")) not in EVIDENCE_TYPE_RANK:
            missing.append("evidence_type")
        if role not in EVIDENCE_ROLE_RANK:
            missing.append("evidence_role")
        if (fm.get("strength") or "") not in STRENGTH_RANK:
            missing.append("strength")
        if missing:
            yield Result(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=f"evidence-line cannot be scored (missing/unrecognized: {', '.join(missing)})",
                rule="evidence.unscored-line",
                task=None,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/validate/test_checks_evidence_lines.py -k unscored -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/evidence_lines.py science/tests/validate/test_checks_evidence_lines.py
git commit -m "feat(validate): evidence.unscored-line check (massable lines only)"
```

---

### Task 9: QA check `belief.fragile-single-line` (#7 leave-one-out)

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py`
- Test: `science/tests/validate/test_checks_belief_sensitivity.py`

- [ ] **Step 1: Write the failing test** — create `tests/validate/test_checks_belief_sensitivity.py`:

```python
from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import _graph_uri
from science_tool.validate import Severity, ValidateContext


def _manifest(root: Path) -> None:
    root.joinpath("science.yaml").write_text(
        "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\n"
        "status: active\nsummary: d\nprofile: research\nlayout_version: 1\n",
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _line(p, k, uri, target, **meta):
    k.add((uri, RDF.type, SCI_NS.EvidenceLine))
    k.add((uri, CITO_NS.supports if meta.get("stance", "supports") == "supports" else CITO_NS.disputes, target))
    for pred, val in (
        (SCI_NS.evidenceStrength, meta.get("strength", "strong")),
        (SCI_NS.evidenceIndependence, meta.get("independence", "independent")),
        (SCI_NS.independenceGroup, meta["group"]),
        (SCI_NS.evidenceRole, meta.get("role", "direct_test")),
        (SCI_NS.evidenceType, meta.get("etype", "empirical_data_evidence")),
    ):
        p.add((uri, pred, Literal(val)))


def _write_two_support_graph(root: Path) -> None:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    prop = URIRef("https://example.org/prop/p1")
    k.add((prop, RDF.type, SCI_NS.Proposition))
    # exactly two independent direct-test supports -> well_supported; drop one -> fragile (flips)
    _line(p, k, URIRef("https://example.org/el/a"), prop, group="g1")
    _line(p, k, URIRef("https://example.org/el/b"), prop, group="g2")
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(root / "knowledge" / "graph.trig"), format="trig")


def _write_support_plus_diagnostic_graph(root: Path) -> None:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    prop = URIRef("https://example.org/prop/p2")
    k.add((prop, RDF.type, SCI_NS.Proposition))
    _line(p, k, URIRef("https://example.org/el/sup"), prop, group="g1")
    _line(p, k, URIRef("https://example.org/el/crit"), prop, group="g2",
          stance="disputes", role="model_criticism")
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(root / "knowledge" / "graph.trig"), format="trig")


def _write_one_support_plus_excluded_circular_graph(root: Path) -> None:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    prop = URIRef("https://example.org/prop/p3")
    k.add((prop, RDF.type, SCI_NS.Proposition))
    _line(p, k, URIRef("https://example.org/el/sup"), prop, group="g1")
    _line(p, k, URIRef("https://example.org/el/circular"), prop, group="g2",
          stance="disputes", independence="circular")
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(root / "knowledge" / "graph.trig"), format="trig")


def test_fragile_single_line_flags_when_drop_flips(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_belief_fragile_single_line
    _write_two_support_graph(tmp_path)
    results = list(check_belief_fragile_single_line(_ctx(tmp_path)))
    assert any(r.severity is Severity.WARN for r in results)


def test_fragile_single_line_flags_diagnostic_only_contestation(tmp_path: Path):
    # h012 shape: one support + one model_criticism dispute. Dropping the diagnostic flips
    # contested True->False; dropping the support flips magnitude. Either way it is fragile.
    from science_tool.validate.checks.evidence_lines import check_belief_fragile_single_line
    _write_support_plus_diagnostic_graph(tmp_path)
    results = list(check_belief_fragile_single_line(_ctx(tmp_path)))
    assert any(r.severity is Severity.WARN for r in results)


def test_fragile_single_line_skips_single_kept_unit_plus_excluded_circular(tmp_path: Path):
    # Raw units has length 2, but only one line is effectively kept. Leave-one-out operates on
    # kept units, so this should not warn.
    from science_tool.validate.checks.evidence_lines import check_belief_fragile_single_line
    _write_one_support_plus_excluded_circular_graph(tmp_path)
    assert list(check_belief_fragile_single_line(_ctx(tmp_path))) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/validate/test_checks_belief_sensitivity.py -q`
Expected: FAIL (`check_belief_fragile_single_line` undefined).

- [ ] **Step 3: Write minimal implementation** — add to `validate/checks/evidence_lines.py` (reuses `_load_belief_graphs`, `_claims`, `collect_evidence_units`, `aggregate_belief`, `_evidence_targets_for_uri`):

```python
@Check(section="evidence lines", order=29)
def check_belief_fragile_single_line(ctx: ValidateContext) -> Iterator[Result]:
    """#7 leave-one-out: if dropping any single kept independent unit flips the ordinal
    belief_state (magnitude or contested), the claim's conclusion is not robust."""
    knowledge, provenance = _load_belief_graphs(ctx)
    if knowledge is None:
        return
    for claim in _claims(knowledge):
        units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, claim))
        base = aggregate_belief(units)
        # Include diagnostics: a claim can be contested solely via a diagnostic dispute
        # (e.g. h012/Simeonov), and dropping that line flips contested — exactly the fragility
        # this check exists to surface.
        kept_uris = {u.line_uri for u in (*base.support_units, *base.dispute_units, *base.diagnostics)}
        if len(kept_uris) < 2:
            continue
        for drop in kept_uris:
            reduced = aggregate_belief([u for u in units if u.line_uri != drop])
            if reduced.magnitude != base.magnitude or reduced.contested != base.contested:
                yield Result(
                    severity=Severity.WARN,
                    path=None,
                    line=None,
                    message=(
                        f"{claim}: belief_state flips ({base.magnitude.value} -> "
                        f"{reduced.magnitude.value}) when dropping a single line ({drop})"
                    ),
                    rule="belief.fragile-single-line",
                    task=None,
                )
                break
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/validate/test_checks_belief_sensitivity.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/evidence_lines.py science/tests/validate/test_checks_belief_sensitivity.py
git commit -m "feat(validate): belief.fragile-single-line leave-one-out check (#7)"
```

---

### Task 10: QA check `belief.nonreproducible` (#8 golden)

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py`
- Test: `science/tests/validate/test_checks_belief_sensitivity.py`

- [ ] **Step 1: Write the failing test** — append to `tests/validate/test_checks_belief_sensitivity.py`:

```python
def test_nonreproducible_errors_when_stored_belief_mismatches(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    # Snapshot the current (correct) belief, then corrupt the stored belief_state.
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    corrupted = rows[0] | {"belief_state": "speculative"}      # same input_hashes, wrong output
    snap.write_text(json.dumps(corrupted) + "\n", encoding="utf-8")

    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_silent_when_inputs_changed(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Different input_hashes -> legitimate change, not flagged, even if belief differs.
    stale = rows[0] | {"belief_state": "speculative", "input_hashes": ["sha256:stale"]}
    snap.write_text(json.dumps(stale) + "\n", encoding="utf-8")
    assert list(check_belief_nonreproducible(ctx)) == []


def test_nonreproducible_errors_on_corrupted_scalar_band(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    # Enable the scalar so bands are recorded and compared (#3: scalar fields are golden too).
    (tmp_path / "core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "core" / "decisions.md").write_text(
        "# Decisions\n\n## D-1: on\n- **Status:** active\n- **Feature flag:** belief-scalar\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Same belief_state/contested/inputs, corrupted band -> must still ERROR when scalar enabled.
    corrupted = rows[0] | {"net_band": [0.0, 0.0]}
    snap.write_text(json.dumps(corrupted) + "\n", encoding="utf-8")
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_errors_on_corrupted_diagnostic_count(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_support_plus_diagnostic_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    corrupted = rows[0] | {"diagnostic_dispute_count": 0}
    snap.write_text(json.dumps(corrupted) + "\n", encoding="utf-8")
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_uses_latest_matching_row_not_latest_per_claim(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    matching_corrupted = rows[0] | {"belief_state": "speculative"}
    stale_later = rows[0] | {"input_hashes": ["sha256:stale"], "belief_state": "speculative"}
    # Old latest-per-claim logic would inspect only the stale later row and skip. Correct
    # latest-matching logic still finds the earlier row with current inputs and errors.
    snap.write_text(
        json.dumps(matching_corrupted) + "\n" + json.dumps(stale_later) + "\n",
        encoding="utf-8",
    )
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/validate/test_checks_belief_sensitivity.py -k nonreproducible -q`
Expected: FAIL (`check_belief_nonreproducible` undefined).

- [ ] **Step 3: Write minimal implementation** — add to `validate/checks/evidence_lines.py`. Reuse the snapshot machinery so the recompute and the stored rows share one code path (DRY):

```python
_GOLDEN_SCALAR_FIELDS = (
    "massed_support_score", "massed_dispute_score",
    "massed_support_band", "massed_dispute_band", "net_band", "net_robust",
)


@Check(section="evidence lines", order=30)
def check_belief_nonreproducible(ctx: ValidateContext) -> Iterator[Result]:
    """#8 golden: equal inputs (input_hashes + config_version + scalar_enabled) must reproduce
    the stored belief. Differing inputs are legitimate change, not flagged."""
    from science_tool.graph.belief_snapshot import make_snapshots, read_snapshots

    graph_file = ctx.project_root / "knowledge" / "graph.trig"
    snap_file = ctx.project_root / "knowledge" / "belief-snapshots.jsonl"
    if not graph_file.exists() or not snap_file.exists():
        return
    stored = read_snapshots(snap_file)
    for now in make_snapshots(graph_file, as_of="recompute"):
        # All stored rows for this claim whose input set matches the current one, then the
        # LATEST among them (file order == append order). Latest-matching, not latest-per-claim.
        matches = [
            r for r in stored
            if r["claim"] == now["claim"]
            and sorted(r["input_hashes"]) == sorted(now["input_hashes"])
            and r["config_version"] == now["config_version"]
            and r["scalar_enabled"] == now["scalar_enabled"]
        ]
        if not matches:
            continue
        prior = matches[-1]
        diffs = [
            f for f in ("belief_state", "contested", "diagnostic_dispute_count")
            if prior.get(f) != now.get(f)
        ]
        if now["scalar_enabled"]:
            diffs += [f for f in _GOLDEN_SCALAR_FIELDS if prior.get(f) != now.get(f)]
        if diffs:
            yield Result(
                severity=Severity.ERROR,
                path=snap_file,
                line=None,
                message=(
                    f"{now['claim']}: belief not reproducible from identical inputs "
                    f"(differing fields: {', '.join(diffs)})"
                ),
                rule="belief.nonreproducible",
                task=None,
            )
```

(Note: `make_snapshots(... as_of="recompute")` — `as_of` is irrelevant to the comparison, which keys on `input_hashes`/`config_version`/`scalar_enabled`. Band fields compare as JSON lists on both sides, so equal bands match exactly.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/validate/test_checks_belief_sensitivity.py -k nonreproducible -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/evidence_lines.py science/tests/validate/test_checks_belief_sensitivity.py
git commit -m "feat(validate): belief.nonreproducible golden check (#8)"
```

---

### Task 11: Full-suite verification + spec status bump

**Files:**
- Modify: `docs/plans/historical/2026-05-24-evidence-aggregation-phase2-design.md` (status line only)

- [ ] **Step 1: Run the full science suite**

Run: `cd science && uv run pytest -q`
Expected: PASS (no regressions; baseline was green before this branch).

- [ ] **Step 2: Run the model suite**

Run: `cd science/model && uv run pytest -q`
Expected: PASS (Phase 2 does not touch the model package; this confirms no incidental breakage).

- [ ] **Step 3: Confirm the new CLI is registered**

Run: `cd science && uv run science belief snapshot --help`
Expected: help text for the snapshot command (exit 0).

- [ ] **Step 4: Bump the design status**

In `docs/plans/historical/2026-05-24-evidence-aggregation-phase2-design.md`, change the status line to:
`**Status**: Implemented (2026-05-24)`

- [ ] **Step 5: Commit**

```bash
git add docs/plans/historical/2026-05-24-evidence-aggregation-phase2-design.md
git commit -m "docs(plans): mark Phase 2 design implemented"
```

---

## Notes for the final reviewer

- **Pilot (manual, out of this plan).** The cancer-evolution repo (`~/d/cancer/mechanisms/evolution`, a separate git repo) is where the design's pilot lives. After this branch lands, the human can add a `## D-NNN` decision there with `- **Feature flag:** belief-scalar`, run `science belief snapshot`, and confirm `science graph validate` stays clean and h012 shows `fragile (contested)` with the net hidden. Subagents must NOT touch that external repo.
- **Spec numeric note.** The rev-c design's h012 example shows `net_band ≈ [0.7818, 0.9982]` (`tanh(1.05)`, `tanh(3.5)`). Tests compute expected values via `math.tanh` rather than hardcoding, so they stay correct regardless of how many digits the prose carries.
