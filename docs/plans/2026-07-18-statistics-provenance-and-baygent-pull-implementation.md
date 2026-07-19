# Statistics-Skill Provenance + baygent Content Pull — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the statistics skills a machine-readable source registry (+ lint rule + `science skills sources` CLI) and pull curated, upstream-linked Bayesian/causal practices from baygent-skills into two new leaves and two extensions.

**Architecture:** A typed `sources.yaml` registry keyed by source ID; leaves cite IDs via a frontmatter `sources:` list. A loader validates records (kind-conditional, shape-validating) and exposes `records` (valid), `errors` (per-ID problems), and `declared_ids` (all keys). The skills linter flags unresolved refs (against `declared_ids`) and invalid records; a `science skills sources` command builds both dependency directions and reports freshness on three orthogonal axes (validation / freshness / ref-resolution) via direct upstream-SHA comparison. Content changes are markdown-only and gated by the linter.

**Tech Stack:** Python ≥3.11 (the repo's floor), `click`, `pyyaml`, `pytest`, `uv`. Skills are markdown under `skills/`. All CLI/lint work runs from `science/`.

## Global Constraints

- Run all Python tooling from `science/`: `uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`. Default pytest excludes `snapshot`/`real_projects`.
- Lint runs from `science/` over the repo `skills/`: `cd science && uv run science skills lint --root ../skills`. Every task that touches `skills/` ends with lint **exit 0**.
- No AI-attribution trailers/footers on commits. No "legacy"/"compatibility" layers. No `Unified` prefix. Composition > inheritance; explicit > defensive; fail early.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/...`) for filepaths written **into** docs/code.
- Frontmatter contract: every `*.md` under `skills/` needs `name` + `description`, a `## Companion Skills` section, and an `skills/INDEX.md` entry. Extra frontmatter keys (`sources:`, `type:`) are allowed.
- Registry constants (verbatim): `GIT_BACKED_KINDS = {"skill-repo","package-docs"}`; `REFERENCE_KINDS = {"book","paper","course"}`; `FETCH_HOST_ALLOWLIST = {"github.com"}`; `SHA_RE = ^[0-9a-f]{40}$`; known record keys = `title, authors, url, kind, license, attribution_notice, upstream_ref, last_checked, doi, arxiv, isbn, notes`.
- **Orthogonal axes:** refs resolve against `declared_ids` (valid **or** invalid records), so a declared-but-invalid source is reported once as `invalid-source-record`, never also as `unknown-source-ref`. `errors` is aggregated per-ID (one report per bad record).
- `check` exit code: non-zero iff any source `validation == invalid` OR `freshness in {stale, unreachable}` OR any ref `status == unresolved` OR any leaf has a malformed `sources:` field. On the freshness axis `fresh` / `not_checked` / `not_applicable` / `unknown` are clean (an invalid record still fails, but via the validation axis; `unknown` is the freshness value invalid/unclassifiable records carry, never the reference-only `not_applicable`). A corrupt/non-mapping registry surfaces as an `invalid` source (never an empty, clean report).

---

### Task 1: Source registry loader + validation

**Files:**
- Create: `science/src/science_tool/skills_lint/sources.py`
- Test: `science/tests/skills_lint/test_sources.py`

**Interfaces:**
- Produces: `SourceRecord` (frozen dataclass); `SourcesRegistry` (`.records: dict[str, SourceRecord]`, `.errors: dict[str, list[str]]`, `.declared_ids: frozenset[str]`); `load_sources(path) -> SourcesRegistry`; `validate_record(source_id, raw) -> list[str]`; `parse_frontmatter(path) -> dict | None`; `leaf_source_refs(path) -> tuple[list[str] | None, str | None]`; `iso_date(value) -> str | None`; and the module constants + regexes (`GIT_BACKED_KINDS`, `REFERENCE_KINDS`, `VALID_KINDS`, `FETCH_HOST_ALLOWLIST`, `SOURCE_KNOWN_KEYS`, `SHA_RE`, `DOI_RE`, `ARXIV_RE`, `ISBN_RE`).

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/skills_lint/test_sources.py
import datetime
from pathlib import Path

from science_tool.skills_lint.sources import (
    iso_date,
    leaf_source_refs,
    load_sources,
    validate_record,
)

GIT_OK = {
    "title": "Baygent Skills",
    "authors": ["Alexandre Andorra"],
    "url": "https://github.com/Learning-Bayesian-Statistics/baygent-skills",
    "kind": "skill-repo",
    "license": "MIT",
    "upstream_ref": "a" * 40,
    "last_checked": "2026-07-18",
}
REF_OK = {
    "title": "Causal Inference: What If",
    "authors": ["Hernán", "Robins"],
    "url": "https://doi.org/10.1201/9781420076615",
    "kind": "book",
    "last_checked": "2026-07-18",
}


def test_valid_git_backed_record_has_no_problems() -> None:
    assert validate_record("baygent-skills", GIT_OK) == []


def test_valid_reference_record_without_license_ok() -> None:
    assert validate_record("whatif", REF_OK) == []


def test_missing_url_is_a_problem() -> None:
    raw = {k: v for k, v in GIT_OK.items() if k != "url"}
    assert any("url" in p for p in validate_record("x", raw))


def test_non_https_url_is_a_problem() -> None:
    assert any("https" in p for p in validate_record("x", {**GIT_OK, "url": "http://github.com/a/b"}))


def test_url_without_hostname_is_a_problem() -> None:
    assert any("hostname" in p for p in validate_record("x", {**GIT_OK, "url": "https:foo"}))


def test_abbreviated_upstream_ref_rejected() -> None:
    assert any("upstream_ref" in p for p in validate_record("x", {**GIT_OK, "upstream_ref": "aa940481"}))


def test_non_github_git_backed_host_rejected_in_loader() -> None:
    assert any("host" in p for p in validate_record("x", {**GIT_OK, "url": "https://gitlab.com/a/b"}))


def test_git_backed_missing_license_rejected() -> None:
    raw = {k: v for k, v in GIT_OK.items() if k != "license"}
    assert any("license" in p for p in validate_record("x", raw))


def test_reference_with_upstream_ref_rejected() -> None:
    assert any("upstream_ref" in p for p in validate_record("x", {**REF_OK, "upstream_ref": "b" * 40}))


def test_unknown_key_rejected() -> None:
    assert any("unknown" in p.lower() for p in validate_record("x", {**GIT_OK, "bogus": 1}))


def test_invalid_kind_rejected() -> None:
    assert any("kind" in p for p in validate_record("x", {**GIT_OK, "kind": "blog"}))


def test_malformed_doi_rejected() -> None:
    assert any("doi" in p for p in validate_record("x", {**REF_OK, "doi": "not-a-doi"}))


def test_wellformed_doi_accepted() -> None:
    assert validate_record("x", {**REF_OK, "doi": "10.7326/M16-2607"}) == []


def test_malformed_isbn_rejected() -> None:
    assert any("isbn" in p for p in validate_record("x", {**REF_OK, "isbn": "123"}))


def test_wellformed_isbn_accepted() -> None:
    assert validate_record("x", {**REF_OK, "isbn": "978-1-119-18684-7"}) == []


def test_malformed_arxiv_rejected() -> None:
    assert any("arxiv" in p for p in validate_record("x", {**REF_OK, "arxiv": "nope"}))


def test_non_string_optional_field_rejected() -> None:
    assert any("notes" in p for p in validate_record("x", {**REF_OK, "notes": 5}))


def test_non_string_identifier_rejected() -> None:
    assert any("doi" in p for p in validate_record("x", {**REF_OK, "doi": 123}))


def test_iso_date_coerces_python_date() -> None:
    assert iso_date(datetime.date(2026, 7, 18)) == "2026-07-18"
    assert iso_date("2026-07-18") == "2026-07-18"
    assert iso_date("not-a-date") is None


def test_load_sources_records_errors_and_declared_ids(tmp_path: Path) -> None:
    (tmp_path / "sources.yaml").write_text(
        "good:\n"
        "  title: Good\n  authors: [A]\n  url: https://doi.org/x\n"
        "  kind: paper\n  last_checked: 2026-07-18\n"
        "bad:\n"
        "  title: Bad\n  authors: [A]\n  kind: paper\n  last_checked: 2026-07-18\n",  # missing url
        encoding="utf-8",
    )
    reg = load_sources(tmp_path / "sources.yaml")
    assert "good" in reg.records
    assert "bad" not in reg.records
    assert "bad" in reg.errors and reg.errors["bad"]  # aggregated per id
    assert reg.declared_ids == frozenset({"good", "bad"})


def test_load_sources_missing_file_is_empty(tmp_path: Path) -> None:
    reg = load_sources(tmp_path / "sources.yaml")
    assert reg.records == {} and reg.errors == {} and reg.declared_ids == frozenset()


def test_leaf_source_refs_reads_list(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: y\nsources: [a, b]\n---\n# X\n", encoding="utf-8")
    assert leaf_source_refs(leaf) == (["a", "b"], None)


def test_leaf_source_refs_flags_non_list(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: y\nsources: nope\n---\n# X\n", encoding="utf-8")
    refs, error = leaf_source_refs(leaf)
    assert refs is None and error is not None


def test_leaf_without_sources_returns_none(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: y\n---\n# X\n", encoding="utf-8")
    assert leaf_source_refs(leaf) == (None, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources.py -q`
Expected: FAIL (`ModuleNotFoundError: science_tool.skills_lint.sources`).

- [ ] **Step 3: Write the loader**

```python
# science/src/science_tool/skills_lint/sources.py
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

GIT_BACKED_KINDS = frozenset({"skill-repo", "package-docs"})
REFERENCE_KINDS = frozenset({"book", "paper", "course"})
VALID_KINDS = GIT_BACKED_KINDS | REFERENCE_KINDS
FETCH_HOST_ALLOWLIST = frozenset({"github.com"})
SOURCE_KNOWN_KEYS = frozenset(
    {
        "title", "authors", "url", "kind", "license", "attribution_notice",
        "upstream_ref", "last_checked", "doi", "arxiv", "isbn", "notes",
    }
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
ARXIV_RE = re.compile(r"^(\d{4}\.\d{4,5}(v\d+)?|[a-z-]+(\.[A-Z]{2})?/\d{7}(v\d+)?)$")
ISBN_RE = re.compile(r"^(\d{13}|\d{9}[\dXx])$")


@dataclass(frozen=True)
class SourceRecord:
    id: str
    title: str
    authors: tuple[str, ...]
    url: str
    kind: str
    last_checked: str
    license: str | None = None
    attribution_notice: str | None = None
    upstream_ref: str | None = None
    doi: str | None = None
    arxiv: str | None = None
    isbn: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SourcesRegistry:
    records: dict[str, SourceRecord]
    errors: dict[str, list[str]]
    declared_ids: frozenset[str]


def iso_date(value: object) -> str | None:
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    return None


def _identifier_problem(ident: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return f"{ident} must be a non-empty string when present"
    if ident == "doi" and not DOI_RE.match(value):
        return "doi is malformed"
    if ident == "arxiv" and not ARXIV_RE.match(value):
        return "arxiv is malformed"
    if ident == "isbn" and not ISBN_RE.match(value.replace("-", "").replace(" ", "")):
        return "isbn is malformed"
    return None


def validate_record(source_id: object, raw: object) -> list[str]:
    if not isinstance(source_id, str) or not source_id:
        return ["source id must be a non-empty string"]
    if not isinstance(raw, dict):
        return ["record must be a mapping"]

    problems: list[str] = []
    unknown = set(raw) - SOURCE_KNOWN_KEYS
    if unknown:
        problems.append(f"unknown keys: {', '.join(sorted(unknown))}")

    if not isinstance(raw.get("title"), str) or not str(raw.get("title")).strip():
        problems.append("title must be a non-empty string")

    authors = raw.get("authors")
    if not isinstance(authors, list) or not authors or not all(
        isinstance(a, str) and a.strip() for a in authors
    ):
        problems.append("authors must be a non-empty list of strings")

    kind = raw.get("kind")
    if kind not in VALID_KINDS:
        problems.append(f"kind must be one of {sorted(VALID_KINDS)}")

    url = raw.get("url")
    parsed = None
    if not isinstance(url, str) or not url:
        problems.append("url is required")
    else:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            problems.append("url must use https")
        elif not parsed.hostname:
            problems.append("url must include a hostname")

    if iso_date(raw.get("last_checked")) is None:
        problems.append("last_checked must be an ISO date")

    for ident in ("doi", "arxiv", "isbn"):
        problem = _identifier_problem(ident, raw.get(ident))
        if problem:
            problems.append(problem)

    for opt in ("license", "attribution_notice", "notes"):
        value = raw.get(opt)
        if value is not None and not isinstance(value, str):
            problems.append(f"{opt} must be a string when present")

    if kind in GIT_BACKED_KINDS:
        ref = raw.get("upstream_ref")
        if not isinstance(ref, str) or not SHA_RE.match(ref):
            problems.append("git-backed source requires a full 40-hex upstream_ref")
        lic = raw.get("license")
        if not isinstance(lic, str) or not lic.strip():
            problems.append("git-backed source requires a license")
        if parsed is not None and parsed.hostname not in FETCH_HOST_ALLOWLIST:
            problems.append(f"git-backed url host must be in {sorted(FETCH_HOST_ALLOWLIST)}")
    elif kind in REFERENCE_KINDS and "upstream_ref" in raw:
        problems.append("reference-only source must not set upstream_ref")

    return problems


def _build_record(source_id: str, raw: dict[str, Any]) -> SourceRecord:
    return SourceRecord(
        id=source_id,
        title=raw["title"],
        authors=tuple(raw["authors"]),
        url=raw["url"],
        kind=raw["kind"],
        last_checked=iso_date(raw["last_checked"]) or "",
        license=raw.get("license"),
        attribution_notice=raw.get("attribution_notice"),
        upstream_ref=raw.get("upstream_ref"),
        doi=raw.get("doi"),
        arxiv=raw.get("arxiv"),
        isbn=raw.get("isbn"),
        notes=raw.get("notes"),
    )


def load_sources(path: Path) -> SourcesRegistry:
    empty = SourcesRegistry(records={}, errors={}, declared_ids=frozenset())
    if not path.is_file():
        return empty
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return SourcesRegistry(records={}, errors={"<file>": [f"invalid YAML: {exc}"]}, declared_ids=frozenset())
    if not isinstance(raw, dict):
        return SourcesRegistry(records={}, errors={"<file>": ["sources.yaml is not a mapping"]}, declared_ids=frozenset())

    records: dict[str, SourceRecord] = {}
    errors: dict[str, list[str]] = {}
    for source_id, record_raw in raw.items():
        sid = str(source_id)
        problems = validate_record(source_id, record_raw)
        if problems:
            errors[sid] = problems
        else:
            records[sid] = _build_record(sid, record_raw)
    return SourcesRegistry(records=records, errors=errors, declared_ids=frozenset(str(k) for k in raw))


def parse_frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        parsed = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def leaf_source_refs(path: Path) -> tuple[list[str] | None, str | None]:
    frontmatter = parse_frontmatter(path)
    if frontmatter is None or "sources" not in frontmatter:
        return None, None
    raw = frontmatter["sources"]
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        return None, "sources must be a list of strings"
    return list(raw), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/skills_lint/sources.py science/tests/skills_lint/test_sources.py
git commit -m "feat(skills): typed source-registry loader with shape-validating, kind-conditional records"
```

---

### Task 2: Lint integration — `unknown-source-ref` + `invalid-source-record`

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py`
- Test: `science/tests/skills_lint/test_lint.py` (append)

**Interfaces:**
- Consumes: `load_sources`, `leaf_source_refs`, `SourcesRegistry` (Task 1).
- Produces: `IssueKind` members `"unknown-source-ref"`, `"invalid-source-record"`; `check_source_refs(path, registry) -> list[SkillIssue]` (resolves against `registry.declared_ids`); `check_skills` loads the registry once and emits one `invalid-source-record` per bad ID (aggregated detail).

- [ ] **Step 1: Write the failing tests** (append to `test_lint.py`)

```python
def test_unknown_source_ref_flagged(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text(
        "known:\n  title: K\n  authors: [A]\n  url: https://doi.org/x\n"
        "  kind: paper\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (skills_root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [known, missing]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills

    kinds = {(i.kind, i.detail) for i in check_skills(skills_root)}
    assert ("unknown-source-ref", "missing") in kinds
    assert ("unknown-source-ref", "known") not in kinds


def test_declared_but_invalid_source_is_not_also_unknown_ref(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "sources.yaml").write_text(
        "brokensrc:\n  title: B\n  authors: [A]\n  kind: paper\n  last_checked: 2026-07-18\n",  # missing url
        encoding="utf-8",
    )
    (skills_root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (skills_root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [brokensrc]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    from science_tool.skills_lint.lint import check_skills

    issues = check_skills(skills_root)
    invalid = [i for i in issues if i.kind == "invalid-source-record" and i.field == "brokensrc"]
    unknown = [i for i in issues if i.kind == "unknown-source-ref"]
    assert len(invalid) == 1  # aggregated: exactly one record report
    assert unknown == []      # not double-flagged as a missing ref


def test_sources_not_a_list_flagged_as_invalid_field(tmp_path: Path) -> None:
    from science_tool.skills_lint.lint import check_source_refs
    from science_tool.skills_lint.sources import SourcesRegistry

    leaf = tmp_path / "leaf.md"
    leaf.write_text("---\nname: x\ndescription: d\nsources: oops\n---\n# X\n", encoding="utf-8")
    issues = check_source_refs(leaf, SourcesRegistry(records={}, errors={}, declared_ids=frozenset()))
    assert len(issues) == 1
    assert issues[0].kind == "invalid-field"
    assert issues[0].field == "sources"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -q -k "source or invalid or unknown"`
Expected: FAIL (`check_source_refs` undefined / new kinds not emitted).

- [ ] **Step 3: Edit `lint.py`**

Extend the `IssueKind` literal:

```python
IssueKind = Literal[
    "missing-frontmatter",
    "invalid-yaml",
    "missing-field",
    "invalid-field",
    "missing-section",
    "broken-relative-link",
    "missing-index-entry",
    "unknown-source-ref",
    "invalid-source-record",
]
```

Add the import near the top:

```python
from science_tool.skills_lint.sources import SourcesRegistry, leaf_source_refs, load_sources
```

Add the checker:

```python
def check_source_refs(path: Path, registry: SourcesRegistry) -> list[SkillIssue]:
    refs, error = leaf_source_refs(path)
    if error is not None:
        return [SkillIssue(path, "invalid-field", field="sources", detail=error)]
    if refs is None:
        return []
    return [
        SkillIssue(path, "unknown-source-ref", detail=ref)
        for ref in refs
        if ref not in registry.declared_ids
    ]
```

Replace `check_skills`:

```python
def check_skills(root: Path) -> list[SkillIssue]:
    issues: list[SkillIssue] = []
    registry = load_sources(root / "sources.yaml")
    issues.extend(
        _relative_issues(
            [
                SkillIssue(root / "sources.yaml", "invalid-source-record", field=sid, detail="; ".join(problems))
                for sid, problems in registry.errors.items()
            ],
            root,
        )
    )
    for path in sorted(root.rglob("*.md")):
        issues.extend(_relative_issues(check_frontmatter(path), root))
        issues.extend(_relative_issues(check_companion_skills(path), root))
        issues.extend(_relative_issues(check_halt_on_conditions(path, root), root))
        issues.extend(_relative_issues(check_relative_links(path), root))
        issues.extend(_relative_issues(check_source_refs(path, registry), root))
    issues.extend(check_index_coverage(root))
    return issues
```

- [ ] **Step 4: Run to verify pass (new + existing)**

Run: `cd science && uv run --frozen pytest tests/skills_lint/ -q`
Expected: PASS (including the pre-existing lint tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/skills_lint/lint.py science/tests/skills_lint/test_lint.py
git commit -m "feat(skills): lint unresolved source refs (vs declared ids) and invalid records"
```

---

### Task 3: Seed `skills/sources.yaml` + third-party notice

**Files:**
- Create: `skills/sources.yaml`
- Create: `THIRD_PARTY_NOTICES.md` (repo root)
- Test: `science/tests/skills_lint/test_sources_registry_repo.py`

**Note on the notice file:** The new leaves re-express baygent's ideas in original
prose (no verbatim copy), so the pull is ideas-only. But because they retain the
upstream workflow's *selection, ordering, thresholds, and distinctive examples*,
we do not treat "no substantial portion" as settled. A root `THIRD_PARTY_NOTICES.md`
carrying the upstream MIT license verbatim is cheap insurance and removes the
ambiguity — it lives at the repo root, outside `skills/`, so the skills linter does
not touch it.

- [ ] **Step 1: Write the failing guard test**

```python
# science/tests/skills_lint/test_sources_registry_repo.py
from pathlib import Path

from science_tool.skills_lint.sources import load_sources

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCES = REPO_ROOT / "skills" / "sources.yaml"


def test_repo_sources_registry_is_valid() -> None:
    registry = load_sources(SOURCES)
    assert registry.errors == {}
    assert "baygent-skills" in registry.records
    assert registry.records["baygent-skills"].kind == "skill-repo"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources_registry_repo.py -q`
Expected: FAIL (`sources.yaml` absent → `baygent-skills` not in records).

- [ ] **Step 3: Create `skills/sources.yaml`**

```yaml
baygent-skills:
  title: "Baygent Skills — Learning Bayesian Statistics"
  authors: ["Alexandre Andorra"]
  url: "https://github.com/Learning-Bayesian-Statistics/baygent-skills"
  kind: skill-repo
  license: MIT
  attribution_notice: "Copyright (c) 2026 Learning Bayesian Statistics — MIT; used on an ideas/practices-only basis."
  upstream_ref: "aa940481ebb9fbd087b2fc41dba3af386b5bdb31"
  last_checked: "2026-07-18"
  notes: >
    Pulled: gated Bayesian-workflow spine, calibration, power-scaling prior
    sensitivity, LOO/stacking model comparison, DAG-first identification with the
    M-bias/collider caveat. Radev co-authored the (unused) amortized-workflow.

gelman-bayesian-workflow:
  title: "Bayesian Workflow"
  authors:
    - "Andrew Gelman"
    - "Aki Vehtari"
    - "Daniel Simpson"
    - "Charles C. Margossian"
    - "Bob Carpenter"
    - "Yuling Yao"
    - "Lauren Kennedy"
    - "Jonah Gabry"
    - "Paul-Christian Bürkner"
    - "Martin Modrák"
  url: "https://arxiv.org/abs/2011.01808"
  kind: paper
  arxiv: "2011.01808"
  last_checked: "2026-07-18"

vehtari-loo:
  title: "Practical Bayesian model evaluation using leave-one-out cross-validation and WAIC"
  authors: ["Aki Vehtari", "Andrew Gelman", "Jonah Gabry"]
  url: "https://doi.org/10.1007/s11222-016-9696-4"
  kind: paper
  doi: "10.1007/s11222-016-9696-4"
  last_checked: "2026-07-18"

hernan-robins-whatif:
  title: "Causal Inference: What If"
  authors: ["Miguel A. Hernán", "James M. Robins"]
  url: "https://www.hsph.harvard.edu/miguel-hernan/causal-inference-book/"
  kind: book
  last_checked: "2026-07-18"

pearl-primer:
  title: "Causal Inference in Statistics: A Primer"
  authors: ["Judea Pearl", "Madelyn Glymour", "Nicholas P. Jewell"]
  url: "https://www.wiley.com/en-us/Causal+Inference+in+Statistics%3A+A+Primer-p-9781119186847"
  kind: book
  isbn: "9781119186847"
  last_checked: "2026-07-18"

vanderweele-ding-evalue:
  title: "Sensitivity Analysis in Observational Research: Introducing the E-Value"
  authors: ["Tyler J. VanderWeele", "Peng Ding"]
  url: "https://doi.org/10.7326/M16-2607"
  kind: paper
  doi: "10.7326/M16-2607"
  last_checked: "2026-07-18"

rosenbaum-sensitivity:
  title: "Observational Studies (2nd ed.), ch. 4 — Sensitivity to Hidden Bias"
  authors: ["Paul R. Rosenbaum"]
  url: "https://doi.org/10.1007/978-1-4757-3692-2_4"
  kind: book
  doi: "10.1007/978-1-4757-3692-2_4"
  last_checked: "2026-07-18"
```

- [ ] **Step 4: Create `THIRD_PARTY_NOTICES.md`** at the repo root — exact content:

```markdown
# Third-Party Notices

This repository's statistics skills draw ideas and practices from the projects
below. Their notices are reproduced here in full as required by their licenses.

## baygent-skills (Learning Bayesian Statistics)

- Source: https://github.com/Learning-Bayesian-Statistics/baygent-skills
- Pinned revision: aa940481ebb9fbd087b2fc41dba3af386b5bdb31
- License: MIT

MIT License

Copyright (c) 2026 Learning Bayesian Statistics

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in the
Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

- [ ] **Step 5: Run to verify pass + lint still green**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources_registry_repo.py -q`
Expected: PASS.
Run: `cd science && uv run science skills lint --root ../skills`
Expected: exit 0, no output (the notice is at the repo root, not under `skills/`, so the linter does not see it).

- [ ] **Step 6: Commit**

```bash
git add skills/sources.yaml THIRD_PARTY_NOTICES.md science/tests/skills_lint/test_sources_registry_repo.py
git commit -m "feat(skills): seed source registry + upstream MIT third-party notice"
```

---

### Task 4: `science skills sources` CLI (list + check)

**Files:**
- Modify: `science/src/science_tool/skills_lint/cli.py`
- Test: `science/tests/skills_lint/test_sources_cli.py`

**Interfaces:**
- Consumes: `load_sources`, `leaf_source_refs`, `SourcesRegistry`, `REFERENCE_KINDS`, `FETCH_HOST_ALLOWLIST`, `SHA_RE` (Task 1); `emit` (`science_tool.output`).
- Produces: `build_dependency_views(root, registry) -> tuple[dict[str, list[str]], dict[str, list[str]], list[tuple[str, str]]]` (by_source, by_leaf, leaf_errors — the last carrying malformed leaf `sources:` fields); `SourceStatus(id, validation, freshness, last_checked, citing_leaves, detail)`; `RefStatus(leaf, ref, status)`; `CheckReport(sources, refs, leaf_errors)` with `.failed()` (fails on any leaf error, invalid/stale/unreachable source, or unresolved ref); `check_sources(root, *, fetch_upstream, fetch=None) -> CheckReport` (surfaces file-level registry errors as `invalid`/`unknown` sources; `fetch` defaults to the module `fetch_remote_head_sha` **resolved at call time**, so the CLI honours a monkeypatched fetch); `fetch_remote_head_sha(url, *, timeout=10, max_bytes=4096, run=_run_git) -> tuple[str | None, str]`; `_run_git(args, *, timeout, env, max_bytes) -> tuple[int | None, bytes]`; the `sources` command group.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/skills_lint/test_sources_cli.py
import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.skills_lint import cli as sources_cli
from science_tool.skills_lint.cli import check_sources, fetch_remote_head_sha


def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text(
        'git:\n  title: G\n  authors: [A]\n'
        '  url: https://github.com/o/r\n  kind: skill-repo\n  license: MIT\n'
        f'  upstream_ref: {"a" * 40}\n  last_checked: 2026-07-18\n'
        "ref:\n  title: R\n  authors: [A]\n  url: https://doi.org/x\n"
        "  kind: book\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (root / "INDEX.md").write_text("`skills/leaf.md`\n", encoding="utf-8")
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [git, ref]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    return root


def test_check_offline_is_clean(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=False)
    by_id = {s.id: s for s in report.sources}
    assert by_id["git"].freshness == "not_checked"
    assert by_id["ref"].freshness == "not_applicable"
    assert by_id["git"].citing_leaves == ("leaf.md",)
    assert by_id["git"].last_checked == "2026-07-18"
    assert all(r.status == "resolved" for r in report.refs)
    assert report.failed() is False


def test_check_fetch_stale_names_citing_leaves(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=True, fetch=lambda url: ("b" * 40, ""))
    git = {s.id: s for s in report.sources}["git"]
    assert git.freshness == "stale"
    assert git.citing_leaves == ("leaf.md",)
    assert report.failed() is True


def test_check_fetch_fresh_is_clean(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=True, fetch=lambda url: ("a" * 40, ""))
    assert {s.id: s.freshness for s in report.sources}["git"] == "fresh"
    assert report.failed() is False


def test_check_fetch_unreachable_fails(tmp_path: Path) -> None:
    report = check_sources(_make_repo(tmp_path), fetch_upstream=True, fetch=lambda url: (None, "timeout"))
    assert {s.id: s.freshness for s in report.sources}["git"] == "unreachable"
    assert report.failed() is True


def test_unresolved_ref_fails(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [git, gone]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    report = check_sources(root, fetch_upstream=False)
    statuses = {(r.ref, r.status) for r in report.refs}
    assert ("gone", "unresolved") in statuses
    assert ("git", "resolved") in statuses
    assert report.failed() is True


def test_cli_list_json_has_both_directions(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = CliRunner().invoke(main, ["skills", "sources", "list", "--root", str(root), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["by_source"]["git"] == ["leaf.md"]
    assert payload["by_leaf"]["leaf.md"] == ["git", "ref"]


def test_cli_check_json_pins_axes_offline(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {"sources", "refs"} <= set(payload)
    for entry in payload["sources"]:
        assert set(entry) >= {"id", "validation", "freshness", "last_checked", "citing_leaves"}
        assert entry["validation"] in {"valid", "invalid"}
        assert entry["freshness"] in {"fresh", "stale", "unreachable", "not_checked", "not_applicable", "unknown"}
    for ref in payload["refs"]:
        assert set(ref) >= {"leaf", "ref", "status"}
        assert ref["status"] in {"resolved", "unresolved"}
    assert "leaf_errors" in payload


def test_cli_check_exit_nonzero_on_unresolved(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: [gone]\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert result.exit_code == 1


def test_check_corrupt_registry_fails_not_silently_clean(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text("just a string, not a mapping\n", encoding="utf-8")
    (root / "INDEX.md").write_text("`skills/x.md`\n", encoding="utf-8")
    report = check_sources(root, fetch_upstream=False)
    # A file-level error must surface as an invalid source, not an empty clean report.
    assert any(s.validation == "invalid" for s in report.sources)
    assert report.failed() is True
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert result.exit_code == 1


def test_check_invalid_record_reports_unknown_freshness_and_fails(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    (root / "sources.yaml").write_text(
        # git-backed but missing upstream_ref/license → invalid; freshness is not
        # "not_applicable" (that is reserved for reference-only), it is "unknown".
        "brokengit:\n  title: B\n  authors: [A]\n"
        "  url: https://github.com/o/r\n  kind: skill-repo\n  last_checked: 2026-07-18\n",
        encoding="utf-8",
    )
    (root / "INDEX.md").write_text("`skills/x.md`\n", encoding="utf-8")
    report = check_sources(root, fetch_upstream=False)
    broken = {s.id: s for s in report.sources}["brokengit"]
    assert broken.validation == "invalid"
    assert broken.freshness == "unknown"
    assert report.failed() is True


def test_check_malformed_leaf_sources_field_fails(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "leaf.md").write_text(
        "---\nname: leaf\ndescription: d\nsources: not-a-list\n---\n"
        "# Leaf\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    report = check_sources(root, fetch_upstream=False)
    assert any(leaf == "leaf.md" for leaf, _ in report.leaf_errors)
    assert report.failed() is True
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert result.exit_code == 1


# --- fetch-mode CLI contract (monkeypatch the module fetch; no network) ---


def test_cli_check_fetch_flag_forwarded_to_fetch(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    calls = {"n": 0}

    def spy(url):
        calls["n"] += 1
        return ("a" * 40, "")

    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", spy)
    # Offline (no flag): fetch must NOT run.
    CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root)])
    assert calls["n"] == 0
    # --fetch-upstream: fetch runs once for the git-backed source.
    CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream"])
    assert calls["n"] == 1


def test_cli_check_fetch_stale_json_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", lambda url: ("b" * 40, ""))
    result = CliRunner().invoke(
        main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream", "--format", "json"]
    )
    payload = json.loads(result.output)
    assert {s["id"]: s["freshness"] for s in payload["sources"]}["git"] == "stale"
    assert result.exit_code == 1


def test_cli_check_fetch_fresh_json_exits_zero(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", lambda url: ("a" * 40, ""))
    result = CliRunner().invoke(
        main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream", "--format", "json"]
    )
    payload = json.loads(result.output)
    assert {s["id"]: s["freshness"] for s in payload["sources"]}["git"] == "fresh"
    assert result.exit_code == 0


def test_cli_check_fetch_unreachable_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    root = _make_repo(tmp_path)
    monkeypatch.setattr(sources_cli, "fetch_remote_head_sha", lambda url: (None, "timeout"))
    result = CliRunner().invoke(main, ["skills", "sources", "check", "--root", str(root), "--fetch-upstream"])
    assert result.exit_code == 1


# --- fetch_remote_head_sha hardening (no network; inject the run seam) ---

def test_fetch_forwards_hardened_args() -> None:
    captured: dict = {}

    def fake_run(args, *, timeout, env, max_bytes):
        captured.update(args=args, timeout=timeout, env=env, max_bytes=max_bytes)
        return 0, (b"a" * 40) + b"\tHEAD\n"

    sha, detail = fetch_remote_head_sha("https://github.com/o/r", timeout=7, max_bytes=99, run=fake_run)
    assert sha == "a" * 40 and detail == ""
    assert captured["args"] == ["git", "ls-remote", "https://github.com/o/r", "HEAD"]
    assert captured["timeout"] == 7 and captured["max_bytes"] == 99
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_fetch_rejects_non_github_host_without_running() -> None:
    called = {"n": 0}

    def fake_run(*a, **k):
        called["n"] += 1
        return 0, b""

    sha, detail = fetch_remote_head_sha("https://gitlab.com/o/r", run=fake_run)
    assert sha is None and "allowlist" in detail
    assert called["n"] == 0


def test_fetch_oversized_output_is_unreachable() -> None:
    sha, detail = fetch_remote_head_sha(
        "https://github.com/o/r", max_bytes=8, run=lambda *a, **k: (0, b"x" * 100)
    )
    assert sha is None and "large" in detail


def test_fetch_malformed_output_is_unreachable() -> None:
    sha, detail = fetch_remote_head_sha(
        "https://github.com/o/r", run=lambda *a, **k: (0, b"not-a-sha\tHEAD\n")
    )
    assert sha is None and "unexpected" in detail


def test_fetch_timeout_is_unreachable() -> None:
    sha, detail = fetch_remote_head_sha("https://github.com/o/r", run=lambda *a, **k: (None, b""))
    assert sha is None


def test_run_git_sets_env_and_bounds_read(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    class FakeStdout:
        def read(self, n):
            seen["read_n"] = n
            return (b"a" * 40) + b"\tHEAD\n"

    class FakeProc:
        returncode = 0
        stdout = FakeStdout()

        def __init__(self, args, **kwargs):
            seen["args"] = args
            seen["env"] = kwargs["env"]

        def poll(self):  # already exited → runner skips the extra kill
            return 0

        def wait(self):
            seen["waited"] = True
            return 0

        def kill(self):
            seen["killed"] = True

    monkeypatch.setattr(sources_cli.subprocess, "Popen", FakeProc)
    code, out = sources_cli._run_git(
        ["git", "ls-remote", "https://github.com/o/r", "HEAD"],
        timeout=5,
        env={"GIT_TERMINAL_PROMPT": "0"},
        max_bytes=16,
    )
    assert code == 0
    assert out.startswith(b"a" * 40)
    assert seen["read_n"] == 17  # max_bytes + 1
    assert seen["waited"] is True  # child is always reaped
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_run_git_timeout_kills_and_reaps(monkeypatch) -> None:
    # A read that outlasts the deadline must kill the child AND wait() to reap it,
    # returning None. The old code that skipped this reaping would leave a zombie.
    import threading

    seen: dict = {}
    release = threading.Event()

    class FakeStdout:
        def read(self, n):
            release.wait(2)  # blocks past the tiny timeout; kill() releases it
            return b""

    class FakeProc:
        returncode = -9
        stdout = FakeStdout()

        def __init__(self, args, **kwargs):
            pass

        def poll(self):
            return None  # still running

        def wait(self):
            seen["waited"] = True
            return -9

        def kill(self):
            seen["killed"] = True
            release.set()  # let the blocked reader unwind so the thread can exit

    monkeypatch.setattr(sources_cli.subprocess, "Popen", FakeProc)
    code, out = sources_cli._run_git(
        ["git", "ls-remote", "https://github.com/o/r", "HEAD"],
        timeout=0.05,
        env={"GIT_TERMINAL_PROMPT": "0"},
        max_bytes=16,
    )
    assert code is None
    assert out == b""
    assert seen.get("killed") is True
    assert seen.get("waited") is True


def test_run_git_capped_live_child_is_killed_before_wait(monkeypatch) -> None:
    # Reader returns at the byte cap while the child is still live (blocked writing
    # to a pipe we stopped reading). It must be killed BEFORE wait(), never an
    # unbounded wait() on a live child, and the capped bytes flow back to the caller.
    seen: dict = {}
    order: list[str] = []

    class FakeStdout:
        def read(self, n):
            seen["read_n"] = n
            return b"x" * n  # fills the cap → over budget, EOF not reached

    class FakeProc:
        returncode = -9
        stdout = FakeStdout()

        def __init__(self, args, **kwargs):
            pass

        def poll(self):
            return None  # still running: blocked on the full pipe

        def kill(self):
            order.append("kill")

        def wait(self):
            order.append("wait")
            return -9

    monkeypatch.setattr(sources_cli.subprocess, "Popen", FakeProc)
    code, out = sources_cli._run_git(
        ["git", "ls-remote", "https://github.com/o/r", "HEAD"],
        timeout=5,
        env={"GIT_TERMINAL_PROMPT": "0"},
        max_bytes=16,
    )
    assert seen["read_n"] == 17
    assert order == ["kill", "wait"]  # kill precedes wait; no unbounded wait on a live child
    assert len(out) == 17  # the over-budget bytes propagate (fetch layer rejects them)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources_cli.py -q`
Expected: FAIL (`check_sources` / `fetch_remote_head_sha` / `_run_git` undefined; `skills sources` not a command).

- [ ] **Step 3: Edit `cli.py`** (append imports + logic)

```python
import os
import subprocess
import threading
from dataclasses import dataclass, field
from urllib.parse import urlparse

from science_tool.skills_lint.sources import (
    FETCH_HOST_ALLOWLIST,
    REFERENCE_KINDS,
    SHA_RE,
    SourcesRegistry,
    leaf_source_refs,
    load_sources,
)


def build_dependency_views(
    root: Path, registry: SourcesRegistry
) -> tuple[dict[str, list[str]], dict[str, list[str]], list[tuple[str, str]]]:
    by_source: dict[str, list[str]] = {sid: [] for sid in registry.declared_ids}
    by_leaf: dict[str, list[str]] = {}
    leaf_errors: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.md")):
        refs, error = leaf_source_refs(path)
        rel = path.relative_to(root).as_posix()
        if error is not None:
            leaf_errors.append((rel, error))
            continue
        if not refs:
            continue
        by_leaf[rel] = list(refs)
        for ref in refs:
            by_source.setdefault(ref, []).append(rel)
    return by_source, by_leaf, leaf_errors


def _run_git(args: list[str], *, timeout: int, env: dict[str, str], max_bytes: int) -> tuple[int | None, bytes]:
    """Run a git command, reading at most ``max_bytes + 1`` bytes. The child is
    always reaped: on a read that outlasts ``timeout`` we kill and wait (returning
    ``None``); once the reader returns we never block on ``wait()`` for a still-live
    child holding a full pipe — we kill it first, then reap. ``returncode`` is
    ``None`` on timeout or spawn failure."""
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    except OSError:
        return None, b""
    box: dict[str, bytes] = {}

    def _read() -> None:
        assert proc.stdout is not None
        box["out"] = proc.stdout.read(max_bytes + 1)

    reader = threading.Thread(target=_read, daemon=True)
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        # Read outlasted the deadline; kill so the blocked read unwinds, then reap.
        proc.kill()
        proc.wait()
        return None, b""
    # Reader returned (EOF or byte cap). If the child is still live it is blocked
    # writing to a pipe we have stopped reading — kill it rather than wait() forever.
    if proc.poll() is None:
        proc.kill()
    proc.wait()
    return proc.returncode, box.get("out", b"")


def fetch_remote_head_sha(url: str, *, timeout: int = 10, max_bytes: int = 4096, run=_run_git) -> tuple[str | None, str]:
    if urlparse(url).hostname not in FETCH_HOST_ALLOWLIST:
        return None, "host not in allowlist"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    code, out = run(["git", "ls-remote", url, "HEAD"], timeout=timeout, env=env, max_bytes=max_bytes)
    if code is None:
        return None, "unreachable (timeout or spawn error)"
    if len(out) > max_bytes:
        # Checked before the return code: an over-budget read means the child was
        # killed mid-write, so its exit status is a signal, not "success"/"failure".
        return None, "ls-remote output too large"
    if code != 0:
        return None, "git ls-remote failed"
    first = out.decode("utf-8", "replace").split("\n", 1)[0]
    sha = first.split("\t", 1)[0].strip()
    if not SHA_RE.match(sha):
        return None, "unexpected ls-remote output"
    return sha, ""


@dataclass(frozen=True)
class SourceStatus:
    id: str
    validation: str
    freshness: str
    last_checked: str = ""
    citing_leaves: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class RefStatus:
    leaf: str
    ref: str
    status: str


@dataclass
class CheckReport:
    sources: list[SourceStatus] = field(default_factory=list)
    refs: list[RefStatus] = field(default_factory=list)
    leaf_errors: list[tuple[str, str]] = field(default_factory=list)

    def failed(self) -> bool:
        if self.leaf_errors:
            return True
        if any(s.validation == "invalid" or s.freshness in ("stale", "unreachable") for s in self.sources):
            return True
        return any(r.status == "unresolved" for r in self.refs)


def check_sources(root: Path, *, fetch_upstream: bool, fetch=None) -> CheckReport:
    # Resolve the fetch seam from the module global at call time (not as a bound
    # default), so the CLI path — which omits `fetch` — honours a monkeypatched
    # `fetch_remote_head_sha` and fetch-mode is testable without network.
    if fetch is None:
        fetch = fetch_remote_head_sha
    registry = load_sources(root / "sources.yaml")
    by_source, by_leaf, leaf_errors = build_dependency_views(root, registry)
    report = CheckReport(leaf_errors=list(leaf_errors))
    # File-level registry errors (unparseable YAML, non-mapping document) live in
    # registry.errors under a key that is not a declared id — surface them so a
    # corrupt registry fails the check instead of yielding an empty, clean report.
    for key in sorted(set(registry.errors) - registry.declared_ids):
        report.sources.append(SourceStatus(key, "invalid", "unknown", "", (), "; ".join(registry.errors[key])))
    for sid in sorted(registry.declared_ids):
        citing = tuple(by_source.get(sid, []))
        if sid in registry.errors:
            report.sources.append(SourceStatus(sid, "invalid", "unknown", "", citing, "; ".join(registry.errors[sid])))
            continue
        record = registry.records[sid]
        if record.kind in REFERENCE_KINDS:
            report.sources.append(SourceStatus(sid, "valid", "not_applicable", record.last_checked, citing))
        elif not fetch_upstream:
            report.sources.append(SourceStatus(sid, "valid", "not_checked", record.last_checked, citing))
        else:
            remote, detail = fetch(record.url)
            if remote is None:
                report.sources.append(SourceStatus(sid, "valid", "unreachable", record.last_checked, citing, detail))
            elif remote == record.upstream_ref:
                report.sources.append(SourceStatus(sid, "valid", "fresh", record.last_checked, citing))
            else:
                report.sources.append(
                    SourceStatus(sid, "valid", "stale", record.last_checked, citing, f"upstream {remote[:8]} != pinned {(record.upstream_ref or '')[:8]}")
                )
    for leaf, ref_list in sorted(by_leaf.items()):
        for ref in ref_list:
            status = "resolved" if ref in registry.declared_ids else "unresolved"
            report.refs.append(RefStatus(leaf, ref, status))
    return report


@skills_group.group(name="sources")
def sources_group() -> None:
    """Skill source-provenance tooling."""


@sources_group.command(name="list")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def sources_list_cmd(root: str, fmt: str) -> None:
    """List the source → leaf dependency tree (both directions)."""
    registry = load_sources(Path(root) / "sources.yaml")
    by_source, by_leaf, _ = build_dependency_views(Path(root), registry)

    def _render() -> None:
        click.echo("By source:")
        for sid in sorted(by_source):
            leaves = by_source[sid]
            click.echo(f"  {sid}: {', '.join(leaves) if leaves else '(unused)'}")
        click.echo("By leaf:")
        for leaf in sorted(by_leaf):
            click.echo(f"  {leaf}: {', '.join(by_leaf[leaf])}")

    emit(
        output_format=fmt,
        payload={
            "by_source": {sid: by_source[sid] for sid in sorted(by_source)},
            "by_leaf": {leaf: by_leaf[leaf] for leaf in sorted(by_leaf)},
        },
        render_text=_render,
    )


@sources_group.command(name="check")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--fetch-upstream", is_flag=True, default=False, help="Compare pinned SHA against upstream HEAD (network).")
def sources_check_cmd(root: str, fmt: str, fetch_upstream: bool) -> None:
    """Validate the registry and (optionally) check upstream freshness."""
    report = check_sources(Path(root), fetch_upstream=fetch_upstream)

    def _render() -> None:
        for status in report.sources:
            line = f"{status.id}: validation={status.validation} freshness={status.freshness} last_checked={status.last_checked}"
            if status.citing_leaves:
                line += f" cited_by={', '.join(status.citing_leaves)}"
            if status.detail:
                line += f" ({status.detail})"
            click.echo(line)
        for ref in report.refs:
            if ref.status == "unresolved":
                click.echo(f"{ref.leaf}: unresolved-source-ref {ref.ref}")
        for leaf, error in report.leaf_errors:
            click.echo(f"{leaf}: invalid sources field ({error})")

    emit(
        output_format=fmt,
        payload={
            "sources": [
                {
                    "id": s.id, "validation": s.validation, "freshness": s.freshness,
                    "last_checked": s.last_checked, "citing_leaves": list(s.citing_leaves), "detail": s.detail,
                }
                for s in report.sources
            ],
            "refs": [{"leaf": r.leaf, "ref": r.ref, "status": r.status} for r in report.refs],
            "leaf_errors": [{"leaf": leaf, "error": error} for leaf, error in report.leaf_errors],
        },
        render_text=_render,
    )
    if report.failed():
        raise click.exceptions.Exit(1)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_sources_cli.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/skills_lint/cli.py science/tests/skills_lint/test_sources_cli.py
git commit -m "feat(skills): science skills sources (both-direction list + three-axis freshness check)"
```

---

### Task 5: New leaf — `bayesian-workflow.md`

**Files:**
- Create: `skills/statistics/bayesian-workflow.md`
- Modify: `skills/INDEX.md` (one line under `## Statistics`), `skills/statistics/SKILL.md` (Leaves row + Principle)

**Interfaces:** cites `baygent-skills`, `gelman-bayesian-workflow`, `vehtari-loo` (present from Task 3).

- [ ] **Step 1: Create the leaf** — exact content:

```markdown
---
name: statistics-bayesian-workflow
description: Use when building, fitting, or reviewing a Bayesian/probabilistic model — prior choice, MCMC sampling, convergence diagnostics, posterior-predictive and calibration checks, prior sensitivity, and Bayesian model comparison.
sources: [baygent-skills, gelman-bayesian-workflow, vehtari-loo]
---

# Bayesian Workflow

Use when building, fitting, or reviewing a Bayesian model. The workflow is a
gated sequence, not a menu: a downstream step is only meaningful once the earlier
gate has passed. Most of these steps an agent will skip unless prompted — that is
exactly why they are written down.

## The Gated Sequence

1. **Formulate the model and name the estimand.** What quantity carries the
   verdict — a contrast, a coefficient, a predicted quantity?
2. **Prior predictive check — before fitting.** Simulate parameters from the
   priors, push them through the likelihood, and confirm the *implied data* are
   physically plausible. Absurd prior-predictive ranges mean the priors are wrong;
   fix them before touching real data.
3. **Fit.** Sampler-agnostic (NUTS/nutpie, NumPyro, emcee). Two habits:
   - Use a **descriptive, reproducible seed** (e.g. `sum(map(ord, name))`), not a
     bare `42`, so the seed records which analysis it belongs to.
   - **Save the fitted object / InferenceData immediately** — diagnostics and
     comparison downstream depend on it.
4. **Convergence gate.** Do not read the posterior until: R-hat ≤ 1.01 on every
   verdict-bearing parameter, ESS ≥ 100·chains, zero divergences, tree-depth not
   saturated, E-BFMI healthy. A failed gate is fixed by re-parameterizing or
   re-specifying — **not** by raising the draw count to bury divergences.
5. **Model criticism vs calibration — keep them distinct.**
   - *Posterior predictive checks* assess in-sample fit (can the fitted model
     reproduce the observed data). Necessary, but **not** calibration.
   - *Calibration* is out-of-sample: **LOO-PIT** (distinct from ordinary in-sample
     PIT), **randomized PIT** for discrete outcomes, and **empirical coverage** on
     held-out or simulated data; **simulation-based calibration (SBC)** when a
     simulator exists. Never present a good posterior-predictive fit *as* evidence
     of calibration — a model can fit the data it was trained on and still be
     miscalibrated out of sample.
6. **Prior/likelihood sensitivity.** Power-scale the prior and the likelihood
   (PSIS, no refit) and flag any conclusion that hinges on the prior. See
   [`sensitivity-arbitration.md`](sensitivity-arbitration.md).
7. **Model comparison.** Out-of-sample predictive comparison, not variable
   selection. See the Bayesian arm of
   [`likelihood-model-comparison.md`](likelihood-model-comparison.md).
8. **Report the interval, not the point.** Report an HDI / credible interval; no
   interval width is magically "right". State the estimand, the priors, the failed
   gates, and any verdict downgrade they force.

## Common Failure Modes

- **Point estimate with no interval.** A posterior mean alone hides the width that
  is the whole reason to be Bayesian.
- **Raising draws to hide divergences.** Divergences are a geometry problem, not a
  sample-size problem; re-parameterize (see the non-centered fix in
  [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md)).
- **PPC passed, called it calibrated.** In-sample fit reported as out-of-sample
  calibration.
- **Prior smuggled into the verdict.** A conclusion that flips under a defensible
  alternate prior, reported as if prior-independent.

## Deeper Dive

The tool-specific version of this workflow — PyMC + ArviZ specifics (nutpie,
`arviz_stats.diagnose()`, PreliZ prior elicitation, regularized-horseshoe sparsity)
— is the upstream `bayesian-workflow` skill by Alexandre Andorra
([baygent-skills](https://github.com/Learning-Bayesian-Statistics/baygent-skills)).

## Companion Skills

- [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md) — non-centered parameterization and grouped-data diagnostics.
- [`sensitivity-arbitration.md`](sensitivity-arbitration.md) — the power-scaling prior-sensitivity step and how it arbitrates the verdict.
- [`likelihood-model-comparison.md`](likelihood-model-comparison.md) — the LOO/ELPD/stacking model-comparison step.
```

- [ ] **Step 2: Add the INDEX entry** — insert under `## Statistics` in `skills/INDEX.md`, after the `statistics-estimator-certification` line:

```markdown
- `statistics-bayesian-workflow`: `skills/statistics/bayesian-workflow.md`
```

- [ ] **Step 3: Add the SKILL.md Leaves row + Principle**

In `skills/statistics/SKILL.md`, add to the Leaves table (after the `estimator-certification` row):

```markdown
| [`bayesian-workflow.md`](./bayesian-workflow.md) | Building/fitting/reviewing a Bayesian model — priors, MCMC, convergence, calibration, comparison |
```

Add Principle 13 after the current Principle 12:

```markdown
13. **A Bayesian fit is a gated sequence, not a menu.** Prior-predictive check
    before fitting; a convergence gate before reading the posterior; calibration
    (LOO-PIT / coverage / SBC) is out-of-sample and distinct from posterior-
    predictive fit; power-scale the prior before trusting the verdict. See
    [`bayesian-workflow`](./bayesian-workflow.md).
```

- [ ] **Step 4: Verify lint green**

Run: `cd science && uv run science skills lint --root ../skills`
Expected: exit 0, no output.

- [ ] **Step 5: Commit**

```bash
git add skills/statistics/bayesian-workflow.md skills/INDEX.md skills/statistics/SKILL.md
git commit -m "feat(statistics): add bayesian-workflow leaf (gated spine + calibration)"
```

---

### Task 6: De-dup the survival leaf's Bayesian diagnostics

**Files:**
- Modify: `skills/statistics/survival-and-hierarchical-models.md`

- [ ] **Step 1: Add `sources:` to the frontmatter**

```markdown
---
name: statistics-survival-and-hierarchical-models
description: Use when designing or reviewing Cox, Weibull, AFT, frailty, mixed-effects, Bayesian hierarchical, or multi-dataset causal models.
sources: [baygent-skills]
---
```

- [ ] **Step 2: Replace the "Bayesian Diagnostics" section body with a pointer**

Replace the entire `## Bayesian Diagnostics` section (its "Minimum requirements" list and the "If diagnostics fail…" paragraph) with:

```markdown
## Bayesian Diagnostics

For the general Bayesian convergence gate (R-hat, ESS, divergences),
posterior-predictive and calibration checks, and prior sensitivity, use
[`bayesian-workflow.md`](bayesian-workflow.md). This leaf adds only the
survival/hierarchical-specific pieces:

- Trace plots and R-hat for **group-level scale parameters**, not just fixed
  effects — the funnel lives in the scales.
- Posterior predictive checks on the **survival/hazard scale** (e.g. predicted vs
  observed Kaplan-Meier), not only on the linear predictor.
- If diagnostics fail, fix the model or downgrade the verdict; do not raise draws
  to hide divergences.
```

- [ ] **Step 3: Add the new leaf to Companion Skills**

Add to the `## Companion Skills` list:

```markdown
- [`bayesian-workflow.md`](bayesian-workflow.md) - the general convergence/calibration/sensitivity gate this leaf specializes.
```

- [ ] **Step 4: Verify lint green**

Run: `cd science && uv run science skills lint --root ../skills`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add skills/statistics/survival-and-hierarchical-models.md
git commit -m "refactor(statistics): point survival leaf at bayesian-workflow for shared diagnostics"
```

---

### Task 7: New leaf — `causal-identification.md`

**Files:**
- Create: `skills/statistics/causal-identification.md`
- Modify: `skills/INDEX.md`, `skills/statistics/SKILL.md`

**Interfaces:** cites `baygent-skills`, `hernan-robins-whatif`, `pearl-primer`, `vanderweele-ding-evalue`, `rosenbaum-sensitivity`.

- [ ] **Step 1: Create the leaf** — exact content:

```markdown
---
name: statistics-causal-identification
description: Use when estimating a causal effect from observational data — choosing an adjustment set, checking the backdoor criterion, distinguishing confounders from mediators/colliders, avoiding over-adjustment and M-bias, or deciding what to do when the effect is not identified.
sources: [baygent-skills, hernan-robins-whatif, pearl-primer, vanderweele-ding-evalue, rosenbaum-sensitivity]
---

# Causal Identification

Use before estimating any causal effect from observational data. Identification
is a question about the **DAG and the estimand**, decided before any model is fit;
a regression coefficient is not a causal effect until identification licenses it.

## DAG First

- **Draw the DAG.** The missing edges are the strongest assumptions you are
  making — they assert "no direct effect", "no common cause". Make them explicit.
- **State the estimand before choosing a design.** Total effect and direct effect
  need *different* adjustment sets; "the effect of X on Y" is ambiguous until you
  say which.

## Adjustment-Set Derivation

- Apply the **backdoor criterion**: block every backdoor path, adjusting for no
  descendant of the treatment.
- **Confounder vs mediator is about role, not timing.** A pre-treatment variable
  is *not* automatically safe to adjust for: conditioning on a collider (or a
  descendant of one) — **M-bias** — opens a path that was closed. The DAG, not the
  measurement order, is the authority.
- **Over-adjustment is a real failure, not caution.** Adjusting for a mediator
  removes part of the total effect you meant to estimate; adjusting for a collider
  induces bias. A *locked* adjustment set that quietly includes a mediator is a
  common, hard-to-catch error — verify the set against the DAG and the estimand,
  not against a covariate wishlist.

## When the Effect Is Not Point-Identified by Adjustment

Keep these four responses distinct — they are not interchangeable, and conflating
them overstates what the analysis can claim:

1. **Alternative identification strategy** (conditional on its own assumptions) —
   an instrument (IV), the front-door criterion. These can *point-identify* an
   effect, but often a **different estimand**: an IV under monotonicity identifies
   a LATE/CACE (the complier effect), not the ATE. **Re-state the estimand
   explicitly** when you switch strategy; never answer an ATE question with a LATE
   without saying so.
2. **Formal partial identification** — set-identifying bounds (Manski-style) that
   bracket the target effect under weaker assumptions.
3. **Sensitivity analysis** that leaves the effect **non-identified** but
   quantifies robustness to hidden bias — scoped to where each tool applies. The
   **E-value** describes how strong unmeasured confounding would have to be to
   explain away an *association*, on its compatible (ratio-scale) effect measures;
   it is not an identification device. **Rosenbaum bounds** apply to
   matched/stratified observational designs. Neither identifies the effect nor
   supplies causal-effect bounds — do not file them under partial identification.
4. **Fail-closed verdict** — when none of the above licenses a causal claim at the
   current operating point, say so plainly rather than reporting an adjusted
   association as if it were the effect.

## Executable Path

The Science toolkit derives adjustment sets and identifiability from the DAG
rather than leaving them to be argued by hand. Three distinct entry points, doing
three different things:

- **`science inquiry validate <slug>`** — runs the identifiability and
  adjustment-set checks **in-process**: it builds the DAG, checks whether the
  estimand is identifiable via the back-door criterion, and reports the valid
  adjustment sets (via `CausalInference.get_all_backdoor_adjustment_sets`). This is
  the command that actually computes and reports the verdict.
- **`science inquiry export-pgmpy <slug>`** — **generates a pgmpy script** that
  computes those same backdoor adjustment sets *when you run it*. Use it to inspect
  or extend the computation; the command emits the script, it does not run it. (Author
  the DAG first via `science inquiry` / `sketch-model` / `specify-model`.)
- **`/science:critique-approach`** — an *agentic* adversarial pass over the DAG for
  missing confounders, colliders, M-bias, and over-adjustment. It critiques the
  model's assumptions; it does not compute identifiability.
- **Caveat:** the in-process identifiability checks (`inquiry validate`) require
  `pgmpy`; if it is absent the check currently **skips rather than fails**, so
  confirm it is installed before trusting a clean result.

## Deeper Dive

For quasi-experimental designs (difference-in-differences, RDD, interrupted time
series, IV, synthetic control), design-specific refutation recipes, and the
calibrated causal-language ladder, see the upstream `causal-inference` skill by
Alexandre Andorra
([baygent-skills](https://github.com/Learning-Bayesian-Statistics/baygent-skills)).

## Companion Skills

- [`survival-and-hierarchical-models.md`](survival-and-hierarchical-models.md) — confounder timing and collider adjustment inside survival/hierarchical models.
- [`bias-vs-variance-decomposition.md`](bias-vs-variance-decomposition.md) — confounding as a bias term that averaging does not remove.
- [`bayesian-workflow.md`](bayesian-workflow.md) — once identification licenses the estimand, the fitting/diagnostic discipline for estimating it.
```

- [ ] **Step 2: INDEX entry** — add under `## Statistics`:

```markdown
- `statistics-causal-identification`: `skills/statistics/causal-identification.md`
```

- [ ] **Step 3: SKILL.md Leaves row + Principle**

Leaves table row:

```markdown
| [`causal-identification.md`](./causal-identification.md) | Choosing an adjustment set, backdoor/confounder/collider/M-bias checks, over-adjustment, or a non-identified estimand |
```

Principle 14:

```markdown
14. **Identification is a DAG question, decided before fitting.** Missing edges are
    the strongest assumptions; pre-treatment timing does not license adjustment
    (M-bias); over-adjusting a mediator or collider is a bias, not caution. When the
    effect is not identified, separate alternative identification (re-stating the
    estimand), partial-identification bounds, hidden-bias sensitivity, and a
    fail-closed verdict. See [`causal-identification`](./causal-identification.md).
```

- [ ] **Step 4: Verify lint green**

Run: `cd science && uv run science skills lint --root ../skills`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add skills/statistics/causal-identification.md skills/INDEX.md skills/statistics/SKILL.md
git commit -m "feat(statistics): add causal-identification leaf (DAG-first + non-identification taxonomy)"
```

---

### Task 8: Extend `likelihood-model-comparison.md` — Bayesian arm (routable)

**Files:**
- Modify: `skills/statistics/likelihood-model-comparison.md`, `skills/statistics/SKILL.md`

**Interfaces:** cites `baygent-skills`, `vehtari-loo`; cross-refs `bayesian-workflow.md`.

- [ ] **Step 1: Update the frontmatter (routing) + add `sources:`**

Replace the frontmatter with (description now advertises the Bayesian arm so it routes):

```markdown
---
name: statistics-likelihood-model-comparison
description: Use when comparing parametric models by likelihood — AIC, BIC, likelihood-ratio tests, nested vs non-nested comparison, identifiability and rare-event numerical-precision audits, bootstrap CIs, and Bayesian out-of-sample comparison (PSIS-LOO / ELPD / stacking weights).
sources: [baygent-skills, vehtari-loo]
---
```

- [ ] **Step 2: Update the SKILL.md router row**

In `skills/statistics/SKILL.md`, replace the existing `likelihood-model-comparison.md` Leaves-table row with:

```markdown
| [`likelihood-model-comparison.md`](./likelihood-model-comparison.md) | Comparing parametric models by likelihood — AIC/BIC/LRT, nested vs non-nested, numerical precision, bootstrap stability, and Bayesian LOO/ELPD/stacking |
```

- [ ] **Step 3: Insert the Bayesian arm section** immediately before `## Bootstrap Confidence and Selection Stability`:

```markdown
## Bayesian Arm — LOO / ELPD / Stacking

For Bayesian models, prefer out-of-sample predictive comparison over information
criteria computed from a point fit:

- **PSIS-LOO (`elpd_loo`)** estimates expected log predictive density by
  leave-one-out cross-validation using Pareto-smoothed importance sampling — no
  refitting. Report the ELPD difference **and its standard error**; a difference
  smaller than a few SE is not a selection.
- **Prefer LOO over WAIC.** WAIC is an asymptotic approximation to the same
  quantity and is less robust; report WAIC only as a cross-check.
- **Stacking weights** (predictive-distribution averaging) beat picking a single
  winner when several models are close — and are more honest than model-probability
  weights when the true model is not in the set.
- **Reliability guard:** LOO is untrustworthy when the Pareto k̂ for influential
  observations exceeds the library-reported `good_k` threshold — `min(1 − 1/log10(S),
  0.7)` for `S` posterior draws, **not** a fixed 0.7. Report k̂ and the threshold;
  refit-based exact LOO or moment-matching is required for the bad points before
  the comparison stands.
- **Compare genuinely different assumptions, not for variable selection.** LOO
  differences among near-identical nested models are noisy; use it to adjudicate
  substantively different structures.

This arm assumes the models passed the convergence gate in
[`bayesian-workflow.md`](bayesian-workflow.md); an unconverged fit makes ELPD
meaningless.
```

- [ ] **Step 4: Add the cross-ref to Companion Skills**

```markdown
- [`bayesian-workflow.md`](./bayesian-workflow.md) — the convergence gate the Bayesian LOO/ELPD arm assumes.
```

- [ ] **Step 5: Verify lint green**

Run: `cd science && uv run science skills lint --root ../skills`
Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add skills/statistics/likelihood-model-comparison.md skills/statistics/SKILL.md
git commit -m "feat(statistics): add routable Bayesian LOO/ELPD/stacking arm to model comparison"
```

---

### Task 9: Extend `sensitivity-arbitration.md` — power-scaling sensitivity

**Files:**
- Modify: `skills/statistics/sensitivity-arbitration.md`

**Interfaces:** cites `baygent-skills`.

- [ ] **Step 1: Add `sources:` to the frontmatter**

```markdown
---
name: statistics-sensitivity-arbitration
description: Use when an analysis includes multiple robustness checks, alternate operationalisations, filters, covariate sets, priors, models, or negative controls whose results could change interpretation.
sources: [baygent-skills]
---
```

- [ ] **Step 2: Insert a section** immediately before `## Anti-Patterns`:

```markdown
## Power-Scaling Prior/Likelihood Sensitivity (Bayesian)

For a Bayesian primary analysis, make prior sensitivity a *pre-committed*
diagnostic rather than an after-the-fact reassurance:

- **Power-scale** the prior (and, separately, the likelihood) by raising it to a
  power and re-weighting the existing posterior draws via PSIS — **no refit**.
- Quantify the shift with the cumulative Jensen-Shannon (CJS) distance between the
  base and power-scaled posteriors; a common flag is **CJS > 0.05**.
- **Prior-dominated** (prior-scaling moves the posterior, likelihood-scaling does
  not) means the data are not driving the conclusion — a verdict downgrade, decided
  by the arbitration rule above, not chosen after seeing the number.
- Attribute the diagnostic to the arm that produced it, as with any other
  sensitivity (see "Attribute Diagnostics to the Arm That Produced Them").
```

- [ ] **Step 3: Verify lint green**

Run: `cd science && uv run science skills lint --root ../skills`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add skills/statistics/sensitivity-arbitration.md
git commit -m "feat(statistics): add power-scaling prior sensitivity to arbitration leaf"
```

---

### Task 10: Capture toolkit causal gaps (docs only)

**Files:**
- Create: `docs/plans/2026-07-18-causal-tooling-gaps.md`

- [ ] **Step 1: Create the capture doc** — exact content:

```markdown
# Causal tooling gaps — capture (no fixes this session)

Date: 2026-07-18
Status: tracked; not scheduled

Surfaced while pulling baygent causal material and sweeping consumer projects
(multiple-myeloma, post-acute-infection, natural-systems). These keep projects
*outside* the toolkit's causal machinery and cause reinvention.

## Open gaps

1. **pgmpy optional → silent skip (fail-open).** `validate_inquiry`'s
   identifiability / adjustment-set checks `skip` when `pgmpy` is not installed
   (post-acute, MM), contradicting the "a check must be able to fail" doctrine.
   Adjacent: fb-2026-05-24-005.
2. **`inquiry import` status-vocab crash.** Pydantic `ValidationError` on MM's
   inquiry statuses (`active`/`descriptive`/`draft`) vs the toolkit's
   `sketch|specified|…`. MM fb-2026-07-11-031 / -032.
3. **Unpopulated documented edge schema.** The edge `identification:` / `posterior:`
   schema in `references/dag-two-axis-evidence-model.md` has no tooling to populate
   or validate it, so MM hand-transcribes via `_add_identification.py` /
   `_add_posteriors.py`.

## Not a current bug (verified 2026-07-18)

The suspected `export-pgmpy` "empty edge list from a named-graph mismatch" is
**already fixed** in the current toolkit — `causal/export_pgmpy.py` reads the
per-inquiry named graph and unions it with `graph/causal`, covered by
`tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_reads_compiled_patch_inquiry_edges`
(reran green). The post-acute note reflects an **older pinned toolkit**; this is a
downstream pin/upgrade, not an open fix.

## Feature opportunities

- A command to **attach a Bayesian fit result to an inquiry edge** (populate the
  documented `posterior:` block), retiring MM's hand-transcription.
- A **canonical causal-evidence-ledger schema** — three bespoke ones exist across
  MM and post-acute.
```

- [ ] **Step 2: Commit**

```bash
git add docs/plans/2026-07-18-causal-tooling-gaps.md
git commit -m "docs(plans): capture toolkit causal tooling gaps"
```

---

### Task 11: Full validation sweep

**Files:** none (verification + any fixups surfaced).

- [ ] **Step 1: Skills lint (whole tree)**

Run: `cd science && uv run science skills lint --root ../skills`
Expected: exit 0, no output.

- [ ] **Step 2: Source freshness/validity check**

Run: `cd science && uv run science skills sources check --root ../skills`
Expected: exit 0; every seed source `validation=valid`, git-backed `freshness=not_checked`, references `not_applicable`; no unresolved refs.
Run: `cd science && uv run science skills sources list --root ../skills`
Expected: under `By source`, `baygent-skills` lists bayesian-workflow, survival-and-hierarchical-models, likelihood-model-comparison, sensitivity-arbitration, causal-identification.

- [ ] **Step 3: Test suite + lint + types**

Run: `cd science && uv run --frozen pytest -q`
Expected: PASS (no regressions; new `tests/skills_lint/*` green).
Run: `cd science && uv run ruff check`
Expected: clean.
Run: `cd science && uv run pyright`
Expected: no new errors in `skills_lint/`.

- [ ] **Step 4: Handle any failures at their source**

This task is verification-only; it introduces no files of its own. If any of
Steps 1-3 fails, do **not** create a catch-all fixup commit here — return to the
task that owns the failing artifact (e.g. a lint failure on a leaf → the task that
wrote that leaf; a `sources check` failure → Task 3 or Task 4), fix it there, and
re-run this sweep. The sweep passes only when Steps 1-3 are all green with no
uncommitted changes:

```bash
git status --short   # expect: empty
```

---

## Self-Review

**Spec coverage** (each spec section → task):
- §1.1 `sources.yaml` schema (kinds, identifiers, `attribution_notice`, full SHA) + upstream MIT third-party notice → Task 3 (data + `THIRD_PARTY_NOTICES.md`) + Task 1 (semantics).
- §1.2 typed loader / kind-conditional + shape validation / hostname / JSON-safe dates → Task 1.
- §1.3 lint `unknown-source-ref` (vs `declared_ids`) + aggregated `invalid-source-record` → Task 2.
- §1.4 `science skills sources list|check`, three axes, `last_checked` + `citing_leaves`, per-ref `resolved|unresolved`, both list directions, exit code, bounded `git ls-remote` behind a seam + host allowlist → Task 4 (host allowlist enforced in Task 1 loader). Corrupt/file-level registry errors and malformed leaf `sources:` fields both fail the check (not silently clean); invalid records report freshness `unknown` (never the reference-only `not_applicable`); the child process is always reaped without an unbounded `wait()`.
- §2.1 `bayesian-workflow.md` (+ calibration terminology) → Task 5.
- §2.2 `causal-identification.md` (+ four-way non-identification, estimand/applicability guards, export-pgmpy-is-a-script clarification) → Task 7.
- §2.3 routable Bayesian LOO/stacking arm (description + router row) + `good_k` threshold → Task 8.
- §2.4 power-scaling sensitivity → Task 9.
- §2.5 wiring (SKILL.md, INDEX.md, sources.yaml) → Tasks 3, 5, 7, 8.
- Survival de-dup + retro-attribution → Task 6.
- Track 3 capture (+ reframed export-pgmpy) → Task 10.
- Testing/validation → Tasks 1-4 (unit, incl. fetch hardening + JSON contracts for both commands/modes) + Task 11 (sweep).

**Placeholder scan:** no TBD/TODO; all code and leaf content is literal (including the verbatim MIT notice in Task 3 and every leaf body); every command has an expected result; every commit stages explicit paths, never `git add -A`. Task 11 is verification-only and has **no** catch-all fixup commit — failures route back to the owning task, so there is no `git add <files>` placeholder.

**Type consistency:** `SourcesRegistry(.records, .errors: dict, .declared_ids)`, `SourceRecord`, `load_sources`, `leaf_source_refs`, `validate_record` used identically across Tasks 1/2/4; `build_dependency_views(...) -> (by_source, by_leaf, leaf_errors)` unpacked as a 3-tuple by both the `list` command and `check_sources`; `check_sources(root, *, fetch_upstream, fetch=...)`, `SourceStatus(id, validation, freshness, last_checked, citing_leaves, detail)`, `RefStatus(leaf, ref, status)`, `CheckReport(.sources, .refs, .leaf_errors, .failed())`, `fetch_remote_head_sha(url, *, timeout, max_bytes, run)`, `_run_git(args, *, timeout, env, max_bytes)` consistent between Task 4 code and its tests; the `_run_git` fake provides `poll`/`wait`/`kill`/`stdout` matching the runner's calls; source IDs cited in Tasks 5-9 all exist in the Task 3 registry.
