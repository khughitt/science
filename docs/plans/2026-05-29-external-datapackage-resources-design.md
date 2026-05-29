# Content-Addressed Datapackage Resources with Pluggable Sources — Design

**Status:** approved design (2026-05-29); implementation plan to follow.

**Goal:** Let a commons dataset declare resources whose bytes legitimately live
off-repo (bulk storage now; remote commons — Zenodo / GitHub / a daemon —
later), so `science commons promote dataset` records each resource's
location + checksum **without requiring the bytes co-located under the
datapackage directory, and without being required to stream multi-GB files at
promote time** — by default it trusts the build-stamped digest and does no local
I/O; integrity re-checking is opt-in (`--verify-digests`).

**Architecture (one sentence):** A resource gains an optional typed `source`
descriptor; its presence flips the resource from "co-located, promote computes
the digest by streaming" to "content-addressed, the digest is build-stamped and
the bytes may live anywhere," with `(hash, bytes)` as the canonical identity
that ties every source and verification boundary together.

**Tech stack:** Python 3.11+ (the existing project runtime — `requires-python
>=3.11`, pyright `pythonVersion = 3.11`); the existing `science_tool.commons` promote /
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
  promote can re-verify *on demand* (`--verify-digests`, when the file is locally
  resolvable), and a future remote consumer verifies *on fetch*. One hash, many
  sources, verification wherever the bytes meet the descriptor — but never forced
  into the default promote path.

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
- **`local.ref`**: an off-repo filesystem path. **Allowed forms: a path that
  begins with the `${OUTPUT_ROOT}` token, or a plain absolute path.** A plain
  *relative* ref is rejected (cwd-dependent, ambiguous — there is no project root
  to resolve it against at consume time). The canonical `datapackage.yaml` stores
  `source` **verbatim** (the unexpanded token), keeping the committed artifact
  host-independent. Token expansion happens only transiently, and only under
  `--verify-digests` (below), when promote tries to locate the file; promote stays
  project-agnostic by expanding from the `OUTPUT_ROOT` environment variable.
- **Discriminator decision (a):** the *presence* of `source` marks a resource as
  sourced; there is no separate `external: true` flag. Fewer fields, one source of
  truth, and co-located resources are unchanged.
- **Ref portability decision (b):** local refs use the `${OUTPUT_ROOT}` token (or
  absolute) rather than plain machine-specific absolute paths only.

## Promote behavior

`_dataset_per_resource` (and the resource-existence validation it shares with
`_validate_datapackage_resources`) becomes source-aware. The **default** path
never touches a sourced resource's bytes — that is what satisfies the
"not required to stream" goal for the 14 GB case:

- **No `source` (co-located)** → unchanged: resolve under the datapackage dir,
  stream → `(hash, bytes)`.
- **`source` present (default)** → **trust** the build-stamped `(hash, bytes)`
  verbatim. **No local I/O** — no stat, no stream, no token expansion. This is
  also remote-uniform: a `/data` file and a Zenodo file behave identically.

Integrity re-checking is **opt-in** via a new `--verify-digests` flag. When set,
promote attempts to locate each sourced resource on this host and reports a
per-resource verdict (it never silently skips):

| ref state under `--verify-digests` | action | verdict |
| --- | --- | --- |
| `local` ref resolves to an existing file | stream + assert match | `verified` or **hard error** on drift (`PromoteResourceDigestMismatchError`) |
| `local` ref resolves but the file is **missing** (env-expanded path absent, or absolute ref absent) | — | **hard error** (stale/typo ref; you asked to verify and it is broken) |
| `local` ref token unexpandable (env unset) | — | `skipped (off-host)` — reported, non-fatal |
| remote `type` (zenodo/github/url/daemon) | — | `skipped (no fetcher this iteration)` — reported, non-fatal |

A hard error (digest drift, or a resolvable-but-missing ref) raises and aborts
the promote, so "failed" verdicts surface as the raised exception rather than
the summary. The remaining verdicts — `verified` and the two `skipped` kinds —
**must** be carried back to the CLI so the skips are visible; that is what makes
"never silently skips" implementable (see the result-object change below). The
CLI prints a per-resource `verified / skipped(off-host) / skipped(remote)`
summary. Co-located resources are always streamed regardless of the flag
(unchanged).

The rendered canonical `datapackage.yaml` carries `path + hash + bytes + source`
for sourced resources (co-located resources render `path + hash + bytes` as
today).

## Validation and errors (fail-loud, no silent fallback)

These checks run at promote time regardless of `--verify-digests` (they are
descriptor-shape checks, not byte checks):

- **`path` is always a safe logical path.** Every resource's `path` (co-located
  *and* sourced) is run through the existing `validate_logical_path`
  (`commons/datapackage.py`) — rejects absolute, `..`, backslashes, drive-letters,
  and non-normalized forms. For sourced resources `path` is a logical package
  name, so this is the only structural guard on it (the old parent-escape /
  `is_file` filesystem check does not apply to sourced resources).
