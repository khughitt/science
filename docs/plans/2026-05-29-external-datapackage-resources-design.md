# Content-Addressed Datapackage Resources with Pluggable Sources — Design

**Status:** approved design (2026-05-29); implementation plan to follow.

**Goal:** Let a commons dataset declare resources whose bytes legitimately live
off-repo (bulk storage now; remote commons — Zenodo / GitHub / a daemon —
later), so `science commons promote dataset` records each resource's
location + checksum **without requiring the bytes co-located under the
datapackage directory and without streaming multi-GB files at promote time**.

**Architecture (one sentence):** A resource gains an optional typed `source`
descriptor; its presence flips the resource from "co-located, promote computes
the digest by streaming" to "content-addressed, the digest is build-stamped and
the bytes may live anywhere," with `(hash, bytes)` as the canonical identity
that ties every source and verification boundary together.

**Tech stack:** Python 3.13, the existing `science_tool.commons` promote /
datapackage layer, frictionless-style datapackage descriptors, pytest.

---

## Motivation

`science commons promote dataset` cannot promote the mm30 Walker (14 GB h5ad)
and Oetjen (1.5 GB h5ad) scRNA datasets. Their datapackages declare the
harmonized AnnData + QC report as resources, but those files live in the
project's bulk scRNA cache on `/data` (7.7 TB), not co-located with the
datapackage in the repo on the SSD (~150 GB free). Today promote
(`_dataset_per_resource` → `stream_sha256_and_bytes`) requires every resource to
be a real file resolvable **under** the datapackage directory and streams it to
compute `(sha256, bytes)`:

- `_datapackage_relative_path` rejects absolute paths and any path that escapes
  the datapackage dir, and resolves through symlinks — so a symlink into the
  cache is rejected (`.resolve()` → parent-escape), and a hardlink is impossible
  across the two filesystems.
- Even when co-location *is* satisfied, promote streams the whole file just to
  mint metadata — a 14 GB read for a pure-metadata operation.

The commons artifact never stores resource bytes: promotion writes a canonical
entity `.md`, a rendered `datapackage.yaml` (per-resource `hash` + `bytes`), and
a recipe stub. The read side (`commons/datapackage.py`: `read_datapackage`,
`DataResource`) already models a resource as `path + hash + bytes`, and the C4a
`validate/checks/variant_identity.py` check already consumes a committed
descriptor by verifying a *local* file's bytes/hash against it. So content
addressing with off-repo bytes is already the de-facto model for the bytes that
matter — promotion is the only step that still demands local, co-located bytes.

## Forward direction (why this shape)

The commons will later support linking to **remote** commons (GitHub, Zenodo, a
dedicated commons repository/daemon). The chosen integrity contract is selected
to generalize cleanly to that future:

- A remote-only resource and a `/data`-resident resource are the **same case** —
  "bytes not under the datapackage dir." Both flow through one code path.
- `(hash, bytes)` becomes the canonical content-address — exactly the join key a
  remote consumer needs: fetch bytes from wherever, verify against the committed
  hash before use.
- Verification is **layered** across boundaries: the producer stamps at build,
  promote verifies *if the file is locally resolvable*, and a future remote
  consumer verifies *on fetch*. One hash, many sources, verification wherever the
  bytes meet the descriptor.

This iteration **builds** the local/off-repo source kind and **models** the
remote kinds as forward-compatible, schema-validated slots that are recorded but
not fetched.

## The contract

A datapackage resource gains an optional **`source`** descriptor. Its presence
is the discriminator:

- **Co-located resource (no `source`)** — unchanged: `path` is relative to the
  datapackage dir, must resolve locally, and promote streams it to compute
  `hash` + `bytes`. Full backward compatibility; every existing resource keeps
  working exactly as before.
- **Sourced resource (`source:` present)** — content-addressed with a pluggable
  origin. It **must** carry build-stamped `hash` + `bytes` (its identity; promote
  cannot compute them when the bytes are off-host). `path` stays the *logical*
  name within the package; the bytes live wherever `source` says.

### The `source` field

```yaml
resources:
  - name: walker-harmonized-anndata
    path: walker2024.h5ad              # logical identity within the package
    format: h5ad
    hash: "sha256:<64 hex chars>"      # build-stamped (required when source present)
    bytes: 14010935296                 # build-stamped (required when source present)
    source:
      type: local                      # local | zenodo | github | url | daemon
      ref: "${OUTPUT_ROOT}/scrna/walker2024.h5ad"
```

- **`type`** enum: `local | zenodo | github | url | daemon`. Only **`local`** is
  *resolved* this iteration; the other kinds are schema-validated and recorded
  but **not fetched** (forward-compatible slots for remote commons).
- **`local.ref`**: an off-repo filesystem path. Supports an `${OUTPUT_ROOT}`
  token and plain absolute paths, so refs are portable rather than hardcoding a
  host path. The canonical `datapackage.yaml` stores `source` **verbatim** (the
  unexpanded token), keeping the committed artifact host-independent. Token
  expansion happens only transiently inside promote when it tries to locate the
  file (see below); promote stays project-agnostic by expanding from the
  `OUTPUT_ROOT` environment variable, **best-effort**: an unexpandable token
  (env unset) simply means "not locally resolvable on this host," never an error.
