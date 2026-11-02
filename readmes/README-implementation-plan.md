# Implementation Plan — Urban Vault Take-Home Assignment

**Status:** FINALIZED IMPLEMENTATION SEQUENCE  
**Implementation agent:** Claude Code  
**Scope authority:** The supplied assignment brief and wireframe  
**Architecture decisions:** The finalized feature READMEs in this folder

This document defines how to implement the complete assignment scope in dependency order. It does not allocate time, redefine requirements, or authorize scope cuts. The assignment brief and wireframe define what must be delivered; the feature READMEs record the agreed technical design and clarify behaviour where the source material leaves room for interpretation.

## 1. Source-of-truth hierarchy

Use the following hierarchy when implementing:

1. **Assignment brief:** authoritative for written requirements, technical requirements, evaluation criteria, constraints, and deliverables.
2. **Wireframe:** authoritative for the depicted screens, role-specific visibility, forms, CTAs, ticket handling flow, and activity/history presentation.
3. **Finalized feature READMEs:** authoritative for the chosen implementation design where the brief or wireframe does not prescribe a technical detail or where an ambiguity has been explicitly discussed and resolved.
4. **Code:** must conform to the sources above; existing code does not override a requirement or finalized decision merely because it was implemented first.

If a feature README appears to conflict with an explicit assignment requirement or depicted wireframe behaviour, do not silently follow the README or silently reinterpret the assignment. Report the exact conflict, identify the affected requirement, and resolve it before implementing that part.

Some finalized decisions are deliberate interpretations of ambiguous source material. The relevant README must label those as assumptions. Examples include the listing's Concerned Department filter using the ticket's current department, and the three-way separation of workflow stage, closure status, and assessment outcome.

## 2. Implementation principles

1. **Read before coding.** Read this plan, `README.md`, and the feature READMEs relevant to the phase.
2. **Implement the full in-scope product.** Do not omit an explicit requirement or move it to an optional tier because it appears time-consuming.
3. **Do not expand scope.** Do not add generalized facility-management capabilities that are not in the assignment or finalized decisions.
4. **Do not redesign finalized decisions.** Do not change roles, relationships, states, endpoint contracts, libraries, or infrastructure without discussing the impact first.
5. **Report contradictions.** If requirements or READMEs conflict, cite the relevant files/sections and pause the affected work instead of guessing.
6. **Test as you go.** Add and run relevant tests alongside each feature. Do not defer all testing until the end.
7. **Use real integration boundaries.** The React application must call the Django APIs. Hardcoded ticket data is acceptable only in isolated frontend tests, not as a substitute for backend functionality.
8. **Keep business logic out of views.** Views handle HTTP; serializers validate and shape data; permission classes and scoped querysets enforce access; selectors handle read queries; services perform business operations and transactions.
9. **Keep the repository reproducible.** Maintain migrations, deterministic seed data, Docker Compose, `.env.example`, setup commands, and test commands as implementation changes.
10. **Be transparent about completion.** Do not mark a requirement complete until its acceptance check has been run. Record actual work/time spent accurately in the final root README as requested by the assignment; do not invent a time figure.

## 3. Assignment-scope traceability

Every item below is part of the implementation scope unless the source explicitly marks it optional or not required.

