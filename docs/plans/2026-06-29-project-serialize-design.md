# Project Serialize (`science project serialize`) — Design

**Status:** Accepted (brainstorm complete) — ready for implementation plan.
**Date:** 2026-06-29
**Feedback origin:** fb-2026-06-28-004 (downstream `natural-systems`: a pushed `finding`
cited sha256s of payload files that lived only in one local checkout under gitignored
`data/processed`). Builds directly on the `science data audit` boundary
(`docs/plans/2026-06-28-data-audit-design.md`, shipped local main `ea35ef0d`).

## Goal

Produce a single, deterministic `.tar.gz` of a project's **tracked source** (entities +
results, **no `data/` payloads**), with a manifest that **hash-inventories the excluded
payloads**. The bundle is portable, byte-for-byte verifiable, and reproducible from code —
the direct antidote to "a shared finding cited hashes of files no one else has."

This is the `proj.serialize()` capability from the data/evidence boundary work. A future
`--public`/Zenodo profile (sensitivity-scrubbed, payloads included) is explicitly **out of
scope** here.

## Privacy stance (settled)

v1 is a **reproducibility bundle, faithful to git — NOT a privacy scrubber.** It ships
**all git-tracked** entities and results with **no sensitivity filtering**. This is
consistent with the data-audit boundary philosophy (tracking is legible from location:
if material is restricted, it must not be tracked). Public-safe scrubbing of both entities
and results is deferred to a later `--public`/Zenodo profile.

Documented loudly in CLI help and the manifest: *serialize is not a privacy scrubber;
tracked content is assumed releasable.*

## Architecture & module seam

"Generalize labnote_export" is scoped to **only what has a real second consumer.** Because
v1 serialize does no sensitivity scrub, it is a **file/package operation, not an entity
operation** — it copies tracked files and hashes them; it never parses frontmatter or
discovers entities. Therefore we do **NOT** extract a neutral entity-source type, and we do
**NOT** move labnote's entity discovery. That would be speculative refactoring of
freshly-merged code with no driver.

The genuinely-shared core is the hashing/versioning/identity primitives:

### `science_tool/project_package/core.py` (new)

```python
@dataclass(frozen=True)
class FileResource:
    path: str       # archive-relative posix path (no top-level project dir)
    sha256: str
    bytes: int

def file_resource(root: Path, relpath: str) -> FileResource:
    """Hash one file under `root`; `path` is `relpath` (already archive-relative)."""

def content_version(base: str, chunks: Iterable[bytes]) -> str:
    """Generic deterministic version: f"{base}+{sha256(concat(chunks))[:12]}".
    Folds sha256 over the chunks in order with NO separators or length prefixes,
    so the labnote call site's digest is preserved byte-for-byte."""
```

A project-identity loader is added here **only if** both labnote and serialize end up
needing the same `science.yaml` id/label handling; otherwise each calls the existing
`load_project_config` / `_load_raw_project_yaml` directly. (Decided during implementation —
no new abstraction without a second caller.)

### `science_tool/labnote_export.py` (refactored, behavior-neutral)

- Imports `file_resource` / `content_version` from `project_package.core`.
- `_sha256` + `_json_resource` → built on `file_resource`; `_data_version` → built on
  `content_version`, **passing labnote's own existing chunk sequence** (science.yaml bytes,
  optional bib/graph bytes, then per-entity source_path + frontmatter json + record json +
  markdown — unchanged order and content).
- Entity discovery, sensitivity gate, views, bundles, links, and app contracts **stay
  local.** No behavior change.
- A **golden test** asserts labnote export output is byte-identical before/after.

### `science_tool/project_package/serialize.py` (new)

```python
@dataclass(frozen=True)
class SerializeResult:
    out_path: Path
    file_count: int
    payload_count: int
    forced: bool

def serialize_project(
    project_root: Path,
    out_archive: Path,
    *,
    force: bool = False,
) -> SerializeResult:
    ...
```

File-level git selection + payload hash inventory + manifest + deterministic tarball.

## Package layout (inside the `.tar.gz`)

Top directory = project id; **manifest paths are archive-relative, WITHOUT the top dir.**

```text
<project-id>/
  manifest.json
  science.yaml
  papers/references.bib        # if tracked
  knowledge/graph.trig          # if tracked
  entities/**/*.md              # all tracked entity files
  results/**/*                  # tracked records only
```

## Selection rules

All inclusion is via `git ls-files`, so the bundle ships **exactly what is committed**:

- **Requires a valid git worktree.** A `git ls-files` failure (not a git repo, git error)
  is a hard fail (exit 1) — serialize is defined over the *tracked* subset, so a non-git
  project has no well-defined bundle.
- **`science.yaml` must be tracked.** Reading project identity from an untracked working-tree
  `science.yaml` would yield a non-portable archive; an untracked or missing `science.yaml`
  hard-fails.
- `git ls-files -- entities/ results/` → tracked source files.
- Tracked top-level singles: `science.yaml`, `papers/references.bib`,
  `knowledge/graph.trig` (each included only if tracked).
