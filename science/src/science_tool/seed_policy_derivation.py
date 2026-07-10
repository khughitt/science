"""Derive `seed_policy` from a workflow's steps (umbrella Spec 2, task:t088).

Pure: no filesystem, no reference resolution, no graph. The caller
(`persist_run_fingerprint`) resolves each step's `method:` ref and passes the
resolved entities in. A step missing from `method_for_step` is an unresolved or
wrong-kind reference, and raises.
"""

from __future__ import annotations

from typing import Any

from science_model.entities import MethodEntity, Stochasticity, WorkflowStepEntity
from science_model.run_fingerprint import SeedPolicy

_PREFIX = "register-run cannot derive seed_policy:"


class SeedPolicyDerivationError(Exception):
    """Raised when a workflow's steps do not determine a seed_policy."""


def _realize(
    source: str,
    config: dict[str, Any],
    config_path: str,
    step: WorkflowStepEntity,
    param: str,
) -> int:
    if source.startswith("literal:"):
        # The model's seed_bindings validator already enforces
        # `^literal:-?\d+\Z`, so this int() call cannot raise.
        return int(source.removeprefix("literal:"))

    if source.startswith("config."):
        dotted_key = source.removeprefix("config.")
        value: Any = config
        for part in dotted_key.split("."):
            if not isinstance(value, dict) or part not in value:
                raise SeedPolicyDerivationError(
                    f"{_PREFIX} {step.id} binds {param!r} to {source!r}, but the "
                    f"config snapshot {config_path} has no key {dotted_key!r}."
                )
            value = value[part]
        if isinstance(value, bool) or not isinstance(value, int):
            raise SeedPolicyDerivationError(
                f"{_PREFIX} {step.id} binds {param!r} to {source!r}, but "
                f"{config_path} key {dotted_key!r} is {value!r}, which is not an integer."
            )
        return value

    # Unreachable: the model's seed_bindings validator rejects any source that
    # is neither `literal:`- nor `config.`-prefixed. Raise anyway rather than
    # fall through to a silent default.
    raise SeedPolicyDerivationError(
        f"{_PREFIX} {step.id} binds {param!r} to {source!r}, which is neither "
        f"`literal:`- nor `config.`-prefixed. Fix the seed_binding source in {step.file_path}."
    )


def derive_seed_policy(
    *,
    workflow_id: str,
    steps: list[WorkflowStepEntity],
    method_for_step: dict[str, MethodEntity],
    config: dict[str, Any],
    config_path: str,
) -> tuple[SeedPolicy, dict[str, dict[str, int]]]:
    if not steps:
        raise SeedPolicyDerivationError(
            f"{_PREFIX} {workflow_id} has no workflow-step. Declare at least one "
            f"step (with `workflow: {workflow_id}`) before registering a run."
        )

    ordered_steps = sorted(steps, key=lambda s: s.id)

    resolved: list[tuple[WorkflowStepEntity, MethodEntity]] = []
    for step in ordered_steps:
        if not step.method:
            raise SeedPolicyDerivationError(
                f"{_PREFIX} {step.id} declares no method. Add `method: method:<slug>` "
                f"to {step.file_path}."
            )
        if step.id not in method_for_step:
            raise SeedPolicyDerivationError(
                f"{_PREFIX} {step.id} references {step.method!r}, which does not "
                f"resolve to a method entity."
            )
        method = method_for_step[step.id]
        if method.stochasticity is None:
            raise SeedPolicyDerivationError(
                f"{_PREFIX} {method.id} has no stochasticity. Add `stochasticity: "
                f"deterministic|seedable|nondeterministic` to {method.file_path}."
            )
        resolved.append((step, method))

    nondet: list[tuple[WorkflowStepEntity, MethodEntity]] = []
    unbound: list[tuple[WorkflowStepEntity, MethodEntity, str]] = []
    paramless: list[tuple[WorkflowStepEntity, MethodEntity]] = []
    seedable_present = False

    for step, method in resolved:
        if method.stochasticity is Stochasticity.NONDETERMINISTIC:
            nondet.append((step, method))
        elif method.stochasticity is Stochasticity.SEEDABLE:
            seedable_present = True
            if not method.seed_params:
                paramless.append((step, method))
            else:
                for param in method.seed_params:
                    if param not in step.seed_bindings:
                        unbound.append((step, method, param))

    step_seeds: dict[str, dict[str, int]] = {}
    for step, method in resolved:
        # A deterministic method contributes no seeds even when its step carries
        # bindings (validate warns on that). This is what keeps `deterministic =>
        # empty step_seeds` true even for a deterministic method that declares
        # seed_params, which Spec 1 permits.
        if method.stochasticity is Stochasticity.DETERMINISTIC:
            continue
        seeds = {
            param: _realize(source, config, config_path, step, param)
            for param, source in step.seed_bindings.items()
            if param in method.seed_params
        }
        if seeds:
            step_seeds[step.id] = seeds

    if nondet or unbound or paramless:
        parts = [f"{s.id} applies {m.id}, which is nondeterministic" for s, m in nondet]
        parts += [f"{s.id} leaves {m.id} seed_param {p!r} unbound" for s, m, p in unbound]
        parts += [
            f"{s.id} applies seedable {m.id}, which declares no seed_params"
            for s, m in paramless
        ]
        rationale = "; ".join(sorted(parts))
        return SeedPolicy(kind="stochastic-unseeded", rationale=rationale), step_seeds

    if seedable_present:
        return SeedPolicy(kind="seeded"), step_seeds

    return SeedPolicy(kind="deterministic"), step_seeds
