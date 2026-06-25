# Dataset verify-access — Implementation Plan

Implements `plan:2026-06-24-dataset-verify-access-design`. Adds `science dataset verify-access <ref>`:
one atomic, idempotent edit over the coupled `origin` / `license` / `access` fields, doubling as the
legacy backfill. TDD throughout — tests land RED before each implementation step.

## Adopted design decisions (the design note's open questions)

1. `--method` is **required** on the verified path (epistemic enum, no default).
2. License: **fail early** when the entity has none and `--license` is omitted; `--license unknown`
   is the explicit "genuinely undetermined" escape hatch.
3. `--tier` is an **optional flag** on `verify-access` (not a separate command).

These are reversible — change them here and the tasks below adjust mechanically.

## Global constraints

- **Working dir / paths.** Run `uv run --frozen`, `pytest`, and `ruff` from `~/d/science/science`
  with package-relative paths (`tests/...`, `src/...`). The repo root has **no**
  `pyproject.toml` / `uv.lock`. Git commands run from the repo root (`~/d/science`) with `science/...`
  paths.
- **Reuse, don't fork.** Build on `resolve_dataset`, `_resolve_dataset_or_exit`,
  `_validate_prospective_write`, `validate_slug`, `AccessBlock` / `_coerce_access`, and the
  `yaml.safe_dump` rendering already in `datasets_catalog.py`. No parallel frontmatter handling.
- **Pure writer.** Inject `today: date` into the writer (as `add_dataset` does,
  `src/science_tool/datasets_catalog.py:90`); never call `date.today()` inside it.
- **No new store.** Reuse the existing `access` fields and the body `## Access verification log`
  section.

---

## T1 — Writer tests (RED)

New file `science/tests/test_dataset_verify_access.py`. Drive a `verify_access(...)` writer in
`science/src/science_tool/datasets_catalog.py`. Use a tmp project root with `entities/datasets/`.

Helper `_write_legacy(root, slug, **fm)` writes a minimal legacy dataset entity (e.g.
`source_class: observational`, `status: candidate`, **no** `origin`/`tier`/`access`/`license`).

Tests:

1. `test_verify_access_backfills_all_coupled_fields` — legacy entity (source_class only) →
   after `verify_access(root, "foo", level="public", method="retrieved", license="CC0-1.0",
   note="landing page public", today=DATE)`:
   - `origin == "external"`, `license == "CC0-1.0"`,
   - `access` block has `level: public`, `availability: available`, `verified: true`,
     `verification_method: retrieved`, `last_reviewed == DATE.isoformat()`,
     `verified_by == "agent (verify-access)"`.
   - body gained a `## Access verification log` line dated `DATE` containing the note.

2. `test_verify_access_yields_available_readiness` — load the written entity through
   `readiness_for(fm)` (or `DatasetEntity.model_validate(...).readiness()`); assert
   `state == "available"` and `readiness_weight(fm)[0] == 1.0`.

3. `test_verify_access_clean_under_dataset_metadata_check` — run `evaluate_dataset_metadata([fm])`
   over the result; assert **no** `dataset.license-missing` and **no** `dataset.tier-unrecognized`
   results.

4. `test_verify_access_idempotent_rereview` — run twice (second call `today=DATE2`); assert
   `last_reviewed == DATE2`, **two** log lines present, and no other field downgraded (still
   `verified: true`, license preserved).

5. `test_verify_access_preserves_existing_license_without_flag` — entity already has
   `license: "MIT"`; call without `license=`; assert it stays `"MIT"`.

6. `test_verify_access_requires_license_when_none_known` — legacy entity, no license, **verified path**,
   call with `license=None` → raises `EntityCommandError` (fail early; message names `--license`).

6b. `test_verify_access_exception_requires_license_when_none_known` — legacy entity, no license,
   **exception path** (`exception="scope-reduced"`, `license=None`) → also raises `EntityCommandError`
   naming `--license`. (Regression guard: the rule is path-independent because the entity still ends
   `origin: external`.)

7. `test_verify_access_exception_branch` — `verify_access(..., exception="scope-reduced",
   license="unknown", rationale="defer", followup_task="task:t1", today=DATE)` →
   `access.exception.mode == "scope-reduced"`,
   `access.exception.decision_date == DATE.isoformat()`, `access.exception.followup_task == "task:t1"`,
   `verified` is `false`, and `readiness().state == "consumable-via-scope-reduced"`.

