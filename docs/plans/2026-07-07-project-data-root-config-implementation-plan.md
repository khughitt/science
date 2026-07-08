# Project Data-Root Configuration Implementation Plan

> **Status:** IMPLEMENTED on `main`.
>
> Landed as the project data-root resolver, dataset CLI defaulting,
> data-audit reporting, logical payload inventory, package serialize/verify
> integration, and user-facing documentation. The execution record is
> `docs/plans/2026-07-07-project-data-root-config-execution-plan.md`.
>
> **Rev 2 (2026-07-07, post-review) resolves five gaps:** (1) manifest records a
> stable **logical** path (`data/processed/x`), not `relative_to(project_root)`,
> which throws for out-of-tree payloads (§Manifest logical-path contract, Task 4);
> (2) `data audit` stays **repo-boundary-only** — it does not walk/fix an
> out-of-tree root (Task 3); (3) CLI defaults get an explicit project-root source
> (`SCIENCE_PROJECT_ROOT`/cwd/`--project-root`, Task 2); (4) global `data.root` must
> be **absolute** (kills cwd-instability), only project `data.root` may be relative
> (§Relative-path rule); (5) worktree hydration is **not** threaded and stays
> repo-relative (Non-goals).
>
> **Rev 3 (2026-07-07, review pass 2):** (a) physical dir = `data_root / logical_dir.name`
> (`.../processed`), not `DEFAULT_DATA_DIRS` joined onto the root, which would double the
> `data/` segment (§Source Design); (b) the project-root helper is a **new**
> `discover_project_root()` (env → walk-up-to-`science.yaml` → cwd) — existing code is
> env-or-cwd only, and `resolve_project_root` is already taken by registry-by-name lookup
> (Task 2); (c) the commons recipe lint needs **no functional change** — it is
> commons-recipe-scoped with no project context and its own output dir already matches no
> marker; Task 6 reduces to a boundary guard test + docstring.

**Goal:** Let a project point its bulk / non-version-controlled data at a
configurable root — resolved from `$SCIENCE_DATA_ROOT` → project `science.yaml`
→ global `~/.config/science/config.yaml` → default `./data` — so large derived
data and expensive caches can live on a local disk **outside** the repo tree
(never Dropbox-synced, never git-tracked), while lightweight provenance
(`datapackage.json`, manifests, QA, small frames) stays version-controlled in a
**separate** in-repo path. The hard invariant: **nothing is ever committed under
the resolved data root.**

**Architecture:** This **generalizes an existing, shipped pattern.** Science
already resolves an out-of-tree bulk-data root for the *commons* store
(`commons/config.py::resolve_commons_data_root()`: `$SCIENCE_COMMONS_DATA_ROOT`
→ `commons.data_root` in global config → default `/data/science-commons`) and
already carries a typed, resolver-backed per-project override precedent
(`project_config.py`: `data_policy: DataPolicyConfig | None` +
`resolve_data_policy()`). We mirror both: add `resolve_data_root(project_root)`
with the same precedence shape, a typed `data:` block on `ProjectConfig`, a
`data:` block on `GlobalConfig`, then thread the resolved root through the
per-project data consumers that currently hardcode `project_root / data/…`.
Datapackage logical paths stay strictly relative (the root lives in config only,
exactly as commons does); portable out-of-tree descriptor refs continue to use
the existing `${OUTPUT_ROOT}` token.

**Tech Stack:** pydantic config models (`project_config.py`, `registry/config.py`),
the commons resolver pattern (`commons/config.py`), `pytest` unit + guard tests,
markdown user-guide/skill docs, `scripts/generate_codex_skills.py`.

---

## Motivating context

A downstream project (`natural-systems`) lives under a Dropbox-synced path and
accumulated a 4.4 GB arXiv run (normalized-equation rows + an 800 MB tex fetch
cache) inside `data/processed/` — which was **both** heavily Dropbox-synced
**and** gitignored (worst of both), with the lightweight provenance either
force-added or untracked. It was migrated by hand to a split layout: bulk to
`/data/proj/natural-systems/…` (local, off-Dropbox, off-git), provenance
committed under `data/provenance/…`. This plan turns that hand-rolled pattern
into a first-class, configurable science capability so projects don't have to
reinvent it (or rely on force-adds).

