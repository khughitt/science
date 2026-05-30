# Open feedback fixes — 2026-05-30

Implementation plan for the **3 open** items from today's `science feedback`
(items 001–007 were already addressed earlier today; their resolution commits
`1a3c6baa`, `837abff6`, `c399c99c`, `2b0ad5cf`, `f2c962ae` are all confirmed
ancestors of `main`).

User-confirmed scope: implement **008 + 010 + 009**, with **009 core-only**
(rename/disambiguate prompt option + non-interactive skip-and-continue; defer the
earlier `bib add` cross-project collision detection).

All paths are under `science/src/science_tool/`. Use TDD. Tests live in
`science/tests/`. Run the suite with `cd ~/d/science/science && uv run pytest`
(the `science` CLI entry point is `science_tool.cli:main`; importing the package
pulls heavy deps `ga4gh-vrs`/`hgvs`, so first import is slow — not hung).

Environment gotchas (see memory `project_shell_env_gotchas.md`): shell is zsh
(quote `--include='*.py'`), `find` is shimmed to `rtk` (avoid `-path`), prefer
foreground `rg`, scope scans (the repo root is a large Dropbox tree).

---

## fb-2026-05-30-008 — `science health` aborts on one malformed dataset
**target:** command:health · **category:** friction · **project:** meta

### Symptom
`science health --format=json` exits 1 with **empty stdout** when a single
dataset has `source_class: derived` but is missing the conditionally-required
`derived_kind`. The other ~22 findings are hidden; JSON consumers get a parse
error. stderr only: `schema validation failed for registered entity kind
'dataset' at <path>: ... source_class=derived requires derived_kind ...`.

### Confirmed locations
- Raise site: `graph/sources.py:316` —
  `f"schema validation failed for registered entity kind {kind!r} at {ref.path}: {details}"`
  (raised as `ValueError` during source loading).
- Existing precedent for catching this exact error string:
  `graph/paper_dataset_migration.py:322` —
  `if isinstance(exc, ValueError) and str(exc).startswith("schema validation failed for registered entity kind"): ...`
- Health entry: `cli.py:3612 health_command` → `cli.py:3646/3654 build_health_report(...)`.
- `graph/health.py:532 build_health_report` → `:553 _run_health_checks(context)`;
  sources come from `:361 _context_sources(context)` / the `HealthContext`.
- Severity-mapping helper already exists: `graph/health.py:424 _validation_health_severity`.

### Confirmed mechanism (read 2026-05-30)
Two collaborating facts:
1. `graph/sources.py:295-317` — when a **core** kind fails pydantic validation and
   it is *not* the missing-identity special case, the loader **hard-raises**
   `ValueError("schema validation failed for registered entity kind ...")`.
   (Profile kinds and missing-identity core entities instead append to
   `skipped_entities` and `continue` — that degrade path already exists.)
2. `cli.py:3644-3656` — `health_command` wraps `build_health_report(...)` in
   `except ValueError as exc: raise click.ClickException(str(exc)) from exc`.
   ClickException prints to **stderr** and exits 1 → in `--format=json` mode
   **stdout is empty** and the whole report is lost. `build_health_report`
   (`graph/health.py:550-551`) loads sources via
   `load_project_sources(project_root)`, which is where the raise originates.

