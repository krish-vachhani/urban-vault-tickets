# Testing Strategy — Urban Vault Ticketing System

**Status:** FINALIZED  
**Backend test runner:** Django built-in test runner with Django REST Framework API testing utilities  
**Frontend test runner:** Vitest + React Testing Library + jsdom  
**Database for backend tests:** PostgreSQL  
**End-to-end framework:** Not required for this assignment

This document defines the automated and manual testing approach for the Urban Vault take-home assignment. The goal is to verify the assignment requirements and protect business rules, authorization boundaries, workflow transitions, asynchronous notification reliability, and user interactions with a focused, maintainable test suite.

## 1. Assignment testing requirements

The take-home brief requires at least four meaningful automated tests covering these areas:

1. A successful API flow **or** a business rule / invalid state transition.
2. Authentication or authorization behaviour.
3. A Celery task, including failure or retry behaviour.
4. An important frontend component or user interaction.

A large test suite is not expected. Prioritize tests that protect critical behaviour. The implementation should satisfy all four categories explicitly; do not rely on a large number of shallow tests as a substitute.

## 2. Finalized testing stack

| Area | Technology / approach | Reason |
|---|---|---|
| Backend test runner | Django built-in test runner | Already integrated with Django; no separate runner is needed |
| REST API testing | DRF `APITestCase` / `APIClient` | Exercises request/response behaviour and authentication |
| Backend test database | PostgreSQL | Matches production database engine and supports the schema's PostgreSQL constraints |
| Test data | `setUpTestData()` and small reusable test helpers | Deterministic records without introducing a fixture factory dependency |
| Celery task tests | Direct task invocation with mocked delivery dependency | Tests task logic and retry decisions without depending on a live broker for each test |
| Transaction callback tests | Django `captureOnCommitCallbacks()` | Verifies dispatch callbacks are registered/executed only after commit |
| Frontend test runner | Vitest | Integrates with the Vite toolchain |
| Frontend component tests | React Testing Library | Tests observable UI behaviour rather than component internals |
| User interactions | `@testing-library/user-event` | Simulates realistic user interactions |
| DOM environment | jsdom | Supplies a browser-like DOM for component tests |
| E2E framework | None required | A manual role-based smoke test complements the required automated tests |

Do not add pytest, Factory Boy, Playwright, or Cypress solely for this assignment. They can be future enhancements if a concrete need arises.

## 3. Backend test strategy

### 3.1 Test organization

Keep tests close to the Django app they cover:

```text
backend/
  apps/
    accounts/
      tests/
        test_authentication.py
    organizations/
      tests/
        test_reference_data_permissions.py
    tickets/
      tests/
        test_creation.py
        test_visibility.py
        test_actions.py
        test_listing.py
    notifications/
      tests/
        test_outbox.py
        test_tasks.py
```

The exact package path may follow the final app layout, but keep tests grouped by business behaviour.

### 3.2 Django and DRF conventions

