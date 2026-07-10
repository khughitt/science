"""Reader-facing stochasticity report for a derived dataset (umbrella Spec 3).

Graph resolves `dataset -> fingerprinted run` and the `member_of` chain; the
source layer supplies the fingerprint's realized `step_seeds`, the workflow's
steps, and each step's method `stochasticity`. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from rdflib import Dataset, Graph, URIRef
from science_model.entities import Stochasticity
from science_model.frontmatter import parse_frontmatter
from science_model.run_fingerprint import RunFingerprint

from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.io import SCI_NS
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.run_resolution import RunChainResolution, resolve_run_chain
from science_tool.graph.sources import ProjectSources, load_project_sources
from science_tool.graph.store.identity import _graph_uri, canonical_id_from_entity_uri
from science_tool.workflow_steps_index import steps_and_methods_for_workflow


class DatasetStochasticityError(Exception):
    """Base for stochasticity-report failures."""


class DatasetNotFoundError(DatasetStochasticityError):
    """The dataset ref does not resolve to a dataset entity."""


class GraphNotBuiltError(DatasetStochasticityError):
    """`knowledge/graph.trig` is absent; the report needs a built graph."""


@dataclass(frozen=True)
class StepReport:
    step_id: str
    method_id: str
    stochasticity: Stochasticity | None
    realized_seeds: dict[str, int] = field(default_factory=dict)
    rationale: str = ""


@dataclass(frozen=True)
class StochasticityReport:
    dataset_id: str
    run_id: str | None
    named_run_id: str | None
    inherited: bool
    chain: list[str]
    seed_policy_kind: str | None
    stochastic_steps: list[StepReport]
    deterministic_step_count: int
    unresolved_reason: str | None


def _is_fingerprinted(knowledge: Graph, run_uri: URIRef) -> bool:
    return (run_uri, SCI_NS.fingerprintPolicy, None) in knowledge


def _canonical_dataset_id(project_root: Path, dataset_ref: str) -> str:
    slug = dataset_ref.removeprefix("dataset:")
    path = project_root / "entities" / "datasets" / f"{slug}.md"
    if not path.is_file():
        raise DatasetNotFoundError(f"no dataset entity: dataset:{slug} ({path})")
    return f"dataset:{slug}"


def _load_knowledge(project_root: Path) -> Graph:
    graph_path = project_root / "knowledge" / "graph.trig"
    if not graph_path.is_file():
        raise GraphNotBuiltError(f"graph not built ({graph_path}); run `science graph build`")
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    return dataset.graph(_graph_uri("graph/knowledge"))


def _run_id_of(uri: URIRef) -> str:
    return canonical_id_from_entity_uri(str(uri)) or str(uri)


def _reject_skipped_stochasticity_sources(sources: ProjectSources) -> None:
    """A skipped workflow-step or method underreports stochasticity — fail loud.

    Mirrors register-run's `_reject_skipped_steps`: the non-strict load silently
    drops any entity that fails schema validation, and a dropped step shrinks the
    workflow's step set. Read the loader's own `skipped_entities` record.
    """
    for skipped in sources.skipped_entities:
        if skipped.kind in ("workflow-step", "method"):
            raise DatasetStochasticityError(
                f"{skipped.path} ({skipped.kind}) failed schema validation and was skipped "
                f"({skipped.reason}); stochasticity would be underreported. Run "
                f"`science validate` and fix it."
            )


def _read_run_fingerprint(project_root: Path, run_id: str) -> tuple[str, RunFingerprint]:
    slug = run_id.removeprefix("workflow-run:")
    path = project_root / "entities" / "workflow-runs" / f"{slug}.md"
    parsed = parse_frontmatter(path)  # takes a Path; returns (fm, body) | None
    if parsed is None:
        raise DatasetStochasticityError(
            f"{run_id} is marked fingerprinted in the graph but {path} has no frontmatter"
        )
    fm, _body = parsed
    raw = fm.get("fingerprint")
    if not raw:
        raise DatasetStochasticityError(
            f"{run_id} is marked fingerprinted in the graph but its entity carries no "
            f"`fingerprint:`; rebuild the graph or re-register the run"
        )
    return str(fm.get("workflow") or ""), RunFingerprint.model_validate(raw)


def report_dataset_stochasticity(project_root: Path, dataset_ref: str) -> StochasticityReport:
    dataset_id = _canonical_dataset_id(project_root, dataset_ref)
    knowledge = _load_knowledge(project_root)
    ds_uri = project_entity_uri(dataset_id)

    resolution: RunChainResolution = resolve_run_chain(
        knowledge, ds_uri, partial(_is_fingerprinted, knowledge)
    )
    chain_ids = [canonical_id_from_entity_uri(str(u)) or str(u) for u in resolution.chain]
    named_run_id = _run_id_of(resolution.named_run) if resolution.named_run is not None else None

    if resolution.run is None:
        reason = resolution.reasons[0].value if resolution.reasons else None
        return StochasticityReport(
            dataset_id=dataset_id, run_id=None, named_run_id=named_run_id,
            inherited=len(resolution.chain) > 1, chain=chain_ids, seed_policy_kind=None,
            stochastic_steps=[], deterministic_step_count=0, unresolved_reason=reason,
        )

    run_id = _run_id_of(resolution.run)
    workflow_id_ref, fingerprint = _read_run_fingerprint(project_root, run_id)

    sources = load_project_sources(project_root, strict_core_schema=False)
    _reject_skipped_stochasticity_sources(sources)
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    workflow_id = resolver.resolve(workflow_id_ref).canonical_id or workflow_id_ref
    pairs = steps_and_methods_for_workflow(sources, resolver, workflow_id)

    stochastic: list[StepReport] = []
    deterministic = 0
    for step, method in pairs:
        s = method.stochasticity if method is not None else None
        if s is Stochasticity.DETERMINISTIC:
            deterministic += 1
            continue
        stochastic.append(
            StepReport(
                step_id=step.id,
                method_id=method.id if method is not None else step.method,
                stochasticity=s,
                realized_seeds=dict(fingerprint.step_seeds.get(step.id, {})),
                rationale=step.rationale,
            )
        )

    return StochasticityReport(
        dataset_id=dataset_id, run_id=run_id, named_run_id=named_run_id,
        inherited=len(resolution.chain) > 1, chain=chain_ids,
        seed_policy_kind=fingerprint.seed_policy.kind, stochastic_steps=stochastic,
        deterministic_step_count=deterministic, unresolved_reason=None,
    )
