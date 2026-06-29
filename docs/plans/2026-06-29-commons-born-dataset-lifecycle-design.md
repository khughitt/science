# Commons-Born Dataset Lifecycle Design

## Status

Accepted design, brainstormed 2026-06-29. This design records the local-first
Science commons dataset lifecycle that should exist before further one-off
commons data recipe work expands.

## Context

Science commons data has mostly followed a project-first lifecycle:

1. create a data recipe or workflow inside a project;
2. prove the dataset is useful there;
3. promote the dataset into `~/d/science-commons`.

That pattern remains useful for project-derived artifacts, but it is the wrong
default for reusable external reference wrappers such as dbSNP, OpenAlex,
ontology tables, reference genomes, crosswalks, and other modular external
datasets. Those datasets should be able to start in commons with no parent
project.

The data-audit design in
`docs/plans/2026-06-28-data-audit-design.md` clarifies the project-side boundary:
payloads stay in ignored `data/`, while lightweight records live in tracked
`results/`. Commons needs a parallel boundary:

- tracked dataset package metadata and recipes live under
  `~/d/science-commons/datasets/<slug>/`;
- generated payload bytes live under `$SCIENCE_COMMONS_DATA_ROOT/<slug>/`,
  defaulting to `/data/science-commons/<slug>/`.

The dbSNP rsID variant-label work exposed the gap: the commons recipe had
metadata and scripts, but the reproducible operator path needed to be made
explicit after the fact. This design makes that path the default for new
commons-born datasets.

The current commons store is not already shaped this way. In the local checkout
reviewed for this design, `~/d/science-commons/datasets/` has 38 dataset
directories, 10 `recipe/build.py` scripts, and only 1 `recipe/Snakefile`
(`dataset:variant-labels-dbsnp-human`, added during the dbSNP repair). Requiring
Snakemake for commons-born datasets is therefore an intentional standardization
decision, not a description of the existing dominant convention. Existing
recipes can continue to work until touched; new commons-born datasets should
start with the workflow entrypoint.

The reason to standardize on Snakemake despite the installed base is that
commons-born datasets need one reproducible operator boundary for download,
verification, build, and datapackage refresh. The existing `build.py` scripts
can still be implementation details invoked by a workflow rule. The lifecycle
CLI should not need dataset-specific knowledge of which scripts to call or in
which order.

## Goals

- Support datasets that are born in commons, not promoted from a project.
- Require every commons-born dataset to have a workflow entrypoint from day one.
- Keep commons recipes modular and minimally processed: wrappers around external
  sources, packaged and described consistently.
- Let downstream projects consume commons datapackages by reference and perform
  project-specific processing locally.
- Preserve the existing commons data-root convention:
  `$SCIENCE_COMMONS_DATA_ROOT/<slug>/`, defaulting to
  `/data/science-commons/<slug>/`.
- Resolve built payloads through the existing commons resolver and per-machine
  data overrides instead of assuming a naive data-root join.
- Design the metadata so future local, Git, GitHub, Zenodo, and other remote
  catalogs can be added without changing the local lifecycle.

## Non-Goals

- Implement a remote package manager in v1.
- Add project-local dependency lockfiles for commons datasets in v1.
- Migrate existing commons recipes immediately.
- Change the project data-audit invariant for `data/` and `results/`.
- Move, delete, or garbage-collect commons payloads automatically.

## Decision

Adopt a local-first commons-born dataset lifecycle:

```text
init -> edit recipe -> build -> validate -> index/find -> project references dataset:<slug>
```

The v1 command surface is:

```bash
science commons dataset init <slug>
science commons dataset build <slug>
science commons dataset validate <slug>
science commons dataset status <slug>
science commons find dataset [filters]
```

Remote catalog metadata is reserved now, but remote execution commands such as
`add-remote`, `update-sources`, and `pull` are deferred.

`science commons find` already owns local index search and already emits the
shared stale-index warning through `CommonsQuery.find()`. V1 should preserve
that behavior, add regression coverage for it, and add only missing
dataset-oriented filters if needed, rather than introducing
`science commons search` as a second local query command. A future
package-manager phase may add `search` as an alias or remote-aware verb, but
that is out of scope for v1.