| Source requirement | Implementation evidence | Completion check |
|---|---|---|
| Implement the screens and primary interactions in the wireframe | React pages and components for ticket creation, Open/Closed listings, ticket details, role-specific CTAs, Activity, History, comments, assignment, forwarding, assessment, and resolution | Walk through each depicted role and stage using seeded accounts |
| Seeded accounts for Client, Facility Manager, Department POC, and Worker; simple account switching using standard authentication | Reproducible seed command, demo login convenience, normal JWT login/logout/refresh | Authenticate as each role through the standard auth flow and switch accounts |
| Backend-enforced ticket visibility and action permissions | Role-aware scoped querysets, permission classes, service-level checks | Negative API tests for cross-Client, cross-Property, cross-Department, and unassigned-Worker access/actions |
| Paginated listing of multiple records | Server-side pagination and enough seed records to show more than one page | Demonstrate page navigation and correct counts from the API |
| Filters for Client Name, Concerned Department, Concerned Facility Manager, and Ticket Status for all users | Server-side query parameter filters applied after role-based visibility scoping | Exercise each filter as each role where the user has authorized records |
| Search by Ticket Issue text for all users | Server-side Issue-name search across TicketIssue relationships | Search returns matching tickets without duplicate rows |
| Sort by Created Time, older first/newest first | Server-side allow-listed ordering with deterministic tie-breaker | Verify both directions and stable pagination |
| Complete ticket creation and handling flow represented in the wireframe | Ticket creation, Worker assignment, Department forwarding, Worker assessment, Mark Resolved, and role-specific screens/actions | Complete the depicted journey; stop the handling flow at Pending Department POC Review except for the agreed Mark Resolved action |
| Create, view, and update operations with client-side and server-side validation | DRF serializers/services and React forms with visible validation feedback | Valid requests succeed; invalid requests return consistent errors and do not partially write data |
| Enforce valid business-state transitions | Explicit action endpoints and service-level transition checks | Invalid transitions are rejected with a clear conflict response |
| Loading, empty, success, validation, permission, and unexpected API-error states | Reusable frontend states and consistent API error handling | Verify each state on relevant pages/forms |
| Desktop and mobile widths; semantic HTML and basic accessibility | Responsive MUI/Tailwind layouts, semantic elements, labels, keyboard-accessible controls and visible focus states | Inspect desktop/mobile layouts and perform basic keyboard/accessibility checks |
| Python, Django, DRF, PostgreSQL, migrations, reproducible sample-data loading | Backend app structure, migrations, management command for deterministic seed data | Clean database can migrate and seed from documented commands |
| Relational model, meaningful relationships, database constraints, at least one justified index | Finalized schema, FK/unique/check/partial constraints, documented indexes | Inspect migrations and demonstrate constraints/query optimization |
| REST semantics, HTTP status codes, serializer validation, consistent error response | Versioned REST endpoints, serializers, central exception/error format | API tests assert success and representative error status/body contracts |
| Authentication and meaningful authorization | SimpleJWT and backend role/relationship authorization | Authentication and authorization tests pass |
| Redis and Celery for one meaningful asynchronous operation; retry/failure and duplicate handling | Transactional notification outbox, Redis broker, Celery Worker, single Beat scheduler, retries, idempotency, recovery | Test success, retry/exhaustion, duplicate no-op and outbox recovery |
| At least two Engineering Depth options | Implement audit/history, transaction boundaries, and intentional query optimization; useful critical-action/task logging may also be included | README explains the selected techniques and tests/evidence demonstrate them |
| React and Material UI, reusable components and feature-level structure | React + TypeScript + Vite, MUI core controls, feature-based folders; Tailwind is supplementary styling | Frontend builds and components are reused appropriately |
| Frontend pagination, filters, sorting, and search match backend | URL search parameters plus TanStack Query using backend query parameters | UI requests match URL state and backend results |
| Form feedback and prevention of duplicate submissions | React Hook Form/Zod, pending mutation states and disabled submit actions | Validation errors display and duplicate clicks do not create duplicate requests |
| Predictable state and avoid unnecessary fetching/rerendering | TanStack Query for server state, Context for auth only, URL/local/form state separated | Query keys, cache invalidation and component state follow the frontend README |
| Docker Compose for web app, PostgreSQL, Redis, Celery Worker | Compose services for frontend, backend, PostgreSQL, Redis, Celery Worker, and the approved single Beat scheduler | Clean Compose startup and service health checks succeed |
| Environment configuration and safe example file | `.env.example` with placeholders only; secrets kept out of Git | Inspect repository and verify no credentials/secrets are committed |
| AWS deployment note covering services, secrets, static/media, workers, scaling, monitoring, recovery | Detailed deployment README and concise root README summary | All requested deployment topics are documented; no live deployment is claimed |
| At least four meaningful automated tests in the required categories | API/business rule, auth/authorization, Celery failure/retry, frontend interaction | Four required categories are explicitly covered and tests pass |
| Source code, migrations, Docker configuration and sample-data setup | Repository implementation and reproducible commands | A clean checkout can be set up using documented instructions |
| Root README with prerequisites, setup, tests, APIs, model, decisions, assumptions, limitations, actual time, optimization, Celery/Redis, improvements | Root `README.md` plus links to feature READMEs | Review root README against the full deliverables list |
| AI-assisted development disclosure | Root README states tools used and how they supported the work | Disclosure is accurate and complete |
| Optional screenshots or short demonstration | Capture only after the product flow works | Optional; do not substitute for required functionality |

