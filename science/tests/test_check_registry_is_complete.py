"""The registry guard: a check module that is not REGISTERED never runs, and every test still passes.

Writing `verdict_agreement.py` does not enable it. `validate` runs only what
`CANONICAL_CHECK_MODULES` names (`checks/__init__.py`): `_load_canonical_checks` imports each listed
module, and the `@Check` decorator appends to `CANONICAL_CHECKS` **as an import side effect**. A
module nobody imports registers nothing.

The registry fails **loud** in one direction (listed-but-missing → `ModuleNotFoundError` at import,
which breaks the entire package) and **silent** in the other (present-but-unlisted → never runs).
Only the silent direction needs a guard.

☠️ **AND ONLY ONE OF THE TWO TESTS BELOW CAN BE THAT GUARD.** This was established by mutation, not
by argument. Unregister `verdict_agreement` and run:

    pytest tests/test_check_registry_is_complete.py                       -> BOTH tests fail
    pytest tests/test_verdict_agreement.py tests/test_check_registry...   -> only the FIRST fails

`test_verdict_agreement.py` imports the check module to reach `check_verdict_agreement`. **That
import runs the decorator**, registering the check inside the shared pytest process — so by the time
the end-to-end test calls `runner.run`, the check is registered no matter what the tuple says. In
the full suite, which always contains both files, an end-to-end test can NEVER catch an
unregistration. It is order-dependent, and its green reads as coverage it does not have.

So the two tests below prove **different things**, and the names say which:

* `test_EVERY_check_module_on_disk_is_REGISTERED` is **the guard**. It compares the directory to the
  tuple and touches no import state, so no other test can contaminate it. It is derived from the
  **filesystem, not from a list** — a guard that enumerates its own scope has a hole by
  construction, which is the very hole it would be closing.
* `test_a_registered_check_REACHES_a_real_project` is a **wiring** test, not a registration guard:
  it proves that a registered check, run through the real entry point over a real materialized
  graph, actually reaches a hypothesis and emits its rule. That is worth having. It is simply not
  the thing that catches an unlisted module.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate import runner


def test_EVERY_check_module_on_disk_is_REGISTERED() -> None:
    # THE GUARD. Immune to import order by construction: disk vs. tuple, no registry state read.
    from science_tool.validate import checks

    on_disk = {
        path.stem
        for path in Path(checks.__file__).parent.glob("*.py")
        if path.stem != "__init__"
    }
    assert on_disk == set(checks.CANONICAL_CHECK_MODULES), (
        f"unregistered: {sorted(on_disk - set(checks.CANONICAL_CHECK_MODULES))}; "
        f"listed but absent: {sorted(set(checks.CANONICAL_CHECK_MODULES) - on_disk)}"
    )


def test_a_registered_check_REACHES_a_real_project(tmp_path: Path) -> None:
    """Wiring, end to end: `runner.run` -> the graph -> the check -> a rule on a real hypothesis.

    NOT a registration guard — see this module's docstring. It proves the other half: that the check
    is reachable from the real entry point and fires on real materialized input, rather than only
    when a test hands it a hand-built context.

    The check reads `knowledge/graph.trig`. Writing source alone leaves the graph absent and the
    check correctly emitting NOTHING, so the artifact is built first — otherwise this test would go
    green without ever exercising the verdict surface.
    """
    from science_tool.graph.materialize import materialize_graph

    (tmp_path / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "id": "demo"}), encoding="utf-8"
    )
    hypotheses = tmp_path / "entities" / "hypotheses"
    hypotheses.mkdir(parents=True)
    (hypotheses / "0001-x.md").write_text(
        "---\n"
        "id: hypothesis:0001-x\n"
        "kind: hypothesis\n"
        "title: x\n"
        "created: 2026-07-13\n"
        "updated: 2026-07-13\n"
        "status: complete\n"
        "verdict: supported\n"          # authored, and nothing behind it
        "---\n\n# x\n",
        encoding="utf-8",
    )

    assert materialize_graph(tmp_path).is_file()      # prove the check has something to read

    rules = {result.rule_id for result in runner.run(tmp_path, strict=False, verbose=False).results}
    assert "verdict.missing-basis" in rules
