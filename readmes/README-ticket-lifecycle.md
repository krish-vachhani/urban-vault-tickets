# Ticket Lifecycle and State Machine

**Status:** FINALIZED  
**Scope boundary:** The handling workflow ends at Pending Department POC Review. The separate `Mark Resolved` action (a mapped Client user or the Ticket's creator) remains available as shown in the wireframe.

## 1. Keep three concepts separate

The Ticket has three distinct pieces of state:

1. **Workflow stage:** where the Ticket is in the handling process.
2. **Ticket status:** whether it is open, has been closed by the Technician's work completion, or is finally closed by the Client.
3. **Assessment outcome:** what the Worker reported when submitting their assessment.

Do not collapse these into one field.

## 2. Workflow stages

Use these exact user-facing stages and stable machine values:

| Machine value | Display label | Meaning |
|---|---|---|
| `PENDING_TECHNICIAN_ASSIGNMENT` | Pending Technician Assignment | Ticket has reached its Department and requires a Worker assignment. |
| `PENDING_TECHNICIAN_ASSESSMENT` | Pending Technician Assessment | A Worker is assigned and must submit an assessment. |
| `PENDING_DEPARTMENT_POC_REVIEW` | Pending Department POC Review | Worker has submitted an assessment. This is the end of the assignment's handling workflow. |

## 3. Ticket status

Use:

| Machine value | Display label | Meaning |
|---|---|---|
| `OPEN` | Open | Ticket is still in the workflow and has not been marked Technician Closed or finally closed. |
| `TECHNICIAN_CLOSED` | Technician Closed | Worker has completed the assessment. The Ticket remains in the Open Tickets listing until the Client confirms resolution. |
| `CLOSED` | Closed | An authorized user (a Client user mapped to the Ticket's Client, or the Ticket's creator) marked the issue resolved. This is terminal in this assignment. |

Open Tickets must include Tickets with status `OPEN` and `TECHNICIAN_CLOSED`. Closed Tickets must include only `CLOSED`.

## 4. Assessment outcomes

The Worker selects exactly one of these outcomes when submitting the assessment:

| Machine value | Display label | Meaning from wireframe |
|---|---|---|
| `FULLY_RESOLVED` | Mark Fully Resolved | The issue has been fully resolved; no further action is needed. |
| `PARTIALLY_RESOLVED` | Mark Partially Resolved | The Worker resolved their part, but another Department/Worker's scope is involved. |
| `CHANGE_REQUESTED` | Suggest Department/Worker Change | The issue is outside the Worker's scope and should be assigned to the correct Department/Worker. |

These are assessment outcomes, not workflow stages and not separate Ticket statuses.

## 5. State transitions

| Action | Authorized actor | Required prior state | Resulting workflow stage | Resulting Ticket status |
|---|---|---|---|---|
| Create Ticket | Client, Facility Manager, Department POC | No Ticket yet | `PENDING_TECHNICIAN_ASSIGNMENT` | `OPEN` |
| Assign Worker | Current Department POC | `PENDING_TECHNICIAN_ASSIGNMENT` + `OPEN` | `PENDING_TECHNICIAN_ASSESSMENT` | `OPEN` |
| Change Department | Current Department POC | `PENDING_TECHNICIAN_ASSIGNMENT` + `OPEN` | Remains `PENDING_TECHNICIAN_ASSIGNMENT` | `OPEN` |
| Submit any assessment outcome | Currently assigned Worker | `PENDING_TECHNICIAN_ASSESSMENT` + `OPEN` | `PENDING_DEPARTMENT_POC_REVIEW` | `TECHNICIAN_CLOSED` |
| Mark Resolved | Client user mapped to the Ticket's Client, or the Ticket's creator | Any of the three workflow stages, provided status is not already closed | Workflow stage remains unchanged | `CLOSED` |

## 6. Detailed transition behaviour

### 6.1 Ticket creation

- Create the Ticket with workflow stage `PENDING_TECHNICIAN_ASSIGNMENT` and status `OPEN`.
- Derive the origin Department from the selected Issue(s).
- Set `current_department_id` equal to `origin_department_id`.
- The Department POC is derived from the current Department.
- Create TicketIssue and TicketFloor relationships in the same transaction.
- Add a TicketActivity entry for creation/routing.

### 6.2 Assign Worker

Only the current Department POC may perform this action, and only while the Ticket is `PENDING_TECHNICIAN_ASSIGNMENT` and `OPEN`.

- The chosen Worker must have role `WORKER` and belong to the Ticket's current Department.
- Create a TicketAssignment row.
- Move the workflow stage to `PENDING_TECHNICIAN_ASSESSMENT`.
- Keep Ticket status `OPEN`.
- Record the action in TicketActivity.
- The assigned Worker gains current-assignee visibility.

Only one active Worker assignment is allowed at a time.

### 6.3 Change Department

Only the current Department POC may perform this action, while the Ticket is `PENDING_TECHNICIAN_ASSIGNMENT` and `OPEN`.

Required input:

- destination Department;
- non-empty forwarding note.

On success:

- update `current_department_id`;
- preserve `origin_department_id`;
- keep workflow stage `PENDING_TECHNICIAN_ASSIGNMENT`;
- keep status `OPEN`;
- create a TicketActivity event containing the old Department, new Department, actor, timestamp, and forwarding note;
- new Department POC gains visibility through the current-Department rule;
- previous Department POC loses visibility through the Department POC role unless another role independently grants access.

The wireframe shows Change Department before Worker assignment. Do not add a later department-transfer workflow after assessment submission.

### 6.4 Submit Worker assessment

Only the currently assigned Worker may submit, and only while the Ticket is `PENDING_TECHNICIAN_ASSESSMENT` and `OPEN`.

- Create one TicketAssessment with the selected outcome.
- Move workflow stage to `PENDING_DEPARTMENT_POC_REVIEW`.
- Set Ticket status to `TECHNICIAN_CLOSED`.
- Keep the Worker assignment active so Current Assignee(s) and historical Worker visibility remain intact during Department POC Review.
- Create **one** `ASSESSMENT_SUBMITTED` TicketActivity entry that records the assessment outcome and the status change (Open → Technician Closed). The wireframe shows this as a single "changed status" event, and its event count ("4 events") depends on it being one entry.

All three assessment outcomes follow the same state transition. The assignment's workflow ends at Pending Department POC Review; do not build subsequent Department POC review actions.

### 6.5 Mark resolved

A Client user mapped to the Ticket's Client, or the user who created the Ticket, may mark it resolved at any of the three workflow stages. The wireframe shows this CTA for the Client, and for an internal employee (Facility Manager) on a Ticket they created. See `README-authorization.md` §4.

- Set status to `CLOSED`.
- Preserve the current workflow stage; closure is a separate state dimension.
- Set `closed_by_id` and `closed_at`.
- End any active Worker assignment while preserving the assignment record.
- Create a TicketActivity event.
- Move the Ticket from Open Tickets to Closed Tickets.

A closed Ticket is terminal for workflow transitions in this assignment. Reopening is out of scope.

## 7. Valid state/status combinations

Enforce these combinations at the database level where practical:

| Workflow stage | Permitted status |
|---|---|
| `PENDING_TECHNICIAN_ASSIGNMENT` | `OPEN`, `CLOSED` |
| `PENDING_TECHNICIAN_ASSESSMENT` | `OPEN`, `CLOSED` |
| `PENDING_DEPARTMENT_POC_REVIEW` | `TECHNICIAN_CLOSED`, `CLOSED` |

## 8. Invalid transitions to reject

Examples:

- Assign Worker when the Ticket is not Pending Technician Assignment.
- Assign a Worker from another Department.
- Change Department after the Ticket has advanced beyond Pending Technician Assignment.
- Submit an assessment when the user is not the active Worker.
- Submit an assessment more than once.
- Submit an assessment before Worker assignment.
- Mark an already-closed Ticket resolved again.
- Perform any workflow action on a closed Ticket.

Use explicit action endpoints/services rather than allowing arbitrary client-side PATCH requests to change workflow fields. Return a consistent `409 Conflict` response for invalid state transitions.

## 9. Concurrency and atomicity

Use `transaction.atomic()` for each state-changing operation. Lock the Ticket row with `select_for_update()` when necessary to prevent concurrent actions from racing. Confirm visibility first, then lock with a separate primary-key query (`Ticket.objects.select_for_update().get(pk=...)`); see `README-authorization.md` §5. The partial unique constraint for one active Worker assignment is an additional database safeguard.

## 10. Out of scope

- Department POC review actions after assessment submission;
- additional work cycles after Department POC Review;
- automatic Worker assignment;
- multi-Department Tickets;
- multiple simultaneous active Workers;
- reopening closed Tickets;
- a separate post-assessment department-transfer workflow.
