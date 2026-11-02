# Reference Data APIs

**Status:** FINALIZED  
**Scope:** Read-only APIs used to populate ticket-creation forms and ticket-handling dropdowns, including Client, Client Office, Floor, Department, Issue, Quick Issue, and eligible Worker data.

This document records the agreed Reference Data API design for the Urban Vault take-home assignment. It is an implementation specification for Claude Code. Do not replace the separate-resource approach with a single aggregated form-data endpoint.

## 1. Purpose

Reference Data APIs provide the data needed by React forms and action panels. They do not create Tickets or mutate ticket workflow state.

The ticket-creation form needs to resolve the following dependencies:

1. Which Clients are associated with the authenticated user?
2. Which Client Offices belong to the selected Client?
3. Which Floors are associated with the selected Client Office?
4. Which Issues can be selected, optionally filtered by Department and search text?
5. Which frequent Issues should appear as Quick Issues for the selected Client?

The Department POC's Assign Worker action needs to retrieve eligible Workers for a particular Ticket.

## 2. Finalized architectural decisions

| Concern | Decision |
|---|---|
| API structure | Separate resource endpoints; do not add one combined ticket-form-data endpoint |
| Authentication | All endpoints require JWT authentication |
| Client choices | Return only Clients mapped to the authenticated User through `UserClient` |
| Client Office choices | Return Offices belonging to the requested Client after checking the User's Client association; for Facility Managers, additionally restrict to Offices in Properties they manage |
| Floor choices | Return only Floors mapped to the requested Client Office |
| Departments | Return active organization-wide Departments |
| Issues | Return active Issues; support search and optional Department filtering |
| Quick Issues | Top four Issues by frequency across the selected Client's Ticket history; use recency as the tie-breaker |
| Eligible Workers | Ticket-scoped endpoint: `GET /api/v1/tickets/{ticket_id}/eligible-workers/` |
| Worker eligibility | Active Workers who belong to the Ticket's current Department |
| Aggregation | Do not create a combined endpoint; the frontend may fetch independent resources as needed |

## 3. Endpoint contracts

All endpoints use the `/api/v1/` prefix and require an authenticated user. The frontend sends the access token using:

```http
Authorization: Bearer <access_token>
```

### 3.1 Authenticated User's Clients

```http
GET /api/v1/me/clients/
```

Purpose: Populate the Client selector using the authenticated User's `UserClient` mappings.

Example response:

```json
{
  "results": [
    { "id": 1, "name": "Harness" },
    { "id": 2, "name": "Acme" }
  ]
}
```

Rules:

- Do not accept a `user_id` query parameter to select whose Client mappings are returned.
- Derive the User exclusively from the authenticated request.
- Return only active Clients associated with that User.
- If the user has one Client, the frontend may preselect it.
- If the user has multiple Clients, the frontend displays the Client selector.
- If the user has no associated active Clients, return an empty result; the frontend must show a useful empty/error state rather than allowing an invalid Ticket submission.
- This endpoint lists the Clients a user may **create** Tickets for. It is not used for the Ticket listing's Client filter, whose options come from `GET /api/v1/tickets/filter-options/` (`README-ticket-listing-api.md` §5).

### 3.2 Client Offices for a Client

```http
GET /api/v1/clients/{client_id}/offices/
```

Purpose: Populate the conditional Client Office selector after a Client is selected.

Example response:

```json
{
  "results": [
    {
      "id": 10,
      "name": "Harness-1317",
      "code": "1317",
      "property": { "id": 5, "name": "Building A" },
      "floor_count": 3
    },
    {
      "id": 11,
      "name": "Harness-1318",
      "code": "1318",
      "property": { "id": 6, "name": "Building B" },
      "floor_count": 2
    }
  ]
}
```

Rules:

- The authenticated User must be mapped to `{client_id}` through `UserClient`.
- Return only active Client Offices belonging to that Client.
- **Additional Facility Manager scope:** if the authenticated User has role `FACILITY_MANAGER`, additionally require `ClientOffice.property.facility_manager_id == request.user.id`. This means the returned Offices are the intersection of (a) the selected Client's Offices and (b) Properties managed by the Facility Manager. Do not return other Offices of the same Client in Properties managed by someone else.
- For `CLIENT` and `DEPARTMENT_POC` users, return all active Offices belonging to the mapped Client; their visibility/creation scope is governed by their respective role rules.
- If the Client has one Office, the frontend may preselect it.
- If the Client has multiple Offices, display the conditional Office selector.
- When the selected Client changes, clear the previously selected Office, Floors, Issues, and Quick Issues before loading data for the new Client.
- A Client Office is the Ticket's location anchor. A Ticket must reference one specific Client Office, not just a Client.
- The same Client/Office authorization must be repeated by the Ticket creation endpoint; a dropdown response is not proof of authorization.

