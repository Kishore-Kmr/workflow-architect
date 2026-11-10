#!/usr/bin/env python3
"""Workflow tool for a project set up by workflow-architect (v0.3).

Commands (run from anywhere; the project is the folder above tools/, or pass --root DIR):
  status               three-line status, plus a "Due:" line when something is due (read-only)
  begin [--practice]   start a step: number it, log it, print the status
  log ACTOR WHAT [--part PART] [--tags "t1 t2"]
                       append one event line to LOG.md (tags are checked)
  check                mechanical checks of the workflow files (read-only)
  health [--json]      the check, then the workflow's health from LOG.md: warnings,
                       re-checks of fixes being tested, progress review due, proposals
                       waiting (read-only)
  fix add WHAT --size small|big|yours --by ai|you|proposed --measure M
          --evidence TEXT --undo TEXT [--expect TEXT]
                       record a workflow fix in WORKFLOW-FIXES.md and LOG.md; refused when
                       the fix level does not allow the AI to make it
  fix mark F-N STATUS NOTE
                       move a fix on: proposed -> testing (the user approved) or rejected;
                       testing -> kept or undone; kept -> undone
  addon on NAME [--parts P1,P2]   |   addon off NAME NOTE
                       switch an add-on on or off (see tools/addons.md); budget and
                       second-opinion are switched off only with the user's answer logged
  spend AMOUNT WHAT [--estimate]
                       budget add-on: record a cost in SPENDING.md; refused over the cap, and
                       over "ask_over" without the user's answer logged in this step
  opinion PART pass|fail FINDINGS
                       second-opinion add-on: record a verdict in SECOND-OPINIONS.md
  experiment new TITLE   |   experiment start X-NNN
                       experiment-plans add-on: create a plan; lock its "What each result
                       would mean" before the run
  practice-done        end the practice round: remove its log lines and files, record it passed

Warning ids: progress, rework, workflow, overrun, escaped, questions, budget,
second-opinion-quiet, correction:<key>, repeat:<key>, silent:R-<n>, unused:<add-on>. A fix's
measure (M) is one of them.
Only the Python standard library is used.
"""
import hashlib
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

VERSION = "0.3"
CORE_FILES = ["BRIEF.md", "NEXT.md", "STATE.json", "LOG.md", "DECISIONS.md", "QUESTIONS.md",
              "RULES.md", "WORKFLOW-FIXES.md", "tools/step.md", "tools/fixes.md",
              "tools/progress-review.md", "tools/addons.md"]
# add-on -> who may switch it off: "user" (only with the user's answer logged) or "ai"
ADDONS = {"budget": "user", "second-opinion": "user", "experiment-plans": "ai"}
SPENDING_FILE = "SPENDING.md"
OPINIONS_FILE = "SECOND-OPINIONS.md"
EXPERIMENTS_DIR = "experiments"
LOCK_FILE = ".workflow-architect/locks.json"
PLAN_SECTIONS = ["Question", "Setup", "What each result would mean", "Results",
                 "What we learned"]
STOP_FILE = "STOP-NOTE.md"
STOP_LINES = ["Tried", "Found", "Reusable", "Could still go"]
STOP_LINE_RE = re.compile(r"^- (Tried|Found|Reusable|Could still go):[ \t]*(.*)$")
SPEND_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (S-\d{3,}|P|-) \| "
                      r"(-?\d+(?:\.\d+)?) \| (estimate|measured) \| (.+)$")
OPINION_RE = re.compile(r"^- (SO-\d+) \| (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (S-\d{3,}|P|-) \| "
                        r"([a-z0-9][a-z0-9-]*) \| (pass|fail) \| (.+)$")
SPENDING_HEADER = """# Spending

Every cost of this project, written with `tools/wf.py spend` (the budget add-on, see
`tools/addons.md`). The cap is in STATE.json "limits"; only the user can raise it.
Format: `- time | step | amount | estimate or measured | what`

"""
OPINIONS_HEADER = """# Second opinions

Verdicts of the second opinion (see `tools/second-opinion.md`), written with
`tools/wf.py opinion`, newest at the bottom.
Format: `- SO-<n> | time | step | part | pass or fail | findings`

"""
PLAN_TEMPLATE = """# {xid} {title}

## Question
(what we want to find out)

## Setup
(data, models, how many runs, expected cost; pilot before scale: the smallest run that could show the idea is wrong)

## What each result would mean
(for each likely result: what we would conclude, and what we would do next)

## Results
(after the run)

## What we learned
(after the run)
"""
MAX_INSTRUCTION_LINES = 80
MAX_RULES = 12
PRACTICE_PART = "practice"
PRACTICE_FILE = ".workflow-architect/practice.md"
GUARD_FILE = ".workflow-architect/guard.json"
GUARDED_FILES = ["BRIEF.md", "DECISIONS.md"]       # the user's: goal, limits, notes, decisions
GUARDED_STATE = ["fix_level", "limits"]
# tag name -> does it need a value (tag:value)?
TAGS = {"progress": True, "workflow": False, "fail": False, "redo": False, "correction": True,
        "repeat": True, "asked": False, "answered": False, "escaped": True, "used": True,
        "overrun": False, "rule": True, "begin": False, "review": False, "noted": True}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
WARNING_RE = re.compile(r"^(progress|rework|workflow|overrun|escaped|questions|budget|"
                        r"second-opinion-quiet|(correction|repeat):[a-z0-9][a-z0-9-]*|"
                        r"silent:R-\d+|unused:(" + "|".join(ADDONS) + r"))$")
MEASURE_RE = WARNING_RE
NOT_PER_STEP = ("budget", "second-opinion-quiet", "silent", "unused")  # no before/after rate
HIGHER_IS_BETTER = {"progress"}
TIME_FMT = "%Y-%m-%d %H:%M"
ENTRY_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (S-\d{3,}|P|-) \| "
                      r"([A-Za-z][\w-]*) \| (.+?) \| (\S+) \|(.*)$")
TAG_RE = re.compile(r"\[([a-z]+)(?::([^\]\s]+))?\]")
RULE_HEAD = re.compile(r"^## (R-\d+)\b[ \t]*(.*)$", re.M)
EVO_HEAD = re.compile(r"^## (F-\d+)[ \t]*\|[ \t]*(\S+)[ \t]*$")
FIELD_RE = re.compile(r"^- ([A-Z][A-Za-z -]*?): ?(.*)$")
EVO_FIELDS = ["Step", "Evidence", "Change", "Size", "Made by", "Expect", "Measure", "Before",
              "Re-check at", "Undo", "Outcome"]
STATUSES = {"proposed", "testing", "kept", "undone", "rejected"}
SIZES = {"small", "big", "yours"}
APPLIERS = {"ai", "you", "proposed"}
TRANSITIONS = {"proposed": {"testing", "rejected"}, "testing": {"kept", "undone"},
               "kept": {"undone"}}
STATE_SCHEMA = {  # key -> allowed types (all required)
    "workflow_architect": (str,), "project": (str,), "phase": (str,), "step": (int,),
    "practice": (bool,), "brief_version": (int,), "structure_version": (int,),
    "autonomy": (str,), "fix_level": (int,), "review_every": (int,),
    "review_phase": (str,), "recheck_after": (int,), "tools": (list,), "instruction_files": (list,),
    "python": (str, type(None)), "git": (str,), "parts": (dict,), "addons": (dict,),
    "addons_later": (list,), "limits": (dict,),
}
CHOICES = {"autonomy": {"one-step", "until-you"}, "fix_level": {1, 2, 3},
           "git": {"each-step", "manual", "none"}}
# Starting values; STATE.json "thresholds" may override them (a big fix, see tools/fixes.md).
THRESHOLDS = {
    "window": 10,                 # steps looked at for rates
    "min_steps": 5,               # the progress warning needs at least this many steps
    "progress_min": 0.5,          # warn when fewer than this share of steps made progress
    "rework_warn_at": 3,          # redo/fail steps in the window
    "correction_warn_at": 2,      # the same correction key
    "repeat_warn_at": 3,          # the same repeated instruction
    "questions_max": 5,           # warn when more questions than this are open
    "question_age_days": 3,       # ...or one is open for more working days than this
    "overrun_factor": 3,          # a step longer than this times the usual step...
    "overrun_floor_minutes": 20,  # ...and at least this long
    "silent_rule_steps": 30,      # a rule that has not mattered for this many steps
    "workflow_window": 5,         # process share: of the last this-many steps...
    "workflow_warn_at": 3,        # ...this many were only about the workflow
    "unused_addon_steps": 20,     # an add-on not used for this many steps
    "budget_warn_share": 0.8,     # warn when this share of the budget cap is spent
    "quiet_opinions": 15,         # second opinions in a row that all passed
}


