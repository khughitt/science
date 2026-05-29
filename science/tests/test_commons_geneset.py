from __future__ import annotations

import pytest

from science_tool.commons.geneset import (
    GENESET_MEMBER_KEY_COLUMN,
    GenesetCollectionError,
    parse_geneset_rows,
)


def test_member_key_column_constant() -> None:
    assert GENESET_MEMBER_KEY_COLUMN == "set_key"


def test_parse_valid_rows() -> None:
    rows = parse_geneset_rows(
        [
            {
                "set_key": "R-HSA-1",
                "name": "Cell cycle",
                "member_ids": "HGNC:1;HGNC:2",
                "source_class": "reference",
                "dataset_usage": '[{"ref":"dataset:study-a","role":"set_definition_source","overlap":"full"}]',
                "source_pmids": "12345;PMID:67890",
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0].set_key == "R-HSA-1"
    assert rows[0].member_ids == ("HGNC:1", "HGNC:2")
    assert rows[0].n_members == 2
    assert rows[0].dataset_usage[0]["role"] == "set_definition_source"
    assert rows[0].source_pmids == ("12345", "PMID:67890")


def test_semicolon_lists_allow_surrounding_whitespace() -> None:
    rows = parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": "HGNC:1; HGNC:2"}])

    assert rows[0].member_ids == ("HGNC:1", "HGNC:2")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("member_ids", "HGNC:1;;HGNC:2"),
        ("member_ids", "HGNC:1; ;HGNC:2"),
        ("source_pmids", "123;;456"),
    ],
)
def test_semicolon_lists_reject_empty_tokens(field: str, value: str) -> None:
    row = {"set_key": "A", "name": "one", "member_ids": "HGNC:1", field: value}

    with pytest.raises(GenesetCollectionError, match=rf"{field}.*empty token"):
        parse_geneset_rows([row])


def test_blank_optional_source_pmids_parse_as_empty_tuple() -> None:
    rows = parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": "HGNC:1", "source_pmids": "  "}])

    assert rows[0].source_pmids == ()


def test_duplicate_set_key_errors() -> None:
    with pytest.raises(GenesetCollectionError, match="row 2: duplicate set_key"):
        parse_geneset_rows(
            [
                {"set_key": "A", "name": "one", "member_ids": "HGNC:1"},
                {"set_key": "A", "name": "two", "member_ids": "HGNC:2"},
            ]
        )


def test_blank_member_ids_errors() -> None:
    with pytest.raises(GenesetCollectionError, match="member_ids"):
        parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": ""}])


def test_missing_required_columns_error() -> None:
    with pytest.raises(GenesetCollectionError, match="missing required columns \\['member_ids'\\]"):
        parse_geneset_rows([{"set_key": "A", "name": "one"}])


def test_dataset_usage_rejects_invalid_json_syntax() -> None:
    with pytest.raises(GenesetCollectionError, match="dataset_usage is not valid JSON"):
        parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": "HGNC:1", "dataset_usage": "["}])


def test_dataset_usage_must_be_json_list() -> None:
    with pytest.raises(GenesetCollectionError, match="dataset_usage"):
        parse_geneset_rows(
            [{"set_key": "A", "name": "one", "member_ids": "HGNC:1", "dataset_usage": '{"ref":"dataset:x"}'}]
        )


def test_dataset_usage_accepts_full_canonical_role_vocabulary() -> None:
    rows = parse_geneset_rows(
        [
            {
                "set_key": "A",
                "name": "one",
                "member_ids": "HGNC:1",
                "dataset_usage": '[{"ref":"dataset:x","role":"training"}]',
            }
        ]
    )
    assert rows[0].dataset_usage[0]["role"] == "training"


def test_dataset_usage_rejects_noncanonical_role() -> None:
    with pytest.raises(GenesetCollectionError, match="role"):
        parse_geneset_rows(
            [
                {
                    "set_key": "A",
                    "name": "one",
                    "member_ids": "HGNC:1",
                    "dataset_usage": '[{"ref":"dataset:x","role":"made_up"}]',
                }
            ]
        )


def test_invalid_source_class_errors() -> None:
    with pytest.raises(GenesetCollectionError, match="source_class"):
        parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": "HGNC:1", "source_class": "curated"}])


def test_derived_source_class_requires_derived_kind() -> None:
    with pytest.raises(GenesetCollectionError, match="derived_kind"):
        parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": "HGNC:1", "source_class": "derived"}])


def test_derived_source_class_accepts_valid_derived_kind() -> None:
    rows = parse_geneset_rows(
        [
            {
                "set_key": "A",
                "name": "one",
                "member_ids": "HGNC:1",
                "source_class": "derived",
                "derived_kind": "model_output",
            }
        ]
    )

    assert rows[0].source_class == "derived"
    assert rows[0].derived_kind == "model_output"
