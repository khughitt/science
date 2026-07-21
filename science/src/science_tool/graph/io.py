from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, TypedDict

import yaml
from rdflib import BNode, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD
from science_model.reasoning import MembershipRole

from science_tool.data_root import PROJECT_CONFIG_FILENAME, project_config_path

PROJECT_NS = Namespace("http://example.org/project/")
SCI_NS = Namespace("http://example.org/science/vocab/")
SCIC_NS = Namespace("http://example.org/science/vocab/causal/")
SCHEMA_NS = Namespace("https://schema.org/")
BIOLINK_NS = Namespace("https://w3id.org/biolink/vocab/")
CITO_NS = Namespace("http://purl.org/spar/cito/")
DCTERMS_NS = Namespace("http://purl.org/dc/terms/")
DCAT_NS = Namespace("http://www.w3.org/ns/dcat#")
REVISION_URI = URIRef(PROJECT_NS["graph_revision"])

# Bundle-membership plumbing (NON-truth-apt; carries no belief, takes no evidence).
# A BundleMembership node annotates a (proposition, frame) cito:discusses edge with its role.
#   SCI_NS.BundleMembership          -- rdf:type of the membership node
#   SCI_NS.membershipProposition     -- node -> proposition IRI
#   SCI_NS.membershipFrame           -- node -> bundle (hypothesis/mechanism) IRI
#   SCI_NS.membershipRole            -- node -> Literal(MembershipRole value)


def entity_uri_for_ref(ref: str) -> URIRef:
    if ":" not in ref:
        raise ValueError(f"invalid entity ref {ref!r}")
    kind, slug = ref.split(":", 1)
    if not kind or not slug:
        raise ValueError(f"invalid entity ref {ref!r}")
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])


def membership_uri_for(prop_cid: str, frame_cid: str) -> URIRef:
    """Deterministic IRI for a (proposition, frame) BundleMembership node."""
    slug = f"{prop_cid}__{frame_cid}".replace(":", "_").replace("/", "_")
    return URIRef(PROJECT_NS[f"membership/{slug}"])


def emit_discusses_membership(
    knowledge: Graph,
    *,
    prop_uri: URIRef,
    frame_uri: URIRef,
    prop_cid: str,
    frame_cid: str,
    role: MembershipRole = MembershipRole.CORE,
) -> None:
    """The one place a bundle-membership cito:discusses edge is emitted.

    Always emits the plain (prop, cito:discusses, frame) triple, plus a
    non-truth-apt BundleMembership node carrying the role. Precondition guard:
    the frame must be a bundle (hypothesis/mechanism) — callers route only
    membership edges here; non-bundle discusses keeps the generic path.
    """
    frame_kind = frame_cid.split(":", 1)[0]
    if frame_kind not in ("hypothesis", "mechanism"):
        raise ValueError(
            f"{prop_cid} discusses {frame_cid!r}, which is a {frame_kind!r}, not a "
            "bundle (hypothesis/mechanism); membership roles are only valid on bundle "
            "frames."
        )
    knowledge.add((prop_uri, CITO_NS.discusses, frame_uri))
    node = membership_uri_for(prop_cid, frame_cid)
    knowledge.add((node, RDF.type, SCI_NS.BundleMembership))
    knowledge.add((node, SCI_NS.membershipProposition, prop_uri))
    knowledge.add((node, SCI_NS.membershipFrame, frame_uri))
    knowledge.add((node, SCI_NS.membershipRole, Literal(role.value)))


_SERIALIZER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("rdf", str(RDF)),
    ("prov", str(PROV)),
    ("schema", str(SCHEMA_NS)),
    ("skos", str(SKOS)),
    ("xsd", str(XSD)),
    ("sci", str(SCI_NS)),
    ("scic", str(SCIC_NS)),
    ("biolink", str(BIOLINK_NS)),
    ("cito", str(CITO_NS)),
    ("dcterms", str(DCTERMS_NS)),
    ("dcat", str(DCAT_NS)),
)
_SAFE_PREFIX_LOCAL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]*$")


def save_canonical_graph_dataset(
    dataset: Dataset,
    graph_path: Path,
    *,
    preferred_graph_order: Sequence[URIRef | str] = (),
) -> None:
    """Persist a canonical graph artifact with deterministic TriG output."""
    _assert_no_blank_nodes(dataset)
    _upsert_revision_metadata(dataset, graph_path, preferred_graph_order=preferred_graph_order)
    _assert_no_blank_nodes(dataset)
    graph_path.write_text(
        _serialize_dataset_deterministically(dataset, preferred_graph_order=preferred_graph_order),
        encoding="utf-8",
    )


