# Bio Identity P4 Assembly Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish P4.1 by making `dataset:assembly-registry` a real pinned commons artifact and proving Science resolves row-bound assembly labels/aliases from that artifact offline.

**Architecture:** `~/d/science` owns the reader contract, identity resolver behavior, and test fixtures. `~/d/science-commons` owns the operator-run recipe and generated CSV/datapackage/entity bytes. Labels and aliases are data-bound to a specific seqcol row; Science never carries a framework-level `hg38 -> GRCh38` synonym map.

**Tech Stack:** Python 3.12, pytest, Ruff, Frictionless-style datapackage YAML, `httpx`, `pyyaml`, GA4GH refget/seqcol via the existing lazy `refget` helper, `rtk` command wrapper.

---

## Preconditions

- Start from a clean `main` in both repos before implementation.
- Create isolated worktrees at execution time with `superpowers:using-git-worktrees`.
- Keep commits split by repo: Science changes commit in `~/d/science`; commons recipe/data changes commit in `~/d/science-commons`.
- Runtime tests must not fetch the network. Network is allowed only for the operator build step in `~/d/science-commons/datasets/assembly-registry/recipe/build.py`.
- Use `~/d/` in docs and comments, not absolute Dropbox paths.

Recommended worktree setup:

```bash
cd ~/d/science
rtk git worktree add .worktrees/bio-identity-p4-assembly-registry -b bio-identity-p4-assembly-registry main

cd ~/d/science-commons
rtk git worktree add .worktrees/bio-identity-p4-assembly-registry -b bio-identity-p4-assembly-registry main
```

Use these roots throughout the plan:

```bash
SCIENCE=~/d/science/.worktrees/bio-identity-p4-assembly-registry
COMMONS=~/d/science-commons/.worktrees/bio-identity-p4-assembly-registry
```

## File Structure

`~/d/science`:

- `science/src/science_tool/commons/assembly.py` - extend the reader contract for `assemblies.csv` to parse row-bound `aliases`, `naming`, and `source_collection_url`; reject duplicate labels/aliases at runtime.
- `science/src/science_tool/commons/assembly_registry_build.py` - extend pure build helpers so the commons recipe can emit the widened artifact contract and validate duplicate row-bound labels/aliases before writing.
- `science/tests/test_commons_assembly.py` - unit tests for alias parsing, duplicate label/alias rejection, and label-vs-alias resolution.
- `science/tests/test_assembly_registry_build.py` - unit tests for widened build rows and duplicate label/alias validation.
- `science/tests/test_identity_resolve.py` - add a real on-disk fixture test proving `resolve_assembly_label()` and `resolve_identity()` use the commons artifact path offline.
- `science/tests/test_commons_contigs.py` - add a fixture-backed smoke test proving contig lookup works through `contigs.csv` and `contig_aliases.csv` copied from the built P4.1 artifact.
- `science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv` - update the small fixture to the widened `assemblies.csv` columns.
- `science/tests/fixtures/commons/assembly-data/assembly-registry/contigs.csv` - copy a small subset from the built commons artifact for the P4.1 smoke fixture.
- `science/tests/fixtures/commons/assembly-data/assembly-registry/contig_aliases.csv` - copy matching aliases from the built commons artifact for the P4.1 smoke fixture.
- `science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml` - update the fixture resource hash/bytes after the fixture CSV changes.
- `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md` - update only after P4.1 lands.

`~/d/science-commons`:

- `datasets/assembly-registry/recipe/sources.yaml` - replace placeholder source entries with pinned rows containing `label`, `aliases`, `naming`, `accession`, `seqcol_digest`, `source_collection_url`, and `assembly_report_url`.
- `datasets/assembly-registry/recipe/build.py` - use the widened Science build helpers, write deterministic CSVs, validate duplicate labels/aliases, and update datapackage/entity metadata.
- `datasets/assembly-registry/assemblies.csv` - generated artifact.
- `datasets/assembly-registry/contigs.csv` - generated artifact.
- `datasets/assembly-registry/contig_aliases.csv` - generated artifact.
- `datasets/assembly-registry/datapackage.yaml` - generated/updated resource hashes and byte counts.
- `datasets/assembly-registry/entity.md` - update `assembly_count`, `updated`, and `version` from the recipe source metadata when bytes change.

## Task 1: Science Reader Supports Row-Bound Aliases

**Files:**
- Modify: `science/src/science_tool/commons/assembly.py`
- Modify: `science/tests/test_commons_assembly.py`
- Modify: `science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv`
- Modify: `science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml`

- [ ] **Step 1: Update the fixture CSV to the widened contract**

Replace `science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv` with:

```csv
seqcol_digest,label,aliases,accession,n_sequences,naming,source_collection_url,source_url
g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp,GRCh38,GRCh38.p14,GCA_000001405.15,455,ncbi,https://seqcolapi.databio.org/collection/g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp,https://seqcolapi.databio.org/collection/g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp
5K4odB173rjao1Cnbk5BnvLt9V7aPAa2,GRCh37,GRCh37.p13,GCA_000001405.14,297,ncbi,https://seqcolapi.databio.org/collection/5K4odB173rjao1Cnbk5BnvLt9V7aPAa2,https://seqcolapi.databio.org/collection/5K4odB173rjao1Cnbk5BnvLt9V7aPAa2
```

- [ ] **Step 2: Update the fixture datapackage hash/bytes**

Run:

```bash
cd "$SCIENCE"
python - <<'PY'
from hashlib import sha256
from pathlib import Path
path = Path("science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv")
data = path.read_bytes()
print(len(data))
print("sha256:" + sha256(data).hexdigest())
PY
```

Update `science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml` so the `assemblies` resource has the printed `bytes` and `hash`. Keep the existing resource name/path/format.

- [ ] **Step 3: Write failing tests for aliases and duplicate labels**

Append these tests to `science/tests/test_commons_assembly.py`:

```python
def test_entry_carries_row_bound_aliases_and_metadata() -> None:
    entry = resolve_assembly("GRCh38.p14", **_kw())

    assert entry == AssemblyEntry(
        seqcol_digest="g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
        label="GRCh38",
        aliases=("GRCh38.p14",),
        accession="GCA_000001405.15",
        n_sequences=455,
        naming="ncbi",
        source_collection_url="https://seqcolapi.databio.org/collection/g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
        source_url="https://seqcolapi.databio.org/collection/g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
    )


def test_parse_rejects_duplicate_label() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    rows = [
        {"seqcol_digest": "D1", "label": "GRCh38", "aliases": "", "accession": ""},
        {"seqcol_digest": "D2", "label": "GRCh38", "aliases": "", "accession": ""},
    ]

    with pytest.raises(AssemblyRegistryError, match="duplicate assembly label"):
        _parse_registry_rows(rows)


def test_parse_rejects_duplicate_alias_across_rows() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    rows = [
        {"seqcol_digest": "D1", "label": "GRCh38", "aliases": "human-current", "accession": ""},
        {"seqcol_digest": "D2", "label": "T2T-CHM13", "aliases": "human-current", "accession": ""},
    ]

    with pytest.raises(AssemblyRegistryError, match="duplicate assembly alias"):
        _parse_registry_rows(rows)


def test_parse_rejects_alias_that_collides_with_another_label() -> None:
    from science_tool.commons.assembly import AssemblyRegistryError, _parse_registry_rows

    rows = [
        {"seqcol_digest": "D1", "label": "GRCh38", "aliases": "human-current", "accession": ""},
        {"seqcol_digest": "D2", "label": "human-current", "aliases": "", "accession": ""},
    ]

    with pytest.raises(AssemblyRegistryError, match="duplicate assembly label or alias"):
        _parse_registry_rows(rows)
```

- [ ] **Step 4: Run the focused tests and verify they fail for the intended reason**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_commons_assembly.py -q
```

Expected: failures mention either `AssemblyEntry.__init__()` missing widened fields, `aliases` not present, or duplicate label/alias checks not raising.

- [ ] **Step 5: Implement the widened reader contract**

In `science/src/science_tool/commons/assembly.py`, replace the `AssemblyEntry` dataclass and add helper functions immediately above `_parse_registry_rows`:

```python
@dataclass(frozen=True, slots=True)
class AssemblyEntry:
    """One registry row: the seqcol digest member key plus row-bound labels."""

    seqcol_digest: str
    label: str
    aliases: tuple[str, ...] = ()
    accession: str = ""
    n_sequences: int | None = None
    naming: str = ""
    source_collection_url: str = ""
    source_url: str = ""


def _optional_clean_text(row: dict[str, Any], column: str) -> str:
    value = row.get(column)
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _parse_aliases(raw: Any, *, row_index: int) -> tuple[str, ...]:
    if raw is None:
        return ()
    text = str(raw).strip()
    if not text:
        return ()
    aliases: list[str] = []
    seen: set[str] = set()
    for alias in text.split("|"):
        cleaned = alias.strip()
        if not cleaned:
            raise AssemblyRegistryError(f"row {row_index}: blank assembly alias in aliases field")
        if cleaned in seen:
            raise AssemblyRegistryError(f"row {row_index}: duplicate assembly alias {cleaned!r}")
        seen.add(cleaned)
        aliases.append(cleaned)
    return tuple(aliases)


def _parse_optional_positive_int(raw: Any, *, row_index: int, column: str) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if not text.isdecimal() or int(text) <= 0:
        raise AssemblyRegistryError(f"row {row_index}: invalid {column} {text!r}")
    return int(text)
```

Then replace `_parse_registry_rows()` with:

```python
def _parse_registry_rows(rows: Iterable[dict[str, Any]]) -> list[AssemblyEntry]:
    """Validate + parse raw CSV rows into entries; fail early on a broken collection."""
    entries: list[AssemblyEntry] = []
    seen_digests: set[str] = set()
    seen_labels: dict[str, tuple[int, str]] = {}
    for i, row in enumerate(rows):
        if "seqcol_digest" not in row:
            raise AssemblyRegistryError(f"row {i}: missing required column 'seqcol_digest'")
        digest = (row.get("seqcol_digest") or "").strip()
        if not digest:
            raise AssemblyRegistryError(f"row {i}: blank seqcol_digest (member key)")
        if digest in seen_digests:
            raise AssemblyRegistryError(f"duplicate member key seqcol_digest={digest!r}")
        seen_digests.add(digest)

        label = _optional_clean_text(row, "label")
        aliases = _parse_aliases(row.get("aliases"), row_index=i)
        if label and label in aliases:
            raise AssemblyRegistryError(f"row {i}: duplicate assembly label or alias {label!r}")
        for token, token_kind in ((label, "label"), *((alias, "alias") for alias in aliases)):
            if not token:
                continue
            if token in seen_labels:
                previous, previous_kind = seen_labels[token]
                if token_kind == "label" and previous_kind == "label":
                    raise AssemblyRegistryError(f"duplicate assembly label {token!r} in rows {previous} and {i}")
                if token_kind == "alias" and previous_kind == "alias":
                    raise AssemblyRegistryError(f"duplicate assembly alias {token!r} in rows {previous} and {i}")
                raise AssemblyRegistryError(f"duplicate assembly label or alias {token!r} in rows {previous} and {i}")
            seen_labels[token] = (i, token_kind)

        entries.append(
            AssemblyEntry(
                seqcol_digest=digest,
                label=label,
                aliases=aliases,
                accession=_optional_clean_text(row, "accession"),
                n_sequences=_parse_optional_positive_int(row.get("n_sequences"), row_index=i, column="n_sequences"),
                naming=_optional_clean_text(row, "naming"),
                source_collection_url=_optional_clean_text(row, "source_collection_url"),
                source_url=_optional_clean_text(row, "source_url"),
            )
        )
    return entries
```

Finally replace the label resolution tail in `resolve_assembly()` with:

```python
    label_matches = [e for e in entries if e.label and e.label == label_or_digest]
    if len(label_matches) == 1:
        return label_matches[0]
    alias_matches = [e for e in entries if label_or_digest in e.aliases]
    return alias_matches[0] if len(alias_matches) == 1 else None
```

- [ ] **Step 6: Run the focused assembly tests**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_commons_assembly.py -q
```

Expected: all tests in `test_commons_assembly.py` pass.

- [ ] **Step 7: Record the identity-resolution error boundary**

Add this paragraph after the runtime parser guarantee in `docs/plans/2026-07-03-bio-identity-p4-assembly-registry-design.md`:

```markdown
At the direct resolver boundary (`load_assembly_registry` / `resolve_assembly`), malformed registry rows raise `AssemblyRegistryError`. At the authoring boundary, `resolve_identity` preserves the P1-P3 graceful-degradation policy: it catches `AssemblyRegistryError`, emits a warning, and returns `resolution_status: declared_unresolved`. Hard prevention of duplicate label/alias artifacts comes from build-time `validate_registry_label_bindings` plus datapackage SHA review; authoring commands do not crash merely because a local commons artifact is corrupt.
```

- [ ] **Step 8: Commit Science reader changes**

Run:

