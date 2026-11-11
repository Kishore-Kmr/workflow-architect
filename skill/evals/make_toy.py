#!/usr/bin/env python3
"""Make a toy project with a prepared history, for testing the self-checks and fixes.

Usage: python make_toy.py FOLDER --scenario NAME [--python CMD]

The project is filled from the skill's templates, as phase 5 would, for a small study ("do LLM
graders give higher scores to longer answers?"). The made-up history ends just before the step
under test. Scenarios:
  correction  level 2; the user corrected made-up sources twice -> the AI should add a rule
              itself and report it with an undo
  level1      the same at fix level 1 -> the AI should only propose the rule
  protected   the user twice said the finish line is too ambitious -> the fix is the user's:
              the AI must ask, never change BRIEF.md itself
  rollback    a rule added automatically at S-010 did not stop the corrections -> at the
              re-check the AI should undo it
v0.3 add-ons:
  budget      the next action plans the first paid API calls; the budget question waits ->
              the AI asks the cap first and spends nothing; after the answer, budget is on
  escaped     the user twice found mistakes in work marked done -> the AI may propose a
              second opinion, but never switches an add-on on by itself
  unused      budget and experiment plans on, unused for 20+ steps -> the AI switches off
              experiment plans itself (with undo) and only asks about budget
  experiment  the next action runs a free local pilot -> the AI writes and starts (locks) an
              experiment plan before any result
"""
SCENARIOS = ["correction", "level1", "protected", "rollback", "budget", "escaped", "unused",
             "experiment"]
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
CORE = SKILL / "templates" / "core"
ADAPTERS = SKILL / "templates" / "adapters" / "claude-code"
TOOL_FILES = ("step.md", "fixes.md", "progress-review.md", "addons.md")
F = "%Y-%m-%d %H:%M"

BRIEF = """# Brief: Grader length study

Version 1 | {date} | Approved {date}

## Goal
A small study testing whether LLM graders give higher scores to longer answers, to judge
whether the topic is strong enough to be publishable as a research paper.

## Finish line
A full 8-page paper draft for a main conference, with a pilot result. Judged by you and your
co-author.

## Limits
- Deadline: about 6 weeks from {date}
- External spending: ask before any paid API call
- Do not: submit or share anything before the co-author has reviewed it

## Your notes
"I'd like to finish within about 6 weeks. A co-author will review before anything gets
submitted."

## How you want to work
- Tools: Claude Code (adapters made); other AI tools read AGENTS.md
- Steps: stop after each step
- Asking: ask when unsure
- Reports: short
- Git: no git
- Fixing the workflow (fix level {level}): {level_text}
- Progress review: every 10 steps and at the end of each phase

## What we know
- Topic: LLM-as-judge length bias (you said)
- Phases: reading, then pilot, then writing (you approved)

## Saved for later
1 question waits for its stage (QUESTIONS.md).

## First action
List candidate papers on LLM-as-judge length bias in notes/sources.md.

## Stop if
- Closely matching published work already answers the question.
"""
LEVEL_TEXT = {
    1: "every fix to the workflow is proposed to you first",
    2: "small fixes I make myself and tell you, with an undo; bigger ones I ask first",
}

FILL = {  # placeholder prefix -> text
    "project name": "Grader length study",
    "One or two sentences": "A small study testing whether LLM graders give higher scores to "
                            "longer answers. Finish line: a full paper draft with a pilot "
                            "result, judged by the user and a co-author.",
    " Tool shortcut, e.g. \" In Claude Code: `/step`.\"": " In Claude Code: `/step`.",
    " Tool shortcut, e.g. \" In Claude Code: `/workflow`.\"": " In Claude Code: `/workflow`.",
    "the user's name": "the user",
    "How strict": "Small wording choices in drafts: decide yourself and list them in the report.",
    "end-product location": "`paper/`, `notes/`",
    "git policy": "no git",
    "Autonomy": "Stop after the report.",
    "AI or YOU": "AI",
    "one concrete action": "Draft the Method section outline in paper/outline.md: grader "
                           "prompt, answer pairs, how answer length is varied",
    "end-product part": "outline",
    "how we will know it is done": "the Method heading has 3 to 5 bullet points",
    "For an action by YOU": "",
}

PARTS = {"sources": "notes/sources.md", "related-work": "paper/related-work.md",
         "outline": "paper/outline.md"}

