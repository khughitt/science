# Skill-Corpus Surfacing (Inventory + `covers:` + Overlay) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the skill corpus as a packaged, drift-checked machine-readable inventory (INDEX-driven, with catalog-validated `covers:` on the bio subtree and resolved companion edges) and a role-typed in-memory overlay keyed by canonical id — the substrate the sub-plan-4 coverage command consumes.

**Architecture:** A `science_tool` generator reads `skills/INDEX.md` (the authoritative id↔path registry) + each skill's frontmatter + `## Companion Skills` section, validates a strict INDEX↔corpus bijection and `covers:` against the `science_model.data_products` catalog, and emits a canonical JSON resource shipped as `science_tool` package data. A `science-model` builder turns the loaded dict into role-typed `LeafSkill`/`RouterSkill` resources (re-validated), keyed by canonical id. `science-model` never reads the corpus or the resource — `science_tool` loads the JSON and passes a dict.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, hatchling packaging, pytest. Design doc: [`2026-07-24-skill-coverage-inventory-design.md`](2026-07-24-skill-coverage-inventory-design.md). Parent: [`2026-07-23-data-product-vocabulary-and-skill-coverage-design.md`](2026-07-23-data-product-vocabulary-and-skill-coverage-design.md).

## Global Constraints

- No AI-attribution trailers/footers on commits (no `Co-Authored-By`, no "Generated with Claude Code").
- Composition over inheritance; explicit over defensive; fail early — no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.
- `uv`/pytest/ruff commands run from `science/` for the CLI package and `science/model/` for the model package (never the repo root). Pyright is configured once by the repo-root `pyrightconfig.json`; test dirs are not type-checked.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) for any filepaths written into docs/code.
- Work happens in the existing worktree on branch `skill-coverage-inventory`. Commit after each task.
- **Canonical skill-id / catalog-term facts (verified against the live corpus):**
  - Skill-id grammar `^[a-z0-9]+(-[a-z0-9]+)*$` — reuse `SKILL_NAME_RE` from `science_tool.graph.skill_loads`.
  - `skills/INDEX.md` is an exact 60-entry id↔path registry (14 routers `SKILL.md` + 46 leaves); every path exists; no non-skills listed. Real skills = `.md` under `skills/` **excluding** `skills/INDEX.md` and `skills/meta/templates/`.
  - Frontmatter `name` equals the INDEX id for all 60 today, but INDEX is the identity authority (do not read identity from `name`).
  - Catalog term ids carry the `data-product:` prefix (e.g. `data-product:gene-expression-bulk-rna`); membership = `term in catalog.by_id` (a `@property`). Catalog loaded via `science_model.data_products.load_catalog()`.
  - All 166 companion links across the corpus resolve to a skill or `skills/INDEX.md` (0 unresolved); resolution: relative to the skill's own dir, strip `#anchor` and any link title.
- Resource path: `science/src/science_tool/graph/skill_inventory.json` (ships in the wheel automatically — hatchling packages non-`.py` files under `packages = ["src/science_tool"]`; the sub-plan-2 `graph/skill_aliases.yaml` is the precedent).

---

### Task 1: Strict frontmatter parser + `SkillInventoryError`

**Files:**
- Create: `science/src/science_tool/graph/skill_inventory.py`
- Test: `science/tests/test_skill_inventory.py`

**Interfaces:**
- Produces: `SkillInventoryError(ValueError)`; `parse_skill_frontmatter(text: str) -> dict` — extracts the fenced block and rejects duplicate keys and YAML merge keys before `yaml.safe_load`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_skill_inventory.py
from __future__ import annotations

import pytest

from science_tool.graph.skill_inventory import SkillInventoryError, parse_skill_frontmatter


def test_parse_frontmatter_reads_mapping() -> None:
    text = "---\nname: transcriptomics-scrna-qa\narchetype: measurement-qa\n---\n\nBody.\n"
    assert parse_skill_frontmatter(text) == {
        "name": "transcriptomics-scrna-qa",
        "archetype": "measurement-qa",
    }


def test_parse_frontmatter_missing_block() -> None:
    with pytest.raises(SkillInventoryError, match="frontmatter"):
        parse_skill_frontmatter("no frontmatter here\n")


