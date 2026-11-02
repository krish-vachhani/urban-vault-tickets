# API Conventions — Errors, Status Codes, Response Shapes

**Status:** FINALIZED (Phase 0 audit decisions G1, G2, G5, I4)
**Applies to:** every endpoint under `/api/v1/`

Several feature READMEs refer to a shared error envelope, a not-found policy, and common response shapes. This document is the single definition of those conventions. Feature READMEs define endpoint-specific behaviour; when they mention an error code or a user summary, they mean the definitions below.

## 1. Base path and format

- All endpoints live under `/api/v1/` and exchange JSON.
- Protected endpoints use `Authorization: Bearer <access_token>` (`README-authentication.md`).
- Successful responses return the resource or result directly (no `data` wrapper).

## 2. Error envelope

Every error response, whatever its status code, has this shape:

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

| Field | Meaning |
|---|---|
| `code` | Stable machine-readable code from §3; the frontend branches on this, never on `message` |
| `message` | Short human-readable summary, safe to show to the user |
| `details` | For `VALIDATION_ERROR`: field name → list of messages, with `non_field_errors` for object-level problems. Otherwise an empty object |

Implementation rules:

- One DRF exception handler (`REST_FRAMEWORK["EXCEPTION_HANDLER"]`) produces this envelope for every error, including DRF's own exceptions and the project's business exceptions. Views do not build error responses by hand.
- An unexpected exception returns `500` with `INTERNAL_ERROR` and a generic message. The stack trace is logged on the server and never returned.
- Never put tokens, passwords, SQL, or internal identifiers of inaccessible records in `message` or `details`.
- **Exception:** the infrastructure health probe `GET /api/v1/health/` is not a business endpoint. It returns its own small body (`{"status": "unavailable", "database": "unreachable"}` with `503`) because Docker and load balancers only read its status code.

## 3. Error codes and HTTP statuses

| HTTP | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Malformed or invalid input: missing fields, bad choices, unknown or out-of-scope IDs in the request body, invalid query parameters |
| 401 | `NOT_AUTHENTICATED` | Missing, invalid, or expired access token; invalid login credentials (generic message); invalid refresh token |
| 403 | `PERMISSION_DENIED` | The user can see the resource but may not perform the action (for example, a Worker creating a Ticket, a non-POC assigning a Worker); CSRF failure on auth endpoints |
| 404 | `NOT_FOUND` | The resource does not exist **or** is outside the user's visibility scope |
| 409 | `INVALID_TICKET_TRANSITION` | The user may perform the action, but the Ticket's current stage/status does not allow it (including a second assessment or resolving a closed Ticket) |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

**Not-found policy (finalized, I4).** A Ticket that does not exist and a Ticket the user cannot see both return `404`, on every Ticket detail, sub-resource (`/activities/`, `/history/`, `/comments/`, `/eligible-workers/`), and action endpoint. This prevents discovering other Tickets by guessing IDs.

**Order of checks** for Ticket action endpoints, so each request gets one predictable error:

1. Authentication → `401`
2. Ticket visibility → `404`
3. Action permission for this user → `403`
4. Request body validation → `400`
5. Ticket state, re-checked after the row lock → `409`

## 4. Invalid identifiers: URL versus request body

- **ID in the URL path** (for example `/clients/{id}/offices/`, `/client-offices/{id}/floors/`, `/tickets/{id}/`): unknown or out of the user's scope → `404 NOT_FOUND`.
- **ID in the request body** (for example `client_office_id`, `issue_ids`, `floor_ids`, `worker_id`, `department_id`): unknown, inactive, or out of the user's scope → `400 VALIDATION_ERROR` on that field. Use the same message for "does not exist" and "not allowed" so the response does not reveal records the user cannot see.

## 5. Response shapes

**Reference data** (Clients, Offices, Floors, Departments, Issues, Quick Issues, eligible Workers) is returned unpaginated:

```json
{ "results": [ { "id": 1, "name": "Harness" } ] }
```

These lists are small and scoped to the user. Issue search returns at most **20** results (`ISSUE_SEARCH_RESULT_LIMIT`), so the full catalogue is never fetched at once.

**Paginated collections** (the Ticket list and the Activity feed) use DRF page-number pagination:

```json
{ "count": 47, "next": "...?page=3", "previous": "...?page=1", "results": [] }
```

The frontend builds page requests from its own URL state and does not follow `next`/`previous` links directly.

| Endpoint | Default `page_size` | Maximum `page_size` |
|---|---|---|
| `GET /tickets/` | 10 | 50 |
| `GET /tickets/{id}/activities/` | 20 | 50 |

## 6. User summaries and role labels

Wherever a response refers to a person (creator, assignees, actors, Workers), it uses a user summary:

```json
{ "id": 20, "name": "Dhananjaya Murthy", "role": "DEPARTMENT_POC", "role_label": "Technical Manager" }
```

`role_label` reproduces the wireframe's "(Technical Manager)", "(Technician)", "(Client POC)" labels. It is computed on the server by one helper function, not stored:

| `role` | `role_label` |
|---|---|
| `CLIENT` | `Client POC` |
| `FACILITY_MANAGER` | `Facility Manager` |
| `DEPARTMENT_POC` | `{Department name} Manager`, e.g. `Technical Manager`, `IT Manager` |
| `WORKER` | `Technician` |

User summaries never include email addresses or other profile fields. Only `GET /api/v1/auth/me/` returns the authenticated user's own email.

## 7. Filter and query-parameter conventions

- A well-formed but unknown filter ID (for example `client_id=999`) returns an **empty result**, never an error and never a broader result.
- A malformed value (for example `client_id=abc`, `page=0`, `page_size=500`) returns `400 VALIDATION_ERROR`.
- An unsupported enumerated value (`tab`, `ordering`, `workflow_stage`, Activity `type`) returns `400 VALIDATION_ERROR`.
- Filters always narrow the user's visible queryset; they never grant access.

## 8. Timestamps and ticket references

- Timestamps are ISO 8601 in UTC with a `Z` suffix, e.g. `2026-10-27T06:10:00Z`. The frontend formats them in the browser's local time.
- The human-readable ticket reference is `TKT-{id}`, returned as `ticket_number`.