```bash
cd "$SCIENCE"
rtk git status --short
rtk git add science/src/science_tool/commons/assembly.py science/tests/test_commons_assembly.py science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml docs/plans/2026-07-03-bio-identity-p4-assembly-registry-design.md
rtk git commit -m "Support row-bound assembly aliases"
```

## Task 2: Science Build Helpers Emit the Widened Assembly Row

**Files:**
- Modify: `science/src/science_tool/commons/assembly_registry_build.py`
- Modify: `science/tests/test_assembly_registry_build.py`

- [ ] **Step 1: Write failing tests for widened row metadata and duplicate labels**

Add these imports and tests to `science/tests/test_assembly_registry_build.py`:

```python
from science_tool.commons.assembly_registry_build import validate_registry_label_bindings
```

```python
def test_build_row_includes_row_bound_alias_and_source_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        "science_tool.commons.assembly_registry_build.compute_seqcol_digest",
        lambda level2: "DIGEST38",
    )

    row = build_registry_row(
        level2=_L2,
        label="GRCh38",
        aliases=("GRCh38.p14",),
        accession="GCA_000001405.15",
        naming="ncbi",
        server_digest="DIGEST38",
        source_collection_url="https://seqcolapi.databio.org/collection/DIGEST38",
        source_url="https://seqcolapi.databio.org/collection/DIGEST38",
    )

    assert row == {
        "seqcol_digest": "DIGEST38",
        "label": "GRCh38",
        "aliases": "GRCh38.p14",
        "accession": "GCA_000001405.15",
        "n_sequences": 2,
        "naming": "ncbi",
        "source_collection_url": "https://seqcolapi.databio.org/collection/DIGEST38",
        "source_url": "https://seqcolapi.databio.org/collection/DIGEST38",
    }


def test_validate_registry_label_bindings_rejects_duplicate_label_and_alias() -> None:
    with pytest.raises(ValueError, match="duplicate assembly label"):
        validate_registry_label_bindings(
            [
                {"seqcol_digest": "D1", "label": "GRCh38", "aliases": ""},
                {"seqcol_digest": "D2", "label": "GRCh38", "aliases": ""},
            ]
        )

    with pytest.raises(ValueError, match="duplicate assembly alias"):
        validate_registry_label_bindings(
            [
                {"seqcol_digest": "D1", "label": "GRCh38", "aliases": "human-current"},
                {"seqcol_digest": "D2", "label": "T2T-CHM13", "aliases": "human-current"},
            ]
        )


def test_validate_registry_label_bindings_rejects_label_alias_collision() -> None:
    with pytest.raises(ValueError, match="duplicate assembly label or alias"):
        validate_registry_label_bindings(
            [
                {"seqcol_digest": "D1", "label": "GRCh38", "aliases": "human-current"},
                {"seqcol_digest": "D2", "label": "human-current", "aliases": ""},
            ]
        )
```

Update the existing `test_build_row_round_trips_when_digest_matches()` call to pass the new required keyword arguments:

```python
    row = build_registry_row(
        level2=_L2,
        label="TEST",
        aliases=(),
        accession="GCA_TEST.1",
        naming="test",
        server_digest=digest,
        source_collection_url="https://x/collection",
        source_url="https://x",
    )
```

Update the existing `test_build_row_raises_on_digest_mismatch()` call the same way:

```python
        build_registry_row(
            level2=_L2,
            label="TEST",
            aliases=(),
            accession="GCA_TEST.1",
            naming="test",
            server_digest="not-the-real-digest",
            source_collection_url="https://x/collection",
            source_url="https://x",
        )
```

- [ ] **Step 2: Run the focused build-helper tests and verify they fail**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_assembly_registry_build.py -q
```

Expected: failures mention missing `validate_registry_label_bindings` and unexpected `aliases`/`naming` keyword arguments.

- [ ] **Step 3: Implement widened build helpers**

In `science/src/science_tool/commons/assembly_registry_build.py`, add these helpers above `build_registry_row()`:

```python
_ALIAS_SEPARATOR = "|"


def _clean_required_text(value: Any, *, field: str, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label!r}: {field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label!r}: blank {field}")
    if cleaned != value:
        raise ValueError(f"{label!r}: invalid whitespace in {field}={value!r}")
    return cleaned