Symlink-based redirection already exists for worktrees
(`data_worktree.hydrate_worktree_data` symlinks `data/{raw,processed,external}`
from an owning worktree). It is lower-friction (audit/serialize follow the
symlink) but breaks under Dropbox (which follows symlinks and re-syncs the
target). Config-based redirection is therefore the primary mechanism this plan
adds; symlink hydration stays as-is for the worktree case.

## Source Design

### Resolver (mirror `resolve_commons_data_root`)

New `resolve_data_root(project_root: Path, config: ProjectConfig | None = None) -> Path`
(home: `science/src/science_tool/data_root.py`, or alongside `data_worktree.py`).
Discovery order:

1. `$SCIENCE_DATA_ROOT` (expanduser) — per-machine / CI override, highest precedence.
2. Project `science.yaml` → `data.root` (typed; expanduser; a relative value
   resolves against `project_root`).
3. Global `~/.config/science/config.yaml` → `data.root` (a **shared parent**):
   per-project root = `<data.root> / <project_id>` (project id from
   `load_project_config(project_root).id`, which already defaults to the dir
   name). This yields the `/data/<project>` layout.
4. Default: `project_root / "data"`.

**Relative-path rule (resolves the cwd-instability the commons note flags).**
The commons resolver resolves a relative global value against the process CWD,
which would make a global data *parent* vary by invocation. To avoid that:

- **Global `data.root` MUST be absolute** (`~` allowed via `expanduser`). A
  relative global value is rejected with a clear error at resolve time — a
  relative global parent is almost certainly a mistake (same reasoning as the
  `data.yaml` overrides requiring absolute).
- **`$SCIENCE_DATA_ROOT` MUST be absolute** (`expanduser` applied), same rejection.
- **Project `science.yaml data.root` MAY be relative** — it resolves against
  `project_root` (stable regardless of cwd), or may be absolute.

`resolve_data_root` returns the **root**. `DEFAULT_DATA_DIRS`
(`data/raw`, `data/processed`, `data/external`) are **logical names**, not
physical sub-paths: the physical directory for a logical `data/<sub>` is
`data_root / <sub>` (`= data_root / logical_dir.name` for the single-level
entries science ships) — e.g. logical `data/processed` → physical
`/data/proj/foo/processed`, **not** `/data/proj/foo/data/processed`. In the
default case (`data_root = project_root/data`) this collapses to the current
`project_root/data/processed`, so behavior is unchanged. The manifest still
records the *logical* name `data/processed/x` (see the logical-path contract
below); only the physical base differs.

### Manifest logical-path contract (reproducibility bundles)

`project_package/payload.py::payload_inventory` currently records each payload's
path as `path.relative_to(project_root).as_posix()` (`payload.py:47`). That
`relative_to` **throws** for a payload physically under an out-of-tree root
(`/data/<project>/processed/x` is not under `project_root`). The fix is a stable
**logical** path, not a physical one:

> A payload's manifest `path` is `<logical_dir> / <subpath>`, where
> `<logical_dir>` is the canonical `DEFAULT_DATA_DIRS` name (e.g. `data/processed`)
> and `<subpath>` is the entry relative to its **physical base**
> (`resolve_data_root()/processed`). So `/data/proj/x/processed/exp/a.parquet`
> and an in-repo `data/processed/exp/a.parquet` both record
> `path: data/processed/exp/a.parquet`.

Consequences: (a) the serialize manifest is **byte-identical** whether the data
root is in-repo or out-of-tree — reproducibility identity is location-independent;
(b) `git_tracked` is looked up by the logical path against the repo `tracked_set`,
so out-of-tree payloads correctly report `git_tracked: false` (nothing out-of-tree
is tracked). Verify resolves the logical path back through `resolve_data_root()`.
Task 4 pins this exact path contract with tests.

### Config surface

**Project** (`project_config.py`) — mirror the `data_policy` precedent with a
nested, typo-catching block:

```python
class ProjectDataConfig(BaseModel):
    """Per-project data-storage location (see resolve_data_root)."""
    model_config = ConfigDict(extra="forbid")  # catches typos, unlike ProjectConfig's extra="allow"
    root: Path | None = None                    # absolute, or relative to project root

class ProjectConfig(BaseModel):
    ...
    data: ProjectDataConfig | None = None
```

**Global** (`registry/config.py`) — mirror `CommonsSettings`:

```python
class DataSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root: Path | None = None   # shared parent; per-project dir = root / <project_id>

class GlobalConfig(BaseModel):
    sync: SyncSettings = ...
    projects: list[RegisteredProject] = ...
    commons: CommonsSettings = ...
    data: DataSettings = Field(default_factory=DataSettings)   # NEW
```

Example global config:

```yaml
# ~/.config/science/config.yaml
data:
  root: /data/proj          # per-project bulk lands at /data/proj/<project-id>/
```

Example project override:

```yaml
# science.yaml
data:
  root: /data/proj/natural-systems
```

### Invariants & the VC/non-VC split

- **Nothing is committed under the resolved data root.** Enforced two ways:
  (a) scaffolding gitignores the in-repo data payload dirs when the root is
  `./data`; (b) a guardrail audit (Task 5) warns when git-tracked files exist
  under the resolved root.
- **VC provenance lives OUTSIDE the data root.** When the root is out-of-tree
  (`/data/<project>`), an in-repo `data/provenance/` is fine (this is what
  natural-systems does). But when the root is the default `./data`, a
  `data/provenance/` would sit *inside* the non-VC root — re-mixing the two. To
  be mode-independent, the recommended convention is a provenance home that is
  **never** under the data root: repo-root `provenance/` (or the existing
  `research/packages/`). Task 7 documents this; the resolver never touches the
  provenance path.
- **Datapackage descriptors stay relative.** `validate_logical_path` already
  forbids absolute/`..` resource paths; the root stays in config, not in
  descriptors. Out-of-tree descriptor refs use the existing `${OUTPUT_ROOT}`
  token (`commons/datapackage.py`).

### Threading targets (from reconnaissance)

The per-project `./data/` world has **no** root indirection today —
`DEFAULT_DATA_DIRS` (`data_worktree.py:7`) is a relative tuple joined to
`project_root` at every consumer. Sites to make root-aware:

| Consumer | File / symbol | Note |
|---|---|---|
| **Reproducibility bundles** | `project_package/payload.py:47` (`payload_inventory`, `_walk_payload_dir`), called by `serialize.py:~246` / `verify.py:~334` | **correctness trap** — walk the physical base, record the **logical** path (see Manifest logical-path contract), Task 4 |
| Data audit | `data_audit.py` (`audit_project`, `_iter`, `location`; `Violation.path` = repo-relative), `data_audit_fix.py` (`apply_fixes` joins `project_root / v.path`) | **repo-boundary only** — audit does NOT walk an out-of-tree root; it never emits non-repo-relative violations (Task 3). Do *not* try to "recompute dirs against the resolved root." |
| `datasets download --dest` | `cli.py:3309` (default `"data/raw"`) | resolve `resolve_data_root(project_root)/raw` only when `--dest` omitted; project root from `SCIENCE_PROJECT_ROOT`/cwd/`--project-root` (Task 2) |
| `datasets validate --path` | `cli.py:3336` (default `"data"`) | same project-root discovery; resolve only when `--path` omitted (Task 2) |
| Commons recipe lint | `commons/dataset_lifecycle.py:388` (`_validate_snakefile_paths`) | **no change required** — commons-recipe-only, no project context, and the commons output dir (`resolve_commons_data_root()/<slug>`) already matches no marker (Task 6: guard test + docstring only). |
| Worktree hydration | `data_worktree.py` (`hydrate_worktree_data`) | **NOT threaded — see Non-goals.** Stays repo-relative; orthogonal to out-of-tree roots. |

## File Structure

