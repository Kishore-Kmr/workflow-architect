#!/usr/bin/env python3
"""Workflow tool for a project set up by workflow-architect (v0.2).

Commands (run from anywhere; the project is the folder above tools/, or pass --root DIR):
  status               three-line status, plus a "Due:" line when something is due (read-only)
  begin [--practice]   start a step: number it, log it, print the status
  log ACTOR WHAT [--part PART] [--tags "t1 t2"]
                       append one event line to LOG.md (tags are checked)
  check                mechanical checks of the workflow files (read-only)
  health [--json]      the check, then the workflow's health from LOG.md: warnings,
                       check-backs of changes on trial, look-back due, proposals waiting
                       (read-only)
  change add WHAT --size small|large|protected --by auto|you|proposed --measure M
             --evidence TEXT --undo TEXT [--expect TEXT]
                       record a workflow change in EVOLUTION.md and LOG.md; refused when the
                       evolution level does not allow applying it automatically
  change mark E-N STATUS NOTE
                       move a change on: proposed -> trial (the user approved) or rejected;
                       trial -> kept or undone; kept -> undone
  practice-done        end the practice round: remove its log lines and files, record it passed

Measures (M): progress, rework, workflow, overrun, escaped, questions, correction:<key>,
repeat:<key>. Warning ids are the same, plus silent:R-<n>.
Only the Python standard library is used.
"""
import hashlib
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

VERSION = "0.2"
CORE_FILES = ["BRIEF.md", "NEXT.md", "STATE.json", "LOG.md", "DECISIONS.md", "QUESTIONS.md",
              "RULES.md", "EVOLUTION.md", "tools/step.md", "tools/evolve.md",
              "tools/lookback.md"]
MAX_INSTRUCTION_LINES = 80
MAX_RULES = 12
PRACTICE_PART = "practice"
PRACTICE_FILE = ".workflow-architect/practice.md"
GUARD_FILE = ".workflow-architect/guard.json"
GUARDED_FILES = ["BRIEF.md", "DECISIONS.md"]       # the user's: goal, limits, notes, decisions
GUARDED_STATE = ["evolution_level", "limits"]
# tag name -> does it need a value (tag:value)?
TAGS = {"progress": True, "workflow": False, "fail": False, "redo": False, "correction": True,
        "repeat": True, "asked": False, "answered": False, "escaped": True, "used": True,
        "overrun": False, "rule": True, "begin": False, "lookback": False, "noted": True}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MEASURE_RE = re.compile(r"^(progress|rework|workflow|overrun|escaped|questions|"
                        r"(correction|repeat):[a-z0-9][a-z0-9-]*)$")
WARNING_RE = re.compile(r"^(progress|rework|workflow|overrun|escaped|questions|"
                        r"(correction|repeat):[a-z0-9][a-z0-9-]*|silent:R-\d+)$")
HIGHER_IS_BETTER = {"progress"}
TIME_FMT = "%Y-%m-%d %H:%M"
ENTRY_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (S-\d{3,}|P|-) \| "
                      r"([A-Za-z][\w-]*) \| (.+?) \| (\S+) \|(.*)$")
TAG_RE = re.compile(r"\[([a-z]+)(?::([^\]\s]+))?\]")
RULE_HEAD = re.compile(r"^## (R-\d+)\b[ \t]*(.*)$", re.M)
EVO_HEAD = re.compile(r"^## (E-\d+)[ \t]*\|[ \t]*(\S+)[ \t]*$")
FIELD_RE = re.compile(r"^- ([A-Z][A-Za-z ]*?): ?(.*)$")
EVO_FIELDS = ["Step", "Evidence", "Change", "Size", "Applied by", "Expect", "Measure", "Before",
              "Check at", "Undo", "Outcome"]
STATUSES = {"proposed", "trial", "kept", "undone", "rejected"}
SIZES = {"small", "large", "protected"}
APPLIERS = {"auto", "you", "proposed"}
TRANSITIONS = {"proposed": {"trial", "rejected"}, "trial": {"kept", "undone"},
               "kept": {"undone"}}
STATE_SCHEMA = {  # key -> allowed types (all required)
    "workflow_architect": (str,), "project": (str,), "phase": (str,), "step": (int,),
    "practice": (bool,), "brief_version": (int,), "structure_version": (int,),
    "autonomy": (str,), "evolution_level": (int,), "lookback_every": (int,),
    "lookback_phase": (str,), "check_after": (int,), "tools": (list,), "instruction_files": (list,),
    "python": (str, type(None)), "git": (str,), "parts": (dict,), "modules": (list,),
    "needed_later": (list,), "limits": (dict,),
}
CHOICES = {"autonomy": {"one-step", "until-you"}, "evolution_level": {1, 2, 3},
           "git": {"each-step", "manual", "none"}}
