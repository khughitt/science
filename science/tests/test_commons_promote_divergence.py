"""Unit tests for _canonical_fields_equal_or_subset (t063).

Tests the pure helper that compares source-derived canonical fields+body against
the already-committed commons canonical entity to decide equal / subset / divergent.
"""

from __future__ import annotations

import pytest

from science_tool.commons.promote import _canonical_fields_equal_or_subset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmp(
    source_fields: dict,
    source_body: dict,
    existing_fields: dict,
    existing_body: dict,
) -> tuple[str, list[str]]:
    """Thin wrapper so tests don't have to cast Mapping."""
    return _canonical_fields_equal_or_subset(
        source_fields, source_body, existing_fields, existing_body
    )


# ---------------------------------------------------------------------------
# Equal
# ---------------------------------------------------------------------------


class TestEqual:
    def test_identical_fields_and_body(self):
        """Identical frontmatter + body → equal."""
        fields = {"title": "My Paper", "year": 2023, "doi": "10.1/foo"}
        body = {"Abstract": "Some abstract text.", "Key Findings": "- Finding 1"}
        assert _cmp(fields, body, fields, body) == ("equal", [])

    def test_title_differs_only_by_case(self):
        """Title is compared case-insensitively; case-only difference → not divergent."""
        src_fields = {"title": "The cancer process"}
        ex_fields = {"title": "THE CANCER PROCESS"}
        assert _cmp(src_fields, {}, ex_fields, {}) == ("equal", [])

    def test_list_order_differs_but_membership_equal(self):
        """Authors list compared as multiset; order difference alone → not divergent."""
        src = {"authors": ["Alice", "Bob"]}
        ex = {"authors": ["Bob", "Alice"]}
        result = _cmp(src, {}, ex, {})
        assert result[0] in ("equal", "subset")
        assert result[1] == []

    def test_body_section_differs_only_by_surrounding_whitespace(self):
        """Body values are strip()-compared; whitespace-only difference → not divergent."""
        src_body = {"Abstract": "  Some abstract text.  "}
        ex_body = {"Abstract": "Some abstract text."}
        assert _cmp({}, src_body, {}, ex_body) == ("equal", [])

    def test_empty_source_and_empty_existing(self):
        """All empty → equal."""
        assert _cmp({}, {}, {}, {}) == ("equal", [])

    def test_string_field_strip_only(self):
        """Non-title string fields are compared after strip (case-sensitive)."""
        src = {"venue": "  Nature  "}
        ex = {"venue": "Nature"}
        assert _cmp(src, {}, ex, {}) == ("equal", [])


# ---------------------------------------------------------------------------
# Subset
# ---------------------------------------------------------------------------


class TestSubset:
    def test_source_omits_field_existing_has(self):
        """Existing has pmid, source doesn't → subset (source is poorer)."""
        src_fields = {"title": "My Paper", "doi": "10.1/foo"}
        ex_fields = {"title": "My Paper", "doi": "10.1/foo", "pmid": "12345"}
        assert _cmp(src_fields, {}, ex_fields, {}) == ("subset", [])

    def test_source_empty_doi_while_existing_has_real_doi(self):
        """source doi='' counts as absent; existing richer → subset."""
        src_fields = {"title": "My Paper", "doi": ""}
        ex_fields = {"title": "My Paper", "doi": "10.1/foo"}
        assert _cmp(src_fields, {}, ex_fields, {}) == ("subset", [])

    def test_source_none_field_while_existing_present(self):
        """source doi=None counts as absent; existing richer → subset."""
        src_fields = {"title": "My Paper", "doi": None}
        ex_fields = {"title": "My Paper", "doi": "10.1/foo"}
        assert _cmp(src_fields, {}, ex_fields, {}) == ("subset", [])

    def test_source_empty_list_while_existing_has_list(self):
        """source tags=[] counts as absent; existing richer → subset."""
        src_fields = {"title": "My Paper", "tags": []}
        ex_fields = {"title": "My Paper", "tags": ["a", "b"]}
        assert _cmp(src_fields, {}, ex_fields, {}) == ("subset", [])

    def test_source_omits_body_section_existing_has(self):
        """Source has no body section that existing has → subset."""
        ex_body = {"Abstract": "Some abstract."}
        assert _cmp({}, {}, {}, ex_body) == ("subset", [])

    def test_shared_values_equal_source_missing_one_field(self):
        """All shared values match; source just has fewer keys → subset."""
        src = {"title": "T", "year": 2020}
        ex = {"title": "T", "year": 2020, "pmid": "999"}
        assert _cmp(src, {}, ex, {}) == ("subset", [])


