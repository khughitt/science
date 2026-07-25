"""Ground the commons-ownership discriminator against a real commons merge.

The synthetic unit tests inject ``entity_source_adapters[id] == "commons-merged"``
onto a bare tmp project (see ``test_evidence.py``). That proves the projection
*logic* but hardcodes the adapter string — if a real commons merge ever tagged
borrowed datasets under a different adapter, those unit tests would stay green
while ``project_evidence`` silently misclassified every commons dataset as
project-owned. This ``real_projects`` test closes that gap: it asserts the string
the discriminator keys on is the one a real merge actually produces, and that the
projection survives a real commons-consuming project without a spurious abort.

health-meta is the designated commons consumer: it borrows reactome,
gene-crosswalk-hgnc, ccle-proteomics, and uk-biobank from science-commons.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.sources import load_project_sources
from science_tool.skills_coverage.evidence import _COMMONS_ADAPTER, project_evidence

_HEALTH_META = Path.home() / "d" / "health" / "meta"


@pytest.mark.real_projects
def test_health_meta_commons_datasets_are_grounded_and_not_owned() -> None:
    if not (_HEALTH_META / "science.yaml").is_file():
        pytest.skip(f"health-meta not present at {_HEALTH_META}")

    # include_commons=True mirrors the production scan (scan.py). health-meta's
    # borrowed refs resolve only through commons, so this is also the load path
    # the coverage command exercises.
    sources = load_project_sources(_HEALTH_META, include_commons=True)
    adapters = sources.entity_source_adapters

    commons_datasets = {
        entity.canonical_id
        for entity in sources.entities
        if entity.kind == "dataset"
        and adapters.get(entity.canonical_id) == _COMMONS_ADAPTER
    }
    assert commons_datasets, (
        f"expected health-meta to carry datasets tagged {_COMMONS_ADAPTER!r}; "
        "the commons-ownership discriminator's grounding assumption is stale"
    )

    # The real commons-consuming project projects without raising. A commons
    # dataset whose data_product falls off the catalog must be skipped, not
    # abort the scan — one commons typo cannot poison every consumer.
    evidence = project_evidence("health-meta", sources)

    # No commons dataset is ever charged as this project's coverage debt:
    # commons term usages carry owned=False, and commons datasets never appear
    # as untagged (project-owned-but-unmapped) usages.
    for usage in evidence.term_usages:
        if usage.dataset_ref in commons_datasets:
            assert not usage.owned, (
                f"commons dataset {usage.dataset_ref} projected as owned"
            )
    for usage in evidence.untagged_usages:
        assert usage.dataset_ref not in commons_datasets, (
            f"commons dataset {usage.dataset_ref} surfaced as project unmapped debt"
        )
