import os
from datetime import datetime, timezone
import time
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Response
from app.report import build_report
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from supabase import create_client

from app.actions import build_proposals, check_executable, ensure_analyzable
from app.executors import ExecutionError, run_action
from app.extract import extract_text
from app.llm import MODEL, analyze_text
from app.actions import build_proposals, check_executable, ensure_analyzable

load_dotenv()
app = FastAPI(title="AI Business Operations Agent")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

@app.middleware("http")
async def log_timing(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    print(f"[timing] {request.method} {request.url.path} -> {response.status_code} "
          f"in {time.perf_counter() - start:.2f}s")
    return response
# ---------- helpers ----------
_token_cache: dict[str, tuple[float, object]] = {}
TOKEN_TTL_SECONDS = 60


def get_user(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1]
    now = time.time()
    hit = _token_cache.get(token)
    if hit and hit[0] > now:
        return hit[1]
    try:
        user = supabase.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "Invalid token")
    if user is None:
        raise HTTPException(401, "Invalid token")
    if len(_token_cache) > 200:
        for t in [t for t, (exp, _u) in _token_cache.items() if exp <= now]:
            _token_cache.pop(t, None)
    _token_cache[token] = (now + TOKEN_TTL_SECONDS, user)
    return user

def log_event(user_id: str, action_id: str | None, event: str, details: dict | None = None):
    try:
        supabase.table("audit_log").insert({
            "user_id": user_id, "action_id": action_id, "event": event, "details": details or {},
        }).execute()
    except Exception as e:
        print(f"[audit] FAILED to write audit row '{event}': {e}")


def get_action(action_id: str, user_id: str) -> dict:
    res = (supabase.table("proposed_actions").select("*")
           .eq("id", action_id).eq("user_id", user_id).execute())
    if not res.data:
        raise HTTPException(404, "Action not found")
    return res.data[0]


def update_action(action_id: str, fields: dict) -> dict:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    return supabase.table("proposed_actions").update(fields).eq("id", action_id).execute().data[0]

def claim_action(action_id: str) -> bool:
    """Atomically moves approved -> executing. False means someone else already did."""
    res = (supabase.table("proposed_actions")
           .update({"status": "executing", "updated_at": datetime.now(timezone.utc).isoformat()})
           .eq("id", action_id).eq("status", "approved").execute())
    return bool(res.data)


