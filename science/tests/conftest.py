from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.audit import (
    AuditFindingRecord,
    EntitySubject,
    Occurrence,
    Transition,
    finding_fingerprint,
    occurrence_key,
)
from science_model.autonomous_runs import (
    AutonomousRunRecord,
    PolicyIdentity,
    RunBudget,
    RunDisposition,
    RunTier,
)
from science_model.evidence_broker import (
    EvidenceSessionSpec,
    InstrumentIdentity,
    SurfacePolicy,
)
from science_model.run_fingerprint import (
    FINGERPRINT_POLICY_V1,
    ArtifactLocality,
    ComponentProvenance,
    ExecutorKind,
    FingerprintComponent,
    RunFingerprint,
    SeedPolicy,
)

# Keep pytest's tmp_path off the per-user /tmp tmpfs quota. The validate parity
# gates stage real downstream projects into tmp_path; on Linux, systemd applies a
# per-UID usrquota to the /tmp tmpfs, and tools such as Claude Code point TMPDIR
# there, so multi-run/concurrent test temp can exhaust it and silently break any
# process that writes to /tmp. Route the test temp root to disk-backed storage.
# Override SCIENCE_TEST_TMPDIR to relocate it (for example, on CI).
_PYTEST_TMP_ROOT = Path(os.environ.get("SCIENCE_TEST_TMPDIR", Path.home() / ".cache" / "science-pytest-tmp"))
_PYTEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_PYTEST_TMP_ROOT)
# tempfile caches the temp dir on first use; set it explicitly so the redirect
# wins even if something already called tempfile.gettempdir() during startup.
tempfile.tempdir = str(_PYTEST_TMP_ROOT)

# Make `_fixtures.*` importable as a top-level package: tests/ has no
# __init__.py (cross-project pytest collection treats it as a rootdir),
# so we add the tests directory to sys.path here.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


@pytest.fixture(autouse=True)
def isolate_science_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / ".science-config"))


def build_inquiry_graph(
    graph_path: Path,
    slug: str = "i01",
    *,
    profile: str = "investigation",
    normalize_slug: bool = False,
    **inquiry: object,
):
    """Merge one compiled inquiry into the trig at ``graph_path`` and return the path.

    The inquiry graph is produced by the pure compiler
    ``science_tool.graph.inquiry_compile.emit_inquiry_views`` (the path that
    replaced the retired ``inquiry add-*`` mutators). Any standard named graphs
    already present at ``graph_path`` (e.g. from ``graph init``) are preserved so
    that subsequent ``graph add`` commands keep working on the same file.

    Keyword args map onto the authored ``inquiry:`` block, e.g.
    ``boundary_roles=[{"ref": ..., "role": "BoundaryIn"}]``,
    ``flow_edges=[{"subject": ..., "predicate": "feedsInto", "object": ...,
    "claim_refs": [...]}]``, ``treatment=...``, ``outcome=...``,
    ``assumptions=[...]``, ``status=...``.

    ``normalize_slug=True`` reproduces the retired ``add_inquiry`` mutator's
    ``_slug`` normalization (hyphens -> underscores), so hyphenated slugs land at
    the same inquiry URI the ``_slug``-normalizing readers resolve.
    """
    from rdflib import Dataset
    from science_model.patch_definition import PatchDefinitionEntity

    from science_tool.graph.inquiry_compile import emit_inquiry_views
    from science_tool.graph.store import _load_dataset, _save_dataset, _slug

    safe_slug = _slug(slug) if normalize_slug else slug
    ent = PatchDefinitionEntity(
        id=f"patch-definition:{safe_slug}",
        title=inquiry.pop("title", "I"),
        focal=inquiry.pop("focal", "hypothesis:h01"),
        scope_set=[{"scope": "local"}],
        neighborhood_policy={},
        patch_type="inquiry",
        project="",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path=f"entities/patches/{safe_slug}.md",
        inquiry={"profile": profile, "status": inquiry.pop("status", "specified"), **inquiry},
    )

    compiled = Dataset()
    emit_inquiry_views(compiled, [ent])

    graph_path.parent.mkdir(parents=True, exist_ok=True)
    dataset = _load_dataset(graph_path) if graph_path.exists() else Dataset()
    for quad in compiled.quads((None, None, None, None)):
        s, p, o, ctx = quad
        dataset.graph(ctx.identifier if hasattr(ctx, "identifier") else ctx).add((s, p, o))
    _save_dataset(dataset, graph_path)
    return graph_path


def build_entity_graph(project_root: Path, entities: list[dict], relations: list[dict] | None = None) -> Path:
    """Author core entity markdown, optional relations, and materialize the graph."""
    import yaml
    from science_model.profiles import CORE_PROFILE

    from _fixtures.entity_helpers import seed_project, write_markdown_entity
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.sources import local_profile_sources_dir, resolve_local_profile_name

    if not (project_root / "science.yaml").exists():
        seed_project(project_root)

    core_homes = {kind.name: kind.home for kind in CORE_PROFILE.entity_kinds}
    for entity in entities:
        kind = entity["kind"]
        entity_id = entity["id"]
        home = core_homes.get(kind)
        if home is None:
            raise ValueError(f"core kind {kind!r} has no markdown home")

        home_path = Path(home)
        rel_path = home_path if home_path.suffix == ".md" else home_path / f"{entity_id}.md"
        frontmatter = dict(entity["frontmatter"])
        frontmatter["id"] = f"{kind}:{entity_id}"
        frontmatter["kind"] = kind
        write_markdown_entity(project_root, rel_path.as_posix(), frontmatter, str(entity["body"]))

    if relations is not None:
        if not isinstance(relations, list):
            raise ValueError("relations must be a list of dicts")
        for index, relation in enumerate(relations):
            if not isinstance(relation, dict):
                raise ValueError(f"relations[{index}] must be a dict")
            for field in ("subject", "predicate", "object"):
                value = relation.get(field)
                if not isinstance(value, str) or not value:
                    raise ValueError(f"relations[{index}].{field} must be a non-empty string")
            graph_layer = relation.get("graph_layer")
            if graph_layer is not None and (not isinstance(graph_layer, str) or not graph_layer):
                raise ValueError(f"relations[{index}].graph_layer must be a non-empty string when present")

        local_profile = resolve_local_profile_name(project_root)
        sources_dir = local_profile_sources_dir(project_root, local_profile=local_profile)
        sources_dir.mkdir(parents=True, exist_ok=True)
        (sources_dir / "relations.yaml").write_text(
            yaml.safe_dump({"relations": relations}, sort_keys=False),
            encoding="utf-8",
        )

    return materialize_graph(project_root)


