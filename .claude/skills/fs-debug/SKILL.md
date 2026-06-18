---
name: fs-debug
description: 'Walk through a failing FetchSandbox workflow with the user — show what broke, propose a hypothesis, offer fix options, only re-run with explicit confirmation. Use when the user says "fs debug", "why did <workflow> fail", "debug my fetchsandbox workflow", "what broke in my last run", "fix the failing checkout test", or arrived here via the fetchsandbox router skill picking option 5 ("Debug a failing workflow"). CONVERSATIONAL — confirms which failure to dig into, proposes hypothesis + fix options, never re-runs without user approval.'
---

# fs-debug — Debug a failing workflow

## Output the user gets

A clear walkthrough of what failed, where, why, and 2-3 things to try.
Nothing re-runs without explicit confirmation.

## Prerequisite

The `fetchsandbox` MCP server must be installed and enabled. If
`mcp__fetchsandbox__*` tools are not available, tell the user to visit
https://fetchsandbox.com/install.

## Important constraint — what we can and CAN'T see

The MCP tools expose **run metadata** (`list_runs`) but the **full
step trace with request/response bodies** only exists when a workflow
has just been re-run via `run_workflow` or `run_all_workflows`. So
debugging an OLD run usually means re-running it (with consent) to
capture the fresh trace.

Be honest with the user about this — don't pretend to have data we
don't have.

## Procedure

### Step 1 — Detect debug context

Read the user's prompt for hints about WHAT they want to debug:

- **`workflow_hint`** — workflow name or scope mentioned (e.g.
  *"why did checkout fail"* → `workflow_hint=checkout`)
- **`sandbox_id`** — pasted sandbox ID, or extractable from a
  `https://fetchsandbox.com/runs/<id>` URL, or readable from a
  `.fetchsandbox/validation-*.md` file in the project (use Read tool
  on any matching file to extract the `Sandbox:` header line)
- **`flow_run_id`** — pasted run ID or extracted from a timeline URL

### Step 2 — GATE 1: confirm sandbox

If `sandbox_id` is found, **STOP and confirm**:

```
Looking at sandbox <sandbox_id>. Right one? (y / paste a different sandbox_id)
```

If NO `sandbox_id` found, **STOP and ask**:

```
Which sandbox is this for?

  1. Paste a sandbox_id (e.g. "cfae558c12")
  2. Paste a timeline URL (e.g. "fetchsandbox.com/runs/...")
  3. We just ran something and I should look at the latest

(Paste a number or the id/URL. Or "I don't know" and I'll check the project's .fetchsandbox/ folder.)
```

Wait. Don't proceed without a confirmed `sandbox_id`.

### Step 3 — GATE 2: pick the failing run

Once `sandbox_id` is confirmed, call
`mcp__fetchsandbox__list_runs(sandbox_id=<sandbox_id>, limit=50)`.

Filter the results to runs with `status="fail"` or
`steps_passed < steps_total`.

**If `workflow_hint` was set**, further filter to runs whose
`workflow_name` matches (case-insensitive substring).

**Render based on what's left:**

**If 0 failing runs match:**

```
No failing runs match in sandbox <sandbox_id>{ for "<workflow_hint>" if set}.

Either:
  a. Re-run the workflow to reproduce + capture the full trace
  b. Look at all runs (pass + fail) and pick one to inspect
  c. Different sandbox

Which?
```
**STOP. Wait.**

**If 1 failing run matches:**

Render a brief one-line summary, then ask via `AskUserQuestion`:

```markdown
**Found 1 failing run:**

| Workflow | Steps | When | Timeline |
|---|---|---|---|
| <workflow_name> | ✗ <K>/<N> | <time-ago> | [<sandbox_id>](<share_url>) |
```

    AskUserQuestion(questions=[{
      header: "Drill in",
      question: "What do you want to do with this failure?",
      options: [
        {label: "Re-run with step-by-step walkthrough",
         description: "I'll narrate each step + show where it broke"},
        {label: "Just open the timeline URL",
         description: "You inspect the trace manually in browser"},
        {label: "Look at a different run",
         description: "Pick from the full run list"},
      ],
    }])

**STOP. Wait for the picker selection.**

**If 2+ failing runs match:**

```
<N> failing runs:

  1. <workflow_name>  ✗ <steps_passed>/<steps_total>  <time-ago>
  2. <workflow_name>  ✗ <steps_passed>/<steps_total>  <time-ago>
  ...

Which one do you want to dig into? (paste a number)
```
**STOP. Wait.**

### Step 4 — Re-run to capture fresh trace (with consent)

If the user picked path (a) — re-run + walkthrough — **STOP one more
time** before actually re-running:

```
Re-running <workflow_name> on sandbox <sandbox_id> will:
  • Reset workflow state for that flow
  • Charge nothing (sandbox is fake)
  • Take ~<estimated_seconds>s based on similar workflows

This produces a fresh failure trace I can walk you through. Proceed?
(y / n / use a different sandbox to isolate)
```

Wait. On `y`, call
`mcp__fetchsandbox__run_workflow(sandbox_id, workflow_name)` (single,
not batch — we want isolated debugging on one workflow).

