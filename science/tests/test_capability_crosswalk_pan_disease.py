"""The packaged crosswalk maps the pan-disease molecular capability shapes.

pan-disease introduced five raw capability shapes absent from the original
mm30/cbioportal/pai inventory. Four map to existing catalog terms; one is
dropped. Every mapping reuses a term already in the public catalog, so the
pan-disease migration needs no catalog extension (no toolkit release):

- ``{germline-variant, gwas}`` -> ``gwas-summary-statistics`` (biobank/GWAS
  association resources; the association layer, distinct from raw calls)
- ``{germline-variant, cnv}`` -> ``copy-number``
- ``{metabolomics}`` -> ``metabolomics`` (root, mirroring the gene-expression /
  proteomics / germline-variant bare roots)
- ``{metabolomics, nmr}`` -> ``metabolomics`` with ``{technology: nmr}`` kept as
  a non-identity qualifier (no ``metabolomics-nmr`` child term exists)
- ``{translation, ribo-seq}`` -> dropped: ribosome profiling has no canonical
  data-product term in the molecular catalog.
"""

from pathlib import Path

import science_tool.datasets as datasets_pkg
from science_model.data_products import load_catalog
from science_tool.datasets.capability_crosswalk import Crosswalk, Dropped, Mapped

_CROSSWALK = Path(datasets_pkg.__file__).parent / "capability_crosswalk.yaml"

# (raw shape, expected data_product, expected surviving qualifiers)
_MAPPED_SHAPES = [
    ({"assay": "germline-variant", "modality": "gwas"}, "data-product:gwas-summary-statistics", {}),
    ({"assay": "germline-variant", "modality": "cnv"}, "data-product:copy-number", {}),
    ({"assay": "metabolomics"}, "data-product:metabolomics", {}),
    ({"assay": "metabolomics", "modality": "nmr"}, "data-product:metabolomics", {"technology": "nmr"}),
]

_DROPPED_SHAPES = [
    {"assay": "translation", "modality": "ribo-seq"},
]


def _crosswalk() -> Crosswalk:
    return Crosswalk.load(_CROSSWALK, catalog_ids=set(load_catalog().by_id))


def test_pan_disease_shapes_map_to_expected_terms() -> None:
    cw = _crosswalk()
    for shape, expected_product, expected_quals in _MAPPED_SHAPES:
        result = cw.rewrite(shape)
        assert isinstance(result, Mapped), f"{shape} should map, not {type(result).__name__}"
        assert result.capability["data_product"] == expected_product, shape
        assert result.capability["qualifiers"] == expected_quals, shape


def test_pan_disease_ribo_seq_is_dropped() -> None:
    cw = _crosswalk()
    for shape in _DROPPED_SHAPES:
        result = cw.rewrite(shape)
        assert isinstance(result, Dropped), f"{shape} should drop, not {type(result).__name__}"