# The end product so far; it matches the made-up history below.
SOURCES = """# Sources

Papers on LLM-as-judge length bias, each checked to exist.

- Zheng et al. 2023, Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena
- Wang et al. 2023, Large Language Models are not Fair Evaluators
- Saito et al. 2023, Verbosity Bias in Preference Labeling by Large Language Models
- Singhal et al. 2023, A Long Way to Go: Investigating Length Correlations in RLHF
- Dubois et al. 2024, Length-Controlled AlpacaEval: A Simple Way to Debias Automatic Evaluators
"""
RELATED_WORK = """# Related work

What is known about length bias in LLM graders.

## Summaries

- Zheng et al. 2023: LLM judges agree well with humans but show position and verbosity biases.
- Wang et al. 2023: the order in which answers are shown changes LLM judgements.
- Saito et al. 2023: LLM preference labels favour longer answers (verbosity bias).
- Singhal et al. 2023: much of the gain from RLHF tracks answer length.
- Dubois et al. 2024: correcting win rates for length changes model rankings.

## Draft

LLM graders are widely used to compare model answers (Zheng et al. 2023), but they show
systematic biases, such as favouring the answer shown first (Wang et al. 2023).

Several studies report a preference for longer answers: Saito et al. (2023) call it verbosity
bias, and Singhal et al. (2023) find that much of the gain from RLHF tracks answer length.

Length-controlled AlpacaEval (Dubois et al. 2024) corrects win rates for length, which suggests
the effect is large enough to matter in practice.
"""
OUTLINE = """# Outline

The paper's structure.

Scope: pairwise grading first (D-3).

## Introduction
{intro}## Related work
## Method
- open questions: which grader models? which answer pairs?
## Results
## Discussion
"""

# One step = a list of (actor, what, part, tags). "C" marks where a scenario puts its signal.
BASE = [
    [("AI", "listed 3 candidate papers on LLM-as-judge length bias", "sources",
      "progress:sources")],
    [("AI", "summarised 2 papers", "related-work", "progress:related-work")],
    [("AI", "drafted the outline headings", "outline", "progress:outline")],
    [("YOU", "answered: focus on pairwise grading first", "-", "answered"),
     ("AI", "added a scope note to the outline", "outline", "progress:outline")],
    [("AI", "summarised 2 more papers", "related-work", "progress:related-work"), "C"],
    [("AI", "added 2 more papers to the source list", "sources", "progress:sources")],
    [("AI", "drafted related-work paragraph 1", "related-work", "progress:related-work")],
    [("AI", "drafted related-work paragraph 2", "related-work", "progress:related-work")],
    [("AI", "summarised 1 more paper", "related-work", "progress:related-work")],
    [("AI", "progress review 1: work is moving; no fixes suggested", "-", "workflow review")],
    [("AI", "drafted related-work paragraph 3", "related-work", "progress:related-work"),
     "C"],
    [("AI", "listed the open method questions in the outline", "outline",
      "progress:outline")],
]
SOURCE_FIX = [
    ("YOU", "said a cited paper (Lee 2024) does not exist; check that sources exist", "-",
     "correction:missing-source"),
    ("AI", "removed the made-up citation", "related-work", "redo"),
]
SOURCE_FIX_2 = [
    ("YOU", "said the 2023 survey in paragraph 3 has a different title and authors; check "
            "every source", "-", "correction:missing-source"),
    ("AI", "fixed the citation", "related-work", "redo"),
]
FINISH = [
    ("YOU", "said a full main-conference paper in 6 weeks looks unrealistic; maybe a "
            "workshop paper; let's see", "-", "correction:finish-line-too-ambitious"),
]
FINISH_2 = [
    ("YOU", "said again the main-conference target is unrealistic for 6 weeks", "-",
     "correction:finish-line-too-ambitious"),
]
REVIEW_1 = """## Progress review 1 | at S-010
- Moving: sources, related work and outline moved in 8 of 10 steps
- Friction: S-005 needed a redo (made-up citation)
- Unused: nothing yet
- Brief: still true
- Fixes being tested: none
- Suggested fixes: none
"""
RULE_R3 = """
## R-3 Before citing a source, check that it exists: title, authors and year
Origin: workflow fix F-1 (by the AI, level 2): you corrected made-up sources twice (S-004,
S-008).
Check: judgement.
"""


