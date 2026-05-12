# science/src/science_tool/annotation/io.py
"""Sidecar TriG I/O.

Parser uses rdflib.Dataset (default_union=True) so the named-graph URI
is irrelevant — we walk all triples in the file. The publicID is set to
the sidecar's directory URI so that relative source IRIs like
<citation-audit-pilot.md> resolve to absolute file URIs at parse time;
the parser strips that prefix back off before storing into the model
(`SpecificResource.source` holds the bare relative path as authored).

Writer (Task 5) hand-rolls canonical TriG for deterministic git-friendly
output. See spec §File layout and §Concrete sidecar example.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from rdflib import RDF, Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS, Namespace, PROV
from rdflib.term import Node

from science_tool.annotation.model import (
    Annotation,
    AuditLedger,
    IriBody,
    Motivation,
    PriorState,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
    Body,
)

OA = Namespace("http://www.w3.org/ns/oa#")
SCI = Namespace("http://example.org/science/vocab/")

_MD_SUFFIX = ".md"
_SIDECAR_SUFFIX = ".anno.trig"


def sidecar_for_markdown(md_path: Path) -> Path:
    """Return the sidecar Path for a markdown file.

    `foo.md` → `foo.anno.trig`; `paper.v1.md` → `paper.v1.anno.trig`.

    Raises ValueError if `md_path` does not end with `.md`.
    """
    name = md_path.name
    if not name.endswith(_MD_SUFFIX):
        raise ValueError(
            f"not a markdown path (expected '.md' suffix): {md_path}"
        )
    base = name[: -len(_MD_SUFFIX)]
    return md_path.with_name(base + _SIDECAR_SUFFIX)


def markdown_for_sidecar(sidecar_path: Path) -> Path:
    """Return the markdown Path for a sidecar file.

    `foo.anno.trig` → `foo.md`; `paper.v1.anno.trig` → `paper.v1.md`.

    Raises ValueError if `sidecar_path` does not end with `.anno.trig`.
    """
    name = sidecar_path.name
    if not name.endswith(_SIDECAR_SUFFIX):
        raise ValueError(
            f"not a sidecar path (expected '.anno.trig' suffix): {sidecar_path}"
        )
    base = name[: -len(_SIDECAR_SUFFIX)]
    return sidecar_path.with_name(base + _MD_SUFFIX)


def read_sidecar(path: Path) -> Sidecar:
    """Parse a `*.anno.trig` file into a Sidecar.

    Walks all named graphs in the file (via ``default_union=True``), so
    the wrapping graph URI is cosmetic. Relative source IRIs are
    normalized back to bare relative paths against the sidecar's
    directory.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    base_dir_uri = path.parent.resolve().as_uri() + "/"
    ds = Dataset(default_union=True)
    ds.parse(source=str(path), format="trig", publicID=base_dir_uri)

    shared_targets = tuple(_iter_shared_targets(ds, base_dir_uri))
    target_index = {t.id: t for t in shared_targets if t.id is not None}
    annotations = tuple(_iter_annotations(ds, target_index, base_dir_uri))
    ledgers = tuple(_iter_ledgers(ds))
    return Sidecar(
        annotations=annotations,
        ledgers=ledgers,
        shared_targets=shared_targets,
    )


def _iter_shared_targets(ds: Dataset, base_dir_uri: str) -> "list[SpecificResource]":
    out: list[SpecificResource] = []
    for subj in ds.subjects(RDF.type, OA.SpecificResource):
        if not isinstance(subj, URIRef):
            continue  # only named SpecificResources are "shared"
        target_id = _local_name(subj)
        source = _normalize_source_uri(
            _required(ds, subj, OA.hasSource, context="shared target"),
            base_dir_uri,
        )
        sel_node = _required(ds, subj, OA.hasSelector, context="shared target")
        selector = _read_selector(ds, sel_node)
        out.append(SpecificResource(source=source, selector=selector, id=target_id))
    return out


def _read_selector(ds: Dataset, node: Node) -> TextQuoteSelector:
    return TextQuoteSelector(
        exact=str(_required(ds, node, OA.exact, context="selector")),
        prefix=str(_required(ds, node, OA.prefix, context="selector")),
        suffix=str(_required(ds, node, OA.suffix, context="selector")),
    )


