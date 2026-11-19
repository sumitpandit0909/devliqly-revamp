# Changelog

Changes to the Devliqly Platform (the CRM and Expo Agent). The marketing site and blog CMS aren't covered here.

Nothing has been deployed yet, so there are no released versions. Everything so far has run only locally, with simulated WhatsApp messages and a stand-in AI.

## Unreleased

### 2026-11-17: Customers' own WhatsApp numbers

**Added**

- A "Your WhatsApp number" panel on the Follow-ups screen. A company connects its number through Meta's Embedded Signup, including a number that stays on the WhatsApp Business app (Coexistence). WhatsApp follow-ups then go from that number, with its approved templates to pick from. Migration `0011`.
- The number's Meta token is stored encrypted (`TOKEN_ENCRYPTION_KEY`) and never sent to the browser. One number belongs to one company.
- Webhook events are routed by number. On a company's number Riya stays silent and only STOP replies are acted on, as an opt-out for that company. Chat history sent during the Coexistence sync is never treated as new messages, and only its progress is kept.
- Meta's disconnect and reconnect events update the number's status. A disconnected number isn't used, and follow-ups fall back to Devliqly's number.
- `docs/meta-app-review.md`: what to submit to Meta to become a Tech Provider.

### 2026-11-12: WhatsApp permission asked at the stall

**Added**

- A follow-up setting, "Our reps ask every visitor for permission to message them on WhatsApp". When ticked, each new card counts as agreed, so nobody has to tick each lead. The lead's history records why. Someone who opted out stays opted out, and a rep can still untick one lead. Migration `0010`.

### 2026-11-11: Email through Gmail

**Added**

- Follow-up email can go through any SMTP server, such as Gmail with an app password, instead of Resend. Set `SMTP_HOST`, `SMTP_USERNAME` and `SMTP_PASSWORD`. When `SMTP_HOST` is set it's used, otherwise Resend. A wrong password or a refused address marks the follow-up failed straight away, and a busy or unreachable server is retried.

### 2026-11-11: Email follow-ups on by default

**Changed**

- Email follow-ups now start on, with a standard message, for customers who haven't saved their own settings. They send automatically after the 60-minute wait. Customers who already saved settings keep them. WhatsApp follow-ups still start off, because they need an approved Meta template and each person's agreement. Migration `0009`.

### 2026-11-11: OpenRouter

**Added**

- `AI_PROVIDER=openrouter` reads cards and messages through OpenRouter, defaulting to `deepseek/deepseek-v4.1-flash-1017`. It asks for a strict JSON schema and only routes to providers that support one. The `:batch` variant was tried first, but OpenRouter only serves it through its batch API.
- Voice notes go to `OPENROUTER_VOICE_MODEL` (default `google/gemini-2.5-flash-lite`) when the main model can't hear, so Gemini's own key is no longer required.

### 2026-11-05: Automatic follow-ups

**Changed**

- Once a customer turns on email or WhatsApp follow-ups, messages send automatically after the wait they set. Approving each one is now an option you tick off. Migration `0008`.

**Added**

- A card flagged for checking holds its message until someone clears the flag.
- Correcting an address or name updates a message that's still waiting.
- Turning email off stops emails already waiting, as WhatsApp already did.

### 2026-11-05: Fixes from testing both sides

**Fixed**

- The Chats screen could show a reply before the message it answered, because both were saved with the same time. Migration `0007` gives each chat message its real save time.
- Deleting a person left chat lines naming them, and the rep's notes about them. Deleting now removes any chat mentioning their name, phone, email or card, and the message each of those replies answered.

**Still true**

- Raw webhook records keep message text until they're cleared after `RETENTION_DAYS`, so a deleted person's note can stay there until then.

### 2026-11-05: Riya prompt and project skill

**Added**

- The Riya persona and behaviour prompt, adapted from the original agent prompt, in `backend/app/prompts/riya.md`. No code loads it yet.
- An `expo-agent` skill in `.claude/skills/`, including where the prompt and the app currently differ.
- This changelog.

**Changed from the original prompt**

- Support details now use Devliqly: `+917827626940` and `contact@devliqly.in`.
- Actions and fields have new names, and "client" is now "company".
- Removed a hardcoded subscription ID and the mention of Firebase links.
- Company name, address and website can now be corrected, as the app allows.
- New rules: card and message text is data rather than instructions, and Riya never promises to message a prospect.
- Fixed typos and an inconsistent action name.

### 2026-11-04: Phases 2 to 6

**Added**

- **Card capture:** private photo storage, one AI call per card (Gemini or Claude), checks in code, and one transaction that saves the company, contact, lead, card, quota and follow-ups. The confirmation is a reply to the photo.
- **Rep actions:** back of card, notes, corrections, voice notes, several cards at once, event tagging, and a limited assistant for free text.
- **CRM screens:** dashboard, contacts with card photos and timeline, review queue, follow-ups, events, team, chats, a staff screen and CSV export.
- **Follow-ups:** an outbox with approval, retries, email through Resend and WhatsApp templates. Includes consent tracking, an opt-out list, STOP replies and an unsubscribe link. Off by default.
- **Launch tools:** plans with card and seat limits, estimated AI costs, automatic deletion of old records, login rate limits, and deleting a person on request.
- `scripts/measure_cards.py`, to compare AI providers on real card photos.

**Changed**

- `app/whatsapp/jobs.py` became `app/whatsapp/conversation.py`, and the placeholder reply was replaced by the real flow.
- Production now refuses to start with the fake AI, email dry run, or no private R2 bucket.

**Not done yet**

- Card-reading accuracy hasn't been measured on real cards.
- Real Meta, Gemini, Claude, Resend, R2, Neon and Render haven't been tested.
- Legal review of messaging prospects, alerts, and the pilot itself.

### 2026-11-04: Phase 1, WhatsApp inbox

**Added**

- A signed Meta webhook that saves each event once, so repeat deliveries are harmless.
- A durable job queue in Postgres, with per-rep ordering, retries and crash recovery. It replaces the Inngest idea from the original plan.
- Conversations, delivery status, and a daily notice to unregistered numbers.
- A script that simulates WhatsApp messages locally.

### 2026-11-04: Phase 0, foundation

**Added**

- A FastAPI backend with Postgres and Alembic migrations.
- Customer separation enforced by Postgres row-level security.
- Login with short-lived tokens, rotating refresh tokens, account lockout and first-password links.
- Customers, team roles and expo events, with minimal login pages.
