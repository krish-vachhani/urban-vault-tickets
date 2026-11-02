# Infrastructure and Deployment — Docker Compose and AWS

**Status:** FINALIZED  
**Local runtime:** Docker Compose  
**Production target:** Amazon ECS on AWS Fargate, private S3 + CloudFront OAC, and API routing through an Application Load Balancer  
**Scheduler:** One Celery Beat instance  
**Scope:** Local development, deployment topology, networking, secrets, scaling, observability, and recovery. A live AWS deployment is not required.

This document records the approved infrastructure architecture for the Urban Vault take-home assignment. Follow it without introducing Kubernetes, microservices, EC2-managed Docker hosts, or a different queueing platform.

## 1. Assignment requirements

The take-home brief requires Docker Compose for the web application, PostgreSQL, Redis, and a Celery worker; environment-variable configuration with a safe example file; and a concise AWS deployment note covering services, secrets, static/media handling, Celery deployment, scaling, monitoring, and failure recovery. A live AWS deployment is not required.

## 2. Finalized infrastructure decisions

| Area | Final decision | Notes |
|---|---|---|
| Local environment | Docker Compose | Reproducible local stack |
| Local frontend | React + Vite container | Development server; proxies `/api` to Django |
| Local backend | Django + DRF container | Development command locally; production image runs Gunicorn |
| Database | PostgreSQL | Named persistent Docker volume locally; Amazon RDS for PostgreSQL in AWS |
| Broker | Redis | Celery broker only; Amazon ElastiCache for Redis OSS in AWS |
| Async execution | Celery Worker | Separate local container and separate ECS service |
| Scheduler | Celery Beat | Separate local container; one single-instance ECS service in production |
| Production compute | Amazon ECS on AWS Fargate | Separate API, Worker, and Beat services; no EC2 host management |
| Frontend hosting | Private S3 bucket + CloudFront Origin Access Control (OAC) | API traffic is routed through CloudFront to the ALB |
| API ingress | Application Load Balancer (ALB) | CloudFront `/api/*` behavior forwards requests to the ALB |
| Container registry | Amazon Elastic Container Registry (ECR) | Stores backend/worker image |
| Secrets | AWS Secrets Manager | Inject required secrets into ECS tasks |
| Logs/metrics | Amazon CloudWatch | Central logs, metrics, and alarms |
| Networking | Amazon VPC | Application and data services use private subnets where appropriate |

The supporting AWS services in this table are part of the approved production design. Exact AWS Region, instance sizes, task CPU/memory, subnet CIDRs, retention periods, and alarm thresholds are deployment-time configuration, not fixed assignment requirements.

## 3. Local Docker Compose topology

Docker Compose must run these six services:

| Compose service | Responsibility | Typical local command/port |
|---|---|---|
| `frontend` | React/Vite development server | Vite on `5173` |
| `backend` | Django REST API | Django development server on `8000` |
| `postgres` | PostgreSQL database | `5432` inside Compose network |
| `redis` | Celery broker | `6379` inside Compose network |
| `celery-worker` | Executes notification delivery tasks | `celery -A config.celery:celery_app worker --loglevel=info` |
| `celery-beat` | Periodically dispatches due and recoverable outbox rows | `celery -A config.celery:celery_app beat --loglevel=info` |

Use one backend Docker image for the `backend`, `celery-worker`, and `celery-beat` services, with different container commands. Do not maintain three independently built copies of the same Python dependencies.

Only the `backend` service has a `build` section; `celery-worker` and `celery-beat` reuse its image tag with `pull_policy: never`. Building the same image tag from three services in parallel fails on a clean machine (verified in Phase 1).

### 3.1 Local networking and dependencies

- All services communicate over the Compose network using service names (`postgres`, `redis`, `backend`), not `localhost` from inside a container.
- PostgreSQL must have a health check (for example, `pg_isready`).
- Redis must have a health check (for example, `redis-cli ping`).
- Backend startup must wait for PostgreSQL readiness before migrations/serving requests.
- Celery Worker and Beat must wait for the backend image/code, PostgreSQL, and Redis to be available.
- Vite proxies `/api/*` to the backend so the browser uses the same origin for API and JWT refresh-cookie requests during local development.
- Use a named volume for PostgreSQL data. Redis persistence is not the source of truth for notifications; lost queued messages are recoverable from PostgreSQL `NotificationOutbox` rows.
- Run exactly one Beat container in the local Compose environment.