def _iter_annotations(
    ds: Dataset,
    target_index: "dict[str, SpecificResource]",
    base_dir_uri: str,
) -> "list[Annotation]":
    out: list[Annotation] = []
    for subj in ds.subjects(RDF.type, OA.Annotation):
        if not isinstance(subj, URIRef):
            continue  # annotations are always named
        ann_id = _local_name(subj)
        ctx = f"annotation {ann_id}"
        target = _read_target(ds, subj, target_index, base_dir_uri, ctx=ctx)
        bodies = tuple(_read_bodies(ds, subj, ctx=ctx))
        motivation = Motivation(
            _local_name(_required(ds, subj, OA.motivatedBy, context=ctx))
        )
        annotation_type = str(_required(ds, subj, SCI.annotationType, context=ctx))
        source = str(_required(ds, subj, SCI.source, context=ctx))
        status = Status(str(_required(ds, subj, SCI.status, context=ctx)))
        creator = str(_required(ds, subj, DCTERMS.creator, context=ctx))
        created = _read_dt(_required(ds, subj, DCTERMS.created, context=ctx))
        modified = _read_optional_dt(ds.value(subj, DCTERMS.modified))
        modified_by = _str_or_none(ds.value(subj, DCTERMS.contributor))
        content_hash = _str_or_none(ds.value(subj, SCI.contentHash))
        description = _str_or_none(ds.value(subj, DCTERMS.description))
        lifted_from = _str_or_none(ds.value(subj, SCI.liftedFrom))
        match_text = _str_or_none(ds.value(subj, SCI.matchText))
        prior_states = tuple(_read_prior_states(ds, subj))
        out.append(
            Annotation(
                id=ann_id,
                target=target,
                bodies=bodies,
                motivation=motivation,
                annotation_type=annotation_type,
                source=source,
                status=status,
                creator=creator,
                created=created,
                modified=modified,
                modified_by=modified_by,
                content_hash=content_hash,
                description=description,
                lifted_from=lifted_from,
                match_text=match_text,
                prior_states=prior_states,
            )
        )
    return out


def _read_target(
    ds: Dataset,
    ann: URIRef,
    target_index: "dict[str, SpecificResource]",
    base_dir_uri: str,
    *,
    ctx: str,
) -> SpecificResource:
    node = _required(ds, ann, OA.hasTarget, context=ctx)
    if isinstance(node, URIRef):
        # Reference to a shared target.
        target_id = _local_name(node)
        if target_id in target_index:
            return target_index[target_id]
    # Inline blank-node target.
    source = _normalize_source_uri(
        _required(ds, node, OA.hasSource, context=f"{ctx} target"),
        base_dir_uri,
    )
    sel_node = _required(ds, node, OA.hasSelector, context=f"{ctx} target")
    return SpecificResource(source=source, selector=_read_selector(ds, sel_node), id=None)


def _read_bodies(ds: Dataset, ann: URIRef, *, ctx: str) -> "list[Body]":
    bodies: list[Body] = []
    for body_node in ds.objects(ann, OA.hasBody):
        if isinstance(body_node, URIRef):
            bodies.append(IriBody(iri=str(body_node)))
            continue
        # Blank-node TextualBody.
        value = _required(ds, body_node, RDF.value, context=f"{ctx} body")
        fmt_node = ds.value(body_node, DCTERMS.format)
        fmt = str(fmt_node) if fmt_node is not None else "text/plain"
        bodies.append(TextualBody(value=str(value), format=fmt))
    if not bodies:
        raise ValueError(f"missing required oa:hasBody on {ctx}")
    return bodies


def _read_prior_states(ds: Dataset, ann: URIRef) -> "list[PriorState]":
    out: list[PriorState] = []
    for prior_node in ds.objects(ann, PROV.wasRevisionOf):
        status = Status(str(_required(ds, prior_node, SCI.status, context="prior state")))
        creator = str(_required(ds, prior_node, DCTERMS.creator, context="prior state"))
        created = _read_dt(_required(ds, prior_node, DCTERMS.created, context="prior state"))
        out.append(PriorState(status=status, creator=creator, created=created))
    return out