class WfError(Exception):
    pass


# ---------- files ----------

def read(path):
    """Text with line endings turned into \\n (for parsing)."""
    return path.read_text(encoding="utf-8-sig")


def read_raw(path):
    """Text with line endings kept as they are (for rewriting a file)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def find_root(argv):
    if "--root" in argv:
        i = argv.index("--root")
        if i + 1 >= len(argv):
            raise WfError("--root needs a folder")
        root = Path(argv[i + 1])
        del argv[i:i + 2]
        return root.resolve()
    here = Path(__file__).resolve().parent.parent
    return here if (here / "STATE.json").exists() else Path.cwd()


def load_state(root):
    p = root / "STATE.json"
    if not p.exists():
        raise WfError("no STATE.json in " + str(root))
    try:
        return json.loads(read(p))
    except json.JSONDecodeError as e:
        raise WfError("STATE.json is not valid JSON: {}".format(e))


def save_state(root, state):
    write(root / "STATE.json", json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def append_line(path, line):
    text = read_raw(path) if path.exists() else ""
    nl = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith(("\n", "\r")):
        text += nl
    write(path, text + line + nl)


def now():
    return datetime.now().strftime(TIME_FMT)


def minutes(a, b):
    return (datetime.strptime(b, TIME_FMT) - datetime.strptime(a, TIME_FMT)).total_seconds() / 60


def one_line(text):
    return " ".join(str(text).split())


def step_name(n):
    return "S-{:03d}".format(n)


def take_opts(argv, names):
    opts, rest, i = {}, [], 0
    while i < len(argv):
        if argv[i] in names:
            if i + 1 >= len(argv):
                raise WfError(argv[i] + " needs a value")
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return opts, rest


# ---------- log ----------

def parse_tags(text):
    """Return list of (name, value) or raise WfError; text is like '[a] [b:c]'."""
    text = text.strip()
    tags = TAG_RE.findall(text)
    if TAG_RE.sub("", text).strip():
        raise WfError("badly formed tags: '{}'".format(text))
    return [(n, v or None) for n, v in tags]


def tag_problems(tags, state, rule_ids, practice_line):
    parts = set(state.get("parts", {}))
    if practice_line:
        parts.add(PRACTICE_PART)
    out = []
    for name, value in tags:
        label = name + (":" + value if value else "")
        if name not in TAGS:
            out.append("unknown tag [{}] (known: {})".format(label, ", ".join(TAGS)))
        elif TAGS[name] and not value:
            out.append("tag [{}] needs a value, like [{}:something]".format(name, name))
        elif not TAGS[name] and value:
            out.append("tag [{}] takes no value".format(label))
        elif name == "progress" and value not in parts:
            out.append("[progress:{}]: '{}' is not a part in STATE.json (parts: {})".format(
                value, value, ", ".join(sorted(parts)) or "none"))
        elif name == "rule" and value not in rule_ids:
            out.append("[rule:{}]: no rule {} in RULES.md".format(value, value))
        elif name in ("correction", "repeat") and not KEY_RE.match(value):
            out.append("[{}]: key must be lowercase words with hyphens".format(label))
        elif name == "used" and value not in ADDONS:
            out.append("[used:{}]: not an add-on (known: {})".format(value, ", ".join(ADDONS)))
        elif name == "noted" and not WARNING_RE.match(value):
            out.append("[{}]: must name a health warning id, like [noted:overrun] or "
                       "[noted:correction:some-key]".format(label))
    return out


def parse_log(root):
    """Return (entries, problems). An entry is a dict; problems are strings."""
    entries, problems = [], []
    p = root / "LOG.md"
    if not p.exists():
        return entries, ["LOG.md is missing"]
    for n, line in enumerate(read(p).splitlines(), 1):
        if not line.startswith("- "):
            continue
        m = ENTRY_RE.match(line)
        if not m:
            problems.append("LOG.md line {}: not in the format "
                            "'- time | step | actor | what | part | tags'".format(n))
            continue
        t, step, actor, what, part, tagtext = m.groups()
        try:
            tags = parse_tags(tagtext)
        except WfError as e:
            problems.append("LOG.md line {}: {}".format(n, e))
            tags = []
        entries.append({"line": n, "time": t, "step": step, "actor": actor, "what": what,
                        "part": part, "tags": tags})
    return entries, problems


def current_step_id(state):
    if state.get("practice"):
        return "P"
    step = state.get("step", 0)
    return step_name(step) if step > 0 else "-"


def add_log(root, state, actor, what, part="-", tags=()):
    if not re.match(r"^[A-Za-z][\w-]*$", actor):
        raise WfError("actor must be one word, like AI or YOU")
    what = one_line(what.replace("|", "/"))
    if not what:
        raise WfError("WHAT is empty")
    part = part or "-"
    practice = bool(state.get("practice"))
    parts = set(state.get("parts", {})) | ({PRACTICE_PART} if practice else set())
    if part != "-" and part not in parts:
        raise WfError("part '{}' is not in STATE.json (parts: {})".format(
            part, ", ".join(sorted(parts))))
    parsed = []
    for t in tags:
        t = t.strip().strip("[]")
        if t:
            name, _, value = t.partition(":")
            parsed.append((name, value or None))
    problems = tag_problems(parsed, state, rule_ids(root), practice)
    problems += ["[used:{}]: that add-on is not on".format(v) for n, v in parsed
                 if n == "used" and v in ADDONS and not addon_on(state, v)]
    if problems:
        raise WfError("; ".join(problems))
    tagtext = " ".join("[{}]".format(n + (":" + v if v else "")) for n, v in parsed)
    line = "- {} | {} | {} | {} | {} |{}".format(now(), current_step_id(state), actor, what,
                                                 part, " " + tagtext if tagtext else "")
    append_line(root / "LOG.md", line)
    if ("review", None) in parsed and not practice:
        state["review_phase"] = state.get("phase")   # the next phase change makes one due
        save_state(root, state)
    return line


# ---------- rules, questions, next ----------

def parse_rules(root):
    p = root / "RULES.md"
    if not p.exists():
        return []
    text = read(p)
    heads = list(RULE_HEAD.finditer(text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        origin = re.search(r"^Origin:[ \t]*(.*)$", text[m.end():end], re.M)
        origin = origin.group(1).strip() if origin else None
        out.append({"id": m.group(1), "paused": m.group(2).lower().startswith("(paused)"),
                    "origin": origin,
                    "core": bool(origin) and origin.lower().startswith("workflow-architect core")})
    return out


def rule_ids(root):
    return [r["id"] for r in parse_rules(root)]


def parse_questions(root):
    """Return {"open": [{"id", "date"}], "later": n, "answered": n}."""
    out = {"open": [], "later": 0, "answered": 0}
    p = root / "QUESTIONS.md"
    if not p.exists():
        return out
    section = None
    for line in read(p).splitlines():
        h = line.strip().lower()
        if h.startswith("## "):
            section = ("open" if "open" in h else "later" if "just in time" in h
                       else "answered" if "answered" in h else None)
        elif line.startswith("- Q-") and section:
            if section == "open":
                qid = re.match(r"^- (Q-\d+)", line)
                date = re.search(r"asked (\d{4}-\d{2}-\d{2})", line)
                out["open"].append({"id": qid.group(1) if qid else "Q-?",
                                    "date": date.group(1) if date else None})
            else:
                out[section] += 1
    return out


def read_next(root):
    p = root / "NEXT.md"
    if not p.exists():
        return None, None, ["NEXT.md is missing"]
    text = read(p)
    actors = re.findall(r"^Actor:[ \t]*(.*)$", text, re.M)
    actions = re.findall(r"^Action:[ \t]*(.*)$", text, re.M)
    problems = []
    if len(actors) != 1:
        problems.append("NEXT.md must have exactly one 'Actor:' line (found {})".format(
            len(actors)))
    elif actors[0].strip() not in ("AI", "YOU"):
        problems.append("NEXT.md: Actor must be AI or YOU, not '{}'".format(actors[0].strip()))
    if len(actions) != 1:
        problems.append("NEXT.md must have exactly one 'Action:' line (found {})".format(
            len(actions)))
    elif not actions[0].strip():
        problems.append("NEXT.md: the Action line is empty")
    if (len(actors) == 1 and actors[0].strip() == "YOU"
            and not re.search(r"^Estimated:[ \t]*\S", text, re.M)):
        problems.append("NEXT.md: an action for the user needs an 'Estimated:' line (how long "
                        "it will take them)")
    actor = actors[0].strip() if len(actors) == 1 else None
    action = actions[0].strip() if len(actions) == 1 else None
    return actor, action, problems


# ---------- workflow fixes ----------

def _num(pattern, text):
    m = re.search(pattern, text or "")
    return int(m.group(1)) if m else None


def parse_fixes(root):
    """Return (entries, problems) for the F-<n> fixes in WORKFLOW-FIXES.md."""
    p = root / "WORKFLOW-FIXES.md"
    if not p.exists():
        return [], ["WORKFLOW-FIXES.md is missing"]
    entries, problems, cur = [], [], None
    for n, line in enumerate(read(p).splitlines(), 1):
        if line.startswith("## "):
            cur = None
            m = EVO_HEAD.match(line)
            if m:
                cur = {"id": m.group(1), "status": m.group(2), "line": n, "fields": {}}
                entries.append(cur)
            elif line.startswith("## F-"):
                problems.append("WORKFLOW-FIXES.md line {}: a fix heading must look like "
                                "'## F-1 | testing'".format(n))
        elif cur is not None:
            m = FIELD_RE.match(line)
            if m:
                cur["fields"][m.group(1)] = m.group(2).strip()
    for e in entries:
        f = e["fields"]
        applied = f.get("Made by", "")
        before = re.match(r"^(\d+(?:\.\d+)?)", f.get("Before", ""))
        e.update({"step": _num(r"S-(\d+)", f.get("Step")),
                  "check_at": _num(r"S-(\d+)", f.get("Re-check at")),
                  "size": f.get("Size", ""), "by": applied.split()[0].lower() if applied else "",
                  "level": _num(r"level (\d)", applied), "measure": f.get("Measure", ""),
                  "before": float(before.group(1)) if before else None,
                  "change": f.get("Change", "")})
    return entries, problems


def fix_problems(entries, state):
    out = []
    cur = state.get("step") if isinstance(state.get("step"), int) else 0
    if [e["id"] for e in entries] != ["F-{}".format(i) for i in range(1, len(entries) + 1)]:
        out.append("WORKFLOW-FIXES.md: fix ids must run F-1, F-2, ... in order")
    for e in entries:
        w = "WORKFLOW-FIXES.md " + e["id"]
        f = e["fields"]
        if e["status"] not in STATUSES:
            out.append(w + ": status must be one of " + ", ".join(sorted(STATUSES)))
        missing = [k for k in EVO_FIELDS if k not in f]
        if missing:
            out.append(w + ": missing line(s): " + ", ".join(missing))
            continue
        if e["step"] is None:
            out.append(w + ": 'Step' must name a step, like S-012")
        elif e["step"] > cur:
            out.append(w + ": its step is after the current step")
        if e["size"] not in SIZES:
            out.append(w + ": 'Size' must be one of " + ", ".join(sorted(SIZES)))
        if e["by"] not in APPLIERS:
            out.append(w + ": 'Made by' must start with AI, you or proposed")
        if not MEASURE_RE.match(e["measure"]):
            out.append(w + ": 'Measure' must be one of the measures in tools/wf.py")
        waiting = e["status"] in ("proposed", "rejected")
        if waiting != (e["by"] == "proposed"):
            out.append(w + ": 'Made by: proposed' goes with status proposed or rejected, "
                           "and only with those")
        if not waiting and (e["check_at"] is None or e["before"] is None):
            out.append(w + ": a fix in use needs 'Before' (a number) and 'Re-check at' (a step)")
        if e["by"] == "ai":
            if e["level"] is None:
                out.append(w + ": 'Made by: AI' must say the fix level, like 'AI (level 2)'")
            elif e["size"] == "yours":
                out.append(w + ": a fix that is the user's to decide is never made by the AI")
            elif e["level"] == 1:
                out.append(w + ": at fix level 1 every fix is proposed")
            elif e["size"] == "big" and e["level"] < 3:
                out.append(w + ": at fix level 2 a big fix is proposed, not made by the AI")
        closed = e["status"] in ("kept", "undone", "rejected")
        if closed == (f["Outcome"] in ("", "-")):
            out.append(w + ": 'Outcome' is filled in when, and only when, the change is kept, "
                           "undone or rejected")
    return out


# ---------- the guard: the user's files change only with the user ----------

def user_answered(entries, step):
    """Is a line by the user, or an [answered] line, logged in this step?"""
    return any(e["step"] == step and (e["actor"] == "YOU" or ("answered", None) in e["tags"])
               for e in entries)


def fingerprint(root, state):
    fp = {}
    for f in GUARDED_FILES:
        p = root / f
        fp[f] = hashlib.sha256(read(p).encode("utf-8")).hexdigest() if p.exists() else None
    for k in GUARDED_STATE:
        fp["STATE.json " + k] = json.dumps(state.get(k), sort_keys=True)
    return fp


def save_guard(root, state):
    p = root / GUARD_FILE
    p.parent.mkdir(exist_ok=True)
    write(p, json.dumps({"step": current_step_id(state),
                         "fingerprint": fingerprint(root, state)}, indent=2) + "\n")


def guard_problems(root, state, entries):
    p = root / GUARD_FILE
    if not p.exists():
        return []
    try:
        guard = json.loads(read(p))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [GUARD_FILE + ": not valid JSON (the next 'begin' rewrites it)"]
    step = current_step_id(state)
    if guard.get("step") != step:
        return []
    old = guard.get("fingerprint", {})
    changed = [k for k, v in fingerprint(root, state).items() if old.get(k) != v]
    if not changed or user_answered(entries, step):
        return []
    return ["{} changed in step {}, but no answer from the user is logged in this step. These "
            "are the user's to change: undo it, or ask and log their answer with "
            "[answered]".format(", ".join(changed), step)]


# ---------- add-ons ----------

def addon_on(state, name):
    addons = state.get("addons")
    return (isinstance(addons, dict) and isinstance(addons.get(name), dict)
            and addons[name].get("on") is True)


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def budget_limits(state):
    """The user's budget from STATE.json limits, or None if it is not set properly."""
    limits = state.get("limits") if isinstance(state.get("limits"), dict) else {}
    b = limits.get("budget")
    if not isinstance(b, dict):
        return None
    cap, ask, cur = b.get("cap"), b.get("ask_over", 0), b.get("currency", "")
    if not (is_number(cap) and is_number(ask) and isinstance(cur, str) and cap > 0 and ask >= 0):
        return None
    return {"cap": float(cap), "ask_over": float(ask), "currency": cur}