def _assert_no_blank_nodes(dataset: Dataset) -> None:
    for graph in dataset.graphs():
        if isinstance(graph.identifier, BNode):
            raise ValueError("Blank nodes are not supported in canonical graph output")
        for subject, predicate, obj in graph:
            if isinstance(subject, BNode) or isinstance(predicate, BNode) or isinstance(obj, BNode):
                raise ValueError("Blank nodes are not supported in canonical graph output")


def _upsert_revision_metadata(
    dataset: Dataset,
    graph_path: Path,
    *,
    preferred_graph_order: Sequence[URIRef | str],
) -> None:
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    for triple in list(provenance.triples((REVISION_URI, None, None))):
        provenance.remove(triple)

    manifest = build_input_manifest(graph_path=graph_path)
    manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    revision_time = _revision_timestamp_from_manifest(manifest)

    semantic_text = _serialize_dataset_deterministically(dataset, preferred_graph_order=preferred_graph_order)
    semantic_hash = hashlib.sha256(semantic_text.encode("utf-8")).hexdigest()

    provenance.add((REVISION_URI, RDF.type, PROV.Entity))
    provenance.add((REVISION_URI, SCHEMA_NS.name, Literal("graph-revision")))
    provenance.add((REVISION_URI, SCHEMA_NS.dateModified, Literal(revision_time, datatype=XSD.dateTime)))
    provenance.add((REVISION_URI, SCHEMA_NS.text, Literal(manifest_json)))
    provenance.add((REVISION_URI, SCHEMA_NS.sha256, Literal(semantic_hash)))


def _serialize_dataset_deterministically(
    dataset: Dataset,
    *,
    preferred_graph_order: Sequence[URIRef | str] = (),
) -> str:
    lines = [f"@prefix {prefix}: <{namespace}> ." for prefix, namespace in _SERIALIZER_PREFIXES]
    lines.append("")

    default_graph = dataset.default_graph
    if len(default_graph):
        lines.extend(_render_graph_triples(default_graph))
        lines.append("")

    named_graphs: dict[str, object] = {}
    for graph in dataset.graphs():
        if graph.identifier == default_graph.identifier:
            continue
        named_graphs[str(graph.identifier)] = graph

    ordered_graph_ids: list[str] = []
    for graph_id in [str(identifier) for identifier in preferred_graph_order]:
        if graph_id in named_graphs and graph_id not in ordered_graph_ids:
            ordered_graph_ids.append(graph_id)
    ordered_graph_ids.extend(sorted(graph_id for graph_id in named_graphs if graph_id not in ordered_graph_ids))

    for index, graph_id in enumerate(ordered_graph_ids):
        graph = named_graphs[graph_id]
        lines.append(f"<{graph_id}> {{")
        graph_lines = _render_graph_triples(graph, indent="    ")
        lines.extend(graph_lines)
        lines.append("}")
        if index != len(ordered_graph_ids) - 1:
            lines.append("")

    return "\n".join(lines) + "\n"


def _render_graph_triples(graph, *, indent: str = "") -> list[str]:
    triples = sorted(graph, key=_triple_sort_key)
    if not triples:
        return []

    grouped: list[tuple[object, list[tuple[object, list[object]]]]] = []
    for subject, predicate, obj in triples:
        if not grouped or grouped[-1][0] != subject:
            grouped.append((subject, []))
        predicates = grouped[-1][1]
        if not predicates or predicates[-1][0] != predicate:
            predicates.append((predicate, []))
        predicates[-1][1].append(obj)

    lines: list[str] = []
    for subject, predicates in grouped:
        rendered_subject = _format_trig_term(subject)
        for predicate_index, (predicate, objects) in enumerate(predicates):
            rendered_predicate = "a" if predicate == RDF.type else _format_trig_term(predicate)
            rendered_objects = _render_object_list(objects, indent=indent)
            suffix = " ." if predicate_index == len(predicates) - 1 else " ;"
            if predicate_index == 0:
                lines.append(f"{indent}{rendered_subject} {rendered_predicate} {rendered_objects}{suffix}")
                continue
            lines.append(f"{indent}    {rendered_predicate} {rendered_objects}{suffix}")
    return lines


def _render_object_list(objects: list[object], *, indent: str) -> str:
    rendered = [_format_trig_term(obj) for obj in objects]
    if len(rendered) == 1:
        return rendered[0]
    separator = ",\n" + indent + "        "
    return separator.join(rendered)


def _triple_sort_key(triple: tuple[object, object, object]) -> tuple[tuple[int, str], tuple[int, str], tuple[int, str]]:
    subject, predicate, obj = triple
    return (_term_sort_key(subject), _term_sort_key(predicate), _term_sort_key(obj))


