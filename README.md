# Urban Vault Ticketing

A full-stack facility-management ticketing application built for the Urban Vault developer assignment. Clients and eligible internal employees report issues at a Client Office; a Department POC coordinates the work; an assigned Worker submits an assessment; and a mapped Client user or the ticket's creator confirms resolution.

## Features

- Four authenticated roles: Client, Facility Manager, Department POC, and Worker, with backend-enforced visibility and action permissions.
- Ticket creation with dependent Client/Office/Floor selection, same-Department Issues, history-derived Quick Issues, and client/server validation.
- Open/Closed lists with server-side pagination, Issue-text search, four filters, and Created Time sorting in both directions.
- Worker assignment, Department forwarding with a note, three assessment outcomes, and Mark Resolved.
- Activity with All/Actions/Comments filters, inline change history, structured assignment history, and comments.
- JWT login, refresh rotation, logout/account switching, and CSRF protection for cookie-based authentication operations.
- Simulated asynchronous notifications with a PostgreSQL transactional outbox, retries, duplicate protection, and recovery.

## Stack and architecture

| Layer | Implementation |
|---|---|
| Backend | Python 3.12, Django 5.2, Django REST Framework, SimpleJWT, Gunicorn |
| Data and async | PostgreSQL 17, Redis 7 as Celery broker, Celery Worker and one Beat scheduler |
| Frontend | React, TypeScript, Vite, Material UI, Tailwind CSS v4 |
| Frontend state/forms | TanStack Query, React Context for auth, React Router URL state, React Hook Form and Zod, Axios |
| Testing | Django/DRF with PostgreSQL; Vitest, React Testing Library, user-event, jsdom |
| Local runtime | Docker Compose: `frontend`, `backend`, `postgres`, `redis`, `celery-worker`, `celery-beat` |

Exact Python dependencies are pinned in [requirements.txt](backend/requirements.txt); frontend dependencies are locked in [package-lock.json](frontend/package-lock.json).

The backend is a modular monolith with four apps: `accounts`, `organizations`, `tickets`, and `notifications`. Thin views use serializers for input/output, selectors for scoped reads, and services for transactional writes. The browser calls `/api/v1` through Vite's `/api` proxy so the frontend and API share one browser origin. Production uses the same origin through CloudFront.

```text
Browser -> Vite :5173 -> Django :8000 -> PostgreSQL
                            |              |
                     after-commit      durable outbox
                       publish             |
                            v              v
                           Redis <- single Beat dispatcher
                             |
                        Celery Worker -> simulated delivery / outbox state
```

## Prerequisites

- Git and Docker with Docker Compose v2 (for example, Docker Desktop), with the Docker daemon running.
- Free host ports `5173` and `8000`, and network access to download images/dependencies.
- A POSIX-compatible shell for the commands below. Run them from the repository root unless stated otherwise.

Host Python, Node, PostgreSQL, and Redis installations are unnecessary for the Compose setup. For optional host-based frontend checks, use Node.js 24+ and npm; the frontend image uses Node 24.

## Local setup

### 1. Configure the environment

```bash
cp .env.example .env
```

Do this only on first setup; keep an existing `.env`. Edit the new file before starting:

| Variables | Local configuration |
|---|---|
| `SECRET_KEY`, `JWT_SIGNING_KEY` | Replace both placeholders with different, long random values |
| `DB_PASSWORD` | Choose a local database password |
| `SEED_DEMO_PASSWORD` | Choose the password you will enter for every seeded demo account |
| `DB_NAME`, `DB_USER`, `DB_HOST`, `DB_PORT` | Keep the example values for Compose; `DB_HOST=postgres` |
| `REDIS_URL` | Keep `redis://redis:6379/0` for Compose |
| `DEBUG`, `REFRESH_COOKIE_SECURE` | Keep `True` and `False`, respectively, for local HTTP |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Keep the supplied localhost/Compose values |
| `VITE_API_BASE_URL`, `API_PROXY_TARGET` | Keep `/api/v1` and `http://backend:8000` |
| `VITE_ENABLE_DEMO_ACCOUNTS` | `true` shows the local email picker |
| `LOG_LEVEL`, `NOTIFICATION_REDISPATCH_INTERVAL_SECONDS` | Defaults: `INFO`, `300` |

