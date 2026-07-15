# ValidationVerdict — the validator/audit convergence (instrument-result follow-on item 2)

**Status:** SHIPPED — merged to local `main` at `c4aa77c7`.

**Origin.** The InstrumentResult convergence
([`2026-07-11-instrument-result-convergence-design.md`](2026-07-11-instrument-result-convergence-design.md))
gave every *finder* a canonical result type so a silent non-run cannot masquerade as a
clean empty. Its Follow-on list, item 2, names the one family the finder type cannot
absorb: the **validator/audit** functions returning `tuple[list[T], bool]`, where the
`bool` is `has_failures` — a pass/fail verdict orthogonal to the finder's ran/empty/unwired
axis. The convergence guard deliberately excluded them (`_is_tuple_precursor` matches only
the `tuple[list[T], str | None]` reason precursor, not `tuple[list[T], bool]`), with a
docstring saying so: "for a validator, `ok` means found rows, i.e. found PROBLEMS —
orthogonal to pass/fail." The design summed it up: *"None of the four is a shape problem
this type can fix."* This spec adds the sibling type that does.

## 1. The defect this closes

Three consequences of leaving the validator family on `tuple[list[T], bool]`:

1. **Guard blind spot.** A *new* public instrument that returns `tuple[list[T], bool]`
   evades the AST boundary guard entirely — the detector is written to skip that shape.
2. **Fabricated verdict on a non-run.** `validate_graph` on an unparseable (or missing)
   graph never ran its content checks, yet returns a row list + `has_failures` — a report
   card for checks that did not execute.
3. **Downstream fragmentation.** Two planned specs (big-picture run integrity; curate +
   transient placement) need a canonical verdict surface; without one they each invent a
   local status convention — the exact fragmentation the convergence exists to prevent.

## 2. The type — `ValidationVerdict[RowT]`

A sibling to `InstrumentResult`, in the same `science_tool/instruments.py` (same
convergence, different axis). **Named `ValidationVerdict`, not `Verdict`**, because
`science_tool.verdict` is an established package — the D5 epistemic verdict-token system
(`VerdictBlock`, parser, registry, rules). Overloading that term in `instruments.py` would
be a false cognate.

```python
ValidationVerdictStatus = Literal["passed", "failed", "unwired"]

class ValidationVerdict(BaseModel, Generic[RowT]):
    status: ValidationVerdictStatus
    rows: list[RowT] = Field(default_factory=list)   # the report card
    reason: str | None = None
    code: str | None = None

    @model_validator(mode="after")
    def _enforce_status_invariant(self) -> "ValidationVerdict[RowT]":
        if self.status == "unwired":
            if self.rows:
                raise ValueError("status='unwired' forbids rows; they are meaningless")
            if not self.code:
                raise ValueError("status='unwired' requires a machine-readable code")
        return self

    @classmethod
    def passed(cls, rows, *, code=None, reason=None) -> "ValidationVerdict[RowT]": ...
    @classmethod
    def failed(cls, rows, *, code=None, reason=None) -> "ValidationVerdict[RowT]": ...
    @classmethod
    def unwired(cls, *, code, reason=None) -> "ValidationVerdict[RowT]": ...
    @classmethod
    def from_has_failures(cls, rows, has_failures, *, code=None, reason=None) -> "ValidationVerdict[RowT]":
        return cls(status="failed" if has_failures else "passed", rows=rows, code=code, reason=reason)
```

**Why no `empty` status.** A validator either ran (`passed`/`failed`, rows = report card)
or could not (`unwired`). "Empty rows" is not a distinct meaning: `passed` with an empty
card is legitimate and is told apart from `unwired` by *status*, never by row count. This
is the deliberate difference from `InstrumentResult`, whose `empty` is a true-zero finding.

**The verdict is set explicitly by the caller.** The type is `Generic[RowT]` and cannot
inspect `row["status"]`, exactly as `InstrumentResult` cannot inspect its rows. Callers
compute `has_failures = any(row["status"] == "fail" ...)` and pick `failed`/`passed`;
`from_has_failures` captures the one pattern all four call sites share.

## 3. Scope — the fully-bounded offender set

A full-namespace AST scan (the expanded module set, below) finds **exactly five** public
`tuple[list[T], bool]` signatures and one bare-`list` audit helper. Nothing else in the
namespace trips the widened detector. The set is closed:

