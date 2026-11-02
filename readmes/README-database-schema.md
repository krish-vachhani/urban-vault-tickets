# Database Schema — Urban Vault Ticketing System

**Status:** LOGICAL SCHEMA FINALIZED  
**Database:** PostgreSQL  
**Backend:** Django and Django REST Framework

This document translates the agreed domain model into relational tables, fields, constraints, indexes, and transaction expectations. Implement the schema through Django models and migrations.

## 1. Schema principles

1. Use a custom Django User model from the beginning, based on `AbstractUser` or an equivalent Django-supported custom-user base.
2. Use relational tables and explicit join tables for the agreed many-to-many relationships.
3. Store original and current Department separately on Ticket.
4. Derive relationships such as current POC and current Worker rather than redundantly storing them on Ticket.
5. Preserve assignment and audit history.
6. Enforce uniqueness and row-level integrity in PostgreSQL where possible.
7. Enforce cross-table business rules and authorization in Django services/serializers.
8. Use transactions for multi-row business operations.

## 2. Tables

The logical schema contains 18 tables, including the `DepartmentWorker` membership mapping and the durable `NotificationOutbox` required by the Celery design.

### 2.1 `User`

One custom authentication/user table for all four roles.

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `name` | VARCHAR(150) | Required display name |
| `email` | VARCHAR(255) | Required, unique login identifier |
| `password` | Django password field | Store only Django's password hash |
| `role` | Choice field | `CLIENT`, `FACILITY_MANAGER`, `DEPARTMENT_POC`, `WORKER` |
| `is_active` | Boolean | Default true |
| `date_joined` | Timestamp | Django account creation time |

A User has one role. Department membership is deliberately not stored on User: the designated POC is represented by `Department.poc_user`, while Worker membership is represented by `DepartmentWorker`. Use Django authentication and password hashing; never store plaintext passwords.

### 2.2 `Client`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `name` | VARCHAR(255) | Required |
| `is_active` | Boolean | Default true |

### 2.3 `UserClient`

Explicit many-to-many mapping between User and Client.

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `user_id` | FK → User | Required |
| `client_id` | FK → Client | Required |
| `created_at` | Timestamp | Mapping creation time |

Constraint: unique `(user_id, client_id)`. This mapping is available for all roles. Its authorization meaning depends on the User's role.

### 2.4 `Property`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `name` | VARCHAR(255) | Required |
| `address` | Text | Required or nullable based on seed-data needs |
| `facility_manager_id` | FK → User | Required; designated Facility Manager |
| `is_active` | Boolean | Default true |

One Property has exactly one designated Facility Manager. A Facility Manager may be assigned multiple Properties. Validate that the referenced User has role `FACILITY_MANAGER`.

### 2.5 `ClientOffice`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `client_id` | FK → Client | Required |
| `property_id` | FK → Property | Required |
| `name` | VARCHAR(255) | Required display name |
| `code` | VARCHAR(100) | Optional stable office code |
| `is_active` | Boolean | Default true |

If `code` is used, enforce uniqueness within a Client, for example with a conditional unique constraint on `(client_id, code)` when code is non-empty.

### 2.6 `Floor`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `property_id` | FK → Property | Required physical owner |
| `name` | VARCHAR(100) | Required |

Constraint: unique `(property_id, name)`.

### 2.7 `ClientOfficeFloor`

Join table representing which physical Floors a Client Office occupies.

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `client_office_id` | FK → ClientOffice | Required |
| `floor_id` | FK → Floor | Required |

Constraint: unique `(client_office_id, floor_id)`. Application validation must ensure the Client Office and Floor belong to the same Property.

### 2.8 `Department`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `name` | VARCHAR(100) | Required, unique |
| `poc_user_id` | One-to-one FK → User | Required designated POC |
| `is_active` | Boolean | Default true |

Validate that the designated POC has role `DEPARTMENT_POC`. The one-to-one relationship ensures a POC cannot be designated for multiple Departments. The POC's Department membership is represented by this relationship; do not expect a `department_id` field on User.

### 2.9 `DepartmentWorker`

Explicit membership mapping between a Department and its Workers. This is the approved refinement to the earlier draft that placed `department_id` directly on User.

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `department_id` | FK → Department | Required |
| `worker_id` | One-to-one FK → User | Required; must reference a User with role `WORKER` |
| `created_at` | Timestamp | Mapping creation time |