[.env.example](.env.example) contains the complete variable list with placeholders only. `.env` is ignored by Git. Vite variables are public frontend configuration: never put a password or secret in a `VITE_*` variable. Django reads process environment variables; it does not load `.env` itself. Compose supplies them.

### 2. Build, migrate, seed, and start

```bash
docker compose config --quiet
docker compose build
docker compose up -d postgres redis
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py seed_demo_data
docker compose up -d --wait
docker compose ps
```

Building first makes the shared backend image available to the API, Worker, and Beat. Migrate and seed before starting the complete application; containers do not run either command automatically.

Open **http://127.0.0.1:5173** (login: `/login`). Check **http://127.0.0.1:5173/api/v1/health/** for `{"status":"ok","database":"ok"}`. Direct backend health is also available at **http://127.0.0.1:8000/api/v1/health/**. `localhost` is also configured, but an unrelated IPv6 listener on `::1:5173` can intercept that address; use `127.0.0.1` if it returns an unexpected page or 404. Use one hostname consistently for login and subsequent requests so cookies remain on that origin.

PostgreSQL and Redis are reachable inside the Compose network, without published host ports. PostgreSQL data persists in the `postgres-data` named volume.

For an already-running stack:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo_data
```

The seed creates **14 demo users and 80 tickets** on an empty ticket database, across two Clients, two Properties, four Offices, and four Departments. Each primary account has at least 12 tickets in each tab, demonstrating pagination at the default page size of 10. Re-running refreshes demo users/reference data and resets their passwords to `SEED_DEMO_PASSWORD`; ticket creation is skipped if any tickets already exist. Historical seed data sends no notifications. See [seed behavior and all accounts](readmes/README-seed-data.md).

### 3. Sign in and try the workflow

These are fictional demo identities on the reserved `.test` domain. **The password is the value you set locally in `SEED_DEMO_PASSWORD`**; no password is supplied in this repository. The demo picker fills the email only. Sign out before selecting another account and logging in normally.

| Role | Primary demo email | Scope |
|---|---|---|
| Client POC | `chaitanya.m@urbanvault.test` | Harness |
| Facility Manager | `chandan.s@urbanvault.test` | Koramangala Hub |
| Technical Department POC | `dhananjaya.m@urbanvault.test` | Technical Department; UI label: Technical Manager |
| Worker | `prakash.k@urbanvault.test` | Technical; UI label: Technician |

Suggested walkthrough:

1. As Chaitanya, create a Harness-1317 ticket for **AC not cooling**, selecting its affected Floors.
2. As Chandan, find the ticket in the list and view its details.
3. As Dhananjaya, open it and assign Prakash Kumar.
4. As Prakash, submit an assessment. The ticket reaches **Pending Department POC Review** and remains in the Open tab as **Technician Closed**.
5. As Chaitanya, mark it resolved. It moves to Closed. Inspect Activity and comments along the way.

For forwarding, use a separate unassigned Technical ticket, forward it to IT with a note, then log in as `abdul@urbanvault.test` (IT POC). `neha.k@urbanvault.test` is an Acme-only Client account for checking Client isolation. All demo accounts use the same locally configured seed password.

## Tests and checks

With the stack running:

```bash
docker compose exec backend python manage.py test --noinput
docker compose exec frontend npm run test -- --run
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
docker compose exec backend python manage.py check
docker compose exec backend python manage.py makemigrations --check --dry-run
docker compose exec backend python manage.py migrate --check
```

Backend tests create and destroy a separate PostgreSQL test database; the configured database user needs permission to create it (the local Compose-initialized user has this). Tests include seed reproducibility, real JWT/CSRF, authorization, workflow/conflicts, concurrent writes, and notification retry/idempotency/recovery. Notification tests mock delivery/broker boundaries; external email and AWS are unnecessary.

Frontend tests cover forms, role-based controls, URL listing state, API errors, authentication, and refresh/account-switch races. From `frontend/`, optional host checks are `npm ci`, `npm run test -- --run`, `npm run typecheck`, `npm run lint`, and `npm run build`. The equivalent native backend command, from `backend/` with dependencies and process environment already configured, is `python manage.py test --noinput`.

The [Phase 7 verification record](readmes/README-phase7-verification.md) reports 376 passing backend tests and 78 passing frontend tests, plus live HTTP/Celery workflow checks. It also records the limits of that evidence: no clean-machine rebuild, visual/responsive browser audit, or live AWS deployment was claimed. See the [submission checklist](readmes/README-submission-checklist.md) for final handoff status and the [testing strategy](readmes/README-testing-strategy.md) for coverage details.

## Useful development commands

| Purpose | Command from the repository root |
|---|---|
| View application/task logs | `docker compose logs -f backend celery-worker celery-beat` |
| Check Worker responsiveness | `docker compose exec celery-worker celery -A config.celery:celery_app inspect ping` |
| Recover due/stale outbox work manually | `docker compose exec backend python manage.py dispatch_pending_notifications` |
| Run frontend tests in watch mode | `docker compose exec frontend npm run test` |
| Django shell | `docker compose exec backend python manage.py shell` |
| Create an optional local admin | `docker compose exec backend python manage.py createsuperuser` |
| Stop and keep database data | `docker compose down` |
| Restart the built stack | `docker compose up -d --wait` |

Django admin is at `http://localhost:8000/admin/`; seeded users are not admin accounts. `docker compose down -v` deletes the database volume: use it only for an intentional full local reset. Editing `.env` requires recreating the affected containers (`docker compose up -d`), rather than just restarting processes. Changing `DB_PASSWORD` does not change credentials in an existing PostgreSQL volume; retain the original local value or deliberately manage the database password.