def parse_lines(root, name, pattern, fmt):
    """Parse the '- ' lines of an add-on file; return (matches, problems)."""
    p = root / name
    if not p.exists():
        return [], []
    out, problems = [], []
    for n, line in enumerate(read(p).splitlines(), 1):
        if line.startswith("- "):
            m = pattern.match(line)
            if m:
                out.append(m.groups())
            else:
                problems.append("{} line {}: not in the format '{}'".format(name, n, fmt))
    return out, problems


def parse_spending(root):
    rows, problems = parse_lines(root, SPENDING_FILE, SPEND_RE,
                                 "- time | step | amount | estimate or measured | what")
    return [{"time": r[0], "step": r[1], "amount": float(r[2]), "kind": r[3], "what": r[4]}
            for r in rows], problems


def parse_opinions(root):
    rows, problems = parse_lines(root, OPINIONS_FILE, OPINION_RE,
                                 "- SO-<n> | time | step | part | pass or fail | findings")
    return [{"id": r[0], "time": r[1], "step": r[2], "part": r[3], "verdict": r[4],
             "findings": r[5]} for r in rows], problems


def plans(root):
    """Experiment plans: [(id, path)], from experiments/X-<n>-*.md."""
    d = root / EXPERIMENTS_DIR
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("X-*.md")):
        m = re.match(r"^(X-\d+)", p.name)
        if m:
            out.append((m.group(1), p))
    return out


def plan_sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def filled(body):
    """More than placeholders like '(after the run)' or comments?"""
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    return any(not (l.startswith("(") and l.endswith(")")) for l in lines)