# Starting values; STATE.json "thresholds" may override them (a large change, see evolve.md).
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
    if problems:
        raise WfError("; ".join(problems))
    tagtext = " ".join("[{}]".format(n + (":" + v if v else "")) for n, v in parsed)
    line = "- {} | {} | {} | {} | {} |{}".format(now(), current_step_id(state), actor, what,
                                                 part, " " + tagtext if tagtext else "")
    append_line(root / "LOG.md", line)
    if ("lookback", None) in parsed and not practice:
        state["lookback_phase"] = state.get("phase")   # the next phase change makes one due
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
    actor = actors[0].strip() if len(actors) == 1 else None
    action = actions[0].strip() if len(actions) == 1 else None
    return actor, action, problems


# ---------- evolution records ----------

def _num(pattern, text):
    m = re.search(pattern, text or "")
    return int(m.group(1)) if m else None


def parse_evolution(root):
    """Return (entries, problems) for the E-<n> changes in EVOLUTION.md."""
    p = root / "EVOLUTION.md"
    if not p.exists():
        return [], ["EVOLUTION.md is missing"]
    entries, problems, cur = [], [], None
    for n, line in enumerate(read(p).splitlines(), 1):
        if line.startswith("## "):
            cur = None
            m = EVO_HEAD.match(line)
            if m:
                cur = {"id": m.group(1), "status": m.group(2), "line": n, "fields": {}}
                entries.append(cur)
            elif line.startswith("## E-"):
                problems.append("EVOLUTION.md line {}: a change heading must look like "
                                "'## E-1 | trial'".format(n))
        elif cur is not None:
            m = FIELD_RE.match(line)
            if m:
                cur["fields"][m.group(1)] = m.group(2).strip()
    for e in entries:
        f = e["fields"]
        applied = f.get("Applied by", "")
        before = re.match(r"^(\d+(?:\.\d+)?)", f.get("Before", ""))
        e.update({"step": _num(r"S-(\d+)", f.get("Step")),
                  "check_at": _num(r"S-(\d+)", f.get("Check at")),
                  "size": f.get("Size", ""), "by": applied.split()[0] if applied else "",
                  "level": _num(r"level (\d)", applied), "measure": f.get("Measure", ""),
                  "before": float(before.group(1)) if before else None,
                  "change": f.get("Change", "")})
    return entries, problems


def evolution_problems(entries, state):
    out = []
    cur = state.get("step") if isinstance(state.get("step"), int) else 0
    if [e["id"] for e in entries] != ["E-{}".format(i) for i in range(1, len(entries) + 1)]:
        out.append("EVOLUTION.md: change ids must run E-1, E-2, ... in order")
    for e in entries:
        w = "EVOLUTION.md " + e["id"]
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
            out.append(w + ": 'Applied by' must start with auto, you or proposed")
        if not MEASURE_RE.match(e["measure"]):
            out.append(w + ": 'Measure' must be one of the measures in tools/wf.py")
        waiting = e["status"] in ("proposed", "rejected")
        if waiting != (e["by"] == "proposed"):
            out.append(w + ": 'Applied by: proposed' goes with status proposed or rejected, "
                           "and only with those")
        if not waiting and (e["check_at"] is None or e["before"] is None):
            out.append(w + ": a change in use needs 'Before' (a number) and 'Check at' (a step)")
        if e["by"] == "auto":
            if e["level"] is None:
                out.append(w + ": 'Applied by: auto' must say the level, like 'auto (level 2)'")
            elif e["size"] == "protected":
                out.append(w + ": a protected change is never applied automatically")
            elif e["level"] == 1:
                out.append(w + ": at evolution level 1 every change is proposed")
            elif e["size"] == "large" and e["level"] < 3:
                out.append(w + ": at evolution level 2 a large change is proposed, not applied")
        closed = e["status"] in ("kept", "undone", "rejected")
        if closed == (f["Outcome"] in ("", "-")):
            out.append(w + ": 'Outcome' is filled in when, and only when, the change is kept, "
                           "undone or rejected")
    return out


# ---------- the guard: the user's files change only with the user ----------

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
    if not changed:
        return []
    if any(e["step"] == step and (e["actor"] == "YOU" or ("answered", None) in e["tags"])
           for e in entries):
        return []
    return ["{} changed in step {}, but no answer from the user is logged in this step. These "
            "are the user's to change: undo it, or ask and log their answer with "
            "[answered]".format(", ".join(changed), step)]


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
        elif key in ("lookback_every", "check_after") and state[key] < 1:
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
    evo, evo_problems = parse_evolution(root)
    # log lines may name a rule that a later change removed, if EVOLUTION.md records it
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
    problems += evo_problems + evolution_problems(evo, state)
    problems += guard_problems(root, state, entries)
    return problems


