# Ticket Listing API

**Status:** FINALIZED  
**Endpoint:** `GET /api/v1/tickets/`  
**Purpose:** Define the single role-aware, server-side paginated Ticket listing used by the Open Tickets and Closed Tickets tabs.

## 1. Requirements and design principles

The assignment requires every role to have Ticket listing with:

- Server-side pagination of multiple records;
- Search by Ticket Issue text;
- Filters for Client Name, Concerned Department, Concerned Facility Manager, and Ticket Status;
- Sorting by Created Time (Older First / Newest First).

Use one reusable endpoint for all roles. The backend determines the authenticated user's authorized Ticket queryset. Search, filters, ordering, and pagination are applied only after that authorization scope has been established.

Do not fetch all Tickets and filter them in React. Do not implement separate listing endpoints for each role.

## 2. Endpoint

```http
GET /api/v1/tickets/
Authorization: Bearer <access_token>
```

Supported query parameters:

| Parameter | Type / allowed values | Purpose | Default |
|---|---|---|---|
| `tab` | `open`, `closed` | Select the Open Tickets or Closed Tickets tab | `open` |
| `page` | Positive integer | Page number | `1` |
| `page_size` | Integer, 1–50 | Number of results per page | `10` |
| `search` | String | Case-insensitive partial search against associated Issue names only | Empty |
| `client_id` | Integer | Filter by Client | No filter |
| `department_id` | Integer | Filter by the Ticket's **current Department** | No filter |
| `facility_manager_id` | Integer | Filter by the Concerned Facility Manager (the current designated manager of the Property) | No filter |
| `workflow_stage` | Allowed workflow-stage value | Filter for the UI's Ticket Status filter | No filter |
| `ordering` | `created_at`, `-created_at` | Created Time, oldest or newest first | `-created_at` |

Example:

```http
GET /api/v1/tickets/?tab=open&page=1&page_size=10&search=AC&client_id=1&department_id=2&facility_manager_id=5&workflow_stage=PENDING_TECHNICIAN_ASSESSMENT&ordering=-created_at
```

Reject unsupported `tab`, `ordering`, or `workflow_stage` values with a consistent `400 Bad Request` validation response. Enforce the maximum page size of 50. The `next` and `previous` pagination links must preserve the active query parameters.

## 3. Open and Closed tab semantics

The Ticket has two distinct state dimensions: `workflow_stage` and closure `status`. The tabs are based on closure status:

| Ticket `status` | Tab |
|---|---|
| `OPEN` | Open Tickets |
| `TECHNICIAN_CLOSED` | Open Tickets |
| `CLOSED` | Closed Tickets |

`TECHNICIAN_CLOSED` means the Worker submitted an assessment; it does not mean the Client has confirmed resolution. Such Tickets remain in Open Tickets.

The UI's Ticket Status filter corresponds to `workflow_stage`, whose values are:

- `PENDING_TECHNICIAN_ASSIGNMENT`;
- `PENDING_TECHNICIAN_ASSESSMENT`;
- `PENDING_DEPARTMENT_POC_REVIEW`.

The `tab` parameter and `workflow_stage` filter are independent and may be combined. A closed Ticket preserves its workflow stage, so it may still be filtered by that stage in the Closed Tickets tab.

## 4. Authorization scope is always applied first

Create the base queryset from the authenticated user. Only then apply tab selection, filters, search, sorting, and pagination.

Every role's base queryset also includes the Tickets the user created (creator visibility, `README-authorization.md` §1). Build the scope with `Exists(...)` subqueries combined with `Q(...) | Q(...)` rather than joins plus `.distinct()`.

### Client

See all Tickets belonging to any Client mapped to the user through `UserClient`, regardless of who created the Ticket.

Conceptual queryset:

```python
Ticket.objects.filter(
    Exists(
        UserClient.objects.filter(
            user=request.user,
            client_id=OuterRef("client_office__client_id"),
        )
    )
)
```

### Facility Manager

See all Tickets from Client Offices within Properties for which the user is the designated Facility Manager, regardless of Client, creator, current Department, or closure status.

```python
Ticket.objects.filter(
    client_office__property__facility_manager=request.user
)
```

### Department POC

See all Tickets whose **current Department** is the Department represented by the authenticated POC, irrespective of Client or Property.

```python
Ticket.objects.filter(
    current_department__poc_user=request.user
)
```

### Worker

See Tickets currently or historically assigned to the authenticated Worker. Historical assignment preserves read-only Ticket visibility.

```python
Ticket.objects.filter(
    Exists(
        TicketAssignment.objects.filter(
            ticket=OuterRef("pk"),
            worker=request.user,
        )
    )
)
```

A historical Worker cannot perform Worker actions unless they are the current active assignee and the action's workflow preconditions are satisfied.

Never accept a role, user ID, Client scope, Property scope, Department scope, or Worker identity from query parameters as a replacement for authenticated-user authorization.

## 5. Filters

All four assignment-required filters must be available to every role. A filter narrows the already-authorized queryset; it never broadens access.

### Client Name — `client_id`

Filter through `client_office__client_id`.