def meaning_hash(sections):
    text = " ".join(sections.get("What each result would mean", "").split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_locks(root):
    p = root / LOCK_FILE
    if not p.exists():
        return {}
    try:
        locks = json.loads(read(p))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return locks if isinstance(locks, dict) else None


def experiment_problems(root):
    locks = load_locks(root)
    if locks is None:
        return [LOCK_FILE + ": not valid JSON"]
    out = []
    found = plans(root)
    if len({x for x, _ in found}) != len(found):
        out.append("experiments/: two plans share an id")
    for xid, p in found:
        s = plan_sections(read(p))
        missing = [h for h in PLAN_SECTIONS if h not in s]
        if missing:
            out.append("experiments/{}: missing section(s): {}".format(p.name, ", ".join(missing)))
            continue
        lock = locks.get(xid)
        if isinstance(lock, dict):
            if meaning_hash(s) != lock.get("hash"):
                out.append("experiments/{}: 'What each result would mean' was changed after the "
                           "experiment started ({}). Restore it as it was, and put new thoughts "
                           "under 'What we learned'".format(p.name, lock.get("step", "?")))
        elif filled(s["Results"]):
            out.append("experiments/{}: has results, but the experiment was never started: run "
                       "'wf.py experiment start {}' before running an experiment".format(p.name,
                                                                                         xid))
    return out


def addon_problems(root, state):
    out = []
    addons = state.get("addons") if isinstance(state.get("addons"), dict) else {}
    parts = state.get("parts") if isinstance(state.get("parts"), dict) else {}
    for name, a in addons.items():
        if name not in ADDONS:
            out.append("STATE.json addons: unknown add-on '{}' (known: {})".format(
                name, ", ".join(ADDONS)))
        elif not (isinstance(a, dict) and isinstance(a.get("on"), bool)
                  and isinstance(a.get("since"), int) and not isinstance(a.get("since"), bool)):
            out.append("STATE.json addons: '{}' needs \"on\" (true or false) and \"since\" (a "
                       "step number)".format(name))
    later = state.get("addons_later") if isinstance(state.get("addons_later"), list) else []
    for name in later:
        if name not in ADDONS:
            out.append("STATE.json addons_later: unknown add-on '{}'".format(name))
    if addon_on(state, "budget"):
        b = budget_limits(state)
        if b is None:
            out.append("budget add-on: STATE.json limits.budget needs \"cap\" (above 0), "
                       "\"currency\" and \"ask_over\" (0 or more), from the user's answer")
        if not (root / SPENDING_FILE).exists():
            out.append("missing file: " + SPENDING_FILE + " (the budget add-on is on)")
        spends, problems = parse_spending(root)
        out += problems
        total = sum(x["amount"] for x in spends)
        if b and total > b["cap"] + 1e-9:
            out.append("{}: {:.2f} {} spent, over the cap of {:.2f}; only the user can raise "
                       "the cap".format(SPENDING_FILE, total, b["currency"], b["cap"]))
    if addon_on(state, "second-opinion"):
        listed = addons["second-opinion"].get("parts")
        if not isinstance(listed, list) or not listed:
            out.append("second-opinion add-on: STATE.json addons.second-opinion needs "
                       "\"parts\": the parts it checks")
        else:
            out += ["second-opinion add-on: '{}' is not a part in STATE.json".format(x)
                    for x in listed if x not in parts]
        for f in ("tools/second-opinion.md", OPINIONS_FILE):
            if not (root / f).exists():
                out.append("missing file: {} (the second-opinion add-on is on; see "
                           "tools/addons.md)".format(f))
        out += parse_opinions(root)[1]
    if addon_on(state, "experiment-plans") and not (root / EXPERIMENTS_DIR).is_dir():
        out.append("missing folder: experiments/ (the experiment-plans add-on is on)")
    return out + experiment_problems(root)     # plans stay checked when the add-on is off


def addons_summary(root, state):
    out = []
    if addon_on(state, "budget"):
        b = budget_limits(state)
        spent = sum(x["amount"] for x in parse_spending(root)[0])
        out.append("budget {:.2f} of {:.2f} {}".format(spent, b["cap"], b["currency"]) if b
                   else "budget (cap not set)")
    if addon_on(state, "second-opinion"):
        out.append("second opinion on " + ", ".join(
            state["addons"]["second-opinion"].get("parts") or ["?"]))
    if addon_on(state, "experiment-plans"):
        out.append("experiment plans ({} started)".format(len(load_locks(root) or {})))
    return "; ".join(out)


# ---------- stop note ----------

def stop_problems(root, state):
    """STOP-NOTE.md: required when the project is stopped; every entry has its four lines."""
    p = root / STOP_FILE
    if not p.exists():
        return (["STATE.json phase is \"stopped\" but there is no STOP-NOTE.md (see AGENTS.md)"]
                if state.get("phase") == "stopped" else [])
    entries, cur, field = [], None, None
    for line in read(p).splitlines():
        if line.startswith("## "):
            cur, field = {"head": line[3:].strip(), "fields": {}}, None
            entries.append(cur)
            continue
        if cur is None:
            continue
        m = STOP_LINE_RE.match(line)
        if m:
            field = m.group(1)
            cur["fields"][field] = m.group(2).strip()
        elif field and line.strip():               # a value continued on the next lines
            cur["fields"][field] = (cur["fields"][field] + " " + line.strip()).strip()
    if not entries:
        return ["STOP-NOTE.md has no entry like '## <date> | stopped: <what>'"]
    out = []
    for e in entries:
        missing = [k for k in STOP_LINES if not e["fields"].get(k)]
        if missing:
            out.append("STOP-NOTE.md '{}': missing or empty: {}".format(
                e["head"], ", ".join("- {}:".format(k) for k in missing)))
    return out


# ---------- check ----------

def check(root):
    problems = []
    try:
        state = load_state(root)
    except WfError as e:
        return [str(e)]
    for key, types in STATE_SCHEMA.items():
        if key not in state:
            problems.append("STATE.json: missing '{}'".format(key))
        elif not isinstance(state[key], types) or (
                isinstance(state[key], bool) and bool not in types):
            problems.append("STATE.json: '{}' has the wrong type".format(key))
        elif key in CHOICES and state[key] not in CHOICES[key]:
            problems.append("STATE.json: '{}' must be one of {}".format(
                key, ", ".join(sorted(map(str, CHOICES[key])))))
        elif key in ("review_every", "recheck_after") and state[key] < 1:
            problems.append("STATE.json: '{}' must be 1 or more".format(key))
    if "thresholds" in state:
        th = state["thresholds"]
        if not isinstance(th, dict) or any(k not in THRESHOLDS or isinstance(v, bool) or
                                           not isinstance(v, (int, float))
                                           for k, v in th.items()):
            problems.append("STATE.json: 'thresholds' must map names from tools/wf.py to "
                            "numbers")
    parts = state.get("parts") if isinstance(state.get("parts"), dict) else {}
    if not parts:
        problems.append("STATE.json: 'parts' must name at least one end-product part")
    for name, path in parts.items():
        if not KEY_RE.match(name):
            problems.append("STATE.json: part name '{}' must be lowercase words with "
                            "hyphens".format(name))
        if not isinstance(path, str) or not (root / path).exists():
            problems.append("STATE.json: part '{}' points to '{}', which does not exist".format(
                name, path))
    instr = state.get("instruction_files") if isinstance(
        state.get("instruction_files"), list) else []
    if not instr:
        problems.append("STATE.json: 'instruction_files' is empty")
    for f in CORE_FILES + instr:
        p = root / f
        if not p.exists():
            problems.append("missing file: " + f)
            continue
        try:
            text = read(p)
        except UnicodeDecodeError:
            problems.append(f + ": not UTF-8 text")
            continue
        if "{{" in text:
            problems.append(f + ": unfilled template placeholder ({{...}})")
        if f in instr and len(text.splitlines()) > MAX_INSTRUCTION_LINES:
            problems.append("{}: {} lines, the cap is {}".format(
                f, len(text.splitlines()), MAX_INSTRUCTION_LINES))
    _, _, next_problems = read_next(root)
    problems += next_problems
    rules = parse_rules(root)
    ids = [r["id"] for r in rules]
    active = [r for r in rules if not r["paused"]]
    if len(active) > MAX_RULES:
        problems.append("RULES.md: {} rules in use, the cap is {} (merge or pause one)".format(
            len(active), MAX_RULES))
    if len(ids) != len(set(ids)):
        problems.append("RULES.md: duplicate rule ids")
    for r in rules:
        if not r["origin"]:
            problems.append("RULES.md: {} has no 'Origin:' line".format(r["id"]))
    entries, log_problems = parse_log(root)
    problems += log_problems
    evo, evo_problems = parse_fixes(root)
    # log lines may name a rule that a later fix removed, if WORKFLOW-FIXES.md records it
    known_rules = set(ids) | {r for e in evo for k in ("Change", "Undo")
                              for r in re.findall(r"\bR-\d+\b", e["fields"].get(k, ""))}
    last_time, last_step = "", 0
    for e in entries:
        where = "LOG.md line {}".format(e["line"])
        if e["time"] < last_time:
            problems.append(where + ": time goes backwards")
        last_time = e["time"]
        if e["step"].startswith("S-"):
            n = int(e["step"][2:])
            if n < last_step or n > state.get("step", 0):
                problems.append(where + ": step number out of order")
            last_step = n
        if e["step"] == "P" and not state.get("practice"):
            problems.append(where + ": practice line left over (run practice-done)")
        is_practice = e["step"] == "P"
        for msg in tag_problems(e["tags"], state, known_rules, is_practice):
            problems.append(where + ": " + msg)
        if e["part"] != "-" and e["part"] not in set(parts) | (
                {PRACTICE_PART} if is_practice else set()):
            problems.append(where + ": part '{}' is not in STATE.json".format(e["part"]))
    if not state.get("practice") and (root / PRACTICE_FILE).exists():
        problems.append(PRACTICE_FILE + " left over from the practice round")
    problems += evo_problems + fix_problems(evo, state)
    problems += addon_problems(root, state)
    problems += stop_problems(root, state)
    problems += guard_problems(root, state, entries)
    return problems


# ---------- health ----------

def analyse(root):
    """Everything the health metrics need, read once."""
    state = load_state(root)
    entries, _ = parse_log(root)
    evo, _ = parse_fixes(root)
    th = dict(THRESHOLDS)
    if isinstance(state.get("thresholds"), dict):
        th.update({k: v for k, v in state["thresholds"].items()
                   if k in th and isinstance(v, (int, float)) and not isinstance(v, bool)})
    steps = {}
    for e in entries:
        if not e["step"].startswith("S-"):
            continue
        n = int(e["step"][2:])
        s = steps.setdefault(n, {"n": n, "tags": set(), "begin": None, "end": e["time"],
                                 "you": False})
        s["tags"].update(e["tags"])
        if ("begin", None) in e["tags"] and s["begin"] is None:
            s["begin"] = e["time"]
        s["end"] = e["time"]
        s["you"] = s["you"] or e["actor"] == "YOU"
    cur = state.get("step", 0)
    ctx = {"root": root, "state": state, "evo": evo, "th": th, "steps": steps,
           "nums": sorted(steps), "cur": cur if isinstance(cur, int) else 0,
           "dates": sorted({e["time"][:10] for e in entries if e["step"].startswith("S-")}),
           "questions": parse_questions(root), "rules": parse_rules(root),
           "spent": sum(x["amount"] for x in parse_spending(root)[0]),
           "opinions": parse_opinions(root)[0]}
    ctx["long"] = long_steps(ctx)
    return ctx


def long_steps(ctx):
    """Steps (without the user's own work) that took far longer than the usual step."""
    th, steps = ctx["th"], ctx["steps"]
    nums = [n for n in ctx["nums"] if steps[n]["begin"] and not steps[n]["you"]]
    dur = {n: minutes(steps[n]["begin"], steps[n]["end"]) for n in nums}
    out = {}
    for i, n in enumerate(nums):
        prior = [dur[m] for m in nums[max(0, i - th["window"]):i]]
        if len(prior) >= th["min_steps"]:
            usual = statistics.median(prior)
            if (dur[n] >= th["overrun_floor_minutes"]
                    and dur[n] > th["overrun_factor"] * max(usual, 1)):
                out[n] = (dur[n], usual)
    return out


def has(step, name, value=None):
    return any(n == name and (value is None or v == value) for n, v in step["tags"])


def flag(metric, step, ctx):
    name, _, key = metric.partition(":")
    if name == "progress":
        return has(step, "progress")
    if name == "rework":
        return has(step, "redo") or has(step, "fail")
    if name == "workflow":
        return has(step, "workflow") and not has(step, "progress")
    if name == "overrun":
        return has(step, "overrun") or step["n"] in ctx["long"]
    if name == "escaped":
        return has(step, "escaped")
    return has(step, name, key)


def metric_value(ctx, metric, step_list):
    if metric.split(":")[0] in NOT_PER_STEP:
        return None
    if metric == "questions":
        return float(len(ctx["questions"]["open"]))
    if not step_list:
        return None
    return sum(flag(metric, s, ctx) for s in step_list) / len(step_list)


def before_text(ctx, metric):
    if metric.split(":")[0] in NOT_PER_STEP:
        return "0 (not measured per step)"
    if metric == "questions":
        return "{} open questions".format(len(ctx["questions"]["open"]))
    window = [ctx["steps"][n] for n in ctx["nums"] if n <= ctx["cur"]][-ctx["th"]["window"]:]
    if not window:
        return "0.00 (no steps yet)"
    k = sum(flag(metric, s, ctx) for s in window)
    return "{:.2f} ({} of the last {} steps)".format(k / len(window), k, len(window))


def handled(ctx, metric):
    """The last step where this warning was dealt with: a change measuring it, or [noted:...]."""
    h = 0
    for e in ctx["evo"]:
        if e["measure"] == metric and e["step"]:
            h = max(h, e["step"])
    for s in ctx["steps"].values():
        if ("noted", metric) in s["tags"]:
            h = max(h, s["n"])
    return h


def rule_start(ctx, rid):
    """The last step where a change named this rule (0: it dates from the setup)."""
    pat = re.compile(r"\b" + re.escape(rid) + r"\b")
    return max([e["step"] for e in ctx["evo"] if e["step"] and pat.search(e["change"])] or [0])


def warnings(ctx):
    th, steps, nums, cur = ctx["th"], ctx["steps"], ctx["nums"], ctx["cur"]
    out = []

    def since(metric, size=None):
        h = handled(ctx, metric)
        sl = [steps[n] for n in nums if n > h]
        return sl[-size:] if size else sl

    def names(sl):
        return ", ".join(step_name(s["n"]) for s in sl)

    def warn(wid, text, fix):
        out.append({"id": wid, "text": text, "fix": fix})

    w = since("progress", th["window"])
    if len(w) >= th["min_steps"]:
        k = sum(flag("progress", s, ctx) for s in w)
        if k < th["progress_min"] * len(w):
            warn("progress", "little progress: {} of the last {} steps moved the end "
                 "product".format(k, len(w)), "re-plan the next actions, or cut process")
    w = since("rework", th["window"])
    hits = [s for s in w if flag("rework", s, ctx)]
    if len(hits) >= th["rework_warn_at"]:
        warn("rework", "much rework: {} of the last {} steps were a redo or a failure "
             "({})".format(len(hits), len(w), names(hits)),
             "clearer actions in NEXT.md, or a check before work counts as done")
    w = since("workflow", th["workflow_window"])
    hits = [s for s in w if flag("workflow", s, ctx)]
    if len(hits) >= th["workflow_warn_at"]:
        warn("workflow", "process is eating the work: {} of the last {} steps were only about "
             "the workflow ({})".format(len(hits), len(w), names(hits)),
             "cut process, so the next steps move the end product")
    for name, at, kind, fix in (
            ("correction", th["correction_warn_at"], "correction",
             "a rule for the AI (small); but if it is about the goal, a limit or a decision, "
             "ask the user"),
            ("repeat", th["repeat_warn_at"], "instruction",
             "a shortcut command or a rule for the AI (small)")):
        for key in sorted({v for s in steps.values() for n, v in s["tags"] if n == name}):
            metric = name + ":" + key
            hits = [s for s in since(metric) if has(s, name, key)]
            if len(hits) >= at:
                warn(metric, "the same {} {} times: {} ({})".format(
                    kind, len(hits), key, names(hits)), fix)
    hits = [s for s in since("escaped") if has(s, "escaped")]
    if hits:
        where = sorted({v for s in hits for n, v in s["tags"] if n == "escaped"})
        warn("escaped", "an error got past a check: {} ({})".format(
            ", ".join(where), names(hits)),
            "tighten the check that missed it, or propose a second opinion on that part "
            "(switching an add-on on is a big fix)")
    hits = [s for s in since("overrun", th["window"]) if flag("overrun", s, ctx)]
    if hits:
        details = []
        for s in hits:
            if s["n"] in ctx["long"]:
                d, usual = ctx["long"][s["n"]]
                details.append("{} took {:.0f} min (usual {:.0f})".format(
                    step_name(s["n"]), d, usual))
            else:
                details.append(step_name(s["n"]) + " was marked [overrun]")
        warn("overrun", "a step took far longer than usual: " + "; ".join(details),
             "split big actions into smaller steps")
    hq = handled(ctx, "questions")
    if not hq or cur - hq >= th["window"]:
        qs = ctx["questions"]["open"]
        old = [q for q in qs if q["date"] and
               sum(1 for d in ctx["dates"] if d > q["date"]) > th["question_age_days"]]
        found = []
        if len(qs) > th["questions_max"]:
            found.append("{} open questions".format(len(qs)))
        if old:
            found.append("open for more than {} working days: {}".format(
                th["question_age_days"], ", ".join(q["id"] for q in old)))
        if found:
            warn("questions", "questions are waiting: " + "; ".join(found),
                 "ask them together in one batch, or drop the ones that no longer matter")
    span = th["silent_rule_steps"]
    for r in ctx["rules"]:
        if r["paused"] or r["core"]:
            continue
        start = max(rule_start(ctx, r["id"]), handled(ctx, "silent:" + r["id"]))
        if cur - start >= span and not any(has(steps[n], "rule", r["id"])
                                           for n in nums if n > cur - span):
            warn("silent:" + r["id"], "rule {} has not mattered in {} steps".format(
                r["id"], span), "pause it (small) or merge it into another rule")
    state = ctx["state"]
    addons = state.get("addons") if isinstance(state.get("addons"), dict) else {}
    span = th["unused_addon_steps"]
    for name in sorted(n for n in addons if n in ADDONS and addon_on(state, n)):
        since = addons[name].get("since") if isinstance(addons[name].get("since"), int) else 0
        start = max(since, handled(ctx, "unused:" + name))
        if cur - start >= span and not any(has(steps[n], "used", name)
                                           for n in nums if n > cur - span):
            warn("unused:" + name, "add-on {} has not been used in {} steps".format(name, span),
                 "switch it off (a small fix)" if ADDONS[name] == "ai" else
                 "ask the user whether to switch it off (theirs to decide)")
    b = budget_limits(state) if addon_on(state, "budget") else None
    hb = handled(ctx, "budget")
    if b and ctx["spent"] >= th["budget_warn_share"] * b["cap"] and (
            not hb or cur - hb >= th["window"]):
        warn("budget", "{:.2f} of {:.2f} {} spent ({:.0f}% of the cap)".format(
            ctx["spent"], b["cap"], b["currency"], 100 * ctx["spent"] / b["cap"]),
            "tell the user and plan the rest of the spending; raising the cap is theirs to "
            "decide")
    if addon_on(state, "second-opinion"):
        hq = handled(ctx, "second-opinion-quiet")
        streak = 0
        for o in reversed(ctx["opinions"]):
            if o["verdict"] != "pass" or not o["step"].startswith("S-") or (
                    int(o["step"][2:]) <= hq):
                break
            streak += 1
        if streak >= th["quiet_opinions"]:
            warn("second-opinion-quiet", "the last {} second opinions all passed".format(streak),
                 "use it on fewer parts or less often (the user's to decide)")
    return out


def rechecks(ctx):
    """Fixes being tested whose re-check step has come, with the before/after numbers."""
    out = []
    for e in ctx["evo"]:
        if e["status"] != "testing" or e["check_at"] is None or ctx["cur"] < e["check_at"]:
            continue
        m = e["measure"]
        after = metric_value(ctx, m, [ctx["steps"][n] for n in ctx["nums"]
                                      if e["step"] < n <= ctx["cur"]])
        before = e["before"]
        if after is None or before is None or (m not in HIGHER_IS_BETTER and
                                               before == 0 and after == 0):
            verdict, todo = "unclear", "nothing to compare: keep it; the next progress review looks at it"
        elif (after > before) if m in HIGHER_IS_BETTER else (after < before):
            verdict, todo = "helped", "keep it"
        elif e["by"] == "ai":
            verdict, todo = "not helped", "undo it (the AI made it) and report"
        else:
            verdict, todo = "not helped", "propose to the user to undo it"
        fmt = "{:.0f}" if m == "questions" else "{:.2f}"
        text = "{} ({}): {} before, {} since -> {}: {}".format(
            e["id"], m, fmt.format(before) if before is not None else "?",
            fmt.format(after) if after is not None else "?", verdict, todo)
        out.append({"id": e["id"], "measure": m, "before": before, "after": after,
                    "verdict": verdict, "text": text})
    return out


def review_due(ctx):
    """Return (due, reason, steps since the last progress review, interval)."""
    state = ctx["state"]
    last = max([n for n, s in ctx["steps"].items() if has(s, "review")] or [0])
    every = state.get("review_every", 10)
    every = every if isinstance(every, int) and every > 0 else 10
    since = ctx["cur"] - last
    if state.get("review_phase") and state.get("phase") != state.get("review_phase"):
        return True, "phase '{}' ended".format(state.get("review_phase")), since, every
    if since >= every:
        return True, "{} steps since the last one".format(since), since, every
    return False, "", since, every


def due_items(ctx):
    items = []
    due, reason, _, _ = review_due(ctx)
    if due:
        items.append("progress review ({}): tools/progress-review.md".format(reason))
    for c in rechecks(ctx):
        items.append("re-check of " + c["id"])
    for e in ctx["evo"]:
        if e["status"] == "proposed":
            items.append("{} waits for the user's answer".format(e["id"]))
    return items


# ---------- commands ----------

def status_lines(root):
    state = load_state(root)
    entries, _ = parse_log(root)
    actor, action, _ = read_next(root)
    q = parse_questions(root)
    problems = check(root)
    step = current_step_id(state)
    step = "practice round" if step == "P" else ("no steps yet" if step == "-" else step)
    last = "none"
    if entries:
        e = entries[-1]
        tags = " ".join("[{}]".format(n + (":" + v if v else "")) for n, v in e["tags"])
        last = '{} {} "{}" {}'.format(e["time"], e["actor"], e["what"], tags).strip()
    lines = [
        "{} | {} | phase: {} | last event: {}".format(state.get("project", "?"), step,
                                                      state.get("phase", "?"), last),
        "Next ({}): {}".format(actor or "?", action or "(NEXT.md needs fixing)"),
        "Questions: {} open, {} saved for later | check: {}".format(
            len(q["open"]), q["later"], "OK" if not problems else
            "{} problem(s), run: wf.py check".format(len(problems))),
    ]
    summary = addons_summary(root, state)
    if summary:
        lines.append("Add-ons: " + summary)
    if not state.get("practice"):
        due = due_items(analyse(root))
        if due:
            lines.append("Due: " + "; ".join(due))
    return lines


def cmd_begin(root, argv):
    state = load_state(root)
    if "--practice" in argv:
        if state.get("practice"):
            raise WfError("the practice round has already begun")
        state["practice"] = True
        save_state(root, state)
        add_log(root, state, "AI", "practice step begins", tags=["begin"])
    else:
        if state.get("practice"):
            raise WfError("the practice round is still on; run practice-done first")
        state["step"] = int(state.get("step", 0)) + 1
        save_state(root, state)
        add_log(root, state, "AI", "step begins", tags=["begin"])
    save_guard(root, state)
    print("\n".join(status_lines(root)))


def cmd_log(root, argv):
    part, tags, rest = "-", [], []
    i = 0
    while i < len(argv):
        if argv[i] in ("--part", "--tags"):
            if i + 1 >= len(argv):
                raise WfError(argv[i] + " needs a value")
            if argv[i] == "--part":
                part = argv[i + 1]
            else:
                tags += argv[i + 1].replace(",", " ").split()
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    if len(rest) < 2:
        raise WfError('usage: wf.py log ACTOR "what happened" [--part PART] [--tags "t1 t2"]')
    line = add_log(root, load_state(root), rest[0], " ".join(rest[1:]), part, tags)
    print(line)


def cmd_check(root, argv):
    problems = check(root)
    if problems:
        print("check: {} problem(s)".format(len(problems)))
        for p in problems:
            print("- " + p)
        return 1
    entries, _ = parse_log(root)
    print("check: OK ({} log lines)".format(len(entries)))
    return 0


def cmd_health(root, argv):
    problems = check(root)
    ctx = analyse(root)
    ws, cbs = warnings(ctx), rechecks(ctx)
    due, reason, since, every = review_due(ctx)
    waiting = [e for e in ctx["evo"] if e["status"] == "proposed"]
    if "--json" in argv:
        print(json.dumps({"problems": problems, "step": ctx["cur"], "warnings": ws,
                          "rechecks": cbs, "review_due": due,
                          "waiting": [e["id"] for e in waiting]}, indent=2))
        return 1 if problems else 0
    lines = []
    if problems:
        lines.append("check: {} problem(s)".format(len(problems)))
        lines += ["- " + p for p in problems]
    window = [ctx["steps"][n] for n in ctx["nums"]][-ctx["th"]["window"]:]
    progress = ("progress: {} of the last {} steps".format(
        sum(flag("progress", s, ctx) for s in window), len(window)) if window
        else "no steps yet")
    lines.append("Health: {} | {} | progress review {}".format(
        "OK" if not ws else "{} warning(s)".format(len(ws)), progress,
        "due" if due else "in {} steps".format(every - since)))
    for w in ws:
        lines.append("- warning [{}] {} -> likely fix: {}".format(w["id"], w["text"], w["fix"]))
    for c in cbs:
        lines.append("- re-check " + c["text"])
    if due:
        lines.append("- progress review due ({}): it is the next step's action -> "
                     "tools/progress-review.md".format(reason))
    for e in waiting:
        lines.append("- waiting for the user: {} ({}): {}".format(e["id"], e["size"],
                                                                  e["change"]))
    if ws or cbs:
        lines.append("What to do: tools/fixes.md")
    print("\n".join(lines))
    return 1 if problems else 0


FIX_USAGE = ('usage: wf.py fix add "what changes" --size small|big|yours '
             '--by ai|you|proposed --measure M --evidence "..." --undo "..." '
             '[--expect "..."]\n       wf.py fix mark F-N STATUS "note"')


def append_block(path, block):
    text = read_raw(path) if path.exists() else ""
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = [l for l in text.splitlines() if l.strip() != "No fixes yet."]
    while lines and not lines[-1].strip():
        lines.pop()
    write(path, nl.join(lines + [""] + block) + nl)


def cmd_fix_add(root, argv):
    opts, rest = take_opts(argv, ("--size", "--by", "--measure", "--evidence", "--undo",
                                  "--expect"))
    what = one_line(" ".join(rest))
    missing = [o for o in ("--size", "--by", "--measure", "--evidence", "--undo")
               if not opts.get(o, "").strip()]
    if not what or missing:
        raise WfError(FIX_USAGE + ("\nmissing: " + ", ".join(missing) if missing else ""))
    size, by, measure = opts["--size"], opts["--by"], opts["--measure"]
    if size not in SIZES:
        raise WfError("--size must be small, big or yours")
    if by not in APPLIERS:
        raise WfError("--by must be ai, you or proposed")
    if not MEASURE_RE.match(measure):
        raise WfError("--measure must be one of: progress, rework, workflow, overrun, escaped, "
                      "questions, correction:<key>, repeat:<key>")
    ctx = analyse(root)
    state, level = ctx["state"], ctx["state"].get("fix_level")
    if by == "ai":
        if size == "yours":
            raise WfError("this fix is the user's to decide, never the AI's: ask the user "
                          "(--by proposed)")
        if level == 1:
            raise WfError("fix level 1: every fix is proposed (--by proposed)")
        if size == "big" and level != 3:
            raise WfError("fix level {}: a big fix is proposed, not made by the AI "
                          "(--by proposed)".format(level))
    nid = len(ctx["evo"]) + 1
    for k in ("--evidence", "--undo", "--expect"):
        if opts.get(k):
            opts[k] = opts[k].replace("F-<n>", "F-{}".format(nid))
    what = what.replace("F-<n>", "F-{}".format(nid))
    proposed = by == "proposed"
    applied = {"ai": "AI (level {})".format(level), "you": "you",
               "proposed": "proposed (waiting for the user)"}[by]
    block = ["## F-{} | {}".format(nid, "proposed" if proposed else "testing"),
             "- Step: {} ({})".format(step_name(ctx["cur"]), now()),
             "- Evidence: " + one_line(opts["--evidence"]),
             "- Change: " + what,
             "- Size: " + size,
             "- Made by: " + applied,
             "- Expect: " + one_line(opts.get("--expect") or "-"),
             "- Measure: " + measure,
             "- Before: " + ("-" if proposed else before_text(ctx, measure)),
             "- Re-check at: " + ("-" if proposed else step_name(
                 ctx["cur"] + int(state.get("recheck_after", 5)))),
             "- Undo: " + one_line(opts["--undo"]),
             "- Outcome: -"]
    append_block(root / "WORKFLOW-FIXES.md", block)
    add_log(root, state, "AI", "{} workflow fix F-{} ({}): {}".format(
        "proposed" if proposed else "made", nid, size, what), tags=["workflow"])
    print("\n".join(block))


def cmd_fix_mark(root, argv):
    if len(argv) < 3:
        raise WfError(FIX_USAGE)
    eid, new, note = argv[0], argv[1], one_line(" ".join(argv[2:]))
    ctx = analyse(root)
    entry = next((e for e in ctx["evo"] if e["id"] == eid), None)
    if not entry:
        raise WfError("no fix {} in WORKFLOW-FIXES.md".format(eid))
    allowed = TRANSITIONS.get(entry["status"], set())
    if new not in allowed:
        raise WfError("{} is {}; it can move to: {}".format(
            eid, entry["status"], ", ".join(sorted(allowed)) or "nothing (it is closed)"))
    if not note:
        raise WfError("add a short note: why (for rejected: the user's words)")
    if new == "testing":
        updates = {"Made by": "you (approved)", "Before": before_text(ctx, entry["measure"]),
                   "Re-check at": step_name(ctx["cur"] + int(ctx["state"].get("recheck_after", 5)))}
    else:
        updates = {"Outcome": "{} at {} ({}): {}".format(new, step_name(ctx["cur"]),
                                                         now()[:10], note)}
    p = root / "WORKFLOW-FIXES.md"
    text = read_raw(p)
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines)
                 if EVO_HEAD.match(l) and EVO_HEAD.match(l).group(1) == eid)
    lines[start] = "## {} | {}".format(eid, new)
    last_field = start
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            break
        m = FIELD_RE.match(lines[i])
        if m:
            last_field = i
            if m.group(1) in updates:
                lines[i] = "- {}: {}".format(m.group(1), updates.pop(m.group(1)))
    for k, v in updates.items():
        last_field += 1
        lines.insert(last_field, "- {}: {}".format(k, v))
    write(p, nl.join(lines) + nl)
    add_log(root, ctx["state"], "AI", "workflow fix {} is now {}: {}".format(eid, new, note),
            tags=["workflow"])
    print("{} is now {}".format(eid, new))


