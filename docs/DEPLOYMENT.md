# AWS EC2 Docker Deployment

This deployment is intentionally sized for the work trial: one EC2 host running Nginx, Gunicorn/Flask, and PostgreSQL through Docker Compose. PostgreSQL uses a persistent named volume and has no public port.

## 1. Launch the instance

Use a current Ubuntu LTS EC2 AMI and an instance type appropriate for Docker builds. For a short-lived review deployment, 2 vCPU and 4 GiB RAM is a practical minimum; increase memory when building on-host if necessary.

Create or attach an SSH key pair. Do not commit the private key to the repository.

## 2. Security group

Inbound rules:

| Port | Source | Purpose |
|---|---|---|
| 22/TCP | Administrator public IP only | SSH |
| 80/TCP | Reviewer access range or `0.0.0.0/0` | HTTP demo |
| 443/TCP | Reviewer access range or `0.0.0.0/0` | Optional HTTPS |

Do not expose PostgreSQL `5432`, Flask/Gunicorn `8000`, or Vite `5173`.

## 3. Connect

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@EC2_PUBLIC_DNS
```

## 4. Install Docker from the official repository

Follow the current Docker Engine installation instructions for Ubuntu. The resulting host must provide both `docker` and `docker compose`.

Verify:

```bash
docker --version
docker compose version
```

Add the `ubuntu` user to the Docker group only when that operational tradeoff is acceptable. Reconnect after changing group membership.

## 5. Install Git and clone

```bash
sudo apt-get update
sudo apt-get install -y git
mkdir -p ~/apps
cd ~/apps
git clone <repository-url> ai-medical-scheduling-agent
cd ai-medical-scheduling-agent
```

For an archive-based submission, upload and extract the project into the same directory instead.

## 6. Configure production environment

```bash
cp .env.example .env
chmod 600 .env
```

Generate strong values locally or on the instance:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set at minimum:

```text
APP_ENV=production
SECRET_KEY=<generated secret>
POSTGRES_DB=scheduling
POSTGRES_USER=scheduling_app
POSTGRES_PASSWORD=<generated database password>
PUBLIC_APP_URL=http://EC2_PUBLIC_DNS
FRONTEND_ORIGIN=http://EC2_PUBLIC_DNS
LOG_LEVEL=INFO
MAX_CONTENT_LENGTH=262144
JSON_STRING_FIELD_MAX_LENGTH=8192
RAW_USER_TEXT_MAX_LENGTH=4000
TRANSCRIPT_TURN_MAX_LENGTH=2000
TRANSCRIPT_TURN_MAX_COUNT=200
RATE_LIMIT_ENABLED=true
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_MAX_REQUESTS=60
```

Leave Vogent values empty until the credentialed integration step. Never put AWS credentials, private keys, or root account credentials in `.env`.

Production startup fails fast when `DATABASE_URL` is missing or non-PostgreSQL, when `SECRET_KEY` is a development placeholder, or when `OPENAI_INTEGRATION_MODE=test` is set without `ALLOW_OPENAI_TEST_MODE_IN_PRODUCTION=true`.

For Vogent callbacks, replace the HTTP `PUBLIC_APP_URL`/`FRONTEND_ORIGIN` values with a real non-local HTTPS origin before configuring the workspace.

## 7. Build and start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Startup behavior:

1. PostgreSQL starts and passes `pg_isready`.
2. Backend runs `alembic upgrade head`.
3. Backend runs the idempotent seed command.
4. Gunicorn starts with production workers and threads.
5. Nginx starts after backend health is green.

If an environment value is changed in `.env` after containers already exist, recreate the service that consumes it. For example, after changing `OPENAI_API_KEY`, run:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

A plain `docker compose restart backend` may keep the prior container environment.

## 8. Verify

```bash
docker compose -f docker-compose.prod.yml ps
curl --fail http://localhost/api/v1/health
curl --fail http://EC2_PUBLIC_DNS/api/v1/health
```

Open `http://EC2_PUBLIC_DNS` and verify:

- Overview metrics load.
- Calls table and a call-detail page load.
- Physicians protocol loads.
- Call Simulator returns a recommendation and can book an open slot.
- The resulting call and appointment appear in the dashboard.
- Browser console contains no application errors.

The repository includes:

```bash
./infra/scripts/smoke-test.sh http://localhost
```

After adding real provider configuration, run the credential-gated checks intentionally:

```bash
OPENAI_API_KEY=<key> OPENAI_MODEL=gpt-5.2 OPENAI_INTEGRATION_MODE=live \
  ./infra/scripts/verify-openai-live.sh

PUBLIC_APP_URL=https://<public-host> VOGENT_FUNCTION_SECRET=<secret> \
  VOGENT_WEBHOOK_SECRET=<secret> ./infra/scripts/verify-vogent-readiness.sh
```

The OpenAI command performs one paid synthetic interpretation request. The Vogent command verifies HTTPS config and route reachability, but it does not claim workspace connectivity or complete a phone call.

## 9. Logs and operations

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=200
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml restart backend nginx
docker compose -f docker-compose.prod.yml ps
```

## 10. Run migrations and seed manually

The backend startup command already runs both. To execute again:

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend flask --app app:create_app seed
```

The seed is designed to be safe to run repeatedly.

## 11. PostgreSQL backup

Create a backup directory readable only by the administrator:

```bash
mkdir -p ~/backups/scheduling
chmod 700 ~/backups/scheduling
```

Run the supplied script:

```bash
./infra/scripts/backup-postgres.sh ~/backups/scheduling
```

Manual equivalent:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > ~/backups/scheduling/scheduling-$(date +%Y%m%d-%H%M%S).sql
```

Copy backups off the instance. A named Docker volume is persistence, not a complete backup strategy.

## 12. Deploy an update

```bash
cd ~/apps/ai-medical-scheduling-agent
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
docker image prune -f
curl --fail http://localhost/api/v1/health
```

## 13. Stop and cleanup

Stop containers while preserving the database volume:

```bash
docker compose -f docker-compose.prod.yml down
```

Remove containers and the PostgreSQL volume only after a verified backup and an explicit decision to destroy data:

```bash
docker compose -f docker-compose.prod.yml down -v
```

## 14. Optional HTTPS

A custom domain is not required for the work trial. When one is available:

1. Point an A/AAAA record to the EC2 address.
2. Permit inbound `443`.
3. Use a supported ACME client or a TLS-terminating AWS service.
4. Mount certificates read-only into Nginx or terminate TLS before Nginx.
5. Redirect HTTP to HTTPS.
6. Set `PUBLIC_APP_URL` and `FRONTEND_ORIGIN` to the HTTPS origin.
7. Rebuild/restart and verify Vogent callbacks over HTTPS.

Do not place certificate private keys in Git.

Nginx sets `client_max_body_size 256k`, aligned with the Flask `MAX_CONTENT_LENGTH` default. Increase both values together only after confirming Vogent payload requirements.

## 15. Production follow-up

A longer-lived production environment should move PostgreSQL to private RDS, use AWS Secrets Manager or Systems Manager Parameter Store, add automated encrypted backups, CloudWatch/OpenTelemetry, a load balancer and managed TLS, image scanning, patching, authentication, rate limiting, and CI/CD.