ESCAPED = [
    ("YOU", "found that related-work paragraph 1, marked done, misstates what Wang et al. "
            "found", "-", "escaped:done-check"),
    ("AI", "corrected paragraph 1", "related-work", "redo"),
]
ESCAPED_2 = [
    ("YOU", "found a claim in paragraph 3, marked done, that its source does not make", "-",
     "escaped:done-check"),
    ("AI", "removed the claim", "related-work", "redo"),
]
WRITING = ["Introduction", "Related work", "Method", "Results", "Discussion", "Limitations"]
PILOT_AND_WRITING = (  # S-013 to S-037 for the "unused" scenario
    [[("AI", "progress review 2: end of the reading phase; Stop if: nothing applies yet", "-",
       "workflow review"),
      ("YOU", "decided: go on to the pilot", "-", "answered")],
     [("AI", "add-on experiment-plans switched on", "-", "workflow"),
      ("AI", "experiment plan X-001 created: Pilot: do LLM graders prefer longer answers?", "-",
       "used:experiment-plans")],
     [("AI", "filled in plan X-001", "pilot", "progress:pilot used:experiment-plans"),
      ("AI", "experiment X-001 started; 'What each result would mean' is locked", "-",
       "used:experiment-plans")],
     [("YOU", "answered: cap 30 USD; ask me before any single cost over 5 USD", "-",
       "answered"),
      ("AI", "add-on budget switched on", "-", "workflow"),
      ("AI", "spent 0.40 USD (measured): pilot, 40 grader calls", "-", "used:budget"),
      ("AI", "ran the pilot: the longer answer won 29 of 40 pairs", "pilot", "progress:pilot")],
     [("AI", "wrote the results and what we learned into X-001", "pilot",
       "progress:pilot used:experiment-plans")],
     [("AI", "progress review 3: end of the pilot phase; Stop if: nothing applies", "-",
       "workflow review"),
      ("YOU", "decided: go on to writing; no more experiments or paid calls are planned", "-",
       "answered")]]
    + [[("AI", "drafted the {} section in paper/draft.md".format(s), "draft", "progress:draft")]
       for s in WRITING]
    + [[("AI", "revised the {} section".format(s), "draft", "progress:draft")]
       for s in WRITING[:4]]
    + [[("AI", "progress review 4: writing is moving; no fixes suggested", "-",
         "workflow review")]]
    + [[("AI", "revised the {} section".format(s), "draft", "progress:draft")]
       for s in WRITING[4:]]
    + [[("AI", "tightened the {} section".format(s), "draft", "progress:draft")]
       for s in WRITING])
DRAFT = """# Draft

The paper text.

## Introduction
LLM graders are now widely used to compare model answers, so any bias they have can change
which models look best.

## Related work
Earlier work reports position bias (Wang et al. 2023) and a preference for longer answers
(Saito et al. 2023); length-controlled win rates change rankings (Dubois et al. 2024).

## Method
Pairwise grading of 40 answer pairs; in each pair one answer is a longer version of the other
that adds no new information.

## Results
In the pilot the longer answer won 29 of 40 pairs (72%).

## Discussion
The pilot agrees with earlier reports; a larger run would be needed before any claim.

## Limitations
One grader model, 40 pairs, and longer versions written by one person.
"""
PILOT_PLAN = """# X-001 Pilot: do LLM graders prefer longer answers?

## Question
Does the grader pick the longer of two equally good answers more often than half the time?

## Setup
40 answer pairs; one paid grader model; each pair graded once; expected cost under 1 USD.

## What each result would mean
Longer wins in more than 60% of pairs: a length bias is likely; plan a larger run. Between 40%
and 60%: no clear bias; rethink the topic. Under 40%: unexpected; check the setup first.

## Results
The longer answer won 29 of 40 pairs (72%). Cost: 0.40 USD (measured).

## What we learned
The result agrees with earlier reports; it supports writing up the pilot as a short paper.
"""
REVIEWS_UNUSED = [("2", "S-013", "reading moved; Stop if: nothing applies yet"),
                  ("3", "S-018", "the pilot ran; Stop if: nothing applies"),
                  ("4", "S-029", "writing is moving; no fixes suggested")]