def _term_sort_key(term: object) -> tuple[int, str]:
    if isinstance(term, URIRef):
        return (0, str(term))
    if isinstance(term, Literal):
        return (1, f"{term.language or ''}|{term.datatype or ''}|{term}")
    msg = f"Unsupported RDF term for deterministic serialization: {term!r}"
    raise TypeError(msg)


def _format_trig_term(term: object) -> str:
    if isinstance(term, URIRef):
        return _format_uri(term)
    if isinstance(term, Literal):
        return term.n3()
    msg = f"Unsupported RDF term for deterministic serialization: {term!r}"
    raise TypeError(msg)


def _format_uri(uri: URIRef) -> str:
    uri_text = str(uri)
    for prefix, namespace in _SERIALIZER_PREFIXES:
        if not uri_text.startswith(namespace):
            continue
        local = uri_text.removeprefix(namespace)
        if _SAFE_PREFIX_LOCAL_RE.match(local):
            return f"{prefix}:{local}"
    return f"<{uri_text}>"


def _graph_uri(layer: str) -> URIRef:
    return URIRef(PROJECT_NS[layer])


#: Envelope version. v1 was a FLAT ``{path: {sha256, mtime_ns}}`` mapping, which could
#: not distinguish "this directory was walked and is empty" from "this directory was
#: never walked". v2 records the walk-set explicitly.
REVISION_MANIFEST_SCHEMA = 2


class RevisionManifest(TypedDict):
    """The graph-revision input manifest.

    ``walked`` is the point of the envelope. A flat file mapping cannot answer the
    question the diff actually asks -- *did we look?* -- so a directory that was never
    walked (because it was omitted from ``include_dirs``, as ``entities/`` was) looked
    exactly like a directory containing no files. Every file under it was silently
    exempt from staleness. Recording the walk-set makes "we did not look here" a
    representable, checkable fact.
    """

    schema: int
    walked: list[str]
    files: dict[str, dict[str, int | str]]


#: Schema of a manifest that is absent or unparseable. Distinct from a v2 manifest that
#: honestly recorded an EMPTY walk-set: "we never looked" and "we looked and there was
#: nothing there" are different facts, and collapsing them is the bug this envelope fixes.
REVISION_MANIFEST_SCHEMA_ABSENT = 0
#: v1: a flat {path: metadata} mapping. Carried no walk-set, so it cannot say what it
#: looked at -- which is why a v1 baseline reads as unwired rather than as "no changes".
REVISION_MANIFEST_SCHEMA_V1 = 1


def _empty_manifest() -> RevisionManifest:
    return RevisionManifest(schema=REVISION_MANIFEST_SCHEMA_ABSENT, walked=[], files={})


def _revision_timestamp_from_manifest(manifest: RevisionManifest) -> str:
    latest_mtime_ns = max(
        (
            int(metadata["mtime_ns"])
            for metadata in manifest["files"].values()
            if isinstance(metadata, dict) and isinstance(metadata.get("mtime_ns"), int)
        ),
        default=0,
    )
    revision_time = datetime.fromtimestamp(latest_mtime_ns / 1_000_000_000, tz=timezone.utc)
    return revision_time.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_revision_manifest(dataset: Dataset) -> RevisionManifest:
    """Read the stored manifest.

    A v1 (flat, un-versioned) manifest is returned with an EMPTY ``walked`` list, which
    the diff reads as "never walked" -- i.e. unwired. That is deliberate: a v1 manifest
    genuinely does not know which directories were walked, and guessing would reintroduce
    the exact silence this envelope exists to remove.
    """
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    manifest_literal = next(provenance.objects(REVISION_URI, SCHEMA_NS.text), None)
    if manifest_literal is None:
        return _empty_manifest()

    try:
        loaded = json.loads(str(manifest_literal))
    except json.JSONDecodeError:
        return _empty_manifest()
    if not isinstance(loaded, dict):
        return _empty_manifest()

    if loaded.get("schema") == REVISION_MANIFEST_SCHEMA:
        raw_files = loaded.get("files")
        raw_walked = loaded.get("walked")
        files_src = raw_files if isinstance(raw_files, dict) else {}
        walked = [entry for entry in raw_walked if isinstance(entry, str)] if isinstance(raw_walked, list) else []
        schema = REVISION_MANIFEST_SCHEMA
    else:
        # v1: a flat path -> metadata mapping. No walk-set was recorded, and none can be
        # inferred -- so it stays empty and the schema stays 1. A v1 baseline cannot say
        # what it looked at, which is precisely why the diff must not trust its silence.
        files_src = loaded
        walked = []
        schema = REVISION_MANIFEST_SCHEMA_V1

    files: dict[str, dict[str, int | str]] = {}
    for key, value in files_src.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        sha = value.get("sha256")
        mtime = value.get("mtime_ns")
        if not isinstance(sha, str):
            continue
        if not isinstance(mtime, int):
            continue
        files[key] = {"sha256": sha, "mtime_ns": mtime}
    return RevisionManifest(schema=schema, walked=sorted(walked), files=files)


