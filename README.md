# AI Business Operations Agent

> Turns unstructured meetings and business documents into structured information, recommends actions, asks a human for approval, and only then executes the approved actions. Every step is recorded in an audit log.

**Student:** [Your name] | **Course:** AI & Data Science | **Institute:** [Your institute] | **Year:** 2026
**Live demo:** [paste your Streamlit URL here] | **Demo video:** [paste link here]

---

## 1. What it does

```
Input → Understand → Recommend → Approve → Execute → Record
```

1. **Input:** a user uploads a meeting transcript, a meeting recording, or a business document (TXT, PDF, DOCX, MP3/WAV/M4A).
2. **Understand:** an LLM extracts a summary, decisions, action items (with owners and deadlines when stated), concerns, and whether a follow-up meeting is needed.
3. **Recommend:** business rules turn the findings into proposed actions: create a task, schedule a meeting, send an email.
4. **Approve:** the user can edit, approve, or reject every proposal.
5. **Execute:** only approved actions run. Tasks are stored in the app; meetings and emails are executed through n8n workflows on Google Calendar and Gmail.
6. **Record:** every recommendation, edit, approval, rejection and execution result is written to an audit log.

**The AI never executes anything by itself.** It only produces structured data. The backend refuses to run any action that a human has not approved.

## 2. Features

- User login (Supabase Auth)
- Upload TXT / PDF / DOCX and meeting audio (local speech-to-text)
- AI analysis with validated, structured JSON output
- Recommended-actions screen with Approve / Edit / Reject
- Internal task list
- Google Calendar event creation and Gmail sending through n8n
- Audit log page (append-only)
- PDF meeting report download
- Fine-tuned small model (LoRA) with an evaluation page: base vs fine-tuned vs Gemini
- Automated tests (AI, n8n and database are mocked)

## 3. Architecture

```
Streamlit UI ──► FastAPI backend ──► Gemini via LangChain (structured JSON)
                      │
                      ├──► Supabase (Auth + PostgreSQL)
                      │
                      └──► [approved actions only] ──► n8n webhook ──► Google Calendar / Gmail
                                                           │
                                                           └──► result returned ──► audit log
```

FastAPI is the security boundary: it verifies the user's login on every request, enforces the approval gate, and talks to n8n.

## 4. Technology stack

| Area | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | Python, FastAPI |
| Database, auth | Supabase (PostgreSQL, Supabase Auth, row-level security) |
| LLM API | Google Gemini |
| LLM framework | LangChain (prompt → model → structured output) |
| Speech-to-text | faster-whisper (local Whisper) |
| Fine-tuning | LoRA (PEFT) on a small open instruct model, trained on Google Colab |
| Automation | n8n |
| External actions | Google Calendar API, Gmail API (OAuth2, through n8n) |
| PDF report | ReportLab |
| Tests | pytest |

## 5. AI components

| Component | What it does |
|---|---|
| LLM API (Gemini) | Reads the text and returns summary, decisions, action items, concerns, follow-up flag |
| LangChain | Builds the prompt → model → Pydantic-validated output chain, with a fallback model |
| Whisper | Converts meeting audio into text |
| Fine-tuned model | A small model trained with LoRA to produce the same structured output |
| Evaluation | The same hidden test meetings are scored for base model, fine-tuned model and Gemini |
| n8n workflows | Execute approved calendar and email actions |

## 6. Project structure

```
ai-business-agent/
├── backend/
│   ├── app/
│   │   ├── main.py          API endpoints
│   │   ├── extract.py       text from TXT/PDF/DOCX/audio
│   │   ├── transcribe.py    local Whisper
│   │   ├── schemas.py       structure of the AI output
│   │   ├── llm.py           LangChain + Gemini (with fallback model)
│   │   ├── actions.py       proposals and the approval gate
│   │   ├── executors.py     runs tasks, calls n8n
│   │   └── report.py        PDF report
│   └── tests/
├── frontend/
│   └── app.py               Streamlit app
├── scripts/                 dataset generation, splits, evaluation
├── data/                    synthetic dataset (train / val / test)
├── database/schema.sql      all database tables
├── n8n/                     start script and exported workflows
├── model/                   evaluation results from Colab
├── sample_data/             demo files
├── .env.example
└── README.md
```

## 7. Getting started (local)

### Prerequisites

- Python 3.11 or newer
- Node.js LTS (used to run n8n)
- Git
- A Supabase project
- A Google AI Studio API key (Gemini)
- A Google Cloud project with the Calendar API and Gmail API enabled (for calendar and email actions)

### Step 1: Clone and install

```powershell
git clone <your-repo-url>
cd ai-business-agent
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Step 2: Environment variables

Copy `.env.example` to `.env` and fill in your values. Never commit `.env`.

| Variable | Meaning |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Public (anon) key, used by the Streamlit login |
| `SUPABASE_SERVICE_KEY` | Secret service key, **backend only** |
| `GEMINI_API_KEY` | Google AI Studio key |
| `GEMINI_MODEL` | Main Gemini model name |
| `GEMINI_FALLBACK_MODEL` | Optional second model, used if the main one fails |
| `N8N_WEBHOOK_URL` | Test webhook, for example `http://localhost:5678/webhook/ping` |
| `N8N_BASE_URL` | Base for action webhooks, for example `http://localhost:5678/webhook` |
| `TIMEZONE` | Your IANA timezone, for example `Europe/London` |
| `EMAIL_ALLOWLIST` | Comma-separated emails the app may send to (safety guard) |
| `EXTERNAL_ACTIONS_ENABLED` | `true` (default) or `false` to disable calendar and email actions |
| `API_URL` | Backend address used by Streamlit (default `http://localhost:8000`) |

### Step 3: Database

