from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

with patch("supabase.create_client", return_value=MagicMock()):
    from app import main

client = TestClient(main.app)
AUTH = {"Authorization": "Bearer test"}
USER = MagicMock(id="u1")


def action(status):
    return {"id": "a1", "status": status, "action_type": "create_task", "payload": {"title": "T"}}


@pytest.fixture
def mocks():
    with patch.object(main, "get_user", return_value=USER), \
         patch.object(main, "log_event") as log, \
         patch.object(main, "update_action", side_effect=lambda i, f: {"id": i, **f}), \
         patch.object(main, "run_action") as run, \
         patch.object(main, "claim_action", return_value=True) as claim, \
         patch.object(main, "get_action") as get:
        yield {"log": log, "run": run, "claim": claim, "get": get}


def events(m):
    return [c.args[2] for c in m["log"].call_args_list]


def test_approve_is_logged(mocks):
    mocks["get"].return_value = action("pending")
    r = client.post("/actions/a1/approve", headers=AUTH)
    assert r.status_code == 200
    assert events(mocks) == ["approved"]


def test_reject_is_logged(mocks):
    mocks["get"].return_value = action("pending")
    r = client.post("/actions/a1/reject", headers=AUTH)
    assert r.status_code == 200
    assert events(mocks) == ["rejected"]


def test_edit_is_logged(mocks):
    mocks["get"].return_value = action("pending")
    r = client.patch("/actions/a1", headers=AUTH, json={"payload": {"title": "New"}})
    assert r.status_code == 200
    assert events(mocks) == ["edited"]


def test_cannot_approve_twice(mocks):
    mocks["get"].return_value = action("approved")
    r = client.post("/actions/a1/approve", headers=AUTH)
    assert r.status_code == 409
    mocks["log"].assert_not_called()


@pytest.mark.parametrize("status", ["pending", "rejected", "failed", "executed"])
def test_execute_is_blocked_unless_approved(mocks, status):
    mocks["get"].return_value = action(status)
    r = client.post("/actions/a1/execute", headers=AUTH)
    assert r.status_code == 409
    mocks["run"].assert_not_called()
    assert events(mocks) == ["blocked"]


def test_execute_success_is_logged(mocks):
    mocks["get"].return_value = action("approved")
    mocks["run"].return_value = {"task_id": "t1"}
    r = client.post("/actions/a1/execute", headers=AUTH)
    assert r.status_code == 200
    mocks["run"].assert_called_once()
    assert events(mocks) == ["executed"]


def test_execute_failure_is_logged(mocks):
    mocks["get"].return_value = action("approved")
    mocks["run"].side_effect = main.ExecutionError("boom")
    r = client.post("/actions/a1/execute", headers=AUTH)
    assert r.status_code == 502
    assert events(mocks) == ["failed"]


def test_unexpected_error_is_logged_as_failed(mocks):
    mocks["get"].return_value = action("approved")
    mocks["run"].side_effect = RuntimeError("surprise")
    r = client.post("/actions/a1/execute", headers=AUTH)
    assert r.status_code == 500
    assert events(mocks) == ["failed"]


def test_second_click_does_not_run_twice(mocks):
    mocks["get"].return_value = action("approved")
    mocks["claim"].return_value = False
    r = client.post("/actions/a1/execute", headers=AUTH)
    assert r.status_code == 409
    mocks["run"].assert_not_called()
    assert events(mocks) == ["blocked"]