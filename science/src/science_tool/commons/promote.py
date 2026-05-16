"""Promote paper entities from per-project files into the commons store.

Pipeline: discover → plan → apply. Atomic-batch transaction semantics
per docs/plans/2026-05-15-commons-promote-papers-design.md §6.3.

This module owns:
- Dataclasses for the public surface (PromoteCandidate, PromotePlan, …).
- `discover_paper_candidates(project_slugs) -> DiscoveryResult` (Task 10).
- `plan_promote(discovery, commons_root, *, resolve_conflict) -> PromotePlan` (Task 14).
- `apply_promote(plan, commons_root, *, invocation) -> PromoteResult` (Tasks 16–17).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Literal

import yaml

from science_model.entity_schema import MergePolicy, default_profile_for_kind
from science_tool.commons.config import resolve_project_by_id
from science_tool.commons.errors import PromoteCandidateError


# --------------------------------------------------------------------------- #
# Public dataclasses                                                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PromoteCandidate:
    """One paper file found during discovery.

    `bibkey` is the source's case (filename stem). `bibkey_normalized` is
    casefold() used only for dedup grouping. See design §4.1.3.
    """

    bibkey: str
    bibkey_normalized: str
    project_slug: str
    project_root: Path
    overlay_source_path: Path
    canonical_fields: dict[str, Any]
    project_only_fields: dict[str, Any]
    canonical_body: dict[str, str]
    project_only_body: dict[str, Any]
    # `project_only_body` is `dict[str, Any]` (not `[str, str]`) so the
    # discovery phase can stash the raw `(frontmatter, body)` pair under
    # sentinel keys `__raw_frontmatter__` / `__raw_body__` for `plan_promote`
    # to consume during classification. After `_classify_entity` runs in
    # `plan_promote`, the dict's values are pure `str` again.


@dataclass(frozen=True, slots=True)
class FieldConflict:
    bibkey: str
    field: str
    candidates: dict[str, Any]  # project_slug → value


@dataclass(frozen=True, slots=True)
class ConflictResolution:
    bibkey: str
    field: str
    candidates: dict[str, Any]
    resolved_to: Any
    source_project: str | None  # None if user entered a manual value


@dataclass(frozen=True, slots=True)
class OverlayRewrite:
    project_slug: str
    path: Path
    before_sha: str
    after_content: str
    pin_version: str
    rename_from: Path | None = None  # set when canonical case differs from source


@dataclass(frozen=True, slots=True)
class PromoteDecision:
    bibkey: str
    canonical_path: Path                 # absolute `<commons>/papers/<bibkey>.md`
    canonical_content: str               # rendered canonical file (markdown + frontmatter)
    canonical_version: str               # "1.0.0" etc.
    overlays: dict[str, OverlayRewrite]  # project_slug → rewrite plan
    resolved_conflicts: tuple[ConflictResolution, ...]


@dataclass(frozen=True, slots=True)
class FailedCandidate:
    bibkey: str | None
    project_slug: str
    source_path: Path
    error_class: str
    error_message: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidates_by_bibkey: dict[str, list[PromoteCandidate]]
    failed_candidates: list[FailedCandidate]


@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]


@dataclass(frozen=True, slots=True)
class PromoteResult:
    op_id: str
    started_at: datetime
    finished_at: datetime
    commons_commit: str | None
    tags_created: list[str]
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    audit_log_path: Path | None
    status: Literal["ok", "failed"]
    failure_stage: Literal[
        "preflight", "validate", "discover", "plan",
        "write_commons", "rewrite_projects", "audit",
    ] | None
    failure_detail: str | None
    # Project slugs whose `doc/papers/<file>.md` were actually modified by this
    # operation. On the success path, every overlay slug; on a partial step-6
    # failure, just the slugs reached before the failure; on
    # preflight/tag/commit failures (no project file touched), the empty list.
    # The audit log filters `projects_touched` (overlay_rewrites + rollback
    # hints) by this list so failure logs don't suggest rollbacks for projects
    # that were never modified (design §6.3 step 7 failure variant).
    projects_touched: list[str]


# --------------------------------------------------------------------------- #
# Public entry points (stubs — implemented in Tasks 10, 14, 16, 17)           #
# --------------------------------------------------------------------------- #


def discover_paper_candidates(project_slugs: list[str]) -> DiscoveryResult:
    """Scan each project's `doc/papers/*.md` directly. Group by case-insensitive
    `bibkey_normalized`. Returns successful candidates + failure records."""
    grouped: dict[str, list[PromoteCandidate]] = {}
    failures: list[FailedCandidate] = []

    for slug in project_slugs:
        project_root = resolve_project_by_id(slug)  # raises CommonsError on bad slug
        candidates, project_failures = _scan_project_papers(project_root, slug)
        failures.extend(project_failures)
        for cand in candidates:
            grouped.setdefault(cand.bibkey_normalized, []).append(cand)

    return DiscoveryResult(candidates_by_bibkey=grouped, failed_candidates=failures)


def plan_promote(
    discovery: DiscoveryResult,
    commons_root: Path,
    *,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
) -> PromotePlan:
    raise NotImplementedError  # Task 14


def apply_promote(
    plan: PromotePlan,
    commons_root: Path,
    *,
    invocation: str,
) -> PromoteResult:
    raise NotImplementedError  # Tasks 16–17


# --------------------------------------------------------------------------- #
# Private helpers                                                              #
# --------------------------------------------------------------------------- #

_BIBKEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,63}$")

# Sentinel keys for stashing raw frontmatter+body in PromoteCandidate.project_only_body
# during discovery, to be consumed by _classify_entity in plan_promote (Task 11).
# Defined as module-level constants so the coupling between discovery and
# classification is greppable rather than hidden in two string literals.
_RAW_FRONTMATTER_KEY = "__raw_frontmatter__"
_RAW_BODY_KEY = "__raw_body__"


def _normalize_bibkey_for_match(raw: str) -> str:
    """Strip `.md`, casefold for dedup grouping. Raises PromoteCandidateError on
    empty / whitespace / regex-failing inputs. Does NOT mutate canonical case."""
    if raw is None:
        raise PromoteCandidateError("bibkey is None")
    stripped = raw.strip()
    if not stripped:
        raise PromoteCandidateError("bibkey is empty / whitespace")
    if stripped.endswith(".md"):
        stripped = stripped[:-3]
    if not _BIBKEY_RE.match(stripped):
        raise PromoteCandidateError(
            f"bibkey {raw!r} does not match [A-Za-z][A-Za-z0-9-]{{1,63}}"
        )
    return stripped.casefold()


def _classify_paper_file_kind(
    frontmatter: dict,
) -> Literal["paper", "skip-other-kind", "skip-other-id"]:
    """Decide whether a file under `doc/papers/` is a paper candidate.

    Rule (design §6.3 step 2):
    1. Explicit `kind: paper` or `type: paper` → paper.
    2. Explicit `kind` / `type` with any other value → skip-other-kind.
    3. No `kind` / `type`, `id` present and NOT starting with `paper:` →
       skip-other-id (defense-in-depth; stronger declaration than directory
       inference, but weaker than an explicit kind/type).
    4. No `kind` / `type` and no contradictory `id` → infer from directory: paper.

    Rules are checked in order: explicit kind/type wins over the id-prefix
    check, so `{"id": "dataset:foo", "kind": "paper"}` returns "paper".
    """
    kind_val = frontmatter.get("kind") or frontmatter.get("type")
    if kind_val == "paper":
        return "paper"
    if kind_val is not None:
        return "skip-other-kind"
    id_val = frontmatter.get("id")
    if isinstance(id_val, str) and not id_val.startswith("paper:"):
        return "skip-other-id"
    return "paper"


logger = logging.getLogger(__name__)


def _parse_paper_file(path: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Raises PromoteCandidateError on
    parse failure, unreadable file, or missing frontmatter delimiters."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PromoteCandidateError(
            f"unreadable file: {exc}", path=path
        ) from exc
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != "---":
        raise PromoteCandidateError("no frontmatter (missing leading ---)", path=path)
    closing_idx: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_idx = idx
            break
    if closing_idx is None:
        raise PromoteCandidateError("no frontmatter (missing closing ---)", path=path)
    yaml_block = "\n".join(lines[1:closing_idx])
    try:
        fm = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        raise PromoteCandidateError(
            f"frontmatter parse error: {exc}", path=path
        ) from exc
    if not isinstance(fm, dict):
        raise PromoteCandidateError(
            "frontmatter is not a mapping", path=path
        )
    body = "\n".join(lines[closing_idx + 1 :])
    if text.endswith("\n") and not body.endswith("\n"):
        body += "\n"
    return fm, body


def _scan_project_papers(
    project_root: Path, project_slug: str
) -> tuple[list[PromoteCandidate], list[FailedCandidate]]:
    """Walk `<project_root>/doc/papers/*.md`, classify each file, return
    (candidates, failures). Skips already-promoted files and explicit non-paper
    kinds. Per-file failures become FailedCandidate records; the walk continues."""
    candidates: list[PromoteCandidate] = []
    failures: list[FailedCandidate] = []
    papers_dir = project_root / "doc" / "papers"
    if not papers_dir.is_dir():
        return candidates, failures

    for md_path in sorted(papers_dir.glob("*.md")):
        try:
            fm, body = _parse_paper_file(md_path)
        except PromoteCandidateError as exc:
            failures.append(
                FailedCandidate(
                    bibkey=md_path.stem,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=str(exc),
                )
            )
            continue

        if "overlay_of" in fm:
            continue  # already promoted; idempotent skip

        classification = _classify_paper_file_kind(fm)
        if classification == "skip-other-kind":
            logger.warning(
                "%s: kind/type is not 'paper'; skipping (explicit non-paper)",
                md_path,
            )
            continue
        if classification == "skip-other-id":
            logger.warning(
                "%s: id prefix is not 'paper:'; skipping (explicit non-paper id)",
                md_path,
            )
            continue

        # Commons / overlay adapters derive ids from filename stems case-
        # sensitively and require frontmatter id to match the stem exactly
        # (adapter.py:149, overlay.py:114). Promote inherits the same rule —
        # the source case is canonical (design §4.1.3). If the source carries
        # an explicit `id:` that disagrees with its filename stem, that's a
        # bug in the source file, not something promote should silently
        # rewrite: fail the candidate so the user can fix it.
        explicit_id = fm.get("id")
        if explicit_id is not None and explicit_id != f"paper:{md_path.stem}":
            failures.append(
                FailedCandidate(
                    bibkey=md_path.stem,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=(
                        f"frontmatter id {explicit_id!r} does not match filename "
                        f"stem {md_path.stem!r}; expected id 'paper:{md_path.stem}'"
                    ),
                )
            )
            continue

        bibkey_source = md_path.stem
        try:
            bibkey_normalized = _normalize_bibkey_for_match(bibkey_source)
        except PromoteCandidateError as exc:
            failures.append(
                FailedCandidate(
                    bibkey=bibkey_source,
                    project_slug=project_slug,
                    source_path=md_path,
                    error_class="PromoteCandidateError",
                    error_message=str(exc),
                )
            )
            continue

        # canonical_fields / project_only_fields / body splits are filled in
        # later by `_classify_entity` (Task 11). For now we stash raw frontmatter
        # + body so discovery is independent of merge-policy lookup.
        candidates.append(
            PromoteCandidate(
                bibkey=bibkey_source,
                bibkey_normalized=bibkey_normalized,
                project_slug=project_slug,
                project_root=project_root,
                overlay_source_path=md_path,
                canonical_fields={},
                project_only_fields={},
                canonical_body={},
                project_only_body={_RAW_FRONTMATTER_KEY: fm, _RAW_BODY_KEY: body},
            )
        )

    return candidates, failures


# --------------------------------------------------------------------------- #
# _classify_entity helpers (Task 11)                                          #
# --------------------------------------------------------------------------- #

# Overlay-only fields that MUST never leak onto the canonical or project-only
# field dicts (the overlay-rewrite step writes these directly).
_OVERLAY_ONLY_KEYS: frozenset[str] = frozenset({"overlay_of", "pin_version", "pin_effective_version"})

# Base-required fields that the promote tool generates on the canonical side
# and that MUST NOT be copied from source. `created` / `updated` are NOT here:
# they have `science:merge: project_only` in the paper schema, so the policy
# lookup routes them correctly to the project_only bucket. The canonical
# writer fills its own `created` / `updated` from the apply timestamp.
_GENERATED_BY_PROMOTE_KEYS: frozenset[str] = frozenset(
    {"schema_profile", "version"}
)

# Identity fields promote re-derives from the PromoteDecision after the
# canonical bibkey case is picked. They are stripped from the canonical merge
# bucket so case-divergent overlays don't surface a bogus `id` conflict
# (design §4.1.3).
_PROMOTE_DERIVED_IDENTITY_KEYS: frozenset[str] = frozenset({"id", "type", "bibkey"})


def _split_body_by_headings(body: str) -> dict[str, str]:
    """Parse a markdown body into `{heading: content_after_heading}`.

    Only `## ` (level-2) headings are tracked. Content before the first `## ` is
    keyed as `""` (the empty string). Sub-headings (`###` etc.) stay inside
    whichever level-2 section contains them.
    """
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)
    return {heading: "\n".join(lines) for heading, lines in sections.items() if lines or heading}


def _classify_entity(
    frontmatter: dict,
    body: str,
    merge_policy: dict[str, MergePolicy],
    canonical_body_sections: list[str],
) -> tuple[dict, dict, dict[str, str], dict[str, str]]:
    """Split (frontmatter, body) into (canonical_fields, project_only_fields,
    canonical_body, project_only_body).

    - Promote-generated fields (schema_profile, version) are NOT copied from
      source; the canonical writer fills them. `created` / `updated` are
      schema-tagged `project_only` and route to the overlay via the policy
      lookup — the canonical writer fills its own from the apply timestamp.
    - Overlay-management fields (overlay_of, pin_version) NEVER appear on either
      side (they're written by the overlay renderer alone).
    - Promote-derived identity fields (id, type, bibkey) NEVER appear on either
      side either — the canonical writer re-emits them from the PromoteDecision
      (after `_pick_canonical_bibkey_case` chooses the canonical-case bibkey).
      Letting them flow through the canonical bucket would surface a bogus
      `id` conflict any time two case-divergent overlays merge (design §4.1.3).
    - For every remaining source field, the merge policy decides:
        REPLACE / APPEND / FORBIDDEN → canonical bucket
        PROJECT_ONLY                  → project-only bucket
        no policy entry               → conservative default: project-only
    - `authors` is coerced to list[str] if it arrives as a string.
    - `journal` is renamed to `venue` (one-time coercion).
    """
    canonical: dict = {}
    project_only: dict = {}
    for key, value in frontmatter.items():
        if key in _OVERLAY_ONLY_KEYS:
            continue
        if key in _PROMOTE_DERIVED_IDENTITY_KEYS:
            continue
        if key in _GENERATED_BY_PROMOTE_KEYS:
            continue
        if key == "journal":
            canonical["venue"] = value
            continue
        if key == "authors" and not isinstance(value, list):
            canonical["authors"] = [str(value)]
            continue
        # `tags` uses APPEND policy in the schema but promote always writes
        # canonical `tags: []` (design §4.1.2) so the source's tags stay
        # project-only during classification; the renderer zeros out canonical tags.
        if key == "tags":
            project_only[key] = value
            continue
        policy = merge_policy.get(key, MergePolicy.PROJECT_ONLY)
        if policy == MergePolicy.PROJECT_ONLY:
            project_only[key] = value
        else:
            canonical[key] = value

    raw_body_sections = _split_body_by_headings(body)
    canonical_set = {s.casefold() for s in canonical_body_sections}
    canonical_body: dict[str, str] = {}
    project_only_body: dict[str, str] = {}
    for heading, content in raw_body_sections.items():
        if heading == "":
            project_only_body[""] = content
            continue
        if heading.casefold() in canonical_set:
            canonical_body[heading] = content
        else:
            project_only_body[heading] = content

    return canonical, project_only, canonical_body, project_only_body


# --------------------------------------------------------------------------- #
# Multi-instance merge helpers (Task 12)                                       #
# --------------------------------------------------------------------------- #


def _merge_canonical_fields(
    candidates: list[PromoteCandidate],
    merge_policy: dict[str, MergePolicy],
) -> tuple[dict, list[FieldConflict]]:
    """Merge canonical_fields across N candidates of the same bibkey.

    Rule per field (driven by merge_policy lookup):
    - APPEND: union of all candidates' lists, sorted + deduped.
    - Anything else (REPLACE / FORBIDDEN / no entry):
      - if no candidate has the field → omitted.
      - if all candidates agree (equal values) → that value.
      - if candidates disagree → field omitted from `merged`; a FieldConflict
        with `{slug: value}` for every candidate that has the field is appended.
    """
    all_keys = {key for c in candidates for key in c.canonical_fields}
    merged: dict = {}
    conflicts: list[FieldConflict] = []

    for key in sorted(all_keys):
        present = [c for c in candidates if key in c.canonical_fields]
        policy = merge_policy.get(key, MergePolicy.REPLACE)
        if policy == MergePolicy.APPEND:
            union: set = set()
            for c in present:
                v = c.canonical_fields[key]
                if isinstance(v, list):
                    union.update(v)
                else:
                    union.add(v)
            merged[key] = sorted(union)
            continue

        values = [c.canonical_fields[key] for c in present]
        if all(v == values[0] for v in values):
            merged[key] = values[0]
        else:
            conflicts.append(
                FieldConflict(
                    bibkey=present[0].bibkey,
                    field=key,
                    candidates={c.project_slug: c.canonical_fields[key] for c in present},
                )
            )

    return merged, conflicts


def _pick_canonical_bibkey_case(
    candidates: list[PromoteCandidate],
    from_order: list[str],
) -> str:
    """Pick the canonical bibkey case from a multi-instance group.

    Rule (design §4.1.3):
    1. Walk from_order; the first project_slug with a matching candidate wins.
    2. If two candidates share the earliest slug (impossible in practice but
       defensive) or from_order is empty, tie-break by lexical project_slug.
    """
    order = {slug: idx for idx, slug in enumerate(from_order)}
    sorted_by_order = sorted(
        candidates,
        key=lambda c: (order.get(c.project_slug, len(order)), c.project_slug),
    )
    return sorted_by_order[0].bibkey


# --------------------------------------------------------------------------- #
# Renderer helpers (Task 13)                                                   #
# --------------------------------------------------------------------------- #

_DATE_KEYS: frozenset[str] = frozenset({"created", "updated"})
# Scalar keys whose values must be emitted as double-quoted strings regardless
# of how pyyaml chooses to serialise them (version strings look numeric to YAML).
_FORCE_QUOTED_KEYS: frozenset[str] = _DATE_KEYS | frozenset({"version", "pin_version"})


def _coerce_date_for_yaml(value: Any) -> str:
    """`datetime.date` / `datetime.datetime` / `str` → ISO-8601 string. Other
    types are returned as-is via `str(value)`."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _render_frontmatter(fields: dict) -> str:
    """Render an ordered, deterministic YAML frontmatter block.

    Date fields go through `_coerce_date_for_yaml` and are quoted; version /
    pin_version scalars are also force-quoted (pyyaml treats "1.0.0" as a
    plain float-like scalar).  Lists are block style.
    """
    out: dict = {}
    for key, value in fields.items():
        if key in _DATE_KEYS:
            out[key] = _coerce_date_for_yaml(value)
        else:
            out[key] = value
    dumped = yaml.safe_dump(
        out,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )
    # Force double-quoting of scalars in _FORCE_QUOTED_KEYS — pyyaml may emit
    # unquoted or single-quoted forms that would round-trip incorrectly.
    lines = []
    for line in dumped.splitlines():
        for k in _FORCE_QUOTED_KEYS:
            prefix = f"{k}:"
            if line.startswith(prefix):
                raw = line[len(prefix):].strip()
                # Strip surrounding single- or double-quotes pyyaml may add
                if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
                    raw = raw[1:-1]
                if raw and raw != "null":
                    line = f'{k}: "{raw}"'
        lines.append(line)
    return "\n".join(lines) + "\n"


def _render_body(sections: dict[str, str]) -> str:
    """Render `{heading: content}` back to markdown. Empty heading "" goes first
    (intro prose); the rest are emitted in insertion order with `## ` prefix."""
    parts: list[str] = []
    if "" in sections:
        intro = sections[""].strip("\n")
        if intro:
            parts.append(intro + "\n")
    for heading, content in sections.items():
        if heading == "":
            continue
        parts.append(f"## {heading}\n{content.rstrip()}\n")
    return "\n".join(parts)


def _render_canonical(
    decision: PromoteDecision,
    *,
    canonical_fields: dict,
    canonical_body: dict[str, str],
    created: date,
    updated: date,
) -> str:
    """Render the commons-side papers/<bibkey>.md content.

    Fills base-required fields (schema_profile, version, created, updated) and
    always emits `tags: []` so the per-project overlay-merge produces only the
    project's overlay tags (design §4.1.2).
    """
    profile_str = default_profile_for_kind("paper").render()
    head: dict = {
        "schema_profile": profile_str,
        "id": f"paper:{decision.bibkey}",
        "type": "paper",
        "title": canonical_fields.get("title", ""),
        "version": decision.canonical_version,
        "created": _coerce_date_for_yaml(created),
        "updated": _coerce_date_for_yaml(updated),
        "bibkey": decision.bibkey,
        "tags": [],
    }
    for k, v in canonical_fields.items():
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(canonical_body)
    return f"---\n{fm}---\n{body}"


def _render_overlay(
    decision: PromoteDecision,
    *,
    project_slug: str,  # noqa: ARG001 — retained for Task 15 audit-log call-site symmetry
    project_only_fields: dict,
    project_only_body: dict[str, str],
) -> str:
    """Render a project-side overlay file. NEVER emits schema_profile; the
    overlay validator is hardcoded to overlay/1.1 (design §4.4)."""
    head: dict = {
        "id": f"paper:{decision.bibkey}",
        "overlay_of": f"paper:{decision.bibkey}",
        "pin_version": decision.canonical_version,
    }
    # Skip overlay-only-management keys (overlay_of/pin_version/pin_effective_version)
    # AND any head-priority key, so project_only_fields can't accidentally
    # overwrite the promote-derived id/overlay_of/pin_version (mirrors
    # _render_canonical's guard pattern).
    for k, v in project_only_fields.items():
        if k in _OVERLAY_ONLY_KEYS:
            continue
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(project_only_body)
    return f"---\n{fm}---\n{body}"
