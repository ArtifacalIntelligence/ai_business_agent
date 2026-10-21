# Run the Project Locally

This guide explains how to run the project on your own computer using
**FastAPI + Uvicorn**, **Streamlit**, and **n8n**.

> **Safety first:** Only run code you trust. Review the source code
> before running it, keep API keys and passwords private, and never
> commit your `.env` file or other secrets to GitHub.

## 1. Prerequisites

Install the following:

-   Python 3.10 or a version supported by the project's dependencies
-   Node-free n8n installation method of your choice (for example, the
    official desktop/local setup or Docker)
-   Git (optional, if you are cloning the repository)

Check Python and pip in PowerShell:

``` powershell
python --version
python -m pip --version
```

If you use Git, clone the repository and enter the project directory:

``` powershell
git clone YOUR_REPOSITORY_URL
cd YOUR_PROJECT_FOLDER
```

If you already have the project files, open PowerShell in the project
folder instead.

## 2. Create and activate a Python virtual environment

From the project folder, run:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the virtual environment's
Python directly instead:

``` powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Avoid changing the computer-wide PowerShell execution policy just to run
this project. If activation is permitted, upgrade pip after activating:

``` powershell
python -m pip install --upgrade pip
```

## 3. Install Python dependencies

If the repository contains `requirements.txt`, install its packages:

``` powershell
python -m pip install -r requirements.txt
```

If no `requirements.txt` exists, ask the project maintainer for the
supported dependency list rather than installing random packages.

## 4. Configure environment variables safely

Create a local `.env` file only if the project expects one, using the
variable names required by the code. Do not put real credentials in this
README or commit them to version control.

Example template --- replace placeholders locally and remove variables
your code does not use:

``` dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=YOUR_SUPABASE_PUBLISHABLE_OR_ANON_KEY
SUPABASE_SERVICE_KEY=YOUR_SUPABASE_SECRET_OR_SERVICE_ROLE_KEY
N8N_WEBHOOK_URL=http://localhost:5678/webhook/ping
N8N_BASE_URL=http://localhost:5678
TIMEZONE=Asia/Karachi
EMAIL_ALLOWLIST=
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=YOUR_SUPPORTED_GEMINI_MODEL
```

Important:

-   Keep `.env` out of Git. Ensure `.env` is listed in `.gitignore`.
-   Never share `SUPABASE_SERVICE_KEY`, private API keys, passwords, or
    credential exports.
-   A Supabase service-role/secret key can bypass database row-level
    security. Use it only in trusted server-side code when required.
-   `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_KEY` are different values;
    do not use one as the other.
-   `GEMINI_API_KEY` and `GEMINI_MODEL` are separate variables.
-   Confirm whether the project uses `python-dotenv` or another
    mechanism to load `.env`. Python does not load `.env` files
    automatically with `os.getenv()` alone.
-   If the project reads settings from environment variables, set them
    using the method supported by the code. For a temporary PowerShell
    session, for example:

``` powershell
$env:TIMEZONE = "Asia/Karachi"
$env:N8N_WEBHOOK_URL = "http://localhost:5678/webhook/ping"
```

Do not paste real secret values into shared terminals, screenshots,
issue trackers, or chat messages.

## 5. Start n8n locally

Start n8n using the installation method configured for your computer.
For a local instance, the usual address is:

``` text
http://localhost:5678
```

Open that address in your browser, sign in or complete local setup, and
import the workflow JSON supplied by the project maintainer if it has
not already been imported.

Check that:

-   The workflow is saved and active when using its production webhook.
-   The webhook path matches the project's configured path (the example
    above uses `/webhook/ping`).
-   Required credentials are configured in n8n itself.
-   You are using the **test webhook URL** when the workflow is
    listening in test mode, and the **production webhook URL** when the
    workflow is active. Follow the URL displayed by your n8n node.

A local `localhost` webhook is intended for processes on your own
computer. It will not work for a cloud-hosted backend.

## 6. Start FastAPI with Uvicorn

Open a **new PowerShell window** in the project folder. Activate the
virtual environment again if needed:

``` powershell
.\.venv\Scripts\Activate.ps1
```

Start the API, assuming the FastAPI instance in `main.py` is named
`app`:

``` powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Using `127.0.0.1` keeps the development server accessible only from your
computer. Do not use `--host 0.0.0.0` for local development unless you
intentionally need access from other devices and understand the network
exposure.

Open the API documentation, if enabled:

``` text
http://127.0.0.1:8000/docs
```

If the app instance is not named `app`, or the API file is not
`main.py`, update the command to match the source code.

## 7. Start Streamlit

Open another **new PowerShell window** in the project folder and
activate the virtual environment:

``` powershell
.\.venv\Scripts\Activate.ps1
```

Start Streamlit using the actual Streamlit entry-point filename. For
example, if it is `app.py`:

``` powershell
python -m streamlit run app.py --server.address 127.0.0.1
```

Replace `app.py` with the correct filename for this project.

Open the local address shown in the terminal, commonly:

``` text
http://localhost:8501
```

If Streamlit calls FastAPI, configure its API URL to use the local
backend address, such as `http://127.0.0.1:8000`. Use the exact
configuration key expected by the code.

## 8. Run and test the application

Keep the three services running in their own terminal windows:

1.  n8n
2.  FastAPI / Uvicorn
3.  Streamlit

Then test the application in the browser. Confirm that Streamlit loads,
API requests succeed, and the n8n workflow executes as expected.

If something fails:

-   Read the error in the relevant terminal.
-   Confirm the service is running and the URL/port is correct.
-   Check that the webhook path matches the n8n workflow.
-   Verify required environment variables are set without printing
    secret values.
-   Do not disable authentication, database security, or firewall
    protections as a troubleshooting shortcut.

## 9. Stop the services

In each terminal window, press:

``` text
Ctrl+C
```

Stop n8n using the method used to start it (for example, stop its Docker
container if you used Docker).

## 10. Before sharing or deploying

-   Keep `.env`, credential files, database dumps, and private workflow
    exports out of public repositories.
-   Review `.gitignore` before running `git add .`.
-   Use separate development credentials where possible.
-   Configure production secrets in the hosting provider's
    secret/environment settings.
-   Replace local `localhost` webhook and API URLs with the correct
    hosted URLs when deploying.
-   Never expose a privileged Supabase key to browser-facing code.
-   Back up workflow definitions and important data securely.

## Project-specific details to fill in

Before publishing this README, the maintainer should confirm:

-   The actual Streamlit entry-point filename
-   The Python version supported by the project
-   The correct n8n installation/start command
-   Whether `.env` is loaded automatically
-   Which environment variables are required
-   The actual n8n webhook path and whether it uses test or production
    mode