- Add `science/src/science_tool/data_root.py` — `resolve_data_root()` + helpers.
- Modify `science/src/science_tool/project_config.py` — `ProjectDataConfig`, `ProjectConfig.data`.
- Modify `science/src/science_tool/registry/config.py` — `DataSettings`, `GlobalConfig.data`.
- Modify `science/src/science_tool/project_package/payload.py` (+ `serialize.py` / `verify.py` callers) — physical walk, logical manifest paths (Task 4).
- Modify `science/src/science_tool/data_audit.py` — repo-boundary-only + external-root info note (Task 3). **Not** `data_audit_fix.py`, **not** `data_worktree.py`.
- Modify `science/src/science_tool/cli.py` — `datasets download`/`validate` lazy default + `--project-root` + `resolve_project_root()` (Task 2).
- Modify `science/src/science_tool/commons/dataset_lifecycle.py` — docstring + guard test only, no logic change (Task 6).
- Add tests under `science/tests/` per task.
- Modify docs: `docs/user-guide/entities.md` (or a data chapter), `skills/data/SKILL.md`, `skills/pipelines/snakemake.md`, `commands/create-project.md`; regenerate affected Codex skill mirrors.

## Task 1: Config surface + resolver (TDD, non-invasive)

**Files:** add `data_root.py`; modify `project_config.py`, `registry/config.py`; add `science/tests/test_data_root.py`.

- [ ] **Step 1 (failing tests):** `test_data_root.py` asserting `resolve_data_root` precedence:
  env over project over global over default; global `data.root` → `<root>/<project_id>`;
  relative project `data.root` resolves against `project_root`; `expanduser` applied;
  unset everywhere → `<project_root>/data`. **Relative-path rule:** a relative global
  `data.root` **and** a relative `$SCIENCE_DATA_ROOT` are each rejected with a clear error;
  a relative *project* `data.root` is accepted and joined to `project_root` (assert it does
  not vary with cwd). Add a `ProjectConfig` parse test that a typo under `data:` raises
  (nested `extra="forbid"`) while an unknown top-level key still loads (existing `extra="allow"`).
- [ ] **Step 2:** implement `ProjectDataConfig` + `ProjectConfig.data`, `DataSettings` +
  `GlobalConfig.data`, and `resolve_data_root()` exactly as in Source Design.
- [ ] **Step 3:** run tests → PASS. Commit `feat: add resolve_data_root + typed data-root config`.

Acceptance: no existing consumer behavior changes yet (resolver exists, unused). `resolve_data_root(root)` with empty config returns `root/data`, so every current caller that later switches to it is behavior-preserving by default.

## Task 2: CLI download/validate defaults (with an explicit project-root source)

**Files:** `cli.py`; `science/tests/` (CLI test).

`datasets download --dest` (`cli.py:3309`) and `datasets validate --path`
(`cli.py:3336`) currently carry **static Click defaults** (`"data/raw"` /
`"data"`) with no project-root — so they cannot resolve a configured root, and a
naive change would resolve the wrong root when invoked from a subdirectory or
automation.

- [ ] **Define the project-root source explicitly.** Today the closest precedent
  is `datasets_identity._project_root_from_env()` and `data_cli.py`, which do
  **env-or-cwd only** (`SCIENCE_PROJECT_ROOT` → else `Path.cwd()`) — there is *no*
  walk-up, so invoking from a subdirectory resolves the subdir as the root. Add a
  **new** helper `discover_project_root()` = `$SCIENCE_PROJECT_ROOT` → walk up from
  cwd to the nearest ancestor containing `science.yaml` → cwd fallback. (Do **not**
  name it `resolve_project_root` — that already exists in `commons/config.py:251`
  for registry-by-name lookup.) Optionally refactor `_project_root_from_env` to
  delegate to the new helper. Add an explicit `--project-root` option to both
  commands for automation.
- [ ] **Resolve the default lazily.** Change the Click defaults to sentinel
  `None`; when `--dest`/`--path` is omitted, compute
  `resolve_data_root(discover_project_root())` (+`/raw` for download). An explicit
  `--dest`/`--path` is used verbatim (no root resolution).
- [ ] Tests: (a) default config + cwd at project root → `--dest` == `<root>/data/raw`
  (unchanged behavior); (b) project `data.root` set → download targets the configured
  root; (c) invoked from a subdirectory → still resolves the project root, not the
  subdir; (d) explicit `--dest ./foo` → used verbatim. Commit.

## Task 3: Data audit stays repo-boundary-only

**Files:** `data_audit.py`; tests. (No `data_worktree.py`, no `data_audit_fix.py` path changes.)

