# Surge SMS demo — Friday partnership meeting brief

A 60–90s screencap showing an agent integrate Surge SMS notifications
into this brownfield Next.js + FastAPI orders app, using the
FetchSandbox MCP server, **without ever burning a real Surge API key**.

Recorded for the Friday 15-min partnership meeting with Surge.

---

## What this demo is supposed to prove

> An AI agent can wire a full Surge SMS flow (account + campaign +
> phone number provisioning, message send, delivery webhook handler)
> into an existing codebase in one prompt — happy path proven against
> a real-shape sandbox — without ever touching a Surge API key.

Four beats:
**1. This is the app (order ships, no SMS)** → **2. Add Surge** →
**3. Mark shipped → SMS fires** → **4. Delivery webhook received.**

---

## Setup (2 min)

```bash
cd ~/brownfield-surge-demo
pnpm install
cd server && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
cp server/.env.example server/.env
cp web/.env.local.example web/.env.local
pnpm dev   # web on :3000, server on :8000
```

The `.mcp.json` at repo root is already configured for the
`fetchsandbox` MCP server. No Surge API key, no Surge account,
no signup.

---

## The four-beat recording (for the partnership meeting)

### Beat 1 — "This is the app" (0–10s)
- Browser at `http://localhost:3000`
- Show: Acme Orders page, order #demo-order, **Mark shipped + notify customer** button
- Click it
- Inline status appears: `Shipped — but SMS notification not wired yet.`
- Caption overlay: **"customer never got their tracking SMS"**

### Beat 2 — "Add Surge" (10–50s)
- Cut to Cursor / Claude Code with the repo open
- Paste **one prompt**:
  ```
  Read README.md, then wire Surge SMS notifications via the
  fetchsandbox MCP server. Run the curated workflows first to see
  the integration shape, then implement the three handlers in
  server/main.py.
  ```
- MCP tool calls appear inline:
  - `mcp__fetchsandbox__list_specs filter="surge"` → Surge spec found
  - `mcp__fetchsandbox__list_workflows` → 4 curated workflows surface
  - `mcp__fetchsandbox__run_workflow account_setup_with_campaign_and_number` → 4/4 green
  - `mcp__fetchsandbox__run_workflow send_message_observe_delivery_lifecycle` → 3/3 green
- Agent writes `/api/surge/setup`, modifies `/api/orders/{id}/ship`, writes `/api/surge-webhook`
- Caption overlay: **"one prompt. no Surge API key. no signup."**

### Beat 3 — "SMS fires" (50–75s)
- Cut back to the browser
- Click **Mark shipped + notify customer** again
- Inline status: `Shipped + SMS sent (message_id=msg_...)`
- Caption overlay: **"customer just got their tracking SMS"**

### Beat 4 — "Webhook received" (75–90s)
- Cut to the server terminal
- Show: `POST /api/surge-webhook` log line — `message.delivered` arrived
- Show: order row updated with `sms_delivered_at` timestamp
- End frame, hold 3s:
  > **acme orders: shipped → sms → delivery webhook**
  > **one prompt. no Surge API key.**
  > **github.com/fetchsandbox/brownfield-surge-demo**

---

## Receipt URLs ready to drop in the deck

Fresh PROD URLs captured 2026-06-18 — pre-load these in browser tabs
before the meeting:

- `account_setup_with_campaign_and_number` (4/4 green, 68ms):
  https://fetchsandbox.com/runs/ebe5482c34?flow=run_12356b4c-553c-4ecb-b2b3-9dd55aa7a8a3

- `send_message_observe_delivery_lifecycle` (3/3 green, 55ms):
  https://fetchsandbox.com/runs/ebe5482c34?flow=run_0b259368-7ca6-490a-95e6-88f4f4faa948

- `contact_audience_blast_lifecycle` (5/5 green, 97ms):
  https://fetchsandbox.com/runs/ebe5482c34?flow=run_d82d6708-90c4-4ba2-8cee-c834eb3d1370

- `verification_lifecycle_opt_in_compliance` (3/3 green, 59ms):
  https://fetchsandbox.com/runs/ebe5482c34?flow=run_f98e96b3-96f9-4cae-a2b7-a034a4c73a27

---

## Recording guidelines

- **Length:** 60–90s, single take, no audio (caption overlays only)
- **Frame:** browser + IDE + terminal, pre-arranged
- **Resolution:** 1920×1080 minimum

---

## Known sharp edges

- **POSTs return 201 on Surge** (not 200). Our curated workflows
  expect_status=201 to match.
- **Webhook fan-out is engine-driven** — Surge's `message.delivered`
  fires automatically after `message.sent` in the happy path. To
  exercise failure modes, use `scenario=message_undeliverable` or
  `scenario=flaky_webhooks`.
- **Don't show the .env file on camera** — Reddit screenshots get
  scanned by leak detectors.

---

## What "good" looks like

- ≤ 90 seconds
- Zero manual code edits — everything written by the agent
- Visible Surge-shape SMS send + delivery webhook chain
- Final card shows the repo URL