- **Discriminator decision (a):** the *presence* of `source` marks a resource as
  sourced; there is no separate `external: true` flag. Fewer fields, one source of
  truth, and co-located resources are unchanged.
- **Ref portability decision (b):** local refs use the `${OUTPUT_ROOT}` token (or
  absolute) rather than plain machine-specific absolute paths only.

## Promote behavior

`_dataset_per_resource` (and the resource-existence validation it shares with
`_validate_datapackage_resources`) becomes source-aware:

1. **No `source`** → current path: resolve under the datapackage dir, stream →
   `(hash, bytes)`.
2. **`source` + locally resolvable** (`local.ref` expands via `OUTPUT_ROOT` /
   absolute path to a file that exists on this host) → **verify-if-present**:
   stream the file, assert it matches the recorded `hash` + `bytes`, fail loud on
   drift.
3. **`source` + not locally resolvable** (a remote `type`; a `local.ref` whose
   token is unexpandable here; or a resolved path that does not exist) → **trust
   recorded** `hash` + `bytes`; no streaming.

The rendered canonical `datapackage.yaml` carries `path + hash + bytes + source`
for sourced resources (co-located resources render `path + hash + bytes` as
today).

## Validation and errors (fail-loud, no silent fallback)

- A sourced resource missing `hash` or `bytes` → hard error (cannot trust an
  unstamped, possibly-remote resource).
- `source.type` outside the enum → hard error.
- A source whose `ref` is malformed (empty, or syntactically-broken `${...}`
  token) → hard error. An `OUTPUT_ROOT` token that is well-formed but
  *unexpandable* here (env unset) is **not** an error — it falls through to
  case 3 (trust recorded). Remote-typed sources are validated for shape only (a
  non-empty `ref`); they are recorded, never fetched, this iteration.
- A co-located resource (no `source`) still hits the existing parent-escape /
  `is_file` checks unchanged.
- **verify-if-present** mismatch → a new `PromoteResourceDigestMismatchError`
  naming the resource and the expected vs. actual `(hash, bytes)`.

## Components (all in `~/d/science/science/src/science_tool/commons/`)

- **`datapackage.py`** — add a `ResourceSource` value type (`type`, `ref`); parse
  it in `parse_canonical_datapackage_yaml` / `read_datapackage` and expose it on
  `DataResource`; render it in `render_canonical_datapackage_yaml`. Add
  `resolve_local_ref(ref) -> Path | None` (expands a well-formed `${OUTPUT_ROOT}`
  token from the environment; returns `None` when the token is unexpandable or the
  resolved path does not exist; raises only on malformed token syntax). `local` is
  the only resolvable type; a small registry maps `type` → resolver, with remote
  types mapped to a "record-only" resolver that always returns `None`.
- **`promote.py`** — make `_dataset_per_resource` and the shared resource-path
  validation source-aware per the three cases above; add
  `PromoteResourceDigestMismatchError`.

The producer-side stamping is **out of scope** for this design (see boundary).

## Data flow

```
build step (producer)        promote (mint)                     commons artifact
─────────────────────        ──────────────                     ────────────────
stamps hash+bytes+source  →  no source:    stream → (hash,bytes) → datapackage.yaml
into datapackage.json        source+local:  verify-if-present       (path+hash+bytes
                             source+remote: trust recorded           [+source])
                             /off-host:     trust recorded
```

## Scope boundary (two repos)

- **THIS design + implementation plan (`~/d/science`):** the descriptor schema
  (`source` on parse / read / render), source-aware `_dataset_per_resource` +
  resource validation, the new mismatch error, `${OUTPUT_ROOT}` ref resolution,
  and tests. This makes the *capability* exist and verified in isolation.
- **Downstream mm30 task (unblocks t717):** mm30's
  `scripts/shared/datapackage.py::add_resource` and the Walker / Oetjen
  `build_data_package.py` stamp `hash` + `bytes` + `source: {type: local, ref:
  "${OUTPUT_ROOT}/scrna/..."}` for the cache-resident resources, then re-run the
  promote dry-run + `--apply`. Not part of this science spec; it is the consumer
  that proves the capability end-to-end.

## Testing

Unit tests in `~/d/science/science/tests/`:

- parse / render round-trip with `source` (local and a remote kind).
- promote **trusts** a non-resolvable sourced resource — asserts no stream
  occurs and the recorded `(hash, bytes)` is copied into the rendered yaml.
- promote **verify-if-present** passes when a local-resolvable `source.ref`
  matches, and raises `PromoteResourceDigestMismatchError` on drift.
- a sourced resource missing `hash`/`bytes` is rejected; a bad `source.type` is
  rejected; a malformed `local.ref` is rejected.
- regression: a co-located resource (no `source`) promotes exactly as before
  (streams, computes, renders).

## YAGNI / non-goals

- No remote fetching (Zenodo / GitHub / daemon) — those `type`s are recorded and
  validated for shape only.
- No change to the commons-write model — bytes are still never stored in commons.
- No producer/build helper in `science_tool` — producers compute `(sha256,
  bytes)` with their own tooling; `science_tool` only accepts, validates, and
  trusts/verifies the stamped values.
