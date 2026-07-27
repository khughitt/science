# Coding Agent Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the host-specific skill generators and unsafe installer with one committed Agent Skills distribution for Codex, Crush, and OpenCode, plus thin OpenCode command adapters and consolidated user documentation.

**Architecture:** `science_tool.agent_assets` is the single generator boundary: one call renders command skills, the non-invocable command-support package, methodology routers, and OpenCode adapters into explicit output roots. `science_tool.agents_cli` validates repository and install inputs at the CLI boundary, constructs a complete immutable link plan, rejects every collision before mutation, and then installs the same generated skill set for all three hosts.

**Tech Stack:** Python 3.11+, Click, pytest, PyYAML, Markdown/Agent Skills packages, filesystem symlinks.

## Global Constraints

- Preserve the canonical authored corpus directly under `skills/`; `skills/generated/` is a committed distribution mirror and must be excluded from canonical inventory and lint discovery.
- Use one shared Agent Skills tree for Codex, Crush, and OpenCode; do not add host-specific generated skill trees.
- Remove `codex-skills/`, the old generator API/script, `--agent`, `--format`, `--output-dir`, and installer `--copy` without a compatibility layer.
- Keep command preamble prose inline in every command skill; delegate only role prompts, aspects, and the generated methodology-router index to non-invocable `science-command-preamble`.
- Emit `user-invocable: true` only for command-derived skills.
- Generated bodies must contain neither “Converted from Claude command …” nor “Adapted from canonical Science skill …” notes.
- Every path-based generated reference stays inside its package; every sibling-skill dependency names an emitted package.
- Install only absolute symlinks; correct links are idempotent and every other file, directory, or symlink collision is preserved and refused.
- Validate the complete install plan, including `science-command-preamble`, before creating any destination.
- Project scope uses `<project>/.agents/skills`; user scope uses `~/.agents/skills`; OpenCode also receives commands in the scope-appropriate OpenCode command directory.
- Use `~/d/` rather than machine-specific absolute paths in code and documentation.
- Run all Python commands from `science/`; do not run concurrent test suites in this worktree.

---

## File and Interface Map

### Created

- `science/src/science_tool/agent_assets.py` — parses canonical sources, computes package ownership/dependencies, renders both generated trees, prunes stale output, and returns `GenerationResult`.
- `science/tests/test_agent_assets.py` — neutral generator contract, rendering, resource-closure, dependency, pruning, and committed-byte tests; incorporates still-valid behavioral assertions from `test_codex_skills.py`.
- `science/tests/test_agents_cli.py` — repository discovery, CLI surface, install planning, collision preservation, scope selection, and symlink tests.
- `scripts/generate_agent_assets.py` — repository-development entry point calling the neutral generator.
- `docs/user-guide/coding-agents.md` — common distribution, install, update, checkout-lifetime, and manual removal model.
- `docs/user-guide/crush.md` — Crush discovery and command-palette behavior.
- `docs/user-guide/opencode.md` — OpenCode skill and namespaced-command behavior.
- `skills/generated/**` — committed shared Agent Skills distribution.
- `commands/opencode/**` — committed thin OpenCode adapters.

### Renamed or replaced

- `science/src/science_tool/codex_skills.py` → `science/src/science_tool/agent_assets.py`
- `science/tests/test_codex_skills.py` → `science/tests/test_agent_assets.py`
- `scripts/generate_codex_skills.py` → `scripts/generate_agent_assets.py`

### Modified

- `science/src/science_tool/agents_cli.py` — neutral generation command and fail-before-write installer.
- `science/src/science_tool/graph/skill_inventory.py` — central `skills/generated/` exclusion.
- `science/src/science_tool/skills_lint/discovery.py` — central `generated/` exclusion.
- `science/tests/test_skill_inventory.py` — generated-prefix exclusion regression.
- `science/tests/skills_lint/test_discovery.py` — generated-prefix exclusion regression.
- `science/tests/test_command_docs.py` — non-recursive canonical command-discovery guard.
- `science/tests/test_no_raw_task_file_reads_in_docs.py` — replace the retired `codex-skills/` exclusion with `skills/generated/`.
- `science/src/science_tool/cli.py` — retains only the simplified `agents` group registration.
- `README.md`, `docs/user-guide/index.md`, `docs/user-guide/codex.md`, `mkdocs.yml` — consolidated agent documentation and navigation.

### Deleted

- `INSTALL.crush.md`
- `INSTALL.opencode.md`
- `MULTI_AGENT.md`
- `codex-skills/**`

### Internal contracts

```python
@dataclass(frozen=True)
class GenerationResult:
    skill_paths: Mapping[str, Path]
    opencode_command_paths: Mapping[str, Path]


def validate_repo_root(candidate: Path) -> Path:
    """Return an absolute toolkit root or raise ValueError."""


def generate_agent_assets(
    repo_root: Path,
    skills_output_root: Path,
    opencode_commands_output_root: Path,
) -> GenerationResult:
    """Render and validate both generated distributions."""


AgentName = Literal["codex", "crush", "opencode"]
InstallScope = Literal["project", "user"]


@dataclass(frozen=True)
class LinkSpec:
    source: Path
    destination: Path


@dataclass(frozen=True)
class InstallPlan:
    links: tuple[LinkSpec, ...]
    current: tuple[LinkSpec, ...]


def build_install_plan(
    *,
    repo_root: Path,
    agent: AgentName,
    scope: InstallScope,
    project_dir: Path,
    user_home: Path,
) -> InstallPlan:
    """Validate sources and collisions without changing the filesystem."""


def apply_install_plan(plan: InstallPlan) -> tuple[LinkSpec, ...]:
    """Create only the not-already-current links from a validated plan."""
```

