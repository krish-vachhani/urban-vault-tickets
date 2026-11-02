# Ticket Details and Action APIs

**Status:** FINALIZED  
**Base path:** `/api/v1/tickets/`  
**Authentication:** JWT using Django REST Framework SimpleJWT; see `README-authentication.md`  
**Authorization source:** Backend role and relationship checks; see `README-authorization.md`

This document specifies the ticket detail, assignment, department forwarding, assessment, resolution, activity, history, and comment endpoints. It captures the decisions agreed for the take-home assignment. It does not authorize implementation of workflow stages beyond the defined end at **Pending Department POC Review**.

## 1. API design principles

- Use explicit endpoints for business actions. Do not expose a generic endpoint that lets the frontend patch arbitrary Ticket fields.
- Every endpoint requires authentication unless explicitly stated otherwise. These endpoints are authenticated.
- Retrieve a Ticket through the authenticated user's visibility-scoped queryset.
- Return `404 Not Found` when the Ticket does not exist **or is outside the caller's visibility scope**. Do not reveal that an inaccessible Ticket exists.
- If the user can view the Ticket but is not permitted to perform the requested action, return `403 Forbidden`.
- If the user is authorized for the action but the Ticket is in an invalid workflow state, return `409 Conflict`.
- Validate request data with DRF serializers and enforce business rules in a dedicated service layer.
- Use `transaction.atomic()` for multi-record state changes. Use `select_for_update()` on the Ticket row for competing state-changing operations.
- Create immutable `TicketActivity` records for important actions in the same database transaction as the action.
- Create required `NotificationOutbox` rows in the same transaction as the business action, then safely publish their IDs after commit using `transaction.on_commit()`. Redis publication failure must not erase the durable outbox intent; see `README-async-processing.md`.

## 2. Ticket details

### Endpoint

```http
GET /api/v1/tickets/{ticket_id}/
Authorization: Bearer <access_token>
```

### Visibility

The Ticket must be in the caller's visibility scope. Apply the policies in `README-authorization.md` before serializing the object.

### Response shape

Return the Ticket's display data and relevant relationships, including:

- `id` and human-readable `ticket_number`;
- Client and Client Office;
- selected Issues and Floors;
- description;
- immutable `origin_department` and mutable `current_department`;
- `workflow_stage` and closure `status`;
- creator and creation timestamp;
- current Department POC (derived from `current_department.poc_user`);
- current Worker, if there is an active TicketAssignment;
- assessment, if one has been submitted;
- `action_required`, using the same rule as the listing (`README-ticket-listing-api.md` §9);
- `available_actions` as UI guidance.

Example (illustrative values):

```json
{
  "id": 1042,
  "ticket_number": "TKT-1042",
  "client": {"id": 1, "name": "Harness"},
  "client_office": {"id": 10, "name": "Harness-1317"},
  "issues": [{"id": 101, "name": "AC not cooling"}],
  "floors": [{"id": 102, "name": "2F"}, {"id": 103, "name": "3F"}],
  "description": "AC units are producing warm air.",
  "origin_department": {"id": 1, "name": "Technical"},
  "current_department": {"id": 1, "name": "Technical"},
  "workflow_stage": "PENDING_TECHNICIAN_ASSESSMENT",
  "status": "OPEN",
  "created_by": {"id": 12, "name": "Chaitanya M", "role": "CLIENT", "role_label": "Client POC"},
  "current_poc": {"id": 20, "name": "Dhananjaya Murthy", "role": "DEPARTMENT_POC", "role_label": "Technical Manager"},
  "current_worker": {"id": 31, "name": "Prakash Kumar", "role": "WORKER", "role_label": "Technician"},
  "assessment": null,
  "action_required": true,
  "available_actions": {
    "can_assign_worker": false,
    "can_change_department": false,
    "can_submit_assessment": true,
    "can_mark_resolved": true,
    "can_comment": true
  }
}
```

