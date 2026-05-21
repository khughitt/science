# Validate as a CLI Verb — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realize the migration described in `docs/plans/2026-05-19-validate-cli-migration-design.md` across three minor `science` releases. Phase 1 ships `science validate` at canonical-body parity with `bash validate.sh` (no sidecar yet, additive); Phase 2 ships the Python sidecar protocol + packaged legacy bash-sidecar runner + registry-schema extension + shim `validate.sh`; Phase 3 removes legacy bash-sidecar support entirely.

**Tech stack:** Python 3.11+ for the CLI, runner, checks, and parser. Click for CLI surface (matching the existing `science_tool.cli:main` group). pytest for tests. YAML for the registry. Bash (frozen) for the packaged legacy runner only. `uv` for everything Python.

---

## File Structure

### Create

- `science/src/science_tool/validate/__init__.py` — public surface: `Check`, `Result`, `Severity`, `ValidateContext`, `hook` decorator.
- `science/src/science_tool/validate/runner.py` — collect canonical checks, discover `validate_local.py`, dispatch hooks, accumulate `Result`s, compute pass/fail.
- `science/src/science_tool/validate/cli.py` — Click command `validate` registered onto `science_tool.cli.main`. Owns formatting, severity counting, `--verbose` / `--strict` / `--format` flags, exit codes.
- `science/src/science_tool/validate/context.py` — `ValidateContext` dataclass; cached file readers (`frontmatter`, `read_yaml`, `read_text_cached`); project-root + manifest resolution.
- `science/src/science_tool/validate/result.py` — `Severity` enum, `Result` dataclass (severity, path, line, message, rule, task), JSON serialisation.
- `science/src/science_tool/validate/checks/__init__.py` — registry of canonical `@Check` modules, ordered.
- `science/src/science_tool/validate/checks/*.py` — one module per current bash section (~20 modules).
- `science/src/science_tool/validate/_legacy/__init__.py` — packaged legacy runner namespace (Phase 2 only).
- `science/src/science_tool/validate/_legacy/validate_legacy.sh` — frozen copy of the last "real" bash canonical, with `SCIENCE_LEGACY_SIDECAR_ONLY=1` and `SCIENCE_VALIDATE_NO_COLOR=1` guards added (Phase 2 only).
- `science/src/science_tool/validate/_legacy/runner.py` — subprocess driver that resolves the packaged script via `importlib.resources`, sets env vars, parses stdout into `Result`s (Phase 2 only).
- `science/src/science_tool/validate/legacy_parser.py` — ANSI-stripping `WARN:` / `ERROR:` line parser (Phase 2 only).
- `science/tests/validate/` — new test directory for parity gate, fixtures, snapshots.
- `science/tests/validate/test_parity_canonical_body.py` — Phase 1 semantic-parity multiset gate (sidecar-excluded).
- `science/tests/validate/test_parity_with_sidecar.py` — Phase 2 sidecar-included parity gate.
- `science/tests/validate/test_legacy_parser.py` — ANSI-stripping + line-prefix parser unit tests (Phase 2).
- `science/tests/validate/test_schema_python_sidecar.py` — registry-schema enum + pairing tests (Phase 2).
- `science/tests/validate/test_phase3_legacy_removed.py` — Phase 3 only: legacy directory absent, hard ERROR fires.
- `science/tests/validate/fixtures/` — synthetic project trees, one per check section, with WARN/ERROR triggers.
- `science/tests/validate/snapshots/` — committed expected outputs for formatter snapshot tests.
- `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` — user-facing porting guide (Phase 2).

### Modify

- `science/src/science_tool/cli.py` — register the new `validate` command group on the root Click group.
- `science/src/science_tool/project_artifacts/registry_schema.py` — add `ExtensionKind.PYTHON_SIDECAR`; extend `_consumer_extension_pairing` so `Consumer.DIRECT_EXECUTE` accepts `{SOURCED_SIDECAR, PYTHON_SIDECAR, NONE}` (Phase 2).
- `science/src/science_tool/project_artifacts/registry.yaml` — bump `validate.sh` to the shim (Phase 2); update `extension_protocol.kind` to `python_sidecar`; recompute `current_hash`; move old hash into `previous_hashes`; append `migrations` entry of kind `project_action`; update changelog (Phase 2).
- `science/src/science_tool/project_artifacts/data/validate.sh` — replace canonical body with the five-line shim (Phase 2).
- `science/src/science_tool/health/` (or wherever `science health` lives) — call `science_tool.validate.runner.run(...)` directly instead of `subprocess` to `bash validate.sh` (Phase 2).

### Tests already in place that must continue passing

- `science/tests/test_initial_validate_sh.py` — header + body integrity. Will need a Phase-2 update to expect the shim body.
- `science/tests/test_first_version_bump.py` — registry shape. Phase-2 update for the new version + extension_protocol.kind.
- `science/tests/test_extensions_validate_hooks.py` — hook-infrastructure tests for the bash canonical. Still gate Phase 1 + Phase 2 (the packaged legacy bash retains the hook infra).
- `science/tests/test_acceptance_managed_artifacts.py` — full lifecycle + shim equivalence. Phase 2 needs new assertions for the shim's contents.

---

## Phase organization