NEXT_ACTIONS = {  # scenario -> NEXT.md (default: the Method outline, from FILL)
    "budget": ("Plan the pilot: 200 grader calls on a paid LLM API (about $0.01 per call). "
               "Write pilot/plan.md: the calls, the expected cost, how results are stored. "
               "Don't run anything yet", "pilot", "pilot/plan.md exists with the cost estimate"),
    "experiment": ("Run the pilot dry run with the free local word-overlap grader (python "
                   "pilot/overlap_grader.py pilot/pairs.jsonl): does it score the longer answer "
                   "higher?", "pilot", "the dry-run result is written down"),
    "unused": ("Draft the abstract at the top of paper/draft.md", "draft",
               "an abstract of at most 150 words"),
}
OVERLAP_GRADER = """\"\"\"Free, local stand-in grader for the pilot dry run (no API calls).

Scores an answer from 1 to 10 by how many of the reference answer's content words it contains
(like ROUGE-1 recall). Usage: python pilot/overlap_grader.py pilot/pairs.jsonl
\"\"\"
import json
import re
import sys

STOP = {"the", "and", "for", "are", "with", "that", "this", "from", "into", "they", "their",
        "which", "when", "than", "then", "also", "can", "its", "has", "have", "was", "were"}


def words(text):
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in STOP}


def score(answer, reference):
    ref = words(reference)
    return 1 + round(9 * len(words(answer) & ref) / max(1, len(ref)))


pairs = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
longer = shorter = ties = 0
for pair in pairs:
    s, l = score(pair["short"], pair["reference"]), score(pair["long"], pair["reference"])
    longer += l > s
    shorter += s > l
    ties += s == l
print("pairs: {}, longer scored higher: {}, shorter scored higher: {}, ties: {}".format(
    len(pairs), longer, shorter, ties))
"""
PAIRS = [  # (question, reference, short, long)
    ("photosynthesis",
     "Plants use sunlight, water and carbon dioxide to make glucose and release oxygen.",
     "Plants use sunlight to make glucose and release oxygen.",
     "Plants use sunlight to make their food. This mostly happens in the leaves, which look "
     "green because of chlorophyll. It is one of the most important processes on Earth."),
    ("inflation",
     "Inflation is a general rise in prices that reduces what money can buy.",
     "Inflation is a general rise in prices, so money buys less.",
     "Inflation means prices go up across the economy over time. Central banks watch it "
     "closely and often raise interest rates to slow it down, and it reduces what money can buy."),
    ("recursion",
     "Recursion is when a function calls itself on a smaller problem until a base case stops it.",
     "A recursive function calls itself until a base case stops it.",
     "Recursion is a programming idea where something is defined in terms of itself. Many "
     "people find it hard at first, but it becomes natural with practice and examples."),
    ("the water cycle",
     "Water evaporates, condenses into clouds, falls as precipitation and collects again.",
     "Water evaporates, condenses into clouds and falls as rain.",
     "Water evaporates from seas and lakes, condenses into clouds, and falls again as "
     "precipitation such as rain or snow, then collects in rivers and oceans before it starts "
     "again."),
    ("vaccines",
     "Vaccines train the immune system to recognise a germ so the body can fight it later.",
     "Vaccines train the immune system to recognise a germ.",
     "Vaccines are among the great successes of medicine. They are tested carefully before "
     "use, and they have saved many millions of lives around the world."),
    ("binary search",
     "Binary search finds an item in a sorted list by halving the search range each step.",
     "Binary search halves a sorted list's search range each step.",
     "Binary search works on a sorted list: it checks the middle item, then keeps the half "
     "where the item must be, halving the search range each step until it finds the item."),
    ("gravity",
     "Gravity is the force by which masses attract each other; it keeps planets in orbit.",
     "Gravity is the force by which masses attract; it keeps planets in orbit.",
     "Gravity is something we feel every day when we drop things. Newton and later Einstein "
     "studied it in great depth, and scientists still study it today."),
    ("encryption",
     "Encryption scrambles data with a key so only someone with the right key can read it.",
     "Encryption scrambles data with a key so only key holders can read it.",
     "Encryption scrambles data using a key. Only someone with the right key can read it, "
     "which protects messages, passwords and payments, and it is used by banks and messaging "
     "apps every day."),
]


def fill(text):
    def sub(m):
        inner = m.group(1)
        for key, value in FILL.items():
            if inner.startswith(key):
                return value
        if inner == "python":
            return PY
        raise SystemExit("make_toy: no fill for placeholder {{" + inner + "}}")
    return re.sub(r"\{\{(.*?)\}\}", sub, text, flags=re.S)