Do not run Django migrations independently in every service's startup command. Run migrations explicitly as a one-off command before starting/restarting the application stack.

### 3.2 Local commands

From the repository root:

```bash
# Create the local environment file (first time only)
cp .env.example .env

# Build and start all six services
docker compose up --build

# Apply database migrations
docker compose exec backend python manage.py migrate

# Load deterministic demo users and sample data
docker compose exec backend python manage.py seed_demo_data

# Run backend tests
docker compose exec backend python manage.py test

# Run frontend tests
docker compose exec frontend npm run test -- --run

# Run the outbox recovery command manually when needed
docker compose exec backend python manage.py dispatch_pending_notifications

# Stop containers without deleting the PostgreSQL volume
docker compose down
```

`docker compose down -v` deletes named volumes and therefore removes local database data; do not use it unless a full local reset is intended.

### 3.3 Environment configuration

Commit `.env.example` with safe placeholders only. Do not commit `.env`, real passwords, Django secret keys, JWT signing keys, AWS credentials, or production endpoints. The file lives at the repository root, where Docker Compose reads it.

The complete set of keys (Phase 0 audit, G7). All of them are in `.env.example` from Phase 1; the phase noted beside a key is when the code starts reading it:

```env
# Django
DEBUG=True
SECRET_KEY=replace-for-local-development
ALLOWED_HOSTS=localhost,127.0.0.1,backend
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
LOG_LEVEL=INFO

# Authentication (Phase 3)
JWT_SIGNING_KEY=replace-for-local-development
REFRESH_COOKIE_SECURE=False

# PostgreSQL
DB_NAME=urban_vault
DB_USER=urban_vault
DB_PASSWORD=replace-for-local-development
DB_HOST=postgres
DB_PORT=5432

# Redis (Celery broker)
REDIS_URL=redis://redis:6379/0

# Notifications (Phase 5)
NOTIFICATION_REDISPATCH_INTERVAL_SECONDS=300

# Demo data (Phase 2)
SEED_DEMO_PASSWORD=replace-for-local-development

# Frontend
VITE_API_BASE_URL=/api/v1
VITE_ENABLE_DEMO_ACCOUNTS=true
API_PROXY_TARGET=http://backend:8000
```

The actual settings names may follow the implementation, but every required setting must be documented and validated at startup. Production values come from Secrets Manager and ECS task configuration, not from a committed environment file.

## 4. Production AWS topology

Use one CloudFront distribution with two origins and path-based cache behaviors:

- Default behavior (`/*`) serves the React production build from a private S3 bucket using CloudFront OAC.
- API behavior (`/api/*`) forwards requests to an Application Load Balancer (ALB), which routes to the Django ECS service.

The application should use one public origin/domain. This keeps the React SPA and API same-origin from the browser's perspective, which simplifies the approved JWT refresh-cookie and CSRF design.

### 4.1 Request path

