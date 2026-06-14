from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

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


def build_inquiry_graph(graph_path: Path, slug: str = "i01", *, profile: str = "investigation", **inquiry: object):
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
    """
    from rdflib import Dataset

    from science_model.patch_definition import PatchDefinitionEntity
    from science_tool.graph.inquiry_compile import emit_inquiry_views
    from science_tool.graph.store import _load_dataset, _save_dataset

    ent = PatchDefinitionEntity(
        id=f"patch-definition:{slug}",
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
        file_path=f"entities/patches/{slug}.md",
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
