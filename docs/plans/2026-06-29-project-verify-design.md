# Project Verify (`science project verify`) — Design

**Status:** Accepted (brainstorm complete) — ready for implementation plan.
**Date:** 2026-06-29
**Feedback origin:** fb-2026-06-28-004 (downstream `natural-systems`: a pushed `finding`
cited sha256s of payload files that lived only in one local checkout). This is the
**consumer side** of the serialize bundle — it turns serialize's reproducibility *promise*
into something a recipient can *check*. Builds directly on
`docs/plans/2026-06-29-project-serialize-design.md` (shipped local main `d82d2bb7`) and the
`science data audit` boundary it rests on.

## Goal

Given a `science-project-serialized.v1` bundle (`.tar.gz` from `science project serialize`),
**verify** it:

1. **Self-check** (always) — the bundle is internally intact and well-formed: its archived
   bytes match the manifest's recorded hashes, its manifest conforms to the v1 schema, and its
   `data_version` recomputes from the recorded inventory.
2. **`--against <root>`** (optional) — the bundle matches a live checkout on all three
   verifiable claims it carries: the `git_commit`, the **source** file hashes, and the
   **payload** hash inventory. The payload comparison is the direct `natural-systems` payoff:
   *do I actually have, on disk, the exact payloads this bundle (and any finding derived from
   it) relied on?*
3. **`--extract <dir>`** (optional, secondary) — materialize the bundle's source tree to disk,
   but only after the self-check passes.

This is the `proj.deserialize()` / round-trip-verify capability deferred from the serialize
design. **Verify-first, not extract-first:** extracting source is nearly free value (the
source already lives in git, and the bundle is a standard tarball); verification is the
value-add.

## Non-goals (deferred)

