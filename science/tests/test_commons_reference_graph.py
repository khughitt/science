from __future__ import annotations

import pytest

from science_tool.commons.reference_graph import (
    REFERENCE_GRAPH_FORMATS,
    REFERENCE_GRAPH_PROFILE_TOKEN,
    REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS,
    ReferenceGraphCollectionError,
    is_reference_graph_frontmatter,
    is_reference_graph_member_frontmatter,
    parse_edge_rows,
    parse_node_index_rows,
)


def _node_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "member_key": "MONDO:1",
        "member_kind": "term",
        "label": "one",
        "status": "active",
        "replaced_by": "",
        "dataset_usage": "[]",
    }
    row.update(overrides)
    return row


def _edge_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "subject": "A",
        "predicate": "is_a",
        "object": "B",
        "evidence": "",
        "dataset_usage": "[]",
    }
    row.update(overrides)
    return row


def test_reference_graph_formats_include_obograph_json() -> None:
    assert "obograph_json" in REFERENCE_GRAPH_FORMATS


def test_reference_graph_profile_token() -> None:
    assert REFERENCE_GRAPH_PROFILE_TOKEN == "+bio.reference_graph/"


def test_required_node_columns() -> None:
    assert REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS == frozenset(
        {"member_key", "member_kind", "label", "status", "replaced_by", "dataset_usage"}
    )


def test_reference_graph_frontmatter_matches_collection_profile_only() -> None:
    assert is_reference_graph_frontmatter(
        {
            "kind": "dataset",
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
        }
    )
    assert not is_reference_graph_frontmatter(
        {
            "kind": "dataset",
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        }
    )
    assert not is_reference_graph_frontmatter(
        {"kind": "analysis", "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0"}
    )


def test_reference_graph_member_frontmatter_matches_member_profile() -> None:
    assert is_reference_graph_member_frontmatter(
        {
            "type": "dataset",
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        }
    )
    assert not is_reference_graph_member_frontmatter(
        {"type": "dataset", "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0"}
    )


def test_parse_valid_node_rows() -> None:
    rows = parse_node_index_rows(
        [
            {
                "member_key": "MONDO:0005148",
                "member_kind": "term",
                "label": "multiple myeloma",
                "status": "active",
                "replaced_by": "",
                "dataset_usage": '[{"ref":"dataset:ordo","role":"upstream","overlap":"partial"}]',
            },
            {
                "member_key": "MONDO:obsolete",
                "member_kind": "term",
                "label": "old label",
                "status": "deprecated",
                "replaced_by": "MONDO:0005148",
                "dataset_usage": "[]",
            },
        ]
    )

    assert rows[0].member_key == "MONDO:0005148"
    assert rows[0].member_kind == "term"
    assert rows[0].status == "active"
    assert rows[0].dataset_usage[0]["role"] == "upstream"
    assert rows[1].replaced_by == ("MONDO:0005148",)


def test_parse_node_rows_counts_deprecated_as_addressable() -> None:
    rows = parse_node_index_rows(
        [
            {
                "member_key": "MONDO:active",
                "member_kind": "term",
                "label": "active",
                "status": "active",
                "replaced_by": "",
                "dataset_usage": "[]",
            },
            {
                "member_key": "MONDO:deprecated",
                "member_kind": "term",
                "label": "deprecated",
                "status": "deprecated",
                "replaced_by": "MONDO:active",
                "dataset_usage": "[]",
            },
        ]
    )

    assert len(rows) == 2
    assert {row.member_key for row in rows} == {"MONDO:active", "MONDO:deprecated"}


def test_duplicate_member_key_errors() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="row 2: duplicate member_key"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": "[]",
                },
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "again",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": "[]",
                },
            ]
        )


def test_missing_node_column_errors() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="missing required columns \\['dataset_usage'\\]"):
        parse_node_index_rows(
            [{"member_key": "MONDO:1", "member_kind": "term", "label": "one", "status": "active", "replaced_by": ""}]
        )


@pytest.mark.parametrize("field", ["member_key", "member_kind", "label"])
def test_blank_node_required_text_fields_error(field: str) -> None:
    with pytest.raises(ReferenceGraphCollectionError, match=f"blank {field}"):
        parse_node_index_rows([_node_row(**{field: "  "})])


def test_invalid_status_errors() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="status"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "obsolete",
                    "replaced_by": "",
                    "dataset_usage": "[]",
                }
            ]
        )


def test_replaced_by_rejects_empty_tokens() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="replaced_by contains an empty token"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "deprecated",
                    "replaced_by": "MONDO:2;;MONDO:3",
                    "dataset_usage": "[]",
                }
            ]
        )


def test_replaced_by_rejects_duplicate_tokens() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="replaced_by.*duplicate"):
        parse_node_index_rows([_node_row(status="deprecated", replaced_by="MONDO:2;MONDO:2")])


def test_dataset_usage_must_be_json_list() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="dataset_usage must be a JSON list"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": '{"ref":"dataset:x"}',
                }
            ]
        )


@pytest.mark.parametrize(
    ("dataset_usage", "message"),
    [
        ('[{"ref":"study:x","role":"upstream"}]', "dataset:"),
        ('["dataset:x"]', "entry is not an object"),
        ('[{"ref":"dataset:x","role":"upstream","overlap":"made_up"}]', "overlap"),
    ],
)
def test_dataset_usage_rejects_malformed_entries(dataset_usage: str, message: str) -> None:
    with pytest.raises(ReferenceGraphCollectionError, match=message):
        parse_node_index_rows([_node_row(dataset_usage=dataset_usage)])


def test_dataset_usage_rejects_invalid_role() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="role"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": '[{"ref":"dataset:x","role":"made_up"}]',
                }
            ]
        )


def test_parse_valid_edge_rows() -> None:
    rows = parse_edge_rows(
        [
            {
                "subject": "MONDO:0005148",
                "predicate": "is_a",
                "object": "MONDO:0000001",
                "evidence": "",
                "dataset_usage": '[{"ref":"dataset:ordo","role":"upstream"}]',
            }
        ]
    )

    assert rows[0].subject == "MONDO:0005148"
    assert rows[0].predicate == "is_a"
    assert rows[0].object == "MONDO:0000001"
    assert rows[0].dataset_usage[0]["ref"] == "dataset:ordo"


def test_edge_rows_trim_and_preserve_nonblank_evidence() -> None:
    rows = parse_edge_rows([_edge_row(evidence="  ECO:0000269  ")])

    assert rows[0].evidence == "ECO:0000269"


def test_edge_rows_reject_missing_required_columns() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="missing required columns \\['object'\\]"):
        parse_edge_rows([{"subject": "A", "predicate": "is_a", "evidence": "", "dataset_usage": "[]"}])


@pytest.mark.parametrize("field", ["subject", "predicate", "object"])
def test_blank_edge_required_text_fields_error(field: str) -> None:
    with pytest.raises(ReferenceGraphCollectionError, match=f"blank {field}"):
        parse_edge_rows([_edge_row(**{field: "  "})])


def test_edge_rows_allow_blank_optional_dataset_usage() -> None:
    rows = parse_edge_rows([{"subject": "A", "predicate": "is_a", "object": "B", "evidence": "", "dataset_usage": ""}])

    assert rows[0].dataset_usage == ()