def build_input_manifest(graph_path: Path) -> RevisionManifest:
    """Walk the project's graph inputs and record BOTH the files and the walk-set.

    ``entities/`` is walked. It was previously omitted from ``include_dirs`` entirely,
    so every entity file -- the bulk of a project's authored content -- was invisible to
    ``science graph diff``: edit a hypothesis, and the graph reported itself up to date.
    """
    project_root = project_root_from_graph_path(graph_path)

    from science_tool.paths import resolve_paths

    pp = resolve_paths(project_root)
    include_dirs: list[Path] = [
        pp.entities_dir,
        pp.doc_dir,
        pp.specs_dir,
        pp.papers_dir / "summaries",
        pp.code_dir,
        pp.tasks_dir,
        pp.knowledge_dir / "sources",
    ]
    notes_dir = project_root / "notes"
    if notes_dir.is_dir():
        include_dirs.append(notes_dir)

    include_files = ("README.md", PROJECT_CONFIG_FILENAME, "CLAUDE.md", "AGENTS.md")

    files: set[Path] = set()
    for file_name in include_files:
        candidate = project_root / file_name
        if candidate.is_file():
            files.add(candidate)

    walked: list[str] = []
    for base in include_dirs:
        if not base.is_dir():
            continue
        # Record it as walked BEFORE the rglob: a directory that exists and holds no
        # files is walked-and-empty, which is a different fact from never-walked.
        walked.append(base.relative_to(project_root).as_posix())
        for candidate in base.rglob("*"):
            if candidate.is_file():
                files.add(candidate)

    exclude_patterns = _revision_manifest_excludes(project_root)
    manifest_files: dict[str, dict[str, int | str]] = {}
    for file_path in sorted(files):
        rel_path = file_path.relative_to(project_root).as_posix()
        if _is_generated_python_cache(rel_path):
            continue
        if _matches_revision_manifest_exclude(rel_path, exclude_patterns):
            continue
        stat = file_path.stat()
        manifest_files[rel_path] = {
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": _sha256_file(file_path),
        }
    return RevisionManifest(schema=REVISION_MANIFEST_SCHEMA, walked=sorted(walked), files=manifest_files)


def _is_generated_python_cache(rel_path: str) -> bool:
    parts = rel_path.split("/")
    return "__pycache__" in parts or rel_path.endswith((".pyc", ".pyo"))


# Transient tidying ledgers contribute NO triples but were still hashed into the
# revision manifest, so editing one flipped the graph to stale and made `science
# validate` warn about a file the graph does not contain. Ledgers are necessarily
# written *after* the entity edits they record, so the natural workflow guaranteed a
# dirty graph every sweep. Every project inherits these excludes instead of
# rediscovering the knob (fb-2026-07-17-001, D2 Option C). The split is deliberately
# NOT directory-aligned: `doc/meta/` mixes transient `*-next-steps.md` with durable
# crosswalks/memos, so the glob is `doc/meta/*-next-steps.md`, not `doc/meta/*`.
DEFAULT_REVISION_MANIFEST_EXCLUDES: tuple[str, ...] = (
    "doc/curations/*.md",
    "doc/meta/*-next-steps.md",
)


def _revision_manifest_excludes(project_root: Path) -> tuple[str, ...]:
    patterns: list[str] = list(DEFAULT_REVISION_MANIFEST_EXCLUDES)
    config_path = project_config_path(project_root)
    if not config_path.is_file():
        return tuple(patterns)
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return tuple(patterns)
    graph = loaded.get("graph") or {}
    if not isinstance(graph, dict):
        return tuple(patterns)
    if "revision_manifest_excludes" not in graph:
        return tuple(patterns)
    raw = graph["revision_manifest_excludes"]
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError("science.yaml graph.revision_manifest_excludes must be a list of strings")
    for item in raw:
        pattern = item.strip()
        if not pattern:
            raise ValueError("science.yaml graph.revision_manifest_excludes entries must be non-empty")
        path = Path(pattern)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(
                "science.yaml graph.revision_manifest_excludes entries must be relative project paths"
            )
        normalized = path.as_posix()
        if normalized not in patterns:
            patterns.append(normalized)
    return tuple(patterns)


def _matches_revision_manifest_exclude(rel_path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(rel_path, pattern) for pattern in patterns)


def project_root_from_graph_path(graph_path: Path) -> Path:
    if graph_path.name in {"graph.trig", "composite.trig"} and graph_path.parent.name == "knowledge":
        return graph_path.parent.parent
    return graph_path.parent


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
