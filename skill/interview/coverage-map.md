# Coverage map

What a design must eventually know. These are topics, not questions: word each question from
the conversation so far. For each topic: when it is relevant, what to find out, what it feeds
(which file or setting changes), and the trigger to use if the user says "decide later".

Never ask about the cost of running the agent itself; the user monitors it. Money questions are
only about external spending.

## end-product: End product and success
- Relevant: always (seed questions 1 and 2).
- Find out: what the finished thing is; what "done" looks like; who judges it; what a good
  result looks like next to a poor one.
- Feeds: the end-product parts (skeleton), the finish line in BRIEF.md, "Done when" lines.
- Later: not allowed; the setup needs it.

## size-timeline: Size, timeline, deadline
- Relevant: always; often inferable (then confirm, don't ask).
- Find out: rough size; deadline or none; how often the user works on it.
- Feeds: phases, how big one step is, the deadline in BRIEF.md limits.
- Later trigger: "when the first phase ends".

## existing-material: Existing material
- Relevant: the folder is not empty, or the user mentions prior work.
- Find out: what to keep and build on, what is reference only, what must not be touched.
- Feeds: parts that point to existing paths; "do not touch" rules; nothing is moved.
- Later: not allowed when the folder has files; the structure depends on it.

## people: People and roles
- Relevant: others are involved (co-authors, clients, annotators, a supervisor).
- Find out: who; their role; what they must approve or provide. The agent never contacts
  anyone itself; contact is a YOU action.
- Feeds: YOU actions for handoffs; approvals as decision points; rules.
- Later trigger: "the first time someone else's input or approval is needed".

## decisions-involvement: Your decisions and involvement
- Relevant: always (light; usually one question).
- Find out: which decisions the user keeps; autonomy (stop after each step, or keep going
  until something needs them); how strict "ask first" is.
- Feeds: STATE.json "autonomy"; the strictness line in AGENTS.md; decision points.
- Default to offer: stop after each step; ask when unsure.

## human-effort: Human effort
- Relevant: the goal needs the user's (or others') hands-on work: expert judgement,
  labelling, user tests, interviews, writing.
- Find out: what kind; hours per week available; the most one task may take.
- Feeds: STATE.json "limits"; YOU actions; a warning before big manual tasks. (Hours module:
  later version, so in v0.1 a temporary rule.)
- Later trigger: "the first task that needs more than a quick answer from you".

## external-resources: External resources and spending
- Relevant: GPUs, cloud compute, paid APIs or LLM calls, bought data, paid annotators,
  services, hosting.
- Find out: which; a spending cap; whether each spend needs approval.
- Feeds: STATE.json "limits"; budget module (later version, so in v0.1 a temporary rule "ask
  before any spending" and a just-in-time question).
- Later trigger: "the first time a task would spend money".

## data-legal-ethics: Data, access, legal, ethics
- Relevant: datasets, people as subjects, licences, private or personal data.
- Find out: sources and licences; consent or ethics approval; what must stay private (and out
  of git).
- Feeds: feasibility checks as early actions; approvals as YOU decision points; `.gitignore`
  and privacy rules.
- Later trigger: "before the data is first used, or before collecting anything from people".

## quality: Quality and verification
- Relevant: always; the form varies (tests, validation, editing, a reader, a demo).
- Find out: how we will check the work is right; which errors would be costly or hard to see.
  A vague answer ("good quality") gets one follow-up: "how would we check it?"
- Feeds: "Done when" lines; checkable rules; reviewer module (later version, so in v0.1 a
  temporary rule, e.g. "you review X before it counts as done").

## value-novelty: Value and novelty
- Relevant: success depends on being new or valuable (research, a product for others).
- Find out: the closest existing work the user knows; who would care; whether to check "is it
  worth it?" before deep work.
- Feeds: an early action (look at the closest work), stop criteria.
- Later trigger: "before the first phase of deep work".

## risks: Risks and unknowns
- Relevant: always.
- Find out: what could make this fail or not worth doing; the smallest test that would tell
  early; when to stop.
- Feeds: the first action (the smallest decisive test); stop criteria in BRIEF.md.

## working-preferences: Working preferences
- Relevant: always (light).
- Find out: report style (short or detailed); git (commit each step, the user commits, or no
  git; create a repo if there is none?); evolution level.
- Feeds: the report format, the git line in tools/step.md, STATE.json "git" and
  "evolution_level".
- Defaults to offer: short reports; level 2 (small reversible workflow changes apply by
  themselves with an undo; bigger ones are proposed), shown in the brief as "OK?".

## tools: Tools available
- Relevant: always, but answered by the machine check; ask only if it is ambiguous.
- Find out: which AI tools the user will use in this folder; Python yes or no; other tools the
  work needs (a compiler, LaTeX, a database).
- Feeds: adapters (CLAUDE.md and `/step` for Claude Code), STATE.json "tools" and "python".

Domain packs (later versions) add topics, e.g. research: target venue, closest work, how labels
are validated, test-split hygiene.
