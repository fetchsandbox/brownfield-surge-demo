---
name: fs-validate
description: 'Validate an API integration against FetchSandbox workflows. Runs workflows (all of them, or a scoped subset the user picks) and shows the result conversationally in chat — no files written to the user repo. CONVERSATIONAL — always confirms intent + scope with the user before running anything. Use ONLY when the user EXPLICITLY says the verb "validate" (e.g. "validate this integration with fetchsandbox", "fs validate", "validate my stripe integration", "check api integration coverage"). For other phrasings like "test my X integration" or "help me with X" — defer to the `fs-router` skill (the orchestrator), which calls `bmad-document-project` + the FetchSandbox proof engine for a multi-persona flow. Power-user friendly: if the user already specified spec + scope clearly, the first confirmation is a one-word ack — they can blast through with "y".'
---

# FetchSandbox: Validate Integration (conversational)

## Output the user gets

**Console-only.** This skill writes NOTHING to the user's repo. All
output appears in the chat:

1. The workflow trace, step by step, with PASS/FAIL marks
2. The proof receipt — what was verified end-to-end
3. A shareable timeline URL `https://fetchsandbox.com/runs/<sandbox_id>`
   the user can drop in Slack or a PR comment
4. (When relevant) compliance notes from the spec's brain.yaml — the
   real-world gotchas they need to handle in their prod code

Why no file: the dev's repo should only contain code THEY wrote. Run
artifacts live in the FetchSandbox dashboard (the timeline URL).
Re-running this skill regenerates the trace — no state to commit.

## Prerequisite

The user must have the `fetchsandbox` MCP server installed. Check that
`mcp__fetchsandbox__*` tools are available. If not, tell them to install:

```
npx -y fetchsandbox-mcp
```

Then re-trigger.

## The principle — confirm before acting

This skill is conversational. There are exactly **three gates** at which
the skill STOPS and waits for the user:

| Gate | What's confirmed | Why |
|---|---|---|
| 1 | Intent (spec + scope) | Avoid running against the wrong API or wrong scope |
| 2 | Workflow selection (if filter matched 0 / many) | Avoid running 18 workflows when user wanted 2 |
| 3 | "What next" after results | User stays in control of follow-up |

Between gates, internal steps (spec resolution, batch run, result
streaming) happen automatically — those are mechanical, not decisions.
NO files are written to the user's repo at any point.

**Power-user mode**: when the user's initial prompt clearly specifies
spec + scope (e.g. "validate stripe checkout with fetchsandbox"), the
Gate 1 confirmation is a single-line ack — they can answer "y" in two
characters and proceed.

## Procedure

### Step 1 — Call `guide()` for deterministic routing

Call `mcp__fetchsandbox__guide` with the user's exact message as
`intent`. This is a stateless lookup; no side effects. It returns:

```
{
  spec: "stripe" | null,
  workflow: "accept_payment" | null,
  scenario: "payment_declined" | null,
  confidence: 0.0 - 1.0,
  reasoning: "…",
  matched_signals: ["spec:stripe", "workflow_default:accept_payment", …],
  next_question: { id, question, options[], default } | null
}
```

From the response, set:

- **`spec_target`** = `response.spec` (router-verified; if null, see fallback below)
- **`scope_hint`** = `response.workflow` (router-verified workflow id) OR any
  qualifier word the user said after the spec name (e.g. "checkout",
  "refunds") that survived the router. Null = all workflows.
- **`next_question`** = `response.next_question` (may be null)
- **`confidence`** = `response.confidence`

**Fallback (only if `confidence === 0` and `spec_target` is null)**: ASK
the user *"Which API do you want to validate? (Stripe, GitHub, Twilio,
Notion, … or paste a URL.)"* — STOP. When they reply, re-call `guide`
with their answer and re-run Step 1.

The router is the source of truth for spec/workflow. Do not silently
override it — if you disagree with its pick, raise it in Gate 1.

### Step 2 — GATE 1: confirm intent (now brain-aware)

**STOP. Do NOT call any other MCP tool yet.** The shape of this gate
depends on whether `next_question` was returned from `guide`:

**(2a) When `next_question` is null** (spec has no brain.yaml yet) —
send the legacy Gate 1 message:

```
Got it. About to validate:

  • Spec:  <spec_target>
  • Scope: <scope_hint or "all workflows">

Proceed? (y / n / or tell me what to change)
```

