# Devliqly Platform

The CRM and Expo Agent, which will be served at https://platform.devliqly.in. Separate from the marketing site and the blog CMS.

## Status

Not live yet. So far it has only run locally, with simulated WhatsApp messages and sends. It hasn't been tested against real Meta, Neon or Render.

| Phase | Scope | State |
|---|---|---|
| 0 | Accounts, login, customer separation | Done |
| 1 | WhatsApp inbox and durable job queue | Done; replies are a placeholder until phase 2 |
| 2 | Card capture: read a photo and save the company, contact and lead | Next |
| 3 | Rep actions: notes, corrections, voice notes | Planned |
| 4 | CRM screens | Planned |
| 5 | Follow-ups | Planned |
| 6 | Launch | Planned |

To do before real customers use it:

- Delete old webhook and job records automatically. They hold message text and phone numbers.
- Add rate limiting by IP address.
- Confirm the Graph API version (`GRAPH_API_VERSION`, default `v23.0`) is still current.

For the pilot, a phone number can belong to only one customer.

## Backend (`backend/`)

Python 3.12, FastAPI, SQLAlchemy (async), Alembic, Postgres.

```
app/main.py        app setup and security headers
app/db.py          sessions and the per-transaction security scope
app/models.py      tables
app/deps.py        current user and organization for a request
app/queue.py       durable background jobs, stored in Postgres
app/whatsapp/      reading Meta's webhooks, sending messages, background handlers
app/routers/       API endpoints
app/static/        minimal login and first-password pages
migrations/        schema history, including row-level security
tests/             run against a real Postgres
```

### How customers stay separated

Every customer is an `organization`. Separation is enforced by Postgres row-level security, not only by query filters:

- The app connects as `platform_app`, a role that can't bypass row-level security.
- Each transaction declares who it acts for with `set_scope()`. It lasts only for that transaction.
- With no scope, customer tables return nothing, so a forgotten scope fails closed.

**Every new table with customer data needs `organization_id`, `ENABLE` and `FORCE ROW LEVEL SECURITY`, and a policy.** `test_every_customer_table_is_protected` fails if one is missed.

### Run locally

You need Postgres and [uv](https://docs.astral.sh/uv/). Defaults expect Postgres on port 55432 with trust login, and can be changed in `.env` (see `backend/.env.example`). This creates a throwaway server:

```bash
initdb -D .pgdata -U postgres -A trust -E UTF8
pg_ctl -D .pgdata -o "-p 55432 -c listen_addresses=127.0.0.1" -l .pgdata/log.txt start
psql -h 127.0.0.1 -p 55432 -U postgres -c "CREATE DATABASE platform_dev" -c "CREATE DATABASE platform_test"
```

Then, from `backend/`:

```bash
uv sync
uv run alembic upgrade head
psql -h 127.0.0.1 -p 55432 -U postgres -c "ALTER ROLE platform_app LOGIN"
uv run python -m app.cli create-operator --name "Your Name" --email you@devliqly.in
uv run uvicorn app.main:app --port 8000
```

The API docs are at http://localhost:8000/docs outside production.

```bash
uv run pytest
```

```bash
uv run ruff check .
```

### WhatsApp flow

```
Meta → POST /webhooks/meta → verify signature → save once (unique event key) + queue a job, in one transaction → 200
                                                                                  ↓
                                        worker (in the same process): handle in order per rep, retry with backoff
```

- **Retries from Meta are harmless:** each message or receipt has a unique key, so repeats do nothing.
- **Crashes lose nothing:** a job and the data that caused it are saved together, and a dead worker's job restarts when its 5-minute lease ends.
- **Staff can see failures:** `GET /api/operator/jobs/summary`, `GET /api/operator/jobs/dead`, and `POST /api/operator/jobs/{seq}/retry`.
- **One known limit:** if the server dies after Meta accepts a message but before saving that, the message is sent again on retry. Meta offers no way to prevent this.

### Try it without Meta

Copy `.env.example` to `.env`, which turns on `WHATSAPP_DRY_RUN` so nothing is really sent. Add a rep with `POST /api/org/members` (see http://localhost:8000/docs), then, with the server running:

```bash
uv run python scripts/simulate_whatsapp.py text --sender +919876543210 --body "Hello"
```

```bash
uv run python scripts/simulate_whatsapp.py text --sender +919876543210 --message-id wamid.same --times 3
```

## Hosting

Render runs the backend (`devliqly-platform` in `/render.yaml`). It needs the paid Starter plan: a free instance sleeps, which would delay WhatsApp webhooks. Neon holds the data, in a project separate from the blog, in the Singapore region to sit next to Render.

1. **Neon:** create a project named `devliqly-platform` in AWS Asia Pacific (Singapore). In its SQL editor, create the app role with a long random password:

   ```sql
   CREATE ROLE platform_app LOGIN PASSWORD 'choose-a-long-random-password' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
   ```

   Create the role with SQL, not the Neon console: console-created roles can bypass row-level security.

2. **Render:** create a Web Service from this repository with:

   | Setting | Value |
   |---|---|
   | Language | Python |
   | Region | Singapore |
   | Branch | `main` |
   | Root Directory | `platform/backend` |
   | Build Command | `pip install uv && uv sync --frozen --no-dev` |
   | Start Command | `.venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'` |
   | Instance Type | Starter |
   | Health Check Path | `/healthz` |

   Environment variables:

   | Key | Value |
   |---|---|
   | `PYTHON_VERSION` | `3.12.10` |
   | `ENVIRONMENT` | `production` |
   | `PUBLIC_BASE_URL` | `https://platform.devliqly.in` |
   | `JWT_SECRET` | a long random value |
   | `MIGRATION_DATABASE_URL` | Neon's direct connection string for the owner role |
   | `DATABASE_URL` | the same direct string, with `platform_app` and its password as the user and password |
   | `WHATSAPP_LINE_ID` | the number's Phone Number ID, from the Meta app |
   | `WHATSAPP_ACCESS_TOKEN` | a permanent System User token from Meta |
   | `WHATSAPP_APP_SECRET` | the Meta app's App Secret |
   | `WHATSAPP_VERIFY_TOKEN` | any long random value |

   Use Neon's direct host (without `-pooler`) for both.

3. **Domain:** add `platform.devliqly.in` in Render, then a Cloudflare CNAME `platform` → `devliqly-platform.onrender.com`, proxy off.

4. **First login:** in the Render service's Shell, run this and open the link it prints:

   ```bash
   .venv/bin/python -m app.cli create-operator --name "Your Name" --email you@devliqly.in
   ```

5. **WhatsApp:** in the Meta app, set the webhook URL to `https://platform.devliqly.in/webhooks/meta` with your `WHATSAPP_VERIFY_TOKEN`, and subscribe to `messages`.

**Check:** https://platform.devliqly.in/readyz returns `{"status":"ready"}`, you can log in, and a WhatsApp message from a registered rep gets a reply.
