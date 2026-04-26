# Managed Artifacts — Long-Term System Design

**Date:** 2026-04-26
**Status:** Approved (brainstorm phase). Pending: implementation plan (`superpowers:writing-plans`).
**Scope:** B (managed-artifact class). Validators are the first instance; the system generalizes to all Science-managed bytes downstreams consume verbatim.
**Composes with (does not deliver):** Bucket C P1 design (entity model); `[t009]` entity-rename / declarative-migrations primitive.
**Supersedes / redirects:** `docs/plans/2026-04-25-managed-artifact-versioning.md` (MAV plan as currently written); `docs/plans/2026-04-25-mav-audit-addendum.md` (Plan #7 — its six fixes become the first version bump under this system).

---

## Summary

A managed artifact is a contract: Science owns the bytes, guarantees a stable extension protocol, and downstream projects consume by installing, customize via the protocol, and stay current via update. The system has one canonical bytes file per artifact (inside the `science-tool` Python package), one declarative registry of capabilities matrices, a per-artifact header protocol, a per-artifact extension protocol whose options are constrained by consumer class, date-based versions with full hash history, declarative migrations with transaction-safe rollback, and loud-signaling-with-manual-mutation propagation. No legacy/compatibility layers; `meta/validate.sh` and `scripts/validate.sh` become one-line `exec` shims.

## Mental model

The system rhymes with how OS package managers handle distributed config: a registry describes what's available, canonical bytes live in one place, version metadata says what's installed where, drift detection answers "are you current," update is a typed verb that may carry migration steps, and held/pinned packages are a first-class concept. Managed artifacts are the `apt` of Science's upstream→downstream propagation surface; templates and entity-model migrations are separate (related) systems that the same human eventually uses.

## Scope

### In scope

- The full lifecycle of any byte-distributable Science output that downstream projects consume verbatim. Initial member: `validate.sh`. Likely future members: hook configs, CI snippets, agent-skeleton sections, `.editorconfig`, generated `.gitignore` fragments.
- A single declarative registry with per-artifact metadata.
- A single canonical bytes location per artifact.
- A sidecar-based extension protocol (no inline marker editing).
- Date-based versioning with full hash history (uncapped).
- Declarative migration steps paired to version bumps (when a bump requires the project to do something beyond byte-replace).
- CLI verbs: `science-tool project artifacts list | check | diff | install | update | pin | unpin`.
- Status surfaced in `science-tool health`, `/status`, `/next-steps`, `science-tool sync`.
- Pre-update `.pre-update.bak`; reversible commits.
- Test gates: per-artifact hash matches version field; registry round-trips; every artifact declares a sidecar protocol or explicitly opts out.

### Out of scope (deliberately)

- **Templates** (`templates/synthesis.md`, `templates/next-steps.md`, etc.) — these are project-fill, contract-checked by validators. Different concept; managed by a different system.
- **Runtime-resolved harness content** (commands, skills, references) — already handled by harness path resolution; not byte-distributed.
- **Project-owned files Science cares about the SHAPE of** — those are the validator's job; `validate.sh` is itself a managed artifact, pleasingly.
- **Cross-project ontology propagation** — separate system, the multi-project sync work. The managed-artifact system is one delivery channel, not a replacement.
- **Entity-rename / declarative entity migrations** (`[t009]`) — composes with this system but is its own next-cycle work, gated on Bucket C.

## Architecture

### Registry as data, not code

A single declarative file `science-tool/src/science_tool/project_artifacts/registry.yaml` lists every managed artifact. Each entry is a **capabilities matrix** that bundles content metadata, header protocol, install behavior, consumer type, extension protocol, mutation policy, version, history, and migrations.

#### Per-artifact capabilities matrix

```yaml
- name: validate.sh
  source: data/validate.sh                     # path within the project_artifacts package
  install_target: validate.sh                  # path relative to project root
  description: Structural validation for Science research projects

  # --- content / install metadata ---
  content_type: text                           # text | binary
  newline: lf                                  # lf | crlf | preserve
  mode: "0755"                                 # filesystem mode for install_target
  consumer: direct_execute                     # see "Consumer taxonomy"

  # --- header protocol (how the managed header is encoded inside the file) ---
  header_protocol:
    kind: shebang_comment                      # see "Header protocol"
    comment_prefix: "#"
    # for shebang_comment: header is inserted immediately AFTER the shebang line.

  # --- extension protocol (how downstream projects extend the artifact) ---
  extension_protocol:
    kind: sourced_sidecar                      # see "Extension protocols"
    sidecar_path: validate.local.sh
    hook_namespace: SCIENCE_VALIDATE_HOOKS     # contract defined per-protocol
    contract: |
      If validate.local.sh exists in the project root, the canonical sources
      it during init (BEFORE any validation runs). The sidecar registers
      callbacks via register_validation_hook <hook-name> <function-name>.
      Canonical dispatches at named hook points during validation.

  # --- mutation policy (transaction & worktree safety) ---
  mutation_policy:
    requires_clean_worktree: true              # default for update/migration
    commit_default: true                       # update emits a commit unless --no-commit
    transaction_kind: temp_commit              # temp_commit (Git) | manifest (outside Git or Git)

  # --- version + history (uncapped — see "Versioning") ---
  version: 2026.04.26
  current_hash: <sha256>
  previous_hashes:                             # ALL released hashes, never aged out
    - version: 2026.04.25
      hash: <sha256>
    - version: 2026.04.20
      hash: <sha256>

  # --- migrations paired to version bumps ---
  migrations:
    - from: 2026.04.25
      to:   2026.04.26
      kind: byte_replace                       # byte_replace | project_action | hybrid
      summary: Audit-surfaced fixes (Plan #7 batch).
    # entries with kind != byte_replace carry a `steps:` block — see "Declarative migrations"

  changelog:
    2026.04.26: Audit-surfaced six-fix batch (Plan #7).
    2026.04.25: P1 #2/#4/#10 validator additions.
```

Adding a managed artifact = one registry entry + one bytes file in `data/`. No code change.

The remaining subsections of Architecture define each capability area in detail.

### One physical canonical, packaged

`science-tool/src/science_tool/project_artifacts/data/<artifact>` is the only **canonical bytes** file upstream. Three points need explicit treatment:

**1. The package data IS the fully-rendered managed artifact** — header included.

The bytes file in `data/` is what installs ship; install is byte-copy plus chmod, not byte-copy plus header rewrite. A test asserts that the bytes file's leading lines match its declared `header_protocol` and that the body's hash matches `current_hash`. Drift detection on installed files re-parses the header to extract the installed version and recompute the body hash. This eliminates an entire class of bugs (install-time header mutation getting out of sync with check-time header parsing) and makes the canonical bytes file directly executable / loadable by the canonical's intended consumer (bash will run `data/validate.sh` directly because the header is shell-comment lines bash ignores).

For shell artifacts: `data/validate.sh` already begins with `#!/usr/bin/env bash`, then the header lines, then the canonical body. For non-shell artifacts: the bytes file contains the header in whatever form the artifact's `header_protocol` declares (or, for `sidecar_metadata` kinds, an unmodified body and a sibling `data/<artifact>.science-managed.yaml` carrying the metadata).

Bumping the version is therefore an atomic act on the bytes file: edit the body, regenerate the header lines (the `science-managed-version` and `science-managed-source-sha256` values), commit. A package-level test rejects any commit where the header values disagree with the body bytes.

**2. Path-convenience shims (`meta/validate.sh`, `scripts/validate.sh`).**

Both files exist today and are reached by muscle memory and tooling. They become one-line shims that exec the canonical via a path-relative `uv run` invocation:

```bash
#!/usr/bin/env bash
# science-managed: shim for validate.sh (path convenience; not a managed artifact)
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --project "$here/../science-tool" \
     science-tool project artifacts exec validate.sh -- "$@"
```

The `science-tool project artifacts exec <name>` verb is part of the v1 CLI surface — it resolves the canonical bytes file path and execs it. The shim form above is repo-position-relative (`$here/..` reaches the repo root from either `meta/` or `scripts/`), so both shims are byte-identical and a single test asserts the spec'd string against both.

These shims are NOT managed artifacts (no header registered for them, no version, no registry entry). They are NOT installed copies. They are pure path conveniences explicitly excluded from "no second canonical bytes file" checks.

**3. Self-installation under the same system.**

`meta/` IS a Science-managed project (it has its own `science.yaml`) but it does NOT need to install `validate.sh` — it consumes via the shim, which reaches the canonical via the package every time. This avoids the "edit canonical → re-install in meta → commit" dance during dev. Downstream projects (`mm30`, `cbioportal`, etc.) DO install — they're independent repos and need a checked-in copy so their own tooling/CI can read it without depending on `science-tool` being importable.

This resolves the apparent contradiction "single canonical AND meta/ self-validates": canonical lives in the package, downstream copies are installed, the upstream repo (including `meta/`) reaches canonical via shim and never copies.

### Consumer taxonomy

The right extension mechanism depends entirely on **who reads the file**. The registry's per-artifact `consumer:` field places each artifact in one of three classes; the extension protocol must be valid for the consumer.

- **`direct_execute`** — the file is invoked by a runtime that reads its own contents (shell, Python script, etc.). Extension via `sourced_sidecar` works because the canonical itself reads and incorporates the sidecar at runtime.

- **`science_loader`** — the file is read by Science's own loader (which can be made aware of sidecars). Extension via `merged_sidecar` works only because every reader is the package's loader, not a raw parser.

- **`native_tool`** — the file is read by an external tool (Git reads `.gitignore`; editors read `.editorconfig`; CI runners read their config). External tools are not aware of sidecars. The only safe pattern is **`generated_effective_file`**: the canonical is treated as a *source*, the project owns the *effective file*, and a Science-tool verb regenerates the effective file from canonical + project-local fragments. The effective file IS NOT a managed artifact (its hash will diverge by design); the canonical input IS.

### Extension protocols

For each consumer class, the extension protocol the registry permits:

- **`direct_execute`** → `sourced_sidecar` or `none`.
- **`science_loader`** → `merged_sidecar` or `none`.
- **`native_tool`** → `generated_effective_file` only (where the canonical is the source artifact, not the on-disk effective file).
- All consumers → `none`, declared explicitly as `extension_protocol: { kind: none, rationale: <reason> }`.

**v1 ships only `direct_execute` + `sourced_sidecar`** (and `none`). The other consumer/protocol combinations are defined here for schema stability but no v1 artifact uses them. They will be exercised when a real artifact requires them; until then their semantics remain provisional.

#### `sourced_sidecar` hook contract (v1)

Sourcing a sidecar at the *end* of a script doesn't help: by then validation has already run with no opportunity for the sidecar to intervene. The contract is therefore:

1. Canonical declares a hook namespace (`SCIENCE_VALIDATE_HOOKS` for `validate.sh`).
2. Canonical defines `register_validation_hook <hook-name> <function-name>`.
3. Canonical defines named hook points (e.g. `before_pre_registration_check`, `after_synthesis_check`, `final_summary`) and dispatches at each point: for each registered function under that hook name, call it.
4. **The sidecar is sourced during canonical's init phase, BEFORE any validation runs.** The sidecar's job is to define functions and call `register_validation_hook` to wire them in.
5. The list of hook points and the namespace name are declared in the artifact's `extension_protocol.contract` field, so projects can rely on them as a stable surface.

This makes extensions intervention-capable rather than after-the-fact. The cost is one more design decision per artifact (which hook points to expose); this is the right cost.

Sidecar files are project-owned: never updated by Science, never tracked by the managed-artifact system, never appear in drift reports. The system also never parses or validates sidecar contents — that responsibility belongs to the canonical's runtime (e.g. bash will report a syntax error when sourcing a malformed sidecar).

**Hard principle:** if you can't design a clean extension protocol for an artifact within its consumer class, it's the wrong file to manage. The registry has no escape hatch for "extension forbidden, just freeze the bytes"; opting out is a deliberate `extension_protocol: { kind: none, rationale: <reason> }` field that exists precisely to make the decision visible.

### Versioning and hash history

Each artifact carries `version` (`YYYY.MM.DD`, optionally `YYYY.MM.DD.N` for same-day bumps), `current_hash`, and `previous_hashes` — a list of every released `{version, hash}` pair, **uncapped**. Storage cost is trivial (~64 bytes per version) and the cap creates real correctness problems with long-lived pins (a project pinned to a version older than the cap window can no longer be classified). Pin entries also store the hash inline (see "No legacy / compatibility layers") so they remain self-classifiable even if registry retention policy ever changed.

Drift classification at downstream check:

- Installed hash matches `current_hash` → **current**.
- Installed hash matches one of `previous_hashes` → **stale (N versions behind, last bumped <date>)**.
- Installed hash matches the project's pin hash → **pinned (and current with respect to the pin)**.
- Installed hash matches none → **locally modified** (or installed-from-fork, or installed-pre-managed-system).
- No managed header in installed file → **untracked** (file exists but isn't managed).
- File missing → **missing**.

### Header protocol (per-artifact)

Every managed artifact must declare how its managed header is encoded. The header carries the artifact name, version, and body hash. The shape varies because shell scripts, JSON files, binary blobs, and `.editorconfig`-like formats accept very different syntax.

Defined kinds:

- **`shebang_comment`** — for executable scripts. Header lines are inserted **immediately after** the shebang (which must remain byte 0). Comment prefix per-artifact (`#` for bash, `;` for some configs). Example layout for `validate.sh`:

  ```bash
  #!/usr/bin/env bash
  # science-managed-artifact: validate.sh
  # science-managed-version: 2026.04.26
  # science-managed-source-sha256: <hash-of-body-after-header>
  # ----- canonical body below -----
  ```

- **`comment`** — for non-executable text files that accept a comment syntax. Header is at byte 0; comment prefix per-artifact.

- **`sidecar_metadata`** — for files where the body cannot accept a header (binary formats, JSON without `//` comments, formats where any prefix would change semantics). Header lives in a sibling file `<install_target>.science-managed.yaml`. Body bytes are unmodified. Drift detection compares body hash against the sidecar's recorded hash.

- **`none_with_registry_hash_only`** — no header anywhere; drift detection is purely "current installed bytes hash equals one of the known hashes in the registry." Use only when no other option works (rare; flagged as a yellow path during design).

Per-artifact `header_protocol` block declares `kind`, `comment_prefix` (where applicable), and any kind-specific fields. The header body hash is always computed over the bytes *after* the header (or over the entire body for `sidecar_metadata` / `none_with_registry_hash_only`).

For v1: `validate.sh` uses `shebang_comment` with `comment_prefix: "#"`. Other kinds are defined here so the registry schema is stable, but no v1 artifact exercises them.

### Declarative migrations, paired with version bumps

Most version bumps are pure byte-replace and need no project-side action. When a bump requires the project to do something the system can't infer, the registry pairs the version with one or more **migration steps**.

#### Step shape

A migration step has a Python module reference *or* a bash block. Python is the **default**; bash is allowed only with constraints because shell snippets are hard to test and the YAML must avoid tag-syntax landmines (a bare `! grep ...` is parsed as a YAML tag, not a string).

```yaml
migrations:
  - from: 2026.04.26
    to:   2026.05.10
    kind: project_action            # byte_replace | project_action | hybrid
    steps:
      - id: add_phase_to_hypotheses
        description: Ensure science.yaml has phase on each hypothesis.
        impl:
          kind: python
          module: science_tool.project_artifacts.migrations.add_phase
          # module exposes: check(project_root) -> bool
          #                 apply(project_root) -> AppliedChanges
          #                 unapply(project_root, applied) -> None  (if reversible)
        touched_paths:                # declared up front for conflict checks
          - specs/hypotheses/*.md
        reversible: true
        idempotent: true

      - id: remove_legacy_flag
        description: Remove deprecated SCIENCE_X env var from .env files.
        impl:
          kind: bash
          shell: bash
          working_dir: "."            # project root
          timeout_seconds: 30
          check: |
            # exits 0 if migration is unnecessary; non-zero otherwise.
            # Block scalar — every line is literal, no YAML tag parsing.
            if ls .env* >/dev/null 2>&1 && grep -q '^SCIENCE_X=' .env*; then
              exit 1
            fi
            exit 0
          apply: |
            sed -i '/^SCIENCE_X=/d' .env*
        touched_paths:
          - .env
          - .env.*
        reversible: false
        idempotent: true
```

#### Update walk

The update CLI:

1. Verify worktree is clean (or `--allow-dirty` is set; see "Dirty-worktree and transaction safety").
2. Take a transaction snapshot (per the artifact's `mutation_policy.transaction_kind`).
3. For each step in order:
   - Run `check` — if it reports unnecessary, skip.
   - Display `description` + the `apply` body. If interactive, prompt for confirmation. `--auto-apply` skips the prompt for steps marked `idempotent: true`.
   - Run `apply` with the declared `working_dir` and `timeout_seconds`.
   - Re-run `check` — must now report unnecessary. If it doesn't, abort and roll back the transaction.
4. After all steps succeed, perform the byte-replace + write `<artifact>.pre-update.bak`.
5. Emit a single commit: `chore(artifacts): refresh validate.sh to 2026.05.10` with body listing every step that ran. Skipped if `--no-commit`.

If any step fails or its post-`check` doesn't pass, the transaction snapshot is restored and the artifact is left at the old version.

#### Test gates for migration steps

- Each step's `check`/`apply`/`check` cycle is exercised by a fixture that builds a synthetic project where `check` initially reports needed, runs `apply`, asserts `check` reports satisfied.
- For `reversible: true` steps with a Python `unapply`, a fixture also asserts `apply` then `unapply` returns to the original state.
- For bash steps: the YAML loader rejects `check`/`apply` values that aren't block scalars (`|` or `>`); plain-flow values are a schema error.

This step shape is what `[t009]` (declarative entity migrations) will reuse; the registry's migration block is the seam where managed-artifact migrations and entity migrations meet. Phase 2 of `scripts/migrate_downstream_conventions.py` (shape-driven rules, landed `fe8d974`) is the working prior art; the formalization above is its declarative successor.

### Dirty-worktree and transaction safety

Mutating verbs (`update`, `pin`, `unpin`, the byte-replace and migration steps inside `update`) must not silently entangle with unrelated in-flight work. Two flag families with **independent** semantics:

- **Worktree-state flag** — controls whether the verb runs against a dirty worktree. `--allow-dirty` permits it; the default refuses.
- **Commit flag** — controls whether the verb emits a commit. `--no-commit` skips commit emission; the default emits per `mutation_policy.commit_default`.

The two flags are orthogonal. `--no-commit` does NOT bypass the clean-worktree check; `--allow-dirty` does NOT skip the commit. Use them in combination as needed.

Rules:

- **Default: clean worktree required.** `update`/`pin`/`unpin` refuse if `git status --porcelain` is non-empty. Message lists the dirty paths.
- **`--allow-dirty`** — proceed against a dirty worktree, but only if no path the operation will touch (the artifact path + every migration step's `touched_paths` glob) intersects with a dirty path. On intersection, refuse with a clear conflict message naming the intersecting paths.
- **`--no-commit`** — perform the mutation but skip the commit. The user is responsible for committing (e.g., bundling with related work). Has no effect on the worktree-state check.
- **Outside a Git repository** — `update` works (byte-replace + `.pre-update.bak`), `commit_default` is treated as false, no commit attempted, transaction kind degrades to `manifest`. `pin`/`unpin` still edit `science.yaml` but cannot commit.
- **Transaction snapshot** — the artifact's `mutation_policy.transaction_kind` selects the mechanism (v1 ships two; `stash` was considered and rejected because its rollback semantics around concurrent `--allow-dirty` user changes are unsafe):
  - `temp_commit` (default; Git-only) — create a temporary commit before migration steps run; on failure, `git reset --hard HEAD~1` to restore. On success, soft-reset the temp commit and create a single canonical commit (carrying the same tree state) with the proper message.
  - `manifest` (Git-or-not) — before any step runs, copy the bytes of every `touched_paths` entry plus the artifact path into a temp directory. On failure, restore each path from the captured copy. Used automatically outside Git.

Because these are user-invoked CLI verbs (not autonomous agent actions), the safety stance is "always reversible by design," not "never use destructive operations." The snapshot mechanism's destructive ops happen entirely on temporary state created by this verb.

### Propagation: loud signaling, manual mutation

Status is surfaced in **all four** of:
- `science-tool health` — one row per managed artifact (status, current, latest, brief drift summary).
- `/status` (the slash command) — loud row when any artifact is stale or locally-modified.
- `/next-steps` — action item when stale: "run `science-tool project artifacts update <name>`."
- `science-tool sync` — warns at the top of sync output if stale artifacts exist.

The mutation is always a typed human verb. There is no auto-update. Pre-update writes `<artifact>.pre-update.bak` for one-step rollback. The update commit message carries old → new version + the registry's `changelog` entry for that bump.

### No legacy / compatibility layers

When canonical drops a behavior, downstreams must update or pin. There is no "we'll keep both behaviors alive in parallel until everyone migrates." Pinning is a deliberate, declared act:

```yaml
# in <project>/science.yaml
managed_artifacts:
  pins:
    - name: validate.sh
      pinned_to: 2026.04.25
      pinned_hash: <sha256>             # captured at pin time; self-classifying even if registry retention ever changed
      rationale: Awaiting CI rewrite; cannot adopt 2026.05.10 yet.
      revisit_by: 2026-06-01
```

Pinned artifacts surface in `health` with a different status (`pinned`) and don't generate stale warnings until the `revisit_by` date passes. If the installed file's hash diverges from `pinned_hash`, health classifies as `pinned-but-locally-modified` — surfaced as a warning regardless of `revisit_by`.

### Test gates

- **Per-artifact `current_hash` matches body bytes.** A package-level pytest test reads each artifact's bytes file from `data/`, parses the header per the entry's `header_protocol` (header is part of the bytes file), recomputes the body hash from the bytes after the header, and asserts equality with `current_hash`. Also asserts the parsed `science-managed-version` line matches the registry's `version`. Catches "you bumped the bytes but forgot to update header values, current_hash, or version."
- **Canonical bytes file is fully-rendered.** A test asserts the bytes file in `data/` begins with the artifact's header in the form its `header_protocol` declares (after the shebang for `shebang_comment` artifacts; at byte 0 for `comment` artifacts; sibling YAML present for `sidecar_metadata`). The bytes file is what installs ship — no install-time header rewrite.
- **Install matrix coverage.** A parameterized test exercises every row of the install matrix and asserts the documented refuse/no-op/act behavior.
- **Every released hash is recorded.** `current_hash` and every `previous_hashes[*].hash` are non-empty SHA256 hex strings; no duplicates between `current_hash` and any historical entry.
- **Registry schema strict-validates.** Load the YAML against a JSON-Schema (or pydantic model) describing all required fields per consumer/extension/header-protocol combination. Reject:
  - `consumer: native_tool` with anything other than `extension_protocol.kind: generated_effective_file`.
  - `consumer: direct_execute` with `extension_protocol.kind: merged_sidecar` (or any other invalid pairing).
  - `migrations[*].steps[*].impl.check`/`apply` values that aren't YAML block scalars.
  - Missing `header_protocol`, `consumer`, `mode`, `content_type`, `mutation_policy` (all required).
- **Every artifact declares an extension protocol.** Either a real protocol valid for its consumer or a deliberate `extension_protocol: { kind: none, rationale: "..." }`. No silent absence.
- **Path-convenience shims are byte-correct.** Test asserts `meta/validate.sh` and (if present) `scripts/validate.sh` match the spec'd shim string exactly. Drift in the shim is itself a defect.
- **Self-installation works.** A test runs `science-tool project artifacts install validate.sh` against a temp project (outside the upstream repo) and asserts: installed bytes are byte-equal to the canonical bytes file (no install-time mutation), file mode equals `0755`, and the file is directly executable.
- **Hook contract works (per-artifact).** For `validate.sh`: a test creates a synthetic project, drops a `validate.local.sh` that registers a hook, runs `validate.sh`, asserts the registered function ran at the expected point.
- **Migration step round-trip.** Each step's `check`→`apply`→`check` cycle is exercised in isolation; `reversible: true` steps also exercise `unapply`. Bash-step YAML rejected if not block-scalar.
- **Transaction safety.** A test triggers a deliberately-failing migration step and asserts: artifact remains at old version, project files restored to pre-update state, `.pre-update.bak` not created, no commit emitted, exit code non-zero.
- **Dirty-worktree refusal.** A test asserts `update` exits non-zero with a clear message when worktree is dirty and `--allow-dirty` is not set; a second test asserts `--allow-dirty` proceeds when dirty paths don't intersect, refuses when they do.

## Components

```
science-tool/src/science_tool/project_artifacts/
├── __init__.py                # public exports: canonical_path, install, check, update, list_artifacts, migrations API
├── registry.yaml              # declarative source of truth (see Architecture)
├── registry_schema.py         # pydantic / JSON-Schema model for strict validation
├── data/
│   └── validate.sh            # the only canonical bytes file (v1)
├── artifacts.py               # registry loader, status classification, hash, install/check/update primitives
├── header.py                  # per-artifact header parse/write (one function per header_protocol kind)
├── migrations/                # migration-step runner + per-migration python modules
│   ├── __init__.py            # step runner; check/apply/unapply protocol
│   ├── transaction.py         # temp_commit / manifest snapshot mechanisms
│   └── <future per-migration python modules>
├── cli.py                     # Click commands; integrated into the existing `project` group
└── health.py                  # health-report integration

science-tool/tests/
├── test_project_artifacts.py  # status, diff, install, update primitives
├── test_managed_registry.py   # schema-strict validation, hash-version match, all required fields
├── test_header_protocol.py    # per-kind parse/write, including shebang_comment byte-0 invariant
├── test_extensions.py         # sourced_sidecar hook contract for validate.sh
├── test_migrations.py         # step round-trip, idempotence, reversibility
├── test_transactions.py       # snapshot mechanisms, deliberate-failure rollback
├── test_dirty_worktree.py     # refusal, --allow-dirty conflict checks
└── test_shims.py              # meta/validate.sh + scripts/validate.sh byte-correctness
```

Modifications to existing files:
- `science-tool/src/science_tool/cli.py` — wire `project artifacts ...` into the existing `project` group.
- `science-tool/src/science_tool/graph/health.py` — managed-artifacts table + total-issues contribution.
- `commands/status.md` — surface stale artifacts.
- `commands/next-steps.md` — recommend update on stale.
- `commands/sync.md` (or `science-tool sync` invocation site) — warn on stale at top of sync output.
- `commands/create-project.md` — replace bare-copy instructions with `science-tool project artifacts install`.
- `commands/import-project.md` — same.
- `docs/project-organization-profiles.md` — replace "Refresh `validate.sh`" with the canonical workflow.
- `pyproject.toml` — package data inclusion for `data/` and `registry.yaml`; mark `registry.yaml` as importable resource.

Replacements (not deletions):
- `meta/validate.sh` — replace existing 934-line file with a one-line `exec` shim. Not a managed install; not a canonical.
- `scripts/validate.sh` — replace existing 942-line file with the same one-line `exec` shim.

The byte-replacement happens as part of implementation, after the canonical lands in the package. Both shims are tested for byte-correctness.

## Data flow

```
install:    classify install_target's current state, then act per the install matrix:

            install_target state                                          → action
            -------------------------------------------------------------- ---------
            missing                                                        install (byte-copy + chmod)
            present, hash matches current_hash                             no-op (idempotent; exit 0 with note)
            present, hash matches a previous_hashes entry                  refuse; suggest `update`
            present, hash matches no known version, has managed header     refuse; surface as locally-modified, suggest `diff` then `update --force`
            present, no managed header, hash matches a known version       refuse without --adopt; with --adopt, write the managed header in place (no body change), classify going forward
            present, no managed header, hash matches no known version      refuse without --force-adopt; with --force-adopt, byte-replace with canonical (writes .pre-install.bak)
            present, has managed header for a different artifact name      refuse; almost certainly a registry/path typo

            On install action: byte-copy bytes file → set mode per registry → (no transaction; install is metadata-light)

check:      read install_target → parse header → compute body hash
            → classify against current_hash, previous_hashes, project pin → status

diff:       check + compute udiff (canonical vs installed) → display

update (no migration):
            verify clean worktree (or --allow-dirty + path-conflict check)
            → write <install_target>.pre-update.bak
            → byte-replace install_target (with new header) and chmod per registry
            → commit chore(artifacts): refresh <name> to <version>  (skipped if --no-commit)

update (with migration):
            verify clean worktree (or --allow-dirty + path-conflict check)
            → take transaction snapshot per mutation_policy.transaction_kind
            → for each step in order:
                 run check; skip if satisfied
                 → confirm (unless --auto-apply + idempotent)
                 → run apply with declared working_dir + timeout
                 → re-run check; abort + rollback if not satisfied
            → write <install_target>.pre-update.bak
            → byte-replace + header rewrite
            → discard snapshot; commit chore(artifacts): ... (lists migrated steps)
            on any failure: restore snapshot, leave artifact at old version, exit non-zero

list:       walk registry → render table (name, target, version, status if --check)

pin:        verify clean worktree (or --allow-dirty + path-conflict check on science.yaml)
            → compute installed hash → write {name, pinned_to, pinned_hash, rationale, revisit_by}
              into <project>/science.yaml managed_artifacts.pins
            → emit commit (unless --no-commit)

unpin:      verify clean worktree (or --allow-dirty + path-conflict check on science.yaml)
            → remove the matching entry from managed_artifacts.pins
            → emit commit (unless --no-commit)
```

## Error handling

- **Locally modified at update time** — refuse without `--force --yes`. With force: still write `.pre-update.bak` and take the transaction snapshot. Surface clearly that local edits will be lost.
- **Dirty worktree** — refuse with default settings. Message lists the dirty paths. With `--allow-dirty`: proceed only if no dirty path intersects with the artifact path or any step's `touched_paths` glob; on intersection, refuse with the conflicting paths named explicitly.
- **Migration step `apply` fails** — restore the transaction snapshot. Artifact remains at old version. No `.pre-update.bak` written. No commit emitted. Exit non-zero with the failing step id, the captured stderr, and instructions for re-running.
- **Migration step post-`check` fails** — same as above. Artifact and project files are restored to pre-update state.
- **Migration step `apply` exceeds `timeout_seconds`** — kill the subprocess, restore the snapshot, exit non-zero with the timeout details.
- **Pin past `revisit_by`** — health/status/next-steps surface as a warning; doesn't block other operations.
- **Pin hash mismatch** (installed file diverges from `pinned_hash`) — classify as `pinned-but-locally-modified`. Surface as warning regardless of `revisit_by` because the pin is no longer protecting what was pinned.
- **Registry references missing bytes file** — package-level test catches at CI time. At runtime, `install`/`check` raises a clear error citing the registry entry.
- **Registry schema invalid** — registry loader refuses to load and reports each violation with a path into the YAML (`registry.yaml: artifact[2].extension_protocol.kind 'merged_sidecar' is invalid for consumer 'direct_execute'`). All CLI verbs and tests fail fast.
- **Sidecar exists but malformed** — system never parses the sidecar (sidecars are project-owned). Behavior is whatever the canonical's source/merge does on bad sidecar; for `validate.sh`, bash will exit on syntax error and surface that to the user — not the managed-artifact system's concern beyond letting the canonical's failure propagate.
- **Header missing or unparseable on a `check`** — classify as `untracked`. Clear message: "this file lacks the managed header; either Science doesn't manage it or it predates the managed system. Run `install --adopt` (auto-claims only if installed bytes hash matches a known historical version; otherwise requires `--force-adopt`). See the install matrix in Data flow."
- **`install` against an existing file** — classified per the install matrix in Data flow; refuse-or-act behavior is keyed to the combination of (managed-header present?) and (installed hash recognized?). `--adopt` rewrites the header in place when bytes match a known historical version; `--force-adopt` byte-replaces with canonical and writes `.pre-install.bak`.
- **Outside Git, with `commit_default: true`** — perform the mutation, skip the commit, emit a one-line warning that the operation succeeded but wasn't committed (project is responsible for tracking).

## Sequencing and dependencies

This design redirects in-flight work. The implementation plan must sequence carefully:

1. **Bucket C design session** (P1 #1/#3/#5/#8) — independently planned, separate cycle. Does NOT block this design's implementation, but its decisions feed `[t009]`'s scoping.
2. **MAV plan** (`docs/plans/2026-04-25-managed-artifact-versioning.md`) — should be **revised** rather than implemented as written. The revision incorporates:
   - Capabilities-matrix registry shape (replaces hardcoded `ArtifactDefinition` per-artifact).
   - Per-artifact `header_protocol`, `consumer`, `extension_protocol`, `mutation_policy`.
   - Hook contract for `sourced_sidecar` (`SCIENCE_VALIDATE_HOOKS`, `register_validation_hook`, source-during-init timing).
   - Declarative migration shape (Python-default; bash-with-constraints).
   - Transaction-safe rollback (`temp_commit` / `manifest`).
   - Dirty-worktree rules with orthogonal `--allow-dirty` / `--no-commit` semantics.
   - Replacement of `meta/validate.sh` and `scripts/validate.sh` with path-convenience shims (NOT deletion; NOT installs).
   - The `pin` / `unpin` / `exec` verbs.
   - The install matrix for the existing-file cases.
3. **Plan #7** (`docs/plans/2026-04-25-mav-audit-addendum.md`) — its six audit-surfaced validator fixes become the **first version bump** under this system: `2026.04.25` → `<implementation date>`. The bump's migration entry is `kind: byte_replace` for most fixes; one or two of the six (id-prefix-table introduction; pre-registration row activation) may carry `project_action` migration steps that warn projects about new prefix-conformance warnings.
4. **Implementation of this design** unblocks: per-project `science-tool project artifacts update validate.sh` (migration plan Task 4); plan-#7 bump landing.
5. **`[t009]`** is downstream of this; consumes the same migration-step shape for entity rename and declarative entity migrations.

## Resolved during design

The 2026-04-26 review passes settled the following in the body above; left here as a quick index so the implementation plan doesn't re-litigate:

- **Header strategy** → per-artifact `header_protocol` field with kinds `shebang_comment` / `comment` / `sidecar_metadata` / `none_with_registry_hash_only`. Shell scripts use `shebang_comment` with header inserted *after* the shebang line.
- **Canonical-bytes ownership** → the package's `data/<artifact>` file IS the fully-rendered managed artifact (header included). Install is byte-copy + chmod. Drift detection re-parses the header from any installed file. No install-time header rewrite.
- **`meta/validate.sh` and `scripts/validate.sh`** → become byte-identical, repo-position-relative shims that exec the canonical via `uv run --project ../science-tool science-tool project artifacts exec validate.sh`. NOT managed installs. NOT canonicals. Path conveniences only.
- **`exec` is a first-class CLI verb** → `science-tool project artifacts exec <name> -- <args...>` resolves the canonical bytes path and execs it. Used by the path-convenience shims and available for any direct-invocation use.
- **Sidecar semantics for native consumers** → consumer taxonomy (`direct_execute` / `science_loader` / `native_tool`); v1 ships only `direct_execute + sourced_sidecar`; other combinations defined in the registry schema but not delivered until a real artifact requires them.
- **`sourced_sidecar` execution timing** → sidecar is sourced during canonical init (BEFORE validation runs); canonical defines named hook points and a `register_validation_hook` primitive; sidecar registers callbacks.
- **Migration step DSL** → Python module reference is the default; bash is allowed only with declared `working_dir` + `timeout_seconds` + `touched_paths` and YAML block scalars (`|` / `>`) for `check`/`apply` (plain-flow rejected).
- **Migration rollback** → transaction snapshot per `mutation_policy.transaction_kind`: `temp_commit` (Git, default) or `manifest` (Git or outside Git). `stash` was considered and rejected because rollback semantics are unsafe under `--allow-dirty`. Snapshot covers BOTH artifact bytes and migrated project files.
- **Pin/hash divergence** → pins store `pinned_hash` inline; `previous_hashes` is uncapped (full history retained).
- **Registry install metadata** → `mode`, `content_type`, `newline` are required fields; `consumer` is required; `mutation_policy` is required.
- **Worktree state vs commit emission** → `--allow-dirty` and `--no-commit` are independent flags. `--allow-dirty` permits dirty worktree only if no touched path intersects with dirty paths. `--no-commit` skips commit emission and has no effect on the worktree-state check.
- **Install behavior for existing files** → explicit install matrix in Data flow distinguishes seven combinations of (managed-header present?) and (installed hash recognized?). `--adopt` rewrites the header in place when bytes match a known historical version; `--force-adopt` byte-replaces with canonical and writes `.pre-install.bak`.

## Open questions (decide during plan-writing or implementation)

These remain truly open and need a call during planning or implementation:

- **Initial managed-artifact membership beyond `validate.sh`.** v1 ships `validate.sh` alone (per the v1-scope note in "Extension protocols"). When the second artifact is introduced, what is it? A managed `.editorconfig` (would force `consumer: native_tool` + `generated_effective_file` to be delivered, exercising that path). A managed shell snippet for a common script preamble (stays in `direct_execute`, low risk, but limited new value). Recommendation lean: don't pre-decide; introduce v1.1's second artifact when a real need surfaces, and let that need drive which consumer/protocol path becomes load-bearing first.
- **Registry loader location.** Parse YAML at runtime (recommended; small file, easy to evolve, error messages cite the YAML directly) versus pre-bake at package build time. Likely just parse at runtime.
- **`science-tool sync` integration shape.** `sync` already does several things; how to surface stale-artifact warnings without crowding existing output. Detail call during plan-writing.

## Acceptance criteria

A reasonable implementation of this design satisfies all of:

1. **Single canonical bytes file.** Exactly one physical bytes file per managed artifact, inside the `science-tool` package. `meta/validate.sh` and `scripts/validate.sh` are one-line `exec` shims, byte-identical to the spec'd shim string. No other `validate.sh` in the upstream tree.
2. **Registry strict-validates.** A test loads `registry.yaml` against the schema and asserts: required fields present, consumer/extension/header-protocol combinations are valid, all hashes are well-formed SHA256, no `current_hash` appears in `previous_hashes`.
3. **Per-artifact `current_hash` matches body bytes.** Test recomputes from the bytes file (per `header_protocol`) and asserts equality.
4. **CLI verbs land:** `science-tool project artifacts list | check | diff | install | update | pin | unpin | exec`. Each has `--help` text and at least one happy-path test. `install` covers every row of the install matrix.
5. **Status surfacing in all four:** `health`, `/status`, `/next-steps`, `science-tool sync`.
6. **Update is reversible.** Every update writes `.pre-update.bak`; commit is single, named, and revertable.
7. **Transaction safety on migration failure.** Deliberately-failing migration step test asserts: artifact and project files restored; no `.pre-update.bak`; no commit; non-zero exit.
8. **Dirty-worktree refusal works.** Default-refuse, `--no-commit`, `--allow-dirty` (with path-conflict check) all behave as specified.
9. **Hook contract works.** Synthetic `validate.local.sh` registers a hook; test asserts it ran at the expected hook point during canonical invocation.
10. **Header protocol works.** `shebang_comment` test asserts shebang remains byte 0; header lines immediately follow; body hash computed correctly over post-header bytes.
11. **Pin behaves correctly.** Pin captures hash inline; `pinned-but-locally-modified` classification surfaces when installed bytes diverge.
12. **Plan #7 ships as the first version bump.** Its six audit-surfaced fixes are batched under one version bump (`2026.04.25` → `<implementation date>`) with appropriate migration entries (most `byte_replace`; any `project_action` steps explicit).
13. **Path-convenience shims correct.** Both `meta/validate.sh` and `scripts/validate.sh` test as byte-equal to the spec'd shim string.

## What this displaces

- **The MAV plan as currently written** (`docs/plans/2026-04-25-managed-artifact-versioning.md`) — its core direction (managed header, package-bundled canonical, drift-check, diff, update CLI) is preserved. Its hardcoded per-artifact dataclass approach is replaced by a YAML registry with the capabilities matrix. Its silence on sidecar protocols, header-protocol per-artifact variation, declarative migrations, hook contracts, transaction safety, dirty-worktree rules, and `pin` is all filled in. Its assumption that `meta/validate.sh` and `scripts/validate.sh` stay alive as full bodies is replaced with one-line shims.
- **Plan #7** (`docs/plans/2026-04-25-mav-audit-addendum.md`) — folds in as the first version bump. Its bookkeeping (single version bump, `previous_hashes` append) is exactly what this system formalizes; its six fixes become the bump's `byte_replace` migration (with any project-action steps surfaced explicitly).
- **The cross-plan "validators in lockstep" rule** — becomes obsolete because there is only one validate.sh body file.
- **The hand-rolled `meta/validate.sh` ↔ `scripts/validate.sh` 9-line drift** — resolves by replacing both files with shims that always reach current canonical.

---

## References

- `docs/plans/2026-04-25-managed-artifact-versioning.md` — MAV plan (to be redirected per Sequencing § above).
- `docs/plans/2026-04-25-mav-audit-addendum.md` — Plan #7 (folds in as first version bump).
- `docs/plans/2026-04-25-rollout-and-migration-handoff.md` — current state of the conventions audit + downstream migration cycle.
- `docs/plans/2026-04-25-conventions-audit-p1-rollout.md` — master rollout plan; cross-plan rules section.
- `docs/audits/downstream-project-conventions/synthesis.md` § 3.3 — synthesis-rollup convention evidence.
- `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` — Q5 long-term direction.
- `scripts/migrate_downstream_conventions.py` (commit `fe8d974`) — Phase 2 shape-driven migration rules; prior art for declarative migration step shape.
- `meta/tasks/active.md` `[t009]` — entity-rename / declarative-migrations primitive; downstream of this design.