`validate_repo_root` and `generate_agent_assets` raise `ValueError` for invalid
developer inputs. Click commands translate those errors into `click.ClickException`.
`build_install_plan` raises `click.ClickException` because collisions and
incomplete committed distributions are user-facing install failures.

---

### Task 1: Protect canonical discovery boundaries

**Files:**

- Modify: `science/src/science_tool/graph/skill_inventory.py`
- Modify: `science/src/science_tool/skills_lint/discovery.py`
- Modify: `science/tests/test_skill_inventory.py`
- Modify: `science/tests/skills_lint/test_discovery.py`
- Modify: `science/tests/test_command_docs.py`

**Interfaces:**

- Consumes: canonical roots `repo_root / "skills"` and `repo_root / "commands"`.
- Produces: prefix-based exclusion of `skills/generated/**`; a guarded contract that canonical command enumeration is `commands/*.md`, never recursive.

- [ ] **Step 1: Write failing generated-prefix discovery tests**

Add generated files, including the nested generated index, to the existing
fixtures:

```python
def test_real_skill_paths_excludes_generated_distribution(tmp_path: Path) -> None:
    _write(tmp_path, "skills/bio/x-qa.md")
    _write(tmp_path, "skills/generated/INDEX.md")
    _write(tmp_path, "skills/generated/science-status/SKILL.md")

    assert real_skill_paths(tmp_path) == {"skills/bio/x-qa.md"}
```

```python
def test_iter_skill_files_excludes_generated_distribution(tmp_path: Path) -> None:
    for rel in (
        "INDEX.md",
        "data/SKILL.md",
        "generated/INDEX.md",
        "generated/science-status/SKILL.md",
        "generated/science-status/references/context.md",
    ):
        _touch(tmp_path / rel)

    found = {path.relative_to(tmp_path).as_posix() for path in iter_skill_files(tmp_path)}

    assert found == {"INDEX.md", "data/SKILL.md"}
```

- [ ] **Step 2: Write the failing command-discovery guard**

Add a helper and test beside the other command-document tests:

```python
def _canonical_command_paths() -> list[Path]:
    return sorted((ROOT / "commands").glob("*.md"))


def test_generated_opencode_adapters_are_not_canonical_commands() -> None:
    canonical = _canonical_command_paths()

    assert canonical
    assert all(path.parent == ROOT / "commands" for path in canonical)
    assert not any("opencode" in path.parts for path in canonical)
```

Change command-document loops in this module to use
`_canonical_command_paths()` so the discovery boundary has one definition.

- [ ] **Step 3: Run the new tests and verify they fail**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_skill_inventory.py::test_real_skill_paths_excludes_generated_distribution \
  tests/skills_lint/test_discovery.py::test_iter_skill_files_excludes_generated_distribution \
  tests/test_command_docs.py::test_generated_opencode_adapters_are_not_canonical_commands
```

Expected: the two skill-discovery tests include generated paths and fail; the
command test passes as a guard.

- [ ] **Step 4: Add prefix exclusions at the discovery functions**

Use repository-relative prefixes in inventory and skill-root-relative prefixes
in lint discovery:

```python
# graph/skill_inventory.py
if (
    rel == "skills/INDEX.md"
    or rel.startswith("skills/generated/")
    or rel.startswith("skills/meta/templates/")
):
    continue
```

```python
# skills_lint/discovery.py
EXCLUDED_PREFIXES = ("generated/", "meta/templates/")


def iter_skill_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(EXCLUDED_PREFIXES):
            continue
        yield path
```

- [ ] **Step 5: Run the boundary suite**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_skill_inventory.py \
  tests/skills_lint/test_discovery.py \
  tests/skills_lint/test_lint.py \
  tests/skills_lint/test_cli.py \
  tests/test_command_docs.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add \
  science/src/science_tool/graph/skill_inventory.py \
  science/src/science_tool/skills_lint/discovery.py \
  science/tests/test_skill_inventory.py \
  science/tests/skills_lint/test_discovery.py \
  science/tests/test_command_docs.py
git commit -m "test(agents): isolate generated skill discovery"
```

---

### Task 2: Establish the neutral command-skill generator and support package

**Files:**

- Rename: `science/src/science_tool/codex_skills.py` → `science/src/science_tool/agent_assets.py`
- Rename: `science/tests/test_codex_skills.py` → `science/tests/test_agent_assets.py`
- Modify: `science/tests/test_agent_assets.py`

**Interfaces:**

- Consumes: canonical `commands/*.md`, `references/command-preamble.md`, `references/role-prompts/*.md`, `aspects/*/*.md`.
- Produces: `GenerationResult`, command-derived `science-*` packages, and `science-command-preamble`.

- [ ] **Step 1: Rename the module and tests, then replace old imports**

Use Git-aware moves:

```bash
git mv science/src/science_tool/codex_skills.py science/src/science_tool/agent_assets.py
git mv science/tests/test_codex_skills.py science/tests/test_agent_assets.py
```

In the renamed test module import only:

```python
from science_tool.agent_assets import (
    GenerationResult,
    command_to_skill_name,
    generate_agent_assets,
)
```

Delete assertions for `generate_codex_skills`, agent-specific headings,
conversion notes, and `codex-skills/INSTALL.codex.md`. Keep the existing
domain-content regression assertions, changing their generated root helper to
`skills_root`.

- [ ] **Step 2: Write failing command/support package contract tests**

Add a fixture that always supplies both explicit temporary roots:

```python
@pytest.fixture
def generated(tmp_path: Path) -> GenerationResult:
    return generate_agent_assets(
        ROOT,
        tmp_path / "skills",
        tmp_path / "commands",
    )
```

Add:

```python
def test_command_skills_are_neutral_invocable_and_inline_preamble(
    generated: GenerationResult,
) -> None:
    command_names = {
        command_to_skill_name(path)
        for path in sorted((ROOT / "commands").glob("*.md"))
    }
    for name in sorted(command_names):
        path = generated.skill_paths[name]
        text = path.read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "user-invocable: true" in text
        assert "## Science Command Preamble" in text
        assert "Resolve project profile" in text
        assert "Converted from Claude command" not in text
        assert "Science Codex" not in text
        assert "Science Crush" not in text
        assert "Science OpenCode" not in text


def test_command_support_skill_is_non_invocable_and_resource_only(
    generated: GenerationResult,
) -> None:
    support = generated.skill_paths["science-command-preamble"].parent
    text = (support / "SKILL.md").read_text(encoding="utf-8")
    assert "name: science-command-preamble" in text
    assert "loaded by Science command skills" in text
    assert "not invoked directly" in text
    assert "user-invocable" not in text
    assert sorted(path.name for path in (support / "references" / "role-prompts").glob("*.md")) == [
        "discussant.md",
        "research-assistant.md",
    ]
    assert sorted(path.parent.name for path in (support / "references" / "aspects").glob("*/*.md")) == [
        "causal-modeling",
        "computational-analysis",
        "hypothesis-testing",
        "software-development",
    ]
```

Add parameterized role tests using one command that declares
`research-assistant` and one that declares `discussant`; assert the rendered
numbered step says to load `science-command-preamble` and names the role, with
no text implying argument or parameter passing.

- [ ] **Step 3: Run the focused tests and verify the removed interface fails**

Run:

```bash
cd science
uv run --frozen pytest tests/test_agent_assets.py -x
```

Expected: collection or first execution fails because
`GenerationResult`/`generate_agent_assets` and the new rendering contract do
not exist.

- [ ] **Step 4: Define the neutral public result and entry point**

At the top of `agent_assets.py` define:

```python
from collections.abc import Mapping
from dataclasses import dataclass


COMMAND_PREAMBLE_HEADING = "## Science Command Preamble"
COMMAND_SUPPORT_SKILL = "science-command-preamble"


@dataclass(frozen=True)
class GenerationResult:
    skill_paths: Mapping[str, Path]
    opencode_command_paths: Mapping[str, Path]


def validate_repo_root(candidate: Path) -> Path:
    root = candidate.expanduser().resolve()
    sentinels = (
        root / "commands",
        root / "skills" / "INDEX.md",
        root / "references" / "command-preamble.md",
        root / "aspects",
    )
    if not (
        sentinels[0].is_dir()
        and sentinels[1].is_file()
        and sentinels[2].is_file()
        and sentinels[3].is_dir()
    ):
        raise ValueError(f"not a Science toolkit root: {root}")
    return root


def generate_agent_assets(
    repo_root: Path,
    skills_output_root: Path,
    opencode_commands_output_root: Path,
) -> GenerationResult:
    repo_root = validate_repo_root(repo_root)
    _validate_output_root(
        repo_root / "skills",
        skills_output_root,
        repo_root / "skills" / "generated",
    )
    _validate_output_root(
        repo_root / "commands",
        opencode_commands_output_root,
        repo_root / "commands" / "opencode",
    )
    command_paths = sorted((repo_root / "commands").glob("*.md"))
    skills_output_root.mkdir(parents=True, exist_ok=True)
    opencode_commands_output_root.mkdir(parents=True, exist_ok=True)

    skill_paths = _generate_command_skills(
        repo_root,
        skills_output_root,
        command_paths,
    )
    skill_paths[COMMAND_SUPPORT_SKILL] = _generate_command_support_skill(
        repo_root,
        skills_output_root,
    )
    return GenerationResult(
        skill_paths=skill_paths,
        opencode_command_paths={},
    )
```

`validate_repo_root` resolves the path and requires all four sentinels:
`commands/`, `skills/INDEX.md`, `references/command-preamble.md`, and
`aspects/`. It raises `ValueError("not a Science toolkit root: <path>")` on
failure instead of returning the current directory.

Add a test that passes `repo_root / "skills" / "accidental"` and a test that
passes `repo_root / "commands" / "accidental"`; both must fail before creating
the output. `_validate_output_root` permits the declared committed root or any
root outside its canonical source tree:

```python
def _validate_output_root(
    canonical_root: Path,
    output_root: Path,
    committed_root: Path,
) -> None:
    resolved = output_root.resolve()
    if resolved == committed_root.resolve():
        return
    try:
        resolved.relative_to(canonical_root.resolve())
    except ValueError:
        return
    raise ValueError(
        f"generated output inside canonical source tree: {resolved}"
    )
```

- [ ] **Step 5: Render the inline preamble and generation-time role**

Parse the role from the parenthesized or “with role” canonical preamble
instruction, including a wrapped line, with:

```python
COMMAND_ROLE_RE = re.compile(
    r"Follow `(?:\$\{CLAUDE_PLUGIN_ROOT\}/)?references/command-preamble\.md`"
    r"(?:\s+\(role:\s*|\s+with role\s+)`?"
    r"(research-assistant|discussant)`?",
    re.MULTILINE,
)
```

Render this exact numbered setup wording before the rest of the rewritten
preamble:

```markdown
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/<role>.md` role prompt and its aspect definitions.
```