**Migrate to `ValidationVerdict` (4 public functions):**

| Function | Module | Type | Notes |
|----------|--------|------|-------|
| `validate_graph` | `graph/store/validation.py` | `ValidationVerdict[dict[str, str]]` | **unwired** on missing/unparseable graph (§4) |
| `validate_graph_dataset` | `graph/store/validation.py` | `ValidationVerdict[dict[str, str]]` | always `passed`/`failed` — a loaded dataset always runs |
| `materialization_audit` | `graph/materialize.py` | `ValidationVerdict[dict[str, str]]` | `from_has_failures` over the re-projected audit rows |
| `audit_project_sources` | `graph/migrate.py` | `ValidationVerdict[AuditRow]` | `from_has_failures`; total given `ProjectSources` |

**Privatize (drops from the guard namespace):** `validate_empirical_run_resolution` →
`_validate_empirical_run_resolution`. Its `bool` is `is_fatal`, not `has_failures`; its only
caller is `validate_graph_dataset` (validation.py:168) and it is not re-exported. The
underscore removes it from the guard's public-def scan; its `tuple[list[str], bool]` shape
is a fine internal helper signature and stays.

**`_NOT_INSTRUMENTS` entry:** `audit_identity_table` (`graph/migrate.py`). A pure fold over
a caller-supplied `IdentityTable` — no I/O, no user-identifier resolution; its only caller
is `audit_project_sources` internally. Surfaced only because adding `migrate.py` to the
namespace exposes its bare `list[AuditRow]` return. By the guard's own test (does it do
I/O, or resolve a user identifier?) it is a pure helper, so it joins the existing
`_NOT_INSTRUMENTS` entries with a written justification. It stays public — it is imported
directly by `tests/test_graph_migrate_identity_audit.py`.

## 4. The unwired behavior change — `validate_graph`

`validate_graph` is the one migrated function with a genuine non-run path. Today it catches
every `Exception` from `_load_dataset` and returns a fabricated `parseable_trig`=fail row.
`_load_dataset` (dataset.py:48) raises `ClickException` for a **missing** file and an rdflib
parse error for a **malformed** one — so a single `unparseable` code would mislabel a
missing graph. Distinguish by existence:

```python
def validate_graph(graph_path: Path) -> ValidationVerdict[dict[str, str]]:
    if not graph_path.exists():
        return ValidationVerdict.unwired(
            code="graph_missing",
            reason=f"Graph file not found: {graph_path}",
        )
    try:
        dataset = _load_dataset(graph_path)
    except Exception as exc:  # noqa: BLE001
        return ValidationVerdict.unwired(
            code="unparseable",
            reason=f"graph.trig did not parse: {exc}",
        )
    return validate_graph_dataset(dataset)
```

`validate_graph_dataset` takes an already-loaded `Dataset`, so it always runs every check
and returns `passed`/`failed` — never `unwired`.

## 5. Consumer contract — exhaustive `unwired` handling, failing closed

**This is a design invariant, not per-consumer discretion.** Collapsing the verdict to a
bool via `status == "failed"` maps `unwired` to `False` — i.e. to "clean" — recreating the
silent-instrument defect at every boundary. Therefore **no consumer may derive a pass/fail
bool without first handling `unwired`.** The canonical shape:

```python
verdict = <producer>(...)
if verdict.status == "unwired":
    <fail closed: raise / exit nonzero / emit ERROR — boundary-appropriate>
rows = verdict.rows
has_failures = verdict.status == "failed"
```

This holds **even for `audit_project_sources` / `materialization_audit`, which are total
today.** Consumers reject `unwired` rather than rely on that implementation detail, so a
future producer change cannot silently pass. These defensive branches are unreachable via
the real producers and are therefore tested by injecting an `unwired` verdict (§7).

Consumer-by-consumer disposition:

| Consumer | Site | `unwired` disposition |
|----------|------|-----------------------|
| `science graph validate` CLI | `graph/cli.py:233` | Print `reason` as "could not run" + `code`; exit nonzero. Branch **before** `emit_query_rows`, so json mode never emits `[]` (which reads as "passed"). |
| `science graph audit` CLI | `graph/cli.py:162` | Same: surface `code`/`reason`, exit nonzero. |
| `validate` check | `validate/checks/graph.py:199-215` | **Load-bearing.** Replace the `parseable_trig`-row sniff with `if verdict.status == "unwired": yield ERROR; return`. The now-empty rows would otherwise make the check silently pass **and** fall through to `diff_graph_inputs_dataset` with an unbound `dataset`. The early return is preserved by the `unwired` branch. |
| `validate` check (audit) | `validate/checks/graph.py:177` | On `unwired`, emit an ERROR finding rather than "all canonical references resolved". |
| source compiler | `graph/materialize.py::_compile` via `_audit_phase` | `_audit_phase` → `ValidationVerdict[AuditRow]` (private). `_compile` **fails closed**: `if verdict.status == "unwired": raise ValueError(...)`. Then `has_failures = verdict.status == "failed"`. `CompilationResult.has_failures` stays a `bool` — `ValidationVerdict` is the *public* boundary type only; private plumbing keeps its bool. |
| freshness | `graph/freshness.py:422` | Reject `unwired` (raise) before the `status == "failed"` gate. |
| entity audit diff | `entities.py:1747, 1751` | Use `.rows` for the baseline/prospective diff; on `unwired`, **raise `EntityCommandError`** (entities.py:47) first — never `assert`, which `python -O` strips, restoring the silent `.rows` path. |
| health check | `collect_unresolved_refs` (`graph/health_checks/unresolved_refs.py:64`) | The function already returns `InstrumentResult[UnresolvedRef]` and has an `unwired` idiom. On an `unwired` audit verdict, **propagate as `InstrumentResult.unwired(code=verdict.code, reason=verdict.reason)`** — a precise bridge between the two types, not the ambiguous "surfaced failure." Then use `.rows`. |

## 6. Guard changes

- `INSTRUMENT_MODULES += ("graph/materialize.py", "graph/migrate.py")`.
- Rewrite the tuple detector (`_is_tuple_precursor`): flag `tuple[list[T], bool]` **and**
  `tuple[list[T], str | None]`. The old docstring's *exclusion* rationale is **reversed** —
  `ValidationVerdict` now carries `has_failures`, so the family must migrate rather than be
  waved through. Both precursor tuple families are rejected.
- Add `("graph/migrate.py", "audit_identity_table")` to `_NOT_INSTRUMENTS` with its
  justification.
- **Contract prose, not just the detector.** The guard's declared contract asserts, in
  several places, that every namespace helper must return `InstrumentResult`. Once
  `ValidationVerdict` is admissible those claims are false even though the AST detector
  passes it (its annotation root is neither a bare collection nor a tuple). Update:
  `instruments.py` `INSTRUMENT_MODULES` docstring (line ~35); `test_instrument_boundary.py`
  module docstring, the `test_instrument_namespace_returns_instrument_result` name/message,
  and the offender-message text — all to "`InstrumentResult` or `ValidationVerdict`."
- `_ALLOWLIST` and `_DEFERRED_INSTRUMENTS` stay empty; `test_migration_is_complete` stays
  green (the full-namespace scan confirms zero public offenders remain post-migration).

## 7. Testing

**`ValidationVerdict` unit tests.** Invariants: `unwired` forbids rows and requires `code`;
`passed`/`failed` allow any rows incl. empty; `passed` with empty rows is distinct from
`unwired` (status, not row count); `from_has_failures(rows, True/False)` maps to
`failed`/`passed`.

**Per-function migration tests.** Each of the four returns the right status/rows.
`validate_graph`: `graph_missing` on an absent path and `unparseable` on a malformed file
are **distinct codes**, tested separately; a well-formed graph returns `passed`/`failed`
correctly.

**Consumer fail-closed tests — one per disposition in the §5 table.** §5 makes exhaustive
`unwired` handling an invariant; the tests must cover *every* boundary, since these are the
branches most likely to regress into reading empty rows as success. Each injects an
`unwired` verdict (monkeypatch the producer) unless the real producer emits it:

- **`science graph validate`** (real `unwired` via unparseable + missing graph), in **table**
  and **json** modes: nonzero exit; output carries "could not run" + machine `code`/`reason`;
  **no empty successful rows payload** (json is not `[]`).