# ---------- health ----------

def analyse(root):
    """Everything the health metrics need, read once."""
    state = load_state(root)
    entries, _ = parse_log(root)
    evo, _ = parse_evolution(root)
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
           "questions": parse_questions(root), "rules": parse_rules(root)}
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
    if metric == "questions":
        return float(len(ctx["questions"]["open"]))
    if not step_list:
        return None
    return sum(flag(metric, s, ctx) for s in step_list) / len(step_list)


def before_text(ctx, metric):
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
            ", ".join(where), names(hits)), "tighten the check that missed it")
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
    return out


def checkbacks(ctx):
    """Changes on trial whose check-back step has come, with the before/after numbers."""
    out = []
    for e in ctx["evo"]:
        if e["status"] != "trial" or e["check_at"] is None or ctx["cur"] < e["check_at"]:
            continue
        m = e["measure"]
        after = metric_value(ctx, m, [ctx["steps"][n] for n in ctx["nums"]
                                      if e["step"] < n <= ctx["cur"]])
        before = e["before"]
        if after is None or before is None or (m not in HIGHER_IS_BETTER and
                                               before == 0 and after == 0):
            verdict, todo = "unclear", "nothing to compare: keep it; the next look-back reviews it"
        elif (after > before) if m in HIGHER_IS_BETTER else (after < before):
            verdict, todo = "helped", "keep it"
        elif e["by"] == "auto":
            verdict, todo = "not helped", "undo it (it was applied automatically) and report"
        else:
            verdict, todo = "not helped", "propose to the user to undo it"
        fmt = "{:.0f}" if m == "questions" else "{:.2f}"
        text = "{} ({}): {} before, {} since -> {}: {}".format(
            e["id"], m, fmt.format(before) if before is not None else "?",
            fmt.format(after) if after is not None else "?", verdict, todo)
        out.append({"id": e["id"], "measure": m, "before": before, "after": after,
                    "verdict": verdict, "text": text})
    return out


def lookback_due(ctx):
    """Return (due, reason, steps since the last look-back, interval)."""
    state = ctx["state"]
    last = max([n for n, s in ctx["steps"].items() if has(s, "lookback")] or [0])
    every = state.get("lookback_every", 10)
    every = every if isinstance(every, int) and every > 0 else 10
    since = ctx["cur"] - last
    if state.get("lookback_phase") and state.get("phase") != state.get("lookback_phase"):
        return True, "phase '{}' ended".format(state.get("lookback_phase")), since, every
    if since >= every:
        return True, "{} steps since the last one".format(since), since, every
    return False, "", since, every