```text
Browser
  |
  v
CloudFront distribution (HTTPS)
  |-- default behavior /* --------> Private S3 origin (React build, OAC)
  |
  `-- API behavior /api/* --------> Application Load Balancer
                                      |
                                      v
                                  ECS Fargate API service
                                      |
                      +---------------+----------------+
                      |                                |
                      v                                v
                 Amazon RDS                     ElastiCache Redis
                PostgreSQL                       Celery broker
                                                       ^
                                                       |
                                             ECS Celery Worker service
                                                       ^
                                                       |
                                                ECS Celery Beat service
```

CloudFront OAC protects the S3 origin only. The ALB/API origin needs its own ingress controls; do not assume S3 OAC protects the ALB. Restrict direct ALB access so application traffic is expected to arrive through the configured CloudFront path/origin controls.

For the `/api/*` CloudFront behavior:

- Disable response caching. Ticket and authentication responses are user-specific and must not be cached at the CDN.
- Forward the `Authorization` header, required cookies, CSRF header, query strings, and other request information required by Django.
- Allow the HTTP methods used by the REST API, including `GET`, `HEAD`, `OPTIONS`, and the required write methods (`POST`, `PUT`, `PATCH`, `DELETE`).
- Preserve refresh-cookie and CSRF behavior end to end.
- Configure HTTPS from viewer to CloudFront and HTTPS to the ALB origin.

For the S3 origin, use a regular S3 bucket origin (not an S3 static website endpoint), keep Block Public Access enabled, configure OAC to sign origin requests, and grant the CloudFront distribution access through the bucket policy. Use bucket-owner-enforced object ownership. CloudFront OAC is not supported with an S3 website endpoint.

### 4.2 ECS Fargate services

Deploy three independently managed ECS services:

| ECS service | Container command | Scaling policy |
|---|---|---|
| `urban-vault-api` | Gunicorn serving Django/DRF | Scale API tasks using CPU/memory and request/latency metrics |
| `urban-vault-celery-worker` | Celery worker | Scale using notification backlog/oldest pending age, with CPU/memory as supporting signals |
| `urban-vault-celery-beat` | Celery Beat scheduler | Desired count exactly 1; never autoscale; prevent overlapping active schedulers during deployments |

The API and Worker can scale independently because they have different workloads. The Beat scheduler must remain single-instance. Celery documents that multiple Beat schedulers for the same schedule can enqueue duplicate periodic tasks; notification dispatch remains idempotent as a second safeguard.

Use Fargate tasks in private application subnets. The ALB routes API traffic to healthy API targets. The Worker and Beat do not need public ingress. Use separate task definitions or the same image with different commands; use separate IAM task roles where their AWS permissions differ.

### 4.3 Supporting AWS services

| Concern | AWS service/design |
|---|---|
| Container images | Amazon ECR |
| Relational database | Amazon RDS for PostgreSQL in private DB subnets |
| Broker | Amazon ElastiCache for Redis OSS, reachable only from application/worker tasks |
| Static frontend | Private Amazon S3 bucket + CloudFront OAC |
| Public routing | CloudFront + ALB |
| Secrets | AWS Secrets Manager, injected through ECS task definitions |
| Logs and metrics | Amazon CloudWatch Logs, metrics, dashboards, and alarms |
| Notifications for alarms | Amazon SNS (optional delivery target for CloudWatch alarms) |

For a production availability posture, use RDS Multi-AZ and automated backups with point-in-time recovery. A lower-cost non-production environment may use a smaller/single-AZ database configuration if its recovery objective permits it. Keep RDS and ElastiCache inaccessible from the public internet.

Use an ElastiCache engine/version that is compatible with the pinned Celery/Kombu Redis transport. Enable in-transit TLS and at-rest encryption where supported by the selected cache configuration. Keep the Redis security group restricted to the API/Worker/Beat task security groups.

## 5. Static assets and media

### React static assets

1. Run the Vite production build.
2. Upload the build output to the private S3 bucket.
3. Serve the bucket through CloudFront with OAC.
4. Use hashed/versioned asset filenames so long-lived caching is safe for immutable assets.
5. Keep the SPA entry document's cache policy short enough for deployments to take effect; invalidate the relevant CloudFront paths after publishing if required.

### User-uploaded media

The assignment does not require file uploads. Do not build a media subsystem just for this assignment. If uploads are introduced later, use a separate private S3 bucket and backend-authorized presigned URLs; do not make the bucket public.

## 6. Secrets and IAM

- Store Django `SECRET_KEY`, JWT signing key, database password, and Redis authentication values in AWS Secrets Manager (or an explicitly documented secure parameter store where appropriate).
- Inject secrets into ECS tasks through task-definition secret references. Secret rotation requires tasks to receive the updated values; arrange a controlled service deployment/restart after rotation where necessary.
- Use an ECS task execution role for image pulls and task startup secret/log delivery permissions.
- Use an ECS task role for application runtime AWS access. Grant least privilege; the API/Worker should not inherit broad account-level permissions.
- Do not bake secrets into Docker images, source code, build arguments, or GitHub Actions logs.
- Use environment variables for non-secret configuration such as `DEBUG=False`, database host, allowed hosts, Redis URL, log level, and public URL.

## 7. Celery, Beat, and the transactional outbox

`README-async-processing.md` defines the authoritative notification design. Infrastructure must implement it as follows:

- PostgreSQL `NotificationOutbox` is the durable source of truth.
- Redis is the Celery broker only; no Celery result backend is required.
- Django creates outbox rows in the same transaction as the triggering ticket operation and attempts to publish after commit.
- A single Celery Beat service schedules the outbox dispatcher every 60 seconds.
- The dispatcher republishes eligible `PENDING` rows and recovers stale `PROCESSING` rows according to the outbox recovery rules.
- Keep `dispatch_pending_notifications` as an operator-invoked Django management command as well as the logic called by the scheduled task.
- Run one Beat scheduler only. Do not autoscale Beat or embed Beat in every worker.
- Keep notification tasks idempotent. Broker/task delivery is at-least-once, not exactly-once.

The outbox schema includes `next_attempt_at` (when a row is due) and `last_dispatched_at` (when it was last published for its current attempt). The dispatcher publishes due rows that have not yet been published, republishes a due row whose last publish is older than the 5-minute re-dispatch interval (a lost message), and recovers `PROCESSING` rows older than the five-minute stale threshold. Update `last_dispatched_at` only after a successful broker publish. If a process crashes after publish but before updating it, a duplicate task can be published; the task's row-lock/idempotency checks make that safe. Retries are scheduled only through `next_attempt_at`; Celery's own task retry is not used (`README-async-processing.md` §7).

The Beat schedule can be defined in Celery's code-based `beat_schedule`; a separate database-backed scheduler package is not required. The existing manual recovery command remains available for diagnosis and operator-triggered recovery.

## 8. Scaling approach

| Component | Scaling approach |
|---|---|
| CloudFront/S3 | CloudFront handles static asset delivery; use cache policies for versioned assets |
| API service | Increase ECS desired count based on sustained CPU/memory, request rate, and latency; ALB distributes requests |
| Celery Worker | Increase worker task count based on queue/outbox backlog and age of oldest pending notification |
| Celery Beat | Exactly one active scheduler instance; no autoscaling |
| RDS PostgreSQL | Start with a modest class; scale vertically when metrics justify it; use read replicas only if read scaling becomes a measured need |
| ElastiCache Redis | Monitor memory/connections; resize or add capacity only when broker measurements justify it |

Do not introduce EKS, Kubernetes, Kafka, sharding, or multi-region deployment for this assignment.

## 9. Monitoring and operational visibility

Use CloudWatch for container logs, AWS service metrics, dashboards, and alarms.

Recommended signals:

- API: request count, 4xx/5xx rates, request latency, target health, task restarts, CPU, and memory.
- RDS: CPU, database connections, free storage, freeable memory, backup status, and failover events.
- ElastiCache: memory, CPU, connections, evictions, and replication/availability events where applicable.
- Celery: worker task success/failure, retries, task duration, and active worker count.
- Outbox: PENDING count, FAILED count, oldest pending age, stale PROCESSING count, and dispatch failures.
- Beat: task scheduling/dispatch logs and confirmation that exactly one scheduler is running.

Use structured application logs containing request/correlation ID, Ticket ID, outbox ID, task ID, event type, and outcome. Never log passwords, JWTs, refresh cookies, or secrets. Configure CloudWatch alarms with thresholds based on observed workload rather than inventing arbitrary thresholds in the assignment README.

Enable the ECS deployment circuit breaker with rollback for rolling service deployments. Use ALB health checks and ECS task health checks so unhealthy API tasks are removed/replaced. Monitor deployment failure events and CloudWatch alarms.

## 10. Failure recovery

| Failure | Recovery strategy |
|---|---|
| API container exits or fails health checks | ALB stops routing to unhealthy targets; ECS replaces unhealthy tasks |
| ECS API deployment fails | Deployment circuit breaker/CloudWatch alarm rollback to last known good service revision |
| Celery Worker exits | ECS replaces the task; Beat/outbox recovery republishes pending or stale work |
| Beat task restarts | ECS restarts the single Beat service; the schedule is code-defined and the outbox remains durable in PostgreSQL |
| Redis is unavailable | Ticket operation remains committed if its PostgreSQL transaction committed; outbox stays PENDING; Beat/manual dispatcher republishes after broker recovery |
| Redis loses queued messages | Pending/stale outbox rows are republished; idempotency guards duplicates |
| Worker crashes while processing | Stale `PROCESSING` rows are reset/requeued after the five-minute processing lease expires |
| Notification repeatedly fails | Outbox row becomes `FAILED`, retains sanitized error context, and can be inspected/reprocessed deliberately |
| RDS instance/AZ failure | RDS Multi-AZ failover for production HA; clients retry transient connection failures |
| Accidental data deletion/corruption | Restore RDS from automated backup/PITR to a recovery instance and validate before cutover |
| Frontend release is broken | Restore the previous versioned S3 build and invalidate relevant CloudFront paths |

For real external email delivery, a crash after a provider accepts an email but before PostgreSQL records `SENT` can still cause duplicate delivery. Use provider idempotency when available; do not promise exactly-once external delivery.

## 11. Suggested deployment pipeline (not a mandatory assignment deliverable)

A simple CI/CD flow can use GitHub Actions:

1. Run backend and frontend automated tests.
2. Build the backend Docker image.
3. Push the image to Amazon ECR.
4. Run Django migrations once as a one-off ECS task before deploying the new application version.
5. Deploy the API, Worker, and single Beat services.
6. Build the Vite frontend and upload versioned assets to S3.
7. Update/invalidate CloudFront entry paths as needed.

Do not run migrations independently in every API task at startup. Use backward-compatible migration practices during rolling deployments so the old and new application versions can safely overlap during deployment.

The CI/CD implementation itself is not a required assignment deliverable; document the production approach without adding an unrequested AWS automation subsystem.

## 12. Security checklist

- [ ] Public traffic uses HTTPS.
- [ ] S3 Block Public Access is enabled; CloudFront OAC is the authorized S3 reader.
- [ ] S3 bucket policy grants access only to the intended CloudFront distribution.
- [ ] API CloudFront behavior disables caching and forwards auth/cookie/CSRF/query data required by Django.
- [ ] Direct ALB access is restricted through origin ingress controls.
- [ ] ECS API, Worker, and Beat tasks run without public IPs in private application subnets.
- [ ] RDS and ElastiCache are in private data subnets and accept traffic only from required application security groups.
- [ ] RDS backups and point-in-time recovery are configured.
- [ ] Redis TLS/in-transit encryption and at-rest encryption are enabled where supported by the selected configuration.
- [ ] Secrets are stored in Secrets Manager and injected at task startup.
- [ ] IAM roles follow least privilege.
- [ ] No production secrets are stored in Git or Docker images.
- [ ] Exactly one active Celery Beat scheduler runs.
- [ ] API responses are not cached by CloudFront.

## 13. Assignment scope and open deployment-time parameters

The assignment requires the deployment note, not a live AWS deployment. Do not create AWS resources unless separately requested.

Deployment-time values intentionally left configurable:

- AWS Region and VPC/subnet CIDRs;
- Fargate CPU/memory and desired task counts;
- ECS deployment percentages and health-check grace periods;
- RDS instance class/storage/backup retention/Multi-AZ choice for each environment;
- ElastiCache node/replication configuration and compatible Redis OSS version;
- CloudFront cache/origin request policies and allowed API methods;
- ALB listener, TLS certificate, and ingress restriction mechanism;
- CloudWatch alarm thresholds and retention periods.

Do not invent these values in application code. Document production defaults only when the deployment context provides a justified requirement.

## 14. Implementation acceptance checklist

- [ ] Docker Compose contains `frontend`, `backend`, `postgres`, `redis`, `celery-worker`, and `celery-beat` services.
- [ ] PostgreSQL uses a named persistent volume and a health check.
- [ ] Redis has a health check and is configured as the Celery broker.
- [ ] Backend, Worker, and Beat use the backend image with distinct commands.
- [ ] Exactly one Beat service/container runs locally and in production.
- [ ] The periodic Beat task dispatches pending/stale outbox notifications; the manual recovery command remains available.
- [ ] `.env.example` has placeholders only; actual `.env` is ignored by Git.
- [ ] Local setup, migrations, seed data, backend tests, frontend tests, and shutdown commands are documented.
- [ ] AWS note describes CloudFront + private S3 OAC, `/api/*` to ALB, ECS Fargate API/Worker/Beat services, RDS PostgreSQL, ElastiCache Redis, ECR, Secrets Manager, VPC, and CloudWatch.
- [ ] Static/media strategy, secrets, IAM, scaling, monitoring, and recovery are documented.
- [ ] No live AWS deployment is required for submission.

## 15. Official references

- [Amazon ECS service load balancing and ALB support](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-load-balancing.html)
- [Run Fargate tasks in private subnets and task networking](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html)
- [Restrict access to an S3 origin with CloudFront OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [Use CloudFront with multiple origins, including an ALB](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistS3AndCustomOrigins.html)
- [CloudFront cache behavior configuration](https://docs.aws.amazon.com/cloudfront/latest/APIReference/API_CacheBehavior.html)
- [Inject Secrets Manager values into ECS tasks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html)
- [RDS automated backups and point-in-time recovery](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html)
- [RDS Multi-AZ DB instance deployments](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html)
- [ElastiCache in-transit encryption](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/in-transit-encryption.html)
- [ECS deployment failure detection and circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-failure-detection.html)
- [Celery periodic tasks and the single-scheduler requirement](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html)
