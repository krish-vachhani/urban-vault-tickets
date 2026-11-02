# Final requirements audit fixes and readiness verification

Verified on 2 November 2026 against the final audit fixes, subsequently committed as `3dbbc7a`. The user authorized the fixes and local documentation commits. No push, archive or submission was performed. The approved architecture and workflow boundaries remain unchanged.

## Findings resolved

| Finding | Result | Regression evidence |
|---|---|---|
| Initial POC routing History missing | Creation and fresh seed history snapshot `Unassigned → Name (Department Manager)` in routing Activity metadata. No POC Worker-assignment row is introduced. | Creation test asserts stored metadata and the serialized Activity response; seed test checks every initial routing event, including forwarded tickets. |
| Client field not searchable | The conditional MUI Client Autocomplete filters only authorized Client options and supports keyboard selection; dependent selections still reset. | Typed filtering excludes a nonmatching Client; ArrowDown/Enter selection loads the chosen Client's Office. Existing dependency/reset tests still pass. |
| Posting from filtered Activity hides new comment | Fetch the fresh All-feed count and open its last page after saving. A success message remains valid even if the feed refresh fails. | Tests post from All, Actions and Comments with 40 existing events; another test adds concurrent events; a failed feed request does not resubmit the saved comment. |
| Quick Issues failures silently hidden | Loading feedback and a retryable error are displayed; ordinary Issue selection stays available. | Pending-request test and failed-request/retry interaction test. |

Pending-submission checks exposed an additional race: rapid double-clicks could pass asynchronous form validation before the disabled button rendered. Immediate submission guards now protect ticket creation, comments and workflow actions. Action-panel switching is disabled while a ticket action is pending. Regression tests hold requests open and assert a single create/comment/assignment call; assignment also cannot be unmounted by toggling its panel. Failed creation can be retried normally.

The schema README's earlier minimal-routing-metadata note was corrected to agree with the original wireframe and the already-approved audit-history requirement. Existing development audit records were not rewritten or backfilled. New tickets and newly seeded submission/demo data contain the corrected snapshots; a database migration is unnecessary.

## Executed checks

| Command/check | Result |
|---|---|
| `docker compose exec -T backend python manage.py test --noinput` | **378 tests passed** against Django's separate PostgreSQL test database |
| `docker compose exec -T frontend npm run test -- --run` | **90 tests passed across 11 files** |
| Frontend `npm run typecheck` | Passed |
| Frontend `npm run lint` | Passed |
| Frontend `npm run build` | Passed; existing non-blocking bundle-size warning remains |
| Backend `python manage.py check` | No issues |
| Backend `python manage.py makemigrations --check --dry-run` | No changes detected |
| Backend `python manage.py migrate --check` | No pending migrations; no development migration applied |
| `git diff --check` | Passed |

Regression-first checks reproduced the routing, Client-search, Quick Issues error and filtered-comment failures before the corresponding fixes. Rapid duplicate ticket/comment submissions also failed before adding guards. A missing import in the new seed test was corrected before the final successful full suite.

A new notification transaction test explicitly verifies that a rolled-back transaction removes its outbox row, discards its commit callback and never invokes the publisher. Existing success/retry/outage tests continue to pass.

## Isolated setup rehearsal

A source snapshot was copied outside the repository into a temporary directory, without private PDFs, dependencies, local configuration or database contents. It used the documented Compose sequence with a separate project name, image tag, generated local credentials and loopback ports to avoid affecting the development stack:

1. Validate Compose configuration and build frontend/backend images.
2. Start PostgreSQL and Redis with new project volumes.
3. Run migrations against the empty database.
4. Run `seed_demo_data`: 14 accounts and 80 initial tickets.
5. Start all six services with `up -d --wait`.
6. Check frontend/API health and authenticate all four primary roles through the Vite proxy.
7. Verify at least two pages in both tabs for each role, initial POC History, Facility Manager action restrictions and the create → assign → assess → resolve journey.
8. Confirm one Worker responds and all six notifications created during the rehearsal reach `SENT`; every seeded/new routing event has History metadata.

The HTTP harness initially chose an Office outside the primary Facility Manager's Property and correctly received 404. It was corrected to select from that manager's authorized Office endpoint; the subsequent complete smoke run passed. The initial failed harness run is not counted as a passing journey.

Docker reused existing dependency-layer caches, but source images were built and database volumes were new. This proves an isolated fresh-database startup, not an entirely uncached clean-machine build. Temporary verification resources are separate from the existing development project and are removed after checks.

## Targeted native Chrome check

After the permissions retry, native Chrome control worked. The dedicated browser connection still reported `The browser access host is unavailable`; no additional operating-system permission prompt appeared. The following checks used native Chrome on the running development app without creating tickets, posting comments or submitting workflow actions:

- Signed in as the Client and checked the list and ticket detail.
- Typed `acm` in the Client chooser, confirmed only the matching authorized Client remained, and selected it with the keyboard. Selecting a single-floor Office hid the Floor chooser.
- Selected a Quick Issue and checked the mutually exclusive chip states.
- Set the responsive viewport to exactly 375px. Checked the creation form, wrapped Quick Issues, ticket detail, resolution confirmation and Activity while scrolling; the comment composer remained visible and the inspected controls fit the viewport.

The browser pass stopped at the user's request to limit token use. It did not repeat the earlier four-role walkthrough or complete a desktop sticky-scroll or comprehensive accessibility audit.

## Evidence boundaries and verdict

- The user's earlier browser checks across Client, Facility Manager, Department POC and Worker, plus the 375px mobile layout, are acknowledged as user-confirmed evidence. They are separate from Phase 7's recorded HTTP/component checks.
- Native Chrome subsequently provided the targeted visual and keyboard evidence above. The other roles retain the earlier user-confirmed browser evidence and the executed automated/HTTP checks; comprehensive keyboard/focus/contrast/screen-reader coverage is not claimed.
- No live Redis outage, external email provider or AWS deployment was introduced. Controlled retry/recovery tests and prior actual Beat recovery remain valid evidence.
- The full no-mistakes pipeline was not started during verification: it requires committed feature-branch history and includes delivery operations, which were outside the scope of that pass. Checks above were executed directly; local commits were authorized afterward.
- The user selected GitHub repository-link submission; no ZIP is required. Pushing remains pending confirmation of the repository URL and visibility. Recipient access must be verified before sharing the link with HR.

**READY FOR SUBMISSION** for the assignment's implemented scope, with the verification boundaries above. The four reported completeness defects and the confirmed duplicate-submit race are resolved; no known application blocker remains. GitHub publication and recipient access remain delivery steps.