def due_items(ctx):
    items = []
    due, reason, _, _ = lookback_due(ctx)
    if due:
        items.append("look-back ({}): tools/lookback.md".format(reason))
    for c in checkbacks(ctx):
        items.append("check-back of " + c["id"])
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
    ws, cbs = warnings(ctx), checkbacks(ctx)
    due, reason, since, every = lookback_due(ctx)
    waiting = [e for e in ctx["evo"] if e["status"] == "proposed"]
    if "--json" in argv:
        print(json.dumps({"problems": problems, "step": ctx["cur"], "warnings": ws,
                          "checkbacks": cbs, "lookback_due": due,
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
    lines.append("Health: {} | {} | look-back {}".format(
        "OK" if not ws else "{} warning(s)".format(len(ws)), progress,
        "due" if due else "in {} steps".format(every - since)))
    for w in ws:
        lines.append("- warning [{}] {} -> likely fix: {}".format(w["id"], w["text"], w["fix"]))
    for c in cbs:
        lines.append("- check-back " + c["text"])
    if due:
        lines.append("- look-back due ({}): it is the next step's action -> "
                     "tools/lookback.md".format(reason))
    for e in waiting:
        lines.append("- waiting for the user: {} ({}): {}".format(e["id"], e["size"],
                                                                  e["change"]))
    if ws or cbs:
        lines.append("What to do: tools/evolve.md")
    print("\n".join(lines))
    return 1 if problems else 0


CHANGE_USAGE = ('usage: wf.py change add "what changed" --size small|large|protected '
                '--by auto|you|proposed --measure M --evidence "..." --undo "..." '
                '[--expect "..."]\n       wf.py change mark E-N STATUS "note"')


def append_block(path, block):
    text = read_raw(path) if path.exists() else ""
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = [l for l in text.splitlines() if l.strip() != "No changes yet."]
    while lines and not lines[-1].strip():
        lines.pop()
    write(path, nl.join(lines + [""] + block) + nl)


def cmd_change_add(root, argv):
    opts, rest = take_opts(argv, ("--size", "--by", "--measure", "--evidence", "--undo",
                                  "--expect"))
    what = one_line(" ".join(rest))
    missing = [o for o in ("--size", "--by", "--measure", "--evidence", "--undo")
               if not opts.get(o, "").strip()]
    if not what or missing:
        raise WfError(CHANGE_USAGE + ("\nmissing: " + ", ".join(missing) if missing else ""))
    size, by, measure = opts["--size"], opts["--by"], opts["--measure"]
    if size not in SIZES:
        raise WfError("--size must be small, large or protected")
    if by not in APPLIERS:
        raise WfError("--by must be auto, you or proposed")
    if not MEASURE_RE.match(measure):
        raise WfError("--measure must be one of: progress, rework, workflow, overrun, escaped, "
                      "questions, correction:<key>, repeat:<key>")
    ctx = analyse(root)
    state, level = ctx["state"], ctx["state"].get("evolution_level")
    if by == "auto":
        if size == "protected":
            raise WfError("a protected change is never applied automatically: ask the user "
                          "(--by proposed)")
        if level == 1:
            raise WfError("evolution level 1: every change is proposed (--by proposed)")
        if size == "large" and level != 3:
            raise WfError("evolution level {}: a large change is proposed, not applied "
                          "(--by proposed)".format(level))
    nid = len(ctx["evo"]) + 1
    for k in ("--evidence", "--undo", "--expect"):
        if opts.get(k):
            opts[k] = opts[k].replace("E-<n>", "E-{}".format(nid))
    what = what.replace("E-<n>", "E-{}".format(nid))
    proposed = by == "proposed"
    applied = {"auto": "auto (level {})".format(level), "you": "you",
               "proposed": "proposed (waiting for the user)"}[by]
    block = ["## E-{} | {}".format(nid, "proposed" if proposed else "trial"),
             "- Step: {} ({})".format(step_name(ctx["cur"]), now()),
             "- Evidence: " + one_line(opts["--evidence"]),
             "- Change: " + what,
             "- Size: " + size,
             "- Applied by: " + applied,
             "- Expect: " + one_line(opts.get("--expect") or "-"),
             "- Measure: " + measure,
             "- Before: " + ("-" if proposed else before_text(ctx, measure)),
             "- Check at: " + ("-" if proposed else step_name(
                 ctx["cur"] + int(state.get("check_after", 5)))),
             "- Undo: " + one_line(opts["--undo"]),
             "- Outcome: -"]
    append_block(root / "EVOLUTION.md", block)
    add_log(root, state, "AI", "{} workflow change E-{} ({}): {}".format(
        "proposed" if proposed else "applied", nid, size, what), tags=["workflow"])
    print("\n".join(block))


def cmd_change_mark(root, argv):
    if len(argv) < 3:
        raise WfError(CHANGE_USAGE)
    eid, new, note = argv[0], argv[1], one_line(" ".join(argv[2:]))
    ctx = analyse(root)
    entry = next((e for e in ctx["evo"] if e["id"] == eid), None)
    if not entry:
        raise WfError("no change {} in EVOLUTION.md".format(eid))
    allowed = TRANSITIONS.get(entry["status"], set())
    if new not in allowed:
        raise WfError("{} is {}; it can move to: {}".format(
            eid, entry["status"], ", ".join(sorted(allowed)) or "nothing (it is closed)"))
    if not note:
        raise WfError("add a short note: why (for rejected: the user's words)")
    if new == "trial":
        updates = {"Applied by": "you (approved)", "Before": before_text(ctx, entry["measure"]),
                   "Check at": step_name(ctx["cur"] + int(ctx["state"].get("check_after", 5)))}
    else:
        updates = {"Outcome": "{} at {} ({}): {}".format(new, step_name(ctx["cur"]),
                                                         now()[:10], note)}
    p = root / "EVOLUTION.md"
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
    add_log(root, ctx["state"], "AI", "workflow change {} is now {}: {}".format(eid, new, note),
            tags=["workflow"])
    print("{} is now {}".format(eid, new))


def cmd_change(root, argv):
    if argv and argv[0] == "add":
        return cmd_change_add(root, argv[1:])
    if argv and argv[0] == "mark":
        return cmd_change_mark(root, argv[1:])
    raise WfError(CHANGE_USAGE)


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
            "log": cmd_log, "check": cmd_check, "health": cmd_health, "change": cmd_change,
            "practice-done": cmd_practice_done}


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
