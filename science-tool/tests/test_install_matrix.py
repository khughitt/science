"""Install-matrix decision table — every row of the spec's install matrix."""

import pytest

from science_tool.project_artifacts.install_matrix import Action, decide
from science_tool.project_artifacts.status import Status


@pytest.mark.parametrize(
    "status,header_present,hash_known,adopt,force_adopt,wrong_name,expected",
    [
        # spec 'install matrix' rows, in order
        (Status.MISSING, False, False, False, False, False, Action.INSTALL),
        (Status.CURRENT, True, True, False, False, False, Action.NO_OP),
        (Status.STALE, True, True, False, False, False, Action.REFUSE_SUGGEST_UPDATE),
        (Status.LOCALLY_MODIFIED, True, False, False, False, False, Action.REFUSE_LOCALLY_MODIFIED),
        # untracked + known historical hash → require --adopt
        (Status.UNTRACKED, False, True, False, False, False, Action.REFUSE_NEEDS_ADOPT),
        (Status.UNTRACKED, False, True, True, False, False, Action.ADOPT_IN_PLACE),
        # untracked + unknown hash → require --force-adopt
        (Status.UNTRACKED, False, False, False, False, False, Action.REFUSE_NEEDS_FORCE_ADOPT),
        (Status.UNTRACKED, False, False, False, True, False, Action.FORCE_ADOPT),
        # managed header for a different name
        (Status.UNTRACKED, True, True, False, False, True, Action.REFUSE_WRONG_NAME),
    ],
)
def test_install_matrix_rows(
    status: Status,
    header_present: bool,
    hash_known: bool,
    adopt: bool,
    force_adopt: bool,
    wrong_name: bool,
    expected: Action,
) -> None:
    decision = decide(
        status=status,
        header_present=header_present,
        hash_known_to_registry=hash_known,
        wrong_name_in_header=wrong_name,
        adopt=adopt,
        force_adopt=force_adopt,
    )
    assert decision.action is expected
    assert decision.reason  # non-empty
