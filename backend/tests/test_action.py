import pytest
from app.actions import build_proposals, check_executable, ensure_analyzable

RESULT = {
    "summary": "Team planned the launch.", "decisions": ["Launch Monday"],
    "action_items": [{"task": "Prepare report", "owner": "Ahmed", "deadline": "Friday"},
                     {"task": "Book room", "owner": None, "deadline": None}],
    "concerns": ["Assets missing"], "follow_up_needed": True, "follow_up_reason": "Review assets",
}


def test_one_task_per_action_item():
    tasks = [p for p in build_proposals(RESULT) if p["action_type"] == "create_task"]
    assert len(tasks) == 2
    assert tasks[0]["payload"]["owner"] == "Ahmed"


def test_follow_up_creates_meeting():
    types = [p["action_type"] for p in build_proposals(RESULT)]
    assert "schedule_meeting" in types


def test_no_follow_up_no_meeting():
    types = [p["action_type"] for p in build_proposals({**RESULT, "follow_up_needed": False})]
    assert "schedule_meeting" not in types


def test_email_draft_is_created_with_empty_recipient():
    email = [p for p in build_proposals(RESULT) if p["action_type"] == "send_email"][0]
    assert email["payload"]["to"] == ""
    assert "Prepare report" in email["payload"]["body"]


@pytest.mark.parametrize("status", ["pending", "rejected", "executing" "executed", "failed"])
def test_only_approved_actions_can_run(status):
    with pytest.raises(ValueError):
        check_executable({"status": status})


def test_approved_action_can_run():
    check_executable({"status": "approved"})

def test_too_short_text_is_not_sent_to_ai():
    with pytest.raises(ValueError):
        ensure_analyzable("hello")


def test_normal_text_is_accepted():
    ensure_analyzable("x" * 60)