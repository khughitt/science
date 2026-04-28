# Validate.sh Hook Points — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realize the hook contract on `data/validate.sh` per `docs/superpowers/specs/2026-04-27-validate-hook-points.md`. Add three named dispatch points (`pre_validation`, `extra_checks`, `post_validation`), bump the canonical version `2026.04.26.1 → 2026.04.26.2`, dogfood the managed-artifact update workflow.

**Tech stack:** Bash for the canonical. Python (pytest) for tests. YAML for the registry. `uv` for everything Python.

---

## File Structure

### Create

- `science-tool/tests/test_validate_hook_points.py` — exercises each hook point fires once, in order, and that `post_validation` fires on both success and failure paths.

### Modify

- `science-tool/src/science_tool/project_artifacts/data/validate.sh` — insert three dispatch points; pre-validation right before section 1; extra-checks right before the summary banner; post-validation via `trap '...' EXIT` set after the sidecar source.
- `science-tool/src/science_tool/project_artifacts/registry.yaml` — bump `version`, recompute `current_hash`, move old hash into `previous_hashes`, append `migrations` entry, append changelog entry, update `extension_protocol.contract` enumerating the three hook points.

### Tests already in place that must continue passing

- `science-tool/tests/test_initial_validate_sh.py` — header + body integrity.
- `science-tool/tests/test_first_version_bump.py` — registry shape (must update assertion for new version).
- `science-tool/tests/test_extensions_validate_hooks.py` — Task 27 hook-infrastructure tests.
- `science-tool/tests/test_acceptance_managed_artifacts.py` — full lifecycle + shim equivalence.

---

## Phase organization

| Phase | Theme | Tasks | Output |
|------:|---|---|---|
| A1 | Add dispatch points to canonical body | T1 | Three `dispatch_hook` call sites + `trap` set up |
| A2 | Bump canonical version + registry update | T2 | v2026.04.26.2 registered, hash + history correct |
| A3 | Acceptance test for hook contract | T3 | `test_validate_hook_points.py` exercises full contract |
| A4 | Cross-references | T4 | Spec note + migration-guide unblock |

Phases run sequentially. Each ends in commits and a passing test suite.

---

## Tasks

### Phase A1 — Add dispatch points to canonical body

### Task 1: Insert three hook dispatch points

**Files:**
- Modify: `science-tool/src/science_tool/project_artifacts/data/validate.sh`

This task does NOT bump the version yet (Task 2 does that, after the new body hash is computable). For the duration of this task the registry's `current_hash` will mismatch the canonical body hash; that's expected and acknowledged by the test in Step 5 below.

- [ ] **Step 1: Locate the three insertion points by content marker (not line number)**

The canonical's structure is stable enough to locate by markers:
- `pre_validation` insertion: between the line `echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"` (the banner closing line, immediately before section 1) and `# ─── 1. Project manifest ───`.
- `extra_checks` insertion: between the last canonical-section's last line and `# ─── Summary ─────────────────────────────────────────────────────`.
- `post_validation` (trap setup): immediately after the existing `if [[ -f "validate.local.sh" ]]; then ... source "validate.local.sh"; fi` block in the hook-infrastructure section, BEFORE the `# === canonical body ===` banner. The trap must be set after the sidecar is sourced so any hooks the sidecar registers are visible to the trap target.

Verify each marker is unique (the script only has one banner, one summary, one sidecar-source block):

```bash
grep -n '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' science-tool/src/science_tool/project_artifacts/data/validate.sh
grep -n '# ─── Summary' science-tool/src/science_tool/project_artifacts/data/validate.sh
grep -n 'source "validate.local.sh"' science-tool/src/science_tool/project_artifacts/data/validate.sh
```

Each should return either one match or a small fixed number that the patch script disambiguates by surrounding context.

- [ ] **Step 2: Write the failing test**

Create `science-tool/tests/test_validate_hook_points.py`:

```python
"""Hook dispatch points exist in the canonical and fire in the documented order."""
from importlib import resources
from pathlib import Path


def _canonical_path() -> Path:
    files = resources.files("science_tool.project_artifacts")
    with resources.as_file(files / "data" / "validate.sh") as p:
        return Path(p)


def test_canonical_dispatches_pre_validation_once() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert text.count('dispatch_hook "pre_validation"') == 1, (
        "expected exactly one pre_validation dispatch site in the canonical"
    )


def test_canonical_dispatches_extra_checks_once() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert text.count('dispatch_hook "extra_checks"') == 1, (
        "expected exactly one extra_checks dispatch site in the canonical"
    )


def test_canonical_traps_post_validation_on_exit() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    assert "trap 'dispatch_hook post_validation' EXIT" in text, (
        "expected EXIT trap dispatching post_validation"
    )


def test_pre_validation_fires_before_section_1() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    pre_pos = text.find('dispatch_hook "pre_validation"')
    sec1_pos = text.find('# ─── 1. Project manifest')
    assert pre_pos > 0 and sec1_pos > 0, "missing markers"
    assert pre_pos < sec1_pos, "pre_validation must dispatch before section 1"


def test_extra_checks_fires_before_summary() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    extra_pos = text.find('dispatch_hook "extra_checks"')
    summary_pos = text.find('# ─── Summary')
    assert extra_pos > 0 and summary_pos > 0, "missing markers"
    assert extra_pos < summary_pos, "extra_checks must dispatch before the summary"


def test_post_validation_trap_set_after_sidecar_source() -> None:
    text = _canonical_path().read_text(encoding="utf-8")
    sidecar_pos = text.find('source "validate.local.sh"')
    trap_pos = text.find("trap 'dispatch_hook post_validation' EXIT")
    assert sidecar_pos > 0 and trap_pos > 0, "missing markers"
    assert trap_pos > sidecar_pos, (
        "EXIT trap must be set AFTER sidecar source so registered hooks are visible"
    )
```

- [ ] **Step 3: Run test to verify it fails**

```
uv run --project science-tool pytest science-tool/tests/test_validate_hook_points.py -v
```

