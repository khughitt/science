import pytest

from science_qa.aspects import CheckSpec
from science_qa.extensions import ProjectLocalError, load_project_local


def test_load_resolves_checkspec_reference(tmp_path, monkeypatch):
    (tmp_path / "myext.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, TableContext, lambda ctx, params: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    specs = load_project_local(["myext:marker"])
    assert len(specs) == 1 and isinstance(specs[0], CheckSpec) and specs[0].check_id == "project-local/marker"


def test_bad_ref_shape_errors():
    with pytest.raises(ProjectLocalError, match="module:attr"):
        load_project_local(["noseparator"])


def test_non_checkspec_errors(tmp_path, monkeypatch):
    (tmp_path / "badext.py").write_text("marker = 123\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="not a CheckSpec"):
        load_project_local(["badext:marker"])


def test_project_local_requires_project_local_aspect(tmp_path, monkeypatch):
    (tmp_path / "badns.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('general', 'non_empty', CHECK_REQUIRED, TableContext, lambda ctx, params: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="project-local aspect"):
        load_project_local(["badns:marker"])


def test_project_local_check_id_collision_errors(tmp_path, monkeypatch):
    (tmp_path / "collision.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('project-local', 'marker', CHECK_REQUIRED, TableContext, lambda ctx, params: [])\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="collides"):
        load_project_local(["collision:marker"], reserved_check_ids={"project-local/marker"})


def test_project_local_requires_owned_missing_input_policy(tmp_path, monkeypatch):
    (tmp_path / "requires.py").write_text(
        "from science_qa.aspects import CHECK_REQUIRED, CheckSpec\n"
        "from science_qa.context import TableContext\n"
        "marker = CheckSpec('project-local', 'needs_col', CHECK_REQUIRED, TableContext, "
        "lambda ctx, params: [], requires=('x',))\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ProjectLocalError, match="requires"):
        load_project_local(["requires:marker"])
