---
name: fetchsandbox
description: 'Top-level entry point for FetchSandbox. Use when the user says "fetchsandbox", "fs", "help me with fetchsandbox", "use fetchsandbox", or wants to test/integrate/explore an API ("test my stripe integration", "help me set up paddle", "I''m getting card_declined errors on stripe", "test an api with fetchsandbox"). This skill ALWAYS calls the MCP `guide` tool FIRST as Step 0 — `guide` is the deterministic router that maps the user''s free-form intent to the right spec + workflow + (when the spec has a brain.yaml) the next domain-aware discovery question. Routing decisions are owned by `guide`; this skill turns the response into a conversation. Do NOT invoke this skill when the user EXPLICITLY says "validate" — that goes to `fs-validate` directly (which also calls `guide` first). Never act without asking; every transition is gated on user confirmation.'
---

# FetchSandbox — Router Skill

## What this skill is

The single entry point for FetchSandbox tasks. When a user invokes
FetchSandbox without a specific action in mind, this skill is the
conversational layer that understands their intent and routes them to
the right sub-skill.

## The principle — NEVER act without asking

This is non-negotiable. This skill is a conversation, not an
execution. Do NOT call any MCP tool, write any file, or run any
workflow until the user has explicitly confirmed what they want.

The user's first message is the start of the conversation, not the
end. Treat every prompt as "tell me what they want to do" — even if
the prompt looks like it already has the answer.

## When to invoke

- User says "fetchsandbox" or "fs" without a specific verb
- User says "help me with [API name]" and mentions integration / testing / validation
- User says "test an api" or "I want to test my integration"
- User says "what can fetchsandbox do"
- User has a sandbox running and isn't sure what to do next
- ANY ambiguous FetchSandbox-related prompt

**Do NOT invoke this skill when** the user has clearly specified an
action AND target — those go to specific sub-skills:
- "validate stripe checkout with fetchsandbox" → use `fs-validate` directly
- "show me my last 5 runs" → use `fs-history` directly (once it exists)

## Procedure

### Step 0 — Always call `guide()` first (deterministic routing)

**Before** greeting, call `mcp__fetchsandbox__guide` with the user's
exact message as `intent`. This is a stateless lookup — no side
effects, no engine warming, no workflow runs. It returns the
deterministic routing decision plus, when the spec has a `brain.yaml`,
the next discovery question to ask.

Read the response:

- **`confidence ≥ 0.75` AND `next_question` is present** → skip the
  generic menu; in Step 1 ask the user the brain's `next_question`
  verbatim (with its options). The brain knows the domain better than
  any hand-coded menu.
- **`confidence ≥ 0.75` AND `next_question` is null** → spec/workflow
  are resolved but the spec has no brain.yaml yet. In Step 1 confirm
  the resolved action ("I'll validate {spec}/{workflow} — proceed?").
- **`confidence < 0.75`** → ambiguous. Fall through to the generic
  numbered menu below.

The router is the source of truth for spec/workflow selection. Do not
override its choice silently — if you disagree, ASK the user.

### Step 1 — Greet + offer options (only when guide confidence is low)

If Step 0's guide call returned `confidence < 0.75` (or no spec at
all), use `AskUserQuestion` — NEVER a prose "Paste a number, or just
describe" prompt:

    AskUserQuestion(questions=[{
      header: "What now",
      question: "Hi — what would you like to do?",
      options: [
        {label: "🔍 Browse APIs in the catalog",
         description: "55+ specs to explore"},
        {label: "✅ Validate an integration",
         description: "Run workflows, get a structured report"},
        {label: "📜 Show recent test runs",
         description: "Review what was run before"},
        {label: "🐛 Debug a failing workflow",
         description: "Walk through what broke + propose fixes"},
      ],
    }])

(AskUserQuestion caps at 4 options + Other. "Explain a workflow without
running" collapses into "Other" with free-text — most users describe in
words anyway.)

