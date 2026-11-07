---
name: workflow-architect
description: Sets up a small, self-checking workflow for a project in the current folder. Checks the machine, interviews the user adaptively, shows a one-page brief and a structure proposal, writes the files only after approval, and tests them with a practice round. Use when the user starts a new project, asks to set up or plan a project workflow, or types /workflow-architect.
---

# workflow-architect (v0.1)

You set up the smallest workflow that fits this user's project, in the current folder. Go
through the phases in order: 0 resume, 1 machine check, 2 interview, 3 brief, 4 structure
proposal, 5 generate, 6 practice round, 7 handover. `<skill>` below means the folder this file
is in.

## Rules for every phase

1. **Check facts, ask intentions.** What you can verify (OS, tools, files), check. Goals,
   preferences, limits and decisions, ask. Never fill in an intention silently.
2. **Ask only what changes the design.** Each question says in one line why it is asked and
   what the answer changes.
3. **Show before writing.** Until the user approves the brief and then the structure, write
   nothing in the project except `.workflow-architect/interview.json`.
4. **Never change, move or delete existing files without asking.** Build around them.
5. **Honesty.** Never record a decision the user did not make; quote their words. Label numbers
   as measured, estimated or assumed.
6. **No questions about the cost of running you**; the user monitors it. Money questions are
   only about external spending.
7. **Plain words**, from the user's point of view. Keep messages short.

## How to ask

At most four questions per batch. If your tool has a structured question feature (multiple
choice with a free-text "Other"), use it. Otherwise write numbered questions with lettered
options, the recommended option first and marked "(recommended)", and say the user may answer
in their own words. Ask open questions in plain text when answers can't be predicted.

Recommend an option only when it is clearly better for this user. If the inclusive choice does
no harm (e.g. supporting more tools), don't ask: do it and say so in the brief. Prefer a
default in the brief (marked **OK?**) over a question.

## Phase 0: resume

- If `.workflow-architect/interview.json` exists, say which stage it reached and offer to
  resume. Starting over keeps the old file, renamed `interview.old.json`, after asking.
- If `STATE.json` and `NEXT.md` already exist, the folder is already set up: say so and stop.
  (Re-interviewing an existing workflow comes in a later version.)

## Phase 1: machine check

The machine check asks nothing: the user's first question is always about the goal (phase 2).
What needs the user goes to the interview, asked after the seed questions.

1. Find a working Python: try `python3 --version`, `python --version`, `py --version`. On
   Windows, "Python was not found" comes from a fake Store placeholder: it means not installed.
   Run `<python> <skill>/scripts/probe.py .` (read-only).
2. **No Python:** check the basics by hand (OS, git, folder contents, AGENTS.md / CLAUDE.md).
   After the seed questions, tell the user, in plain words: "Python isn't installed. The workflow still works without
   it, but its checker (`tools/wf.py`) can't run, so I would do those checks by reading the
   files: slower, more tokens, less reliable. Later versions also use it for the workflow's
   self-checks." Offer: (a) install Python, naming the command for this machine (e.g.
   `winget install Python.Python.3.13`, `brew install python`, `sudo apt install python3`), or
   (b) continue without it. Install only after a yes, then run the probe.
3. Report the findings in at most 3 lines, without questions. Note as unknowns for the
   interview, to ask after the seed questions: existing files (build around them? what to
   keep?); Python missing. Possible secrets that git does not ignore: name them (names only)
   and plan `.gitignore`.
   Never ask which AI tools the user will use: adapters are made for the tool you are running
   in and for any other installed tool that needs one (see phase 5). You know which tool you
   are: state it.
4. Create `.workflow-architect/interview.json` (format in `<skill>/interview/planner.md`) with
   the machine summary and the answers.

## Phase 2: interview

Read `<skill>/interview/planner.md` and `<skill>/interview/coverage-map.md`, then follow the
planner: the seed questions first (always the first questions), then at most a short batch of
what the setup needs now. Anything tied to a later stage is saved for later with that stage as
its trigger. Save interview.json after each batch.

## Phase 3: brief

Fill in part 1 of `<skill>/interview/brief-template.md` and show it in full. Every default you
proposed is marked **OK?**. Ask: approve, change, or ask. Revise until approved; record the
approval in interview.json with the user's words.

## Phase 4: structure proposal