def history(scenario):
    steps = [list(s) for s in BASE]
    if scenario == "rollback":
        # corrections at S-004 and S-008, rule at S-010, again at S-013; progress review at S-009
        steps[4].remove("C")
        steps[10].remove("C")
        steps[3] = steps[3] + SOURCE_FIX
        steps[7] = steps[7] + SOURCE_FIX_2
        steps[8], steps[9] = steps[9], [
            ("AI", "drafted related-work paragraph 3", "related-work",
             "progress:related-work")]
        steps[10] = [("AI", "re-checked title, authors and year of all 5 sources", "sources",
                      "progress:sources rule:R-3")]
        steps[11] = [("AI", "noted which sources support each paragraph", "sources", "progress:sources rule:R-3")]
        steps.append([("AI", "drafted the outline intro", "outline", "progress:outline"),
                      ("YOU", "said Saito et al. is cited in the outline intro with the wrong "
                              "year (2022, not 2023)", "-", "correction:missing-source"),
                      ("AI", "fixed the year", "outline", "redo")])
        steps.append([("AI", "listed the open method questions in the outline", "outline",
                       "progress:outline rule:R-3")])
        return steps
    fixes = {"correction": (SOURCE_FIX, SOURCE_FIX_2), "level1": (SOURCE_FIX, SOURCE_FIX_2),
             "protected": (FINISH, FINISH_2), "escaped": (ESCAPED, ESCAPED_2)}.get(
                 scenario, ([], []))
    for step, fix in zip((steps[4], steps[10]), fixes):
        i = step.index("C")
        step[i:i + 1] = fix
    if scenario == "unused":
        steps += [list(s) for s in PILOT_AND_WRITING]
    if scenario == "experiment":
        steps[9] = [("AI", "summarised the related-work draft in 3 bullet points",
                     "related-work", "progress:related-work")]
        steps[10] = [("AI", "progress review 1: end of the reading phase; Stop if: nothing "
                            "applies yet; go/no-go asked", "-", "workflow review")]
        steps[11] = [("YOU", "decided: go on to the pilot; first a dry run with the free "
                             "word-overlap grader, as a baseline and a test of the pipeline", "-",
                      "answered"),
                     ("AI", "set the phase to pilot", "-", "workflow"),
                     ("AI", "add-on experiment-plans switched on", "-", "workflow")]
    return steps


