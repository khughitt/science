# Verdict Parse / Rollup MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a minimum-viable `science-tool verdict` sub-command
family that parses interpretation docs' `verdict:` frontmatter
blocks, validates rule-derived composites against body tokens,
resolves claim IDs through the project-local registry, and
aggregates verdicts across an entire project — enough to run
`science-tool verdict rollup --by-claim` on the mm30 corpus as the
acceptance harness.

**Architecture:** New `src/science_tool/verdict/` sub-package with a
small stack: `tokens.py` (5-token enum + body-verdict extractor),
`models.py` (dataclasses for `VerdictBlock`, `Claim`, `Context`,
`ClaimRegistry`), `parser.py` (markdown + YAML frontmatter
extraction, dataclass hydration, validation), `rules.py`
(aggregation rules: `and` / `or` / `majority` / `weighted-majority`
/ `bimodal` / `non-adjudicating` / `reframed`, plus a
`rule_disagrees_with_body` detector), `registry.py` (load
`<project>/specs/claim-registry.yaml`, build canonical ID + synonym
maps, resolve IDs), `rollup.py` (walk interpretation directories,
aggregate by `hypothesis` / `question` / `edge` / `claim` /
`all`), `cli.py` (click `verdict_group` with `parse` and `rollup`
subcommands). Wired into top-level `main` via
`main.add_command(verdict_group)`.

**Tech Stack:** Python ≥ 3.11, click ≥ 8.1 (not typer), pyyaml ≥ 6,
jsonschema ≥ 4 (already project deps), stdlib `dataclasses`,
rich ≥ 13 for CLI output, pytest ≥ 9.

**Acceptance harness:** this plan is considered complete when the
following all pass on the mm30 corpus (9 existing atomic-
decomposition docs + 37-claim `specs/claim-registry.yaml`):

- `science-tool verdict parse <file>` on each of mm30's 9
  atomic-decomposition docs returns the JSON shape from the spec's
  "Implementation contract for the parser" section, and emits
  `rule_disagrees_with_body: true` on exactly one doc: t163
  (`2026-04-12-t163-prolif-adjusted-tf-edges.md`).
- `science-tool verdict rollup --scope hypothesis` on mm30 prints a
  per-hypothesis polarity-distribution table matching the
  hand-emulated t245 conflict/coverage scan results.
- `science-tool verdict rollup --by-claim` on mm30 (with the
  registry present) aggregates evidence from multiple citing
  interpretations under each canonical claim ID.
- All unit tests pass under `uv run pytest -q`.

---

## File Structure

### New files (all under `~/d/science/science-tool/`)

| Path | Responsibility |
|------|---------------|
| `src/science_tool/verdict/__init__.py` | Sub-package marker; re-exports `VerdictBlock`, `Claim`, `parse_file`, `aggregate_composite`. |
| `src/science_tool/verdict/tokens.py` | `Token` enum (5 values), `parse_body_verdict` extracts the first `**Verdict:** [TOKEN]` line from markdown prose. |
| `src/science_tool/verdict/models.py` | Dataclasses: `Context`, `Claim`, `VerdictBlock`, `ClaimRegistryEntry`, `ClaimRegistry`, `ParseResult`. All JSON-serializable via `dataclasses.asdict`. |
| `src/science_tool/verdict/parser.py` | `parse_file(path) -> ParseResult`: extract `---\n...\n---` frontmatter + body, load `verdict:` YAML block, hydrate `VerdictBlock`, extract body composite token, run rule aggregation, emit `rule_disagrees_with_body` and `validation_warnings`. |
| `src/science_tool/verdict/rules.py` | `aggregate_composite(rule, claims, weights) -> Token` with seven rule branches; `rule_disagrees_with_body(rule_composite, body_composite) -> bool`. |
| `src/science_tool/verdict/registry.py` | `load_registry(path) -> ClaimRegistry`; `resolve(cid) -> canonical_id | None`; `has_registry(project_root) -> bool`. |
| `src/science_tool/verdict/rollup.py` | `walk_interpretations(root) -> Iterator[ParseResult]`; `group_by(results, scope, registry) -> dict[str, list[ParseResult]]`; emits per-group polarity tallies. |
| `src/science_tool/verdict/cli.py` | click `verdict_group` with `parse` and `rollup` subcommands; JSON + rich-table output modes. |
| `tests/test_verdict_tokens.py` | Unit tests for `Token` enum + body-verdict extractor. |
| `tests/test_verdict_models.py` | Round-trip serialization test for `VerdictBlock`. |
| `tests/test_verdict_parser.py` | Parser tests against fixture markdown files (includes a t163-like mismatch fixture). |
| `tests/test_verdict_rules.py` | Table-driven tests for each aggregation rule. |
| `tests/test_verdict_registry.py` | Registry load + synonym resolution tests. |
| `tests/test_verdict_rollup.py` | Rollup tests on a multi-file fixture project. |
| `tests/test_verdict_cli.py` | CLI-level invocation tests via `click.testing.CliRunner`. |
| `tests/fixtures/verdict/doc_and.md` | Fixture: `and` rule, two-claim doc, agreement. |
| `tests/fixtures/verdict/doc_majority_disagrees.md` | Fixture: `majority` rule, t163-style load-bearing-minority case (body `[~]`, rule `[-]`). |
| `tests/fixtures/verdict/doc_bimodal.md` | Fixture: `bimodal` rule with 4 atomic claims. |
| `tests/fixtures/verdict/doc_non_adjudicating.md` | Fixture: `non-adjudicating` rule + `closure_terminal`. |
| `tests/fixtures/verdict/doc_reframed.md` | Fixture: `reframed` rule + `reframing_target` + `reframing_reason`. |
| `tests/fixtures/verdict/doc_weighted_majority.md` | Fixture: `weighted-majority` rule with explicit weights. |
| `tests/fixtures/verdict/claim-registry.yaml` | Fixture project's claim registry (5 canonical IDs + synonyms). |

### Modified files

| Path | Purpose |
|------|---------|
| `src/science_tool/cli.py` | Add `from science_tool.verdict.cli import verdict_group` import and `main.add_command(verdict_group)` registration. |
| `docs/specs/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md` | v1.2 touch-ups: reference the mm30 `specs/claim-registry.yaml` as the first concrete implementation; note the t246 finding that the `confidence` column in backfill audit TSVs is advisory-only; bump acceptance criterion 6 from "6 reference docs" to "9" given mm30's new dogfood docs (t099, t240, t258). |

### Explicitly NOT created by this plan

See the "What this MVP leaves out" section at the end of this plan.

---

## Task 1: Scaffold `verdict/` sub-package + `Token` enum

**Files:**
- Create: `src/science_tool/verdict/__init__.py`
- Create: `src/science_tool/verdict/tokens.py`
- Test: `tests/test_verdict_tokens.py`

- [ ] **Step 1.1: Write the failing test**

Create `tests/test_verdict_tokens.py`:

```python
from science_tool.verdict.tokens import Token, parse_body_verdict


def test_token_enum_has_five_values() -> None:
    assert {t.value for t in Token} == {"[+]", "[-]", "[~]", "[?]", "[⌀]"}


def test_parse_body_verdict_finds_first_line() -> None:
    md = """# Some Interpretation

## Verdict

**Verdict:** [+] The prediction held with p < 0.01.

## Summary

further prose here...
"""
    assert parse_body_verdict(md) == (Token.POSITIVE, "The prediction held with p < 0.01.")


def test_parse_body_verdict_handles_non_adjudicating() -> None:
    md = "\n**Verdict:** [⌀] Non-adjudicating terminal.\n"
    assert parse_body_verdict(md) == (Token.NON_ADJUDICATING, "Non-adjudicating terminal.")


def test_parse_body_verdict_returns_none_when_missing() -> None:
    assert parse_body_verdict("# Doc with no verdict\n\nprose\n") is None


def test_parse_body_verdict_takes_first_match() -> None:
    md = "**Verdict:** [+] first\n\n**Verdict:** [-] later line should be ignored\n"
    tok, clause = parse_body_verdict(md)
    assert tok == Token.POSITIVE
    assert clause == "first"
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_tokens.py -v`
Expected: collection error / `ImportError: No module named 'science_tool.verdict'`.

- [ ] **Step 1.3: Create the package + minimum implementation**

Create `src/science_tool/verdict/__init__.py`:

```python
"""Verdict-token parsing and rollup subsystem.

Implements the 5-token verdict vocabulary plus atomic-claim
decomposition per science-spec:2026-04-19-verdict-tokens-and-atomic-
decomposition-design (v1.1+).
"""

from __future__ import annotations

from science_tool.verdict.tokens import Token, parse_body_verdict

__all__ = ["Token", "parse_body_verdict"]
```

Create `src/science_tool/verdict/tokens.py`:

```python
"""Five-token verdict vocabulary and body-verdict extractor."""

from __future__ import annotations

import re
from enum import Enum


class Token(str, Enum):
    """Verdict polarity tokens per spec v1.1.

    Polarity is with respect to the PREDICTED DIRECTION, not project valence.
    """

    POSITIVE = "[+]"
    NEGATIVE = "[-]"
    MIXED = "[~]"
    INCONCLUSIVE = "[?]"
    NON_ADJUDICATING = "[⌀]"

    @classmethod
    def from_str(cls, s: str) -> "Token":
        for t in cls:
            if t.value == s:
                return t
        raise ValueError(f"Unknown verdict token: {s!r}")


# Matches the first `**Verdict:** [TOKEN] clause` line. Permissive
# on whitespace and anchors on the literal `**Verdict:**` prefix so
# it's robust to backfill-style comments and later prose.
_BODY_VERDICT_RE = re.compile(
    r"\*\*Verdict:\*\*\s*(\[[+\-~?⌀]\])\s*(.+?)(?=\n\n|\n<!--|\Z)",
    re.DOTALL,
)


def parse_body_verdict(markdown: str) -> tuple[Token, str] | None:
    """Return (token, clause) from the first `**Verdict:** [X] ...` line.

    The clause runs up to the first blank line, HTML comment, or end
    of document. Returns None if no verdict line is present.
    """
    match = _BODY_VERDICT_RE.search(markdown)
    if match is None:
        return None
    token = Token.from_str(match.group(1))
    clause = match.group(2).strip()
    return token, clause
```

