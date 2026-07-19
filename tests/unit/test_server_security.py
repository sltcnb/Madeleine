"""Path-traversal regressions for the web API's case/dataset name handling.

Requires the optional `web` extra (fastapi). Skipped automatically when it
isn't installed — see `pyproject.toml`'s `[project.optional-dependencies]`.
"""

import pytest

pytest.importorskip("fastapi", reason="server tests require the 'web' extra (fastapi)")

from fastapi import HTTPException  # noqa: E402

from mneme.api import server  # noqa: E402


@pytest.mark.parametrize("name", ["..", "../../etc", "../secret", "a/../../b", "/etc/passwd"])
def test_case_rejects_traversal(name):
    with pytest.raises(HTTPException) as exc:
        server._case(name)
    assert exc.value.status_code == 400


def test_case_rejects_empty_and_dot():
    for name in ("", "."):
        with pytest.raises(HTTPException) as exc:
            server._case(name)
        assert exc.value.status_code == 400


def test_case_accepts_plain_name(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA", tmp_path)
    case = server._case("my-case_01")
    assert case == tmp_path / "cases" / "my-case_01"


@pytest.mark.parametrize("dataset", ["../../x", "..", "../evil", "a/b", ""])
def test_dataset_name_rejects_traversal(dataset):
    with pytest.raises(HTTPException) as exc:
        server._safe_segment(dataset, "dataset name")
    assert exc.value.status_code == 400


def test_dataset_name_accepts_plain_value():
    assert server._safe_segment("windows.pslist", "dataset name") == "windows.pslist"
