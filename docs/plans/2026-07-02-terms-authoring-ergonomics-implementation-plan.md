# Terms Authoring Ergonomics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow `science terms add` command that writes lightweight local semantic rows to the configured local profile's `terms.yaml`.

**Architecture:** Put the writer in a focused `science_tool.terms` module so YAML parsing, local-profile routing, validation, identity checks, and file writing stay out of the root CLI. Register a small Click command group in `cli.py` that adapts options to `add_term()` and reports user-correctable errors. Keep docs and generated Codex mirrors aligned after behavior is green.

**Tech Stack:** Python 3.13, Click, PyYAML, Pydantic source loading, Science `load_project_sources()`, pytest, generated Codex skills.

---

## File Structure

- Create `science/src/science_tool/terms.py`
  - Owns `TermsCommandError`, `TermsAddResult`, YAML document parsing, local-profile target selection, registered-kind validation, identity collision checks, and row writing.
  - Exposes one public function: `add_term(...)`.
- Modify `science/src/science_tool/cli.py`
  - Imports `TermsCommandError` and `add_term`.
  - Registers `science terms add`.
  - Does not add update/delete/list/promote commands.
- Create `science/tests/test_terms_cli.py`
  - Covers CLI behavior, YAML output, duplicate prevention, invalid ids, unsupported prefixes, external ontology-prefix rejection, markdown-owner collision, malformed YAML, reload behavior, local-profile routing, rejected flags, commons/core loading guard, and unrelated-collision diagnostics.
- Modify `science/tests/test_user_guide_docs.py`
  - Guards user-guide wording for `science terms add`, local-profile targeting, and the full concept-vs-lightweight-term boundary.
- Modify `science/tests/test_command_docs.py`
  - Guards command docs for executable `science terms add` guidance instead of hand-authored YAML as the routine path.
- Modify `science/tests/test_codex_skills.py`
  - Guards committed and generated Codex mirrors.
- Modify user-facing docs:
  - `docs/user-guide/entities.md`
  - `docs/user-guide/epistemic-model.md`
  - `docs/user-guide/cli-and-workflows.md`
  - `commands/sketch-model.md`
  - `commands/specify-model.md`
  - `commands/create-graph.md`
  - `commands/health.md`
- Regenerate generated mirrors in `codex-skills/science-create-graph/SKILL.md`, `codex-skills/science-health/SKILL.md`, `codex-skills/science-sketch-model/SKILL.md`, and `codex-skills/science-specify-model/SKILL.md`.

## Implementation Notes

