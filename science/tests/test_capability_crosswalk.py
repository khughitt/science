import pytest
from science_tool.datasets.capability_crosswalk import (
    Crosswalk, CrosswalkError, Mapped, Dropped, Refused,
)

CAT = {"data-product:gene-expression-microarray"}


def _write(tmp_path, body):
    p = tmp_path / "cw.yaml"
    p.write_text("schema_version: \"1\"\nmappings:\n" + body)
    return p


_GOOD = (
    "  - match: {assay: gene-expression, modality: microarray}\n"
    "    data_product: data-product:gene-expression-microarray\n"
    "    qualifiers: {}\n"
    "  - match: {case_definition: who-lc}\n"
    "    out_of_scope: {disposition: drop, rationale: epidemiological facet}\n"
)


def test_maps_pair(tmp_path):
    cw = Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=CAT)
    r = cw.rewrite({"assay": "gene-expression", "modality": "microarray"})
    assert isinstance(r, Mapped) and r.capability == {
        "data_product": "data-product:gene-expression-microarray", "qualifiers": {}}


def test_out_of_scope_drop(tmp_path):
    cw = Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=CAT)
    assert isinstance(cw.rewrite({"case_definition": "who-lc"}), Dropped)


def test_refuse_disposition(tmp_path):
    body = ("  - match: {trait: x}\n"
            "    out_of_scope: {disposition: refuse, rationale: author must remodel}\n")
    cw = Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)
    assert isinstance(cw.rewrite({"trait": "x"}), Refused)


def test_unknown_shape_fails_early(tmp_path):
    cw = Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=CAT)
    with pytest.raises(CrosswalkError):
        cw.rewrite({"assay": "made-up"})


def test_rejects_empty_mappings(tmp_path):
    p = tmp_path / "cw.yaml"
    p.write_text("schema_version: \"1\"\nmappings: []\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(p, catalog_ids=CAT)


def test_rejects_duplicate_match(tmp_path):
    body = _GOOD + ("  - match: {assay: gene-expression, modality: microarray}\n"
                    "    data_product: data-product:gene-expression-microarray\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_both_data_product_and_out_of_scope(tmp_path):
    body = ("  - match: {a: b}\n"
            "    data_product: data-product:gene-expression-microarray\n"
            "    out_of_scope: {disposition: drop, rationale: x}\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_unknown_mapping_key(tmp_path):
    body = ("  - match: {a: b}\n    data_product: data-product:gene-expression-microarray\n"
            "    notes: nope\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_data_product_absent_from_catalog(tmp_path):
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=set())


def test_rejects_bad_disposition(tmp_path):
    body = "  - match: {a: b}\n    out_of_scope: {disposition: nuke, rationale: x}\n"
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_bad_schema_version(tmp_path):
    p = tmp_path / "cw.yaml"
    p.write_text("schema_version: \"2\"\nmappings:\n  - match: {a: b}\n"
                 "    out_of_scope: {disposition: drop, rationale: x}\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(p, catalog_ids=CAT)


def test_rejects_empty_match(tmp_path):
    body = "  - match: {}\n    out_of_scope: {disposition: drop, rationale: x}\n"
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_neither_data_product_nor_out_of_scope(tmp_path):
    body = "  - match: {a: b}\n"
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_invalid_qualifiers(tmp_path):
    body = ("  - match: {a: b}\n"
            "    data_product: data-product:gene-expression-microarray\n"
            "    qualifiers: {k: \"\"}\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_out_of_scope_as_bool(tmp_path):
    body = "  - match: {a: b}\n    out_of_scope: true\n"
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_empty_rationale(tmp_path):
    body = "  - match: {a: b}\n    out_of_scope: {disposition: drop, rationale: \"\"}\n"
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_qualifiers_alongside_out_of_scope(tmp_path):
    body = ("  - match: {a: b}\n"
            "    qualifiers: {k: v}\n"
            "    out_of_scope: {disposition: drop, rationale: x}\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)
