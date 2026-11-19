# Devliqly Platform

The CRM and Expo Agent, which will be served at https://platform.devliqly.in. Separate from the marketing site and the blog CMS.

See [CHANGELOG.md](CHANGELOG.md) for what changed and when. The Expo Agent's persona prompt is in [riya.md](backend/app/prompts/riya.md), though no code uses it yet.

## Status

All six build phases are written and tested, but it isn't live. It has only run locally, with simulated WhatsApp messages and a stand-in AI. Nothing has been tested against real Meta, Gemini, Claude, OpenRouter, Resend, R2, Neon or Render.

| Phase | Scope | State |
|---|---|---|
| 0 | Accounts, login, customer separation | Built |
| 1 | WhatsApp inbox and durable job queue | Built |
| 2 | Card capture: read a photo and save the company, contact and lead | Built; accuracy not measured |
| 3 | Rep actions: back of card, notes, corrections, voice notes, bursts, event tagging | Built |
| 4 | CRM screens: dashboard, contacts, review queue, events, team, chats, CSV export | Built |
| 5 | Follow-ups: outbox, email, WhatsApp templates, opt-outs | Built |
| 6 | Launch: plans, quotas, cost dashboard, data clean-up, rate limits | Built; the pilot itself is still to do |

Before real customers use it:

- **Measure card reading** on 50–100 real cards with `scripts/measure_cards.py`, and choose a provider. The target is under 12 seconds for most cards.
- **Get legal advice** on messaging prospects (Meta, TRAI, DPDP). Channels are off by default but send automatically once on, and WhatsApp only goes to people marked as having agreed.
- **Check the prices and versions in the settings** against the providers' current pages: `GRAPH_API_VERSION`, `GEMINI_MODEL`, `OPENROUTER_MODEL`, `OPENROUTER_VOICE_MODEL` and the `*_USD_PER_MTOK` values. Costs shown in the app are estimates from these.
- **Set up alerts.** Failures appear on the Staff screen and in Render's logs, but nothing notifies anyone yet.
- **Check rate limiting on Render.** Its limit is per IP address, using the address the proxy reports, which a determined attacker may be able to fake. The per-account login lockout still applies.

Known limits:

- A phone number can belong to only one customer's rep.
- Reps get a WhatsApp reply only within Meta's 24-hour window, which is always open because each reply answers their message. There are no reminders sent to reps yet.
- Voice notes need a model that hears audio. Claude and the default OpenRouter model (DeepSeek) don't, so voice notes go to `OPENROUTER_VOICE_MODEL` when `OPENROUTER_API_KEY` is set, or else to Gemini with `GEMINI_API_KEY`.
- Don't use OpenRouter's `:batch` models: they only work through OpenRouter's batch API, and the chat API answers 404. The default, `deepseek/deepseek-v4.1-flash-1017`, read a printed test card in about 5 seconds; real cards are untested.
- Card photos are kept until someone deletes the contact. There's no automatic expiry for them.
- Deleting a person doesn't clear raw webhook records, which hold message text until they're removed after `RETENTION_DAYS`.

## Backend (`backend/`)

Python 3.12, FastAPI, SQLAlchemy (async), Alembic, Postgres.

