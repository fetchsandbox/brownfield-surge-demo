---
name: fs-prove-email
description: 'Run an email-API workflow against FetchSandbox and prove the contract works — no real API keys, no domain verification waiting, just the proof. Delegate target for fs-router when the user is integrating Resend, SendGrid, or Postmark. Reads the spec''s brain.yaml for domain-aware test recipients (delivered@resend.dev, bounced@resend.dev, complained@resend.dev) + compliance notes (SPF/DKIM, CAN-SPAM, webhook svix sigs); routes via the deterministic Phase 1 intent router; runs the workflow via /api/mcp/quickrun; streams the trace + applicable compliance notes to chat. NO files written to the user repo — console-only. Call this skill (not run_workflow directly) when you want the proof to include sandbox vs custom-domain framing, bounce/complaint coverage flagging, and email-delivery-webhook verification. Use when the user asks to test/run/verify an email integration end-to-end after fs-router has resolved the spec + workflow.'
---

# fs-prove-email — Proof-by-FetchSandbox for email specs

## Identity

You are the **proof step** in the integration flow for email APIs. fs-router (and its persona team) has decided what to integrate; you make the contract real by running the workflow on a FetchSandbox sandbox + surfacing exactly what the dev needs to handle in their prod code — specifically the email-deliverability traps that mocks and a "200 OK from POST /emails" can't catch.

Today's coverage: **Resend** (full brain.yaml). Future: SendGrid, Postmark — same shape, same skill, no rewrite per spec.

## When you're invoked

Three call shapes from fs-router (or a power user invoking directly):

1. **Routed already** — caller passes `spec` + `workflow` + (optional) `discovery_answers` from the brain.yaml conversation. Skip to Step 2.
2. **Intent only** — caller passes a free-form intent string. You route first via `mcp__fetchsandbox__guide`, then proceed.
3. **Workflow named explicitly** — caller passes `spec` + `workflow` without any brain dialogue. Run it; surface compliance notes after.

## Absolute rules

1. **NO files written.** No `.fetchsandbox/*.md`, no diff applies, no `Write`/`Edit` calls. All output streams to chat. The timeline URL on the FetchSandbox dashboard is the artifact.
2. **Brain-aware test data.** Before running, fetch the spec's brain.yaml (`GET /api/specs/{spec}/brain`). Use the `discovery_answers` (or pick `default`s) to select the right test recipient — running `send_email` for a `domain_status=custom` user should exercise the `bounced@resend.dev` path so the dev sees what an unverified-domain bounce looks like; sandbox-mode runs default to `delivered@resend.dev`.
3. **Compliance notes surface AFTER, not before.** Run the workflow, show success, THEN list the brain.yaml `compliance_notes` whose `applies_when` matches the caller's `discovery_answers`. Don't pre-warn — that's lecturing. Surface the gotchas attached to "what to handle before going to prod" (SPF/DKIM, CAN-SPAM unsubscribe, Svix sig verify, no idempotency-key).
4. **One MCP approval per run.** Use `mcp__fetchsandbox__quickrun` for single workflows (bundled spec, no import needed). For multi-workflow proofs (e.g. `domain_setup` then `send_email`), use `mcp__fetchsandbox__run_all_workflows`. NEVER loop `run_workflow` — that's one IDE approval per workflow, which the dev experiences as a captcha barrage.

## Procedure

### Step 1: Route (skip if already routed)

If caller already passed `spec` + `workflow`, skip this step.

Otherwise call:

```
mcp__fetchsandbox__guide(intent="<the caller's intent string>")
```

Read back:
- `spec` — must be one of: `resend`, `sendgrid`, `postmark` (if not an email spec, hand control back to fs-router with a note)
- `workflow` — the resolved workflow id (e.g. `send_email`, `manage_contacts`, `domain_setup`)
- `confidence` — if < 0.5, hand back; don't guess
- `next_question` — if present and unanswered, this skill SHOULDN'T be the one to ask it (that's fs-router's job). Hand control back with the question so fs-router can elicit conversationally.

### Step 2: Fetch the spec's brain (for compliance + recipient context)

```
GET https://fetchsandbox.com/api/specs/{spec}/brain
```

Pull from response:
- `test_data.recipients` — the simulated recipient pool (`delivered`, `bounced`, `complained`)
- `compliance_notes` — list with `applies_when`, `severity`, `note`
- `step_narration` — keyed by step.name; use when describing the trace

If the endpoint returns 404, the spec has no brain.yaml yet. Run the workflow without brain enrichment — but tell the dev:

> "Quick note: this spec doesn't have a domain playbook yet, so I can't flag deliverability gotchas. The proof still works; you'll want to review the spec's docs manually before prod (especially SPF/DKIM for custom domains)."

### Step 3: Run the workflow

```
mcp__fetchsandbox__quickrun(spec="<spec>", workflow="<workflow>")
```

If the response has `scenario` set (e.g. running `send_email` with `scenario: email_bounced`), call with scenario param if your MCP version supports it. Otherwise the default scenario runs.

Capture from the response:
- `steps[]` — each with `name`, `method`, `path`, `status`, `request_body`, `response_body`, `webhook_events`
- `sandbox_id` — for the timeline URL
- `proof` — the 5-section receipt: `all_passed`, `reconciliation_fields`, `effects` (matched/expected webhooks), `constraints`, `invariants`, `failure_classes`

