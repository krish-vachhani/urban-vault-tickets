# Final submission checklist

Prepared for Phase 8 review on 2 November 2026. This phase changes documentation only. No commit, push, archive publication, submission message, or AWS deployment is performed. The user's explicit reporting exclusions take precedence over the assignment's reporting template.

## Required deliverables

| Deliverable | Status | Evidence |
|---|---|---|
| Source repository or ZIP | Source present; final handoff pending | `backend/`, `frontend/`, migrations, committed dependency manifests/lockfile, tests |
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

The scan covers current tracked files plus non-ignored review files, not an exhaustive audit of every historical Git object. Existing development data was not reset, reseeded, or migrated; the full startup/build sequence was reviewed against configuration, not re-run from a clean machine. These checks do not replace the Phase 7 report or claim an unperformed visual audit. No generated build files are part of the submission candidate.

Outstanding review items:

- [ ] Review desktop/mobile layout, keyboard navigation, and accessibility in a real browser. Phase 7 used component tests and live HTTP checks without a visual browser audit.
- [ ] Optionally rehearse the documented setup from a fresh checkout/volume before handoff. A clean-machine image rebuild is not claimed by the Phase 7 evidence.
- [ ] Review the final documentation and AI disclosure; no independent-authorship or production-deployment claim is made.
- [ ] Choose repository link or ZIP delivery and verify recipient access. No repository visibility change or invitation has been made.
- [ ] After approving and committing the final contents in a later step, create and inspect the final archive if using ZIP delivery.

Production configuration gaps are documented in the AWS note. They do not require a live deployment for this assignment and are not authorization to start production implementation in Phase 8.

## Submission contents and exclusions

Include the root README, `CLAUDE.md`, `readmes/`, `docker-compose.yml`, `.env.example`, `.gitignore`, and the tracked backend/frontend source, tests, migrations, Dockerfiles/ignore files, configuration, and dependency manifests/lockfile. Empty Python package files are required and must remain in the submission.

Exclude:

- `docs/assignment-brief.pdf`, `docs/assignment-wireframe.pdf`, and other private assignment PDFs/contact details.
- `.env`, environment-specific files, real credentials, keys, cookies, tokens, database exports, or local database storage.
- `node_modules/`, virtual environments, Python caches, coverage reports, frontend build output, collected static/media files, Beat schedule files, local review/tool artifacts, and OS/editor clutter.
- `.git/` from a ZIP. A repository submission naturally has Git history, so its tracked contents/history need their own credential/privacy review before sharing access.

`.gitignore` already excludes the private PDFs, local environment, dependencies, database artifacts, and generated output. Ignored files still exist locally and must not be included by zipping the working directory wholesale. No ignore/configuration change is necessary for the current contents.

## Packaging procedure after approval

These commands are for a later approved, committed revision. `git archive HEAD` excludes uncommitted Phase 8 documentation, so do not use it for the current review draft.

```bash
git status --short
git ls-files
git archive --format=zip --prefix=urban-vault-tickets/ --output=../urban-vault-tickets-submission.zip HEAD
unzip -l ../urban-vault-tickets-submission.zip
```

Before delivery, require a clean intended revision, inspect archive entries against the contents/exclusions above, and confirm `README.md`, `.env.example`, Compose, migrations, seed command, tests, and frontend lockfile are included. `git archive` includes tracked files even if an ignore rule later matches them; review the manifest rather than treating the ignore file as a secret scanner. Extract the archive outside this checkout for any final setup rehearsal. Share only the chosen repository link or reviewed archive after user approval.
