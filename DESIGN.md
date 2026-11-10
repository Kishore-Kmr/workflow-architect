# workflow-architect — design

Draft 4 · 2026-11-07 · Target: any AI coding tool (harness-agnostic); v0.1 hand-tested in Claude Code
Status: v0.1, v0.2 and v0.3 built and tested (see `tests/`); v0.3 closed 2026-11-10 on the
builder's tests. Next: v0.4 (section 10). Decisions so far: section 12. Open questions: section 13.

## 1. What it is

A personal skill for AI coding tools (Claude Code, Codex and others that read skills). You open
your tool in a project folder and start the skill (in Claude Code: `/workflow-architect`). It
checks the machine, interviews you adaptively, reads back a one-page
brief, proposes the smallest workflow that fits, builds it after your approval and tests it with a
practice round. During the project the workflow checks its own health and evolves: it adds what
is missing, removes what is unused, and asks you before any change you have not delegated.

## 2. Principles

1. **Check facts, ask intentions.** What the agent can verify (OS, tools, files) it checks. Goals,
   preferences, limits and decisions it asks. It never fills in an intention silently.
2. **Ask only what changes the design.** Every question names the design decision it informs; if
   no answer would change the workflow, it is not asked. Inferences are confirmed, not assumed.
3. **Show before writing.** The brief and the structure are approved before files are created.
4. **Minimal core; everything else is earned.** Parts are added when an answer or evidence
   justifies them, and removed when unused.
5. **Evolve from evidence.** Every change cites the log lines behind it, states its expected
   effect and is checked afterwards; changes that do not help are rolled back.
6. **Explicit authority.** You decide which fixes the workflow may make by itself; some decisions
   are always yours.
7. **Files are the memory.** Handoffs, decisions and changes are files, so sessions can be short
   and fresh, and everything can be audited.
8. **Honesty.** Never record a decision you did not make; label numbers (measured, estimated,
   assumed); every report says what moved in the end product, or that nothing did.

## 3. Phases

### 3.1 Machine check