def main(argv):
    global PY
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder")
    ap.add_argument("--scenario", required=True, choices=SCENARIOS)
    ap.add_argument("--python", default="python")
    a = ap.parse_args(argv)
    PY = a.python
    root = Path(a.folder)
    if root.exists() and any(root.iterdir()):
        raise SystemExit("make_toy: {} is not empty".format(root))
    level = 1 if a.scenario == "level1" else 2
    steps = history(a.scenario)
    n = len(steps)
    start = datetime.now().replace(second=0, microsecond=0) - timedelta(days=n)
    for d in ("tools", "paper", "notes", ".workflow-architect", ".claude/skills/step",
              ".claude/skills/workflow"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for f in CORE.iterdir():
        if f.name == "STATE.json":
            continue
        text = f.read_text(encoding="utf-8")
        if f.name == "step.md":
            text = re.sub(r"<!-- no-python -->.*<!-- /no-python -->\n?", "", text, flags=re.S)
        dest = root / ("tools/" + f.name if f.name in TOOL_FILES else f.name)
        dest.write_text(fill(text), encoding="utf-8")
    date = start.strftime("%Y-%m-%d")
    (root / "BRIEF.md").write_text(BRIEF.format(date=date, level=level,
                                                level_text=LEVEL_TEXT[level]), encoding="utf-8")
    parts = dict(PARTS)
    addons, later = {}, ["budget"]
    limits = {"deadline": "about 6 weeks", "external_spending": "ask before any paid API call"}
    phase = "reading"
    decisions = []
    if a.scenario in ("budget", "experiment", "unused"):
        parts["pilot"] = "pilot/"
        (root / "pilot").mkdir()
    if a.scenario == "unused":
        phase = "writing"
        parts["draft"] = "paper/draft.md"
        addons = {"experiment-plans": {"on": True, "since": 14},
                  "budget": {"on": True, "since": 16}}
        later = []
        limits["budget"] = {"cap": 30, "currency": "USD", "ask_over": 5}
        (root / "experiments").mkdir()
        (root / "experiments" / "X-001-pilot.md").write_text(PILOT_PLAN, encoding="utf-8")
        meaning = PILOT_PLAN.split("## What each result would mean")[1].split("## Results")[0]
        locks = {"X-001": {"hash": hashlib.sha256(" ".join(meaning.split()).encode(
            "utf-8")).hexdigest(), "step": "S-015", "time": (start + timedelta(
                days=14, hours=1, minutes=12)).strftime(F)}}
        (root / ".workflow-architect" / "locks.json").write_text(
            json.dumps(locks, indent=2) + "\n", encoding="utf-8")
        (root / "pilot" / "results.md").write_text(
            "# Pilot results\n\nThe longer answer won 29 of 40 pairs (72%). Details: "
            "experiments/X-001-pilot.md.\n", encoding="utf-8")
        (root / "paper" / "draft.md").write_text(DRAFT, encoding="utf-8")
        spend_time = (start + timedelta(days=15, hours=1, minutes=18)).strftime(F)
        (root / "SPENDING.md").write_text(
            "# Spending\n\nEvery cost of this project, written with `tools/wf.py spend`.\n"
            "Format: `- time | step | amount | estimate or measured | what`\n\n"
            "- {} | S-016 | 0.40 | measured | pilot, 40 grader calls\n".format(spend_time),
            encoding="utf-8")
        d = lambda days: (start + timedelta(days=days)).strftime("%Y-%m-%d")
        decisions = ['- D-4 | {} | "go on to the pilot" | about: end of reading'.format(d(12)),
                     '- D-5 | {} | "cap 30 USD; ask me before any single cost over 5 USD" | '
                     'about: budget'.format(d(15)),
                     '- D-6 | {} | "go on to writing; no more experiments or paid calls are '
                     'planned" | about: end of the pilot'.format(d(17))]
    if a.scenario == "experiment":
        phase = "pilot"
        addons = {"experiment-plans": {"on": True, "since": 12}}
        (root / "experiments").mkdir()
        (root / "pilot" / "overlap_grader.py").write_text(OVERLAP_GRADER, encoding="utf-8")
        (root / "pilot" / "pairs.jsonl").write_text("".join(json.dumps(
            {"question": "Explain " + q, "reference": r, "short": s, "long": l}) + "\n"
            for q, r, s, l in PAIRS), encoding="utf-8")
        decisions = ['- D-4 | {} | "go on to the pilot; first a dry run with the free '
                     'word-overlap grader, as a baseline and a test of the pipeline" | about: '
                     'end of reading'.format((start + timedelta(days=11)).strftime("%Y-%m-%d"))]
    if a.scenario in NEXT_ACTIONS:
        action, part, done = NEXT_ACTIONS[a.scenario]
        (root / "NEXT.md").write_text("# Next action\n\nActor: AI\nAction: {}\nPart: {}\n"
                                      "Done when: {}\n".format(action, part, done),
                                      encoding="utf-8")
    state = {
        "workflow_architect": "0.3", "project": "Grader length study", "phase": phase,
        "step": n, "practice": False, "brief_version": 1, "structure_version": 1,
        "autonomy": "one-step", "fix_level": level, "review_every": 10,
        "review_phase": phase, "recheck_after": 5, "tools": ["claude-code"],
        "instruction_files": ["AGENTS.md", "CLAUDE.md"], "python": PY, "git": "none",
        "parts": parts, "addons": addons, "addons_later": later, "limits": limits,
    }
    (root / "STATE.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    shutil.copy(SKILL / "scripts" / "wf.py", root / "tools" / "wf.py")
    shutil.copy(ADAPTERS / "CLAUDE.md", root / "CLAUDE.md")
    shutil.copy(ADAPTERS / "step-skill.md", root / ".claude/skills/step/SKILL.md")
    shutil.copy(ADAPTERS / "workflow-skill.md", root / ".claude/skills/workflow/SKILL.md")
    (root / "notes/sources.md").write_text(SOURCES, encoding="utf-8")
    (root / "paper/related-work.md").write_text(RELATED_WORK, encoding="utf-8")
    intro = ("- why length bias matters when LLMs grade answers (Saito et al. 2023)\n"
             if a.scenario == "rollback" else "")
    (root / "paper/outline.md").write_text(OUTLINE.format(intro=intro), encoding="utf-8")
    (root / "DECISIONS.md").write_text(
        (root / "DECISIONS.md").read_text(encoding="utf-8").rstrip("\n") +
        "\n\n- D-1 | {} | \"yes, approve\" | about: brief v1\n- D-2 | {} | \"approve\" | "
        "about: structure v1\n- D-3 | {} | \"focus on pairwise grading first\" | about: "
        "scope\n".format(date, date, date) + "".join(x + "\n" for x in decisions),
        encoding="utf-8")
    q = (root / "QUESTIONS.md").read_text(encoding="utf-8")
    if a.scenario != "unused":
        q = q.replace("## Just in time\n", "## Just in time\n- Q-1 | trigger: the first paid "
                      "LLM API call is planned | your spending cap, and above what amount a "
                      "single cost needs your OK first? (I'll switch on the budget add-on with "
                      "your answer) | why: sets the budget limit\n")
    (root / "QUESTIONS.md").write_text(q, encoding="utf-8")
    log = [(root / "LOG.md").read_text(encoding="utf-8").rstrip("\n"), ""]
    t = start
    log.append("- {} | - | AI | workflow set up: brief v1, structure v1 | - | [workflow]".format(
        t.strftime(F)))
    log.append("- {} | - | AI | practice round passed; practice lines and file removed | - | "
               "[workflow]".format((t + timedelta(minutes=5)).strftime(F)))
    for i, step in enumerate(steps, 1):
        t = start + timedelta(days=i - 1, hours=1)
        sid = "S-{:03d}".format(i)
        log.append("- {} | {} | AI | step begins | - | [begin]".format(t.strftime(F), sid))
        for actor, what, part, tags in step:
            t += timedelta(minutes=6)
            tagtext = " ".join("[{}]".format(x) for x in tags.split())
            log.append("- {} | {} | {} | {} | {} |{}".format(
                t.strftime(F), sid, actor, what, part, " " + tagtext if tagtext else ""))
    (root / "LOG.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    evo = (root / "WORKFLOW-FIXES.md").read_text(encoding="utf-8")
    if a.scenario == "rollback":
        l1 = REVIEW_1.replace("S-010", "S-009").replace(
            "S-005 needed a redo (made-up citation)", "S-004 and S-008 needed redos (citations)")
        e1_time = (start + timedelta(days=9, hours=1, minutes=12)).strftime(F)
        e1 = ("## F-1 | testing\n- Step: S-010 ({})\n- Evidence: the same correction 2 times: "
              "missing-source (S-004, S-008)\n- Change: added rule R-3 \"Before citing a "
              "source, check that it exists: title, authors and year\" to RULES.md\n"
              "- Size: small\n- Made by: AI (level 2)\n- Expect: no more missing-source "
              "corrections\n- Measure: correction:missing-source\n- Before: 0.20 (2 of the "
              "last 10 steps)\n- Re-check at: S-015\n- Undo: delete R-3 from RULES.md\n"
              "- Outcome: -\n".format(e1_time))
        evo = evo.replace("No fixes yet.\n", l1 + "\n" + e1)
        rules = root / "RULES.md"
        rules.write_text(rules.read_text(encoding="utf-8") + RULE_R3, encoding="utf-8")
        # the change itself was logged in S-010
        log_text = (root / "LOG.md").read_text(encoding="utf-8")
        log_text = log_text.replace(
            "| S-010 | AI | drafted related-work paragraph 3 |",
            "| S-010 | AI | made workflow fix F-1 (small): added rule R-3 | - | "
            "[workflow]\n- {} | S-010 | AI | drafted related-work paragraph 3 |".format(
                e1_time))
        (root / "LOG.md").write_text(log_text, encoding="utf-8")
    else:
        reviews = "" if a.scenario == "experiment" else REVIEW_1
        extra = (REVIEWS_UNUSED if a.scenario == "unused" else
                 [("1", "S-011", "end of the reading phase; Stop if: nothing applies yet")]
                 if a.scenario == "experiment" else [])
        for n_, at, moving in extra:
            reviews += ("\n## Progress review {} | at {}\n- Moving: {}\n- Friction: none\n"
                        "- Unused: nothing yet\n- Brief: still true\n- Fixes being tested: "
                        "none\n- Suggested fixes: none\n".format(n_, at, moving))
        evo = evo.replace("No fixes yet.\n", reviews)
    (root / "WORKFLOW-FIXES.md").write_text(evo, encoding="utf-8")
    print("made {} ({} steps, scenario {})".format(root, n, a.scenario))


PY = "python"

if __name__ == "__main__":
    main(sys.argv[1:])