`data audit` is a **repo-hygiene** tool by construction: `Violation.path` is
documented "repo-relative posix", the walk emits `abs_path.relative_to(project_root)`,
and `apply_fixes()` later does `project_root / v.path` / `project_root / v.proposed_target`.
An out-of-tree payload is, by design, outside that boundary — it has no
repo-relative path and no in-repo "move to `results/`" fix. So audit must **not**
try to walk or fix an out-of-tree root (that was the wrong instinct in the prior
draft).

- [ ] When `resolve_data_root(project_root)` is **inside** `project_root` (the default
  `./data` case), behavior is unchanged — audit walks it as today (regression test over an
  existing fixture asserts byte-identical output).
- [ ] When the resolved root is **out-of-tree**, audit does not walk it and emits no
  Violations for it; instead it records a single informational note (e.g.
  `external-data-root: <path> (not audited; provenance lives in-repo)`) so the boundary is
  visible without producing non-repo-relative violations that `apply_fixes` could not act on.
- [ ] Do **not** change `Violation.path` semantics or `apply_fixes`. Test: a project with an
  out-of-tree root produces zero data-payload violations and one info note; `apply_fixes` is
  never handed an out-of-tree path. Commit.

Rationale: repo-boundary hygiene (audit/fix) and out-of-tree payload **inventory**
(Task 4, logical paths) are deliberately separate concerns. Conflating them is
what breaks `Violation.path` and `apply_fixes`.

## Task 4: Reproducibility bundles — physical walk, logical manifest paths (the correctness trap)

**Files:** `project_package/payload.py` (the walk), `serialize.py` / `verify.py` (callers); tests.

`payload_inventory` (`payload.py:14`) walks `project_root / d` for each relative
`d` and records `path.relative_to(project_root)` (`payload.py:47`). Two changes,
per the **Manifest logical-path contract** above:

- [ ] **Walk the physical base.** For each logical dir `d` (e.g. `data/processed`),
  the physical base becomes `resolve_data_root(project_root) / d.name`
  (`.../processed`), not `project_root / d`. Pass the resolved root (or the
  physical bases) into `payload_inventory` / `_walk_payload_dir`.
- [ ] **Record the logical path.** Replace `path.relative_to(project_root)` with
  `d / path.relative_to(physical_base)` — a stable `data/processed/exp/a.parquet`
  regardless of physical location. Look up `git_tracked` by this logical path.
  `verify` maps the logical path back through `resolve_data_root()` to read bytes.
- [ ] **Tests pin the exact path contract:**
  - out-of-tree root: manifest payload inventory is **non-empty**, entries have
    `path: data/processed/...` (not `/data/...`), verify passes — proving we neither
    ship an empty bundle nor leak an absolute physical path into the manifest;
  - **byte-identical manifests:** the same fixture serialized with root `./data`
    vs an out-of-tree root produces the *same* payload `path`/`sha256` list
    (location-independent reproducibility identity);
  - `git_tracked` is `false` for every out-of-tree payload and matches repo state
    for the in-repo case;
  - the existing symlink-cycle guard (`payload.py:37-39`) still fires. Commit.

## Task 5: "No tracked files under the data root" guardrail + scaffolding

**Files:** an audit checker (e.g. extend `data_audit.py` or a new check), `commands/create-project.md`; tests.

- [ ] Guardrail: emit a warning (not a hard error) when git-tracked files exist under the
  resolved data root — this is the structural enforcement of "never commit under the root."
- [ ] Scaffolding: when the root is in-repo (`./data`), `create-project` gitignores the payload
  subdirs (`data/raw`, `data/processed`, `data/external`) using the `dir/*` + `!keep` idiom
  already recommended in the command; when the root is out-of-tree, nothing to ignore.
- [ ] Document that the **VC provenance directory must live outside the data root** (repo-root
  `provenance/` or `research/packages/`); never `data/provenance/` when `./data` is the root.
  Test the guardrail fires on a tracked payload and stays quiet on a clean layout. Commit.

## Task 6: Commons recipe lint — no change required (scoped clarification + guard)

**Files:** `commons/dataset_lifecycle.py` (docstring only); tests.