def cmd_fix(root, argv):
    if argv and argv[0] == "add":
        return cmd_fix_add(root, argv[1:])
    if argv and argv[0] == "mark":
        return cmd_fix_mark(root, argv[1:])
    raise WfError(FIX_USAGE)


def require_user_answer(root, state, why):
    entries, _ = parse_log(root)
    if not user_answered(entries, current_step_id(state)):
        raise WfError(why + ": ask the user, log their answer with [answered], then run this "
                      "again")


def cmd_addon(root, argv):
    usage = 'usage: wf.py addon on NAME [--parts P1,P2]  |  wf.py addon off NAME "why"'
    if len(argv) < 2 or argv[0] not in ("on", "off"):
        raise WfError(usage)
    action, name = argv[0], argv[1]
    if name not in ADDONS:
        raise WfError("unknown add-on '{}' (known: {})".format(name, ", ".join(ADDONS)))
    state = load_state(root)
    addons = state.get("addons") if isinstance(state.get("addons"), dict) else {}
    if action == "off":
        note = one_line(" ".join(argv[2:]))
        if not note:
            raise WfError(usage)
        if not addon_on(state, name):
            raise WfError("add-on {} is not on".format(name))
        if ADDONS[name] == "user":
            require_user_answer(root, state, "only the user may switch off " + name)
        addons[name]["on"] = False
        state["addons"] = addons
        save_state(root, state)
        add_log(root, state, "AI", "add-on {} switched off: {}".format(name, note),
                tags=["workflow"])
        print("add-on {} is off; its files are kept".format(name))
        return
    opts, _ = take_opts(argv[2:], ("--parts",))
    if addon_on(state, name):
        raise WfError("add-on {} is already on".format(name))
    entry = {"on": True, "since": state.get("step", 0)}
    if name == "budget":
        if budget_limits(state) is None:
            raise WfError('first put the user\'s answer in STATE.json "limits", like "budget": '
                          '{"cap": 30, "currency": "USD", "ask_over": 5}')
        if not (root / SPENDING_FILE).exists():
            write(root / SPENDING_FILE, SPENDING_HEADER)
    elif name == "second-opinion":
        listed = (opts.get("--parts") or "").replace(",", " ").split()
        if not listed:
            raise WfError("--parts is needed: the parts that need a second opinion")
        bad = [x for x in listed if x not in state.get("parts", {})]
        if bad:
            raise WfError("not parts in STATE.json: " + ", ".join(bad))
        entry["parts"] = listed
        if not (root / OPINIONS_FILE).exists():
            write(root / OPINIONS_FILE, OPINIONS_HEADER)
    else:
        (root / EXPERIMENTS_DIR).mkdir(exist_ok=True)
    addons[name] = entry
    state["addons"] = addons
    if isinstance(state.get("addons_later"), list):
        state["addons_later"] = [x for x in state["addons_later"] if x != name]
    save_state(root, state)
    add_log(root, state, "AI", "add-on {} switched on".format(name), tags=["workflow"])
    print("add-on {} is on{}".format(name, "; now write tools/second-opinion.md (see "
                                           "tools/addons.md)" if name == "second-opinion"
                                     else ""))