## 4. Explicit assignment boundaries

Do not implement the following because the assignment excludes them or does not require them:

- Registration, password reset, or user-management screens.
- A live AWS deployment. The AWS deployment approach is documentation only.
- A full production notification provider integration. The agreed notification operation is simulated.
- A department-review workflow after the Worker submits an assessment. The depicted handling flow ends at Pending Department POC Review.
- Microservices, Kafka, RabbitMQ, event sourcing, Redux, or a repository framework.
- Worker scheduling, availability, workload optimization, property-worker mapping, or automatic assignment.
- Multiple departments within one ticket.
- Multiple simultaneously active Workers on one ticket.
- A general-purpose multi-tenant platform or other facility-management modules not shown or required.

Screenshots or a short screen recording are optional deliverables; all explicitly required product, technical, testing, and documentation requirements remain in scope.

## 5. Dependency-ordered implementation sequence

Implement in the following order. This is a dependency sequence, not a time allocation or a reduction in scope.

1. **Preflight and scope audit:** inspect the repository, read all specifications, and map requirements to implementation work.
2. **Project foundation:** configure backend/frontend projects, custom User model, environment settings, Docker Compose, and health checks.
3. **Domain and data layer:** implement all models, migrations, constraints, indexes, admin inspection, and reproducible seed data.
4. **Authentication and reference data:** implement JWT lifecycle, account switching, `/me`, Client/Office/Floor/Department/Issue APIs, Quick Issues, and eligible Workers.
5. **Ticket backend:** implement ticket creation, paginated listing, search, all filters, sorting, detail, authorization, assignment, forwarding, assessments, Mark Resolved, Activity, History, and comments.
6. **Asynchronous notifications:** implement the transactional outbox, Redis broker, Celery tasks, retries, idempotency, recovery dispatcher, and single-instance Beat scheduler.
7. **Frontend:** implement all role-aware screens and forms; integrate every required API; implement URL state, query/cache behaviour, error/loading/empty/success states, responsiveness, and accessibility.
8. **Automated testing and hardening:** complete the required test categories and meaningful coverage of core business/security/reliability behaviours; resolve defects.
9. **Integration and delivery:** run the full Docker environment and smoke flow, verify seed data and pagination, complete root README and AWS note, inspect repository hygiene, and prepare submission.

Do not substitute frontend fixtures for incomplete backend APIs. Component-level mocks are appropriate only in frontend tests.

## 6. Phase-by-phase Claude Code prompts

Run one prompt at a time. Read the referenced specifications first, inspect changes, run the stated checks, and confirm acceptance before proceeding. If a phase reveals an ambiguity, stop and report it instead of silently making a product decision.

### Phase 0 — Preflight and scope audit

**Read:** `README.md`, this plan, the assignment brief/wireframe where available, and every feature README in `readmes/`.

**Prompt:**

> Before changing code, inspect the repository and read every Markdown specification in `readmes/`. Compare the specifications against the assignment brief and wireframe. Produce a scope traceability checklist covering every required product, technical, testing, infrastructure, and delivery requirement. Identify contradictions, missing prerequisites, and any requirement that is not covered by an implementation specification. Do not write application code yet. Do not create a time budget or recommend omitting any in-scope requirement. Do not redesign finalized decisions. Cite exact files/sections for issues. If there are no blocking conflicts, confirm readiness for Phase 1.