- **`science graph audit`** (`cli.py:162`, injected `unwired`): surfaces `code`/`reason`,
  exits nonzero — not exit 0 over empty rows.
- **`validate`-check, validate side** (injected `unwired` `validate_graph`): exactly one
  ERROR **and** `diff_graph_inputs_dataset` is **not called** (assert the follow-up skipped).
- **`validate`-check, audit side** (`checks/graph.py:177`, injected `unwired`
  `materialization_audit`): emits an ERROR, not "all canonical references resolved".
- **`_compile` / `_audit_phase`** (injected `unwired` `audit_project_sources`): raises, does
  not compile.
- **`freshness`** (injected `unwired`): raises, does not continue past the audit.
- **entity baseline/prospective audit** (`entities.py`, injected `unwired`): raises
  `EntityCommandError`, does not diff empty `.rows`.
- **`collect_unresolved_refs`** (injected `unwired`): returns `InstrumentResult.unwired`
  carrying the verdict's `code`/`reason`, not `InstrumentResult.from_rows([])`.

**Guard tests.** Both new modules are scanned; `audit_identity_table` sits in
`_NOT_INSTRUMENTS`; `test_migration_is_complete` and `test_allowlist_has_no_stale_entries`
stay green. **The detector test is parameterized over *both* precursor tuple families** —
`tuple[list[T], bool]` **and** `tuple[list[T], str | None]` (and the `Optional[str]`
spelling, which `_is_str_or_none` still accepts). There are no remaining reason-precursor
offenders in-tree to catch a `str | None` regression implicitly, so the detector must be
asserted directly on synthetic signatures of both shapes.

**Existing call-site updates.** ~35 test sites unpack `rows, has_failures = fn(...)`; each
becomes `verdict = fn(...)` with `.rows` / `.status`. Mechanical, but each must keep its
original assertion intent.

## 8. Files

- Modify: `science/src/science_tool/instruments.py` (add `ValidationVerdict`; docstring)
- Modify: `science/src/science_tool/graph/store/validation.py` (migrate two; privatize one)
- Modify: `science/src/science_tool/graph/materialize.py` (`materialization_audit`,
  `_audit_phase`, `_compile` fail-closed)
- Modify: `science/src/science_tool/graph/migrate.py` (`audit_project_sources`)
- Modify: `science/src/science_tool/graph/cli.py` (two commands, unwired branches)
- Modify: `science/src/science_tool/validate/checks/graph.py` (unwired handling, both sites)
- Modify: `science/src/science_tool/graph/freshness.py`,
  `science/src/science_tool/entities.py`,
  `science/src/science_tool/graph/health_checks/unresolved_refs.py` (consumer contract)
- Modify: `science/tests/test_instrument_boundary.py` (namespace, detector, prose,
  `_NOT_INSTRUMENTS`; parameterized both-precursor detector test)
- Create: `science/tests/test_validation_verdict.py` (type unit tests)
- Modify (consumer fail-closed regressions, §7 — one per disposition):
  `science/tests/test_graph_cli.py` (validate + audit CLI, table/json),
  `science/tests/validate/test_checks_graph.py` (validate + audit sides),
  `science/tests/graph/test_phase_split_contracts.py` (`_compile`/`_audit_phase`),
  `science/tests/test_freshness_derivation.py` (freshness),
  `science/tests/test_entities.py` (baseline/prospective audit),
  `science/tests/test_health.py` (`collect_unresolved_refs`)
- Modify (mechanical `.rows`/`.status` unpacking, intent preserved): the remaining
  tuple-unpacking sites, incl. `science/tests/test_graph_validate_run_resolution.py`,
  `science/tests/test_graph_validate_patch_convenience.py`,
  `science/tests/test_graph_migrate.py`, `science/tests/test_dataset_usage_materialize.py`,
  `science/tests/test_chain_freshness_integration.py`,
  `science/tests/test_meta_reference.py`, `science/tests/test_substrate_two_scope_e2e.py`,
  `science/tests/test_identity_audit_entrypoints.py`,
  `science/tests/test_chain_audit_references.py`

## 9. Out of scope

- Migrating finders to `ValidationVerdict` or validators to `InstrumentResult` — the two
  axes are deliberately distinct.
- The other Follow-on items (attention ranking; `curate/inventory` payload).
- Any change to what the validators *check*; this migrates the *return shape* only.
