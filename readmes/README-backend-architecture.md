# Backend Architecture — Urban Vault Ticketing System

**Status:** FINALIZED  
**Backend:** Python, Django, Django REST Framework  
**Database:** PostgreSQL  
**Async processing:** Redis + Celery

This document defines how the agreed product and database design should be organized in Django. It is an implementation architecture for the take-home assignment: use clear boundaries and testable business operations without introducing infrastructure or abstraction layers that are outside the agreed scope.

Testing conventions and the required backend/Celery scenarios are defined in `README-testing-strategy.md`. Keep business-service tests focused on their transaction, authorization, and state-transition guarantees.

## 1. Architecture decision

Use a **modular Django monolith**: one Django project, one deployable backend, one PostgreSQL database, and four Django apps grouped by business responsibility.

The four apps are:

1. `accounts`
2. `organizations`
3. `tickets`
4. `notifications`

Do not split the system into microservices. Do not introduce Kafka, a repository framework, event sourcing, or a generic domain-engine layer.

## 2. Django app boundaries and ownership

### 2.1 `accounts`

Owns authentication and the single custom User model.

Responsibilities:

- Custom User model with one role: `CLIENT`, `FACILITY_MANAGER`, `DEPARTMENT_POC`, or `WORKER`.
- SimpleJWT login, refresh-cookie, logout, and current-user endpoints.
- Authentication-related serializers and views.
- User identity response used by the frontend.

The User model must not contain `department_id`. Department membership is represented in the `organizations` app as described below. `accounts` is a foundational app and must not import `organizations` models.

If the app packages live under the suggested `apps/` directory, configure their `AppConfig.label` values as `accounts`, `organizations`, `tickets`, and `notifications`, while their Python `name` values may be `apps.accounts`, `apps.organizations`, `apps.tickets`, and `apps.notifications`. This keeps model labels such as `accounts.User` stable for `AUTH_USER_MODEL` and string foreign-key references. Alternatively, place the app packages directly at the Python import root and keep the same labels.

### 2.2 `organizations`

Owns organizational and physical-location reference data.

Models:

- `Client`
- `UserClient`
- `Property`
- `ClientOffice`
- `Floor`
- `ClientOfficeFloor`
- `Department`
- `DepartmentWorker`
- `Issue`

Responsibilities:

- Client-to-user mappings.
- Property-to-Facility-Manager mapping.
- Client Office and Floor relationships.
- Organization-wide Departments.
- Designated Department POC relationship.
- Worker-to-Department membership.
- Issue catalogue and Issue-to-Department classification.
- Read APIs for reference data and ticket form dropdowns.

`Department.poc_user` is a one-to-one relationship to the designated POC User. `DepartmentWorker` maps a Worker to a Department; `DepartmentWorker.worker_id` is unique so one Worker can belong to at most one Department. Do not duplicate this membership as `User.department_id`.

The `organizations` app may reference the custom User model through `settings.AUTH_USER_MODEL`; `accounts` must not import `organizations` models. Validate role relationships in organization services/serializers.

### 2.3 `tickets`

Owns the ticketing business domain.

Models:

- `Ticket`
- `TicketIssue`
- `TicketFloor`
- `TicketAssignment`
- `TicketAssessment`
- `TicketActivity`
- `TicketComment`

Responsibilities:

- Ticket creation and role-aware validation.
- Server-side listing, filtering, search, ordering, and pagination.
- Ticket detail and action-availability response.
- Department routing and forwarding.
- Worker assignment and assignment history.
- Worker assessment and Mark Resolved.
- Activity timeline, assignment/Department history, and comments.
- Ticket-specific visibility and action authorization.

The Ticket stores immutable `origin_department_id` and mutable `current_department_id`. Derive the current Department POC from `current_department.poc_user`; derive the current Worker from the active `TicketAssignment`.

### 2.4 `notifications`

Owns asynchronous notification delivery.

Models and modules:

- `NotificationOutbox`
- Celery notification tasks.
- Outbox creation/dispatch helpers.
- Pending/stale outbox recovery command.

The outbox records durable notification intent in PostgreSQL. Redis is the Celery broker. The Celery worker executes the simulated notification. The `tickets` business operation creates the required outbox row inside the same transaction as its ticket changes; task publication happens after commit.

Use lazy/string model references for `NotificationOutbox` foreign keys to `tickets.Ticket` and `tickets.TicketActivity`, and `accounts.User`, to avoid model-import cycles. Keep imports between app services deliberate; do not import ticket models at module import time from the notification model module.

