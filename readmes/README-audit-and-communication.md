# Ticket Activity, Assignment History, Assessments, and Comments

**Status:** FINALIZED  
**Purpose:** Define the separate records needed to explain what happened to a Ticket, who handled it, what the Worker concluded, and what users communicated.

## 1. Keep four concepts separate

Use four distinct entities:

| Entity | Responsibility |
|---|---|
| `TicketActivity` | Immutable audit/timeline entries for important system and user actions |
| `TicketAssignment` | Structured current and historical Worker assignments |
| `TicketAssessment` | Worker's structured assessment outcome |
| `TicketComment` | User-generated communication |

Do not combine all four into one generic table. They have different validation rules, query patterns, and meanings.

## 2. TicketActivity

Every important Ticket action should create an Activity record in the same database transaction as the business change.

Examples:

- Ticket created/routed;
- Worker assigned;
- Department changed;
- Worker assessment submitted (one entry that also records the Open → Technician Closed status change);
- Ticket marked resolved.

Suggested fields:

```text
TicketActivity
--------------
id
 ticket_id          FK -> Ticket
 actor_id           nullable FK -> User (null for system event)
event_type
 description
 metadata           JSON/JSONB, default {}
 created_at
```

Activity records are append-only at the application level. Do not expose ordinary edit/delete operations for Activity entries.

Use `metadata` for structured context such as previous and next Department IDs, Worker ID, forwarding note, or assessment outcome. Do not use metadata as a replacement for the normalized Ticket, Assignment, or Assessment tables.

For events that change the assignee, Department, or status, store a `change` object with display-ready values, for example `{"field": "assignee", "from": "Unassigned", "to": "Prakash Kumar (Technician)"}`. The Activity API returns it so the frontend can draw the wireframe's inline History: `Unassigned → Dhananjaya Murthy (Technical Manager)`, `Technical → IT`, `Open → Technician Closed`.

## 3. TicketAssignment

A Ticket can have multiple assignment records over its lifetime, preserving reassignment history, but it can have at most one active Worker at a time.

Suggested fields:

```text
TicketAssignment
----------------
id
ticket_id           FK -> Ticket
worker_id           FK -> User
assigned_by_id      FK -> User
assigned_at
ended_at            nullable; null means active
end_reason          nullable
```

Enforce one active assignment per Ticket using a PostgreSQL partial unique constraint on `ticket_id` where `ended_at IS NULL`.

Rules:

- The assigned person must have role `WORKER`.
- The Worker must belong to the Ticket's current Department when assigned.
- Only the current active Worker can submit the assessment.
- Historical assignment records remain queryable and preserve historical Worker visibility.
- The assignment remains active after the Worker submits an assessment so Current Assignee(s) can still display the Worker during Pending Department POC Review.
- End the active assignment when the Ticket is finally closed by the Client, or when a supported reassignment operation replaces it.

The wireframe does not require a post-assignment reassignment UI. The schema supports assignment history, but do not invent a new reassignment workflow screen/action beyond the supplied flow.

## 4. TicketAssessment

The Worker must choose exactly one of the three assessment outcomes:

| Value | Display label | Meaning |
|---|---|---|
| `FULLY_RESOLVED` | Mark Fully Resolved | Entire issue resolved; no further action needed. |
| `PARTIALLY_RESOLVED` | Mark Partially Resolved | Worker's part resolved, but another Department/Worker's scope remains. |
| `CHANGE_REQUESTED` | Suggest Department/Worker Change | Issue is outside Worker's scope and should be assigned to the correct Department/Worker. |

Suggested fields:

```text
TicketAssessment
----------------
id
ticket_id           one-to-one FK -> Ticket
submitted_by_id      FK -> User
outcome
submitted_at
```

Only one assessment is permitted per Ticket in this assignment's workflow. The submitter must be the current active Worker and the Ticket must be at `PENDING_TECHNICIAN_ASSESSMENT` with status `OPEN`.

All three outcomes cause the same workflow transition:

- workflow stage becomes `PENDING_DEPARTMENT_POC_REVIEW`;
- Ticket status becomes `TECHNICIAN_CLOSED`;
- one `ASSESSMENT_SUBMITTED` Activity record is added, recording the outcome and the Open → Technician Closed change;
- the Worker assignment remains associated/active for display and visibility.

**Finalized decision (Phase 0 audit, B4):** the assessment has **no note field**. The wireframe's assessment panel offers only the three outcomes and a Submit button. If the Worker needs to add context, they post an ordinary comment, which appears in the Activity feed. The "Comment" box drawn under the status-change event in the wireframe is interpreted as such an ordinary comment.

## 5. TicketComment

Comments are user-generated messages and must be stored separately from audit actions.

Suggested fields:

```text
TicketComment
--------------
id
ticket_id       FK -> Ticket
author_id       FK -> User
body
created_at
```

Rules:

- Any user who has Ticket visibility may add a comment.
- This includes Client users, Facility Managers, current Department POCs, and current or historically assigned Workers who retain Ticket visibility.
- Comment permission does not grant workflow-action permission.
- Validate that the body is non-empty after trimming.
- Comments are displayed chronologically in the Ticket Activity feed.

## 6. Activity timeline and History UI

The wireframe's Activity section has filters:

- All (selected by default);
- Actions;
- Comments.

The Activity API should present a unified chronological feed by combining `TicketActivity` and `TicketComment` records. The API response should identify whether each item is an action or comment and include its timestamp and actor information.

The History section should be built from structured assignment history and relevant Department-change Activity records. Do not store a second, manually maintained copy of assignment history in Ticket.

The wireframe draws History **inline inside each Activity entry** (before → after). Render it from the `change` field of each Activity item. The separate `GET /tickets/{id}/history/` endpoint (`README-ticket-actions-api.md` §9) is retained as the structured assignment and Department history.

A separate Activity filter for Actions should exclude comments; the Comments filter should return comments only.

## 7. Transaction requirements

Write the business record and its corresponding Activity record atomically.

| Operation | Atomic writes |
|---|---|
| Ticket creation | Ticket + TicketIssue + TicketFloor + creation/routing Activity |
| Worker assignment | TicketAssignment + Ticket workflow-stage update + assignment Activity |
| Department forwarding | Ticket current Department update + forwarding Activity |
| Assessment submission | TicketAssessment + Ticket stage/status update + one assessment Activity (outcome and status change) |
| Mark resolved | Ticket closure fields/status + active assignment end + resolution Activity |

Use `transaction.atomic()`. For conflicting state changes, lock the Ticket row with `select_for_update()`.

## 8. Celery interaction

Notification-triggering business actions create `NotificationOutbox` records in the same PostgreSQL transaction as their Ticket, Assignment, Assessment, and Activity writes. After commit, the outbox ID is published to Celery through `transaction.on_commit()`.

If Redis is unavailable, the committed outbox record remains `PENDING` and can be re-published by the `dispatch_pending_notifications` management command. Transient delivery failures are retried through the outbox's durable `next_attempt_at` schedule (at most 4 attempts); the outbox idempotency key and locked status check make repeated task execution a no-op after successful delivery. See `README-async-processing.md` for the complete design.

A failed business transaction must not create an outbox record or trigger a notification.

## 9. Assignment boundary

The workflow ends after assessment submission and entry into Pending Department POC Review. Do not add subsequent Department POC review/approval actions. `Mark Resolved` (a mapped Client user or the Ticket's creator) remains a separate action available at each of the three workflow stages, as agreed in the state-machine design.
