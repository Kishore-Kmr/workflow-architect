# {{project name}}

{{One or two sentences from BRIEF.md: what this project makes, for whom, and the finish line.}}

This folder runs a small workflow set up by workflow-architect. Its files are the memory: read
them instead of relying on earlier conversations. Sessions can be short and fresh.

## Start of every session

1. Read `NEXT.md`: the one next action and who does it (AI or YOU).
2. Run `{{python}} tools/wf.py status` for a short status (it says when a progress review is due).
3. To move the project forward, do one step: follow `tools/step.md`.{{ Tool shortcut, e.g. " In Claude Code: `/step`." or delete}}
4. Before any work, read `RULES.md` and the "Your notes" section of `BRIEF.md` (the user's own
   notes and assumptions; they may add to it at any time). Read the rest of `BRIEF.md` when
   you need the goal, limits or style.

## The workflow checks and fixes itself

After each step, `tools/wf.py health` checks the workflow. Small fixes may be made by the AI
(STATE.json "fix_level"); each is recorded in `WORKFLOW-FIXES.md` with how to undo it. When
the user says "undo fix <n>", asks about the workflow itself, or says the goal or a key fact
changed, follow `tools/fixes.md`.{{ Tool shortcut, e.g. " In Claude Code: `/workflow`." or delete}}

## Core rule: when unsure, ask; don't assume

Stop and ask {{the user's name, or "the user"}} when:
- the brief does not cover the case;
- two readings of a request would lead to different work;
- an action would exceed a limit in BRIEF.md;
- an action cannot be undone.

{{How strict, from the interview, e.g. "Small wording choices in drafts: decide yourself and list them in the report." or delete}}

Never record a decision the user did not make. Label numbers as measured, estimated or assumed.

## Always ask first (the user's to decide)

The goal, finish line and success criteria; spending money or the user's hours beyond the
limits; go/no-go decisions; deleting work or data, or anything irreversible; anything outward
(push, publish, contacting people); rules that constrain the user; new paid tools or accounts;
how freely the workflow fixes itself (fix level).

## Where things are

| File | What it holds |
|---|---|
| `BRIEF.md` | the approved brief: goal, finish line, limits, how we work |
| {{end-product location, e.g. `deliverable/`}} | the end product; its parts and paths are in `STATE.json` |
| `NEXT.md` | exactly one next action and its actor |
| `STATE.json` | phase, step number and settings |
| `LOG.md` | one line per event, with tags |
| `DECISIONS.md` | the user's decisions, word for word, dated |
| `QUESTIONS.md` | open questions, and questions saved for later with their triggers |
| `RULES.md` | project rules, each with its origin |
| `WORKFLOW-FIXES.md` | fixes to this workflow, with undo, and progress review reports |
| `tools/step.md` | how to do one step |
| `tools/fixes.md` | how the workflow fixes itself; undo; re-interview |
| `tools/progress-review.md` | the regular progress review by a fresh AI |
| `tools/wf.py` | status, begin, log, check, health, fix |