8. `test_verify_access_exception_clears_existing_verified` — start from an **already-verified** entity
   (`verified: true`, method + last_reviewed set); apply `exception="scope-reduced"`; assert
   `verified == false` after (lifecycle invariant: `verified: true` ⊥ `exception.mode`), and that the
   stale `verification_method` no longer claims verification. Conversely, applying the verified path to
   an exception-gated entity clears `exception.mode` back to `""`.

9. `test_verify_access_refuses_derived` — entity with `origin: derived` (+ a derivation block) →
   raises `EntityCommandError` pointing at `register-run`.

10. `test_verify_access_unknown_slug` — missing entity → raises `EntityCommandError`.

Run (expect failures — `verify_access` undefined):

```bash
cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_verify_access.py -q
```

## T2 — Writer implementation (GREEN)

In `science/src/science_tool/datasets_catalog.py`, add:

```python
def verify_access(
    project_root: Path,
    ref: str,
    *,
    level: str | None = None,
    license: str | None = None,
    method: str | None = None,          # required on the verified path
    verified_by: str = "agent (verify-access)",
    source_url: str | None = None,
    tier: str | None = None,
    note: str = "",
    exception: str | None = None,       # mutually exclusive with the verified path
    rationale: str = "",
    superseded_by: str | None = None,
    followup_task: str | None = None,
    today: date | None = None,
) -> tuple[str, Path, str, float, list[str]]:
    # returns (entity_id, dest, readiness_state, readiness_weight, warnings)
    ...
```

Logic:

1. Resolve **locally** (reuse the path `resolve_dataset` walks, or factor a `_load_local_dataset`
   helper that returns `(path, fm, body)` and refuses commons-only refs).
2. Guard: if `fm.get("origin") == "derived"` → `EntityCommandError` (invariant #8; point at
   `register-run`).
3. Set `origin = "external"` if absent.
4. License (**path-independent** — applies to both the verified and exception branches, since both
   land `origin: external`): if `license` given → use it; elif existing non-empty license → preserve;
   else → `EntityCommandError` naming `--license` (the `unknown` sentinel is a valid explicit value).
   Do **not** gate this on the verified path — an exception-gated entity with an empty license trips
   `dataset.license-missing` exactly the same (`dataset_metadata.py:84–92`).
5. Branch (mutually exclusive — enforce both directions):
   - **verified path** (no `exception`): require `method` (else `EntityCommandError`); build the
     `access` dict — `level` (given / existing / `"public"`), `availability: "available"`,
     `verified: True`, `verification_method: method`, `last_reviewed: today.isoformat()`,
     `verified_by`, `source_url` (given / existing). **Clear any existing `exception.mode` to `""`**
     (lifecycle invariant: a verified entity carries no exception).
   - **exception path** (`exception` set): set `access.exception` — `mode`, `decision_date:
     today.isoformat()`, `rationale`, and `superseded_by_dataset` / `followup_task` as applicable.
     **Set `verified: False`** (actively clear it, in case we're converting an already-verified
     entity); keep `availability: available`. `decision_date` is required by `AccessException`
     (`science/model/src/science_model/packages/schema.py:85–93`) — never omit it.
6. `tier`: if given, set it.
7. Body: ensure a `## Access verification log` section exists; append
   `- {today} ({verified_by}): {note or method/exception summary}`.
8. Re-render with `yaml.safe_dump(..., sort_keys=False)`; validate in two passes and collect warnings:
   - `_validate_prospective_write(...)` — graph / source-audit blockers (raises on a blocking row).
   - `evaluate_dataset_metadata([new_fm])` — license / tier / cadence vocabulary warnings. This is a
     **separate** pass; `_validate_prospective_write` does not run the metadata checks (it diffs
     source-audit rows, `entities.py:1026–1052`), so an unrecognized license would otherwise slip
     through. Append its `Result.message`s to the warning list.
9. Atomic write (tmp + `os.replace`, mirroring `add_dataset`).
10. Compute `readiness_state` and weight via `readiness_for(new_fm)` / `readiness_weight(new_fm)` and
    return both (no graph build needed — readiness is frontmatter-only).

