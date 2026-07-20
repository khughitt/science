"""Keep-existing must never discard canonical body content silently.

fb-2026-07-16-004 (addendum). `commons promote` offers `[k] keep existing
(overlay)` on an ExistingCanonicalConflict. On `[k]` the source's canonical
body sections are neither promoted nor preserved: `overlay_existing` writes no
canonical artifacts, and `_render_overlay` emits only `project_only_body`. The
sections are dropped with no diff, no warning, and no count.

Measured on three real cbioportal papers: 347 lines destroyed. The direction of
loss runs backwards from quality — the commons canonicals were promoted from a
thinner project's copies, so keep-existing makes the worse document win.
"""

from __future__ import annotations

from science_tool.commons.promote_body_loss import (
    BodyLossEntry,
    canonical_body_loss,
)


def test_section_absent_from_commons_is_pure_loss() -> None:
    """MartinezJimenez2020's 81-line Methods section had no counterpart at all."""
    loss = canonical_body_loss(
        source_body={"Methods": "line\n" * 81},
        existing_body={},
    )

    assert loss.entries == [
        BodyLossEntry(section="Methods", source_lines=81, existing_lines=0, disposition="dropped")
    ]
    assert loss.lines_dropped == 81
    assert loss.lines_kept == 0
    assert loss.has_loss


def test_richer_source_section_is_reported_as_a_downgrade() -> None:
    """Haigis2019's 112-line Key Findings would be replaced by the commons' 39."""
    loss = canonical_body_loss(
        source_body={"Key Findings": "line\n" * 112},
        existing_body={"Key Findings": "line\n" * 39},
    )

    assert loss.entries == [
        BodyLossEntry(
            section="Key Findings", source_lines=112, existing_lines=39, disposition="downgraded"
        )
    ]
    assert loss.lines_dropped == 112
    assert loss.lines_kept == 39


def test_shorter_source_section_is_reported_as_replaced_not_downgraded() -> None:
    """Losing content is the defect; a shorter source is still replaced, not a downgrade."""
    loss = canonical_body_loss(
        source_body={"Summary": "line\n" * 5},
        existing_body={"Summary": "line\n" * 40},
    )

    assert loss.entries[0].disposition == "replaced"
    assert loss.has_loss


def test_identical_sections_are_not_loss() -> None:
    loss = canonical_body_loss(
        source_body={"Summary": "same text\n"},
        existing_body={"Summary": "same text\n"},
    )

    assert loss.entries == []
    assert not loss.has_loss
    assert loss.lines_dropped == 0


def test_whitespace_only_difference_is_not_loss() -> None:
    loss = canonical_body_loss(
        source_body={"Summary": "  same text  \n\n"},
        existing_body={"Summary": "same text\n"},
    )

    assert not loss.has_loss


def test_empty_source_section_is_not_loss() -> None:
    """An absent or blank source section had nothing to contribute."""
    loss = canonical_body_loss(
        source_body={"Methods": "   \n"},
        existing_body={},
    )

    assert not loss.has_loss


def test_sections_only_in_commons_are_not_loss() -> None:
    """Keep-existing preserves them; they are not at risk."""
    loss = canonical_body_loss(
        source_body={},
        existing_body={"Limitations": "line\n" * 12},
    )

    assert not loss.has_loss


def test_entries_are_ordered_by_net_lines_lost() -> None:
    """Worst first, measured as source lines minus the lines replacing them.

    Methods (81 -> 0, net 81) outranks Key Findings (112 -> 39, net 73) even
    though Key Findings is the larger section: nothing replaces Methods.
    """
    loss = canonical_body_loss(
        source_body={
            "Summary": "line\n" * 10,
            "Key Findings": "line\n" * 112,
            "Methods": "line\n" * 81,
        },
        existing_body={"Key Findings": "line\n" * 39, "Summary": "line\n" * 9},
    )

    assert [entry.section for entry in loss.entries] == ["Methods", "Key Findings", "Summary"]


def test_the_measured_haigis2019_incident() -> None:
    """The real numbers from the report: 131 lines lost, 81 kept."""
    loss = canonical_body_loss(
        source_body={"Key Findings": "line\n" * 112, "Methods": "line\n" * 19},
        existing_body={"Key Findings": "line\n" * 39, "Limitations": "line\n" * 42},
    )

    assert loss.lines_dropped == 131
    assert loss.lines_kept == 39
    assert {entry.disposition for entry in loss.entries} == {"downgraded", "dropped"}
