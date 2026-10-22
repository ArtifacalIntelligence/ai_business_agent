import pytest
from unittest.mock import patch, MagicMock
from app import executors


def fake_response(status, data):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = data
    m.text = str(data)
    return m


def test_email_without_recipient_fails():
    with pytest.raises(executors.ExecutionError):
        executors.run_send_email({"to": "", "subject": "s", "body": "b"})


def test_email_blocked_by_allowlist(monkeypatch):
    monkeypatch.setenv("EMAIL_ALLOWLIST", "me@example.com")
    with pytest.raises(executors.ExecutionError):
        executors.run_send_email({"to": "other@example.com", "subject": "s", "body": "b"})


def test_n8n_unconfirmed_answer_is_rejected():
    with patch.object(executors.requests, "post",
                      return_value=fake_response(200, {"message": "Workflow was started"})):
        with pytest.raises(executors.ExecutionError):
            executors.call_n8n("send-email", {})


def test_n8n_error_status_is_rejected():
    with patch.object(executors.requests, "post", return_value=fake_response(500, {"x": 1})):
        with pytest.raises(executors.ExecutionError):
            executors.call_n8n("send-email", {})


def test_n8n_success_returns_data():
    with patch.object(executors.requests, "post", return_value=fake_response(200, {"id": "abc"})):
        assert executors.call_n8n("x", {})["id"] == "abc"


def test_meeting_end_is_after_start():
    body = executors.build_meeting_body(
        {"title": "t", "start": "2099-01-01T10:00", "duration_minutes": 45, "attendees": []})
    assert body["end"] > body["start"]


def test_meeting_in_the_past_is_rejected():
    with pytest.raises(executors.ExecutionError):
        executors.build_meeting_body({"start": "2000-01-01T10:00"})


def test_meeting_without_start_is_rejected():
    with pytest.raises(executors.ExecutionError):
        executors.build_meeting_body({"title": "t"})


def test_create_task_inserts_a_row():
    sb = MagicMock()
    sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "t1"}]
    out = executors.run_create_task(sb, "u1", {"id": "a1", "payload": {"title": "Do it"}})
    assert out == {"task_id": "t1"}


def test_create_task_with_empty_title_fails():
    with pytest.raises(executors.ExecutionError):
        executors.run_create_task(MagicMock(), "u1", {"id": "a1", "payload": {"title": "  "}})