```
app/main.py        app setup and security headers
app/db.py          sessions and the per-transaction security scope
app/models.py      tables
app/deps.py        current user and organization for a request
app/queue.py       durable background jobs, stored in Postgres
app/whatsapp/      reading Meta's webhooks, sending messages, what a rep's messages do, the limited assistant
app/ai.py          the AI steps, each one call that fills in a form
app/cards.py       checking what the AI read, and saving contacts and leads
app/followups.py   the outbox for messages to prospects, and opt-outs
app/storage.py     private storage for card photos
app/maintenance.py deleting old records
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

### Card capture

```
photo → ⏳ → private storage → AI reads it (cards read in parallel) → code checks it → one transaction per rep, in order:
company, contact, lead, card, quota, follow-up → confirmation as a reply to that photo → ✅
```

- **The AI fills in a form and nothing more.** It has no tools and sees no history, so text on a card can't make it do anything. Code decides what's valid.
- **Duplicates:** one photo makes one card. One person makes one contact per customer, matched on phone or email, and one lead per event. A re-scan only fills gaps.
- **Unclear cards:** one with no name or no way to reach them waits in the review queue. A low-confidence one is saved and flagged.
- **What a rep's next message means** is decided by code: buttons, replying to a confirmation, and waiting states that expire after 10 minutes. Only other text and voice notes reach the AI, which picks one of a few actions on that rep's own leads, with the database limited to that customer. It can't message prospects.

### Follow-ups

Email is on by default with a standard message, and WhatsApp is off until a customer turns it on. After that, messages send automatically after the wait they set (60 minutes by default), and they can choose to approve each one instead. These are fixed templates, not AI-written messages, and each lead gets at most one message per channel, so a re-scan can't message someone twice and there's no second follow-up.

A card flagged for checking holds its message until someone clears the flag. A corrected address or name updates a message that's still waiting. Consent, the opt-out list and whether the channel is still on are checked again at the moment of sending.

WhatsApp follow-ups go only to people marked as having agreed, because a scanned card isn't agreement. A company whose reps ask every visitor can tick that once in the settings instead of on each lead.

A company can connect its own WhatsApp number on the Follow-ups screen, through Meta's Embedded Signup. WhatsApp follow-ups then go from that number, and the approved templates are listed to choose from. A number on the WhatsApp Business app stays there (Coexistence): the company keeps chatting in the app, Riya never answers on that number, and only STOP replies are acted on. The contacts and chat history sync is started, and its progress shown, but the synced chats aren't stored. This needs Meta's Tech Provider approval; see [docs/meta-app-review.md](docs/meta-app-review.md). Replying STOP, or the unsubscribe link in an email, opts someone out and blocks anything waiting.

### Try it without Meta

Copy `.env.example` to `.env`, which turns on `WHATSAPP_DRY_RUN` and `EMAIL_DRY_RUN` so nothing is really sent, and `AI_PROVIDER=fake`, which makes up a person for each photo. Log in at http://localhost:8000, add a rep on the Team screen, then, with the server running:

```bash
uv run python scripts/simulate_whatsapp.py text --sender +919876543210 --body "Hello"
```

```bash
uv run python scripts/simulate_whatsapp.py photo --sender +919876543210
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
   | `META_APP_ID`, `META_SIGNUP_CONFIG_ID` | the Meta app's ID and its Embedded Signup configuration, so customers can connect their own WhatsApp number |
   | `TOKEN_ENCRYPTION_KEY` | a Fernet key that encrypts customers' WhatsApp tokens; needed once `META_SIGNUP_CONFIG_ID` is set |
   | `AI_PROVIDER` | `gemini`, `anthropic` or `openrouter` |
   | `GEMINI_API_KEY` | from Google AI Studio; needed for voice notes whichever provider reads cards |
   | `ANTHROPIC_API_KEY` | from the Claude Console, if using `anthropic` |
   | `OPENROUTER_API_KEY` | from openrouter.ai, if using `openrouter`; also used for voice notes through `OPENROUTER_VOICE_MODEL` |
   | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | a new private R2 bucket with no public access or custom domain, and a token limited to it |
   | `EMAIL_FROM` | the address follow-ups come from |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` | to send through a mail server such as Gmail (`smtp.gmail.com`, 587, the Gmail address, an app password). `EMAIL_FROM` can be a Gmail alias added under "Send mail as". Personal Gmail allows about 500 emails a day. |
   | `RESEND_API_KEY` | instead of SMTP, from Resend with your sending domain verified |

   Use Neon's direct host (without `-pooler`) for both database connections. The app won't start in production without `R2_BUCKET`, so photos can't end up on Render's disk.

3. **Domain:** add `platform.devliqly.in` in Render, then a Cloudflare CNAME `platform` → `devliqly-platform.onrender.com`, proxy off.

4. **First login:** in the Render service's Shell, run this and open the link it prints:

   ```bash
   .venv/bin/python -m app.cli create-operator --name "Your Name" --email you@devliqly.in
   ```

5. **WhatsApp:** in the Meta app, set the webhook URL to `https://platform.devliqly.in/webhooks/meta` with your `WHATSAPP_VERIFY_TOKEN`, and subscribe to `messages`, `account_update`, `history`, `smb_app_state_sync` and `smb_message_echoes`.

6. **First customer:** on the Staff screen, add a customer and send the owner their link. They add an event and their reps.

**Check:** https://platform.devliqly.in/readyz returns `{"status":"ready"}`, you can log in, and a card photo from a registered rep gets saved and confirmed.