- A sourced resource with a missing **or invalid** `hash`/`bytes` → hard error
  (cannot trust an unstamped or malformed resource — default promote copies these
  fields verbatim into the rendered yaml). `hash` must pass the existing
  `parse_resource_hash` (`sha256:<64 hex>`); `bytes` must be an `int`, **not** a
  `bool`, and `>= 0`. This is the same check `parse_canonical_datapackage_yaml`
  already applies on the commons read side, hoisted to the project-side promote
  input.
- `source.type` outside the enum → hard error.
- A source `ref` that is malformed → hard error: empty/whitespace, a
  syntactically-broken `${...}` token, **any token other than `${OUTPUT_ROOT}`**,
  or (for `local`) a plain *relative* path.
  Allowed `local.ref`: `${OUTPUT_ROOT}`-prefixed or absolute.
- A co-located resource (no `source`) still hits the existing parent-escape /
  `is_file` checks unchanged, and is always streamed.

Byte-level outcomes (only under `--verify-digests`) follow the table above: a
digest mismatch or a resolvable-but-missing local file is a **hard error**; an
unexpandable token / remote type is a reported, non-fatal skip. The new error
type is `PromoteResourceDigestMismatchError`, naming the resource and expected
vs. actual `(hash, bytes)`.

## Components (all in `~/d/science/science/src/science_tool/commons/`)

- **`datapackage.py`** — add a `ResourceSource` value type (`type`, `ref`); parse
  it in `parse_canonical_datapackage_yaml` / `read_datapackage` and expose it on
  `DataResource` (so the source survives a read round-trip); render it in
  `render_canonical_datapackage_yaml`. Validate `source.type` against the enum and
  `ref` shape (reject relative `local` refs). Add `resolve_local_ref` with a
  **single** explicit contract:

  ```python
  # one frozen result type — no Path | None ambiguity
  class RefResolution: ...                       # sealed/Union of the two below
  @dataclass(frozen=True)
  class Unexpandable(RefResolution): ...          # ${OUTPUT_ROOT} but OUTPUT_ROOT env unset, or a remote type
  @dataclass(frozen=True)
  class Resolved(RefResolution):
      path: Path
      exists: bool

  def resolve_local_ref(ref: str) -> RefResolution: ...
  ```

  **Only `${OUTPUT_ROOT}` is a valid token this iteration** (expanded from the
  `OUTPUT_ROOT` env var); any other `${VAR}` is *malformed* and rejected at
  validation time. `resolve_local_ref` raises only on malformed `ref` (already
  caught by validation); otherwise returns `Unexpandable` (the `${OUTPUT_ROOT}`
  token present but `OUTPUT_ROOT` unset) or `Resolved(path, exists)` (an absolute
  ref, or a token expanded against a set `OUTPUT_ROOT`). This lets promote tell
  "off-host skip" from "resolved-but-missing error" without a `None` overload.
  `local` is the only resolvable type; a registry maps `type` → resolver, remote
  types → a record-only resolver (always `Unexpandable`).
- **`promote.py`** — make `_dataset_per_resource` + the shared resource-path
  validation source-aware (default trust; co-located stream unchanged); add
  `PromoteResourceDigestMismatchError`; run `validate_logical_path` on every
  resource `path`.

  **Result channel for verify verdicts.** `_dataset_per_resource` no longer
  returns a bare `dict[str, tuple[str, int]]`; it returns a small frozen result so
  non-fatal skips can reach the CLI:

  ```python
  @dataclass(frozen=True)
  class ResourceVerification:
      name: str
      status: Literal["verified", "skipped_off_host", "skipped_remote"]
      detail: str                       # e.g. the unexpanded ref / remote type
  @dataclass(frozen=True)
  class PerResourceResult:
      per_resource: dict[str, tuple[str, int]]      # unchanged payload for rendering
      verifications: list[ResourceVerification]     # empty unless --verify-digests
  ```

  Callers read `.per_resource` exactly where they used the old dict (rendering is
  untouched). `plan_promote` aggregates `.verifications` across datasets onto the
  returned `PromotePlan` (alongside the existing `dataset_audit_extras` channel),
  and `_promote_kind_cmd` prints the per-resource summary. Hard-error verdicts
  (drift / resolvable-but-missing) raise from inside `_dataset_per_resource` and
  never reach the list.

  **Thread the opt-in flag through the existing API** rather than reading global
  state:
  - CLI: add `--verify-digests` to the `promote dataset` command (`cli.py`), pass
    `verify_digests=` into `_promote_kind_cmd` (cli.py:620), which forwards it to
    `plan_promote(..., verify_digests=...)`.
  - `plan_promote` (promote.py:572) gains a keyword-only `verify_digests: bool =
    False`; it forwards to `_dataset_per_resource(dataset_primary, verify_digests=...)`
    (call site ~725) and to `_validate_dataset_group_datapackages(...,
    verify_digests=...)` (~734), which in turn passes it to its inner
    `_dataset_per_resource(candidate, verify_digests=...)` (~2446).
  - `_dataset_per_resource(candidate, *, verify_digests: bool = False)`
    (promote.py:2379) is where the default-trust vs verify-table logic lives.
  Default `False` everywhere preserves every existing caller/test untouched.
