# ASEA — Agent-Agnostic Verification & Trust Layer for AI-Written Code

## Overview

ASEA is an agent-agnostic verification and trust layer designed to sit between AI coding agents / human developers and production codebases.

This repository contains **Module 0 (Project Foundation)**, **Module 1 (PR/Diff Ingestion)**, **Module 3 (Negative-Space Scanner)**, **Module 4 (Architecture Fit Checker)**, **Module 5 (Explainable Confidence Scoring)**, and **Module 6 (Governance & Audit Trail)**.

---

## 🛠 Tech Stack

- **Language:** Python 3.12+
- **Framework:** Django 5.0+ / Django REST Framework 3.14+
- **Database:** PostgreSQL
- **Authentication:** JWT (`djangorestframework-simplejwt`)
- **HTTP Client:** `requests`
- **LLM Integration:** OpenAI-compatible REST API (`LLM_API_KEY`, `LLM_MODEL`)
- **Environment Management:** `python-dotenv`

---

## 📁 Project Structure

```text
backend/
├── manage.py                  # Django administrative script
├── config/                    # Core project configuration
│   ├── __init__.py
│   ├── settings.py            # Environment-driven PostgreSQL & JWT settings
│   ├── urls.py                # Main API routing table
│   ├── wsgi.py
│   └── asgi.py
├── apps/                      # Modular application domain packages
│   ├── __init__.py
│   ├── users/                 # Authentication & user profile foundation
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── views.py
│   │   └── urls.py
│   └── verification/          # Verification domain, Ingestion, Scanner, Arch Checker, Scoring & Audit Log
│       ├── __init__.py
│       ├── admin.py           # Admin interface registration (VerificationRun & AuditLog)
│       ├── apps.py
│       ├── models.py          # VerificationRun & AuditLog model schemas
│       ├── serializers.py     # SubmitIngestionSerializer, VerificationRunSerializer & AuditLogSerializer
│       ├── views.py           # HealthCheckView, SubmitVerificationView, ScanVerificationView, ArchitectureCheckView, ScoreVerificationView, AuditLogView
│       ├── urls.py            # API routing table (/api/verify/submit, scan, architecture, score, audit)
│       ├── tests.py           # Automated test suite (36 tests)
│       ├── services/          # Business logic services
│       │   ├── __init__.py
│       │   ├── github.py      # GitHubIngestionService (GitHub REST API ingestion)
│       │   ├── scanner.py     # NegativeSpaceScannerService (Read-only LLM Negative-Space Scanner)
│       │   ├── architecture.py# ArchitectureCheckerService (Static rules + LLM Architecture Fit Checker)
│       │   ├── scoring.py     # ConfidenceScoringService (Deterministic 0-100 Confidence Scoring)
│       │   └── audit.py       # AuditLogService (Append-only audit trail logging & secret sanitization)
│       └── migrations/        # Database migrations

├── requirements.txt           # Python dependency declarations
├── .env.example               # Environment variables template
├── .env                       # Local environment variables
├── .gitignore                 # Version control exclusion rules
└── README.md                  # Developer documentation
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` before running the project:

```bash
cp .env.example .env
```

| Variable | Description | Example |
| :--- | :--- | :--- |
| `SECRET_KEY` | Django application secret key | `django-insecure-key-32bytes-minimum` |
| `DEBUG` | Enable debug mode (`True`/`False`) | `True` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `localhost,127.0.0.1` |
| `DATABASE_NAME` | PostgreSQL database name | `asea_db` |
| `DATABASE_USER` | PostgreSQL user | `postgres` |
| `DATABASE_PASSWORD` | PostgreSQL password | `postgres` |
| `DATABASE_HOST` | PostgreSQL host | `localhost` |
| `DATABASE_PORT` | PostgreSQL port | `5432` |
| `JWT_SECRET_KEY` | Signing key for JWT tokens | `jwt-secret-key-32bytes-minimum` |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | Access token lifespan in minutes | `60` |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Refresh token lifespan in days | `7` |
| `GITHUB_TOKEN` | Personal Access Token for GitHub REST API | `ghp_your_token_here` |
| `LLM_API_KEY` | API key for LLM provider (Modules 3 & 4) | `your_llm_api_key` |
| `LLM_MODEL` | Model ID for LLM provider | `gpt-4o-mini` |

---

## 🐘 PostgreSQL Database Setup

Create a PostgreSQL database and user:

```sql
CREATE DATABASE asea_db;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE asea_db TO postgres;
```

---

## 🚀 Getting Started

### 1. Installation

Create a virtual environment and install dependencies:

```bash
cd backend
python -m venv venv

# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Database Migrations

Run database migrations to initialize PostgreSQL tables:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Running the Server

Start the Django REST Framework server:

```bash
python manage.py runserver
```

---

## 🧪 Automated Testing

Execute the automated test suite (uses mocked GitHub API & LLM responses):

```bash
python manage.py test
```

Tests cover:
- Health check endpoint (`GET /api/health/`)
- VerificationRun model creation & field serialization
- JWT authentication (login, token refresh, authorization checks)
- PR/Diff ingestion (`POST /api/verify/submit`):
  - Successful PR and diff ingestion with status transition (`QUEUED` → `INGESTING` → `INGESTED`)
  - Response formatting (`HTTP 202` with `{"runId": "<uuid>", "status": "INGESTED"}`)
  - Rejecting non-GitHub repository URLs (`HTTP 400`)
  - Handling 404 non-existent PRs with status `FAILED` (`HTTP 400`)
  - Rejecting unauthenticated requests (`HTTP 401`)
- Negative-Space Scanner (`POST /api/verify/<run_id>/scan`):
  - Successful scan returning structured findings (`HTTP 200 OK`, status transition `SCANNING` → `SCANNED`)
  - Verification of 8 category types and 5 severity levels
  - Handling LLM failure, timeout, or missing key gracefully (`HTTP 500`, status `SCAN_FAILED`)
  - Rejection of unauthenticated requests (`HTTP 401`)
- Architecture Fit Checker (`POST /api/verify/<run_id>/architecture`):
  - Combining rule-based static analysis and LLM architectural evaluation
  - Status transition `CHECKING_ARCHITECTURE` → `ARCHITECTURE_CHECKED`
  - Handling LLM API failure (`HTTP 500`, status `ARCHITECTURE_FAILED`)
  - Rejection of unauthenticated requests (`HTTP 401`)
- Explainable Confidence Scoring (`POST /api/verify/<run_id>/score`):
  - Deterministic 0-100 scoring based on Module 3 & Module 4 finding severities
  - Exact severity penalty deductions (CRITICAL: -25, HIGH: -15, MEDIUM: -8, LOW: -3, INFO: -1)
  - Clamping score at lower bound 0 and returning 100 for zero findings
  - Human-readable narrative explanation generation and breakdown JSON
  - Rejection of unauthenticated requests (`HTTP 401`)
- Governance & Audit Trail (`GET /api/verify/<run_id>/audit`):
  - Append-only audit logging at application layer for key pipeline events (`PR_INGESTION`, `NEGATIVE_SPACE_SCAN`, `ARCHITECTURE_CHECK`, `CONFIDENCE_SCORING`)
  - Automatic sanitization of sensitive API keys, secrets, tokens, and authorization credentials
  - Returning audit entries in strict chronological order
  - Rejection of unauthenticated requests (`HTTP 401`) and non-existent run IDs (`HTTP 404`)

---

## 📡 API Endpoints

### 1. Submit PR / Diff for Verification
- **POST** `/api/verify/submit`
- **Headers:** `Authorization: Bearer <access_token>`
- **Request Body:**
```json
{
  "repoUrl": "https://github.com/owner/repository",
  "prNumber": 42
}
```
- **Response (HTTP 202 Accepted):**
```json
{
  "runId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "INGESTED"
}
```

### 2. Trigger Negative-Space Scan
- **POST** `/api/verify/<run_id>/scan`
- **Headers:** `Authorization: Bearer <access_token>`
- **Response (HTTP 200 OK):**
```json
{
  "runId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "SCANNED",
  "findingsCount": 1,
  "findings": [
    {
      "category": "RATE_LIMITING",
      "severity": "HIGH",
      "description": "Login endpoint lacks rate limiting.",
      "reason": "No throttling middleware applied in login_user view."
    }
  ]
}
```

### 3. Trigger Architecture Fit Check
- **POST** `/api/verify/<run_id>/architecture`
- **Headers:** `Authorization: Bearer <access_token>`
- **Response (HTTP 200 OK):**
```json
{
  "runId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "ARCHITECTURE_CHECKED",
  "findingsCount": 1,
  "findings": [
    {
      "category": "DESIGN_PATTERNS",
      "severity": "MEDIUM",
      "description": "Handler pattern used instead of View class pattern.",
      "evidence": "class UserHandler"
    }
  ]
}
```

### 4. Trigger Confidence Scoring
- **POST** `/api/verify/<run_id>/score`
- **Headers:** `Authorization: Bearer <access_token>`
- **Response (HTTP 200 OK):**
```json
{
  "runId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "SCORED",
  "score": 82,
  "explanation": "Base confidence score of 100 reduced by 18 penalty points across 2 total finding(s) (1 HIGH (-15 pts), 1 LOW (-3 pts)). Final confidence score evaluated to 82/100.",
  "breakdown": [
    {
      "source": "Module 3 (Negative-Space Scanner)",
      "category": "RATE_LIMITING",
      "severity": "HIGH",
      "deduction": 15,
      "description": "Login endpoint lacks rate limiting.",
      "reason": "No throttling middleware applied in login_user view."
    },
    {
      "source": "Module 4 (Architecture Fit Checker)",
      "category": "DESIGN_PATTERNS",
      "severity": "LOW",
      "deduction": 3,
      "description": "Handler pattern used instead of View class pattern.",
      "evidence": "class UserHandler"
    }
  ]
}
```

### 5. Fetch Verification Audit Trail
- **GET** `/api/verify/<run_id>/audit`
- **Headers:** `Authorization: Bearer <access_token>`
- **Response (HTTP 200 OK):**
```json
{
  "runId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "auditTrail": [
    {
      "id": 1,
      "runId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
      "event": "PR_INGESTION",
      "status": "SUCCESS",
      "timestamp": "2026-09-09T11:15:00.000Z",
      "details": {
        "repository_url": "https://github.com/owner/repository",
        "pr_number": 42,
        "files_count": 2
      }
    },
    {
      "id": 2,
      "runId": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
      "event": "NEGATIVE_SPACE_SCAN",
      "status": "SUCCESS",
      "timestamp": "2026-09-09T11:15:05.000Z",
      "details": {
        "findingsCount": 1
      }
    }
  ]
}
```

### 6. Health Check
- **GET** `/api/health/` (Unauthenticated)
```bash
curl http://127.0.0.1:8000/api/health/
```
- **Response:**
```json
{
  "status": "ok",
  "database": "connected"
}
```

### 7. JWT Login
- **POST** `/api/auth/token/`
- **Request Body:** `{"username": "user", "password": "password"}`

