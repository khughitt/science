import os
import subprocess
from pathlib import Path

from rdflib import Literal, URIRef

from science_tool.graph.materialize import _build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def test_code_edit_flips_finding_to_needs_review(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    local = tmp_path / "knowledge" / "local"
    local.mkdir(parents=True)
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# decision_bearing: true\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:x\ntype: dataset\ntitle: X\n"
        "status: active\norigin: derived\ntier: use-now\nproduced_by: [code-file:run.py]\n",
        encoding="utf-8",
    )
    # A finding reviewed in January, citing the dataset as a source.
    # Markdown entities are scanned under doc/ (MarkdownAdapter default roots:
    # ["doc", "specs", "research/packages"]) — NOT knowledge/local, which is for
    # aggregate YAML sources.
    findings = tmp_path / "entities" / "findings"
    findings.mkdir(parents=True)
    (findings / "f1.md").write_text(
        "---\nid: finding:f1\nkind: finding\ntitle: F1\nstatus: active\n"
        "created: 2026-01-01\nsource_refs:\n  - dataset:x\n"
        "review_state:\n  last_reviewed: 2026-01-15\n---\nbody\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    # Code file's last content-changing commit is in April — newer than the finding's baseline.
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)

    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)
    finally:
        os.chdir(prev)

    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    code_uri = URIRef(PROJECT_NS["code-file/run.py"])
    finding_uri = URIRef(PROJECT_NS["finding/f1"])

    # Closure: code-file bears_on finding (through the operational dataset conduit).
    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    assert (str(code_uri), str(finding_uri)) in pairs

    # Freshness: the finding flips to needs-review, triggered by the code file.
    assert (finding_uri, SCI_NS.freshnessState, Literal("needs-review")) in knowledge
    assert (finding_uri, SCI_NS.triggeredBy, code_uri) in knowledge
