# Content-Addressed Datapackage Resources with Pluggable Sources — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a commons dataset declare resources whose bytes live off-repo (bulk storage now; remote commons later) so `science commons promote dataset` records each resource's location + checksum without co-locating or streaming the bytes — trusting the build-stamped digest by default, re-verifying only under an opt-in `--verify-digests` flag.

**Architecture:** A resource gains an optional typed `source` descriptor; its *presence* flips the resource from "co-located, promote streams it to compute the digest" to "content-addressed, the digest is build-stamped and the bytes may live anywhere." `(hash, bytes)` is the canonical identity. The default promote path does no local I/O for sourced resources; `--verify-digests` resolves a `local` ref on this host and asserts the digest, reporting a per-resource verdict (`verified` / `skipped_off_host` / `skipped_remote`) that flows back to the CLI through a small result object so a skip is never silent.

**Tech Stack:** Python 3.11+ (`requires-python >=3.11`), the existing `science_tool.commons` promote / datapackage layer, frictionless-style datapackage descriptors, pytest. Tests run from `~/d/science/science` with `uv run --frozen pytest`.

**Design doc:** `~/d/science/docs/plans/historical/2026-05-29-external-datapackage-resources-design.md`

---

## File Structure

All production code lives under `~/d/science/science/src/science_tool/commons/`; tests under `~/d/science/science/tests/`.

- **`datapackage.py`** — descriptor layer. Gains: `ResourceSource` value type, the `SOURCE_TYPES` enum + `OUTPUT_ROOT_TOKEN` constant, `validate_source()` (shape validation, raises `ValueError`), the sealed `RefResolution` / `Unexpandable` / `Resolved` types and `resolve_local_ref()`, `source` parsing in `parse_canonical_datapackage_yaml` and `read_datapackage`, the `source` field on `DataResource`. Render already passes `source` through verbatim (it is not a computed key) — Task 3 only adds a regression test for that.
- **`errors.py`** — gains `PromoteResourceDigestMismatchError`.
- **`promote.py`** — gains `ResourceVerification` + `PerResourceResult`, a source-aware `_dataset_per_resource` (default trust; co-located stream unchanged) returning `PerResourceResult`, a source-aware `_validate_datapackage_resources` (skip the filesystem existence check for sourced resources), `validate_logical_path` on every resource `path`, the `verify_digests` keyword threaded through `plan_promote` and `_validate_dataset_group_datapackages`, and a `resource_verifications` channel on `PromotePlan`.
- **`cli.py`** — gains the `--verify-digests` flag on `promote dataset`, threads `verify_digests` through `_promote_kind_cmd` → `plan_promote`, and prints the per-resource verify summary.
- **`inventory.py`** — adds `source` to the serialized per-resource dict so the inventory is not lossy for sourced resources.

**Out of scope (downstream / non-goals):** producer-side stamping (mm30's `build_data_package.py`), remote fetching for `zenodo`/`github`/`url`/`daemon` (recorded + shape-validated only), and `resolver.py` / `science commons data resolve` (unchanged this iteration).

---

## Task 1: `ResourceSource` value type + `validate_source`

**Files:**
- Modify: `science/src/science_tool/commons/datapackage.py`
- Test: `science/tests/test_commons_datapackage_source.py` (create)

The `source` descriptor and its shape validation. `validate_source` raises a plain `ValueError` (mirroring `parse_resource_hash`) so each caller — `read_datapackage` (→ `CommonsDatapackageError`), `parse_canonical_datapackage_yaml` (→ `CommonsError`), and `_dataset_per_resource` (→ `PromoteCandidateError`) — wraps it into its own error type.

**Allowed `ref` shapes this iteration:**

| `type` | `ref` |
| --- | --- |
| `local` | absolute path, exactly `${OUTPUT_ROOT}`, or `${OUTPUT_ROOT}/...` |
| `url` | absolute `http://` or `https://` URL |
| `zenodo` / `github` / `daemon` | any non-empty, non-whitespace string |

Rejected for `local`: empty/whitespace, a plain relative path, any `${...}` token other than `${OUTPUT_ROOT}`, and `${OUTPUT_ROOT}foo` (token not followed by `/` or end-of-string).

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_commons_datapackage_source.py`:

```python
"""Tests for the datapackage `source` descriptor (ResourceSource + validate_source)."""
from __future__ import annotations

import pytest

from science_tool.commons.datapackage import (
    OUTPUT_ROOT_TOKEN,
    SOURCE_TYPES,
    ResourceSource,
    validate_source,
)


def test_source_types_enum():
    assert SOURCE_TYPES == frozenset({"local", "zenodo", "github", "url", "daemon"})
    assert OUTPUT_ROOT_TOKEN == "${OUTPUT_ROOT}"


@pytest.mark.parametrize(
    "ref",
    [
        "/data/proj/mm30/8.0/scrna/walker2024.h5ad",  # absolute
        "${OUTPUT_ROOT}",                              # bare token
        "${OUTPUT_ROOT}/scrna/walker2024.h5ad",        # token + subpath
    ],
)
def test_validate_source_accepts_local_ref(ref):
    src = validate_source({"type": "local", "ref": ref})
    assert src == ResourceSource(type="local", ref=ref)


@pytest.mark.parametrize(
    "ref",
    [
        "scrna/walker2024.h5ad",        # plain relative
        "",                             # empty
        "   ",                          # whitespace
        "${OUTPUT_ROOT}foo",            # token not followed by '/' or end
        "${SCRATCH}/x.h5ad",            # a different token
        "${OUTPUT_ROOT/x",              # syntactically broken token
    ],
)
def test_validate_source_rejects_bad_local_ref(ref):
    with pytest.raises(ValueError):
        validate_source({"type": "local", "ref": ref})


def test_validate_source_accepts_url():
    src = validate_source({"type": "url", "ref": "https://example.org/x.h5ad"})
    assert src.type == "url"


@pytest.mark.parametrize(
    "ref",
    [
        "ftp://example.org/x",  # wrong scheme
        "example.org/x",        # no scheme
        "",                     # empty
        "https://",             # scheme but no host
        "https:///x.h5ad",      # scheme + path but empty host
    ],
)
def test_validate_source_rejects_bad_url(ref):
    with pytest.raises(ValueError):
        validate_source({"type": "url", "ref": ref})


@pytest.mark.parametrize("type_", ["zenodo", "github", "daemon"])
def test_validate_source_accepts_opaque_remote(type_):
    src = validate_source({"type": type_, "ref": "10.5281/zenodo.123"})
    assert src.type == type_ and src.ref == "10.5281/zenodo.123"


@pytest.mark.parametrize("type_", ["zenodo", "github", "daemon"])
def test_validate_source_rejects_blank_opaque_remote(type_):
    with pytest.raises(ValueError):
        validate_source({"type": type_, "ref": "   "})


def test_validate_source_rejects_unknown_type():
    with pytest.raises(ValueError, match="type"):
        validate_source({"type": "s3", "ref": "/x"})


def test_validate_source_rejects_non_mapping():
    with pytest.raises(ValueError):
        validate_source("local")


def test_validate_source_rejects_missing_or_nonstring_ref():
    with pytest.raises(ValueError):
        validate_source({"type": "local"})
    with pytest.raises(ValueError):
        validate_source({"type": "local", "ref": 123})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_datapackage_source.py -q`
Expected: FAIL — `ImportError: cannot import name 'ResourceSource'`.

- [ ] **Step 3: Implement `ResourceSource` + `validate_source`**

In `science/src/science_tool/commons/datapackage.py`, first add `import urllib.parse` to the imports at the top (next to `import re`, line 10). Then add near the top-level constants (after line 25, the `_RESOURCE_COMPUTED_KEYS` definition):

```python
SOURCE_TYPES = frozenset({"local", "zenodo", "github", "url", "daemon"})
OUTPUT_ROOT_TOKEN = "${OUTPUT_ROOT}"
```

Add the value type next to `DataResource` (after the `DataResource` class, ~line 263):

```python
@dataclass(frozen=True, slots=True)
class ResourceSource:
    """An off-repo origin for a content-addressed resource.

    `type` is one of SOURCE_TYPES; `ref` is the type-specific locator (a
    filesystem path or `${OUTPUT_ROOT}` token for `local`, an http(s) URL for
    `url`, an opaque non-empty string for the remote kinds).
    """

    type: str
    ref: str
```

Add the validator (place it after `parse_resource_hash`, ~line 85):

```python
def validate_source(raw: object) -> ResourceSource:
    """Validate a resource `source` mapping and return a `ResourceSource`.

    Raises `ValueError` on any unsafe/malformed form. Callers wrap this into
    their own error type. Only `local` and `url` refs are shape-checked beyond
    "non-empty string"; the other remote kinds are opaque this iteration.
    """
    if not isinstance(raw, dict):
        raise ValueError("source must be a mapping with 'type' and 'ref'")
    type_ = raw.get("type")
    if type_ not in SOURCE_TYPES:
        raise ValueError(
            f"source.type {type_!r} is not one of {sorted(SOURCE_TYPES)}"
        )
    ref = raw.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError(f"source.ref must be a non-empty string, got {ref!r}")

    if type_ == "local":
        _validate_local_ref_shape(ref)
    elif type_ == "url":
        parsed = urllib.parse.urlparse(ref)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                f"url source.ref must be an absolute http(s) URL with a host, got {ref!r}"
            )
    # zenodo / github / daemon: opaque non-empty string (already checked).
    return ResourceSource(type=type_, ref=ref)


