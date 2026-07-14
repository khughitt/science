"""`<kind>.unbacked-inverse` — WIRING, asserted through the runner. **Not a registration guard.**

The assertion travels the path a **user** travels: `runner.run` over a real project, not a direct
`check_supersession(ctx)` call against a hand-built context. That proves the check is reachable from
the real entry point and fires on real input — which is worth proving, and is all this file proves.

☠️ IT IS NOT THE GUARD THAT CATCHES AN UNLISTED MODULE, and believing otherwise is how one goes
missing. `@Check` registers **as an import side effect**, so *any* file in the pytest process that
imports `checks.supersession` registers the check no matter what `CANONICAL_CHECK_MODULES` says.
Established by mutation — drop `"supersession"` from the tuple and run:

    pytest tests/validate/test_check_supersession.py                     -> FAILS (catches it)
    pytest <any file importing the module> tests/validate/test_check...   -> 3 PASSED (blind)

This file imports only `runner`, deliberately, so today it does catch an unregistration. That is an
accident of nobody else importing the module — a guard by luck, which decays into a wiring test the
day someone adds the import, and decays **silently**. The real guard is structural and already
covers this module: `test_check_registry_is_complete.py::test_EVERY_check_module_on_disk_is_REGISTERED`
compares the *directory* to the tuple and reads no registry state, so no import can contaminate it.

`interpretation` is the kind used throughout: it can carry the field TODAY, so no migration and no
version pin are in play, and it stays WARN through Task 12 (where it is the uncertified-kind
control).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate import runner
from science_tool.validate.result import Severity


def _write(root: Path, name: str, fm: dict) -> None:
    path = root / "entities" / "interpretations" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump({"title": name, **fm}, sort_keys=False) + "---\n\nbody\n",
        encoding="utf-8",
    )


def _supersedes(target: str) -> dict[str, str]:
    return {"predicate": "sci:supersedes", "target": target}


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: sup\n", encoding="utf-8")


def _results(root: Path) -> list:
    return list(runner.run(root, strict=False, verbose=False).results)


def test_a_registered_check_fires_through_the_runner(tmp_path: Path) -> None:
    _seed(tmp_path)
    # `i1` claims `i2` superseded it. `i2` exists and resolves -- and grounds nothing: there is no
    # `sci:supersedes` edge anywhere in the corpus.
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation",
                            "status": "superseded", "superseded_by": "interpretation:i2"})
    _write(tmp_path, "i2", {"id": "interpretation:i2", "kind": "interpretation"})

    findings = [r for r in _results(tmp_path) if r.rule == "interpretation.unbacked-inverse"]

    assert len(findings) == 1
    assert findings[0].severity is Severity.WARN
    assert findings[0].path == tmp_path / "entities/interpretations/i1.md"


def test_a_BACKED_inverse_is_silent(tmp_path: Path) -> None:
    # The control that makes the check falsifiable. SAME corpus, one edge added -- and the finding
    # has to disappear, or the rule is just "any superseded_by is a finding" wearing a better name.
    _seed(tmp_path)
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation",
                            "status": "superseded", "superseded_by": "interpretation:i2"})
    _write(tmp_path, "i2", {"id": "interpretation:i2", "kind": "interpretation",
                            "relations": [_supersedes("interpretation:i1")]})

    assert [r for r in _results(tmp_path) if r.rule.endswith(".unbacked-inverse")] == []


# ---------------------------------------------------------------------------------------------
# the edges that are not edges — ERROR, because `materialize` REFUSES TO BUILD A GRAPH over them
# ---------------------------------------------------------------------------------------------
#
# `mark_superseded` already blocks on both. But it is OPT-IN, and `validate` is the pass everyone
# runs: a corpus can carry either of these forever and never once run the consolidation command.
# ERROR rather than WARN, and flat rather than kind-scoped, because the verdict comes from the
# RELATION MODEL -- `materialize` raises -- and not from any kind's status vocabulary. Nothing here
# waits on Task 12's per-kind ratchet.


def _dataset(root: Path, name: str) -> None:
    path = root / "entities" / "datasets" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump({"id": f"dataset:{name}", "kind": "dataset", "title": name})
        + "---\n\nbody\n",
        encoding="utf-8",
    )


def _rules(root: Path) -> list[str]:
    return [r.rule for r in _results(root)]


def test_a_SELF_SUPERSESSION_is_an_ERROR_through_the_runner(tmp_path: Path) -> None:
    # `materialize` raises `self-referential authored relation` on this corpus, so it does not build
    # a graph -- and before this rule existed, `validate` said NOTHING about it.
    _seed(tmp_path)
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation",
                            "relations": [_supersedes("interpretation:i1")]})

    findings = [r for r in _results(tmp_path) if r.rule == "supersession.self-referential"]

    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert findings[0].path == tmp_path / "entities/interpretations/i1.md"


def test_an_ILLEGAL_KIND_PAIR_is_an_ERROR_through_the_runner(tmp_path: Path) -> None:
    # `interpretation -> dataset` is not an allowed `sci:supersedes` pair. Reported against the file
    # that AUTHORED the edge -- the superseder -- because that is the line that has to change.
    _seed(tmp_path)
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation",
                            "relations": [_supersedes("dataset:d")]})
    _dataset(tmp_path, "d")

    findings = [r for r in _results(tmp_path) if r.rule == "supersession.illegal-kind-pair"]

    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert findings[0].path == tmp_path / "entities/interpretations/i1.md"


def test_a_LEGAL_CHAIN_raises_NEITHER_relation_validity_ERROR(tmp_path: Path) -> None:
    # THE CONTROL that makes both rules falsifiable. An ordinary, valid, fully-reconciled chain --
    # legal pair, no self-edge, inverse backed by its edge. If either ERROR fires here, the rule is
    # "any sci:supersedes edge is a finding" wearing a better name.
    _seed(tmp_path)
    _write(tmp_path, "i1", {"id": "interpretation:i1", "kind": "interpretation",
                            "status": "superseded", "superseded_by": "interpretation:i2"})
    _write(tmp_path, "i2", {"id": "interpretation:i2", "kind": "interpretation",
                            "relations": [_supersedes("interpretation:i1")]})

    rules = _rules(tmp_path)

    assert "supersession.self-referential" not in rules
    assert "supersession.illegal-kind-pair" not in rules
    assert not [r for r in rules if r.endswith(".unbacked-inverse")]
