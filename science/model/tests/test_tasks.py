from datetime import date

from science_model.tasks import Task, TaskCreate, TaskStatus, TaskUpdate


def test_task_model():
    t = Task(
        id="t001",
        project="seq-feats",
        title="Run baseline",
        description="Execute the baseline pipeline",
        type="analysis",
        priority="P1",
        status=TaskStatus.PROPOSED,
        blocked_by=[],
        related=[],
        created=date(2026, 3, 1),
    )
    assert t.status == "proposed"
    assert t.completed is None


def test_task_create_defaults():
    tc = TaskCreate(title="New task")
    assert tc.priority == "P2"
    assert tc.type == ""
    assert tc.description == ""


def test_task_update_partial():
    tu = TaskUpdate(status=TaskStatus.ACTIVE)
    assert tu.title is None
    assert tu.status == "active"


def test_task_has_artifacts_field():
    t = Task(id="1", title="Run analysis", artifacts=["data-package:results-01"])
    assert t.artifacts == ["data-package:results-01"]


def test_task_has_findings_field():
    t = Task(id="1", title="Run analysis", findings=["finding:f01"])
    assert t.findings == ["finding:f01"]


def test_task_artifacts_and_findings_default_empty():
    t = Task(id="1", title="Simple task")
    assert t.artifacts == []
    assert t.findings == []


def test_task_parent_defaults_to_empty_string():
    t = Task(id="t016", title="Follow-up")
    assert t.parent == ""


def test_task_parent_can_be_set():
    t = Task(id="t016", title="Follow-up", parent="task:t001")
    assert t.parent == "task:t001"


def test_task_create_and_update_parent_fields():
    tc = TaskCreate(title="Follow-up", parent="task:t001")
    tu = TaskUpdate(parent="task:t002")
    assert tc.parent == "task:t001"
    assert tu.parent == "task:t002"
