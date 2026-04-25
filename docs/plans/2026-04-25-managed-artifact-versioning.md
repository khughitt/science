# Managed Artifact Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit version, drift-check, diff, and update support for copied Science-managed artifacts, starting with `validate.sh`.

**Architecture:** Add a small `science_tool.project_artifacts` module that owns the artifact registry, status classification, canonical content rendering, and update operations. Expose it through `science-tool project artifacts check|diff|update`, then update project creation/import docs to use the managed artifact path. Keep project-owned files, generated files, runtime-resolved commands/skills/templates, and package dependencies outside this updater.

**Tech Stack:** Python >=3.11, Click, pathlib, dataclasses, pytest, Bash for `validate.sh`, Markdown docs.

---

## File Structure

Create:

- `science-tool/src/science_tool/project_artifacts/__init__.py` — public exports for artifact status/check/update helpers.
- `science-tool/src/science_tool/project_artifacts/artifacts.py` — artifact definitions, canonical content loading, hash calculation, and status classification.
- `science-tool/src/science_tool/project_artifacts/data/validate.sh` — packaged canonical managed validator content.
- `science-tool/tests/test_project_artifacts.py` — unit tests for status classification, diff output, JSON payloads, update refusal, and canonical source sync.

Modify:

- `science-tool/src/science_tool/cli.py` — add `science-tool project artifacts check|diff|update` commands under the existing `project` group.
- `science-tool/src/science_tool/graph/health.py` — include managed artifact status in `science-tool health` reports.
- `science-tool/tests/test_health.py` — health-report integration test for managed artifact drift.
- `scripts/validate.sh` — add the managed artifact header.
- `commands/create-project.md` — replace bare copy instructions with managed artifact install/update instructions.
- `commands/import-project.md` — same managed artifact instruction update.
- `commands/status.md` — surface stale managed artifacts from `science-tool health` output.
- `commands/next-steps.md` — recommend managed artifact update when `science-tool health` reports stale artifacts.
- `README.md` — mention copied managed artifact checks in project validation/versioning guidance.
- `docs/project-organization-profiles.md` — replace "Refresh `validate.sh`" with the explicit managed-artifact check/update workflow.
- `science-tool/pyproject.toml` — include packaged artifact data if package data is not already included broadly.

Do not modify project-owned files such as `science.yaml`, `AGENTS.md`, `.ai/**`, `doc/**`, `specs/**`, `tasks/**`, or `knowledge/sources/**` in this implementation.

---

## Task 1: Add Managed Header To Canonical Validator

**Files:**

- Modify: `scripts/validate.sh`

- [ ] **Step 1: Add the header immediately after the shebang**

Edit `scripts/validate.sh` so the top of the file is:

```bash
#!/usr/bin/env bash
# science-managed-artifact: validate.sh
# science-managed-version: 2026.04.25
# science-managed-source-sha256: computed-by-science-tool
# validate.sh — Structural validation for Science research projects
```

The sentinel value `computed-by-science-tool` is intentional in the canonical file body; `science-tool` computes the real content hash while ignoring the hash line.

- [ ] **Step 2: Verify the script still parses**

Run:

```bash
bash -n scripts/validate.sh
```

Expected: exit code `0`, no output.

- [ ] **Step 3: Verify validator tests do not depend on old header position**

Run:

```bash
rg -n "validate\\.sh|Structural validation|shebang|line 1|first comment" science-tool/tests/test_validate_script.py
```

Expected: no assertions that depend on the old top-of-file comment layout. Existing tests should execute the script behaviorally through `subprocess.run`.

- [ ] **Step 4: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat(project-artifacts): mark validator as managed"
```

---

## Task 2: Package Canonical Validator Content

**Files:**

- Create: `science-tool/src/science_tool/project_artifacts/__init__.py`
- Create: `science-tool/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science-tool/pyproject.toml`

- [ ] **Step 1: Create the package directory**

Run:

```bash
mkdir -p science-tool/src/science_tool/project_artifacts/data
```

- [ ] **Step 2: Copy the canonical validator into package data**

Run:

```bash
cp scripts/validate.sh science-tool/src/science_tool/project_artifacts/data/validate.sh
```

- [ ] **Step 3: Add module marker**

Create `science-tool/src/science_tool/project_artifacts/__init__.py`:

```python
"""Managed copied artifacts for Science projects."""

from science_tool.project_artifacts.artifacts import (
    ArtifactDefinition,
    ArtifactStatus,
    ArtifactStatusReport,
    check_artifact,
    check_artifacts,
    diff_artifact,
    update_artifact,
)