Capture the response: `steps`, each step's `method`, `path`,
`response_status`, `response_body`, `detail`.

### Step 5 — GATE 3: present the failure + propose hypothesis

Identify the FIRST failing step (lowest index where `status="failed"`).

Send to user:

```
Re-ran <workflow_name>. Failed at step <N>:

  Step <N>: <step_name>
  → <method> <path>
  → expected: <expected_status>, got: <response_status>
  → server said: <detail or response_body.error truncated to 200 chars>

Steps that PASSED before this one:
  ✓ Step 1: <name>     (returned: <key_id>)
  ✓ Step 2: <name>     (returned: <key_id>)
  ...

Hypothesis: <one-line guess at why it failed — e.g.:
  "Step <N> needs <missing_field> in the request body and the workflow definition didn't include it"
  "Step <N-1> returned <unexpected_status> which made step <N>'s precondition wrong"
  "Webhook event <expected_event> never fired before step <N>'s timeout">

What do you want to do?
  1. 🔁  Re-run with a tweak (tell me what to change in the request)
  2. 🔍  Show me the full request/response JSON for step <N>
  3. 📝  Note this in .fetchsandbox/debug-<workflow>-<date>.md and we move on
  4. 🌐  Open the timeline URL to inspect manually
  5. ←  Back to the failing-runs list

(Paste a number, or describe what you want.)
```

**STOP. Wait.**

### Step 6 — Route on the user's choice

**If 1 (re-run with tweak)**:
ASK what to change. *"What do you want to change for step <N>'s request? Paste an updated body, override a path param, or describe the change."*
Then re-run with the override (use `run_workflow` — the MCP tool
doesn't support per-call overrides today, so be honest with the user
that this might require editing the workflow definition or running a
different workflow). If the override isn't supported by current MCP
tools, tell them so and offer to write a quick override script using
the `import_spec` URL + curl.

**If 2 (show full JSON)**:
Render the failed step's `request_body` and `response_body` (use the
truncation handling from `fs-validate` — if `_truncated: true`, paste
preview + note the cap).

**If 3 (note + move on)**:
Use Write to create `.fetchsandbox/debug-<workflow>-<YYYY-MM-DD>.md`
with the failure summary. Tell the user the path. Ask: *"Anything
else, or done?"*

**If 4 (open timeline)**:
Reply with the URL — let user click in their IDE.

**If 5 (back)**:
Return to Step 3 (re-render the failing-runs list).

### Step 7 — Always offer next

After any action:

```
What next?
  1. Try a different fix
  2. Look at another failing run
  3. Switch sandboxes
  4. We're done
```

Wait. Don't auto-start anything.

## When fs-debug should hand off to other skills

- User asks to **validate everything again** → `fs-validate`
  (`.claude/skills/fs-validate/SKILL.md`)
- User wants to **see all runs (not just failures)** → `fs-history`
  (`.claude/skills/fs-history/SKILL.md`)
- User wants to **explore other workflows for the same spec** →
  `fs-explore` (`.claude/skills/fs-explore/SKILL.md`)

Always ask before handing off — use `AskUserQuestion`, never prose:

    AskUserQuestion(questions=[{
      header: "Hand off",
      question: "Switch to <target-skill> or stay focused here?",
      options: [
        {label: "Switch to <target-skill>",
         description: "<one-line of what that skill does>"},
        {label: "Stay on this failure",
         description: "Keep debugging the current run"},
      ],
    }])

## Anti-patterns — DO NOT

- **DO NOT** auto-rerun a failed workflow on first contact. The user
  might want to inspect the existing trace first, or pick a different
  failure, or just open the URL.
- **DO NOT** invent root causes. If you don't have enough info to form
  a real hypothesis, say so + offer the next inspection via
  `AskUserQuestion` (NEVER prose `"Want me to (a) X (b) Y (c) Z?"`):

      AskUserQuestion(questions=[{
        header: "Investigate",
        question: "Not enough info to hypothesize. Where should I look next?",
        options: [
          {label: "Inspect the request body",
           description: "What exactly did we send? Often the issue is in the payload."},
          {label: "Check the webhook events",
           description: "Webhook trail often shows why the state transition stalled"},
          {label: "Compare to a known-passing run",
           description: "Side-by-side diff against the latest successful invocation"},
        ],
      }])
- **DO NOT** modify the workflow definition or the user's code. Debug
  is read-mostly. Suggest changes; let the user apply them.
- **DO NOT** retry the same exact failed run hoping for different
  results. Failures are deterministic in our sandbox.
- **DO NOT** dump 50 lines of JSON unsolicited. Show the
  truncated/summarized failure first; full JSON only when the user
  picks option 2.

## Why this skill exists

`fs-validate` tells the user IF something failed. `fs-history` tells
them WHAT failed. `fs-debug` tells them WHY — with consent at every
turn, so the agent never wastes the user's time chasing the wrong
hypothesis or re-running on the wrong sandbox.

Without this skill, a failed workflow is a dead-end: user sees
✗ in the report, has no path forward except "delete and try again."
With this skill, every failure becomes a guided diagnostic.
