import pytest
from pydantic import ValidationError
from science_model.data_products import (
    CatalogError, build_catalog, load_catalog,
)


def _cat(terms, version="1"):
    return {"schema_version": version, "terms": terms}


def _term(tid, broader=None, assay="ge"):
    return {"id": tid, "label": tid, "assay": assay, "technology": "", "broader": broader or []}


def test_round_trip():
    cat = build_catalog(_cat([
        _term("data-product:gene-expression"),
        _term("data-product:gene-expression-bulk-rna", ["data-product:gene-expression"]),
    ]))
    assert cat.model_dump()["terms"][1]["broader"] == ["data-product:gene-expression"]


def test_rejects_bad_schema_version():
    with pytest.raises(ValidationError):
        build_catalog(_cat([], version="2"))


def test_rejects_unknown_field_on_term():
    with pytest.raises(ValidationError):
        build_catalog(_cat([{**_term("data-product:x"), "broarder": []}]))  # typo'd key


def test_rejects_malformed_id():
    with pytest.raises(ValidationError):
        build_catalog(_cat([_term("gene-expression")]))  # missing data-product: prefix


def test_rejects_empty_mappings_ok_but_empty_label():
    with pytest.raises(ValidationError):
        build_catalog(_cat([{"id": "data-product:x", "label": "", "assay": "ge",
                             "technology": "", "broader": []}]))


def test_rejects_duplicate_ids():
    with pytest.raises(CatalogError):
        build_catalog(_cat([_term("data-product:x"), _term("data-product:x")]))


def test_rejects_unresolved_broader():
    with pytest.raises(CatalogError):
        build_catalog(_cat([_term("data-product:x", ["data-product:missing"])]))


def test_rejects_self_broader():
    with pytest.raises(CatalogError):
        build_catalog(_cat([_term("data-product:x", ["data-product:x"])]))


def test_rejects_cyclic_broader():
    with pytest.raises(CatalogError):
        build_catalog(_cat([
            _term("data-product:a", ["data-product:b"]),
            _term("data-product:b", ["data-product:a"]),
        ]))


def test_descends_is_reflexive_and_transitive():
    cat = build_catalog(_cat([
        _term("data-product:root"),
        _term("data-product:mid", ["data-product:root"]),
        _term("data-product:leaf", ["data-product:mid"]),
    ]))
    assert cat.descends("data-product:leaf", "data-product:leaf")
    assert cat.descends("data-product:leaf", "data-product:root")
    assert not cat.descends("data-product:root", "data-product:leaf")


def test_packaged_catalog_loads():
    cat = load_catalog()
    assert cat.schema_version == "1"
    assert isinstance(cat.by_id, dict)