`available_actions` is a convenience for rendering UI controls only. It is not an authorization grant. `can_mark_resolved` is true for a Client user mapped to the Ticket's Client and for the Ticket's creator, while the Ticket is not closed. Every action endpoint must independently recheck the authenticated user's role, relationships, ticket visibility, status, and workflow stage.

The details query should use `select_related()` for single-valued relationships and `prefetch_related()` for Issues, Floors, assignment(s), and other collections needed by the response.

## 3. Eligible Workers

### Endpoint

```http
GET /api/v1/tickets/{ticket_id}/eligible-workers/
Authorization: Bearer <access_token>
```

This is deliberately ticket-scoped, not a general department-worker directory.

### Authorization and validation

- The caller must be the designated POC of the Ticket's current Department.
- The Ticket must be at `PENDING_TECHNICIAN_ASSIGNMENT` and have status `OPEN`.
- The Ticket must be visible to the caller.
- Return active Users with role `WORKER` who have a `DepartmentWorker` membership for the Ticket's `current_department_id`.
- Do not filter by Property; Worker-to-Property mapping is out of scope.

### Response

```json
{
  "results": [
    {"id": 31, "name": "Prakash Kumar", "role": "WORKER", "role_label": "Technician"},
    {"id": 32, "name": "Rahul Sharma", "role": "WORKER", "role_label": "Technician"}
  ]
}
```

If the caller can view the Ticket but is not the current Department POC or the Ticket is not awaiting Worker assignment, return `403` for missing action permission or `409` for invalid state, respectively. If the Ticket is outside the caller's visibility scope, return `404`.

## 4. Assign Worker

### Endpoint

```http
POST /api/v1/tickets/{ticket_id}/assign-worker/
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request

```json
{
  "worker_id": 31
}
```

### Authorization and business validation

- Caller must be the designated POC of `Ticket.current_department`.
- Ticket must have `workflow_stage = PENDING_TECHNICIAN_ASSIGNMENT`.
- Ticket must have `status = OPEN`.
- Selected Worker must exist, be active, have role `WORKER`, and belong to the Ticket's current Department.
- There must not already be an active Worker assignment.
- The client cannot provide or override `assigned_by`; derive it from the authenticated user.

### Transactional side effects

Within one transaction:

1. Lock the Ticket row using `select_for_update()`.
2. Recheck visibility, POC authorization, workflow stage, status, and absence of an active assignment.
3. Create `TicketAssignment` with the selected Worker and authenticated POC as `assigned_by`.
4. Change workflow stage to `PENDING_TECHNICIAN_ASSESSMENT`; keep status `OPEN`.
5. Create a `TicketActivity` event of type `WORKER_ASSIGNED`, recording the Worker and actor in structured metadata.
6. Create a `NotificationOutbox` row for the assigned Worker, linked to the `WORKER_ASSIGNED` Activity.
7. Commit.

After commit, safely publish the outbox ID to Celery using `transaction.on_commit()`.

### Success

Return `201 Created`.

```json
{
  "message": "Worker assigned successfully.",
  "ticket_id": 1042,
  "workflow_stage": "PENDING_TECHNICIAN_ASSESSMENT",
  "worker": {"id": 31, "name": "Prakash Kumar", "role": "WORKER", "role_label": "Technician"}
}
```

### Reassignment scope

The data model preserves assignment history and supports ending an old assignment and creating a new one. However, the supplied wireframe only defines the initial Assign Worker action before a Worker is assigned. Do not invent an additional reassignment UI or API flow after assignment unless the implementation team explicitly records a new decision. The active-assignment uniqueness constraint remains in force.

## 5. Change Department

### Endpoint

```http
POST /api/v1/tickets/{ticket_id}/change-department/
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request

```json
{
  "department_id": 2,
  "forwarding_note": "This issue appears to be related to IT infrastructure."
}
```

### Authorization and business validation

- Caller must be the designated POC of the Ticket's current Department.
- Ticket must have `workflow_stage = PENDING_TECHNICIAN_ASSIGNMENT`.
- Ticket must have `status = OPEN`.
- Destination Department must exist and be active.
- Destination Department must differ from the current Department.
- `forwarding_note` is required and must not be blank.

