"""Resolve a dataset NODE to the fingerprinted workflow-run(s) that produced it.

Operates on the materialized graph, not on entity objects: run resolution is
graph-phase, where `DatasetEntity` instances do not exist. Reads the derivation
triples emitted by `materialize._add_derivation_edges`.

Two helpers, deliberately:

* `own_derivation_run` answers "does THIS dataset's own derivation edge name a
  run?" and returns None for `member_of`, because a membership edge is not
  run-produced.
* `resolved_empirical_runs` walks `member_of` to the parent chain and is what
  evidence validation uses.

Collapsing them would smuggle the edge-level exemption into evidence resolution.
Neither reads the disk. Recipe provenance is not a run; code provenance is not a
run either; and a run without a fingerprint is not a fingerprinted run.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from rdflib import Graph, URIRef

from science_tool.graph.io import SCI_NS

KIND_WORKFLOW_RUN = "workflow-run"
KIND_WORKFLOW_RECIPE = "workflow-recipe"
KIND_MEMBER_OF = "member_of"


class MemberOfCycleError(Exception):
    """A member_of parent chain revisits a dataset."""


class NoRunReason(StrEnum):
    RECIPE_ONLY = "recipe-only"
    RUN_UNFINGERPRINTED = "run-unfingerprinted"
    CODE_ONLY_NO_RUN = "code-only-no-run"
    NO_PROVENANCE = "no-provenance"


def _derivation_kind(knowledge: Graph, dataset: URIRef) -> str | None:
    value = knowledge.value(dataset, SCI_NS.derivationKind)
    return None if value is None else str(value)


def own_derivation_run(knowledge: Graph, dataset: URIRef) -> URIRef | None:
    """The run named by this dataset's OWN derivation edge, or None."""
    if _derivation_kind(knowledge, dataset) != KIND_WORKFLOW_RUN:
        return None
    return cast("URIRef | None", knowledge.value(dataset, SCI_NS.workflowRun))


@dataclass(frozen=True)
class RunChainResolution:
    """A dataset's resolution to a fingerprinted run, with the chain walked.

    `chain` runs from the queried dataset (index 0) down to the dataset whose
    own derivation named `run`. `len(chain) > 1` means the run was inherited
    through `member_of` and the caller must display the chain so a member
    dataset never looks directly run-produced.

    `named_run` is the run a derivation edge named even when it is not
    fingerprinted, so a reader CLI can name it. `run` non-None ⟹ `named_run == run`.
    """

    run: URIRef | None
    named_run: URIRef | None = None
    chain: list[URIRef] = field(default_factory=list)
    reasons: list[NoRunReason] = field(default_factory=list)


def resolve_run_chain(
    knowledge: Graph,
    dataset: URIRef,
    is_fingerprinted: Callable[[URIRef], bool],
) -> RunChainResolution:
    """Resolve `dataset` to its fingerprinted run, recording the member_of chain.

    Same traversal as `resolved_empirical_runs`, but returns the single run it
    resolves to plus the datasets visited to reach it. `is_fingerprinted` is
    required: naming a run is not resolving to a *fingerprinted* one.
    """
    visited: set[URIRef] = set()
    chain: list[URIRef] = []
    current = dataset

    while True:
        if current in visited:
            raise MemberOfCycleError(f"member_of cycle revisits {current}")
        visited.add(current)
        chain.append(current)

        kind = _derivation_kind(knowledge, current)

        if kind == KIND_WORKFLOW_RUN:
            run = cast("URIRef | None", knowledge.value(current, SCI_NS.workflowRun))
            if run is None:
                return RunChainResolution(None, None, chain, [NoRunReason.NO_PROVENANCE])
            if not is_fingerprinted(run):
                return RunChainResolution(None, run, chain, [NoRunReason.RUN_UNFINGERPRINTED])
            return RunChainResolution(run, run, chain, [])

        if kind == KIND_WORKFLOW_RECIPE:
            return RunChainResolution(None, None, chain, [NoRunReason.RECIPE_ONLY])

        if kind == KIND_MEMBER_OF:
            parent = cast("URIRef | None", knowledge.value(current, SCI_NS.memberOfParent))
            if parent is None:
                return RunChainResolution(None, None, chain, [NoRunReason.NO_PROVENANCE])
            current = parent
            continue

        if kind is not None:
            raise ValueError(f"unknown sci:derivationKind {kind!r} on {current}")

        # No derivation. Code-only provenance is not a run.
        if (current, SCI_NS.producedBy, None) in knowledge:
            return RunChainResolution(None, None, chain, [NoRunReason.CODE_ONLY_NO_RUN])
        return RunChainResolution(None, None, chain, [NoRunReason.NO_PROVENANCE])


def resolved_empirical_runs(
    knowledge: Graph,
    dataset: URIRef,
    is_fingerprinted: Callable[[URIRef], bool],
) -> tuple[list[URIRef], list[NoRunReason]]:
    """Fingerprinted runs this dataset resolves to, walking member_of to the parent.

    `is_fingerprinted` is required and has no default: naming a workflow-run is
    not the same as resolving to a *fingerprinted* one. Delegates to
    `resolve_run_chain`, discarding the chain — evidence resolution needs only
    the run set.
    """
    result = resolve_run_chain(knowledge, dataset, is_fingerprinted)
    return ([result.run] if result.run is not None else []), result.reasons
