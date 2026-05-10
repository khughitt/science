from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import XSD

from science_tool.graph.io import PROJECT_NS

from science_tool.wander.provenance import created_date_for, source_path_for

PROV = URIRef("http://www.w3.org/ns/prov#wasDerivedFrom")
SCHEMA_IDENTIFIER = URIRef("https://schema.org/identifier")
DCTERMS_CREATED = URIRef("http://purl.org/dc/terms/created")


def _entity_uri(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _add_provenance(dataset: Dataset, *, entity_uri: URIRef, source_path: str) -> URIRef:
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    safe = source_path.replace("/", "_").replace(" ", "_").lower()
    source_uri = URIRef(PROJECT_NS[f"source/{safe}"])
    provenance.add((entity_uri, PROV, source_uri))
    provenance.add((source_uri, SCHEMA_IDENTIFIER, Literal(source_path)))
    return source_uri


def test_source_path_for_returns_relative_path() -> None:
    dataset = Dataset()
    entity = _entity_uri("hypothesis/h1")
    _add_provenance(dataset, entity_uri=entity, source_path="doc/hypotheses/h1.md")

    assert source_path_for(entity, dataset) == "doc/hypotheses/h1.md"


def test_source_path_for_returns_none_when_no_provenance() -> None:
    dataset = Dataset()
    assert source_path_for(_entity_uri("hypothesis/missing"), dataset) is None


def test_created_date_uses_dcterms_when_available() -> None:
    dataset = Dataset()
    entity = _entity_uri("hypothesis/h1")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((entity, DCTERMS_CREATED, Literal("2026-01-15", datatype=XSD.date)))

    assert created_date_for(entity, dataset, source_path=None) == date(2026, 1, 15)


def test_created_date_falls_back_to_git_first_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    file_path = repo / "doc" / "h1.md"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("# H1\n")
    subprocess.run(["git", "add", "doc/h1.md"], cwd=repo, check=True)
    env = {**os.environ, "GIT_AUTHOR_DATE": "2026-02-10T12:00:00", "GIT_COMMITTER_DATE": "2026-02-10T12:00:00"}
    subprocess.run(["git", "commit", "-q", "-m", "add"], cwd=repo, check=True, env=env)

    dataset = Dataset()  # no dcterms:created in graph
    result = created_date_for(
        _entity_uri("hypothesis/h1"),
        dataset,
        source_path=str(file_path),
        repo_root=repo,
    )

    assert result == date(2026, 2, 10)


def test_created_date_falls_back_to_mtime_when_not_in_git(tmp_path: Path) -> None:
    file_path = tmp_path / "loose.md"
    file_path.write_text("hello")
    os.utime(file_path, (1717200000, 1717200000))

    dataset = Dataset()
    result = created_date_for(
        _entity_uri("hypothesis/h1"),
        dataset,
        source_path=str(file_path),
        repo_root=tmp_path,
    )

    assert isinstance(result, date)


def test_created_date_returns_none_with_no_inputs() -> None:
    assert created_date_for(_entity_uri("hypothesis/h1"), Dataset(), source_path=None) is None