def cmd_spend(root, argv):
    estimate = "--estimate" in argv
    rest = [a for a in argv if a != "--estimate"]
    if len(rest) < 2:
        raise WfError('usage: wf.py spend AMOUNT "what" [--estimate]')
    try:
        amount = float(rest[0])
    except ValueError:
        raise WfError("AMOUNT must be a number, like 0.50")
    what = one_line(" ".join(rest[1:]).replace("|", "/"))
    state = load_state(root)
    if not addon_on(state, "budget"):
        raise WfError("the budget add-on is not on (see tools/addons.md)")
    b = budget_limits(state)
    if b is None:
        raise WfError('STATE.json limits.budget is not set (see tools/addons.md)')
    spends, problems = parse_spending(root)
    if problems:
        raise WfError("; ".join(problems))
    total = sum(x["amount"] for x in spends) + amount
    if total > b["cap"] + 1e-9:
        raise WfError("over the cap: this would make {:.2f} of {:.2f} {}. Ask the user; only "
                      "they can raise the cap".format(total, b["cap"], b["currency"]))
    if total < -1e-9:
        raise WfError("the total would go below zero")
    if amount > b["ask_over"]:
        require_user_answer(root, state, "a single cost over {:.2f} {} needs the user's OK "
                            "first".format(b["ask_over"], b["currency"]))
    kind = "estimate" if estimate else "measured"
    append_line(root / SPENDING_FILE, "- {} | {} | {:.2f} | {} | {}".format(
        now(), current_step_id(state), amount, kind, what))
    add_log(root, state, "AI", "spent {:.2f} {} ({}): {}".format(amount, b["currency"], kind,
                                                                 what), tags=["used:budget"])
    print("recorded {:.2f}; total {:.2f} of {:.2f} {}".format(amount, total, b["cap"],
                                                              b["currency"]))