__all__ = [
    "ArtifactDefinition",
    "ArtifactStatus",
    "ArtifactStatusReport",
    "check_artifact",
    "check_artifacts",
    "diff_artifact",
    "update_artifact",
]
```

- [ ] **Step 4: Ensure package data is included**

Add the managed validator package-data entry under the existing `[tool.hatch.build.targets.wheel.force-include]` table in `science-tool/pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/science_tool/dag/edges.schema.json" = "science_tool/dag/edges.schema.json"
"src/science_tool/project_artifacts/data/validate.sh" = "science_tool/project_artifacts/data/validate.sh"
```

The existing `edges.schema.json` line must remain.

- [ ] **Step 5: Verify package data file exists**

Run:

```bash
test -f science-tool/src/science_tool/project_artifacts/data/validate.sh
```

Expected: exit code `0`.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/project_artifacts science-tool/pyproject.toml
git commit -m "feat(project-artifacts): package canonical validator"
```

---

## Task 3: Implement Artifact Status Classification And Safe Updates

**Files:**

- Create: `science-tool/src/science_tool/project_artifacts/artifacts.py`
- Test: `science-tool/tests/test_project_artifacts.py`

- [ ] **Step 1: Write failing tests**

Create `science-tool/tests/test_project_artifacts.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.project_artifacts.artifacts import (
    ARTIFACTS,
    ArtifactDefinition,
    ArtifactStatus,
    check_artifact,
    check_artifacts,
    diff_artifact,
    managed_content_hash,
    next_backup_path,
    update_artifact,
)


def test_validate_artifact_is_registered() -> None:
    assert "validate.sh" in ARTIFACTS
    artifact = ARTIFACTS["validate.sh"]
    assert artifact.destination == Path("validate.sh")
    assert artifact.mode == 0o755


def test_missing_artifact_reports_missing(tmp_path: Path) -> None:
    report = check_artifact(tmp_path, ARTIFACTS["validate.sh"])

    assert report.status == ArtifactStatus.MISSING
    assert report.path == tmp_path / "validate.sh"


def test_current_artifact_reports_current(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]
    (tmp_path / "validate.sh").write_text(artifact.rendered_content(), encoding="utf-8")

    report = check_artifact(tmp_path, artifact)

    assert report.status == ArtifactStatus.CURRENT
    assert report.current_hash == artifact.source_hash


def test_untracked_artifact_reports_untracked(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]
    (tmp_path / "validate.sh").write_text("#!/usr/bin/env bash\necho local\n", encoding="utf-8")

    report = check_artifact(tmp_path, artifact)

    assert report.status == ArtifactStatus.UNTRACKED


def test_locally_modified_artifact_reports_locally_modified(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]
    modified = artifact.rendered_content() + "\n# local edit\n"
    (tmp_path / "validate.sh").write_text(modified, encoding="utf-8")

    report = check_artifact(tmp_path, artifact)

    assert report.status == ArtifactStatus.LOCALLY_MODIFIED


def test_previous_managed_hash_reports_outdated(tmp_path: Path) -> None:
    old_content = "\n".join(
        [
            "#!/usr/bin/env bash",
            "# science-managed-artifact: validate.sh",
            "# science-managed-version: 2026.04.01",
            "# science-managed-source-sha256: old",
            "echo old",
            "",
        ]
    )
    old_hash = managed_content_hash(old_content)
    artifact = ArtifactDefinition(
        name="validate.sh",
        destination=Path("validate.sh"),
        package_resource="validate.sh",
        version="2026.04.25",
        mode=0o755,
        previous_hashes=(old_hash,),
    )
    (tmp_path / "validate.sh").write_text(old_content, encoding="utf-8")

    report = check_artifact(tmp_path, artifact)

    assert report.status == ArtifactStatus.OUTDATED


def test_check_artifacts_returns_all_known_artifacts(tmp_path: Path) -> None:
    reports = check_artifacts(tmp_path)

    assert [report.name for report in reports] == ["validate.sh"]
    assert reports[0].status == ArtifactStatus.MISSING


def test_hash_ignores_source_hash_line() -> None:
    a = "\n".join(
        [
            "#!/usr/bin/env bash",
            "# science-managed-source-sha256: one",
            "echo ok",
            "",
        ]
    )
    b = a.replace("one", "two")

    assert managed_content_hash(a) == managed_content_hash(b)


def test_diff_artifact_shows_project_and_canonical_content(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]
    (tmp_path / "validate.sh").write_text("#!/usr/bin/env bash\necho local\n", encoding="utf-8")

    diff = diff_artifact(tmp_path, artifact)

    assert f"--- {tmp_path / 'validate.sh'}" in diff
    assert "+++ canonical/validate.sh" in diff
    assert "-echo local" in diff


def test_hash_normalizes_crlf_and_bare_cr_only() -> None:
    lf = "#!/usr/bin/env bash\n# science-managed-source-sha256: one\necho ok\n"
    crlf = lf.replace("\n", "\r\n")
    bare_cr = lf.replace("\n", "\r")

    assert managed_content_hash(lf) == managed_content_hash(crlf)
    assert managed_content_hash(lf) == managed_content_hash(bare_cr)
    assert managed_content_hash(lf) != managed_content_hash(lf.replace("echo ok", "echo ok "))


def test_force_update_writes_backup_before_overwrite(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]
    original = "#!/usr/bin/env bash\necho local\n"
    target = tmp_path / "validate.sh"
    target.write_text(original, encoding="utf-8")

    report = update_artifact(tmp_path, artifact, force=True, accept_loss=True, require_project=False)

    assert report.status == ArtifactStatus.CURRENT
    assert (tmp_path / "validate.sh.pre-update.bak").read_text(encoding="utf-8") == original


def test_update_refuses_force_without_accept_loss(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]
    (tmp_path / "validate.sh").write_text("#!/usr/bin/env bash\necho local\n", encoding="utf-8")

    try:
        update_artifact(tmp_path, artifact, force=True, accept_loss=False, require_project=False)
    except RuntimeError as exc:
        assert "--force --yes" in str(exc)
    else:
        raise AssertionError("update_artifact should require accept_loss with force")


def test_update_refuses_non_project_root_by_default(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]

    try:
        update_artifact(tmp_path, artifact)
    except RuntimeError as exc:
        assert "science.yaml" in str(exc)
    else:
        raise AssertionError("update_artifact should refuse non-project roots by default")


def test_update_allows_bootstrap_escape_hatch(tmp_path: Path) -> None:
    artifact = ARTIFACTS["validate.sh"]

    report = update_artifact(tmp_path, artifact, require_project=False)

    assert report.status == ArtifactStatus.CURRENT


def test_next_backup_path_uses_numeric_suffix(tmp_path: Path) -> None:
    first = tmp_path / "validate.sh.pre-update.bak"
    first.write_text("old", encoding="utf-8")

    assert next_backup_path(tmp_path / "validate.sh") == tmp_path / "validate.sh.pre-update.2.bak"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_project_artifacts.py -q
```

