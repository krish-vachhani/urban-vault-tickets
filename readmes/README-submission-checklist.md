# Final submission checklist

Prepared for Phase 8 review on 2 November 2026 and updated during final GitHub submission preparation. Phase 8 changed documentation only; the subsequent audit fixes are committed as `3dbbc7a`, with documentation commits also authorized. No push, submission message or AWS deployment has been performed. The user selected repository-link submission; no ZIP is required. The user's explicit reporting exclusions take precedence over the assignment's reporting template.

## Required deliverables

| Deliverable | Status | Evidence |
|---|---|---|
| GitHub source repository | Source present; publication and recipient access pending | `backend/`, `frontend/`, migrations, committed dependency manifests/lockfile, tests; no ZIP required |
| README/setup instructions | Prepared | [Root README](../README.md): prerequisites, environment, ordered Compose setup, migrations, seed, login, commands, API/model/design explanations, assumptions, limitations, improvements |
| AWS deployment note | Prepared; documentation only | [Infrastructure/deployment note](README-infrastructure-deployment.md): approved services, release/configuration, secrets, static assets, Celery, monitoring/scaling, recovery, and production preparation gaps |
| AI disclosure | Included | Root README names OpenAI ChatGPT / Codex and Anthropic Claude / Claude Code, and describes assistance with development, testing, review, and documentation |
| Docker Compose | Present | Six services in `docker-compose.yml`; shared backend image; PostgreSQL volume; PostgreSQL/Redis/backend probes |
| Example environment | Present | `.env.example` has placeholders; implemented configuration readers match documented names |
| Migrations and reproducible demo data | Present and tested | App migrations; `seed_demo_data`; seed tests verify 14 accounts, 80 initial tickets, repeat-run behavior, relationships, and pagination volumes |
| Required automated test categories | Covered | API/workflow, authentication/authorization, Celery failure/retry, and frontend user interaction; see evidence below |
| Optional screenshots/recording | Not included | Optional in the assignment; no generated capture is required for the source submission |

The private brief and wireframe were reviewed locally for these deliverables. They are intentionally not reproduced here or included in the submission because they contain recruiter contact details.

## Verification and evidence boundaries

The [Phase 7 record](README-phase7-verification.md) reports 376 backend tests and 78 frontend tests passing, TypeScript/ESLint/build checks passing, migration consistency, real role-based HTTP flows, and actual Redis/Worker/Beat delivery. It explicitly distinguishes controlled outage/concurrency tests from live infrastructure tests.

Phase 8 checks executed against the existing running Compose stack:

| Command/check | Result |
|---|---|
| `docker compose --env-file .env.example config --quiet` | Passed; example resolves the six-service configuration |
| `docker compose exec -T backend python manage.py test --noinput` | 376 tests passed, including seed reproducibility in the separate PostgreSQL test database |
| `docker compose exec -T frontend npm run test -- --run` | 78 tests passed across 11 files |
| `docker compose exec -T frontend npm run typecheck` | Passed |
| `docker compose exec -T frontend npm run lint` | Passed |
| `docker compose exec -T frontend npm run build` | Passed; existing non-blocking bundle-size warning remains |
| `docker compose exec -T backend python manage.py check` | No issues |
| `docker compose exec -T backend python manage.py makemigrations --check --dry-run` | No changes detected |
| `docker compose exec -T backend python manage.py migrate --check` | No pending migrations |
| Seed/recovery command `--help` and implementation inspection | Command names/options match the README |
| Read-only verification of seeded account hashes/roles | All 14 accounts are active, match the seed roles, and accept the locally configured `SEED_DEMO_PASSWORD`; no credentials printed |
| HTTP health through `127.0.0.1:5173/api/v1/health/`, direct backend health, frontend entry HTML | HTTP 200; database status `ok`; Urban Vault entry page served |
| `docker compose exec -T celery-worker celery -A config.celery:celery_app inspect ping` | One Worker responded |
| Git status, candidate-path review, relative Markdown links, reporting exclusions, and `git diff --check` | Documentation-only changes; checks passed |
| Current submission candidate scan | No private PDFs, local environment/database/dependency/build files; no matches for local secret values or checked private-key/token signatures |

