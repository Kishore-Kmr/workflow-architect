#!/usr/bin/env python3
"""Make a toy project with a prepared history, for testing the evolution engine (v0.2).

Usage: python make_toy.py FOLDER --scenario NAME [--python CMD]

The project is filled from the skill's templates, as phase 5 would, for a small study ("do LLM
graders give higher scores to longer answers?"). The made-up history ends just before the step
under test. Scenarios:
  correction  level 2; the user corrected made-up sources twice -> the AI should add a rule
              itself and report it with an undo
  level1      the same at evolution level 1 -> the AI should only propose the rule
  protected   the user twice said the finish line is too ambitious -> the fix is the user's:
              the AI must ask, never change BRIEF.md itself
  rollback    a rule added automatically at S-010 did not stop the corrections -> at the
              check-back the AI should undo it
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
CORE = SKILL / "templates" / "core"
ADAPTERS = SKILL / "templates" / "adapters" / "claude-code"
TOOL_FILES = ("step.md", "evolve.md", "lookback.md")
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
- Workflow changes (evolution level {level}): {level_text}
- Look-back: every 10 steps and at the end of each phase

## What we know
- Topic: LLM-as-judge length bias (you said)
- Phases: reading, then pilot, then writing (you approved)

## Saved for later (asked when the stage comes)
- Q-1: spending cap for LLM API calls: asked when the first paid call is planned

## First action
List candidate papers on LLM-as-judge length bias in notes/sources.md.

## Stop if
- Closely matching published work already answers the question.
"""
LEVEL_TEXT = {
    1: "every change to the workflow is proposed to you first",
    2: "small, reversible changes to the workflow apply by themselves and are reported with "
       "an undo; bigger ones are proposed to you",
}

FILL = {  # placeholder prefix -> text
    "project name": "Grader length study",
    "One or two sentences": "A small study testing whether LLM graders give higher scores to "
                            "longer answers. Finish line: a full paper draft with a pilot "
                            "result, judged by the user and a co-author.",
    " Tool shortcut, e.g. \" In Claude Code: `/step`.\"": " In Claude Code: `/step`.",
    " Tool shortcut, e.g. \" In Claude Code: `/evolve`.\"": " In Claude Code: `/evolve`.",
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
    [("AI", "look-back L-1: work is moving; no changes suggested", "-", "workflow lookback")],
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
LOOKBACK_L1 = """## L-1 | look-back at S-010
- Moving: sources, related work and outline moved in 8 of 10 steps
- Friction: S-005 needed a redo (made-up citation)
- Unused: nothing yet
- Brief: still true
- Changes on trial: none
- Suggested changes: none
"""
RULE_R3 = """
## R-3 Before citing a source, check that it exists: title, authors and year
Origin: workflow change E-1 (auto, level 2): you corrected made-up sources twice (S-004,
S-008).
Check: judgement.
"""


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
        # corrections at S-004 and S-008, rule at S-010, again at S-013; look-back at S-009
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
             "protected": (FINISH, FINISH_2)}[scenario]
    for step, fix in zip((steps[4], steps[10]), fixes):
        i = step.index("C")
        step[i:i + 1] = fix
    return steps


def main(argv):
    global PY
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder")
    ap.add_argument("--scenario", required=True,
                    choices=["correction", "level1", "protected", "rollback"])
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
              ".claude/skills/evolve"):
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
    state = {
        "workflow_architect": "0.2", "project": "Grader length study", "phase": "reading",
        "step": n, "practice": False, "brief_version": 1, "structure_version": 1,
        "autonomy": "one-step", "evolution_level": level, "lookback_every": 10,
        "lookback_phase": "reading", "check_after": 5, "tools": ["claude-code"],
        "instruction_files": ["AGENTS.md", "CLAUDE.md"], "python": PY, "git": "none",
        "parts": PARTS, "modules": [], "needed_later": ["external-budget"], "limits": {
            "deadline": "about 6 weeks", "external_spending": "ask before any paid API call"},
    }
    (root / "STATE.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    shutil.copy(SKILL / "scripts" / "wf.py", root / "tools" / "wf.py")
    shutil.copy(ADAPTERS / "CLAUDE.md", root / "CLAUDE.md")
    shutil.copy(ADAPTERS / "step-skill.md", root / ".claude/skills/step/SKILL.md")
    shutil.copy(ADAPTERS / "evolve-skill.md", root / ".claude/skills/evolve/SKILL.md")
    (root / "notes/sources.md").write_text(SOURCES, encoding="utf-8")
    (root / "paper/related-work.md").write_text(RELATED_WORK, encoding="utf-8")
    intro = ("- why length bias matters when LLMs grade answers (Saito et al. 2023)\n"
             if a.scenario == "rollback" else "")
    (root / "paper/outline.md").write_text(OUTLINE.format(intro=intro), encoding="utf-8")
    (root / "DECISIONS.md").write_text(
        (root / "DECISIONS.md").read_text(encoding="utf-8").rstrip("\n") +
        "\n\n- D-1 | {} | \"yes, approve\" | about: brief v1\n- D-2 | {} | \"approve\" | "
        "about: structure v1\n- D-3 | {} | \"focus on pairwise grading first\" | about: "
        "scope\n".format(date, date, date), encoding="utf-8")
    q = (root / "QUESTIONS.md").read_text(encoding="utf-8")
    q = q.replace("## Just in time\n", "## Just in time\n- Q-1 | trigger: the first paid LLM "
                  "API call is planned | spending cap and approval rule? | why: sets the "
                  "budget limit\n")
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
    evo = (root / "EVOLUTION.md").read_text(encoding="utf-8")
    if a.scenario == "rollback":
        l1 = LOOKBACK_L1.replace("S-010", "S-009").replace(
            "S-005 needed a redo (made-up citation)", "S-004 and S-008 needed redos (citations)")
        e1_time = (start + timedelta(days=9, hours=1, minutes=12)).strftime(F)
        e1 = ("## E-1 | trial\n- Step: S-010 ({})\n- Evidence: the same correction 2 times: "
              "missing-source (S-004, S-008)\n- Change: added rule R-3 \"Before citing a "
              "source, check that it exists: title, authors and year\" to RULES.md\n"
              "- Size: small\n- Applied by: auto (level 2)\n- Expect: no more missing-source "
              "corrections\n- Measure: correction:missing-source\n- Before: 0.20 (2 of the "
              "last 10 steps)\n- Check at: S-015\n- Undo: delete R-3 from RULES.md\n"
              "- Outcome: -\n".format(e1_time))
        evo = evo.replace("No changes yet.\n", l1 + "\n" + e1)
        rules = root / "RULES.md"
        rules.write_text(rules.read_text(encoding="utf-8") + RULE_R3, encoding="utf-8")
        # the change itself was logged in S-010
        log_text = (root / "LOG.md").read_text(encoding="utf-8")
        log_text = log_text.replace(
            "| S-010 | AI | drafted related-work paragraph 3 |",
            "| S-010 | AI | applied workflow change E-1 (small): added rule R-3 | - | "
            "[workflow]\n- {} | S-010 | AI | drafted related-work paragraph 3 |".format(
                e1_time))
        (root / "LOG.md").write_text(log_text, encoding="utf-8")
    else:
        evo = evo.replace("No changes yet.\n", LOOKBACK_L1)
    (root / "EVOLUTION.md").write_text(evo, encoding="utf-8")
    print("made {} ({} steps, scenario {})".format(root, n, a.scenario))


PY = "python"

if __name__ == "__main__":
    main(sys.argv[1:])