Expected: collection/import failure because `science_tool.project_artifacts.artifacts` does not exist yet.

- [ ] **Step 3: Implement artifact models and status checks**

Create `science-tool/src/science_tool/project_artifacts/artifacts.py`:

```python
from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path


HASH_PREFIX = "# science-managed-source-sha256:"
ARTIFACT_PREFIX = "# science-managed-artifact:"
VERSION_PREFIX = "# science-managed-version:"
HEADER_SEARCH_LINES = 12


class ArtifactStatus(StrEnum):
    MISSING = "missing"
    CURRENT = "current"
    OUTDATED = "outdated"
    LOCALLY_MODIFIED = "locally_modified"
    UNTRACKED = "untracked"


@dataclass(frozen=True)
class ArtifactDefinition:
    name: str
    destination: Path
    package_resource: str
    version: str
    mode: int
    previous_hashes: tuple[str, ...] = ()
    comment_prefix: str = "#"

    @property
    def hash_prefix(self) -> str:
        return f"{self.comment_prefix} science-managed-source-sha256:"

    @property
    def canonical_content(self) -> str:
        return resources.files("science_tool.project_artifacts.data").joinpath(self.package_resource).read_text(
            encoding="utf-8"
        )

    @property
    def source_hash(self) -> str:
        return managed_content_hash(self.canonical_content)

    def rendered_content(self) -> str:
        lines = self.canonical_content.splitlines()
        rendered: list[str] = []
        for line in lines:
            if line.startswith(self.hash_prefix):
                rendered.append(f"{self.hash_prefix} {self.source_hash}")
            else:
                rendered.append(line)
        return "\n".join(rendered) + "\n"


@dataclass(frozen=True)
class ArtifactStatusReport:
    name: str
    path: Path
    status: ArtifactStatus
    expected_version: str
    expected_hash: str
    current_version: str | None = None
    current_hash: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "path": str(self.path),
            "status": self.status.value,
            "expected_version": self.expected_version,
            "expected_hash": self.expected_hash,
            "current_version": self.current_version or "",
            "current_hash": self.current_hash or "",
        }


ARTIFACTS: dict[str, ArtifactDefinition] = {
    "validate.sh": ArtifactDefinition(
        name="validate.sh",
        destination=Path("validate.sh"),
        package_resource="validate.sh",
        version="2026.04.25",
        mode=0o755,
    )
}


def managed_content_hash(content: str) -> str:
    normalized_lines = []
    for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith(HASH_PREFIX):
            normalized_lines.append(f"{HASH_PREFIX} <ignored>")
        else:
            normalized_lines.append(line)
    normalized = "\n".join(normalized_lines).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _header_value(content: str, prefix: str) -> str | None:
    for line in content.splitlines()[:HEADER_SEARCH_LINES]:
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            return value or None
    return None


def next_backup_path(path: Path) -> Path:
    first = path.with_name(f"{path.name}.pre-update.bak")
    if not first.exists():
        return first
    index = 2
    while True:
        candidate = path.with_name(f"{path.name}.pre-update.{index}.bak")
        if not candidate.exists():
            return candidate
        index += 1


def check_artifact(project_root: Path, artifact: ArtifactDefinition) -> ArtifactStatusReport:
    path = project_root / artifact.destination
    if not path.exists():
        return ArtifactStatusReport(
            name=artifact.name,
            path=path,
            status=ArtifactStatus.MISSING,
            expected_version=artifact.version,
            expected_hash=artifact.source_hash,
        )

    content = path.read_text(encoding="utf-8")
    current_hash = managed_content_hash(content)
    current_name = _header_value(content, ARTIFACT_PREFIX)
    current_version = _header_value(content, VERSION_PREFIX)

    if current_name != artifact.name:
        status = ArtifactStatus.UNTRACKED
    elif current_hash == artifact.source_hash:
        status = ArtifactStatus.CURRENT
    elif current_hash in artifact.previous_hashes:
        status = ArtifactStatus.OUTDATED
    else:
        status = ArtifactStatus.LOCALLY_MODIFIED

    return ArtifactStatusReport(
        name=artifact.name,
        path=path,
        status=status,
        expected_version=artifact.version,
        expected_hash=artifact.source_hash,
        current_version=current_version,
        current_hash=current_hash,
    )


def check_artifacts(project_root: Path) -> list[ArtifactStatusReport]:
    return [check_artifact(project_root, artifact) for artifact in ARTIFACTS.values()]


def diff_artifact(project_root: Path, artifact: ArtifactDefinition) -> str:
    path = project_root / artifact.destination
    expected = artifact.rendered_content().splitlines(keepends=True)
    current = path.read_text(encoding="utf-8").splitlines(keepends=True) if path.exists() else []
    return "".join(
        difflib.unified_diff(
            current,
            expected,
            fromfile=str(path),
            tofile=f"canonical/{artifact.name}",
        )
    )


def update_artifact(
    project_root: Path,
    artifact: ArtifactDefinition,
    *,
    force: bool = False,
    accept_loss: bool = False,
    require_project: bool = True,
) -> ArtifactStatusReport:
    if require_project and not (project_root / "science.yaml").is_file():
        raise RuntimeError(f"{project_root} does not look like a Science project root: missing science.yaml")

    before = check_artifact(project_root, artifact)
    destructive = before.status in {ArtifactStatus.LOCALLY_MODIFIED, ArtifactStatus.UNTRACKED}
    if destructive and not (force and accept_loss):
        msg = f"{artifact.name} is {before.status.value}; pass --force --yes to overwrite after reviewing the diff"
        raise RuntimeError(msg)

    path = project_root / artifact.destination
    if path.exists() and before.status != ArtifactStatus.CURRENT:
        backup_path = next_backup_path(path)
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(artifact.rendered_content(), encoding="utf-8")
    path.chmod(artifact.mode)
    return check_artifact(project_root, artifact)
```