- [ ] **Step 1.4: Run test to verify it passes**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_tokens.py -v`
Expected: 5 passed.

- [ ] **Step 1.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/__init__.py src/science_tool/verdict/tokens.py tests/test_verdict_tokens.py
git commit -m "feat(verdict): scaffold verdict sub-package with Token enum + body parser"
```

---

## Task 2: Dataclass models for `VerdictBlock`, `Claim`, `Context`, `ParseResult`

**Files:**
- Create: `src/science_tool/verdict/models.py`
- Test: `tests/test_verdict_models.py`

- [ ] **Step 2.1: Write the failing test**

Create `tests/test_verdict_models.py`:

```python
from dataclasses import asdict

from science_tool.verdict.models import (
    Claim,
    Context,
    ParseResult,
    VerdictBlock,
)
from science_tool.verdict.tokens import Token


def test_verdict_block_minimal_construction() -> None:
    block = VerdictBlock(composite=Token.POSITIVE, rule="and", claims=[])
    assert block.composite == Token.POSITIVE
    assert block.rule == "and"
    assert block.claims == []
    assert block.closure_terminal is None
    assert block.reframing_target is None


def test_claim_with_contexts_and_weight() -> None:
    c = Claim(
        id="h1#edge5-ifn-arm",
        polarity=Token.POSITIVE,
        strength="strong",
        weight=1.5,
        evidence_summary="NES=+2.83 padj<1e-15",
        contexts=[
            Context(context="MM.1S", polarity=Token.POSITIVE, strength="strong"),
            Context(context="RPMI-8226", polarity=Token.POSITIVE, strength="strong"),
        ],
    )
    assert c.weight == 1.5
    assert len(c.contexts) == 2
    assert c.contexts[0].context == "MM.1S"


def test_parse_result_roundtrips_to_dict() -> None:
    result = ParseResult(
        interpretation_id="interpretation:2026-04-14-t197",
        composite_token=Token.MIXED,
        composite_clause="Weakly_replicated; IFN both, E2F partial.",
        rule="and",
        rule_derived_composite=Token.MIXED,
        rule_disagrees_with_body=False,
        claims=[
            Claim(
                id="h1#edge5-ifn-arm",
                polarity=Token.POSITIVE,
                strength="strong",
                weight=1.0,
                evidence_summary="",
                contexts=[],
            )
        ],
        validation_warnings=[],
    )
    d = asdict(result)
    assert d["interpretation_id"] == "interpretation:2026-04-14-t197"
    assert d["rule_disagrees_with_body"] is False
    assert d["claims"][0]["id"] == "h1#edge5-ifn-arm"
    assert d["closure_terminal"] is None  # top-level field present


def test_parse_result_surfaces_closure_terminal_and_reframing_fields() -> None:
    result = ParseResult(
        interpretation_id="interpretation:fake",
        composite_token=Token.NON_ADJUDICATING,
        composite_clause="closed under observational adjusters",
        rule="non-adjudicating",
        rule_derived_composite=Token.NON_ADJUDICATING,
        rule_disagrees_with_body=False,
        closure_terminal="non_adjudicating_under_observational_adjusters",
    )
    assert result.closure_terminal == "non_adjudicating_under_observational_adjusters"
    assert result.reframing_target is None
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_models.py -v`
Expected: `ImportError: No module named 'science_tool.verdict.models'`.

- [ ] **Step 2.3: Write the implementation**

Create `src/science_tool/verdict/models.py`:

```python
"""Dataclass models for verdict frontmatter blocks and parse results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from science_tool.verdict.tokens import Token


@dataclass
class Context:
    """Per-context polarity + strength for a single claim (v1.1 `contexts` sub-block)."""

    context: str
    polarity: Token
    strength: str | None = None


@dataclass
class Claim:
    """A single atomic claim inside a verdict block.

    The `weight` field is only consulted when the parent rule is
    `weighted-majority`; for other rules it defaults to 1.0 and is
    ignored. `members` lists sub-claim IDs that this claim groups
    (v1.1 gap 4 addition).
    """

    id: str
    polarity: Token
    strength: str | None = None
    weight: float = 1.0
    evidence_summary: str = ""
    contexts: list[Context] = field(default_factory=list)
    members: list[str] = field(default_factory=list)


@dataclass
class VerdictBlock:
    """The `verdict:` frontmatter block, fully hydrated from YAML."""

    composite: Token
    rule: str
    claims: list[Claim] = field(default_factory=list)
    closure_terminal: str | None = None  # only set when rule == "non-adjudicating"
    reframing_target: str | None = None  # only set when rule == "reframed"
    reframing_reason: str | None = None  # only set when rule == "reframed"


@dataclass
class ClaimRegistryEntry:
    """One canonical claim in the project-local registry."""

    id: str
    source: str
    definition: str
    predicted_direction: Token
    synonyms: list[str] = field(default_factory=list)
    members: list[str] = field(default_factory=list)
    cited_in: list[str] = field(default_factory=list)


@dataclass
class ClaimRegistry:
    """Project-local claim registry (`specs/claim-registry.yaml`)."""

    version: int
    project: str
    entries: list[ClaimRegistryEntry] = field(default_factory=list)
    conventions: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    """Output of `parse_file(path)` — the spec's §"Implementation contract for the parser".

    `closure_terminal`, `reframing_target`, `reframing_reason` are
    surfaced at the top level (not nested inside the original
    VerdictBlock) so `science-tool verdict parse` output includes
    them directly, per spec v1.1 acceptance criteria.
    """

    interpretation_id: str
    composite_token: Token
    composite_clause: str
    rule: str
    rule_derived_composite: Token
    rule_disagrees_with_body: bool
    closure_terminal: str | None = None
    reframing_target: str | None = None
    reframing_reason: str | None = None
    claims: list[Claim] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
```

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_models.py -v`
Expected: 3 passed.

- [ ] **Step 2.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/models.py tests/test_verdict_models.py
git commit -m "feat(verdict): dataclass models for VerdictBlock, Claim, Context, ParseResult"
```

---

## Task 3: Rule aggregation — `and` / `or` / `majority`

**Files:**
- Create: `src/science_tool/verdict/rules.py`
- Test: `tests/test_verdict_rules.py`

- [ ] **Step 3.1: Write the failing test**

Create `tests/test_verdict_rules.py`:

```python
import pytest

from science_tool.verdict.models import Claim
from science_tool.verdict.rules import aggregate_composite, rule_disagrees_with_body
from science_tool.verdict.tokens import Token


def _claim(cid: str, p: Token, w: float = 1.0) -> Claim:
    return Claim(id=cid, polarity=p, weight=w)


def test_and_rule_all_positive_yields_positive() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.POSITIVE)]
    assert aggregate_composite("and", claims) == Token.POSITIVE


def test_and_rule_any_negative_yields_negative() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("and", claims) == Token.NEGATIVE


def test_and_rule_mixed_yields_mixed() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.MIXED)]
    assert aggregate_composite("and", claims) == Token.MIXED


def test_or_rule_any_positive_yields_positive() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("or", claims) == Token.POSITIVE


def test_or_rule_all_negative_yields_negative() -> None:
    claims = [_claim("c1", Token.NEGATIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("or", claims) == Token.NEGATIVE


def test_majority_rule_half_positive_yields_positive() -> None:
    claims = [
        _claim("c1", Token.POSITIVE),
        _claim("c2", Token.POSITIVE),
        _claim("c3", Token.NEGATIVE),
        _claim("c4", Token.MIXED),
    ]
    assert aggregate_composite("majority", claims) == Token.POSITIVE


def test_majority_rule_no_majority_yields_mixed() -> None:
    claims = [
        _claim("c1", Token.POSITIVE),
        _claim("c2", Token.NEGATIVE),
        _claim("c3", Token.MIXED),
    ]
    assert aggregate_composite("majority", claims) == Token.MIXED


def test_rule_disagrees_with_body_false_when_matching() -> None:
    assert rule_disagrees_with_body(Token.POSITIVE, Token.POSITIVE) is False


def test_rule_disagrees_with_body_true_when_mismatching() -> None:
    assert rule_disagrees_with_body(Token.NEGATIVE, Token.MIXED) is True


def test_unknown_rule_raises() -> None:
    with pytest.raises(ValueError, match="Unknown aggregation rule"):
        aggregate_composite("wat", [_claim("c1", Token.POSITIVE)])
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_rules.py -v`
Expected: `ImportError: No module named 'science_tool.verdict.rules'`.

- [ ] **Step 3.3: Write the implementation (and/or/majority only — weighted-majority/bimodal/non-adjudicating/reframed come in Task 4)**

Create `src/science_tool/verdict/rules.py`:

```python
"""Rule aggregation for verdict composite-token derivation."""

from __future__ import annotations

from collections import Counter

from science_tool.verdict.models import Claim
from science_tool.verdict.tokens import Token


def aggregate_composite(
    rule: str,
    claims: list[Claim],
) -> Token:
    """Derive the composite Token from a list of Claim polarities under a rule."""
    if rule == "and":
        return _rule_and(claims)
    if rule == "or":
        return _rule_or(claims)
    if rule == "majority":
        return _rule_majority(claims)
    raise ValueError(f"Unknown aggregation rule: {rule!r}")


def _rule_and(claims: list[Claim]) -> Token:
    polarities = {c.polarity for c in claims}
    if polarities == {Token.POSITIVE}:
        return Token.POSITIVE
    if Token.NEGATIVE in polarities:
        return Token.NEGATIVE
    return Token.MIXED


def _rule_or(claims: list[Claim]) -> Token:
    polarities = {c.polarity for c in claims}
    if Token.POSITIVE in polarities:
        return Token.POSITIVE
    if polarities == {Token.NEGATIVE}:
        return Token.NEGATIVE
    return Token.MIXED


def _rule_majority(claims: list[Claim]) -> Token:
    """≥50% of claims share a polarity → that polarity; else [~]."""
    counts = Counter(c.polarity for c in claims)
    total = len(claims)
    if total == 0:
        return Token.MIXED
    for polarity in (Token.POSITIVE, Token.NEGATIVE):
        if counts[polarity] / total >= 0.5:
            return polarity
    return Token.MIXED


def rule_disagrees_with_body(rule_composite: Token, body_composite: Token) -> bool:
    """Return True iff the rule-derived composite differs from the body verdict."""
    return rule_composite != body_composite
```

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_rules.py -v`
Expected: 10 passed.

- [ ] **Step 3.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/rules.py tests/test_verdict_rules.py
git commit -m "feat(verdict): and/or/majority aggregation rules + disagreement detector"
```

---

## Task 4: Rule aggregation — `weighted-majority` / `bimodal` / `non-adjudicating` / `reframed`

**Files:**
- Modify: `src/science_tool/verdict/rules.py`
- Modify: `tests/test_verdict_rules.py`

- [ ] **Step 4.1: Add failing tests for the four new rules**

Append to `tests/test_verdict_rules.py`:

```python
def test_weighted_majority_tips_to_minority_with_high_weight() -> None:
    # t163-style: 3 negatives weight 1.0 each, 1 positive weight 3.0 → positive wins.
    claims = [
        _claim("n1", Token.NEGATIVE, w=1.0),
        _claim("n2", Token.NEGATIVE, w=1.0),
        _claim("n3", Token.NEGATIVE, w=1.0),
        _claim("p1", Token.POSITIVE, w=3.0),
    ]
    assert aggregate_composite("weighted-majority", claims) == Token.POSITIVE


def test_weighted_majority_falls_back_to_mixed_when_no_50pct() -> None:
    claims = [
        _claim("p1", Token.POSITIVE, w=1.0),
        _claim("n1", Token.NEGATIVE, w=1.0),
    ]
    assert aggregate_composite("weighted-majority", claims) == Token.MIXED


def test_bimodal_always_yields_mixed() -> None:
    claims = [
        _claim("c1", Token.POSITIVE),
        _claim("c2", Token.POSITIVE),
        _claim("c3", Token.NEGATIVE),
        _claim("c4", Token.NEGATIVE),
    ]
    assert aggregate_composite("bimodal", claims) == Token.MIXED


def test_non_adjudicating_always_yields_non_adjudicating() -> None:
    claims = [_claim("c1", Token.NEGATIVE), _claim("c2", Token.POSITIVE)]
    assert aggregate_composite("non-adjudicating", claims) == Token.NON_ADJUDICATING


def test_reframed_always_yields_mixed() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("reframed", claims) == Token.MIXED
```

- [ ] **Step 4.2: Run tests to verify the new cases fail**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_rules.py -v`
Expected: 5 new failures with `ValueError: Unknown aggregation rule`.

- [ ] **Step 4.3: Extend the rules module**

Modify `src/science_tool/verdict/rules.py`. Replace the existing `aggregate_composite` function with:

```python
def aggregate_composite(
    rule: str,
    claims: list[Claim],
) -> Token:
    """Derive the composite Token from a list of Claim polarities under a rule."""
    if rule == "and":
        return _rule_and(claims)
    if rule == "or":
        return _rule_or(claims)
    if rule == "majority":
        return _rule_majority(claims)
    if rule == "weighted-majority":
        return _rule_weighted_majority(claims)
    if rule == "bimodal":
        return Token.MIXED
    if rule == "non-adjudicating":
        return Token.NON_ADJUDICATING
    if rule == "reframed":
        return Token.MIXED
    raise ValueError(f"Unknown aggregation rule: {rule!r}")
```

Add to the end of the same file:

```python
def _rule_weighted_majority(claims: list[Claim]) -> Token:
    """≥50% of total weight shares a polarity → that polarity; else [~]."""
    total_weight = sum(c.weight for c in claims)
    if total_weight == 0:
        return Token.MIXED
    weight_by_polarity: dict[Token, float] = {}
    for c in claims:
        weight_by_polarity[c.polarity] = weight_by_polarity.get(c.polarity, 0.0) + c.weight
    for polarity in (Token.POSITIVE, Token.NEGATIVE):
        if weight_by_polarity.get(polarity, 0.0) / total_weight >= 0.5:
            return polarity
    return Token.MIXED
```

- [ ] **Step 4.4: Run all rule tests**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_rules.py -v`
Expected: 15 passed.

- [ ] **Step 4.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/rules.py tests/test_verdict_rules.py
git commit -m "feat(verdict): add weighted-majority, bimodal, non-adjudicating, reframed rules"
```

---

## Task 5: Fixture markdown files for the parser

**Files:**
- Create: `tests/fixtures/verdict/doc_and.md`
- Create: `tests/fixtures/verdict/doc_majority_disagrees.md`
- Create: `tests/fixtures/verdict/doc_bimodal.md`
- Create: `tests/fixtures/verdict/doc_non_adjudicating.md`
- Create: `tests/fixtures/verdict/doc_reframed.md`
- Create: `tests/fixtures/verdict/doc_weighted_majority.md`
- Create: `tests/fixtures/verdict/claim-registry.yaml`

- [ ] **Step 5.1: Create `doc_and.md` (the happy path — rule matches body)**

```markdown
---
id: "interpretation:fixture-and"
type: "interpretation"
title: "Fixture: and rule, two claims, both positive"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "h1#edge5-ifn-arm"
      polarity: "[+]"
      strength: "strong"
      evidence_summary: "NES=+2.83 padj<1e-15 in both contexts"
    - id: "h1#edge5-ifn-arm-gamma"
      polarity: "[+]"
      strength: "strong"
      evidence_summary: "IFN-gamma also strong"
---

## Verdict

**Verdict:** [+] Both arms replicate strongly.

## Findings

body prose.
```

- [ ] **Step 5.2: Create `doc_majority_disagrees.md` (t163-style load-bearing minority)**

```markdown
---
id: "interpretation:fixture-majority-disagrees"
type: "interpretation"
title: "Fixture: majority rule mechanically yields [-] but body says [~]"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[~]"
  rule: "majority"
  claims:
    - id: "t163#edge-cdk2-e2f1-survives-prolif-adj"
      polarity: "[-]"
      strength: "moderate"
      evidence_summary: "collapsed"
    - id: "t163#edge-e2f1-ezh2-survives-prolif-adj"
      polarity: "[-]"
      strength: "strong"
      evidence_summary: "collapsed"
    - id: "t163#edge-e2f1-phf19-survives-prolif-adj"
      polarity: "[-]"
      strength: "strong"
      evidence_summary: "collapsed"
    - id: "t163#edge-ezh2-phf19-survives-prolif-adj"
      polarity: "[+]"
      strength: "moderate"
      evidence_summary: "survives — the load-bearing mechanism edge"
---

## Verdict

**Verdict:** [~] 3/4 collapse, but EZH2 -> PHF19 survives and is the load-bearing mechanism edge.
```

- [ ] **Step 5.3: Create `doc_bimodal.md`**

```markdown
---
id: "interpretation:fixture-bimodal"
type: "interpretation"
title: "Fixture: bimodal rule with 4 atoms"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[~]"
  rule: "bimodal"
  claims:
    - id: "h4#attractor-2-robustness"
      polarity: "[+]"
      strength: "strong"
      evidence_summary: "robust under 50% perturbation"
    - id: "h4#attractor-12-robustness"
      polarity: "[+]"
      strength: "strong"
      evidence_summary: "robust under 50% perturbation"
    - id: "h4#attractor-8-robustness"
      polarity: "[-]"
      strength: "strong"
      evidence_summary: "collapses"
    - id: "h4#attractor-9-robustness"
      polarity: "[-]"
      strength: "moderate"
      evidence_summary: "collapses"
---

## Verdict

**Verdict:** [~] Bimodal partial rescue: 2 basins robust, 2 collapse.
```

- [ ] **Step 5.4: Create `doc_non_adjudicating.md`**

```markdown
---
id: "interpretation:fixture-non-adjudicating"
type: "interpretation"
title: "Fixture: non-adjudicating terminal"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[⌀]"
  rule: "non-adjudicating"
  closure_terminal: "non_adjudicating_under_observational_adjusters"
  claims:
    - id: "t204#v140_6-multitype-non-pc-absorption"
      polarity: "[-]"
      strength: "moderate"
      evidence_summary: "no_additional_absorption"
---

## Verdict

**Verdict:** [⌀] Non-adjudicating under observational adjusters.
```

- [ ] **Step 5.5: Create `doc_reframed.md`**

```markdown
---
id: "interpretation:fixture-reframed"
type: "interpretation"
title: "Fixture: reframed prior finding"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[~]"
  rule: "reframed"
  reframing_target: "interpretation:t149-ribosome-regulator-falsification"
  reframing_reason: "Raw-TPM correlations were compositional; CLR refit flipped signs."
  claims:
    - id: "t149#myc-max-uniform-negative-falsification"
      polarity: "[-]"
      strength: "strong"
      evidence_summary: "retracted under CLR"
---

## Verdict

