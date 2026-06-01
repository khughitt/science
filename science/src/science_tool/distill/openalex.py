from __future__ import annotations

from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from science_tool.distill import (
    DEFAULT_SNAPSHOT_DIR,
    SCHEMA_NS,
    SCI_NS,
    bind_common_prefixes,
    write_snapshot,
)
from science_tool.openalex import OPENALEX_MAX_PER_PAGE, OpenAlexClient, OpenAlexRequestCache, OpenAlexStatus

OPENALEX_BASE = "https://api.openalex.org"

# Hierarchy: domains → fields → subfields → topics
LEVELS = ("domains", "fields", "subfields", "topics")


def distill_openalex(
    *,
    level: str = "subfields",
    output_path: Path | None = None,
    cache_path: Path | None = None,
) -> Path:
    """Fetch OpenAlex science hierarchy up to the given level and write Turtle snapshot."""
    if level not in LEVELS:
        raise ValueError(f"Invalid level: {level}. Must be one of {LEVELS}")

    target_idx = LEVELS.index(level)
    levels_to_fetch = LEVELS[: target_idx + 1]

    all_items: dict[str, dict[str, dict]] = {}
    for lvl in levels_to_fetch:
        all_items[lvl] = {item["id"]: item for item in _fetch_all_pages(lvl, cache_path=cache_path)}

    g = Graph()
    bind_common_prefixes(g)

    node_count = 0
    for lvl in levels_to_fetch:
        for item_id, item in all_items[lvl].items():
            node_uri = URIRef(item_id)
            g.add((node_uri, RDF.type, SCI_NS.Concept))
            g.add((node_uri, RDF.type, SKOS.Concept))
            g.add((node_uri, SKOS.prefLabel, Literal(item["display_name"])))

            works_count = item.get("works_count")
            if works_count is not None:
                g.add((node_uri, SCHEMA_NS.size, Literal(works_count, datatype=XSD.integer)))

            # Link to parent via skos:broader
            parent_key = _parent_level_key(lvl)
            if parent_key and parent_key in item and isinstance(item[parent_key], dict):
                parent_uri = URIRef(item[parent_key]["id"])
                g.add((node_uri, SKOS.broader, parent_uri))
                g.add((parent_uri, SKOS.narrower, node_uri))

            node_count += 1

    triple_count = len(g)

    if output_path is None:
        stem = "openalex-topics" if level == "topics" else "openalex-science-map"
        output_path = DEFAULT_SNAPSHOT_DIR / f"{stem}.ttl"

    return write_snapshot(
        g,
        output_path=output_path,
        name=f"OpenAlex Science Map ({level} level)",
        source_url=f"{OPENALEX_BASE}/{level}",
        version=f"openalex:{level}",
        node_count=node_count,
        triple_count=triple_count,
    )


def _parent_level_key(level: str) -> str | None:
    """Return the JSON key for the parent entity at a given hierarchy level."""
    return {
        "domains": None,
        "fields": "domain",
        "subfields": "field",
        "topics": "subfield",
    }.get(level)


def _fetch_all_pages(endpoint: str, *, cache_path: Path | None = None) -> list[dict]:
    """Fetch all pages from an OpenAlex API endpoint. Returns list of result dicts."""
    cache = OpenAlexRequestCache(cache_path) if cache_path is not None else None
    client = OpenAlexClient(cache=cache)
    items: list[dict] = []
    page = 1
    per_page = OPENALEX_MAX_PER_PAGE

    while True:
        record = client.get(f"/{endpoint}", params={"per_page": str(per_page), "page": str(page)})
        if record.status not in {OpenAlexStatus.OK, OpenAlexStatus.EMPTY}:
            raise RuntimeError(f"OpenAlex {endpoint} fetch failed: {record.status.value}: {record.error}")

        data = record.payload or {}

        results = data.get("results", [])
        if not results:
            break

        items.extend(results)

        meta = data.get("meta", {})
        total = meta.get("count", 0)
        if len(items) >= total:
            break

        page += 1

    return items