### Transactional side effects

Within one transaction:

1. Lock the Ticket row and revalidate all conditions.
2. Update `current_department_id` to the destination Department.
3. Preserve `origin_department_id` unchanged.
4. Keep workflow stage `PENDING_TECHNICIAN_ASSIGNMENT` and status `OPEN`.
5. Create a `TicketActivity` event of type `DEPARTMENT_CHANGED`, recording previous Department, destination Department, forwarding note, and actor.
6. Create a `NotificationOutbox` row for the destination Department POC, linked to the `DEPARTMENT_CHANGED` Activity.
7. Commit.

After commit, safely publish the outbox ID to Celery.

The Department POC is derived from `current_department.poc_user`; do not maintain a redundant `current_poc_id` on Ticket.

No Worker assignment is created by this action. The agreed flow exposes Change Department before Worker assignment, so there is no active Worker to transfer in this action.

### Success

Return `200 OK` with the updated current Department, workflow stage, and status.

## 6. Submit Worker Assessment

### Endpoint

```http
POST /api/v1/tickets/{ticket_id}/submit-assessment/
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request

```json
{
  "outcome": "PARTIALLY_RESOLVED"
}
```

Allowed outcomes:

- `FULLY_RESOLVED`
- `PARTIALLY_RESOLVED`
- `CHANGE_REQUESTED`

### Authorization and business validation

- Caller must be the Worker with the active TicketAssignment.
- Ticket must have `workflow_stage = PENDING_TECHNICIAN_ASSESSMENT`.
- Ticket must have `status = OPEN`.
- No TicketAssessment may already exist.
- Outcome must be one of the allowed values.

### Transactional side effects

Within one transaction:
1. Lock the Ticket row and recheck all conditions, including the active assignment belonging to the caller.
2. Create the single `TicketAssessment` record with the authenticated Worker as `submitted_by`.
3. Change workflow stage to `PENDING_DEPARTMENT_POC_REVIEW`.
4. Change Ticket status to `TECHNICIAN_CLOSED`.
5. Preserve the Worker assignment so the Worker remains visible as a current assignee in the Department POC Review stage.
6. Create one `ASSESSMENT_SUBMITTED` `TicketActivity` entry recording the outcome and the status change (`change`: Open → Technician Closed).
7. Create a `NotificationOutbox` row for the current Department POC, linked to the assessment Activity.
8. Commit.

After commit, safely publish the outbox ID to Celery.

The assignment explicitly ends at Pending Department POC Review. Do not implement subsequent Department POC review actions or additional assessment rounds.

### Success

Return `201 Created` with the assessment outcome, new workflow stage, and new status.

## 7. Mark Resolved

### Endpoint

```http
POST /api/v1/tickets/{ticket_id}/mark-resolved/
Authorization: Bearer <access_token>
```

No request body is required by the agreed wireframe interpretation.

### Authorization and business validation

- Caller must be either (a) a `CLIENT` user associated through `UserClient` with the Client that owns the Ticket's Client Office, or (b) the user who created the Ticket (`README-authorization.md` §4).
- Ticket must be visible to the caller.
- Ticket status must not already be `CLOSED`.
- Ticket workflow stage must be one of the three supported stages.

### Transactional side effects

Within one transaction:

1. Lock the Ticket row and revalidate conditions.
2. Set `status = CLOSED`.
3. Set `closed_by_id` to the authenticated user.
4. Set `closed_at` using the server timestamp.
5. End any active Worker assignment by setting its end timestamp and appropriate end reason; preserve its history.
6. Preserve the workflow stage and assessment record, if any.
7. Create a `TicketActivity` event of type `TICKET_RESOLVED`, with a `change` from the previous status to Closed.
8. Commit.

No resolution notification is included in the finalized notification scope. Do not create a NotificationOutbox row for this action.

### Success

Return `200 OK` with the updated Ticket status, `closed_by`, and `closed_at`.

Once closed, all workflow-changing actions must be rejected. Comments remain allowed for users who still have Ticket visibility, as agreed.

## 8. Activities timeline

### Endpoint

```http
GET /api/v1/tickets/{ticket_id}/activities/?type=ALL&page=1&page_size=20
Authorization: Bearer <access_token>
```

Supported `type` values:

- `ALL` (default)
- `ACTIONS`
- `COMMENTS`

The endpoint combines `TicketActivity` and `TicketComment` into one chronological, paginated timeline. Each item should include a stable ID/type discriminator, actor where available, readable description, timestamp, and event type for actions.

Each item has the same shape, so the frontend renders one list:

| Field | Meaning |
|---|---|
| `id` | Stable string ID that is unique across both sources, e.g. `"action-7"` or `"comment-3"` |
| `type` | `ACTION` or `COMMENT` |
| `event_type` | Activity event code for actions (e.g. `WORKER_ASSIGNED`); `null` for comments |
| `actor` | User summary with `role_label`; `null` for system events |
| `description` | Readable verb phrase for actions (e.g. "assigned technician."); the comment body for comments |
| `change` | `{field, from, to}` for events that change assignee, Department, or status; otherwise `null` |
| `note` | The forwarding note on `DEPARTMENT_CHANGED`; otherwise `null` |
| `created_at` | ISO 8601 timestamp |

Example action item:

```json
{
  "id": "action-7",
  "type": "ACTION",
  "event_type": "WORKER_ASSIGNED",
  "actor": {"id": 20, "name": "Dhananjaya Murthy", "role": "DEPARTMENT_POC", "role_label": "Technical Manager"},
  "description": "assigned technician.",
  "change": {"field": "assignee", "from": "Unassigned", "to": "Prakash Kumar (Technician)"},
  "note": null,
  "created_at": "2026-10-28T09:10:00Z"
}
```

Example comment item:

```json
{
  "id": "comment-3",
  "type": "COMMENT",
  "event_type": null,
  "actor": {"id": 31, "name": "Prakash Kumar", "role": "WORKER", "role_label": "Technician"},
  "description": "Technician inspected the AC.",
  "change": null,
  "note": null,
  "created_at": "2026-11-02T11:30:00Z"
}
```

The user must be able to view the Ticket to view its Activity. Apply the same visibility-scoped Ticket lookup before querying either source table.

**Bounded feed (Phase 0 audit, R4).** Sort oldest first (as in the wireframe) by `created_at`, then by `type` and ID as a stable tie-breaker. Paginate with the standard page envelope (`count`, `next`, `previous`, `results`; default `page_size` 20, maximum 50). The frontend shows `count` as "N events".

Keep the query simple and bounded: combine the `TicketActivity` and `TicketComment` querysets with one SQL `UNION ALL` of two `.values()` querysets that select the same columns, order it, and let the paginator apply `LIMIT`/`OFFSET`. Do not load the whole timeline into Python to merge it.

## 9. Assignment and Department history

### Endpoint

```http
GET /api/v1/tickets/{ticket_id}/history/
Authorization: Bearer <access_token>
```

Return structured assignment history from `TicketAssignment` and relevant Department forwarding events from `TicketActivity`.

The History display should preserve the Unassigned/assigned progression shown in the wireframe. It must not infer historical assignment data from the current Worker field alone.

The wireframe draws History inline inside each Activity entry; the frontend renders that from each Activity item's `change` field (§8). This endpoint is retained as the structured assignment and Department history.

Apply the same Ticket visibility check.

## 10. Add Comment

### Endpoint

```http
POST /api/v1/tickets/{ticket_id}/comments/
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request