**Verdict:** [~] Prior finding reframed; original signal was compositional.
```

- [ ] **Step 5.6: Create `doc_weighted_majority.md`**

```markdown
---
id: "interpretation:fixture-weighted-majority"
type: "interpretation"
title: "Fixture: weighted-majority rule with load-bearing minority"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[+]"
  rule: "weighted-majority"
  claims:
    - id: "n1"
      polarity: "[-]"
      strength: "weak"
      weight: 1.0
      evidence_summary: "n1"
    - id: "n2"
      polarity: "[-]"
      strength: "weak"
      weight: 1.0
      evidence_summary: "n2"
    - id: "n3"
      polarity: "[-]"
      strength: "weak"
      weight: 1.0
      evidence_summary: "n3"
    - id: "p1"
      polarity: "[+]"
      strength: "strong"
      weight: 3.0
      evidence_summary: "load-bearing p1"
---

## Verdict

**Verdict:** [+] One load-bearing positive outweighs three weak negatives.
```

- [ ] **Step 5.7: Create `tests/fixtures/verdict/claim-registry.yaml`**

```yaml
version: 1
project: fixture
schema: "science-spec:2026-04-19-verdict-tokens-and-atomic-decomposition-design#v1.1"
created: "2026-04-21"
conventions:
  separator: "#"
  id_pattern: "^(h[1-4]|t[0-9]+)#[A-Za-z0-9_-]+$"
  synonym_resolution: "first-match-wins"
claims:
  - id: "h1#edge5-ifn-arm"
    source: "hypothesis:h1"
    definition: "IFN arm of the edge-5 PRC2 mechanism."
    predicted_direction: "[+]"
    synonyms:
      - "h1-edge6-ifn-arm"   # deliberate drift case
    cited_in:
      - "interpretation:fixture-and"
  - id: "h1#edge5-ifn-arm-gamma"
    source: "hypothesis:h1"
    definition: "IFN-gamma sub-arm."
    predicted_direction: "[+]"
    cited_in:
      - "interpretation:fixture-and"
  - id: "t163#edge-cdk2-e2f1-survives-prolif-adj"
    source: "task:t163"
    definition: "Does CDK2->E2F1 survive proliferation adjustment?"
    predicted_direction: "[+]"
    cited_in:
      - "interpretation:fixture-majority-disagrees"
  - id: "t163#edge-ezh2-phf19-survives-prolif-adj"
    source: "task:t163"
    definition: "Does EZH2->PHF19 survive proliferation adjustment? (load-bearing edge)"
    predicted_direction: "[+]"
    cited_in:
      - "interpretation:fixture-majority-disagrees"
  - id: "h4#attractor-2-robustness"
    source: "hypothesis:h4"
    definition: "Is attractor #2 robust under perturbation?"
    predicted_direction: "[+]"
    cited_in:
      - "interpretation:fixture-bimodal"
```

- [ ] **Step 5.8: Commit**

```bash
cd ~/d/science/science-tool
git add tests/fixtures/verdict/
git commit -m "test(verdict): add 6 fixture markdown docs + minimal claim registry"
```

---

## Task 6: Parser — YAML frontmatter + verdict-block hydration

**Files:**
- Create: `src/science_tool/verdict/parser.py`
- Test: `tests/test_verdict_parser.py`

- [ ] **Step 6.1: Write failing parser tests**

Create `tests/test_verdict_parser.py`:

```python
from pathlib import Path

import pytest

from science_tool.verdict.parser import parse_file
from science_tool.verdict.tokens import Token

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "verdict"


def test_parse_and_rule_fixture() -> None:
    result = parse_file(FIXTURE_DIR / "doc_and.md")
    assert result.interpretation_id == "interpretation:fixture-and"
    assert result.composite_token == Token.POSITIVE
    assert result.rule == "and"
    assert result.rule_derived_composite == Token.POSITIVE
    assert result.rule_disagrees_with_body is False
    assert len(result.claims) == 2
    assert result.claims[0].id == "h1#edge5-ifn-arm"


def test_parse_majority_disagrees_fixture_sets_flag() -> None:
    result = parse_file(FIXTURE_DIR / "doc_majority_disagrees.md")
    assert result.composite_token == Token.MIXED
    assert result.rule_derived_composite == Token.NEGATIVE
    assert result.rule_disagrees_with_body is True


def test_parse_bimodal_fixture() -> None:
    result = parse_file(FIXTURE_DIR / "doc_bimodal.md")
    assert result.rule == "bimodal"
    assert result.rule_derived_composite == Token.MIXED
    assert result.rule_disagrees_with_body is False
    assert len(result.claims) == 4


def test_parse_non_adjudicating_fixture_captures_closure_terminal() -> None:
    result = parse_file(FIXTURE_DIR / "doc_non_adjudicating.md")
    assert result.rule == "non-adjudicating"
    assert result.composite_token == Token.NON_ADJUDICATING
    assert result.rule_disagrees_with_body is False
    assert result.closure_terminal == "non_adjudicating_under_observational_adjusters"


def test_parse_reframed_fixture_captures_target_and_reason() -> None:
    result = parse_file(FIXTURE_DIR / "doc_reframed.md")
    assert result.rule == "reframed"
    assert result.rule_derived_composite == Token.MIXED
    assert result.reframing_target == "interpretation:t149-ribosome-regulator-falsification"
    assert result.reframing_reason is not None
    assert "compositional" in result.reframing_reason


def test_parse_weighted_majority_fixture() -> None:
    result = parse_file(FIXTURE_DIR / "doc_weighted_majority.md")
    assert result.rule == "weighted-majority"
    assert result.rule_derived_composite == Token.POSITIVE
    assert result.rule_disagrees_with_body is False


def test_parse_missing_frontmatter_raises(tmp_path: Path) -> None:
    p = tmp_path / "no_frontmatter.md"
    p.write_text("# Just a heading\n\n**Verdict:** [+] something\n")
    with pytest.raises(ValueError, match="missing frontmatter"):
        parse_file(p)


def test_parse_missing_verdict_block_raises(tmp_path: Path) -> None:
    p = tmp_path / "no_verdict_block.md"
    p.write_text(
        "---\ntitle: \"no verdict block\"\nid: \"interpretation:fake\"\n---\n\n## Verdict\n\n**Verdict:** [+] body only\n"
    )
    with pytest.raises(ValueError, match="no 'verdict:' block"):
        parse_file(p)
```

- [ ] **Step 6.2: Run tests to verify they fail**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_parser.py -v`
Expected: `ImportError: cannot import name 'parse_file' from 'science_tool.verdict.parser'` (module does not yet exist).

- [ ] **Step 6.3: Write the parser implementation**

Create `src/science_tool/verdict/parser.py`:

```python
"""Parse an interpretation .md file into a ParseResult."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from science_tool.verdict.models import Claim, Context, ParseResult, VerdictBlock
from science_tool.verdict.rules import aggregate_composite, rule_disagrees_with_body
from science_tool.verdict.tokens import Token, parse_body_verdict

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def parse_file(path: Path | str) -> ParseResult:
    """Parse a markdown file with a frontmatter `verdict:` block.

    Raises ValueError if the file is missing frontmatter or a
    verdict block. Verdicts with unknown rules raise from the
    downstream `aggregate_composite` call.
    """
    raw = Path(path).read_text(encoding="utf-8")
    fm, body = _split_frontmatter(raw, path)
    meta = yaml.safe_load(fm) or {}
    verdict_yaml = meta.get("verdict")
    if verdict_yaml is None:
        raise ValueError(f"{path}: frontmatter has no 'verdict:' block")
    verdict = _hydrate_verdict(verdict_yaml)
    interp_id = meta.get("id", f"unknown:{Path(path).stem}")

    body_verdict = parse_body_verdict(body)
    body_token, body_clause = (
        body_verdict if body_verdict is not None else (verdict.composite, "")
    )

    warnings: list[str] = []
    if verdict.rule == "reframed" and not verdict.reframing_target:
        warnings.append("rule=reframed but reframing_target is missing")
    if verdict.rule == "non-adjudicating" and not verdict.closure_terminal:
        warnings.append("rule=non-adjudicating but closure_terminal is missing")

    if body_verdict is None:
        warnings.append("body has no `**Verdict:** [X]` line; using frontmatter composite as fallback")

    derived = aggregate_composite(verdict.rule, verdict.claims)
    return ParseResult(
        interpretation_id=interp_id,
        composite_token=body_token,
        composite_clause=body_clause,
        rule=verdict.rule,
        rule_derived_composite=derived,
        rule_disagrees_with_body=rule_disagrees_with_body(derived, body_token),
        closure_terminal=verdict.closure_terminal,
        reframing_target=verdict.reframing_target,
        reframing_reason=verdict.reframing_reason,
        claims=verdict.claims,
        validation_warnings=warnings,
    )


def _split_frontmatter(raw: str, path: Path | str) -> tuple[str, str]:
    match = _FRONTMATTER_RE.match(raw)
    if match is None:
        raise ValueError(f"{path}: missing frontmatter (expected leading --- ... ---)")
    return match.group(1), match.group(2)


def _hydrate_verdict(data: dict[str, Any]) -> VerdictBlock:
    composite = Token.from_str(data["composite"])
    rule = str(data["rule"])
    claims_yaml = data.get("claims", []) or []
    claims = [_hydrate_claim(c) for c in claims_yaml]
    return VerdictBlock(
        composite=composite,
        rule=rule,
        claims=claims,
        closure_terminal=data.get("closure_terminal"),
        reframing_target=data.get("reframing_target"),
        reframing_reason=data.get("reframing_reason"),
    )


def _hydrate_claim(data: dict[str, Any]) -> Claim:
    contexts = [
        Context(
            context=str(ctx["context"]),
            polarity=Token.from_str(ctx["polarity"]),
            strength=ctx.get("strength"),
        )
        for ctx in data.get("contexts", []) or []
    ]
    return Claim(
        id=str(data["id"]),
        polarity=Token.from_str(data["polarity"]),
        strength=data.get("strength"),
        weight=float(data.get("weight", 1.0)),
        evidence_summary=str(data.get("evidence_summary", "")),
        contexts=contexts,
        members=list(data.get("members", []) or []),
    )
```

