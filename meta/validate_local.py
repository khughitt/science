from collections.abc import Iterable
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext, hook

RULE = "evidence-payloads"
TASK = "task:t034"


@hook("extra_checks")
def check_t034_evidence_payloads(ctx: ValidateContext) -> Iterable[Result]:
    from t034_validator import validate_payload
    from t034_validator.loader import load_directory

    evidence_dir = ctx.project_root / "evidence"
    store, load_errors = load_directory(evidence_dir)
    all_issues = []
    for payload_id in sorted(store.payloads):
        all_issues.extend(validate_payload(store, payload_id))

    for issue in all_issues:
        severity = Severity.ERROR if issue.severity == "error" else Severity.WARN
        yield Result(severity, Path("evidence"), None, str(issue), RULE, TASK)
    for error in load_errors:
        yield Result(Severity.ERROR, Path("evidence"), None, f"LOAD {error}", RULE, TASK)

    n_errors = sum(1 for issue in all_issues if issue.severity == "error")
    yield Result(
        Severity.INFO,
        Path("evidence"),
        None,
        f"t034: {len(store.payloads)} payload(s), {n_errors} error(s), {len(load_errors)} load error(s)",
        RULE,
        TASK,
    )