### Concerned Department — `department_id`

**Finalized project decision: filter by `current_department_id`.**

This is an explicit implementation interpretation. The assignment brief describes Concerned Department as the Department to which the Issue belongs. This project uses the Ticket's current handling Department for the listing filter so that the filter reflects the Department currently responsible for the Ticket after forwarding. Preserve `origin_department_id` for initial classification/history; do not use it for this listing filter.

Conceptual filter:

```python
queryset = queryset.filter(current_department_id=department_id)
```

### Concerned Facility Manager — `facility_manager_id`

Filter through `client_office__property__facility_manager_id`.

For a Client, Department POC, or Worker, this filter only narrows Tickets that the user is already authorized to see. It does not grant access to another manager's Tickets.

### Ticket Status — `workflow_stage`

Filter by the Ticket's `workflow_stage` field, using the three user-facing workflow stages listed in Section 3. The Open/Closed tab continues to use the separate closure `status` field.

### Filter options — `GET /api/v1/tickets/filter-options/`

**Finalized decision (Phase 0 audit, B3).** The filter dropdowns need option lists that match what the user can see. `/me/clients/` is not suitable: it lists the Clients a user may create Tickets for, while Facility Managers, Department POCs, and Workers can see Tickets of Clients they are not mapped to. No other endpoint lists Facility Managers.

This read-only endpoint returns the distinct filter values found among the Tickets **visible to the authenticated user**: the same base queryset as the listing, before tab, filters, or search are applied.

```json
{
  "clients": [{"id": 1, "name": "Harness"}],
  "departments": [{"id": 1, "name": "Technical"}, {"id": 2, "name": "IT"}],
  "facility_managers": [{"id": 5, "name": "Chandan S"}],
  "workflow_stages": [
    {"value": "PENDING_TECHNICIAN_ASSIGNMENT", "label": "Pending Technician Assignment"},
    {"value": "PENDING_TECHNICIAN_ASSESSMENT", "label": "Pending Technician Assessment"},
    {"value": "PENDING_DEPARTMENT_POC_REVIEW", "label": "Pending Department POC Review"}
  ]
}
```

Rules:

- Derive options only from visible Tickets; never list a Client, Department, or Facility Manager the user has no visible Ticket for.
- `departments` uses each visible Ticket's **current** Department, matching the `department_id` filter.
- `facility_managers` uses the designated Facility Manager of each visible Ticket's Property.
- `workflow_stages` always lists the three stages.
- Sort each list by name. People are returned with `id` and `name` only.
- The response is not paginated. The frontend caches it and invalidates it after Ticket creation and Department changes.
- This endpoint serves the listing filters only. It is not the combined ticket-form data endpoint excluded by `README-reference-data-apis.md` §6.

## 6. Search

`search` searches associated Issue names only, using case-insensitive partial matching.

Examples:

```http
GET /api/v1/tickets/?search=AC
GET /api/v1/tickets/?search=internet
```

Do not silently expand search to Description, Client name, Ticket number, or comments. Those fields are not part of the assignment's specified Issue-text search.

Use the Ticket-to-Issue relationship through an `Exists(...)` subquery, for example `Exists(TicketIssue.objects.filter(ticket=OuterRef("pk"), issue__name__icontains=search))`. Unlike a join plus `distinct()`, this never duplicates Ticket rows when several of a Ticket's Issues match.

## 7. Sorting

Only Created Time sorting is required.

| `ordering` | Query ordering |
|---|---|
| `-created_at` | Newest first (default) |
| `created_at` | Oldest first |

For deterministic page boundaries when multiple Tickets have the same timestamp, use a stable ID tie-breaker:

- Newest first: `-created_at, -id`;
- Oldest first: `created_at, id`.

Do not expose arbitrary model-field ordering through the API.

## 8. Pagination

Use DRF `PageNumberPagination`.

- Default `page_size`: 10;
- Maximum `page_size`: 50;
- Default page: 1;
- Seed enough records to demonstrate several pages and the interaction of filters/search/sorting with pagination.

Response envelope:

```json
{
  "count": 47,
  "next": "http://localhost:8000/api/v1/tickets/?tab=open&page=2&page_size=10",
  "previous": null,
  "results": [
    {
      "id": 1047,
      "ticket_number": "TKT-1047",
      "workflow_stage": "PENDING_TECHNICIAN_ASSIGNMENT",
      "status": "OPEN"
    }
  ]
}
```

The count must be calculated after authorization and all active filters/search have been applied, but before slicing the current page.

## 9. Ticket list representation

Each result should include the data required by the wireframe's Ticket card without requiring one detail request per row:

- `id` and display `ticket_number` (`TKT-{id}`);
- Client ID/name;
- Client Office ID/name;
- associated Issues (IDs and names);
- affected Floors (IDs and names);
- `workflow_stage` and closure `status`;
- creator ID/name/role;
- `created_at`;
- current Department ID/name;
- current assignees: the designated POC derived from current Department and the active Worker assignment, if one exists;
- `action_required`: a boolean computed on the server for the authenticated user, driving the red "Action Required" badge;
- `role_label` on every user summary (`created_by`, `current_assignees`), as defined in `README-api-conventions.md` §6.