Re-examination shows this lint needs **no functional change** for the feature:

- It is **commons-recipe-only** — the sole caller is `commons/cli.py:634`
  (`validate_dataset_package(commons_root, slug)`), scanning `dataset_dir/recipe/Snakefile`.
  It never scans project `workflows/`, so a project's configured data root never reaches it.
- `_validate_snakefile_paths(findings, snakefile_path)` has **no** project/commons-root
  context (Finding), so "whitelist a path under a resolved data root" is not expressible
  there — and it doesn't need to be.
- The commons's own bulk output dir is `resolve_commons_data_root()/<slug>` (default
  `/data/science-commons/<slug>`), which matches **none** of the markers
  (`/data/proj/`, `/data/raw/`, `/data/clean/`, `/data/processed/`) — verified. So a
  correctly-written commons recipe writing to its own output dir is already un-flagged; the
  markers only catch stray *parent-project* paths, which remains the intended behavior.

- [ ] Add a **guard test** asserting a commons recipe `Snakefile` that writes under
  `resolve_commons_data_root()/<slug>` is not flagged, while one containing `/data/processed/`
  still is — documenting the boundary so a future change doesn't accidentally broaden the
  markers into the commons output dir. Update the `_validate_snakefile_paths` docstring to
  state the scope (commons recipe only; commons output dir is intentionally excluded). No
  signature or logic change. Commit.

## Task 7: Docs + skills + guard tests

**Files:** `docs/user-guide/entities.md` (or a data chapter), `skills/data/SKILL.md`,
`skills/pipelines/snakemake.md`, `commands/create-project.md`; `science/tests/test_user_guide_docs.py`,
`test_command_docs.py`, `test_codex_skills.py`; regenerate Codex mirrors.

- [ ] Add an anchored **Split storage: version-controlled provenance vs out-of-tree bulk**
  section documenting: the data-root resolver + precedence, the `data:` config blocks, the
  "never commit under the root" invariant, and the VC-provenance-separate convention. Add
  guard tests anchored on the new headings (the plan's convention). Regenerate any affected
  Codex skill mirrors via `scripts/generate_codex_skills.py`; add committed + generated skill
  guards. Commit docs, then commit regenerated skills.

## Task 8: Final review

- [ ] Cumulative diff review; confirm default-path behavior is unchanged for projects with no
  `data:` config (every resolver fallback is `./data`). Confirm datapackage descriptors remain
  relative and no absolute `/data/...` leaked into any resource path. Run the focused suites
  (`test_data_root`, package serialize/verify, doc guards). Record status.

## Non-goals

- No change to the **commons** data-root mechanism (this plan generalizes its *pattern*, not
  its store).
- **Worktree hydration is not threaded with the data root and stays repo-relative.**
  `hydrate_worktree_data` (`data_worktree.py:19`) links `project_root/data/{raw,processed,external}`
  from an owning worktree; it is orthogonal to out-of-tree roots (a configured `/data/<project>`
  root is already shared across worktrees, so there is nothing in `project_root/data/` to
  hydrate). `DEFAULT_DATA_DIRS` keeps its role as the *logical* dir names (reused by the Task 4
  logical-path contract), not as physical roots. No `data_root` parameter is added to worktree
  entry points.
- No migration tooling for existing projects (natural-systems was migrated by hand); an
  optional `science data relocate` helper is a possible later slice.
- No change to datapackage descriptor path semantics (paths stay relative).

## Self-Review Notes

- **Behavior-preserving by default:** every resolver fallback is `<project_root>/data`, so a
  project with no `data:` config sees identical paths — Tasks 2–4 are refactors under an
  unchanged default.
- **The one correctness trap** (Task 4, serialize/verify payload inventory) is isolated with a
  dedicated regression test because it is the failure mode that would silently ship an empty
  reproducibility bundle.
- **Prior art reused, not reinvented:** resolver mirrors `resolve_commons_data_root`; typed
  field mirrors `data_policy`/`resolve_data_policy`; portable refs reuse `${OUTPUT_ROOT}`.
- **Enforcement is structural** (Task 5 guardrail + scaffolding), not just documented, so "never
  commit under the root" is checkable, not aspirational.