def _iter_ledgers(ds: Dataset) -> "list[AuditLedger]":
    out: list[AuditLedger] = []
    for subj in ds.subjects(RDF.type, SCI.AuditLedger):
        if not isinstance(subj, URIRef):
            continue
        led_id = _local_name(subj)
        ctx = f"ledger {led_id}"
        source = str(_required(ds, subj, SCI.source, context=ctx))
        hashes_node = ds.value(subj, SCI.auditedHashes)
        hashes = (
            tuple(str(item) for item in ds.items(hashes_node)) if hashes_node else ()
        )
        modified = _read_dt(_required(ds, subj, DCTERMS.modified, context=ctx))
        out.append(
            AuditLedger(
                id=led_id, source=source, audited_hashes=hashes, modified=modified
            )
        )
    return out


def _required(ds: Any, subj: Node, pred: URIRef, *, context: str) -> Node:
    """Look up a required predicate. Raise loudly if absent."""
    val = ds.value(subj, pred)
    if val is None:
        raise ValueError(f"missing required {pred} on {context} ({subj})")
    return val


def _str_or_none(node: Node | None) -> str | None:
    return None if node is None else str(node)


def _normalize_source_uri(uri_node: Node, base_dir_uri: str) -> str:
    """Strip the sidecar's directory URI prefix to recover the bare relative path.

    URIs that don't start with ``base_dir_uri`` (e.g., absolute http:// or
    cross-directory file://) are returned unchanged.
    """
    s = str(uri_node)
    if s.startswith(base_dir_uri):
        return s[len(base_dir_uri):]
    return s


def _local_name(node: Node | None) -> str:
    if node is None:
        return ""
    s = str(node)
    if "#" in s:
        return s.rsplit("#", 1)[1]
    return s.rsplit("/", 1)[-1]


def _read_dt(node: Node) -> datetime:
    if isinstance(node, Literal):
        py = node.toPython()
        if isinstance(py, datetime):
            return py
    return datetime.fromisoformat(str(node))


def _read_optional_dt(node: Node | None) -> datetime | None:
    if node is None:
        return None
    return _read_dt(node)


