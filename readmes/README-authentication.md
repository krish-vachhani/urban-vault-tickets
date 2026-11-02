# Authentication Architecture — JWT with SimpleJWT

**Status:** Finalized  
**Scope:** Authentication, token lifecycle, browser token storage, seeded-account switching, and the authenticated-user endpoint.

This document records the agreed authentication design for the Urban Vault take-home assignment. It is an implementation specification for Claude Code; it must not be treated as permission to redesign the authentication architecture independently.

## 1. Purpose

The application has four authenticated user roles:

- `CLIENT`
- `FACILITY_MANAGER`
- `DEPARTMENT_POC`
- `WORKER`

The assignment requires seeded accounts for these roles, standard authentication, and a simple way to switch between the seeded accounts. Ticket visibility and action permissions must be enforced by the backend. Registration, password reset, and user-management screens are not required.

The frontend is React and the backend is Django REST Framework. The agreed authentication mechanism is JSON Web Tokens (JWT) using `djangorestframework-simplejwt`.

## 2. Finalized decisions

| Concern | Decision |
|---|---|
| Authentication library | Django REST Framework SimpleJWT |
| Access token storage | In React memory only |
| Refresh token storage | `HttpOnly` browser cookie |
| Access token lifetime | 10 minutes |
| Refresh token lifetime | 1 day |
| Refresh rotation | Enabled |
| Blacklist after rotation | Enabled |
| Logout | Blacklist the current refresh token and clear its cookie |
| Authorization source | Current database state, not JWT role claims |
| API access-token transport | `Authorization: Bearer <access_token>` |
| Demo account switching | Normal logout/login using seeded credentials; no impersonation endpoint |
| Password storage | Django's standard password hashing mechanisms |

## 3. Login and token lifecycle

### 3.1 Login

1. The user submits email and password to the login endpoint.
2. Django validates the credentials against the custom Django User model.
3. The backend issues an access token and a refresh token.
4. The access token is returned in the JSON response.
5. The refresh token is set as an `HttpOnly` cookie and is never returned in the JSON response.
6. React stores the access token in memory.
7. React obtains the authenticated-user profile for application context.

The refresh token must not be exposed to JavaScript.

### 3.2 Normal API requests

Protected API requests send the access token using the standard Bearer header:

```http
Authorization: Bearer <access_token>
```

Do not send the refresh token to ordinary resource endpoints. Do not use the refresh cookie as the authentication mechanism for ticket endpoints.

### 3.3 Access-token expiration

When an API request fails because the access token has expired:

1. The frontend calls the refresh endpoint. The browser sends the refresh cookie automatically for the same-origin auth path.
2. The frontend includes the CSRF token in the `X-CSRFToken` header.
3. The backend validates the refresh token.
4. SimpleJWT rotates the refresh token and blacklists the previous refresh token.
5. The backend sets the replacement refresh token as a new `HttpOnly` cookie and returns a new access token in JSON.
6. React replaces the in-memory access token and retries the original request once.

The frontend should prevent concurrent requests from launching multiple refresh operations. Use a single in-flight refresh operation and let waiting requests reuse its result. Do not retry the same request indefinitely.

### 3.4 Application reload

The access token is deliberately not persisted. On application startup or page reload:

1. React obtains a CSRF token.
2. React calls the refresh endpoint using the refresh cookie.
3. If refresh succeeds, React stores the new access token in memory and calls `/api/v1/auth/me/` to obtain the current user profile.
4. If refresh fails because the cookie is missing, expired, or revoked, React clears authentication state and shows the login screen.

### 3.5 Logout

1. React calls the logout endpoint with the CSRF header.
2. The backend blacklists the presented refresh token when it is valid.
3. The backend clears the refresh cookie using the same cookie name, path, and security attributes.
4. React clears the access token and user profile from memory.
5. The user is returned to the login screen.

Logout must not rely on a still-valid access token; a user whose access token has expired should still be able to revoke the refresh token.

**Important limitation:** Blacklisting a refresh token does not immediately invalidate an access token that has already been issued. Such an access token may remain usable until its expiry (at most the configured 10-minute lifetime). The frontend must clear it immediately on logout, and the short access-token lifetime limits exposure if a token has been copied.

## 4. Browser storage and cookie security

### 4.1 Access token

- Keep the access token in application memory only (for example, in the authentication provider/state layer).
- Do not store it in `localStorage`, `sessionStorage`, IndexedDB, or a persistent browser cache.
- Clear it on logout, account switching, failed refresh, and authentication-state reset.

### 4.2 Refresh cookie

Use a host-only cookie with these attributes:

| Attribute | Setting |
|---|---|
| `HttpOnly` | `true` |
| `Secure` | `true` in production; disabled only for local HTTP development |
| `SameSite` | `Lax` |
| `Path` | `/api/v1/auth/` |
| `Domain` | Unset (host-only cookie) |
| Lifetime | Match the 1-day refresh-token lifetime |

The cookie name should be a clear application-specific name, such as `uv_refresh`.