Expected: 6 failures (the dispatch sites and trap don't exist yet).

- [ ] **Step 4: Apply the three insertions**

Edit `science-tool/src/science_tool/project_artifacts/data/validate.sh` to add:

**(a) After the sidecar-source block, before `# === canonical body ===`:**

```bash
# Trap post_validation hooks so they fire on every exit path
# (success, failure, signal). Set AFTER sidecar source so any hooks
# the sidecar registered are visible.
trap 'dispatch_hook post_validation' EXIT
```

**(b) Immediately before `# ─── 1. Project manifest ───`:**

```bash
# Hook point: pre_validation. Fires after helpers and banner are set up,
# before any canonical-section runs.
dispatch_hook "pre_validation"

```

**(c) Immediately before `# ─── Summary ─────────────────────────────────────────────────────`:**

```bash
# Hook point: extra_checks. Fires after all canonical sections complete,
# before the pass/fail summary. Use for project-specific structural checks.
dispatch_hook "extra_checks"

```

- [ ] **Step 5: Run the new test to verify it passes**

```
uv run --project science-tool pytest science-tool/tests/test_validate_hook_points.py -v
```

Expected: 6 passed.

The body-hash-mismatch test in `test_initial_validate_sh.py::test_current_hash_matches_body` and the version assertion in `test_first_version_bump.py::test_registry_has_two_versions` will now FAIL because the canonical body changed but the registry hasn't bumped yet. This is expected — Task 2 fixes both.

- [ ] **Step 6: Quality gates (no commit yet — Task 2 commits both phases together)**

```
uv run --project science-tool ruff check science-tool/tests/test_validate_hook_points.py
uv run --project science-tool ruff format science-tool/tests/test_validate_hook_points.py
```

Expected: clean.

- [ ] **Step 7: Verify the canonical still runs**

Smoke-test against a synthetic minimal project to confirm the dispatch calls don't break a sidecar-less invocation:

```bash
TMP=$(mktemp -d)
cd "$TMP"
cat > science.yaml <<'YAML'
name: smoke
created: "2026-04-27"
last_modified: "2026-04-27"
status: "active"
summary: "smoke"
profile: software
layout_version: 2
knowledge_profiles:
  local: local
YAML
touch AGENTS.md CLAUDE.md
mkdir -p doc specs tasks knowledge src
echo "<!-- tasks -->" > tasks/active.md

bash /mnt/ssd/Dropbox/science/science-tool/src/science_tool/project_artifacts/data/validate.sh
echo "exit code: $?"
```

Expected: a normal validate.sh run (may emit warnings on a minimal project — that's fine; the point is no syntax error from the new dispatch lines).

---

### Phase A2 — Bump canonical version + registry update

### Task 2: Bump version 2026.04.26.1 → 2026.04.26.2

**Files:**
- Modify: `science-tool/src/science_tool/project_artifacts/data/validate.sh` (header version + hash)
- Modify: `science-tool/src/science_tool/project_artifacts/registry.yaml`
- Modify: `science-tool/tests/test_first_version_bump.py` (assertion update for new version)

This task is the dogfood: the registry workflow itself is exercised on its own canonical.

- [ ] **Step 1: Compute the new body hash and update the canonical's header**

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

new = re.sub(
    rb"# science-managed-version: \S+\n",
    b"# science-managed-version: 2026.04.26.2\n",
    raw,
    count=1,
)
new = re.sub(
    rb"# science-managed-source-sha256: \S+\n",
    f"# science-managed-source-sha256: {new_hash}\n".encode(),
    new,
    count=1,
)
p.write_bytes(new)
PY
```

Capture the printed hash; you'll paste it into the registry next.

- [ ] **Step 2: Update `registry.yaml`**

Edit `science-tool/src/science_tool/project_artifacts/registry.yaml`:

- Move the existing `current_hash` (the v2026.04.26.1 hash, currently `31ca36b395f4714842b2263844fe924f73ce1bb922bc3fb002ee6dc25d5ed8f4`) into a new entry in `previous_hashes`:

  ```yaml
  previous_hashes:
    - version: '2026.04.26'
      hash: f4596de3e9b2696066097621d5aef5606f247d144c5530409433427949c830d1
    - version: '2026.04.26.1'
      hash: 31ca36b395f4714842b2263844fe924f73ce1bb922bc3fb002ee6dc25d5ed8f4
  ```

- Set `current_hash` to the new value from Step 1.
- Set `version` to `'2026.04.26.2'`.
- Append to `migrations`:

  ```yaml
    - from: '2026.04.26.1'
      to: '2026.04.26.2'
      kind: byte_replace
      summary: 'Add named hook dispatch points (pre_validation / extra_checks / post_validation).'
      steps: []
  ```

- Append to `changelog`:

  ```yaml
    '2026.04.26.2': 'Add named hook dispatch points; the sourced_sidecar extension protocol is now functional end-to-end.'
  ```

- Update `extension_protocol.contract` to enumerate the three hook points:

  ```yaml
    extension_protocol:
      kind: sourced_sidecar
      sidecar_path: validate.local.sh
      hook_namespace: SCIENCE_VALIDATE_HOOKS
      contract: |
        Sidecar registers hooks via `register_validation_hook <hook> <fn>`.
        Canonical sources sidecar BEFORE validation runs, then dispatches at:
          - pre_validation: after helpers + banner, before section 1.
          - extra_checks: after all canonical sections, before the summary.
          - post_validation: at process exit (trap EXIT), regardless of pass/fail.
        Hooks see all helpers and globals (PROFILE, ERRORS, WARNINGS).
        See docs/superpowers/specs/2026-04-27-validate-hook-points.md.
  ```

- [ ] **Step 3: Update `test_first_version_bump.py` for the new version**

Replace `2026.04.26.1` with `2026.04.26.2` and update the previous-hashes assertions:

```python
def test_registry_has_two_versions() -> None:
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    assert len(art.previous_hashes) >= 2  # was >= 1
    assert art.version == "2026.04.26.2"  # was 2026.04.26.1
    assert art.previous_hashes[-1].version == "2026.04.26.1"  # was 2026.04.26


def test_byte_replace_migration_recorded() -> None:
    reg = load_packaged_registry()
    art = next(a for a in reg.artifacts if a.name == "validate.sh")
    bump = next(m for m in art.migrations if m.to_version == "2026.04.26.2")  # was .1
    assert bump.kind.value == "byte_replace"
    assert bump.steps == []
    assert "hook" in bump.summary.lower()  # was "Plan #7"
```

(Also rename the file conceptually — `test_first_version_bump.py` is now misleading since this is the second bump. Rename to `test_version_bump_history.py`. Optional but recommended; the test file is small.)

- [ ] **Step 4: Run all version-related and integrity tests**

```
uv run --project science-tool pytest \
  science-tool/tests/test_initial_validate_sh.py \
  science-tool/tests/test_first_version_bump.py \
  science-tool/tests/test_validate_hook_points.py \
  science-tool/tests/test_extensions_validate_hooks.py \
  science-tool/tests/test_registry_loader.py \
  -v
```

Expected: all green.

- [ ] **Step 5: Quality gates**

```
uv run --project science-tool ruff check science-tool/
uv run --project science-tool ruff format science-tool/
uv run --project science-tool pyright science-tool/src/science_tool/project_artifacts/
```

Expected: clean.

- [ ] **Step 6: Commit (Task 1 + Task 2 together; the two are atomically meaningful)**

```bash
git add science-tool/src/science_tool/project_artifacts/data/validate.sh \
        science-tool/src/science_tool/project_artifacts/registry.yaml \
        science-tool/tests/test_validate_hook_points.py \
        science-tool/tests/test_first_version_bump.py
git commit -m "feat(project-artifacts): version bump 2026.04.26.1 -> 2026.04.26.2 (hook dispatch)

Adds three named hook dispatch points to the canonical:
  - pre_validation: before section 1.
  - extra_checks:   after all sections, before summary.
  - post_validation: trap EXIT, fires on every exit path.

The sourced_sidecar extension protocol is now functional end-to-end:
sidecars can register hooks via register_validation_hook and have them
fire at the documented points. Updates registry: moves prior hash into
previous_hashes, adds byte_replace migration, refreshes contract field.

Per docs/superpowers/specs/2026-04-27-validate-hook-points.md."
```

---

### Phase A3 — Acceptance test for the hook contract

### Task 3: End-to-end hook lifecycle test

**Files:**
- Create / extend: `science-tool/tests/test_validate_hook_points.py` (the file from Task 1; this task adds the integration test).

This task executes the canonical against a synthetic project with a sidecar that registers one hook per dispatch point and proves all three fire, in order, including on failure paths.

- [ ] **Step 1: Add the integration tests to the existing `test_validate_hook_points.py`**

Append:

```python
import os
import subprocess
import sys
import textwrap
from pathlib import Path


def _scaffold_minimal_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        textwrap.dedent(
            """\
            name: hooktest
            created: "2026-04-27"
            last_modified: "2026-04-27"
            status: "active"
            summary: "hooktest"
            profile: software
            layout_version: 2
            knowledge_profiles:
              local: local
            """
        ),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text("# Hooktest\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    for d in ("doc", "specs", "tasks", "knowledge", "src"):
        (root / d).mkdir()
    (root / "tasks" / "active.md").write_text("<!-- tasks -->\n", encoding="utf-8")


def _run_canonical(project: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    canonical = _canonical_path()
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", str(canonical)],
        cwd=project,
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_all_three_hook_points_fire_in_order(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    _scaffold_minimal_project(project)
    log = project / "hook-log.txt"

    (project / "validate.local.sh").write_text(
        textwrap.dedent(
            f"""\
            on_pre()  {{ echo pre  >> "{log}"; }}
            on_extra(){{ echo extra >> "{log}"; }}
            on_post() {{ echo post >> "{log}"; }}
            register_validation_hook pre_validation on_pre
            register_validation_hook extra_checks   on_extra
            register_validation_hook post_validation on_post
            """
        ),
        encoding="utf-8",
    )

    result = _run_canonical(project)
    assert log.exists(), f"no hook log written; canonical output:\n{result.stdout}\n{result.stderr}"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines == ["pre", "extra", "post"], f"unexpected hook firing order: {lines}"


def test_post_validation_fires_when_extra_checks_fails(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    _scaffold_minimal_project(project)
    log = project / "hook-log.txt"

    (project / "validate.local.sh").write_text(
        textwrap.dedent(
            f"""\
            on_extra(){{ echo extra >> "{log}"; exit 99; }}
            on_post() {{ echo post  >> "{log}"; }}
            register_validation_hook extra_checks    on_extra
            register_validation_hook post_validation on_post
            """
        ),
        encoding="utf-8",
    )

    result = _run_canonical(project)
    assert result.returncode == 99, f"expected exit 99 from extra_checks; got {result.returncode}"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines == ["extra", "post"], f"post_validation must still fire on failure; got: {lines}"


def test_multiple_hooks_per_point_dispatch_in_registration_order(tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    _scaffold_minimal_project(project)
    log = project / "hook-log.txt"

    (project / "validate.local.sh").write_text(
        textwrap.dedent(
            f"""\
            a(){{ echo a >> "{log}"; }}
            b(){{ echo b >> "{log}"; }}
            c(){{ echo c >> "{log}"; }}
            register_validation_hook pre_validation a
            register_validation_hook pre_validation b
            register_validation_hook pre_validation c
            """
        ),
        encoding="utf-8",
    )

    _run_canonical(project)
    assert log.read_text(encoding="utf-8").splitlines() == ["a", "b", "c"]
```

- [ ] **Step 2: Run the new tests**

```
uv run --project science-tool pytest science-tool/tests/test_validate_hook_points.py -v
```

Expected: 9 passed (6 from Task 1 + 3 new integration tests).

- [ ] **Step 3: Run the entire suite**

```
uv run --project science-tool pytest --ignore=meta/tests 2>&1 | tail -10
```

Expected: prior baseline (5 pre-existing failures) + new tests passing. No new failures.

- [ ] **Step 4: Quality gates + commit**

```bash
uv run --project science-tool ruff check science-tool/tests/test_validate_hook_points.py
uv run --project science-tool ruff format science-tool/tests/test_validate_hook_points.py

git add science-tool/tests/test_validate_hook_points.py
git commit -m "test(project-artifacts): end-to-end hook dispatch contract

Exercises the three hook points (pre_validation / extra_checks /
post_validation) by invoking the canonical against a synthetic project
with a sidecar. Verifies firing order, multi-hook-per-point ordering,
and that post_validation fires even when extra_checks fails (trap EXIT
contract). Per spec acceptance criterion 5."
```

---

### Phase A4 — Cross-references

### Task 4: Update prior spec + plan with the hook-contract closure

**Files:**
- Modify: `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md` — note that the hook contract is now functional as of 2026.04.26.2.
- Modify: `docs/superpowers/plans/2026-04-26-managed-artifacts-implementation.md` — append a "Post-implementation: hook dispatch points" status note.

- [ ] **Step 1: Add a status note to the parent spec**

Open `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md`. In the section that defines the `sourced_sidecar` extension protocol (search for "sourced_sidecar"), append:

> **Hook dispatch implementation:** The `register_validation_hook` API and the `dispatch_hook` infrastructure shipped in v2026.04.26 (Task 27 / Task 28). Concrete dispatch *call sites* in the canonical body landed in v2026.04.26.2 per `docs/superpowers/specs/2026-04-27-validate-hook-points.md` (`pre_validation`, `extra_checks`, `post_validation`).

- [ ] **Step 2: Add a status note to the parent plan**

Open `docs/superpowers/plans/2026-04-26-managed-artifacts-implementation.md`. At the very bottom, before the `> **End of plan.**` line, append:

> ## Post-implementation follow-ups
>
> - **Hook dispatch points landed.** The hook contract was wired structurally in T27/T28 but no `dispatch_hook` calls fired from the canonical body. Resolved in `docs/superpowers/plans/2026-04-27-validate-hook-points-implementation.md` with version bump to 2026.04.26.2.
> - **`Snapshot.restore()` idempotent.** Latent ManifestSnapshot double-restore noted during Phase 8 review fixed in commit `fb9c1cd`.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md \
        docs/superpowers/plans/2026-04-26-managed-artifacts-implementation.md
git commit -m "docs(specs): note hook-dispatch closure and Snapshot idempotency

Cross-references the validate-hook-points spec (2026-04-27) and the
post-acceptance Snapshot.restore() idempotency fix from the
managed-artifacts implementation."
```

---

## Cross-cutting conventions

- **TDD per task.** Each behavior change: failing test → run-fail → minimal implementation → run-pass → commit.
- **Commit messages.** `feat(project-artifacts): <what>` for canonical changes; `test(project-artifacts): <what>` for test-only commits; `docs(specs): <what>` for spec/plan updates. Body cites the spec.
- **Quality gates.** `ruff check` + `ruff format` + `pyright` clean before each commit.
- **No legacy compat.** No "support both old and new" branches; the canonical body simply gains three lines and one trap.
- **Type hints required** on Python; modern style (`X | None`, `list[X]`).
- **`uv run --project science-tool`** from repo root for all Python invocations.

---

## Sequencing dependencies

```
T1 ─ T2 ─ T3 ─ T4
```

T1 inserts dispatch points without bumping the registry; the canonical's header hash and registry's `current_hash` are deliberately out of sync between T1 and T2 (and T1 leaves two existing tests temporarily failing). T2 closes the loop. T3 proves the contract end-to-end. T4 updates the upstream spec/plan to reflect the closure.

---

## What this displaces

- The "future-tense hook capability" implication in `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md`. After this plan lands, hooks are present-tense.
- Unblocks the four-project rollout planned in `docs/migration/2026-04-27-managed-artifacts-rollout.md` (forthcoming; depends on this plan landing first).

---

## Self-review

**Spec coverage** — every acceptance criterion in `docs/superpowers/specs/2026-04-27-validate-hook-points.md` maps to a task:

| Spec acceptance | Task |
|---|---|
| #1 (one dispatch site each + trap) | T1 (asserted by `test_canonical_dispatches_*` and `test_canonical_traps_post_validation_on_exit`) |
| #2 (pre_validation before section 1) | T1 (`test_pre_validation_fires_before_section_1`) |
| #3 (extra_checks before summary) | T1 (`test_extra_checks_fires_before_summary`) |
| #4 (post_validation on every exit path) | T3 (`test_post_validation_fires_when_extra_checks_fails`) |
| #5 (firing order, multi-hook ordering, post_validation on failure) | T3 (all three integration tests) |
| #6 (current_hash matches body) | T2 (existing `test_current_hash_matches_body`) |
| #7 (migrations entry present) | T2 (`test_byte_replace_migration_recorded`, updated for .2) |
| #8 (extension_protocol.contract enumerates hooks) | T2 (Step 2 explicit edit) |
| #9 (existing tests pass) | T2 Step 4, T3 Step 3 |
| #10 (acceptance sidecar test) | T3 (`test_all_three_hook_points_fire_in_order`) |

**Type / name consistency** — `dispatch_hook`, `register_validation_hook`, `SCIENCE_VALIDATE_HOOKS` all defined in v2026.04.26 (Task 27); referenced consistently. New names introduced this plan: `pre_validation`, `extra_checks`, `post_validation` — consistent across spec, registry contract field, canonical body, and tests.

---

> **End of plan.** Implementation can proceed via `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` (inline). Estimated 4 tasks; phases A1-A4 sequential per the dependency graph.
