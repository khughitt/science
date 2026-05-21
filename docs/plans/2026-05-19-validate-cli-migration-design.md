# Validate as a CLI Verb — Migration Design

**Date:** 2026-05-19
**Status:** Draft. Not yet approved.
**Scope:** B (managed-artifact class) ∪ A (CLI verbs). Migrates `validate.sh` from a versioned managed-artifact + sidecar-extension shape to a `science validate` CLI subcommand + Python plugin extension. Composes with — and partially supersedes — the `validate.sh` entry in `project_artifacts/registry.yaml`.
**Composes with (does not deliver):** `2026-04-26-managed-artifacts-long-term-design.md` (managed-artifact spec) and `2026-04-27-validate-hook-points.md` (the hook system this migration carries forward into Python).
**Supersedes / redirects:** Eventually retires the `sourced_sidecar` extension protocol for `validate.sh`. The protocol itself stays — other artifacts may still use it.

---

## Summary

`validate.sh` started language-agnostic because Science could not assume a Python interpreter, much less the Science CLI, in downstream projects. That assumption has flipped: every Science project now installs the CLI (`uv run science …`). Meanwhile, the canonical body has grown a Python interpreter call in almost every section (graph audit, prose lint, annotation drift, task validation, frontmatter cross-references, …), and project-local sidecars increasingly embed Python heredocs inside bash hook bodies. The bash framing is no longer pulling its weight; it is in the way.

Migrate the canonical to a `science validate` CLI subcommand whose canonical checks live in Python and whose project-local extensions register as Python plugins. Replace `validate.local.sh` with `validate_local.py`. Keep a thin one-line shim at `validate.sh` so `bash validate.sh` keeps working through a deprecation window. Phase across three minor versions so existing downstreams (`health/meta`, `cancer/mechanisms/evolution`, the four Bucket-A reference projects, and any others holding hook sidecars) port at their own pace.

## Mental model

The hook system that landed `2026-04-27-validate-hook-points.md` already split the validator into "canonical body" + "project-local sidecar." The migration completes that separation by changing the substrate from bash-with-embedded-python to Python-with-importable-plugins. The contract — three named hook points (`pre_validation`, `extra_checks`, `post_validation`), shared `error`/`warn`/`info` helpers folded into pass/fail counts, registration-order dispatch — stays. Only the binding changes.

Concretely: the user's own `health/meta/validate.local.sh` (just shipped 2026-05-19) is fourteen lines of bash wrapping a ninety-line Python heredoc that uses `WARN:` / `INFO:` prefixes to smuggle structured output back across the shell boundary. That file is the migration's worked example, and its shape is the strongest evidence that the bash framing has become a cost center.

## Problem

The current shape pays for an assumption that no longer holds:

1. **The canonical body is mostly a Python-launcher.** Sections 6 (notes), 16 (knowledge graph), 17 (task queue), 18 (frontmatter cross-refs), 19 (prose lints), 20 (annotation drift), plus several earlier sections, all call out to `python3 -c '…'` or `$SCIENCE_TOOL …` with a few lines of bash glue. The non-Python sections are mostly file-existence checks and grep — trivially expressible in Python.
2. **Sidecars are double-translated.** A project-local check that needs YAML parsing, regex over multiple files, or any non-trivial data wrangling becomes a bash function that wraps a Python heredoc that emits stringly-typed lines that bash dispatches to `warn`/`info`. The boundary forces every signal across a `case "$line" in WARN:*)` switch. That is a code smell, not an architecture.
3. **Managed-artifact versioning for a check runner is heavy.** The hash-pinned `validate.sh` + the `previous_hashes` ledger + `byte_replace`/`project_action` migrations exist to keep canonical bash bytes synchronised across N downstream copies. A Python CLI version *is* the canonical bytes; bumps propagate via `uv add` / `uv sync`, which is the package manager's job. Drift detection becomes "what version of `science` is installed."
4. **Cross-platform / shell variance.** The canonical relies on Bash 4+ associative arrays (`declare -A`), `<<<` here-strings, GNU-flavoured `find`/`sed`. A Python implementation has no such hidden coupling.
5. **Testing.** Today there is a sidecar idiom — write a synthetic project, run `bash validate.sh`, scrape output — that is fragile (stdout ordering, ANSI codes, locale). Python checks become unit-testable functions returning structured results, with the CLI layer responsible only for formatting.