def cmd_opinion(root, argv):
    if len(argv) < 3 or argv[1] not in ("pass", "fail"):
        raise WfError('usage: wf.py opinion PART pass|fail "findings, short"')
    part, verdict = argv[0], argv[1]
    findings = one_line(" ".join(argv[2:]).replace("|", "/"))
    state = load_state(root)
    if not addon_on(state, "second-opinion"):
        raise WfError("the second-opinion add-on is not on (see tools/addons.md)")
    listed = state["addons"]["second-opinion"].get("parts") or []
    if part not in listed:
        raise WfError("part '{}' is not listed for a second opinion (listed: {})".format(
            part, ", ".join(listed)))
    opinions, problems = parse_opinions(root)
    if problems:
        raise WfError("; ".join(problems))
    sid = "SO-{}".format(len(opinions) + 1)
    append_line(root / OPINIONS_FILE, "- {} | {} | {} | {} | {} | {}".format(
        sid, now(), current_step_id(state), part, verdict, findings))
    add_log(root, state, "AI", "second opinion {} on {}: {}: {}".format(sid, part, verdict,
                                                                        findings),
            part=part, tags=["used:second-opinion"])
    print("{}: {} ({})".format(sid, verdict, part))


def cmd_experiment(root, argv):
    usage = 'usage: wf.py experiment new "title"  |  wf.py experiment start X-NNN'
    if not argv or argv[0] not in ("new", "start"):
        raise WfError(usage)
    state = load_state(root)
    if not addon_on(state, "experiment-plans"):
        raise WfError("the experiment-plans add-on is not on (see tools/addons.md)")
    if argv[0] == "new":
        title = one_line(" ".join(argv[1:]))
        if not title:
            raise WfError(usage)
        (root / EXPERIMENTS_DIR).mkdir(exist_ok=True)
        xid = "X-{:03d}".format(max([int(x[2:]) for x, _ in plans(root)] or [0]) + 1)
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "plan"
        p = root / EXPERIMENTS_DIR / "{}-{}.md".format(xid, slug)
        write(p, PLAN_TEMPLATE.format(xid=xid, title=title))
        add_log(root, state, "AI", "experiment plan {} created: {}".format(xid, title),
                tags=["used:experiment-plans"])
        print(p.relative_to(root).as_posix())
        return
    if len(argv) < 2:
        raise WfError(usage)
    xid = argv[1]
    found = [p for x, p in plans(root) if x == xid]
    if not found:
        raise WfError("no plan {} in experiments/".format(xid))
    s = plan_sections(read(found[0]))
    missing = [h for h in PLAN_SECTIONS if h not in s]
    if missing:
        raise WfError("{}: missing section(s): {}".format(found[0].name, ", ".join(missing)))
    for h in ("Question", "Setup", "What each result would mean"):
        if not filled(s[h]):
            raise WfError("{}: fill in '{}' before the start".format(found[0].name, h))
    if filled(s["Results"]):
        raise WfError("{}: results are already written; a plan is started before the run".format(
            found[0].name))
    locks = load_locks(root)
    if locks is None:
        raise WfError(LOCK_FILE + " is not valid JSON")
    if xid in locks:
        raise WfError("{} was already started".format(xid))
    locks[xid] = {"hash": meaning_hash(s), "step": current_step_id(state), "time": now()}
    (root / LOCK_FILE).parent.mkdir(exist_ok=True)
    write(root / LOCK_FILE, json.dumps(locks, indent=2) + "\n")
    add_log(root, state, "AI", "experiment {} started; 'What each result would mean' is "
                               "locked".format(xid), tags=["used:experiment-plans"])
    print("{} started; its 'What each result would mean' is locked".format(xid))