### 3.3 Floors for a Client Office

```http
GET /api/v1/client-offices/{client_office_id}/floors/
```

Purpose: Populate the Floor multi-select for the selected Client Office.

Example response:

```json
{
  "results": [
    { "id": 101, "name": "1F" },
    { "id": 102, "name": "2F" },
    { "id": 103, "name": "3F" }
  ]
}
```

Rules:

- The authenticated User must be mapped to the Client that owns the Office.
- Apply the same role-specific Office scope as the Client Office endpoint. In particular, a Facility Manager may retrieve Floors only for an Office whose Property they manage.
- Return only active Floors mapped through `ClientOfficeFloor`.
- The floor mapping must be consistent with the Office's Property.
- If there is exactly one mapped Floor, the frontend may hide the selector and the Ticket creation service should associate that Floor automatically.
- If there are multiple mapped Floors, the frontend must require one or more selections.
- If there are no mapped Floors, no Floor selector is shown and no `TicketFloor` rows are created.
- Ticket creation must independently validate every submitted Floor against the selected Client Office's mapping.

### 3.4 Departments

```http
GET /api/v1/departments/
```

Purpose: Return active organization-wide Departments for reference/display and Department forwarding choices.

Example response:

```json
{
  "results": [
    { "id": 1, "name": "Technical" },
    { "id": 2, "name": "IT" },
    { "id": 3, "name": "Electrical" }
  ]
}
```

Rules:

- Departments are organization-wide, not Property-specific.
- Return active Departments only.
- The Change Department operation must independently authorize the current Department POC, validate that the destination is active and different from the current Department, and require a non-empty forwarding note.
- The frontend may exclude the Ticket's current Department from the selection, but backend validation is authoritative.
- This endpoint does not grant ticket visibility or Department POC action permissions.

### 3.5 Search Issues

```http
GET /api/v1/issues/?search=AC
GET /api/v1/issues/?department_id=1&search=AC
```

Purpose: Populate the searchable, multi-select Issue control.

Example response:

```json
{
  "results": [
    {
      "id": 101,
      "name": "AC not cooling",
      "department": { "id": 1, "name": "Technical" }
    }
  ]
}
```

Rules:

- Return active Issues only.
- `search` matches Issue text/name.
- `department_id` is an optional filter.
- Include the Issue's Department in each result so the frontend can identify the Department represented by the selected Issue.
- Once the first Issue is selected, the frontend should restrict subsequent Issue choices to that same Department.
- Ticket creation must validate that every submitted Issue exists, is active, and belongs to the same Department.
- The Ticket's `origin_department_id` is derived from the common Department of the selected Issues; it is not accepted as an authoritative client-supplied value.

Reference-data endpoints return an unpaginated `{"results": [...]}` object (`README-api-conventions.md` §5). Issue search returns at most 20 results, so the full catalogue is never fetched at once.

### 3.6 Quick Issues for a Client

```http
GET /api/v1/clients/{client_id}/quick-issues/
```

Purpose: Return up to four frequently reported Issues for the selected Client so the frontend can render the wireframe's "Quick Issues - tap to autofill" suggestions.

Example response:

```json
{
  "results": [
    {
      "id": 101,
      "name": "AC not cooling",
      "department_id": 1,
      "occurrences": 12,
      "last_reported_at": "2026-10-27T11:40:00Z"
    }
  ]
}
```

Ranking algorithm:

1. Consider the selected Client's Ticket history across all of that Client's Offices.
2. Count how many distinct Tickets contain each Issue through `TicketIssue`.
3. Sort by occurrence count descending.
4. Break ties by the most recent Ticket creation time containing that Issue, descending.
5. Return at most four active Issues.

Additional rules:

- A Client user or internal employee must be mapped to the requested Client through `UserClient`.
- The same Quick Issue endpoint is used for either ticket-creation flow; the frontend passes the selected Client ID.
- Quick Issues are suggestions only. They do not bypass Issue selection validation or the same-Department rule.
- Tapping a Quick Issue selects/autofills that Issue in the multi-select control. The user can continue selecting other Issues from the same Department.
- Once an Issue is selected, Quick Issue chips from a different Department are disabled.
- No separate `QuickIssue` table is required; calculate results from historical `TicketIssue` relationships.
- Include historical Tickets regardless of current open/closed status because the ranking represents the Client's Ticket creation history. Only currently active Issue catalogue entries are returned.

The frequency ranking and recency tie-breaker are finalized product decisions for this assignment. The source wireframe only says Quick Issues are based on the Client's ticket creation history; the precise top-four ranking is our documented implementation choice.

### 3.7 Eligible Workers for a Ticket