| Phase | Theme | Tasks | Output |
|------:|---|---|---|
| **P1.A** | Package scaffold + Click integration | T1, T2 | `science validate --help` works; empty runner; `Result` + `Severity` types stable |
| **P1.B** | Canonical check port | T3, T4 | All ~20 bash sections re-expressed as `@Check`-decorated Python; runner dispatches them in order |
| **P1.C** | Parity gate + JSON output | T5, T6, T7 | CI gate green; snapshot tests committed; `--format json` schema-stable |
| **P1.D** | Experimental Python sidecar | T8, T9 | `validate_local.py` discoverable behind `--experimental-python-sidecar`; doc published |
| **P2.A** | Registry-schema extension | T10 | `ExtensionKind.PYTHON_SIDECAR` + pairing validation |
| **P2.B** | Packaged legacy runner | T11, T11.5, T12, T13 | `_legacy/` package; bash frozen + guarded; ANSI parser; precedence rule; wheel force-includes |
| **P2.C** | Sidecar-included parity + opt-out env var | T14, T15 | `SCIENCE_VALIDATE_DISABLE_SIDECAR=1` honoured both sides; Phase-2 parity gate green |
| **P2.D** | Shim deployment + downstream port | T16, T17, T18, T19 | Shim `validate.sh` released; `health/meta` and `cancer/mechanisms/evolution` ported; `science health` skips subprocess |
| **P2.E** | Porting guide | T20 | `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` published |
| **P3.A** | Legacy removal | T21, T22 | `_legacy/` deleted; hard-ERROR existence check stays |
| **P3.B** | Schema + release notes | T23, T24 | Schema unchanged (other artifacts retain `SOURCED_SIDECAR`); release notes finalised |

Phases run sequentially across three minor releases. Tasks within a phase may run in parallel where their files don't collide.

---

## Phase 1 — Ship `science validate` at canonical-body parity

### Task 1: Scaffold the `science_tool.validate` package

**Files:**
- Create: `science/src/science_tool/validate/__init__.py`
- Create: `science/src/science_tool/validate/result.py`
- Create: `science/src/science_tool/validate/context.py`
- Create: `science/src/science_tool/validate/runner.py`
- Create: `science/src/science_tool/validate/checks/__init__.py`

- [ ] **Step 1: Define `Severity` and `Result`.**
  - `Severity` is `(str, Enum)` with `ERROR`, `WARN`, `INFO`.
  - `Result` is a frozen dataclass: `severity: Severity`, `path: Path | None`, `line: int | None`, `message: str`, `rule: str | None`, `task: str | None`.
  - Add `Result.to_dict()` returning the JSON-serialisable form. Add `Severity.from_str(name)` for parser reuse.
  - Add unit tests asserting frozen-ness, equality semantics, and JSON round-trip.

- [ ] **Step 2: Define `ValidateContext`.**
  - Fields: `project_root: Path`, `doc_dir: Path`, `specs_dir: Path`, `papers_dir: Path`, `provenance_dir: Path | None`, `themes_dir: Path | None`, `manifest: dict`, `strict: bool`, `verbose: bool`.
  - Helpers (cached): `frontmatter(path)`, `read_yaml(path)`, `read_text_cached(path)`. Caches keyed by absolute path + mtime to survive multi-check reads.
  - Resolve `science.yaml` for the manifest; raise `ValidateContextError` with a clean message if absent.
  - Unit-test cache hits (read the same file twice; assert one disk read via a counting stub).

- [ ] **Step 3: Define `Check` decorator + registry.**
  - `@Check(section: str, order: int)` registers the wrapped callable in `checks/__init__.py::CANONICAL_CHECKS`, sorted by `order`.
  - The wrapped callable signature is `(ctx: ValidateContext) -> Iterable[Result]`. The decorator preserves the function for direct testing.
  - Unit-test: register two mock checks, dispatch via the registry, assert ordering.

- [ ] **Step 4: Define `hook` decorator + registry.**
  - `@hook(name: Literal["pre_validation", "extra_checks", "post_validation"])` appends the function to a per-name list in `runner._HOOKS`. Registration is order-preserving and idempotent on `(name, fn)` pairs (same as the bash contract).
  - Unit-test: register two hooks at `extra_checks`, dispatch, assert both fired in registration order.

- [ ] **Step 5: Implement `runner.run(project_root: Path, *, strict: bool, verbose: bool, enable_python_sidecar: bool = False) -> RunResult`.**
  - The signature parameterises sidecar discovery so Phase 1 callers can hold the flag off by default; Phase 2 Task 13 drops the experimental gate by changing the CLI default to `True` (the parameter itself stays for tests that need to force-disable sidecars).
  - Build `ValidateContext`.
  - **Discover and import the Python sidecar FIRST** (when `enable_python_sidecar=True`), before any hook dispatch, so any `@hook(...)` registrations in `validate_local.py` are visible to the subsequent `pre_validation` dispatch. This matches today's bash contract: `validate.sh` sources `validate.local.sh` at line 26–29 BEFORE the `pre_validation` dispatch at line 205.
  - The Phase-2 legacy bash sidecar runner has its OWN phase contract: it dispatches the bash hook points at the corresponding parent-run phases via two separate subprocess invocations (one for `pre_validation`, one for `extra_checks`); see Task 12 Step 1 below for the full ordering. The runner does not call `run_legacy_sidecar(...)` as a single blob during sidecar import — that would invert today's `extra_checks` ordering relative to canonical sections.
  - The full dispatch order is therefore: (1) build context, (2) import Python sidecar if enabled, (3) invoke legacy bash sidecar in `pre_validation`-phase mode if a `validate.local.sh` is in scope (Phase 2+), (4) dispatch Python `pre_validation` hooks, (5) iterate `CANONICAL_CHECKS` in order, (6) invoke legacy bash sidecar in `extra_checks`-phase mode if applicable, (7) dispatch Python `extra_checks` hooks, (8) tally counts and build `RunResult`, (9) dispatch `post_validation` hooks (Python only — the bash trap-dispatched `post_validation` fires inside each subprocess at the end of that subprocess) in a `try/finally`.
  - Tally severity counts; build `RunResult(results, errors, warnings, infos)`.
  - Always dispatch `post_validation` Python hooks via `try/finally` (regardless of internal exceptions in the canonical checks or extra_checks hooks).
  - Unit-test the run-pipeline with a single mock check + one mock hook per point + a mock `validate_local.py` registering a `pre_validation` hook; assert sidecar import precedes hook dispatch and that each hook fires exactly once.