def cmd_practice_done(root, argv):
    state = load_state(root)
    if not state.get("practice"):
        raise WfError("no practice round is running")
    entries, _ = parse_log(root)
    practice = [e for e in entries if e["step"] == "P"]
    if not any(n == "begin" for e in practice for n, _ in e["tags"]):
        raise WfError("no practice step was begun (run begin --practice)")
    if not any(n == "progress" for e in practice for n, _ in e["tags"]):
        raise WfError("the practice step logged no [progress:practice] line; finish it first")
    drop = {e["line"] for e in practice}
    p = root / "LOG.md"
    text = read_raw(p)
    nl = "\r\n" if "\r\n" in text else "\n"
    kept = [l for n, l in enumerate(text.splitlines(), 1) if n not in drop]
    write(p, nl.join(kept) + nl)
    if (root / PRACTICE_FILE).exists():
        (root / PRACTICE_FILE).unlink()
    state["practice"] = False
    save_state(root, state)
    add_log(root, state, "AI", "practice round passed; practice lines and file removed",
            tags=["workflow"])
    return cmd_check(root, [])


COMMANDS = {"status": lambda r, a: print("\n".join(status_lines(r))), "begin": cmd_begin,
            "log": cmd_log, "check": cmd_check, "health": cmd_health, "fix": cmd_fix,
            "addon": cmd_addon, "spend": cmd_spend, "opinion": cmd_opinion,
            "experiment": cmd_experiment, "practice-done": cmd_practice_done}


def main(argv):
    argv = list(argv)
    try:
        root = find_root(argv)
        if not argv or argv[0] not in COMMANDS:
            print(__doc__.strip())
            return 0 if argv and argv[0] in ("-h", "--help", "help") else 2
        return COMMANDS[argv[0]](root, argv[1:]) or 0
    except WfError as e:
        print("wf.py: " + str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    sys.exit(main(sys.argv[1:]))
