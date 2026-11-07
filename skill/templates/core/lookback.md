# Look-back

Every few steps (STATE.json "lookback_every") and at the end of each phase, someone who did not
do the work looks at how the workflow is doing: the AI that did the steps should not grade its
own process. Below, `wf` means `{{python}} tools/wf.py`.

## Who does it

- If this session did none of the recent steps, do it yourself.
- If this session did some of them: give the look-back to a helper agent with a fresh context,
  if your tool has one (in Claude Code, the Agent tool), with this instruction: "Read
  tools/lookback.md in <project folder> and do the look-back as the helper." If your tool has
  no helper agents, stop and ask the user to open a fresh session and say "do a look-back".
- The helper only reads, writes the report and logs it. It changes nothing else.

## Read

`wf health`; BRIEF.md; STATE.json; RULES.md; EVOLUTION.md; QUESTIONS.md; NEXT.md; the LOG.md
lines since the last look-back; a quick look at each end-product part.

## Answer, with evidence (step numbers)

1. Moving: what moved in the end product since the last look-back? Is it heading for the
   finish line?
2. Friction: where did steps fail, get redone, wait for someone, or take long?
3. Unused: rules that never mattered, files or parts nobody used, questions nobody needs.
4. Brief: do the goal, the finish line, the limits and "Your notes" still match what is
   happening?
5. Changes on trial: are they helping?

## Write

Add to the end of EVOLUTION.md, at most 15 lines:

```
## L-<n> | look-back at S-<step>
- Moving: ...
- Friction: ...
- Unused: ...
- Brief: still true | ask the user about: <which part>
- Changes on trial: ...
- Suggested changes: <each with its size: small, large or protected> | none
```

Then log it: `wf log AI "look-back L-<n>: <one line>" --tags "workflow lookback"`.

## Afterwards (the AI running the workflow, not the helper)

Handle each suggested change as `tools/evolve.md` says (size, level, record, report). If the
brief no longer matches, ask the user whether to re-interview (`tools/evolve.md`). Tell the user
what the look-back found in at most five lines.