## Proposal

### Three layers

```
┌────────────────────────────────────────────────────────────────────┐
│ science_tool.validate.cli       — Click group attached to the      │
│                                   existing science_tool.cli:main;  │
│                                   formatting, exit codes           │
├────────────────────────────────────────────────────────────────────┤
│ science_tool.validate.runner    — collect checks, dispatch hooks,  │
│                                   accumulate Results               │
├────────────────────────────────────────────────────────────────────┤
│ science_tool.validate.checks.*  — canonical checks (one module per │
│                                   current section)                 │
└────────────────────────────────────────────────────────────────────┘
```

The CLI surface integrates as a Click command under the existing `science` script (`science_tool.cli:main` in `pyproject.toml` `[project.scripts]`); the new `science validate` verb is a `@click.command` registered with the root Click group alongside the existing `science tasks`, `science annotate`, etc. Project-local extension binds at the runner layer through a discovered `validate_local.py` (see *Extension protocol* below).

### Canonical check shape

Each current section becomes a function in `science/src/science_tool/validate/checks/<name>.py`. The runner iterates a declared order:

```python
# science/src/science_tool/validate/checks/hypotheses.py
from collections.abc import Iterable

from science_tool.validate import Check, Result, Severity, ValidateContext

@Check(section="hypotheses", order=8)
def check_hypothesis_frontmatter(ctx: ValidateContext) -> Iterable[Result]:
    for path in ctx.specs_dir.glob("hypotheses/*.md"):
        fm = ctx.frontmatter(path)
        if "id" not in fm:
            yield Result(Severity.ERROR, path, "missing id field")
        ...
```

`ValidateContext` carries the canonical state today scattered across globals in `validate.sh`: `PROFILE`, `DOC_DIR`, `SPECS_DIR`, `STRICT`, resolved `science` tool path, parsed manifest, etc. It also exposes helpers (`frontmatter()`, `read_yaml()`, `read_text_cached()`) so a check author never re-parses what's already cached for the run.

`Result` carries severity, source location (path + optional line), message, and an optional `rule` / `task` attribution (the structured form of the `(rule: reviews-are-not-evidence, t024)` suffix the user's sidecar currently appends to strings). Formatting belongs to the CLI layer.

### Hook taxonomy (carried over from `2026-04-27-validate-hook-points.md`)

The three named hook points stay. They become Python decorators:

```python
# validate_local.py
from collections.abc import Iterable

from science_tool.validate import Result, Severity, hook

@hook("extra_checks")
def check_reviews_are_not_evidence(ctx) -> Iterable[Result]:
    bg = {p.stem for p in ctx.papers_dir.glob("*.md")
          if ctx.frontmatter(p).get("status") == "background"}
    for yaml_path in ctx.provenance_dir.glob("*.yaml"):
        record = ctx.read_yaml(yaml_path)
        source = record.get("source_ref", "")
        if not source.startswith("paper:"):
            continue
        if source[len("paper:"):] not in bg:
            continue
        if record.get("review_typed_source") is not True:
            yield Result(
                Severity.WARN, yaml_path,
                f"source_ref={source} (status:background) but review_typed_source={record.get('review_typed_source')!r}",
                rule="reviews-are-not-evidence", task="t024",
            )
        ...
```

Same semantics as the bash hook protocol: registration order, mutable counters via the `Result` stream, structured attribution. What changes is the substrate.

### Extension protocol: `validate_local.py`

Discovery: the runner imports `validate_local.py` from the project root (if present) via `importlib` with a synthetic module name. No `sys.path` mutation; the file's directory is added only for the duration of the import. The file is permitted to declare hooks via the `@hook(...)` decorator and to define module-level helpers. It MUST NOT mutate global state in `science`.

Registration is namespaced per import so two projects in a federation root don't collide (compare to today's `SCIENCE_VALIDATE_HOOKS` associative array which is shared shell state).