```http
GET /api/v1/tickets/{ticket_id}/eligible-workers/
```

Purpose: Populate the Worker selector in the Department POC's Assign Worker panel.

Each Worker is a user summary (`README-api-conventions.md` §6), so `role` is always `WORKER` and `role_label` is `Technician`.

Example response:

```json
{
  "results": [
    { "id": 31, "name": "Prakash Kumar", "role": "WORKER", "role_label": "Technician" },
    { "id": 32, "name": "Rahul Sharma", "role": "WORKER", "role_label": "Technician" }
  ]
}
```

Rules:

- Only the Ticket's current Department POC may retrieve this list for assignment.
- The Ticket must be visible to that POC through its current Department relationship.
- The Ticket must be `PENDING_TECHNICIAN_ASSIGNMENT` and `OPEN`.
- Return active Users whose role is `WORKER` and who have a `DepartmentWorker` row for the Ticket's `current_department_id`.
- Do not add Property/Worker mapping or geographic eligibility; this was explicitly excluded from the agreed model.
- The Assign Worker POST endpoint must repeat all authorization, workflow-stage, role, and Department-membership checks. The GET response does not authorize a later POST.
- If the Ticket is not accessible to the caller, do not reveal its existence through this endpoint.

## 4. Frontend dependency and selection behaviour

The frontend must treat reference data as dependent resources rather than loading every possible value at application startup.

For ticket creation by any eligible role:

1. Fetch `/me/clients/`.
2. Preselect the Client if exactly one is returned; otherwise require Client selection. This conditional Client selector applies to Client users as well as internal employees because `UserClient` is many-to-many for all roles.
3. Fetch Offices for the selected Client. The backend applies role-specific Office scope before returning results.
4. Preselect the Office if exactly one authorized Office is returned; otherwise require Office selection. For Facility Managers, only Offices in Properties they manage are returned; for Client and Department POC users, all active Offices belonging to the mapped Client are returned.
5. Fetch Floors for the selected Office.
6. Show a Floor multi-select only when more than one mapped Floor exists; auto-associate the single Floor when only one exists.
7. Fetch Issues with search support and fetch Quick Issues for the selected Client.
8. After the first Issue is selected, restrict further Issue selection to its Department.

For Client ticket creation, use the same Client and Office resolution behaviour. If the Client user is associated with multiple Clients, conditionally show the Client selector as agreed; if only one Client is mapped, preselect it.

When a parent selection changes, clear dependent child selections immediately to prevent stale IDs from being submitted.

## 5. Authorization and error behaviour

All endpoints require authentication. Enforce access on the backend; never rely on frontend filtering or hidden controls.

Expected behaviour:

- Missing/invalid access token: `401 Unauthorized`.
- Client, Office, or Floor addressed in the URL but outside the user's scope: `404 Not Found`, so its existence is not revealed.
- Eligible Workers for a Ticket outside the user's visibility: `404 Not Found`. Ticket visible but the user is not its current Department POC: `403 Forbidden`. Ticket not awaiting assignment: `409 Conflict`.
- Unknown resource: `404 Not Found`.
- Invalid query parameter or malformed ID: `400 Bad Request`.

Use the common error envelope defined in `README-api-conventions.md`. Do not invent a separate error shape for each reference-data endpoint.

## 6. Out of scope

- A combined `/ticket-form-data/` endpoint.
- Client, Office, Floor, Department, or Issue create/update/delete endpoints; these are seeded/reference data for this assignment.
- A standalone `QuickIssue` table.
- Worker-to-Property eligibility mapping.
- Automatic Worker assignment or workload balancing.
- Returning all Clients or all Workers and filtering them in React.

## 7. Implementation acceptance criteria

- Every endpoint requires JWT authentication.
- `/me/clients/` returns only the caller's mapped active Clients.
- A user cannot retrieve another Client's Offices or Quick Issues without a `UserClient` mapping.
- Office and Floor results are scoped to the requested parent records and the caller's Client mapping.
- Facility Manager Office and Floor results are additionally restricted to Properties where the caller is the designated Facility Manager; a Client mapping alone does not authorize an Office in another Property.
- Issue search and optional Department filtering work server-side.
- Selecting an Issue from one Department prevents selecting another Department's Issue in the same Ticket; the backend independently rejects mixed-Department submissions.
- Quick Issues return at most four Issues, ranked by frequency and then recency, using historical Tickets across all Offices of the selected Client.
- The eligible-Workers endpoint is ticket-scoped and only returns active Workers in the Ticket's current Department to the authorized current Department POC while the Ticket awaits Worker assignment.
- The later action endpoints repeat all relevant authorization and validation; a reference-data response is never treated as an authorization grant.
- The frontend clears dependent selections when the parent Client or Office changes.
