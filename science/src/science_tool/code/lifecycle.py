"""The code-file lifecycle status vocabulary (umbrella design §6).

`status` is authored in the `# science:code` block and validated as a WARN
`Result` by the code-files check — never enforced on the CodeFileEntity model,
so an unrecognized value cannot hard-fail `graph materialize` (the §6 fragility
firewall). `exploratory` is the pressure-release valve: exempt from
workflow-ownership gating (Tier 2, Plan B2) but never from registration.
"""

from __future__ import annotations

CODE_FILE_STATUSES: frozenset[str] = frozenset(
    {
        "exploratory",
        "workflow-owned",
        "library",
        "retired",
    }
)