def _seed_registry_project(project_root: Path, entity_kinds: list[dict[str, object]]) -> Path:
    """Create a minimal project with the requested project-local entity kinds."""
    import yaml

    from _fixtures.entity_helpers import seed_project

    seed_project(project_root)
    manifest = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        yaml.safe_dump(
            {
                "name": "test-local",
                "imports": ["core"],
                "strictness": "typed-extension",
                "entity_kinds": entity_kinds,
                "relation_kinds": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return project_root


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    return _seed_registry_project(tmp_path, [])


@pytest.fixture
def tmp_project_with_design_kind(tmp_path: Path) -> Path:
    return _seed_registry_project(
        tmp_path,
        [
            {
                "name": "design",
                "canonical_prefix": "design",
                "layer": "layer/local",
                "description": "Project-local design record.",
            }
        ],
    )


@pytest.fixture
def tmp_project_with_scoped_kind(tmp_path: Path) -> Path:
    return _seed_registry_project(
        tmp_path,
        [
            {
                "name": "logbook",
                "canonical_prefix": "logbook",
                "layer": "layer/local",
                "description": "Project-local logbook record.",
                "curation_scope": "none",
            }
        ],
    )


#: Splice this into a hand-authored `workflow-run` frontmatter block so
#: The authored `execution:` declaration `register-run` captures a fingerprint
#: from. Nothing under `fingerprint:` is declared here — the whole block is
#: observed at register-run (t093), and `seed_policy`/`step_seeds` within it are
#: derived from the workflow's steps (t088). Pairs with `seed_git_repo`, which
#: supplies the `config.yaml` this declares as `config_snapshot`; the project must
#: also carry a workflow/workflow-step/method trio for the derivation to resolve.
REGISTER_RUN_EXECUTION_FRONTMATTER = (
    "config_snapshot: config.yaml\n"
    "execution:\n"
    "  executor: local\n"
    "  input_artifact_locality: science-managed\n"
    "  output_artifact_locality: science-managed\n"
)


def seed_git_repo(root: Path) -> None:
    """git-init `root` (idempotent), commit, and write `uv.lock` + `config.yaml`.

    Fixture prerequisite for `register-run`'s fingerprint capture, which shells
    out to git (`rev-parse HEAD`, `status --porcelain`) and hashes `uv.lock` and
    the run's declared `config_snapshot`. Safe to call more than once in one
    test (e.g. once per simulated run) — each call adds a commit.
    """
    if not (root / ".git").is_dir():
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    lock = root / "uv.lock"
    if not lock.exists():
        lock.write_text("lock\n", encoding="utf-8")
    config = root / "config.yaml"
    if not config.exists():
        config.write_text("alpha: 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        [
            "git", "-c", "user.email=test@test", "-c", "user.name=test",
            "commit", "-q", "-m", "seed", "--allow-empty",
        ],
        cwd=root, check=True,
    )


@pytest.fixture
def local_fingerprint():
    def _cap(v: str) -> FingerprintComponent:
        return FingerprintComponent(value=v, provenance=ComponentProvenance.CAPTURED)

    def _make(**over) -> RunFingerprint:
        base = dict(
            fingerprint_policy=FINGERPRINT_POLICY_V1,
            executor=ExecutorKind.LOCAL,
            input_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
            output_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
            code_sha=_cap("a" * 40),
            code_dirty=_cap("false"),
            environment_digest=_cap("sha256:env"),
            parameters_digest=_cap("sha256:params"),
            input_manifest_digest=_cap("sha256:in"),
            output_manifest_digest=_cap("sha256:out"),
            seed_policy=SeedPolicy(kind="deterministic"),
        )
        base.update(over)
        return RunFingerprint(**base)

    return _make


@pytest.fixture
def materialized_knowledge_for_evidence_line(tmp_path: Path):
    """Materialize a real project graph for one evidence line and hand back its
    knowledge-graph named subgraph plus the evidence line's URI.

    Runs the actual `science graph build` CLI pipeline (not a hand-built
    rdflib.Graph) so tests using this fixture prove what the real materializer
    emits, not what a test author assumes it emits. Any `run_refs` entries are
    backed by minimal authored `workflow-run` entities so reference resolution
    succeeds.
    """

    def _build(*, run_refs: list[str], belief_eligible: bool):
        from click.testing import CliRunner
        from rdflib import Dataset, URIRef

        from science_tool.cli import main
        from science_tool.graph.io import PROJECT_NS

        root = tmp_path
        (root / "science.yaml").write_text(
            "name: run-refs-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
        )

        propositions = root / "entities" / "propositions"
        propositions.mkdir(parents=True, exist_ok=True)
        (propositions / "p1.md").write_text(
            "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n",
            encoding="utf-8",
        )

        papers = root / "entities" / "papers"
        papers.mkdir(parents=True, exist_ok=True)
        (papers / "x.md").write_text(
            "---\nid: paper:x\nkind: paper\ntitle: X\n---\n\nAbstract.\n",
            encoding="utf-8",
        )

        runs_dir = root / "entities" / "workflow-runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        for ref in run_refs:
            slug = ref.split(":", 1)[1]
            run_path = runs_dir / f"{slug}.md"
            if not run_path.exists():
                run_path.write_text(
                    f"---\nid: workflow-run:{slug}\nkind: workflow-run\ntitle: {slug.upper()}\n---\n",
                    encoding="utf-8",
                )

        run_refs_block = "run_refs: []\n"
        if run_refs:
            run_refs_block = "run_refs:\n" + "".join(f"  - {ref}\n" for ref in run_refs)

        evidence_lines = root / "entities" / "evidence-lines"
        evidence_lines.mkdir(parents=True, exist_ok=True)
        (evidence_lines / "e1.md").write_text(
            "---\n"
            "id: evidence-line:e1\n"
            "kind: evidence-line\n"
            "title: Evidence line\n"
            "stance: supports\n"
            "target: proposition:p1\n"
            "source: paper:x\n"
            f"belief_eligible: {belief_eligible}\n"
            f"{run_refs_block}"
            "---\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(main, ["graph", "build", "--project-root", str(root)])
        assert result.exit_code == 0, f"graph build failed:\n{result.output}"

        dataset = Dataset()
        dataset.parse(source=str(root / "knowledge" / "graph.trig"), format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        line_uri = URIRef(PROJECT_NS["evidence-line/e1"])
        return knowledge, line_uri

    return _build


@pytest.fixture
def materialized_knowledge_for_run(tmp_path: Path, local_fingerprint):
    """Materialize a real project graph for one workflow-run entity and hand
    back its knowledge-graph named subgraph plus the run's URI.

    Runs the actual `science graph build` CLI pipeline (not a hand-built
    rdflib.Graph) so tests using this fixture prove what the real materializer
    emits, not what a test author assumes it emits. The fingerprint block, when
    present, is built from the `local_fingerprint` fixture and serialized to
    the same frontmatter shape `register-run` writes.
    """

    def _build(*, with_fingerprint: bool):
        import yaml
        from click.testing import CliRunner
        from rdflib import Dataset, URIRef

        from science_tool.cli import main
        from science_tool.graph.io import PROJECT_NS

        root = tmp_path
        (root / "science.yaml").write_text(
            "name: run-fingerprint-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
        )

        fingerprint_block = ""
        if with_fingerprint:
            fingerprint = local_fingerprint()
            fingerprint_yaml = yaml.safe_dump(
                {"fingerprint": fingerprint.model_dump(mode="json", exclude_none=True)},
                sort_keys=False,
            )
            fingerprint_block = fingerprint_yaml

        runs_dir = root / "entities" / "workflow-runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / "r1.md").write_text(
            "---\n"
            "id: workflow-run:r1\n"
            "kind: workflow-run\n"
            "title: R1\n"
            f"{fingerprint_block}"
            "---\n",
            encoding="utf-8",
        )

        runner = CliRunner()
        result = runner.invoke(main, ["graph", "build", "--project-root", str(root)])
        assert result.exit_code == 0, f"graph build failed:\n{result.output}"

        dataset = Dataset()
        dataset.parse(source=str(root / "knowledge" / "graph.trig"), format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        run_uri = URIRef(PROJECT_NS["workflow-run/r1"])
        return knowledge, run_uri

    return _build


@pytest.fixture
def materialized_knowledge_for_dataset(tmp_path: Path):
    """Materialize a real project graph for one dataset entity and hand back its
    knowledge-graph named subgraph, the dataset's URI, and (kind-dependent) the
    URI the dataset's derivation should reach.

    Runs the actual `science graph build` CLI pipeline (not a hand-built
    rdflib.Graph) so tests using this fixture prove what the real materializer
    emits for each of the three `derivation` union arms, not what a test author
    assumes it emits.

    ``kind`` selects the derivation shape authored on `dataset:ds1`:
      - "workflow-run": a full `DerivationBlock` naming `workflow-run:r1`;
        `related_uri` is the run's URI.
      - "workflow-recipe": a `WorkflowRecipeDerivationBlock` naming a recipe
        (not a run); `related_uri` is None.
      - "member_of": a `MemberOfDerivationBlock` naming `dataset:parent`;
        `related_uri` is the parent dataset's URI.
      - None: no `derivation` block at all (origin=external); `related_uri`
        is None.
    """

    def _build(*, kind: str | None):
        from click.testing import CliRunner
        from rdflib import Dataset, URIRef

        from science_tool.cli import main
        from science_tool.graph.io import PROJECT_NS

        root = tmp_path
        (root / "science.yaml").write_text(
            "name: dataset-derivation-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
        )

        datasets_dir = root / "entities" / "datasets"
        datasets_dir.mkdir(parents=True, exist_ok=True)

        related_uri = None

        if kind == "workflow-run":
            runs_dir = root / "entities" / "workflow-runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            (runs_dir / "r1.md").write_text(
                "---\nid: workflow-run:r1\nkind: workflow-run\ntitle: R1\n---\n",
                encoding="utf-8",
            )
            (datasets_dir / "ds1.md").write_text(
                "---\n"
                "id: dataset:ds1\n"
                "kind: dataset\n"
                "title: DS1\n"
                "origin: derived\n"
                "derivation:\n"
                "  workflow: workflow:wf\n"
                "  workflow_run: workflow-run:r1\n"
                "  git_commit: abc\n"
                "  config_snapshot: config.yaml\n"
                "  produced_at: '2026-04-19T00:00:00Z'\n"
                "---\n",
                encoding="utf-8",
            )
            related_uri = URIRef(PROJECT_NS["workflow-run/r1"])
        elif kind == "workflow-recipe":
            (datasets_dir / "ds1.md").write_text(
                "---\n"
                "id: dataset:ds1\n"
                "kind: dataset\n"
                "title: DS1\n"
                "origin: derived\n"
                "derivation:\n"
                "  kind: workflow\n"
                "  workflow_recipe: workflow:wf\n"
                "---\n",
                encoding="utf-8",
            )
        elif kind == "member_of":
            (datasets_dir / "parent.md").write_text(
                "---\n"
                "id: dataset:parent\n"
                "kind: dataset\n"
                "title: Parent\n"
                "origin: external\n"
                "access:\n"
                "  level: public\n"
                "  verified: true\n"
                "---\n",
                encoding="utf-8",
            )
            (datasets_dir / "ds1.md").write_text(
                "---\n"
                "id: dataset:ds1\n"
                "kind: dataset\n"
                "title: DS1\n"
                "origin: derived\n"
                "derivation:\n"
                "  kind: member_of\n"
                "  parent_dataset: dataset:parent\n"
                "  member_key: row1\n"
                "---\n",
                encoding="utf-8",
            )
            related_uri = URIRef(PROJECT_NS["dataset/parent"])
        elif kind is None:
            (datasets_dir / "ds1.md").write_text(
                "---\n"
                "id: dataset:ds1\n"
                "kind: dataset\n"
                "title: DS1\n"
                "origin: external\n"
                "access:\n"
                "  level: public\n"
                "  verified: true\n"
                "---\n",
                encoding="utf-8",
            )
        else:
            raise ValueError(f"unknown derivation kind {kind!r}")

        runner = CliRunner()
        result = runner.invoke(main, ["graph", "build", "--project-root", str(root)])
        assert result.exit_code == 0, f"graph build failed:\n{result.output}"

        dataset = Dataset()
        dataset.parse(source=str(root / "knowledge" / "graph.trig"), format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        ds_uri = URIRef(PROJECT_NS["dataset/ds1"])
        return knowledge, ds_uri, related_uri

    return _build


# ---------------------------------------------------------------------------
# Hand-built TriG fixtures for `empirical_run_resolution` (Task 10).
#
# Style copied from `test_dataset_independence.py:338-360`: build the
# knowledge/provenance graphs directly with rdflib, then serialize to TriG
# text so `validate_graph_dataset` can parse it via `Dataset.parse(data=...,
# format="trig")`, exactly like the graph-phase validator consumes a real
# `graph.trig`. Do not invent predicates — reuse `SCI_NS`/`CITO_NS` terms
# from `science_tool.graph.io`.
# ---------------------------------------------------------------------------


def _run_resolution_dataset():
    from rdflib import Dataset

    from science_tool.graph.io import PROJECT_NS

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    return ds, knowledge, provenance


def _add_empirical_line(knowledge, provenance, line, target, dataset, usage, *, role="analyzed", overlap="full"):
    """Wire up a belief-eligible empirical_data evidence line with one DEPENDENCE dataset usage."""
    from rdflib import RDF, Literal

    from science_tool.graph.io import CITO_NS, SCI_NS

    knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
    knowledge.add((line, CITO_NS.supports, target))
    provenance.add((line, SCI_NS.hasDatasetUsage, usage))
    provenance.add((usage, RDF.type, SCI_NS.DatasetUsage))
    provenance.add((usage, SCI_NS.dataset, dataset))
    provenance.add((usage, SCI_NS.usageRole, Literal(role)))
    provenance.add((usage, SCI_NS.usageOverlap, Literal(overlap)))
    provenance.add((line, SCI_NS.evidenceType, Literal("empirical_data")))


@pytest.fixture
def empirical_line_without_run_trig():
    """Dataset has no derivation at all → NoRunReason.NO_PROVENANCE, no run_refs rescue."""
    from rdflib import URIRef

    from science_tool.graph.io import PROJECT_NS

    ds, knowledge, provenance = _run_resolution_dataset()
    line = URIRef(PROJECT_NS["evidence-line/e1"])
    target = URIRef(PROJECT_NS["proposition/p1"])
    dataset = URIRef(PROJECT_NS["dataset/d1"])
    usage = URIRef(PROJECT_NS["usage/u1"])
    _add_empirical_line(knowledge, provenance, line, target, dataset, usage)
    return ds.serialize(format="trig")


@pytest.fixture
def empirical_line_with_run_trig():
    """Dataset's own derivation names a FINGERPRINTED workflow-run → resolves, passes."""
    from rdflib import Literal, URIRef

    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.run_resolution import KIND_WORKFLOW_RUN

    ds, knowledge, provenance = _run_resolution_dataset()
    line = URIRef(PROJECT_NS["evidence-line/e1"])
    target = URIRef(PROJECT_NS["proposition/p1"])
    dataset = URIRef(PROJECT_NS["dataset/d1"])
    usage = URIRef(PROJECT_NS["usage/u1"])
    run = URIRef(PROJECT_NS["workflow-run/r1"])
    _add_empirical_line(knowledge, provenance, line, target, dataset, usage)
    knowledge.add((dataset, SCI_NS.derivationKind, Literal(KIND_WORKFLOW_RUN)))
    knowledge.add((dataset, SCI_NS.workflowRun, run))
    knowledge.add((run, SCI_NS.fingerprintPolicy, Literal("science-run-fingerprint/v1")))
    return ds.serialize(format="trig")


@pytest.fixture
def member_of_cycle_trig():
    """Dataset's own member_of chain revisits itself → MemberOfCycleError → fatal row."""
    from rdflib import Literal, URIRef

    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.run_resolution import KIND_MEMBER_OF

    ds, knowledge, provenance = _run_resolution_dataset()
    line = URIRef(PROJECT_NS["evidence-line/e1"])
    target = URIRef(PROJECT_NS["proposition/p1"])
    dataset = URIRef(PROJECT_NS["dataset/d1"])
    usage = URIRef(PROJECT_NS["usage/u1"])
    _add_empirical_line(knowledge, provenance, line, target, dataset, usage)
    knowledge.add((dataset, SCI_NS.derivationKind, Literal(KIND_MEMBER_OF)))
    knowledge.add((dataset, SCI_NS.memberOfParent, dataset))  # self-cycle
    return ds.serialize(format="trig")


@pytest.fixture
def empirical_line_with_unfingerprinted_run_trig():
    """Dataset's own derivation names a run that carries NO sci:fingerprintPolicy → warns.

    Proves the contract fails CLOSED: naming a run is not the same as resolving to a
    fingerprinted one.
    """
    from rdflib import Literal, URIRef

    from science_tool.graph.io import PROJECT_NS, SCI_NS
    from science_tool.graph.run_resolution import KIND_WORKFLOW_RUN

    ds, knowledge, provenance = _run_resolution_dataset()
    line = URIRef(PROJECT_NS["evidence-line/e1"])
    target = URIRef(PROJECT_NS["proposition/p1"])
    dataset = URIRef(PROJECT_NS["dataset/d1"])
    usage = URIRef(PROJECT_NS["usage/u1"])
    run = URIRef(PROJECT_NS["workflow-run/r1"])
    _add_empirical_line(knowledge, provenance, line, target, dataset, usage)
    knowledge.add((dataset, SCI_NS.derivationKind, Literal(KIND_WORKFLOW_RUN)))
    knowledge.add((dataset, SCI_NS.workflowRun, run))
    # Deliberately no sci:fingerprintPolicy on `run`.
    return ds.serialize(format="trig")


@pytest.fixture
def line_with_unfingerprinted_run_ref_trig():
    """`run_refs` names an unfingerprinted run and the dataset has no provenance of its
    own → the run_refs entry must NOT rescue resolution; run_refs is not a back door.
    """
    from rdflib import URIRef

    from science_tool.graph.io import PROJECT_NS, SCI_NS

    ds, knowledge, provenance = _run_resolution_dataset()
    line = URIRef(PROJECT_NS["evidence-line/e1"])
    target = URIRef(PROJECT_NS["proposition/p1"])
    dataset = URIRef(PROJECT_NS["dataset/d1"])
    usage = URIRef(PROJECT_NS["usage/u1"])
    run = URIRef(PROJECT_NS["workflow-run/r1"])
    _add_empirical_line(knowledge, provenance, line, target, dataset, usage)
    # dataset has no derivation of its own (NO_PROVENANCE)
    knowledge.add((line, SCI_NS.runRef, run))
    # `run` deliberately carries no sci:fingerprintPolicy.
    return ds.serialize(format="trig")


@pytest.fixture
def line_with_produced_by_dataset_and_fingerprinted_run_ref_trig():
    """Rescue case: dataset provenance is sound but code-only (sci:producedBy, no run),
    and `run_refs` names a FINGERPRINTED run → resolves via the run_refs union.
    """
    from rdflib import Literal, URIRef

    from science_tool.graph.io import PROJECT_NS, SCI_NS

    ds, knowledge, provenance = _run_resolution_dataset()
    line = URIRef(PROJECT_NS["evidence-line/e1"])
    target = URIRef(PROJECT_NS["proposition/p1"])
    dataset = URIRef(PROJECT_NS["dataset/d1"])
    usage = URIRef(PROJECT_NS["usage/u1"])
    code = URIRef(PROJECT_NS["code-file/producer"])
    run = URIRef(PROJECT_NS["workflow-run/r1"])
    _add_empirical_line(knowledge, provenance, line, target, dataset, usage)
    knowledge.add((dataset, SCI_NS.producedBy, code))  # code-only, no run
    knowledge.add((line, SCI_NS.runRef, run))
    knowledge.add((run, SCI_NS.fingerprintPolicy, Literal("science-run-fingerprint/v1")))
    return ds.serialize(format="trig")


def _seed_stochastic_pipeline(root: Path) -> str:
    """Scaffold a registrable run whose workflow mixes a seedable, a
    nondeterministic, and a deterministic step, then run register-run and build
    the graph. Returns the derived dataset id.

    Order matters: register-run (writes the captured `fingerprint:` and the
    derived dataset) MUST precede `graph build`, or the graph carries neither
    the `sci:fingerprintPolicy` marker nor the derived dataset's derivation edge.
    register-run reads the source layer, not the graph, so it needs no prior build.
    """
    import yaml
    from click.testing import CliRunner

    from science_tool.cli import main as science_cli

    (root / "science.yaml").write_text(
        "name: stoch-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    wf = root / "entities" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    (wf / "pipe.md").write_text(
        '---\nid: "workflow:pipe"\nkind: "workflow"\ntitle: "Pipe"\n'
        "outputs:\n"
        '  - slug: "clusters"\n    title: "Clusters"\n    resource_names: ["clusters"]\n    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    methods = root / "entities" / "methods"
    methods.mkdir(parents=True, exist_ok=True)
    (methods / "embed.md").write_text(
        '---\nid: "method:embed"\nkind: "method"\ntitle: "Embed"\nstochasticity: "nondeterministic"\n---\n',
        encoding="utf-8",
    )
    (methods / "cluster.md").write_text(
        '---\nid: "method:cluster"\nkind: "method"\ntitle: "Cluster"\n'
        'stochasticity: "seedable"\nseed_params: ["random_state"]\n---\n',
        encoding="utf-8",
    )
    (methods / "normalize.md").write_text(
        '---\nid: "method:normalize"\nkind: "method"\ntitle: "Normalize"\nstochasticity: "deterministic"\n---\n',
        encoding="utf-8",
    )
    steps = root / "entities" / "workflow-steps"
    steps.mkdir(parents=True, exist_ok=True)
    (steps / "embed.md").write_text(
        '---\nid: "workflow-step:embed"\nkind: "workflow-step"\ntitle: "Embed"\n'
        'workflow: "workflow:pipe"\nmethod: "method:embed"\n'
        'rationale: "GPU atomics; residual nondeterminism accepted"\n---\n',
        encoding="utf-8",
    )
    (steps / "cluster.md").write_text(
        '---\nid: "workflow-step:cluster"\nkind: "workflow-step"\ntitle: "Cluster"\n'
        'workflow: "workflow:pipe"\nmethod: "method:cluster"\n'
        'seed_bindings:\n  random_state: "literal:42"\n---\n',
        encoding="utf-8",
    )
    (steps / "normalize.md").write_text(
        '---\nid: "workflow-step:normalize"\nkind: "workflow-step"\ntitle: "Normalize"\n'
        'workflow: "workflow:pipe"\nmethod: "method:normalize"\n---\n',
        encoding="utf-8",
    )
    datasets = root / "entities" / "datasets"
    datasets.mkdir(parents=True, exist_ok=True)
    (datasets / "src.md").write_text(
        '---\nid: "dataset:src"\nkind: "dataset"\ntitle: "Src"\norigin: "external"\n'
        'datapackage: "data/src/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", '
        'last_reviewed: "2026-04-19", source_url: "https://s"}\n---\n',
        encoding="utf-8",
    )
    runs = root / "entities" / "workflow-runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "pipe-r1.md").write_text(
        '---\nid: "workflow-run:pipe-r1"\nkind: "workflow-run"\ntitle: "Pipe r1"\n'
        'workflow: "workflow:pipe"\nproduces: []\ninputs: ["dataset:src"]\n'
        'git_commit: "abc"\nlast_run: "2026-04-19T12:00:00Z"\n'
        f"{REGISTER_RUN_EXECUTION_FRONTMATTER}"
        "---\n",
        encoding="utf-8",
    )
    rundir = root / "results" / "pipe" / "r1"
    rundir.mkdir(parents=True)
    (rundir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "pipe-r1",
                "resources": [
                    {"name": "clusters", "path": "clusters.csv", "format": "csv", "hash": "sha256:clusters"}
                ],
            }
        ),
        encoding="utf-8",
    )
    (rundir / "clusters.csv").write_text("col\nval\n", encoding="utf-8")
    seed_git_repo(root)

    runner = CliRunner()
    env = {"SCIENCE_PROJECT_ROOT": str(root)}
    reg = runner.invoke(
        science_cli, ["dataset", "register-run", "workflow-run:pipe-r1"],
        env=env, catch_exceptions=False,
    )
    assert reg.exit_code == 0, reg.output
    build = runner.invoke(
        science_cli, ["graph", "build", "--project-root", str(root)],
        env=env, catch_exceptions=False,
    )
    assert build.exit_code == 0, build.output

    derived = list(datasets.glob("pipe-*-clusters.md"))
    assert len(derived) == 1, f"expected 1 derived dataset, got {[p.name for p in derived]}"
    return f"dataset:{derived[0].stem}"


@pytest.fixture
def registrable_run_project(tmp_path: Path) -> tuple[Path, str]:
    """A project with a registered run + built graph; returns (root, dataset_id)."""
    dataset_id = _seed_stochastic_pipeline(tmp_path)
    return tmp_path, dataset_id


@pytest.fixture
def registrable_member_project(tmp_path: Path) -> tuple[Path, str, str]:
    """A member dataset joined by `member_of` to the run-produced parent.

    Returns (root, member_dataset_id, run_id). Reporting on the member must
    resolve the parent's run and mark it inherited.
    """
    from click.testing import CliRunner

    from science_tool.cli import main as science_cli

    parent_id = _seed_stochastic_pipeline(tmp_path)
    member = tmp_path / "entities" / "datasets" / "clusters-subset.md"
    member.write_text(
        '---\nid: "dataset:clusters-subset"\nkind: "dataset"\ntitle: "Clusters subset"\n'
        'origin: "derived"\n'
        "derivation:\n"
        '  kind: "member_of"\n'
        f'  parent_dataset: "{parent_id}"\n'
        '  member_key: "subset-a"\n---\n',
        encoding="utf-8",
    )
    build = CliRunner().invoke(
        science_cli, ["graph", "build", "--project-root", str(tmp_path)],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)}, catch_exceptions=False,
    )
    assert build.exit_code == 0, build.output
    return tmp_path, "dataset:clusters-subset", "workflow-run:pipe-r1"


