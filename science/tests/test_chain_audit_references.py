"""Tests for reference auditing of chain, audits, and proposition_refs fields."""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _audit_rows(project: Path):
    rows, _has_failures = audit_project_sources(load_project_sources(project))
    return rows


def _project_with_dangling_chain_link(tmp_path: Path) -> Path:
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")
    # mechanism:a exists; mechanism:b does NOT -- this is the dangling ref.
    _write(
        tmp_path,
        "doc/mechanisms/a.md",
        """---
id: mechanism:a
kind: mechanism
title: "A"
project: test
summary: "A summary."
ontology_terms: []
related: []
source_refs: []
participants:
  - meta:participant-1
  - meta:participant-2
propositions:
  - meta:proposition
---
""",
    )
    _write(
        tmp_path,
        "doc/chains/ab.md",
        """---
id: chain:ab
kind: structural-chain
title: "AB chain"
project: test
ontology_terms: []
related: []
source_refs: []
chain:
  - mechanism:a
  - mechanism:b
---
""",
    )
    return tmp_path


def test_dangling_chain_link_surfaces_in_audit(tmp_path: Path) -> None:
    project = _project_with_dangling_chain_link(tmp_path)
    rows = _audit_rows(project)
    dangling = [
        row
        for row in rows
        if row["status"] == "fail"
        and row["source"] == "chain:ab"
        and row["field"] == "chain"
        and row["target"] == "mechanism:b"
    ]
    assert dangling, f"expected dangling-ref row for mechanism:b, got {rows!r}"


def test_dangling_audits_ref_surfaces(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")
    _write(
        tmp_path,
        "doc/audits/x.md",
        """---
id: chain-audit:x
kind: chain-audit
title: "X audit"
project: test
ontology_terms: []
related: []
source_refs: []
audits: chain:does-not-exist
proposition_refs: []
bayes_factor_evidence:
  hypothesis_ref: hypothesis:foo
  null_baseline: uniform
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:x
      polarity: "[-]"
---
""",
    )
    rows = _audit_rows(tmp_path)
    assert any(
        row["status"] == "fail"
        and row["source"] == "chain-audit:x"
        and row["field"] == "audits"
        and row["target"] == "chain:does-not-exist"
        for row in rows
    )


def test_dangling_proposition_ref_in_chain_audit_surfaces(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")
    _write(
        tmp_path,
        "doc/chains/abc.md",
        """---
id: chain:abc
kind: structural-chain
title: "ABC"
project: test
ontology_terms: []
related: []
source_refs: []
chain:
  - mechanism:a
  - mechanism:b
---
""",
    )
    for slug in ("a", "b"):
        _write(
            tmp_path,
            f"doc/mechanisms/{slug}.md",
            f"""---
id: mechanism:{slug}
kind: mechanism
title: "{slug.upper()}"
project: test
summary: "{slug.upper()} summary."
ontology_terms: []
related: []
source_refs: []
participants:
  - meta:participant-1
  - meta:participant-2
propositions:
  - meta:proposition
---
""",
        )
    _write(
        tmp_path,
        "doc/audits/abc.md",
        """---
id: chain-audit:abc
kind: chain-audit
title: "ABC audit"
project: test
ontology_terms: []
related: []
source_refs: []
audits: chain:abc
proposition_refs:
  - proposition:does-not-exist
bayes_factor_evidence:
  hypothesis_ref: hypothesis:foo
  null_baseline: uniform
  interpretation: evidence-against
verdict:
  composite: "[-]"
  rule: single-claim
  claims:
    - id: claim:x
      polarity: "[-]"
---
""",
    )
    rows = _audit_rows(tmp_path)
    assert any(
        row["status"] == "fail"
        and row["source"] == "chain-audit:abc"
        and row["field"] == "proposition_refs"
        and row["target"] == "proposition:does-not-exist"
        for row in rows
    )
