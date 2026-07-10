"""Render a StochasticityReport as human lines or a JSON-ready dict."""

from __future__ import annotations

from science_tool.datasets_stochasticity import StochasticityReport


def render_json(report: StochasticityReport) -> dict:
    return {
        "dataset_id": report.dataset_id,
        "run_id": report.run_id,
        "named_run_id": report.named_run_id,
        "inherited": report.inherited,
        "chain": report.chain,
        "seed_policy_kind": report.seed_policy_kind,
        "deterministic_step_count": report.deterministic_step_count,
        "unresolved_reason": report.unresolved_reason,
        "stochastic_steps": [
            {
                "step_id": s.step_id,
                "method_id": s.method_id,
                "stochasticity": s.stochasticity.value if s.stochasticity is not None else None,
                "realized_seeds": s.realized_seeds,
                "rationale": s.rationale,
            }
            for s in report.stochastic_steps
        ],
    }


def render_human(report: StochasticityReport) -> list[str]:
    lines: list[str] = []
    if report.run_id is None:
        if report.named_run_id is not None:
            lines.append(
                f"{report.dataset_id}: resolves to {report.named_run_id}, but it is not "
                f"fingerprinted ({report.unresolved_reason})"
            )
        else:
            lines.append(f"{report.dataset_id}: no fingerprinted run ({report.unresolved_reason})")
        return lines

    suffix = " (inherited)" if report.inherited else ""
    lines.append(f"run: {report.run_id}{suffix}")
    if report.inherited:
        lines.append("  " + " <- member_of <- ".join(report.chain))
    lines.append(f"seed policy: {report.seed_policy_kind}")
    lines.append("")

    total = len(report.stochastic_steps) + report.deterministic_step_count
    lines.append(f"stochastic steps ({len(report.stochastic_steps)} of {total}):")
    for s in report.stochastic_steps:
        klass = s.stochasticity.value if s.stochasticity is not None else "unclassified"
        seeds = ", ".join(f"{k}={v}" for k, v in sorted(s.realized_seeds.items())) or "no realized seed"
        line = f"  {s.step_id}  {klass}  {seeds}"
        if s.stochasticity is not None and s.stochasticity.value == "nondeterministic":
            line += " - not exactly reproducible" + (f": {s.rationale}" if s.rationale else "")
        lines.append(line)
    if report.deterministic_step_count:
        lines.append(f"deterministic steps: {report.deterministic_step_count} (omitted)")
    return lines
