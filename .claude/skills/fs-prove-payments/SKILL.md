---
name: fs-prove-payments
description: 'Run a payments-API workflow against FetchSandbox and prove the contract works — no real keys, no partner onboarding, just the test. Delegate target for fs-router when the user is integrating Stripe, Paddle, Polar, or Square. Reads the spec''s brain.yaml for domain-aware test data + compliance notes; routes via the deterministic Phase 1 intent router; runs the workflow via /api/mcp/quickrun; streams the trace + applicable compliance notes to chat. NO files written to the user repo — console-only. Call this skill (not run_workflow directly) when you want the proof to include test card selection by geo, 3DS coverage flagging, and webhook-event verification. Use when the user asks to test/run/verify a payments integration end-to-end after fs-router has resolved the spec + workflow.'
---

# fs-prove-payments — Proof-by-FetchSandbox for payments specs

## Identity

You are the **proof step** in the integration flow. fs-router (and its
persona team) has decided what to integrate; you make the contract
real by running the workflow on a FetchSandbox sandbox + surfacing
exactly what the dev needs to handle in their prod code.

Today's coverage: **Stripe** (full brain.yaml). Future: Paddle, Polar,
Square — same shape, same skill, no rewrite per spec.

## When you're invoked

Three call shapes from fs-router (or a power user invoking directly):

1. **Routed already** — caller passes `spec` + `workflow` + (optional)
   `discovery_answers` from the brain.yaml conversation. Skip to Step 2.
2. **Intent only** — caller passes a free-form intent string. You route
   first via `mcp__fetchsandbox__guide`, then proceed.
3. **Workflow named explicitly** — caller passes `spec` + `workflow`
   without any brain dialogue. Run it; surface compliance notes after.

## Absolute rules

1. **NO files written.** No `.fetchsandbox/*.md`, no diff applies, no
   `Write`/`Edit` calls. All output streams to chat. The timeline URL
   on the FetchSandbox dashboard is the artifact.
2. **Brain-aware test data.** Before running, fetch the spec's
   brain.yaml (`GET /api/specs/{spec}/brain`). Use the
   `discovery_answers` (or pick `default`s) to select the right test
   card library — running `accept_payment` for an EU customer must use
   `cards_eu.happy` (3DS-compatible), not `cards_us.happy`.
3. **Compliance notes surface AFTER, not before.** Run the workflow,
   show success, THEN list the brain.yaml compliance_notes whose
   `applies_when` matches the caller's `discovery_answers`. Don't
   pre-warn — that's lecturing. Surface the gotchas attached to "what
   to handle before going to prod".
4. **One MCP approval per run.** Use `mcp__fetchsandbox__quickrun` for
   single workflows (bundled spec, no import needed). For multi-workflow
   runs, use `mcp__fetchsandbox__run_all_workflows`. NEVER loop
   `run_workflow` — that's one IDE approval per workflow, which the dev
   experiences as a captcha barrage.

## Procedure

### Step 1: Route (skip if already routed)

If caller already passed `spec` + `workflow`, skip this step.

Otherwise call:

```
mcp__fetchsandbox__guide(intent="<the caller's intent string>")
```

Read back:
- `spec` — must be one of: `stripe`, `paddle`, `polar`, `square`
  (if not a payments spec, hand control back to fs-router with a note)
- `workflow` — the resolved workflow id
- `confidence` — if < 0.5, hand back; don't guess
- `next_question` — if present and unanswered, this skill SHOULDN'T be
  the one to ask it (that's fs-router's job). Hand control back with
  the question so fs-router can elicit conversationally.

### Step 2: Fetch the spec's brain (for compliance + test data context)

```
GET https://fetchsandbox.com/api/specs/{spec}/brain
```

Pull from response:
- `test_data` — the card libraries (e.g. `cards_us`, `cards_eu`)
- `compliance_notes` — list with `applies_when`, `severity`, `note`
- `step_narration` — keyed by step.name; use when describing the trace

If the endpoint returns 404, the spec has no brain.yaml yet. Run the
workflow without brain enrichment — but tell the dev:

> "Quick note: this spec doesn't have a domain playbook yet, so I can't
> flag compliance gotchas. The proof still works; you'll want to review
> the spec's docs manually before prod."

### Step 3: Run the workflow

```
mcp__fetchsandbox__quickrun(spec="<spec>", workflow="<workflow>")
```

If the response has `scenario` set (e.g. running `accept_payment` with
`scenario: payment_declined`), call with scenario param if your MCP
version supports it. Otherwise the default scenario runs.

