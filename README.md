# AirGuard Community Dashboard

AirGuard is a Django dashboard for current indoor PM2.5 readings in participating community buildings. It imports and archives Govee exports, calculates EPA PM2.5 AQI using hourly NowCast inputs, displays stale-data states, and sends verified forecast-threshold email alerts.

Forecast generation is intentionally still in development. The dashboard stores and displays forecast rows and the alert evaluator consumes fresh rows, but this repository does not create them.

## Implemented system

- Current building and sensor views, bounded hourly history, CSV download, stale-data handling, and 60-second change polling.
- English and Spanish interface text, keyboard-operable dialogs/tabs, semantic tables, and accessible chart descriptions.
- Authoritative building/sensor manifest in `dashboard/sensor_manifest.py`; unlisted sensors are disabled by `seed_db` rather than deleted.
- Token-authenticated Govee CSV and custom JSON ingestion with timestamp/value validation, raw-file archives, SHA-256 idempotency, and provenance links.
- IMAP ingestion of allowed-sender emails containing CSV or safe ZIP attachments, with raw `.eml` archives and message-id deduplication.
- Consent-based subscriptions with email verification, signed unsubscribe links, community and staff-only facility audiences, and per-IP signup throttling.
- AQI, WHO 24-hour PM2.5 guideline, and EPA 24-hour PM2.5 standard alert rules. WHO/EPA options use a building-level rolling 24-hour series and are health guidance, not regulatory determinations.
- Transactional alert events, a retrying database email outbox, unsubscribe/bounce/complaint suppression, and a token-protected Postmark-compatible event webhook.
- Windows launchers for VMOS exports, mailbox processing, alert evaluation, delivery, Task Scheduler installation, and Waitress production serving.
- Health endpoint at `/health/`, Django admin audit records, persistent scheduler logs, and GitHub Actions checks.

## Local setup (Windows Command Prompt)

```cmd
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Set a private `DJANGO_SECRET_KEY` in `.env`, then initialize the application:

```cmd
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_demo
.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. `seed_demo` is for local display/testing only. Production must use:

```cmd
.venv\Scripts\python.exe manage.py seed_db
```

Generate secrets without installing another package:

```cmd
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Production sensor manifest

| External ID | Building | Public name | Scheduled VMOS pull |
|---|---|---|---|
| BGC-A1 | Boys & Girls Club - Main | Big Classroom | No |
| BGC-A2 | Boys & Girls Club - Main | Small Classroom | No |
| BGC-A3 | Boys & Girls Club - Main | Kitchen | No |
| BGC-A4 | Boys & Girls Club - Main | Gym | No |
| BGC-B6 | Boys & Girls Club - Renovated | Lounge | Yes |
| BGC-B7 | Boys & Girls Club - Renovated | Classroom B7 | Yes |
| BGC-B8 | Boys & Girls Club - Renovated | Classroom B8 | Yes |
| RBC-1 | Robinson Center | Classroom | No |
| RBC-2 | Robinson Center | Theater | No |
| RBC-3 | Robinson Center | Lobby | No |

Change names, placements, buildings, or VMOS membership in the manifest, review the change, and rerun `seed_db`. The ingestion API never creates an unknown sensor automatically.

## Govee ingestion

An export filename must begin with its external sensor ID and `_export_`, for example `BGC-B6_export_202608241200.csv`. Supported timestamp/PM2.5 headers include the standard Govee export names.

For a local folder upload, place CSV files in `emails\` and run:

```cmd
set AIRGUARD_INGEST_TOKEN=the-same-token-as-the-dashboard
upload_govee_files.cmd
```

Files move to `emails\read\` only after a successful authenticated upload. The Bash equivalent is `emailscript.sh`. Set `AIRGUARD_UPLOAD_URL` when the dashboard is not local.

For mailbox ingestion, configure all `GOVEE_IMAP_*` settings and the exact `GOVEE_MAIL_ALLOWED_SENDER` in `.env`, then run:

```cmd
.venv\Scripts\python.exe manage.py process_govee_mail
```

Run this command on the dashboard server. It reads unread mail from the allowed Govee sender over IMAP, imports CSV/ZIP attachments directly into Django, and marks a message read only after successful or duplicate processing. Non-export Govee messages are ignored; failed exports remain unread for retry and do not prevent later messages from being processed. Accepted raw CSV and email evidence is retained under `var\media`; do not prune it without an approved retention policy.

## VMOS and scheduled processing

VMOS Cloud schedules the `v36 - ag email` workflow once per hour. `run_vmos_exports.cmd` remains available as a manual local fallback for the sibling `vmos_govee` workflow.

The preferred deployment runs mailbox ingestion on the dashboard host, where it writes directly to the production database and media storage. Schedule this command at 30 minutes past each hour using the host's cron or scheduled-job service:

```bash
30 * * * * cd /path/to/AirGuard-Community-Dashboard-2026 && .venv/bin/python manage.py process_govee_mail
```

On a Windows dashboard host, `run_govee_mail_ingestion.cmd` performs the same operation. `run_airguard_jobs.cmd` independently attempts these alert steps every run:

1. Evaluate verified subscriptions against fresh forecast rows.
2. Send due outbox messages.

`install_scheduled_tasks.cmd` is only for a Windows machine that actually hosts the dashboard. Run it from an elevated Command Prompt under the intended service account:

```cmd
install_scheduled_tasks.cmd
```

This creates an hourly Govee mailbox task at 30 minutes past the hour and a 15-minute alert task. It does not silently install tasks during application setup. Confirm their account, environment variables, history, and “run whether user is logged on” setting in Windows Task Scheduler. Logs are written to `logs\govee-mail-ingestion.log` and `logs\airguard-jobs.log`.

If the dashboard host cannot run scheduled jobs, `.github/workflows/govee-mail-ingestion.yml` can poll Fastmail and forward each CSV to the public HTTPS ingestion API. Configure these GitHub repository settings before enabling it:

- Actions variable `AIRGUARD_UPLOAD_URL`: the full `/api/v1/measurements/govee/` URL.
- Actions variable `AIRGUARD_ENABLE_GOVEE_INGESTION`: `true`.
- Actions secrets `GOVEE_IMAP_USER`, `GOVEE_IMAP_PASSWORD`, and `AIRGUARD_INGEST_TOKEN`.

The GitHub job runs at minute 30 every hour and can also be tested manually. It marks mail read only after the dashboard accepts every attachment. Do not enable it while host-side mailbox polling is active, and do not use it until the dashboard upload URL is publicly reachable over HTTPS.

## Email alerts

Alert evaluation is safe to rerun: event and outbox keys prevent duplicate messages for the same subscription/rule/projected date. AQI alerts use forecast values plus recent observations through the NowCast calculation. WHO/EPA alerts require at least 18 of the 24 rolling hourly building values.

The current hosted-mail setup uses one Fastmail account with separate role addresses:

- `airguard_alerts@fastmail.com` sends dashboard confirmation and alert messages.
- `airguard_vmos@fastmail.com` receives Govee CSV exports requested by VMOS.
- Django authenticates to `smtp.fastmail.com:587` with TLS and polls `imap.fastmail.com:993` with SSL using a revocable mail-only app password stored in the ignored `.env` file.

The Fastmail account is currently a trial and must be subscribed or migrated before the trial expires. Set `GOVEE_MAIL_ALLOWED_SENDER` to the exact sender observed on the first real Govee export; do not guess it. The account login, role-address inventory, and app credential are recorded only in `.env` and must not be committed.

Verification links expire after 48 hours by default (`AIRGUARD_VERIFY_MAX_AGE_HOURS`). Delivery jobs claim outbox rows atomically, retry with backoff, recover abandoned sends, and stop retrying after `AIRGUARD_EMAIL_MAX_ATTEMPTS`.

Useful commands:

```cmd
.venv\Scripts\python.exe manage.py evaluate_alerts
.venv\Scripts\python.exe manage.py send_outbox
```

Development prints email to the console. Production must configure a real SMTP provider, a verified `DEFAULT_FROM_EMAIL`, SPF/DKIM/DMARC DNS records, and provider monitoring. Point provider bounce/complaint events to:

```text
POST https://your-host/api/v1/email-events/postmark/
X-AirGuard-Webhook-Token: your AIRGUARD_POSTMARK_WEBHOOK_TOKEN
```

Test verification, one real alert, unsubscribe, bounce, and complaint flows before enabling public signup. Provider/DNS changes are external and are not performed by this repository.

## Production deployment

At minimum, set these `.env` values:

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<long unique secret>
DJANGO_ALLOWED_HOSTS=airguard.example.org
DJANGO_CSRF_TRUSTED_ORIGINS=https://airguard.example.org
AIRGUARD_SITE_URL=https://airguard.example.org
AIRGUARD_INGEST_TOKEN=<long unique token>
AIRGUARD_POSTMARK_WEBHOOK_TOKEN=<different long unique token>
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
```

Start the loopback-only Waitress service with:

```cmd
run_production.cmd
```

WhiteNoise serves collected, compressed, versioned static assets. Put IIS, nginx, or another TLS reverse proxy in front of `127.0.0.1:8000`; do not expose the development server. Back up `db.sqlite3` (or `DJANGO_DATABASE_PATH`) and `var\media` together, monitor disk space, and test restoration. SQLite is suitable only for this single-host, low-write deployment; move to a managed database before adding multiple web/job hosts.

Create facility staff accounts with `manage.py createsuperuser` or Django admin. `/facility-notifications/` requires a staff login and is also marked `noindex`.

Operational checks:

```cmd
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py check --deploy
.venv\Scripts\python.exe manage.py makemigrations --check
.venv\Scripts\python.exe manage.py test dashboard
```

`GET /health/` reports database availability, enabled-sensor count, latest reading/ingest times, and pending or failed email count. Use Django admin to inspect inbound messages, ingest batches, subscriptions, alert events, outbox rows, suppressions, and provider events.

## Remaining external or forecast work

- Build and validate the forecast producer, then write future `Forecast` rows with trustworthy `generated_at`, `source`, and `run_id` provenance. The dashboard ignores forecasts older than `AIRGUARD_FORECAST_MAX_AGE_HOURS`.
- Confirm production hosting/DNS/TLS, SMTP sender-domain verification, the inbound mailbox, secrets, backups, and monitoring.
- Run a supervised VMOS export for each BGC-B sensor and approve coordinates/device selection before activating Task Scheduler.
- Perform stakeholder review of sensor/building names, Spanish copy, alert wording, and the protected facility workflow.
- Run production accessibility and deliverability checks with the final domain/provider. Repository tests cannot certify those external systems.
