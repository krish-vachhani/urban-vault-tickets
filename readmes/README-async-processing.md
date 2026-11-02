# Asynchronous Notifications — Redis, Celery, and Transactional Outbox

**Status:** FINALIZED  
**Scope:** Asynchronous ticket notifications, durable notification intent, task dispatch, retry/failure handling, idempotency, and recovery.

This document records the agreed asynchronous-processing architecture for the Urban Vault assignment. Implement this design without introducing a different broker, event-streaming platform, or notification product.

## 1. Purpose and assignment requirement

The assignment requires Redis and Celery to support at least one meaningful asynchronous operation, with retry/failure handling and an explanation of duplicate-execution handling. This project uses ticket notifications because they naturally follow important ticket events.

The implementation uses simulated notification delivery. A real email/SMS provider and a notification inbox UI are not required.

## 2. Finalized architecture

| Component | Responsibility |
|---|---|
| Django / DRF | Performs the business operation and creates durable notification intent |
| PostgreSQL | Stores `NotificationOutbox` records and their delivery state; it is the source of truth |
| Redis | Celery message broker only |
| Celery worker | Executes notification delivery asynchronously |
| Simulated delivery adapter | Represents delivery for this assignment, using structured logging and an observable SENT state |

Do not add Kafka, RabbitMQ, a separate Celery result backend, or a notification inbox/read-state subsystem.

## 3. Notification events and recipients

Create notifications for these business events:

| Business event | Recipient(s) | Notes |
|---|---|---|
| Ticket created/routed | Concerned Facility Manager and current Department POC | Deduplicate if a recipient is selected through more than one route; do not notify the actor; link to the `TICKET_ROUTED` Activity |
| Worker assigned | Newly assigned Worker | Send only to the Worker selected by the current Department POC |
| Department changed | Designated POC of the destination/current Department | Do not notify the forwarding actor |
| Worker assessment submitted | Current Department POC | Notify the POC after the assessment transaction commits |

Do not add a Client-resolved notification in this assignment's selected notification scope. It may be added later only through a documented decision.

Notification content should be minimal and safe: event type, Ticket ID/display reference, recipient, and the information needed to construct the simulated message. Do not put credentials, tokens, or unnecessary sensitive data in the payload.

## 4. Why use the Transactional Outbox Pattern?

Directly calling `.delay()` after a database commit leaves a failure gap: PostgreSQL may commit the assignment while Redis is unavailable, so the business action succeeds but the notification task is never published.

Instead, create a `NotificationOutbox` row in the same PostgreSQL transaction as the business action. The row records the durable intent to notify a recipient. After commit, publish the outbox row ID to Celery.

This means:

- If the business transaction rolls back, no outbox row exists and no notification should be sent.
- If the business transaction commits but Redis publishing fails, the outbox row remains available for recovery.
- Redis transports a reference to the durable job; it is not the source of truth for whether the notification is required or delivered.

## 5. `NotificationOutbox` table

This is the eighteenth logical database table (`README-database-schema.md` §2.18).

| Field | Type / relationship | Rules |
|---|---|---|
| `id` | BigAutoField | Primary key |
| `ticket_id` | FK → Ticket | Required |
| `source_activity_id` | FK → TicketActivity | Required; the action that caused this notification |
| `recipient_id` | FK → User | Required |
| `event_type` | Choice/string | Required notification event |
| `idempotency_key` | VARCHAR(255) | Required, unique |
| `payload` | JSONField / PostgreSQL JSONB | Required, default empty object; minimal template data |
| `status` | Choice field | `PENDING`, `PROCESSING`, `SENT`, `FAILED` |
| `attempt_count` | Positive integer | Default 0; number of delivery attempts begun. **Authoritative** attempt limit: at most 4 in total |
| `processing_started_at` | Nullable timestamp | Used to detect work abandoned by a lost worker |
| `next_attempt_at` | Timestamp | Required; when the row is next due. Set to the creation time initially and to a backoff time after a transient failure |
| `last_dispatched_at` | Nullable timestamp | Last successful broker publish for the current attempt; cleared when a retry is scheduled. Prevents republishing the same due row on every Beat tick |
| `last_error` | Nullable text | Sanitized error summary; do not store secrets or tokens |
| `created_at` | Timestamp | Required |
| `updated_at` | Timestamp | Required |
| `sent_at` | Nullable timestamp | Set after successful simulated delivery |

Constraints and indexes:

- Unique `idempotency_key`.
- `0 <= attempt_count <= 4`.
- Index `(status, next_attempt_at)` to find PENDING rows whose next attempt is due.
- Index `(ticket_id, created_at)` for operational inspection.
- Use protective deletion behaviour for Ticket, source Activity, and recipient records referenced by the outbox.

Use a stable idempotency key derived from the source Activity and recipient, for example `activity:{activity_id}:recipient:{recipient_id}`. One source event must not create duplicate outbox records for the same recipient.

## 6. Transaction and dispatch lifecycle

For each notification-triggering business operation:

1. Start `transaction.atomic()` and lock the Ticket row where the operation can race.
2. Perform and validate the Ticket/Assignment/Assessment changes.
3. Create the corresponding `TicketActivity` record.
4. Create one `NotificationOutbox` row per distinct recipient, using the source Activity ID and recipient ID in its idempotency key.
5. Commit the transaction.
6. Register an `on_commit` callback that safely publishes the outbox row ID to Celery. After a successful broker publish, update `last_dispatched_at`; if publish fails, leave the row pending and log the failure. Register it with `transaction.on_commit(callback, robust=True)` so a publishing error is logged and never turns the committed action into an API error.

The `on_commit` publisher must catch/log broker publication errors rather than turning an already-committed business action into an apparent API failure. When Redis is unavailable, leave the outbox record `PENDING`.

Only enqueue after commit. Never publish a notification for a Ticket action that rolled back.

## 7. Celery task behaviour

Use a task that accepts only the `NotificationOutbox.id`, for example `deliver_notification(outbox_id)`.

**One retry mechanism (Phase 0 audit, R3).** The task makes **one** delivery attempt per execution and never calls Celery's `self.retry()`. Retries are scheduled durably in PostgreSQL through `next_attempt_at` and published by the single dispatcher (§9). The `attempt_count` column, not Celery's in-memory retry counter, enforces the attempt limit. This avoids two uncoordinated mechanisms (Celery retries and Beat re-dispatch) racing each other and resetting the retry budget.

Each execution uses a short claim transaction followed by delivery and finalization:

1. In a short `transaction.atomic()` block, load the outbox row with `select_for_update()`.
2. Return without delivery if its status is `SENT` or `FAILED` (both terminal).
3. If its status is `PROCESSING` and `processing_started_at` is still fresh, return without starting a concurrent delivery.
4. If `next_attempt_at` is still in the future, return; this is a duplicate or early message, and the dispatcher will publish the row when it is due.
5. Otherwise increment `attempt_count`, set `PROCESSING` and `processing_started_at`, then commit the claim.
6. Invoke the simulated delivery adapter outside the claim transaction.
7. On success, set `SENT` and `sent_at`, clear `last_error`, and log a structured success event.
8. On a transient failure with fewer than 4 attempts used: store a sanitized `last_error`, set status back to `PENDING`, set `next_attempt_at` to now plus the backoff delay, and clear `last_dispatched_at` so the dispatcher publishes the row once it is due.
9. On a transient failure on the 4th attempt, or on any permanent failure: set `FAILED` and keep `last_error` for inspection.

The claim transaction must be committed before delivery so concurrent task copies can see the fresh `PROCESSING` state. A worker crash after claiming can leave a stale `PROCESSING` row; the dispatcher resets stale claims after the five-minute threshold (§9). Keep the task's hard time limit (60 seconds) well below that threshold so a valid delivery is never mistaken for abandoned work. A crashed attempt still counts as an attempt.

### Retry policy

- At most **4 delivery attempts in total** (the initial attempt plus up to 3 retries), counted by `attempt_count`.
- Exponential backoff with jitter before the next attempt: 30 s, then 60 s, then 120 s, each plus up to 20% random jitter, stored in `next_attempt_at`.
- Retry transient delivery errors only. Permanent validation/configuration errors go straight to `FAILED`.
- Keep the final `FAILED` row in PostgreSQL; do not silently delete it.
- Name these values as constants in one place (maximum attempts, backoff steps, jitter ratio, stale threshold, re-dispatch interval). Only the re-dispatch interval may be overridden by the `NOTIFICATION_REDISPATCH_INTERVAL_SECONDS` environment variable (default 300); the others are fixed constants.

## 8. Duplicate execution and delivery guarantees

Celery task execution is treated as **at least once**, not exactly once.

Idempotency is enforced at the application/database boundary:

- Unique outbox idempotency key prevents duplicate jobs for the same source Activity and recipient.
- The task locks the outbox row before checking/updating its state.
- A repeated task for a `SENT` or terminal `FAILED` row is a no-op.
- A task that arrives before its row's `next_attempt_at` is a no-op.
- A recent `PROCESSING` row must not be processed concurrently.

For this assignment's simulated delivery, the durable `SENT` state is the observable delivery result. The simulated adapter should not perform an irreversible external side effect. Do not claim that Celery/Redis alone guarantees exactly-once execution.

If the simulated adapter is later replaced by a real external email provider, a process can crash after the provider accepts a message but before PostgreSQL records `SENT`. Use that provider's idempotency facility (when available) or explicitly accept at-least-once delivery; the database transaction cannot make an external email send atomic with PostgreSQL.

## 9. Broker outage and worker-crash recovery

The durable outbox row is what makes recovery possible. The approved architecture uses both a periodic Celery Beat dispatcher and an operator-invoked management command.

Celery Beat schedules the dispatcher task every **60 seconds**, so a retry is published within about one minute of becoming due (in addition to its 30/60/120-second backoff). Each run:

1. Resets stale `PROCESSING` rows (the **five-minute processing lease** has expired: `processing_started_at` older than 5 minutes) to `PENDING`, due immediately, with `last_dispatched_at` cleared. A stale row that has already used all 4 attempts becomes `FAILED` instead.
2. Selects `PENDING` rows with `next_attempt_at <= now` whose `last_dispatched_at` is null (not yet published for this attempt) or older than the **5-minute re-dispatch interval** (the message was probably lost, for example in a Redis restart).
3. Locks them with `select_for_update(skip_locked=True)`, so concurrent dispatcher runs or the manual command never claim the same rows, publishes each ID, and sets `last_dispatched_at` after each successful publish.

A duplicate publish after a process crash remains safe because the delivery task is idempotent.

Provide a Django management command for manual recovery/inspection as well:

```bash
python manage.py dispatch_pending_notifications
```

The command should:

- enqueue due `PENDING` outbox rows that have not been published for their current attempt;
- identify `PROCESSING` rows whose `processing_started_at` is older than the five-minute processing lease, reset them to `PENDING`, and enqueue them again;
- skip `SENT` and terminal `FAILED` rows;
- use row locking/atomic updates so multiple command invocations do not claim the same row concurrently.

The management command must invoke the same dispatch/recovery logic as the periodic task, so manual and scheduled recovery cannot drift. The processing lease is five minutes (finalized).

If Redis restarts and queued messages are lost, pending/stale outbox rows can be republished by Celery Beat or the manual recovery command.

## 10. Redis and Celery configuration

- Redis is the Celery broker, e.g. `redis://redis:6379/0` inside Docker Compose.
- Do not configure a Celery result backend for this feature; PostgreSQL holds delivery state.
- Set `task_ignore_result = True`.
- Use late acknowledgement / worker-loss behaviour only where it is correctly paired with the outbox idempotency checks; do not rely on broker delivery settings as the only duplicate protection.
- Configure a 60-second hard time limit and structured logging for the delivery task.
- Docker Compose must include `frontend`, `backend`, `postgres`, `redis`, `celery-worker`, and `celery-beat` services. Run exactly one Beat instance.

Use environment variables for Redis/broker configuration. Do not commit secrets.

## 11. Testing requirements

At minimum, automate these meaningful cases:

1. **Successful delivery:** a PENDING outbox row is processed and becomes SENT.
2. **Retry/failure:** a transient failure returns the row to `PENDING` with `attempt_count` incremented, a future `next_attempt_at`, and a sanitized `last_error`; a failure on the 4th attempt makes the row `FAILED`. Also test a transient failure followed by success.
3. **Duplicate execution:** executing the same task again after SENT does not perform a second simulated delivery.
4. **Transactional creation:** if the business transaction rolls back, its outbox row does not exist and no task is published.
5. **Broker publication failure:** the business operation remains committed, the outbox remains PENDING, and the recovery command can enqueue it later.
6. **Dispatcher:** publishes only due, unpublished `PENDING` rows; recovers stale `PROCESSING` rows; does not republish a row within the re-dispatch interval.

Use Celery eager mode or controlled task invocation in automated tests, and mock the simulated delivery adapter to deterministically trigger success and failure. Do not make real network calls.

## 12. Logging and observability

Log useful identifiers and outcomes:

- outbox ID;
- Ticket ID;
- event type;
- recipient user ID;
- attempt count;
- success/failure outcome;
- sanitized error class/message.

Do not log access/refresh tokens, passwords, or unnecessary personal data.

## 13. Out of scope

- Actual email/SMS provider integration;
- notification inbox UI, read/unread state, or user notification preferences;
- Kafka, RabbitMQ, or a second broker;
- Celery result backend;
- multiple Celery Beat schedulers;
- exactly-once guarantees for external delivery;
- notifications for Ticket resolution unless a later documented decision adds them.

## 14. Implementation acceptance checklist

- [ ] Add `NotificationOutbox` as the eighteenth logical table and create a migration.
- [ ] Create outbox records in the same transaction as notification-triggering business events.
- [ ] Publish only after commit; safely handle Redis publish failure.
- [ ] Implement `deliver_notification(outbox_id)` with row locking and idempotency checks.
- [ ] Implement durable retries (`next_attempt_at`, at most 4 attempts counted by `attempt_count`, exponential backoff with jitter, no Celery `self.retry()`) and a terminal FAILED state.
- [ ] Implement `dispatch_pending_notifications` recovery command for PENDING and stale PROCESSING rows.
- [ ] Add simulated delivery logging without external network calls.
- [ ] Add Redis, Celery Worker, and one Celery Beat service to Docker Compose.
- [ ] Configure the Beat schedule to run the outbox dispatcher every 60 seconds; do not run more than one scheduler.
- [ ] Add tests for success, retry/final failure, duplicate execution, rollback, broker outage recovery, and dispatcher selection.
- [ ] Document the outbox flow, retry semantics, and at-least-once guarantee in the root README.