def _validate_local_ref_shape(ref: str) -> None:
    """Allow only: an absolute path, exactly `${OUTPUT_ROOT}`, or `${OUTPUT_ROOT}/...`."""
    if ref == OUTPUT_ROOT_TOKEN or ref.startswith(OUTPUT_ROOT_TOKEN + "/"):
        return
    if "${" in ref:
        raise ValueError(
            f"local source.ref {ref!r} uses an unsupported or malformed token; "
            f"only {OUTPUT_ROOT_TOKEN} (bare or followed by '/') is allowed"
        )
    if not PurePosixPath(ref).is_absolute():
        raise ValueError(
            f"local source.ref {ref!r} must be absolute or use the "
            f"{OUTPUT_ROOT_TOKEN} token; a plain relative path is ambiguous"
        )
```

(`PurePosixPath` is already imported at line 12.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_datapackage_source.py -q`
Expected: PASS (all parametrized cases).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/datapackage.py science/tests/test_commons_datapackage_source.py
git commit -m "feat(commons): add ResourceSource type and source shape validation"
```

---

## Task 2: `RefResolution` + `resolve_local_ref`

**Files:**
- Modify: `science/src/science_tool/commons/datapackage.py`
- Test: `science/tests/test_commons_datapackage_source.py` (extend)

A single, sealed result type so promote can distinguish "off-host skip" from "resolved-but-missing error" without a `Path | None` overload. `resolve_local_ref` handles `local` refs only (the only resolvable type this iteration); promote maps remote `type`s straight to `skipped_remote` without calling a resolver.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_datapackage_source.py`:

```python
from pathlib import Path

from science_tool.commons.datapackage import (
    Resolved,
    Unexpandable,
    resolve_local_ref,
)


def test_resolve_absolute_ref_existing(tmp_path, monkeypatch):
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    f = tmp_path / "x.h5ad"
    f.write_bytes(b"abc")
    res = resolve_local_ref(str(f))
    assert isinstance(res, Resolved)
    assert res.path == f and res.exists is True


def test_resolve_absolute_ref_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    res = resolve_local_ref(str(tmp_path / "nope.h5ad"))
    assert isinstance(res, Resolved) and res.exists is False


def test_resolve_token_unexpandable_when_env_unset(monkeypatch):
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    assert isinstance(resolve_local_ref("${OUTPUT_ROOT}/scrna/x.h5ad"), Unexpandable)


def test_resolve_token_expands_against_env(tmp_path, monkeypatch):
    (tmp_path / "scrna").mkdir()
    f = tmp_path / "scrna" / "x.h5ad"
    f.write_bytes(b"abc")
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    res = resolve_local_ref("${OUTPUT_ROOT}/scrna/x.h5ad")
    assert isinstance(res, Resolved) and res.path == f and res.exists is True


def test_resolve_bare_token_expands_to_root(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    res = resolve_local_ref("${OUTPUT_ROOT}")
    assert isinstance(res, Resolved) and res.path == tmp_path


def test_resolve_raises_when_output_root_blank(monkeypatch):
    monkeypatch.setenv("OUTPUT_ROOT", "   ")
    with pytest.raises(ValueError, match="OUTPUT_ROOT"):
        resolve_local_ref("${OUTPUT_ROOT}/x.h5ad")


def test_resolve_raises_when_output_root_relative(monkeypatch):
    monkeypatch.setenv("OUTPUT_ROOT", "relative/dir")
    with pytest.raises(ValueError, match="OUTPUT_ROOT"):
        resolve_local_ref("${OUTPUT_ROOT}/x.h5ad")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_datapackage_source.py -q`
Expected: FAIL — `ImportError: cannot import name 'Resolved'`.

- [ ] **Step 3: Implement `RefResolution` + `resolve_local_ref`**

Add to `science/src/science_tool/commons/datapackage.py`. First extend the imports at the top — line 10 `import re` already exists; add `import os` near it. Then add the types and function (after `_validate_local_ref_shape`):

```python
class RefResolution:
    """Sealed result of resolving a `local` source ref on this host."""


@dataclass(frozen=True, slots=True)
class Unexpandable(RefResolution):
    """The ref carries the `${OUTPUT_ROOT}` token but OUTPUT_ROOT is unset.

    Reported as `skipped_off_host` by promote — non-fatal.
    """

    ref: str


@dataclass(frozen=True, slots=True)
class Resolved(RefResolution):
    """The ref resolved to a concrete local path (which may or may not exist)."""

    path: Path
    exists: bool


def resolve_local_ref(ref: str) -> RefResolution:
    """Resolve a validated `local` source ref against this host.

    - absolute ref → `Resolved(path, exists)`.
    - `${OUTPUT_ROOT}`-token ref, OUTPUT_ROOT unset → `Unexpandable` (off-host).
    - `${OUTPUT_ROOT}`-token ref, OUTPUT_ROOT set to an absolute path →
      `Resolved(expanded_path, exists)`.

    Raises `ValueError` only on a configuration error that blocks resolution:
    OUTPUT_ROOT set but blank or relative. (Malformed refs are already rejected
    by `validate_source`; this function assumes a validated ref.)
    """
    if ref == OUTPUT_ROOT_TOKEN or ref.startswith(OUTPUT_ROOT_TOKEN + "/"):
        root = os.environ.get("OUTPUT_ROOT")
        if root is None:
            return Unexpandable(ref=ref)
        if not root.strip() or not Path(root).is_absolute():
            raise ValueError(
                f"OUTPUT_ROOT must be a non-blank absolute path to expand {ref!r}; "
                f"got {root!r}"
            )
        suffix = ref[len(OUTPUT_ROOT_TOKEN) :].lstrip("/")
        path = Path(root) / suffix if suffix else Path(root)
        return Resolved(path=path, exists=path.exists())
    # validate_source guarantees the only remaining shape is an absolute path.
    path = Path(ref)
    return Resolved(path=path, exists=path.exists())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_datapackage_source.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/datapackage.py science/tests/test_commons_datapackage_source.py
git commit -m "feat(commons): add resolve_local_ref with sealed RefResolution"
```

---

## Task 3: parse / read / render round-trip of `source`

**Files:**
- Modify: `science/src/science_tool/commons/datapackage.py`
- Test: `science/tests/test_commons_datapackage_source.py` (extend)

`read_datapackage` and `parse_canonical_datapackage_yaml` must parse + validate `source` when present and surface it on `DataResource`. `render_canonical_datapackage_yaml` already copies every non-computed key (so `source` passes through verbatim) — Task 3 adds a regression test pinning that, plus the read-side parsing.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_datapackage_source.py`:

```python
import textwrap

from science_tool.commons.datapackage import (
    parse_canonical_datapackage_yaml,
    read_datapackage,
    render_canonical_datapackage_yaml,
)
from science_tool.commons.errors import CommonsDatapackageError, CommonsError

VALID_HASH = "sha256:" + "a" * 64


