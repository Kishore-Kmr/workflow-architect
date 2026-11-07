# Question planner

There is no fixed questionnaire. You keep a project model and a list of open unknowns, and after
every batch of answers you choose the next few questions. Topics are in `coverage-map.md`.

## What you keep (saved in `.workflow-architect/interview.json`)

- **Facts**, each labelled: *you said*, *checked* (by the machine check or by looking), or
  *inferred* (must be confirmed: in the next batch or in the brief, never silently used).
- **Topics**, each marked *relevant*, *not relevant* (with the reason) or *unknown yet*.
- **Unknowns**: what you still need to know, with what the answer would change.
- **Saved for later**: just-in-time questions, each with a trigger.

## Seed questions (always asked, first batch)

1. What are you making?
2. What is the goal: what does success look like, and who judges it?
3. Optional, open: "Anything else you already know: constraints, ideas, worries?"

All three are open text. If the user's opening message already answers one, read it back as a
fact to confirm instead of asking it again.

## After every batch of answers

1. **Update the model.** Read back, in a few short lines, what you took from free text
   ("From your answer I took: no deadline; a co-author must approve the final draft. Right?").
2. **Mark topics** relevant, not relevant (with reason) or unknown yet.
3. **List the unknowns whose answer would change the initial structure**: which files or parts
   exist, which rules or limits are set, what the first action is, which settings are chosen.
   If no possible answer would change the structure, it is not asked.
4. **Rank** by impact (how different the structure would be across the likely answers) and by
   dependency (prerequisites first: ask what kind of project before asking its details).
5. **Ask at most four, in one batch.** Multiple choice with "Other" when answers are
   predictable; open text when not. Each question has one line saying why it is asked and what
   it changes, and a recommended option where there is one. See "How to ask" in SKILL.md.
6. **Stop** when no setup-relevant unknown remains. Everything else goes to "saved for later"
   with a trigger (e.g. "the first time a task would spend money"); these become QUESTIONS.md
   "Just in time".

## Rules

- A vague answer gets one follow-up ("good quality" -> "how would we check it?"). Then accept it.
- "Decide later" is always allowed: save the question with a trigger, and use a safe default
  meanwhile only if you name it in the brief as "OK?".
- Show progress at the start of each batch: "about N open points left".
- Save interview.json after each batch, so the interview can resume in a fresh session.
- Don't ask what the machine check already answered. Don't ask about topics marked not
  relevant. Don't ask about the cost of running the agent.
- Inferences are confirmed, not assumed.
- Usually 2 to 4 batches are enough. If you reach a fifth, check that each question still
  changes the structure.

## Example: same seeds, different paths

| Seed answers | Likely next questions | Skipped |
|---|---|---|
| A paper on whether AI graders favour long answers; aim: Findings of ACL | closest work you know? data? will experiments call paid LLM APIs? human labels, and your hours? | deployment, users |
| A budgeting app for myself; I'll use it monthly | platform? existing code? how will we check it works? | venue, labels, spending (unless hosting) |
| Fine-tune a small model; must beat baseline Y | GPU provider and budget? data licence? evaluation set? limit per training run? | venue (unless a paper is planned) |

## interview.json format

```json
{
  "skill_version": "0.1",
  "stage": "machine-check | interview | brief | proposal | generate | practice | done",
  "updated": "YYYY-MM-DD HH:MM",
  "machine": {"summary": "the probe's lines", "python": "python or null",
              "tools": ["claude-code"]},
  "facts": [{"id": "F-1", "topic": "end-product", "fact": "...",
             "source": "you said | checked | inferred", "confirmed": true}],
  "topics": {"end-product": {"status": "relevant | not-relevant | unknown", "reason": "..."}},
  "unknowns": [{"id": "U-1", "topic": "...", "question": "...",
                "changes": "what the answer would change", "needs": ["U-0"]}],
  "batches": [{"n": 1, "asked": ["..."], "answers": ["the user's words, verbatim"],
               "took": ["F-3", "F-4"]}],
  "later": [{"question": "...", "trigger": "...", "why": "..."}],
  "approvals": [{"what": "brief v1", "date": "YYYY-MM-DD", "words": "the user's words"}]
}
```
