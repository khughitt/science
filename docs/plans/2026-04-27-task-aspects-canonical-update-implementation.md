# Task-aspects canonical update — Implementation Plan

**Goal:** Land v2026.04.26.3 of the canonical `validate.sh` per `docs/superpowers/specs/2026-04-27-task-aspects-canonical-update.md`. Single-line canonical change + version bump + propagate to the three already-migrated projects.

---

## File Structure

### Modify

- `science-tool/src/science_tool/project_artifacts/data/validate.sh` — change `for field in type priority status created` to `for field in aspects priority status created`. Bump header `science-managed-version` and `science-managed-source-sha256`.
- `science-tool/src/science_tool/project_artifacts/registry.yaml` — bump `version`, recompute `current_hash`, append `2026.04.26.2` to `previous_hashes`, append `byte_replace` migration .2 → .3, append changelog.
- `science-tool/tests/test_first_version_bump.py` — update version assertions to `2026.04.26.2` (the now-previous) and `2026.04.26.3` (the new current).
- Each downstream project's installed `validate.sh` is refreshed via the `update` verb (no per-project plan files).

### Create

None.

---

## Tasks

### Task 1: Canonical change + version bump

**Files:** `data/validate.sh`, `registry.yaml`, `test_first_version_bump.py`.

- [ ] **Step 1: Update the test assertions** (TDD: tests fail until the canonical bumps).

```python
# test_first_version_bump.py — update assertions
def test_registry_has_two_versions() -> None:
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    assert len(art.previous_hashes) >= 3   # was >= 2
    assert art.version == "2026.04.26.3"   # was 2026.04.26.2
    assert art.previous_hashes[-1].version == "2026.04.26.2"  # was .1


def test_byte_replace_migration_recorded() -> None:
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    bump = next(m for m in art.migrations if m.to_version == "2026.04.26.3")
    assert bump.kind.value == "byte_replace"
    assert bump.steps == []
    assert "aspects" in bump.summary.lower()
```

