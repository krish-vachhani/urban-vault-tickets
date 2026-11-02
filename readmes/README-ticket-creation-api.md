# Ticket Creation API

**Status:** FINALIZED  
**Endpoint:** `POST /api/v1/tickets/`  
**Scope:** Create a Ticket for a specific Client Office, with one or more Issues from one Department and the affected Floors.

This document records the agreed Ticket Creation API contract and business rules. It is an implementation specification for Claude Code. Do not create separate Ticket creation endpoints per role, and do not trust client-supplied creator, Department, workflow, status, or closure fields.

## 1. Purpose and product behaviour

A Client, Facility Manager, or Department POC can report a facility issue. Each submitted Ticket:

- belongs to exactly one Client Office;
- is created by the authenticated User;
- contains one or more selected Issues;
- may affect one or more Floors mapped to that Office;
- is initially routed to the Department associated with its selected Issues;
- starts at `PENDING_TECHNICIAN_ASSIGNMENT` with status `OPEN`.

A Worker cannot create Tickets.

Use one common creation endpoint for all three eligible roles. The role-specific differences are validation and authorization rules, not different Ticket resources.

## 2. Endpoint

```http
POST /api/v1/tickets/
Authorization: Bearer <access_token>
Content-Type: application/json
```

Successful creation returns `201 Created`.

## 3. Request contract

Example:

```json
{
  "client_office_id": 10,
  "issue_ids": [101],
  "floor_ids": [102, 103],
  "description": "AC units on floors 2 and 3 are producing warm air."
}
```

| Field | Required | Meaning |
|---|---|---|
| `client_office_id` | Yes | Specific Client Office where the issue exists |
| `issue_ids` | Yes | Non-empty list of selected Issue IDs; multiple allowed |
| `floor_ids` | Conditional | Affected Floors; required when the Office has multiple mapped Floors |
| `description` | Client: optional; Facility Manager/Department POC: required | Additional issue details |

Do not accept these as authoritative request fields: `client_id`, `created_by_id`, `origin_department_id`, `current_department_id`, `workflow_stage`, `status`, `closed_by_id`, `closed_at`, `ticket_number`, or `assigned_by_id`.

The selected Client is used by the UI to filter available Offices. The backend derives the Client through `client_office.client`; the request only needs the selected `client_office_id`.

## 4. Role-specific authorization and Client/Office selection

All three creation roles must have a `UserClient` mapping to the Client that owns the selected Office. UserClient membership is many-to-many for all roles, but its authorization effect depends on the role.

### 4.1 Client user

- May create a Ticket for any active Office belonging to a Client mapped to the authenticated User.
- If mapped to one Client, preselect it; if mapped to multiple Clients, show a conditional Client selector.
- After selecting a Client, if exactly one Office is available, preselect it; if multiple Offices exist, show a conditional Office selector.
- Description is optional.

### 4.2 Facility Manager

- May create a Ticket only for an active Office whose Client is mapped to the authenticated User **and** whose Property has `facility_manager_id == request.user.id`.
- The Office options are the intersection of the selected Client's Offices and Properties managed by the Facility Manager.
- A Client mapping alone does not authorize creating a Ticket for that Client's Office in another manager's Property.
- If one authorized Client is mapped, preselect it; if multiple are mapped, show a Client selector.
- After selecting the Client, preselect the Office only if exactly one Office remains in the Facility Manager's authorized Property scope; otherwise require Office selection.
- Description is required and must not be empty/whitespace.

### 4.3 Department POC

- May create a Ticket for any active Office belonging to a Client mapped to the authenticated User.
- Departments are organization-wide; there is no Property restriction for Department POC Ticket creation.
- Use the same conditional Client and Office selection rules.
- Description is required and must not be empty/whitespace.

### 4.4 Worker

- Cannot create Tickets. Reject with `403 Forbidden`.

### 4.5 Reference-data dependency

Use the reference-data endpoints documented in `README-reference-data-apis.md`:

1. `GET /api/v1/me/clients/`
2. `GET /api/v1/clients/{client_id}/offices/`
3. `GET /api/v1/client-offices/{client_office_id}/floors/`
4. `GET /api/v1/issues/`
5. `GET /api/v1/clients/{client_id}/quick-issues/`