```json
{
  "body": "Technician inspected the AC compressor."
}
```

### Authorization and validation

- Caller must be authenticated and have current Ticket visibility.
- All users with Ticket visibility may comment, including a Worker with historical assignment visibility.
- A comment is independent of workflow action permissions.
- Reject empty or whitespace-only bodies.
- Enforce a documented maximum length (recommended: 5,000 characters).
- Comments remain allowed after Ticket closure, provided the user still has Ticket visibility.
- Comment editing/deletion is not required.

### Side effects

Create a `TicketComment` with the authenticated user as `author`. Do not create a duplicate `TicketActivity` row solely for the comment; the Activity API includes the comment as a timeline item by reading `TicketComment`.

Return `201 Created`.

## 11. HTTP status and error conventions

Use the error envelope and codes defined in `README-api-conventions.md`. Example:

```json
{
  "error": {
    "code": "INVALID_TICKET_TRANSITION",
    "message": "Ticket is not awaiting technician assessment.",
    "details": {}
  }
}
```

| Situation | HTTP status |
|---|---:|
| Missing/invalid access token | 401 |
| Ticket absent or outside caller's visibility scope | 404 |
| Ticket visible, but caller lacks permission for the action | 403 |
| Invalid request fields | 400 |
| Validly authenticated/authorized action, but invalid current state or conflicting state | 409 |
| Successful creation (assignment, assessment, comment) | 201 |
| Successful update (department change, resolution) | 200 |