The refresh token must not be included in API response JSON, frontend logs, analytics, or error messages.

### 4.3 CSRF protection

The refresh token is automatically sent by the browser as a cookie. Therefore, endpoints that set, rotate, or revoke this cookie must be protected against CSRF.

- Use Django's CSRF protection for login, refresh, and logout operations.
- Expose a small CSRF bootstrap endpoint that sets/returns a Django CSRF token.
- Send that token in the `X-CSRFToken` header on unsafe authentication requests.
- Validate the request origin/referer using Django's configured CSRF protections.
- Configure `CSRF_TRUSTED_ORIGINS` through environment-specific settings where required.
- In production, use HTTPS and secure cookies.

**Explicit enforcement is required (Phase 0 audit, R2).** DRF views are exempt from Django's CSRF check unless DRF session authentication is used, so CSRF is **not** enforced on the login, refresh, and logout views automatically. Implementation rules:

- Enforce CSRF explicitly on the login, refresh, and logout views (for example with `csrf_protect` applied to the view's `dispatch`, or an equivalent explicit check). Do not rely on the middleware alone.
- `GET /api/v1/auth/csrf/` uses `ensure_csrf_cookie` and returns the token, so the frontend can obtain it at startup and send it in `X-CSRFToken`.
- A missing or invalid token is rejected with `403 Forbidden` and the standard error envelope (`PERMISSION_DENIED`).
- Automated tests cover a missing token and an invalid token for login, refresh, and logout, plus a successful request with a valid token.

Access-token-authenticated resource endpoints use the Bearer header. They must not fall back to cookie authentication.

### 4.4 Same-origin application routing

Prefer serving the frontend and `/api/v1/` under the same browser origin:

- In local development, configure the React development server to proxy `/api` requests to Django.
- In production, use a reverse proxy or equivalent routing so the browser sees the frontend and API under the same origin.

This avoids unnecessary cross-origin cookie configuration. If deployment later requires a genuinely cross-site frontend/API arrangement, that is a separate security decision and must be reviewed rather than changing cookie settings casually.

## 5. JWT claims and authorization

JWT establishes the authenticated user's identity. It is not the source of truth for the user's current role or business relationships.

- Use the standard SimpleJWT token claims, including the user identifier and token lifecycle claims.
- Do not embed role, department membership, Client mappings, Property assignments, or ticket permissions as authoritative JWT claims.
- On authenticated requests, resolve the User from the database and check that the account is active.
- Apply ticket visibility and action authorization using current database relationships and the finalized authorization rules.

This ensures that a role or relationship change is reflected by subsequent API requests without waiting for a role claim in an old access token to expire.

## 6. Authentication API contract

The following authentication endpoints are finalized at the contract level. Ticket and reference-data contracts are specified in their own READMEs; the shared error envelope, error codes, and user summary shape are in `README-api-conventions.md`.

### 6.1 Obtain CSRF token

```http
GET /api/v1/auth/csrf/
```

Purpose:
- Set Django's CSRF cookie.
- Return a CSRF token for React to include in `X-CSRFToken` on unsafe authentication requests.

Example response:

```json
{
  "csrf_token": "<csrf-token>"
}
```

### 6.2 Login

```http
POST /api/v1/auth/login/
Content-Type: application/json
X-CSRFToken: <csrf-token>
```

Request:

```json
{
  "email": "chaitanya@example.com",
  "password": "<password>"
}
```

Successful response (illustrative):

```json
{
  "access": "<short-lived-access-token>",
  "user": {
    "id": 12,
    "name": "Chaitanya",
    "email": "chaitanya@example.com",
    "role": "CLIENT"
  }
}
```

The backend also sets the refresh cookie. It must not include a `refresh` property in the JSON response.

Invalid credentials return a generic `401 Unauthorized` response. Do not reveal whether the email or password was the incorrect part.

### 6.3 Refresh access token

```http
POST /api/v1/auth/refresh/
X-CSRFToken: <csrf-token>
```

- No refresh token is accepted in the JSON body.
- The refresh token is read only from the `HttpOnly` cookie.
- On success, rotate the refresh token, blacklist the previous token, set the new cookie, and return the new access token.

Example response:

```json
{
  "access": "<new-short-lived-access-token>"
}
```

A missing, expired, malformed, or blacklisted refresh token returns `401 Unauthorized` and does not issue a new access token.

### 6.4 Logout

```http
POST /api/v1/auth/logout/
X-CSRFToken: <csrf-token>
```

- Read the refresh token from the cookie.
- Blacklist it when valid.
- Clear the refresh cookie.
- Clear frontend in-memory authentication state.

The endpoint should handle an already-missing or expired refresh cookie gracefully and still clear the browser cookie. It must not expose token contents in errors.

### 6.5 Current authenticated user

```http
GET /api/v1/auth/me/
Authorization: Bearer <access_token>
```

Example response (illustrative):

```json
{
  "id": 12,
  "name": "Dhananjaya Murthy",
  "email": "dhananjaya@example.com",
  "role": "DEPARTMENT_POC",
  "department": {
    "id": 2,
    "name": "Technical"
  },
  "clients": [
    {
      "id": 1,
      "name": "Harness"
    },
    {
      "id": 2,
      "name": "Acme"
    }
  ]
}
```

The response must reflect current database relationships. Return the Department for Department POCs (through `Department.poc_user`) and Workers (through `DepartmentWorker`); return `department: null` for Clients and Facility Managers. Include `role_label` as defined in `README-api-conventions.md` §6. Return only Client associations relevant to the authenticated user.

Unauthenticated or invalid access-token requests return `401 Unauthorized`.

## 7. SimpleJWT configuration

Use the following agreed baseline. Values may be moved into settings/environment configuration, but do not change their meaning without updating this document.

```python
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY"),
    "AUTH_HEADER_TYPES": ("Bearer",),
}
```

Install and enable SimpleJWT's blacklist application and run its migrations:

```python
INSTALLED_APPS = [
    # Django and project applications...
    "rest_framework_simplejwt.token_blacklist",
]
```

Use a dedicated `JWT_SIGNING_KEY` supplied through environment configuration. Do not commit the key. Do not reuse a hard-coded development value in production.

Configure DRF's default authentication class to use SimpleJWT's `JWTAuthentication`. Do not configure the API to silently fall back to cookie-based authentication.

## 8. Seeded accounts and account switching

The assignment requires seeded accounts for all four roles and a simple way to switch between them.

Provide at least one reproducible demo account for each role:

- Client POC
- Facility Manager
- Department POC
- Worker

The login screen may show a development-only demo account selector that pre-fills the selected account's email. The user must still authenticate through the normal login endpoint using credentials.

Implementation guidance:

- Seed demo accounts using a reproducible Django management command or fixture.
- Read the demo password from an environment variable such as `SEED_DEMO_PASSWORD`; do not commit a real password.
- Document demo credentials in local development instructions without putting secrets in source control.
- Show the demo selector only in development or when an explicit development flag enables it.
- Account switching must call logout, clear the current in-memory access token and user state, then perform a normal login for the next account.
- Do not create an endpoint that impersonates another user or bypasses password validation.

The exact demo names, email addresses, relationships, and seed-data volumes are specified in `README-seed-data.md`. The example identities in this document are illustrative.

## 9. Out of scope

Do not implement the following for this assignment:

- Public registration.
- Password reset or password recovery screens.
- User-management screens.
- OAuth/social login.
- Multi-factor authentication.
- A custom identity provider.
- User impersonation or authentication bypass for demo switching.

## 10. Implementation and testing checklist

Claude Code must implement and verify the following behaviours:

- [ ] Login succeeds with valid seeded credentials.
- [ ] Login rejects invalid credentials with a generic error.
- [ ] Access token is returned in JSON; refresh token is only set as an `HttpOnly` cookie.
- [ ] Refresh token is never stored in localStorage or sessionStorage.
- [ ] Protected APIs require a valid Bearer access token.
- [ ] Expired access token can be renewed using the refresh cookie.
- [ ] Refresh rotation replaces the cookie and blacklists the previous refresh token.
- [ ] A blacklisted, malformed, or expired refresh token cannot obtain a new access token.
- [ ] Logout blacklists the current refresh token and clears the cookie.
- [ ] CSRF validation is enforced for login, refresh, and logout, with automated tests for missing and invalid tokens.
- [ ] Application reload restores the session through refresh and `/me/`.
- [ ] Disabled users cannot authenticate or continue making authenticated API requests.
- [ ] Changing accounts clears the previous frontend authentication state.
- [ ] Current role and relationships are resolved from the database, not trusted from JWT role claims.
- [ ] The development-only demo account selector is not exposed in production.

At least one automated backend test should cover authentication or authorization, as required by the assignment. Additional tests around refresh rotation, blacklist behaviour, CSRF, and disabled users are recommended where time permits.

## 11. Decision rationale

JWT with SimpleJWT was selected because the application has a separate React frontend and DRF API, and a Bearer-token contract gives them a clear integration boundary.

The access-token-in-memory and refresh-token-in-`HttpOnly`-cookie design avoids persistent JavaScript-readable token storage while retaining a usable session across page reloads. Refresh rotation and blacklisting limit refresh-token reuse. Database-backed authorization avoids treating potentially stale role and relationship claims as permissions.

This design is more involved than Django Session Authentication, but it is the agreed architecture. Do not simplify it by moving both tokens into localStorage or by returning the refresh token in JSON.

## 12. Assignment source and scope

Source-derived requirements: the take-home assignment requires standard authentication, seeded accounts for Client, Facility Manager, Department POC, and Worker roles, a simple account-switching method, and backend-enforced ticket visibility/action permissions. Registration, password-reset, and user-management screens are not required.

The JWT mechanism, token lifetimes, cookie storage, rotation, blacklist, and endpoint contracts in this document are architectural decisions made for this implementation; they are not explicitly mandated by the assignment brief.