- [ ] **Step 6.4: Run tests to verify they pass**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_parser.py -v`
Expected: 8 passed.

- [ ] **Step 6.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/parser.py tests/test_verdict_parser.py
git commit -m "feat(verdict): parse_file — frontmatter + verdict-block hydration + disagreement detection"
```

---

## Task 7: Claim registry loader + synonym resolution

**Files:**
- Create: `src/science_tool/verdict/registry.py`
- Test: `tests/test_verdict_registry.py`

- [ ] **Step 7.1: Write failing tests**

Create `tests/test_verdict_registry.py`:

```python
from pathlib import Path

from science_tool.verdict.registry import has_registry, load_registry

FIXTURE_REG = Path(__file__).parent / "fixtures" / "verdict" / "claim-registry.yaml"


def test_load_registry_parses_fixture() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.version == 1
    assert registry.project == "fixture"
    assert len(registry.entries) == 5


def test_registry_resolve_canonical_id_returns_self() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.resolve("h1#edge5-ifn-arm") == "h1#edge5-ifn-arm"


def test_registry_resolve_synonym_returns_canonical() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.resolve("h1-edge6-ifn-arm") == "h1#edge5-ifn-arm"


def test_registry_resolve_unknown_returns_none() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.resolve("bogus#id") is None


def test_has_registry_detects_fixture_project() -> None:
    # The fixture file lives under tests/fixtures/verdict/; treat that dir as the project root.
    project_root = FIXTURE_REG.parent
    # has_registry looks under <project_root>/specs/claim-registry.yaml.
    # Our fixture is at <fixture_dir>/claim-registry.yaml, so copy-via-symlink into a tmp specs/.
    # For the unit test, call has_registry pointing directly at a synthesized specs/ dir below.
    assert has_registry(project_root, alt_filename="claim-registry.yaml") is True


def test_has_registry_false_when_missing(tmp_path: Path) -> None:
    assert has_registry(tmp_path) is False
```

- [ ] **Step 7.2: Run tests to verify they fail**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_registry.py -v`
Expected: `ImportError: No module named 'science_tool.verdict.registry'`.

- [ ] **Step 7.3: Write the registry implementation**

Create `src/science_tool/verdict/registry.py`:

```python
"""Project-local claim registry (`specs/claim-registry.yaml`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from science_tool.verdict.models import ClaimRegistry, ClaimRegistryEntry
from science_tool.verdict.tokens import Token


@dataclass
class IndexedClaimRegistry:
    """Registry + precomputed ID -> canonical lookup."""

    registry: ClaimRegistry
    _index: dict[str, str] = field(default_factory=dict)

    def resolve(self, claim_id: str) -> str | None:
        return self._index.get(claim_id)

    @property
    def version(self) -> int:
        return self.registry.version

    @property
    def project(self) -> str:
        return self.registry.project

    @property
    def entries(self) -> list[ClaimRegistryEntry]:
        return self.registry.entries


def load_registry(path: Path | str) -> IndexedClaimRegistry:
    """Load a project-local claim registry YAML and index it for resolution."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    entries = [_hydrate_entry(raw) for raw in data.get("claims", []) or []]
    registry = ClaimRegistry(
        version=int(data.get("version", 1)),
        project=str(data.get("project", "")),
        entries=entries,
        conventions=data.get("conventions", {}) or {},
    )
    index: dict[str, str] = {}
    for entry in entries:
        index[entry.id] = entry.id
        for syn in entry.synonyms:
            # First-match-wins: if a synonym collides, the first
            # canonical ID to claim it keeps it. Project owners can
            # reorder the registry to disambiguate.
            index.setdefault(syn, entry.id)
    return IndexedClaimRegistry(registry=registry, _index=index)


def _hydrate_entry(raw: dict[str, Any]) -> ClaimRegistryEntry:
    return ClaimRegistryEntry(
        id=str(raw["id"]),
        source=str(raw.get("source", "")),
        definition=str(raw.get("definition", "")),
        predicted_direction=Token.from_str(raw.get("predicted_direction", "[+]")),
        synonyms=list(raw.get("synonyms", []) or []),
        members=list(raw.get("members", []) or []),
        cited_in=list(raw.get("cited_in", []) or []),
    )


def has_registry(
    project_root: Path | str,
    *,
    alt_filename: str | None = None,
) -> bool:
    """Return True iff `<project_root>/specs/claim-registry.yaml` exists.

    If `alt_filename` is provided, look for that filename inside the
    project_root directly (used by test fixtures that don't have a
    `specs/` subdir).
    """
    root = Path(project_root)
    if alt_filename is not None:
        return (root / alt_filename).is_file()
    return (root / "specs" / "claim-registry.yaml").is_file()
```

- [ ] **Step 7.4: Run tests to verify they pass**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_registry.py -v`
Expected: 6 passed.

- [ ] **Step 7.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/registry.py tests/test_verdict_registry.py
git commit -m "feat(verdict): claim-registry loader + synonym resolution"
```

---

## Task 8: Rollup engine — walk + group-by

**Files:**
- Create: `src/science_tool/verdict/rollup.py`
- Test: `tests/test_verdict_rollup.py`

- [ ] **Step 8.1: Write failing tests**

Create `tests/test_verdict_rollup.py`:

```python
from pathlib import Path

from science_tool.verdict.registry import load_registry
from science_tool.verdict.rollup import group_by, tally_polarities, walk_interpretations
from science_tool.verdict.tokens import Token

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "verdict"


def test_walk_finds_all_verdict_bearing_fixtures() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))
    # 6 fixture .md files all have verdict: blocks.
    assert len(results) == 6
    ids = {r.interpretation_id for r in results}
    assert "interpretation:fixture-and" in ids


def test_group_by_all_returns_single_bucket() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))
    groups = group_by(results, scope="all")
    assert set(groups.keys()) == {"all"}
    assert len(groups["all"]) == 6


def test_group_by_claim_requires_registry() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))
    registry = load_registry(FIXTURE_DIR / "claim-registry.yaml")
    groups = group_by(results, scope="claim", registry=registry)
    # h1#edge5-ifn-arm is cited in doc_and.md -> 1 citation expected.
    assert "h1#edge5-ifn-arm" in groups
    assert len(groups["h1#edge5-ifn-arm"]) == 1


def test_tally_polarities_counts_composites() -> None:
    results = list(walk_interpretations(FIXTURE_DIR))
    tally = tally_polarities(results)
    # Fixtures: doc_and [+], doc_bimodal [~], doc_majority_disagrees [~],
    # doc_non_adjudicating [⌀], doc_reframed [~], doc_weighted_majority [+].
    # So [+]=2, [~]=3, [⌀]=1.
    assert tally[Token.POSITIVE] == 2
    assert tally[Token.MIXED] == 3
    assert tally[Token.NON_ADJUDICATING] == 1
    assert tally.get(Token.NEGATIVE, 0) == 0
```

- [ ] **Step 8.2: Run tests to verify they fail**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_rollup.py -v`
Expected: ImportError.

- [ ] **Step 8.3: Write the rollup implementation**

Create `src/science_tool/verdict/rollup.py`:

```python
"""Cross-document verdict rollup."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal

from science_tool.verdict.models import ParseResult
from science_tool.verdict.parser import parse_file
from science_tool.verdict.registry import IndexedClaimRegistry
from science_tool.verdict.tokens import Token

Scope = Literal["all", "claim"]


def walk_interpretations(directory: Path | str) -> Iterator[ParseResult]:
    """Parse every `.md` under `directory` that has a `verdict:` block.

    Silently skips files that have no frontmatter or no `verdict:`
    block. Errors from malformed `verdict:` blocks propagate.
    """
    for md_path in sorted(Path(directory).glob("**/*.md")):
        raw = md_path.read_text(encoding="utf-8")
        if "verdict:" not in raw:
            continue
        try:
            result = parse_file(md_path)
        except ValueError:
            # Missing frontmatter or missing verdict: block → skip.
            continue
        yield result


def group_by(
    results: Iterable[ParseResult],
    scope: Scope,
    registry: IndexedClaimRegistry | None = None,
) -> dict[str, list[ParseResult]]:
    """Group parse results by scope.

    scope='all' returns a single bucket keyed 'all'.
    scope='claim' requires registry; groups by canonical claim ID.
    """
    results = list(results)
    if scope == "all":
        return {"all": results}
    if scope == "claim":
        if registry is None:
            raise ValueError("scope='claim' requires a ClaimRegistry")
        buckets: dict[str, list[ParseResult]] = {}
        for r in results:
            seen: set[str] = set()
            for claim in r.claims:
                canonical = registry.resolve(claim.id) or claim.id
                if canonical in seen:
                    continue
                seen.add(canonical)
                buckets.setdefault(canonical, []).append(r)
        return buckets
    raise ValueError(f"Unknown scope: {scope!r}")


def tally_polarities(results: Iterable[ParseResult]) -> dict[Token, int]:
    """Return a Counter-style dict mapping Token -> composite-count."""
    counter = Counter(r.composite_token for r in results)
    return dict(counter)
```

- [ ] **Step 8.4: Run tests to verify they pass**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_rollup.py -v`
Expected: 4 passed.

- [ ] **Step 8.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/rollup.py tests/test_verdict_rollup.py
git commit -m "feat(verdict): rollup engine — walk, group-by all/claim, polarity tally"
```