## API overview

All paths below are relative to `/api/v1/`, use trailing slashes, and exchange JSON. Protected endpoints require a Bearer access token. Auth writes require the CSRF token from `GET auth/csrf/` in `X-CSRFToken`; refresh tokens travel only in an HttpOnly cookie.

| Methods | Paths | Purpose |
|---|---|---|
| GET | `health/` | Public API/database health |
| GET | `auth/csrf/`, `auth/me/` | CSRF bootstrap; authenticated profile |
| POST | `auth/login/`, `auth/refresh/`, `auth/logout/` | Session lifecycle |
| GET | `me/clients/`, `clients/{id}/offices/`, `client-offices/{id}/floors/` | Authorized location choices |
| GET | `departments/`, `issues/`, `clients/{id}/quick-issues/` | Issue catalogue/reference data |
| GET, POST | `tickets/` | List or create |
| GET | `tickets/filter-options/`, `tickets/{id}/` | Scoped filter choices; detail |
| GET | `tickets/{id}/eligible-workers/` | Current Department's eligible Workers |
| POST | `tickets/{id}/assign-worker/`, `tickets/{id}/change-department/` | POC actions |
| POST | `tickets/{id}/submit-assessment/`, `tickets/{id}/mark-resolved/` | Assessment and closure |
| GET | `tickets/{id}/activities/`, `tickets/{id}/history/` | Paginated feed; structured history |
| POST | `tickets/{id}/comments/` | Add a comment |

Listing parameters: `tab=open|closed`, `page`, `page_size` (1–50, default 10), `search` (Issue names), `client_id`, `department_id` (current Department), `facility_manager_id`, `workflow_stage`, and `ordering=created_at|-created_at` (default newest first).

Business errors use `{ "error": { "code": "...", "message": "...", "details": {} } }`: 400 invalid input, 401 authentication, 403 forbidden action, 404 missing/inaccessible ticket, 409 invalid transition, and 500 unexpected error. See the [API conventions](readmes/README-api-conventions.md), [reference APIs](readmes/README-reference-data-apis.md), [creation](readmes/README-ticket-creation-api.md), [listing](readmes/README-ticket-listing-api.md), and [action contracts](readmes/README-ticket-actions-api.md) for payloads and responses.

## Data model and engineering decisions