## 3. Suggested project structure

Use this as a practical starting point. Do not create empty folders or split every small file prematurely.

```text
backend/
  manage.py
  config/
    __init__.py
    settings.py
    urls.py
    celery.py
    env.py          # environment-variable helpers; settings fail fast when misconfigured
    health.py       # GET /api/v1/health/ for Docker and load-balancer health checks
    asgi.py
    wsgi.py
  apps/
    accounts/
      __init__.py
      apps.py
      models.py
      serializers.py
      views.py
      urls.py
      services.py
      tests/
    organizations/
      __init__.py
      apps.py
      models.py
      serializers.py
      selectors.py
      views.py
      urls.py
      services.py
      tests/
    tickets/
      __init__.py
      apps.py
      models.py
      serializers.py
      permissions.py
      selectors.py
      views.py
      urls.py
      services.py
      tests/
    notifications/
      __init__.py
      apps.py
      models.py
      services.py
      tasks.py
      management/
        commands/
          dispatch_pending_notifications.py
      tests/
  requirements.txt
  Dockerfile
```

`.env.example` lives at the repository root, where Docker Compose reads it.

A dedicated serializer/test subpackage can be introduced when a file becomes unwieldy. Keep the final structure understandable and proportionate to the scope.

## 4. Layer responsibilities

### 4.1 Models

Models define:

- Database fields and relationships.
- `Meta` constraints and indexes.
- Simple model-level properties or methods that are intrinsic to one entity.

Models should not contain HTTP request/response handling, call Celery tasks directly, send notifications, or become the location for the entire ticket workflow.

Use Django model constraints for invariants that PostgreSQL can enforce, including uniqueness, the one-active-Worker partial unique constraint, and valid field combinations where practical.

### 4.2 Serializers

Use DRF serializers for:

- Request payload shape and field validation.
- Primitive validation such as required fields, valid choices, non-empty text, and list shape.
- Response serialization.
- Mapping validated input into calls to service functions.

For business operations with multiple related writes, do not hide the whole workflow inside `ModelSerializer.create()` or `update()`. The view should validate input through a serializer and call a clearly named service function.

Use distinct request and response serializers where their responsibilities differ. Do not accept client-supplied authoritative values such as creator, current/origin Department, workflow stage, status, current POC, current Worker, or closure fields.

### 4.3 Views and ViewSets

Use DRF `GenericViewSet` with only the required mixins for Ticket resources (list, retrieve, create) and explicit `@action` methods for business operations. Do not expose generic Ticket update/delete actions or a broad `ModelViewSet` surface that permits arbitrary state changes.

Use read-only generic viewsets or APIViews for reference data as appropriate. Use APIViews for small authentication endpoints if they are clearer than a ViewSet.

Views should remain thin:

1. Authenticate and apply permissions.
2. Resolve the authorized object/queryset.
3. Validate request data with a serializer.
4. Call a service for a business write.
5. Serialize the result and return the appropriate HTTP response.

Views must not contain multi-step transaction orchestration.

### 4.4 Permissions and object scope

Use DRF `IsAuthenticated` as the default for protected endpoints, plus focused custom permission classes where role-level checks improve clarity.

Ticket visibility must be applied in the queryset/selector before retrieving or serializing a Ticket. An inaccessible Ticket ID returns `404`, following the agreed anti-enumeration policy. A user who can view a Ticket but cannot perform a particular action receives `403`; an invalid workflow state receives `409`.

Do not rely on hidden frontend controls or `available_actions` flags as authorization. Action services must recheck role, relationships, ticket scope, workflow stage, status, and current assignment.

### 4.5 Selectors

Selectors contain reusable read-only ORM queries. Use them for non-trivial query construction so the same visibility rules and optimized query shapes are not reimplemented inconsistently.

Examples:

- `tickets/selectors.py`: authorized Ticket queryset, ticket list/detail querysets, filter options, eligible Workers, Activity, and History. Build visibility with `Exists(...)` subqueries, including the creator rule (`README-authorization.md` §1).
- `organizations/selectors.py`: the authenticated user's Clients, role-scoped Client Offices, mapped Floors, searchable Issues, and Departments.

Selectors may use `select_related()`, `prefetch_related()`, annotations, and filtering. They must not perform business writes.

### 4.6 Services

