# Acme Orders — SMS notifications

A small orders app that wants to send SMS notifications to customers
when their orders ship. Next.js 15 (App Router) on the front, FastAPI
on the back, Clerk for sign-in. **Surge is not wired yet** — that's
the agent's job.

## Stack

| Layer    | What |
|---|---|
| Frontend | Next.js 15 + React 19, Clerk (`@clerk/nextjs`) |
| Backend  | FastAPI, Clerk JWT verify, Postgres orders table |
| Workspace| pnpm monorepo: `web/` + `server/` |

## What's wired

- `POST /api/orders` — Clerk-gated; creates an order row in Postgres
- `GET  /api/orders/[id]` — order detail page
- "Mark shipped" button on the order detail page — calls
  `POST /api/orders/[id]/ship` which today just flips the status flag

## What's NOT wired yet

- **Surge account + campaign setup.** Before any SMS can send,
  we need a Surge account with an approved 10DLC campaign and an
  attached phone number. `POST /api/surge/setup` is a stub.
- **Send "your order shipped" SMS.** When an order is marked
  shipped, we should send a templated SMS to the customer's phone
  with their tracking URL. `POST /api/orders/[id]/ship` should
  trigger this. Today it doesn't.
- **Receive Surge delivery webhooks.** When Surge confirms
  `message.delivered`, we need to flag the order row so support
  can see the customer was notified. `POST /api/surge-webhook` is
  a stub.

## Run locally

```bash
pnpm install
cd server && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
cp server/.env.example server/.env
cp web/.env.local.example web/.env.local
pnpm dev   # web on :3000, server on :8000
```

Open http://localhost:3000, place an order, click **Mark shipped**.
Today the status flips but no SMS goes out.

## Agent task

Wire the three "NOT wired yet" items using **Surge** via the
fetchsandbox MCP server (`.mcp.json` is already configured — no
Surge API key needed, no Surge account required).

Run the curated workflows first to see the integration shape:

- `account_setup_with_campaign_and_number` — account, campaign,
  phone number provisioning
- `send_message_observe_delivery_lifecycle` — POST a message →
  GET it back → observe message.sent and message.delivered events
- `verification_lifecycle_opt_in_compliance` — TCPA-compliant
  opt-in code verification (use this for new contacts who haven't
  consented)

Mirror those shapes into `server/main.py`.
