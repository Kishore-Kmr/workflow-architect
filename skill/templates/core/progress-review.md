# Progress review

Every few steps (STATE.json "review_every") and at the end of each phase, an AI that did not do
the work checks whether the work is moving and what slows it down: the AI that did the steps
should not grade its own process. Below, `wf` means `{{python}} tools/wf.py`.

## Who does it

- If this session did none of the recent steps, do it yourself.
- If this session did some of them: give the review to a helper agent with a fresh context, if
  your tool has one (in Claude Code, the Agent tool), with this instruction: "Read
  tools/progress-review.md in <project folder> and do the progress review as the helper." If
  your tool has no helper agents, stop and ask the user to open a fresh session and say "do a
  progress review".
- The helper only reads, writes the report and logs it. It changes nothing else.

## Read

`wf health`; BRIEF.md; STATE.json; RULES.md; WORKFLOW-FIXES.md; QUESTIONS.md; NEXT.md; the
LOG.md lines since the last progress review; a quick look at each end-product part.

## Answer, with evidence (step numbers)

1. Moving: what moved in the end product since the last review? Is it heading for the finish
   line?
2. Friction: where did steps fail, get redone, wait for someone, or take long?
3. Unused: rules that never mattered, add-ons or files nobody used, questions nobody needs.
4. Brief: do the goal, the finish line, the limits and "Your notes" still match what is
   happening? At the end of a phase: does anything in the brief's "Stop if" list apply?
5. Fixes being tested: are they helping?

## Write

Add to the end of WORKFLOW-FIXES.md, at most 15 lines:

```
## Progress review <n> | at S-<step>
- Moving: ...
- Friction: ...
- Unused: ...
- Brief: still true | ask the user about: <which part>
- Stop if: nothing applies | <which item, and the evidence> (at the end of a phase)
- Fixes being tested: ...
- Suggested fixes: <each with its size: small, big or yours> | none
```

Then log it: `wf log AI "progress review <n>: <one line>" --tags "workflow review"`.

## Afterwards (the AI running the workflow, not the helper)

- Handle each suggested fix as `tools/fixes.md` says (size, fix level, record, report).
- If the brief no longer matches, ask the user whether to re-interview (`tools/fixes.md`).
- At the end of a phase, put the go/no-go decision to the user: NEXT.md becomes
  `Actor: YOU`, `Action: decide: continue into <next phase>, narrow, change direction, or
  stop`, with the evidence in the report, including any "Stop if" item that applies. If they
  choose to stop or to change direction, first add the entry to STOP-NOTE.md (see AGENTS.md).
- Tell the user what the review found in at most five lines.