For projects that want richer plugin layouts (multiple files, shared helpers), `validate_local/` as a package directory is a v2 affordance — not in v1.

### What happens to `validate.sh` and `validate.local.sh`

`validate.sh` becomes a five-line shim, installed by `science project artifacts install validate.sh`:

```bash
#!/usr/bin/env bash
# science-managed-artifact: validate.sh
# science-managed-version: 2026.06.01.1
# science-managed-source-sha256: <64-hex sha256 of the body lines after the header>
exec uv run science validate "$@"
```

The three header keys (`artifact`, `version`, `source-sha256`) and version-format constraint (`YYYY.MM.DD[.N]`) are required by `science_tool.project_artifacts.header.parse_header` — see `header.py:48–55`. The shim ships with the real sha256 of its body and a normal date-based version; the `.shim` suffix illustration from earlier drafts of this plan was invalid and is dropped. Future shim updates bump the suffix (`2026.06.01.2`, …).

The shim is still a managed artifact (so `science project artifacts update` keeps it in sync), but it has no body to maintain — it is a one-byte-equivalent stub. The current ~1500-line canonical body lives only in `science/src/science_tool/validate/`. Downstream projects do not carry a 1500-line bash file at all once they update.

`validate.local.sh` is read on a deprecation path through a **packaged legacy runner**, not by re-invoking the shim. The Python canonical does not recursively call `bash validate.sh`; instead the `science_tool.validate` package ships a frozen copy of the last "real" bash canonical (the version present before the shim landed) as a package data resource — concretely `science_tool/validate/_legacy/validate_legacy.sh` plus the matching `_legacy/run_legacy_sidecar.py` driver. When `science validate` detects a `validate.local.sh` and decides to honour it (see precedence rule below), it:

1. Resolves the absolute path to the packaged `validate_legacy.sh` via `importlib.resources` (or a `pathlib` materialisation step if `importlib.resources` cannot expose a filesystem path under the chosen install layout).
2. Spawns `bash <absolute-path-to-validate_legacy.sh>` as a subprocess with **`cwd` set to the project root** — the same project root the Python canonical was invoked against. The sidecar's project-relative paths (`doc/papers`, `doc/provenance`, `specs/hypotheses`, project-local scripts) resolve correctly because cwd is unchanged from the user's invocation. The legacy bash file is referenced by absolute path; nothing is copied into a tempdir.
3. Passes `SCIENCE_LEGACY_SIDECAR_ONLY=1` and `SCIENCE_VALIDATE_NO_COLOR=1` in the subprocess environment. The first short-circuits the legacy canonical past its built-in sections and runs only the `dispatch_hook` calls; the second disables ANSI colour wrapping in the canonical's `red`/`yellow`/`green`/`info` helpers. Both behaviours require a one-time modification to the legacy canonical (a guard near the section dispatcher; an `if [ -n "${SCIENCE_VALIDATE_NO_COLOR:-}" ]; then` branch in each colour helper that emits the plain `"%s\n"` form). Today's helpers always emit `\033[3Xm…\033[0m` (canonical `validate.sh:92–94`), so without `NO_COLOR` the prefix-match parser below would never fire.
4. Parses the legacy bash's stdout line-by-line. The parser strips ANSI escape sequences (`\x1b\[[0-9;]*m`) defensively in case a sidecar emits its own colour-wrapped output, then matches lines beginning with `WARN:` / `ERROR:` and folds them into `Result` objects alongside the Python checks. Lines that don't match are forwarded to the run log at INFO severity (mirroring today's behaviour where the bash canonical's banner echos pass through verbatim).

The legacy bash is pinned (version + sha256) inside the package; it never updates. It is removed entirely at Phase 3. The deprecation warning includes a one-line port hint pointing at the porting guide. Crucially the legacy runner is independent of the project's installed `validate.sh` shim — the shim's `exec uv run science validate "$@"` body and the shim's `--verbose`/`--strict`-only flag contract (today's `validate.sh` rejects unknown flags at lines 76–88 of the canonical) are never on the legacy code path.

