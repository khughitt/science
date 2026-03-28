#!/usr/bin/env python3
"""Extract a biology (biolink-model) term catalog from the LinkML source.

One-time dev script — not part of the runtime package.
Produces science-model/src/science_model/ontologies/biology/catalog.yaml.

Usage:
    uv run scripts/extract_biology_catalog.py
    # or: uvx --from biolink-model-toolkit python scripts/extract_biology_catalog.py

Requires: linkml (pip install linkml) or biolink-model-toolkit.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

BIOLINK_VERSION = "4.3.7"
BIOLINK_SCHEMA_URL = (
    f"https://raw.githubusercontent.com/biolink/biolink-model/v{BIOLINK_VERSION}/biolink-model.yaml"
)
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "science-model/src/science_model/ontologies/biology/catalog.yaml"

# Recommended entity types — commonly used in translational science projects.
RECOMMENDED_ENTITY_TYPES: set[str] = {
    "Gene",
    "Protein",
    "Disease",
    "PhenotypicFeature",
    "ChemicalEntity",
    "SmallMolecule",
    "Drug",
    "Pathway",
    "BiologicalProcess",
    "MolecularActivity",
    "CellularComponent",
    "Cell",
    "CellLine",
    "AnatomicalEntity",
    "Organism",
    "Genotype",
    "SequenceVariant",
    "NucleicAcidEntity",
    "Transcript",
    "Publication",
    "Study",
    "InformationContentEntity",
    "Dataset",
    "GeneFamily",
    "Polypeptide",
    "Genome",
    "Exon",
    "RNAProduct",
    "MicroRNA",
    "NoncodingRNAProduct",
    "Haplotype",
    "OrganismTaxon",
}

# Recommended predicates — commonly used relation types.
RECOMMENDED_PREDICATES: set[str] = {
    "interacts_with",
    "physically_interacts_with",
    "genetically_interacts_with",
    "related_to",
    "causes",
    "contributes_to",
    "treats",
    "prevents",
    "predisposes",
    "correlated_with",
    "positively_correlated_with",
    "negatively_correlated_with",
    "has_phenotype",
    "has_part",
    "part_of",
    "participates_in",
    "located_in",
    "expressed_in",
    "enables",
    "actively_involved_in",
    "gene_associated_with_condition",
    "target_for",
    "is_sequence_variant_of",
    "has_gene_product",
    "encodes",  # gene -> protein
    "member_of",
    "subclass_of",
    "overlaps",
    "colocalizes_with",
    "affects",
    "regulates",
    "positively_regulates",
    "negatively_regulates",
}


def main() -> None:
    try:
        from linkml_runtime.utils.schemaview import SchemaView
    except ImportError:
        print("Error: linkml-runtime not available. Install with: uv add --dev linkml-runtime", file=sys.stderr)
        sys.exit(1)

    print(f"Loading biolink-model v{BIOLINK_VERSION} from {BIOLINK_SCHEMA_URL} ...")
    sv = SchemaView(BIOLINK_SCHEMA_URL)

    # --- Extract entity types (classes descended from NamedThing) ---
    entity_types: list[dict[str, object]] = []
    named_thing_descendants = set(sv.class_descendants("NamedThing"))

    for cls_name in sorted(named_thing_descendants):
        cls_def = sv.get_class(cls_name)
        if cls_def is None:
            continue
        # Skip abstract/mixin classes — they aren't usable as entity types
        if cls_def.abstract or cls_def.mixin:
            continue

        curie_id = f"biolink:{cls_name}"
        # Convert CamelCase to snake_case for the name field
        name = _camel_to_snake(cls_name)
        description = (cls_def.description or "").strip()
        id_prefixes = list(cls_def.id_prefixes) if cls_def.id_prefixes else []
        recommended = cls_name in RECOMMENDED_ENTITY_TYPES

        entry: dict[str, object] = {
            "id": curie_id,
            "name": name,
            "description": description[:200] if description else f"A {name} entity.",
        }
        if id_prefixes:
            entry["curie_prefixes"] = id_prefixes
        if recommended:
            entry["recommended"] = True

        entity_types.append(entry)

    # --- Extract predicates (slots that are used as relationships) ---
    predicates: list[dict[str, object]] = []

    for slot_name in sorted(sv.all_slots()):
        slot_def = sv.get_slot(slot_name)
        if slot_def is None:
            continue
        # Only include slots that are relationship predicates
        # (those whose domain/range are classes, not attributes)
        slot_range = str(slot_def.range) if slot_def.range else ""
        slot_domain = str(slot_def.domain) if slot_def.domain else ""

        # Filter: predicate slots connect entity types (classes).
        # Skip pure data-property slots (range is a type like string, integer).
        range_class = sv.get_class(slot_range)
        if range_class is None:
            continue
        # Must descend from NamedThing on at least the range side
        range_ancestors = set(sv.class_ancestors(slot_range)) if range_class else set()
        if "NamedThing" not in range_ancestors and slot_range != "NamedThing":
            continue

        curie_id = f"biolink:{slot_name}"
        name = slot_name
        description = (slot_def.description or "").strip()
        domain = f"biolink:{slot_domain}" if slot_domain else "biolink:NamedThing"
        range_val = f"biolink:{slot_range}" if slot_range else "biolink:NamedThing"
        recommended = slot_name in RECOMMENDED_PREDICATES

        pred_entry: dict[str, object] = {
            "id": curie_id,
            "name": name,
            "description": description[:200] if description else f"A {name} predicate.",
            "domain": domain,
            "range": range_val,
        }
        if recommended:
            pred_entry["recommended"] = True

        predicates.append(pred_entry)

    # --- Build catalog ---
    catalog: dict[str, object] = {
        "ontology": "biology",
        "version": BIOLINK_VERSION,
        "prefix": "biolink",
        "prefix_uri": "https://w3id.org/biolink/vocab/",
        "entity_types": entity_types,
        "predicates": predicates,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        yaml.dump(catalog, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )

    n_recommended_types = sum(1 for et in entity_types if et.get("recommended"))
    n_recommended_preds = sum(1 for p in predicates if p.get("recommended"))
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  Entity types: {len(entity_types)} total, {n_recommended_types} recommended")
    print(f"  Predicates:   {len(predicates)} total, {n_recommended_preds} recommended")


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    result: list[str] = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            # Don't add underscore between consecutive uppercase (e.g., RNA -> rna)
            if name[i - 1].islower() or (i + 1 < len(name) and name[i + 1].islower()):
                result.append("_")
        result.append(char.lower())
    return "".join(result)


if __name__ == "__main__":
    main()
