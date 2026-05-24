# Closira Enquiry API

A lightweight backend simulating Closira's core customer enquiry-handling workflow.
Built with **Python + FastAPI**, using **SQLite** for storage, **Alembic** for migrations, and **FastAPI BackgroundTasks** for async processing.

---

## Quick Start

### 1. Clone and enter the repo
```bash
git clone <your-repo-url>
cd backend
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env if needed — defaults work out of the box
```

### 5. Run database migrations
```bash
alembic upgrade head
```

This creates the `enquiries` and `enquiry_events` tables. To roll back:
```bash
alembic downgrade -1
```

### 6. Run the server
```bash
uvicorn app.main:app --reload
```

The API is now running at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

## API Endpoints

| Method | Endpoint                      | Description                                      |
|--------|-------------------------------|--------------------------------------------------|
| POST   | `/enquiry`                    | Create a new inbound enquiry (non-blocking)      |
| POST   | `/enquiry/{id}/follow-up`     | Schedule a follow-up for an open enquiry         |
| POST   | `/enquiry/{id}/escalate`      | Manually escalate to a human agent               |
| GET    | `/enquiry/{id}/history`       | Full conversation history and status timeline    |
| GET    | `/health`                     | API status and database connectivity             |

---

## Database Schema

### `enquiries`
| Column             | Type     | Notes                                                    |
|--------------------|----------|----------------------------------------------------------|
| id                 | TEXT PK  | UUID generated at creation                               |
| tenant_id          | TEXT     | Nullable — stubbed for multi-tenancy (see below)         |
| channel            | TEXT     | `whatsapp` / `email` / `call`                            |
| customer_name      | TEXT     |                                                          |
| message            | TEXT     | Raw inbound message                                      |
| status             | TEXT     | `pending` → `processing` → `sop_matched` / `escalated`  |
| matched_sop        | TEXT     | Populated by background task                             |
| suggested_response | TEXT     | Populated by background task                             |
| escalation_reason  | TEXT     | Set on manual or auto escalation                         |
| created_at         | DATETIME |                                                          |
| updated_at         | DATETIME | Auto-updated on every change                             |

### `enquiry_events`
| Column      | Type     | Notes                                      |
|-------------|----------|--------------------------------------------|
| id          | TEXT PK  | UUID                                       |
| enquiry_id  | TEXT FK  | References `enquiries.id`                  |
| event_type  | TEXT     | e.g. `sop_matched`, `follow_up_scheduled`  |
| detail      | TEXT     | Human-readable description                 |
| created_at  | DATETIME |                                            |

**Design rationale:** `enquiry_events` is an append-only log. Status changes are never overwritten — every transition is recorded as a new row. This powers the `/history` endpoint and would support full audit trails in production.

---

## SOPs (Standard Operating Procedures)

The background task matches messages to one of 5 hardcoded SOPs using keyword rules:

| SOP Name            | Trigger Keywords                                          |
|---------------------|-----------------------------------------------------------|
| Booking Enquiry     | book, appointment, schedule, reserve, slot, availability  |
| Pricing Question    | price, pricing, cost, plan, fee, rate, charge, how much   |
| Complaint           | complaint, unhappy, frustrated, issue, problem, refund    |
| After-Hours Message | after hours, closed, weekend, holiday, office hours       |
| General Information | information, info, details, tell me, explain, what is     |

If no SOP matches, the enquiry is **automatically escalated** and flagged for human review.

---

## FastAPI BackgroundTasks vs Celery

**Decision: FastAPI BackgroundTasks**

| Factor            | BackgroundTasks                        | Celery                                      |
|-------------------|----------------------------------------|---------------------------------------------|
| Setup             | Zero — built into FastAPI              | Requires Redis or RabbitMQ broker + worker  |
| Deployment        | Single process                         | Separate worker process(es)                 |
| Task retry        | Not built-in                           | First-class support                         |
| Monitoring        | None                                   | Flower dashboard                            |
| Fit for this task | Lightweight keyword matching           | Overkill for this scope                     |

**Rationale:** The background task here is a lightweight DB read + keyword check + DB write — it completes in milliseconds and doesn't need retries, scheduling, or distributed workers. `BackgroundTasks` gets the job done with zero infrastructure. In production, where tasks might call LLMs, send emails, or need retry logic, Celery would be the right call. The `process_enquiry(enquiry_id)` interface is designed so this swap would be a one-line change.

An additional practical consideration: Celery requires a Redis or RabbitMQ broker, and Redis has no native Windows build — it requires WSL2 or Docker Desktop. Unnecessary overhead for a prototype that runs fine without it.

---

## SQLite vs PostgreSQL