**Precedence between sidecar files.** If `validate_local.py` exists, it is the source of truth: hooks register from it and `validate.local.sh` is ignored except for a single deprecation WARN per run pointing the user at the porting guide and noting the bash file is stale. If only `validate.local.sh` exists, the legacy runner above handles it (plus a single deprecation WARN). If neither exists, no warning. This is the explicit precedence (Python wins, bash silenced) that the Phase 2 acceptance criteria below test.

After two minor `science` releases, `validate.local.sh` support is removed. The deprecation window is generous because there are at most a handful of downstream sidecars today and the port is mostly mechanical.

### Output, exit codes, severity

Severity model is unchanged: ERROR / WARN / INFO, with `--strict` promoting select WARNs (mirrors today's `strict_warn` helper). Exit code: 0 if no ERRORs, nonzero otherwise; WARNs alone never fail validation (same as today).

Output: by default the CLI matches the current bash output shape (colour ANSI, banner, summary). A `--format json` flag is added so CI / harness consumers get structured output cheaply — this is a free win the bash version cannot realistically offer.

### Versioning

Once migrated, the validate version IS the `science` package version. The registry entry for `validate.sh` simplifies to a shim with a single migration step: `byte_replace` from the last "real" canonical version to the shim. The `previous_hashes` ledger up to that bump is preserved; entries after the shim land are effectively empty (the shim does not change again).

A *future* hash-pinning of `validate_local.py` files is out of scope here; they are project-owned, not Science-managed.

### Parity gate

The "Python implementation matches the bash implementation" claim is decomposed into three independent gates so they can fail (and be reviewed) separately:

- **Semantic parity, canonical body only (CI-gating, Phase 1):** for each fixture project run *with no project-local sidecar present*, both implementations produce the same sorted multiset of `(severity, path, line_or_none, rule_id)` tuples. `rule_id` is the structured form of today's stringly-appended `(rule: …, t…)` suffix; messages and ANSI escapes are *not* compared. This is what Phase 1 ships and CI gates on.
- **Semantic parity, with sidecar (CI-gating, Phase 2 only):** once the packaged legacy runner exists, the same multiset comparison runs on fixture projects *that include* a `validate.local.sh`. The Python side dispatches the legacy bash sidecar through the legacy runner; the bash side is today's `bash validate.sh` sourcing the same sidecar directly. Comparing both implementations with sidecars present is not possible in Phase 1 because the legacy runner doesn't ship until Phase 2 — Phase 1's parity gate explicitly excludes sidecar effects, and Phase 1's per-real-project acceptance criteria temporarily move any existing `validate.local.sh` aside during parity testing.
- **Formatter snapshot (reviewer-gating, both phases):** on one canonical fixture project, the rendered coloured-banner output and the `--format json` output are snapshot-compared against committed expected outputs. Snapshot diffs surface in PR review but do not auto-fail CI; they exist so that intentional formatting changes (banner text, colour choices) get a human eye, not a green build.

This split avoids the brittleness of comparing two implementations character-for-character, keeps Phase 1's scope honest (the legacy runner is a Phase 2 deliverable), and still catches the cases that matter (a missing check, a wrong severity, a path off by a directory).

## Migration phasing

The migration spans three minor `science` versions. Each phase ships independently and is reversible up to the next phase.

### Phase 1 — Ship `science validate` reading the current canonical's behaviour (additive, no breakage)

- Add `science_tool.validate` package with `Check` / `Severity` / `Result` / `ValidateContext` plumbing.
- Wire `science_tool.validate.cli` as a Click subcommand on the existing root group in `science_tool/cli.py`.
- Port the canonical's 20 sections to Python check modules. Each ported section gets a **parity gate** defined as a sorted multiset of `(severity, path, line_or_none, rule_id)` tuples — semantic equivalence only, not textual. Formatter output is covered by separate snapshot tests against a small fixture project (see *Parity gate* note below).
- Ship the `@hook(...)` decorator and `validate_local.py` discovery, both gated behind `--experimental-python-sidecar` initially.
- `bash validate.sh` is untouched in this phase. Nobody is forced to migrate yet.

Acceptance:

1. `uv run science validate` exists. The canonical-body-only semantic parity multiset (sidecar-excluded gate above) matches `bash validate.sh` on all four Bucket-A reference projects plus `health/meta` and `cancer/mechanisms/evolution`. The parity comparison is run against an isolated copy of each project tree (rsync into a tempdir, with any `validate.local.sh` excluded from the copy), *not* against the live worktree, so test infrastructure never mutates a downstream working tree. An equivalent path for in-place runs is supported via `SCIENCE_VALIDATE_DISABLE_SIDECAR=1`, honoured by both implementations — the legacy canonical skips its `source validate.local.sh` step, and `science validate` skips both sidecar files — so a developer reproducing the parity gate locally can opt out of sidecar effects without touching files on disk. `science validate` with the sidecar in place is *not* tested against `bash validate.sh` in Phase 1; that comparison waits for Phase 2's legacy runner.
2. The canonical-body-only parity gate runs in CI for `science` itself across the synthetic project corpus described in *Parity-test corpus build-out*.
3. Formatter snapshot test covers the default coloured-banner output and the new `--format json` output on a single fixture project. Snapshot diffs are reviewer-gating, not CI-gating.
4. `--format json` exists and round-trips against a JSON-schema test.

### Phase 2 — Promote `validate_local.py`, deprecate `validate.local.sh`

- Drop the `--experimental-` gate on the Python sidecar protocol.
- Implement the precedence rule from *What happens to `validate.sh`*: `validate_local.py` always wins; `validate.local.sh` runs only when no `validate_local.py` is present; one deprecation WARN per run whenever any `validate.local.sh` is observed.
- Ship the packaged legacy runner (`science_tool/validate/_legacy/`) and the `SCIENCE_LEGACY_SIDECAR_ONLY=1` short-circuit it relies on.
- Extend `science_tool.project_artifacts.registry_schema`:
  - Add `ExtensionKind.PYTHON_SIDECAR = "python_sidecar"`.
  - Extend the `_consumer_extension_pairing` validator so `Consumer.DIRECT_EXECUTE` accepts `{SOURCED_SIDECAR, PYTHON_SIDECAR, NONE}`.
  - Unit-test the new enum value and the new pairing (round-trip + the existing duplicate-hash / hash-format guards still pass).
- Ship a porting guide and a `science project artifacts port-validate-sidecar` helper that converts a bash sidecar into a `validate_local.py` skeleton (best-effort; the user must port the body).
- Ship the shim `validate.sh` as a new artifact version. `science project artifacts update validate.sh` migrates from the canonical body to the shim. The migration is `project_action` because removing ~1500 lines of `validate.sh` is a visible diff projects will want to inspect.

Acceptance:

1. All Science-tracked downstream projects have been migrated to either `validate_local.py` or have no sidecar (whichever applies).
2. The shim is the registry's current `validate.sh` version, with `extension_protocol.kind = python_sidecar` and `sidecar_path = validate_local.py`.
3. With `validate_local.py` only present: zero deprecation WARNs; Python sidecar runs.
4. With `validate.local.sh` only present: one deprecation WARN; legacy runner executes the bash sidecar via the packaged frozen canonical (no recursion through the shim).
5. With both files present: one deprecation WARN; `validate_local.py` runs; `validate.local.sh` is *not* executed.
6. Existing managed-artifact tests for `validate.sh` continue to pass under the new shim contents.
7. The Phase-2 sidecar-included semantic parity gate (from the *Parity gate* section) is green on the real-project corpus (`health/meta`, `cancer/mechanisms/evolution`, …) with their `validate.local.sh` files in place — comparing `bash validate.sh` (today's behaviour) against `science validate` routing the sidecar through the legacy runner.

### Phase 3 — Remove `validate.local.sh` support

- `science validate` checks for the existence of `validate.local.sh` and, if found, emits a hard ERROR pointing at the porting guide. The file is never sourced or executed — only its presence is detected.
- The legacy bash dispatch path (`science_tool/validate/_legacy/`) is deleted from the package along with the packaged legacy canonical, the `SCIENCE_LEGACY_SIDECAR_ONLY` and `SCIENCE_VALIDATE_NO_COLOR` env-var contracts that propped it up, and the WARN/ERROR-line parser.
- The `validate.sh` shim stays; it is still the recommended entry-point for users who type `bash validate.sh` from muscle memory and for harnesses that call it.

Acceptance:

1. No code path in `science_tool` *sources or executes* `validate.local.sh`; only an existence check remains, behind the ERROR-emission branch. The `_legacy/` package directory is gone.
2. The registry's `extension_protocol.kind` for `validate.sh` remains `python_sidecar`.
3. `ExtensionKind.SOURCED_SIDECAR` is *not* removed from the schema — other artifacts may still use it — only the `validate.sh` entry no longer references it.

## Cross-project impact

| Downstream | Has `validate.local.sh`? | Phase-2 port effort |
|---|---|---|
| `health/meta` | Yes (just shipped 2026-05-19) — `check_reviews_are_not_evidence_guardrail`, both Check A (provenance YAMLs) and Check B (evidence_refs blocks) | Low — the bash is already a Python heredoc; the port is mostly removing the bash shell |
| `cancer/mechanisms/evolution` | Yes (mirror of above; Check B only) | Low — same shape |
| `pan-disease` | TBC | Audit before Phase 2 |
| Bucket-A reference projects (`mm30`, `cbioportal`, `natural-systems`, `protein-landscape`) | Audit; some had hook plans per `2026-04-27-validate-hook-points-implementation.md` | Audit per-project |

The total population of `validate.local.sh` files is small (single digits, possibly under five) so a per-project escort during Phase 2 is feasible.

## Open questions

- **`pyproject.toml` entry-points vs file-based discovery.** The proposal uses file-based discovery (`validate_local.py` in project root) because most science projects are not installable Python packages. Should we *also* expose an entry-point hook so projects that *are* packages can ship checks via their package metadata? Leaning yes (additive, no cost if unused), but defer to Phase 2.
- **Context resolution under federation roots.** When a federation root contains multiple Science projects (today's `~/d/health/` family with `meta` + `pan-disease` + future children), should `science validate` accept a `--all` flag that walks the family? Or stay strictly single-project? Probably single-project in v1; federation-walk is a separate verb.
- **Parity-test corpus build-out.** The semantic parity gate above is only as strong as its fixtures. Today's `tests/managed_artifacts/test_validate*.py` synthetic projects are the natural starting point but need extension to cover every section's WARN/ERROR triggers and every `rule_id` the bash canonical attaches. Estimated: ~1 week of test-corpus build-out, partially recoverable later as the canonical evolves.
- **Should the shim survive Phase 3?** Argument for keeping: muscle memory, harnesses that call `bash validate.sh`. Argument against: `uv run science validate` is two words shorter and matches every other `science` verb. Keep the shim for at least two minor versions after Phase 3 and re-evaluate.
- **`science health` integration.** `science health` currently invokes `bash validate.sh` under the hood for some checks. That call site converts to a direct Python import once `science_tool.validate` exists — no subprocess needed. Trivial follow-up, but worth noting.
- **CLI binary name drift.** Some downstreams invoke `uv run science …` (newer), others `uv run science-tool …` (older). The `science validate` verb should be available under both names during the deprecation window for the binary itself, which is orthogonal to this plan but worth a one-line check.

## Cross-references

- Builds on / preserves the hook contract from `docs/plans/2026-04-27-validate-hook-points.md`.
- Composes with `docs/plans/2026-04-26-managed-artifacts-long-term-design.md` — the managed-artifact framework continues to govern the shim `validate.sh`, and the `extension_protocol` field grows a new value for the Python sidecar.
- Worked example for the porting guide: `~/d/health/meta/validate.local.sh` (current shape) → `validate_local.py` (target shape). The current file is ~145 lines including a 90-line embedded Python heredoc; the port estimate is 60-80 lines of clean Python.
- Sibling shape: `~/d/cancer/mechanisms/evolution/validate.local.sh` (Check B only; same migration).
- Successor implementation plan: TBD — write after design approval.