Re-run T1 → green.

## T3 — CLI test (RED)

New file `science/tests/test_dataset_verify_access_cli.py`, mirroring `test_dataset_add_cli.py`
(`CliRunner`, a fixture project root). Tests:

1. `test_cli_verify_access_backfills_and_reports_readiness` — invoke
   `dataset verify-access foo --level public --method retrieved --license CC0-1.0 --note "..."`;
   assert exit 0, on-disk entity validates, and stdout reports the resulting state
   (`available (weight 1.0)`).
2. `test_cli_verify_access_missing_method_errors` — verified path without `--method` → non-zero exit,
   message names `--method`.
3. `test_cli_verify_access_missing_license_errors` — legacy entity, no `--license`, on **both** the
   verified path and `--exception scope-reduced` → non-zero exit, message names `--license`
   (parametrize over the two paths to lock in the path-independent rule).
4. `test_cli_verify_access_exception_path` — `--exception scope-reduced --license unknown
   --rationale "defer" --followup-task task:t1` → exit 0, state `consumable-via-scope-reduced`.
5. `test_cli_verify_access_refuses_derived` — derived entity → non-zero exit, message names
   `register-run`.

```bash
cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_verify_access_cli.py -q
```

## T4 — CLI implementation (GREEN)

In `science/src/science_tool/cli.py`, add `@dataset_group.command("verify-access")` next to
`dataset_add` (`cli.py:5538`):

```python
@dataset_group.command("verify-access")
@click.argument("ref")
@click.option("--level", type=click.Choice(["public","registration","controlled","commercial","mixed"]))
@click.option("--method", type=click.Choice(["retrieved", "credential-confirmed"]))
@click.option("--license", "license_", default=None)
@click.option("--by", "verified_by", default="agent (verify-access)")
@click.option("--source-url", default=None)
@click.option("--tier", type=click.Choice(["use-now","evaluate-next","track"]), default=None)
@click.option("--note", default="")
@click.option("--exception", type=click.Choice(["scope-reduced","expanded-to-acquire","substituted"]), default=None)
@click.option("--rationale", default="")
@click.option("--superseded-by", default=None)
@click.option("--followup-task", default=None)
@click.option("--project-root", default=None, type=click.Path(path_type=Path, file_okay=False, dir_okay=True))
def dataset_verify_access(...):
    """Verify (or exception-gate) a dataset's accessibility — sets origin/license/access together."""
    ...
    entity_id, dest, state, weight, warnings = verify_access(root, ref, ...)
    for w in warnings: click.echo(f"warning: {w}", err=True)
    click.echo(f"{entity_id} -> {state} (weight {weight:g})")
```

The weight comes back from the writer (which already computed it over the new frontmatter); the CLI
does not reach into `new_fm`, which isn't in its scope.

Map `EntityCommandError` → `click.echo(err=True)` + `Exit(1)` (as `dataset_add` does). Re-run T3 → green.

## T5 — Docs

- Update `plugin:science:catalog-datasets` SKILL Step 3 (Branch A and Branch B): replace the
  hand-edit instructions with `science dataset verify-access <slug> --method ... --license ...`
  (Branch A) and `... --exception ...` (Branch B), keeping the "append a body log line" outcome
  (now done by the command). Skill source lives under `~/d/science/plugins/.../catalog-datasets/`
  (or `skills/`); locate the actual `SKILL.md` and edit there.
- Add the command to any `dataset` help/overview in `docs/plans/2026-06-21-dataset-catalog-cli-design.md`
  if it enumerates subcommands.

## T6 — Verification

```bash
cd ~/d/science/science && uv run --frozen ruff check src/science_tool/datasets_catalog.py src/science_tool/cli.py tests/test_dataset_verify_access*.py
cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_verify_access.py tests/test_dataset_verify_access_cli.py tests/test_dataset_add_cli.py tests/test_datasets_validate.py -q
```

Then a real end-to-end smoke on a legacy entity (e.g. a `health-meta` dataset lacking `origin`):
`verify-access` it, then `uv run --frozen science validate` and `science dataset prioritize` and
confirm the entity moves to weight `1.0` with zero new warnings.
