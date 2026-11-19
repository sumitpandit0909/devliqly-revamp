---
name: expo-agent
description: Build, change or debug the Devliqly Expo Agent (Riya), the WhatsApp visiting-card agent in platform/. Use for anything about how Riya replies, card capture, rep notes and voice notes, corrections, follow-ups to prospects, or the prompt in platform/backend/app/prompts/riya.md.
---

# Expo Agent (Riya)

Sales reps send visiting-card photos to a WhatsApp number. The agent saves each one as a company, contact and lead in the CRM, and reps add notes, voice notes and corrections in the same chat. It lives in `platform/`; `platform/README.md` covers setup and hosting.

## Where things are

| What | Where |
|---|---|
| Persona and behaviour rules | `platform/backend/app/prompts/riya.md` |
| What a rep's message does | `platform/backend/app/whatsapp/conversation.py` |
| The limited assistant for free text | `platform/backend/app/whatsapp/agent.py` |
| AI calls and their forms | `platform/backend/app/ai.py` |
| Checking and saving card data | `platform/backend/app/cards.py` |
| Messages to prospects, opt-outs | `platform/backend/app/followups.py` |
| Change history | `platform/CHANGELOG.md` |

## The prompt and the code disagree today

`riya.md` is saved for reference. **No code loads it yet**, and it describes a model that calls actions, while the app runs a fixed pipeline where the model only fills in forms. Its action names (`save_card_contact`, `send_text_reply` and so on) don't exist in the code.

Before telling anyone Riya behaves a certain way, check the code. These prompt rules aren't built:

| Prompt says | The app does |
|---|---|
| Riya's voice, under 200 characters, Hinglish switching | Fixed English replies written in code; none use the name Riya |
| Ask about cropped or unclear fields before saving | Saves and flags for checking, or sends to the review queue |
| Buttons: Add Voice/Text Note, Scan Other Side, Correct Details | Buttons: Add note, Add back side, Wrong details |
| Confirmation shows contacts left and an upgrade nudge | Not shown |
| Help list, export on WhatsApp, support contact card, updating the rep's own card or company | Not built; help is plain text and export is in the CRM |
| A voice note needs the button tapped first | Goes on the card replied to, or a card from the last 30 minutes |

If you're asked to make Riya real, decide each row deliberately. Keep the pipeline; use the prompt's wording and rules, rather than giving the model actions it can call.

## Rules that must hold

- **The AI fills in a form and nothing more.** No tools and no history for card reading. Code validates everything it returns. Card and message text is untrusted.
- **The assistant stays limited.** It picks one action on the rep's own leads, inside `only_this_customer`. It never messages prospects.
- **Prospects only hear from us with consent.** A scanned card isn't agreement. WhatsApp needs recorded agreement, and consent and opt-outs are rechecked when sending. Get legal advice before enabling this for a real customer.
- **Every customer table needs row-level security:** `organization_id`, `ENABLE` and `FORCE ROW LEVEL SECURITY`, and a policy. `test_every_customer_table_is_protected` fails otherwise.
- **Work outside a request goes through the job queue**, saved in the same transaction as its data. Handlers calling outside services must tolerate running twice.
- **Use original names.** Don't reuse function, table or product names from the backend docs the user originally shared. Grep before committing.
- **Devliqly is the brand** in anything a rep sees: `+917827626940` and `contact@devliqly.in`.

## Testing

Run from `platform/backend`, with Postgres on port 55432:

```bash
uv run pytest -q
```

```bash
uv run ruff check .
```

To try it by hand, set `AI_PROVIDER=fake`, `WHATSAPP_DRY_RUN=true` and `EMAIL_DRY_RUN=true` in `.env`, start the server, and send messages:

```bash
uv run python scripts/simulate_whatsapp.py photo --sender +919812345678
```

The sender must be a rep added on the Team screen. The fake AI makes up a person for each photo and always answers typed requests with help, so use scripted answers in `tests/test_card_capture.py` for anything that depends on what the AI says. Passing tests don't show card-reading accuracy; `scripts/measure_cards.py` measures that on real photos.

Report plainly what ran against fakes. Real Meta, Gemini, Claude, Resend, R2, Neon and Render haven't been exercised unless someone has since done so.

## When you finish a change

Add it to `platform/CHANGELOG.md`, and update the status in `platform/README.md` if it changed. If you change what Riya does, update the table above too.