Index freshness should reuse `RegistryBuilder.is_stale()`, not a new freshness
heuristic. The existing registry staleness contract is: stale when
`registry.sqlite` is missing, malformed, or missing required `schema_meta` rows;
when the source file count changes; when the source path digest changes; or when
the maximum source mtime advances. The source file set is the same one used by
the registry builder: commons entity owner files plus dataset `datapackage.yaml`
files. Because `find` is shared by `dataset`, `paper`, `topic`, and `theme`, the
stale-index warning is global to every `science commons find ...` invocation,
not dataset-only behavior.

## Package Shape

A commons-born dataset package lives at:

```text
~/d/science-commons/datasets/<slug>/
```

Required files:

```text
entity.md
datapackage.yaml
recipe/Snakefile
recipe/README.md
```

Optional files:

```text
recipe/config.yaml
recipe/lockfile.yaml
recipe/*.py
recipe/test_*.py
```

`recipe/Snakefile` is required for every v1 commons-born dataset, including
datasets whose upstream artifact is already packaged elsewhere. A minimal
workflow may only download, verify, and copy a prepared package, but the
regeneration path must still be a workflow target.

Generated payloads live outside git under:

```text
$SCIENCE_COMMONS_DATA_ROOT/<slug>/
```

The default commons data root remains:

```text
/data/science-commons/
```

The design does not rename this root to `/data/commons` or
`/data/science/commons`. Those can be considered later as aliases or migration
targets if the broader data-root audit standardizes them.

Status, validation, and project resolution must not assume that the only
candidate path is `$SCIENCE_COMMONS_DATA_ROOT/<slug>/<resource>`. They must use
the same resolution semantics as `science_tool.commons.resolver.resolve`:

1. `resolve_commons_data_root() / <slug> / <logical-resource-path>`;
2. the per-machine override directory from
   `load_data_overrides()` / `~/.config/science/data.yaml`;
3. hash verification against `datapackage.yaml` when checking a built resource.

This matters because real machines may keep commons payloads under paths such
as `~/d/science-commons-data/<slug>/` via `data.yaml` overrides.

## Dataset Versioning

Each commons dataset has an explicit semver `version:` in `entity.md`. This is
the human-facing compatibility contract for the Science wrapper package, not
the upstream artifact release.

For external wrappers, upstream versions belong in the workflow source pins:
`recipe/lockfile.yaml`, source sidecars, build summaries, or equivalent recipe
metadata. For example, a dbSNP build number changes the source pin; the
dataset package `version:` changes when the wrapper's resource contract,
processing policy, schema, or compatibility surface changes.

Git commits and future catalog revisions remain provenance, not a replacement
for dataset versioning. Future package-manager operations should be able to pin
both:

```text
dataset:<slug>@<version>
source:<remote-name>@<catalog-revision-or-commit>
```

In v1, validation requires that the dataset version exists and satisfies the
base entity semver pattern (`^[0-9]+\.[0-9]+\.[0-9]+$`).

## Project Consumption

V1 project consumption stays lightweight and reference-driven. Projects declare
existing `dataset:<slug>` references in frontmatter, lineage, datapackage
metadata, or validation fields. Science resolves those references from the local
commons index and data root.

V1 does not create project-local commons dependency manifests or vendored
dataset lockfiles. A future command such as:

```bash
science pull dataset:<slug>@<version>
```

may create project-local pins once remote catalogs and remote package resolution
exist.

## CLI Behavior

### `science commons dataset init <slug>`

Creates a tracked package skeleton:

- `datasets/<slug>/entity.md`
- `datasets/<slug>/datapackage.yaml`
- `datasets/<slug>/recipe/Snakefile`
- `datasets/<slug>/recipe/README.md`

The command:

- rejects invalid slugs;
- rejects an existing dataset directory;
- writes only under the commons root;
- creates an external reference package that is valid as an unbuilt scaffold;
- prints the next build/validation commands;
- does not fetch or build data.

### `science commons dataset build <slug>`

Runs Snakemake against:

```text
datasets/<slug>/recipe/Snakefile
```

The CLI passes standard config values:

- `dataset_slug`
- `commons_data_root`
- `source_root`
- `output_root`
- `dataset_output_dir`

The workflow owns downloads, lockfiles, payload writes, summaries, and
datapackage hash refresh. The CLI must not download directly or call recipe
scripts as a shortcut.

`dataset_output_dir` must be resolved through the existing commons data
location rules: use the per-slug `load_data_overrides()` entry when present,
otherwise use `resolve_commons_data_root() / <slug>`. `output_root` is retained
for workflows that already write `<output_root>/<slug>/...`, but new workflows
should prefer the explicit `dataset_output_dir` to avoid assuming all datasets
share one physical parent directory.

### `science commons dataset validate <slug>`

Validates the dataset package and v1 commons-born invariants:

- `entity.md` exists and declares `id: dataset:<slug>`;
- `type: dataset` and `version:` are present;
- `datapackage: datapackage.yaml` points at the package datapackage;
- `datapackage.yaml` exists;
- `recipe/Snakefile` exists;
- payload references are either present or explicitly unbuilt;
- placeholder hashes are reported as unbuilt, not silently accepted as usable;
- large payload bytes are absent from the tracked dataset directory unless
  explicitly allowlisted by the tracked-package file policy;
- the package does not depend on parent-project `data/` or `results/` paths.

Validation distinguishes a valid unbuilt scaffold from an invalid package.

### `science commons dataset status <slug>`

Supports `--json` for parity with existing commons commands and to provide a
stable machine-readable status contract for future automation.

Reports scaffold and build state:

- package exists or missing;
- workflow exists or missing;
- lockfile present or missing;
- datapackage hashes are placeholders or real values;
- expected data-root outputs are present or missing;
- local index is fresh or stale.

`status` is read-only and should not fail merely because payloads are absent.

### `science commons find dataset [filters]`

Searches the local commons index/catalog only in v1. The existing
`science commons find` command already supports entity-type search plus filters
such as tags, ontology terms, years, slug globs, and `--json`; v1 should improve
that command for dataset lifecycle use instead of adding a competing
`search` command. It already warns when the index is stale and tells the user
how to rebuild it; v1 should keep that behavior covered by tests. The warning
applies to the shared `find` command for all supported entity types, not only
`dataset`.

Remote search is deferred.

## Mutation Boundaries

- `init` is the only command that writes tracked skeleton files directly.
- `build` invokes Snakemake and lets the workflow mutate package lockfiles,
  package datapackages, and `$SCIENCE_COMMONS_DATA_ROOT/<slug>/`.
- `validate`, `status`, and `find` are read-only.
- Science lifecycle commands do not move, delete, or clean payloads.

This keeps reproducibility in the workflow and prevents hidden one-off download
paths from becoming part of the operator lifecycle.

## Remote-Ready Catalog Model

Remote support is a v2 feature, but v1 should reserve a catalog-level model so
the local design does not block it.

A future `commons.yaml` at the commons root can describe named package sources:

```yaml
catalog_version: 1
sources:
  local:
    type: path
    uri: ~/d/science-commons
  bio-commons:
    type: git
    uri: https://github.com/org/science-bio-commons.git
  dbsnp-release:
    type: zenodo
    doi: 10.xxxx/zenodo.xxxxx
```

The split is load-bearing:

- dataset recipes describe upstream scientific data sources, such as NCBI URLs,
  DOI files, checksums, API exports, and source lockfiles;
- commons catalog sources describe where Science discovers dataset packages,
  such as a local path, Git repository, GitHub repository, Zenodo bundle, or
  future registry.

Future remote support should materialize remote catalog state into a local cache
or local commons store first. Normal project validation should not depend on
live network calls.

Reserved future commands include:

```bash
science commons add-remote <name> <repo|github-url|zenodo-doi>
science commons update-sources
science commons search <query> --remote
science pull dataset:<slug>@<version>
```

## Validation Rules

A commons-born dataset package is valid when:

1. It has `entity.md` with `id: dataset:<slug>`, `type: dataset`, semver
   `version:`, `status:`, schema-legal dataset `origin`, and
   `datapackage: datapackage.yaml`. V1 `science commons dataset init` scaffolds
   `origin: external` wrappers only; derived dataset packages require a
   `derivation:` block and are deferred to a later explicit workflow.