**(2b) When `next_question` is present** (spec has a brain.yaml — today:
stripe; soon: paddle/polar/resend/clerk/square) — fold the discovery
question into Gate 1 so the user answers it AT confirmation time, not
mid-run:

```
Got it. About to validate <spec_target> ({scope_hint or "all workflows"}).

```

**End Gate 1 with `AskUserQuestion` — NEVER prose "[1] / [2] / [3] / pick
a number" picker shorthand.** If `guide()` returned `next_questions[]`
plural, use multi-question form (tabs UX):

    AskUserQuestion(questions=[{
      header: "<≤12 chars chip>",
      question: "{next_question.question}",
      options: [
        {label: "{options[0].label}", description: "{infer from implies}"},
        {label: "{options[1].label}", description: "{infer from implies}"},
        ...,
        {label: "Use default ({next_question.default})",
         description: "Skip the picker — proceed with default"},
      ],
    }])

Then **WAIT for the picker selection:**

- If they pick a non-default option → record that option's `implies`
  block as run hints (`currency`, `three_ds`, `test_card_library`,
  `capture_method`, etc.) → continue to Step 3
- If they pick "Use default" → proceed with `next_question.default`
  (or just the resolved spec/workflow if no default) → continue to Step 3
- If they pick "Other" with free-text correction (e.g. *"all workflows"*)
  → update scope hint and re-render Gate 1
- If they dismiss/cancel → reply *"OK, paused. Tell me when you're
  ready."*, end the conversation

### Step 3 — Resolve the spec (internal, no gate)

Once intent is confirmed:

1. If the user gave a URL → call `mcp__fetchsandbox__import_spec(url=…)`
2. If they named a known API:
   - Call `mcp__fetchsandbox__list_specs(filter=<spec_target>)` to verify it's in the catalog
   - If exactly 1 match → use the vendor's public OpenAPI URL for
     `import_spec` (common URLs below)
   - If multiple matches → ASK the user: *"Found N matches: [list].
     Which one?"* — STOP, then continue
   - If zero matches → ASK: *"No catalogued spec for '<spec_target>'.
     Paste a public OpenAPI URL, or pick from these popular ones:
     [Stripe, GitHub, Twilio, Notion, OpenAI]"* — STOP

Common public OpenAPI URLs (use to skip a second round-trip):
- Stripe: `https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json`
- GitHub: `https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json`

Capture from import response: `spec_id`, `sandbox_id`, `name`,
`workflow_count`, `workflows_preview`.

### Step 4 — GATE 2: confirm workflow scope

Filter workflows based on `scope_hint`:

- If `scope_hint` is null → all `workflow_count` workflows in scope, no
  filter needed. **Skip Gate 2** (intent was already "all workflows" and
  user already confirmed in Gate 1). Continue to Step 6.
- If `scope_hint` is set:
  1. Call `mcp__fetchsandbox__list_workflows(spec_id=<spec_id>)` to get
     the full list.
  2. Filter to workflows whose `id` OR `name` OR `description` contains
     `scope_hint` (case-insensitive substring).
  3. **Now gate based on match count**:

**If matched 1 workflow:**
**STOP. Send to user:**
```
Found 1 workflow matching '<scope_hint>':

  • <name> — <description>

Run it now? (y / show me all <workflow_count> instead)
```
WAIT for reply.

**If matched 2-5 workflows:**
**STOP. Send to user:**
```
Matched <N> workflows for '<scope_hint>':

  1. <name1>
  2. <name2>
  3. <name3>

Run all <N>? Or paste numbers to pick a subset. Or 'all' to run every workflow (<workflow_count>).
```
WAIT for reply.

**If matched 6+ workflows:**
**STOP. Send to user:**
```
Matched <N> workflows for '<scope_hint>' (showing first 5):

  1. <name1>
  2. <name2>
  3. <name3>
  4. <name4>
  5. <name5>
  … and <N-5> more

Run all <N>? Run just the first 5? Or paste a more specific scope.
```
WAIT for reply.

**If matched 0 workflows:**
**STOP. Send to user:**
```
No exact match for '<scope_hint>'. Three options:

  a. Run all <workflow_count> workflows (full coverage)
  b. List all <workflow_count> so you can pick
  c. Closest semantic match: <best_guess> — run just that

Which? (a / b / c)
```
WAIT for reply.

In all cases, the user's reply determines `final_workflow_names` (or
`null` to run all).

### Step 5 — Run (internal, no gate)