Crucially the raise must stay for `science validate` / graph build (they *should*
fail on a schema-invalid core entity — the feedback itself notes "graph won't
build"). So the fix must be **scoped to health**, not a global softening of
`sources.py`.

### Fix approach (scoped, keeps validate strict)
Add a `strict_core_schema: bool = True` parameter to `load_project_sources` (and
the inner loop holding `sources.py:295-317`). When `False`, the core-kind
schema-failure branch appends a `SkippedEntity(reason="entity_schema_validation_failed")`
and `continue`s instead of raising — so the *rest* of the entities still load.
Then:
- `build_health_report` calls `load_project_sources(project_root, strict_core_schema=False)`.
- Health surfaces `sources.skipped_entities` whose `reason ==
  "entity_schema_validation_failed"` as findings (new code e.g.
  `entity.schema-invalid`, severity error), so the bad entity is still reported.
- Validate / graph keep the default `strict_core_schema=True` (unchanged hard fail).
- Defensive belt-and-braces: in `cli.py:3655`, only ClickException-wrap
  *non-schema* ValueErrors (or drop the wrap once health no longer raises).
- Bonus (cheap, requested): extend the `source-class-undeclared` advice text to
  note that `source_class: derived` additionally requires `derived_kind`.

### Tests
- `tests/` (likely `test_health*.py` or `graph` health tests): a project with one
  dataset `source_class: derived` and no `derived_kind` → `build_health_report`
  returns a report containing an `entity.schema-invalid` (or chosen code) finding
  AND the other findings; does NOT raise. Add a CLI-level test that
  `science health --format=json` produces parseable JSON (non-empty stdout).

---

## fb-2026-05-30-010 — symlink/realpath duplicate project auto-registration
**target:** command:commons · **category:** friction · **project:** cycles

### Symptom
A project reachable via both `~/d/health/processes/cycles` (a `~/d` symlink) and
`/mnt/ssd/Dropbox/health/processes/cycles` (realpath). Invoking `science` from the
realpath auto-registers a **second** `projects[]` entry with the same id `cycles`,
after which `commons promote` fails: `project id 'cycles' is ambiguous: 2
registered projects share it`. The duplicate reappears every invocation from the
realpath.

### Confirmed locations
- `registry/config.py` — module docstring line 1: "Global configuration and
  project auto-registration for Science multi-project sync."
- `:46 class RegisteredProject`, `:61 projects: list[RegisteredProject]`.
- Dedup/keep logic: `:90 kept: list[RegisteredProject] = []`,
  `:92 resolved = Path(project.path).expanduser().resolve()`.
- `:111 register_project` ("Register or refresh a project. Idempotent; uses
  resolved path."), `:113 resolved = str(project_root.resolve())`,
  `:132 cfg.projects.append(...)`.

### Confirmed mechanism (read 2026-05-30)
The function is `ensure_registered` (`registry/config.py:103-142`), NOT
`register_project`. The idempotency check at **`:116-117`** is a **raw string
compare**: `for project in cfg.projects: if project.path == resolved:` where
`resolved = str(project_root.resolve())` (`:113`). A previously-stored canonical
entry whose `path` is `/home/keith/d/...` (the documented `~/d` symlink form, not
the realpath) never string-equals the realpath `/mnt/ssd/Dropbox/...`, so the
match fails and `:132 cfg.projects.append(...)` adds a **second** entry with the
same id. Note `prune_missing_projects:92` already does the right thing
(`Path(project.path).expanduser().resolve()`); `ensure_registered` just doesn't.

### Fix (concrete patch for ensure_registered)
Match by **resolved** path, collapse any existing duplicates that resolve to the
same real path (self-heals the current broken state), and normalize the stored
path to the realpath:

```python
resolved_path = project_root.resolve()
resolved = str(resolved_path)
cfg = load_global_config(config_path)

matches = [p for p in cfg.projects
           if Path(p.path).expanduser().resolve() == resolved_path]
if matches:
    primary = matches[0]
    changed = False
    if len(matches) > 1:  # collapse symlink-alias duplicates
        cfg.projects = [p for p in cfg.projects
                        if p is primary
                        or Path(p.path).expanduser().resolve() != resolved_path]
        changed = True
    if primary.path != resolved:  # heal non-realpath stored path
        primary.path = resolved
        changed = True
    if project_id is not None and primary.id != project_id:
        primary.id = project_id; changed = True
    if role is not None and primary.role != role:
        primary.role = role; changed = True
    if parent is not _UNSET and primary.parent != parent:
        primary.parent = cast(str | None, parent); changed = True
    if changed:
        save_global_config(cfg, config_path)
    return
# else: append as today
```
(Optionally also `refuse-and-warn` if the same id maps to a *different* real path —
a genuine misconfiguration rather than a symlink alias.)

### Tests
- `tests/` (registry/config tests): registering the same project via two paths
  that resolve to the same realpath yields exactly one `projects[]` entry (no
  duplicate id). Simulate with a `tmp_path` real dir + a symlink to it; register
  from both; assert single entry. Add a guard that a colliding id with a
  different real path is refused/warned rather than appended.

---

## fb-2026-05-30-009 — commons promote can't disambiguate colliding citekeys (CORE)
**target:** command:commons · **category:** gap · **project:** cycles

### Symptom
Local `paper:Zeng2024` / `paper:Li2024` collide with **different** commons papers
sharing the same `FirstAuthorYear` citekey. `commons promote --apply` only offers
`[k]eep-existing-overlay` / `[a]bort` — both wrong when the entities are genuinely
different papers. In non-interactive runs (`</dev/null`) the whole batch aborts on
the first collision.

### Locations to confirm
The promote command + its conflict prompt were **not** surfaced by the initial
grep (which matched overlay code in `commons/cli.py` and `entities_inventory.py`).
Locate the promote implementation first:
- `cd science/src/science_tool/commons && ls` then
  `rg -n "promote|prompt|keep|abort|Choice|conflict|overlay_exists" .`
- Likely files: `commons/cli.py` (promote command) and a `commons/promote*.py` or
  `commons/overlay.py` helper that builds the canonical/overlay plan and applies
  it. Find the interactive prompt that currently presents keep/abort.

### Fix approach (core only)
1. **Add a `[r]ename / disambiguate` option** to the promote conflict prompt:
   when the colliding canonical entity is a *different* paper (e.g. different DOI),
   offer to promote under a disambiguated citekey (`Zeng2024` → `Zeng2024a`, next
   free suffix). Implement a small helper that, given a target key and the set of
   existing commons keys, returns the next free `<key><letter>` suffix; rewrite
   the candidate's id/citekey before promoting.
2. **Non-interactive skip-and-continue:** when stdin is not a TTY (or an
   explicit `--on-conflict=skip` / existing non-interactive flag), **skip the
   conflicting candidate and continue the batch** instead of aborting on the
   first collision. Emit a clear per-skip message and a final summary of skipped
   items (no silent truncation).

Defer (not in this round): cross-project collision detection at `bib add` /
cross-project registry build (the "full" option).

### Tests
- Promote helper unit test: next-free-suffix disambiguation
  (`Zeng2024` with `{Zeng2024}` present → `Zeng2024a`; with `{Zeng2024,
  Zeng2024a}` → `Zeng2024b`).
- Promote flow test (interactive simulated): a candidate colliding with a
  different-DOI canonical, choosing rename, promotes under the disambiguated key
  and leaves the existing canonical untouched.
- Non-interactive test: batch with one colliding candidate among several →
  conflicting one skipped, the rest promoted, exit code reflects partial success,
  summary lists the skip.

---

## Closeout (after each fix lands, TDD-green)
Mark items addressed via the feedback CLI (entries live in
`~/.config/science/feedback/fb-2026-05-30-0XX.yaml`):

```
science feedback update fb-2026-05-30-008 --status addressed --resolution "..."
science feedback update fb-2026-05-30-009 --status addressed --resolution "..."   # note: core only; full detection deferred
science feedback update fb-2026-05-30-010 --status addressed --resolution "..."
```
(`update` requires `--resolution` when setting status to addressed — see
`feedback.py:update_entry`.) Then run the full suite green and commit on a
`fix/feedback-2026-05-30-open` branch.