### Task 2: Wire `science validate` Click command

**Files:**
- Create: `science/src/science_tool/validate/cli.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Implement `validate.cli.validate_cmd`** as a `@click.command(name="validate")` with flags `--verbose`, `--strict`, `--format [text|json]` (default `text`), `--project-root PATH` (default cwd).
- [ ] **Step 2: Register the command** by importing it in `science_tool.cli` and adding `main.add_command(validate.cli.validate_cmd)`. The root group is already `science_tool.cli:main` per `pyproject.toml [project.scripts] science = "science_tool.cli:main"`.
- [ ] **Step 3: Implement text formatting.** Match today's bash output shape: per-section "Checking …" banner header, coloured ERROR/WARN lines, terminal summary banner with green/yellow/red status. **Use the existing colour policy at `science_tool.styles`** (`ColorPolicy` enum + `set_color_policy` / `get_color_policy` + the Rich `Console` factory at `styles.py:91`+) rather than ad-hoc `click.style(...)` calls. The root `--color` flag and `NO_COLOR` / `FORCE_COLOR` env vars are already honoured by that module (`styles.py:96–103`); `science validate` inherits both for free if it routes its output through `get_color_policy(ctx)` + the shared `Console`. This keeps the new command's colour behaviour aligned with every other `science` subcommand instead of diverging.
- [ ] **Step 4: Implement `--format json`.** Emit `{"summary": {"errors": N, "warnings": N, "infos": N}, "results": [Result.to_dict(), ...]}`. Add a JSON-schema fixture at `science/tests/validate/fixtures/output.schema.json`; round-trip-test.
- [ ] **Step 5: Exit codes and `--strict` semantics.** `0` if `errors == 0`; non-zero otherwise; WARNs alone never fail validation (mirroring `validate.sh:1517–1525`: exit 1 only when `ERRORS > 0`, exit 0 with `PASSED with N warning(s)` when only WARNs are present). `--strict` does NOT promote WARNs to ERRORs — it matches the bash `strict_warn` helper at `validate.sh:109–113`, which is a guarded WARN: under `--strict`, advisory WARNs that are normally suppressed are emitted (still as WARNs, still counted into `WARNINGS`, still exit 0). The strict-promotability list is per-check, declared at `@Check(strict_promotable=True)` time; the runner emits those checks' WARNs only when `strict=True`. This preserves Phase-1 parity with `bash validate.sh --strict`.
- [ ] **Step 6: Smoke test.** `science validate --help` returns 0; `science validate --format json` on an empty project root returns valid JSON.

### Task 3: Port canonical checks from `data/validate.sh` to Python modules

**Files:**
- Create: `science/src/science_tool/validate/checks/<one-per-section>.py` (~20 modules).

Inventory of bash sections from `data/validate.sh` (current canonical):

| # | Bash header line in canonical | Target module |
|---:|---|---|
| 1 | `Checking tooling scaffold...` (line 212) | `tooling.py` |
| 2 | `Checking project manifest...` (line 246) | `manifest.py` |
| 3 | `Checking directory structure...` (line 310) | `directory_structure.py` |
| 4 | `Checking research scope...` (line 424) | `research_scope.py` |
| 5 | `Checking document structure...` (line 432) | `document_structure.py` |
| 6 | `Checking hypotheses...` (line 462) | `hypotheses.py` |
| 7 | `Checking reference integrity...` (line 516) | `references.py` |
| 8 | `Checking paper summaries...` (line 556) | `papers.py` |
| 9 | `Checking for unresolved markers...` (line 561) | `unresolved_markers.py` |
| 10 | `Checking research gap analysis...` (line 588) | `gap_analysis.py` |
| 11 | `Checking research plan conventions...` (line 623) | `research_plan.py` |
| 12 | `Checking discussion documents...` (line 643) | `discussions.py` |
| 13 | `Pre-registration documents` (line 681) | `prereg.py` |
| 14 | `Hypothesis comparison documents` (line 709) | `hypothesis_comparisons.py` |
| 15 | `Bias audit documents` (line 719) | `bias_audits.py` |
| 16 | `Checking notes...` (line 762) | `notes.py` |
| 17 | `Checking knowledge graph...` (line 834) | `graph.py` |
| 18 | `Checking task queue...` (line 981) | `tasks.py` |
| 19 | `Checking frontmatter cross-references...` (line 1204) | `cross_references.py` |
| 20 | `Checking prose quality lints...` (line 1433) | `prose_lints.py` |
| 21 | `Checking annotation drift...` (line 1462) | `annotations.py` |

(Numbers are approximate; the bash canonical numbers some sections as 18/19 etc. Use the bash header text as the authority for what each module ports.)

- [ ] **Step 1: Inventory each bash section.** For each row above, copy the bash block into a docstring at the top of the target module. This is the "ported-from" reference. Note any embedded `python3 -c` heredocs — they become direct Python within the module.
- [ ] **Step 2: Port section bodies in dependency order.**
  - Sections that don't depend on `SCIENCE_TOOL` calls first: tooling.py, manifest.py, directory_structure.py, document_structure.py, research_scope.py, research_plan.py, prereg.py, hypothesis_comparisons.py, bias_audits.py, discussions.py, papers.py, unresolved_markers.py, gap_analysis.py.
  - Sections that call `$SCIENCE_TOOL` next: hypotheses.py, references.py, notes.py, cross_references.py.
  - Sections that already are mostly Python heredocs: graph.py (knowledge graph), tasks.py (task queue YAML walk), prose_lints.py (`science prose lint --format json`), annotations.py (`science annotate verify --format json`).

  For `SCIENCE_TOOL` callouts, replace `$SCIENCE_TOOL <args>` with direct Python imports from the equivalent `science_tool.<subcommand>` module. Where the subcommand only exposes a CLI surface (no library function), refactor to expose a library function and have the CLI call into it — this avoids subprocess-from-Python.
- [ ] **Step 3: Strict mode.** Where the bash uses `strict_warn`, declare the check's WARN as strict-promotable at `@Check(strict_promotable=True)`. The runner consumes that metadata at counting time.
- [ ] **Step 4: Per-module unit tests.** For each ported module, add a fixture project under `science/tests/validate/fixtures/<module>/` that exercises both the passing and failing paths. Assert that the Python check produces the expected `Result` multiset.
- [ ] **Step 5: Integration check.** Run `science validate` on the science project itself (the science repo's own files); compare against `bash validate.sh` on the same checkout. Diffs surface real porting bugs before the parity gate codifies them.

### Task 4: Shared helpers for checks

**Files:**
- Create: `science/src/science_tool/validate/_helpers.py` (or extend `context.py`).

- [ ] **Step 1: Frontmatter helper.** Parse YAML frontmatter from a markdown file. Return `(frontmatter_dict, body_text)`. Used by the majority of checks.
- [ ] **Step 2: Reference resolver.** Given a related-ID like `paper:Foo2024`, `cite:Bar2023`, `task:t012`, return the resolved `Path` (or `None` if broken). Today's bash canonical does this in several places via grep; centralise it.
- [ ] **Step 3: Section-banner echo.** A helper that emits the per-section "Checking …" banner — keeps formatter logic centralised when the runner iterates checks.

### Task 5: Build the parity-test corpus

**Files:**
- Create: `science/tests/validate/fixtures/` (one subdir per section, plus a `_combined/` synthetic project that exercises multiple sections at once).

- [ ] **Step 1: Per-section fixtures** (covered by Task 3 Step 4).
- [ ] **Step 2: Combined fixture.** A small synthetic Science project (~30 files) that triggers at least one WARN and one ERROR across diverse sections. This is the primary parity-gate input.
- [ ] **Step 3: rsync helper.** A pytest helper `isolated_copy(project_path: Path) -> Path` that rsyncs a project tree into a tempdir, EXCLUDING `validate.local.sh` and `validate_local.py`, returns the tempdir path. Used by the canonical-body-only parity gate against real downstream projects (`health/meta`, `cancer/mechanisms/evolution`, …) without mutating their working trees.
- [ ] **Step 4: `SCIENCE_VALIDATE_DISABLE_SIDECAR=1` (Phase 1 partial).** Have `science validate` honour this env var by short-circuiting sidecar discovery. The bash canonical does not honour it yet (that's a Phase 2 modification on the packaged frozen canonical); Phase 1 simply doesn't need it for the bash side because Phase 1 parity runs against rsync'd copies with sidecars excluded.

### Task 6: Implement the canonical-body-only semantic parity gate

**Files:**
- Create: `science/tests/validate/test_parity_canonical_body.py`

- [ ] **Step 1: Build the multiset extractor.** Given a stdout string from `bash validate.sh`, parse only `WARN:` and `ERROR:` lines (strip ANSI defensively) into `(severity, path_relative_to_project, line_or_none, rule_id)` tuples. INFO lines from the bash `info()` helper (`validate.sh:115–119`) emit as `"  msg"` with no severity prefix and are NOT part of the parity multiset — they are advisory chatter that varies by `--verbose` flag and whose format is not stable enough to compare across implementations. Sort the extracted tuples.
- [ ] **Step 2: Build the Python-side extractor.** Given the runner's `RunResult`, project the `results` list down to the same tuple shape, FILTERING out `Severity.INFO` entries so the comparison is symmetric with Step 1. Sort.
- [ ] **Step 3: Assertion.** For each fixture, run both sides in `isolated_copy(...)`; assert the two multisets are equal. Fail with a structured diff (`set_a - set_b` and `set_b - set_a` shown side-by-side).
- [ ] **Step 4: Real-project assertion (Phase 1 acceptance criterion 1).** Same gate, but iterate over a list of real downstream project paths (defined in a fixture config file). Skip if the path doesn't resolve; warn (don't fail) if any project's sidecar files exist in the rsync'd copy, indicating the exclude pattern broke.
- [ ] **Step 5: CI integration.** Run on every PR. Failures block merge.

### Task 7: Implement formatter snapshot tests

**Files:**
- Create: `science/tests/validate/test_formatter_snapshots.py`
- Create: `science/tests/validate/snapshots/text_default.txt`, `snapshots/json_default.json`

- [ ] **Step 1: Snapshot fixture.** Choose one canonical fixture project from Task 5. Run `science validate` against it with default formatting; commit the output to `snapshots/text_default.txt`. Repeat with `--format json` → `snapshots/json_default.json`.
- [ ] **Step 2: Snapshot test.** Re-run; assert byte-equal match. On diff, emit a unified diff in the test output. Mark as `@pytest.mark.snapshot` and exclude from the CI-gating set (per design: snapshot diffs are reviewer-gating).
- [ ] **Step 3: Update script.** Add `scripts/update-validate-snapshots.py` that regenerates snapshots after intentional formatter changes.

### Task 8: Experimental Python sidecar discovery

**Files:**
- Modify: `science/src/science_tool/validate/runner.py`
- Modify: `science/src/science_tool/validate/cli.py`

- [ ] **Step 1: Gate flag.** Add `--experimental-python-sidecar` to the CLI. Default off. The flag toggles the `enable_python_sidecar` argument that Task 1 Step 5 already exposes on `runner.run(...)`; the CLI maps the flag to the boolean before delegating to the runner.
- [ ] **Step 2: Discovery.** When `enable_python_sidecar=True` and a `validate_local.py` exists in `project_root`, import it via `importlib.util.spec_from_file_location` + `module_from_spec` + `exec_module`. The directory of `validate_local.py` is added to `sys.path` ONLY for the duration of the import.
- [ ] **Step 3: Hook isolation.** Before each project's `validate_local.py` is imported, clear `runner._HOOKS`; after the run, clear again. This prevents cross-project leakage when multiple projects are validated in one process.
- [ ] **Step 4: Acceptance test.** A synthetic project with a `validate_local.py` that registers `@hook("extra_checks")` and yields one WARN. Assert the WARN appears in the run output only when `--experimental-python-sidecar` is set.

### Task 9: Document `science validate`

**Files:**
- Modify: `docs/` reference index (location TBD by the existing convention; check `docs/` for the equivalent of `cli.md` or a per-command reference file).

- [ ] **Step 1: Write the reference page.** Sections: synopsis, flags, exit codes, severity model, JSON output schema, environment variables (`NO_COLOR`, `SCIENCE_VALIDATE_DISABLE_SIDECAR`), discovery (`validate.sh`, `validate_local.py`).
- [ ] **Step 2: Cross-link from CLI overview.**

---

## Phase 2 — `validate_local.py` promoted; legacy bash sidecar on a deprecation path

### Task 10: Registry-schema extension

**Files:**
- Modify: `science/src/science_tool/project_artifacts/registry_schema.py`
- Create: `science/tests/validate/test_schema_python_sidecar.py`

- [ ] **Step 1: Add enum value.** Append `PYTHON_SIDECAR = "python_sidecar"` to `ExtensionKind` (`registry_schema.py:25`).
- [ ] **Step 2: Extend pairing validator.** In `_consumer_extension_pairing` (`registry_schema.py:158`), update the `DIRECT_EXECUTE` set to `{SOURCED_SIDECAR, PYTHON_SIDECAR, NONE}`.
- [ ] **Step 3: Tests.** (a) Round-trip an `Artifact` with `extension_protocol.kind = python_sidecar` + `consumer = direct_execute`; assert no validation error. (b) Round-trip with `kind = python_sidecar` + `consumer = science_loader`; assert the pairing validator raises. (c) Existing `SOURCED_SIDECAR` round-trips still pass.

### Task 11: Build the packaged legacy runner

**Files:**
- Create: `science/src/science_tool/validate/_legacy/__init__.py`
- Create: `science/src/science_tool/validate/_legacy/validate_legacy.sh`
- Create: `science/src/science_tool/validate/_legacy/VERSION` (records the frozen canonical's source-sha256 and the version label it was frozen at)
- Create: `science/src/science_tool/validate/_legacy/runner.py`
- Create: `science/src/science_tool/validate/legacy_parser.py`
- Create: `science/tests/validate/test_legacy_parser.py`
- Modify: `science/pyproject.toml` (add `_legacy/*.sh` and `_legacy/VERSION` to `[tool.hatch.build.targets.wheel.force-include]`; see Task 11.5 below)

- [ ] **Step 1: Freeze the canonical body.** Copy the current `data/validate.sh` (the version present just before the shim lands) to `_legacy/validate_legacy.sh`. Record its sha256 in a sibling `_legacy/VERSION` file.
- [ ] **Step 2: Add `SCIENCE_LEGACY_SIDECAR_ONLY=1` guard.** Modify the frozen script: after the sidecar source AND after the EXIT trap setup, branch on the env var; when set, the branch dispatches `pre_validation`, dispatches `extra_checks`, then `exit 0`. The exit triggers the existing `trap 'dispatch_hook post_validation' EXIT` at `validate.sh:34` so `post_validation` hooks still fire. ALL canonical sections (1 through 19) are skipped, but hook dispatch is preserved — today's bash dispatches `pre_validation` at `validate.sh:205` (right after helpers/banner) and `extra_checks` at `validate.sh:1512` (right before summary, `validate.sh:1515`). The summary banner is also suppressed under this flag so the legacy-parser sees only hook-emitted output.
- [ ] **Step 3: Add `SCIENCE_VALIDATE_NO_COLOR=1` guard.** Modify `red`, `yellow`, `green`, `info`, `error`, `warn`, `strict_warn` helpers: when the env var is set, emit plain `"%s\n"` instead of the `\033[3Xm…\033[0m` form. Today's helpers always wrap (`validate.sh:92–94`); without this branch the parser's `WARN:` / `ERROR:` prefix match fails.
- [ ] **Step 4: Implement `legacy_parser.parse(stdout: str) -> tuple[list[Result], list[str]]`.**
  - Strip ANSI: `re.sub(r"\x1b\[[0-9;]*m", "", line)` before matching.
  - Match `^WARN: (.*)$` and `^ERROR: (.*)$`; map to `Severity.WARN` / `Severity.ERROR`.
  - Path/line extraction: today's bash WARN strings include a path-prefix in many cases (e.g., `WARN: doc/papers/Foo.md: missing X`). The parser does a best-effort path extraction by splitting on the first `: ` after the severity tag; if the leading token is a valid path under `project_root`, emit `Result(path=Path(token), message=rest, …)`; otherwise emit `Result(path=None, message=full, …)`.
  - **Non-matching lines (banners, `info()` echoes from `validate.sh:115–119`, blank lines) are NOT turned into `Result` objects.** They are returned as the second element of the tuple — a plain `list[str]` of log lines that the runner forwards to its log channel (surfaced under `--verbose`). The parity gate's multiset comparison only consumes the `list[Result]`. This keeps the Python side and the bash side aligned: today's `bash validate.sh` does not parse its own banner output back into severity events, so neither should the Python legacy runner. The parity-gate multiset extractor (Task 6 Step 1) likewise only matches `WARN:` / `ERROR:` lines and ignores the rest.
  - Unit tests cover: plain WARN, ANSI-wrapped WARN, WARN with path prefix, WARN without path prefix, ERROR variants, mixed multiline output, banner-line-only input (yields zero Results, N log lines), empty input.
- [ ] **Step 5: Implement `_legacy/runner.run_legacy_sidecar(project_root: Path) -> tuple[list[Result], list[str]]`.**
  - Resolve `_legacy/validate_legacy.sh` via `importlib.resources.files("science_tool.validate._legacy") / "validate_legacy.sh"`, then `resources.as_file(...)` to obtain an absolute filesystem path.
  - `subprocess.run(["bash", str(absolute_path)], cwd=project_root, env={..., "SCIENCE_LEGACY_SIDECAR_ONLY": "1", "SCIENCE_VALIDATE_NO_COLOR": "1"}, capture_output=True, text=True, check=False)`.
  - Pass `subprocess`'s `stdout` to `legacy_parser.parse(...)`; return the `(results, log_lines)` tuple. The calling runner appends `results` to its `Result` stream and forwards `log_lines` to the run log.
  - Handle non-zero exit: emit a single ERROR `Result` with the bash exit code and the captured stderr (truncated) so failures aren't silent.
- [ ] **Step 6: Acceptance.** A synthetic project with a `validate.local.sh` registering one `@hook` (bash) yielding one WARN. Run `_legacy.runner.run_legacy_sidecar(...)` directly; assert the parsed `Result` matches. Stress with an ANSI-wrapped sidecar message; assert ANSI is stripped.

### Task 11.5: Wheel packaging for `_legacy/` data files

**Files:**
- Modify: `science/pyproject.toml`

Non-Python files inside the package (the frozen bash script, the VERSION sentinel) are not pulled in by the default hatch wheel build for `packages = ["src/science_tool"]`; only `.py` files ship by default. Today's `[tool.hatch.build.targets.wheel.force-include]` block (`pyproject.toml:42–45`) explicitly force-includes `dag/edges.schema.json`, `project_artifacts/registry.yaml`, and `project_artifacts/data/`. Without an equivalent entry for `_legacy/`, the Phase-2 `importlib.resources.files(...)` call from `_legacy/runner.py` Step 5 would fail in any installed wheel (it would work in editable installs but break the release).

- [ ] **Step 1: Add force-include entries.** Append to `[tool.hatch.build.targets.wheel.force-include]`:

  ```toml
  "src/science_tool/validate/_legacy/validate_legacy.sh" = "science_tool/validate/_legacy/validate_legacy.sh"
  "src/science_tool/validate/_legacy/VERSION" = "science_tool/validate/_legacy/VERSION"
  ```

- [ ] **Step 2: Wheel-roundtrip test.** Add `science/tests/validate/test_legacy_packaged_resources.py`: build a wheel via `python -m build --wheel` (or invoke hatch's internal API), install it into a tempdir venv, run `python -c "from importlib.resources import files; print((files('science_tool.validate._legacy') / 'validate_legacy.sh').is_file())"`; assert `True`. Same assertion for `VERSION`. This guards against silent breakage if anyone refactors the package layout.
- [ ] **Step 3: Phase-3 cleanup checkpoint.** When Task 22 deletes `_legacy/`, the matching force-include entries must also be removed — Task 22 Step 1 has been amended (see Phase 3) to enumerate this.

### Task 12: Sidecar precedence rule + legacy hook phasing in `science validate`

**Files:**
- Modify: `science/src/science_tool/validate/runner.py`
- Modify: `science/src/science_tool/validate/_legacy/validate_legacy.sh` (extend the `SCIENCE_LEGACY_SIDECAR_ONLY=1` branch from Task 11 Step 2 to honour a new env var `SCIENCE_LEGACY_DISPATCH_PHASE`)
- Modify: `science/src/science_tool/validate/_legacy/runner.py` (accept a `phase` argument; pass through as `SCIENCE_LEGACY_DISPATCH_PHASE`)

- [ ] **Step 1: Legacy hook phasing.** A single bash subprocess cannot straddle the Python canonical-checks phase, so the legacy runner is invoked **twice** — once before Python canonical checks (with `SCIENCE_LEGACY_DISPATCH_PHASE=pre_validation`) and once after (`=extra_checks`) — so that bash `extra_checks` hooks see exactly the same "after canonical sections" ordering they see today at `validate.sh:1510`. Each invocation re-sources `validate.local.sh`, dispatches only the named phase's hooks, then exits (the trap at `validate.sh:34` still fires `post_validation` at the end of EACH subprocess; the runner deduplicates by only counting the second invocation's `post_validation` output, since the first's would be premature).

  The supersedes Task 11 Step 2's earlier "dispatch both phases in one subprocess" plan: the new contract is `SCIENCE_LEGACY_SIDECAR_ONLY=1` AND `SCIENCE_LEGACY_DISPATCH_PHASE in {pre_validation, extra_checks, both}`, where `both` (the default if the variable is unset) preserves the Task 11 Step 2 single-shot behaviour for tests that want it. The runner.py path always passes `pre_validation` or `extra_checks` separately; `both` exists only as a legacy-debug affordance.

  **Caveat documented in the porting guide (Task 20):** bash hooks that consume Python-side `ERRORS` / `WARNINGS` counters or canonical-check Result state will NOT see Python results — those counters are per-bash-process and not visible to the bash subprocess. This is a deliberate narrowing of legacy support: such hooks must be ported to `validate_local.py` (where they have first-class access to `ctx` and the in-progress `Result` stream) before Phase 3 retires the legacy runner.

- [ ] **Step 2: Precedence.** Check `(project_root / "validate_local.py")` and `(project_root / "validate.local.sh")` for existence during the sidecar-import phase (runner.run Step 5 point 2).
  - Both absent → no sidecar; no deprecation warning.
  - `validate_local.py` only → import it (per Task 8). The import side effect registers any `@hook(...)` decorators into `runner._HOOKS`. No legacy subprocess invocations.
  - `validate.local.sh` only → schedule two legacy subprocess invocations (one per phase, per Step 1); emit a single deprecation WARN.
  - Both present → import `validate_local.py`; emit a single deprecation WARN about the stale bash file. `validate.local.sh` is NOT executed.
- [ ] **Step 3: Test the precedence matrix and the hook-phasing contract.**
  - Four fixtures for precedence (none, py only, sh only, both); assert behaviour per row, including the ordering: the deprecation WARN appears before any other WARN/ERROR in the run output.
  - Two additional fixtures for legacy hook phasing: (a) a `validate.local.sh` registering a hook on `pre_validation` that emits "PRE-FIRED" — assert it appears in the run output BEFORE any canonical-section output; (b) a `validate.local.sh` registering a hook on `extra_checks` that emits "POST-FIRED" — assert it appears AFTER all canonical-section output but BEFORE the summary, matching `validate.sh:1510`'s position.

### Task 13: Drop the `--experimental-` gate

**Files:**
- Modify: `science/src/science_tool/validate/cli.py`

- [ ] **Step 1: Remove the flag.** Delete `--experimental-python-sidecar` from the CLI; flip the runner's `enable_python_sidecar` default to `True` so `science validate` (with no flag) discovers Python sidecars by default. The `enable_python_sidecar` parameter itself stays on `runner.run(...)` so tests that want to force-disable sidecars can still pass `enable_python_sidecar=False`.
- [ ] **Step 2: Update the docs page from Task 9.**

### Task 14: `SCIENCE_VALIDATE_DISABLE_SIDECAR=1` opt-out

**Files:**
- Modify: `science/src/science_tool/validate/runner.py`
- Modify: `science/src/science_tool/validate/_legacy/validate_legacy.sh`

- [ ] **Step 1: Python side.** In `runner.run(...)`, if the env var is set, skip both `validate_local.py` and `validate.local.sh` discovery entirely (no deprecation WARN either — the user is explicitly opting out).
- [ ] **Step 2: Bash side (frozen canonical).** In `_legacy/validate_legacy.sh`, guard the `source validate.local.sh` line with the same env var.
- [ ] **Step 3: Acceptance.** A fixture project with both files; running `SCIENCE_VALIDATE_DISABLE_SIDECAR=1 science validate` yields zero WARN/ERROR from either sidecar AND zero deprecation messages.

### Task 15: Sidecar-included semantic parity gate

**Files:**
- Create: `science/tests/validate/test_parity_with_sidecar.py`

- [ ] **Step 1: Fixture matrix.** Real-project paths from Task 6's config, plus two synthetic fixtures (one with a `validate.local.sh` hook adding WARN, one with the same hook adding ERROR).
- [ ] **Step 2: Comparison.** For each, run `bash validate.sh` (sources its own `validate.local.sh`) AND `science validate` (routes through the legacy runner). Compare semantic multisets per Task 6 Step 1.
- [ ] **Step 3: CI gate.** Required-green to close Phase 2.

### Task 16: `science project artifacts port-validate-sidecar` helper

**Files:**
- Create: `science/src/science_tool/project_artifacts/port_validate_sidecar.py`
- Modify: `science/src/science_tool/project_artifacts/cli.py` (register the subcommand on `artifacts_group`, the existing `@click.group("artifacts")` at `cli.py:11–13` — NOT on the root group in `science_tool/cli.py`, which only attaches `artifacts_group` to `project` at `cli.py:3403`)

- [ ] **Step 1: Implement the command.** Add `@artifacts_group.command("port-validate-sidecar")` to `project_artifacts/cli.py`, following the existing style of `list_cmd` (`cli.py:16–`). Use the same `--project-root` option type and conventions.
- [ ] **Step 2: Scope.** Best-effort skeleton generator. Reads `validate.local.sh`; extracts each `register_validation_hook <name> <fn>` call site; emits a `validate_local.py` containing one `@hook(...)` function per registration, with the bash body inlined as a string-literal comment. The user ports the body.
- [ ] **Step 3: Output convention.** Refuses to overwrite an existing `validate_local.py` unless `--force` is passed. Writes to `validate_local.py.draft` by default; user copies/diffs.
- [ ] **Step 4: Unit-test on a synthetic `validate.local.sh`.** Also assert via `click.testing.CliRunner` that `science project artifacts port-validate-sidecar --help` works end-to-end (catches registration mistakes).

### Task 17: Ship shim `validate.sh`

**Files:**
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`

- [ ] **Step 1: Replace canonical body with shim.** New body:

  ```bash
  #!/usr/bin/env bash
  # science-managed-artifact: validate.sh
  # science-managed-version: <YYYY.MM.DD.N matching ^\d{4}\.\d{2}\.\d{2}(?:\.\d+)?$>
  # science-managed-source-sha256: <64-hex sha256 of the body lines after the header>
  exec uv run science validate "$@"
  ```

  The `source-sha256` is recomputed from the body lines after the header per `header.py:60`.
- [ ] **Step 2: Verify header parses.** Run `science_tool.project_artifacts.header.parse_header` against the shim bytes; assert it returns a `ParsedHeader` with the expected fields. Add a unit test in the existing `test_initial_validate_sh.py` (or a Phase-2 sibling) asserting this.

### Task 18: Update `registry.yaml` for the shim

**Files:**
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`

- [ ] **Step 1: Update `validate.sh` entry.**
  - `version`: new shim version (Task 17 Step 1).
  - `current_hash`: shim body sha256.
  - `previous_hashes`: append the prior `current_hash` (the last "real" canonical) with its version.
  - `extension_protocol.kind`: `python_sidecar`.
  - `extension_protocol.sidecar_path`: `validate_local.py`.
  - `extension_protocol.hook_namespace`: remove (not applicable for the Python protocol; the schema's field is optional).
  - `extension_protocol.contract`: rewrite to describe the Python-import + `@hook(...)` flow.
- [ ] **Step 2: Migration entry.**
  - Append a `migrations:` entry with `from: <old-version>`, `to: <new-shim-version>`, `kind: byte_replace`, `summary: "Migrate from in-project canonical body to packaged shim; project-local checks move to validate_local.py per docs/migration/2026-05-19-validate-local-sh-porting-guide.md."`
  - **The migration kind is `byte_replace`, not `project_action`.** The shim transition is literally a byte-replacement of the canonical body; the schema rejects `byte_replace` entries with non-empty `steps` (`registry_schema.py:125–127`) AND rejects `project_action` entries with no `steps` (`registry_schema.py:128–129`), so `project_action` would require declaring concrete `MigrationStep`s (each with `id`, `description`, `impl: PythonImpl | BashImpl`, `touched_paths`). There is no real per-project action to take beyond accepting the new bytes — the diff is visible via `science project artifacts diff validate.sh` and via the standard `science project artifacts update` flow, which is the right surface for "user reviews the byte-level diff" UX. Keep this as `byte_replace`; if a real project-action ever emerges (e.g. "auto-port `validate.local.sh` to `validate_local.py`"), that becomes a separate migration entry with a `kind: hybrid` or `project_action` plus a real step.
- [ ] **Step 3: Update changelog.**

### Task 19: `science health` skips the subprocess

**Files:**
- Modify: `science/src/science_tool/health/` (path TBC)

- [ ] **Step 1: Locate the call site.** Today's `science health` invokes `bash validate.sh` under the hood. Replace with a direct call to `science_tool.validate.runner.run(...)`.
- [ ] **Step 2: Surface the `RunResult`.** Fold its `errors` / `warnings` into the health-check summary using the same severity vocabulary `science health` already uses.

### Task 20: Porting guide

**Files:**
- Create: `docs/migration/2026-05-19-validate-local-sh-porting-guide.md`

- [ ] **Step 1: Worked example.** Use `~/d/health/meta/validate.local.sh` (committed 2026-05-19) as the canonical example. Show before (bash + embedded Python heredoc) and after (`validate_local.py` with `@hook("extra_checks")`). Estimated ~60-80 lines of clean Python from ~145 lines of bash+heredoc.
- [ ] **Step 2: Cookbook.** Common porting moves: env-var reads, file globs, YAML parsing, multi-line WARN formatting, ANSI use (drop entirely).
- [ ] **Step 3: Cross-link** the design and implementation plans.

---

## Phase 3 — Remove `validate.local.sh` support

### Task 21: Hard-ERROR existence check

**Files:**
- Modify: `science/src/science_tool/validate/runner.py`

- [ ] **Step 1: Replace the legacy-runner branch.** If `(project_root / "validate.local.sh").exists()`, emit `Severity.ERROR` with message pointing at the porting guide (`docs/migration/2026-05-19-validate-local-sh-porting-guide.md`). The file is never sourced or executed — only its presence is detected.
- [ ] **Step 2: Update tests.** `test_phase3_legacy_removed.py` asserts the ERROR fires and asserts no subprocess call is attempted (mock the subprocess module and assert it wasn't called).

### Task 22: Delete the `_legacy/` package directory

**Files:**
- Delete: `science/src/science_tool/validate/_legacy/__init__.py`
- Delete: `science/src/science_tool/validate/_legacy/validate_legacy.sh`
- Delete: `science/src/science_tool/validate/_legacy/runner.py`
- Delete: `science/src/science_tool/validate/legacy_parser.py`
- Delete: associated tests (`test_legacy_parser.py`).

- [ ] **Step 1: Remove imports + force-includes.** Grep for any remaining references to `_legacy` or `legacy_parser`; remove. Also remove the two `_legacy/` entries from `[tool.hatch.build.targets.wheel.force-include]` in `science/pyproject.toml` (added in Task 11.5). Verify with a wheel rebuild + `unzip -l` that no `_legacy/` artifacts ship.
- [ ] **Step 2: Remove env-var documentation.** `SCIENCE_LEGACY_SIDECAR_ONLY` and `SCIENCE_VALIDATE_NO_COLOR` were only meaningful inside the frozen bash. Remove from docs. `SCIENCE_VALIDATE_DISABLE_SIDECAR` stays — it remains useful for testing and for users who want to bypass `validate_local.py` without renaming it.
- [ ] **Step 3: Test absence.** Add an assertion that `importlib.util.find_spec("science_tool.validate._legacy")` returns `None`.

### Task 23: Confirm schema unchanged

**Files:** (no edits; verification only)

- [ ] **Step 1: Assert.** `ExtensionKind.SOURCED_SIDECAR` is still in the schema; some artifacts (TBC) continue to use it. The `validate.sh` entry no longer references it; it now points at `PYTHON_SIDECAR`.
- [ ] **Step 2: Add a regression test** that loads `registry.yaml`, iterates artifacts, and asserts `validate.sh.extension_protocol.kind == "python_sidecar"`.

### Task 24: Release notes + final cleanup

**Files:**
- Modify: `CHANGELOG.md` (or equivalent)

- [ ] **Step 1: Three release-notes entries** spanning the three minor versions where Phases 1, 2, 3 landed. Each calls out the user-visible change and links to the porting guide / design.

---

## Cross-references

- Design: `docs/plans/2026-05-19-validate-cli-migration-design.md`.
- Predecessor: `docs/plans/2026-04-27-validate-hook-points.md` (hook contract this implementation preserves) and `docs/plans/2026-04-27-validate-hook-points-implementation.md` (hook infrastructure the frozen bash inherits).
- Composes with: `docs/plans/2026-04-26-managed-artifacts-long-term-design.md` (the managed-artifact framework governs the shim and registry entry).
- Downstream worked example: `~/d/health/meta/validate.local.sh` (real-world legacy sidecar, primary porting example).
- Sibling worked example: `~/d/cancer/mechanisms/evolution/validate.local.sh` (mirror; same migration shape).