- No re-materialization of payloads (the bundle never contained them — by design).
- No `--public`/Zenodo profile concerns (serialize-side).
- No bidirectional source diff ("the checkout has tracked source the bundle lacks"). Source
  comparison is one-directional: bundle → checkout (*does this checkout reproduce the
  bundle's source?*).
- No mutation of the target checkout. Verify is read-only against `--against`.

## Architecture & module seam

`serialize.py` is the **writer**; `verify.py` is the **reader/checker**. Three module changes:

### `science_tool/project_package/verify.py` (new)

The verify entry point and the three checkers (self, against, extract). Owns `VerifyError`
(operational/precondition failures) and the `VerifyResult` verdict.

### `science_tool/project_package/manifest.py` (new)

A strict pydantic `SerializedManifest` model describing the `science-project-serialized.v1`
schema. `verify` parses the bundle's `manifest.json` through it; any schema failure is a
self-check (integrity) failure. The model is **strict on integrity-critical fields**:

- `schema_version` — must equal `"science-project-serialized.v1"` exactly.
- `project.id` — a safe single path segment (reuse serialize's safe-id rule: non-empty, not
  `.`/`..`, no `/` or `\`, matches `[A-Za-z0-9._-]+`).
- `files[].path` / `payloads[].path` — safe relative POSIX paths: non-empty, not absolute, no
  `..` segment, no backslash, no leading `/`.
- `*.sha256` — exactly 64 lowercase hex chars.
- `*.bytes` — integer `>= 0`.
- **Duplicate rejection** — `files[].path` and `payloads[].path` must each be unique;
  duplicates are an integrity failure.
- **No unknown fields** — every model (top-level and nested: `project`, `provenance`,
  `boundary_audit`, each `files[]`/`payloads[]` entry) sets `extra="forbid"`. A v1 manifest
  must not carry fields that are neither schema-owned nor folded into `data_version`; an
  unexpected field is an integrity failure.

A test asserts that `serialize`'s manifest dict parses cleanly through `SerializedManifest`,
keeping writer and reader in lockstep **without** modifying `serialize.py`.

### `science_tool/project_package/payload.py` (new) — behavior-neutral extraction

`--against` must walk a checkout's `data/` with **byte-identical** hashing, sorting,
symlink-cycle handling, regular-file guards, and `git_tracked` computation to what serialize
recorded — otherwise the comparison is unsound. This is a real second consumer, so the walk
moves to a shared module (the same precedent as the `core.py`/labnote extraction):

- Move `_payload_inventory` + `_walk_payload_dir` out of `serialize.py` into
  `project_package/payload.py`, renamed to public `payload_inventory(project_root, data_dirs,
  tracked_set)` + `_walk_payload_dir`.
- Introduce a neutral `PayloadError` raised by the guards (cycle / non-regular file).
- `serialize.py` imports `payload_inventory` and translates `PayloadError` → `SerializeError`
  with the **same message shape** as today (behavior-neutral).
- Keep the move **mechanically small** — no logic change. A golden/determinism test pins
  serialize's payload output unchanged.

`verify.py` reuses `file_resource` / `content_version` from `core.py` and `payload_inventory`
from `payload.py`; nothing new is invented for hashing.

## Bundle shape (what serialize produces — the contract verify enforces)

Every archive member sits under a **single top-level `<project-id>/` prefix**:

```text
<project-id>/manifest.json
<project-id>/science.yaml
<project-id>/entities/**/*.md
<project-id>/results/**/*
<project-id>/papers/references.bib     # if tracked
<project-id>/knowledge/graph.trig      # if tracked
```

The manifest's `files[]`/`payloads[]` paths are archive-relative **without** the top dir.

## Self-check (always runs first)

1. **Readable as our bundle.** Opens as gzip + tar. Failure → integrity (exit 2).
2. **Single shared prefix (structural).** Every member path has exactly one top-level
   segment and all members share the same one. Zero members, a root-level `manifest.json`, or
   mixed prefixes → integrity (exit 2).
3. **Manifest present + valid.** `<shared-prefix>/manifest.json` parses through
   `SerializedManifest` (all strict rules above); then the shared prefix must equal that
   manifest's (safe) `project.id` (a prefix ≠ `project.id` → integrity, exit 2). This matches
   what serialize writes (`<project-id>/manifest.json`, …) and rejects bundles shaped
   otherwise. Failure → integrity (exit 2).
4. **Member completeness.** After stripping the `<project-id>/` prefix, the member set equals
   `{manifest.json} ∪ {files[].path}` **exactly** — no missing, no extra. Mismatch → integrity
   (exit 2).
5. **Safe member kinds.** Every tar member must be a **regular file**. Directories, symlinks,
   hardlinks, device/fifo members, and any absolute or `..`-bearing member path are rejected →
   integrity (exit 2). (A received tarball is untrusted input.)
6. **Content hashes.** Each `files[]` member's archived bytes re-hash to the recorded `sha256`
   and length `bytes`. Mismatch → integrity (exit 2).
7. **`data_version` recompute.** Split the stored `data_version` on the **last** `+` into
   `(base, digest12)`; rebuild the canonical chunk list from `files[]` then `payloads[]` (the
   same canonical-record JSON serialize uses — per `files[]` entry `{path,sha256,bytes}`
   sorted-keys, per `payloads[]` entry `{path,sha256,bytes,git_tracked}` sorted-keys, in
   sorted manifest order); recompute `content_version(base, chunks)` and compare to the stored
   value. Mismatch (a hand-edited manifest) → integrity (exit 2).

If the self-check fails, **nothing else runs and nothing is written** (no `--against`, no
`--extract`).

## `--against <root>`

Runs only if the self-check passed. Preconditions are validated first and short-circuit as
**operational (exit 4)**: `<root>` must exist, be a git worktree, and have a HEAD commit.
Then all three comparisons run and each is reported independently:

- **commit** — `provenance.git_commit` vs `git -C <root> rev-parse HEAD`. Differ → **differ
  class** (exit 1).
- **source** — for each manifest `files[]` entry, re-hash the target's working-tree file at
  that path (`file_resource`). Hash differs **or** file absent in the checkout → **differ
  class** (exit 1). One-directional (bundle → checkout); local-only source is not examined.
- **payloads** — `payload_inventory(<root>, DEFAULT_DATA_DIRS, tracked_set_of_root)` vs the
  manifest's `payloads[]`, joined by `path` (the `git_tracked` field is informational, not
  part of the match):
  - present + sha256/bytes match → **ok**
  - present + sha256 or bytes differs → **DIFFER** (exit 1)
  - in bundle, absent locally → **MISSING** (exit 3)
  - local-only (not in bundle) → **EXTRA** — reported as info, **non-fatal** (a recipient
    holding *more* data than the bundle referenced is not a reproducibility failure).

A `PayloadError` from the walk (symlink cycle / non-regular file under the target's `data/`)
is an operational failure of the `--against` target → exit 4, naming the path.

## `--extract <dir>`

Verify-then-extract, secondary. Self-check must pass first (integrity failure aborts before
any write). The target `<dir>` must be **empty or nonexistent** — refuse to overwrite, fail
loud (exit 4).

**Atomic / nothing-written-on-failure:** extract into a staging directory, then rename/replace
the (empty/absent) target into place as the final step. A filesystem error mid-extraction
leaves the target untouched (operational → exit 4). Extraction is path-traversal–safe (the
same safe-member rules as self-check step 5) and writes the archive **faithfully**:
`<dir>/<project-id>/manifest.json` + the full source tree.

`--against` and `--extract` may be combined. The full sequence is: **self-check → preflight
all operational preconditions (including `--against` target validity and `--extract` target
emptiness) → run `--against` comparisons → extract.** Both targets are preflighted *up front*,
so an empty-dir or invalid-root failure surfaces as exit 4 before any comparison verdict is
computed; a *mid-extract* filesystem write error still exits 4 (the staging-rename keeps the
target untouched). Extraction is gated only on the self-check (integrity), not on `--against`
drift.

## Exit codes

Self-check always runs first, so a broken bundle wins. Operational preconditions are then
preflighted and short-circuit (exit 4) before any comparison verdict is computed. Precedence:
**2 → 4 → 1 → 3 → 0**.

| Code | Meaning |
|---|---|
| 0 | Fully clean (self-check ok; with `--against`, all three dimensions clean) |
| 1 | **differ** — commit, a source file, or a payload differs (divergence) |
| 2 | **bundle integrity** — unreadable, not our bundle, bad prefix, invalid/duplicate manifest, member mismatch, unsafe member, hash mismatch, `data_version` mismatch |
| 3 | **missing** — payload(s) in the inventory are absent locally and nothing differs |
| 4 | **operational** — bundle file not found; `--against` target missing / not a git worktree / no HEAD / payload-walk guard failure; `--extract` dir not empty or write error |

Note on Click: Click's own parser/usage errors (missing required argument, unknown option)
exit with **Click's default usage code (2)** *before* the command body runs. That is a
pre-dispatch layer distinct from our in-command integrity meaning of 2; we document it rather
than override Click. Exit 4 is reserved for "the command dispatched, but a
path/environment/precondition was invalid." The positional bundle uses `Path(exists=False)`
so a missing bundle is *our* exit 4, not Click's.

## CLI

Add `verify` to the **existing** `project` group, sibling to `serialize`:

```
science project verify <bundle.tar.gz> [--against <root>] [--extract <dir>] [--json]
```

- `<bundle.tar.gz>` — positional, required, `click.Path(exists=False, dir_okay=False,
  path_type=Path)` (verify opens and validates it; a missing file is exit 4).
- `--against` — `click.Path(file_okay=False, path_type=Path)`. **No envvar binding.**
  Comparison must be requested *explicitly*; binding `--against` to `SCIENCE_PROJECT_ROOT`
  would make a plain `verify bundle.tar.gz` silently run checkout comparison (and exit 1/3/4)
  whenever that env var happens to be set — self-check-only verification must stay
  environment-independent.
- `--extract` — `click.Path(file_okay=False, path_type=Path)`.
- `--json` — emit a stable machine-readable verdict; **stdout stays pure JSON**.

**Human output** (default): the per-dimension summary —

```
science project verify bundle.tar.gz
  ✓ schema science-project-serialized.v1
  ✓ 142 files match manifest hashes
  ✓ data_version 2026-06-29+ab12cd recomputes

science project verify bundle.tar.gz --against ~/proj
  commit:   4806b789 == HEAD               ✓
  source:   142/142 match working tree     ✓
  payloads: 9/10 present & match
            1 MISSING: data/processed/x.parquet
            0 differ
```

**`--json` output** (stable contract): its own top-level `version` (the **CLI JSON-shape**
contract, independent of the bundle schema — matches `data audit --json`), overall `status` +
`exit_code`, the bundle's own `bundle_schema_version`, the self-check result, per-dimension
`--against` results, and explicit `missing` / `differ` / `extra` payload lists, plus a
`warnings` array. The bundle-schema field is named `bundle_schema_version` (not
`schema_version`) so it is never confused with the JSON-shape `version`.

```json
{
  "version": 1,
  "bundle_schema_version": "science-project-serialized.v1",
  "exit_code": 3,
  "status": "missing",
  "self_check": {"passed": true, "files": 142, "data_version": "2026-06-29+ab12cd"},
  "against": {
    "root": "/home/keith/proj",
    "commit": {"bundle": "4806b789...", "head": "4806b789...", "match": true},
    "source": {"total": 142, "match": 142, "differ": [], "absent": []},
    "payloads": {"ok": 9, "differ": [], "missing": ["data/processed/x.parquet"], "extra": []}
  },
  "warnings": []
}
```

**Warnings** go in the JSON `warnings` array; in non-JSON mode they print to **stderr** so
JSON stdout (when `--json`) and the human verdict stay clean. The headline warning: if the
manifest's `boundary_audit.forced` is true, warn `bundle built with --force; payload boundary
was not clean at serialize time` (non-fatal; does not change the exit code).

## Error handling

Mirrors serialize's fail-loud discipline — every operational failure names the offending path.
Nothing is written except a successful `--extract` after a clean self-check (and that via the
staging-rename so a mid-extract error leaves nothing behind).

| Condition | Exit |
|---|---|
| Bundle file not found / unreadable path | 4 |
| Not gzip / not tar / truncated | 2 |
| Bad/mixed/`project.id`-mismatched top-level prefix | 2 |
| Manifest missing / fails `SerializedManifest` (schema, unsafe id/path, bad sha, dup path) | 2 |
| Member set ≠ `{manifest.json} ∪ files[]` (after prefix strip) | 2 |
| Unsafe tar member (dir, symlink, hardlink, device, absolute/`..`) | 2 |
| File content sha256/bytes mismatch | 2 |
| `data_version` recompute mismatch | 2 |
| `--against` root missing / not a git worktree / no HEAD | 4 |
| `--against` payload-walk guard failure (cycle / non-regular under target `data/`) | 4 |
| `--against` commit / source / payload **differs** | 1 |
| `--against` payload(s) **missing**, nothing differs | 3 |
| `--extract` dir not empty / filesystem write error | 4 |
| All clean | 0 |

## Testing

1. **manifest model** — valid manifest parses; each strict rule rejects (bad schema_version,
   unsafe `project.id`, absolute/`..` file path, 63-char sha, negative bytes, **duplicate
   `files[].path`**, **duplicate `payloads[].path`**, **an unexpected/unknown field on a
   nested model** via `extra="forbid"`).
2. **serialize ↔ model lockstep** — `serialize`'s manifest dict parses cleanly through
   `SerializedManifest`.
3. **payload extraction golden** — serialize's payload inventory byte-identical after the
   `payload.py` move; `PayloadError` → `SerializeError` message shape unchanged.
4. **self-check pass** — a freshly serialized fixture verifies exit 0.
5. **self-check failures** — tampered file byte; dropped member; **extra member**; edited
   `data_version`; **archive prefix ≠ `manifest.project.id`**; non-tar input; root-level
   `manifest.json`. Each → exit 2.
6. **unsafe member rejection** — a tar containing a **symlink** member and one containing a
   **hardlink** member each → exit 2 (built by hand, not via serialize).
7. **`--against` matrix** — commit match/differ; source match/differ/absent; payload
   ok/differ/missing/extra. Assert exit 0/1/3 per the precedence (differ=1 dominates
   missing=3; extra is non-fatal).
8. **missing≠differ** — a checkout missing one payload (nothing differs) → exit 3; a checkout
   with one *differing* payload → exit 1 even if others are missing.
9. **`--against` operational** — target not a git repo / no HEAD → exit 4, path named.
10. **`--extract`** — happy path writes `<dir>/<project-id>/…` faithfully; empty-dir guard →
    exit 4; abort-on-integrity-failure writes nothing; path-traversal member rejected; staging
    rename leaves target untouched on a simulated mid-extract error.
11. **`--force` warning** — a `--force`-built bundle verifies with the boundary warning
    (stderr in human mode, `warnings[]` in JSON) and the warning does not change the exit code.
12. **`--json`** — stdout is pure JSON of the documented shape; exit code matches `exit_code`.
13. **CLI wiring** — `project verify` registered under the existing `project` group; positional
    bundle + `--against`/`--extract`/`--json` parse; exit codes correct.
14. **full round-trip** — `serialize` a fixture → `verify` exit 0 → `verify --against` the same
    clean checkout exit 0.

## Out of scope (deferred)

- Payload re-materialization / fetching missing payloads from a remote.
- Bidirectional source diff (checkout has source the bundle lacks).
- `--public`/Zenodo profile (serialize-side).
- Verifying against a bare commit (no working tree) rather than a checkout.
