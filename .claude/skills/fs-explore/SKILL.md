---
name: fs-explore
description: 'Browse FetchSandbox''s 50+ pre-validated API specs and drill into any one. Use when the user says "what APIs does fetchsandbox support", "show me the fetchsandbox catalog", "browse fetchsandbox specs", "list fs specs", "fs explore", "what can I test with fetchsandbox", or arrived here via the fetchsandbox router skill picking option 1 ("Browse APIs"). CONVERSATIONAL — confirms before drilling in, offers 3 next actions per spec, never auto-runs anything.'
---

# fs-explore — Browse the FetchSandbox catalog

## Output the user gets

A clear menu of every API we support, then (on their pick) a description
of that spec's workflows + 3 offered next actions: peek workflows /
validate / import as raw sandbox. Nothing runs without confirmation.

## Prerequisite

The `fetchsandbox` MCP server must be installed and enabled. If
`mcp__fetchsandbox__list_specs` is not available, tell the user to
visit https://fetchsandbox.com/install for the walkthrough.

## Procedure

### Step 1 — Detect any catalog filter hint

Read the user's exact message. Look for a hint about WHAT they want to
browse (e.g. *"show me payment APIs"*, *"do you support Twilio?"*,
*"what comms tools do you have"*). Extract a one-word `filter_hint` or
null:

| User said | `filter_hint` |
|---|---|
| "browse fetchsandbox specs" | null (show all) |
| "show me payment APIs" | "payment" |
| "do you support twilio?" | "twilio" |
| "what comms tools" | "comm" |

### Step 2 — GATE 1: list, then ask which to drill into

Call `mcp__fetchsandbox__list_specs(filter=<filter_hint>)`.
(If `filter_hint` is null, omit the filter — returns all 50+.)

**Format the response** as a compact numbered list, grouped by
inferred category (Payments / Comms / Dev Tools / AI / Data / Other —
infer from tags or name; don't overthink it). Limit to 15 items
visible; if more, show the top 15 and say *"…and N more — say 'show
all' or refine your search"*.

**Send to user — STOP. Do NOT call any other MCP tool yet.**

Example shape:

```
Found <N> matching APIs:

PAYMENTS
  1. Stripe — payments, subscriptions, webhooks
  2. Paddle — billing, checkout
  3. Polar — subscription billing

COMMS
  4. Twilio — SMS, voice, WhatsApp
  5. Resend — transactional email

DEV TOOLS
  6. GitHub — repos, issues, PRs
  7. GitLab — repos, MRs
  ...

```

**End with `AskUserQuestion` — NEVER a prose "paste a number, name, or
'show all'" prompt:**

    AskUserQuestion(questions=[{
      header: "Drill in",
      question: "Which spec do you want to drill into?",
      options: [
        // Top 3 specs from the list above as labeled options
        {label: "<spec_1_name>", description: "<one-line of what it covers>"},
        {label: "<spec_2_name>", description: "<one-line>"},
        {label: "<spec_3_name>", description: "<one-line>"},
        {label: "Show all <N> + different search",
         description: "Refine the list with a new keyword or expand"},
      ],
    }])

Wait for the picker selection. If user picks one of the top 3 → continue
to Step 3 with that spec. If they pick "Show all + different search",
ask via free-text Other for the new keyword, set `filter_hint`, re-run
Step 2.

### Step 3 — Import the chosen spec (internal, no gate)

Once the user picks a spec, import it to get the sandbox + workflows:

1. Call `mcp__fetchsandbox__import_spec` with the spec's public URL or
   slug. Capture `sandbox_id`, `workflow_count`, `workflows_preview`.

If the spec ID is ambiguous (e.g. user typed a name that matches
multiple), ASK which one before importing.

### Step 4 — GATE 2: present the spec + offer 3 actions

Show the spec details. Send to user:

```
<spec name> — <one-line description>

  • Endpoints: <endpoint_count>
  • Workflows: <workflow_count>
  • Sandbox:   <sandbox_id>
  • Timeline:  https://fetchsandbox.com/runs/<sandbox_id>

What do you want to do?

  1. 💬  See its workflows (just descriptions, no run)
  2. ✅  Validate end-to-end (runs workflows, writes a markdown report)
  3. 🔌  Import as a usable sandbox I can call from my code
  4. ←  Pick a different spec

(Paste a number, or describe what you want.)
```

**STOP. Wait for user's reply.**

### Step 5 — Route based on user's choice

**If they pick 1 (see workflows):**
Call `mcp__fetchsandbox__list_workflows(spec_id=<spec_id>)`. Render
the list as a compact table:
```
| # | Workflow | Steps | Description |
|---|---|---|---|
| 1 | accept_payment | 5 | Charge a customer end-to-end |
| 2 | refund_charge | 3 | Refund a previously-captured payment |
| ...
```
Then ask: *"Want to drill into one for more detail? Or run one? Or back to spec list?"*

**If they pick 2 (validate end-to-end):**
Hand off to the `fs-validate` skill at `.claude/skills/fs-validate/SKILL.md`.
Pass the `spec_target=<spec slug>` so it starts at Gate 1 with the
spec pre-confirmed. The user only needs to confirm scope.

**If they pick 3 (import as raw sandbox):**
The sandbox is already imported (Step 3). Show the user the sandbox
base URL + a sample curl:
```
Your sandbox is live at:
  https://api.fetchsandbox.com/sandboxes/<sandbox_id>

Try a request:
  curl -X POST https://api.fetchsandbox.com/sandboxes/<sandbox_id>/v1/customers \
    -H "content-type: application/json" \
    -d '{"email":"test@example.com"}'

Or share this URL with your team:
  https://fetchsandbox.com/runs/<sandbox_id>

```

**Then close with `AskUserQuestion` — NEVER a prose "Want me to..." prompt:**

    AskUserQuestion(questions=[{
      header: "Next move",
      question: "Call an endpoint, or are you good?",
      options: [
        {label: "Call <endpoint>",
         description: "POST /<path> with sample body — proves the contract live"},
        {label: "Pick a different endpoint",
         description: "I'll list more endpoints from this spec"},
        {label: "I'm good", description: "End this exploration thread"},
      ],
    }])

**STOP. Wait for the picker selection.**

**If they pick 4 (different spec):**
Go back to Step 2 with the original `filter_hint`.

### Step 6 — Always offer return

After any action completes, end with:

```
What next?
  1. Validate this spec
  2. Browse a different spec
  3. We're done

(Paste a number.)
```

Wait. Do not auto-start anything.

## Anti-patterns — DO NOT

- **DO NOT** call `import_spec` or `list_workflows` for a spec the user
  didn't explicitly pick. Wait for their number/name.
- **DO NOT** show all 50+ specs in one wall of text. Group + limit to 15.
- **DO NOT** auto-route to `fs-validate` without the user picking
  option 2. They might just want to peek workflows or get the raw URL.
- **DO NOT** invent categories that don't fit the spec's actual tags.
  When in doubt, put it in "Other".

## Why this skill exists

Users land on `fetchsandbox` having heard "50+ APIs supported" but
don't know which ones or what they can do with each. Without exploration,
they fall back to "the one API I already know" (usually Stripe). This
skill turns the catalog from a list into a guided tour.