For commands without an explicit role, use `research-assistant`; `discussant`
is opt-in and is declared explicitly by the discussion command. Keep the entire
rewritten preamble body inline, but replace:

- the role fallback with the support-skill step above;
- `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` with the support package's generated
  methodology index and generated-router loading instruction;
- canonical aspect paths with support-package aspect references;
- Claude `$ARGUMENTS` prose with agent-neutral “user input” wording.

Emit frontmatter in this form:

```python
header = [
    "---",
    f"name: {skill_name}",
    f'description: "{escaped_description}"',
    "user-invocable: true",
    "---",
    "",
]
```

The command loop has one neutral signature and returns the files it actually
wrote:

```python
def _generate_command_skills(
    repo_root: Path,
    output_root: Path,
    command_paths: list[Path],
) -> dict[str, Path]:
    preamble = _load_command_preamble(repo_root)
    generated = {}
    for command_path in command_paths:
        name = command_to_skill_name(command_path)
        title, description, body = _parse_command(command_path)
        role = _command_role(body)
        skill_dir = output_root / name
        _replace_generated_directory(skill_dir)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(
            _render_command_skill(
                name=name,
                title=title,
                description=description,
                body=body,
                preamble=preamble,
                role=role,
            ),
            encoding="utf-8",
        )
        generated[name] = skill_path
    return generated
```

`_render_command_skill` implements the ordered rewrites and exact frontmatter
shown above. `_command_role` accepts only the two canonical role names and
raises `ValueError` when an explicit role instruction contains anything else.

- [ ] **Step 6: Generate the support package resources**

Implement `_generate_command_support_skill` by recreating only its owned
directory and copying the two resource trees structure-preservingly:

```python
def _generate_command_support_skill(repo_root: Path, output_root: Path) -> Path:
    skill_dir = output_root / COMMAND_SUPPORT_SKILL
    _replace_generated_directory(skill_dir)
    _copy_tree(repo_root / "references" / "role-prompts", skill_dir / "references" / "role-prompts")
    _copy_tree(repo_root / "aspects", skill_dir / "references" / "aspects")
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            (
                "---",
                f"name: {COMMAND_SUPPORT_SKILL}",
                'description: "Support resources loaded by Science command skills; not invoked directly."',
                "---",
                "",
                "# Science Command Support Resources",
                "",
                "Use the named role prompt, aspect definitions, and methodology index requested by the loading Science command skill.",
                "",
            )
        ),
        encoding="utf-8",
    )
    return skill_dir / "SKILL.md"
```

`_copy_tree` recursively copies files in sorted order and creates parents; it
does not call `copytree` over an existing generated directory.

```python
def _replace_generated_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError(f"generated package path is not a directory: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"generated resource source is not a directory: {source}")
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
```

- [ ] **Step 7: Run the command/support tests**

Run:

```bash
cd science
uv run --frozen pytest tests/test_agent_assets.py -k \
  "command or preamble or role or arguments or cli_compatibility"
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  science/src/science_tool/agent_assets.py \
  science/tests/test_agent_assets.py
git commit -m "feat(agents): generate neutral command skills"
```

---

### Task 3: Generate methodology routers and enforce package ownership

**Files:**

- Modify: `science/src/science_tool/agent_assets.py`
- Modify: `science/tests/test_agent_assets.py`

**Interfaces:**

- Consumes: every `skills/*/SKILL.md`, its recursive local subtree, and the standalone `skills/writing/scientific-writing.md`.
- Produces: one emitted owner per canonical `skills/` source, generated router dependencies, and the support package's generated router index.

- [ ] **Step 1: Write failing router inventory and recursive-resource tests**

Derive expected routers from frontmatter rather than hard-coding directory
names:

```python
def _frontmatter_name(path: Path) -> str:
    match = re.search(
        r"^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$",
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, path
    return match.group(1)


def test_every_top_level_router_has_one_generated_package(
    generated: GenerationResult,
) -> None:
    expected = {
        f"science-{_frontmatter_name(path)}"
        for path in sorted((ROOT / "skills").glob("*/SKILL.md"))
    }
    expected.add("science-scientific-writing")
    assert expected <= set(generated.skill_paths)


@pytest.mark.parametrize(
    ("skill_name", "resource"),
    (
        ("science-bio", "references/genomics/somatic-mutation-qa.md"),
        ("science-literature", "references/sources/openalex.md"),
        ("science-skill-development", "references/templates/router.md"),
    ),
)
def test_methodology_resources_are_recursive(
    generated: GenerationResult,
    skill_name: str,
    resource: str,
) -> None:
    assert (generated.skill_paths[skill_name].parent / resource).is_file()
```

Add tests that `science-writing` does not contain
`references/scientific-writing.md`, delegates to
`science-scientific-writing`, and all generated methodology/support skills omit
`user-invocable`.

Adapt the existing dangling-link helper into a parameterized portability test:
generate packages, symlink each package into a temporary
`.agents/skills/<name>`, parse every relative Markdown link, and assert it
resolves both from the committed-style package path and from the installed
symlink path. Explicit sibling-skill loads are validated by emitted name rather
than treated as filesystem links.

- [ ] **Step 2: Write failing ownership and dependency tests**

Create a small temporary canonical fixture in which two routers would own one
canonical `skills/` source and assert `ValueError` contains
`"canonical skill source has multiple owners"`. Add a dependency validator
test that removes a declared generated package from the in-memory emitted-name
set and asserts `"missing generated skill dependency"`.

Add the real-corpus assertion:

```python
def test_command_skill_references_to_canonical_skills_become_router_loads(
    generated: GenerationResult,
) -> None:
    for command in ("science-plan-analysis", "science-pre-register"):
        root = generated.skill_paths[command].parent
        text = (root / "SKILL.md").read_text(encoding="utf-8")
        assert "science-study-design" in text
        assert not list(root.rglob("estimator-certification.md"))
```

- [ ] **Step 3: Run the router tests and verify they fail**

Run:

```bash
cd science
uv run --frozen pytest tests/test_agent_assets.py -k \
  "router or methodology or recursive or owner or dependency or scientific_writing"
```

Expected: FAIL because only the two legacy companion packages exist and
resource copying is flat.

- [ ] **Step 4: Build an explicit canonical-source ownership map**

Introduce:

```python
@dataclass(frozen=True)
class MethodologyPackage:
    name: str
    router_source: Path
    owned_sources: tuple[Path, ...]


def _methodology_packages(repo_root: Path) -> tuple[MethodologyPackage, ...]:
    packages = []
    for router in sorted((repo_root / "skills").glob("*/SKILL.md")):
        canonical_name, _, _ = _parse_skill(router)
        owned = tuple(
            path
            for path in sorted(router.parent.rglob("*"))
            if path.is_file()
        )
        if router.parent.name == "writing":
            owned = tuple(path for path in owned if path.name != "scientific-writing.md")
        packages.append(
            MethodologyPackage(
                name=f"science-{canonical_name}",
                router_source=router,
                owned_sources=owned,
            )
        )
    packages.append(
        MethodologyPackage(
            name="science-scientific-writing",
            router_source=repo_root / "skills" / "writing" / "scientific-writing.md",
            owned_sources=(repo_root / "skills" / "writing" / "scientific-writing.md",),
        )
    )
    _validate_unique_skill_owners(packages, repo_root)
    return tuple(packages)
```

When validating owners, only paths under canonical `repo_root / "skills"` are
unique. Documentation and template resources bundled into separate commands
do not enter this ownership map.

- [ ] **Step 5: Render recursive methodology packages**

For each package:

1. Recreate `skills_output_root / package.name`.
2. Render its router as `SKILL.md` with emitted `name`, canonical description,
   no `user-invocable`, and no adaptation note.
3. Copy every other owned file to
   `references/<path-relative-to-router-parent>`, except rename any nested
   canonical `SKILL.md` to `router.md`.
4. Rewrite links within the owned subtree to their new relative package paths.
5. Rewrite a link leaving the owned subtree to a context-safe
   `` `<owning-generated-name>` skill `` noun phrase and record that
   dependency. Process whole Markdown links before bare backticked paths.
   Preserve imperative “Load ...” wording only when the complete source
   instruction is imperative.
6. Special-case no source identity: `science-writing` delegates to
   `science-scientific-writing`; it never owns the leaf.

Use `PurePosixPath` for emitted Markdown references so generated bytes do not
depend on the development platform. Assert that every emitted package contains
exactly one `SKILL.md`, at its root: Codex, Crush, and OpenCode may scan skill
roots recursively, and a preserved nested `SKILL.md` would be mis-discovered as
an undeclared extra skill.

- [ ] **Step 6: Generate the support methodology index**

Write `science-command-preamble/references/methodology-index.md` from the
methodology package records:

```markdown
# Science Methodology Skills

- `science-bio`
- `science-data-management`
- `science-epistemics`
```

Include every top-level generated methodology router and
`science-scientific-writing`, sorted by emitted identity. Do not include source
paths. Validate every name in this index against the complete emitted package
set.

- [ ] **Step 7: Validate all generated sibling dependencies**

After all package names are known and before returning `GenerationResult`,
validate the recorded dependency map:

```python
def _validate_dependencies(
    dependencies: Mapping[str, set[str]],
    emitted_names: set[str],
) -> None:
    for owner, targets in sorted(dependencies.items()):
        missing = sorted(targets - emitted_names)
        if missing:
            raise ValueError(
                f"missing generated skill dependency for {owner}: {missing}"
            )
```

Every command has `science-command-preamble`; commands with canonical
methodology references also have the owning router. Every adapter dependency
is added in Task 4.

- [ ] **Step 8: Run all generator tests**

Run:

```bash
cd science
uv run --frozen pytest tests/test_agent_assets.py
```

Expected: PASS, including the migrated domain-content regressions.

- [ ] **Step 9: Commit**

```bash
git add \
  science/src/science_tool/agent_assets.py \
  science/tests/test_agent_assets.py
git commit -m "feat(agents): generate methodology skill packages"
```

---

### Task 4: Generate OpenCode adapters and committed distributions

**Files:**

- Modify: `science/src/science_tool/agent_assets.py`
- Modify: `science/tests/test_agent_assets.py`
- Rename: `scripts/generate_codex_skills.py` → `scripts/generate_agent_assets.py`
- Modify: `science/src/science_tool/agents_cli.py`
- Modify: `science/src/science_tool/cli.py`
- Delete: `codex-skills/**`
- Create: `skills/generated/**`
- Create: `commands/opencode/**`
- Modify: `science/tests/test_no_raw_task_file_reads_in_docs.py`

**Interfaces:**

- Consumes: complete skill-name set from Task 3 and canonical command descriptions.
- Produces: namespaced `$ARGUMENTS` adapters, neutral generated provenance index, stale-output pruning, `science agents generate`.

- [ ] **Step 1: Write failing adapter, pruning, and byte-equality tests**

Add:

