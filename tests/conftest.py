import pytest


@pytest.fixture(autouse=True)
def no_million_employee_list(tmp_path, monkeypatch):
    """Tests never read this PC's own employees.txt (Documents\\learn-million): no list unless a test writes one."""
    monkeypatch.setenv("TABLE_READER_MILLION_EMPLOYEES", str(tmp_path / "no-employees.txt"))
