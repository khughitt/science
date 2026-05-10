from __future__ import annotations

import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from rdflib import Dataset, URIRef
from rdflib.namespace import Namespace

from science_tool.graph.io import PROJECT_NS

PROV_WAS_DERIVED_FROM = URIRef("http://www.w3.org/ns/prov#wasDerivedFrom")
SCHEMA_IDENTIFIER = URIRef("https://schema.org/identifier")
DCTERMS = Namespace("http://purl.org/dc/terms/")
SCI_CREATED_PRED = URIRef("https://w3id.org/science#created")


def source_path_for(entity_uri: URIRef, dataset: Dataset) -> str | None:
    """Return the source file path for an entity, or None if no provenance edge exists."""
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    for source_uri in provenance.objects(entity_uri, PROV_WAS_DERIVED_FROM):
        for identifier in provenance.objects(source_uri, SCHEMA_IDENTIFIER):
            return str(identifier)
    return None


def created_date_for(
    entity_uri: URIRef,
    dataset: Dataset,
    *,
    source_path: str | None,
    repo_root: Path | None = None,
) -> date | None:
    """Resolve created date with fallback chain: graph → git first-commit → mtime."""
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for predicate in (DCTERMS.created, SCI_CREATED_PRED):
        for literal in knowledge.objects(entity_uri, predicate):
            parsed = _parse_iso_date(str(literal))
            if parsed is not None:
                return parsed

    if source_path is None:
        return None

    if repo_root is not None:
        git_date = _git_first_commit_date(repo_root, source_path)
        if git_date is not None:
            return git_date

    path = Path(source_path)
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
    return None


def _parse_iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def _git_first_commit_date(repo_root: Path, source_path: str) -> date | None:
    rel = source_path
    try:
        rel = str(Path(source_path).resolve().relative_to(repo_root.resolve()))
    except ValueError:
        pass
    try:
        result = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--", rel],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    return _parse_iso_date(lines[-1])  # `git log` is reverse chronological; oldest is last
