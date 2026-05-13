# Bibliography Source References Design

## Goal

Make `cite:<bibkey>` a first-class project reference category backed by a project bibliography, without treating citations as local entities or global ontology terms.

## Problem

Downstream projects use three distinct literature identifiers:

- `cite:Smith2024` for a BibTeX entry in `papers/references.bib`
- `paper:Smith2024` for project reading notes about that citation
- `manuscript:foo` for project-owned writing in progress

`cite:` is currently handled unevenly. `refs check` already validates Pandoc-style citations such as `[@Smith2024]`, and knowledge-gap code counts `source_refs: [cite:Smith2024]`, but graph health still treats `cite:` as an unregistered reference kind. Adding `cite` to external prefixes would hide missing bibkeys and misclassify a project-local bibliography namespace as a global ontology prefix. Adding it as an entity kind would imply one Markdown entity per citation, which is the job of `paper:`.

## Design

Add a bibliography reference category alongside local entity kinds and external prefixes.

For v1, the project bibliography is `papers/references.bib` and the only recognized bibliography prefix is `cite:`. A future `science.yaml` field can make this configurable, but the existing project convention is stable enough to avoid configuration until there is a second real convention.

The new behavior:

- `source_refs: [cite:Smith2024]` is recognized by graph health and materialization as a bibliography reference, not as an unregistered entity kind.
- `refs check` validates `cite:<bibkey>` entries in frontmatter against `papers/references.bib`, using the same key corpus as Pandoc-style `[@Smith2024]` prose citations.
- Missing BibTeX files fail `cite:<bibkey>` source refs explicitly, matching the existing behavior for prose citations when no bibliography exists.
- Bibliography refs do not materialize as project entities in v1. They may materialize as lightweight external/bibliography nodes later if coverage analysis needs RDF-visible citation records.

## Components

`science_tool.bibliography` should own BibTeX key extraction. It can start with the current lightweight parser from `refs.py`, moved behind a small function such as `load_bib_keys(root: Path) -> set[str]`. A PyPI BibTeX parser is not required for v1 because the immediate validation only needs entry keys.

`science_tool.refs` should validate frontmatter refs whose raw value starts with `cite:`. The output should use `ref_type="citation"` and messages like `cite:Smith2024 — not in papers/references.bib`.

`science_tool.graph.sources` should expose `is_bibliography_reference(raw: str) -> bool`.

`science_tool.graph.health.collect_unregistered_ref_kinds` should skip bibliography refs after metadata and external checks.

`science_tool.graph.materialize` should ignore bibliography refs for provenance in v1, just as it ignores `meta:` refs. This avoids creating misleading `prov:wasDerivedFrom` edges to unresolved entity URIs.

## Tests

Add focused tests for:

- `refs check` accepts `source_refs: [cite:Smith2024]` when `papers/references.bib` contains `@article{Smith2024, ...}`.
- `refs check` reports `source_refs: [cite:Missing2024]` when the key is absent.
- `health` does not report `cite` in `unregistered_ref_kinds`.
- graph materialization does not create an unresolved provenance edge for `cite:Smith2024`.

## Out Of Scope

- Configurable bibliography paths or prefixes.
- BibTeX field validation beyond entry keys.
- RDF materialization of BibTeX entries.
- Automatic conversion between `cite:<bibkey>` and `paper:<bibkey>`.
