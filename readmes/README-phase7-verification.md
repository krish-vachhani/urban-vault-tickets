# Phase 7 — Integration verification and hardening

Verified on 2 November 2026. Starting revision: `a3ec084`. The working tree was clean before this phase. This report records pre-commit verification; changes were left uncommitted for review and nothing was pushed.

The implementation plan names Phase 7 "Automated test completion and hardening". This verification also covers the integration checks explicitly requested for this phase. Phase 8 submission/documentation work has not started.

## 1. Infrastructure

Executed `docker compose up -d --wait` against the existing stack. All six services were running: PostgreSQL, Redis, Django, frontend, Celery Worker, and one Celery Beat. PostgreSQL, Redis, and backend reported healthy through their configured health checks. Frontend, Worker, and Beat were verified through HTTP requests, Celery ping, and actual notification delivery; these three services do not define Compose health checks.

Executed `docker compose exec -T backend celery -A config.celery:celery_app inspect ping`: one worker responded. Worker and Beat were restarted after the logging fix to load the updated code.

Live requests through Vite returned HTTP 200 for `/api/v1/health/` with database status `ok`, and HTTP 200 for the CSRF bootstrap with a token and cookie. Authenticated reads and writes also went through Vite to Django, with the application origin supplied for CSRF checks. Tokens, cookies, and passwords were not printed.

The existing images and persistent volumes were reused. A clean-machine image rebuild was not performed. No database reset, seed reload, volume deletion, or configuration overwrite was performed.

## 2. Backend automated checks

Final command:

```bash
docker compose exec -T backend python manage.py test --noinput
```

Result: **376 tests passed**, in 10.028 seconds. Django created and destroyed its separate PostgreSQL test database. The development database was not used as the test database.

Existing tests were inspected and executed for:

- Real JWT authentication, refresh rotation/blacklisting, logout, account switching, disabled accounts, and CSRF enforcement.
- All four visibility rules, creator visibility, historical Worker visibility, inaccessible-ID 404 responses, action authorization, and Facility Manager Property restrictions.
- Ticket creation, validation, server-derived fields, Department/Floor rules, atomic rollback, and error envelopes.
- Listing scope, all four filters and combinations, Issue search, stable ordering, server pagination, filter options, and query counts.
- Assignment, Department forwarding, all three assessment outcomes, invalid transitions, closure, comments, Activity, and assignment/Department History.
- Database constraints and real concurrent transactions for competing assignments, duplicate assessments, resolution versus assessment, and duplicate resolution.
- Notification success, durable retry/backoff/exhaustion, idempotency, commit/rollback, broker-outage recovery, dispatch selection, and stale-processing recovery.

Notification delivery failures were induced with controlled mocks. Automated tests require neither an external email provider nor AWS.

## 3. Frontend automated checks

Executed:

```bash
docker compose exec -T frontend npm run test -- --run
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run build
```

Results: **78 tests passed across 11 files**, in 4.16 seconds; TypeScript, ESLint, and production build passed. The baseline had 75 frontend tests; three session-race regression cases were added.

Coverage includes dependent Client/Office/Floor/Issue form interactions, validation and API errors, role-specific CTAs, action payloads and conflicts, listing URL state, empty/error handling, ticket visibility loss, comments/Activity, session restoration, account-cache clearing, and single-flight token refresh.

The production build emits a non-blocking chunk-size warning (approximately 869 kB JavaScript before gzip, 273 kB after gzip). No bundle optimization was introduced without a demonstrated functional problem.

## 4. Live workflow verification

Executed a temporary Python HTTP smoke script through the running Vite proxy using real seeded-account logins. Its password came from the existing container environment and was never printed. The script created verification records rather than changing existing tickets.

