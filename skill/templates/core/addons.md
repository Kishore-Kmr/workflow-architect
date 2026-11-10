# Add-ons

Extra parts this workflow can switch on when the project needs them, and switch off when they
go unused. STATE.json "addons" shows which are on. Below, `wf` means `{{python}} tools/wf.py`.

Switching an add-on on is a big workflow fix; who may switch it off is said below (see
`tools/fixes.md`). When a question saved for later leads to an add-on, say so in the question
("I'll switch on the budget add-on with your answer"): the user's answer is then the approval.

## Budget

- **Needed when:** the first paid resource is planned: paid API or LLM calls, GPUs, cloud
  compute, data, annotators, services.
- **Ask:** the spending cap and its currency, and the amount above which a single cost needs
  the user's OK first.
- **Switch on:** log the user's answer with `[answered]`, put it in STATE.json "limits" as
  `"budget": {"cap": 30, "currency": "USD", "ask_over": 5}`, then `wf addon on budget`. It
  creates SPENDING.md.
- **While on:** before any paid action, estimate its cost and record it:
  `wf spend <amount> "<what>" --estimate`. `wf` refuses a spend that would go over the cap,
  and a single cost over "ask_over" unless the user's OK is logged in this step. When the real
  cost is known and differs, record the difference: `wf spend <difference> "<what>: measured"`
  (a negative number if it cost less). Never spend outside `wf spend`. SPENDING.md lines:
  `- time | step | amount | estimate or measured | what`.
- **Health:** warns at 80% of the cap.
- **Switched off by:** the user only.

## Second opinion

- **Needed when:** mistakes in a part would be costly or hard to spot, or a mistake got past
  (an `[escaped]` warning).
- **Ask:** which parts need it. If another AI tool is installed (STATE.json "tools"), whether to
  use it for the second opinion: a different model notices different mistakes. Default: a
  fresh AI in this tool.
- **Switch on:** `wf addon on second-opinion --parts <part,part>`. It creates
  SECOND-OPINIONS.md. Then write `tools/second-opinion.md` and, in Claude Code,
  `.claude/agents/second-opinion.md`, both as shown below; add both to the file map in
  AGENTS.md.
- **While on:** work on a listed part counts as done only after a pass.
  - Ask a helper agent with a fresh context (in Claude Code, the `second-opinion` agent) to
    follow `tools/second-opinion.md`. Give it only the part's file, its "Done when" line, the
    goal from BRIEF.md and the sources the work relies on; never LOG.md or your reasoning. If
    the user chose another AI tool, run that tool with the same instruction. With no helper
    agents, ask the user to open a fresh session and say "give a second opinion on <part>".
  - Record its verdict exactly as given: `wf opinion <part> pass|fail "<its findings, short>"`.
  - After a fail, fix the work (`[redo]`) and ask again.
  - If the user later finds a mistake in work that passed, log it with
    `[escaped:second-opinion]` and add their example under "Examples" in
    `tools/second-opinion.md`.
- **Health:** warns when 15 second opinions in a row passed: it may be checking more than
  needed. Using it less is the user's to decide.
- **Switched off by:** the user only.

`tools/second-opinion.md`:

```
# Second opinion

You check one piece of work before it counts as done. You did not make it, and you see only:
the work, its "Done when", the project goal, and the sources it relies on. You change nothing.

1. Check the work against its "Done when" and the goal.
2. Check every claim against its sources: does the source exist, and does it say this?
3. Answer in at most 10 lines: the first line is `pass` or `fail`, then each problem and where
   it is.

## Examples of mistakes that got past before (from the user)
- (none yet)
```

`.claude/agents/second-opinion.md` (Claude Code only):

```
---
name: second-opinion
description: Checks one piece of work before it counts as done. Reads only; changes nothing.
tools: Read, Grep, Glob
---

Read tools/second-opinion.md in the project folder and follow it.
```

## Experiment plans

- **Needed when:** the first experiment: a run whose result is not known in advance (a pilot,
  a comparison, a benchmark).
- **Ask:** nothing.
- **Switch on:** `wf addon on experiment-plans`. It creates the `experiments/` folder.
- **While on:** never run an experiment without a started plan.
  1. `wf experiment new "<title>"` creates `experiments/X-<n>-<title>.md`.
  2. Fill in Question, Setup and "What each result would mean": for each likely result, what
     we would conclude and what we would do next.
  3. `wf experiment start X-<n>` locks "What each result would mean".
  4. Run the experiment, then fill in Results and What we learned.

  The check fails if the locked section is edited later, or if results are written before the
  start.
- **Switched off by:** the AI (a small fix), when unused.