**Decision: SQLite**

SQLite is used because this is a prototype with no concurrent writers. Schema management is handled by Alembic, so switching to PostgreSQL requires only changing `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql://user:password@localhost/closira
```

No other code changes are needed — SQLAlchemy abstracts the rest.

**When to switch:** Move to PostgreSQL when you need concurrent writes, connection pooling, or multi-tenant row-level security.

---

## Alembic (Migrations)

Schema changes are managed via Alembic rather than `create_all()` at startup. This means:
- The schema has a versioned history
- Changes can be applied and rolled back cleanly
- The codebase is ready for schema evolution without manual SQL

Migration files live in `alembic/versions/`. To generate a new migration after a model change:

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

---

## Multi-Tenancy

Every `Enquiry` row has a nullable `tenant_id` column. In production, this would:
- Be populated from the authenticated JWT on every inbound request
- Be used to scope every DB query (`WHERE tenant_id = ?`)
- Have a `Tenants` table with plan limits, SOP configs, etc.

For this prototype it is stubbed as `NULL` but the schema and index are ready for it.

---

## Structured Logging

All key events emit JSON log lines to stdout:

```json
{"asctime": "2024-01-15T10:30:00", "name": "app.main", "levelname": "INFO",
 "message": "SOP matched", "enquiry_id": "abc-123", "sop": "Pricing Question", "event": "sop_matched"}
```

Key events logged: `enquiry_created`, `task_started`, `sop_matched`, `auto_escalated`, `manually_escalated`, `follow_up_scheduled`

---

## Testing the API

Full test evidence with screenshots for all endpoints and error cases is documented here:
**[API Test Evidence (Google Doc)](https://docs.google.com/document/d/1ln3wO9uXeCDw3TM4C1fVoZ95LPdiuqsH7JlvoOfGXrQ/edit?usp=sharing)**

The doc covers:
- Health check
- All 5 SOP matches (pricing, booking, complaint, after-hours, general info)
- Background task in action — terminal logs + history timeline proving async execution
- Auto-escalation (no SOP match)
- Follow-up scheduling
- Manual escalation
- Error cases: 404, 422 (invalid channel), 409 (conflict on escalated enquiry)

---

## Project Structure

```
backend/
├── alembic/
│   ├── versions/            # Migration files
│   ├── env.py               # Alembic config — imports Base for autogenerate
│   └── script.py.mako
├── app/
│   ├── main.py              # FastAPI app, lifespan, global error handler
│   ├── database.py          # SQLAlchemy engine, session, health check
│   ├── models.py            # ORM models (Enquiry, EnquiryEvent)
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── tasks.py             # Background SOP matching logic
│   ├── logger.py            # JSON structured logging setup
│   └── routes/
│       ├── enquiry.py       # /enquiry endpoints
│       └── health.py        # /health endpoint
├── alembic.ini
├── requirements.txt
├── .env.example
└── README.md
```

---

## Channel Integration (Architecture & Future Scope)

This prototype accepts enquiries via REST where the caller specifies the `channel` field. It does **not** integrate with real messaging providers — it simulates the processing layer that would sit behind them.

In production, each channel would have a dedicated ingestion adapter:

**WhatsApp** — Meta sends a webhook `POST` on every inbound message via the WhatsApp Business API. An adapter verifies the `X-Hub-Signature` header, extracts sender name and message body, and calls `POST /enquiry` with `channel: "whatsapp"`.

**Email** — SendGrid Inbound Parse or Mailgun Routes forward inbound emails as HTTP `POST` requests. An adapter parses `from`, `subject`, and `text` and calls `POST /enquiry` with `channel: "email"`.

**Phone / Call** — Twilio Voice transcribes the call and posts a transcript webhook. An adapter receives it and calls `POST /enquiry` with `channel: "call"`.

In all three cases, **the `/enquiry` endpoint and everything downstream is identical** — adapters are purely ingestion concerns. Adding a real channel requires no changes to core processing logic.

---

## Known Limitations & Trade-offs

1. **No real follow-up scheduling** — the endpoint records the intent but does not send a message after `delay_minutes`. Production would use a delayed Celery task or job scheduler.
2. **SOP matching is keyword-only** — a production system would use an LLM or classifier. The `_match_sop()` interface is designed for a drop-in replacement.
3. **No authentication** — endpoints are open. Production would add JWT middleware with tenant scoping on every query.
4. **SQLite has no concurrent write support** — fine for a prototype; switch to PostgreSQL for anything beyond local dev.
5. **BackgroundTasks shares the request process** — a crash or restart loses in-flight tasks. Celery with a persistent broker solves this.