- Run tests with Django's built-in test runner: `python manage.py test`.
- Use `APITestCase` / `APIClient` for endpoint-level tests.
- Use `setUpTestData()` for shared, read-only setup data within a test class. Create or modify per-test records in `setUp()` or inside the test.
- Use small reusable test helpers for creating Users, Clients, Properties, Offices, Floors, Departments, Issues, and Tickets. Do not make tests depend on the demo seed command.
- Use `force_authenticate()` for isolated authorization or view tests where token issuance is not under test.
- Include at least one authentication test that obtains a real SimpleJWT access token and sends it using `Authorization: Bearer <token>`. This verifies that the configured JWT authentication path actually works.
- Use `TransactionTestCase` (or DRF's transaction-capable equivalent) when a test must observe real transaction/commit or row-locking behaviour. Ordinary `TestCase`/`APITestCase` wraps tests in transactions and is not a substitute for every concurrency test.
- Use Django's `captureOnCommitCallbacks(execute=True)` when testing `transaction.on_commit()` dispatch registration with ordinary `TestCase`-style tests.

### 3.3 Required and recommended backend scenarios

The assignment's four categories are mandatory. The following concrete scenarios are the recommended implementation target; combine related assertions where that keeps tests readable.

| Scenario | Setup / action | Expected result |
|---|---|---|
| Successful ticket creation | Authenticated eligible user submits valid Office, same-Department Issues, and valid Floors | HTTP 201; Ticket, TicketIssue, TicketFloor, creator Activity, routing Activity, and durable notification intent are created atomically as applicable |
| Invalid mixed-Department Issues | Submit Issue IDs belonging to different Departments | HTTP 400; no Ticket, join rows, Activity, or outbox records remain |
| Ticket visibility / IDOR | A Client user requests a Ticket belonging to an unrelated Client | HTTP 404; no ticket details are disclosed |
| Real JWT authentication | Obtain SimpleJWT token through the authentication flow and request a protected endpoint | Valid token succeeds; missing/invalid/expired token is rejected according to the API authentication contract |
| Worker assignment | Current Department POC assigns a Worker belonging to the Ticket's current Department | HTTP 201; active assignment created, stage updated, Activity/outbox created transactionally |
| Invalid transition | Worker submits assessment when the Ticket is not in `PENDING_TECHNICIAN_ASSESSMENT` | HTTP 409; no assessment or partial state update |
| Assessment submission | Currently assigned Worker submits one of the three supported outcomes | Assessment created once; stage becomes `PENDING_DEPARTMENT_POC_REVIEW`; status becomes `TECHNICIAN_CLOSED`; assignment remains visible/active |
| Mark resolved | A mapped Client user, or the Ticket's creator, marks an eligible open Ticket resolved | Status becomes `CLOSED`; `closed_by` and `closed_at` populated; active assignment ended; Activity created |
| Listing behaviour | Request listing with search, filters, ordering, and page parameters | Results are role-scoped and server-paginated; filter/search/order semantics match `README-ticket-listing-api.md` |

The assignment requires only a small number of meaningful tests. Prioritize successful ticket creation or invalid transition, an actual authorization boundary, Celery failure/retry, and a frontend interaction if time becomes constrained. The remaining cases are strongly recommended because they protect our most important decisions.

### 3.4 Test authorization boundaries, not just button visibility

At minimum, test these server-side boundaries:

- A Client cannot retrieve an unrelated Client's Ticket; return 404 under the agreed non-disclosure policy.
- A Facility Manager cannot create a Ticket for an Office outside a Property they manage, even if the Client is mapped to them.
- A Department POC cannot assign a Worker to a Ticket outside their current Department.
- A Worker who is not the current assignee cannot submit an assessment.
- A historical Worker can view a Ticket under the agreed visibility rule but cannot perform current Worker actions.
- A user cannot gain permission by supplying another user's ID, Client ID, Department ID, or Ticket ID in request data.
- A user who is neither a mapped Client user nor the Ticket's creator cannot mark it resolved (`403`).
- A Department POC who created a Ticket routed to another Department can still view it.
- Login, refresh, and logout reject a missing or invalid CSRF token.

The frontend may hide unavailable controls, but backend tests must prove that direct API calls are rejected.

## 4. PostgreSQL test database

Run backend tests against PostgreSQL, not SQLite.

Reasons:

- The schema uses PostgreSQL partial unique constraints, such as one active `TicketAssignment` per Ticket.
- The application relies on PostgreSQL transaction and row-locking behaviour for concurrent state-changing actions.
- SQLite does not provide equivalent behaviour for all these constraints and locking semantics.

Django's test runner should create and tear down its dedicated test database using the configured test database settings. Never point test settings at a development, staging, or production database.

The CI/local test environment must provide a PostgreSQL service and the same migrations used by the application. Tests must not silently skip the PostgreSQL-specific constraints.

## 5. Celery and transactional outbox tests

The notification implementation is defined in `README-async-processing.md`. That document remains authoritative for outbox states, retry count, retry policy, idempotency, and recovery behaviour.

Use direct task invocation with mocked notification delivery for focused unit tests. Do not rely exclusively on Celery eager mode: eager execution does not reproduce all real worker/broker behaviour.

### 5.1 Required Celery scenarios

| Scenario | Expected result |
|---|---|
| Successful simulated delivery | Outbox row transitions to `SENT`, `sent_at` is set, and success is logged |
| Transient delivery failure | Row returns to `PENDING`; `attempt_count` increments; `next_attempt_at` is set by the backoff/jitter policy; `last_error` is sanitized |
| Retry exhaustion | A failure on the 4th attempt (counted by `attempt_count`) makes the row `FAILED` with a sanitized error summary |
| Dispatcher selection | Publishes only due, unpublished `PENDING` rows; recovers stale `PROCESSING` rows; skips rows published within the re-dispatch interval |
| Duplicate execution | Re-executing a task for a `SENT` row is a no-op and does not perform delivery again |
| Rolled-back business transaction | Outbox row is rolled back and no post-commit task is published |
| Broker publish failure after commit | Business action remains successful; outbox row remains `PENDING` for recovery |

At least one automated test must explicitly exercise failure/retry behaviour to satisfy the assignment. Include duplicate execution handling in an automated test because it is a finalized reliability decision.

### 5.2 Testing `on_commit()` dispatch

- Use `captureOnCommitCallbacks()` to verify a dispatch callback is registered and only executed after a successful transaction commit.
- Verify a rolled-back transaction does not publish a Celery task.
- Mock the broker/task publisher when testing the callback. A unit test need not require a live Redis server.
- Add one Docker-based smoke check with the actual Redis broker, Celery Worker, and the single Celery Beat dispatcher if the full environment is available; this is an integration check, not a prerequisite for every unit test run.

### 5.3 Concurrency tests

The partial unique index is the final guard against multiple active Worker assignments. If time permits, add a PostgreSQL-backed transaction test for concurrent/repeated assignment attempts using real transactions. Do not claim concurrency safety based only on a mocked unit test.

## 6. Frontend test strategy

### 6.1 Tooling

- Vitest as the test runner.
- React Testing Library for rendering and assertions.
- `@testing-library/user-event` for interactions.
- jsdom as the DOM environment.
- Mock API functions/Axios at the feature boundary; do not require a running Django server for every component test.
- For components using TanStack Query, create a fresh `QueryClient` for each test and disable query retries to keep tests deterministic.

### 6.2 Required frontend interaction test

The primary test should exercise the Ticket Creation form:

1. Render the form for a known role.
2. Select an available Client.
3. Verify the corresponding Client Offices are displayed.
4. Select an Office and verify its Floors are loaded.
5. Select one or more Issues.
6. Verify issue choices are constrained to one Department after the first Issue is selected.
7. Submit an invalid form and verify visible validation feedback.
8. Submit valid data and verify the correct API payload is sent.

This is the frontend interaction required by the assignment.

### 6.3 Recommended additional frontend test

Test role- and stage-dependent action rendering:

- Department POC sees Assign Worker / Change Department only at `PENDING_TECHNICIAN_ASSIGNMENT`.
- Current Worker sees Submit Assessment only at `PENDING_TECHNICIAN_ASSESSMENT`.
- Client (and the Ticket's creator) sees Mark Resolved for an eligible open Ticket at any of the three agreed workflow stages.
- Facility Manager does not see ticket-handling CTAs on Tickets they did not create.
- A historical Worker sees the Ticket but not the current Worker's action CTA.

These tests validate UI behaviour only. Backend authorization tests remain mandatory and authoritative.

## 7. Manual end-to-end smoke test

A full E2E automation framework is not required. Before submission, manually exercise the seeded-account flow:

1. Log in as a Client POC and create a Ticket with valid Issue and Floor selections.
2. Log in as the relevant Facility Manager and verify the Ticket is visible for the managed Property, with no handling CTA.
3. Log in as the current Department POC and assign an eligible Worker.
4. Verify the Worker receives the assigned Ticket and the simulated notification is processed.
5. Log in as the assigned Worker and submit each assessment outcome across separate seeded Tickets, verifying the stage/status changes.
6. Log in as the Client POC and mark an eligible Ticket resolved; then log in as a Facility Manager who created a Ticket and mark that Ticket resolved.
7. Verify Open/Closed tabs, Activity, assignment history, comments, search, filters, and sorting.
8. Attempt a cross-Client Ticket URL using another role/account and verify the backend returns 404.

Use multiple seeded Tickets to demonstrate pagination, filters, and sorting. Do not rely on a single sample Ticket.

## 8. Commands

Backend, from the backend project directory:

```bash
python manage.py test
```

Frontend, from the frontend project directory (define the `test` script as `vitest`):

```bash
npm run test -- --run
```

For interactive frontend watch mode:

```bash
npm run test
```

The finalized Docker Compose backend service is named `backend`; run the backend test command inside it with:

```bash
docker compose exec backend python manage.py test
```

Use the actual Compose service name if it differs. Document both commands in the final root project README.

## 9. Coverage policy

- Do not impose an arbitrary percentage coverage threshold for this assignment.
- Prefer a few meaningful tests of critical business paths over many shallow tests.
- Do not duplicate every serializer validation rule in both frontend and backend test suites. Test representative client feedback on the frontend and authoritative enforcement on the backend.
- Prioritize the four explicitly required categories first.
- Keep tests deterministic, independent, and safe to run repeatedly.
- Do not make tests depend on the order in which files or test classes execute.

## 10. Out of scope

- A large browser E2E suite.
- Performance/load testing infrastructure.
- Mutation testing.
- A mandatory coverage percentage.
- External email-provider integration tests.
- Live Redis/Celery infrastructure for every unit test.
- Tests that rely on production credentials or production data.

## 11. Implementation acceptance checklist

- [ ] `python manage.py test` runs against PostgreSQL and passes.
- [ ] At least one test covers a successful API flow or invalid business transition.
- [ ] At least one test covers authentication or backend authorization.
- [ ] At least one Celery test covers failure/retry behaviour.
- [ ] At least one frontend component/interaction test passes.
- [ ] Duplicate notification execution is tested as a no-op after delivery.
- [ ] Outbox dispatch is tested against transaction commit/rollback behaviour.
- [ ] Docker smoke check verifies the single Celery Beat scheduler dispatches due outbox work through the Redis broker.
- [ ] Ticket visibility tests cover role-specific scope and the 404 non-disclosure rule.
- [ ] Frontend tests use a fresh TanStack Query client and deterministic mocks.
- [ ] Seeded-account manual smoke test is completed and documented.
