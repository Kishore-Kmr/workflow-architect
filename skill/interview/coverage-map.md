# Coverage map

What a design must eventually know. These are topics, not questions: most are answered by the
seed questions (especially the user's notes in seed 3), by a default in the brief, or by a
question saved for the stage where it matters. For each topic: when it is relevant, what to
find out, what it feeds (which file or setting changes), and **when** to ask:

- *seed*: covered by the seed questions;
- *setup*: ask after the seeds, only if the notes don't answer it and the setup can't be built
  without it;
- *brief*: don't ask; propose a default in the brief, marked **OK?**;
- *later*: don't ask at setup; save a just-in-time question with the trigger given.

Never ask about the cost of running the agent itself; the user monitors it. Never ask which AI
tools the user will use. Money questions are only about external spending, and only at their
stage.

## end-product: End product and success
- Relevant: always.
- Find out: what the finished thing is; what "done" looks like; who judges it.
- Feeds: the end-product parts, the finish line in BRIEF.md, "Done when" lines.
- When: seed. A vague goal gets one follow-up at setup.

## size-timeline: Size, timeline, deadline
- Relevant: always.
- Find out: rough size; deadline or none.
- Feeds: phases, step size, the deadline in BRIEF.md limits.
- When: brief (from the notes if given; otherwise "no deadline" **OK?**).

## existing-material: Existing material
- Relevant: the folder is not empty, or the user mentions prior work.
- Find out: what to keep and build on, what is reference only, what must not be touched.
- Feeds: parts that point to existing paths; "do not touch" rules; nothing is moved.
- When: setup, if the folder has files (the structure depends on it).

## people: People and roles
- Relevant: others are involved (co-authors, clients, annotators, a supervisor).
- Find out: who; their role; what they must approve or provide. The agent never contacts
  anyone itself; contact is a YOU action.
- Feeds: YOU actions for handoffs; approvals as decision points; rules.
- When: from the notes if mentioned; otherwise later: "the first time someone else's input or
  approval is needed".

## decisions-involvement: Your decisions and involvement
- Relevant: always.
- Find out: which decisions the user keeps; autonomy (stop after each step, or keep going
  until something needs them); how strict "ask first" is.
- Feeds: STATE.json "autonomy"; the strictness line in AGENTS.md; decision points.
- When: brief ("stop after each step; ask when unsure" **OK?**).

## human-effort: Human effort
- Relevant: the goal needs hands-on human work: expert judgement, labelling, user tests,
  interviews, writing.
- Find out: what kind; hours per week available; the most one task may take.
- Feeds: STATE.json "limits"; YOU actions; a warning before big manual tasks.
- When: later: "the first task that needs more than a quick answer from you" (e.g. the first
  labelling task).

## external-resources: External resources and spending
- Relevant: GPUs, cloud compute, paid APIs or LLM calls, bought data, paid annotators,
  services, hosting.
- Find out: which; a spending cap; whether each spend needs approval.
- Feeds: STATE.json "limits"; the budget module (v0.3; until then a temporary rule).
- When: later: "when the first task that would spend money is planned" (e.g. the first
  experiment). Until then the protected list already requires asking before any spend.

## data-legal-ethics: Data, access, legal, ethics
- Relevant: datasets, people as subjects, licences, private or personal data.
- Find out: sources and licences; consent or ethics approval; what must stay private.
- Feeds: feasibility checks; approvals as YOU decision points; `.gitignore` and privacy rules.
- When: setup only if private data is already in the folder (it shapes `.gitignore` and
  rules); otherwise later: "before the data is first used, or before collecting anything from
  people".

## quality: Quality and verification
- Relevant: always; the form varies (tests, validation, editing, a reader, a demo).
- Find out: how we will check the work is right; which errors would be costly or hard to see.
- Feeds: "Done when" lines; checkable rules; the reviewer module (v0.3; until then a
  temporary rule).
- When: brief (propose how the first phase is checked, **OK?**); later for each new phase.

## value-novelty: Value and novelty
- Relevant: success depends on being new or valuable (research, a product for others).
- Find out: the closest existing work; who would care; is it worth doing.
- Feeds: the first action (look at the closest work yourself), stop criteria.
- When: don't ask the user to list work; it goes in the notes if they know some. Make the
  check itself an early action, in the brief.

## risks: Risks and unknowns
- Relevant: always.
- Find out: what could make this fail or not worth doing; the smallest test that would tell
  early; when to stop.
- Feeds: the first action (the smallest decisive test); stop criteria in BRIEF.md.
- When: brief (propose the first action and stop criteria, **OK?**).

## working-preferences: Working preferences
- Relevant: always.
- Find out: report style; git (commit each step, the user commits, or no git; create a repo
  if there is none?); evolution level.
- Feeds: the report format, the git line in tools/step.md, STATE.json "git" and
  "evolution_level".
- When: brief: short reports; git as fits the folder; level 2 (small reversible workflow
  changes apply by themselves with an undo; bigger ones are proposed), each **OK?**.

## tools: Tools available
- Relevant: always; answered by the machine check.
- Feeds: adapters (made for the current tool and any installed tool that needs one), STATE.json
  "tools" and "python".
- When: never asked, except Python missing (setup: install or skip).

Domain packs (later versions) add topics, e.g. research: target venue, how labels are
validated, test-split hygiene; each with its stage trigger.