- [ ] **Step 4: Record the managed artifact bump maintenance rule**

When the canonical artifact changes in the future, compute the old
`managed_content_hash(canonical_content)` before editing, bump `version`, and
append that old hash to `previous_hashes`. Without that step, existing managed
copies will be reported as `locally_modified` instead of `outdated`.

- [ ] **Step 5: Run tests**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_project_artifacts.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/project_artifacts/artifacts.py science-tool/tests/test_project_artifacts.py
git commit -m "feat(project-artifacts): classify managed artifact drift"
```

---

## Task 4: Add CLI Commands

**Files:**

- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_project_artifacts.py`

- [ ] **Step 1: Add CLI tests**

Append to `science-tool/tests/test_project_artifacts.py`:

```python
from click.testing import CliRunner

from science_tool.cli import main


def test_project_artifacts_check_json_reports_missing(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["project", "artifacts", "check", "--project-root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    assert '"status": "missing"' in result.output
    assert '"name": "validate.sh"' in result.output


def test_project_artifacts_check_strict_fails_on_missing(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["project", "artifacts", "check", "--project-root", str(tmp_path), "--strict"],
    )

    assert result.exit_code != 0
    assert "missing" in result.output


def test_project_artifacts_update_writes_validator(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["project", "artifacts", "update", "validate.sh", "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "validate.sh").exists()
    assert "current" in result.output


def test_project_artifacts_update_refuses_non_project_without_escape_hatch(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["project", "artifacts", "update", "validate.sh", "--project-root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "science.yaml" in result.output


def test_project_artifacts_update_allows_bootstrap_escape_hatch(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["project", "artifacts", "update", "validate.sh", "--project-root", str(tmp_path), "--no-project-check"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "validate.sh").exists()


def test_project_artifacts_update_refuses_untracked_without_force(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "validate.sh").write_text("#!/usr/bin/env bash\necho local\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["project", "artifacts", "update", "validate.sh", "--project-root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "untracked" in result.output


def test_project_artifacts_force_update_writes_backup(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "validate.sh").write_text("#!/usr/bin/env bash\necho local\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        [
            "project",
            "artifacts",
            "update",
            "validate.sh",
            "--project-root",
            str(tmp_path),
            "--force",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "validate.sh.pre-update.bak").exists()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_project_artifacts.py -q
```

