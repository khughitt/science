from __future__ import annotations

import subprocess
import sys

from science_model.entity_schema.profile import default_profile_for_kind

from science_tool.identity_authoring import BASE_DATASET_SCHEMA_PROFILE


def test_base_dataset_profile_is_derived_not_declared() -> None:
    """The authoring default has no independent value authority.

    A literal here is a second declaration of "what profile does a new dataset get", and it
    drifted from `default_profile_for_kind` once already: the constant stayed at dataset/1.0
    when the default moved to 2.0, which would have had every commons-born scaffold re-create
    the `status: REPLACE` crash the dataset/2.0 migration exists to close.
    """
    assert BASE_DATASET_SCHEMA_PROFILE == default_profile_for_kind("dataset").render()


def test_newly_authored_datasets_default_to_the_migrated_mixin() -> None:
    assert BASE_DATASET_SCHEMA_PROFILE == "science-entity-base/1.0+dataset/2.0"


def test_identity_authoring_imports_in_clean_process() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "from science_tool.identity_authoring import build_identity_context; print('ok')"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
