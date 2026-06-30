# Project Packaging

Project packaging turns a Science project into a deterministic reproducibility
bundle and gives recipients a way to check that bundle against their own
checkout.

The packaging commands are:

```bash
science project serialize --project-root <root> --out <bundle.tar.gz> [--force]
science project verify <bundle.tar.gz> [--against <root>] [--extract <dir>] [--json]
```

Use this workflow when a result, finding, or downstream discussion depends on
local project files and local data payload hashes. The bundle is built for
reproducibility. It is not a privacy scrubber.

## Serialize

`science project serialize` writes a deterministic `.tar.gz` bundle containing
the project's git-tracked source files plus a manifest inventory of excluded
payload data.

The command includes tracked project source:

- `science.yaml`
- `entities/**`
- `results/**`
- `papers/references.bib`, if tracked
- `knowledge/graph.trig`, if tracked

The command does not include `data/` payload bytes. Instead, it walks the
configured data roots and records each payload's repo-relative path, SHA-256,
byte count, and `git_tracked` flag in `manifest.json`.

Serialize is git-faithful:

- The project must be a git worktree with a `HEAD` commit.
- `science.yaml` must be git-tracked.
- Selected source files must match `HEAD`; dirty selected source hard-fails.
- Selected source files must be regular files, not symlinks.
- `--out` must resolve outside the project root.
- The archive top-level directory is the safe project id from `science.yaml`.

The command runs the [data-boundary audit](../conventions/data-boundary.md)
before writing the archive. It blocks on payload-boundary violations: stranded
records, leaked payloads, and tracked payloads under data roots. Generic audit
flags do not block serialization.

`--force` bypasses only those payload-boundary violations. It does not bypass
missing or untracked `science.yaml`, dirty source, missing `HEAD`, invalid
project config, unsafe project id, symlinks, unreadable files, or payload walk
guard failures. A forced bundle records that fact in `boundary_audit.forced`.

Because serialize ships all selected git-tracked source files without
sensitivity filtering, restricted material must not be tracked. Public-safe
scrubbing and publication profiles are separate future workflows.

## Labnote App Export

`science labnote export --project-root <root> --out <dir>` writes a public app
package for Labnote. This export is separate from deterministic project
serialization: it filters to public entities, emits app-view descriptors, and
writes JSON bundles that Labnote can load directly.

The export includes `references/index.json`, a `science.references` bundle
derived from `papers/references.bib`, and registers it in `manifest.json` as a
public JSON bundle named `references`. Public Markdown bodies and
`source_refs: ["cite:<bibkey>"]` values must resolve against the bibliography.
Unknown citekeys and unsupported citation syntax fail closed during export. See
[Citations And Reference Bundles](../conventions/citations-and-references.md)
for the reference-record contract and v1 Markdown citation grammar.

## Bundle Manifest

Serialized bundles use the schema version
`science-project-serialized.v1`. Inside the tarball, every member lives under a
single `<project-id>/` prefix. Manifest paths omit that prefix.

The manifest records:

- project id, label, and summary
- `data_version`
- provenance, including the source git commit
- boundary audit status and forced status
- copied source files with path, SHA-256, and byte count
- excluded payloads with path, SHA-256, byte count, and `git_tracked`

`data_version` is derived from canonical manifest records, not only raw bytes.
Changing a file path, payload path, payload tracking state, hash, or size changes
the version.

## Verify

`science project verify` always starts with a bundle self-check. If the
self-check fails, checkout comparison and extraction do not run.

The self-check verifies:

- the archive is a readable gzip tar
- all members share one top-level prefix matching `manifest.project.id`
- `manifest.json` conforms to the strict v1 schema
- archive members are exactly `manifest.json` plus `files[]`
- every archive member is a safe regular file path
- each archived source file matches the manifest SHA-256 and byte count
- `data_version` recomputes from the manifest records

`--against <root>` compares the verified bundle with a live checkout. The target
root must be a git worktree with a `HEAD` commit. The comparison checks:

- bundle `provenance.git_commit` against target `HEAD`
- every bundled source file against the target working-tree file
- the payload inventory under the target data roots

Payload comparison treats SHA-256, byte count, and `git_tracked` as part of the
live contract. If the payload bytes match but the tracking state differs, the
payload differs. Local payloads that are not recorded in the bundle are reported
as extra and are non-fatal; they mean the target has more data than the bundle
claimed, not less.

`--extract <dir>` writes the verified source tree to a new or empty directory.
Extraction is verify-first and uses a staging directory so an extraction failure
does not leave a partial target behind.

`--json` emits a stable machine-readable verdict with `version: 1`,
`bundle_schema_version`, `exit_code`, `status`, `self_check`, optional
`against`, and `warnings`.

## Verify Exit Codes

| Code | Meaning |
|---|---|
| 0 | Clean self-check and, when `--against` is used, clean checkout comparison. |
| 1 | Commit, source, or payload differs. |
| 2 | Bundle integrity failure, such as invalid manifest, unsafe member, missing member, hash mismatch, or `data_version` mismatch. |
| 3 | Payloads are missing locally and nothing differs. |
| 4 | Operational failure, such as missing bundle, invalid `--against` root, no target `HEAD`, payload walk guard failure, or invalid extract target. |

Click parser errors, such as unknown options or missing required arguments, use
Click's normal usage error behavior before the command body runs.