| Journey | Evidence executed in this phase |
|---|---|
| Client creates and resolves | Ticket 87: Client creation, POC assignment, Worker assessment, Client resolution, repeated-resolution 409 |
| Facility Manager creates and views | Manager viewed ticket 87 without handling permission; created ticket 88 and resolved it as creator |
| Department POC assigns and forwards | Assigned ticket 87; forwarded ticket 88 from Technical to IT; original POC subsequently received 404; destination POC assigned an IT Worker; origin Department stayed Technical |
| Worker assessment | `FULLY_RESOLVED` on ticket 87 and `CHANGE_REQUESTED` on ticket 88; all three outcomes also passed in automated API tests |
| Comments and Activity/History | Client, Manager, POC, and Worker comments succeeded on a visible ticket; each role read Activity and assignment History |
| Scope and errors | Unrelated Client detail/comment requests returned 404; non-creator Manager resolution and Worker creation returned 403; repeated assignment/resolution returned 409; invalid page returned 400 |
| Listing | Live pagination, each of four filters, Issue search, and both Created Time sort directions succeeded; detailed semantics additionally asserted by automated tests |
| Session | Real refresh-cookie exchange restored authenticated access; logout cleared the cookie and subsequent refresh returned 401; account switching/cache isolation additionally verified by automated tests |

Live outbox evidence: all **10** notification rows for tickets 87–89 reached `SENT`, each with `attempt_count=1` and `sent_at` populated. Ticket 89 was created through the normal service while suppressing only its immediate post-commit publish in that script process. Both due rows began unpublished, then the actual Beat scheduler dispatched them through Redis to the actual Worker. No manual dispatcher or direct task invocation delivered those two rows.

The temporary smoke harness initially used an incorrect action-hint field name, then inspected a cached QuerySet after waiting for delivery. These were harness errors, not application defects. The field name was corrected; a follow-up script freshly queried all 10 delivered rows, closed ticket 89, and completed refresh/logout assertions. The main script's initial nonzero exits are not counted as a passing single end-to-end command.

Tickets **87, 88, and 89** remain as clearly labelled, closed verification records. No pre-existing ticket or seeded record was deleted or edited.

## 5. Confirmed bugs and fixes

### Requests could cross a logout/account-switch boundary

The Axios retry logic treated any replacement token as a refresh of the same session. A delayed 401 from the old account could therefore replay its mutation under the new account. A pending refresh could also overwrite cleared credentials, or the new account's credentials, after the previous session ended.

The fix tracks a session version that changes when credentials are cleared. Requests retain their originating version; obsolete retries are cancelled. Refresh completion checks its originating version before setting an access token. Obsolete failures do not terminate a newer session. Normal single-flight refresh and late 401 retry within the same session remain covered and pass.

Three deterministic regression cases cover old-account mutation replay, refresh completion after logout, and refresh completion after switching accounts. The original two cases were run before the fix and failed as expected.

### Notification error logs could reveal arbitrary exception details

Outbox error summaries were sanitized for database storage, but `logger.exception()` still emitted raw exception messages and tracebacks for unexpected delivery and broker-publication failures. Those messages can include connection credentials.

Both paths now log application identifiers and exception type without arbitrary exception text or traceback. Existing retry and broker-outage tests were extended to assert safe logs. Both assertions failed before the fix and pass in the complete final backend suite. Retry scheduling and recovery behavior are unchanged.

## 6. Migrations and system checks

Executed successfully:

```bash
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py makemigrations --check --dry-run
docker compose exec -T backend python manage.py migrate --check
docker compose exec -T backend python manage.py showmigrations --plan
git diff --check
```

Django reported no issues; no model changes or pending migrations were detected; every migration in the plan was applied. No new migration was needed or applied.

## 7. Evidence boundaries and remaining work

- All automated results above were executed in this phase. Existing tests were reused where sufficient and regression assertions were added for the confirmed bugs.
- No previous manual-browser verification record was found in the repository, so no historical browser result is claimed as evidence. A new visual/responsive browser audit was not performed; frontend interactions were checked in jsdom and HTTP integration was checked against the actual stack.
- Redis outage, retries, crashes, and concurrency were tested with the existing controlled automated cases. The live Redis service was not interrupted and its data was not flushed.
- The live Celery smoke used the simulated delivery adapter. External email, AWS deployment, production ingress/cookie configuration, and a clean-machine installation were not exercised.
- The full no-mistakes pipeline was not started because it requires committed changes and the user prohibited committing/pushing. Checks were run directly.
- Phase 8 final packaging and submission documentation remain intentionally untouched. In particular, a root project `README.md` is still absent; it is a documented Phase 8 deliverable.

## 8. Readiness

Phase 7's technical verification and hardening are complete. All four mandatory test categories pass, and no unresolved application defect was identified in the executed checks. The application is ready for review of the Phase 7 changes. Final submission readiness still requires the intentionally deferred Phase 8 handoff/documentation work and user approval.
