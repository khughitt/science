"""`<kind>.unbacked-inverse` — asserted THROUGH the runner, never through a direct call.

A check module is inert until it is BOTH decorated and imported. `@Check` is what appends to
`CANONICAL_CHECKS`, and `_load_canonical_checks` — which iterates `CANONICAL_CHECK_MODULES` — is the
only thing that *imports* the module, and therefore the only thing that ever *runs* the decorator.
Decorated-but-unlisted = never registered = never run.

So the assertion travels the path a **user** travels. A direct `check_supersession(ctx)` call cannot
tell a registered check from an unregistered one — and an unregistered check is the entire defect.

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


def test_the_check_is_REGISTERED_and_fires_through_the_runner(tmp_path: Path) -> None:
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