# --- plan 4c: review-append fixtures -----------------------------------------

REVIEW_AT = datetime(2026, 8, 2, tzinfo=UTC)
REVIEW_RUN_ID = "run:2026-07-25-curation-sweep-a3f1"
AGENT = "curation-sweep"

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
SUBJECT = EntitySubject(ref="dataset:gtex-v8")
RULE = "dataset.cached-field-drift"
QUALS = {"field": "year"}


def _occurrence(
    finding_id: str,
    *,
    ingestion_ref: str = "ing:1",
    quals: dict | None = None,
    message: str = "drifted",
) -> Occurrence:
    # The occurrence's qualifiers must agree with the record's identity on every
    # identity-bearing key, so this helper takes them rather than hardcoding one set.
    return Occurrence(
        idempotency_key=occurrence_key(
            producer_id="dataset_anomalies",
            ingestion_ref=ingestion_ref,
            finding_id=finding_id,
        ),
        producer_id="dataset_anomalies",
        ingestion_ref=ingestion_ref,
        observed_at=NOW,
        severity="warn",
        message=message,
        qualifiers=dict(QUALS if quals is None else quals),
        evidence=(),
    )


def _build_audit_finding_record(
    quals: dict | None = None, *, message: str = "drifted"
) -> AuditFindingRecord:
    quals = QUALS if quals is None else quals
    finding_id = finding_fingerprint(
        rule_id=RULE, subject=SUBJECT, identity_qualifiers=quals
    )
    return AuditFindingRecord(
        finding_id=finding_id,
        fingerprint_version=1,
        rule_id=RULE,
        subject=SUBJECT,
        identity_qualifiers=quals,
        occurrences=(_occurrence(finding_id, quals=quals, message=message),),
        transitions=(
            Transition(
                from_status=None,
                to_status="proposed",
                actor="ingest",
                at=NOW,
                reason="detected",
            ),
        ),
        status="proposed",
    )


