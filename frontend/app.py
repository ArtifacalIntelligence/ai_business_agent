import os
from datetime import datetime, timedelta
import json
import requests
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from pathlib import Path
import pandas as pd
# ---------- upload----------

load_dotenv()
API = os.getenv("API_URL", "http://localhost:8000")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])

st.set_page_config(page_title="AI Business Ops Agent", layout="wide")
if "token" not in st.session_state:
    st.session_state.setdefault("acts", {})
    st.session_state.setdefault("msgs", {})
    st.session_state.token = None

TYPE_LABELS = {"create_task": "Create task",
               "schedule_meeting": "Schedule meeting (Google Calendar)",
               "send_email": "Send email (Gmail)"}
STATUS_ICONS = {"pending": "🟡", "approved": "🟢", "rejected": "⚪", "executing": "🟠", "executed": "✅", "failed": "🔴"}


def api(method: str, path: str, **kwargs):
    try:
        r = requests.request(method, f"{API}{path}", timeout=300,
                             headers={"Authorization": f"Bearer {st.session_state.token}"}, **kwargs)
    except requests.RequestException:
        st.error("Cannot reach the backend. Start it in the backend folder with: "
                 "uvicorn app.main:app --reload")
        st.stop()
    if r.status_code == 401:
        st.session_state.token = None
        st.rerun()
    return r

def detail(r) -> str:
    try:
        return r.json().get("detail", r.text)
    except Exception:
        return r.text


# ---------- Login / Signup ----------
if not st.session_state.token:
    st.title("AI Business Operations Agent")
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
    with tab_login:
        email = st.text_input("Email", key="login_email")
        pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("Log in"):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state.token = res.session.access_token
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
    with tab_signup:
        email2 = st.text_input("Email", key="su_email")
        pw2 = st.text_input("Password (min 6 characters)", type="password", key="su_pw")
        if st.button("Create account"):
            try:
                sb.auth.sign_up({"email": email2, "password": pw2})
                st.success("Account created. Now log in.")
            except Exception as e:
                st.error(f"Signup failed: {e}")
    st.stop()


# ---------- Rendering helpers ----------
def render_analysis(a: dict):
    st.markdown("#### Summary")
    st.write(a["summary"])
    if a.get("participants"):
        st.caption("Participants: " + ", ".join(a["participants"]))
    st.markdown("#### Decisions")
    for d in a["decisions"] or ["None found"]:
        st.write(f"- {d}")
    st.markdown("#### Action items")
    if a["action_items"]:
        st.table([{"Task": i["task"], "Owner": i["owner"] or "-",
                   "Deadline": i["deadline"] or "-"} for i in a["action_items"]])
    else:
        st.write("None found")
    st.markdown("#### Concerns")
    for c in a["concerns"] or ["None found"]:
        st.write(f"- {c}")
    st.markdown("#### Follow-up meeting")
    if a["follow_up_needed"]:
        st.write("Yes: " + (a.get("follow_up_reason") or ""))
    else:
        st.write("Not needed")


