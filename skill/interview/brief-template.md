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
  tools/addons.md  extra parts it can switch on later (budget, second opinion, experiment plans)
  tools/wf.py      status, log, checks, health               <- because: Python is available
  .claude/skills/  the /step and /workflow commands            <- because: you use Claude Code
  <end-product parts, e.g. deliverable/outline.md>           <- because: <answer>

Existing files: <kept as they are; which ones the parts point to>
Rules from your answers: <rule> <- because: <answer>
Add-ons switched on now: <add-on> <- because: <answer> (or "none")
Add-ons later: <add-on>, switched on when <trigger>, with question Q-<n>
Not added: <add-on>: <why not>; would be added if <what would change it>
You will be asked during the work: <just-in-time questions and their triggers>
Git: <what will happen, e.g. "git init, then one commit after the practice round">
```

Then ask: approve, change, or ask about something.

## Add-ons

Full details in `<skill>/templates/core/addons.md`. If the brief shows a need:
- **In the first phase:** propose switching the add-on on at setup; ask its questions now.
- **In a later stage** (e.g. budget before the first paid call, experiment plans before the
  first experiment): propose only a just-in-time question that says it will switch the add-on
  on; the user's answer is then the approval.
- Never propose a rule for what an add-on does, or one that repeats the core rules, the
  "Always ask first" list in AGENTS.md (spending, outward actions, irreversible steps) or a
  setting (autonomy, reports, git). A new project usually needs 2 to 5 rules in all.
- No add-on is needed for go/no-go moments or the user's time: each progress review at a phase
  end puts the go/no-go decision to the user, and every task for the user carries a time
  estimate.

| Add-on | Needed when | Asked when it is switched on | Switched off by |
|---|---|---|---|
| Budget | the first paid resource (APIs, GPUs, data, annotators) | the cap and its currency; above what amount a single cost needs the user's OK | the user |
| Second opinion | mistakes would be costly or hard to spot, or one got past | which parts; whether to use another installed AI tool | the user |
| Experiment plans | the first experiment | nothing | the AI, when unused |