(Also update the in-file fixture's `# science-managed-version: 2026.04.26.1` line to `2026.04.26.2`, since `previous_hashes[-1]` will be the .2 entry post-bump.)

- [ ] **Step 2: Run tests to verify they fail**

```
uv run --project science-tool pytest science-tool/tests/test_first_version_bump.py -v
```

Expected: 2-3 failures (version mismatch).

- [ ] **Step 3: Apply the canonical edit**

Locate the task-field block in `data/validate.sh` (around line 844). It looks like:

```bash
for field in type priority status created; do
```

Replace with:

```bash
for field in aspects priority status created; do
```

That is the entire substantive change. Verify by `grep -n "for field in.*priority status" data/validate.sh` returns one line containing `aspects priority status created`.

- [ ] **Step 4: Recompute body hash and update header**

```bash
python3 - <<'PY'
from pathlib import Path
import re

from science_tool.project_artifacts.hashing import body_hash
from science_tool.project_artifacts.registry_schema import HeaderKind, HeaderProtocol

p = Path("science-tool/src/science_tool/project_artifacts/data/validate.sh")
proto = HeaderProtocol(kind=HeaderKind.SHEBANG_COMMENT, comment_prefix="#")
raw = p.read_bytes()
new_hash = body_hash(raw, proto)
print("new body hash:", new_hash)

new = re.sub(rb"# science-managed-version: \S+\n",
             b"# science-managed-version: 2026.04.26.3\n", raw, count=1)
new = re.sub(rb"# science-managed-source-sha256: \S+\n",
             f"# science-managed-source-sha256: {new_hash}\n".encode(), new, count=1)
p.write_bytes(new)
PY
```

Capture the printed hash.

- [ ] **Step 5: Update registry.yaml**

- Append the v2026.04.26.2 hash (`9d6a34869403411d42cefd0fb7f6a2e433320329d2e8f2da244c2171878eb136`) to `previous_hashes`.
- Set `current_hash` to the new hash from Step 4.
- Set `version` to `'2026.04.26.3'`.
- Append migration:

  ```yaml
    - from: '2026.04.26.2'
      to: '2026.04.26.3'
      kind: byte_replace
      summary: 'Task field check: type -> aspects (per 2026-04-19-entity-aspects-design.md).'
      steps: []
  ```

- Append changelog:

  ```yaml
    '2026.04.26.3': 'Replace deprecated `type:` task-field check with `aspects:` per 2026-04-19-entity-aspects-design.md.'
  ```

- [ ] **Step 6: Run tests**

```
uv run --project science-tool pytest \
    science-tool/tests/test_initial_validate_sh.py \
    science-tool/tests/test_first_version_bump.py \
    science-tool/tests/test_validate_hook_points.py \
    science-tool/tests/test_extensions_validate_hooks.py \
    -v
```

Expected: all pass.

- [ ] **Step 7: Quality gates + commit**

```
uv run --project science-tool ruff check science-tool/
uv run --project science-tool ruff format --check science-tool/
uv run --project science-tool pyright science-tool/src/science_tool/project_artifacts/

git add science-tool/src/science_tool/project_artifacts/data/validate.sh \
        science-tool/src/science_tool/project_artifacts/registry.yaml \
        science-tool/tests/test_first_version_bump.py
git commit -m "feat(project-artifacts): version bump 2026.04.26.2 -> 2026.04.26.3 (task aspects)

Replaces canonical task-field check 'type' with 'aspects' per
docs/specs/2026-04-19-entity-aspects-design.md. All four reference
projects had migrated their tasks to 'aspects:' during the entity-
aspects rollout, but the canonical validator was never updated to
match — every task was failing with 'missing required field: type'.

Per docs/superpowers/specs/2026-04-27-task-aspects-canonical-update.md."
```

---

### Task 2: Cross-project propagation

After the canonical lands, the three migrated projects need a refresh. This task exercises the `update --force --yes` workflow across multiple projects.

For each of `mm30`, `cbioportal`, `natural-systems`:

- [ ] **Step 1: Verify drift status**

```bash
cd <project-root>
uv run --project ~/d/science/science-tool \
    science-tool project artifacts check validate.sh --project-root .
```

Expected: `stale (1 version behind)`.

- [ ] **Step 2: Update**

```bash
uv run --project ~/d/science/science-tool \
    science-tool project artifacts update validate.sh \
    --project-root . --force --yes
```

Expected: a `chore(artifacts): refresh validate.sh to 2026.04.26.3` commit on the project's branch.

- [ ] **Step 3: Verify**

```bash
uv run --project ~/d/science/science-tool \
    science-tool project artifacts check validate.sh --project-root .
# expected: current  (validate.sh @ 2026.04.26.3)

bash validate.sh 2>&1 | tail -3
# expected: lower error count than the v.2 smoke-run.
```

- [ ] **Step 4: Capture before/after error counts in the project's migration spec**

Append a "v2026.04.26.3 update" decision-log entry to each project's `doc/plans/2026-04-27-managed-artifacts-migration.md`:

```markdown
- **2026-04-27 (later)**: updated to v2026.04.26.3 via `science-tool project artifacts update --force --yes`. Smoke-run error count dropped from N to M (mostly task-aspects errors resolved by the canonical's task-field fix).
```

---

## Sequencing

```
T1 ─ T2 (mm30) ─ T2 (cbioportal) ─ T2 (natural-systems)
```

T2's three project updates can run in any order; pick the simplest first as proof and proceed if it works.

## What this does NOT do

- Does not migrate `protein-landscape` — that's the next migration spec, gated on this canonical landing first.
- Does not address `workflow/Snakefile` or `meta:` xref handling — separate decisions per the migration analysis.
- Does not touch `science-tool health`'s legacy-`type:` flagging — that's the 2026-04-19 spec's responsibility.

## Cross-references

- Spec: `docs/superpowers/specs/2026-04-27-task-aspects-canonical-update.md`
- Underlying convention: `docs/specs/2026-04-19-entity-aspects-design.md`
- Predecessor canonical bump: `docs/superpowers/plans/2026-04-27-validate-hook-points-implementation.md` (.1 → .2)