Expected: CLI tests fail because `project artifacts` commands do not exist yet.

- [ ] **Step 3: Add `project artifacts` CLI group**

In `science-tool/src/science_tool/cli.py`, below the existing `project_index` command and before `health_command`, add:

```python
@project.group("artifacts")
def project_artifacts() -> None:
    """Manage copied Science framework artifacts in a project."""


@project_artifacts.command("check")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option("--strict", is_flag=True, help="Exit non-zero if any managed artifact is not current.")
def project_artifacts_check(project_root: Path, output_format: str, strict: bool) -> None:
    """Check copied managed artifacts for drift."""
    from science_tool.project_artifacts import ArtifactStatus, check_artifacts

    root = project_root.resolve()
    reports = check_artifacts(root)
    rows = []
    for report in reports:
        display_path = report.path.relative_to(root)
        rows.append(
            {
                "name": report.name,
                "status": report.status.value,
                "expected_version": report.expected_version,
                "current_version": report.current_version or "",
                "path": str(display_path),
            }
        )

    emit_query_rows(
        output_format=output_format,
        title="Managed Artifacts",
        columns=[
            ("name", "Name"),
            ("status", "Status"),
            ("expected_version", "Expected"),
            ("current_version", "Current"),
            ("path", "Path"),
        ],
        rows=rows,
    )
    if strict and any(report.status != ArtifactStatus.CURRENT for report in reports):
        raise click.ClickException("One or more managed artifacts are not current.")


@project_artifacts.command("diff")
@click.argument("artifact_name")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def project_artifacts_diff(artifact_name: str, project_root: Path) -> None:
    """Show differences between a project artifact and the canonical artifact."""
    from science_tool.project_artifacts.artifacts import ARTIFACTS, diff_artifact

    artifact = ARTIFACTS.get(artifact_name)
    if artifact is None:
        raise click.ClickException(f"Unknown managed artifact: {artifact_name}")

    diff = diff_artifact(project_root.resolve(), artifact)
    click.echo(diff or f"{artifact_name}: no differences")


@project_artifacts.command("update")
@click.argument("artifact_name", required=False)
@click.option("--all", "all_artifacts", is_flag=True, help="Update all managed artifacts.")
@click.option("--force", is_flag=True, help="Overwrite untracked or locally modified artifacts.")
@click.option("--yes", "accept_loss", is_flag=True, help="Confirm forced overwrite after reviewing the diff.")
@click.option("--no-project-check", is_flag=True, help="Allow writes when science.yaml is absent.")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def project_artifacts_update(
    artifact_name: str | None,
    all_artifacts: bool,
    force: bool,
    accept_loss: bool,
    no_project_check: bool,
    project_root: Path,
) -> None:
    """Install or update copied managed artifacts."""
    from science_tool.project_artifacts.artifacts import ARTIFACTS, update_artifact

    if not all_artifacts and artifact_name is None:
        raise click.ClickException("Pass an artifact name or --all.")
    if all_artifacts and artifact_name is not None:
        raise click.ClickException("Pass either an artifact name or --all, not both.")

    if all_artifacts:
        names = list(ARTIFACTS)
    else:
        assert artifact_name is not None
        if artifact_name not in ARTIFACTS:
            raise click.ClickException(f"Unknown managed artifact: {artifact_name}")
        names = [artifact_name]

    root = project_root.resolve()
    if no_project_check:
        click.echo("WARN: --no-project-check is enabled; writing even if science.yaml is absent.")
    failed = False
    for name in names:
        try:
            report = update_artifact(
                root,
                ARTIFACTS[name],
                force=force,
                accept_loss=accept_loss,
                require_project=not no_project_check,
            )
        except RuntimeError as exc:
            failed = True
            click.echo(f"{name}: failed: {exc}")
            continue
        click.echo(f"{report.name}: {report.status.value}")

    if failed:
        raise click.ClickException("One or more managed artifacts failed to update.")
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_project_artifacts.py -q
```

