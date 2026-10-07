# ASEA: Agent-Agnostic Verification & Trust Layer 🛡️

Hey there! Welcome to **ASEA** (Agent-Agnostic Verification & Trust Layer). If you've ever dealt with AI-generated code and thought, *"This looks great, but what did it silently break?"* — this project is for you.

ASEA acts as an active, intelligent shield between AI coding agents (or human developers!) and your production codebase. It automatically ingests pull requests, scans for invisible security logic gaps (we call this *negative-space scanning*), verifies that the new code actually fits your repository's existing architectural patterns, and rolls it all up into an explainable **Confidence Score**. 

No black-box rejections. Just transparent, actionable feedback.

---

## 🌟 What makes ASEA special?

Instead of just running a standard linter, ASEA evaluates code structurally and semantically using eight modular components. The complete pipeline runs flawlessly inside a beautiful React-based dashboard, or directly in your CI/CD workflow via GitHub Actions.

Here is what's under the hood:
- **Module 0 (Foundation):** The robust Django + PostgreSQL backend that orchestrates the verification flow.
- **Module 1 (PR Ingestion):** Seamlessly pulls in GitHub Pull Requests, diffs, and context automatically.
- **Module 3 (Negative-Space Scanner):** The "what's missing?" scanner. Powered by an LLM, it detects missing security validations, unhandled edge cases, and missing rate-limiters that standard static analysis misses.
- **Module 4 (Architecture Fit Checker):** Uses a hybrid of static AST rules and LLM evaluation to ensure the incoming code doesn't just work, but *belongs* in your codebase (e.g. enforcing your specific naming and class conventions).
- **Module 5 (Explainable Confidence Scoring):** A deterministic, math-driven engine that assigns severity penalties (Critical: -25, High: -15, etc.) and gives you a clear 0-100 score. 
- **Module 6 (Governance & Audit Trail):** An append-only audit logger that sanitizes secrets and provides a bulletproof timeline of every verification step.
- **Module 7 (CI/CD + MCP):** Plug-and-play GitHub Actions workflow to run this on every PR, plus a native **Model Context Protocol (MCP)** JSON-RPC server so other AI agents can talk to ASEA directly!
- **Module 8 (Dashboard):** A stunning, glassmorphism-styled React/Vite dashboard to trigger verifications and view results visually.

---

## 🛠️ The Tech Stack

**Backend (The Brains):**
- **Python 3.12+** & **Django 5.0+** / Django REST Framework
- **PostgreSQL** (can gracefully fall back to SQLite for local development)
- **JWT Authentication** for secure API access
- **OpenAI-compatible LLM Integration** for semantic analysis

**Frontend (The Beauty):**
- **React 18** & **Vite**
- **Vanilla CSS** (No heavy CSS frameworks, just pure, optimized glassmorphism)
- **Framer Motion** & **Lucide React** for micro-animations and iconography
- **Axios** for API orchestration

---

## 🚀 Getting Started

Want to spin this up locally? It's easier than you think.

### 1. Backend Setup

Open a terminal and drop into the backend folder:
```bash
cd backend
python -m venv venv
```
Activate your virtual environment:
- **Windows:** `.\venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

Install the dependencies and set up the local database (we default to SQLite locally so you don't have to wrestle with Postgres containers on day one):
```bash
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
```
Create your admin user so you can log into the dashboard:
```bash
python manage.py createsuperuser
```
Fire it up:
```bash
python manage.py runserver
```

### 2. Frontend Setup

Leave the backend running, open a new terminal, and head into the frontend folder:
```bash
cd frontend
npm install
```
Start the Vite dev server:
```bash
npm run dev
```

That's it! Open your browser (usually `http://localhost:5173`), log in with the superuser you just created, and start verifying Pull Requests.

---

## 🤖 CI/CD and Agent Integration (MCP)

If you look in `.github/workflows/asea_verification.yml`, you'll see we've already configured the GitHub Actions pipeline. It will automatically ping the backend's `/api/verify/ci-trigger` endpoint whenever a PR is opened. 

For AI builders: ASEA includes a native **Model Context Protocol (MCP)** interface! Check out `backend/apps/verification/mcp.py`. Agents can invoke `asea_submit_verification` and `asea_get_verification_result` as standard JSON-RPC 2.0 tools to self-verify their own code before they ask you for a code review.

---

## 🧪 Testing

We take trust seriously, so we test thoroughly.
To run the backend test suite (43 exhaustive tests covering everything from scoring math to audit-trail sanitization):
```bash
cd backend
python manage.py test
```

To run the frontend component tests:
```bash
cd frontend
npm run test
```

---

*Built with passion to keep codebases clean, secure, and human-readable, no matter who (or what) wrote the code.*