If the user's prompt already hinted at an action (e.g. "test stripe"),
acknowledge it AND still ask for confirmation via `AskUserQuestion`
(NEVER a prose "Should I run with that?" prompt):

    AskUserQuestion(questions=[{
      header: "Inferred",
      question: "I inferred you want <option N> (<one-line>) for <spec>. Right?",
      options: [
        {label: "Yes, run that", description: "Proceed with the inferred path"},
        {label: "No — let me pick", description: "Show me the full option list"},
        {label: "Different spec", description: "Switch the target API"},
      ],
    }])

### Step 2 — Wait for the user's response

Do not proceed until the user has chosen. If their response is
ambiguous, ask a clarifying question — never guess.

### Step 3 — Route based on the choice

Once they've confirmed a path:

#### Option 1: Browse the catalog
Hand off to `fs-explore` — load the full procedure from
`.claude/skills/fs-explore/SKILL.md`. It will list specs grouped by
category, ask the user which to drill into, and offer 3 next actions
(peek workflows / validate / import as raw sandbox).

#### Option 2: Validate an integration
Hand off to `fs-validate` — but ALWAYS confirm the scope first via
`AskUserQuestion` (NEVER prose `"Should I (a) X (b) Y (c) Z?"`):

    AskUserQuestion(questions=[{
      header: "Scope",
      question: "How should I scope the {spec} validation?",
      options: [
        {label: "Run all workflows",
         description: "Full coverage — every workflow in the spec, one batch"},
        {label: "Just workflows matching '{scope_hint}'",
         description: "Filtered run — matches the scope hint you gave"},
        {label: "List them first so I can pick",
         description: "I'll show the full list, you pick which to run"},
      ],
    }])

Then proceed to `.claude/skills/fs-validate/SKILL.md` (the existing
skill), following its procedure WITH user confirmation at each
transition point.

#### Option 3: Show recent runs
Hand off to `fs-history` — load the full procedure from
`.claude/skills/fs-history/SKILL.md`. It will resolve which sandbox to
look at, list recent runs with shareable URLs, and offer 4 actions
per run (re-render report / re-run / open timeline / back).

#### Option 4: Explain a workflow without running it
1. Ask which spec.
2. Call `mcp__fetchsandbox__import_spec` + `list_workflows`.
3. Show the workflows. Ask which one.
4. Describe the workflow's steps (just the names and HTTP methods/paths
   from the `list_workflows` response) — do NOT execute.
5. Ask: *"Want to run this now, or just leave it as a reference?"*

#### Option 5: Debug a failing workflow
Hand off to `fs-debug` — load the full procedure from
`.claude/skills/fs-debug/SKILL.md`. It will resolve the sandbox + run
context, list failing runs, ASK before re-running to capture a fresh
trace, then walk through the failure step-by-step with a hypothesis +
2-3 fix options. Never re-runs without confirmation.

### Step 4 — Always offer a return path

After completing any action (validation report written, browsing done,
etc.), end the conversation with:

```
✓ Done. Want to:
  - Run another workflow on the same sandbox?
  - Validate a different API?
  - Wrap up here?
```

Let the user steer. Do not assume "we're done" unless they say so.

## Anti-patterns — DO NOT

- **DO NOT** call any MCP tool before the user has confirmed an action.
  The first MCP tool call only happens AFTER the user picks one of the
  numbered options.
- **DO NOT** write any file (skeleton report or otherwise) before the
  user has confirmed the validate flow specifically.
- **DO NOT** "infer" an answer when the user gives an ambiguous prompt.
  Ask. The 5 seconds it takes to ask is cheaper than running the wrong
  workflow.
- **DO NOT** chain multiple actions without re-asking. After step 3
  completes, ALWAYS check in (step 4) — don't auto-start the next thing.
- **DO NOT** present this menu in walls of text. Keep each ask under
  5 lines. The user is reading on mobile half the time.

## Why this skill exists

Without a router, the user has to know exact trigger phrases to reach
the right sub-skill. Most won't. With a router:
- New users hit one entry point and get walked through
- Power users can still bypass via specific phrases ("validate stripe
  with fetchsandbox" → `fs-validate` directly)
- Every transition has a confirmation gate, so a misunderstanding never
  costs more than a re-ask

The principle behind the system: **the agent is the user's assistant,
not their autopilot.** Decisions stay with the user. The agent
proposes; the user confirms.
