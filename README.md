# DelTracking SMTP Notifier

DelTracking is a self-hosted delivery tracking and email notification system built with FastAPI, Vue 3, SQLite, and the NextSLS tracking API.

It provides a Chinese-language administration dashboard for managing tracking numbers, recipients, schedules, SMTP settings, query history, and failed email retries.

## Features

- Query shipments through the NextSLS tracking API.
- Store shipment metadata and the complete tracking timeline.
- Detect status changes and newly added tracking events.
- Establish a baseline on the first successful query without sending an email.
- Send recipient-specific HTML and plain-text email summaries.
- Retry failed messages through a transactional notification outbox.
- Run automatic queries on a configurable 5–1440 minute schedule.
- Pause scheduling or trigger individual and bulk queries manually.
- Audit every run, including per-shipment failures and notification status.
- Manage the service through a responsive Vue administration dashboard.

## Architecture

| Component | Technology | Responsibility |
| --- | --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy | API, authentication, tracking jobs, scheduling, and email delivery |
| Frontend | Vue 3, TypeScript, Vite | Administration dashboard |
| Database | SQLite in WAL mode, Alembic | Persistent configuration, tracking data, runs, and notification outbox |
| Web entry point | Nginx | Static SPA hosting and same-origin `/api` and `/health` proxying |
| Deployment | Docker Compose | Backend, web service, health checks, and persistent data volume |

The backend intentionally runs as a single Uvicorn worker because the scheduler is embedded in the application process. Do not scale multiple backend containers against the same database.

## Quick Start with Docker

Requirements:

- Docker Engine
- Docker Compose v2

Copy and edit the environment file:

```sh
cp .env.example .env
```

Generate independent values for `SESSION_SECRET` and `SMTP_ENCRYPTION_KEY`:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Set the generated values, a strong administrator password, and your NextSLS application ID in `.env`. Then build and start the service:

```sh
docker compose up -d --build
docker compose ps
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) for local HTTP access.

Check service health:

```sh
curl --fail http://127.0.0.1:8080/health/live
curl --fail http://127.0.0.1:8080/health/ready
```

The Compose entry point binds only to `127.0.0.1:8080`. Use an existing Nginx, Caddy, hosting panel, or Cloudflare Tunnel installation to provide a public domain and HTTPS.

For reverse proxy examples, backup and restore commands, upgrades, and troubleshooting, see the [server deployment guide](docs/deployment.md).

## Environment Variables

The main deployment variables are documented in [.env.example](.env.example):

- `SESSION_SECRET`: signs administrator sessions.
- `SMTP_ENCRYPTION_KEY`: Fernet key used to encrypt the SMTP password at rest.
- `ADMIN_USERNAME`: initial administrator username.
- `ADMIN_PASSWORD`: initial administrator password.
- `TRACKING_APP_ID`: NextSLS application identifier.
- `APP_TIMEZONE`: application and scheduler timezone; defaults to `Asia/Shanghai`.
- `SCHEDULE_INTERVAL_MINUTES`: initial query interval; defaults to `30`.
- `COOKIE_SECURE`: keep `true` behind HTTPS; use `false` only for local HTTP testing.

Never commit `.env`, database files, backups, SMTP credentials, or administrator passwords.

## Local Development

### Backend

```sh
cd backend
python -m pip install -e ".[dev]"
pytest
```

Run the API locally after configuring the required environment variables:

```sh
uvicorn app.main:app --reload
```

### Frontend

```sh
cd frontend
npm ci
npm run dev
```

The production frontend is served by Nginx in Docker. During local frontend development, requests to `/api/v1` must reach the FastAPI service through a compatible reverse proxy or development proxy.

## Testing

Backend checks:

```sh
cd backend
ruff check .
pytest
```

Frontend checks:

```sh
cd frontend
npm run lint
npm run typecheck
npm run test
npm run test:e2e
npm run build
```

The live NextSLS integration test is opt-in and uses tracking number `1024658760`. It asserts only the successful response structure and the presence of tracking events; it does not assume a fixed shipment status.

## Data and Operations

- Application data is stored in the named Docker volume `deltracking_data`.
- Alembic migrations run before the backend starts.
- Container logs are written to stdout and stderr.
- Recreating containers does not remove the SQLite database or operational history.
- `docker compose down --volumes` deletes the persistent database and must not be used unless data removal is intentional.

## Legacy Migration Status

The legacy `main.py`, `run.bat`, and `config.json` files are temporarily retained for the final legacy-data migration step. The Docker deployment does not use them.

## License

See [LICENSE](LICENSE).
