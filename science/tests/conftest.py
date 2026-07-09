from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
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


#: Splice this into a hand-authored `workflow-run` frontmatter block so
#: `register-run`'s fail-loud fingerprint capture (Task 6b) has an authored
#: executor/localities/seed_policy to work with. Pairs with `seed_git_repo`,
#: which supplies the `config.yaml` this declares as `config_snapshot`.
REGISTER_RUN_FINGERPRINT_FRONTMATTER = (
    "config_snapshot: config.yaml\n"
    "fingerprint:\n"
    "  executor: local\n"
    "  input_artifact_locality: science-managed\n"
    "  output_artifact_locality: science-managed\n"
    "  seed_policy: {kind: deterministic}\n"
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