Capture from the response:
- `steps[]` — each with `name`, `method`, `path`, `status`,
  `request_body`, `response_body`, `webhook_events`
- `sandbox_id` — for the timeline URL
- `proof` — the 5-section receipt: `all_passed`, `reconciliation_fields`,
  `effects` (matched/expected), `constraints`, `invariants`,
  `failure_classes`

### Step 4: Stream the trace + proof to chat (console-only)

**Use this STRUCTURED format. Tables for everything except the
resource-flow arrow chain. Never raw MCP tool JSON, never a prose
"what this tells you" paragraph.**

```markdown
## Proof: <workflow_name>

| Workflow | Result | Steps | Duration | Webhooks | Sandbox |
|---|---|---|---|---|---|
| <workflow_name> | ✅ Passed / ❌ Failed | <K>/<N> | <ms> | <fired>/<expected> verified | [<sandbox_id>](<timeline_url>) |

**What this proves:** <one-line — connect the proof to a specific
contract the user's code depends on, e.g. "your /create-payment-intent
→ confirm → capture → webhook contract end-to-end">.

**Resource flow:**
\`\`\`
<resource arrow chain: cus_X → pi_Y (<state>) → confirm → <state>
  → capture → <state> ✓>
\`\`\`

---

## Code review — `<user file>`

| Status | Webhook event | Currently handled? | Prod analog |
|---|---|---|---|
| ✅ | <event_type> | Yes — `<file:line>` | <how user's code consumes it> |
| ⚠️ | <event_type> | **No** | <what they'll miss in prod if unhandled> |
| ⏭️ | <event_type> | N/A | <why skipped, e.g. "3DS — skipped, you picked US-only"> |

(Repeat per relevant webhook event from the brain. Use ✅ for handled,
⚠️ for missing-but-important, ⏭️ for skipped-by-config.)

---

## Compliance gotchas (filtered for <user's discovery_answers>)

| Severity | Note |
|---|---|
| `[blocker]` | <first line of n.note, trimmed> |
| `[warning]` | <first line of n.note, trimmed> |

**Skipped:** <comma-list of note ids that didn't match config, with
parenthetical reason — e.g. "eu_3ds_requirement (US only)">

(If 0 notes apply: `"Brain flags no compliance blockers for this combo. Ship clean."`)

---

> **Honest limit:** <only when there's a real gap — e.g. happy-path only
> when failure scenarios are available, or MCP tool can't reach a
> feature. Frame as actionable: "say *'now test payment_declined'* if
> you want failure proof too.">
```

**Anti-patterns — never do these:**

- ❌ Pasting raw MCP tool JSON (`"_truncated": true`, `"preview": "{\n..."`)
  into chat. The trimmed summary IS the output; canvas URL has full detail.
- ❌ Prose "What this tells you about your code:" paragraph. Use the
  **Code review** table — rows per webhook event with ✅/⚠️/⏭️ status.
- ❌ Bullet list of webhook events with inline descriptions. Each event
  is a TABLE ROW with Status / Event / Currently-handled / Prod-analog
  columns. Scannable in 5 seconds vs reading prose.
- ❌ Plain "Honest limitation: ..." paragraph. Use a `>` blockquote with
  bold `**Honest limit:**` — visually distinct from chat prose.
- ❌ The verbose `reconciliation: / effects: / constraints: / invariants:`
  block. Replaced by the proof table + arrow chain — denser, more readable.
- ❌ Listing steps as bullet points instead of an arrow chain. Bullets
  read as inventory; arrows read as a story.

**Rules — always do these:**

- ✅ Resource IDs in the arrow chain (cus_X, pi_Y, ch_Z, re_W, evt_V).
  Real IDs from the response, not placeholders.
- ✅ Reference user-repo `file:line` numbers when proposing follow-ups
  (use the introspect output from fs-router Step 2). Don't say "your
  webhook handler" — say "`server/main.py:30-37`".
- ✅ Frame "the one that matters" — connect specific test data to the
  user's prod code. Example: *"charge.failed fired ✓ (the one that
  matters — your `payment_intent.payment_failed` handler is the prod
  analog)."*
- ✅ Use the brain.yaml's `step_narration` to enrich the arrow chain
  where helpful. E.g. on Confirm the PaymentIntent: append a brief
  *"(EU + 3DS cards return `requires_action` here — client must handle
  the redirect)"*.
