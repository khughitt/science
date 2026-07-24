# Gen-3 Dataset Write-Path Fix + Guard (Skill-Coverage sub-plan 1b) — Design

> **Status:** design / spec, approved for planning. Part of Plan 2 (the skill-coverage
> layer) of the data-product-vocabulary program. Parent design:
> [`2026-07-23-data-product-vocabulary-and-skill-coverage-design.md`](2026-07-23-data-product-vocabulary-and-skill-coverage-design.md).
> Sibling shipped sub-plan: enrollment
> ([`2026-07-23-skill-coverage-enrollment-implementation.md`](2026-07-23-skill-coverage-enrollment-implementation.md)).

## Motivation

Plan 1 introduced entity-schema **generation 3**, which moves `dataset` onto its
data-product capability shape (`dataset/3.0`). Generation is selected by a project's
declared `entity_schema_version` pin, read through the single authority
`validated_entity_schema_version` (returns `1`/`2`/`3`, or `None` when absent). The
load path and the migrator both thread the pin correctly.

The **authoring/write** path does not. Two project dataset writers default their
`schema_profile` to the import-time constant `BASE_DATASET_SCHEMA_PROFILE`
(`identity_authoring.py:19`), which is `science-entity-base/1.0+dataset/2.0` computed
at gen-2 and frozen at import. Neither writer consults the project's pin, so a project
pinned `entity_schema_version: 3` persists `dataset/2.0` into its dataset records.

This must be closed before any project is pinned gen-3 in the field (it is the
prerequisite for the release-coordinated external migration, Tasks 13/14).

## Grounding findings that shape the design

- **Project datasets DO carry `schema_profile`** (unlike hypotheses, which derive it at
  load time). Two writers persist it:
  - `datasets_register.py:253` (`_entity_yaml_block`), written by
    `write_derived_dataset_entities` (`science dataset register-run`).
  - `datasets_catalog.py:58` (`_render_candidate`), written by `add_dataset`
    (`science dataset add`).
  Both hold `project_root` but never read `entity_schema_version`.
- **The impact is latent, not load-breaking.** `dataset ∉ PROJECT_MIXIN_NAMES`
  (`profile.py:24`), so the project load path never validates a dataset against the full
  `dataset/3.0` profile (`sources.py:1285-1286`); the genuinely gen-3-sensitive
  obligation (the `provided_capabilities` shape) is checked off `project_schema._generation`,
  not the record's persisted string (`sources.py:1297-1318`). The wrong string becomes
  load-bearing only on **promotion to commons**.
- **Only generation 3 changes the dataset shape.** The mixin matrix
  (`profile.py:92-95`) keeps `dataset/2.0` for generations ≤ 2 and moves to `dataset/3.0`
  only at generation 3. `default_profile_for_kind` defines no generation-1 row and raises
  for it, so a resolution rule must map unpinned/1/2 → gen-2 without invoking generation 1.
- **`validated_entity_schema_version(raw)`** is THE authority both paths read the pin
  through, on the raw `science.yaml` dict (full `ProjectConfig` requires `name`, which a
  write-time pin read must not demand). The graph loader reads it this way at
  `sources.py:366`.
- **No import cycle:** `project_config.py` does not import `identity_authoring`, so the
  dataset-profile resolver may live in `identity_authoring.py` and import the pin reader
  from `project_config.py`.
- **Other `default_profile_for_kind` sites are not project write-path gaps:**
  `entities_cli.py:506` (`entity sections`) is display-only introspection with no project
  context; `sources.py:1593` feeds a transient in-memory merge policy (not persisted);
  `commons/promote.py` and the commons dataset scaffolders are commons-scoped, where a
  fixed gen-2 default is correct (commons `dataset` stays `dataset/2.0` across generations)
  and release-gated (Task 13).

## Design

### 1. Single pin reader

`project_config.py` gains a path-based pin reader that routes through the one authority,
mirroring how the loader reads it:

```python
def project_entity_schema_version(project_root: Path) -> int | None:
    """The project's declared entity_schema_version pin (1/2/3), or None if unpinned.

    Reads the raw science.yaml mapping and validates through the single authority
    (`validated_entity_schema_version`) -- no full ProjectConfig required, exactly as the
    graph loader reads the pin. This keeps the write path and the load path reading the
    generation through one function, so they can never disagree. A missing science.yaml is
    unpinned (None), not an error, mirroring the loader -- write sites like `add_dataset` are
    exercised against bare directories that have no config.
    """
    path = project_config_path(project_root)
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return validated_entity_schema_version(raw)
```

### 2. Generation-aware dataset-profile resolver

`identity_authoring.py` gains the resolver, colocated with `BASE_DATASET_SCHEMA_PROFILE`
and the `default_profile_for_kind` wrapping that already establish dataset-profile
authority there:

```python
def project_dataset_schema_profile(project_root: Path) -> str:
    """Default schema_profile for a PROJECT dataset record, honoring the project's pin.

    Only generation 3 changes the dataset shape, so any project not pinned generation 3
    (unpinned, 1, or 2) keeps `dataset/2.0` -- no regression for existing projects, and no
    attempt to resolve a generation-1 mixin row (which does not exist).
    """
    pin = project_entity_schema_version(project_root)
    return default_profile_for_kind("dataset", generation=3 if pin == 3 else 2).render()
```

### 3. Both writers default through the resolver

- `add_dataset` (`datasets_catalog.py`): `schema_profile: str | None = None`; when `None`,
  resolve via `project_dataset_schema_profile(project_root)` before rendering. The CLI at
  `datasets/cli.py:394` stops substituting `BASE_DATASET_SCHEMA_PROFILE` for `None` and
  passes the caller value through (the resolution moves into `add_dataset`, which holds
  `project_root`).
- `write_derived_dataset_entities` (`datasets_register.py`): resolve the gen-aware default
  once from `root` and thread it as the fallback into `_entity_yaml_block` and
  `_output_schema_profile`, replacing their `= BASE_DATASET_SCHEMA_PROFILE` defaults with
  an explicitly passed resolved value. A per-output explicit `schema_profile` in the
  workflow output still overrides (unchanged behavior).

Explicit caller overrides (a `--schema-profile` flag, an output-declared profile) continue
to win in both writers; only the *default* becomes generation-aware.

Commons consumers of `BASE_DATASET_SCHEMA_PROFILE` (`commons/dataset_lifecycle.py:286`,
`commons/cli.py:670`) are unchanged.

### 4. Regression guard (reference scan, deny-by-default)

A test walks the whole `science_tool` source tree with the `ast` module and collects every
module that **references** `BASE_DATASET_SCHEMA_PROFILE` in any form: a `from ... import` of
the name (and the `ast.Name` uses it binds), an aliased module attribute
(`import ... as ia; ia.BASE_DATASET_SCHEMA_PROFILE`, an `ast.Attribute`), and a star import
from the defining module. It asserts that set is a subset of the sanctioned allowlist — the
commons package (`science_tool/commons/**`), where the fixed gen-2 default is correct.

Scanning **all reference forms**, not just the `ImportFrom` edge, is required: an
`ImportFrom`-only check would miss the aliased-module attribute access and the star import.
The polarity is deny-by-default — the guard scans the entire tree and the allowlist names
only what is *permitted*, so a future project-side writer that reaches for the raw gen-2
constant fails the build and is forced through `project_dataset_schema_profile`. New modules
are caught, not silently exempted.

The defining module (`identity_authoring.py`) is scanned too. The guard exempts only the
constant's exact top-level assignment target; it still rejects any `ast.Name` load there.
The bite proof temporarily adds a real `BASE_DATASET_SCHEMA_PROFILE` load to that module and
requires the boundary failure to name `identity_authoring.py`, then restores the file and
requires green. Stated limit: matching the bare attribute name would also flag an unrelated
symbol sharing the exact name `BASE_DATASET_SCHEMA_PROFILE`; none exists in this tree and the
name is specific enough that a collision is implausible.

### 5. Testing

Behavioral tests exercise the real writers against constructed projects:

- A project pinned `entity_schema_version: 3` → both writers persist
  `science-entity-base/1.0+dataset/3.0`.
- An unpinned project and a project pinned `entity_schema_version: 2` → both writers persist
  `science-entity-base/1.0+dataset/2.0` (no regression).
- An explicit caller-provided `schema_profile` survives unchanged in both writers.
- The pin reader returns `3`/`2`/`None` for pinned-3/pinned-2/unpinned projects.
- The import-choke guard tests, including assignment-target allowance and defining-module
  load rejection (§4).

Verification gate: full `science` and `science/model` suites, `ruff check`, `pyright`.

## Out of scope (documented limitations)

- **`science entity sections` display** (`entities_cli.py:506`): shows gen-2 dataset field
  constraints in a gen-3 project. Display-only, no persisted write; the command takes only
  `kind` and has no project context. Left as a known cosmetic limitation.
- **Merge-policy site** (`sources.py:1593`): transient in-memory policy, behavior-neutral
  (`dataset/2.0` and `dataset/3.0` carry byte-identical `science:merge` annotations).
- **Commons promote / scaffolders** (`commons/promote.py`, `commons/dataset_lifecycle.py`,
  `commons/cli.py`): commons-scoped, where gen-2 is the correct fixed default;
  release-gated under Task 13.