# ---------- documents ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/documents")
async def upload_document(file: UploadFile = File(...), authorization: str | None = Header(None)):
    user = get_user(authorization)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large (limit 25 MB).")
    try:
        text = await run_in_threadpool(extract_text, file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Could not read this file: {e}")
    if not text.strip():
        raise HTTPException(400, "No text could be extracted from this file.")
    row = supabase.table("documents").insert({
        "user_id": user.id, "filename": file.filename,
        "file_type": file.filename.rsplit(".", 1)[-1].lower(), "extracted_text": text,
    }).execute().data[0]
    log_event(user.id, None, "document_uploaded", {"document_id": row["id"], "filename": file.filename})
    return row


@app.get("/documents")
def list_documents(authorization: str | None = Header(None)):
    user = get_user(authorization)
    res = (supabase.table("documents").select("id, filename, file_type, created_at")
           .eq("user_id", user.id).order("created_at", desc=True).execute())
    return res.data


@app.get("/documents/{doc_id}")
def get_document(doc_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    res = (supabase.table("documents").select("*")
           .eq("id", doc_id).eq("user_id", user.id).execute())
    if not res.data:
        raise HTTPException(404, "Document not found")
    return res.data[0]


# ---------- analysis ----------
@app.post("/documents/{doc_id}/analyze")
def analyze_document(doc_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    doc = (supabase.table("documents").select("id, extracted_text")
           .eq("id", doc_id).eq("user_id", user.id).execute())
    if not doc.data:
        raise HTTPException(404, "Document not found")
    try:
        ensure_analyzable(doc.data[0]["extracted_text"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        result = analyze_text(doc.data[0]["extracted_text"])
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    row = supabase.table("analyses").insert({
        "document_id": doc_id, "user_id": user.id,
        "result": result.model_dump(), "model": MODEL,
    }).execute().data[0]
    log_event(user.id, None, "analyzed", {"document_id": doc_id, "model": MODEL})
    return row


@app.get("/documents/{doc_id}/analysis")
def get_analysis(doc_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    res = (supabase.table("analyses").select("*")
           .eq("document_id", doc_id).eq("user_id", user.id)
           .order("created_at", desc=True).limit(1).execute())
    return res.data[0] if res.data else {"result": None}


# ---------- recommendations + approval ----------
@app.post("/documents/{doc_id}/recommend")
def recommend(doc_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    an = (supabase.table("analyses").select("id, result")
          .eq("document_id", doc_id).eq("user_id", user.id)
          .order("created_at", desc=True).limit(1).execute())
    if not an.data:
        raise HTTPException(400, "Analyze the document first")
    analysis = an.data[0]
    existing = (supabase.table("proposed_actions").select("*")
                .eq("analysis_id", analysis["id"]).execute())
    if existing.data:
        return existing.data
    rows = [{"user_id": user.id, "document_id": doc_id, "analysis_id": analysis["id"], **p}
            for p in build_proposals(analysis["result"])]
    if not rows:
        return []
    created = supabase.table("proposed_actions").insert(rows).execute().data
    for a in created:
        log_event(user.id, a["id"], "recommended", {"type": a["action_type"], "payload": a["payload"]})
    return created


@app.get("/documents/{doc_id}/actions")
def list_actions(doc_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    res = (supabase.table("proposed_actions").select("*")
           .eq("document_id", doc_id).eq("user_id", user.id).order("created_at").execute())
    return res.data


class EditBody(BaseModel):
    payload: dict


@app.patch("/actions/{action_id}")
def edit_action(action_id: str, body: EditBody, authorization: str | None = Header(None)):
    user = get_user(authorization)
    action = get_action(action_id, user.id)
    if action["status"] not in ("pending", "failed"):
        raise HTTPException(409, f"Cannot edit an action that is {action['status']}")
    row = update_action(action_id, {"payload": body.payload, "status": "pending", "result": None})
    log_event(user.id, action_id, "edited", {"payload": body.payload})
    return row


@app.post("/actions/{action_id}/approve")
def approve_action(action_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    action = get_action(action_id, user.id)
    if action["status"] != "pending":
        raise HTTPException(409, f"Cannot approve an action that is {action['status']}")
    row = update_action(action_id, {"status": "approved"})
    log_event(user.id, action_id, "approved")
    return row


@app.post("/actions/{action_id}/reject")
def reject_action(action_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    action = get_action(action_id, user.id)
    if action["status"] not in ("pending", "failed"):
        raise HTTPException(409, f"Cannot reject an action that is {action['status']}")
    row = update_action(action_id, {"status": "rejected"})
    log_event(user.id, action_id, "rejected")
    return row



def _execute(user, action: dict) -> dict:
    action_id = action["id"]
    try:
        check_executable(action)  # the approval gate
    except ValueError as e:
        log_event(user.id, action_id, "blocked", {"reason": str(e)})
        raise HTTPException(409, str(e))
    if not claim_action(action_id):  # stops double-clicks from running twice
        log_event(user.id, action_id, "blocked", {"reason": "already running or changed"})
        raise HTTPException(409, "This action is already running or was just changed.")
    action["status"] = "executing"
    try:
        result = run_action(supabase, user.id, action)
    except ExecutionError as e:
        update_action(action_id, {"status": "failed", "result": {"error": str(e)}})
        log_event(user.id, action_id, "failed", {"error": str(e)})
        raise HTTPException(502, str(e))
    except Exception as e:
        msg = f"Unexpected error: {e}. Check Google before retrying."
        update_action(action_id, {"status": "failed", "result": {"error": msg}})
        log_event(user.id, action_id, "failed", {"error": msg})
        raise HTTPException(500, msg)
    row = update_action(action_id, {"status": "executed", "result": result})
    log_event(user.id, action_id, "executed", {"result": result})
    return row


@app.get("/actions/{action_id}")
def read_action(action_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    return get_action(action_id, user.id)


@app.post("/actions/{action_id}/execute")
def execute_action(action_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    return _execute(user, get_action(action_id, user.id))


@app.post("/actions/{action_id}/approve-and-run")
def approve_and_run(action_id: str, body: EditBody, authorization: str | None = Header(None)):
    user = get_user(authorization)
    action = get_action(action_id, user.id)
    if action["status"] not in ("pending", "failed"):
        raise HTTPException(409, f"Cannot run an action that is {action['status']}")
    changed = body.payload != action["payload"]
    action = update_action(action_id, {"payload": body.payload, "status": "approved", "result": None})
    if changed:
        log_event(user.id, action_id, "edited", {"payload": body.payload})
    log_event(user.id, action_id, "approved")
    return _execute(user, action)

# ---------- tasks ----------
@app.get("/tasks")
def list_tasks(authorization: str | None = Header(None)):
    user = get_user(authorization)
    res = (supabase.table("tasks").select("*").eq("user_id", user.id)
           .order("created_at", desc=True).execute())
    return res.data


class TaskBody(BaseModel):
    status: str


@app.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskBody, authorization: str | None = Header(None)):
    user = get_user(authorization)
    if body.status not in ("todo", "done"):
        raise HTTPException(400, "status must be 'todo' or 'done'")
    res = (supabase.table("tasks").update({"status": body.status})
           .eq("id", task_id).eq("user_id", user.id).execute())
    if not res.data:
        raise HTTPException(404, "Task not found")
    return res.data[0]

@app.get("/documents/{doc_id}/report")
def download_report(doc_id: str, authorization: str | None = Header(None)):
    user = get_user(authorization)
    doc = (supabase.table("documents").select("filename")
           .eq("id", doc_id).eq("user_id", user.id).execute())
    if not doc.data:
        raise HTTPException(404, "Document not found")
    an = (supabase.table("analyses").select("result, model")
          .eq("document_id", doc_id).eq("user_id", user.id)
          .order("created_at", desc=True).limit(1).execute())
    if not an.data:
        raise HTTPException(400, "Analyze the document first")
    pdf = build_report(doc.data[0]["filename"], an.data[0]["result"], an.data[0].get("model"))
    log_event(user.id, None, "report_generated", {"document_id": doc_id})
    return Response(content=pdf, media_type="application/pdf")


# ---------- audit log ----------
@app.get("/audit")
def list_audit(limit: int = 100, authorization: str | None = Header(None)):
    user = get_user(authorization)
    limit = max(1, min(limit, 500))
    rows = (supabase.table("audit_log").select("*").eq("user_id", user.id)
            .order("created_at", desc=True).limit(limit).execute().data)
    ids = list({r["action_id"] for r in rows if r.get("action_id")})
    info = {}
    if ids:
        acts = (supabase.table("proposed_actions").select("id, action_type, payload")
                .in_("id", ids).execute().data)
        info = {a["id"]: a for a in acts}
    for r in rows:
        a = info.get(r.get("action_id"))
        r["action_type"] = a["action_type"] if a else None
        p = (a or {}).get("payload") or {}
        r["action_title"] = p.get("title") or p.get("subject") or ""
    return rows

# ---------- n8n connection test ----------
@app.post("/n8n/ping")
def n8n_ping(authorization: str | None = Header(None)):
    get_user(authorization)
    try:
        r = requests.post(os.environ["N8N_WEBHOOK_URL"], json={"hello": "from fastapi"}, timeout=10)
        return {"n8n_status": r.status_code}
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach n8n: {e}")