def write_sidecar(path: Path, sidecar: Sidecar) -> None:
    """Write a Sidecar to TriG with deterministic, git-friendly formatting.

    Hand-rolled rather than rdflib-serialized to control ordering and
    spacing; rdflib's TriG serializer randomizes blank-node IDs and
    triple ordering across runs.
    """
    lines: list[str] = []
    lines.append("@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
    lines.append("@prefix oa:   <http://www.w3.org/ns/oa#> .")
    lines.append("@prefix dc:   <http://purl.org/dc/terms/> .")
    lines.append("@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .")
    lines.append("@prefix prov: <http://www.w3.org/ns/prov#> .")
    lines.append("@prefix sci:  <http://example.org/science/vocab/> .")
    lines.append("@prefix anno: <#> .")
    lines.append("")
    lines.append("anno:annotations {")

    # Shared targets first (so by-ID references resolve), sorted.
    for target in sorted(sidecar.shared_targets, key=lambda t: t.id or ""):
        lines.extend(_emit_shared_target(target))
        lines.append("")

    # Annotations sorted by ID.
    for ann in sorted(sidecar.annotations, key=lambda a: a.id):
        lines.extend(_emit_annotation(ann))
        lines.append("")

    # Ledgers sorted by ID.
    for led in sorted(sidecar.ledgers, key=lambda l: l.id):
        lines.extend(_emit_ledger(led))
        lines.append("")

    lines.append("}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _emit_shared_target(target: SpecificResource) -> "list[str]":
    if target.id is None:
        raise ValueError("shared target requires id")
    sel = target.selector
    return [
        f"  anno:{target.id} a oa:SpecificResource ;",
        f"    oa:hasSource <{target.source}> ;",
        f"    oa:hasSelector [",
        f"      a oa:TextQuoteSelector ;",
        f"      oa:exact   {_str_lit(sel.exact)} ;",
        f"      oa:prefix  {_str_lit(sel.prefix)} ;",
        f"      oa:suffix  {_str_lit(sel.suffix)}",
        f"    ] .",
    ]


def _emit_annotation(ann: Annotation) -> "list[str]":
    out: list[str] = []
    out.append(f"  anno:{ann.id} a oa:Annotation ;")
    if ann.target.id is not None:
        out.append(f"    oa:hasTarget       anno:{ann.target.id} ;")
    else:
        sel = ann.target.selector
        out.append(f"    oa:hasTarget       [")
        out.append(f"      oa:hasSource <{ann.target.source}> ;")
        out.append(f"      oa:hasSelector [")
        out.append(f"        a oa:TextQuoteSelector ;")
        out.append(f"        oa:exact   {_str_lit(sel.exact)} ;")
        out.append(f"        oa:prefix  {_str_lit(sel.prefix)} ;")
        out.append(f"        oa:suffix  {_str_lit(sel.suffix)}")
        out.append(f"      ]")
        out.append(f"    ] ;")
    for body in ann.bodies:
        out.extend(_emit_body(body))
    out.append(f"    oa:motivatedBy     oa:{ann.motivation.value} ;")
    out.append(f"    sci:annotationType {_str_lit(ann.annotation_type)} ;")
    out.append(f"    sci:source         {_str_lit(ann.source)} ;")
    out.append(f"    sci:status         {_str_lit(ann.status.value)} ;")
    if ann.content_hash is not None:
        out.append(f"    sci:contentHash    {_str_lit(ann.content_hash)} ;")
    if ann.lifted_from is not None:
        out.append(f"    sci:liftedFrom     {_str_lit(ann.lifted_from)} ;")
    if ann.match_text is not None:
        out.append(f"    sci:matchText      {_str_lit(ann.match_text)} ;")
    out.append(f"    dc:creator         {_str_lit(ann.creator)} ;")
    out.append(f"    dc:created         {_dt_lit(ann.created)}")
    if ann.modified is not None:
        out[-1] += " ;"
        out.append(f"    dc:modified        {_dt_lit(ann.modified)}")
        # modified_by is required whenever modified is set (model invariant).
        assert ann.modified_by is not None
        out[-1] += " ;"
        out.append(f"    dc:contributor     {_str_lit(ann.modified_by)}")
    if ann.description is not None:
        out[-1] += " ;"
        out.append(f"    dc:description     {_str_lit(ann.description)}")
    for prior in ann.prior_states:
        out[-1] += " ;"
        out.append(f"    prov:wasRevisionOf [")
        out.append(f"      sci:status       {_str_lit(prior.status.value)} ;")
        out.append(f"      dc:created       {_dt_lit(prior.created)} ;")
        out.append(f"      dc:creator       {_str_lit(prior.creator)}")
        out.append(f"    ]")
    out[-1] += " ."
    return out


def _emit_body(body: Body) -> "list[str]":
    if isinstance(body, IriBody):
        return [f"    oa:hasBody         <{body.iri}> ;"]
    return [
        f"    oa:hasBody         [",
        f"      a oa:TextualBody ;",
        f"      dc:format        {_str_lit(body.format)} ;",
        f"      rdf:value        {_str_lit(body.value)}",
        f"    ] ;",
    ]


def _emit_ledger(led: AuditLedger) -> "list[str]":
    hashes = " ".join(_str_lit(h) for h in led.audited_hashes)
    return [
        f"  anno:{led.id} a sci:AuditLedger ;",
        f"    sci:source         {_str_lit(led.source)} ;",
        f"    sci:auditedHashes  ( {hashes} ) ;",
        f"    dc:modified        {_dt_lit(led.modified)} .",
    ]


def _str_lit(s: str) -> str:
    """Escape a string for use as a TriG plain literal."""
    escaped = (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
    return f'"{escaped}"'


def _dt_lit(dt: datetime) -> str:
    return f'"{dt.isoformat()}"^^xsd:dateTime'


def atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` atomically via temp + os.replace.

    Same semantics as P3.2's `cli._atomic_write_text` (which calls
    this helper now).
    """
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name, dir=str(path.parent), text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def serialize_sidecar(sidecar: Sidecar) -> str:
    """Serialize a Sidecar to its TriG textual form.

    Mirrors `write_sidecar`'s emission to a string buffer (via temp
    file) so callers that need the textual representation don't have
    to write to disk first.
    """
    fd, tmp = tempfile.mkstemp(suffix=".anno.trig")
    os.close(fd)
    try:
        write_sidecar(Path(tmp), sidecar)
        return Path(tmp).read_text(encoding="utf-8")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
