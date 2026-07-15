"""`severity_for_kind` -- the one authority the three kind-level emitters share."""

from science_tool.validate.kind_severity import severity_for_kind
from science_tool.validate.result import Severity


def test_severity_is_a_property_of_the_KIND() -> None:
    # The original incident: severity graded on `layout_version >= 3`. All five projects were
    # v3, so the gate graded NOTHING and 472 entities errored the moment the check landed. Severity
    # rides on certification, which is per KIND.
    assert severity_for_kind("hypothesis") is Severity.ERROR  # sources AND consumers certified (D5)
    assert severity_for_kind("report") is Severity.WARN  # not migrated
    assert severity_for_kind("question") is Severity.WARN
    assert severity_for_kind("interpretation") is Severity.WARN