2. It has `datapackage.yaml` with stable resource names, relative resource
   paths, and hashes/bytes when built.
3. It has `recipe/Snakefile`.
4. Commons datapackages are YAML. `datapackage.yaml` is intentional and should
   be parsed with the existing YAML commons datapackage reader; project-side
   `datapackage.json` conventions do not change this package format.
5. Payload bytes are not stored in the tracked dataset directory unless they
   pass the tracked-package file policy below.
6. Dataset `version:` is present, semver, and means wrapper-package version.
7. The package can build independently of any parent project.

Tracked-package file policy:

- canonical tracked package files such as `entity.md`, `datapackage.yaml`,
  `recipe/Snakefile`, `recipe/README.md`, and workflow lockfiles are allowed;
- generated payload extensions from the data-audit policy, or files larger than
  `150_000` bytes, are invalid in the tracked dataset package unless explicitly
  allowlisted. The implementation should reuse the data-audit SSOT
  (`science_tool.data_policy.DataPolicy.payload_extensions` and
  `science_tool.data_policy.classify()` once that design lands) rather than
  reimplementing a parallel extension/size classifier. This policy also applies
  inside `recipe/` except for canonical workflow metadata files, so large lookup
  tables and generated payloads are not hidden under recipe paths;
- the allowlist should be explicit package metadata, for example
  `tracked_payload_allowlist:` entries with path and reason in `entity.md`;
- allowlisted tracked data should be reserved for deliberately small reference
  tables or fixtures that are part of the package contract, not bulk generated
  resources.

Mutable upstream source refs are allowed only when the workflow lockfile pins
the resolved artifact. For example, a recipe may contact an API or a mutable
landing URL during discovery, but the accepted build must record stable
artifact URLs, checksums, byte counts, versions, or equivalent source pins.

## Error Handling

The implementation should fail early and avoid silent fallbacks.

`init` rejects invalid slugs, existing directories, and writes outside the
commons root.

`build` refuses missing `recipe/Snakefile`, streams Snakemake output, and
returns Snakemake's exit status.

`validate` reports missing workflow, missing datapackage, placeholder hashes,
missing payloads, mutable source refs, and parent-project dependencies with
specific findings.

`status` reports state without treating absent payloads as an error.

`find` reports stale or missing index state and remains local-only in v1.

## Testing Strategy

Tests should cover:

- `init` creates the exact skeleton and refuses collisions;
- `build` invokes Snakemake with the expected `-s
  datasets/<slug>/recipe/Snakefile` and standard config values;
- `build` tests mock subprocess execution rather than downloading data;
- `validate` distinguishes valid unbuilt scaffold, missing workflow, placeholder
  datapackage, and built package with real hashes;
- `status --json` returns stable machine-readable state;
- `find` returns local indexed commons datasets and has regression coverage for
  the existing shared stale-index warning;
- remote catalog parsing accepts `path`, `git`, `github`, and `zenodo` source
  declarations even though execution is deferred.

## Rollout

1. Record this design.
2. Write an implementation plan for the local lifecycle commands.
3. Implement the v1 local lifecycle.
4. Convert or normalize existing commons recipes opportunistically.
5. Add remote source indexing and `science pull` later.

Existing commons recipes should not block v1. They can remain as-is until touched
for other work, then be normalized toward this package contract.

The normalization cost is accepted as a gradual migration cost. The v1 lifecycle
sets the standard for new commons-born datasets; it does not require converting
all existing `build.py` recipes before the commands are useful.

## dbSNP Follow-Up

The dbSNP rsID variant-label recipe has already been repaired to use a
Snakemake workflow rather than one-off operator commands. After the commons-born
dataset lifecycle lands, revisit `dataset:variant-labels-dbsnp-human` and make
it conform to the final scaffold, validation, status, and build command
contract.

## Naming Collision Notes

`science commons init` already initializes or verifies the commons store layout.
The dataset scaffold command is deliberately nested as
`science commons dataset init <slug>` to avoid colliding with store
initialization. Help text should make this distinction explicit.