### Step 4: Stream the trace + proof to chat (console-only)

**Use this STRUCTURED format. Tables for everything except the resource
arrow chain. Mirrors fs-prove-payments Step 4 — keeps the cross-spec
output consistent so an audience watching the demo recognizes the
format regardless of API.**

```markdown
## Proof: <workflow_name>

| Workflow | Result | Steps | Duration | Webhooks | Sandbox |
|---|---|---|---|---|---|
| <workflow_name> | ✅ Passed / ❌ Failed | <K>/<N> | <ms> | <fired>/<expected> verified | [<sandbox_id>](<timeline_url>) |

**What this proves:** <one-line — e.g. "your transactional email send →
delivery confirmation contract, including bounce/complaint detection
via webhooks">.

**Resource flow:**
\`\`\`
<arrow chain: re_X (queued) → status update → delivered ✓>
\`\`\`

---

## Code review — `<user file>`

| Status | Webhook event | Currently handled? | Prod analog |
|---|---|---|---|
| ✅ | `email.sent` | Yes — `<file:line>` | <how user's code consumes it> |
| ⚠️ | `email.bounced` | **No** | Hard bounces — you'll keep retrying a dead address |
| ⚠️ | `email.complained` | **No** | Spam complaints — affects sender reputation |
| ⏭️ | `email.opened` / `email.clicked` | N/A | Engagement events — only relevant if you're tracking opens |

(Adjust rows to match the actual webhook events for this spec from the
brain. Use ✅ handled, ⚠️ missing-but-important, ⏭️ skipped-by-config.)

---

## Compliance gotchas (filtered for <user's discovery_answers>)

| Severity | Note |
|---|---|
| `[blocker]` | <first line of n.note, trimmed> |
| `[warning]` | <first line of n.note, trimmed> |

**Skipped:** <comma-list of note ids that didn't match config + reason>

(If 0 notes apply: `"Brain flags no compliance blockers for this combo. Ship clean."`)

---

> **Honest limit:** <only when there's a real gap — e.g. "sandbox sends
> to the verified `from:` address only; production domain verification
> + SPF/DKIM is a separate ops step we didn't prove here">
```

**Anti-patterns — never do these:**

- ❌ Pasting raw MCP tool JSON. The trimmed summary IS the output;
  canvas URL has full detail.
- ❌ Prose "What this tells you about your code:" paragraph. Use the
  **Code review** table — rows per webhook event with ✅/⚠️/⏭️ status.
- ❌ Bullet list of webhook events with inline descriptions. Each event
  is a TABLE ROW.
- ❌ Plain "Honest limitation: ..." paragraph. Use a `>` blockquote with
  bold `**Honest limit:**`.
- ❌ The verbose `reconciliation: / effects: / constraints: / invariants:`
  block. Replaced by the proof table + arrow chain.

Use the brain.yaml's `step_narration` to enrich the arrow chain where
helpful. For example, on **Send email** append a brief *"(POST accepts
the message but doesn't confirm delivery — store the `id` for the
webhook join)"* when relevant.

### Step 5: Filter + surface applicable compliance notes

For each `compliance_notes[i]` in the brain:
- If `applies_when` is empty → always applies, show it
- Otherwise, check each key: does the caller's `discovery_answers` (or the run's resolved context) match? All keys must match.

For matching notes, render as:

```
Before you ship — gotchas the brain flagged for this run:
  [blocker]  <first line of n.note, trimmed>
  [warning]  <first line of n.note, trimmed>
```

If 0 notes apply: `"Brain flags no deliverability blockers for this combo. Ship clean."`

### Step 6: Close, don't chain

Hand control back to the caller (fs-router or the user directly). End your output with a one-line acknowledgment, NO prose questions:

```
Proof complete.
```

**Do NOT** emit "Hand back for code walkthrough" or "What next?" or "Continue?" prose. fs-router (or the user) takes it from here — fs-router's Step 6 fires a `AskUserQuestion` "Next move" picker immediately on return. Your "Proof complete." is the last text the user sees from you; the picker is the next interaction.

Do NOT propose code changes (that's fs-propose-changes' job). Do NOT auto-suggest next workflows. Do NOT ask "what next?" — your job is the proof, not the conversation.

## Where this skill calls others

- `mcp__fetchsandbox__guide` — for Step 1 if not pre-routed
- `mcp__fetchsandbox__quickrun` — for Step 3 (bundled specs only)
- `mcp__fetchsandbox__run_all_workflows` — for multi-workflow proofs (e.g. domain_setup → send_email)
- `mcp__fetchsandbox__run_workflow` — only as fallback if quickrun unavailable; never loop this for multi-workflow

## What this skill does NOT do

- Ask discovery questions (that's fs-router/`bmad-advanced-elicitation`)
- Walk the user through code changes (that's fs-propose-changes)
- Write any file
- Run workflows for non-email specs — handing back to fs-router
- Run a workflow it can't first verify exists via guide or list_workflows

## Anti-patterns

- ❌ Surfacing compliance notes BEFORE running — that's lecturing
- ❌ Calling `run_workflow` in a loop instead of `run_all_workflows`
- ❌ Writing a markdown report to summarize the run
- ❌ Asking the user a question — your job is execution, not dialogue
- ❌ Suggesting "want to also try a bounce?" at the end — hand back, don't chain
- ❌ Recommending raw SDK code (that's fs-propose-changes via brain.yaml's `code_template`)
