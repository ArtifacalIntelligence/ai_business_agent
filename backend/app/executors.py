import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


class ExecutionError(Exception):
    pass


def call_n8n(path: str, body: dict) -> dict:
    base = os.getenv("N8N_BASE_URL", "http://localhost:5678/webhook")
    try:
        r = requests.post(f"{base}/{path}", json=body, timeout=60)
    except requests.RequestException as e:
        raise ExecutionError(f"Could not reach n8n: {e}")
    if r.status_code >= 400:
        raise ExecutionError(f"n8n returned {r.status_code}: {r.text[:300]}")
    try:
        data = r.json()
    except ValueError:
        raise ExecutionError(f"n8n sent an unreadable answer: {r.text[:200]}")
    if not isinstance(data, dict) or "id" not in data:
        raise ExecutionError(
            "n8n did not confirm the action (no id in its answer). Check the Webhook node responds "
            f"with the 'Respond to Webhook' node, and check Google before retrying. Answer: {str(data)[:200]}")
    return data


def run_create_task(supabase, user_id: str, action: dict) -> dict:
    p = action["payload"]
    title = (p.get("title") or "").strip()
    if not title:
        raise ExecutionError("Task title is empty")
    row = supabase.table("tasks").insert({
        "user_id": user_id, "action_id": action["id"], "title": title,
        "owner": p.get("owner"), "deadline": p.get("deadline"),
    }).execute().data[0]
    return {"task_id": row["id"]}


def build_meeting_body(p: dict) -> dict:
    if not p.get("start"):
        raise ExecutionError("Pick a date and time for the meeting first")
    try:
        tz = ZoneInfo(os.getenv("TIMEZONE", "UTC"))
    except ZoneInfoNotFoundError:
        raise ExecutionError("TIMEZONE in .env is not a valid timezone name (example: Europe/London)")
    try:
        start = datetime.fromisoformat(p["start"]).replace(tzinfo=tz)
    except ValueError:
        raise ExecutionError(f"Invalid start time: {p['start']}")
    if start < datetime.now(tz):
        raise ExecutionError("The meeting time is in the past. Edit the date and time.")
    end = start + timedelta(minutes=int(p.get("duration_minutes", 30)))
    attendees = [a for a in p.get("attendees", []) if a]
    parts = []
    if p.get("reason"):
        parts.append(p["reason"])
    if attendees:
        parts.append("Attendees: " + ", ".join(attendees))
    parts.append("Created by AI Business Operations Agent after human approval.")
    return {"title": p.get("title") or "Follow-up meeting", "description": "\n\n".join(parts),
            "start": start.isoformat(), "end": end.isoformat(), "attendees": attendees}


def run_schedule_meeting(p: dict) -> dict:
    return call_n8n("schedule-meeting", build_meeting_body(p))


def run_send_email(p: dict) -> dict:
    to = (p.get("to") or "").strip()
    if not to or "@" not in to:
        raise ExecutionError("Recipient email is missing or invalid")
    allow = [e.strip().lower() for e in os.getenv("EMAIL_ALLOWLIST", "").split(",") if e.strip()]
    if allow and to.lower() not in allow:
        raise ExecutionError(f"{to} is not in EMAIL_ALLOWLIST (safety guard)")
    return call_n8n("send-email", {
        "to": to, "subject": p.get("subject") or "Meeting summary", "body": p.get("body") or ""})


def run_action(supabase, user_id: str, action: dict) -> dict:
    t, p = action["action_type"], action["payload"]
    if t == "create_task":
        return run_create_task(supabase, user_id, action)
    if t == "schedule_meeting":
        return run_schedule_meeting(p)
    if t == "send_email":
        return run_send_email(p)
    raise ExecutionError(f"Unknown action type: {t}")