`scripts/probe.py` (read-only) finds the OS and shell, git, Python, installed AI CLIs, the folder's
contents and any existing CLAUDE.md, AGENTS.md or `.claude/`. It reports what it found in a few
lines and asks nothing: the first question is always about the goal. What needs you ("the folder
has 14 files: build around them?") is asked after the goal questions. It never changes existing
files without asking. It notes which AI tool is running and which others are installed. If Python
is missing it explains the impact in plain terms (the `tools/wf.py` checks would then be done by
the agent reading files: slower, costlier, less reliable) and you choose: install it, or skip it.

### 3.2 Adaptive interview

There is no fixed questionnaire. The interviewer keeps:
- a **project model**: facts, each labelled *you said*, *checked* or *inferred (to confirm)*;
- a list of **open unknowns**, derived from the coverage map (3.2.2) and the answers so far.

#### 3.2.1 Seed questions (always asked)

1. What are you making?
2. What is the goal: what does success look like, and who judges it?
3. Optional, open: "Anything else the workflow should know?" The single place for specifics and
   assumptions (deadline, known work, data, people, paid services, constraints, worries), shown
   as hints, not asked one by one. The interviewer reads back what it took; the answer is kept
   word for word in BRIEF.md "Your notes", which you can add to at any time.

The seeds are always the first questions.

#### 3.2.2 Coverage map: what a design must eventually know

Topics, not questions. The wording of each question is generated from the conversation.

| Topic | Relevant when | Feeds |
|---|---|---|
| End product and success | always | end-product skeleton, finish line, review criteria |
| Size, timeline, deadline | always (often inferable) | phases, step size, progress review interval |
| Existing material | folder not empty, or prior work mentioned | what is kept; build-around plan |
| People and roles | others involved (co-authors, clients, annotators) | permissions, human handoffs, review |
| Your decisions and involvement | always (light) | decision points, autonomy, asking policy |
| Human effort | the goal needs human work (expert judgement, labelling, user tests) | hours tracking; warning before big manual tasks |
| External resources and spending | GPUs, cloud compute, paid APIs or LLM calls, data, annotators, services | budget add-on |
| Data, access, legal, ethics | datasets, human subjects, licences, private data | feasibility checks; approvals as decision points |
| Quality and verification | always; the form varies (tests, validation, editing) | second opinion, checks, validation plan |
| Value and novelty | success depends on being new or valuable (research, product) | "worth it?" check before deep work |
| Risks and unknowns | always | first actions (smallest decisive test), stop criteria |
| Working preferences | always (light) | report style, git, how freely the workflow fixes itself (default 2, confirmed in the brief) |
| Tools available | from the machine check; asked only if ambiguous | which tools could give a second opinion |

Not asked by default: the cost of the agent running the project (you monitor it yourself).
Domain packs (section 8) add topics, e.g. research: target venue, closest work, how labels are
validated, test-split hygiene; fine-tuning: compute provider, data licence, evaluation set.

#### 3.2.3 Question planner (after every batch of answers)

1. Update the project model; read back anything taken from free text.
2. Mark each topic *relevant*, *not relevant (with reason)* or *unknown yet*.
3. List the unknowns the setup needs now (no sensible default, and the brief or structure
   cannot be written without them). Unknowns tied to a later stage (experiments, spending,
   labelling, other people, submission) are not asked now: they become just-in-time questions
   triggered by that stage. The "Always ask first" list already makes every spend wait for you.
4. Rank them by impact (how different the structure would be across answers) and dependency
   (prerequisites first).
5. Ask at most four, in one batch (with the tool's question feature if it has one, else plain
   text with lettered options): multiple choice with "Other" when answers are predictable,
   open text when not; each with one line on why it is asked and what it changes, and a
   recommended option where there is one.
6. Stop when nothing the setup needs now is unknown (usually after the seeds and at most one
   short batch). The rest become **just-in-time questions** in
   QUESTIONS.md, each with a trigger (e.g. "the first time a task would spend money").

Rules: vague answers get one follow-up ("good quality" → "how would we check it?"); "decide
later" is always allowed and recorded with a trigger; progress is shown as "about N open points
left"; answers are saved after each batch (`.workflow-architect/interview.json`) so the interview
can resume in a fresh session.

#### 3.2.4 Example: same seeds, different paths

| Seed answers | Asked at setup (if not in the notes) | Saved for later, with trigger |
|---|---|---|
| A study of whether AI graders favour long answers; is it publishable? | usually nothing more | paid APIs and cap (first experiment); labels and hours (first labelling task); venue (once judged worth it) |
| A budgeting app for myself; I'll use it monthly | existing code: build on it? | hosting (if it ever leaves the laptop) |
| Fine-tune a small model; must beat baseline Y | none, if the data is here | GPU provider and budget (first training run); data licence (before first use) |

### 3.3 Brief readback

One page: goal, finish line, limits, how you want to work (including how freely the workflow
fixes itself and the progress review), relevant topics,
skipped topics with reasons, open and just-in-time questions, and every proposed default marked
"OK?". Nothing is built until you approve it.

### 3.4 Structure proposal

The folder tree: the core plus only the add-ons the brief justifies for the first phase (each
with the answer that triggered it), the add-ons expected later and what will switch them on,
and what you will be asked during the work. You approve, change or ask.

### 3.5 Generation and practice round

Write the files, then run one practice cycle with a dummy task through every enabled part
(the step, the log, NEXT, the checks and any add-on that is on). Anything that fails on this machine is fixed or
replaced, with your agreement, before handover. The dummy work is removed.

### 3.6 Working loop: the step (`/step` in Claude Code; "do a step" in any tool)

1. Status in three lines (`wf.py begin`, which also numbers the step).
2. Ask any question that blocks the next action; record the answer.
3. Check limits: the budget (if that add-on is on), the time estimate on tasks for you, and
   the "Always ask first" list.
4. Do the action. With add-ons on: a paid action goes through `wf.py spend`; an experiment runs
   only after its plan is started; work on a listed part is done only after a second opinion's
   pass.
5. Update the end product, LOG (with tags), STATE and NEXT (exactly one action); commit if chosen.
6. Health check (`wf.py health`, a script, no AI cost: the file checks, then the metrics);
   fix the workflow if a signal fired (section 7). If a progress review is due, it is the next
   step's action.
7. Report: what moved in the end product (or "nothing moved"), external spend if any, the
   second opinion's verdict, next action, questions for you (including proposed workflow
   fixes), one-line workflow health, fixes it made by itself (with "to undo, say 'undo fix
   <n>'").
8. Continue or stop, according to the autonomy level.

## 4. Minimal core (every project)

| File | Purpose |
|---|---|
| `AGENTS.md` | short: what this is, how to start, the rules, where things are (read by most AI tools) |
| tool adapters | only for the tools you use, e.g. a `CLAUDE.md` that imports AGENTS.md, and `/step` in `.claude/skills/step/` |
| `BRIEF.md` | the approved brief (versioned) |
| `deliverable/` | the end-product skeleton; every task fills a named part |
| `NEXT.md` | exactly one next action and its actor (AI or YOU); an action for you carries a time estimate |
| `STATE.json` | phase, brief and structure versions, autonomy, fix level, add-ons, settings; budget and hours only if relevant (open questions are counted from QUESTIONS.md, not copied) |
| `LOG.md` | one line per event: time, actor, what, end-product part, tags |
| `DECISIONS.md` | your decisions, word for word, dated |
| `QUESTIONS.md` | open and just-in-time questions with their triggers |
| `RULES.md` | a few rules, each with its origin and its check (if any) |
| `WORKFLOW-FIXES.md` | every workflow fix: evidence, change, size, made by (the AI or you), measure, re-check, undo, outcome; and the progress review reports |
| `tools/step.md` | the step procedure in plain words, so any tool can follow it |
| `tools/fixes.md` | how the workflow fixes itself (sizes, fix levels, records), re-check, undo, `/workflow`, re-interview |
| `tools/progress-review.md` | the periodic progress review by a fresh AI |
| `tools/addons.md` | the add-ons it can switch on (section 5), with their instructions |
| `/workflow` | Claude Code adapter for tools/fixes.md; other tools: "check the workflow" |
| `tools/wf.py` | `status`, `begin`, `log`, `check`, `health`, `fix add` / `fix mark`, `addon on` / `off`, `spend`, `opinion`, `experiment new` / `start`, `practice-done` (if Python is available or installed with your OK) |

Rule in every AGENTS.md: **when unsure, ask; don't assume.** Agents stop and ask when the brief
does not cover the case, when two readings lead to different work, when an action would exceed a
limit, or when it cannot be undone. How strict this is comes from the interview.

## 5. Add-ons (added when needed, removed when unused)

| Add-on | Added when | Adds |
|---|---|---|
| Budget | the first paid external resource | a cap and an "ask first" amount; `SPENDING.md`; `wf.py spend` refuses to go over the cap; a warning at 80% |
| Second opinion | errors would be costly or hard to see, or an error slipped past | a second AI sees only the work, its "Done when", the goal and the sources, never the log or the driver's reasoning; cannot edit; ideally another model; your examples of missed errors go into its instructions; verdicts in `SECOND-OPINIONS.md` |
| Experiment plans | the first experiment | `experiments/X-<n>.md`: what each possible result would mean, locked by `wf.py experiment start` before the run |

No add-on needed (core): at the end of each phase the brief's "Stop if" list is checked and the
go/no-go decision is put to you; every task for you carries a time estimate.

## 6. How agents talk

The driver (the AI doing the step) works from the files. With the second-opinion add-on, the
work, its "Done when", the goal and the sources go to a fresh AI that never sees the log or the
driver's reasoning and cannot edit; its verdict goes into `SECOND-OPINIONS.md`, and the driver
fixes the work or writes a YOU action into NEXT.md. The progress review is also done by a fresh
AI. Each agent starts fresh with only what it needs. Between steps the autonomy level decides.

## 7. Self-checks and fixes (the evolution engine)

### 7.1 Signals: tags in LOG.md

`[progress:<part>]` `[workflow]` `[fail]` `[redo]` `[correction:<key>]` `[repeat:<key>]` `[asked]`
`[answered]` `[escaped:<where>]` `[used:<add-on>]` `[overrun]` `[rule:<id>]` `[review]`
`[noted:<warning>]`, plus timestamps, step numbers and a `[begin]` line at the start of each step
(for step durations). `wf.py spend`, `opinion` and `experiment` log `[used:...]` themselves.

### 7.2 Health metrics (`wf.py health`, every step, no AI cost)

Thresholds are starting values; a progress review can propose tuning them (a big fix).

| Metric | Warns when | Likely fix |
|---|---|---|
| Progress rate | under half of the last 10 steps moved the end product | re-plan; trim process |
| Rework rate | 3 or more of the last 10 steps were redo or fail | clearer actions in NEXT.md; a check or a second opinion |
| Repeated correction | the same key twice | a rule for the AI, plus a check if code can verify it; asked instead if it concerns the goal, a limit or a decision |
| Repeated instruction | the same key three times | a project command |
| Escaped error | any | tighten the check that missed it, or propose a second opinion |
| Second opinion finds nothing | the last 15 second opinions all passed | use it less (yours to decide) |
| Question backlog | more than 5 open, or one open for more than 3 working days (days with steps; sessions are not logged) | batch questions; adjust asking policy |
| Overrun | a step took 3× the median of the previous 10 and at least 20 minutes (steps with your own work left out), or was tagged `[overrun]` | split tasks |
| Unused add-on | no `[used:<add-on>]` in 20 steps | switch it off: a small fix for experiment plans; yours to decide for budget and second opinion |
| Budget | 80% of the cap spent | tell you; raising the cap is yours |
| Silent rule | no `[rule:<id>]` in 30 steps (core and paused rules left out) | pause, later retire |
| Process share | 3 of the last 5 steps were only `[workflow]` | warn: process is eating the work |
| Goal drift | work not linked to the brief or end product (judged by the progress review, not the script) | re-interview the affected topics |

A warning counts only events after it was last dealt with: a fix that measures it, or a
`[noted:<warning>]` log line saying why no fix is needed.

### 7.3 Check points

- **Every step:** the metrics, and one health line in the report.
- **When a metric warns:** the driver reads the evidence lines, names a likely cause and drafts a
  fix.
- **Every N steps and at each phase end** (N: default 10, shown in the brief for your OK): a
  **progress review** by a fresh AI that did not do the work (a helper agent with a fresh
  context if the tool has one, otherwise a fresh session). It writes only its report ("Progress
  review <n>" in WORKFLOW-FIXES.md): is the work moving, where is the friction, what is unused,
  does the brief still match reality? At a phase end it also checks the brief's "Stop if" list,
  and the go/no-go decision is put to you. The driver handles the fixes it suggests; it should
  not grade its own process.
- **Any time:** you type `/workflow` ("check the workflow" in other tools), or say something is
  annoying (logged as a signal).

### 7.4 Fix sizes and how freely the workflow fixes itself

- **Small** (easy to undo): add a rule that constrains only the agents; tweak a checklist or
  template; turn a repeated instruction into a command; split a recurring task; pause an unused
  rule; switch off an add-on the AI may switch off (experiment plans).
- **Big:** switch an add-on on; add or remove a file, folder, command or agent; change step size,
  the progress review interval or the health thresholds; delete anything.
- **Yours** (always you): the goal, finish line and success criteria (anything in BRIEF.md, so
  every re-interview); external spending or your hours beyond limits; go/no-go decisions;
  deleting work or data, or anything irreversible; anything outward (push, publish, contacting
  people); rules that constrain you; switching off the budget or the second opinion, and the
  second opinion's independence; how freely the workflow fixes itself; new paid tools or
  accounts.

How freely it fixes itself (STATE.json "fix_level"). The default is 2; the brief shows it for
confirmation, and it can be changed any time:
1. **Propose:** every fix waits for your approval.
2. **Small fixes by itself (default):** small fixes are made and reported with an undo; big ones
   are proposed; yours are asked.
3. **Small and big fixes by itself,** within your limits; yours are asked.

Script guards: `wf.py fix add` refuses a fix by the AI that the level does not allow, and
`wf.py check` flags such entries written by hand. `wf.py addon off budget|second-opinion` and
`wf.py spend` over the "ask first" amount need your answer logged in the step; `wf.py spend`
never goes over the cap. `wf.py begin` notes a fingerprint of BRIEF.md, DECISIONS.md, the fix
level and the limits; `wf.py check` flags any change to them in a step where no answer from you
is logged.

### 7.5 Testing a fix: re-check, keep or undo

Every fix gets an entry in WORKFLOW-FIXES.md (written by `wf.py fix add`): id (F-<n>), evidence
(log lines), change, size, made by (the AI or you), expected effect, measure, its value before
(rate over the last 10 steps), re-check step (after K steps, default 5), and undo: the exact
steps to reverse it (no copies of files are kept; your decision of 2026-11-07). At the re-check
the script compares the measure before and since the fix. If there is nothing to compare (zero
before and since, or a warning that is not a per-step rate: unused add-on, budget, silent rule,
quiet second opinion), the fix is kept and the next progress review looks at it again. If there
is no improvement the fix is undone: by the AI if the AI made it, otherwise as a proposal. With
few steps this comparison is noisy: it is a sanity check, reviewed again at the progress review,
not proof.

### 7.6 Re-interview

When the goal or a key fact changes, or a just-in-time topic becomes relevant (e.g. the first GPU
rental), only the affected questions are asked (`/workflow`, see `tools/fixes.md`). BRIEF.md gets
a new version with a "Changes" section, and the structure is re-checked against it.

### 7.7 Guards against bloat

Starting caps: RULES.md at most 12 rules in use (merge or pause one to add another); AGENTS.md
and each adapter at most 80 lines. Every add-on must justify itself: unused add-ons are switched
off, and the progress review looks for unused rules, files and parts. Rationale: AI-generated
multi-agent designs tend to bloat (arXiv 2606.13003, "The Illusion of Multi-Agent Advantage").

### 7.8 Learning across projects (later)

Changes that worked can be offered, with your approval, to the skill's lesson library, so that new
projects start with them.

## 8. Skill package layout

In this repo the package lives in `skill/`; the repo root keeps DESIGN.md, CLAUDE.md and test
material. The package uses the open Agent Skills format (a folder with `SKILL.md`), so tools other
than Claude Code can load it. For use, `skill/` is linked or copied to the tool's skills folder
(Claude Code: `~/.claude/skills/workflow-architect/`; link or copy decided when v0.1 is first
tried).

```
skill/
├── SKILL.md                phases and rules (entry point)
├── interview/
│   ├── planner.md          how the next questions are chosen
│   ├── coverage-map.md     topics: why, relevant when, design decisions fed, when needed
│   └── brief-template.md
├── templates/              files written into projects: core files; tools/step.md,
│                           tools/fixes.md (fix sizes, levels, undo, re-interview),
│                           tools/progress-review.md, tools/addons.md (the add-on catalogue);
│                           tool adapters (/step, /workflow)
├── scripts/
│   ├── probe.py            machine check (read-only)
│   └── wf.py               copied into projects; tags, metrics and thresholds live here
└── evals/                  tests for the skill
```

## 9. Testing

- **Each version:** a hands-on run on a toy project before the next version starts.
- **Simulated users:** an agent plays a user with hidden facts (e.g. "needs GPUs", "2 hours a
  week", "a co-author must approve"). Pass only if the interviewer found them by asking and the
  structure reflects them; any silent assumption fails. Different seed answers must produce
  different question paths.
- **Mechanical checks:** valid files, exactly one action in NEXT.md, the practice round passes,
  the file count fits the user's needs.
- **Evolution tests:** a log with the same correction twice → a rule appears (fix level 2) or
  is proposed (level 1), never a change that is yours; an unused add-on → switched off or asked
  about; a fix that does not help → undone; add-ons: the first paid call waits for a cap; an
  experiment plan is locked before any result.
- **Comparison:** the same simulated users with plain Claude Code asked to "set up a workflow for
  this project", using skill-creator's with/without comparison.
- **Real use:** 2–3 small real projects for about two weeks: time to first real progress, how much
  structure is still in use, changes kept and rolled back.

## 10. Build order

1. **v0.1:** machine check, adaptive interview (seeds, coverage map, planner), brief, proposal,
   minimal core, `/step` with full event tags (so evolution has data from day one), practice round.
2. **v0.2:** evolution engine: `wf.py health`, warnings, `/evolve`, change levels, trial and
   rollback, look-back, re-interview. Built and tested 2026-11-07 to 2026-11-10 (renamed
   2026-11-10: progress review, workflow fixes, `/workflow`).
3. **v0.3:** the three add-ons (section 5) and the two core lines; the plainer words of
   2026-11-10. Domain packs and the other modules are set aside or discarded (section 12).
4. **v0.4:** full tests (section 9), lesson import, learning across projects, docs.

## 11. Not in scope for now

Hands-on tests in tools other than Claude Code (after v0.1); scheduling between sessions; parallel tracks (agent teams); public release.

## 12. Decisions so far

- 2026-11-06: name `workflow-architect` (for now); folder
  `C:\Users\Smile\OneDrive\Desktop\New folder\workflow-architect`; Claude Code only for now.
- 2026-11-06, your comments: the interview is adaptive, not a fixed list (a few universal seed
  questions; the rest follow from the goal and earlier answers); the workflow must check itself
  mid-project and evolve by itself; the agent's own usage cost is not asked (you monitor it);
  money questions only for external spending (GPUs, compute, LLM APIs and the like).
- 2026-11-06: the evolution levels and the protected list are fine for now; level 2 is the
  default. Python, and whatever other tools are relevant, may be used.
- 2026-11-07: the skill is harness-agnostic, not Claude Code only (replaces "Claude Code only for
  now"). v0.1: tool-neutral design (open Agent Skills format; project rules in AGENTS.md; small
  adapters only for the tools used), hand-tested in Claude Code only.
- 2026-11-07: if Python is missing, the skill explains the impact at a high level and you decide:
  install Python and continue, or skip it.
- 2026-11-07: git: the agent commits this repo at sensible points and pushes to
  `https://github.com/Kishore-Kmr/workflow-architect.git` (replaces "ask before the first commit"
  and "never push").
- 2026-11-07: v0.1 projects get an empty EVOLUTION.md but no `/evolve`; `/evolve` comes in v0.2.
- 2026-11-07: when an interview finds a need v0.1 cannot meet (a module from v0.3), the proposal
  says so, RULES.md gets a temporary rule and QUESTIONS.md a just-in-time question.
- 2026-11-07: for use, `~/.claude/skills/workflow-architect` is a junction (link) to `skill/`, so
  changes in the repo take effect immediately.
- 2026-11-07, your comments after your hands-on test: (1) the first question is always about the
  goal and objective; other questions (e.g. tools) only after. (2) No "which AI tools" question
  with a restrictive recommendation: more tools do no harm, so adapters are made without asking.
  (3) Questions that matter only at a later stage (e.g. paid APIs for experiments) are not asked
  until that stage. (4) Not many specific questions one by one (deadline, closest work...): one
  single place where you type any other specifics or assumptions.
- 2026-11-07, builder's change following comment (3), approved by you the same day: the same applies to
  temporary rules. A rule for a missing module is added at setup only if it applies to the
  first phase; a later-stage need gets only its just-in-time question. No rule may repeat the
  core rules, the protected list or a setting. (Retest: 11 rules were proposed before this.)
- 2026-11-07, v0.2 plan approved by you, with two changes: (1) no saved copies of files before
  a workflow change (too much overhead); each change records in EVOLUTION.md exactly how to undo
  it, and git history helps where git is used. (2) No upgrade path for projects set up with
  v0.1; they are set up fresh. Your v0.2 hands-on test uses a toy project with a prepared
  history, so the self-checks can be seen without 15-20 real steps.
- 2026-11-10, your v0.2 hands-on test: it worked; your comment: words like "look-back" and
  "self-change" don't say what they are about. Approved new words: progress review (was
  look-back); workflow fix, Fix 1 (was workflow change, E-1); re-check and testing (was
  check-back and trial); how freely it fixes itself (was evolution level); yours to decide (was
  protected); `/workflow` (was `/evolve`); files WORKFLOW-FIXES.md, tools/fixes.md,
  tools/progress-review.md.
- 2026-11-10: domain packs set aside, in your words: "I think the AI already knows what should
  be needed for each type of project." v0.3 builds only the add-ons (modules).
- 2026-11-10: v0.3 shrunk, approved by you ("go with the shrinked version. Discard the rest"):
  three add-ons (budget, second opinion, experiment plans); go/no-go points and your hours
  become two core lines (check the brief's "Stop if" list at each phase end and ask you; a time
  estimate on every task for you). Discarded: workers/helpers, two strikes and time limits,
  checks and hooks as an add-on (a workflow fix can add a check), "worth it?" check.
- 2026-11-10: v0.3 closed without your hands-on test, in your words: "Your tests alone are
  sufficient for this."

## 13. Open questions

1. Later: which 2–3 real projects to test on; whether to offer your research RULES.md lessons
   as an import.
2. Domain packs (extra topics and end-product skeletons per kind of project): only if the
   real-project tests show the interview missing important topics.
3. The progress rate counts steps tagged progress, not how much moved (a v0.3 run: tightening
   one-sentence sections counted as progress while the draft stayed at 258 words). The progress
   review is meant to catch this; a size-aware measure only if real use shows the need.