def test_parse_frontmatter_rejects_duplicate_key() -> None:
    text = "---\nname: a\ncovers:\n  - data-product:x\ncovers:\n  - data-product:y\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_merge_key() -> None:
    text = "---\nbase: &b\n  k: v\nname: <<\n<<: *b\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="merge"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_non_mapping() -> None:
    with pytest.raises(SkillInventoryError, match="mapping"):
        parse_skill_frontmatter("---\n- just\n- a list\n---\n\nB\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.graph.skill_inventory`.

- [ ] **Step 3: Write minimal implementation**

```python
# science/src/science_tool/graph/skill_inventory.py
"""Packaged skill inventory: an INDEX-driven scan of the skills corpus into a
canonical JSON resource (identity, role, archetype, catalog-validated `covers:`,
and resolved companion edges), plus the loader for it.

`science_model` never reads this resource or the corpus: `load_skill_inventory`
returns a plain dict, and `science_model.skill_coverage.build_skill_overlay`
consumes that dict. Generation validates a strict INDEX<->corpus bijection and
`covers:` against the data-product catalog — every violation is a hard error.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path

import yaml

from science_tool.graph.skill_loads import SKILL_NAME_RE


class SkillInventoryError(ValueError):
    """The skills corpus, INDEX, or a skill's frontmatter is structurally invalid."""


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_skill_frontmatter(text: str) -> dict:
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise SkillInventoryError("missing frontmatter block")
    block = match.group(1)
    node = yaml.compose(block, Loader=yaml.SafeLoader)
    if isinstance(node, yaml.MappingNode):
        seen: set[object] = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise SkillInventoryError("YAML merge keys are not allowed in skill frontmatter")
            key = getattr(key_node, "value", None)
            if key in seen:
                raise SkillInventoryError(f"duplicate frontmatter key {key!r}")
            seen.add(key)
    data = yaml.safe_load(block)
    if not isinstance(data, dict):
        raise SkillInventoryError("frontmatter is not a mapping")
    return data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/skill_inventory.py science/tests/test_skill_inventory.py
git commit -m "feat(graph): strict skill-frontmatter parser rejecting duplicate and merge keys"
```

---

### Task 2: INDEX registry + strict bijection

**Files:**
- Modify: `science/src/science_tool/graph/skill_inventory.py`
- Test: `science/tests/test_skill_inventory.py`

**Interfaces:**
- Consumes: `SkillInventoryError`, `SKILL_NAME_RE`.
- Produces: `real_skill_paths(repo_root: Path) -> set[str]`; `load_index_registry(repo_root: Path) -> list[tuple[str, str]]` — ordered `(id, path)` pairs, after enforcing the bijection (unique ids matching the grammar, unique existing paths, exact set-equality with the real-skill set).

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_skill_inventory.py`:

```python
from pathlib import Path

from science_tool.graph.skill_inventory import load_index_registry, real_skill_paths


def _write(root: Path, rel: str, body: str = "---\nname: x\n---\n\nB\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _write_corpus(root: Path, entries: list[tuple[str, str]], *, index_lines: list[str] | None = None) -> None:
    for _sid, rel in entries:
        _write(root, rel)
    lines = index_lines if index_lines is not None else [f"- `{sid}`: `{rel}`" for sid, rel in entries]
    _write(root, "skills/INDEX.md", "---\nname: science-skill-index\n---\n\n" + "\n".join(lines) + "\n")


def test_registry_reads_pairs_in_index_order(tmp_path: Path) -> None:
    entries = [("bio", "skills/bio/SKILL.md"), ("bio-x-qa", "skills/bio/x-qa.md")]
    _write_corpus(tmp_path, entries)
    assert load_index_registry(tmp_path) == entries


def test_real_skill_paths_excludes_index_and_templates(tmp_path: Path) -> None:
    _write(tmp_path, "skills/bio/x-qa.md")
    _write(tmp_path, "skills/INDEX.md")
    _write(tmp_path, "skills/meta/templates/router.md")
    assert real_skill_paths(tmp_path) == {"skills/bio/x-qa.md"}


def test_registry_rejects_duplicate_id(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write(tmp_path, "skills/b.md")
    _write_corpus(tmp_path, [], index_lines=["- `dup`: `skills/a.md`", "- `dup`: `skills/b.md`"])
    with pytest.raises(SkillInventoryError, match="duplicate INDEX id"):
        load_index_registry(tmp_path)


def test_registry_rejects_duplicate_path(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write_corpus(tmp_path, [], index_lines=["- `one`: `skills/a.md`", "- `two`: `skills/a.md`"])
    with pytest.raises(SkillInventoryError, match="duplicate INDEX path"):
        load_index_registry(tmp_path)


def test_registry_rejects_bad_grammar(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write_corpus(tmp_path, [], index_lines=["- `Bad_Id`: `skills/a.md`"])
    with pytest.raises(SkillInventoryError, match="grammar"):
        load_index_registry(tmp_path)


def test_registry_rejects_missing_path(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [], index_lines=["- `ghost`: `skills/ghost.md`"])
    with pytest.raises(SkillInventoryError, match="does not exist"):
        load_index_registry(tmp_path)


def test_registry_rejects_orphan_skill(tmp_path: Path) -> None:
    _write(tmp_path, "skills/listed.md")
    _write(tmp_path, "skills/orphan.md")
    _write_corpus(tmp_path, [], index_lines=["- `listed`: `skills/listed.md`"])
    with pytest.raises(SkillInventoryError, match="missing from INDEX"):
        load_index_registry(tmp_path)


def test_registry_rejects_extra_non_skill(tmp_path: Path) -> None:
    _write(tmp_path, "skills/real.md")
    _write(tmp_path, "skills/meta/templates/router.md")
    _write_corpus(tmp_path, [], index_lines=[
        "- `real`: `skills/real.md`",
        "- `tmpl`: `skills/meta/templates/router.md`",
    ])
    with pytest.raises(SkillInventoryError, match="not a real skill"):
        load_index_registry(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -k "registry or real_skill" -v`
Expected: FAIL — `load_index_registry` / `real_skill_paths` do not exist.

- [ ] **Step 3: Implement**

Append to `skill_inventory.py`:

```python
_INDEX_LINE_RE = re.compile(r"^\s*-\s*`([^`]+)`:\s*`(skills/[^`]+)`", re.MULTILINE)


def real_skill_paths(repo_root: Path) -> set[str]:
    out: set[str] = set()
    for path in (repo_root / "skills").rglob("*.md"):
        rel = path.relative_to(repo_root).as_posix()
        if rel == "skills/INDEX.md" or rel.startswith("skills/meta/templates/"):
            continue
        out.add(rel)
    return out


def load_index_registry(repo_root: Path) -> list[tuple[str, str]]:
    index_text = (repo_root / "skills" / "INDEX.md").read_text(encoding="utf-8")
    entries = _INDEX_LINE_RE.findall(index_text)
    ids: set[str] = set()
    paths: set[str] = set()
    for sid, rel in entries:
        if SKILL_NAME_RE.fullmatch(sid) is None:
            raise SkillInventoryError(f"INDEX id {sid!r} fails the canonical skill-id grammar")
        if sid in ids:
            raise SkillInventoryError(f"duplicate INDEX id {sid!r}")
        if rel in paths:
            raise SkillInventoryError(f"duplicate INDEX path {rel!r}")
        if not (repo_root / rel).is_file():
            raise SkillInventoryError(f"INDEX path {rel!r} does not exist")
        ids.add(sid)
        paths.add(rel)
    real = real_skill_paths(repo_root)
    orphan = real - paths
    if orphan:
        raise SkillInventoryError(f"real skills missing from INDEX: {sorted(orphan)}")
    extra = paths - real
    if extra:
        raise SkillInventoryError(f"INDEX lists paths that are not a real skill: {sorted(extra)}")
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -v`
Expected: PASS (Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/skill_inventory.py science/tests/test_skill_inventory.py
git commit -m "feat(graph): INDEX-driven skill registry with strict corpus bijection"
```

---

### Task 3: Companion section extraction + resolution

**Files:**
- Modify: `science/src/science_tool/graph/skill_inventory.py`
- Test: `science/tests/test_skill_inventory.py`

**Interfaces:**
- Consumes: `SkillInventoryError`.
- Produces: `companion_section(text: str) -> str`; `resolve_companions(repo_root: Path, skill_rel_path: str, section: str, path_to_id: dict[str, str]) -> list[dict]` — each `{"target": <id-or-"science-skill-index">, "role": "leaf"|"router"|"index"}`, authored order, distinct targets, broken/off-corpus → hard error.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_skill_inventory.py`:

```python
from science_tool.graph.skill_inventory import companion_section, resolve_companions

_PATH_TO_ID = {
    "skills/bio/transcriptomics/cohort-qa.md": "transcriptomics-cohort-qa",
    "skills/bio/transcriptomics/SKILL.md": "transcriptomics",
    "skills/statistics/compositional-data.md": "statistics-compositional-data",
}


def test_companion_section_extracts_only_that_section() -> None:
    text = "# T\n\n## Companion Skills\n\n- [`a`](a.md)\n\n## Next\n\n- not this\n"
    assert "- [`a`](a.md)" in companion_section(text)
    assert "not this" not in companion_section(text)


def test_resolve_companions_typed_targets(tmp_path: Path) -> None:
    section = (
        "- [`cohort-qa.md`](cohort-qa.md) - x\n"
        "- [`SKILL.md`](SKILL.md) - the router\n"
        "- [`compositional-data`](../../statistics/compositional-data.md#anchor) - y\n"
        "- [`index`](../../INDEX.md) - the index\n"
    )
    edges = resolve_companions(tmp_path, "skills/bio/transcriptomics/scrna-qa.md", section, _PATH_TO_ID)
    assert edges == [
        {"target": "transcriptomics-cohort-qa", "role": "leaf"},
        {"target": "transcriptomics", "role": "router"},
        {"target": "statistics-compositional-data", "role": "leaf"},
        {"target": "science-skill-index", "role": "index"},
    ]


def test_resolve_companions_rejects_broken_target(tmp_path: Path) -> None:
    with pytest.raises(SkillInventoryError, match="non-skill"):
        resolve_companions(tmp_path, "skills/bio/transcriptomics/scrna-qa.md",
                           "- [`x`](../../nope/ghost.md)\n", _PATH_TO_ID)


def test_resolve_companions_rejects_duplicate_target(tmp_path: Path) -> None:
    section = "- [`a`](cohort-qa.md)\n- [`a again`](cohort-qa.md)\n"
    with pytest.raises(SkillInventoryError, match="duplicate companion"):
        resolve_companions(tmp_path, "skills/bio/transcriptomics/scrna-qa.md", section, _PATH_TO_ID)


def test_resolve_companions_empty_section() -> None:
    assert resolve_companions(Path("/x"), "skills/a.md", "", _PATH_TO_ID) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -k companion -v`
Expected: FAIL — the functions do not exist.

- [ ] **Step 3: Implement**

Append to `skill_inventory.py`:

```python
_COMPANION_SECTION_RE = re.compile(
    r"^## Companion Skills\s*$(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
_LINK_TARGET_RE = re.compile(r"\]\(([^)]+)\)")


def companion_section(text: str) -> str:
    match = _COMPANION_SECTION_RE.search(text)
    return match.group(1) if match else ""


def resolve_companions(
    repo_root: Path, skill_rel_path: str, section: str, path_to_id: dict[str, str]
) -> list[dict]:
    root = repo_root.resolve()
    skill_abs = root / skill_rel_path
    edges: list[dict] = []
    seen: set[str] = set()
    for target in _LINK_TARGET_RE.findall(section):
        raw = target.split()[0].split("#")[0]  # drop any link title and #anchor
        if not raw:
            continue
        resolved = (skill_abs.parent / raw).resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise SkillInventoryError(
                f"{skill_rel_path}: companion target {raw!r} escapes the repo"
            ) from exc
        if rel == "skills/INDEX.md":
            target_id, role = "science-skill-index", "index"
        elif rel in path_to_id:
            target_id = path_to_id[rel]
            role = "router" if resolved.name == "SKILL.md" else "leaf"
        else:
            raise SkillInventoryError(
                f"{skill_rel_path}: companion target {raw!r} resolves to non-skill {rel!r}"
            )
        if target_id in seen:
            raise SkillInventoryError(
                f"{skill_rel_path}: duplicate companion target {target_id!r}"
            )
        seen.add(target_id)
        edges.append({"target": target_id, "role": role})
    return edges
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -v`
Expected: PASS (all Task 1–3 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/skill_inventory.py science/tests/test_skill_inventory.py
git commit -m "feat(graph): parse and resolve skill companion edges to canonical ids"
```

---

### Task 4: `build_skill_inventory` + canonical serialization

**Files:**
- Modify: `science/src/science_tool/graph/skill_inventory.py`
- Test: `science/tests/test_skill_inventory.py`

**Interfaces:**
- Consumes: `parse_skill_frontmatter`, `load_index_registry`, `companion_section`, `resolve_companions`; `science_model.data_products.DataProductCatalog`.
- Produces: `build_skill_inventory(repo_root: Path, catalog: DataProductCatalog) -> dict` (a `{"skills": [...]}` object, list sorted by `id`); `serialize_inventory(inventory: dict) -> str` (canonical JSON + trailing newline).

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_skill_inventory.py`:

```python
from science_model.data_products import build_catalog

from science_tool.graph.skill_inventory import build_skill_inventory, serialize_inventory


def _catalog():
    return build_catalog({
        "schema_version": "1",
        "terms": [
            {"id": "data-product:gene-expression-single-cell", "label": "scRNA", "assay": "rna"},
            {"id": "data-product:somatic-variant", "label": "SNV", "assay": "dna"},
        ],
    })


def _leaf(name, archetype="measurement-qa", covers="", sources="", companions=""):
    fm = f"---\nname: {name}\ndescription: d for {name}\narchetype: {archetype}\n"
    fm += covers + sources + "---\n\nBody.\n\n## Companion Skills\n\n" + companions
    return fm


def _router(name):
    return f"---\nname: {name}\ndescription: router {name}\n---\n\nBody.\n\n## Companion Skills\n\n"


def _mkcorpus(root: Path) -> None:
    (root / "skills").mkdir(parents=True, exist_ok=True)
    _write(root, "skills/SKILL.md", _router("bio"))
    _write(root, "skills/scrna.md", _leaf(
        "scrna",
        covers="covers:\n  - data-product:gene-expression-single-cell\n",
        sources="sources: [scanpy]\n",
        companions="- [`somatic`](somatic.md) - x\n",
    ))
    _write(root, "skills/somatic.md", _leaf("somatic", covers="covers:\n  - data-product:somatic-variant\n"))
    _write(root, "skills/INDEX.md",
           "---\nname: science-skill-index\n---\n\n"
           "- `bio`: `skills/SKILL.md`\n- `scrna`: `skills/scrna.md`\n- `somatic`: `skills/somatic.md`\n")


def test_build_inventory_shape_and_order(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    inv = build_skill_inventory(tmp_path, _catalog())
    assert [s["id"] for s in inv["skills"]] == ["bio", "scrna", "somatic"]  # id-sorted
    bio = inv["skills"][0]
    assert bio["role"] == "router" and "archetype" not in bio and "covers" not in bio
    scrna = inv["skills"][1]
    assert scrna["role"] == "leaf"
    assert scrna["archetype"] == "measurement-qa"
    assert scrna["covers"] == ["data-product:gene-expression-single-cell"]
    assert scrna["sources"] == ["scanpy"]
    assert scrna["companions"] == [{"target": "somatic", "role": "leaf"}]
    somatic = inv["skills"][2]
    assert "sources" not in somatic  # absent -> omitted
    assert "companions" not in somatic  # empty section -> omitted


def test_build_inventory_keys_off_index_not_name(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    # Rewrite one leaf's frontmatter name to diverge from its INDEX id.
    p = tmp_path / "skills/scrna.md"
    p.write_text(p.read_text().replace("name: scrna", "name: totally-different"), encoding="utf-8")
    inv = build_skill_inventory(tmp_path, _catalog())
    scrna = next(s for s in inv["skills"] if s["id"] == "scrna")
    assert scrna["id"] == "scrna" and scrna["name"] == "totally-different"


def test_build_inventory_rejects_off_catalog_covers(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/scrna.md"
    p.write_text(p.read_text().replace(
        "data-product:gene-expression-single-cell", "data-product:not-a-term"), encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="not in .*catalog"):
        build_skill_inventory(tmp_path, _catalog())


def test_build_inventory_rejects_duplicate_covers(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/scrna.md"
    p.write_text(p.read_text().replace(
        "covers:\n  - data-product:gene-expression-single-cell\n",
        "covers:\n  - data-product:gene-expression-single-cell\n  - data-product:gene-expression-single-cell\n",
    ), encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="duplicate covers"):
        build_skill_inventory(tmp_path, _catalog())


def test_build_inventory_rejects_router_with_covers(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/SKILL.md"
    p.write_text(p.read_text().replace(
        "description: router bio\n", "description: router bio\ncovers:\n  - data-product:somatic-variant\n"),
        encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="router.*covers"):
        build_skill_inventory(tmp_path, _catalog())


def test_build_inventory_rejects_leaf_without_archetype(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    p = tmp_path / "skills/somatic.md"
    p.write_text(p.read_text().replace("archetype: measurement-qa\n", ""), encoding="utf-8")
    with pytest.raises(SkillInventoryError, match="archetype"):
        build_skill_inventory(tmp_path, _catalog())


def test_serialize_is_canonical(tmp_path: Path) -> None:
    _mkcorpus(tmp_path)
    text = serialize_inventory(build_skill_inventory(tmp_path, _catalog()))
    assert text.endswith("\n")
    assert text == serialize_inventory(build_skill_inventory(tmp_path, _catalog()))  # deterministic
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -k "build_inventory or serialize" -v`
Expected: FAIL — `build_skill_inventory` / `serialize_inventory` do not exist.

- [ ] **Step 3: Implement**

Add the import at the top of `skill_inventory.py` (under the existing imports):

```python
from science_model.data_products import DataProductCatalog
```

Append to `skill_inventory.py`:

```python
def _string_list(rel: str, raw: object, field: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise SkillInventoryError(f"{rel}: {field} must be a list of strings")
    return list(raw)


def _validate_covers(rel: str, raw: object, catalog_ids: dict[str, object]) -> list[str]:
    terms = _string_list(rel, raw, "covers")
    seen: set[str] = set()
    for term in terms:
        if term not in catalog_ids:
            raise SkillInventoryError(f"{rel}: covers term {term!r} is not in the data-product catalog")
        if term in seen:
            raise SkillInventoryError(f"{rel}: duplicate covers term {term!r}")
        seen.add(term)
    return terms


def build_skill_inventory(repo_root: Path, catalog: DataProductCatalog) -> dict:
    entries = load_index_registry(repo_root)
    path_to_id = {rel: sid for sid, rel in entries}
    catalog_ids = catalog.by_id
    skills: list[dict] = []
    for sid, rel in entries:
        path = repo_root / rel
        text = path.read_text(encoding="utf-8")
        frontmatter = parse_skill_frontmatter(text)
        name = frontmatter.get("name")
        if not isinstance(name, str) or not name:
            raise SkillInventoryError(f"{rel}: frontmatter is missing a string name")
        description = frontmatter.get("description")
        if not isinstance(description, str) or not description:
            raise SkillInventoryError(f"{rel}: frontmatter is missing a string description")
        role = "router" if path.name == "SKILL.md" else "leaf"
        entry: dict = {"id": sid, "name": name, "path": rel, "role": role, "description": description}
        if role == "router":
            if "archetype" in frontmatter:
                raise SkillInventoryError(f"{rel}: a router must not declare archetype")
            if "covers" in frontmatter:
                raise SkillInventoryError(f"{rel}: a router must not declare covers")
        else:
            archetype = frontmatter.get("archetype")
            if not isinstance(archetype, str) or not archetype:
                raise SkillInventoryError(f"{rel}: a leaf must declare a string archetype")
            entry["archetype"] = archetype
            covers = _validate_covers(rel, frontmatter.get("covers"), catalog_ids)
            if covers:
                entry["covers"] = covers
            sources = _string_list(rel, frontmatter.get("sources"), "sources")
            if sources:
                entry["sources"] = sources
        companions = resolve_companions(repo_root, rel, companion_section(text), path_to_id)
        if companions:
            entry["companions"] = companions
        skills.append(entry)
    skills.sort(key=lambda item: item["id"])
    return {"skills": skills}


def serialize_inventory(inventory: dict) -> str:
    return json.dumps(inventory, indent=2, sort_keys=True) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Lint**

Run: `cd science && uv run ruff check src/science_tool/graph/skill_inventory.py tests/test_skill_inventory.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/skill_inventory.py science/tests/test_skill_inventory.py
git commit -m "feat(graph): assemble canonical skill inventory with covers and companions"
```

---

### Task 5: Author bio `covers:`, generate + commit the resource, drift + packaging tests

**Files:**
- Modify: 8 bio leaf skill files (frontmatter `covers:`)
- Modify: `science/src/science_tool/graph/skill_inventory.py` (add `load_skill_inventory`)
- Create: `scripts/generate_skill_inventory.py`
- Create: `science/src/science_tool/graph/skill_inventory.json` (generated)
- Modify: `science/pyproject.toml` (register the `packaging` marker + default-exclude it)
- Test: `science/tests/test_skill_inventory.py`

**Interfaces:**
- Consumes: `build_skill_inventory`, `serialize_inventory`; `science_model.data_products.load_catalog`.
- Produces: `load_skill_inventory() -> dict` (reads the packaged JSON via `importlib.resources`).

- [ ] **Step 1: Add `load_skill_inventory`**

Append to `skill_inventory.py`:

```python
_RESOURCE_NAME = "skill_inventory.json"


def load_skill_inventory() -> dict:
    text = (
        resources.files("science_tool.graph")
        .joinpath(_RESOURCE_NAME)
        .read_text(encoding="utf-8")
    )
    return json.loads(text)
```

- [ ] **Step 2: Author `covers:` on the bio subtree**

Add a `covers:` block to the frontmatter of each file below (place it after the existing `sources:`/`archetype:` line, before the closing `---`). Use exactly these catalog term ids (each verified present in `catalog.yaml`):

```
skills/bio/transcriptomics/bulk-rnaseq-qa.md   -> data-product:gene-expression-bulk-rna
skills/bio/transcriptomics/microarray-qa.md    -> data-product:gene-expression-microarray
skills/bio/transcriptomics/scrna-qa.md         -> data-product:gene-expression-single-cell
skills/bio/genomics/somatic-mutation-qa.md     -> data-product:somatic-variant
skills/bio/genomics/mutational-signatures-qa.md-> data-product:mutational-signature
skills/bio/genomics/copy-number-sv-qa.md       -> data-product:copy-number, data-product:structural-variant
skills/bio/proteomics/proteomics-qa.md         -> data-product:proteomics
skills/bio/functional-genomics-qa.md           -> data-product:genetic-dependency, data-product:genetic-perturbation, data-product:drug-sensitivity
```

Block style, e.g. for `copy-number-sv-qa.md`:

```yaml
covers:
  - data-product:copy-number
  - data-product:structural-variant
```

Leave `driver-selection.md`, `cohort-qa.md`, `data-integration.md`, `protein-sequence-structure-qa.md` **without** `covers:` (uncovered by design). Do not touch any non-bio leaf.

- [ ] **Step 3: Create the generator script**

```python
# scripts/generate_skill_inventory.py
from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "science" / "src"))
    sys.path.insert(0, str(repo_root / "science" / "model" / "src"))
    from science_model.data_products import load_catalog
    from science_tool.graph.skill_inventory import build_skill_inventory, serialize_inventory

    inventory = build_skill_inventory(repo_root, load_catalog())
    out = repo_root / "science" / "src" / "science_tool" / "graph" / "skill_inventory.json"
    out.write_text(serialize_inventory(inventory), encoding="utf-8")
    print(f"Wrote {out} ({len(inventory['skills'])} skills)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate the committed resource**

Run: `cd /home/keith/d/science/.worktrees/skill-coverage-inventory && uv run --project science python scripts/generate_skill_inventory.py`
Expected: prints `Wrote .../skill_inventory.json (60 skills)`; creates the JSON.

- [ ] **Step 5: Register the `packaging` marker**

In `science/pyproject.toml`, extend the default filter and marker list:

```toml
addopts = "-q -m 'not snapshot and not real_projects and not git_source and not packaging'"
```

and add to the `markers` list:

```toml
  "packaging: builds the wheel to assert data files ship; slow, run explicitly with -m packaging",
```

- [ ] **Step 6: Write the drift + packaging + corpus-absent tests**

Append to `science/tests/test_skill_inventory.py`:

```python
import subprocess
import zipfile
from importlib import resources

from science_model.data_products import load_catalog

from science_tool.graph.skill_inventory import load_skill_inventory

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_committed_inventory_matches_regeneration() -> None:
    generated = serialize_inventory(build_skill_inventory(_REPO_ROOT, load_catalog()))
    committed = resources.files("science_tool.graph").joinpath("skill_inventory.json").read_text(encoding="utf-8")
    assert generated == committed, "skill_inventory.json is stale — run scripts/generate_skill_inventory.py"


def test_load_skill_inventory_round_trips() -> None:
    inv = load_skill_inventory()
    ids = [s["id"] for s in inv["skills"]]
    assert ids == sorted(ids)  # canonical-id order
    assert "transcriptomics-scrna-qa" in ids
    scrna = next(s for s in inv["skills"] if s["id"] == "transcriptomics-scrna-qa")
    assert scrna["covers"] == ["data-product:gene-expression-single-cell"]


@pytest.mark.packaging
def test_inventory_ships_in_wheel(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=_REPO_ROOT / "science", check=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert any(n.endswith("science_tool/graph/skill_inventory.json") for n in names)
```

- [ ] **Step 7: Run the tests (default suite + the packaging marker explicitly)**

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -v`
Expected: PASS; the drift test confirms the committed resource matches.

Run: `cd science && uv run --frozen pytest tests/test_skill_inventory.py -m packaging -v`
Expected: PASS — `skill_inventory.json` is in the built wheel.

- [ ] **Step 8: Commit**

```bash
git add skills/bio scripts/generate_skill_inventory.py science/src/science_tool/graph/skill_inventory.json science/src/science_tool/graph/skill_inventory.py science/pyproject.toml science/tests/test_skill_inventory.py
git commit -m "feat(skills): author bio covers and ship the generated skill inventory resource"
```

---

### Task 6: Role-typed overlay builder (`science-model`)

**Files:**
- Create: `science/model/src/science_model/skill_coverage/overlay.py`
- Modify: `science/model/src/science_model/skill_coverage/__init__.py`
- Test: `science/model/tests/test_skill_overlay.py`

**Interfaces:**
- Consumes: `science_model.data_products.DataProductCatalog`; the inventory dict shape from Task 4.
- Produces: `Companion`, `LeafSkill`, `RouterSkill`, `SkillOverlay`, `SkillOverlayError`; `build_skill_overlay(inventory: dict, catalog: DataProductCatalog) -> SkillOverlay`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_skill_overlay.py
from __future__ import annotations

import pytest

from science_model.data_products import build_catalog
from science_model.skill_coverage import (
    LeafSkill,
    RouterSkill,
    SkillOverlayError,
    build_skill_overlay,
)


def _catalog():
    return build_catalog({
        "schema_version": "1",
        "terms": [{"id": "data-product:somatic-variant", "label": "SNV", "assay": "dna"}],
    })


def _inv(skills):
    return {"skills": skills}


def test_build_overlay_role_typing() -> None:
    overlay = build_skill_overlay(_inv([
        {"id": "bio", "name": "bio", "path": "skills/bio/SKILL.md", "role": "router",
         "description": "r", "companions": [{"target": "somatic", "role": "leaf"}]},
        {"id": "somatic", "name": "somatic", "path": "skills/somatic.md", "role": "leaf",
         "description": "d", "archetype": "measurement-qa",
         "covers": ["data-product:somatic-variant"]},
    ]), _catalog())
    router = overlay.get("bio")
    assert isinstance(router, RouterSkill)
    assert router.companions[0].target == "somatic" and router.companions[0].role == "leaf"
    leaf = overlay.get("somatic")
    assert isinstance(leaf, LeafSkill)
    assert leaf.covers == ("data-product:somatic-variant",)
    assert leaf.sources == ()  # omitted -> empty
    assert [s.id for s in overlay] == ["bio", "somatic"]  # id order
    assert "somatic" in overlay and len(overlay) == 2


def test_build_overlay_rejects_duplicate_id() -> None:
    with pytest.raises(SkillOverlayError, match="duplicate"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf",
             "description": "d", "archetype": "a"},
            {"id": "x", "name": "x2", "path": "skills/x2.md", "role": "leaf",
             "description": "d", "archetype": "a"},
        ]), _catalog())


def test_build_overlay_rejects_off_catalog_cover() -> None:
    with pytest.raises(SkillOverlayError, match="catalog"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf",
             "description": "d", "archetype": "a", "covers": ["data-product:ghost"]},
        ]), _catalog())


def test_build_overlay_rejects_router_with_covers() -> None:
    with pytest.raises(SkillOverlayError, match="router"):
        build_skill_overlay(_inv([
            {"id": "r", "name": "r", "path": "skills/SKILL.md", "role": "router",
             "description": "d", "covers": ["data-product:somatic-variant"]},
        ]), _catalog())


def test_build_overlay_rejects_leaf_without_archetype() -> None:
    with pytest.raises(SkillOverlayError, match="archetype"):
        build_skill_overlay(_inv([
            {"id": "x", "name": "x", "path": "skills/x.md", "role": "leaf", "description": "d"},
        ]), _catalog())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run --frozen pytest tests/test_skill_overlay.py -v`
Expected: FAIL — `science_model.skill_coverage` exports do not exist.

- [ ] **Step 3: Implement the overlay module**

```python
# science/model/src/science_model/skill_coverage/overlay.py
"""Role-typed, in-memory skill overlay built from the packaged inventory dict.

`science_model` never reads the corpus or the packaged resource: `science_tool`
loads `skill_inventory.json` and passes the dict here. The builder re-validates
the structural invariants (it does not trust an editable resource): a duplicate
id, an off-catalog or duplicate `covers` term, a router carrying `covers`, or a
leaf missing `archetype` is a hard error.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from science_model.data_products import DataProductCatalog


class SkillOverlayError(ValueError):
    """The inventory dict violates a role-typing or catalog invariant."""


@dataclass(frozen=True, slots=True)
class Companion:
    target: str
    role: str  # "leaf" | "router" | "index"


@dataclass(frozen=True, slots=True)
class LeafSkill:
    id: str
    name: str
    description: str
    archetype: str
    covers: tuple[str, ...]
    sources: tuple[str, ...]
    companions: tuple[Companion, ...]
    role: str = "leaf"


@dataclass(frozen=True, slots=True)
class RouterSkill:
    id: str
    name: str
    description: str
    companions: tuple[Companion, ...]
    role: str = "router"


class SkillOverlay:
    """Canonical-id-keyed view over role-typed skills; iterates in id order."""

    def __init__(self, skills: list[LeafSkill | RouterSkill]) -> None:
        self._by_id: dict[str, LeafSkill | RouterSkill] = {}
        for skill in skills:
            if skill.id in self._by_id:
                raise SkillOverlayError(f"duplicate skill id {skill.id!r}")
            self._by_id[skill.id] = skill

    def get(self, skill_id: str) -> LeafSkill | RouterSkill | None:
        return self._by_id.get(skill_id)

    def __contains__(self, skill_id: object) -> bool:
        return skill_id in self._by_id

    def __iter__(self) -> Iterator[LeafSkill | RouterSkill]:
        return (self._by_id[key] for key in sorted(self._by_id))

    def __len__(self) -> int:
        return len(self._by_id)


def _companions(entry: dict) -> tuple[Companion, ...]:
    return tuple(Companion(target=c["target"], role=c["role"]) for c in entry.get("companions", []))


def build_skill_overlay(inventory: dict, catalog: DataProductCatalog) -> SkillOverlay:
    catalog_ids = catalog.by_id
    skills: list[LeafSkill | RouterSkill] = []
    for entry in inventory.get("skills", []):
        role = entry["role"]
        companions = _companions(entry)
        if role == "router":
            if entry.get("covers") or entry.get("archetype"):
                raise SkillOverlayError(f"router {entry['id']!r} must not carry covers/archetype")
            skills.append(RouterSkill(
                id=entry["id"], name=entry["name"], description=entry["description"],
                companions=companions,
            ))
        elif role == "leaf":
            archetype = entry.get("archetype")
            if not archetype:
                raise SkillOverlayError(f"leaf {entry['id']!r} is missing archetype")
            covers = entry.get("covers", [])
            seen: set[str] = set()
            for term in covers:
                if term not in catalog_ids:
                    raise SkillOverlayError(f"leaf {entry['id']!r} covers off-catalog term {term!r}")
                if term in seen:
                    raise SkillOverlayError(f"leaf {entry['id']!r} has duplicate covers term {term!r}")
                seen.add(term)
            skills.append(LeafSkill(
                id=entry["id"], name=entry["name"], description=entry["description"],
                archetype=archetype, covers=tuple(covers),
                sources=tuple(entry.get("sources", [])), companions=companions,
            ))
        else:
            raise SkillOverlayError(f"skill {entry['id']!r} has unknown role {role!r}")
    return SkillOverlay(skills)
```

- [ ] **Step 4: Export from the package**

In `science/model/src/science_model/skill_coverage/__init__.py`, add near the top (after the existing imports):

```python
from science_model.skill_coverage.overlay import (
    Companion,
    LeafSkill,
    RouterSkill,
    SkillOverlay,
    SkillOverlayError,
    build_skill_overlay,
)
```

and extend `__all__` (add these entries to the existing list):

```python
    "Companion",
    "LeafSkill",
    "RouterSkill",
    "SkillOverlay",
    "SkillOverlayError",
    "build_skill_overlay",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_skill_overlay.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Full verification gate**

```bash
cd science && uv run --frozen pytest && uv run --frozen pytest tests/test_skill_inventory.py -m packaging && uv run ruff check && uv run pyright
cd ../model && uv run --frozen pytest && uv run ruff check
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add science/model/src/science_model/skill_coverage/overlay.py science/model/src/science_model/skill_coverage/__init__.py science/model/tests/test_skill_overlay.py
git commit -m "feat(skill-coverage): role-typed in-memory skill overlay keyed by canonical id"
```

---

## Self-review notes (for the executor)

- **Spec coverage:** T1 = dup/merge-safe frontmatter parser (design §3 "Frontmatter parsing"); T2 = INDEX bijection (§3 "Generation" + §5); T3 = companion parse/resolve (§3 "Companion resolution"); T4 = inventory assembly, covers validation, ordering, `sources` omission (§3 "Contents" + §2); T5 = bio `covers:` authoring (§2), generated committed resource + drift + wheel packaging (§3 "Drift check" + testing "wheel packaging"); T6 = role-typed overlay, dup-id, re-validation, `sources==[]`, id-order iteration (§4). Every design §2–§5 requirement and testing bullet maps to a task.
- **Out of scope (do not implement):** the `science skills coverage` command, the `coverage-report`, the `dataset_usage` occurrence join, coverage states / `unmapped-skill-reference` diagnostics, typed companion-edge relation semantics, non-bio `covers:`, any persistent overlay artifact.
- **Package boundary:** `science_model` (T6) imports only `science_model.data_products`; it never imports `science_tool` and never reads the corpus or the JSON — `science_tool` (T5) loads the resource and hands over a dict. Verified: `science_model` has no `science_tool` imports today.
- **Type/name consistency:** `build_skill_inventory(repo_root, catalog)` and `serialize_inventory(inv)` (T4) are consumed verbatim by the script and drift test (T5). `build_skill_overlay(inventory, catalog)` (T6) consumes the exact dict shape T4 emits (`role`/`archetype`/`covers`/`sources`/`companions` keys, omitted-when-empty). `SKILL_NAME_RE` and the dup/merge-key discipline are reused from `science_tool.graph.skill_loads`.
- **Resource ships automatically:** hatchling packages non-`.py` files under `packages = ["src/science_tool"]` (the sub-plan-2 `skill_aliases.yaml` precedent); the T5 `@pytest.mark.packaging` wheel test proves it rather than assuming it.