**Not-found policy (finalized):** Return `404 Not Found` both when a Ticket does not exist and when it exists but is outside the authenticated user's visibility scope. This avoids disclosing inaccessible Ticket existence. If the caller can view the Ticket but lacks permission to perform an action, return `403`.

## 12. Concurrency and consistency

For state-changing operations (`assign-worker`, `change-department`, `submit-assessment`, `mark-resolved`):

1. Enter `transaction.atomic()`.
2. Confirm visibility through the scoped queryset, then lock the Ticket row with a separate primary-key query: `Ticket.objects.select_for_update().get(pk=ticket_id)`. PostgreSQL rejects `FOR UPDATE` with `DISTINCT`, and locking through nullable joins needs `of=("self",)`; a plain primary-key lock avoids both (Phase 0 audit, R1).
3. Re-evaluate visibility, authorization, state, status, and action-specific preconditions after acquiring the lock.
4. Apply all related writes and append the Activity record.
5. Commit.
6. Dispatch asynchronous work only after commit.

The partial unique constraint on active TicketAssignment is an additional safeguard against concurrent duplicate active assignments. The one-to-one TicketAssessment constraint prevents more than one assessment record.

The database transaction and lock protect state transitions; the frontend's disabled/loading button is only a usability measure and is not a concurrency guarantee.

## 13. Required automated tests

At minimum, add meaningful tests for:

1. Ticket detail is returned to an authorized user and returns 404 to a user outside the Ticket's visibility scope (including a guessed Ticket ID).
2. Only the current Department POC can assign a Worker, and the selected Worker must belong to the current Department.
3. Assignment creates the assignment record, advances the stage, and creates an Activity record atomically.
4. Department forwarding changes only `current_department`, preserves `origin_department`, records the forwarding note, and leaves the workflow stage unchanged.
5. Only the active assigned Worker can submit an assessment; all three outcomes lead to Pending Department POC Review and Technician Closed.
6. Mark resolved (by a mapped Client user, or by the Ticket's creator) sets closure fields, closes the active assignment, preserves workflow stage, and rejects a second closure; any other user who can view the Ticket receives `403`.
7. Any visible user can comment, including after closure; a user without visibility receives 404.
8. Concurrent or repeated invalid state-changing requests cannot create duplicate active assignments or assessments.

The assignment requires at least four automated tests across API/business rules, authorization, Celery retry/failure, and a frontend interaction. The above list is a focused ticket-action test plan; Celery and frontend tests are specified in their own feature documents.

## 13a. Response shapes and behaviours fixed in Phase 4

The sections above leave these details open. They are recorded here so the frontend and the tests share one definition.

- **`GET /history/`** returns two chronological lists, not a single `results` array:
  `{"assignments": [...], "department_changes": [...]}`.
  Each assignment item: `id` (`"assignment-{id}"`), `type` (`ASSIGNMENT`), `actor` (the POC who assigned), `worker`, `change` (`{field: "assignee", from, to}`, where `from` is `"Unassigned"` for the first assignment and the previous Worker's label for a later one), `assigned_at`, `ended_at`, `end_reason`.
  Each department-change item: `id` (`"department-change-{id}"`), `type` (`DEPARTMENT_CHANGE`), `actor`, `change` (`{field: "department", from, to}`), `note`, `created_at`.
- **`POST /comments/`** returns `201` with the new comment in the Activity item shape of §8 (`id: "comment-{id}"`, `type: "COMMENT"`, `description` = the body, `event_type`/`change`/`note` null), so the frontend can append it to the feed without a refetch.
- **`POST /change-department/`** returns `200` with `{ticket_id, current_department, workflow_stage, status}`. **`POST /submit-assessment/`** returns `201` with `{ticket_id, outcome, workflow_stage, status}`. **`POST /mark-resolved/`** returns `200` with `{ticket_id, workflow_stage, status, closed_by, closed_at}`. Action responses are built from the result of the service call, never by re-reading the Ticket through the visibility scope: after forwarding, the forwarding POC no longer sees the Ticket but still receives their own successful response.
- **Assessment permission and the 403/409 split.** "Caller is the Worker with the active assignment" is the 403 rule. A Worker whose assignment has ended (reassigned, or the Ticket was resolved) is not the active assignee and receives `403`; the active Worker submitting a second time receives `409`.
- **Check order inside Assign Worker and Change Department.** Following `README-api-conventions.md` §3, body validation (`400`: unknown, inactive, or wrong-Department Worker; unknown, inactive, or unchanged destination Department) runs before the state check (`409`). Both run against the locked Ticket.
- **Free-text limit.** The forwarding note, comment body, and Ticket description are limited to 5,000 characters (`400` beyond that).
- **Eligible Workers** is a `GET` on the same router as the other actions; its behaviour is unchanged.
- **Notification rows.** Phase 4 writes the `NotificationOutbox` rows inside each action's transaction (recipients per `README-async-processing.md` §3, never the actor, deduplicated). Publishing them to Celery after commit, and delivering them, is Phase 5.

## 14. Out of scope

- Generic Ticket PATCH endpoint for changing arbitrary fields.
- Department POC review actions after Worker assessment.
- Additional assessment rounds or assessment editing.
- Automatic Worker assignment.
- Property-aware Worker eligibility.
- Multiple simultaneous active Workers.
- Reassignment UI after the initial assignment unless separately approved.
- Comment editing or deletion.
- Reopening closed Tickets.
- Any workflow beyond the supplied wireframe's end at Pending Department POC Review, apart from the agreed Mark Resolved action.

## 15. Implementation checklist for Claude Code

- [ ] Implement Ticket detail using a visibility-scoped queryset.
- [ ] Include derived current POC and active Worker in detail response.
- [ ] Include `available_actions` as UI hints only; never rely on them for security.
- [ ] Implement ticket-scoped eligible Workers endpoint.
- [ ] Implement explicit Assign Worker endpoint and atomic side effects.
- [ ] Implement Change Department endpoint, preserving origin Department.
- [ ] Implement Submit Assessment endpoint and one-assessment constraint.
- [ ] Implement the Mark Resolved endpoint (mapped Client users or the Ticket's creator) and closure fields.
- [ ] Implement combined, paginated Activity timeline.
- [ ] Implement structured History response.
- [ ] Implement Comment creation for all visible users, including after closure.
- [ ] Return 404 for inaccessible Ticket IDs; 403 for action permission failure on a visible Ticket; 409 for invalid state transitions.
- [ ] Lock Ticket rows for state-changing actions and revalidate after locking.
- [ ] Record Activity in the same transaction as each important action.
- [ ] Dispatch Celery tasks after commit only.
- [ ] Add automated tests for authorization, state transitions, consistency, and comments.