- ✅ Be HONEST about gaps — if the MCP tool doesn't reach a feature
  (scenarios, per-card variants), say so + point to the dashboard URL.

### Step 4.5: Scenario-didn't-materialize honest report (when applicable)

When the user asked for a failure scenario (`payment_declined`,
`insufficient_funds`, `fraud_hold`, etc.) but the curated workflow's
deterministic steps still produced a passing trace — the scenario param
was accepted but overridden — render this specific format instead of
the Step 4 happy-path proof:

```markdown
## Scenario `<scenario_name>` didn't materialize

| Asked for | Got | Why |
|---|---|---|
| `<scenario>` | `<terminal_state, e.g. succeeded>` | <one-line — usually "curated workflow's deterministic steps override the scenario param — workflow picks a guaranteed-pass test card"> |

**Resource flow (looks identical to happy path):**
\`\`\`
<arrow chain> (expected: <expected_terminal_state>)
\`\`\`

### How to actually exercise the `<target_branch>` branch

| Method | Command | What it proves |
|---|---|---|
| **CLI forward + declined card** | `stripe listen --forward-to localhost:<port>/<webhook_path>`, then trigger with declined test card | Real PaymentIntent flow exercises `<file:line>` end-to-end |
| **Synthetic webhook trigger** | `stripe trigger <event_type>` | Fires a realistic event payload at the handler — no real PaymentIntent needed |

> **Why two options:** the first proves the FULL path (intent → confirm
> → decline → webhook → your handler); the second is faster but skips
> the upstream PaymentIntent flow.

[ End with `AskUserQuestion`: which method to try ]
```

**Anti-patterns specific to this case:**

- ❌ Pretending the scenario worked when it didn't. The trace shows
  `succeeded`; don't paper over that.
- ❌ Prose "Two ways to actually prove..." paragraph + numbered list.
  Tables make the trade-off scannable.
- ❌ Skipping the `expected:` callout in the arrow chain. The user
  should see at a glance that the terminal state didn't match the
  scenario they asked for.

### Step 5: Filter + surface applicable compliance notes

For each `compliance_notes[i]` in the brain:
- If `applies_when` is empty → always applies, show it
- Otherwise, check each key: does the caller's `discovery_answers`
  (or the run's resolved context) match? All keys must match.

For matching notes, render as a markdown table — composes cleanly into
the fs-router Step 7 rich wrap-up report:

    **Compliance gotchas (filtered for <user's discovery_answers>):**

    | Severity | Note |
    |---|---|
    | `[blocker]` | <first line of n.note, trimmed> |
    | `[warning]` | <first line of n.note, trimmed> |

    Skipped (didn't match config): <list of suppressed note ids>

If 0 notes apply: `"Brain flags no compliance blockers for this combo. Ship clean."`

### Step 6: Close, don't chain

Hand control back to the caller (fs-router or the user directly). End
your output with a one-line acknowledgment, NO prose questions:

```
Proof complete.
```

**Do NOT** emit "Hand back for code walkthrough" or "What next?" or
"Continue?" prose. fs-router (or the user) takes it from here — fs-router's
Step 6 fires a `AskUserQuestion` "Next move" picker immediately on return.
Your "Proof complete." is the last text the user sees from you; the picker
is the next interaction.

Do NOT propose code changes (that's fs-propose-changes' job). Do NOT
auto-suggest next workflows. Do NOT ask "what next?" — your job is the
proof, not the conversation.

## Where this skill calls others

- `mcp__fetchsandbox__guide` — for Step 1 if not pre-routed
- `mcp__fetchsandbox__quickrun` — for Step 3 (bundled specs only)
- `mcp__fetchsandbox__run_all_workflows` — for multi-workflow proofs
- `mcp__fetchsandbox__run_workflow` — only as fallback if quickrun
  unavailable; never loop this for multi-workflow

## What this skill does NOT do

- Ask discovery questions (that's fs-router/`bmad-advanced-elicitation`)
- Walk the user through code changes (that's fs-propose-changes)
- Write any file
- Run workflows for non-payments specs — handing back to fs-router
- Run a workflow it can't first verify exists via guide or list_workflows

## Anti-patterns

- ❌ Surfacing compliance notes BEFORE running — that's lecturing
- ❌ Calling `run_workflow` in a loop instead of `run_all_workflows`
- ❌ Writing a markdown report to summarize the run
- ❌ Asking the user a question — your job is execution, not dialogue
- ❌ Suggesting "want to also try X?" at the end — hand back, don't chain
