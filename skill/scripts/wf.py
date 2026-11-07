#!/usr/bin/env python3
"""Workflow tool for a project set up by workflow-architect (v0.1).

Commands (run from anywhere; the project is the folder above tools/, or pass --root DIR):
  status                  three-line status (read-only)
  begin [--practice]      start a step: number it, log it, print the status
  log ACTOR WHAT [--part PART] [--tags "t1 t2"]
                          append one event line to LOG.md (tags are checked)
  check                   mechanical checks of the workflow files (read-only)
  practice-done           end the practice round: remove its log lines and files, record it passed

Only the Python standard library is used.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

VERSION = "0.1"
CORE_FILES = ["BRIEF.md", "NEXT.md", "STATE.json", "LOG.md", "DECISIONS.md", "QUESTIONS.md",
              "RULES.md", "EVOLUTION.md", "tools/step.md"]
MAX_INSTRUCTION_LINES = 80
MAX_RULES = 12
PRACTICE_PART = "practice"
PRACTICE_FILE = ".workflow-architect/practice.md"
# tag name -> does it need a value (tag:value)?
TAGS = {"progress": True, "workflow": False, "fail": False, "redo": False, "correction": True,
        "repeat": True, "asked": False, "answered": False, "escaped": True, "used": True,
        "overrun": False, "rule": True, "begin": False}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TIME_FMT = "%Y-%m-%d %H:%M"
ENTRY_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (S-\d{3,}|P|-) \| "
                      r"([A-Za-z][\w-]*) \| (.+?) \| (\S+) \|(.*)$")
TAG_RE = re.compile(r"\[([a-z]+)(?::([^\]\s]+))?\]")
STATE_SCHEMA = {  # key -> (allowed types, required)
    "workflow_architect": (str,), "project": (str,), "phase": (str,), "step": (int,),
    "practice": (bool,), "brief_version": (int,), "structure_version": (int,),
    "autonomy": (str,), "evolution_level": (int,), "tools": (list,),
    "instruction_files": (list,), "python": (str, type(None)), "git": (str,),
    "parts": (dict,), "modules": (list,), "needed_later": (list,), "limits": (dict,),
}
CHOICES = {"autonomy": {"one-step", "until-you"}, "evolution_level": {1, 2, 3},
           "git": {"each-step", "manual", "none"}}


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


def rule_ids(root):
    p = root / "RULES.md"
    return re.findall(r"^## (R-\d+)\b", read(p), re.M) if p.exists() else []


def current_step_id(state):
    if state.get("practice"):
        return "P"
    step = state.get("step", 0)
    return "S-{:03d}".format(step) if step > 0 else "-"


def add_log(root, state, actor, what, part="-", tags=()):
    if not re.match(r"^[A-Za-z][\w-]*$", actor):
        raise WfError("actor must be one word, like AI or YOU")
    what = " ".join(what.replace("|", "/").split())
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
    return line


# ---------- questions and next ----------

def question_counts(root):
    p = root / "QUESTIONS.md"
    counts = {"open": 0, "later": 0, "answered": 0}
    if not p.exists():
        return counts
    section = None
    for line in read(p).splitlines():
        h = line.strip().lower()
        if h.startswith("## "):
            section = ("open" if "open" in h else "later" if "just in time" in h
                       else "answered" if "answered" in h else None)
        elif line.startswith("- Q-") and section:
            counts[section] += 1
    return counts


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
    ids = rule_ids(root)
    if len(ids) > MAX_RULES:
        problems.append("RULES.md: {} rules, the cap is {} (merge or retire one)".format(
            len(ids), MAX_RULES))
    if len(ids) != len(set(ids)):
        problems.append("RULES.md: duplicate rule ids")
    if (root / "RULES.md").exists():
        blocks = re.split(r"^## R-\d+.*$", read(root / "RULES.md"), flags=re.M)[1:]
        for rid, block in zip(ids, blocks):
            if not re.search(r"^Origin:", block, re.M):
                problems.append("RULES.md: {} has no 'Origin:' line".format(rid))
    entries, log_problems = parse_log(root)
    problems += log_problems
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
        for msg in tag_problems(e["tags"], state, ids, is_practice):
            problems.append(where + ": " + msg)
        if e["part"] != "-" and e["part"] not in set(parts) | (
                {PRACTICE_PART} if is_practice else set()):
            problems.append(where + ": part '{}' is not in STATE.json".format(e["part"]))
    if not state.get("practice") and (root / PRACTICE_FILE).exists():
        problems.append(PRACTICE_FILE + " left over from the practice round")
    return problems


# ---------- commands ----------

def status_lines(root):
    state = load_state(root)
    entries, _ = parse_log(root)
    actor, action, _ = read_next(root)
    q = question_counts(root)
    problems = check(root)
    step = current_step_id(state)
    step = "practice round" if step == "P" else ("no steps yet" if step == "-" else step)
    last = "none"
    if entries:
        e = entries[-1]
        tags = " ".join("[{}]".format(n + (":" + v if v else "")) for n, v in e["tags"])
        last = '{} {} "{}" {}'.format(e["time"], e["actor"], e["what"], tags).strip()
    return [
        "{} | {} | phase: {} | last event: {}".format(state.get("project", "?"), step,
                                                      state.get("phase", "?"), last),
        "Next ({}): {}".format(actor or "?", action or "(NEXT.md needs fixing)"),
        "Questions: {} open, {} saved for later | check: {}".format(
            q["open"], q["later"], "OK" if not problems else
            "{} problem(s), run: wf.py check".format(len(problems))),
    ]


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
            "log": cmd_log, "check": cmd_check, "practice-done": cmd_practice_done}


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
