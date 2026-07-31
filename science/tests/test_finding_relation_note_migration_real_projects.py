"""Step 3 -- the `relations[].note` corpus migration, asserted on the REAL corpus.

`mixin-finding-1.0` reuses `$defs/authored_relation` verbatim from `mixin-hypothesis-2.0`:
`{predicate, target, graph_layer}` with `additionalProperties: false`. Three
`natural-systems` findings authored a fourth key, `note`, which
`AuthoredTargetedRelation` (source_contracts.py:18) silently discards -- the exact defect
that `$comment` names, sitting in the corpus of the kind being closed.

The ruling was to migrate the corpus rather than widen the schema or the model. See
docs/plans/2026-07-30-schema-closure-finding-slice-inventory.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.real_projects

DECLARED_RELATION_KEYS = {"predicate", "target", "graph_layer"}

# Every project root on this machine, enumerated rather than globbed: a glob that matched
# nothing would pass this file silently.
PROJECT_ROOTS = (
    "cancer/cancer-types/breast",
    "cancer/cancer-types/head-and-neck",
    "cancer/cancer-types/multiple-myeloma",
    "cancer/cancer-types/ovarian",
    "cancer/cancer-types/prostate",
    "cancer/conditions/pre-cancer",
    "cancer/data-sources/cbioportal",
    "cancer/mechanisms/evolution",
    "cancer/meta",
    "cancer/therapeutics",
    "health/comparisons/pan-disease",
    "health/meta",
    "health/processes/cycles",
    "health/processes/immunity",
    "health/processes/post-acute-infection",
    "natural-systems",
    "protein-landscape",
    "science-commons",
)

MIGRATED = (
    "0017-blind-census-near-miss-fails-certification-uncalibrated",
    "0018-skeleton-score-ranks-equivalence-similarity-vs-certification",
    "0019-rule-r-prime-holdout-census-certifies-tau-0-92",
)


def _frontmatter(path: Path) -> dict | None:
    """Parse frontmatter, letting a genuine YAML error RAISE.

    Templates are excluded by path before parsing rather than by swallowing the error:
    `.ai/templates/gene-note.md` carries `{{SYMBOL}}` placeholders that are not valid
    YAML. A blanket try/except here would also hide a real record whose frontmatter has
    been corrupted, which is precisely the kind of silent pass this file exists to
    prevent.
    """
    if "templates" in path.parts:
        return None
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    parsed = yaml.safe_load(text[4:end])
    return parsed if isinstance(parsed, dict) else None


def _records_of_kind(kind: str) -> list[tuple[Path, dict]]:
    out: list[tuple[Path, dict]] = []
    for relative in PROJECT_ROOTS:
        root = Path.home() / "d" / relative
        if not root.exists():
            pytest.fail(
                f"project root {relative} is missing; under `-m real_projects` that FAILS "
                "rather than skips, so a shrinking corpus cannot look like a clean one"
            )
        for path in root.rglob("*.md"):
            if ".venv" in path.parts or ".worktrees" in path.parts:
                continue
            fm = _frontmatter(path)
            if fm is not None and fm.get("kind") == kind:
                out.append((path, fm))
    return out


def test_no_finding_relation_carries_an_undeclared_key():
    """The migration itself, over every finding in every project."""
    offenders = [
        (str(path), sorted(set(rel) - DECLARED_RELATION_KEYS))
        for path, fm in _records_of_kind("finding")
        for rel in (fm.get("relations") or [])
        if isinstance(rel, dict) and set(rel) - DECLARED_RELATION_KEYS
    ]
    assert offenders == []


def test_the_three_migrated_records_still_carry_their_relation():
    """The migration removed a key; it must not have removed the edge.

    Without this, deleting the whole `relations:` block would pass the test above.
    """
    by_stem = {path.stem: fm for path, fm in _records_of_kind("finding")}
    for stem in MIGRATED:
        relations = by_stem[stem].get("relations") or []
        assert len(relations) == 1, stem
        assert relations[0]["predicate"] == "sci:amends", stem
        assert relations[0]["target"].startswith("finding:"), stem


def test_the_amendment_prose_survives_in_the_body():
    """Why dropping the key lost nothing.

    Each removed `note` was a compressed restatement of that record's own `## Summary`,
    which is where the prose is actually rendered and read. This asserts the body still
    names the finding the relation amends -- so the migration is a de-duplication rather
    than a deletion of content.
    """
    by_path = {path: fm for path, fm in _records_of_kind("finding")}
    paths = {path.stem: path for path in by_path}
    for stem in MIGRATED:
        body = paths[stem].read_text().split("\n---", 1)[1]
        # The prose cites `finding:0016`, not the full id slug -- match how it is written.
        number = by_path[paths[stem]]["relations"][0]["target"].split(":", 1)[1].split("-")[0]
        assert f"finding:{number}" in body, (
            f"{stem} body no longer names the amended finding:{number}"
        )


def test_interpretation_still_carries_note_and_that_is_out_of_scope():
    """Scope, recorded as a test rather than a comment.

    19 `interpretation` records author `relations[].note` the same way. `interpretation`
    is not a tranche kind and its slice owns its own corpus, so they are deliberately
    untouched. If this count ever reaches zero, someone migrated them -- and this file
    should stop claiming they are pending.
    """
    remaining = [
        str(path)
        for path, fm in _records_of_kind("interpretation")
        for rel in (fm.get("relations") or [])
        if isinstance(rel, dict) and "note" in rel
    ]
    assert len(remaining) == 19