def _clean_aliases(aliases: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    cleaned_aliases: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        cleaned = _clean_required_text(alias, field="alias", label="assembly")
        if _ALIAS_SEPARATOR in cleaned:
            raise ValueError(f"assembly alias {cleaned!r} contains reserved separator {_ALIAS_SEPARATOR!r}")
        if cleaned in seen:
            raise ValueError(f"duplicate assembly alias {cleaned!r}")
        seen.add(cleaned)
        cleaned_aliases.append(cleaned)
    return tuple(cleaned_aliases)


def validate_registry_label_bindings(rows: list[dict[str, Any]]) -> None:
    """Fail if any label or alias is claimed by more than one assembly row."""
    seen: dict[str, tuple[int, str]] = {}
    for row_index, row in enumerate(rows):
        label = str(row.get("label") or "").strip()
        aliases_raw = str(row.get("aliases") or "").strip()
        aliases = tuple(alias.strip() for alias in aliases_raw.split(_ALIAS_SEPARATOR) if alias.strip())
        for token, token_kind in ((label, "label"), *((alias, "alias") for alias in aliases)):
            if not token:
                continue
            if token in seen:
                previous_index, previous_kind = seen[token]
                if token_kind == "label" and previous_kind == "label":
                    raise ValueError(f"duplicate assembly label {token!r} in rows {previous_index} and {row_index}")
                if token_kind == "alias" and previous_kind == "alias":
                    raise ValueError(f"duplicate assembly alias {token!r} in rows {previous_index} and {row_index}")
                raise ValueError(
                    f"duplicate assembly label or alias {token!r} in rows {previous_index} and {row_index}"
                )
            seen[token] = (row_index, token_kind)
```

Replace `build_registry_row()` with:

```python
def build_registry_row(
    *,
    level2: dict[str, Any],
    label: str,
    aliases: tuple[str, ...] | list[str] = (),
    accession: str,
    naming: str,
    server_digest: str,
    source_collection_url: str,
    source_url: str,
) -> dict[str, Any]:
    """Build one registry row, asserting the recomputed digest matches the server."""
    clean_label = _clean_required_text(label, field="label", label=label)
    clean_accession = _clean_required_text(accession, field="accession", label=clean_label)
    clean_naming = _clean_required_text(naming, field="naming", label=clean_label)
    clean_collection_url = _clean_required_text(
        source_collection_url,
        field="source_collection_url",
        label=clean_label,
    )
    clean_source_url = _clean_required_text(source_url, field="source_url", label=clean_label)
    clean_aliases = _clean_aliases(aliases)
    computed = compute_seqcol_digest(level2)
    if computed != server_digest:
        raise ValueError(f"seqcol digest mismatch for {clean_label!r}: server={server_digest!r} computed={computed!r}")
    return {
        "seqcol_digest": server_digest,
        "label": clean_label,
        "aliases": _ALIAS_SEPARATOR.join(clean_aliases),
        "accession": clean_accession,
        "n_sequences": len(level2["names"]),
        "naming": clean_naming,
        "source_collection_url": clean_collection_url,
        "source_url": clean_source_url,
    }
```

- [ ] **Step 4: Run the focused build-helper tests**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_assembly_registry_build.py -q
```

Expected: all tests in `test_assembly_registry_build.py` pass.

- [ ] **Step 5: Run the focused Science commons tests**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_commons_assembly.py science/tests/test_assembly_registry_build.py -q
```

Expected: both test files pass.

- [ ] **Step 6: Commit Science build-helper changes**

Run:

```bash
cd "$SCIENCE"
rtk git add science/src/science_tool/commons/assembly_registry_build.py science/tests/test_assembly_registry_build.py
rtk git commit -m "Emit widened assembly registry rows"
```

## Task 3: Science Identity Resolver Uses the On-Disk Fixture Offline

**Files:**
- Modify: `science/tests/test_identity_resolve.py`

- [ ] **Step 1: Update existing `AssemblyEntry` test doubles**

In `science/tests/test_identity_resolve.py`, replace both fake `AssemblyEntry(...)` calls with:

```python
        return AssemblyEntry(
            seqcol_digest=_HG38_DIGEST,
            label="hg38",
            aliases=(),
            accession="GCF_000001405.40",
            n_sequences=455,
            naming="ucsc",
            source_collection_url="https://seqcolapi.databio.org/collection/g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
            source_url="https://seqcolapi.databio.org/collection/g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
        )
```

- [ ] **Step 2: Add a real fixture-backed identity resolver test**

Add these imports near the top of `science/tests/test_identity_resolve.py`:

```python
from pathlib import Path
```

Add these constants after `_AVAILABLE_GENE_REGISTRY`:

```python
_FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_ASSEMBLY_COMMONS = _FIXTURES / "assembly"
_ASSEMBLY_DATA = _FIXTURES / "assembly-data"
```

Add this test:

```python
def test_identity_resolver_reads_on_disk_assembly_registry_without_network(monkeypatch) -> None:
    def fail_socket(*args, **kwargs):
        raise AssertionError("runtime identity resolution must not open network sockets")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert (
        resolve_assembly_label(
            "GRCh38",
            ASSEMBLY_REGISTRY_ID,
            commons_root=_ASSEMBLY_COMMONS,
            data_root=_ASSEMBLY_DATA,
        )
        == _HG38_DIGEST
    )

    resolved = resolve_identity(
        {
            "taxon": 9606,
            "assembly": {
                "label": "GRCh38.p14",
                "registry": ASSEMBLY_REGISTRY_ID,
            },
        },
        registries=_AVAILABLE_GENE_REGISTRY,
        commons_root=_ASSEMBLY_COMMONS,
        data_root=_ASSEMBLY_DATA,
    )

    assert resolved.identity_context["assembly"] == {
        "label": "GRCh38.p14",
        "registry": ASSEMBLY_REGISTRY_ID,
        "seqcol_digest": _HG38_DIGEST,
        "resolution_status": "resolved",
    }
    assert resolved.messages == ()
```

- [ ] **Step 3: Run the identity tests**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_identity_resolve.py -q
```

Expected: the file passes, and the new identity test passes without monkeypatching `science_tool.commons.assembly.resolve_assembly`.

- [ ] **Step 4: Commit Science identity integration tests**

Run:

```bash
cd "$SCIENCE"
rtk git add science/tests/test_identity_resolve.py
rtk git commit -m "Test offline assembly identity resolution"
```

## Task 4: Commons Recipe Writes Widened Deterministic Artifacts

**Files:**
- Modify in `~/d/science-commons`: `datasets/assembly-registry/recipe/build.py`
- Modify in `~/d/science-commons`: `datasets/assembly-registry/recipe/sources.yaml`

- [ ] **Step 1: Replace `sources.yaml` with concrete source fields**

In `~/d/science-commons/datasets/assembly-registry/recipe/sources.yaml`, replace the placeholder structure with this concrete schema. Keep `seqcol_digest` values as operator-pinned source data discovered in Step 2; do not guess them from labels.

```yaml
# Pinned seqcol collection digests, fetched + verified no-FASTA at build time.
# Labels and aliases are row-bound to the exact seqcol digest in the same row.
artifact_version: "1.0.1"
seqcol_base_url: https://seqcolapi.databio.org
assemblies:
  - label: GRCh38
    aliases:
      - GRCh38.p14
    naming: ncbi
    accession: GCA_000001405.15
    seqcol_digest: "__OPERATOR_PINNED_GRCh38_SEQCOL_DIGEST__"
    source_collection_url: "__OPERATOR_PINNED_GRCh38_SOURCE_COLLECTION_URL__"
    assembly_report_url: https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/GCA_000001405.15_GRCh38_assembly_report.txt
  - label: GRCh37
    aliases:
      - GRCh37.p13
    naming: ncbi
    accession: GCA_000001405.14
    seqcol_digest: "__OPERATOR_PINNED_GRCh37_SEQCOL_DIGEST__"
    source_collection_url: "__OPERATOR_PINNED_GRCh37_SOURCE_COLLECTION_URL__"
    assembly_report_url: https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.14_GRCh37.p13/GCA_000001405.14_GRCh37.p13_assembly_report.txt
```

The sentinel strings are intentionally invalid. The recipe in this task must reject any `seqcol_digest` or `source_collection_url` beginning with `__OPERATOR_PINNED_`.

- [ ] **Step 2: Discover and pin seqcol source rows with auditable commands**

Run these commands from the commons worktree. They write inspection data outside the repo so the committed artifact contains only curated source rows and generated CSVs:

```bash
cd "$COMMONS"
mkdir -p /tmp/science-assembly-registry
rtk curl -sS https://seqcolapi.databio.org/list/collection > /tmp/science-assembly-registry/seqcol-collections.json
python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/science-assembly-registry/seqcol-collections.json").read_text())
Path("/tmp/science-assembly-registry/candidate-digests.txt").write_text(
    "\n".join(payload["results"]) + "\n",
    encoding="utf-8",
)
print(f"wrote {len(payload['results'])} candidate digests")
PY
```

For each candidate digest, inspect the level-2 names and sequences:

```bash
cd "$COMMONS"
while read -r DIGEST; do
  rtk curl -sS "https://seqcolapi.databio.org/collection/${DIGEST}?level=2" > "/tmp/science-assembly-registry/${DIGEST}.level2.json"
done < /tmp/science-assembly-registry/candidate-digests.txt
python - <<'PY'
import json
from pathlib import Path
for path in sorted(Path("/tmp/science-assembly-registry").glob("*.level2.json")):
    payload = json.loads(path.read_text())
    names = payload.get("names") or []
    seqs = payload.get("sequences") or []
    print(path.name.removesuffix(".level2.json"), len(names), names[:5], names[-5:], seqs[:2], seqs[-2:])
PY
```

Select GRCh38 and GRCh37 rows only when the inspected `names` and assembly report match the intended `naming: ncbi` row. If exact UCSC `hg38` or `hg19` collections are found, add additional rows with `label: hg38` or `label: hg19`, `naming: ucsc`, and no alias that points at a GRCh row.

- [ ] **Step 3: Write failing commons recipe tests by running the recipe with sentinels**

Run:

```bash
cd "$COMMONS/datasets/assembly-registry"
uv run --with refget --with httpx --with pyyaml --with ~/d/science/.worktrees/bio-identity-p4-assembly-registry python recipe/build.py
```

Expected before implementation: either the old recipe ignores the sentinel-specific validation or fails with an unclear network/digest error. After implementation, the failure must be a `ValueError` that names the invalid sentinel field.

- [ ] **Step 4: Replace recipe field constants and add metadata helpers**

In `~/d/science-commons/datasets/assembly-registry/recipe/build.py`, replace the field constants with:

```python
_ASSEMBLY_FIELDS = [
    "seqcol_digest",
    "label",
    "aliases",
    "accession",
    "n_sequences",
    "naming",
    "source_collection_url",
    "source_url",
]
_CONTIG_FIELDS = ["seqcol_digest", "sequence_index", "name", "refget_digest", "length"]
_ALIAS_FIELDS = ["seqcol_digest", "refget_digest", "alias", "alias_kind", "sequence_accession"]
```

Add these imports:

```python
import hashlib
from datetime import UTC, datetime
```

Add these helper functions below `_write_csv()`:

```python
def _require_text(src: dict[str, Any], key: str, *, label: str) -> str:
    value = src.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{label}: {key} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label}: blank {key}")
    if cleaned.startswith("__OPERATOR_PINNED_"):
        raise ValueError(f"{label}: {key} still contains operator-pinning sentinel {cleaned!r}")
    return cleaned


def _aliases(src: dict[str, Any], *, label: str) -> tuple[str, ...]:
    raw = src.get("aliases", [])
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"{label}: aliases must be a list")
    aliases: list[str] = []
    seen: set[str] = set()
    for alias in raw:
        if not isinstance(alias, str) or not alias.strip():
            raise ValueError(f"{label}: aliases must be non-blank strings")
        cleaned = alias.strip()
        if cleaned in seen:
            raise ValueError(f"{label}: duplicate alias {cleaned!r}")
        seen.add(cleaned)
        aliases.append(cleaned)
    return tuple(aliases)


def _sha256_resource(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest(), len(data)


def _update_datapackage(path: Path, *, version: str) -> None:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["version"] = version
    by_path = {resource["path"]: resource for resource in doc["resources"]}
    for resource_path in ("assemblies.csv", "contigs.csv", "contig_aliases.csv"):
        digest, byte_count = _sha256_resource(_OUT / resource_path)
        by_path[resource_path]["hash"] = digest
        by_path[resource_path]["bytes"] = byte_count
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _replace_frontmatter_value(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[index] = f"{key}: {value}"
            return "\n".join(lines) + "\n"
    raise ValueError(f"entity.md missing frontmatter key {key!r}")


def _update_entity(path: Path, *, assembly_count: int, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    today = datetime.now(UTC).date().isoformat()
    text = _replace_frontmatter_value(text, "version", f'"{version}"')
    text = _replace_frontmatter_value(text, "updated", f'"{today}"')
    text = _replace_frontmatter_value(text, "assembly_count", str(assembly_count))
    path.write_text(text, encoding="utf-8")
```

- [ ] **Step 5: Replace the recipe `main()` with widened build logic**

Replace `main()` with:

```python
def main() -> None:
    sources = yaml.safe_load((_HERE / "sources.yaml").read_text(encoding="utf-8"))
    if not isinstance(sources, dict):
        raise ValueError("sources.yaml must contain a mapping")
    seqcol_base_url = sources.get("seqcol_base_url", "https://seqcolapi.databio.org")
    if not isinstance(seqcol_base_url, str) or not seqcol_base_url.strip():
        raise ValueError("sources.yaml seqcol_base_url must be a non-blank string")
    artifact_version = sources.get("artifact_version")
    if not isinstance(artifact_version, str) or not artifact_version.strip():
        raise ValueError("sources.yaml artifact_version must be a non-blank string")
    source_rows = sources.get("assemblies")
    if not isinstance(source_rows, list) or not source_rows:
        raise ValueError("sources.yaml assemblies must be a non-empty list")

    assembly_rows: list[dict[str, Any]] = []
    contig_rows: list[dict[str, Any]] = []
    alias_rows: list[dict[str, Any]] = []

    for src in source_rows:
        if not isinstance(src, dict):
            raise ValueError("each assembly source must be a mapping")
        label = _require_text(src, "label", label="assembly source")
        seqcol_digest = _require_text(src, "seqcol_digest", label=label)
        source_collection_url = _require_text(src, "source_collection_url", label=label)
        assembly_report_url = _require_text(src, "assembly_report_url", label=label)
        level2 = fetch_seqcol_level2(seqcol_digest, base_url=seqcol_base_url)
        assembly_rows.append(
            build_registry_row(
                level2=level2,
                label=label,
                aliases=_aliases(src, label=label),
                accession=_require_text(src, "accession", label=label),
                naming=_require_text(src, "naming", label=label),
                server_digest=seqcol_digest,
                source_collection_url=source_collection_url,
                source_url=source_collection_url,
            )
        )
        assembly_contigs = build_contig_rows(level2=level2, seqcol_digest=seqcol_digest)
        contig_rows.extend(assembly_contigs)
        report_rows = parse_assembly_report(fetch_text(assembly_report_url))
        alias_rows.extend(build_contig_alias_rows(contig_rows=assembly_contigs, report_rows=report_rows))

    validate_registry_label_bindings(assembly_rows)
    assembly_rows.sort(key=lambda row: row["label"])
    contig_rows.sort(key=lambda row: (row["seqcol_digest"], int(row["sequence_index"])))
    alias_rows.sort(key=lambda row: (row["seqcol_digest"], row["refget_digest"], row["alias_kind"], row["alias"]))

    _write_csv(_OUT / "assemblies.csv", _ASSEMBLY_FIELDS, assembly_rows)
    _write_csv(_OUT / "contigs.csv", _CONTIG_FIELDS, contig_rows)
    _write_csv(_OUT / "contig_aliases.csv", _ALIAS_FIELDS, alias_rows)
    _update_datapackage(_OUT / "datapackage.yaml", version=artifact_version)
    _update_entity(_OUT / "entity.md", assembly_count=len(assembly_rows), version=artifact_version)
    print(f"wrote {len(assembly_rows)} assemblies, {len(contig_rows)} contigs, {len(alias_rows)} aliases to {_OUT}")
```

Also add `validate_registry_label_bindings` to the existing import from `science_tool.commons.assembly_registry_build`.

- [ ] **Step 6: Run the recipe with sentinel values and verify it fails early**

Run:

```bash
cd "$COMMONS/datasets/assembly-registry"
uv run --with refget --with httpx --with pyyaml --with ~/d/science/.worktrees/bio-identity-p4-assembly-registry python recipe/build.py
```

Expected: failure includes `still contains operator-pinning sentinel`.

- [ ] **Step 7: Commit the recipe contract before generated bytes**

Run:

```bash
cd "$COMMONS"
rtk git add datasets/assembly-registry/recipe/build.py datasets/assembly-registry/recipe/sources.yaml
rtk git commit -m "Wire assembly registry recipe contract"
```

## Task 5: Build and Commit the Commons Assembly Registry Artifact

**Files:**
- Modify in `~/d/science-commons`: `datasets/assembly-registry/recipe/sources.yaml`
- Modify in `~/d/science-commons`: `datasets/assembly-registry/assemblies.csv`
- Modify in `~/d/science-commons`: `datasets/assembly-registry/contigs.csv`
- Modify in `~/d/science-commons`: `datasets/assembly-registry/contig_aliases.csv`
- Modify in `~/d/science-commons`: `datasets/assembly-registry/datapackage.yaml`
- Modify in `~/d/science-commons`: `datasets/assembly-registry/entity.md`

- [ ] **Step 1: Replace source sentinels with audited seqcol pins**

Edit `~/d/science-commons/datasets/assembly-registry/recipe/sources.yaml` so each row has a real `seqcol_digest` and `source_collection_url`.

Run this check after editing so the row shape is pinned and auditable:

```bash
cd "$COMMONS/datasets/assembly-registry"
python - <<'PY'
from pathlib import Path
import yaml

sources = yaml.safe_load(Path("recipe/sources.yaml").read_text())
assert sources["artifact_version"] == "1.0.1"
rows = sources["assemblies"]
by_label = {row["label"]: row for row in rows}
assert {"GRCh38", "GRCh37"} <= set(by_label)

grch38 = by_label["GRCh38"]
assert grch38["aliases"] == ["GRCh38.p14"]
assert grch38["naming"] == "ncbi"
assert grch38["accession"] == "GCA_000001405.15"
assert grch38["assembly_report_url"] == "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/GCA_000001405.15_GRCh38_assembly_report.txt"

grch37 = by_label["GRCh37"]
assert grch37["aliases"] == ["GRCh37.p13"]
assert grch37["naming"] == "ncbi"
assert grch37["accession"] == "GCA_000001405.14"
assert grch37["assembly_report_url"] == "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.14_GRCh37.p13/GCA_000001405.14_GRCh37.p13_assembly_report.txt"

for label, row in by_label.items():
    digest = row["seqcol_digest"]
    source_url = row["source_collection_url"]
    assert isinstance(digest, str) and digest and not digest.startswith("__OPERATOR_PINNED_"), label
    assert source_url == f"https://seqcolapi.databio.org/collection/{digest}", label

print("sources.yaml pins are shaped correctly")
PY
```

Do not add `hg38` or `hg19` aliases to either row. Add `hg38`/`hg19` only as separate rows if exact UCSC-named seqcol collections were independently audited.

- [ ] **Step 2: Run the operator build**

Run:

```bash
cd "$COMMONS/datasets/assembly-registry"
uv run --with refget --with httpx --with pyyaml --with ~/d/science/.worktrees/bio-identity-p4-assembly-registry python recipe/build.py
```

Expected: prints `wrote 2 assemblies, ...` unless exact UCSC rows were intentionally added. The command writes all three CSVs and updates `datapackage.yaml` plus `entity.md`.

- [ ] **Step 3: Verify generated resource metadata matches file bytes**

Run:

```bash
cd "$COMMONS/datasets/assembly-registry"
python - <<'PY'
from hashlib import sha256
from pathlib import Path
import yaml
dp = yaml.safe_load(Path("datapackage.yaml").read_text())
assert dp["version"] == "1.0.1"
for resource in dp["resources"]:
    path = Path(resource["path"])
    data = path.read_bytes()
    actual_hash = "sha256:" + sha256(data).hexdigest()
    actual_bytes = len(data)
    assert resource["hash"] == actual_hash, (resource["path"], resource["hash"], actual_hash)
    assert resource["bytes"] == actual_bytes, (resource["path"], resource["bytes"], actual_bytes)
    print(resource["path"], actual_bytes, actual_hash)
PY
```

Expected: prints one line each for `assemblies.csv`, `contigs.csv`, and `contig_aliases.csv`; no assertion failures.

- [ ] **Step 4: Verify no global alias conflation was introduced**

Run:

```bash
cd "$COMMONS/datasets/assembly-registry"
python - <<'PY'
import csv
rows = list(csv.DictReader(open("assemblies.csv", encoding="utf-8", newline="")))
for row in rows:
    aliases = [a for a in row.get("aliases", "").split("|") if a]
    print(row["label"], row["naming"], row["seqcol_digest"], aliases)
    if row["label"] == "GRCh38":
        assert "hg38" not in aliases
    if row["label"] == "GRCh37":
        assert "hg19" not in aliases
PY
```

Expected: GRCh rows do not list UCSC labels as aliases.

- [ ] **Step 5: Validate commons dataset if the repo has a validation command**

Run:

```bash
cd "$COMMONS"
uv run --with ~/d/science/.worktrees/bio-identity-p4-assembly-registry science validate datasets/assembly-registry
```

Expected: pass. If this repo does not expose `science validate` with this invocation, record the exact command failure in the task notes and rely on Step 3 plus Science fixture verification in Task 6.

- [ ] **Step 6: Commit the generated commons artifact**

Run:

```bash
cd "$COMMONS"
rtk git status --short
rtk git add datasets/assembly-registry/recipe/sources.yaml datasets/assembly-registry/assemblies.csv datasets/assembly-registry/contigs.csv datasets/assembly-registry/contig_aliases.csv datasets/assembly-registry/datapackage.yaml datasets/assembly-registry/entity.md
rtk git commit -m "Build pinned assembly registry artifact"
```

## Task 6: Science Fixture Tracks the Built Artifact Contract

**Files:**
- Modify: `science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv`
- Modify: `science/tests/fixtures/commons/assembly-data/assembly-registry/contigs.csv`
- Modify: `science/tests/fixtures/commons/assembly-data/assembly-registry/contig_aliases.csv`
- Modify: `science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml`
- Modify: `science/tests/test_commons_assembly.py`
- Modify: `science/tests/test_identity_resolve.py`
- Modify: `science/tests/test_commons_contigs.py`

- [ ] **Step 1: Copy the built assembly rows and a small built contig subset**

From the Science worktree, run:

```bash
cd "$SCIENCE"
rtk cp "$COMMONS/datasets/assembly-registry/assemblies.csv" science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv
python - "$COMMONS" <<'PY'
import csv
from pathlib import Path
import sys

commons = Path(sys.argv[1]) / "datasets" / "assembly-registry"
fixture = Path("science/tests/fixtures/commons/assembly-data/assembly-registry")

assemblies = list(csv.DictReader((fixture / "assemblies.csv").open(encoding="utf-8", newline="")))
grch38 = next(row for row in assemblies if row["label"] == "GRCh38")
seqcol_digest = grch38["seqcol_digest"]

contigs = [
    row
    for row in csv.DictReader((commons / "contigs.csv").open(encoding="utf-8", newline=""))
    if row["seqcol_digest"] == seqcol_digest and row["name"] == "1"
]
if len(contigs) != 1:
    raise SystemExit(f"expected one GRCh38 contig named '1', got {len(contigs)}")
contig = contigs[0]

aliases = [
    row
    for row in csv.DictReader((commons / "contig_aliases.csv").open(encoding="utf-8", newline=""))
    if row["seqcol_digest"] == seqcol_digest and row["refget_digest"] == contig["refget_digest"]
]
if not any(row["alias"] == "chr1" and row["alias_kind"] == "ucsc" for row in aliases):
    raise SystemExit("expected copied GRCh38 contig alias chr1/ucsc")

with (fixture / "contigs.csv").open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=["seqcol_digest", "sequence_index", "name", "refget_digest", "length"])
    writer.writeheader()
    writer.writerow(contig)

with (fixture / "contig_aliases.csv").open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(
        fh,
        fieldnames=["seqcol_digest", "refget_digest", "alias", "alias_kind", "sequence_accession"],
    )
    writer.writeheader()
    writer.writerows(aliases)
PY
```

If the built artifact contains more than GRCh38 and GRCh37, keep the fixture small by deleting extra rows manually unless a test in this task covers the extra row.

- [ ] **Step 2: Update the fixture datapackage resources and hashes**

Replace `science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml` with the same resource shape used by the real commons artifact, but keep the fixture metadata minimal:

```yaml
name: assembly-registry
profile: data-package
resources:
  - name: assemblies
    path: assemblies.csv
    format: csv
    mediatype: text/csv
    hash: "sha256:REPLACE"
    bytes: 0
  - name: contigs
    path: contigs.csv
    format: csv
    mediatype: text/csv
    hash: "sha256:REPLACE"
    bytes: 0
  - name: contig_aliases
    path: contig_aliases.csv
    format: csv
    mediatype: text/csv
    hash: "sha256:REPLACE"
    bytes: 0
```

Then run this script and write the printed `hash`/`bytes` values into the matching resources:

```bash
cd "$SCIENCE"
python - <<'PY'
from hashlib import sha256
from pathlib import Path
root = Path("science/tests/fixtures/commons/assembly-data/assembly-registry")
for name in ("assemblies.csv", "contigs.csv", "contig_aliases.csv"):
    data = (root / name).read_bytes()
    print(name, len(data), "sha256:" + sha256(data).hexdigest())
PY
```

- [ ] **Step 3: Update expected fixture values in tests**

Read the copied fixture:

```bash
cd "$SCIENCE"
python - <<'PY'
import csv
from pathlib import Path
rows = list(csv.DictReader(Path("science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv").open()))
for row in rows:
    print(row["label"], row["seqcol_digest"], row["aliases"], row["n_sequences"], row["naming"])
PY
```

Update these test constants and assertions to match the printed GRCh38 row:

Set `_HG38_DIGEST` in `science/tests/test_identity_resolve.py` to the exact GRCh38 `seqcol_digest` printed by the command above. In `science/tests/test_commons_assembly.py`, reconcile the full expected `AssemblyEntry` in `test_entry_carries_row_bound_aliases_and_metadata()` against the printed built row: `seqcol_digest`, `aliases`, `accession`, `n_sequences`, `naming`, `source_collection_url`, and `source_url`. Also update the expected digest strings in `test_available_keys_are_the_seqcol_digests()` and `test_resolve_by_exact_digest()` to the printed GRCh38 and GRCh37 values.

- [ ] **Step 4: Add a built-artifact contig smoke test**

Add these imports to `science/tests/test_commons_contigs.py`:

```python
import csv
```

Add these constants after `_FIXTURES`:

```python
_BUILT_COMMONS = _FIXTURES / "assembly"
_BUILT_DATA = _FIXTURES / "assembly-data"
```

Append this test to `science/tests/test_commons_contigs.py`:

```python
def test_built_assembly_registry_fixture_resolves_copied_contig_alias() -> None:
    fixture_root = _BUILT_DATA / "assembly-registry"
    with (fixture_root / "assemblies.csv").open(encoding="utf-8", newline="") as fh:
        grch38 = next(row for row in csv.DictReader(fh) if row["label"] == "GRCh38")
    with (fixture_root / "contigs.csv").open(encoding="utf-8", newline="") as fh:
        contig = next(row for row in csv.DictReader(fh) if row["seqcol_digest"] == grch38["seqcol_digest"])

    match = resolve_contig(
        "chr1",
        seqcol_digest=grch38["seqcol_digest"],
        commons_root=_BUILT_COMMONS,
        data_root=_BUILT_DATA,
    )

    assert isinstance(match, ContigMatch)
    assert match.refget_digest == contig["refget_digest"]
    assert match.name == contig["name"]
    assert match.alias_kind == "ucsc"
```

- [ ] **Step 5: Run Science resolver and contig tests against the built artifact fixture**

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_commons_assembly.py science/tests/test_identity_resolve.py science/tests/test_commons_contigs.py -q
```

Expected: all three files pass. The new contig smoke test must use `_BUILT_COMMONS` and `_BUILT_DATA`, not the old `assembly-c4a` fixture returned by `_kw()`.

- [ ] **Step 6: Commit fixture synchronization**

Run:

```bash
cd "$SCIENCE"
rtk git add science/tests/fixtures/commons/assembly-data/assembly-registry/assemblies.csv science/tests/fixtures/commons/assembly-data/assembly-registry/contigs.csv science/tests/fixtures/commons/assembly-data/assembly-registry/contig_aliases.csv science/tests/fixtures/commons/assembly/datasets/assembly-registry/datapackage.yaml science/tests/test_commons_assembly.py science/tests/test_identity_resolve.py science/tests/test_commons_contigs.py
rtk git commit -m "Sync assembly resolver fixture with built artifact"
```

## Task 7: Update the Umbrella and Run Full Verification

**Files:**
- Modify: `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`

- [ ] **Step 1: Update the umbrella progress ledger**

In `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`, change P4.1 in the P4 work package list from active work to landed work. Add a progress ledger entry:

```markdown
- 2026-07-03: P4.1 assembly-registry landed. `science-commons` now has a pinned `dataset:assembly-registry` artifact with row-bound assembly labels/aliases, deterministic `assemblies.csv`/`contigs.csv`/`contig_aliases.csv`, and updated datapackage hashes; Science resolver tests exercise the on-disk artifact offline.
```

Also update the `Next:` line from:

```markdown
- Next: P4.1 assembly-registry build entrypoint + resolver integration fixture.
```

to:

```markdown
- Next: P4.2 gene-crosswalk-hgnc build entrypoint.
```

- [ ] **Step 2: Run focused Science verification**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_commons_assembly.py science/tests/test_assembly_registry_build.py science/tests/test_identity_resolve.py science/tests/test_commons_contigs.py -q
```

Expected: all focused tests pass.

- [ ] **Step 3: Run broader Science verification**

Run:

```bash
cd "$SCIENCE"
uv run --frozen pytest science/tests/test_commons_assembly.py science/tests/test_assembly_registry_build.py science/tests/test_commons_assembly_report_build.py science/tests/test_commons_contigs.py science/tests/test_identity_resolve.py -q
uv run --frozen ruff check science/src/science_tool/commons/assembly.py science/src/science_tool/commons/assembly_registry_build.py science/tests/test_commons_assembly.py science/tests/test_assembly_registry_build.py science/tests/test_identity_resolve.py science/tests/test_commons_contigs.py
```

Expected: pytest passes; Ruff reports no issues.

- [ ] **Step 4: Run commons artifact verification**

Run:

```bash
cd "$COMMONS/datasets/assembly-registry"
python - <<'PY'
from hashlib import sha256
from pathlib import Path
import csv
import yaml

dp = yaml.safe_load(Path("datapackage.yaml").read_text())
assert dp["version"] == "1.0.1"
for resource in dp["resources"]:
    path = Path(resource["path"])
    data = path.read_bytes()
    assert resource["hash"] == "sha256:" + sha256(data).hexdigest()
    assert resource["bytes"] == len(data)

assemblies = list(csv.DictReader(Path("assemblies.csv").open(encoding="utf-8", newline="")))
assert len(assemblies) >= 2
labels = {row["label"] for row in assemblies}
assert {"GRCh38", "GRCh37"} <= labels
claimed = {}
for i, row in enumerate(assemblies):
    tokens = [row["label"], *[a for a in row["aliases"].split("|") if a]]
    for token in tokens:
        assert token not in claimed, (token, claimed[token], i)
        claimed[token] = i
print("assembly-registry artifact verification passed")
PY
```

Expected: prints `assembly-registry artifact verification passed`.

- [ ] **Step 5: Commit umbrella update in Science**

Run:

```bash
cd "$SCIENCE"
rtk git add docs/plans/2026-07-03-bio-identity-adoption-umbrella.md
rtk git commit -m "Record assembly registry P4 progress"
```

## Task 8: Final Cross-Repo Status Report

**Files:**
- No file changes.

- [ ] **Step 1: Check Science status and log**

Run:

```bash
cd "$SCIENCE"
rtk git status --short
rtk git log --oneline -6
```

Expected: clean status; recent commits include:

```text
Record assembly registry P4 progress
Sync assembly resolver fixture with built artifact
Test offline assembly identity resolution
Emit widened assembly registry rows
Support row-bound assembly aliases
```

- [ ] **Step 2: Check commons status and log**

Run:

```bash
cd "$COMMONS"
rtk git status --short
rtk git log --oneline -4
```

Expected: clean status; recent commits include:

```text
Build pinned assembly registry artifact
Wire assembly registry recipe contract
```

- [ ] **Step 3: Prepare completion notes**

Report:

- Science commit range.
- Commons commit range.
- Exact GRCh38 and GRCh37 seqcol digests pinned in `datasets/assembly-registry/recipe/sources.yaml`.
- Whether exact UCSC `hg38`/`hg19` rows were found and included.
- Verification commands and pass/fail results.
- Any skipped validation command and the exact reason it was skipped.

## Self-Review

Spec coverage:

- Row-bound labels/aliases are implemented in Tasks 1, 2, 4, and 5.
- Runtime duplicate label/alias rejection is implemented in Task 1.
- Build-time duplicate label/alias rejection is implemented in Tasks 2 and 4.
- Widened artifact columns are implemented in Tasks 2, 4, 5, and 6.
- Source provenance and naming are implemented in Tasks 4 and 5.
- Datapackage hash/bytes and entity metadata updates are implemented in Tasks 4 and 5.
- Offline resolver integration is implemented in Tasks 3 and 6.
- Contig smoke coverage is implemented in Task 3 and verified in Task 7.
- Umbrella progress tracking is implemented in Task 7.
- Cross-repo commit separation is enforced by the preconditions and Tasks 4-8.

Placeholder scan:

- The only sentinel strings are in Task 4 by design and are explicitly rejected by the recipe before artifact generation.
- Task 5 requires replacing those sentinels with audited seqcol pins discovered from the source server and verified by recomputation.
- No implementation task contains open-ended “handle errors” language without concrete checks.

Type consistency:

- `AssemblyEntry.aliases` is a `tuple[str, ...]` in Science reader tests and fake resolver entries.
- `build_registry_row(... aliases=...)` accepts `tuple[str, ...] | list[str]` and emits a pipe-delimited CSV string.
- `resolve_assembly()` continues returning `AssemblyEntry | None`.
- `validate_registry_label_bindings()` operates on row dicts and is shared by the commons recipe.