The local machine also has a separate Node listener on `::1:5173`: `localhost` selected that listener and returned 404. The verified Compose frontend/API address is `127.0.0.1:5173`, now used in the setup instructions. The unrelated listener was not stopped or modified.

The Phase 8 scan covered current tracked files plus non-ignored review files, rather than historical Git objects. Existing development data was not reset, reseeded, or migrated; Phase 8 reviewed the startup/build sequence without running it from a clean machine. The later final readiness report records the isolated setup rehearsal and targeted browser checks separately. No generated build files are part of the submission candidate.

During final Git preparation, the initial history scan covered all eight reachable commits and 282 distinct historical file blobs, plus 236 current candidate files. No excluded paths or checked secret signatures were found. Credential-like literal findings were reviewed as test fixtures or documentation examples. This is a targeted credential/privacy check, not a guarantee against every possible secret format; subsequent audit-fix and documentation changes were also reviewed before committing.

Outstanding review items:

- [x] Acknowledge the user's previously completed browser checks across all four roles and the 375px layout. Phase 7 itself did not perform these checks. The final fix pass adds keyboard Client-selection and interaction regressions; a subsequent targeted native Chrome pass checked Client search, Quick Issues and the 375px creation/detail layout, as recorded in the final readiness report.
- [x] Rehearse setup outside this checkout with isolated volumes. The final readiness pass built images, migrated an empty PostgreSQL database, seeded 80 tickets and started all six services; role/API and actual Worker-delivery checks passed. Existing Docker dependency-layer caches were reused, so this is not represented as an entirely uncached clean-machine build.
- [ ] Optionally broaden keyboard/focus/contrast/screen-reader checks. Native Chrome access worked on retry, but the targeted pass stopped at the user's requested scope and does not establish comprehensive accessibility coverage.
- [x] Review the final documentation and AI disclosure; no independent-authorship or production-deployment claim is made.
- [x] Choose GitHub repository-link delivery. No ZIP is required.
- [ ] Confirm the GitHub repository URL and visibility, then authorize the push. No repository visibility change or invitation has been made.
- [ ] After publication, verify recipient access and share the repository link with HR.

Production configuration gaps are documented in the AWS note. They do not require a live deployment for this assignment and are not authorization to start production implementation in Phase 8.

The subsequent [final readiness verification](README-final-readiness.md) records all four audit findings fixed, rapid-submission protection, 378 backend tests and 90 frontend tests passing, and the isolated setup evidence. The Phase 7 and Phase 8 results above remain historical records. Final application fixes are committed as `3dbbc7a`; GitHub publication remains pending user confirmation.

## Submission contents and exclusions

Include the root README, `CLAUDE.md`, `readmes/`, `docker-compose.yml`, `.env.example`, `.gitignore`, and the tracked backend/frontend source, tests, migrations, Dockerfiles/ignore files, configuration, and dependency manifests/lockfile. Empty Python package files are required and must remain in the submission.

Exclude:

- `docs/assignment-brief.pdf`, `docs/assignment-wireframe.pdf`, and other private assignment PDFs/contact details.
- `.env`, environment-specific files, real credentials, keys, cookies, tokens, database exports, or local database storage.
- `node_modules/`, virtual environments, Python caches, coverage reports, frontend build output, collected static/media files, Beat schedule files, local review/tool artifacts, and OS/editor clutter.
- A repository submission includes Git history; tracked contents and reachable history were reviewed for credentials/private files before publication preparation.

`.gitignore` already excludes the private PDFs, local environment, dependencies, database artifacts, and generated output. Ignored files still exist locally and must remain outside Git. No ignore/configuration change is necessary for the current contents.

## GitHub publication after confirmation

The configured `origin` is `https://github.com/krish-vachhani/urban-vault-tickets.git`. This configuration does not establish that the intended repository or its visibility has been confirmed. Before pushing, obtain the user's confirmation of the URL and visibility. If private, ensure HR has repository access; if public, verify that the repository can be opened while signed out.

```bash
git status --short
git branch --show-current
git log -3 --oneline
git remote -v
```

Require the intended committed revision on `main` with a clean working tree. After URL, visibility and push authorization are confirmed, publish with `git push -u origin main`. Verify the latest commit and rendered README on GitHub, verify recipient access, and provide the repository's web URL for the user to submit to HR. No archive or message to HR is created by this preparation step.