def parse_start(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now() + timedelta(days=1)


def card_call(action_id: str, method: str, path: str, spinner: str = "Working...", **kwargs):
    """Runs one request for one card and refreshes only that card."""
    st.session_state["msgs"].pop(action_id, None)
    with st.spinner(spinner):
        r = api(method, path, **kwargs)
    if r.ok:
        st.session_state["acts"][action_id] = r.json()
    elif r.status_code in (500, 502):  # the action ran and failed: reload its saved state
        fresh = api("GET", f"/actions/{action_id}")
        if fresh.ok:
            st.session_state["acts"][action_id] = fresh.json()
    else:
        st.session_state["msgs"][action_id] = detail(r)
    st.rerun(scope="fragment")


@st.fragment
def action_card(action_id: str):
    a = st.session_state["acts"][action_id]
    k, t, p, status = a["id"], a["action_type"], a["payload"], a["status"]
    editable = status in ("pending", "failed")
    new = dict(p)
    with st.container(border=True):
        st.markdown(f"**{TYPE_LABELS.get(t, t)}**  {STATUS_ICONS.get(status, '')} {status}")
        if t == "create_task":
            new["title"] = st.text_input("Task", p.get("title", ""), key=f"t_{k}", disabled=not editable)
            new["owner"] = st.text_input("Owner", p.get("owner") or "", key=f"o_{k}",
                                         disabled=not editable) or None
            new["deadline"] = st.text_input("Deadline", p.get("deadline") or "", key=f"d_{k}",
                                            disabled=not editable) or None
        elif t == "schedule_meeting":
            new["title"] = st.text_input("Title", p.get("title", ""), key=f"mt_{k}", disabled=not editable)
            if p.get("reason"):
                st.caption(f"Why: {p['reason']}")
            start = parse_start(p.get("start") or "")
            c1, c2, c3 = st.columns(3)
            d = c1.date_input("Date", start.date(), key=f"md_{k}", disabled=not editable)
            tm = c2.time_input("Time", start.time().replace(second=0, microsecond=0),
                               key=f"mtm_{k}", disabled=not editable)
            new["duration_minutes"] = c3.number_input(
                "Minutes", 15, 240, int(p.get("duration_minutes", 30)), step=15,
                key=f"mdu_{k}", disabled=not editable)
            new["start"] = datetime.combine(d, tm).isoformat(timespec="minutes")
            emails = st.text_input("Attendee emails (comma separated)",
                                   ", ".join(p.get("attendees", [])), key=f"ma_{k}",
                                   disabled=not editable)
            new["attendees"] = [e.strip() for e in emails.split(",") if e.strip()]
        else:
            new["to"] = st.text_input("To (email)", p.get("to", ""), key=f"et_{k}", disabled=not editable)
            new["subject"] = st.text_input("Subject", p.get("subject", ""), key=f"es_{k}",
                                           disabled=not editable)
            new["body"] = st.text_area("Message", p.get("body", ""), height=220, key=f"eb_{k}",
                                       disabled=not editable)

        res = a.get("result") or {}
        if status == "executed":
            msg = "Done."
            if res.get("htmlLink"):
                msg += f" [Open event]({res['htmlLink']})"
            st.success(msg)
        if status == "failed":
            st.error(res.get("error", "Failed"))
        if status == "executing":
            st.warning("This action is running, or was interrupted. Check Google before retrying.")
        if st.session_state["msgs"].get(k):
            st.error(st.session_state["msgs"][k])

        if editable:
            c1, c2, c3 = st.columns(3)
            if c1.button("Save edits", key=f"sv_{k}"):
                card_call(k, "PATCH", f"/actions/{k}", json={"payload": new})
            if c2.button("Approve & run", key=f"ap_{k}", type="primary"):
                card_call(k, "POST", f"/actions/{k}/approve-and-run",
                          spinner="Running... please wait for the result before clicking another card.",
                          json={"payload": new})
            if c3.button("Reject", key=f"rj_{k}"):
                card_call(k, "POST", f"/actions/{k}/reject")


def documents_page():
    st.title("Documents")
    if st.session_state.get("flash"):
        st.error(st.session_state.pop("flash"))

    st.subheader("Upload a document, transcript or meeting audio")
    uploaded = st.file_uploader("TXT, PDF, DOCX, MP3, WAV, M4A",
                                type=["txt", "pdf", "docx", "mp3", "wav", "m4a"])
    if uploaded and st.button("Upload"):
        if uploaded.size > 4_000_000:
            st.error("This online demo accepts files up to about 4 MB. Please use a smaller file.")
        else:
            with st.spinner("Reading the file (audio can take a few minutes)..."):
                r = api("POST", "/documents", files={"file": (uploaded.name, uploaded.getvalue())})
            if r.ok:
                st.success("Uploaded!")
            else:
                st.error(detail(r))

    r = api("GET", "/documents")
    if not r.ok:
        st.error(detail(r))
        return
    docs = r.json()
    if not docs:
        st.info("No documents yet. Upload one above.")
        return

    st.subheader("Your documents")
    labels = {d["id"]: f"{d['filename']}  ({d['created_at'][:10]})" for d in docs}
    doc_id = st.selectbox("Choose a document", list(labels), format_func=lambda i: labels[i])

    text = api("GET", f"/documents/{doc_id}").json()["extracted_text"]
    st.caption(f"{len(text):,} characters extracted. The AI reads the full text.")
    st.text(text[:1500])
    with st.expander("Show more of the extracted text"):
        st.text(text[:20000])

    if st.button("Analyze with AI", key=f"an_{doc_id}"):
        with st.spinner("AI is reading the document..."):
            ar = api("POST", f"/documents/{doc_id}/analyze")
        if not ar.ok:
            st.error(detail(ar))

    latest = api("GET", f"/documents/{doc_id}/analysis").json()
    if latest.get("result"):
        st.divider()
        st.caption(f"Analyzed with: {latest.get('model')}")
        render_analysis(latest["result"])
        pdfs = st.session_state.setdefault("pdfs", {})
        if st.button("Create PDF report", key=f"pdfb_{doc_id}"):
            pr = api("GET", f"/documents/{doc_id}/report")
            if pr.ok:
                pdfs[doc_id] = pr.content
            else:
                st.error(detail(pr))
        if doc_id in pdfs:
            st.download_button("Download PDF report", pdfs[doc_id], file_name="meeting_report.pdf",
                               mime="application/pdf", key=f"pdfd_{doc_id}")

        st.divider()
        st.markdown("### Recommended actions")
        acts = api("GET", f"/documents/{doc_id}/actions").json()
        if not acts:
            if st.button("Generate recommendations", key=f"rec_{doc_id}"):
                rr = api("POST", f"/documents/{doc_id}/recommend")
                if not rr.ok:
                    st.session_state["flash"] = detail(rr)
                st.rerun()
        for a in acts:
            st.session_state["acts"][a["id"]] = a
            action_card(a["id"])

def tasks_page():
    st.title("Tasks")
    tasks = api("GET", "/tasks").json()
    if not tasks:
        st.info("No tasks yet. Approve a 'Create task' action and it will appear here.")
    for t in tasks:
        done = t["status"] == "done"
        c1, c2 = st.columns([5, 1])
        title = f"~~**{t['title']}**~~" if done else f"**{t['title']}**"
        c1.markdown(f"{title}  \nOwner: {t['owner'] or '-'} · Deadline: {t['deadline'] or '-'}")
        if c2.button("Reopen" if done else "Mark done", key=f"tk_{t['id']}"):
            api("PATCH", f"/tasks/{t['id']}", json={"status": "todo" if done else "done"})
            st.rerun()

def audit_page():
    st.title("Audit log")
    st.caption("Every recommendation, approval and execution, newest first. Times are UTC.")
    r = api("GET", "/audit", params={"limit": 300})
    if not r.ok:
        st.error(detail(r))
        return
    rows = r.json()
    if not rows:
        st.info("Nothing recorded yet.")
        return
    events = sorted({x["event"] for x in rows})
    chosen = st.multiselect("Filter by event", events, default=events)
    table = []
    for x in rows:
        if x["event"] not in chosen:
            continue
        table.append({
            "Time (UTC)": x["created_at"][:19].replace("T", " "),
            "Event": x["event"],
            "Action": TYPE_LABELS.get(x.get("action_type") or "", "-"),
            "What": x.get("action_title") or "-",
            "Details": json.dumps(x.get("details") or {}, ensure_ascii=False)[:160],
        })
    st.dataframe(table, hide_index=True)


ROOT_DIR = Path(__file__).resolve().parent.parent


def results_page():
    st.title("Fine-tuning results")
    mpath = ROOT_DIR / "model" / "metrics.json"
    if not mpath.exists():
        st.info("Put metrics.json in the model folder to see the results here.")
        return
    m = json.loads(mpath.read_text(encoding="utf-8"))
    cols = {k: v for k, v in m.items() if isinstance(v, dict) and k != "notes"}
    labels = {"base": "Base model (before training)", "tuned": "Fine-tuned (LoRA)", "gemini": "Gemini"}
    df = pd.DataFrame(cols).rename(columns=labels)
    st.caption("Scores on 30 meetings the model never saw during training (1.00 is perfect).")
    st.dataframe(df)
    st.bar_chart(df)
    notes = m.get("notes") or {}
    if notes:
        st.caption(f"Gemini model: {notes.get('gemini_model')} ({notes.get('gemini_batching')})")

    ppath, tpath = ROOT_DIR / "model" / "predictions.json", ROOT_DIR / "data" / "test.jsonl"
    if ppath.exists() and tpath.exists():
        preds = json.loads(ppath.read_text(encoding="utf-8"))
        rows = [json.loads(x) for x in tpath.read_text(encoding="utf-8").splitlines() if x.strip()]
        n = min(len(rows), len(preds.get("tuned", [])), len(preds.get("base", [])))
        if n:
            st.subheader("Look at one test meeting")
            i = int(st.number_input("Meeting number", 1, n, 1)) - 1
            st.text(rows[i]["transcript"][:3000])
            c1, c2, c3 = st.columns(3)
            c1.markdown("**Correct answer**")
            c1.json(rows[i]["analysis"])
            c2.markdown("**Fine-tuned model**")
            c2.code(preds["tuned"][i], language="json")
            c3.markdown("**Base model**")
            c3.code(preds["base"][i], language="json")

# ---------- Sidebar + routing ----------
with st.sidebar:
    page = st.radio("Page", ["Documents", "Tasks", "Audit", "Model results"])
    if st.button("Test n8n connection"):
        r = api("POST", "/n8n/ping")
        st.write(r.status_code, r.json())
    if st.button("Log out"):
        st.session_state.token = None
        st.rerun()

if page == "Documents":
    documents_page()
elif page == "Tasks":
    tasks_page()
elif page == "Audit":
    audit_page()
else:
    results_page()