`action_required` is true when the Ticket is waiting on this user's workflow step:

- the current Department POC, at `PENDING_TECHNICIAN_ASSIGNMENT` or `PENDING_DEPARTMENT_POC_REVIEW`;
- the active Worker, at `PENDING_TECHNICIAN_ASSESSMENT`.

It is always false for a closed Ticket and for every other user. It is deliberately **not** derived from `available_actions`: the wireframe shows the badge to the POC at the review stage, where no CTA exists, and never to Clients even though they can mark a Ticket resolved.

Example item:

```json
{
  "id": 1042,
  "ticket_number": "TKT-1042",
  "client": {"id": 1, "name": "Harness"},
  "client_office": {"id": 10, "name": "Harness-1317"},
  "issues": [{"id": 101, "name": "AC not cooling"}],
  "floors": [{"id": 102, "name": "2F"}, {"id": 103, "name": "3F"}],
  "workflow_stage": "PENDING_TECHNICIAN_ASSESSMENT",
  "status": "OPEN",
  "created_by": {"id": 12, "name": "Chaitanya M", "role": "CLIENT", "role_label": "Client POC"},
  "created_at": "2026-11-02T10:30:00Z",
  "current_department": {"id": 1, "name": "Technical"},
  "current_assignees": [
    {"id": 14, "name": "Dhananjaya Murthy", "role": "DEPARTMENT_POC", "role_label": "Technical Manager"},
    {"id": 31, "name": "Prakash Kumar", "role": "WORKER", "role_label": "Technician"}
  ],
  "action_required": false
}
```

If no active Worker assignment exists, include the current Department POC and omit the Worker entry. Ensure the UI can display the Unassigned state where applicable.

Do not return sensitive User fields, credentials, password hashes, token material, or unrelated profile data.

## 10. Query performance

Use `select_related()` for single-valued relationships needed by list cards:

- `client_office`;
- `client_office__client`;
- `client_office__property__facility_manager`;
- `created_by`;
- `current_department`;
- `current_department__poc_user`.

Use `prefetch_related()` for collection relationships:

- TicketIssue and Issue;
- TicketFloor and Floor;
- active TicketAssignment and Worker.

Avoid N+1 queries. Use `Exists(...)` subqueries for visibility and search so multi-valued relationships (Issues, Assignments, Client mappings) never duplicate Ticket rows. Inspect query counts for representative list requests.

Proposed supporting indexes (coordinate with the database-design README to avoid duplicates):

- Ticket `(current_department_id, status, created_at)`;
- Ticket `(client_office_id, status, created_at)`;
- TicketAssignment `(worker_id, ticket_id)`;
- any additional index justified by observed query plans rather than added speculatively.

The listing endpoint should use the ORM and remain fully server-side. Do not fetch an unbounded Ticket collection and paginate/filter in React.

## 11. Error behaviour

Use the API-wide error envelope and authorization policy.

- `401 Unauthorized`: missing, expired, or invalid access token;
- `400 Bad Request`: invalid `tab`, unsupported ordering, invalid workflow-stage filter, invalid page/page size, or malformed filter value;
- filters and search never reveal out-of-scope data: they only narrow the visible queryset;
- `200 OK`: successful listing, including an empty `results` array when no records match.

An unknown but syntactically valid filter ID returns an empty result (`README-api-conventions.md` §7); it never broadens the queryset. A malformed value such as `client_id=abc` returns `400`.

## 12. Acceptance criteria and tests

Test at least the following:

1. Each role receives only its authorized Tickets.
2. Client POCs see Tickets created by other POCs mapped to the same Client.
3. Facility Managers see Tickets from all Client Offices in managed Properties and no others.
4. Department POC visibility and the Department filter both use `current_department_id`.
5. Worker visibility includes current and historical assignments without duplicate Ticket rows.
6. `tab=open` includes `OPEN` and `TECHNICIAN_CLOSED`; `tab=closed` includes only `CLOSED`.
7. The Client, current Department, Facility Manager, and workflow-stage filters work individually and together.
8. Issue-text search is case-insensitive and searches Issue names only.
9. Oldest-first and newest-first sorting are correct and deterministic.
10. Pagination returns the correct count, next/previous links, and page contents after filtering and searching.
11. Changing query parameters cannot expose Tickets outside the user's authorization scope.
12. List serialization does not cause N+1 query growth for related Client, Office, Issue, Floor, creator, Department, POC, and Worker data.
13. A user sees the Tickets they created even when no role rule grants visibility.
14. Filter options contain only values from the user's visible Tickets.
15. `action_required` is correct for the current POC (assignment and review stages), the active Worker, a Client, and closed Tickets.

## 13. Out of scope

- Client-side pagination/filtering/search over a complete Ticket collection;
- search by Description, Client name, Ticket number, or comments;
- arbitrary sorting by any model field;
- separate list endpoints for each role;
- cursor pagination;
- unbounded page sizes;
- filtering that bypasses the role-scoped base queryset.