Fill in part 2 of brief-template.md. The core (every project): AGENTS.md, BRIEF.md, NEXT.md,
STATE.json, LOG.md, DECISIONS.md, QUESTIONS.md, RULES.md, EVOLUTION.md, tools/step.md, tools/wf.py
(if Python), the end-product parts, and tool adapters. Add only what the brief
justifies, each with the answer behind it. Modules are not built in v0.1: if the brief shows a
need for one, say "needed, coming in a later version". Propose its temporary rule only if the
need applies to the first phase; for a later stage, only its just-in-time question (see the end
of brief-template.md). Ask: approve, change, or ask.

## Phase 5: generate

After approval, in the project folder. First tell the user that their tool may ask permission
for a few of these writes, and that approving them is expected (Claude Code asks before writing
inside `.claude/`, and may ask before copying `wf.py` from the skill folder). If a write is
refused, stop and offer options; don't work around it.

1. **Core files.** `BRIEF.md` is the approved brief. The rest come from `<skill>/templates/core/`:
   replace every `{{...}}` with content from the brief, or delete it where the placeholder says
   so. `step.md` goes to `tools/step.md`.
   Copy `<skill>/scripts/wf.py` to `tools/wf.py` with a file-copy command; don't retype it.
2. **Python or not.** With Python: delete the `<!-- no-python -->` block (and its markers) from
   tools/step.md. Without: keep the block, don't copy wf.py, set STATE.json "python" to null,
   and in AGENTS.md and step.md say the `wf` commands are done by hand (see tools/step.md).
3. **End product:** create each agreed part (a file with a heading and a one-line purpose, or a
   folder), and list them in STATE.json "parts" as name -> path. Existing files may be parts:
   point to them, don't move them.
4. **Adapters**, without asking: for the tool you are running in, and for every other installed
   tool that needs one. In v0.1 only Claude Code has an adapter:
   - Claude Code: `CLAUDE.md` from `<skill>/templates/adapters/claude-code/CLAUDE.md` (if a
     CLAUDE.md exists, ask to add the line `@AGENTS.md` to it instead), and
     `.claude/skills/step/SKILL.md` from `.../claude-code/step-skill.md`. Add `CLAUDE.md` to
     STATE.json "instruction_files".
   - Codex, Copilot and others read AGENTS.md: nothing extra; the user says "do a step".
   - Existing AGENTS.md: ask before changing it; propose adding a short "Workflow" section.
5. **RULES.md:** the two core rules, rules from the interview (Origin quotes the answer), and
   temporary rules for missing modules that apply to the first phase. No rule that repeats the
   core rules, the protected list or a setting. Few: usually 2 to 5; the cap is 12.
6. **QUESTIONS.md:** open questions, and just-in-time questions with triggers.
   **DECISIONS.md:** the user's decisions from the interview, word for word and dated,
   including the approvals of the brief and the structure.
7. **Git** as agreed: `git init` only if approved; `.gitignore` for secrets found. Don't commit
   yet.
8. Log the setup: `<python> tools/wf.py log AI "workflow set up: brief v1, structure v1"
   --tags workflow`. Then run `<python> tools/wf.py check` and fix every problem.

## Phase 6: practice round

Test every part on this machine with a dummy task (`wf` = `<python> tools/wf.py`):

1. Write NEXT.md as: `Actor: AI` / `Action: Practice: write one line in
   .workflow-architect/practice.md` / `Part: practice` / `Done when: the file exists`.
2. Follow tools/step.md for one step, using `wf begin --practice` instead of `wf begin`: write
   the file, log it with `--part practice --tags "progress:practice"`, rewrite NEXT.md with the
   real first action from the brief, run `wf check`, and draft the report. Skip git in this
   step: practice work is never committed.
3. Run `wf practice-done`. It removes the practice log lines and file, records that the round
   passed, and runs the check again.
4. If git is used: commit ("Set up workflow with workflow-architect") only if the user chose to
   commit after each step; otherwise leave it to them.
5. If anything failed, explain it plainly and fix it, or propose a replacement and ask. Don't
   hand over until the round passes. Without Python, do the same steps by hand.

## Phase 7: handover

In at most 8 lines: what was built (number of files); the first action and who does it; how to
continue: open a fresh session in this folder and type `/step` (Claude Code) or say "do a step"
(other tools); everything is kept in the files, so sessions can be short; what they will be
asked later and when. Set interview.json "stage" to "done".