```python
def test_opencode_adapters_are_thin_and_namespaced(
    generated: GenerationResult,
) -> None:
    expected = {
        f"science-{path.stem}"
        for path in sorted((ROOT / "commands").glob("*.md"))
    }
    assert set(generated.opencode_command_paths) == expected
    for name, path in generated.opencode_command_paths.items():
        text = path.read_text(encoding="utf-8")
        assert path.name == f"{name}.md"
        assert f"Load and execute the `{name}` skill" in text
        assert "$ARGUMENTS" in text
        assert "## Science Command Preamble" not in text
```

Add stale skill-directory and stale adapter files before a second generation
and assert both disappear. Add a static non-generated file in each output root
and assert generation raises rather than guessing whether it owns the file.

Add a recursive byte map helper:

```python
def _file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
```

Compare temporary generation exactly with committed `skills/generated/` and
`commands/opencode/`.

- [ ] **Step 2: Run the adapter tests and verify they fail**

Run:

```bash
cd science
uv run --frozen pytest tests/test_agent_assets.py -k \
  "opencode or stale or committed"
```

Expected: FAIL because no adapters are returned and committed roots do not
match.

- [ ] **Step 3: Render thin adapters and neutral distribution index**

For every canonical command, emit:

```python
def _render_opencode_adapter(name: str, description: str) -> str:
    return "\n".join(
        (
            "---",
            f"description: {description}",
            "---",
            "",
            f"Load and execute the `{name}` skill using this input:",
            "",
            "$ARGUMENTS",
            "",
        )
    )
```

Record a dependency from the adapter to its same-named generated command
skill. Fail generation if the target is absent.

Write `skills/generated/INDEX.md` with separate command, methodology, and
support tables. Use neutral “Agent Skill” column headings and retain canonical
source paths only in this distribution-provenance index.

- [ ] **Step 4: Make pruning exact and fail on undeclared output**

Compute expected relative files for each output root. Remove stale generated
`science-*` directories and stale `science-*.md` OpenCode adapters. Permit only
the declared generated `INDEX.md` outside those patterns. Raise `ValueError`
for any other file instead of deleting or silently preserving it.

- [ ] **Step 5: Simplify the generation CLI and script**

Replace the `generate` command options with only:

```python
@agents_group.command(name="generate")
@click.option("--repo-root", type=click.Path(path_type=Path), default=None)
def generate_cmd(*, repo_root: Path | None) -> None:
    try:
        root = validate_repo_root(repo_root or _resolve_repo_root())
        result = generate_agent_assets(
            root,
            root / "skills" / "generated",
            root / "commands" / "opencode",
        )
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    click.echo(
        f"Generated {len(result.skill_paths)} skills and "
        f"{len(result.opencode_command_paths)} OpenCode commands"
    )
```

`_resolve_repo_root` walks upward and calls `validate_repo_root` for each
candidate. If none validates, raise `ValueError` instead of returning CWD.

The renamed repository script imports `generate_agent_assets`, targets the two
committed roots, and prints both counts. It has no agent or format branching.

- [ ] **Step 6: Regenerate committed output and remove the old distribution**

Run:

```bash
cd science
uv run --frozen science agents generate --repo-root ..
```

Then remove the tracked `codex-skills/` tree as the deliberate breaking path
change and update `test_no_raw_task_file_reads_in_docs.py` so its generated
surface exclusion is `skills/generated/`, not `codex-skills/`.

- [ ] **Step 7: Run generator and command-document tests**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_agent_assets.py \
  tests/test_command_docs.py \
  tests/test_no_raw_task_file_reads_in_docs.py
```

Expected: PASS, including exact committed-byte equality.

- [ ] **Step 8: Commit**

```bash
git add \
  science/src/science_tool/agent_assets.py \
  science/src/science_tool/agents_cli.py \
  science/src/science_tool/cli.py \
  science/tests/test_agent_assets.py \
  science/tests/test_no_raw_task_file_reads_in_docs.py \
  scripts/generate_agent_assets.py \
  skills/generated \
  commands/opencode
git add -u -- codex-skills
git commit -m "feat(agents): commit shared agent distributions"
```

---

### Task 5: Replace the installer with fail-before-write absolute links

**Files:**

- Modify: `science/src/science_tool/agents_cli.py`
- Create: `science/tests/test_agents_cli.py`

**Interfaces:**

- Consumes: validated committed distributions from Task 4.
- Produces: `build_install_plan`, `apply_install_plan`, and `science agents install --agent ... --scope ...`.

- [ ] **Step 1: Write failing scope and complete-set plan tests**

Use direct helper tests with injected roots:

```python
@pytest.fixture
def generated_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "toolkit"
    (repo / "skills").mkdir(parents=True)
    (repo / "skills" / "INDEX.md").write_text("# Skills\n", encoding="utf-8")
    shutil.copytree(ROOT / "skills" / "generated", repo / "skills" / "generated")
    shutil.copytree(ROOT / "commands" / "opencode", repo / "commands" / "opencode")
    (repo / "references").mkdir()
    (repo / "references" / "command-preamble.md").write_text(
        "# Command Preamble\n",
        encoding="utf-8",
    )
    (repo / "aspects").mkdir()
    return repo


@pytest.mark.parametrize("agent", ["codex", "crush", "opencode"])
@pytest.mark.parametrize("scope", ["project", "user"])
def test_install_plan_contains_support_skill(
    generated_repo: Path,
    tmp_path: Path,
    agent: AgentName,
    scope: InstallScope,
) -> None:
    plan = build_install_plan(
        repo_root=generated_repo,
        agent=agent,
        scope=scope,
        project_dir=tmp_path / "project",
        user_home=tmp_path / "home",
    )
    destinations = {link.destination for link in plan.links}
    base = (
        tmp_path / "project" / ".agents" / "skills"
        if scope == "project"
        else tmp_path / "home" / ".agents" / "skills"
    )
    assert base / "science-command-preamble" in destinations