The Office endpoint must apply the role-specific scope above. Ticket creation must repeat the same authorization; a previously returned dropdown option is not an authorization grant.

## 5. Issue validation and Department derivation

- `issue_ids` must be present, non-empty, and contain no duplicate IDs.
- Every Issue must exist and be active.
- Every selected Issue must belong to the same Department.
- All Issues must be validated from database state; do not trust a Department ID supplied by React.
- The common Issue Department becomes `origin_department_id`.
- Set `current_department_id` to the same Department at creation.
- The frontend should restrict additional Issue selections to the Department of the first selected Issue, but the backend must independently reject mixed-Department submissions.

Quick Issues are suggestions only. They do not bypass any of these validations. The Client's Quick Issues are ranked by frequency across historical Tickets, with recency as the tie-breaker, as defined in `README-reference-data-apis.md`.

## 6. Floor validation and conditional behaviour

Floors are physically owned by a Property. A Client Office may be mapped to one or more Floors through `ClientOfficeFloor`.

The service must load the active Floors mapped to the selected Client Office and apply these rules:

| Mapped Floors for Office | Frontend behaviour | Backend behaviour |
|---|---|---|
| Zero | Hide Floor selector | Create no `TicketFloor` rows; reject any submitted Floor IDs |
| Exactly one | Hide Floor selector | Automatically associate the sole mapped Floor; do not require `floor_ids` from the client |
| More than one | Show required multi-select | Require at least one selected Floor; every submitted Floor must be in the Office's mapping |

Additional rules:

- Reject duplicate Floor IDs.
- Reject Floor IDs that do not belong to the selected Client Office.
- Reject inactive or unknown Floor IDs.
- For a multi-Floor Office, an empty selection is invalid because the wireframe marks Floor(s) as required when the field is shown.
- The frontend cannot establish Floor eligibility by supplying arbitrary IDs; the backend revalidates the mapping.

## 7. Server-derived Ticket fields

The backend derives all of the following:

| Ticket field | Source/value |
|---|---|
| `created_by_id` | `request.user` |
| `origin_department_id` | Common Department of validated selected Issues |
| `current_department_id` | Same as `origin_department_id` at creation |
| `workflow_stage` | `PENDING_TECHNICIAN_ASSIGNMENT` |
| `status` | `OPEN` |
| `created_at` / `updated_at` | Server/database timestamps |
| `closed_by_id` | `NULL` |
| `closed_at` | `NULL` |
| displayed ticket reference | `TKT-{id}` derived after the Ticket has a primary key |

The initial Department POC is derived through `ticket.current_department.poc_user`. Do not create a TicketAssignment row for the Department POC; TicketAssignment is for Worker assignments only.

## 8. Transaction and side effects

Ticket creation requires multiple related writes. Perform them inside one `transaction.atomic()` block:

1. Create the Ticket with server-derived fields.
2. Create all `TicketIssue` rows.
3. Create all `TicketFloor` rows (including the automatically associated single Floor when applicable).
4. Create a user-actor `TicketActivity` event for `TICKET_CREATED`.
5. Create a system-actor `TicketActivity` event for `TICKET_ROUTED`, recording the initial Department/POC routing.

If any database write fails, roll back the entire operation. Do not leave a Ticket without its Issues, affected Floors, or creation/routing Activity.

Create `NotificationOutbox` rows for the concerned Facility Manager and current Department POC inside this same transaction (skip the actor and deduplicate recipients). Link these rows to the `TICKET_ROUTED` Activity as their `source_activity_id`. After commit, publish the outbox IDs to Celery using a safe `transaction.on_commit()` callback. If Redis publishing fails, leave the rows `PENDING` for the recovery command. See `README-async-processing.md`.

Prevent accidental duplicate form submission in React by disabling Submit while the request is in progress. A dedicated server-side idempotency-key protocol has not been selected and should not be added without a reason.

## 9. Successful response

Return `201 Created` with the created Ticket representation. Example:

```json
{
  "id": 1042,
  "ticket_number": "TKT-1042",
  "client_office": {
    "id": 10,
    "name": "Harness-1317"
  },
  "issues": [
    { "id": 101, "name": "AC not cooling" }
  ],
  "floors": [
    { "id": 102, "name": "2F" },
    { "id": 103, "name": "3F" }
  ],
  "origin_department": {
    "id": 1,
    "name": "Technical"
  },
  "current_department": {
    "id": 1,
    "name": "Technical"
  },
  "workflow_stage": "PENDING_TECHNICIAN_ASSIGNMENT",
  "status": "OPEN",
  "description": "AC units on floors 2 and 3 are producing warm air.",
  "created_at": "2026-11-02T10:30:00Z"
}
```

The response may include additional safe display fields such as Client name, creator display name, and current Department POC. Do not expose password hashes, refresh tokens, or unrelated user data.

After a successful creation the frontend opens the new Ticket's detail page. The creator can always view it because of the creator visibility rule (`README-authorization.md` §1), even when the Ticket routes to a Department they do not represent.

## 10. Validation and HTTP error behaviour

Use the shared error envelope defined in `README-api-conventions.md`. The outcomes are:

| Situation | Expected status |
|---|---|
| Missing/invalid access token | `401 Unauthorized` |
| Authenticated Worker attempts Ticket creation | `403 Forbidden` |
| User is not mapped to the selected Office's Client | `400 Bad Request` on `client_office_id`, with the same message as an unknown Office so unrelated Client data is not revealed |
| Facility Manager selects an Office in an unmanaged Property | `400 Bad Request` on `client_office_id`, with the same message as above |
| Unknown/inactive Client Office, Issue, or Floor in the request body | `400 Bad Request` on the relevant field (`README-api-conventions.md` §4) |
| No Issues / duplicate IDs / mixed Departments | `400 Bad Request` |
| Invalid Floor selection or missing Floor for a multi-Floor Office | `400 Bad Request` |
| Missing internal-user Description | `400 Bad Request` |

Example validation response:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Selected issues must belong to the same department.",
    "details": {
      "issue_ids": ["Issues cannot belong to multiple departments."]
    }
  }
}
```

Use the shared API error envelope. The finalized Ticket detail/action policy is `404 Not Found` for a Ticket outside the caller's visibility scope. Submitted reference IDs must also be validated against the caller's permitted Client/Office scope; do not return unrelated reference data. Keep reference-input validation responses consistent across endpoints.

## 11. Query efficiency

- Fetch selected Issues in one query and derive their common Department from the returned records.
- Fetch the Client Office with its Client and Property relationships using `select_related()` as appropriate.
- Fetch mapped Floors in one bounded query.
- Use `bulk_create()` for TicketIssue and TicketFloor rows when it preserves validation and expected signals.
- Build the response with `select_related()` / `prefetch_related()` to avoid N+1 queries.

Do not perform one database query per selected Issue or Floor.

## 12. Acceptance criteria and tests

At minimum, cover:

1. A Client user successfully creates a Ticket for a mapped Client Office.
2. A Facility Manager can create only for a mapped Client's Office in a Property they manage.
3. A Facility Manager cannot create for another manager's Property even when the Client is mapped to them.
4. A Department POC can create for an Office of any mapped Client, regardless of Property.
5. A Worker receives `403` when attempting creation.
6. Client-created Description may be omitted; internal-user Description may not be blank.
7. Mixed-Department Issues are rejected.
8. Invalid or out-of-Office Floors are rejected.
9. One mapped Floor is automatically attached; multiple mapped Floors require a selection; zero mapped Floors create no TicketFloor rows.
10. The Ticket, relationships, and Activity are committed together; injected failures roll back all writes.
11. Successful creation returns `201`, with initial workflow stage/status and server-derived Department fields.
12. The creator can open the created Ticket's detail even when it routes to a Department they do not represent.

## 13. Out of scope

- Separate Ticket creation endpoints for each role;
- Client or Department values accepted as authoritative fields in the payload;
- user-supplied workflow stage/status/creator/assignee fields;
- Tickets containing Issues from multiple Departments;
- multi-Department routing;
- Worker creation of Tickets;
- automatic Worker assignment;
- a dedicated QuickIssue table;
- a server-side idempotency-key subsystem unless later justified;
- external notification provider integration and notification UI; the simulated Celery notification/outbox flow is specified in `README-async-processing.md`.
