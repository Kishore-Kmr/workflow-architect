# Changing this workflow

The workflow checks itself after every step (`wf health`, a script) and changes itself when the
evidence says so. This file says how. Below, `wf` means `{{python}} tools/wf.py`.

## When the health check warns

1. Read the log lines it names. Say the likely cause in one line.
2. If it was a one-off and no change is needed, log why:
   `wf log AI "<why>" --tags "noted:<warning id>"`. The warning then counts only newer events.
3. Otherwise draft the smallest change that removes the cause. Prefer rewording or pausing what
   exists over adding. RULES.md keeps at most 12 rules in use: to add one, merge or pause one.
4. Size it:
   - **Small** (easy to undo; binds only the AI): add or reword a rule for the AI; tweak a
     template, a checklist or the wording of `tools/step.md`; turn a repeated instruction into
     a shortcut command; split a recurring task; pause an unused rule (`## R-3 (paused) ...`).
   - **Large:** add or remove a file, folder, command or helper agent; change how often the
     workflow stops (STATE.json "autonomy"), the look-back interval or the health thresholds;
     delete anything.
   - **Protected**, always the user's: everything under "Always ask first" in AGENTS.md, and how
     freely the workflow changes itself (STATE.json "evolution_level").
5. Apply or propose, by STATE.json "evolution_level":

   | Level | Small | Large | Protected |
   |---|---|---|---|
   | 1 | propose | propose | ask |
   | 2 | apply, report with undo | propose | ask |
   | 3 | apply, report with undo | apply, report with undo | ask |

6. Record it first, whether you apply it, propose it or ask (protected): otherwise the warning
   comes back at every step. `wf change add "<what changes>" --size <size> --by auto|proposed
   --measure <what should improve, usually the warning id> --evidence "<warning and steps>"
   --undo "<exact steps to reverse it>"`. Write the undo so that someone else could follow it.
   `wf` refuses an automatic change that the level does not allow. For a protected change,
   the change is the question to the user, e.g. "re-interview: move the finish line to a
   workshop paper?".
7. **Applied:** make the change. In the report say what changed, why, and "to undo, say
   'undo E-<n>'". **Proposed:** ask the user in the report, under "Questions for you". When they
   answer, log their words as `YOU` with `[answered]` and add the decision to DECISIONS.md.
   Yes: make the change, then `wf change mark E-<n> trial "<their words>"`. No:
   `wf change mark E-<n> rejected "<their words>"`.

## Check-back

`wf health` says when a change on trial is due, with its numbers before and since:
- helped: `wf change mark E-<n> kept "<numbers>"`;
- not helped, applied automatically: follow its Undo line, then
  `wf change mark E-<n> undone "<numbers>"`, and say so in the report;
- not helped, applied by the user: propose undoing it;
- nothing to compare: mark it kept; the next look-back reviews it.

With few steps the numbers are a rough sign, not proof.

## Undo

When the user says "undo E-<n>": follow the Undo line in EVOLUTION.md exactly, then
`wf change mark E-<n> undone "you asked"`. If later edits mean the Undo line no longer fits,
show the user what you would change and ask first.

## /evolve: the user asks to review or change the workflow

1. Run `wf health` and tell the user in plain words: warnings, changes on trial, proposals
   waiting for them.
2. Offer, in one question: (a) a look-back now (`tools/lookback.md`); (b) undo a change; (c)
   answer the waiting proposals; (d) change how freely the workflow changes itself (level 1:
   it proposes every change; 2: small changes by itself, with undo; 3: small and large ones);
   (e) something changed: the goal, the finish line, a limit or a key fact.
3. Log the user's choice and words as `YOU` with `[answered]`, then do it.

## Re-interview: the goal, finish line, a limit or a key fact changed

Also when a look-back finds that the brief no longer matches what is happening.

1. Find the parts of BRIEF.md it affects. Ask only about those: at most four questions at a
   time, each saying why it is asked; offer a default where you can.
2. Draft the new brief: version +1, with a "## Changes" section at the bottom, one line per
   change: "v<old> -> v<new>: <before> -> <after> (the user's words)". Show it, and replace
   BRIEF.md only after the user approves.
3. Record the approval word for word in DECISIONS.md, set STATE.json "brief_version", and log
   it with `[answered]`.
4. Check the workflow against the new brief: parts, rules, questions saved for later. Each
   change that follows is a workflow change: size it, then apply or propose it as above.