---

## Task 9: CLI — `verdict parse` and `verdict rollup` commands

**Files:**
- Create: `src/science_tool/verdict/cli.py`
- Test: `tests/test_verdict_cli.py`

- [ ] **Step 9.1: Write failing CLI tests**

Create `tests/test_verdict_cli.py`:

```python
import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.verdict.cli import verdict_group

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "verdict"


def test_verdict_parse_emits_expected_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        verdict_group,
        ["parse", str(FIXTURE_DIR / "doc_and.md")],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["interpretation_id"] == "interpretation:fixture-and"
    assert payload["composite_token"] == "[+]"
    assert payload["rule_derived_composite"] == "[+]"
    assert payload["rule_disagrees_with_body"] is False


def test_verdict_parse_flags_disagreement_for_t163_like_fixture() -> None:
    runner = CliRunner()
    result = runner.invoke(
        verdict_group,
        ["parse", str(FIXTURE_DIR / "doc_majority_disagrees.md")],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["composite_token"] == "[~]"
    assert payload["rule_derived_composite"] == "[-]"
    assert payload["rule_disagrees_with_body"] is True


def test_verdict_rollup_all_prints_tally() -> None:
    runner = CliRunner()
    result = runner.invoke(
        verdict_group,
        ["rollup", "--scope", "all", "--root", str(FIXTURE_DIR), "--output", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["scope"] == "all"
    # 6 fixture docs; 2 [+], 3 [~], 1 [⌀].
    assert payload["groups"]["all"]["n"] == 6
    assert payload["groups"]["all"]["tally"]["[+]"] == 2
    assert payload["groups"]["all"]["tally"]["[~]"] == 3
    assert payload["groups"]["all"]["tally"]["[⌀]"] == 1


def test_verdict_rollup_by_claim_requires_registry() -> None:
    runner = CliRunner()
    # No --registry given; expect a clear error referring to registry-init.
    result = runner.invoke(
        verdict_group,
        ["rollup", "--scope", "claim", "--root", str(FIXTURE_DIR)],
    )
    assert result.exit_code != 0
    assert "registry-init" in result.output or "registry" in result.output


def test_verdict_rollup_by_claim_groups_per_canonical_id() -> None:
    runner = CliRunner()
    result = runner.invoke(
        verdict_group,
        [
            "rollup",
            "--scope",
            "claim",
            "--root",
            str(FIXTURE_DIR),
            "--registry",
            str(FIXTURE_DIR / "claim-registry.yaml"),
            "--output",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["scope"] == "claim"
    assert "h1#edge5-ifn-arm" in payload["groups"]
    assert payload["groups"]["h1#edge5-ifn-arm"]["n"] == 1
```

