# Design: `science data audit` + the data-policy SSOT

## Status
Accepted (brainstormed 2026-06-28). Supersedes the implementation premise of the
triage note `docs/plans/2026-06-28-feedback-data-evidence-tracking-boundary.md`
(fb-2026-06-28-004), which proposed force-add-in-place. **That premise is rejected**
(see below). This is the accepted design for the first effort.

## Origin
Downstream `natural-systems`, 2026-06-28: a committed, pushed `finding` cited sha256s
of a freeze file, a precision JSON, and a verdicts JSONL that existed only in one local
checkout — because they sat inside the gitignored `data/processed` subtree. ~470
equivalent evidence files across 8 subprojects had been silently dropped; one early
subtree had been rescued with `git add -f`. The triage note framed the fix as
"force-add evidence in place."

## The reframing (why force-add-in-place is rejected)
A mixed ignored / force-added tree is **brittle**: files get accidentally added or
silently dropped, and you cannot look at a directory and know what is "in" the project.
The boundary must be **legible from location**, never from a pile of `git add -f`
exceptions.

This also serves a larger goal: a project should be shareable as a lightweight package
(`proj.serialize()` → JSON/MD/YAML records + entities, **no payloads**), backed by the
codebase so a consumer can fork it, re-run the pipeline, and regenerate the payloads —
with an optional later Zenodo bundle that includes open payloads. That only works if
"tracked" means "reproducible-from-code lightweight record" and payloads live cleanly
outside the tracked tree.

## Boundary model (the invariant this encodes)

| Location | Meaning | Git |
|---|---|---|
| `data/{raw,processed,external}/` | payload territory — large, fetchable/regenerable | **ignored** (symlink-hydrated via `data_worktree`) |
| `entities/` | durable identity / owner records | tracked |
| `results/<workflow-or-exp>/…` | lightweight **pipeline records**: QA reports, result summaries, run manifests, datapackage descriptors, verdicts, small tables | tracked |

Rules:
- Records link to owners by **explicit fields** (`dataset:`, `workflow:`, `run:`,
  `derived_from:`), **not** directory proximity.
- Generated records are **not** entity owners — they do not live under `entities/`.
- `results/` is already the established home: `datasets_register.py:172` emits
  `results/<workflow-slug>/<run-id>/<slug>/datapackage.yaml`; `workflow_run.py` loads
  `results/**/datapackage.json`; the `DatapackageAdapter` already scans `["data","results"]`.
  This design **formalizes an existing convention**, it does not invent a new axis.
- `DEFAULT_DATA_DIRS` (`data_worktree.py:7`) is the authoritative "this subtree is
  payload" signal and is read by the audit. `data_worktree` is unchanged.

## Scope of this effort
**In:** the policy SSOT module + `science data audit` (read-only report + conservative
`--fix`). **Deferred** (noted, not built): size-guard pre-commit hook; validate-time
orphaned-provenance warn; `science health` orphaned-files check; `.gitignore`/scaffold
template delta + downstream migration sweep; a future explicit `data migrate-payloads`
(or `--fix-payloads`) for relocating tracked payloads.

---

## Component 1 — `data_policy.py` (the SSOT)

A frozen, typed policy plus a pure classifier. Lives at
`science/src/science_tool/data_policy.py` (all package code is under `science/src/…`;
this spec lives at the repo root).