- **Clean source (reproducible-from-commit).** The bundle copies *working-tree* bytes but
  records `provenance.git_commit = HEAD`. To keep "exactly what is committed" true, every
  selected source path must match HEAD: if `git diff HEAD -- entities results <singles>` is
  non-empty, **hard fail** (commit or stash first). This check runs before project config
  parsing so a dirty/invalid `science.yaml` reports as unreproducible source drift rather
  than a raw config parse error. Not bypassable by `--force`.
- **Regular files only.** A selected source path that is a symlink or non-regular file is a
  **hard fail** — `read_bytes()` would otherwise package external/untracked target content
  under a tracked path, breaking the git-faithful model.
- **Safe project id.** The archive's top-level dir is the project id; it must be a single safe
  path segment (non-empty, not `.`/`..`, no `/` or `\`). Otherwise hard fail before writing.
- `results/` is `git ls-files -- results/` specifically, so **untracked local output is
  intentionally omitted.**
- `data/` is **never** in `files[]`. The `DEFAULT_DATA_DIRS`
  (`data/raw`, `data/processed`, `data/external`) are walked separately for the payload
  inventory.
- No sensitivity filtering; no `excluded` block.

### `files[]`

Every copied file (including `science.yaml`, `references.bib`, `graph.trig`) gets a
`FileResource` entry. Sorted by archive-relative path.

### `payloads[]` (hash inventory of the absent `data/` tree)

- Walk `DEFAULT_DATA_DIRS`. Since data is **symlink-hydrated** via `data_worktree`, hash the
  **target file content** (follow symlinks to the real regular file).
- Guard symlink cycles and non-regular files (fifos, sockets, dangling links): **fail
  closed** with an explicit error naming the offending path (not silent skip).
- Each entry: `path` (repo-relative posix), `sha256`, `bytes`, `git_tracked`.
  - `git_tracked` is normally `false` (payloads are gitignored). A tracked `data/` payload is
    a `TRACKED_PAYLOAD` boundary violation (see below), so it only reaches the manifest when
    `--force` was used; in that case record the **true** value — never pretend.
- Sorted by repo-relative path.

## Boundary gate

- Run `audit_project(project_root, policy)` (from `data_audit.py`) **before** archive
  creation.
- **Fail closed:** any violation → refuse with a summary of the quadrants + count, exit 1.
- `--force` bypasses **only** audit violations. It does **not** bypass missing
  `science.yaml`, dirty source, unreadable files, invalid project config, or payload-walk
  guard failures — those always hard-fail.

## Data-audit extension (prerequisite, in scope)

The current audit flags `LEAKED_PAYLOAD` only for a payload tracked **outside** `data/`
(the `loc != "DATA"` branch in `_violation_for`, `data_audit.py`). A payload that is
**tracked while sitting inside
`data/`** is also a boundary violation (the whole point of `data/` is that it's ignored), but
it goes uncaught today — so serialize's gate would miss it. Close the gap with a **dedicated
quadrant** rather than overloading `LEAKED_PAYLOAD`, because its remediation differs:

- New `Quadrant.TRACKED_PAYLOAD` for `class=PAYLOAD, loc=DATA, git_tracked=True`.
- `_violation_for`: emit it with `proposed_target=None` (remediation is `git rm --cached`,
  i.e. untrack-in-place — **never** an auto-move). `_planned_action` returns `"flag"` for it
  (report-only; `--fix` never acts on it).
- `render_json` surfaces it like the other quadrants; report/help text names the
  `git rm --cached` remediation.
- This is a self-contained `data_audit.py` change with its own tests, sequenced **before**
  the serialize tasks so the gate is meaningful.

## `manifest.json` schema (`science-project-serialized.v1`)

```json
{
  "schema_version": "science-project-serialized.v1",
  "project": {"id": "demo", "label": "Demo", "summary": "..."},
  "data_version": "<base>+<digest12>",
  "provenance": {"git_commit": "<sha>", "tool": "science"},
  "boundary_audit": {"passed": true, "forced": false},
  "files":    [{"path": "entities/questions/q-001.md", "sha256": "...", "bytes": 1234}],
  "payloads": [{"path": "data/processed/x.parquet", "sha256": "...", "bytes": 99, "git_tracked": false}]
}
```

- `boundary_audit.passed` = audit found zero violations; `forced` = `--force` was used to
  build despite violations. A forced archive is always distinguishable from a clean one.
- `data_version` uses `content_version(base, chunks)` where `base` mirrors labnote's
  (`raw_config.last_modified or version or "0"`). To capture path/manifest changes (not just
  bytes — a rename with identical content must change the version), serialize hashes the
  **canonical resource records**, not raw file contents: for each `files[]` entry the sorted
  JSON of `{path, sha256, bytes}`, then for each `payloads[]` entry the sorted JSON of
  `{path, sha256, bytes, git_tracked}`, in sorted manifest order. `content_version()` itself
  stays separator-free (labnote's call site is unchanged and byte-identical); only serialize's
  chunk list is boundary-aware/canonical.
- `provenance.git_commit` = `git rev-parse HEAD`. A repo with **no HEAD commit** (e.g. a fresh
  `git init` with nothing committed) is a **hard fail** — `git ls-files` can succeed there while
  there is no commit to be reproducible from, which contradicts the reproducibility story.

## CLI

Add `serialize` to the **existing** `project` group (`@main.group() def project()` at
`cli.py:4572`, already home to `project index` / `project artifacts`):

```
science project serialize --project-root <root> --out <bundle.tar.gz> [--force]
```

- `--project-root`: matches the prevailing house convention (35 vs 8 `--project` uses) and
  the sibling `labnote export`. Defaults to `.`, honors `SCIENCE_PROJECT_ROOT` envvar.
- `--out`: required, the output `.tar.gz` path. **Must not resolve inside the project root**
  (see error handling) — otherwise a prior archive sitting under a tracked path could be
  selected into the new one, breaking determinism and making the bundle self-referential.
- `--force`: bypass audit violations only.
- Exit 0 on success; exit 1 on audit violations (no `--force`) or hard-fail conditions
  (missing/untracked `science.yaml`, non-git worktree, `--out` inside project root,
  dirty source, invalid config, unreadable/guard failures).
- On success, echo a one-line summary: file count, payload count, forced flag, out path.

## Determinism

The archive is byte-identical for identical input:

- Tar entries **sorted** by archive-relative path.
- Every member normalized: `mtime=0`, `uid=gid=0`, `uname=gname=""`,
  mode `0644` (files) / `0755` (dirs).
- Gzip stream written with `mtime=0`.
- `manifest.json` itself is generated before tarring and included as a normal member;
  JSON written with `sort_keys=True` + stable indentation.

A test asserts two consecutive runs over the same project produce identical archive bytes.

## Error handling

| Condition | Behavior |
|---|---|
| Not a git worktree / `git ls-files` fails | Hard fail, exit 1 (not bypassable) |
| No HEAD commit (`git rev-parse HEAD` fails) | Hard fail, exit 1 (not bypassable) |
| Missing or untracked `science.yaml` | Hard fail, exit 1 (not bypassable by `--force`) |
| Selected source differs from HEAD (dirty) | Hard fail, exit 1 (not bypassable); name an example path |
| Selected source is a symlink / non-regular | Hard fail, exit 1; name the path |
| Unsafe project id (empty, `.`/`..`, contains `/` or `\`) | Hard fail, exit 1 |
| `--out` resolves inside the project root | Hard fail, exit 1 (not bypassable) |
| Audit violations, no `--force` | Refuse with summary, exit 1 |
| Audit violations, `--force` | Build; `boundary_audit.forced=true` |
| Symlink cycle / non-regular file in `data/` | Hard fail, name the path |
| Filesystem read/stat error (source or payload) | Wrap `OSError` → hard fail naming the path (CLI catches it) |
| Invalid/unreadable `science.yaml` during config/manifest load | Wrap as hard fail (`SerializeError`) after clean-source checks |
| No tracked entities/results | Build an archive with empty `files[]` for those roots (still includes tracked `science.yaml`); not an error |

## Testing

0. **data-audit `TRACKED_PAYLOAD`** — a tracked file under `data/` that classifies as
   PAYLOAD yields a `TRACKED_PAYLOAD` violation with `proposed_target=None` and planned
   action `"flag"`; an *untracked* `data/` payload yields no violation; `render_json`
   includes it. (Prerequisite task, `test_data_audit.py`.)
1. **labnote golden test** — export output byte-identical after the `core` extraction
   (reuse existing `test_labnote_export.py` fixtures).
2. **serialize happy path** — tmp-project fixture: assert archive membership, manifest
   schema, `files[]` covers tracked source incl. `science.yaml`, `data/` absent from
   `files[]`.
3. **payload inventory** — an uncopied `data/processed/*` file appears in `payloads[]` with
   correct sha256/bytes and `git_tracked=false`; symlink-hydrated content hashed via target.
4. **results selection** — only `git ls-files -- results/` included; an untracked
   `results/` file is omitted.
5. **boundary gate** — violations → refuse + exit 1; `--force` → build with
   `boundary_audit.forced=true`.
6. **guard failure** — a non-regular / cyclic data entry hard-fails with the path named.
7. **determinism** — two runs produce byte-identical archives; a path-only rename (identical
   bytes) changes `data_version` (canonical-record hashing).
8. **`--out` inside project root** — hard-fails before any archive is written.
9. **non-git worktree / untracked `science.yaml`** — hard-fail, exit 1.
10. **CLI wiring** — `project serialize` registered under the existing `project` group;
    `--project-root`/`--out`/`--force` parse; exit codes correct.

## Out of scope (deferred)

- `--public`/Zenodo profile (sensitivity scrub of entities AND results; payloads included).
- `proj.deserialize()` / import / round-trip verification command.
- Any reuse of the per-workflow `research-package` builder.
- Neutral entity-source type extraction (no second consumer in v1).