def _write_dp(tmp_path, body: str):
    p = tmp_path / "datapackage.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_read_datapackage_surfaces_source(tmp_path):
    p = _write_dp(
        tmp_path,
        f"""\
        name: ds
        resources:
          - name: walker
            path: walker2024.h5ad
            hash: {VALID_HASH}
            bytes: 14010935296
            source:
              type: local
              ref: ${{OUTPUT_ROOT}}/scrna/walker2024.h5ad
        """,
    )
    desc = read_datapackage(p)
    src = desc.resources[0].source
    assert src is not None
    assert src.type == "local"
    assert src.ref == "${OUTPUT_ROOT}/scrna/walker2024.h5ad"


def test_read_datapackage_source_absent_is_none(tmp_path):
    p = _write_dp(
        tmp_path,
        f"""\
        name: ds
        resources:
          - name: r1
            path: r1.txt
            hash: {VALID_HASH}
            bytes: 12
        """,
    )
    assert read_datapackage(p).resources[0].source is None


def test_read_datapackage_rejects_bad_source(tmp_path):
    p = _write_dp(
        tmp_path,
        f"""\
        name: ds
        resources:
          - name: r1
            path: r1.txt
            hash: {VALID_HASH}
            bytes: 12
            source:
              type: local
              ref: relative/path.h5ad
        """,
    )
    with pytest.raises(CommonsDatapackageError, match="source"):
        read_datapackage(p)


def test_parse_canonical_validates_source(tmp_path):
    text = textwrap.dedent(
        f"""\
        name: ds
        resources:
          - name: r1
            path: r1.txt
            hash: {VALID_HASH}
            bytes: 12
            source:
              type: bogus
              ref: x
        """
    )
    with pytest.raises(CommonsError, match="source"):
        parse_canonical_datapackage_yaml(text)


def test_render_preserves_source_verbatim():
    project_doc = {
        "name": "ds",
        "resources": [
            {
                "name": "walker",
                "path": "walker2024.h5ad",
                "source": {
                    "type": "local",
                    "ref": "${OUTPUT_ROOT}/scrna/walker2024.h5ad",
                },
            }
        ],
    }
    rendered = render_canonical_datapackage_yaml(
        project_doc=project_doc,
        canonical_slug="ds",
        per_resource={"walker": (VALID_HASH, 14010935296)},
    )
    parsed = parse_canonical_datapackage_yaml(rendered)
    r = parsed["resources"][0]
    assert r["source"] == {"type": "local", "ref": "${OUTPUT_ROOT}/scrna/walker2024.h5ad"}
    assert r["hash"] == VALID_HASH and r["bytes"] == 14010935296
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_datapackage_source.py -k "source or render" -q`
Expected: FAIL — `read_datapackage` returns a `DataResource` with no `source` attribute; `parse_canonical_datapackage_yaml` does not validate `source`.

- [ ] **Step 3a: Add `source` to `DataResource`**

In `science/src/science_tool/commons/datapackage.py`, extend the `DataResource` dataclass (~line 253):

```python
@dataclass(frozen=True, slots=True)
class DataResource:
    """One resource entry from a datapackage.yaml."""

    path: str  # validated forward-slash relative logical path
    hash: str  # full "sha256:<hex>" string, verbatim from resources[].hash
    name: str | None = None  # resources[].name if present
    bytes: int | None = None  # resources[].bytes if present
    format: str | None = None  # resources[].format if present
    mediatype: str | None = None  # resources[].mediatype if present
    source: ResourceSource | None = None  # resources[].source if present
```

- [ ] **Step 3b: Parse `source` in `read_datapackage`**

In `read_datapackage`, just before the `resources.append(DataResource(...))` call (~line 399), parse the source:

```python
        raw_source = entry.get("source")
        source = None
        if raw_source is not None:
            try:
                source = validate_source(raw_source)
            except ValueError as exc:
                raise CommonsDatapackageError(
                    path,
                    reason=f"resources[{index}] ({logical_path}) has an invalid source: {exc}",
                ) from exc
```

Then pass `source=source` into the `DataResource(...)` constructor.

- [ ] **Step 3c: Validate `source` in `parse_canonical_datapackage_yaml`**

In `parse_canonical_datapackage_yaml`, inside the resource loop, after the `bytes` check (~line 248), add:

```python
        raw_source = entry.get("source")
        if raw_source is not None:
            try:
                validate_source(raw_source)
            except ValueError as exc:
                raise CommonsError(
                    f"resources[{index}] ({logical_path}) has an invalid source: {exc}"
                ) from exc
```

(`render_canonical_datapackage_yaml` needs no change — `source` is not in `_RESOURCE_COMPUTED_KEYS`, so it is copied verbatim.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_datapackage_source.py -q`
Expected: PASS.

- [ ] **Step 5: Run the existing datapackage suite for regressions**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_datapackage.py tests/test_commons_promote_dataset_plan.py -q`
Expected: PASS (no regressions in existing parse/render/read behavior).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/datapackage.py science/tests/test_commons_datapackage_source.py
git commit -m "feat(commons): parse and surface resource source on read; validate on canonical parse"
```

---

## Task 4: `PromoteResourceDigestMismatchError`

**Files:**
- Modify: `science/src/science_tool/commons/errors.py`
- Test: `science/tests/test_commons_promote_source.py` (create)

The hard-error type raised under `--verify-digests` when a resolved local file's digest does not match the build-stamped `(hash, bytes)`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_promote_source.py`:

```python
"""Tests for source-aware promote: default trust, --verify-digests, validation."""
from __future__ import annotations

import pytest


def test_digest_mismatch_error_names_resource_and_values():
    from science_tool.commons.errors import (
        CommonsError,
        PromoteResourceDigestMismatchError,
    )

    err = PromoteResourceDigestMismatchError(
        slug="walker",
        resource_name="walker-h5ad",
        expected=("sha256:" + "a" * 64, 10),
        actual=("sha256:" + "b" * 64, 11),
        path=None,
    )
    assert isinstance(err, CommonsError)
    assert err.slug == "walker"
    assert err.resource_name == "walker-h5ad"
    assert "walker-h5ad" in str(err)
    assert ("sha256:" + "a" * 64) in str(err)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py -q`
Expected: FAIL — `ImportError: cannot import name 'PromoteResourceDigestMismatchError'`.

- [ ] **Step 3: Implement the error**

In `science/src/science_tool/commons/errors.py`, add after `PromoteResourceMissingError` (~line 229):

```python
class PromoteResourceDigestMismatchError(CommonsError):
    """A sourced resource's local bytes do not match its build-stamped digest.

    Raised only under `--verify-digests`, when a `local` ref resolves to an
    existing file whose `(sha256, bytes)` differs from the stamped values.
    Hard error — aborts the promote.
    """

    def __init__(
        self,
        *,
        slug: str,
        resource_name: str,
        expected: tuple[str, int],
        actual: tuple[str, int],
        path: "Path | None",
    ) -> None:
        self.slug = slug
        self.resource_name = resource_name
        self.expected = expected
        self.actual = actual
        self.path = path
        super().__init__(
            f"dataset {slug!r}: resource {resource_name!r} digest mismatch at "
            f"{path}: expected {expected}, got {actual}"
        )
```