```

For OpenCode, assert a second group targets
`<project>/.opencode/commands/science-*.md` or
`<home>/.config/opencode/commands/science-*.md`. Codex and Crush plans must
contain no OpenCode command links.

Delete the support package from a copied fixture and assert plan construction
fails before `.agents/` or `.opencode/` exists.

- [ ] **Step 2: Write failing collision-preservation and idempotency tests**

Parameterize conflicting regular files, real directories with a sentinel
payload, unrelated symlinks, and dangling symlinks. Assert:

```python
with pytest.raises(click.ClickException, match="destination collision"):
    build_install_plan(...)

assert sentinel.read_bytes() == original_bytes
assert not any(path.name == "science-status" for path in untouched_destination.iterdir())
```

Add a two-link plan where the second destination conflicts. Assert the first
link is not created, proving the collision scan covers the complete plan before
mutation.

Apply a collision-free plan, then assert every `source.is_absolute()`, every
destination is a symlink whose `readlink()` equals the absolute source, and a
second plan classifies all links as `current` with no new work.

- [ ] **Step 3: Run installer tests and verify they fail**

Run:

```bash
cd science
uv run --frozen pytest tests/test_agents_cli.py
```

Expected: FAIL because the plan/result contracts and `--scope` do not exist.

- [ ] **Step 4: Implement immutable install planning**

Define the dataclasses and literals from the File and Interface Map. Build
sorted `LinkSpec` values from every `skills/generated/science-*` directory that
contains `SKILL.md`. Validate:

1. `science-command-preamble` is present;
2. frontmatter `name` equals the directory name;
3. every source resolves to an absolute existing path;
4. OpenCode adapter stems map to existing skill names;
5. each destination is absent or is a symlink whose literal target equals the
   same absolute source.

Collect correct links in `InstallPlan.current`. Collect all collisions and
raise one `click.ClickException` listing them before creating directories.

- [ ] **Step 5: Apply a validated plan**

Implement:

```python
def apply_install_plan(plan: InstallPlan) -> tuple[LinkSpec, ...]:
    current_destinations = {link.destination for link in plan.current}
    pending = tuple(
        link for link in plan.links if link.destination not in current_destinations
    )
    for link in pending:
        link.destination.parent.mkdir(parents=True, exist_ok=True)
        link.destination.symlink_to(link.source)
    return pending
```

No unlink, `rmtree`, copying, stale-link pruning, or automatic uninstall path
is permitted.

- [ ] **Step 6: Replace the Click installer surface**

Use required `--agent`, `--scope` choice defaulting to `project`, optional
`--project-dir`, and optional `--repo-root`. Resolve the project directory and
user home before plan construction. Translate repository validation errors to
`click.ClickException`, then report installed and already-current counts.

Test with `CliRunner` that `--copy`, `--no-symlink`, and the removed generation
options are rejected by Click, not silently mapped.

- [ ] **Step 7: Run installer and CLI surface tests**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_agents_cli.py \
  tests/test_cli_surface_contract.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add \
  science/src/science_tool/agents_cli.py \
  science/tests/test_agents_cli.py
git commit -m "feat(agents): install generated assets safely"
```

---

### Task 6: Consolidate coding-agent documentation

**Files:**

- Create: `docs/user-guide/coding-agents.md`
- Rewrite: `docs/user-guide/codex.md`
- Create: `docs/user-guide/crush.md`
- Create: `docs/user-guide/opencode.md`
- Modify: `docs/user-guide/index.md`
- Modify: `mkdocs.yml`
- Modify: `README.md`
- Delete: `INSTALL.crush.md`
- Delete: `INSTALL.opencode.md`
- Delete: `MULTI_AGENT.md`
- Modify: `science/tests/test_agent_assets.py`

**Interfaces:**

- Consumes: final CLI syntax and installation paths from Tasks 4–5.
- Produces: one detailed common guide, three host-specific pages, compact README entry point, and no root/generated-tree installation manuals.

- [ ] **Step 1: Write failing documentation contract tests**

Add repository-document assertions to `test_agent_assets.py`:

```python
def test_coding_agent_docs_use_current_distribution_and_cli() -> None:
    checked = [
        ROOT / "README.md",
        ROOT / "docs" / "user-guide" / "coding-agents.md",
        ROOT / "docs" / "user-guide" / "codex.md",
        ROOT / "docs" / "user-guide" / "crush.md",
        ROOT / "docs" / "user-guide" / "opencode.md",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in checked)
    assert "skills/generated/" in text
    assert "science agents install" in text
    assert "codex-skills/" not in text
    assert "crush-skills/" not in text
    assert "opencode-skills/" not in text
    assert "Converted from Claude command" not in text


def test_root_install_documents_are_removed() -> None:
    for rel in ("INSTALL.crush.md", "INSTALL.opencode.md", "MULTI_AGENT.md"):
        assert not (ROOT / rel).exists()
```

Add navigation assertions that all four pages occur in `docs/user-guide/index.md`
and `mkdocs.yml`.

- [ ] **Step 2: Run documentation tests and verify they fail**

Run:

```bash
cd science
uv run --frozen pytest tests/test_agent_assets.py -k "docs or documentation or install"
```

Expected: FAIL for missing pages and retired paths.

- [ ] **Step 3: Write the common coding-agent guide**