**Acceptance:** All source requirements are mapped; conflicts and open details are reported; no unrequested code changes are made.

**Status:** Completed on 2026-11-02. The resulting decisions are recorded in `README.md` → Decision log and applied to the affected READMEs.

### Phase 1 — Scaffold, configuration, Docker Compose, custom User

**Read:**
- `README-backend-architecture.md`
- `README-authentication.md`
- `README-frontend-architecture.md`
- `README-infrastructure-deployment.md`

**Prompt:**

> Set up the Django backend and React + TypeScript + Vite frontend using the finalized structures and technology choices. Create the four Django apps (`accounts`, `organizations`, `tickets`, `notifications`) and configure the custom Django User model before the first migration. Implement environment-based settings and a safe `.env.example`. Create Docker Compose with frontend, backend, postgres, redis, celery-worker, and a single celery-beat service. Add PostgreSQL and Redis health checks, a persistent PostgreSQL volume, service dependencies, and the Vite `/api` proxy required for same-origin browser requests. Add the initial React providers/bootstrap and Tailwind v4 + MUI CSS-layer integration. Do not implement business APIs yet. Verify the project builds and services start using documented commands.

**Acceptance:** Custom User is configured before initial migrations; all required local services build/start; no secrets are committed; the approved frontend stack and `/api` proxy are configured.

### Phase 2 — Models, migrations, constraints, admin, seed data

**Read:**
- `README-domain-model.md`
- `README-database-schema.md`
- `README-ticket-lifecycle.md`
- `README-audit-and-communication.md`
- `README-backend-architecture.md`
- `README-seed-data.md`

**Prompt:**

> Implement the 18 logical database tables and relationships exactly as specified: User, Client, UserClient, Property, ClientOffice, Floor, ClientOfficeFloor, Department, DepartmentWorker, Issue, Ticket, TicketIssue, TicketFloor, TicketAssignment, TicketAssessment, TicketActivity, TicketComment, and NotificationOutbox. Preserve the custom User design: no `User.department_id`; Department has one designated POC; DepartmentWorker maps Workers to one Department with a unique worker constraint. Implement immutable origin Department and mutable current Department separately, workflow/status choices and valid combinations, at most one active Worker assignment, one assessment per ticket, required indexes, and deletion protections. Add practical Django admin registrations for inspecting seeded data. Create a deterministic, idempotent management command, following `README-seed-data.md`, to seed all four roles, multiple Clients/Offices/Properties/Floors/Departments/Issues, appropriate mappings, and enough tickets to demonstrate every listing behaviour including more than one page. Use safe local-only demo credentials and document them. Add model/constraint tests.

**Acceptance:** Migrations apply on PostgreSQL; constraints match the schema README; seed command can be run repeatedly without duplicate data; seeded records demonstrate the relationships and paginated listings.

### Phase 3 — Authentication and reference-data APIs

**Read:**
- `README-authentication.md`
- `README-reference-data-apis.md`
- `README-authorization.md`
- `README-backend-architecture.md`
- `README-api-conventions.md`

**Prompt:**

> Implement the SimpleJWT authentication flow exactly as documented: access token in React memory, refresh token in HttpOnly cookie, refresh rotation/blacklisting, explicitly enforced CSRF protection for login, refresh, and logout (with tests for missing/invalid tokens), current-user endpoint, normal logout, and seeded-account convenience that still uses standard authentication. Implement every reference-data endpoint: authenticated user's mapped Clients, authorized Client Offices, mapped Floors, Departments, searchable Issues, Client Quick Issues (top four by frequency with recency tie-breaker), and ticket-scoped eligible Workers. Enforce role and relationship scope on the backend. Use consistent error responses and serializers. Add authentication/reference-data permission tests.

**Acceptance:** All four seeded roles can authenticate and switch accounts through normal login/logout; refresh works securely; users cannot enumerate unrelated Clients, Offices, Floors, or Workers; Quick Issues use the agreed ranking.

