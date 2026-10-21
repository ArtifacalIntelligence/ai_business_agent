import pytest
from unittest.mock import patch, MagicMock
from app import llm
from app.schemas import MeetingAnalysis, ActionItem


def test_valid_output_is_returned():
    expected = MeetingAnalysis(
        summary="s", decisions=["Launch Monday"],
        action_items=[ActionItem(task="Report", owner="Ahmed", deadline="Friday")])
    fake_chain = MagicMock()
    fake_chain.invoke.return_value = expected
    with patch.object(llm, "get_chain", return_value=fake_chain):
        r = llm.analyze_text("any text")
    assert r.action_items[0].owner == "Ahmed"


def test_failure_raises_clear_error():
    fake_chain = MagicMock()
    fake_chain.invoke.side_effect = Exception("boom")
    with patch.object(llm, "get_chain", return_value=fake_chain), \
         patch.object(llm.time, "sleep"):
        with pytest.raises(RuntimeError):
            llm.analyze_text("any text", retries=2)