Expected: all project artifact tests pass.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_project_artifacts.py
git commit -m "feat(project-artifacts): add artifact check and update CLI"
```

---

## Task 5: Add Canonical Source Sync Test

**Files:**

- Modify: `science-tool/tests/test_project_artifacts.py`

- [ ] **Step 1: Add sync test**

Append:

```python
def test_packaged_validator_matches_root_validator() -> None:
    artifact = ARTIFACTS["validate.sh"]
    root_validator = Path(__file__).resolve().parents[2] / "scripts" / "validate.sh"

    assert managed_content_hash(root_validator.read_text(encoding="utf-8")) == artifact.source_hash
```

- [ ] **Step 2: Run the test**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_project_artifacts.py::test_packaged_validator_matches_root_validator -q
```

Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add science-tool/tests/test_project_artifacts.py
git commit -m "test(project-artifacts): guard packaged validator drift"
```

---

## Task 6: Integrate Managed Artifacts Into Health And Status Surfaces

**Files:**

- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/tests/test_health.py`
- Modify: `commands/status.md`
- Modify: `commands/next-steps.md`

- [ ] **Step 1: Add a health-report test for stale managed artifacts**

Append to `science-tool/tests/test_health.py` near the existing `TestBuildHealthReport` tests. Existing tests in that class already verify `build_health_report(tmp_path)` works with a minimal project containing only `science.yaml`, so this fixture follows the current health-test style rather than inventing a separate scaffold.

```python
def test_project_health_reports_non_current_managed_artifacts(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "profile: software",
                "layout_version: 2",
                "knowledge_profiles:",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True)
    (tmp_path / "validate.sh").write_text("#!/usr/bin/env bash\necho local\n", encoding="utf-8")

    from science_tool.graph.health import build_health_report

    report = build_health_report(tmp_path)

    assert report["managed_artifacts"][0]["name"] == "validate.sh"
    assert report["managed_artifacts"][0]["status"] == "untracked"
```

- [ ] **Step 2: Run the test and confirm failure**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_health.py::TestBuildHealthReport::test_project_health_reports_non_current_managed_artifacts -q
```

Expected: fail because `managed_artifacts` is not yet in the health report.

- [ ] **Step 3: Extend health report types and builder**

In `science-tool/src/science_tool/graph/health.py`, add this typed dict near the other health finding types:

```python
class ManagedArtifactFinding(TypedDict):
    name: str
    status: str
    expected_version: str
    current_version: str
    path: str
```

Add this field to `HealthReport`:

```python
    managed_artifacts: list[ManagedArtifactFinding]
```

Inside `build_health_report`, before the final `return`, add:

```python
    from science_tool.project_artifacts import ArtifactStatus, check_artifacts

    managed_artifacts: list[ManagedArtifactFinding] = [
        {
            "name": report.name,
            "status": report.status.value,
            "expected_version": report.expected_version,
            "current_version": report.current_version or "",
            "path": str(report.path.relative_to(project_root)),
        }
        for report in check_artifacts(project_root)
        if report.status != ArtifactStatus.CURRENT
    ]
```

Add `"managed_artifacts": managed_artifacts,` to the returned dict.

- [ ] **Step 4: Render managed artifact findings in table output**

In `science-tool/src/science_tool/cli.py`, update `health_command`:

1. Include managed artifacts in `total_issues`, directly after the existing `dataset_anomalies` term:

```python
        + len(report.get("managed_artifacts") or [])
```

2. Before the unresolved references table, add:

```python
    managed_artifacts = report.get("managed_artifacts") or []
    if managed_artifacts:
        table = Table(title=f"Managed Artifacts ({len(managed_artifacts)})")
        table.add_column("Name", style="bold")
        table.add_column("Status")
        table.add_column("Expected")
        table.add_column("Current")
        table.add_column("Path")
        for row in managed_artifacts:
            table.add_row(
                row["name"],
                row["status"],
                row["expected_version"],
                row["current_version"] or "-",
                row["path"],
            )
        console.print(table)
        console.print(
            "\n[bold]Next:[/bold] run [cyan]science-tool project artifacts diff <name>[/cyan] "
            "then [cyan]science-tool project artifacts update <name>[/cyan]."
        )
```

- [ ] **Step 5: Update `/science:status` command guidance**

In `commands/status.md`, add this bullet under "Staleness Warnings":

```markdown
- managed copied artifacts reported by `science-tool health` as `missing`, `outdated`, `untracked`, or `locally_modified`
```

- [ ] **Step 6: Update `/science:next-steps` command guidance**

In `commands/next-steps.md`, after the `## Cross-Project Sync Check` section and before `## After Writing`, insert:

````markdown
## Managed Artifact Check

Run:

```bash
science-tool health --project-root . --format json
```

If `managed_artifacts` contains any rows, include a Recommended Next Action to review the diff and update the managed artifact. For `untracked` or `locally_modified`, say that the user should inspect the diff before adopting the Science-managed copy.
````

- [ ] **Step 7: Run focused tests**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_health.py::TestBuildHealthReport::test_project_health_reports_non_current_managed_artifacts -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add science-tool/src/science_tool/graph/health.py science-tool/src/science_tool/cli.py science-tool/tests/test_health.py commands/status.md commands/next-steps.md
git commit -m "feat(project-artifacts): surface managed artifact drift in health"
```

---

## Task 7: Update Creation And Import Guidance

**Files:**

- Modify: `commands/create-project.md`
- Modify: `commands/import-project.md`
- Modify: `README.md`
- Modify: `docs/project-organization-profiles.md`

- [ ] **Step 1: Update create-project validator section**

In `commands/create-project.md`, replace:

```markdown
Copy the validation script from `${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh` and make it executable.
```

with:

````markdown
Install the managed validator artifact:

```bash
science-tool project artifacts update validate.sh --project-root .
```

If `science-tool` is not available yet during bootstrap, copy `${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh` as a fallback; the copied file must retain its `science-managed-*` header so future artifact checks can update it.

Managed artifact updates write backups next to the artifact as `*.pre-update*.bak`; these backups are ignored by default, and users may remove or commit them manually after reviewing an update.
````

- [ ] **Step 2: Update import-project validator section**

In `commands/import-project.md`, replace:

```markdown
Copy `${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh` into the project root and make it executable.
```

with:

````markdown
Install or refresh the managed validator artifact:

```bash
science-tool project artifacts update validate.sh --project-root .
```

If the existing project already has a custom `validate.sh`, run `science-tool project artifacts check --project-root .` first. Do not overwrite an untracked or locally modified validator unless the user explicitly wants to adopt the Science-managed copy.

Managed artifact updates write backups next to the artifact as `*.pre-update*.bak`; these backups are ignored by default. If a project wants to retain a backup in git, add it explicitly with `git add -f`.
````

- [ ] **Step 3: Update create/import `.gitignore` guidance**

In `commands/create-project.md`, add this line to the `.gitignore` block:

```gitignore
*.pre-update*.bak
```

In `commands/import-project.md`, add this item to the "Ensure the project ignores:" list:

```markdown
- `*.pre-update*.bak`
```

- [ ] **Step 4: Update project organization migration rule**

In `docs/project-organization-profiles.md`, replace:

```markdown
5. Refresh `validate.sh` after framework validator changes.
```

with:

````markdown
5. Run `science-tool project artifacts check --project-root .` and update managed copied artifacts such as `validate.sh` when they are outdated.
````

- [ ] **Step 5: Add README note**

In `README.md`, after the paragraph that says all artifacts are version-controlled, cross-linked, and validated by `bash validate.sh`, add:

````markdown
Copied framework artifacts such as `validate.sh` are managed explicitly:

```bash
science-tool project artifacts check --project-root .
science-tool project artifacts update validate.sh --project-root .
```

Commands, skills, and framework templates are resolved centrally and are not copied into projects unless a project intentionally creates an override under `.ai/`.

When forced updates replace an existing managed artifact, `science-tool` writes a sibling `*.pre-update*.bak` file first. Project scaffolds ignore these backups by default; remove or commit them deliberately after reviewing the update.
````

- [ ] **Step 6: Run Markdown search verification**

Run:

```bash
rg -n 'Copy .*validate.sh|Refresh `validate.sh`' commands README.md docs/project-organization-profiles.md
```

Expected: no old bare-copy or vague refresh instruction remains in the searched files.

- [ ] **Step 7: Commit**

```bash
git add commands/create-project.md commands/import-project.md README.md docs/project-organization-profiles.md
git commit -m "docs(project-artifacts): document managed validator workflow"
```

---

## Task 8: Downstream mm30 Verification

**Files:**

- Verify only unless the user explicitly approves updating `/home/keith/d/r/mm30/validate.sh`.

This task is user-local verification for Keith's workstation. Other operators should skip it or adapt the paths to a downstream Science project that has an older copied `validate.sh`.

- [ ] **Step 1: Check the motivating downstream project**

Run:

```bash
uv run --project science-tool science-tool project artifacts check --project-root /home/keith/d/r/mm30
```

Expected before adoption: `validate.sh` reports `untracked` because the existing file predates the managed header. This confirms the checker finds the real drift case without assuming it is safe to overwrite.

- [ ] **Step 2: Show the diff for review**

Run:

```bash
uv run --project science-tool science-tool project artifacts diff validate.sh --project-root /home/keith/d/r/mm30
```

Expected: unified diff shows the current `mm30/validate.sh` versus the canonical managed validator. Review whether local project-specific validator logic exists.

- [ ] **Step 3: Adopt the managed validator only with explicit approval**

If the user wants `mm30` to adopt the Science-managed validator, run:

```bash
uv run --project science-tool science-tool project artifacts update validate.sh --project-root /home/keith/d/r/mm30 --force --yes
```

Expected:

- command reports `validate.sh: current`
- `/home/keith/d/r/mm30/validate.sh.pre-update.bak` exists
- backup contains the pre-update validator

If the user does not want to adopt the managed validator yet, stop after the diff and record that `mm30` intentionally remains `untracked`.

- [ ] **Step 4: Re-check artifact status**

If Step 3 adopted the managed validator, run:

```bash
uv run --project science-tool science-tool project artifacts check --project-root /home/keith/d/r/mm30 --strict
```

Expected: exit code `0`, `validate.sh` reports `current`.

If Step 3 did not adopt it, run the same command without `--strict`:

```bash
uv run --project science-tool science-tool project artifacts check --project-root /home/keith/d/r/mm30
```

Expected: exit code `0`, `validate.sh` reports `untracked`.

- [ ] **Step 5: Verify downstream validation still runs**

Run:

```bash
cd /home/keith/d/r/mm30 && bash validate.sh --verbose
```

Expected: the validator runs to completion. It may report project-specific warnings or errors unrelated to managed artifact adoption; record those separately instead of treating them as updater failures.

- [ ] **Step 6: Commit**

Do not commit `mm30` changes from the Science repository. If Step 3 modified `mm30`, commit that change from the `mm30` repository with a message such as:

```bash
git add validate.sh validate.sh.pre-update.bak
git commit -m "chore: adopt managed Science validator"
```

Only include the backup in the downstream commit if the project wants to retain it in git. Otherwise leave it untracked or remove it after confirming the update.

---

## Task 9: Verification

**Files:**

- Verify only.

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_project_artifacts.py tests/test_validate_script.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run formatter**

Run:

```bash
uv run --frozen ruff format science-tool/src/science_tool/project_artifacts science-tool/tests/test_project_artifacts.py science-tool/src/science_tool/cli.py
```

Expected: files formatted.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run --frozen ruff check science-tool/src/science_tool/project_artifacts science-tool/tests/test_project_artifacts.py science-tool/src/science_tool/cli.py
```

Expected: no lint errors.

- [ ] **Step 4: Run type check**

Run:

```bash
uv run --frozen pyright
```

Expected: no new type errors.

- [ ] **Step 5: Smoke-test artifact update in a temporary project**

Run:

```bash
tmpdir="$(mktemp -d)"
printf 'name: smoke\nprofile: software\nlayout_version: 2\n' > "$tmpdir/science.yaml"
uv run --project science-tool science-tool project artifacts check --project-root "$tmpdir"
uv run --project science-tool science-tool project artifacts update validate.sh --project-root "$tmpdir"
uv run --project science-tool science-tool project artifacts check --project-root "$tmpdir"
test -x "$tmpdir/validate.sh"
```

Expected:

- First check reports `validate.sh: missing`.
- Update reports `validate.sh: current`.
- Second check reports `validate.sh: current`.
- Executable test exits `0`.

- [ ] **Step 6: Final commit if verification changed formatting**

```bash
git add science-tool/src/science_tool/project_artifacts science-tool/tests/test_project_artifacts.py science-tool/src/science_tool/cli.py
git commit -m "chore(project-artifacts): format managed artifact implementation"
```

Skip this commit if there are no formatting changes.

---

## Self-Review Checklist

- Design coverage: implements copied managed artifact detection/update for `validate.sh`; leaves runtime-resolved, project-owned, generated, and dependency artifacts outside the updater.
- Replacement safety: `untracked` and `locally_modified` refuse overwrite without `--force --yes`, and any non-current overwrite writes a `.pre-update.bak` backup.
- Drift guard: packaged validator and root `scripts/validate.sh` are hash-compared in tests.
- Bootstrap path: project creation/import docs retain a fallback for direct copy but require managed headers.
- Health/status closure: `science-tool health`, `/science:status`, `/science:next-steps`, and the downstream `mm30` verification are included.
- Scope discipline: no migrations for `science.yaml`, docs, tasks, entities, graph files, commands, skills, or templates are included in this plan.
