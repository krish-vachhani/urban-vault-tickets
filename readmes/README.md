# Urban Vault — Architecture Readmes

These documents capture the product and architecture decisions discussed for the Urban Vault Full-Stack Developer take-home assignment.

They are intended to be read by both the developer and Claude Code before implementation. The documents explain not only **what** to implement, but also **why** the decisions were made and which behaviours must be preserved.

## Document index

| File | Subject | Status |
|---|---|---|
| [README-domain-model.md](README-domain-model.md) | Business entities, roles, and relationships | Finalized |
| [README-database-schema.md](README-database-schema.md) | PostgreSQL tables, fields, constraints, indexes, and transactions | Finalized; includes DepartmentWorker membership mapping |
| [README-ticket-lifecycle.md](README-ticket-lifecycle.md) | Workflow stages, ticket status, assessment outcomes, and transitions | Finalized |
| [README-authorization.md](README-authorization.md) | Ticket visibility and action permissions for all four roles | Finalized |
| [README-audit-and-communication.md](README-audit-and-communication.md) | Activity, assignment history, assessments, and comments | Finalized |
| [README-authentication.md](README-authentication.md) | JWT authentication, token lifecycle, secure browser storage, seeded-account switching, and auth endpoints | Finalized; CSRF explicitly enforced on auth views |
| [README-api-conventions.md](README-api-conventions.md) | Error envelope and codes, 404 policy, order of checks, response shapes, user summaries and role labels, filter conventions | Finalized |
| [README-seed-data.md](README-seed-data.md) | Demo accounts, organizations, Floors, Departments, Issues, and Ticket volumes for every role and listing behaviour | Finalized |
| [README-reference-data-apis.md](README-reference-data-apis.md) | Client, Office, Floor, Department, Issue, Quick Issue, and ticket-scoped eligible Worker APIs | Finalized; includes Facility Manager Property scope |
| [README-ticket-creation-api.md](README-ticket-creation-api.md) | Ticket creation request/response, role-specific validation, floor/issue rules, transactions, and side effects | Finalized |
| [README-ticket-listing-api.md](README-ticket-listing-api.md) | Role-scoped server-side pagination, Issue search, filters, filter options, sorting, `action_required`, and list response shape | Finalized; Concerned Department filter uses current Department |
| [README-ticket-actions-api.md](README-ticket-actions-api.md) | Ticket details, eligible Workers, assignment, Department forwarding, assessments, Mark Resolved, Activity, History, comments, and error/concurrency rules | Finalized; inaccessible Ticket IDs return 404 |
| [README-async-processing.md](README-async-processing.md) | Redis broker, Celery notifications, transactional outbox, durable retry scheduling (`next_attempt_at`), idempotency, and recovery | Finalized |
| [README-frontend-architecture.md](README-frontend-architecture.md) | React + TypeScript + Vite, MUI + Tailwind v4, React Router, TanStack Query, Context, React Hook Form + Zod, Axios/JWT interceptors, and Vitest + React Testing Library | Finalized |
| [README-backend-architecture.md](README-backend-architecture.md) | Django app boundaries, DRF views/serializers/permissions, selectors, service layer, transactions, and cross-app dependencies | Finalized |
| [README-testing-strategy.md](README-testing-strategy.md) | Django/DRF API tests, PostgreSQL test database, Celery retry/idempotency tests, React interaction tests, and manual smoke test | Finalized |
| [README-infrastructure-deployment.md](README-infrastructure-deployment.md) | Docker Compose, ECS Fargate, CloudFront/S3 OAC, ALB routing, RDS, ElastiCache, Celery Beat, secrets, scaling, monitoring, and recovery | Finalized |
| [README-implementation-plan.md](README-implementation-plan.md) | Dependency-ordered Claude Code prompts, assignment-scope traceability, phase acceptance criteria, Git checkpoints, and completion gate | Finalized |

## How to use these documents

1. Read `README-domain-model.md` and `README-database-schema.md` before creating Django models or migrations.
2. Read `README-ticket-lifecycle.md` before implementing ticket actions or status changes.
3. Read `README-authorization.md` before implementing querysets, permissions, or action endpoints.
4. Read `README-audit-and-communication.md` before implementing activity, comments, assignment history, or assessments.
5. If a document identifies an item as **Open implementation detail**, do not silently invent a business rule. Resolve it in the architecture discussion or record the chosen assumption before implementation.
6. Read `README-reference-data-apis.md` before implementing Client/Office/Floor/Department/Issue dropdowns, Quick Issues, or the ticket-scoped eligible-Workers endpoint.
7. Read `README-ticket-creation-api.md` before implementing `POST /api/v1/tickets/`; its role-specific Office scope and validation rules are authoritative.
8. Read `README-ticket-listing-api.md` and `README-ticket-actions-api.md` before implementing Ticket listing, detail, and action endpoints. The action README is authoritative for the 404 policy, action preconditions, transaction boundaries, and concurrency checks.
9. Read `README-async-processing.md` before implementing `NotificationOutbox`, Celery notification tasks, Redis broker configuration, retries, idempotency, or the recovery command.
10. Read `README-frontend-architecture.md` before implementing React providers, routing, server-state queries/mutations, cache invalidation, forms, Axios/JWT interceptors, frontend styling, tests, or feature folder structure. All frontend library and responsibility choices in that document are finalized.
11. Read `README-backend-architecture.md` before creating Django apps, views, serializers, permission classes, selectors, service functions, or cross-app imports. It is authoritative for the modular monolith and service-layer boundaries.
12. Read `README-testing-strategy.md` before writing backend, Celery, or frontend tests. It defines the required test categories, PostgreSQL test database, test tooling, retry/idempotency cases, and manual smoke-test flow.
13. Read `README-infrastructure-deployment.md` before writing Docker Compose files, container commands, health checks, environment examples, or the AWS deployment note. It is authoritative for the six local services and the production AWS topology.
14. Read `README-api-conventions.md` before implementing any endpoint, serializer, exception handler, or frontend error handling.
15. Read `README-seed-data.md` before implementing the `seed_demo_data` command or the login screen's demo-account picker.
16. Read `README-implementation-plan.md` before starting implementation. It defines the dependency order, one-prompt-at-a-time Claude Code workflow, assignment-scope traceability, phase acceptance criteria, Git checkpoints, and final scope-completion gate. It does not allocate time or permit requirements to be omitted.