Open the Supabase **SQL Editor**, paste the whole of `database/schema.sql` and run it. The script is safe to run again.

In Supabase, Authentication settings: for local development, turn off "Confirm email" so sign-up works immediately.

### Step 4: n8n and Google

1. Start n8n with the script (it sets the correct URL values): `powershell -ExecutionPolicy Bypass -File .\n8n\start-n8n.ps1`
2. Open http://localhost:5678, create your owner account.
3. Import the workflows from the `n8n/` folder (Workflows → Import from file): `ping.json`, `schedule-meeting.json`, `send-email.json`.
4. In Google Cloud: create an OAuth client (Web application) with the redirect URI `http://localhost:5678/rest/oauth2-credential/callback`, and add your Google account as a **test user**.
5. In n8n, create **Google Calendar OAuth2** and **Gmail OAuth2** credentials with that client, sign in, and attach them to the Google nodes of the imported workflows.
6. Publish (activate) all three workflows.

While the Google app is in testing mode, the login expires after about 7 days: sign in again before a demo.

### Step 5: Run

Three terminals (activate the virtual environment in the first two):

```powershell
# 1. backend
cd backend
uvicorn app.main:app --reload

# 2. frontend
cd frontend
streamlit run app.py

# 3. n8n
powershell -ExecutionPolicy Bypass -File .\n8n\start-n8n.ps1
```

Open http://localhost:8501.

### Step 6: Tests

```powershell
cd backend
python -m pytest -v
```

The tests use fake AI, fake n8n and a fake database, so they need no keys and use no quota.

## 8. Using the app

1. Log in (or sign up).
2. **Documents:** upload a file, choose it, click **Analyze with AI**.
3. Click **Generate recommendations**. Edit, approve, or reject each card.
4. **Tasks:** see tasks created by approved actions.
5. **Audit:** see every recommendation, edit, approval and execution.
6. **Model results:** see the evaluation table, chart, and example outputs.
7. **Create PDF report** on an analyzed document to download a meeting report.

## 9. Fine-tuning and evaluation

**Dataset.** Real meeting transcripts were not available, so Gemini generated synthetic meeting transcripts together with their correct structured answers. The generator (`scripts/generate_dataset.py`) writes several meetings per request. A sample was checked by hand. `scripts/prepare_splits.py` removes duplicates and splits the data **once** into train (150), validation (20), and a hidden test set (30).

**Training.** LoRA fine-tuning of a small open instruct model on a free Colab T4 GPU: [Qwen2.5-1.5B-Instruct: edit if you used a different model], 3 epochs, only the answer part of each example counts toward the loss.

**Evaluation.** The same 30 unseen meetings are given to (1) the base model, (2) the fine-tuned model, (3) Gemini, and scored with one shared function:

| Metric | Meaning |
|---|---|
| `json_valid` | Share of answers in the correct format |
| `action_recall` | Share of real action items found |
| `action_precision` | Share of predicted action items that are real |
| `owner_accuracy`, `deadline_accuracy` | Correct owner and deadline, including correctly saying "none" |
| `follow_up_accuracy` | Correct yes/no on needing a follow-up meeting |

**Results** (generate this table with `python scripts/metrics_to_markdown.py` and paste it here):

| Metric | Base model | Fine-tuned (LoRA) | Gemini |
|---|---|---|---|
| _fill in_ | | | |

Notes for honest reading: action items are matched by text similarity (threshold 0.5), so the scores are good for comparing models but not a perfect judge; Gemini answered several meetings per request; the training data is synthetic.

## 10. Safety and design decisions

- **Approval gate:** the backend refuses to execute any action whose status is not `approved` (tested for every other status).
- **Double-click protection:** an action is claimed atomically before it runs, so it cannot execute twice.
- **Email allowlist:** emails can only be sent to addresses listed in `EMAIL_ALLOWLIST`.
- **Past meeting times, missing recipients, and unconfirmed n8n answers** are rejected with clear messages. n8n must return the Google result for an action to count as done.
- **Audit log:** append-only; users can read and add rows, never edit or delete them.
- **Row-level security:** each user can only see their own documents, analyses, actions, tasks and audit rows.
- **Secrets:** keys live in `.env` (never committed); the service key is used only by the backend.
- **Public-demo switch:** `EXTERNAL_ACTIONS_ENABLED=false` turns off calendar and email actions while tasks keep working.

## 11. Limitations

- Free-tier Gemini limits are small (about 20 requests per day per model on the key used here)
- Synthetic, English-only training data
- The fine-tuned model is small and is evaluated offline, not used in the live pipeline
- Approximate text matching in the evaluation
- The PDF report uses a Latin-only font
- Google login in testing mode expires after about 7 days
- Hosted free tiers sleep when idle and wake up slowly

## 12. Future work

Slack, Outlook/Teams and Jira integrations; recurring workflows and reminders; more document types; a larger real dataset; running the fine-tuned model inside the live pipeline; vector search over company knowledge; organization-level permissions.

## 13. Deployment

| Part | Where | Notes |
|---|---|---|
| Streamlit frontend | Streamlit Community Cloud | Main file `frontend/app.py`; secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `API_URL` |
| FastAPI backend | Render (web service) | Root directory `backend`; start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Database and auth | Supabase | Already hosted |
| n8n | Local machine (or a tunnel), or disabled in the public demo | Set `EXTERNAL_ACTIONS_ENABLED=false` online |

Free hosting tiers sleep after inactivity: open the backend `/health` page and the app a few minutes before a presentation.

## 14. License and credits

Academic project. Built with Streamlit, FastAPI, Supabase, LangChain, Google Gemini, faster-whisper, Hugging Face Transformers and PEFT, n8n, ReportLab.
