# Question planner

There is no fixed questionnaire, and the interview is short: the seed questions, then at most a
short batch of what the setup needs now. Everything else is either a default in the brief
(marked **OK?**) or a question saved for the stage where it matters. Topics are in
`coverage-map.md`.

## What you keep (saved in `.workflow-architect/interview.json`)

- **Facts**, each labelled: *you said*, *checked* (by the machine check or by looking), or
  *inferred* (must be confirmed: in the next batch or in the brief, never silently used).
- **Topics**, each marked *relevant*, *not relevant* (with the reason) or *unknown yet*.
- **Unknowns**: what you still need to know, with what the answer would change, and *when* it
  is needed (now, for the setup; or at a later stage).
- **Saved for later**: just-in-time questions, each with a stage trigger.

## Seed questions (always the first questions, in one batch)

Nothing comes before them: no questions about tools, files or the machine.

1. What are you making?
2. What is the goal: what does success look like, and who judges it?
3. **Anything else the workflow should know?** This is the single place for specifics and
   assumptions. Show examples as one line of hints, not as separate questions: deadline, work
   you already know of, data, people involved, paid services, constraints, worries. Say: "Write
   as much or as little as you like. Whatever you leave out, I'll ask when it becomes relevant.
   You can add to this later too." The answer is kept word for word in BRIEF.md "Your notes".

All three are open text. If the user's opening message already answers one, read it back as a
fact to confirm instead of asking it again.

## After every batch of answers

1. **Update the model.** Read back, in a few short lines, what you took from free text
   ("From your notes I took: a co-author must approve before submission. Right?").
2. **Mark topics** relevant, not relevant (with reason) or unknown yet.
3. **Ask now only what the setup needs now**: an answer without which you cannot write the
   brief, the structure or the first phase's work, *and* for which no sensible default exists.
   Typical cases: an unclear goal; existing files (what to keep); Python missing.
   - An unknown tied to a later stage (experiments, spending, data collection, labelling,
     other people's input, submission, release) is **not asked now**: save it for later, with
     that stage as the trigger ("when the first experiment is planned").
   - Safety does not need early questions: the protected list already makes every spend,
     outward action and irreversible step wait for the user.
   - If a sensible default exists, put it in the brief marked **OK?** instead of asking.
4. **Rank** what is left by impact and by dependency (prerequisites first).
5. **Ask at most four, in one batch.** Multiple choice with "Other" when answers are
   predictable; open text when not. Each question has one line saying why it is asked and
   what it changes. Recommend an option only when it is clearly better for this user.
6. **Stop** when nothing the setup needs now is unknown. Usually that is after the seed batch
   and at most one more. Then write the brief.

## Rules

- Don't walk through topics one by one (deadline, closest work, budget, hours...). The third
  seed question is the place for them; what the user doesn't mention is saved for later or
  becomes a default marked **OK?**.
- A vague answer to the goal gets one follow-up ("good quality" -> "how would we check it?").
  Then accept it.
- "Decide later" is always allowed: save the question with a trigger.
- Show progress at the start of each batch after the first: "about N open points left".
- Save interview.json after each batch, so the interview can resume in a fresh session.
- Don't ask what the machine check already answered, or which AI tools the user will use.
  Don't ask about the cost of running the agent.
- Inferences are confirmed, not assumed: in the next batch or in the brief.

## Example: same seeds, different paths

| Seed answers | Asked at setup (only if not in the notes) | Saved for later, with trigger |
|---|---|---|
| A study of whether AI graders favour long answers; is it publishable? | nothing more, usually: the first phase is a "worth it?" check | paid APIs and a cap (first experiment); human labels and hours (first labelling task); venue (once the topic is judged worth it) |
| A budgeting app for myself; I'll use it monthly | existing code: build on it? | hosting (if it ever leaves the laptop) |
| Fine-tune a small model; must beat baseline Y | none, if the data is already here | GPU provider and budget (first training run); data licence (before first use) |

## interview.json format

```json
{
  "skill_version": "0.1",
  "stage": "machine-check | interview | brief | proposal | generate | practice | done",
  "updated": "YYYY-MM-DD HH:MM",
  "machine": {"summary": "the probe's lines", "python": "python or null",
              "tools": ["claude-code"]},
  "notes": "the user's answer to seed question 3, word for word",
  "facts": [{"id": "F-1", "topic": "end-product", "fact": "...",
             "source": "you said | checked | inferred", "confirmed": true}],
  "topics": {"end-product": {"status": "relevant | not-relevant | unknown", "reason": "..."}},
  "unknowns": [{"id": "U-1", "topic": "...", "question": "...",
                "changes": "what the answer would change", "when": "now | <stage>"}],
  "batches": [{"n": 1, "asked": ["..."], "answers": ["the user's words, verbatim"],
               "took": ["F-3", "F-4"]}],
  "later": [{"question": "...", "trigger": "...", "why": "..."}],
  "approvals": [{"what": "brief v1", "date": "YYYY-MM-DD", "words": "the user's words"}]
}
```
