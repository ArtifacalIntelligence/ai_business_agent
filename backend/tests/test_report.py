from app.report import build_report

ANALYSIS = {
    "summary": "The team planned the launch.", "participants": ["Ahmed", "Sarah"],
    "decisions": ["Launch Monday"],
    "action_items": [{"task": "Prepare report", "owner": "Ahmed", "deadline": "Friday"},
                     {"task": "Book room", "owner": None, "deadline": None}],
    "concerns": ["Assets missing"], "follow_up_needed": True, "follow_up_reason": "Review assets",
}


def test_report_is_a_pdf():
    pdf = build_report("meeting.txt", ANALYSIS, "some-model")
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000


def test_special_characters_do_not_crash():
    odd = {**ANALYSIS, "summary": "A <b>bold</b> & risky claim", "concerns": ["x < y & z > w"]}
    assert build_report("a&b.txt", odd, None).startswith(b"%PDF")


def test_minimal_analysis_works():
    assert build_report("empty.txt", {}, None).startswith(b"%PDF")