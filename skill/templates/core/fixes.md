# Fixing this workflow

The workflow checks itself after every step (`wf health`, a script) and fixes itself when the
evidence says so. This file says how. Below, `wf` means `{{python}} tools/wf.py`.

## When the health check warns

1. Read the log lines it names. Say the likely cause in one line.
2. If it was a one-off and no fix is needed, log why:
   `wf log AI "<why>" --tags "noted:<warning id>"`. The warning then counts only newer events.
3. Otherwise draft the smallest fix that removes the cause. Prefer rewording or pausing what
   exists over adding. RULES.md keeps at most 12 rules in use: to add one, merge or pause one.
4. Size it:
   - **Small** (easy to undo; binds only the AI): add or reword a rule for the AI; tweak a
     template, a checklist or the wording of `tools/step.md`; turn a repeated instruction into
     a shortcut command; split a recurring task; pause an unused rule (`## R-3 (paused) ...`);
     switch off an add-on whose entry in `tools/addons.md` says "switched off by: the AI".
   - **Big:** switch an add-on on; add or remove a file, folder or command; change how often the
     workflow stops (STATE.json "autonomy"), the progress review interval or the health
     thresholds; delete anything.
   - **Yours** (always the user's to decide): everything under "Always ask first" in AGENTS.md;
     how freely the workflow fixes itself (STATE.json "fix_level"); anything in BRIEF.md, and
     so every re-interview; switching off an add-on that only the user may switch off.
5. Make it or propose it, by STATE.json "fix_level":

   | Fix level | Small | Big | Yours |
   |---|---|---|---|
   | 1 | propose | propose | ask |
   | 2 | make it, report with undo | propose | ask |
   | 3 | make it, report with undo | make it, report with undo | ask |

6. Record it first, whether you make it, propose it or ask: otherwise the warning comes back at
   every step. `wf fix add "<what changes>" --size small|big|yours --by ai|proposed
   --measure <what should improve, usually the warning id> --evidence "<warning and steps>"
   --undo "<exact steps to reverse it>"`. Write the undo so that someone else could follow it.
   `wf` refuses a fix by the AI that the fix level does not allow. For a fix that is yours, the
   fix is the question to the user, e.g. "re-interview: move the finish line to a workshop
   paper?".
7. **Made:** make the fix. In the report say what changed, why, and "to undo, say
   'undo fix <n>'". **Proposed:** ask the user in the report, under "Questions for you". When
   they answer, log their words as `YOU` with `[answered]` and add the decision to
   DECISIONS.md. Yes: make the fix, then `wf fix mark F-<n> testing "<their words>"`. No:
   `wf fix mark F-<n> rejected "<their words>"`.

## Re-check

`wf health` says when a fix being tested is due for its re-check, with the numbers before and
since:
- helped: `wf fix mark F-<n> kept "<numbers>"`;
- not helped, made by the AI: follow its Undo line, then `wf fix mark F-<n> undone
  "<numbers>"`, and say so in the report;
- not helped, made by the user: propose undoing it;
- nothing to compare: mark it kept; the next progress review looks at it again.

With few steps the numbers are a rough sign, not proof.

## Undo

When the user says "undo fix <n>" (or "undo F-<n>"): follow the Undo line in WORKFLOW-FIXES.md
exactly, then `wf fix mark F-<n> undone "you asked"`. If later edits mean the Undo line no
longer fits, show the user what you would change and ask first.

## /workflow: the user asks about the workflow itself

1. Run `wf health` and tell the user in plain words: warnings, fixes being tested, proposals
   waiting for them, add-ons that are on.
2. Offer, in one question: (a) a progress review now (`tools/progress-review.md`); (b) undo a
   fix; (c) answer the waiting proposals; (d) change how freely the workflow fixes itself (1:
   it proposes every fix; 2: small fixes by itself, with undo; 3: small and big ones); (e)
   something changed: the goal, the finish line, a limit or a key fact.
3. Log the user's choice and words as `YOU` with `[answered]`, then do it.

## Re-interview: the goal, finish line, a limit or a key fact changed

Also when a progress review finds that the brief no longer matches what is happening.

1. Find the parts of BRIEF.md it affects. Ask only about those: at most four questions at a
   time, each saying why it is asked; offer a default where you can.
2. Draft the new brief: version +1, with a "## Changes" section at the bottom, one line per
   change: "v<old> -> v<new>: <before> -> <after> (the user's words)". Show it, and replace
   BRIEF.md only after the user approves.
3. Record the approval word for word in DECISIONS.md, set STATE.json "brief_version", and log
   it with `[answered]`.
4. If the change drops a direction, add its entry to STOP-NOTE.md (see AGENTS.md).
5. Check the workflow against the new brief: parts, rules, add-ons, questions saved for later.
   Each change that follows is a workflow fix: size it, then make or propose it as above.
