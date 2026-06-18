---
name: fs-history
description: 'Show the user''s recent FetchSandbox test runs for a sandbox + drill into any one. Use when the user says "show my fetchsandbox runs", "what did I test before", "fs history", "show recent validations", "what runs exist for this sandbox", or arrived here via the fetchsandbox router skill picking option 3 ("Show recent test runs"). CONVERSATIONAL — asks which sandbox first, confirms before drilling in, offers 4 actions per run.'
---

# fs-history — Recent FetchSandbox runs

## Output the user gets

A list of their recent workflow runs for a chosen sandbox, with
shareable timeline URLs. On drill-in, options to re-render the report,
re-run with same params, or open the timeline.

## Prerequisite

The `fetchsandbox` MCP server must be installed and enabled. If
`mcp__fetchsandbox__list_runs` is not available, tell the user to
visit https://fetchsandbox.com/install.

## Procedure

### Step 1 — Resolve which sandbox

A `sandbox_id` is required. Check (in order):

1. Conversation context — was a sandbox_id mentioned recently?
2. The user's prompt — did they paste a sandbox_id or a URL like
   `https://fetchsandbox.com/runs/<id>`? Extract from the URL.
3. The project — is there a `.fetchsandbox/validation-*.md` file with
   a sandbox_id in the header? (use the Read tool on any matching file)

If a `sandbox_id` is found, **STOP and confirm**:

```
Looking at sandbox <sandbox_id> (<spec name if known>). Right one? (y / paste a different sandbox_id)
```

If NONE found, **STOP and ask**:

```
Which sandbox do you want to see runs for?

  1. Paste a sandbox_id (e.g. "cfae558c12")
  2. Paste a timeline URL (e.g. "https://fetchsandbox.com/runs/...")
  3. Import a fresh spec to start a new sandbox
  4. We're done

(Paste a number or the id/URL.)
```

Wait for the user's reply.

### Step 2 — List the runs (internal, no gate)

Once `sandbox_id` is confirmed, call
`mcp__fetchsandbox__list_runs(sandbox_id=<sandbox_id>, limit=20)`.

If `total=0`, render this picker — NEVER prose `"Want me to (a) X (b) Y?"`:

    AskUserQuestion(questions=[{
      header: "No runs",
      question: "No runs found for sandbox <sandbox_id>. What next?",
      options: [
        {label: "Run a workflow now",
         description: "Hand off to fs-validate to populate this sandbox"},
        {label: "Check a different sandbox",
         description: "I'll list your other sandboxes — pick one"},
        {label: "Switch to browse mode",
         description: "Maybe you want fs-explore instead of fs-history"},
      ],
    }])

**STOP. Wait for the picker selection.**

If `total >= 1`, continue to Step 3.

### Step 3 — GATE 1: render runs + ask which to drill into

Format the runs as a compact list, newest first. Send to user:

```
<total> recent runs for sandbox <sandbox_id>:

  1. accept_payment        ✓ pass   6/6 steps     12 min ago    →  fetchsandbox.com/runs/<sandbox_id>#<flow_run_id>
  2. refund_charge         ✗ fail   2/3 steps     45 min ago    →  fetchsandbox.com/runs/<sandbox_id>#<flow_run_id>
  3. accept_payment        ✓ pass   6/6 steps     1 hour ago    →  fetchsandbox.com/runs/<sandbox_id>#<flow_run_id>
  ...

Which one do you want to drill into? (paste a number or "all")
```

Read fields from the `list_runs` response: `workflow_name`,
`status` (pass/fail), `steps_passed/steps_total`, time-ago derived
from `started_at`, `share_url`.

**STOP. Wait.**

If user picks a number → continue to Step 4 with that run.
If user says "all" → render full detail for the first 5, summarize the rest.
If they ask to compare two → tell them: *"Comparison isn't supported yet — pick one to drill into, or open both timeline URLs in your browser."*

### Step 4 — GATE 2: present the run + offer 4 actions

For the chosen run, send to user:

```
<workflow_name> · <status badge>

  • Steps:     <steps_passed>/<steps_total>
  • Started:   <started_at>
  • Last seen: <last_activity_at>
  • Requests:  <request_count>
  • Webhooks:  <webhook_count>
  • Timeline:  <share_url>

What do you want to do?

  1. 📄  Re-render the markdown report (writes to .fetchsandbox/validation-*.md)
  2. 🔁  Re-run this workflow (fresh sandbox state)
  3. 🌐  Open the timeline URL in browser
  4. ←  Back to the runs list

(Paste a number.)
```

**STOP. Wait.**

### Step 5 — Route on user's choice

**If 1 (re-render report)**:
We don't currently have a per-flow_run detail API beyond `list_runs`
metadata — the rich report is generated from a fresh `run_workflow`
or `run_all_workflows` call. Use this picker — NEVER a prose
`"Want me to re-run or open the timeline?"`:

    AskUserQuestion(questions=[{
      header: "Re-render gap",
      question: "Rich report regenerates only on a fresh run. What now?",
      options: [
        {label: "Re-run the workflow (option 2)",
         description: "Hand off to fs-validate — fresh run produces the full trace"},
        {label: "Open the timeline URL (option 3)",
         description: "View the archive without re-running"},
        {label: "Cancel — I'll pick something else",
         description: "Go back to the run list"},
      ],
    }])

**If 2 (re-run)**:
Hand off to `fs-validate` skill at `.claude/skills/fs-validate/SKILL.md`,
passing the spec slug + workflow name as a pre-set scope. The user
only needs to confirm.

**If 3 (open timeline)**:
Reply with the URL and tell the user it's clickable. Don't navigate
yourself — they click in their IDE.

**If 4 (back)**:
Go back to Step 3 (re-render the list).

### Step 6 — Always offer return

After any action completes:

```
What next?
  1. Look at another run
  2. Switch to a different sandbox
  3. Run a fresh validation
  4. We're done
```

Wait. Never auto-start.

## Anti-patterns — DO NOT

- **DO NOT** call `list_runs` without a confirmed `sandbox_id`. Always
  ask or detect first.
- **DO NOT** pretend you can show the FULL trace of a past run. Only
  metadata is available via `list_runs`; the full report only exists if
  it was written to `.fetchsandbox/` at run time or you re-run.
- **DO NOT** auto-rerun a failed workflow just because the user is
  looking at it. Failed runs in history are signals, not bugs to fix.

## Why this skill exists

Users run a validation, get a report, share the URL with their team —
then come back a week later and forget what they validated. This skill
gives them their own history without having to dig through git or chat
transcripts.