### Phase 4 — Ticket APIs and business operations

**Read:**
- `README-ticket-lifecycle.md`
- `README-authorization.md`
- `README-database-schema.md`
- `README-ticket-creation-api.md`
- `README-ticket-listing-api.md`
- `README-ticket-actions-api.md`
- `README-audit-and-communication.md`
- `README-backend-architecture.md`
- `README-api-conventions.md`

**Prompt:**

> Implement the complete ticket API surface using DRF views/viewsets, serializers, permission classes, scoped selectors, and service functions. Implement create, detail, server-side paginated listing, all four filters, the filter-options endpoint, `action_required`, Issue-text search, created-time ordering, eligible Workers, assignment, Department forwarding, Worker assessment, Mark Resolved, Activity, History, and comments. Enforce role-specific Client/Office/Floor/Issue/Description validation; Office scope for Facility Managers; same-Department Issues; selected Floors belonging to the Client Office; and all finalized authorization rules, including creator visibility and Mark Resolved for mapped Client users or the Ticket's creator. Build visibility with `Exists(...)` subqueries and lock Tickets with a separate primary-key query. Use explicit action endpoints rather than a generic writable Ticket PATCH. Enforce the finalized three workflow stages, closure statuses, assessment outcomes, valid transitions, 404 for inaccessible tickets, 403 for disallowed actions on visible tickets, 409 for invalid transitions, and the consistent error envelope. Use transactions and row locking for state-changing operations; preserve assignment and audit history; create outbox intent in the same transaction for notification-triggering events. Optimize read querysets using justified `select_related`, `prefetch_related`, and indexes. Add backend tests while implementing each operation.

**Acceptance:** The complete backend workflow is API-driven; permissions and state transitions are enforced server-side; filters/search/sort/pagination run on the database; invalid requests do not partially write; response shapes match the API READMEs.

### Phase 5 — Notification Outbox and Celery

**Read:**
- `README-async-processing.md`
- `README-database-schema.md`
- `README-infrastructure-deployment.md`
- `README-testing-strategy.md`

**Prompt:**

> Implement the PostgreSQL NotificationOutbox, Redis Celery broker, simulated notification delivery, retry policy, idempotency and recovery exactly as documented. Notification intent must be inserted in the same database transaction as the triggering ticket operation. Dispatch after commit, and run exactly one Celery Beat scheduler that invokes the pending/stale outbox dispatcher on the documented schedule. Ensure the dispatcher can recover jobs when Redis was unavailable and stale PROCESSING records can be recovered safely if a Worker dies. Use unique idempotency keys, durable retries scheduled through `next_attempt_at` with at most four total attempts counted by `attempt_count` (no Celery `self.retry()`), exponential backoff with jitter, and a terminal FAILED state with retained error information. Already-sent jobs must be harmless no-ops on redelivery. Add tests for successful delivery, retry/exhaustion, duplicate execution, transaction rollback/on-commit behaviour, and stale recovery. Do not integrate a real email/SMS provider.

**Acceptance:** PostgreSQL retains notification intent if Redis is unavailable; Beat runs as a single instance; the Worker executes simulated notifications; retries, failures, and recovery are persisted; duplicate delivery attempts do not create duplicate successful notification records.

### Phase 6 — Frontend implementation and API integration

**Read:**
- `README-frontend-architecture.md`
- `README-authentication.md`
- `README-reference-data-apis.md`
- `README-ticket-creation-api.md`
- `README-ticket-listing-api.md`
- `README-ticket-actions-api.md`
- `README-ticket-lifecycle.md`
- `README-authorization.md`

**Prompt:**