(`Path` is already imported at the top of `errors.py`, line 5.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/errors.py science/tests/test_commons_promote_source.py
git commit -m "feat(commons): add PromoteResourceDigestMismatchError"
```

---

## Task 5: source-aware `_dataset_per_resource` with `PerResourceResult`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Test: `science/tests/test_commons_promote_source.py` (extend)

The core change. `_dataset_per_resource` becomes source-aware and returns a `PerResourceResult` (`.per_resource` for rendering, unchanged payload; `.verifications` for the CLI). Default path trusts the stamped `(hash, bytes)` with **no local I/O** for sourced resources. `--verify-digests` resolves `local` refs and produces a verdict. Co-located resources stream exactly as before. `validate_logical_path` runs on every resource `path`.

The function builds a `PromoteCandidate` directly in tests, so the test constructs one with a `datapackage_doc` (the parsed JSON dict) and a `datapackage_source_path`.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_source.py`:

```python
from pathlib import Path

VALID_HASH = "sha256:" + "a" * 64


def _candidate(tmp_path, resources, project_slug="mm"):
    """Build a minimal dataset PromoteCandidate with the given resources list."""
    from science_tool.commons.promote import PromoteCandidate

    tmp_path.mkdir(parents=True, exist_ok=True)
    dp_path = tmp_path / "datapackage.json"
    dp_path.write_text("{}", encoding="utf-8")  # bytes unused; doc passed directly
    return PromoteCandidate(
        slug="walker",
        slug_normalized="walker",
        project_slug=project_slug,
        project_root=tmp_path,
        overlay_source_path=tmp_path / "doc" / "data-walker.md",
        canonical_fields={},
        project_only_fields={},
        canonical_body={},
        project_only_body={},
        datapackage_source_path=dp_path,
        datapackage_doc={"name": "walker", "resources": resources},
    )


def _sourced(ref="${OUTPUT_ROOT}/scrna/walker2024.h5ad", *, hash_=VALID_HASH, bytes_=14010935296):
    return {
        "name": "walker-h5ad",
        "path": "walker2024.h5ad",
        "hash": hash_,
        "bytes": bytes_,
        "source": {"type": "local", "ref": ref},
    }


def test_default_trusts_sourced_resource_without_io(tmp_path, monkeypatch):
    from science_tool.commons import promote

    called = []
    monkeypatch.setattr(
        promote, "stream_sha256_and_bytes",
        lambda p: called.append(p) or ("sha256:" + "f" * 64, 1),
    )
    cand = _candidate(tmp_path, [_sourced()])
    result = promote._dataset_per_resource(cand)
    assert called == []  # NO byte I/O for a sourced resource
    assert result.per_resource == {"walker-h5ad": (VALID_HASH, 14010935296)}
    assert result.verifications == ()


def test_sourced_missing_hash_is_hard_error(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    res = _sourced()
    del res["hash"]
    with pytest.raises(PromoteCandidateError, match="hash"):
        promote._dataset_per_resource(_candidate(tmp_path, [res]))


@pytest.mark.parametrize("bad", ["sha256:zzz", "md5:" + "a" * 32, "nope"])
def test_sourced_invalid_hash_is_hard_error(tmp_path, bad):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    with pytest.raises(PromoteCandidateError, match="hash"):
        promote._dataset_per_resource(_candidate(tmp_path, [_sourced(hash_=bad)]))


@pytest.mark.parametrize("bad", [-1, True, "12", 1.5])
def test_sourced_invalid_bytes_is_hard_error(tmp_path, bad):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    with pytest.raises(PromoteCandidateError, match="bytes"):
        promote._dataset_per_resource(_candidate(tmp_path, [_sourced(bytes_=bad)]))


def test_bad_source_type_is_hard_error(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    res = _sourced()
    res["source"] = {"type": "s3", "ref": "/x"}
    with pytest.raises(PromoteCandidateError, match="source"):
        promote._dataset_per_resource(_candidate(tmp_path, [res]))


def test_path_failing_logical_validation_rejected(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    res = _sourced()
    res["path"] = "../escape.h5ad"
    with pytest.raises(PromoteCandidateError, match="path"):
        promote._dataset_per_resource(_candidate(tmp_path, [res]))


def test_verify_passes_when_local_file_matches(tmp_path, monkeypatch):
    from science_tool.commons import promote
    from science_tool.commons.datapackage import stream_sha256_and_bytes

    (tmp_path / "scrna").mkdir()
    f = tmp_path / "scrna" / "walker2024.h5ad"
    f.write_bytes(b"hello world!")
    real_hash, real_bytes = stream_sha256_and_bytes(f)
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    cand = _candidate(tmp_path, [_sourced(hash_=real_hash, bytes_=real_bytes)])
    result = promote._dataset_per_resource(cand, verify_digests=True)
    assert [v.status for v in result.verifications] == ["verified"]


def test_verify_raises_on_drift(tmp_path, monkeypatch):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteResourceDigestMismatchError

    (tmp_path / "scrna").mkdir()
    (tmp_path / "scrna" / "walker2024.h5ad").write_bytes(b"different bytes")
    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))
    cand = _candidate(tmp_path, [_sourced()])  # stamped hash is all-'a', won't match
    with pytest.raises(PromoteResourceDigestMismatchError):
        promote._dataset_per_resource(cand, verify_digests=True)


def test_verify_hard_errors_when_resolved_but_missing(tmp_path, monkeypatch):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    monkeypatch.setenv("OUTPUT_ROOT", str(tmp_path))  # file never created
    cand = _candidate(tmp_path, [_sourced()])
    with pytest.raises(PromoteCandidateError, match="missing"):
        promote._dataset_per_resource(cand, verify_digests=True)


def test_verify_skips_off_host_when_token_unexpandable(tmp_path, monkeypatch):
    from science_tool.commons import promote

    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    cand = _candidate(tmp_path, [_sourced()])
    result = promote._dataset_per_resource(cand, verify_digests=True)
    assert [v.status for v in result.verifications] == ["skipped_off_host"]


def test_verify_skips_remote_type(tmp_path):
    from science_tool.commons import promote

    res = _sourced()
    res["source"] = {"type": "zenodo", "ref": "10.5281/zenodo.123"}
    cand = _candidate(tmp_path, [res])
    result = promote._dataset_per_resource(cand, verify_digests=True)
    assert [v.status for v in result.verifications] == ["skipped_remote"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py -q`
Expected: FAIL — `_dataset_per_resource` returns a bare dict and is not source-aware.

- [ ] **Step 3a: Add the result types + imports**

In `science/src/science_tool/commons/promote.py`, extend the `datapackage` import (find the existing `from science_tool.commons.datapackage import ...` block — it already imports `render_canonical_datapackage_yaml` and `stream_sha256_and_bytes`) to also import:

```python
    Resolved,
    Unexpandable,
    parse_resource_hash,
    resolve_local_ref,
    validate_logical_path,
    validate_source,
```

Extend the `errors` import to add `PromoteResourceDigestMismatchError` and `DataLogicalPathError`.

Add the result types near `PromotePlan` (after line 435):

```python
@dataclass(frozen=True, slots=True)
class ResourceVerification:
    """One sourced resource's --verify-digests verdict (non-fatal outcomes only).

    `project_slug` disambiguates the same resource `name` appearing in more than
    one project of a multi-project dataset group.
    """

    project_slug: str
    name: str
    status: Literal["verified", "skipped_off_host", "skipped_remote"]
    detail: str


@dataclass(frozen=True, slots=True)
class PerResourceResult:
    """Return type of `_dataset_per_resource`.

    `per_resource` is the unchanged {alias: (hash, bytes)} payload used by
    rendering; `verifications` is empty unless `--verify-digests` is set.
    """

    per_resource: dict[str, tuple[str, int]]
    verifications: tuple[ResourceVerification, ...] = ()
```

(`Literal` is already imported in `promote.py`; if not, add `from typing import Literal`.)

- [ ] **Step 3b: Rewrite `_dataset_per_resource`**

Replace the body of `_dataset_per_resource` (lines 2379–2421) with:

```python
def _dataset_per_resource(
    candidate: PromoteCandidate, *, verify_digests: bool = False
) -> PerResourceResult:
    if candidate.datapackage_source_path is None or candidate.datapackage_doc is None:
        raise PromoteCandidateError(
            "dataset planning requires discovery datapackage metadata",
            slug=candidate.slug,
        )

    per_resource: dict[str, tuple[str, int]] = {}
    verifications: list[ResourceVerification] = []
    dp_parent = candidate.datapackage_source_path.parent
    resources = candidate.datapackage_doc.get("resources")
    if not isinstance(resources, list):
        raise PromoteCandidateError(
            "dataset datapackage resources must be a list",
            slug=candidate.slug,
        )
    for idx, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            raise PromoteCandidateError(
                f"datapackage resources[{idx}] must be an object",
                slug=candidate.slug,
            )
        resource_path = resource.get("path")
        if not isinstance(resource_path, str) or not resource_path.strip():
            raise PromoteCandidateError(
                f"datapackage resources[{idx}].path must be a non-empty string",
                slug=candidate.slug,
            )
        try:
            validate_logical_path(resource_path)
        except DataLogicalPathError as exc:
            raise PromoteCandidateError(
                f"datapackage resources[{idx}].path is invalid: {exc.reason}",
                slug=candidate.slug,
            ) from exc
        name = _resource_name(resource, resource_path)

        raw_source = resource.get("source")
        if raw_source is None:
            # Co-located resource: resolve under the datapackage dir and stream.
            resource_abs = _datapackage_relative_path(
                dp_parent,
                resource_path,
                field=f"datapackage resources[{idx}].path",
            )
            try:
                per_resource[name] = stream_sha256_and_bytes(resource_abs)
            except OSError as exc:
                raise PromoteCandidateError(
                    f"cannot read datapackage resources[{idx}] bytes: {exc}",
                    slug=candidate.slug,
                    path=resource_abs,
                ) from exc
            continue

        # Sourced resource: trust the build-stamped (hash, bytes); no local I/O
        # in the default path.
        try:
            source = validate_source(raw_source)
        except ValueError as exc:
            raise PromoteCandidateError(
                f"datapackage resources[{idx}] has an invalid source: {exc}",
                slug=candidate.slug,
            ) from exc
        stamped = _stamped_metadata(resource, idx, candidate.slug)
        per_resource[name] = stamped
        if verify_digests:
            verifications.append(
                _verify_sourced_resource(
                    candidate.project_slug, name, source, stamped, candidate.slug
                )
            )

    return PerResourceResult(
        per_resource=per_resource, verifications=tuple(verifications)
    )


def _stamped_metadata(
    resource: Mapping[str, Any], idx: int, slug: str
) -> tuple[str, int]:
    """Validate and return the build-stamped (hash, bytes) of a sourced resource."""
    raw_hash = resource.get("hash")
    if not isinstance(raw_hash, str):
        raise PromoteCandidateError(
            f"sourced datapackage resources[{idx}] has a missing or non-string 'hash'",
            slug=slug,
        )
    try:
        parse_resource_hash(raw_hash)
    except ValueError as exc:
        raise PromoteCandidateError(
            f"sourced datapackage resources[{idx}] has an invalid 'hash': {exc}",
            slug=slug,
        ) from exc
    raw_bytes = resource.get("bytes")
    if (
        not isinstance(raw_bytes, int)
        or isinstance(raw_bytes, bool)
        or raw_bytes < 0
    ):
        raise PromoteCandidateError(
            f"sourced datapackage resources[{idx}] has a missing or invalid 'bytes'",
            slug=slug,
        )
    return raw_hash, raw_bytes


def _verify_sourced_resource(
    project_slug: str,
    name: str,
    source: "ResourceSource",
    stamped: tuple[str, int],
    slug: str,
) -> ResourceVerification:
    """Resolve a sourced resource on this host and return its verify verdict.

    Raises on a hard error (digest drift, or a ref that resolves but is missing).
    """
    if source.type != "local":
        return ResourceVerification(
            project_slug=project_slug,
            name=name,
            status="skipped_remote",
            detail=f"{source.type}: no fetcher this iteration",
        )
    try:
        resolution = resolve_local_ref(source.ref)
    except ValueError as exc:
        raise PromoteCandidateError(
            f"cannot verify sourced resource {name!r}: {exc}",
            slug=slug,
        ) from exc
    if isinstance(resolution, Unexpandable):
        return ResourceVerification(
            project_slug=project_slug,
            name=name,
            status="skipped_off_host",
            detail=resolution.ref,
        )
    assert isinstance(resolution, Resolved)
    if not resolution.exists:
        raise PromoteCandidateError(
            f"sourced resource {name!r} ref resolves to a missing file: "
            f"{resolution.path}",
            slug=slug,
            path=resolution.path,
        )
    actual = stream_sha256_and_bytes(resolution.path)
    if actual != stamped:
        raise PromoteResourceDigestMismatchError(
            slug=slug,
            resource_name=name,
            expected=stamped,
            actual=actual,
            path=resolution.path,
        )
    return ResourceVerification(
        project_slug=project_slug,
        name=name,
        status="verified",
        detail=f"{actual[0]} ({actual[1]} bytes)",
    )
```

(`ResourceSource` is the type imported from `datapackage`; add it to the import block if pyright complains. `Mapping` and `Any` are already imported in `promote.py`.)

- [ ] **Step 3c: Fix the two existing call sites to use `.per_resource`**

At line ~725 (inside `plan_promote`):

```python
            dataset_primary = _primary_candidate_for_plan(classified, from_order)
            _primary_result = _dataset_per_resource(dataset_primary)
            dataset_primary_per_resource = _primary_result.per_resource
```

(The `verify_digests` threading is added in Task 7; for now keep the default call so this task compiles and existing tests pass.)

At line ~2446 (inside `_validate_dataset_group_datapackages`):

```python
        candidate_per_resource = _dataset_per_resource(candidate).per_resource
```

- [ ] **Step 4: Run the new tests + the existing dataset suite**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py tests/test_commons_promote_dataset_plan.py tests/test_commons_promote_dataset_discovery.py tests/test_commons_promote_dataset_integration.py -q`
Expected: PASS (new source tests green; existing co-located dataset tests unaffected because `.per_resource` matches the old dict).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_source.py
git commit -m "feat(commons): source-aware _dataset_per_resource with default trust and --verify path"
```

---

## Task 6: source-aware discovery validation (`_validate_datapackage_resources`)

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Test: `science/tests/test_commons_promote_source.py` (extend)

During discovery, `_validate_datapackage_resources` requires every resource to be an existing file under the datapackage dir (`is_file()`). A sourced resource's bytes are off-repo, so that check must be skipped for sourced resources — but the source shape and the `path` logical-validation must still hold. Without this, Walker/Oetjen fail discovery as `PromoteResourceMissingError` before planning is even reached.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_promote_source.py`:

```python
def test_validate_resources_skips_filesystem_check_for_sourced(tmp_path):
    from science_tool.commons import promote

    dp_abs = tmp_path / "datapackage.json"
    dp_abs.write_text("{}", encoding="utf-8")
    dp_doc = {"resources": [_sourced()]}  # off-repo file does not exist locally
    # Must NOT raise PromoteResourceMissingError for a sourced resource.
    promote._validate_datapackage_resources("walker", dp_abs, dp_doc)


def test_validate_resources_still_requires_colocated_file(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteResourceMissingError

    dp_abs = tmp_path / "datapackage.json"
    dp_abs.write_text("{}", encoding="utf-8")
    dp_doc = {"resources": [{"name": "r1", "path": "missing.txt"}]}
    with pytest.raises(PromoteResourceMissingError):
        promote._validate_datapackage_resources("ds", dp_abs, dp_doc)


def test_validate_resources_rejects_bad_source_at_discovery(tmp_path):
    from science_tool.commons import promote
    from science_tool.commons.errors import PromoteCandidateError

    dp_abs = tmp_path / "datapackage.json"
    dp_abs.write_text("{}", encoding="utf-8")
    res = _sourced()
    res["source"] = {"type": "local", "ref": "relative/path"}
    with pytest.raises(PromoteCandidateError, match="source"):
        promote._validate_datapackage_resources("walker", dp_abs, {"resources": [res]})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py -k validate_resources -q`
Expected: FAIL — `_validate_datapackage_resources` calls `is_file()` and raises `PromoteResourceMissingError` for the sourced resource.

- [ ] **Step 3: Make `_validate_datapackage_resources` source-aware**

Replace the loop body of `_validate_datapackage_resources` (lines 1929–1945) with:

```python
    for idx, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise PromoteCandidateError(f"datapackage resources[{idx}] must be an object")
        resource_path = resource.get("path")
        if not isinstance(resource_path, str) or not resource_path.strip():
            raise PromoteCandidateError(f"datapackage resources[{idx}].path must be a non-empty string")
        try:
            validate_logical_path(resource_path)
        except DataLogicalPathError as exc:
            raise PromoteCandidateError(
                f"datapackage resources[{idx}].path is invalid: {exc.reason}"
            ) from exc

        raw_source = resource.get("source")
        if raw_source is not None:
            # Sourced resource: bytes are off-repo; validate the source shape
            # and skip the co-located filesystem existence check.
            try:
                validate_source(raw_source)
            except ValueError as exc:
                raise PromoteCandidateError(
                    f"datapackage resources[{idx}] has an invalid source: {exc}"
                ) from exc
            continue

        resource_abs = _datapackage_relative_path(
            dp_abs.parent,
            resource_path,
            field=f"datapackage resources[{idx}].path",
        )
        if not resource_abs.is_file():
            raise PromoteResourceMissingError(
                slug=slug,
                resource_name=_resource_name(resource, resource_path),
                resource_path=Path(resource_path),
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py tests/test_commons_promote_dataset_discovery.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_source.py
git commit -m "feat(commons): skip co-located file check for sourced resources at discovery"
```

---

## Task 7: thread `verify_digests` through `plan_promote` + aggregate verdicts

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Test: `science/tests/test_commons_promote_source.py` (extend)

`plan_promote` gains a keyword-only `verify_digests: bool = False`, forwards it to `_dataset_per_resource` (primary) and `_validate_dataset_group_datapackages` (group members). It aggregates **both** the primary's `verifications` **and** the group members' verifications (returned by the group validator) onto a new `PromotePlan.resource_verifications` channel keyed by canonical slug — otherwise a non-primary project's off-host/remote skip would be silently discarded, breaking the "never silently skips" contract for multi-project dataset groups. Each `ResourceVerification` carries its `project_slug`, so the same resource `name` across projects stays distinguishable. Default `False` everywhere keeps every existing caller and test untouched.

- [ ] **Step 1: Write the failing test**

This test drives the full discover → plan path using a synthetic project whose datapackage declares a sourced resource. The project/commons scaffolding is reused by Task 8's CLI test and Task 10's end-to-end test, so put it in a shared, importable (non-test) helper module rather than inline.

First create `science/tests/promote_source_fixtures.py`:

```python
"""Shared fixtures for source-aware promote tests (Tasks 7, 8, 10)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "t@x"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "t"],
        check=True, capture_output=True,
    )


def sourced_project(tmp_path: Path, ref: str) -> Path:
    """A copy of the proj-dataset fixture with r1 turned into a sourced resource."""
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    dp_path = proj / "data" / "fixture-ds" / "datapackage.json"
    dp = json.loads(dp_path.read_text())
    dp["resources"][0] = {
        "name": "r1",
        "path": "r1.txt",
        "format": "txt",
        "mediatype": "text/plain",
        "hash": "sha256:" + "a" * 64,
        "bytes": 12,
        "source": {"type": "local", "ref": ref},
    }
    dp_path.write_text(json.dumps(dp), encoding="utf-8")
    # r2 stays co-located; delete r1.txt so only the sourced one is off-repo.
    (proj / "data" / "fixture-ds" / "r1.txt").unlink()
    init_repo(proj)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "init"], check=True)
    return proj


def init_commons(tmp_path: Path) -> Path:
    """A minimal initialized commons store with the empty layout dirs."""
    commons = tmp_path / "commons"
    commons.mkdir()
    init_repo(commons)
    (commons / "datasets").mkdir()
    (commons / ".migrations").mkdir()
    (commons / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(["git", "-C", str(commons), "commit", "-q", "-m", "init"], check=True)
    return commons
```

Then append the plan-level tests to `science/tests/test_commons_promote_source.py` (note the import of the shared helpers and `init_repo`/`sourced_project`/`init_commons` are now the canonical names):

```python
from promote_source_fixtures import init_commons, init_repo, sourced_project


def test_plan_promote_aggregates_skip_verdict(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)  # token unexpandable → off-host
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(
        discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET, verify_digests=True
    )
    verifs = plan.resource_verifications.get("fixture-ds", ())
    assert any(v.name == "r1" and v.status == "skipped_off_host" for v in verifs)


def test_plan_promote_no_verify_has_empty_verifications(tmp_path, monkeypatch):
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    assert plan.resource_verifications.get("fixture-ds", ()) == ()


def test_group_validator_returns_non_primary_verdicts(tmp_path, monkeypatch):
    """A non-primary project's skip verdict is returned, not silently discarded.

    Drives `_validate_dataset_group_datapackages` directly with two candidates
    that share identical stamped (hash, bytes) — passing divergence — both
    sourced and off-host (OUTPUT_ROOT unset). Both projects' skips must surface,
    distinguished by project_slug.
    """
    from science_tool.commons import promote

    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    primary = _candidate(tmp_path / "a", [_sourced()], project_slug="proj-a")
    secondary = _candidate(tmp_path / "b", [_sourced()], project_slug="proj-b")

    primary_result = promote._dataset_per_resource(primary, verify_digests=True)
    verifications = promote._validate_dataset_group_datapackages(
        canonical_slug="walker",
        primary=primary,
        candidates=[primary, secondary],
        primary_per_resource=primary_result.per_resource,
        verify_digests=True,
    )
    # The group validator returns only the NON-primary candidates' verdicts.
    assert [v.project_slug for v in verifications] == ["proj-b"]
    assert verifications[0].status == "skipped_off_host"
```

(`_candidate` takes the project root as its first arg and `mkdir`s it; pass distinct subdirs `tmp_path / "a"` and `tmp_path / "b"` and distinct `project_slug` values so the two candidates have separate datapackage paths and distinguishable verdicts.)
- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py -k plan_promote -q`
Expected: FAIL — `plan_promote` has no `verify_digests` kwarg and `PromotePlan` has no `resource_verifications`.

- [ ] **Step 3a: Add the `resource_verifications` field to `PromotePlan`**

Extend `PromotePlan` (~line 430):

```python
@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    kind: PromoteKindConfig
    dataset_audit_extras: dict[str, dict[str, Any]] = field(default_factory=dict)
    mixin_extensions: tuple["ProfileComponent", ...] = ()
    resource_verifications: dict[str, tuple[ResourceVerification, ...]] = field(
        default_factory=dict
    )
```

- [ ] **Step 3b: Thread `verify_digests` through `plan_promote`**

Add the keyword-only parameter to `plan_promote` (signature ~line 572):

```python
def plan_promote(
    discovery: DiscoveryResult,
    *,
    commons_root: Path,
    kind: PromoteKindConfig,
    resolve_conflict: Callable[[FieldConflict | ExistingCanonicalConflict], Any] | None = None,
    from_order: list[str] | None = None,
    mixin_extensions: tuple["ProfileComponent", ...] = (),
    verify_digests: bool = False,
) -> PromotePlan:
```

Add the accumulator next to `dataset_audit_extras` (~line 630):

```python
    dataset_resource_verifications: dict[str, tuple[ResourceVerification, ...]] = {}
```

Update the primary call site (the lines just edited in Task 5, ~line 725). Collect the primary's verdicts AND the group members' verdicts (returned by the group validator) so no project's skip is dropped:

```python
            dataset_primary = _primary_candidate_for_plan(classified, from_order)
            _primary_result = _dataset_per_resource(
                dataset_primary, verify_digests=verify_digests
            )
            dataset_primary_per_resource = _primary_result.per_resource
            _group_verifications: tuple[ResourceVerification, ...] = ()
```

(the existing `datapackage_doc is None` guard stays as-is between this and the group-validator call)

Pass `verify_digests` into the group validator and capture its returned verdicts (~line 734):

```python
            _group_verifications = _validate_dataset_group_datapackages(
                canonical_slug=canonical_case,
                primary=dataset_primary,
                candidates=classified,
                primary_per_resource=dataset_primary_per_resource,
                verify_digests=verify_digests,
            )
            combined_verifications = (
                _primary_result.verifications + _group_verifications
            )
            if combined_verifications:
                dataset_resource_verifications[canonical_case] = combined_verifications
```

Add `resource_verifications=dataset_resource_verifications` to the `PromotePlan(...)` constructor at the end of `plan_promote` (~line 1001):

```python
    return PromotePlan(
        decisions=decisions,
        failed_candidates=soft_failures,
        kind=kind,
        dataset_audit_extras=dataset_audit_extras,
        mixin_extensions=mixin_extensions,
        resource_verifications=dataset_resource_verifications,
    )
```

- [ ] **Step 3c: Thread `verify_digests` through `_validate_dataset_group_datapackages` and return its verdicts**

The group validator already calls `_dataset_per_resource` for every non-primary candidate (~line 2446); thread `verify_digests` into that call and collect the resulting `verifications` so they reach `plan_promote` instead of being discarded. Change the return type from `None` to `tuple[ResourceVerification, ...]`.

Add the keyword-only param and an accumulator (signature ~line 2424):

```python
def _validate_dataset_group_datapackages(
    *,
    canonical_slug: str,
    primary: PromoteCandidate,
    candidates: list[PromoteCandidate],
    primary_per_resource: dict[str, tuple[str, int]],
    verify_digests: bool = False,
) -> tuple[ResourceVerification, ...]:
```

The early return for single-candidate groups (`if len(candidates) <= 1: return`) becomes `return ()`. Inside the per-candidate loop, capture the full result (~line 2446):

```python
        candidate_result = _dataset_per_resource(candidate, verify_digests=verify_digests)
        candidate_per_resource = candidate_result.per_resource
        group_verifications.extend(candidate_result.verifications)
```

Declare `group_verifications: list[ResourceVerification] = []` at the top of the function (after the single-candidate early return), and `return tuple(group_verifications)` at the end. Every `raise` path is unchanged (hard errors still abort before any return).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py tests/test_commons_promote_dataset_plan.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/promote.py science/tests/test_commons_promote_source.py
git commit -m "feat(commons): thread verify_digests through plan_promote and aggregate verdicts"
```

---

## Task 8: CLI `--verify-digests` flag + verify summary

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_cli_promote_dataset.py` (extend)

Add the opt-in flag to `promote dataset`, thread `verify_digests` through `_promote_kind_cmd` → `plan_promote`, and print the per-resource verdict summary so a skip is visible to the operator.

- [ ] **Step 1: Inspect the existing CLI test to match its harness**

Run: `cd ~/d/science/science && sed -n '1,60p' tests/test_commons_cli_promote_dataset.py`
This shows the `CliRunner` setup (sandboxed `XDG_CONFIG_HOME`, the `resolve_project_by_id` monkeypatch, `--from`/`--slug` invocation) the new test must mirror.

- [ ] **Step 2: Write the failing test**

Append this test to `science/tests/test_commons_cli_promote_dataset.py`. It imports the shared fixtures from Task 7's `promote_source_fixtures` module, invokes `promote dataset --verify-digests` with `OUTPUT_ROOT` unset (so the local token is unexpandable → reported `skipped_off_host`), and asserts the summary text:

```python
def test_promote_dataset_verify_digests_prints_skip(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from promote_source_fixtures import init_commons, sourced_project
    from science_tool.commons.cli import commons_group

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("OUTPUT_ROOT", raising=False)
    # resolve_commons_root must point at our sandboxed commons store. The other
    # CLI dataset tests in this module set this via XDG/config; mirror whatever
    # they do (e.g. monkeypatch resolve_commons_root or write the config file).
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root", lambda: commons
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        [
            "promote", "dataset",
            "--from", "proj-dataset",
            "--slug", "fixture-ds",
            "--verify-digests",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "verify:" in result.output
    assert "skipped_off_host" in result.output
```

> The `resolve_commons_root` monkeypatch above is the one detail to reconcile with this module's existing harness (Step 1's `sed` shows how the other dataset CLI tests point the command at a sandboxed commons). Use the same mechanism they use; the rest of the scaffolding comes from the shared `promote_source_fixtures` helpers.

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_cli_promote_dataset.py -k verify_digests -q`
Expected: FAIL — `--verify-digests` is not a recognized option.

- [ ] **Step 4a: Add the flag to `promote dataset`**

In `science/src/science_tool/commons/cli.py`, add the option to the `promote dataset` command params list (after the `--mixin` option, ~line 589):

```python
        click.Option(
            ["--verify-digests"],
            "verify_digests",
            is_flag=True,
            default=False,
            help=(
                "Re-verify each sourced resource's build-stamped digest against "
                "its local bytes (when resolvable on this host). Off by default: "
                "promote trusts the stamped digest and does no byte I/O."
            ),
        ),
```

Add the parameter to `promote_dataset_cmd` and forward it (~line 592):

```python
def promote_dataset_cmd(
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
    slug: str,
    mixin_args: tuple[str, ...],
    verify_digests: bool,
) -> None:
    ...
    _promote_kind_cmd(
        kind=PROMOTE_KIND_DATASET,
        entity_id=f"dataset:{slug}",
        from_=from_,
        apply_=apply_flag,
        limit=limit,
        mixin_extensions=mixin_extensions,
        verify_digests=verify_digests,
    )
```

- [ ] **Step 4b: Thread it through `_promote_kind_cmd`**

Add the keyword to `_promote_kind_cmd` (~line 620) and pass it into `plan_promote` (~line 695):

```python
def _promote_kind_cmd(
    *,
    kind: PromoteKindConfig,
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_: bool,
    limit: int | None,
    mixin_extensions: tuple["ProfileComponent", ...] = (),
    verify_digests: bool = False,
) -> None:
    ...
        plan = plan_promote(
            discovery,
            commons_root=root,
            kind=kind,
            from_order=list(from_),
            mixin_extensions=mixin_extensions,
            verify_digests=verify_digests,
        )
```

- [ ] **Step 4c: Print the verify summary**

In `_echo_dataset_plan_details` (~line 747), after the `resources:` block, add:

```python
    verifications = plan.resource_verifications.get(decision.slug, ())
    if verifications:
        click.echo("    verify:")
        for v in verifications:
            click.echo(f"      - [{v.project_slug}] {v.name}: {v.status} ({v.detail})")
```

- [ ] **Step 5: Run the test + the existing dataset CLI suite**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_cli_promote_dataset.py -q`
Expected: PASS (new test green; existing tests unaffected — the flag defaults to off and the summary block is empty without sourced resources).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli_promote_dataset.py
git commit -m "feat(commons): add --verify-digests flag and per-resource verify summary"
```

---

## Task 9: inventory `source` field

**Files:**
- Modify: `science/src/science_tool/commons/inventory.py`
- Test: `science/tests/test_commons_inventory.py` (extend)

`build_commons_inventory` serializes each resource as `{path, hash, bytes, format, mediatype}` — dropping `source`. Add `source` so the inventory is not lossy for sourced resources. This test drives `build_commons_inventory` **end-to-end** against a real commons store fixture (the same `_make_store` + `SCIENCE_COMMONS_ROOT` harness the existing inventory tests use), so it genuinely gates the production change rather than re-deriving the expected dict from `read_datapackage`.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_inventory.py`. It copies the valid store, rewrites the `cath-domains` datapackage's single resource into a *sourced* resource, then runs the real inventory build:

```python
def test_build_commons_inventory_preserves_resource_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sourced resource's `source` survives end-to-end into the inventory."""
    root = _make_store(tmp_path)
    (root / "datasets" / "cath-domains" / "datapackage.yaml").write_text(
        "name: cath-domains\n"
        "profile: \"data-package\"\n"
        "resources:\n"
        "  - name: cath_domains\n"
        "    path: cath_domains.parquet\n"
        "    hash: \"sha256:" + "0" * 64 + "\"\n"
        "    bytes: 4521339201\n"
        "    format: \"parquet\"\n"
        "    mediatype: \"application/vnd.apache.parquet\"\n"
        "    source:\n"
        "      type: local\n"
        "      ref: ${OUTPUT_ROOT}/cath/cath_domains.parquet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    payload = build_commons_inventory()

    cath = next(e for e in payload.entities if e.id == "dataset:cath-domains")
    assert cath.data["resources"][0]["source"] == {
        "type": "local",
        "ref": "${OUTPUT_ROOT}/cath/cath_domains.parquet",
    }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_inventory.py -k preserves_resource_source -q`
Expected: FAIL with `KeyError: 'source'` — the production dict at `inventory.py:117` does not yet emit a `source` key.

- [ ] **Step 3a: Update the existing co-located assertion to expect `source: None`**

Adding `source` to the serialized dict changes the shape asserted by the existing `test_build_commons_inventory_projects_dataset_resources` (it pins the full resource dict for `cath-domains` and `rnaseq-example`). Update that assertion (~line 174) so co-located resources carry an explicit `"source": None`:

```python
    cath = next(e for e in payload.entities if e.id == "dataset:cath-domains")
    assert cath.data["resources"] == [
        {
            "path": "cath_domains.parquet",
            "hash": "sha256:" + "0" * 64,
            "bytes": 4521339201,
            "format": "parquet",
            "mediatype": "application/vnd.apache.parquet",
            "source": None,
        }
    ]
```

- [ ] **Step 3b: Add `source` to the serialized resource dict**

In `science/src/science_tool/commons/inventory.py`, extend the per-resource dict (~line 117):

```python
            data["resources"] = [
                {
                    "path": resource.path,
                    "hash": resource.hash,
                    "bytes": resource.bytes,
                    "format": resource.format,
                    "mediatype": resource.mediatype,
                    "source": (
                        {"type": resource.source.type, "ref": resource.source.ref}
                        if resource.source is not None
                        else None
                    ),
                }
                for resource in descriptor.resources
            ]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_inventory.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/inventory.py science/tests/test_commons_inventory.py
git commit -m "feat(commons): preserve resource source in commons inventory"
```

---

## Task 10: end-to-end regression — sourced dataset promotes without streaming

**Files:**
- Test: `science/tests/test_commons_promote_source.py` (extend)

A final integration test proving the headline behavior: a dataset whose resource is sourced (off-repo) promotes through discover → plan → apply, the default path never streams the off-repo bytes, the rendered `datapackage.yaml` carries `path + hash + bytes + source`, and a co-located sibling resource still streams normally.

- [ ] **Step 1: Write the test**

Append to `science/tests/test_commons_promote_source.py`:

```python
def test_sourced_dataset_promotes_end_to_end_without_streaming(tmp_path, monkeypatch):
    from science_tool.commons import promote as promote_mod
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = sourced_project(tmp_path, "${OUTPUT_ROOT}/scrna/x.h5ad")
    commons = init_commons(tmp_path)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    # Spy on streaming: the sourced r1 must NOT be streamed; the co-located r2 must.
    streamed = []
    real_stream = promote_mod.stream_sha256_and_bytes
    monkeypatch.setattr(
        promote_mod,
        "stream_sha256_and_bytes",
        lambda p: streamed.append(p.name) or real_stream(p),
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    apply_promote(plan, commons_root=commons, invocation="source-e2e")

    assert "r1.txt" not in streamed       # sourced → never read
    assert "r2.txt" in streamed           # co-located → streamed

    import yaml as y

    parsed = y.safe_load(
        (commons / "datasets/fixture-ds/datapackage.yaml").read_text(encoding="utf-8")
    )
    r1 = next(r for r in parsed["resources"] if r["name"] == "r1")
    assert r1["hash"] == "sha256:" + "a" * 64
    assert r1["bytes"] == 12
    assert r1["source"] == {"type": "local", "ref": "${OUTPUT_ROOT}/scrna/x.h5ad"}
```

- [ ] **Step 2: Run the test**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_promote_source.py -k end_to_end -q`
Expected: PASS — sourced resource promotes, its bytes are never streamed, `source` round-trips into the canonical `datapackage.yaml`.

> If `apply_promote` re-streams or re-validates resources during apply and the sourced file's absence trips a check, treat that as an apply-path gap surfaced by this test: extend the apply path's resource handling to be source-aware the same way discovery/plan are (skip filesystem reads for sourced resources). The test is the gate.

- [ ] **Step 3: Commit**

```bash
cd ~/d/science && git add science/tests/test_commons_promote_source.py
git commit -m "test(commons): end-to-end sourced dataset promotes without streaming"
```

---

## Final: full suite + branch finish

- [ ] **Step 1: Run the whole commons test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/ -k commons -q`
Expected: PASS (no regressions across promote / datapackage / inventory / cli).

- [ ] **Step 2: Type-check (if the project gates on pyright)**

Run: `cd ~/d/science/science && uv run --frozen pyright src/science_tool/commons/datapackage.py src/science_tool/commons/promote.py src/science_tool/commons/cli.py src/science_tool/commons/inventory.py`
Expected: no new errors introduced by these changes.

- [ ] **Step 3: Finish the branch**

Use the **superpowers:finishing-a-development-branch** skill on `feat/external-datapackage-resources` to verify tests, then choose merge / PR / keep.

---

## Self-Review

**1. Spec coverage** (design § → task):
- `source` field + `ResourceSource` type → Task 1, Task 3.
- `local.ref` shape rules (`${OUTPUT_ROOT}` token, reject relative/other-token/`${OUTPUT_ROOT}foo`) → Task 1.
- remote `type`s recorded + shape-validated, not fetched → Task 1 (validation), Task 5 (`skipped_remote`).
- `RefResolution` / `Unexpandable` / `Resolved` / `resolve_local_ref`, blank/relative `OUTPUT_ROOT` config error → Task 2.
- presence-as-discriminator; co-located unchanged → Task 5 (no-`source` branch streams as before).
- default trust, no I/O for sourced → Task 5 (`test_default_trusts_sourced_resource_without_io`).
- `--verify-digests` verdict table (verified / drift hard-error / resolvable-but-missing hard-error / off-host skip / remote skip) → Task 5.
- valid (not merely present) `hash`/`bytes` via `parse_resource_hash` + non-bool int ≥ 0 → Task 5 (`_stamped_metadata`).
- `validate_logical_path` on every `path` (co-located + sourced) → Task 5, Task 6.
- discovery skips the co-located file check for sourced resources → Task 6.
- `PerResourceResult` result channel; CLI prints summary; never-silently-skips → Task 5, Task 7, Task 8.
- **`plan_promote` aggregates BOTH primary and group-member verdicts** onto `PromotePlan` — the group validator returns its non-primary verdicts instead of discarding them, and `ResourceVerification.project_slug` keeps duplicate resource names distinguishable across a multi-project group → Task 5 (`project_slug` field + `test_group_validator_returns_non_primary_verdicts`), Task 7 (aggregation + return-type change).
- `verify_digests` threaded keyword-only through `_promote_kind_cmd` → `plan_promote` → `_dataset_per_resource` + `_validate_dataset_group_datapackages`, default `False` → Task 7, Task 8.
- `PromoteResourceDigestMismatchError` → Task 4.
- inventory `source` not lossy → Task 9 (real end-to-end `build_commons_inventory` test; existing co-located assertion updated to `source: None`).
- `url` ref requires scheme ∈ {http, https} + netloc (via `urllib.parse.urlparse`, not `startswith`) → Task 1.
- render carries `path + hash + bytes + source` → Task 3 (verbatim pass-through) + Task 10 (e2e assertion).
- regression: co-located promotes as before → Task 5, Task 10.
- non-goals (no remote fetch, no producer helper, `resolver.py` unchanged) → not implemented by design; no task.

**2. Placeholder scan:** every code step carries the actual code; commands carry expected outcomes. The shared `promote_source_fixtures.py` helper module (created in Task 7) is imported by Tasks 8 and 10 — there are no `# ...` elisions in any test body. The single residual prose note is in Task 8: reconcile the `resolve_commons_root` monkeypatch with this module's existing harness (the one mechanism that genuinely differs per test file); the test body itself is complete.

**3. Type consistency:** `ResourceSource(type, ref)`, `Unexpandable(ref)`, `Resolved(path, exists)`, `resolve_local_ref(ref) -> RefResolution`, `validate_source(raw) -> ResourceSource`, `_dataset_per_resource(candidate, *, verify_digests=False) -> PerResourceResult`, `PerResourceResult(per_resource, verifications)`, `ResourceVerification(project_slug, name, status, detail)`, `_verify_sourced_resource(project_slug, name, source, stamped, slug)`, `PromotePlan.resource_verifications: dict[str, tuple[ResourceVerification, ...]]`, `plan_promote(..., verify_digests=False)`, `_validate_dataset_group_datapackages(..., verify_digests=False) -> tuple[ResourceVerification, ...]`, `PromoteResourceDigestMismatchError(slug, resource_name, expected, actual, path)` — names and signatures are used identically across the tasks that define and consume them. Shared test helpers: `init_repo`, `sourced_project`, `init_commons` (in `promote_source_fixtures.py`).
