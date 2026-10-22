from datetime import datetime, timedelta


def _default_meeting_start() -> str:
    t = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    return t.isoformat(timespec="minutes")


def _email_body(result: dict) -> str:
    lines = [result.get("summary", ""), ""]
    if result.get("decisions"):
        lines.append("Decisions:")
        lines += [f"- {d}" for d in result["decisions"]]
        lines.append("")
    if result.get("action_items"):
        lines.append("Action items:")
        for i in result["action_items"]:
            lines.append(f"- {i['task']} (owner: {i.get('owner') or 'not assigned'}, "
                         f"deadline: {i.get('deadline') or 'none'})")
        lines.append("")
    if result.get("concerns"):
        lines.append("Concerns:")
        lines += [f"- {c}" for c in result["concerns"]]
    return "\n".join(lines).strip()


def build_proposals(result: dict) -> list[dict]:
    """Business rules: analysis -> proposed actions. No AI call, so no quota used."""
    proposals = []
    for item in result.get("action_items", []):
        proposals.append({"action_type": "create_task", "payload": {
            "title": item["task"], "owner": item.get("owner"), "deadline": item.get("deadline")}})
    if result.get("follow_up_needed"):
        proposals.append({"action_type": "schedule_meeting", "payload": {
            "title": "Follow-up meeting", "reason": result.get("follow_up_reason"),
            "start": _default_meeting_start(), "duration_minutes": 30, "attendees": []}})
    if result.get("summary"):
        proposals.append({"action_type": "send_email", "payload": {
            "to": "", "subject": "Meeting summary", "body": _email_body(result)}})
    return proposals


def check_executable(action: dict) -> None:
    """THE APPROVAL GATE: nothing runs unless a human approved it."""
    if action["status"] != "approved":
        raise ValueError(f"Action is '{action['status']}'. Only approved actions can run.")


MIN_TEXT_CHARS = 50


def ensure_analyzable(text: str) -> None:
    """Stops tiny or empty documents from wasting one of your Gemini requests."""
    if len((text or "").strip()) < MIN_TEXT_CHARS:
        raise ValueError(
            f"This document has too little text to analyze (need at least {MIN_TEXT_CHARS} characters).")