### Policy
- `DEFAULT_DATA_POLICY` framework constant (built like `DEFAULT_ANCHOR_PATTERNS` in
  `project_config.py`):
  - `record_patterns`: **name/path-based only** (no size encoded — size is the
    classifier's job) globs marking a file as a candidate RECORD —
    `datapackage.{json,yaml}`; `RESULTS*.md`; `*-report.{md,json}`; `**/qa/*.json`;
    `{README,RUBRIC}.md`; `validate_*.py`; `*worksheet*.jsonl`; `*verdict*`; `*label*`;
    `*-notes.md`; `*majority*`; dataset metadata sidecars; interpretation `.md`. A bare
    `.csv`/`.tsv`/`.json` that matches none of these is **not** auto-classified RECORD —
    it falls to the unknown-small → FLAG branch (surfaced for an explicit decision), which
    is the intended conservative behavior. The concrete pattern set is pinned in the
    implementation plan; these are the intent and are tunable via `data_policy:`.
  - `payload_extensions`: `.parquet .feather .pkl .pdf .npy .npz .tar .tar.gz .tgz .zip
    .mp4 .mat` (+ `**/tex/**` raw-dump dirs).
  - `size_threshold`: `150_000` bytes (≈150 KB).
- Optional per-project override: a new `DataPolicyConfig` block on `ProjectConfig`
  (mirrors `ProseLintConfig`/`RefsConfig`, `extra="forbid"`), surfaced as a
  `data_policy:` key in `science.yaml`. Fields: `record_patterns`, `payload_extensions`,
  `size_threshold`. Absent block → `DEFAULT_DATA_POLICY`.

### Classifier
`classify(rel_path: Path, size_bytes: int, policy: DataPolicy) -> FileClass`
where `FileClass ∈ {RECORD, PAYLOAD, FLAG}`. **Conservative** decision table
(first match wins):

| Condition | Class |
|---|---|
| payload extension (any size) | `PAYLOAD` |
| matches a record pattern AND `size ≤ threshold` | `RECORD` |
| matches a record pattern AND `size > threshold` | `FLAG` (large record — "irreplaceable hand-authored?" author decides) |
| no pattern match AND `size > threshold` | `PAYLOAD` (safe to ignore the large unknown) |
| no pattern match AND `size ≤ threshold` | `FLAG` (never auto-track the unknown) |

Properties: pure, deterministic, no filesystem mutation, no git calls. This is the one
place the COMMIT-vs-KEEP-IGNORED rule is expressed; the audit (and future hook) consume
it.

---

## Component 2 — `science data audit`

A **new top-level `data` click group** (room for `data check-size` etc. later). The
audit is repo-wide filesystem payload-policy hygiene — broader than dataset semantics,
so it is deliberately *not* placed under `datasets`.

### What it computes
Walks the repo. For each file determines `(class, location, git_tracked)`:
- `class` from the classifier.
- `location` ∈ {`DATA` (under a `DEFAULT_DATA_DIRS` subtree), `RESULTS`, `ENTITIES`,
  `TRACKED_OTHER`} — `DATA` is read from `DEFAULT_DATA_DIRS`, not hard-coded.
- `git_tracked` from `git ls-files` (one batched call).

Cross-checks into quadrants:
- **STRANDED_RECORD** — `class=RECORD`, `location=DATA` (ignored) → belongs in `results/`.
- **LEAKED_PAYLOAD** — `class=PAYLOAD`, `git_tracked=True`, `location` is a tracked dir
  → belongs in `data/` + ignored.
- **FLAG** — `class=FLAG`, or any case the `--fix` logic cannot resolve unambiguously →
  reported with a *proposed* target, never auto-acted.

### Read-only (`science data audit`)
Grouped human report per quadrant. Nonzero exit when violations exist (CI-ready for a
later build gate). `--json` emits the machine-readable report (see contract below).

### `--fix` (conservative)
Automatic actions are limited to the **safe, common direction** — moving stranded
records *out of* ignored `data/` *into* tracked `results/`:

1. **STRANDED_RECORD →** move to
   `results/<nearest-exp-or-workflow>/<relative-name>`.
   - **Move semantics (postcondition).** Stranded records are, by definition, ignored/
     untracked (they live inside an ignored `data/` subtree), so `git mv` — which requires
     a **tracked** source — would fail for the primary case. The rule is source-state
     dependent, converging on one uniform end state:
     - **Tracked source** (rare; a record force-added earlier) → `git mv source target`
       (preserves history, stages the rename).
     - **Untracked/ignored source** (the common case) → filesystem move
       (`shutil.move`/`os.replace`) **then `git add <target>`**. There is no staged
       deletion (the source was never tracked).
     - **Uniform end state:** the target exists under `results/…` and is **staged**; the
       source is gone. `--fix` **stages** the result but does **not commit** — the author
       reviews `git status` and commits. (The moved-and-rewritten datapackage descriptor
       in step 2 is likewise staged.)
   - **`<nearest-exp-or-workflow>` resolution — exact, ordered** (first that succeeds;
     implementers must not invent their own slug extraction):
     1. If the moved file **is** or **has a sibling** `datapackage.{yaml,json}` declaring
        a `workflow:` field → use that value with the `workflow:` prefix stripped as the
        slug (matches `datasets_register.py`'s `workflow_id.removeprefix("workflow:")`).
     2. Else fall back to the **first path segment after** `data/{raw,processed,external}/`
        (the "exp" directory). The datapackage `name` field
        (`<workflow-slug>-<run-slug>-<out-slug>`) is **not** parsed for a slug: workflow
        slugs themselves contain hyphens, so the segment boundaries are ambiguous from the
        string alone.
   - Preserve relative substructure beneath that segment to avoid collisions; if the
     destination already exists with different content → **FLAG**, do not overwrite.
2. **Structural reference rewrite — datapackage descriptors only.** When the moved file
   is a `datapackage.{yaml,json}`, recompute its resource references so each still
   resolves to the unchanged payload left under `data/`.
   - **Resolution contract (must be preserved):** consumers resolve a resource as
     `descriptor.parent / basepath / resources[].path` — e.g. per-output datapackages set
     `basepath: ".."` and keep `resources[].path` verbatim (`datasets_register.py:97`;
     asserted at `test_dataset_register_run.py:130`). The run-aggregate case has no/empty
     basepath and resolves `descriptor.parent / path` (`datasets_register.py:84`). So the
     **effective resource base** is `descriptor.parent / (basepath or ".")`.
   - **Rewrite rule:** for each resource, compute the absolute target from the *old*
     descriptor (`old_descriptor.parent / (basepath or ".") / path`). After the move,
     **preserve the existing `basepath` string** and recompute
     `resources[].path = relpath(target, new_descriptor.parent / (basepath or "."))` —
     i.e. relative to the effective resource base, so the resolution contract still holds.
     (With `basepath: ".."` and a payload left under `data/`, this yields a path like
     `../data/processed/<exp>/x.feather`; with no basepath, relative-to-descriptor.)
   - **Path form:** **relative** (never project-root-relative). Project-root-relative
     (`data/processed/…`) would be easier to audit but would **not** resolve under the
     current `descriptor.parent / basepath / path` contract; adopting it is a deferred
     loader-change, out of scope here.
   - **FLAG (do not move the descriptor)** if the rewrite cannot be done unambiguously:
     a resource `path` (or `basepath`) is absolute, escapes the repo, or is otherwise
     non-relative, or the target payload does not exist.
3. **LEAKED_PAYLOAD → FLAG only, never move.** Un-tracking a payload
   (`git rm --cached` + move + gitignore) can break references, committed fixtures, LFS
   expectations, or need history cleanup a working-tree move cannot achieve. `--fix`
   reports it with a proposed target (`git rm --cached … ; mv → data/… ; gitignore`) and
   leaves the decision to the author. A future explicit `data migrate-payloads` may
   automate this deliberately.
4. **Ambiguous anything → FLAG with proposed target.** No guessing.

**Symlink-hydrated `data/` safety (footnote, pinned).** `data_worktree` hydrates a
worktree's `data/{raw,processed,external}/` as **symlinks** to a shared external source
root. Two guards:
- **Traversal:** the audit walks the project tree but does **not descend through a
  symlinked directory whose real path escapes `project_root`** (avoids scanning the entire
  external source and symlink loops). A `DEFAULT_DATA_DIRS` entry that *is* a symlink is
  noted, and its contents are classified for the report but treated as out-of-tree for
  fixing.
- **Fixing:** `--fix` **must not move a file whose source path traverses a symlinked
  `DEFAULT_DATA_DIRS` entry** (or whose real path resolves outside `project_root`) — doing
  so would mutate the shared/external source through the symlink, affecting other
  worktrees. Such a stranded record is **FLAGged** (with its proposed `results/…` target)
  rather than moved. The common, safe case — a non-worktree main checkout where `data/`
  is real ignored directories — moves normally.

So the default `--fix` posture is exactly:
- MAY relocate stranded records from ignored `data/` into tracked `results/`.
- MAY structurally rewrite a moved datapackage's resource paths.
- Does NOT move payloads or resolve ambiguous records.

This keeps an *audit-repair* command from becoming a *data-migration* tool.

### Machine-readable move report (`--json`)
A stable contract for tests, CI, and downstream migration sweeps. Emitted by both the
read-only audit (planned actions) and `--fix` (performed actions). Shape:

```json
{
  "version": 1,
  "violations": [
    {"quadrant": "stranded_record", "path": "data/processed/exp1/RESULTS.md",
     "class": "record", "action": "move",
     "target": "results/exp1/RESULTS.md", "performed": true},
    {"quadrant": "stranded_record", "path": "data/processed/exp1/datapackage.yaml",
     "class": "record", "action": "move+rewrite-resources",
     "target": "results/exp1/datapackage.yaml", "performed": true,
     "basepath": "..",
     "rewritten_resources": [
       {"name": "matrix", "from": "matrix.feather",
        "to": "../data/processed/exp1/matrix.feather"}]},
    {"quadrant": "leaked_payload", "path": "entities/x/big.feather",
     "class": "payload", "action": "flag",
     "target": "data/processed/…", "performed": false},
    {"quadrant": "flag", "path": "data/processed/exp1/weird.bin",
     "class": "flag", "action": "flag", "target": null, "performed": false}
  ]
}
```

`performed` is always `false` in read-only mode and reflects reality in `--fix` mode
(e.g. a FLAGged item stays `false`).

---

## Reconciliation with existing machinery
- **`data_worktree.py`:** unchanged. `results/` is NOT added to `DEFAULT_DATA_DIRS`
  (tracked files are not symlink-hydrated). The audit reads `DEFAULT_DATA_DIRS` as the
  payload-territory signal.
- **`DatapackageAdapter` / `datasets_register`:** already scan `["data","results"]`;
  relocating descriptors to `results/` while preserving `basepath` and recomputing
  `resources[].path` against the effective resource base stays loader-compatible.
- **`project_config.py`:** new `DataPolicyConfig` follows the established nested-block
  pattern; non-breaking (`ProjectConfig` is `extra="allow"`).

## Testing (TDD)
- **Policy:** classification decision-table tests (each row), default-vs-override,
  threshold boundary, payload-extension precedence.
- **Audit (read-only):** quadrant detection on a fixture tree (stranded record, leaked
  tracked payload, large-record FLAG, unknown-small FLAG); `--json` shape; nonzero exit
  on violations.
- **`--fix` move semantics:** untracked/ignored stranded record → filesystem move +
  `git add <target>`, ending **staged** under `results/…` with the source gone (the
  primary case); tracked source → `git mv`; **no commit** is created (assert `git status`
  shows staged-but-uncommitted). `<nearest-exp-or-workflow>` resolution order (explicit
  datapackage `workflow:` field → first path segment; the `name` field is not parsed).
- **`--fix` datapackage rewrite:** preserve `basepath` (incl. the `basepath: ".."` case)
  and recompute against the effective resource base, with a round-trip assert that
  `new_descriptor.parent / basepath / path` resolves to the original payload; collision →
  FLAG (no overwrite); absolute/escaping resource path → FLAG (descriptor not moved).
- **`--fix` symlink guard:** a stranded record under a symlinked `DEFAULT_DATA_DIRS` entry
  (or whose real path escapes `project_root`) → **FLAG, not moved** (no mutation of the
  shared source); the non-symlink case moves normally.
- **`--fix` other:** leaked payload → FLAG (file untouched, still tracked); ambiguous →
  FLAG; `--json` `performed` flags accurate.

## Open follow-ons (explicitly deferred)
1. Size-guard pre-commit hook consuming `data_policy` (P2).
2. `science validate` warn when a finding/report cites an ignored non-payload file
   (reuses the classifier).
3. `science health` orphaned-files/dirs check (same boundary, recurring-hygiene face).
4. `.gitignore`/scaffold template delta + an initial `science data audit --fix` sweep
   across downstream projects.
5. Explicit `data migrate-payloads` (or `--fix-payloads`) for tracked-payload relocation.
6. Project-root-relative datapackage resource paths (needs a loader change).

## Appendix — downstream evidence
`natural-systems` commits `8ba917dd` (spike) and `bc685f4f` (476 files / ~8.3 MB tracked,
~8 GB payloads left ignored) are the concrete before/after; their per-cluster manifests
enumerate the COMMIT-vs-KEEP-IGNORED split this policy formalizes.