Call `mcp__fetchsandbox__run_all_workflows` ONCE with:
- `sandbox_id`
- `workflow_names` = the user's confirmed list (omit if "all")

**Do NOT loop `run_workflow` in singular form.** That tool is for
ad-hoc single-workflow execution and creates one IDE approval prompt per
workflow. `run_all_workflows` collapses everything to one approval.

If `run_all_workflows` is unavailable (very old MCP version), stop and
tell the user to upgrade: `npx -y fetchsandbox-mcp@latest`. Do NOT
silently fall back to a `run_workflow` loop.

### Step 6 — GATE 3: present results in chat + offer next step

After `run_all_workflows` returns, **stream the result directly to
chat**. NO file is written. Use the inline format below — concise
trace, then a one-line summary, then the next-step offer.

Per workflow, show:

```
✓ <workflow name> · <duration>ms · <steps_passed>/<steps_total> steps

  Step 1: <method> <path> → <response_status>
  Step 2: <method> <path> → <response_status>
  Step 3: <method> <path> → <response_status>
  Webhooks: <matched>/<expected> fired — <event type list>
```

Then the summary block:

```
✓ Validated <K>/<N> workflows of <spec name> (<scope_hint or "all">)
  • Duration: <X>s
  • Timeline: https://fetchsandbox.com/runs/<sandbox_id>  ← view full traces here

<if any failed>
Failed: <list of failed workflow names>
</if>

```

**End with `AskUserQuestion` — NEVER a "Reply with a number" prose prompt:**

    AskUserQuestion(questions=[{
      header: "Next move",
      question: "What's next?",
      options: [
        {label: "Validate a different scope on this spec",
         description: "I'll list the other workflows for this spec"},
        {label: "Validate a different API",
         description: "Switch to a different spec entirely (fs-explore to browse)"},
        {label: "Open the timeline in browser",
         description: "Inspect the full run trace at <timeline_url>"},
        {label: "We're done",
         description: "Close this validation thread"},
      ],
    }])

**Length discipline**: if the trace is long (>6 workflows or >20 steps
total), summarize the passing ones (`✓ <name> · all <N> steps passed`)
and ONLY expand failed ones. The timeline URL is the source of truth
for full request/response bodies — point users there for deep dives.

**Do NOT** redact bodies if you do print them inline — sandbox data is
fake. **Do NOT** write any file: the timeline URL is the artifact.

**STOP. Wait for user's reply.** Do not auto-start anything new. The
user is in control of follow-up. Common replies:

- `4` / `done` / `we're done` → reply *"Cool. Report at <path>."*, end
- `1` / *"validate refunds too"* → start Step 1 again with new `scope_hint`
- `2` / *"now do github"* → start Step 1 again with new `spec_target`
- `3` / *"open the timeline"* → reply *"Open: <timeline URL>"* — do not
  navigate; the user clicks

## If the user interrupts mid-flow

If the user says "stop", "pause", or denies an approval:
- Acknowledge in chat: *"Paused. The sandbox state is preserved on the
  FetchSandbox server — pick back up by re-triggering the skill, or
  view what ran so far at https://fetchsandbox.com/runs/<sandbox_id>."*
- Nothing on disk to clean up (this skill writes no files).

## Anti-patterns — DO NOT

- **Do NOT** call any MCP tool before the user has passed Gate 1
- **Do NOT** skip Gate 1, even when the user's initial prompt is
  unambiguous — the confirmation takes 2 seconds and prevents wrong-API
  runs
- **Do NOT** loop `run_workflow` to validate. Always use
  `run_all_workflows`. Looping is the bug we fixed in v0.2.0.
- **Do NOT** write any file to the user's repo. Console output only.
  The timeline URL is the artifact.
- **Do NOT** ignore the user's scope qualifier. "validate stripe
  checkout" ≠ "validate stripe".
- **Do NOT** invent fields the run response didn't return.
- **Do NOT** retry a failed workflow. First run is the truth.
- **Do NOT** auto-start a follow-up validation after Gate 3 unless the
  user explicitly asks for one.
- **Do NOT** commit the report. Write it, mention the path, let the
  user decide whether to commit.

## Why conversational

Without confirmation gates, a single mistyped spec name or scope word
costs the user a full 18-workflow run on the wrong target. With three
gates, the worst-case cost of a misunderstanding is one re-ask.

The agent is the user's assistant, not their autopilot. Decisions
stay with the user.