Cover:

- the authored `skills/` versus generated `skills/generated/` boundary;
- one shared skill distribution for all three hosts;
- project and user install commands for each `--agent`;
- OpenCode's additional adapter installation;
- links to the current official Codex, Crush, and OpenCode discovery
  documentation supporting the shared `~/.agents/skills` user root;
- the persistent-checkout requirement and absolute symlink model;
- idempotent reinstall and fail/preserve collision semantics;
- Windows directory-junction or supported-symlink guidance with the same
  identity and collision rules;
- manual removal of only the known Science-owned symlinks;
- regeneration with `cd science && uv run --frozen science agents generate`;
- intentional removal of the old raw `INSTALL.codex.md` URL and old
  `codex-skills/` path.

Do not use machine-specific paths; examples that need a checkout path use
`~/d/science`.

- [ ] **Step 4: Rewrite the host pages**

Each page links to `coding-agents.md` for common setup and keeps only
host-specific behavior:

- Codex: `.agents/skills`, explicit skill selection, and current user discovery.
- Crush: `.agents/skills`, `user-invocable: true` command palette, and
  `science-statistics`/`science-command-preamble` not appearing in that palette.
- OpenCode: `.agents/skills`, `.opencode/commands` or
  `~/.config/opencode/commands`, `/science-*` commands, `$ARGUMENTS`, and
  permissions.

- [ ] **Step 5: Update README and guide navigation**

Replace the Codex-only Start Here paragraph with a compact Claude/Codex/Crush/
OpenCode table. Link every coding-agent row to its user-guide page. Add
`coding-agents.md`, `crush.md`, and `opencode.md` to the guide reading path,
chapter table, and MkDocs Workflows & Tooling navigation.

- [ ] **Step 6: Delete obsolete installation files**

Remove the three root documents. Confirm no installation document exists under
`skills/generated/`.

- [ ] **Step 7: Run documentation and site checks**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_agent_assets.py \
  tests/test_command_docs.py \
  tests/test_no_raw_task_file_reads_in_docs.py
cd ..
uv run --with-requirements docs/requirements.txt mkdocs build --strict
```

Expected: pytest PASS; MkDocs completes without missing-page or broken-link
errors.

- [ ] **Step 8: Commit**

```bash
git add \
  README.md \
  docs/user-guide/coding-agents.md \
  docs/user-guide/codex.md \
  docs/user-guide/crush.md \
  docs/user-guide/opencode.md \
  docs/user-guide/index.md \
  mkdocs.yml \
  science/tests/test_agent_assets.py
git add -u INSTALL.crush.md INSTALL.opencode.md MULTI_AGENT.md
git commit -m "docs(agents): consolidate coding agent setup"
```

---

### Task 7: Verify generated portability and all host contracts

**Files:**

- Modify if a gate exposes a defect: only files already listed in Tasks 1–6.
- Record smoke evidence in the final implementation handoff; do not add a machine-specific receipt to the repository.

**Interfaces:**

- Consumes: complete implementation and committed generated distributions.
- Produces: fresh verification evidence for generated bytes, installed symlink resolution, Python quality gates, and installed-host smoke behavior.

- [ ] **Step 1: Regenerate and require a clean distribution diff**

Run:

```bash
cd science
uv run --frozen science agents generate --repo-root ..
cd ..
git diff --exit-code -- skills/generated commands/opencode
```

Expected: generation succeeds and `git diff --exit-code` returns 0.

- [ ] **Step 2: Run focused agent/discovery/documentation tests**

Run:

```bash
cd science
uv run --frozen pytest \
  tests/test_agent_assets.py \
  tests/test_agents_cli.py \
  tests/test_skill_inventory.py \
  tests/skills_lint/test_discovery.py \
  tests/skills_lint/test_lint.py \
  tests/skills_lint/test_cli.py \
  tests/test_command_docs.py \
  tests/test_no_raw_task_file_reads_in_docs.py
```

Expected: PASS.

- [ ] **Step 3: Run lint and types**

Run:

```bash
cd science
uv run --frozen ruff check
uv run --frozen pyright
```

Expected: both PASS with no errors.

- [ ] **Step 4: Run the full suite once**

Run from the top-level agent with a timeout longer than three minutes:

```bash
cd science
uv run --frozen pytest
```

Expected: PASS. Do not run another suite concurrently in this worktree.

- [ ] **Step 5: Run project-scoped host smoke checks**

Record installed versions:

```bash
codex --version
crush --version
opencode --version
```

Create one temporary Git fixture, install each host with
`science agents install --scope project`, and verify:

1. all three discover `science-status`;
2. Codex can select `science-status`;
3. Crush surfaces `science-status` in its palette but not
   `science-statistics` or `science-command-preamble`;
4. OpenCode loads `science-status` and invokes `/science-status`;
5. each host can read one installed package reference;
6. the installed set for every host contains `science-command-preamble`.

Do not mutate the real user skill directories. If a host offers no stable
noninteractive discovery command, record the exact manual check and result
rather than inventing an automated assertion.

- [ ] **Step 6: Inspect final changes**

Run:

```bash
git status --short
git diff --check
git diff --stat 811f7cfa..HEAD
```

Expected: only intended implementation changes are present; `git diff --check`
prints nothing.

- [ ] **Step 7: Commit any verification-only corrections**

If Steps 1–6 required corrections, rerun the affected focused test before
committing them:

```bash
git diff --name-only -z | xargs -0 git add --
git commit -m "fix(agents): satisfy distribution verification"
```

If no correction was necessary, do not create an empty commit.