- **`inventory.py`** — `build_commons_inventory` serializes per-resource
  `{path, hash, bytes, format, mediatype}` (line ~116); **add `source`** so the
  inventory is not lossy for sourced resources.

The producer-side stamping is **out of scope** for this design (see boundary).
`resolver.py` (`science commons data resolve`) is **also out of scope this
iteration** (see non-goals).

## Data flow

```
build step (producer)        promote (mint)                       commons artifact
─────────────────────        ───────────────                      ────────────────
stamps hash+bytes+source  →  no source:        stream → (hash,bytes) → datapackage.yaml
into datapackage.json        source (default):  trust recorded         (path+hash+bytes
                             source (--verify-  verify-if-resolvable     [+source])
                               digests):          else skip/ERROR
```

## Scope boundary (two repos)

- **THIS design + implementation plan (`~/d/science`):** the descriptor schema
  (`source` on parse / read / render + `DataResource`), source-aware
  `_dataset_per_resource` (default trust) + resource validation
  (`validate_logical_path` on every `path`), the `--verify-digests` flag and its
  verify path, the new mismatch error, `${OUTPUT_ROOT}` best-effort ref resolution,
  the inventory `source` field, and tests. This makes the *capability* exist and
  verified in isolation.
- **Downstream mm30 task (unblocks t717):** mm30's
  `scripts/shared/datapackage.py::add_resource` and the Walker / Oetjen
  `build_data_package.py` stamp `hash` + `bytes` + `source: {type: local, ref:
  "${OUTPUT_ROOT}/scrna/..."}` for the cache-resident resources, then re-run the
  promote dry-run + `--apply`. Not part of this science spec; it is the consumer
  that proves the capability end-to-end.

## Testing

Unit tests in `~/d/science/science/tests/`:

- parse / render round-trip with `source` (local and a remote kind); read
  round-trip surfaces `source` on `DataResource`.
- **default promote trusts** a sourced resource — asserts **no byte I/O** occurs
  (e.g. patch/spy `stream_sha256_and_bytes` and assert not called for the sourced
  resource) and the recorded `(hash, bytes)` is copied into the rendered yaml.
- `--verify-digests`: passes when a local-resolvable `source.ref` matches; raises
  `PromoteResourceDigestMismatchError` on drift; **hard-errors** when the ref
  resolves but the file is missing; **reports a non-fatal skip** when the token is
  unexpandable (`OUTPUT_ROOT` unset) and when the type is remote.
- the verify verdicts reach the caller: `_dataset_per_resource` returns a
  `PerResourceResult` whose `verifications` list is empty without the flag and,
  with it, carries one `ResourceVerification` per sourced resource with the right
  `status` (verified / skipped_off_host / skipped_remote); `plan_promote` surfaces
  them on the plan so the CLI summary cannot silently drop a skip.
- validation: sourced resource with missing **or invalid** `hash` (not
  `sha256:<64hex>`) / `bytes` (non-int, `bool`, or negative) rejected; bad
  `source.type` rejected; empty / relative / non-`${OUTPUT_ROOT}` / malformed-token
  `local.ref` rejected; a `path` failing `validate_logical_path` (absolute, `..`,
  backslash) rejected for both co-located and sourced resources.
- `inventory.py`: a sourced resource's `source` survives into the inventory
  serialization (not dropped).
- regression: a co-located resource (no `source`) promotes exactly as before
  (streams, computes, renders).

## YAGNI / non-goals

- No remote fetching (Zenodo / GitHub / daemon) — those `type`s are recorded and
  validated for shape only.
- No change to the commons-write model — bytes are still never stored in commons.
- No producer/build helper in `science_tool` — producers compute `(sha256,
  bytes)` with their own tooling; `science_tool` only accepts, validates, and
  trusts/verifies the stamped values.
- **`resolver.py` (`commons data resolve`) is unchanged this iteration.** It
  resolves `data_root/<slug>/<logical_path>` and re-hashes on every call (built
  for small co-located CSVs, never multi-GB bytes), so it neither consults
  `source.ref` nor fetches remote sources. A sourced large resource is therefore
  promote-side metadata that is **not** retrievable via `data resolve` yet;
  teaching the resolver to honor `source` (local ref first, then remote fetchers)
  is the natural follow-on once remote commons lands. Called out so the limitation
  is explicit, not silent.
