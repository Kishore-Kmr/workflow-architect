# One step

A step does exactly one action from `NEXT.md` and leaves the files ready for the next step.
Below, `wf` means `{{python}} tools/wf.py`.

1. **Begin.** Run `wf begin`. It numbers the step, logs it and prints a three-line status.
   Read `NEXT.md`.
2. **Questions first.** If the actor in NEXT.md is YOU, ask the user whether it is done; if not,
   remind them what to do and stop. If anything blocks the action, ask now. Look in
   QUESTIONS.md "Just in time" for a trigger this action would hit, and ask that question first.
   Record answers: decisions word for word in DECISIONS.md, questions moved to "Answered" in
   QUESTIONS.md. Log `[asked]` when you ask and `[answered]` when they answer.
3. **Limits.** Check the action against the limits and "Your notes" in BRIEF.md, RULES.md and
   the protected list in AGENTS.md. If it would cross one, ask first.
4. **Do the action.** One action only, in the end-product part NEXT.md names.
5. **Record.**
   - Update the end product.
   - Log each event: `wf log AI "what happened" --part <part> --tags "<tags>"` (tags below).
     Log the user's actions and words as actor `YOU`.
   - Update STATE.json only if the phase changed.
   - Rewrite NEXT.md: exactly one next action, its actor (AI or YOU), its part, "Done when".
   - Git: {{git policy, e.g. "commit with a message saying what moved; never push" or "do not commit; the user commits" or "no git"}}.
6. **Check.** Run `wf check`. Fix any problem in the workflow files before reporting, and log
   the fix with `[workflow]`.
7. **Report**, short and plain:
   - Moved: which part changed and how, or "nothing moved in the end product".
   - Next: the action in NEXT.md and who does it.
   - Questions for you: only if there are any.
   - Workflow: the `wf check` result.
8. **Continue or stop.** {{Autonomy, one of: "Stop after the report." or "Begin the next step, unless the next actor is YOU, a question is waiting, a limit is near or the check failed."}}

## Tags

Each log line gets the tags that apply; none is fine for a plain note. The workflow later reads
these tags to check its own health, so be accurate rather than generous.

| Tag | Use when |
|---|---|
| `[progress:<part>]` | the end product changed in that part (a part name from STATE.json) |
| `[workflow]` | the work was on the workflow itself, not on the end product |
| `[fail]` | an attempt did not work |
| `[redo]` | redoing work that was considered done |
| `[correction:<key>]` | the user corrected you; `<key>` names the kind of mistake |
| `[repeat:<key>]` | the user gave an instruction they had given before |
| `[asked]` / `[answered]` | you asked the user something / they answered |
| `[escaped:<where>]` | an error turned up that an earlier check should have caught |
| `[used:<module>]` | a module listed in STATE.json "modules" was used |
| `[overrun]` | the step took much longer than expected |
| `[rule:<id>]` | a rule in RULES.md changed what you did |

Keys are lowercase words with hyphens (`missing-source`). Before inventing a key, search LOG.md
for keys already used and reuse the same key for the same kind of issue. If the user says
something about the workflow is annoying, log their words with `[workflow]` and a
`[correction:<key>]`. `[begin]` is written by `wf begin`; don't add it yourself.
<!-- no-python -->

## Without tools/wf.py (this project has no Python)

- `wf begin`: add 1 to "step" in STATE.json, then append to LOG.md
  `- YYYY-MM-DD HH:MM | S-<step as 3 digits> | AI | step begins | - | [begin]`. Status = the
  NEXT.md action, the last LOG.md line, and the number of open questions.
- `wf log`: append one line in exactly the format `- time | step | actor | what | part | tags`.
  Part is a name from STATE.json "parts" or `-`; tags use only the table above.
- `wf check`: NEXT.md has exactly one `Actor:` (AI or YOU) and one non-empty `Action:`;
  STATE.json is valid JSON; AGENTS.md has at most 80 lines; RULES.md has at most 12 rules.
<!-- /no-python -->