# ---------------------------------------------------------------------------
# Divergent
# ---------------------------------------------------------------------------


class TestDivergent:
    def test_non_title_string_field_differs_by_case(self):
        """Non-title fields are case-sensitive; different case → divergent."""
        src = {"venue": "nature"}
        ex = {"venue": "Nature"}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["venue"])

    def test_source_has_field_existing_lacks(self):
        """Source has doi, existing absent → source value diverges."""
        src = {"doi": "10.1/foo"}
        ex = {}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["doi"])

    def test_field_value_differs(self):
        """Same key, different value → divergent."""
        src = {"year": 2021}
        ex = {"year": 2022}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["year"])

    def test_list_membership_differs(self):
        """Author list has different membership → divergent."""
        src = {"authors": ["Alice", "Bob"]}
        ex = {"authors": ["Alice", "Carol"]}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["authors"])

    def test_body_section_text_differs_beyond_whitespace(self):
        """Body section with substantively different text → divergent."""
        src_body = {"Abstract": "Original abstract."}
        ex_body = {"Abstract": "A completely different abstract."}
        result = _cmp({}, src_body, {}, ex_body)
        assert result == ("divergent", ["Abstract"])

    def test_multiple_diverging_fields_sorted(self):
        """Multiple diverging fields → all listed, sorted."""
        src = {"doi": "10.1/src", "title": "Source Title", "year": 2021}
        ex = {"doi": "10.1/ex", "title": "Existing Title", "year": 2021}
        result = _cmp(src, {}, ex, {})
        verdict, fields = result
        assert verdict == "divergent"
        assert fields == sorted(fields)
        assert "doi" in fields
        assert "title" in fields  # case-insensitive compare: different casefolded values

    def test_title_diverges_when_content_differs(self):
        """Title that genuinely differs (not just case) → divergent."""
        src = {"title": "Source title about cancer"}
        ex = {"title": "Existing title about aging"}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["title"])

    def test_list_count_differs(self):
        """Authors list has different count (superset, not just reordering) → divergent."""
        src = {"authors": ["Alice", "Bob", "Carol"]}
        ex = {"authors": ["Alice", "Bob"]}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["authors"])

    def test_body_and_field_diverge_together(self):
        """Both a frontmatter field and a body section diverge → all reported, sorted."""
        src_fields = {"year": 2021}
        src_body = {"Abstract": "New text."}
        ex_fields = {"year": 2022}
        ex_body = {"Abstract": "Old text."}
        verdict, fields = _cmp(src_fields, src_body, ex_fields, ex_body)
        assert verdict == "divergent"
        assert "Abstract" in fields
        assert "year" in fields
        assert fields == sorted(fields)

    def test_source_body_section_existing_has_same_with_whitespace(self):
        """Source body section matches existing after strip → not divergent."""
        src_body = {"Key Findings": "\n- Finding 1\n"}
        ex_body = {"Key Findings": "- Finding 1"}
        assert _cmp({}, src_body, {}, ex_body) == ("equal", [])

    def test_list_element_whitespace_normalization(self):
        """List elements are stripped before multiset compare → whitespace differences ok."""
        src = {"authors": [" Alice ", "Bob"]}
        ex = {"authors": ["Alice", " Bob "]}
        result = _cmp(src, {}, ex, {})
        assert result[0] in ("equal", "subset")

    def test_source_empty_string_body_section_not_divergent_when_existing_has_it(self):
        """Source body section = '' counts as absent → existing richer → subset."""
        src_body = {"Abstract": ""}
        ex_body = {"Abstract": "Some abstract."}
        assert _cmp({}, src_body, {}, ex_body) == ("subset", [])

    def test_list_duplicate_count_diverges(self):
        """Same membership set but different duplicate counts → divergent (multiset differs)."""
        src = {"authors": ["a", "a", "b"]}
        ex = {"authors": ["a", "b", "b"]}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["authors"])

    def test_type_mismatch_int_vs_bool_diverges(self):
        """Source int vs existing bool → incompatible types diverge, not equal."""
        src = {"flag": 1}
        ex = {"flag": True}
        result = _cmp(src, {}, ex, {})
        assert result == ("divergent", ["flag"])