- [ ] **Step 9.2: Run tests to verify they fail**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_cli.py -v`
Expected: ImportError on `science_tool.verdict.cli`.

- [ ] **Step 9.3: Write the CLI implementation**

Create `src/science_tool/verdict/cli.py`:

```python
"""click subcommands for the verdict subsystem."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from science_tool.verdict.parser import parse_file
from science_tool.verdict.registry import has_registry, load_registry
from science_tool.verdict.rollup import group_by, tally_polarities, walk_interpretations
from science_tool.verdict.tokens import Token


@click.group("verdict")
def verdict_group() -> None:
    """Parse and roll up verdict-token + atomic-claim frontmatter."""


@verdict_group.command("parse")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def parse_cmd(file: Path) -> None:
    """Parse ONE interpretation file and print JSON per the spec contract."""
    result = parse_file(file)
    click.echo(json.dumps(_serialize_parse_result(result), indent=2, ensure_ascii=False))


@verdict_group.command("rollup")
@click.option(
    "--scope",
    type=click.Choice(["all", "claim"]),
    default="all",
    show_default=True,
    help="Aggregation scope. 'claim' requires --registry.",
)
@click.option(
    "--root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Directory to walk for verdict-bearing .md files.",
)
@click.option(
    "--registry",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to a claim-registry.yaml (required for --scope=claim).",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format.",
)
def rollup_cmd(
    scope: str,
    root: Path,
    registry: Path | None,
    output: str,
) -> None:
    """Aggregate verdicts across the project at the requested scope."""
    results = list(walk_interpretations(root))

    registry_obj = None
    if scope == "claim":
        if registry is None:
            # Try auto-discover at <root>/specs/claim-registry.yaml
            default_path = root / "specs" / "claim-registry.yaml"
            if default_path.exists():
                registry_obj = load_registry(default_path)
            else:
                raise click.ClickException(
                    "scope=claim requires a claim registry. Provide --registry, or run "
                    "`science-tool verdict registry-init` to bootstrap one."
                )
        else:
            registry_obj = load_registry(registry)

    groups = group_by(results, scope=scope, registry=registry_obj)  # type: ignore[arg-type]
    payload: dict[str, Any] = {"scope": scope, "n_documents": len(results), "groups": {}}
    for key, docs in groups.items():
        tally = tally_polarities(docs)
        payload["groups"][key] = {
            "n": len(docs),
            "tally": {t.value: count for t, count in tally.items()},
            "documents": [r.interpretation_id for r in docs],
        }

    if output == "json":
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    console = Console()
    table = Table(title=f"verdict rollup — scope={scope}, n_docs={len(results)}")
    table.add_column("Group")
    table.add_column("n", justify="right")
    for t in Token:
        table.add_column(t.value, justify="right")
    for key, details in payload["groups"].items():
        row = [key, str(details["n"])]
        for t in Token:
            row.append(str(details["tally"].get(t.value, 0)))
        table.add_row(*row)
    console.print(table)


def _serialize_parse_result(result: object) -> dict[str, Any]:
    data = asdict(result)
    # Replace enum objects with their .value string for JSON output.
    data["composite_token"] = data["composite_token"].value if hasattr(data["composite_token"], "value") else data["composite_token"]
    data["rule_derived_composite"] = (
        data["rule_derived_composite"].value
        if hasattr(data["rule_derived_composite"], "value")
        else data["rule_derived_composite"]
    )
    for claim in data.get("claims", []):
        if hasattr(claim.get("polarity"), "value"):
            claim["polarity"] = claim["polarity"].value
        for ctx in claim.get("contexts", []):
            if hasattr(ctx.get("polarity"), "value"):
                ctx["polarity"] = ctx["polarity"].value
    return data
```

- [ ] **Step 9.4: Run tests to verify they pass**

Run: `cd ~/d/science/science-tool && uv run pytest tests/test_verdict_cli.py -v`
Expected: 5 passed.

- [ ] **Step 9.5: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/verdict/cli.py tests/test_verdict_cli.py
git commit -m "feat(verdict): CLI — parse, rollup (all + claim scopes), JSON + table output"
```

---

## Task 10: Wire `verdict_group` into the top-level CLI

**Files:**
- Modify: `src/science_tool/cli.py`

- [ ] **Step 10.1: Add the import and registration**

Open `src/science_tool/cli.py`. Locate the block of `main.add_command(...)` calls (around lines 167-171). Add the verdict group import and registration.

Add near the other sub-group imports (alphabetically after `research_package_group`):

```python
from science_tool.verdict.cli import verdict_group
```

Add the registration line immediately after the last existing `main.add_command(...)` line (currently `main.add_command(refs_group)`):

```python
main.add_command(verdict_group)
```

- [ ] **Step 10.2: Verify the top-level CLI exposes the new group**

Run:

```bash
cd ~/d/science/science-tool
uv run science-tool verdict --help
```

Expected stdout contains:

```
Usage: science-tool verdict [OPTIONS] COMMAND [ARGS]...

  Parse and roll up verdict-token + atomic-claim frontmatter.

Commands:
  parse
  rollup
```

- [ ] **Step 10.3: Run the full test suite to confirm no regressions**

Run: `cd ~/d/science/science-tool && uv run pytest -q`
Expected: all tests pass (~30+ new verdict tests + existing tests unchanged).

- [ ] **Step 10.4: Commit**

```bash
cd ~/d/science/science-tool
git add src/science_tool/cli.py
git commit -m "feat(cli): register verdict subgroup in top-level science-tool CLI"
```

---

## Task 11: Dogfood on mm30 — parse 9 docs, verify only t163 disagrees

**Files:**
- None created or modified; this is a manual validation step whose output lives in the commit message.

- [ ] **Step 11.1: Parse each of the 9 mm30 atomic-decomposition docs and confirm behavior**

Run (from `~/d/science/science-tool`):

```bash
cd ~/d/science/science-tool
for f in \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-19-t221-literature-gene-lookups.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-14-t197-gse155135-ezh2i-replication.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-19-t234-hopfield-hamming-robustness.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-18-t204-bulk-composition-beyond-pc-maturity-verdict.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-12-t163-prolif-adjusted-tf-edges.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-12-ribosome-regulator-screen-clr.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-21-t099-skerget-transition-matrix.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-21-t240-misund-phf19-trajectory.md \
  /mnt/ssd/Dropbox/r/mm30/doc/interpretations/2026-04-21-t258-phf19-pathway-specificity.md; do
    echo "=== $f ==="
    uv run science-tool verdict parse "$f" | python -c "import sys, json; d = json.load(sys.stdin); print(f\"composite={d['composite_token']} derived={d['rule_derived_composite']} disagrees={d['rule_disagrees_with_body']}\")"
done
```

Expected output:

```
=== .../2026-04-19-t221-literature-gene-lookups.md ===
composite=[~] derived=[~] disagrees=False
=== .../2026-04-14-t197-gse155135-ezh2i-replication.md ===
composite=[~] derived=[~] disagrees=False
=== .../2026-04-19-t234-hopfield-hamming-robustness.md ===
composite=[~] derived=[~] disagrees=False
=== .../2026-04-18-t204-bulk-composition-beyond-pc-maturity-verdict.md ===
composite=[⌀] derived=[⌀] disagrees=False
=== .../2026-04-12-t163-prolif-adjusted-tf-edges.md ===
composite=[~] derived=[-] disagrees=True
=== .../2026-04-12-ribosome-regulator-screen-clr.md ===
composite=[~] derived=[~] disagrees=False
=== .../2026-04-21-t099-skerget-transition-matrix.md ===
composite=[+] derived=[+] disagrees=False
=== .../2026-04-21-t240-misund-phf19-trajectory.md ===
composite=[~] derived=[~] disagrees=False
=== .../2026-04-21-t258-phf19-pathway-specificity.md ===
composite=[+] derived=[+] disagrees=False
```

This is the acceptance harness: exactly one disagreement, on t163.

- [ ] **Step 11.2: Run `rollup --by-claim` on the mm30 interpretations directory**

Run:

```bash
cd ~/d/science/science-tool
uv run science-tool verdict rollup \
  --scope claim \
  --root /mnt/ssd/Dropbox/r/mm30/doc/interpretations \
  --registry /mnt/ssd/Dropbox/r/mm30/specs/claim-registry.yaml \
  --output json | python -m json.tool | head -40
```

Expected: JSON payload with `scope: "claim"`, `n_documents: 9` (the 9 atomic-decomposition docs), and at least these canonical claim IDs present in `groups`:

```
h1-prognosis#edge5-ifn-arm
h1-prognosis#edge6-e2f-arm
t163#edge-ezh2-phf19-survives-prolif-adj
t240#phf19-log2fc-correlates-with-pi-change
...
```

- [ ] **Step 11.3: Run `rollup --scope all` with table output as visual sanity-check**

Run:

```bash
cd ~/d/science/science-tool
uv run science-tool verdict rollup \
  --scope all \
  --root /mnt/ssd/Dropbox/r/mm30/doc/interpretations \
  --output table
```

Expected: rich table showing per-token tally across the 9 atomic-decomposition docs.

- [ ] **Step 11.4: Commit the dogfood-pass receipt**

Create or append to a short receipt file `tests/dogfood_mm30_receipt.md` documenting what was run + expected output:

```markdown
# mm30 dogfood receipt — 2026-04-21

`science-tool verdict parse` + `verdict rollup --by-claim` pass the
acceptance harness on the mm30 corpus:

- 9/9 docs parse cleanly.
- Exactly 1 `rule_disagrees_with_body: true` case, on t163.
- `rollup --by-claim` groups citations under canonical IDs (37-claim
  registry); every doc's claim IDs resolve either directly or via
  synonyms.

See commit for reproduction commands.
```

Commit:

```bash
cd ~/d/science/science-tool
git add tests/dogfood_mm30_receipt.md
git commit -m "test(verdict): mm30 dogfood pass — 9/9 parse, t163 lone disagreement, by-claim rollup works"
```

---

## Task 12: Update the design spec (v1.2 touch-ups)

**Files:**
- Modify: `docs/specs/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md`

- [ ] **Step 12.1: Bump the revision history and acceptance criteria**

Open `docs/specs/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md`. Find the "Revision history" section near the top and add a new entry after the v1.1 entry:

```markdown
- **v1.2 (2026-04-21):** MVP implementation lands in `science-tool`
  (plan: `docs/plans/2026-04-21-verdict-parse-rollup-mvp.md`).
  Three touch-ups from dogfooding experience:
  - Reference the **mm30 `specs/claim-registry.yaml`** (37 canonical
    claims across 4 anchor types: hypothesis, DAG-edge, task,
    article) as the first concrete registry implementation.
  - Mark the `confidence` column in backfill audit TSVs as
    **advisory-only**, per mm30 t246 finding: overall inter-LLM
    agreement on backfill labels is 97%, but per-tier calibration
    is uninformative at realistic sample sizes; the per-claim
    `strength` field (v1.1) carries the same semantic at the right
    resolution.
  - Bump acceptance criterion 6 from "6 reference docs" to "9"
    (mm30 added t099, t240, t258 under the new schema on 2026-04-21).
```

Find the "Status" line at the top of the doc and change:

```markdown
**Status:** rev 1.1 — incorporates 6 schema gaps surfaced in mm30 t243 dogfood
```

to:

```markdown
**Status:** rev 1.2 — MVP parser + rollup landed; v1.1 gaps incorporated; confidence column marked advisory
```

And the `**Revised:**` line:

```markdown
**Revised:** 2026-04-21 (v1.2)
```

- [ ] **Step 12.2: Update acceptance criterion 6**

Find the "Acceptance criteria" section. Change:

```markdown
- [x] mm30 has 6 reference docs authored under the new schema (decomposed `claims:` block) as dogfooding examples. *(done 2026-04-21 per `mm30/discussion:2026-04-19-t243-atomic-decomposition-dogfood`)*
```

to:

```markdown
- [x] mm30 has 9 reference docs authored under the new schema (decomposed `claims:` block) as dogfooding examples — the original 6 (t197, t204, t163, t221, t234, CLR) plus t099, t240, t258 added 2026-04-21 during the MVP-plan authorship loop.
```

Also under v1.0 original acceptance criteria, flip the `verdict parse / verdict rollup` boxes to checked:

```markdown
- [x] `science-tool verdict parse` validates a sample interpretation end-to-end. *(done 2026-04-21 via MVP plan)*
- [x] `science-tool verdict rollup` produces a per-hypothesis verdict distribution table on mm30. *(done 2026-04-21 via MVP plan — per-claim rollup scope)*
```

Under v1.1 additions, flip the following box to checked:

```markdown
- [x] `science-tool verdict parse` correctly emits `rule_disagrees_with_body: true` on the t163 reference doc (the one validation case from the dogfood). *(done 2026-04-21)*
```

- [ ] **Step 12.3: Add the mm30-registry reference paragraph**

Under the "Claim-id registry (v1.1: required-but-permissive)" section, after the existing "Bootstrap helper" block, insert:

```markdown
### First concrete implementation

The mm30 project hosts the first real project-local claim registry
at `specs/claim-registry.yaml` (bootstrapped 2026-04-21, 37
canonical claims across 4 anchor types: hypothesis, DAG-edge, task,
article). The registry includes explicit `synonyms:` entries that
unify three naming styles surfaced in the t243 dogfood (e.g.
`h1-edge6-ifn-arm` in t197 resolves to canonical
`h1-prognosis#edge5-ifn-arm` — catching a real edge-numbering drift
between the interpretation-authored claim ID and the DAG's
authoritative edge list). Projects adopting the convention can copy
the mm30 registry's `conventions:` block (separator `#`, anchor
types, id_pattern regex) as a starting template.
```

- [ ] **Step 12.4: Add the confidence-column advisory note**

Under the `backfill` subcommand section, after the existing code fence, add:

```markdown
**Note on the `confidence` column** (added v1.2): the backfill audit
TSVs produced by this subcommand have historically included a
per-row `confidence` column (subagent self-report, 0.7-0.95). The
mm30 t246 calibration backtest (2026-04-21) found that column
uninformative at realistic sample sizes: overall inter-LLM
agreement on backfill labels was 97.2% across a 36-doc stratified
sample, with no observable per-tier separation. Treat the column
as **advisory-only**; the per-claim `strength` field (v1.1) carries
the same semantic at a better resolution once atomic decomposition
is authored.
```

- [ ] **Step 12.5: Commit**

```bash
cd ~/d/science
git add docs/specs/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md
git commit -m "docs(verdict-spec): v1.2 touch-ups — mm30 registry reference, confidence advisory, 9 dogfood docs"
```

---

## What this MVP leaves out — pickup context for follow-on plans

The MVP ships `verdict parse` + `verdict rollup` (scope: all, claim) +
the rule-aggregation machinery + the claim-registry read path. Seven
spec-defined capabilities are NOT in this plan; each is sized and
described below so a follow-on plan can pick up without losing
context.

### 1. `verdict conflicts` — cross-doc polarity conflict scan

**What it does.** For each registered `question:` or `hypothesis:`
in the project, enumerate all interpretations cited as evidence
(traversing the `related:` lists in both question and interpretation
frontmatter); flag any source whose evidence basket contains both
`[+]` and `[-]` verdicts. This is what the mm30 t245 discussion
hand-emulated on 2026-04-19.

**Why it was not in the MVP.** It requires a cross-entity citation
graph (question → interpretation edges, hypothesis → interpretation
edges), not just a flat directory walk. The project-specific
convention for where those citations live (frontmatter `related:`
arrays? a separate graph.trig file? both?) varies across projects.
The MVP's `rollup` operates on flat directory walks only.

**Pickup suggestions.** (a) Decide on the citation-graph source:
frontmatter `related:` arrays are the simplest and most universal.
(b) Implement `build_citation_graph(project_root) -> dict[str,
list[str]]`. (c) For each group key from `rollup`, check whether
its associated interpretations' composite tokens contain both `[+]`
and `[-]`. (d) Emit a one-line-per-conflict JSON/table output. Reference
the t245 discussion doc in mm30 for the shape of real output on a
non-trivial corpus.

### 2. `verdict coverage` — confirmation-bias detector

**What it does.** Per-hypothesis polarity distribution across all
cited evidence. Flag any hypothesis with ≥5 evidence docs AND 100%
one-polarity verdicts as a confirmation-bias candidate. (The mm30
t245 found H4 was at 6/6 `[+]/[~]` with zero `[-]` — that's the
archetype flag; t099 2026-04-21 added the first `[-]`/`-` evidence
line against strict H2 block-diagonal, partially resolving the flag.)

**Why it was not in the MVP.** Same citation-graph dependency as
`conflicts`. The coverage logic itself is a counter + threshold, but
it needs the same graph build step.

**Pickup suggestions.** Share the citation-graph loader with
`conflicts`. Thresholds (`--min-evidence`, `--max-single-polarity-pct`)
should be CLI options with documented defaults (suggest `--min-evidence 5`,
`--max-pct 1.0`). Output: one row per flagged hypothesis with
polarity tally + count + flag reason.

### 3. `verdict watchlist` — single-anchor `[-]` surfacing

**What it does.** For every `[-]` verdict in the corpus, check whether
it is the ONLY `[-]` on its associated question. Single-anchor
negative verdicts are vulnerable to flipping with one new study;
surfacing them prioritizes replication targets.

**Why it was not in the MVP.** Same citation-graph dependency. Also
requires a "associated question" linkage for each interpretation,
which is less consistently encoded than interpretation ↔ hypothesis.

**Pickup suggestions.** Ship after `conflicts` + `coverage`; the
citation-graph infrastructure amortizes. The output should include
the anchoring interpretation's ID, the question it addresses, and
a suggested replication target (e.g., the closest related existing
dataset, if the project graph encodes dataset references).

### 4. `verdict registry-init --scan doc/interpretations/` — bootstrap helper

**What it does.** Walk all interpretations in a project, collect
every distinct claim ID from their `verdict.claims:` blocks, and
write a stub `specs/claim-registry.yaml` with `definition: TBD`
placeholders. Project owners then hand-curate the placeholders into
real definitions + canonicalize synonyms.

**Why it was not in the MVP.** The MVP expects the registry to
already exist (hand-bootstrapped, as mm30's was). `registry-init`
is how OTHER projects bring the schema up; mm30's already there.
Implementing it now would ship a code path with no dogfooding cohort.

**Pickup suggestions.** The implementation is mechanically simple
— walk + collect IDs via the MVP's `walk_interpretations` function,
group by inferred anchor type (regex: `h[1-6]` → hypothesis,
`t\d+` → task, `[a-z]+\d{4}` → article), write YAML with TBD
placeholders. The interesting design question is: how should
`registry-init` handle claim IDs that are synonyms of each other
(two different name styles for the same claim)? mm30's registry
resolved these by hand; the tool could propose synonyms based on
string similarity but should NOT auto-merge without confirmation.

### 5. `verdict reframed-trail <interpretation-id>` — chain walker

**What it does.** Follow the `reframing_target:` links from a given
interpretation back through the chain of reframings (an
interpretation `X` with `reframing_target: Y` means `X` reframes
`Y`; `Y` might itself have `reframing_target: Z`; etc.). Produce
the chain of interpretations + a short rationale per step (from each
`reframing_reason:`).

**Why it was not in the MVP.** The mm30 corpus has exactly ONE
reframed-trail case (the CLR doc → t149), which doesn't exercise a
multi-step chain. Implementing it for a single-step case is a thin
wrapper that would need re-testing when a multi-step chain appears.
Parse + rollup is already sufficient for the existing case.

**Pickup suggestions.** Implement when a second mm30 reframing lands
(or in another project). The graph walk is straightforward (BFS
with cycle detection). Output format: nested JSON or a markdown
trail with dates and short clauses.

### 6. `verdict backfill --project <path>` — LLM classifier helper

**What it does.** Reads interpretation docs that have no `## Verdict`
line, dispatches an LLM classifier with the 5-token rubric (and the
atomic-decomposition schema), writes an audit TSV of proposed labels
+ clauses + per-doc confidences, leaves edits as a diff for human
review. This is the programmatic form of the 2026-04-19
cross-project backfill that was done by hand (8 subagent dispatches
across 6 projects).

**Why it was not in the MVP.** `backfill` requires subagent or LLM
API dispatch, which is a larger architectural commitment than the
pure-parser MVP. It also intersects with the project's ongoing
backfill methodology (already-run for 6 projects on 2026-04-19), so
the right interface depends on what "the backfill workflow" looks
like going forward.

**Pickup suggestions.** (a) Decide: in-tool LLM API calls (needs an
API-key auth layer) or subagent dispatch via a Claude-Code-style
runner? (b) If LLM API: Anthropic SDK calls with prompt caching for
the rubric; ~6-9 cents per doc at claude-haiku-4-5 pricing. (c)
Per-project `~/.science-tool/backfill/config.yaml` with rubric +
model choice. (d) Based on the t246 finding (confidence column is
advisory-only), consider removing the `confidence` column from the
output TSV or renaming it to `subagent_self_report_confidence` to
make its advisory status obvious.

### 7. `big-picture` integration — consume rollup output

**What it does.** `science:big-picture` already produces per-
hypothesis rollups. With `verdict rollup` now structured, the
big-picture workflow should consume the structured output and
surface polarity distributions as a column alongside existing
hypothesis-status fields.

**Why it was not in the MVP.** `big-picture` lives in
`src/science_tool/big_picture/` (separate sub-package). Integrating
the two is a straightforward data-plumbing task but it couples the
two subsystems' release cycles. Ship the standalone `verdict rollup`
first; wire big-picture afterward.

**Pickup suggestions.** Add `from science_tool.verdict.rollup import
walk_interpretations, group_by, tally_polarities` inside
`big_picture/generator.py` (or wherever the per-hypothesis rollup
currently lives). Extend the big-picture report schema with a
`verdict_distribution:` field per hypothesis entry.

### 8. `members:` claim subfield resolution + aggregation

**What it does.** The v1.1 `members:` subfield (spec gap 4) lets a
grouped claim (e.g., `h4#attractors-multi-sample-non-singletons-robustness`)
list the individual member-claim IDs it groups. The spec's v1.1
acceptance criterion states: `members:` "resolves to the listed
member-claim IDs and aggregates their per-member polarity (when
those members are themselves registered claims)."

**Why it was not in the MVP.** The parser HYDRATES the `members:`
list into `Claim.members` (Task 2's `Claim` dataclass includes the
field), but no aggregation step in the MVP consumes it. The
semantically-correct aggregation requires: (a) looking up each
member-claim ID in the registry, (b) deciding whether member
polarities override the grouped claim's declared polarity (spec is
ambiguous — the v1.1 text says "aggregates" without specifying
how). Resolving this requires additional spec work, not just code.

**Pickup suggestions.** Before implementing, propose a spec v1.3
revision that specifies: does `members:` imply the grouped claim's
polarity MUST equal the aggregate of member polarities? Or is it
documentation-only? The mm30 registry's
`h4#attractors-multi-sample-non-singletons-robustness` uses
`members:` as documentation (lists the 4 individual attractor IDs
that share the grouped result); no code aggregation is needed
there. A real aggregation use case hasn't emerged yet.

### 9. natural-systems-guide reference doc under the new schema

**What it does.** The spec's acceptance criterion list includes:
"natural-systems-guide has at least one reference doc authored
under the new schema." This is cross-project dogfooding; mm30
has 9 such docs now, NS has zero.

**Why it was not in the MVP.** NS is a separate project that
hasn't adopted the atomic decomposition yet; pushing the schema
onto a project without the author's ownership is anti-pattern.
The MVP establishes the schema is implementable (via mm30's 9
dogfood docs); the NS adoption is a followup coordinated with
that project's owner.

**Pickup suggestions.** Natural candidates: NS's per-theme kappa
docs (multiple findings with agreement/disagreement per tier) map
cleanly onto `majority` rule with per-tier atomic claims. See the
spec's "Reference use cases" table row for `natural-systems
2026-03-30-t092-per-theme-kappa.md`. Open a PR in that project
with one reference doc + the same `specs/claim-registry.yaml`
bootstrap pattern mm30 used.

### 10. Posterior P(verdict), claim-graph belief propagation, calibration framework

The spec's "Out of scope (deferred to follow-on specs)" section
lists these as explicitly out-of-scope for ALL verdict-token work,
not just this MVP. Each is a separate spec of its own (see mm30
tasks t248 and t249 for the Bayesian meta-analysis + belief-
propagation work, and mm30 t246's calibration discussion for the
calibration-framework precursor). Not in the pickup queue for the
current spec lineage.

---

## Reference pointers for the executing engineer

- **Spec (authoritative):** `~/d/science/docs/specs/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md`
- **mm30 claim registry (real-world example):** `/mnt/ssd/Dropbox/r/mm30/specs/claim-registry.yaml`
- **mm30 9 atomic-decomposition docs (real-world fixtures):**
  `doc/interpretations/2026-04-19-t221-literature-gene-lookups.md`,
  `2026-04-14-t197-gse155135-ezh2i-replication.md`,
  `2026-04-19-t234-hopfield-hamming-robustness.md`,
  `2026-04-18-t204-bulk-composition-beyond-pc-maturity-verdict.md`,
  `2026-04-12-t163-prolif-adjusted-tf-edges.md` (the `rule_disagrees_with_body` case),
  `2026-04-12-ribosome-regulator-screen-clr.md`,
  `2026-04-21-t099-skerget-transition-matrix.md`,
  `2026-04-21-t240-misund-phf19-trajectory.md`,
  `2026-04-21-t258-phf19-pathway-specificity.md`.
- **Hand-emulated conflict/coverage scan (target for Task 11 rollup output):**
  `/mnt/ssd/Dropbox/r/mm30/doc/discussions/2026-04-19-verdict-conflict-coverage-scan.md`
- **Dogfood discussion (schema validation on real docs):**
  `/mnt/ssd/Dropbox/r/mm30/doc/discussions/2026-04-19-t243-atomic-decomposition-dogfood.md`
- **Calibration backtest (advisory-only finding for confidence column):**
  `/mnt/ssd/Dropbox/r/mm30/doc/discussions/2026-04-21-t246-verdict-confidence-calibration.md`
