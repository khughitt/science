"""Import-cycle guards.

Every assertion here runs in a FRESH interpreter. Written as an in-process import,
each would probe the safe direction -- and under pytest would be worse than useless,
since collection has almost certainly imported one side already and `sys.modules`
returns a hit without executing anything. A cycle test that shares a process with
its own test runner tests the runner's import order.
"""

from __future__ import annotations

import subprocess
import sys


def _fresh(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )


def test_evidence_broker_imports_in_a_fresh_interpreter() -> None:
    result = _fresh("import science_model.evidence_broker")
    assert result.returncode == 0, result.stderr


def test_correspondence_leaf_imports_in_a_fresh_interpreter() -> None:
    result = _fresh("import science_model.correspondence")
    assert result.returncode == 0, result.stderr