def _build_run_record(**overrides) -> AutonomousRunRecord:
    fields = {
        "id": REVIEW_RUN_ID,
        "agent": AGENT,
        "model": "test-model",
        "tier": RunTier.BELIEF_NEUTRAL,
        "branch": f"auto/{REVIEW_RUN_ID.removeprefix('run:')}",
        "base_commit": "a" * 40,
        "head_commit": "b" * 40,
        "toolkit_revision": "c" * 40,
        "policy_identity": PolicyIdentity(id="core-default", version="1"),
        "basis_digest": "d" * 64,
        "started": datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        "ended": datetime(2026, 7, 25, 9, 30, tzinfo=UTC),
        "budget": RunBudget(tokens=100, wall_clock_seconds=1800.0),
        "disposition": RunDisposition.CLEAN,
    }
    fields.update(overrides)
    return AutonomousRunRecord(**fields)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_science_project(root: Path) -> None:
    """A project with a real, non-empty belief basis.

    The shape is copied from `test_autonomy_perturbation_alarm.py`'s `_seed_project`,
    which is known to yield actual evidence units: a proposition, a belief-eligible
    evidence line bearing on it, and the paper the line is sourced from. `pmid` is quoted
    because unquoted digits parse as an int and pydantic rejects an int for a `str` field.
    """
    _write(root, "science.yaml", "name: lifecycle-fixture\nknowledge_profiles:\n  local: local\n")
    _write(root, "entities/propositions/p1.md", "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n")
    _write(
        root,
        "entities/papers/x.md",
        "---\n"
        "id: paper:x\n"
        "kind: paper\n"
        "title: X\n"
        "venue: Nature\n"
        'pmid: "111"\n'
        "year: 2020\n"
        "url: https://example.org/x\n"
        "---\n\nBody.\n",
    )
    _write(
        root,
        "entities/evidence-lines/e1.md",
        "---\n"
        "id: evidence-line:e1\n"
        "kind: evidence-line\n"
        "title: Evidence line\n"
        "stance: supports\n"
        "target: proposition:p1\n"
        "source: paper:x\n"
        "strength: strong\n"
        "belief_eligible: true\n"
        "---\n",
    )


