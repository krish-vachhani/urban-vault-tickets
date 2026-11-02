# CLAUDE.md — Urban Vault Ticketing (take-home assignment)

Permanent project instructions. Read this file before every task.

## What this project is

A full-stack facility-management ticketing system built for the Urban Vault Full-Stack Developer take-home assignment:

- **Backend:** Python, Django, Django REST Framework, PostgreSQL, Redis, Celery (`backend/`)
- **Frontend:** React, TypeScript, Vite, Material UI, Tailwind CSS v4, TanStack Query (`frontend/`)
- **Local runtime:** Docker Compose (`docker-compose.yml`)

## Source of truth — read before writing code

Use this hierarchy:

1. `docs/assignment-brief.pdf` and `docs/assignment-wireframe.pdf` define the required scope. They are kept locally only and are git-ignored because they contain recruiter contact details; never commit them.
2. `readmes/` documents the approved product and technical decisions. Start with `readmes/README.md`; it lists which document to read before each kind of work.
3. Code must satisfy both. Existing code never overrides a requirement or a finalized decision.

Rules:

- Read the README files relevant to a task **before** writing code for it. `readmes/README-implementation-plan.md` lists the documents for each phase.
- Do not redesign a finalized decision without naming a concrete problem and getting approval.
- If a README conflicts with the brief, the wireframe, or another README, stop and report the conflict with file and section references. Do not resolve it silently.
- If a decision changes, update the affected README(s) first, then the code.
- Do not invent features outside the assignment scope. The 9-hour timebox is not a reason to drop in-scope requirements.

## Working process

- Work one implementation phase at a time, following `readmes/README-implementation-plan.md`.
- At the end of each phase, report what was done and **wait for approval** before starting the next phase.
- Run the relevant checks/tests before claiming something works, and report failures honestly.
- Never commit secrets, `.env` files, dependency folders, or build outputs.

## Code quality standard (applies to every phase)

All code must be exceptionally readable, human-friendly, and easy to understand, debug, modify, and explain in a technical interview.

Do:

- Use descriptive names for variables, functions, classes, and files.
- Write small, focused functions that each do one thing.
- Keep logic explicit and straightforward; prefer a few clear lines over a clever one.
- Keep a clear separation of responsibilities (see the layering rules below).
- Use appropriate typing: Python type hints on service/selector functions; strict TypeScript in the frontend.
- Handle errors explicitly and meaningfully; return the documented API error envelope.
- Give constants a name (no unexplained magic numbers or strings).
- Add a short comment when the *why* is not obvious from the code; do not narrate the obvious.

Avoid:

- Clever one-liners, unnecessary abstractions, and speculative generality.
- Duplicated logic — reuse the shared selector/service/component instead.
- Dead code, commented-out code, and unused imports.
- Unnecessary dependencies — add a library only when it removes real complexity.

## Layering rules

Backend (`readmes/README-backend-architecture.md`):

- Four Django apps: `accounts`, `organizations`, `tickets`, `notifications`.
- **Views** stay thin: authenticate, resolve the authorized object, validate input with a serializer, call a service, return a response.
- **Serializers** validate request shape and render responses; they do not run multi-step workflows.
- **Selectors** hold reusable read-only queries, including role-based visibility.
- **Services** hold business operations and own transactions and row locks.
- Business state changes only through explicit action endpoints, never a generic PATCH.

Frontend (`readmes/README-frontend-architecture.md`):

- Server state → TanStack Query. Auth/session → React Context. Listing state → URL search params. Forms → React Hook Form + Zod. Temporary UI → `useState`.
- MUI owns interactive components; Tailwind owns layout and spacing.
- Feature folders under `frontend/src/features/`; shared code under `frontend/src/shared/`.

## Common commands

From the repository root:

```bash
cp .env.example .env                                    # first time only
docker compose up --build                               # start all six services
docker compose exec backend python manage.py migrate    # apply migrations
docker compose exec backend python manage.py test       # backend tests (PostgreSQL)
docker compose exec frontend npm run test -- --run      # frontend tests
docker compose down                                     # stop (keeps database volume)
```

Frontend checks from `frontend/`: `npm run lint`, `npm run typecheck`, `npm run build`.