The unique `worker_id` relationship ensures a Worker belongs to at most one Department. Each Department can have multiple `DepartmentWorker` rows. Validate the Worker's role in the application. Do not add a `department_id` field to User. A user designated as a Department POC must not also be registered as a Worker.

### 2.10 `Issue`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `name` | VARCHAR(255) | Required |
| `department_id` | FK → Department | Required |
| `is_active` | Boolean | Default true |

Constraint: unique `(department_id, name)`. Each Issue belongs to exactly one Department.

### 2.11 `Ticket`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `client_office_id` | FK → ClientOffice | Required |
| `created_by_id` | FK → User | Required |
| `origin_department_id` | FK → Department | Required, immutable after creation |
| `current_department_id` | FK → Department | Required, mutable only through Department-forwarding operation |
| `workflow_stage` | Choice field | Three stages defined in lifecycle README |
| `status` | Choice field | `OPEN`, `TECHNICIAN_CLOSED`, `CLOSED` |
| `description` | Text, nullable | Optional for Client-created tickets; required for internal-created tickets |
| `closed_by_id` | Nullable FK → User | Set when an authorized user (mapped Client user or the Ticket's creator) marks the Ticket resolved |
| `closed_at` | Nullable timestamp | Set when the Ticket is marked resolved |
| `created_at` | Timestamp | Creation time |
| `updated_at` | Timestamp | Last update time |

At creation, derive the origin Department from the selected Issue(s), after validating that all selected Issues share one Department. Set `current_department_id` to the same Department initially.

Do not store `client_id`, `facility_manager_id`, `current_poc_id`, or `current_worker_id` redundantly on Ticket. Derive them through the relationships documented in `README-domain-model.md`.

The human-readable ticket reference may be rendered as `TKT-{id}`. Whether to persist a separate public ticket-number column is an implementation detail; do not introduce a second identifier unless there is a concrete need.

### Ticket status/stage consistency

Enforce these combinations with a database CheckConstraint where practical:

| `workflow_stage` | Allowed `status` |
|---|---|
| `PENDING_TECHNICIAN_ASSIGNMENT` | `OPEN`, `CLOSED` |
| `PENDING_TECHNICIAN_ASSESSMENT` | `OPEN`, `CLOSED` |
| `PENDING_DEPARTMENT_POC_REVIEW` | `TECHNICIAN_CLOSED`, `CLOSED` |

A separate check should require `closed_by_id` and `closed_at` to be either both null or both populated. A closed ticket must have both populated. Enforce this as: `status = CLOSED` if and only if both closure fields are populated.

### 2.12 `TicketIssue`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | FK → Ticket | Required |
| `issue_id` | FK → Issue | Required |

Constraint: unique `(ticket_id, issue_id)`. Application validation must ensure every Issue selected for a Ticket belongs to the same Department. The Ticket's `origin_department_id` is the snapshot of that initial Department.

### 2.13 `TicketFloor`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | FK → Ticket | Required |
| `floor_id` | FK → Floor | Required |

Constraint: unique `(ticket_id, floor_id)`. Application validation must ensure every selected Floor is mapped to the Ticket's Client Office.

### 2.14 `TicketAssignment`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | FK → Ticket | Required |
| `worker_id` | FK → User | Required Worker |
| `assigned_by_id` | FK → User | Required Department POC |
| `assigned_at` | Timestamp | Required |
| `ended_at` | Nullable timestamp | Null means active assignment |
| `end_reason` | Nullable choice/text | Reason assignment ended |

Enforce at most one active Worker assignment per Ticket with a PostgreSQL partial unique constraint on `ticket_id` where `ended_at IS NULL`.

Validate that the assigned User has role `WORKER` and has a `DepartmentWorker` row for the Ticket's `current_department_id` at assignment time.

The assignment remains active after assessment submission so the Worker remains the displayed/current assignee during Department POC Review. End it when the ticket is reassigned or finally closed. The assignment data model supports historical reassignment, but a post-assignment reassignment UI/action is not required by the supplied wireframe.

### 2.15 `TicketAssessment`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | One-to-one FK → Ticket | At most one assessment per Ticket |
| `submitted_by_id` | FK → User | Required assigned Worker |
| `outcome` | Choice field | `FULLY_RESOLVED`, `PARTIALLY_RESOLVED`, `CHANGE_REQUESTED` |
| `submitted_at` | Timestamp | Required |

Only the currently assigned Worker may submit the assessment, and only while the Ticket is at `PENDING_TECHNICIAN_ASSESSMENT` with status `OPEN`.

### 2.16 `TicketActivity`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | FK → Ticket | Required |
| `actor_id` | Nullable FK → User | Null for system-generated activity |
| `event_type` | Choice/string | Required event code |
| `description` | Text | Human-readable timeline description |
| `metadata` | JSONField / PostgreSQL JSONB | Structured event details; default empty object |
| `created_at` | Timestamp | Required |

Activity records are append-only at the application level. Do not provide ordinary update or delete endpoints for them.

Event codes: `TICKET_CREATED`, `TICKET_ROUTED`, `WORKER_ASSIGNED`, `DEPARTMENT_CHANGED`, `ASSESSMENT_SUBMITTED`, and `TICKET_RESOLVED`.

- Assessment submission writes **one** `ASSESSMENT_SUBMITTED` entry that also records the status change; there is no separate Technician Closed entry (Phase 0 audit, I2).
- `TICKET_RESOLVED` replaces the earlier `CLIENT_RESOLVED` name because the Ticket's creator may also resolve it.
- For events that change the assignee, Department, or status, `metadata` contains a `change` object (`field`, `from`, `to`) with display-ready values. The Activity API returns it so the frontend can draw the wireframe's inline before → after History (Phase 0 audit, I5). `DEPARTMENT_CHANGED` also stores the forwarding note.

### 2.17 `TicketComment`

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | FK → Ticket | Required |
| `author_id` | FK → User | Required |
| `body` | Text | Required, non-empty after trimming |
| `created_at` | Timestamp | Required |

Comments are separate from Activity actions. The Activity endpoint can combine Activity and Comment records into a chronological feed.


### 2.18 `NotificationOutbox`

Durable record of a notification that must be delivered asynchronously. The outbox row is created in the same PostgreSQL transaction as the Ticket action that requires the notification. PostgreSQL, not Redis, is the source of truth for notification intent and delivery state.

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | FK → Ticket | Required |
| `source_activity_id` | FK → TicketActivity | Required; Activity that caused the notification |
| `recipient_id` | FK → User | Required |
| `event_type` | Choice/string | Required notification event |
| `idempotency_key` | VARCHAR(255) | Required, unique; derived from source Activity and recipient |
| `payload` | JSONField / PostgreSQL JSONB | Minimal notification/template data; default empty object |
| `status` | Choice field | `PENDING`, `PROCESSING`, `SENT`, `FAILED` |
| `attempt_count` | Positive integer | Default 0; counts total delivery attempts, including the initial attempt. Authoritative retry limit: at most 4 attempts |
| `processing_started_at` | Nullable timestamp | Used to recover stale PROCESSING rows after worker loss |
| `next_attempt_at` | Timestamp | Required; when the row is next due for delivery. Creation time initially; a backoff time after a transient failure |
| `last_dispatched_at` | Nullable timestamp | Last successful broker publish for the current attempt; cleared when a retry is scheduled |
| `last_error` | Nullable text | Sanitized error summary; never store tokens or secrets |
| `created_at` | Timestamp | Required |
| `updated_at` | Timestamp | Required |
| `sent_at` | Nullable timestamp | Set on successful simulated delivery |

Add a unique constraint on `idempotency_key`, a constraint `0 <= attempt_count <= 4`, and indexes on `(status, next_attempt_at)` and `(ticket_id, created_at)`. Use protective deletion behaviour for referenced Ticket, Activity, and User records.

The Celery task receives the outbox row ID, locks the row, and treats SENT/terminal FAILED records as no-ops. Notification retry and broker recovery behaviour are specified in `README-async-processing.md`.

## 3. Key database constraints

Implement at least the following:

- unique User email;
- unique `(user_id, client_id)` in `UserClient`;
- unique Department name;
- one designated POC per Department (`Department.poc_user` one-to-one);
- unique `DepartmentWorker.worker_id` so a Worker belongs to at most one Department;
- unique `(property_id, floor.name)`;
- unique `(department_id, issue.name)`;
- unique `(client_office_id, floor_id)`;
- unique `(ticket_id, issue_id)`;
- unique `(ticket_id, floor_id)`;
- at most one active `TicketAssignment` per Ticket;
- at most one `TicketAssessment` per Ticket;
- assignment end time must not precede assignment start time;
- Ticket closure fields must be mutually consistent;
- Ticket workflow stage and status must be a permitted combination;
- unique `NotificationOutbox.idempotency_key`;
- `NotificationOutbox.attempt_count` between 0 and 4.

## 4. Cross-table business validation

These rules involve multiple rows/tables and should be enforced in Django service/serializer logic, inside transactions where relevant:

- Property's designated manager must have role `FACILITY_MANAGER`.
- Department's designated POC must have role `DEPARTMENT_POC`; the Department-to-POC relationship is stored on `Department.poc_user`. Every active POC account must be designated for exactly one Department.
- A Worker must have exactly one `DepartmentWorker` membership; `DepartmentWorker.worker_id` is unique. Every active Worker account must have exactly one such mapping. Client and Facility Manager users do not require Department membership.
- A user designated as a Department POC must not also appear as a Worker in `DepartmentWorker`.
- Ticket creator must have an eligible role and be mapped to the selected Client.
- Selected Client Office must belong to the selected Client.
- Selected Client Office must be mapped to the selected Client's Property.
- All selected Issues must belong to one Department.
- Selected Floors must be occupied by/mapped to the selected Client Office.
- Assigned Worker must belong to the Ticket's current Department.
- Only the authorized current Department POC may assign or forward a Ticket.
- Only the currently assigned Worker may submit the assessment.
- Only a Client user mapped to the Ticket's Client, or the Ticket's creator, may mark the Ticket resolved.
- A closed Ticket cannot undergo further workflow transitions.

## 5. Indexing strategy

Create indexes for the listing and detail access patterns required by the assignment. Candidate indexes:

| Table | Index | Query supported |
|---|---|---|
| `Ticket` | `(current_department_id, status, created_at)` | Department POC listing, status filter, chronological ordering |
| `Ticket` | `(client_office_id, status, created_at)` | Office/Client listing, status filter, chronological ordering |
| `DepartmentWorker` | `(department_id, worker_id)` or the indexed `department_id` FK plus unique `worker_id` | Eligible Worker lookup for the Ticket's current Department |
| `TicketAssignment` | `(worker_id, ticket_id)` | Current and historical Worker visibility |
| `TicketActivity` | `(ticket_id, created_at)` | Chronological Activity |
| `TicketComment` | `(ticket_id, created_at)` | Chronological Comments |
| `NotificationOutbox` | `(status, next_attempt_at)` | Finding PENDING notifications whose next attempt is due |
| `NotificationOutbox` | `(ticket_id, created_at)` | Notification inspection for a Ticket |

Review actual generated SQL and query plans. Avoid adding indexes without a query/use case. Search over Issue text may need a PostgreSQL trigram or other search index depending on the API search implementation; decide that during API design and verify it with the chosen query.

Use `select_related()` for foreign-key/one-to-one relationships and `prefetch_related()` for collections such as Issues, Floors, Assignments, Activities, and Comments where they are needed.

## 6. Transaction boundaries

Use `transaction.atomic()` for related writes:

| Operation | Writes in one transaction |
|---|---|
| Create Ticket | Ticket, TicketIssue rows, TicketFloor rows, TicketActivity, and NotificationOutbox rows for the Facility Manager/current Department POC recipients |
| Assign Worker | TicketAssignment, Ticket workflow-stage update, TicketActivity, and NotificationOutbox row for the assigned Worker |
| Change Department | Ticket current Department update, TicketActivity containing forwarding note and old/new Department, and NotificationOutbox row for the destination Department POC |
| Submit assessment | TicketAssessment, Ticket stage/status update, TicketActivity, and NotificationOutbox row for the current Department POC |
| Mark resolved | Ticket closure fields/status, active assignment end, TicketActivity |

Use `select_for_update()` on the Ticket row for state-changing operations where concurrent requests could race. Lock with a separate primary-key query after visibility has been confirmed (`README-authorization.md` §5). The partial unique constraint on active assignments is a final database safeguard, not a substitute for transaction handling.

Create each required `NotificationOutbox` row inside the same transaction as its business action. After commit, use `transaction.on_commit()` to publish the outbox ID to Celery. After a successful broker publish, update `last_dispatched_at`. If Redis publishing fails, leave the outbox row pending for the Celery Beat dispatcher and manual recovery command documented in `README-async-processing.md`. Never rely on direct task publishing as the only durable record of notification intent.

## 7. Deletion and historical retention

Do not expose hard-delete operations for Tickets, Assessments, Assignments, Activities, or Comments in the assignment UI/API.

Prefer deactivation (`is_active = false`) for Clients, Properties, Client Offices, Departments, Issues, and Users when they should no longer be used for new operations. Use protective foreign-key deletion policies for records referenced by ticket history. The exact `on_delete` choice for each Django field should be applied consistently with this retention requirement.

## 8. Finalized selection and derived-data decisions

The following decisions are now finalized and must not be treated as open questions:

- If a Client has one authorized Client Office for the authenticated User, preselect it; if there are multiple authorized Offices, require a conditional Office selection.
- For a Facility Manager, the authorized Office list is the intersection of the selected Client's Offices and Offices whose Property is managed by that Facility Manager.
- If an Office has exactly one mapped Floor, hide the Floor selector and associate that Floor automatically with the Ticket.
- If an Office has multiple mapped Floors, show the required multi-select and require at least one selection.
- If an Office has no mapped Floors, do not show the Floor selector and do not create `TicketFloor` rows.
- Quick Issues are the top four Issues by frequency across the selected Client's historical Tickets, with the most recent occurrence as the tie-breaker.

## 9. Remaining implementation details — document the choice

1. **Ticket display identifier:** Render `TKT-{id}` from the primary key; no separately persisted public identifier is currently required.
2. **Issue text search index:** Choose the index to match the implemented API search query, verify the query plan, and document the choice. The API contract requires Issue-name search only.

## 10. Assignment scope exclusions

Do not add multi-tenant organization tables, multiple active Workers per Ticket, multiple Department POCs, Worker-to-Property mapping, multiple assessments, or Event Sourcing. `NotificationOutbox` is a durable job table for asynchronous notification delivery; it does not make the application event-sourced.

## 11. Implementation notes (Phase 2)

Choices made while writing the models. None changes a finalized decision above.

- **Deletion policy:** every foreign key uses `on_delete=PROTECT`. Referenced records cannot be deleted; retire them with `is_active=False`.
- **`Property.address`:** optional (`blank=True`), because no workflow rule needs it. The seed fills it in.
- **`ClientOffice.code`:** optional. A blank code means "no code"; the `(client, code)` unique constraint applies only to non-blank codes. The seed leaves codes blank, because Harness-1317 and HSR-1317 would otherwise need different codes for no reason.
- **`TicketAssignment.end_reason`:** choices `REASSIGNED` (a supported reassignment replaced the Worker) and `TICKET_CLOSED` (the Ticket was marked resolved).
- **Timestamps:** `created_at`, `assigned_at`, and `submitted_at` on the ticket tables and the outbox use `default=timezone.now` instead of `auto_now_add`, so the seed can spread Tickets over 60 days. `updated_at` uses `auto_now`.
- **Role checks:** the foreign keys to Facility Manager, POC, and Worker Users use `limit_choices_to`. This only restricts the choices offered by the Django admin and model forms (`full_clean()` honours it). It is neither a database constraint nor authorization. Role validation stays in the application services (§4), which the Phase 3–4 services must perform explicitly on every write. "A POC is not also a Worker" follows from a User having one role, once the services validate the Worker role. `ClientOfficeFloor.clean()` checks that the Floor and the Office share a Property.
- **Immutable origin Department:** `origin_department` is a separate column from `current_department`; nothing in the database stops it being updated. Immutability is enforced by the services, which never write it after creation.
- **Issue-search index (§9, item 2), decided in Phase 4:** no extra index. Search is `Exists(TicketIssue where issue.name ILIKE '%text%')`. The Issue catalogue is a small table (tens of rows per Department), so the `ILIKE` scan over it is trivial, and the join back to Tickets uses the existing unique `(ticket, issue)` index. A trigram GIN index (and the `pg_trgm` extension) would only pay off on a large catalogue. Revisit it if the catalogue grows to many thousands of Issues.
- **No further indexes in Phase 4:** the listing, visibility, active-assignment, and Activity/comment queries are served by the indexes already in the schema (`(current_department, status, created_at)`, `(client_office, status, created_at)`, `(worker, ticket)`, the partial unique active-assignment index, and the `(ticket, created_at)` indexes).
- **Activity `metadata` keys written by the seed and services:** `TICKET_ROUTED` → `department_id`, `change`; `WORKER_ASSIGNED` → `worker_id`, `change`; `DEPARTMENT_CHANGED` → `from_department_id`, `to_department_id`, `note`, `change`; `ASSESSMENT_SUBMITTED` → `outcome`, `change`; `TICKET_RESOLVED` → `change`. Routing snapshots the initial POC's display label as an assignee change from `Unassigned`, reproducing the wireframe's initial History line and the audit README §2. This corrects the earlier minimal-routing-metadata note; it does not introduce a POC Worker-assignment row.