Services implement business operations and own transaction boundaries.

Required ticket service operations include:

- `create_ticket(...)`
- `assign_worker(...)`
- `change_department(...)`
- `submit_assessment(...)`
- `mark_ticket_resolved(...)`
- `add_ticket_comment(...)` (may be a small service if authorization/audit side effects are needed)

Each state-changing service should:

1. Start `transaction.atomic()` where multiple related writes must succeed or fail together.
2. When concurrent state changes can race, confirm visibility first and then lock the Ticket with a separate primary-key query: `Ticket.objects.select_for_update().get(pk=...)` (`README-authorization.md` §5).
3. Revalidate business preconditions against current database state.
4. Apply related model changes.
5. Create required `TicketActivity` records.
6. Create required `NotificationOutbox` records within the same transaction.
7. Publish/dispatch only after commit through `transaction.on_commit()` or the agreed outbox dispatcher mechanism.

Do not trust a check performed only in a prior GET request or serializer validation; recheck race-sensitive rules inside the service transaction.

### 4.7 Celery tasks

Celery tasks belong to `notifications` and should receive an outbox record ID, not a large serialized Ticket/User object. The task loads and locks the outbox row, checks its status/idempotency, performs simulated delivery, updates its durable state, and retries only transient delivery failures according to `README-async-processing.md`.

## 5. API style

- Version REST APIs under `/api/v1/`.
- Use resource endpoints for reads and creation.
- Use explicit action endpoints for business transitions, e.g. `/tickets/{id}/assign-worker/`, `/change-department/`, `/submit-assessment/`, and `/mark-resolved/`.
- Do not expose an unrestricted `PATCH /tickets/{id}/` for business state.
- Use appropriate status codes: 201 for creation, 200 for successful action/read, 400 for invalid fields, 401 for unauthenticated, 403 for action permission denied, 404 for inaccessible/nonexistent resources, and 409 for invalid transition/conflict.
- Normalize errors with the error envelope defined in `README-api-conventions.md`, produced by one DRF exception handler; do not leak stack traces, secrets, or sensitive data.

## 6. Cross-app dependency rules

Keep the dependency structure simple:

- `accounts` is foundational and does not import models from other apps.
- `organizations` references `accounts.User` through `settings.AUTH_USER_MODEL`.
- `tickets` references `accounts.User` and `organizations` models.
- `notifications` references User, Ticket, and TicketActivity using Django model references; notification model definitions must not import ticket model Python classes at module load time.
- `tickets` may call a notification service to create outbox rows, but avoid circular module imports. Keep the notification model independent through string foreign keys and isolate task dispatch in `notifications`.

Set `AUTH_USER_MODEL = "accounts.User"` before creating the first migration. Create the initial custom User migration first; do not swap the user model after other app migrations have been applied.

## 7. Decisions deliberately not adopted

Do not introduce:

- Microservices or separate databases per app.
- Repository pattern or generic repository base classes.
- Event sourcing.
- Kafka or RabbitMQ.
- CQRS infrastructure beyond simple read-only selectors and write services.
- A generic workflow engine.
- A permission framework beyond DRF permissions plus explicit scoped selectors and service checks.
- Unrestricted model CRUD for Ticket state.

The modular monolith, selectors, serializers, permission classes, and services provide sufficient separation for this application.

## 8. Implementation acceptance criteria

- Exactly four Django apps are used for the agreed business boundaries: `accounts`, `organizations`, `tickets`, and `notifications`.
- The custom User model lives in `accounts` and is configured before initial migrations.
- `User` has no `department_id`; POC membership is represented by `Department.poc_user`, and Worker membership by `DepartmentWorker`.
- `DepartmentWorker.worker_id` is unique and references a User with role `WORKER`.
- Ticket business writes go through explicit services with appropriate transactions and row locking.
- Ticket visibility is consistently scoped before detail retrieval and listing serialization.
- Views remain thin and use serializers, permissions, selectors, and services for their distinct responsibilities.
- Ticket state cannot be changed through a generic unrestricted update endpoint.
- Notification outbox writes occur in the same transaction as the related ticket action and dispatch is deferred until commit.
- No repository framework, microservices, or event-sourcing layer is added.


## Infrastructure reference

Docker Compose service names, container commands, the single-instance Celery Beat scheduler, and the AWS deployment topology are defined in `README-infrastructure-deployment.md`. Do not define a conflicting container/service topology here.