> Implement the complete React application according to the finalized feature-based structure. Use React Router Declarative mode and URL search parameters for ticket tab, page, search, filters, and ordering. Use TanStack Query v5 for every server-state query/mutation; Context only for authentication; React Hook Form + Zod for forms; Axios with centralized Bearer-token injection, refresh-cookie handling, CSRF support, and single-flight refresh. Store the access token in memory only; never put access/refresh tokens in localStorage or sessionStorage. Clear query cache and user-specific state on logout/account switch. Build login with development-only seeded-account convenience that still authenticates normally. Implement all wireframe screens and role-specific interactions: conditional Client/Office/Floor fields, Quick Issues, same-Department multi-select Issues, Open/Closed listings, search, filters, sorting, pagination, detail view, Activity filters, History, sticky comments, Department POC assignment/forwarding panels, Worker assessment options, and Client Mark Resolved. Use backend-provided actions only as UI guidance; every action calls its explicit API and the backend rechecks permissions. Use MUI for core controls and Tailwind v4 for layout/spacing with the approved CSS-layer integration. Implement loading, empty, success, validation, permission, conflict, and unexpected API-error states. Support desktop/mobile widths, semantic HTML, and basic accessibility. Do not hardcode business records or permissions in the UI. Add the agreed TicketForm and TicketActions interaction tests.

**Acceptance:** All four roles can complete their permitted journey; every required screen/action is integrated with real APIs; URL-backed list state works; forms and server validation agree; refresh handles concurrent 401s; cache is cleared on account switch; desktop/mobile and accessibility requirements are addressed; frontend tests and production build pass.

### Phase 7 — Automated test completion and hardening

**Read:** `README-testing-strategy.md` and the feature READMEs relevant to any failing behaviour.

**Prompt:**

> Audit the implementation against every test requirement in the assignment brief and `README-testing-strategy.md`. Ensure the four mandatory categories are explicitly covered: (1) successful API flow/business rule/invalid transition, (2) authentication or authorization, (3) Celery task failure/retry, and (4) important frontend interaction. Complete meaningful tests for ticket creation, role-specific visibility, action permissions, listing filters/search/pagination/sorting, valid/invalid transitions, one-active-assignment constraint, assessment, resolution, outbox idempotency/retry/rollback/recovery, TicketForm, and role-specific CTAs. Use PostgreSQL for backend integration tests. Use Django test runner + DRF APIClient/APITestCase and Vitest + React Testing Library + user-event + jsdom. Avoid flaky sleeps and external services. Fix defects rather than weakening assertions. Run the complete backend and frontend test suites and report exact commands/results.

**Acceptance:** All four mandatory categories pass; core role, workflow, listing, and async behaviours have meaningful assertions; no tests depend on external email or AWS services.

### Phase 8 — Full integration and submission

**Read:** all feature READMEs, especially `README-infrastructure-deployment.md`, `README-testing-strategy.md`, and this plan.

**Prompt:**

> Perform a final scope-completeness audit against the assignment brief and wireframe. Start the complete Docker Compose environment from a clean state; apply migrations; run the reproducible seed command; verify frontend/backend health; run backend and frontend tests; and smoke-test the four-role journey: Client creates a ticket, Facility Manager sees it, Department POC assigns a Worker or forwards the Department, Worker submits one of the three assessments, and Client marks the ticket resolved. Verify listing pagination, all four filters, Issue search, and both Created Time sort directions with seeded records. Verify Activity, History, comments, loading/empty/error/permission states, and responsive layouts. Check `.env.example` contains placeholders only and no secrets, dependency folders, or environment-specific files are committed. Complete the root README with prerequisites, setup commands, test commands, API overview, data model, architecture decisions, assumptions, limitations, at least two Engineering Depth choices, query optimization, Celery/Redis/Outbox design, AWS deployment approach, AI tools used and how they were used, actual time spent, and improvements possible with more time. Do not claim a live AWS deployment. Report each assignment requirement as complete, incomplete, or not applicable, with evidence.

**Acceptance:** Every in-scope requirement is checked against the source; clean Docker startup works; migrations and seeds are reproducible; required tests pass; the four-role workflow and listing behaviours work; documentation is complete; any remaining defect is disclosed explicitly.

## 7. Git and review checkpoints

Use small, reviewable commits after each verified implementation phase. Suggested sequence:

1. `chore: scaffold full-stack project and local services`
2. `feat: add domain models migrations and demo seed data`
3. `feat: implement jwt auth and reference data APIs`
4. `feat: implement ticket lifecycle and role-scoped APIs`
5. `feat: add transactional notification outbox and celery delivery`
6. `feat: build role-aware ticketing frontend`
7. `test: cover ticket workflow authorization and async notifications`
8. `docs: complete setup architecture and submission guide`

Before each commit:

- Inspect `git diff` and `git status`.
- Run the relevant tests/build checks.
- Confirm `.env`, secrets, local databases, `node_modules`, virtual environments, build outputs, and other dependency folders are ignored.
- Do not commit generated credentials or environment-specific files.

Do not mark a phase complete merely because code was generated. Record the command(s) run and whether they passed. If a check fails, report the failure and fix it before treating the phase as accepted.

## 8. Root README deliverables checklist

The repository root `README.md` must include:

- Project overview and implemented workflow.
- Prerequisites and versions.
- Setup and Docker Compose run instructions.
- Migration and seeded-data commands, including demo accounts/credentials safe for local evaluation only.
- Backend and frontend test commands.
- API endpoint overview.
- Data-model and architecture explanation, linking to `readmes/` feature specifications.
- Assumptions and limitations.
- Explanation of at least two Engineering Depth choices (the agreed design includes audit history, transactions, and query optimization; useful logging may also be documented where implemented).
- Redis/Celery/Outbox design, retry and duplicate handling.
- AWS deployment approach, clearly stating that no live deployment was performed if that is the case.
- Actual time spent, recorded truthfully after implementation.
- AI-assisted development disclosure: name the tools and accurately describe how they were used.
- What would be improved with more time.

## 9. Final scope-completion gate

Do not call the assignment complete until every applicable item below has been implemented and verified against the brief and wireframe:

- [ ] Four seeded roles can authenticate and switch accounts using standard authentication.
- [ ] Backend visibility and action authorization match the agreed role/relationship rules.
- [ ] Client and internal ticket creation follow their respective conditional and validation rules.
- [ ] Quick Issues are derived from Client ticket history; conditional Office/Floor selection works; selected Issues belong to one Department.
- [ ] Ticket listing has server-side pagination, all four required filters, Issue-text search, and Created Time sorting in both directions.
- [ ] Ticket details and all depicted role-specific CTAs work.
- [ ] Worker assignment and Department forwarding work with correct visibility and Activity/History effects.
- [ ] All three Worker assessment outcomes work and lead to Pending Department POC Review.
- [ ] A mapped Client user or the Ticket's creator can mark a ticket resolved at each agreed workflow stage; Open/Closed tabs reflect closure status.
- [ ] Activity filters, assignment/department History, and comments work.
- [ ] Required loading, empty, success, validation, permission, and unexpected error states are handled.
- [ ] Desktop/mobile layouts, semantic HTML, and basic accessibility are addressed.
- [ ] Redis/Celery notification flow uses the transactional outbox, retries, idempotency, recovery, and one Beat scheduler.
- [ ] At least four meaningful automated test categories required by the brief are covered and tests pass.
- [ ] Docker Compose runs frontend, backend, PostgreSQL, Redis, Celery Worker, and one Celery Beat instance.
- [ ] `.env.example` is safe; migrations and seed command are reproducible.
- [ ] At least two Engineering Depth options are implemented and explained; query optimization and indexes are justified.
- [ ] Root README and feature READMEs are complete and consistent.
- [ ] AWS deployment note covers all requested topics; no live deployment is claimed unless actually performed.
- [ ] AI-tool usage and actual time spent are disclosed truthfully.

## 10. Scope and change-control note

This plan controls implementation order; it does not replace or reduce the assignment scope. The brief and wireframe define the required product. The finalized feature READMEs define the agreed technical implementation and documented assumptions. If a new decision changes a requirement or architecture, update the affected README(s), dependent documents, and acceptance checks before changing code.