- **Relationships:** Users map to Clients through `UserClient`. A Client Office belongs to a Client and Property; Properties have a designated Facility Manager and Floors. Office/Floor and Ticket/Issue/Floor relationships use join tables. Departments have one designated POC; `DepartmentWorker` gives each Worker one Department. Tickets retain origin/current Departments, assignments, one assessment, Activity, and comments. See the [domain model](readmes/README-domain-model.md) and [schema](readmes/README-database-schema.md).
- **Audit history:** Important actions preserve actor, timestamp, and structured before/after changes. Assignment history and comments are separate records. The unified Activity feed uses database-side `UNION ALL`, ordering, and pagination.
- **Atomic writes and concurrency:** Services write ticket changes, related rows, Activity, and required outbox rows in one transaction. A separate primary-key `select_for_update()` locks competing ticket changes. PostgreSQL constraints enforce one active assignment, one assessment, and consistent closure/stage values.
- **Query optimization:** `Exists` scopes visibility and Issue search without duplicate ticket rows. `select_related` and `prefetch_related` load display relationships without per-ticket lookups; listing tests check query growth. Composite indexes cover `(current_department, status, created_at)` and `(client_office, status, created_at)`; assignment and feed indexes support their access patterns. No trigram index is added for the small Issue catalogue.
- **Frontend state:** TanStack Query owns API data and mutation invalidation; URL parameters own listing state; Context owns the session. Logout/account switching clears cached data. Access tokens stay in memory, with a rotating HttpOnly refresh cookie and coordinated refresh requests. See [backend](readmes/README-backend-architecture.md), [frontend](readmes/README-frontend-architecture.md), and [authentication](readmes/README-authentication.md).

### Redis, Celery, and reliable notifications

Notification intent is committed to PostgreSQL with the business action; an after-commit callback publishes its outbox ID to Redis. A Worker performs simulated delivery and records `SENT`. One Beat instance dispatches due work every 60 seconds, including broker-loss recovery and abandoned processing claims.

Retries use durable `next_attempt_at` scheduling: at most four delivery attempts, with 30/60/120-second backoff plus up to 20% jitter. The processing lease and default redispatch interval are five minutes. Unique event/recipient keys, row locks, and terminal-state checks make duplicates harmless after `SENT`/`FAILED`. Redis is a broker only; no result backend is used. Delivery is treated as at least once; exactly-once external delivery is not promised. See [async processing](readmes/README-async-processing.md).

## Assumptions, boundaries, and improvements

- The handling flow ends at **Pending Department POC Review**, for all three assessment outcomes. There is no subsequent POC approval/reassignment workflow or reopening. Mark Resolved remains a separate action available to a mapped Client user or the creator.
- Workflow stage, closure status, and assessment outcome are separate. `TECHNICIAN_CLOSED` stays in Open until final resolution. The UI's Ticket Status filter uses workflow stage; Concerned Department uses the current handling Department, preserving origin Department for history.
- Role-specific visibility also includes tickets the user created. Workers retain visibility through historical assignments. Visibility alone does not authorize a workflow action. Any user with visibility can comment, including after closure.
- Tickets contain Issues from one Department and at most one active Worker. Registration, password reset, uploads, real email/SMS, and live updates are outside the assignment scope.
- Compose uses development servers. The AWS approach below is documented, with no live deployment claimed. The frontend build has a non-blocking bundle-size warning; a full browser responsiveness/accessibility audit remains a review item.
- Potential follow-up improvements: measured route-level bundle splitting, browser workflow/accessibility checks, and deployment automation/operational instrumentation for the documented AWS target. These are suggestions, not implemented features or additions to this phase.

## AWS deployment note

The approved target is private S3 + CloudFront OAC for the React build, with uncached `/api/*` routed through an ALB to ECS Fargate. Separate API, Celery Worker, and single-instance Beat services share the backend image; RDS PostgreSQL stores data/outbox state, ElastiCache Redis is the broker, ECR stores images, Secrets Manager supplies secrets, and CloudWatch provides operational visibility.

The [AWS deployment and operations note](readmes/README-infrastructure-deployment.md) covers release steps, exact configuration names, static assets, security, scaling, monitoring, and recovery, including deployment work still required before production use. No AWS resources were provisioned for this submission.

## AI-assisted development disclosure

This project was developed with assistance from **OpenAI ChatGPT / Codex** and **Anthropic Claude / Claude Code**. These tools supported requirements interpretation, architecture discussions, implementation, test creation and execution, debugging, review, and documentation. Codex also assisted with integration verification/hardening and final delivery documentation. The submitted work includes AI-assisted code, tests, and prose; it is not represented as independently written without that assistance. Executed test results and verification limits are documented separately from generated suggestions.

See the [documentation index](readmes/README.md) and [final submission checklist](readmes/README-submission-checklist.md) for the detailed specifications and delivery review.