def _seeded_git_project(tmp_path: Path) -> Path:
    """A git project with a real, non-empty belief basis, committed INCLUDING its graph.

    Building and committing `knowledge/graph.trig` here is load-bearing, not tidiness.
    `start_run` materializes, so a fixture that never built the graph leaves it untracked
    the moment `start` returns -- and every dirty-tree test below would then pass because
    of the supervisor's own write instead of the condition it names. With the graph
    already committed, the deterministic rebuild leaves the tree clean.
    """
    from science_tool.graph.materialize import materialize_graph

    root = tmp_path / "project"
    root.mkdir()
    _seed_science_project(root)
    materialize_graph(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    assert not _git(root, "status", "--porcelain"), "the fixture must start clean"
    return root


def _finish_run(project: Path, baseline_path: Path):
    from science_tool.autonomy.lifecycle import finish_run

    return finish_run(
        project, baseline_path=baseline_path, head=_git(project, "rev-parse", "HEAD"),
        ended=datetime(2026, 7, 25, 9, 30, tzinfo=UTC), tokens=100, wall_clock_seconds=1800.0,
    )


def _start_brokered_run(project: Path, tmp_path: Path, monkeypatch, *, inline_paths=()):
    from science_tool.autonomy.lifecycle import start_run

    monkeypatch.setenv("SCIENCE_CONTROL_PLANE", str(tmp_path / "control"))
    return start_run(
        project,
        agent=AGENT,
        model="test-model",
        tier=RunTier.BELIEF_NEUTRAL,
        short_id="a3f1",
        started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        evidence=_spec(inline_paths=inline_paths),
    )


def _spec(*, inline_paths: tuple[Path, ...] = ()) -> EvidenceSessionSpec:
    return EvidenceSessionSpec(
        budget=2,
        surface_policy=SurfacePolicy(deny_prefixes=("private",), notice="withheld"),
        instrument=InstrumentIdentity(ref="rubric.md", sha256="c" * 64, prompt_hash="d" * 64),
        inline_paths=inline_paths,
    )


@pytest.fixture
def stored_case(tmp_path: Path):
    """A project holding exactly one stored case, ready to review.

    Built through ``AuditFindingRecord``'s own constructor and written with
    ``write_case``, so every derived value is the one the model computes.
    """
    from science_tool.findings.storage import write_case

    record = _build_audit_finding_record()
    write_case(tmp_path, record)
    return record


@pytest.fixture
def human_attestation():
    from science_model.audit import ReviewAttestation

    def build(**overrides):
        fields = {
            "reviewer_kind": "human",
            "reviewer_ref": "keith",
            "run_ref": "manual-review-2026-08-02",
            "at": REVIEW_AT,
        }
        fields.update(overrides)
        return ReviewAttestation(**fields)

    return build


@pytest.fixture
def agent_attestation():
    from science_model.audit import ReviewAttestation

    def build(**overrides):
        fields = {
            "reviewer_kind": "agent",
            "reviewer_ref": AGENT,
            "lens": "rubric.md",
            "model": "test-model",
            "run_ref": REVIEW_RUN_ID,
            "at": REVIEW_AT,
        }
        fields.update(overrides)
        return ReviewAttestation(**fields)

    return build


@pytest.fixture
def unbrokered_run(tmp_path: Path):
    """A finalized run record with `evidence=None` — a run that was never brokered."""
    from science_tool.autonomy.record_writer import write_run_record

    def build(*, agent: str = AGENT, model: str = "test-model"):
        record = _build_run_record(
            id=REVIEW_RUN_ID,
            agent=agent,
            model=model,
            evidence=None,
        )
        write_run_record(tmp_path, record)
        return record

    return build


@pytest.fixture
def sealed_agent_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A project with a real sealed exposure, plus one stored case to review.

    The lifecycle fixture commits `knowledge/graph.trig` before `start_run`, and the
    toolkit cleanliness pin keeps this test about exposure replay while 4c is built.
    """
    from science_tool.autonomy import toolkit as toolkit_module
    from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
    from science_tool.evidence_broker.session import Session
    from science_tool.findings.storage import write_case

    project = _seeded_git_project(tmp_path)
    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)
    baseline = _start_brokered_run(project, tmp_path, monkeypatch)
    assert baseline.evidence is not None
    Session(project, baseline.evidence).request(
        EvidenceRequest(op=EvidenceOp.READ, target="science.yaml")
    )
    outcome = _finish_run(
        project, baseline.evidence.journal_path.parent / "baseline.json"
    )
    assert outcome.record is not None and outcome.record.evidence is not None

    record = _build_audit_finding_record()
    write_case(project, record)
    return project, record, baseline.evidence.journal_path.parent


@pytest.fixture
def case_files():
    """Snapshot the canonical case files only.

    Entering ``locked_store`` creates ``.ingest.lock``; refused appends must compare
    the canonical case bytes rather than treating that operational file as a write.
    """

    def snapshot(project_root: Path) -> dict[str, bytes]:
        cases = project_root / "doc" / "audits" / "cases"
        return {p.name: p.read_bytes() for p in sorted(cases.glob("*.md"))}

    return snapshot


@pytest.fixture
def plant_attacks(tmp_path: Path):
    """Factory: arm a repository with every git-config vector the write primitives reach.

    Returns `plant(root) -> sentinels_dir`. Each vector writes a sentinel file into that
    directory; a test's assertion is that the directory is still empty afterwards.

    NOTHING IS PLANTED AS AN UNTRACKED FILE IN THE PROJECT. `start_run`'s
    `assert_repository_is_at` refuses any dirty tree, untracked files included, so a driver
    script dropped beside the entities would make the run refuse BEFORE the vector was
    reached -- the test would pass without the defence ever running. The scripts live in
    `workshop`, a SIBLING of the repository under test; everything else lives under `.git/`,
    which git does not report.

    For the same reason the filter attribute goes in `$GIT_DIR/info/attributes` rather than an
    untracked `.gitattributes`. That is also the stronger probe: it is one of the three
    attribute layers `_filter_driver_overrides` covers, `--attr-source` does not reach it, and
    it is invisible to `git status` -- the actor-controlled layer the threat model is about.
    """
    workshop = tmp_path / "workshop"
    sentinels = workshop / "sentinels"
    sentinels.mkdir(parents=True, exist_ok=True)

    def _script(name: str, body: str = "") -> Path:
        path = workshop / f"{name}.sh"
        path.write_text(f"#!/bin/sh\ntouch {sentinels / name}\n{body}", encoding="utf-8")
        path.chmod(0o755)
        return path

    def _plant(root: Path) -> Path:
        hooks = root / ".git" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        # `prepare-commit-msg` is planted because the probe claims it: a hook named in the
        # docstring and absent from the fixture is a coverage claim nothing backs.
        for hook in (
            "pre-commit", "prepare-commit-msg", "commit-msg", "post-commit", "post-checkout"
        ):
            path = hooks / hook
            path.write_text(f"#!/bin/sh\ntouch {sentinels / hook}\n", encoding="utf-8")
            path.chmod(0o755)

        driver = _script("filter", "cat\n")
        gpg = _script("gpg", "exit 1\n")
        fsmonitor = _script("fsmonitor")

        (root / ".git" / "info").mkdir(parents=True, exist_ok=True)
        (root / ".git" / "info" / "attributes").write_text("* filter=evil\n", encoding="utf-8")
        config = root / ".git" / "config"
        config.write_text(
            config.read_text(encoding="utf-8")
            + f'[filter "evil"]\n\tclean = {driver}\n\tsmudge = {driver}\n'
            + f"[core]\n\tfsmonitor = {fsmonitor}\n"
            + "[commit]\n\tgpgsign = true\n"
            + f"[gpg]\n\tprogram = {gpg}\n",
            encoding="utf-8",
        )
        return sentinels

    return _plant


@pytest.fixture
def ungraphed_project(tmp_path: Path) -> Path:
    """A git project with a real belief basis and NO committed `knowledge/graph.trig`.

    The distinction from `test_autonomy_lifecycle.py`'s `project` fixture is the whole point.
    That one materializes and commits the graph before `git init`, so `start_run`'s rebuild is
    byte-identical and leaves the tree clean -- which makes it useless for testing that
    `start_run` cleans up after itself, because nothing is left to clean. This one has never
    materialized, so the rebuild is the supervisor's own residue.
    """
    import subprocess

    from science_tool.boundary.config import BoundaryConfig
    from science_tool.boundary.generate import render_managed_block, splice_managed_block

    root = tmp_path / "ungraphed"
    (root / "entities" / "propositions").mkdir(parents=True)
    (root / "entities" / "papers").mkdir(parents=True)
    (root / "entities" / "evidence-lines").mkdir(parents=True)
    (root / "science.yaml").write_text(
        "name: harness-fixture\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    (root / "entities" / "propositions" / "p1.md").write_text(
        "---\nid: proposition:p1\nkind: proposition\ntitle: P1\n---\n\nClaim.\n", encoding="utf-8"
    )
    (root / "entities" / "papers" / "x.md").write_text(
        "---\nid: paper:x\nkind: paper\ntitle: X\nvenue: Nature\n"
        'pmid: "111"\nyear: 2020\nurl: https://example.org/x\n---\n\nBody.\n',
        encoding="utf-8",
    )
    (root / "entities" / "evidence-lines" / "e1.md").write_text(
        "---\nid: evidence-line:e1\nkind: evidence-line\ntitle: Evidence line\n"
        "stance: supports\ntarget: proposition:p1\nsource: paper:x\n"
        "strength: strong\nbelief_eligible: true\n---\n",
        encoding="utf-8",
    )
    # A real enrolled project carries the science-managed boundary block in its root
    # `.gitignore` -- this fixture has no declared boundary roots, but the block is
    # unconditional (it also ignores the ingestion lock), so it renders even here.
    (root / ".gitignore").write_text(
        splice_managed_block("", render_managed_block(BoundaryConfig())), encoding="utf-8"
    )
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", "base")):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
            capture_output=True, check=True,
        )
    return root


@pytest.fixture
def supervised_project(ungraphed_project: Path, tmp_path: Path, monkeypatch) -> Path:
    """`ungraphed_project` with the toolkit-cleanliness check and the control plane pinned.

    `assert_toolkit_matches` refuses a dirty judging toolkit, and the checkout these tests run
    in is dirty exactly while this plan is being implemented -- which is not what any harness
    test is about. Lifted from `test_autonomy_lifecycle.py`'s `pinned_toolkit` fixture.

    `SCIENCE_CONTROL_PLANE` is pinned for a second, independent reason, and it is not tidiness.
    The harness derives its baseline path from `run_dir`, which defaults to the REAL
    `$XDG_STATE_HOME/science/runs/<project-key>/<run-slug>/`. That location outlives the
    process, while `project_key` is only a digest of the project path -- so a `tmp_path` that
    pytest ever reuses resolves to a directory that already holds a baseline, and `start_run`
    correctly refuses to overwrite a run's before-state. The failure is a stale directory in
    the developer's home, not anything about the run, and the tests would also be writing
    there. Every other autonomy suite pins this variable for the same reason.
    """
    from science_tool.autonomy import toolkit as toolkit_module

    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)
    monkeypatch.setenv("SCIENCE_CONTROL_PLANE", str(tmp_path / "control"))
    return ungraphed_project