## Source of truth and change process

- A decision labelled **Finalized** is an agreed product/architecture decision and must not be changed independently during implementation.
- A section labelled **Open implementation detail** or **Proposed assumption** is not a finalized decision.
- If a decision changes, update the relevant README and any dependent README before changing code.
- Do not leave contradictory versions of a decision in different documents.

## Assignment boundary

The implementation must follow the supplied take-home brief and wireframe. These define the required scope; implementation planning must not downgrade explicit requirements based on schedule or convenience. The documented workflow ends when the Worker submits an assessment and the ticket reaches **Pending Department POC Review**. Do not invent later department-review or resolution workflows beyond the agreed `Mark Resolved` action (a mapped Client user or the Ticket's creator).

## Decision log

Decisions made after the feature READMEs were first finalized. Each is applied to the documents listed.

| Date | ID | Decision | Documents updated |
|---|---|---|---|
| 2026-11-02 | B1 | Mark Resolved is allowed for a Client user mapped to the Ticket's Client **or** the Ticket's creator (matches the wireframe's internal-creation frame) | authorization, lifecycle, actions-api, schema, audit, domain, testing, plan |
| 2026-11-02 | B2 | Every user can view the Tickets they created, in addition to their role rule | authorization, listing-api, creation-api, domain, testing |
| 2026-11-02 | B3 | New `GET /api/v1/tickets/filter-options/`, derived only from the user's visible Tickets | listing-api, reference-data, frontend |
| 2026-11-02 | B4 | No assessment note field; Workers add context with an ordinary comment | audit |
| 2026-11-02 | I1 | `last_dispatched_at` (and `next_attempt_at`, see R3) added to the NotificationOutbox schema table | schema, async |
| 2026-11-02 | I2 | Assessment writes one `ASSESSMENT_SUBMITTED` Activity entry containing the outcome and status change; `CLIENT_RESOLVED` renamed `TICKET_RESOLVED` | lifecycle, actions-api, audit, schema |
| 2026-11-02 | I4 | Inaccessible Tickets always return `404` | authorization, listing-api, reference-data, api-conventions |
| 2026-11-02 | I5 | Activity items carry `change` (before → after) for inline History; `/history/` endpoint retained | actions-api, audit, schema, frontend |
| 2026-11-02 | G1–G2, G5 | Error envelope and codes, response shapes, role labels | api-conventions (new) |
| 2026-11-02 | G3 | Seed data specification | seed-data (new) |
| 2026-11-02 | G4 | Server-computed `action_required` flag for the "Action Required" badge | listing-api, actions-api, frontend |
| 2026-11-02 | G6 | Screen/route inventory and wireframe details | frontend |
| 2026-11-02 | G7 | Complete environment-variable list | infrastructure |
| 2026-11-02 | G8 | Ticket-creation notifications link to the `TICKET_ROUTED` Activity | creation-api, async |
| 2026-11-02 | R1 | Visibility via `Exists(...)`; state changes lock the Ticket with a separate primary-key query | authorization, listing-api, actions-api, lifecycle, schema, backend |
| 2026-11-02 | R2 | CSRF explicitly enforced on login/refresh/logout, with tests | authentication, frontend, testing, plan |
| 2026-11-02 | R3 | One retry mechanism: durable `next_attempt_at` scheduling, `attempt_count` authoritative (max 4), no Celery `self.retry()`; retry delays 30/60/120 s; Beat every 60 s; five-minute PROCESSING lease | async, schema, infrastructure, testing, plan |
| 2026-11-02 | R4 | Activity feed is a paginated SQL `UNION ALL`, never merged in Python | actions-api |

## Root project README

These feature readmes do not replace the repository's root `README.md`. The root project README is still required for prerequisites, setup and run instructions, test commands, API overview, architecture summary, actual time spent, limitations, AI-tool disclosure, and a concise AWS deployment summary. `README-infrastructure-deployment.md` is the detailed source for the AWS architecture and Docker Compose requirements.
