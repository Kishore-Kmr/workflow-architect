# Brief and structure proposal: formats

## Part 1: the brief (shown in phase 3, saved as BRIEF.md after approval)

One page. Mark every default you proposed (rather than the user said) with **OK?**. Remove the
marks once the user approves, and change the status line.

```markdown
# Brief: <project name>

Version <n> | <date> | <"Draft for your approval" or "Approved <date>">

## Goal
<What we are making, for whom, why. 2-3 lines.>

## Finish line
<What "done" looks like, and who judges it.>

## Limits
- Deadline: <date, or none>
- Your time: <hours per week, the most one task may take> (only if relevant)
- External spending: <cap, approval rule> (only if relevant)
- Do not: <what must not be touched or done>

## Your notes
<The user's answer to "Anything else the workflow should know?", word for word, or "(none
yet)". Yours to add to at any time; the workflow reads it before each step.>

## How you want to work
- Tools: <the tool you run in; adapters made; "other AI tools read AGENTS.md">
- Steps: <stop after each step | keep going until something needs you>
- Asking: <how strict "ask first" is>
- Reports: <short | detailed>
- Git: <commit after each step | you commit | no git>
- Fixing the workflow: small fixes I make myself and tell you, with an undo; bigger ones I
  ask first. **OK?**
- Progress review: every 10 steps and at the end of each phase, a fresh AI checks whether the
  work is moving and what slows it down; at each phase end you decide whether to go on. **OK?**

## What we know
- <topic>: <fact> (<you said | checked | inferred: right?>)

## Not relevant here
- <topic>: <reason>

## Open questions
- <question>: <why it matters>

## Saved for later (asked when the stage comes)
- <question>: asked when <stage trigger>

## First action
<The smallest action that tells us the most, and who does it.> **OK?**

## Stop if
- <What would make us stop or rethink.> **OK?** (mark each one you proposed)
```

## Part 2: the structure proposal (shown in phase 4)

```text
Structure proposal (version 1)

<folder>/
  AGENTS.md        rules and file map, read by most AI tools
  CLAUDE.md        makes Claude Code read AGENTS.md          <- because: you use Claude Code
  BRIEF.md         the approved brief
  NEXT.md          the one next action
  STATE.json       phase, step number, settings
  LOG.md           one line per event, with tags
  DECISIONS.md     your decisions, word for word
  QUESTIONS.md     open questions; questions saved for later
  RULES.md         <n> rules: <short list>
  WORKFLOW-FIXES.md  fixes to the workflow, with undo (empty for now)
  tools/step.md    how to do one step
  tools/fixes.md   how the workflow checks and fixes itself
  tools/progress-review.md  the regular progress review
  tools/wf.py      status, log, checks, health               <- because: Python is available
  .claude/skills/  the /step and /workflow commands            <- because: you use Claude Code
  <end-product parts, e.g. deliverable/outline.md>           <- because: <answer>

Existing files: <kept as they are; which ones the parts point to>
Rules from your answers: <rule> <- because: <answer>
Needed, but not in this version yet: <module> <- because: <answer>
  for now: rule R-<n> "<temporary rule>" and question Q-<n>, asked when <trigger>
Not added: <module>: <why not>; would be added if <what would change it>
You will be asked during the work: <just-in-time questions and their triggers>
Git: <what will happen, e.g. "git init, then one commit after the practice round">
```

Then ask: approve, change, or ask about something.

## Modules: not built yet (they come in v0.3)

They come in a later version. If the brief shows a need:
- **It applies to the first phase:** propose its temporary rule for RULES.md (Origin: the user's
  answer, "temporary until the <module> module exists") and its just-in-time question.
- **It belongs to a later stage** (e.g. budget before the first paid call, experiment cards
  before the first experiment): propose only the just-in-time question. The rule is added when
  that stage comes.
- Never propose a rule that repeats the core rules, the "Always ask first" list in AGENTS.md (spending,
  outward actions, irreversible steps) or a setting (autonomy, reports, git). A new project
  usually needs 2 to 5 rules in all.

Use the table for the "Not added" lines too.

| Module | Needed when | Temporary rule | Just-in-time question (trigger) |
|---|---|---|---|
| Independent reviewer | errors would be costly or hard to see | the user (or a named person) checks <part> before it counts as done | who checks it, against what? (first draft of <part>) |
| Workers | big, repetitive or parallel tasks | split such a task over several steps; say how many before starting | how to split it? (first big task) |
| Decision points | go/no-go moments | at <moment>, stop and put the go/no-go decision in NEXT.md as a YOU action | what would make it a go? (before <moment>) |
| External budget | the first paid external resource | ask before any spending | spending cap and approval rule? (first spend) |
| Human hours | tasks need the user's work | give the estimated hours before any YOU task over <limit> | hours per week? (first big YOU task) |
| Time limits, two strikes | overruns; a task fails twice | after two failed attempts, ask whether the task is still needed | (none) |
| Experiment cards | the first experiment | before running, write what each possible result would mean | (none) |
| "Worth it?" check | uncertain value | before deep work, look at the closest existing work and report | who would care? (before deep work) |
| Checks and hooks | a checkable rule is broken twice | arises during the work, not at setup | (none) |