- Use project-local `docs/plans/` for this plan. Do not create a new planning hierarchy.
- Use `PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest ...` for pytest commands.
- If pytest fails because Click or pytest cannot write cache/temp files in the sandbox, rerun the exact command with escalated permissions.
- Keep `--profile` absent. Rows outside `knowledge_profiles.local` do not load today.
- Expose only `--project-root`, not a `--project` alias. `terms add` is a new command with no legacy callers, and adding `--project` would trip the exact-equality `--project` allowlist in `test_cli_surface_contract.py`. `--project-root`-only sidesteps that contract entirely.
- Emit minimal YAML rows: only keys with values. Do not emit empty `aliases`, `same_as`, or `ontology_terms`.
- Use `id`, not `canonical_id`, for newly written rows.
- Deliberately omit `kind`; the aggregate adapter infers kind from the id prefix.
- Do not use `Path.cwd()` as a Click option default. Click decorators are evaluated when `science_tool.cli` is imported, before `CliRunner.isolated_filesystem()` changes the process CWD. Use `Path(".")` / `"."` as the default and resolve inside the command or writer.
- Test helper `write_markdown_entity` has signature `(root, rel_path, frontmatter, body="")` — the tests here call it positionally, which is correct; do not switch to keyword args `relpath=`/`frontmatter_dict=` (those names don't exist).
- The collision-location assertions (`"markdown:entities/concepts/treatment-response.md"`, `"aggregate:knowledge/sources/local/entities.yaml"`) are built from the real `IdentityDeclaration.adapter` name and `source_ref.path`. If a red test shows a different adapter name or path spelling, fix the ASSERTION to match the real values — the implementation string is derived from live code and is the source of truth, not the test literal.
- Prefix validation uses `registry.resolve(kind)` as a single accept/reject gate. This safely rejects both unregistered kinds (`notakind:`) and external ontology prefixes (`HP:`) — the registry does not register ontology CURIE prefixes as kinds (they live in a separate `curie_prefixes` field, reached via `external_prefixes(...)`, never through `registry.resolve`). We therefore do NOT try to detect "is this specifically an ontology prefix" — in a bare project with no declared ontology, `HP` is indistinguishable from a typo anyway. The one honest error message names the registered-kind requirement and points to `--ontology-term` as the fix if the prefix was meant as an external CURIE. Do not reword this into two branches that imply the command detected which case it was.

---

### Task 1: Add Failing CLI Tests For Basic Terms Authoring

**Files:**
- Create: `science/tests/test_terms_cli.py`
- Modify: none

- [ ] **Step 1: Create the test file with basic creation, serialization, reload, local-profile, and rejected-flag tests**

Create `science/tests/test_terms_cli.py` with this content:

```python
from __future__ import annotations

from pathlib import Path

import yaml
from _fixtures.entity_helpers import seed_project, write_markdown_entity
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.sources import load_project_sources


def _read_terms(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_terms_add_creates_minimal_local_terms_yaml_and_reloads() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "terms",
                "add",
                "concept:treatment-response",
                "--title",
                "Treatment response",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Added concept:treatment-response" in result.output
        assert "knowledge/sources/local/terms.yaml" in result.output

        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        assert terms_path.is_file()
        payload = _read_terms(terms_path)
        assert payload == {
            "terms": [
                {
                    "id": "concept:treatment-response",
                    "title": "Treatment response",
                }
            ]
        }

        sources = load_project_sources(root)
        by_id = {entity.canonical_id: entity for entity in sources.entities}
        entity = by_id["concept:treatment-response"]
        assert entity.kind == "concept"
        assert entity.title == "Treatment response"
        assert entity.file_path == "knowledge/sources/local/terms.yaml"


def test_terms_add_serializes_only_populated_optional_fields() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "terms",
                "add",
                "method:cox-regression",
                "--title",
                "Cox proportional-hazards regression",
                "--description",
                "Survival model with proportional hazards.",
                "--alias",
                "Cox model",
                "--alias",
                "Cox PH",
                "--same-as",
                "wikidata:Q1132755",
                "--ontology-term",
                "biolink:StatisticalMethod",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = _read_terms(root / "knowledge" / "sources" / "local" / "terms.yaml")
        assert payload == {
            "terms": [
                {
                    "id": "method:cox-regression",
                    "title": "Cox proportional-hazards regression",
                    "description": "Survival model with proportional hazards.",
                    "aliases": ["Cox model", "Cox PH"],
                    "same_as": ["wikidata:Q1132755"],
                    "ontology_terms": ["biolink:StatisticalMethod"],
                }
            ]
        }


def test_terms_add_uses_configured_local_profile() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        (root / "science.yaml").write_text(
            "name: term-cli-test\nknowledge_profiles: {local: lab}\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:lab-term", "--title", "Lab term"],
        )

        assert result.exit_code == 0, result.output
        assert "knowledge/sources/lab/terms.yaml" in result.output
        assert (root / "knowledge" / "sources" / "lab" / "terms.yaml").is_file()
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_preserves_existing_order_and_unrelated_top_level_keys() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        terms_path.write_text(
            yaml.safe_dump(
                {
                    "metadata": {"curator": "science"},
                    "terms": [
                        {"id": "concept:first", "title": "First"},
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:second", "--title", "Second"],
        )

        assert result.exit_code == 0, result.output
        payload = _read_terms(terms_path)
        assert payload["metadata"] == {"curator": "science"}
        assert payload["terms"] == [
            {"id": "concept:first", "title": "First"},
            {"id": "concept:second", "title": "Second"},
        ]


def test_terms_add_rejects_flags_that_would_write_ignored_or_unloaded_fields() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        for flag in ("--body", "--content", "--name", "--profile"):
            result = runner.invoke(
                main,
                [
                    "terms",
                    "add",
                    "concept:treatment-response",
                    "--title",
                    "Treatment response",
                    flag,
                    "value",
                ],
            )
            assert result.exit_code != 0, result.output
            assert f"No such option: {flag}" in result.output
```

- [ ] **Step 2: Run the basic tests and verify they fail because the command does not exist**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_terms_cli.py -q
```

Expected: FAIL. The relevant failure text should include `No such command 'terms'`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add science/tests/test_terms_cli.py
git commit -m "test: specify terms add basics"
```

---

### Task 2: Implement Basic `science terms add`

**Files:**
- Create: `science/src/science_tool/terms.py`
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_terms_cli.py`

- [ ] **Step 1: Add the focused terms writer module**

Create `science/src/science_tool/terms.py` with this content:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from science_tool.graph.entity_registry import EntityKindNotRegisteredError
from science_tool.graph.identity_table import ParticipationMode, build_identity_table
from science_tool.graph.sources import (
    load_project_sources,
    local_profile_sources_dir,
    resolve_local_profile_name,
)


class TermsCommandError(ValueError):
    """Raised for user-correctable terms CLI errors."""


@dataclass(frozen=True)
class TermsAddResult:
    term_id: str
    path: Path


def add_term(
    *,
    project_root: Path,
    term_id: str,
    title: str,
    description: str | None = None,
    aliases: list[str] | None = None,
    same_as: list[str] | None = None,
    ontology_terms: list[str] | None = None,
) -> TermsAddResult:
    """Create a lightweight term row in the configured local profile's terms.yaml."""
    project_root = project_root.resolve()
    normalized_id, kind = _parse_term_id(term_id)
    profile_name = resolve_local_profile_name(project_root)
    terms_path = local_profile_sources_dir(project_root, local_profile=profile_name) / "terms.yaml"
    document = _load_terms_document(terms_path)
    _ensure_target_has_no_duplicate(document, normalized_id)

    sources = load_project_sources(project_root, strict_identity=False)
    try:
        sources.registry.resolve(kind)
    except EntityKindNotRegisteredError as exc:
        raise TermsCommandError(
            f"Unsupported term id prefix {kind!r}: the prefix must be a registered entity "
            "kind such as concept: or method:. If it is an external ontology CURIE prefix, "
            "pass the CURIE via --ontology-term instead of using it as the term id."
        ) from exc

    _ensure_loaded_sources_can_accept_id(sources, normalized_id)

    row = _term_row(
        term_id=normalized_id,
        title=title,
        description=description,
        aliases=list(aliases or []),
        same_as=list(same_as or []),
        ontology_terms=list(ontology_terms or []),
    )
    document["terms"].append(row)
    terms_path.parent.mkdir(parents=True, exist_ok=True)
    terms_path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return TermsAddResult(term_id=normalized_id, path=terms_path)


def _parse_term_id(term_id: str) -> tuple[str, str]:
    normalized = term_id.strip()
    if ":" not in normalized:
        raise TermsCommandError("Term id must be a canonical CURIE-style id such as concept:treatment-response")
    prefix, local_id = normalized.split(":", 1)
    if not prefix or not local_id:
        raise TermsCommandError("Term id must include a non-empty prefix and local id")
    return normalized, prefix


def _load_terms_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"terms": []}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TermsCommandError(f"{path}: terms.yaml is not valid YAML") from exc
    if not isinstance(data, dict):
        raise TermsCommandError(f"{path}: terms.yaml must be a YAML mapping with a list-valued 'terms' key")
    if "terms" not in data or not isinstance(data["terms"], list):
        raise TermsCommandError(f"{path}: terms.yaml must contain a list-valued 'terms' key")
    return data


def _row_id(row: object) -> str | None:
    if not isinstance(row, dict):
        return None
    value = row.get("id") or row.get("canonical_id")
    return value if isinstance(value, str) else None


def _ensure_target_has_no_duplicate(document: dict[str, Any], term_id: str) -> None:
    for row in document["terms"]:
        if _row_id(row) == term_id:
            raise TermsCommandError(f"{term_id} already exists in the target terms.yaml")


def _ensure_loaded_sources_can_accept_id(sources: Any, term_id: str) -> None:
    collisions = build_identity_table(sources).collisions()
    for collision in collisions:
        if collision.canonical_id == term_id:
            raise TermsCommandError(f"{term_id} already resolves to an existing owner")
    genuine_unrelated = [collision for collision in collisions if collision.is_genuine]
    if genuine_unrelated:
        ids = ", ".join(sorted(collision.canonical_id for collision in genuine_unrelated))
        raise TermsCommandError(
            f"Project already contains identity collision(s) unrelated to this term: {ids}; resolve them first"
        )

    owners = [
        declaration
        for declaration in sources.identity_declarations
        if declaration.participation_mode is ParticipationMode.OWNER and declaration.canonical_id == term_id
    ]
    if owners:
        locations = ", ".join(
            sorted(
                f"{owner.adapter}:{owner.source_ref.path if owner.source_ref is not None else '<unknown>'}"
                for owner in owners
            )
        )
        raise TermsCommandError(f"{term_id} already resolves to an existing owner: {locations}")


def _term_row(
    *,
    term_id: str,
    title: str,
    description: str | None,
    aliases: list[str],
    same_as: list[str],
    ontology_terms: list[str],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": term_id,
        "title": title,
    }
    if description:
        row["description"] = description
    if aliases:
        row["aliases"] = aliases
    if same_as:
        row["same_as"] = same_as
    if ontology_terms:
        row["ontology_terms"] = ontology_terms
    return row
```

- [ ] **Step 2: Register the Click group and command**

Modify `science/src/science_tool/cli.py`.

Add this import near the other `science_tool` imports:

```python
from science_tool.terms import TermsCommandError, add_term
```

Add this group after the `entity` group command definitions begin, immediately before `@main.group("entity")` or immediately after the `entity_group()` definition if that reads more cleanly:

```python
@main.group("terms")
def terms_group() -> None:
    """Create lightweight local semantic terms."""


@terms_group.command("add")
@click.argument("term_id")
@click.option("--title", required=True, help="Display title for the lightweight term.")
@click.option("--description", default=None, help="Short description used as the lightweight content preview.")
@click.option("--alias", "aliases", multiple=True, help="Alias string (repeatable).")
@click.option("--same-as", "same_as", multiple=True, help="External equivalent id or URI (repeatable).")
@click.option("--ontology-term", "ontology_terms", multiple=True, help="Ontology CURIE (repeatable).")
@click.option(
    "--project-root",
    "project_path",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path("."),
    help="Project root whose configured local profile should receive the term (default: current working directory).",
)
def terms_add(
    term_id: str,
    title: str,
    description: str | None,
    aliases: tuple[str, ...],
    same_as: tuple[str, ...],
    ontology_terms: tuple[str, ...],
    project_path: Path,
) -> None:
    """Add a lightweight term row to the configured local profile."""
    try:
        result = add_term(
            project_root=project_path,
            term_id=term_id,
            title=title,
            description=description,
            aliases=list(aliases),
            same_as=list(same_as),
            ontology_terms=list(ontology_terms),
        )
    except TermsCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Added {result.term_id} at {result.path.relative_to(project_path.resolve())}")
```

- [ ] **Step 3: Run the basic tests and verify they pass**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_terms_cli.py -q
```

Expected: PASS for the five tests from Task 1.

- [ ] **Step 4: Commit the basic implementation**

```bash
git add science/src/science_tool/terms.py science/src/science_tool/cli.py science/tests/test_terms_cli.py
git commit -m "feat: add terms add command"
```

---

### Task 3: Add Validation And Collision Tests

**Files:**
- Modify: `science/tests/test_terms_cli.py`

- [ ] **Step 1: Append validation tests**

Append these tests to `science/tests/test_terms_cli.py`:

```python

def test_terms_add_rejects_duplicate_target_row_without_rewrite() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        original = "terms:\n  - id: concept:treatment-response\n    title: Treatment response\n"
        terms_path.write_text(original, encoding="utf-8")

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "already exists in the target terms.yaml" in result.output
        assert terms_path.read_text(encoding="utf-8") == original


def test_terms_add_rejects_malformed_and_empty_ids_before_writing() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        for term_id in ("treatment-response", "concept:", ":treatment-response"):
            result = runner.invoke(
                main,
                ["terms", "add", term_id, "--title", "Treatment response"],
            )
            assert result.exit_code != 0, result.output

        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_rejects_unsupported_prefix_and_external_ontology_prefix() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        unsupported = runner.invoke(
            main,
            ["terms", "add", "notakind:treatment-response", "--title", "Treatment response"],
        )
        external = runner.invoke(
            main,
            [
                "terms",
                "add",
                "HP:0001250",
                "--title",
                "Seizure",
                "--ontology-term",
                "HP:0001250",
            ],
        )

        assert unsupported.exit_code != 0
        assert "Unsupported term id prefix 'notakind'" in unsupported.output
        assert "must be a registered entity kind" in unsupported.output
        assert external.exit_code != 0
        assert "Unsupported term id prefix 'HP'" in external.output
        assert "--ontology-term" in external.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_rejects_existing_markdown_owner() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/concepts/treatment-response.md",
            {
                "id": "concept:treatment-response",
                "type": "concept",
                "title": "Treatment Response",
                "status": "active",
            },
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "concept:treatment-response already resolves to an existing owner" in result.output
        assert "markdown:entities/concepts/treatment-response.md" in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_rejects_malformed_terms_yaml_without_rewrite() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        original = "terms: [\n"
        terms_path.write_text(original, encoding="utf-8")

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "terms.yaml is not valid YAML" in result.output
        assert terms_path.read_text(encoding="utf-8") == original


def test_terms_add_rejects_existing_non_list_terms_key_without_rewrite() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        terms_path = root / "knowledge" / "sources" / "local" / "terms.yaml"
        terms_path.parent.mkdir(parents=True)
        original = "terms: {}\n"
        terms_path.write_text(original, encoding="utf-8")

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "list-valued 'terms' key" in result.output
        assert terms_path.read_text(encoding="utf-8") == original
```

- [ ] **Step 2: Append identity-check tests**

Add these imports near the top of `science/tests/test_terms_cli.py`:

```python
import shutil

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
```

Then append these helper/test definitions to `science/tests/test_terms_cli.py`:

```python
_COMMONS_FIXTURE = Path(__file__).parent / "fixtures" / "commons" / "valid"


def _copy_commons_fixture(tmp_path: Path) -> Path:
    commons_root = tmp_path / "commons"
    shutil.copytree(_COMMONS_FIXTURE, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    return commons_root


def test_terms_add_rejects_loaded_aggregate_owner() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        local_sources = root / "knowledge" / "sources" / "local"
        local_sources.mkdir(parents=True)
        (local_sources / "entities.yaml").write_text(
            yaml.safe_dump(
                {
                    "entities": [
                        {
                            "id": "concept:treatment-response",
                            "kind": "concept",
                            "title": "Treatment response aggregate",
                        }
                    ]
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:treatment-response", "--title", "Treatment response"],
        )

        assert result.exit_code != 0
        assert "concept:treatment-response already resolves to an existing owner" in result.output
        assert "aggregate:knowledge/sources/local/entities.yaml" in result.output
        assert not (local_sources / "terms.yaml").exists()


def test_terms_add_rejects_existing_commons_owner(tmp_path: Path, monkeypatch) -> None:
    commons_root = _copy_commons_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/concepts/local-context.md",
            {
                "id": "concept:local-context",
                "type": "concept",
                "title": "Local context",
                "status": "active",
                "related": ["topic:single-cell-foundation-models"],
            },
        )

        result = runner.invoke(
            main,
            ["terms", "add", "topic:single-cell-foundation-models", "--title", "Single-cell foundation models"],
        )

        assert result.exit_code != 0
        assert "topic:single-cell-foundation-models already resolves to an existing owner" in result.output
        assert "commons-merged:commons://topics/single-cell-foundation-models.md" in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_reports_unrelated_genuine_identity_collision_distinctly() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "entities/concepts/one.md",
            {
                "id": "concept:duplicate",
                "type": "concept",
                "title": "Duplicate One",
                "status": "active",
            },
        )
        write_markdown_entity(
            root,
            "entities/concepts/two.md",
            {
                "id": "concept:duplicate",
                "type": "concept",
                "title": "Duplicate Two",
                "status": "active",
            },
        )

        result = runner.invoke(
            main,
            ["terms", "add", "concept:new-term", "--title", "New term"],
        )

        assert result.exit_code != 0
        assert "Project already contains identity collision(s) unrelated to this term" in result.output
        assert "concept:duplicate" in result.output
        assert "concept:new-term already resolves" not in result.output
        assert not (root / "knowledge" / "sources" / "local" / "terms.yaml").exists()


def test_terms_add_identity_precheck_loads_non_strict_with_commons_default(
    tmp_path: Path, monkeypatch
) -> None:
    import science_tool.terms as terms_module

    seed_project(tmp_path)
    calls: list[dict[str, object]] = []

    class StopAfterLoad(Exception):
        pass

    def fake_load_project_sources(project_root: Path, **kwargs: object):
        calls.append(kwargs)
        raise StopAfterLoad

    monkeypatch.setattr(terms_module, "load_project_sources", fake_load_project_sources)

    try:
        terms_module.add_term(
            project_root=tmp_path,
            term_id="concept:commons-owned",
            title="Commons owned",
        )
    except StopAfterLoad:
        pass
    else:
        raise AssertionError("expected fake loader to stop the command")

    assert calls == [{"strict_identity": False}]
```

Note the scope of this test: it is an argument-contract guard only. It proves
the identity precheck loads sources non-strict and does **not** override
`include_commons` (so the default `True` stands, and core/commons owners are in
the loaded set). The functional owner-collision path is exercised against
markdown, aggregate, and commons owners by
`test_terms_add_rejects_existing_markdown_owner`,
`test_terms_add_rejects_loaded_aggregate_owner`, and
`test_terms_add_rejects_existing_commons_owner`.

- [ ] **Step 3: Run the validation tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_terms_cli.py -q
```

Expected: PASS if Task 2's implementation exactly matches the intended validation contract. Any failures should be confined to the validation/identity tests (usually a message-wording or collision-string mismatch), never the Task 1 basics — reconcile those in Task 4.

- [ ] **Step 4: Commit the validation tests**

```bash
git add science/tests/test_terms_cli.py
git commit -m "test: cover terms add validation"
```

---

### Task 4: Complete Validation Behavior

**Files:**
- Modify: `science/src/science_tool/terms.py`
- Test: `science/tests/test_terms_cli.py`

- [ ] **Step 1: Confirm `terms.py` matches the validation contract**

Open `science/src/science_tool/terms.py` and make sure these exact implementation details are present:

```python
sources = load_project_sources(project_root, strict_identity=False)
```

```python
try:
    sources.registry.resolve(kind)
except EntityKindNotRegisteredError as exc:
    raise TermsCommandError(
        f"Unsupported term id prefix {kind!r}: the prefix must be a registered entity "
        "kind such as concept: or method:. If it is an external ontology CURIE prefix, "
        "pass the CURIE via --ontology-term instead of using it as the term id."
    ) from exc
```

```python
owners = [
    declaration
    for declaration in sources.identity_declarations
    if declaration.participation_mode is ParticipationMode.OWNER and declaration.canonical_id == term_id
]
```

```python
genuine_unrelated = [collision for collision in collisions if collision.is_genuine]
```

If any of those snippets are missing, apply the complete `terms.py` content from Task 2 Step 1 again and keep the imports in sync.

- [ ] **Step 2: Confirm the fake loader test stops immediately after source loading**

`test_terms_add_identity_precheck_loads_non_strict_with_commons_default` should use a private sentinel exception so it only verifies the source-load call signature and does not rely on any public `TermsCommandError` wrapping behavior:

```python
def test_terms_add_identity_precheck_loads_non_strict_with_commons_default(
    tmp_path: Path, monkeypatch
) -> None:
    import science_tool.terms as terms_module

    seed_project(tmp_path)
    calls: list[dict[str, object]] = []

    class StopAfterLoad(Exception):
        pass

    def fake_load_project_sources(project_root: Path, **kwargs: object):
        calls.append(kwargs)
        raise StopAfterLoad

    monkeypatch.setattr(terms_module, "load_project_sources", fake_load_project_sources)

    try:
        terms_module.add_term(
            project_root=tmp_path,
            term_id="concept:commons-owned",
            title="Commons owned",
        )
    except StopAfterLoad:
        pass
    else:
        raise AssertionError("expected fake loader to stop the command")

    assert calls == [{"strict_identity": False}]
```

- [ ] **Step 3: Run the focused terms tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_terms_cli.py -q
```

Expected: PASS.

- [ ] **Step 4: Run source-loader regression tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_load_project_sources_unified.py::test_load_project_sources_reads_lightweight_terms_yaml science/tests/test_load_project_sources_unified.py::test_concept_markdown_owner_collides_with_terms_yaml_under_strict_identity science/tests/test_load_project_sources_unified.py::test_concept_markdown_owner_wins_over_terms_yaml_in_nonstrict_load -q
```

Expected: PASS.

- [ ] **Step 5: Commit validation implementation**

```bash
git add science/src/science_tool/terms.py science/tests/test_terms_cli.py
git commit -m "fix: validate lightweight term authorship"
```

---

### Task 5: Add Failing Documentation Guard Tests

**Files:**
- Modify: `science/tests/test_user_guide_docs.py`
- Modify: `science/tests/test_command_docs.py`
- Modify: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Update user-guide guard tests**

Modify `science/tests/test_user_guide_docs.py`. There is no existing
lightweight-semantic-terms test to edit, and the source-authored-concepts /
epistemic tests use different names and section slices than an earlier draft
assumed. Make these three concrete changes, reusing the `_read`/`_norm`/`GUIDE_ROOT`
helpers already defined in this file (`_read` takes a `Path`).

**(a)** Add a new test for the entities lightweight-terms guidance:

```python
def test_entities_documents_terms_add_for_lightweight_terms() -> None:
    normalized = _norm(_read(GUIDE_ROOT / "entities.md"))

    assert "`terms.yaml` is for lightweight semantic rows" in normalized
    assert 'Use `science terms add <id> --title "<title>"` for routine lightweight term creation' in normalized
    assert "The command writes to the configured local profile's `terms.yaml`" in normalized
    assert "Do not pass external ontology CURIEs as the term id; put them in `--ontology-term`." in normalized
    assert "Promote the row to a Markdown entity owner when it accumulates body prose" in normalized
```

**(b)** In the existing `test_entities_chapter_documents_source_authored_concepts`
(it already asserts ``"`terms.yaml` is the lightweight concept tier"`` and
``"`science entity create concept"``), add one assertion so the tier line now
routes through the command:

```python
    assert "Use `science terms add concept:" in normalized
```

**(c)** Add a new test for the epistemic-model lightweight refs. Do not fold
this into `test_epistemic_model_documents_inquiry_ref_ownership_contract`; that
test slices only the "Inquiry Ref Ownership Contract" section, and the edited
wording lives earlier in the chapter:

```python
def test_epistemic_model_references_terms_add_for_lightweight_refs() -> None:
    normalized = _norm(_read(GUIDE_ROOT / "epistemic-model.md"))

    assert "source records or `science terms add` lightweight rows before the inquiry can be materialized" in normalized
    assert "Use `science terms add concept:" in normalized
    assert "`science entity create concept" in normalized
```

- [ ] **Step 2: Update command-doc guard tests**

Modify `science/tests/test_command_docs.py`.

In `test_sketch_model_uses_source_first_inquiry_authoring`, replace the old lightweight terms assertion with:

```python
    assert "Use `science terms add concept:" in normalized
    assert "when the term only needs a resolvable lightweight identity" in normalized
```

In `test_specify_model_marks_direct_graph_concepts_as_non_durable`, replace the old source-record assertion with:

```python
    assert "Make sure those refs resolve through source records, `science terms add` rows, or concept entity owners" in normalized
```

Add a new test near the existing concept ownership docs tests:

```python
def test_graph_and_health_commands_use_terms_add_for_lightweight_terms() -> None:
    create_graph = _norm(_read("commands/create-graph.md"))
    health = _norm(_read("commands/health.md"))

    assert "Use `science terms add <id> --title \"<title>\"` for simple project-scoped concepts" in create_graph
    assert "add a lightweight term with `science terms add`" in health
    assert "hand-edit `terms.yaml`" not in create_graph
```

- [ ] **Step 3: Update Codex skill guard tests**

Modify `science/tests/test_codex_skills.py`.

First, update the existing `test_create_graph_points_to_cookbook_for_new_entities`. Its assertion ``assert "lightweight `terms.yaml` row" in text`` guards wording that Task 6/7 removes from the regenerated `science-create-graph` skill, so it would fail after regeneration. Replace that one assertion with:

```python
    assert 'science terms add <id> --title "<title>"' in text
```

In `test_concept_ownership_committed_skills_reflect_command_boundaries`, replace the old lightweight terms assertions with:

```python
    assert "Use `science terms add concept:" in sketch_model
    assert "when the term only needs a resolvable lightweight identity" in sketch_model
    assert "Make sure those refs resolve through source records, `science terms add` rows, or concept entity owners" in specify_model
```

In `test_generated_concept_ownership_skills_reflect_command_boundaries`, make the same assertion replacements:

```python
    assert "Use `science terms add concept:" in sketch_model
    assert "when the term only needs a resolvable lightweight identity" in sketch_model
    assert "Make sure those refs resolve through source records, `science terms add` rows, or concept entity owners" in specify_model
```

Add this committed-skill test:

```python
def test_terms_authoring_committed_skills_use_terms_add() -> None:
    create_graph = _norm(_read_skill("science-create-graph"))
    health = _norm(_read_skill("science-health"))

    assert "Use `science terms add <id> --title \"<title>\"` for simple project-scoped concepts" in create_graph
    assert "add a lightweight term with `science terms add`" in health
```

Add this generated-skill test:

```python
def test_terms_authoring_generated_skills_use_terms_add(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    create_graph = _norm(generated["science-create-graph"].read_text(encoding="utf-8"))
    health = _norm(generated["science-health"].read_text(encoding="utf-8"))

    assert "Use `science terms add <id> --title \"<title>\"` for simple project-scoped concepts" in create_graph
    assert "add a lightweight term with `science terms add`" in health
```

- [ ] **Step 4: Run docs guard tests and verify they fail on old wording**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py -q
```

Expected: FAIL. Failures should point to missing `science terms add` wording in source docs and committed/generated skill mirrors.

- [ ] **Step 5: Commit the failing docs tests**

```bash
git add science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py
git commit -m "test: specify terms authoring docs"
```

---

### Task 6: Update User Guide And Command Docs

**Files:**
- Modify: `docs/user-guide/entities.md`
- Modify: `docs/user-guide/epistemic-model.md`
- Modify: `docs/user-guide/cli-and-workflows.md`
- Modify: `commands/sketch-model.md`
- Modify: `commands/specify-model.md`
- Modify: `commands/create-graph.md`
- Modify: `commands/health.md`
- Test: docs guard tests from Task 5

> **Editing note:** The "Replace … with …" target strings below are shown as
> single lines for readability, but several are line-wrapped in the source files
> (`sketch-model.md:177-178`, `specify-model.md:115-116`, `create-graph.md:38-39`,
> `epistemic-model.md:104-106`). A literal single-line find/replace will miss
> them. Match a distinctive fragment, replace the full wrapped span, then rely on
> the Task 5 guard tests (which normalize whitespace via `_norm`) to confirm the
> edit landed rather than eyeballing exact line breaks.

- [ ] **Step 1: Update `docs/user-guide/entities.md`**

Replace the stable project-local concept row with this text:

```markdown
| Stable project-local concept | Prefer the most specific registered source kind. When a local `concept:*` ref only needs a lightweight identity, use `science terms add concept:<slug> --title "<title>"`; when it needs prose, lifecycle status, source refs, aliases, same-as links, or relationships, create a Markdown owner with `science entity create concept ...`. |
```

Replace the `### Lightweight Semantic Terms` section body through the paragraph ending `lifecycle work.` with:

```markdown
`terms.yaml` is for lightweight semantic rows that are more durable than a
one-off prose label but do not yet deserve a full Markdown owner. Use
`science terms add <id> --title "<title>"` for routine lightweight term
creation:

```bash
science terms add concept:treatment-response --title "Treatment response"
science terms add method:cox-regression --title "Cox proportional-hazards regression" --ontology-term "biolink:StatisticalMethod"
```

The command writes to the configured local profile's `terms.yaml`, usually
`knowledge/sources/local/terms.yaml`, and appends a minimal row:

```yaml
terms:
  - id: concept:treatment-response
    title: Treatment response
```

Keep entries minimal: `id` and `title` are required; `--alias`, `--same-as`,
`--ontology-term`, and `--description` are optional. Do not pass external
ontology CURIEs as the term id; put them in `--ontology-term`. Promote the row
to a Markdown entity owner when it accumulates body prose, structured
relations, or lifecycle work.
```

In `### Source-Authored Concepts`, replace:

```markdown
`terms.yaml` is the lightweight concept tier. Use it when a term needs a stable
resolvable `concept:*` identity but does not need body prose, lifecycle work, or
structured relationships.
```

with:

```markdown
`terms.yaml` is the lightweight concept tier. Use
`science terms add concept:<slug> --title "<title>"` when a term needs a stable
resolvable `concept:*` identity but does not need body prose, lifecycle work, or
structured relationships.
```

- [ ] **Step 2: Update `docs/user-guide/epistemic-model.md`**

Replace:

```markdown
source records or lightweight term rows before the inquiry can be materialized.
```

with:

```markdown
source records or `science terms add` lightweight rows before the inquiry can be materialized.
```

Replace:

```markdown
Use `concept:*` only when that ref already resolves through a source owner. Use
a local-profile `terms.yaml` row for lightweight terms, or
`science entity create concept "<title>"` when the project-local concept needs a
full Markdown owner under `entities/concepts/`.
```

with:

```markdown
Use `concept:*` only when that ref already resolves through a source owner. Use
`science terms add concept:<slug> --title "<title>"` for lightweight terms, or
`science entity create concept "<title>"` when the project-local concept needs a
full Markdown owner under `entities/concepts/`.
```

- [ ] **Step 3: Update `docs/user-guide/cli-and-workflows.md`**

Find the command-family taxonomy table and add a row for `terms` in the source-write section:

```markdown
| `terms` | Source-write | Creates lightweight local semantic term rows in the configured local profile's `terms.yaml`. |
```

If the table is grouped differently, preserve the existing table columns and use this exact wording in the description:

```markdown
Creates lightweight local semantic term rows in the configured local profile's `terms.yaml`.
```

- [ ] **Step 4: Update `commands/sketch-model.md`**

Replace:

```markdown
Use a lightweight `terms.yaml` row when the term only needs a resolvable identity.
```

with:

```markdown
Use `science terms add concept:<slug> --title "<title>"` when the term only needs a resolvable lightweight identity.
```

Keep the existing negative guard against fenced `science graph add concept` examples.

- [ ] **Step 5: Update `commands/specify-model.md`**

Replace:

```markdown
Make sure those refs resolve through source records, lightweight term rows, or concept entity owners before rebuilding the
```

with:

```markdown
Make sure those refs resolve through source records, `science terms add` rows, or concept entity owners before rebuilding the
```

Preserve the surrounding line wrapping if needed, but keep the full sentence readable after `_norm()`.

- [ ] **Step 6: Update `commands/create-graph.md`**

Replace:

```markdown
Use a lightweight `terms.yaml` row for simple project-scoped concepts, or `science entity create concept "<title>"` when
```

with:

```markdown
Use `science terms add <id> --title "<title>"` for simple project-scoped concepts, or `science entity create concept "<title>"` when
```

- [ ] **Step 7: Update `commands/health.md`**

Replace the semantic triage bullet that mentions adding a lightweight `terms.yaml` row with wording containing:

```markdown
add a lightweight term with `science terms add`
```

For example:

```markdown
- Semantic triage: create or reuse the typed entity chosen by the cookbook, add a lightweight term with `science terms add`, create a full concept entity with `science entity create concept "<title>"`, or leave the ref in prose until it has a durable owner.
```

- [ ] **Step 8: Run docs guard tests before regenerating skills**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py -q
```

Expected: FAIL only for committed Codex skill mirror assertions. Source docs and generated-skill assertions should pass.

Do not commit yet; regenerate mirrors in Task 7.

---

### Task 7: Regenerate Codex Skills And Commit Docs

**Files:**
- Modify generated files under `codex-skills/science-*/SKILL.md`
- Modify docs from Task 6
- Test: docs guard tests from Task 5

- [ ] **Step 1: Regenerate Codex skills**

Run:

```bash
rtk uv run --project science python scripts/generate_codex_skills.py
```

Expected: generated `codex-skills/science-create-graph/SKILL.md`, `codex-skills/science-health/SKILL.md`, `codex-skills/science-sketch-model/SKILL.md`, and `codex-skills/science-specify-model/SKILL.md` reflect the source command doc changes.

- [ ] **Step 2: Inspect generated diff for unintended broad churn**

Run:

```bash
git diff --stat codex-skills commands docs/user-guide science/tests
```

Expected: changed generated mirrors correspond to changed command docs. If unrelated generated mirrors changed, inspect them and only keep changes caused by the source docs in this plan.

- [ ] **Step 3: Run docs tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit docs and generated mirrors**

```bash
git add docs/user-guide/entities.md docs/user-guide/epistemic-model.md docs/user-guide/cli-and-workflows.md commands/sketch-model.md commands/specify-model.md commands/create-graph.md commands/health.md codex-skills science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py
git commit -m "docs: route lightweight terms through terms add"
```

---

### Task 8: Final Verification

**Files:**
- All files touched by Tasks 1-7

- [ ] **Step 1: Run focused behavior and docs tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_terms_cli.py science/tests/test_load_project_sources_unified.py::test_load_project_sources_reads_lightweight_terms_yaml science/tests/test_load_project_sources_unified.py::test_concept_markdown_owner_collides_with_terms_yaml_under_strict_identity science/tests/test_load_project_sources_unified.py::test_concept_markdown_owner_wins_over_terms_yaml_in_nonstrict_load science/tests/test_user_guide_docs.py science/tests/test_command_docs.py science/tests/test_codex_skills.py -q
```

Expected: PASS.

- [ ] **Step 2: Run CLI surface contract tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp rtk uv run --project science pytest science/tests/test_cli_surface_contract.py -q
```

Expected: PASS with no edits to `test_cli_surface_contract.py`. Because `terms add` exposes only `--project-root` (no `--project` alias), the exact-equality `--project` allowlist in `test_project_option_usage_is_intentionally_classified` is untouched, and `test_project_root_aliases_exist_for_touched_filesystem_project_flags` only requires its listed commands to carry `--project-root` — it does not forbid an unlisted command from exposing it. If this test fails, do not add `--project`; keep the surface to `--project-root` only.

- [ ] **Step 3: Check formatting whitespace**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Inspect final status and commits**

Run:

```bash
git status --short --branch
git log --oneline -6
```

Expected: worktree clean except for any user-owned changes that existed before implementation. Recent commits should show the tests, implementation, validation, and docs commits from this plan.

---

## Self-Review Checklist

- Spec coverage:
  - `science terms add` command: Tasks 1-2.
  - Configured local profile only, no free-form `--profile`: Tasks 1-2 and Task 3 rejected-flag tests.
  - Minimal YAML rows and append-only ordering: Tasks 1-2.
  - Registered entity-kind prefix validation and external ontology-prefix rejection: Tasks 3-4.
  - Duplicate target rows and loaded owner collisions: Tasks 3-4.
  - Non-strict source load and unrelated collision diagnostic: Tasks 3-4.
  - Commons/core owner rejection: covered by the end-to-end commons-owner test and the argument-contract guard that keeps `include_commons` at its default.
  - Reload through `load_project_sources()` with title: Task 1.
  - Docs and generated Codex mirrors: Tasks 5-7.
  - Final verification: Task 8.
- Placeholder scan:
  - The plan has been scanned for unfinished markers and vague validation instructions.
  - Every changed code path has concrete test and implementation snippets.
- Type consistency:
  - Public writer is `add_term(...)`.
  - CLI error type is `TermsCommandError`.
  - Result type is `TermsAddResult`.
  - YAML field names are `id`, `title`, `description`, `aliases`, `same_as`, and `ontology_terms`.
