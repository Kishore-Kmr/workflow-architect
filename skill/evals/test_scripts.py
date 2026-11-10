"""Self-test for probe.py and wf.py. Run: python skill/evals/test_scripts.py

Builds a project from the templates in a temporary folder (as phase 5 would), then runs the
practice round and the failure cases that `wf.py check` must catch.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
CORE = SKILL / "templates" / "core"
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")
TOOL_FILES = ("step.md", "fixes.md", "progress-review.md", "addons.md")


def run(args, cwd=None):
    p = subprocess.run([sys.executable] + [str(a) for a in args], cwd=cwd,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def snapshot(folder):
    return sorted((str(p.relative_to(folder)), p.stat().st_size, p.stat().st_mtime_ns)
                  for p in Path(folder).rglob("*"))


def make_project(root):
    """Fill the templates the way phase 5 would, with Python and Claude Code."""
    root = Path(root)
    (root / "tools").mkdir()
    (root / "deliverable").mkdir()
    (root / ".workflow-architect").mkdir()
    for f in CORE.iterdir():
        dest = root / (("tools/" + f.name) if f.name in TOOL_FILES else f.name)
        text = f.read_text(encoding="utf-8")
        if f.name == "step.md":
            text = re.sub(r"<!-- no-python -->.*<!-- /no-python -->\n?", "", text, flags=re.S)
        if f.name == "STATE.json":
            state = json.loads(PLACEHOLDER.sub("x", text))
            state.update({"project": "Toy", "phase": "drafting", "review_phase": "drafting",
                          "autonomy": "one-step",
                          "tools": ["claude-code"], "python": "python", "git": "none",
                          "parts": {"outline": "deliverable/outline.md"},
                          "instruction_files": ["AGENTS.md", "CLAUDE.md"]})
            text = json.dumps(state, indent=2) + "\n"
        elif f.name == "NEXT.md":
            text = ("# Next action\n\nActor: AI\nAction: Write the outline\nPart: outline\n"
                    "Done when: five headings\n")
        else:
            text = PLACEHOLDER.sub("x", text)
        dest.write_text(text, encoding="utf-8")
    shutil.copy(SKILL / "templates" / "adapters" / "claude-code" / "CLAUDE.md", root)
    shutil.copy(SKILL / "scripts" / "wf.py", root / "tools" / "wf.py")
    (root / "deliverable" / "outline.md").write_text("# Outline\n", encoding="utf-8")
    (root / "BRIEF.md").write_text("# Brief: Toy\n\nVersion 1\n", encoding="utf-8")
    return root


class ProbeTest(unittest.TestCase):
    def test_read_only_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "notes.md").write_text("hi", encoding="utf-8")
            Path(d, ".env").write_text("SECRET=1", encoding="utf-8")
            before = snapshot(d)
            code, out = run([SKILL / "scripts" / "probe.py", d, "--json"])
            self.assertEqual(code, 0, out)
            r = json.loads(out)
            self.assertEqual(r["folder_scan"]["files"], 2)
            self.assertIn(".env", [s["path"] for s in r["possible_secrets"]])
            code, out = run([SKILL / "scripts" / "probe.py", d])
            self.assertEqual(code, 0, out)
            self.assertIn("Machine check", out)
            self.assertEqual(before, snapshot(d), "probe.py changed the folder")


class ProjectCase(unittest.TestCase):
    """A project made from the templates, in a temporary folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = make_project(self.tmp.name)
        self.wf = self.root / "tools" / "wf.py"

    def tearDown(self):
        self.tmp.cleanup()

    def wf_ok(self, *args):
        code, out = run([self.wf] + list(args))
        self.assertEqual(code, 0, out)
        return out

    def wf_fails(self, *args, expect=""):
        code, out = run([self.wf] + list(args))
        self.assertNotEqual(code, 0, out)
        self.assertIn(expect, out)
        return out

    def log_text(self):
        return (self.root / "LOG.md").read_text(encoding="utf-8")


class WfTest(ProjectCase):
    def test_fresh_project_passes(self):
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_practice_round_then_real_step(self):
        self.wf_ok("log", "AI", "workflow set up", "--tags", "workflow")
        self.wf_ok("begin", "--practice")
        self.wf_fails("begin", expect="practice")
        (self.root / ".workflow-architect" / "practice.md").write_text("x", encoding="utf-8")
        self.wf_ok("log", "AI", "wrote practice line", "--part", "practice",
                   "--tags", "progress:practice")
        self.assertIn("| P |", self.log_text())
        self.assertIn("check: OK", self.wf_ok("check"))
        self.assertIn("check: OK", self.wf_ok("practice-done"))
        self.assertNotIn("| P |", self.log_text())
        self.assertIn("practice round passed", self.log_text())
        self.assertFalse((self.root / ".workflow-architect" / "practice.md").exists())
        self.wf_fails("log", "AI", "x", "--part", "practice", expect="not in STATE.json")
        status = self.wf_ok("begin")
        self.assertEqual(len(status.strip().splitlines()), 3, status)
        self.assertIn("S-001", status)
        self.assertIn("Next (AI): Write the outline", status)
        line = self.wf_ok("log", "AI", "wrote a | outline", "--part", "outline",
                          "--tags", "progress:outline rule:R-2")
        self.assertIn("| S-001 | AI | wrote a / outline | outline | [progress:outline] "
                      "[rule:R-2]", line)
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_log_rejects_bad_tags(self):
        self.wf_fails("log", "AI", "x", "--tags", "nonsense", expect="unknown tag")
        self.wf_fails("log", "AI", "x", "--tags", "progress:nope", expect="not a part")
        self.wf_fails("log", "AI", "x", "--tags", "progress", expect="needs a value")
        self.wf_fails("log", "AI", "x", "--tags", "rule:R-9", expect="no rule R-9")
        self.wf_fails("log", "AI", "x", "--tags", "correction:Bad Key", expect="unknown tag")
        self.wf_fails("log", "AI", "x", "--tags", "correction:Bad_Key", expect="key must")
        self.wf_fails("practice-done", expect="no practice round")
        self.assertNotIn("| AI | x |", self.log_text())

    def test_check_catches_problems(self):
        cases = {
            "NEXT.md": ("Actor: AI\nActor: YOU\nAction: two\n", "exactly one 'Actor:'"),
            "BRIEF.md": ("# Brief {{goal}}\n", "unfilled template placeholder"),
            "RULES.md": ("".join("## R-{} r\nOrigin: t\n".format(i) for i in range(1, 14)),
                         "cap is 12"),
            "AGENTS.md": ("line\n" * 81, "cap is 80"),
            "LOG.md": ("# Log\n\n- 2026-01-01 10:00 | P | AI | left | - | [begin]\n",
                       "practice line left over"),
            "STATE.json": ("{not json", "not valid JSON"),
        }
        for name, (text, expect) in cases.items():
            with self.subTest(name):
                p = self.root / name
                original = p.read_text(encoding="utf-8")
                p.write_text(text, encoding="utf-8")
                self.wf_fails("check", expect=expect)
                p.write_text(original, encoding="utf-8")
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_keeps_windows_line_endings(self):
        log = self.root / "LOG.md"
        log.write_bytes(log.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.wf_ok("log", "YOU", "said hello", "--tags", "answered")
        data = log.read_bytes()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertIn("check: OK", self.wf_ok("check"))


F = "%Y-%m-%d %H:%M"


class HistoryCase(ProjectCase):
    """A project with helpers for made-up history and health output."""

    def state(self, **changes):
        p = self.root / "STATE.json"
        s = json.loads(p.read_text(encoding="utf-8"))
        if changes:
            s.update(changes)
            p.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
        return s

    def history(self, specs):
        """Append made-up steps to LOG.md. A spec is a tag string, or a dict with "tags",
        "minutes" (step length), "actor", "days" (days skipped before the step)."""
        log = self.root / "LOG.md"
        text = log.read_text(encoding="utf-8")
        specs = [{"tags": s} if isinstance(s, str) else s for s in specs]
        span = sum((timedelta(days=s.get("days", 0), minutes=s.get("minutes", 10) + 30)
                    for s in specs), timedelta(minutes=5))
        latest = datetime.now().replace(second=0, microsecond=0) - span
        times = re.findall(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", text, re.M)
        if times and datetime.strptime(times[-1], F) > latest:
            # move the existing lines back, so the whole history stays in the past and real
            # lines written later by wf.py come after it
            shift = datetime.strptime(times[-1], F) - latest
            text = re.sub(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", lambda m: "- " + (
                datetime.strptime(m.group(1), F) - shift).strftime(F), text, flags=re.M)
            times = re.findall(r"^- (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", text, re.M)
        t = (datetime.strptime(times[-1], F) if times else latest) + timedelta(minutes=1)
        step = self.state()["step"]
        lines = []
        for spec in specs:
            spec = {"tags": spec} if isinstance(spec, str) else spec
            step += 1
            sid = "S-{:03d}".format(step)
            t += timedelta(days=spec.get("days", 0))
            lines.append("- {} | {} | AI | step begins | - | [begin]".format(t.strftime(F), sid))
            t += timedelta(minutes=spec.get("minutes", 10))
            tags = " ".join("[{}]".format(x) for x in spec.get("tags", "").split())
            part = "outline" if "progress:outline" in spec.get("tags", "") else "-"
            lines.append("- {} | {} | {} | made-up event | {} |{}".format(
                t.strftime(F), sid, spec.get("actor", "AI"), part, " " + tags if tags else ""))
            t += timedelta(minutes=30)
        log.write_text(text.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
        self.state(step=step)

    def health(self):
        code, out = run([self.wf, "health", "--json"])
        self.assertEqual(code, 0, out)
        return json.loads(out)

    def warning_ids(self):
        return [w["id"] for w in self.health()["warnings"]]

    def fixes(self):
        return (self.root / "WORKFLOW-FIXES.md").read_text(encoding="utf-8")

    def add_rule_change(self, by="ai", size="small"):
        return run([self.wf, "fix", "add", 'added R-3 "check every source exists"',
                    "--size", size, "--by", by, "--measure", "correction:missing-source",
                    "--evidence", "same correction twice (S-004, S-008)",
                    "--undo", "delete R-3 from RULES.md"])

    P = "progress:outline"


class FixTest(HistoryCase):
    """v0.2: health warnings, workflow fixes, re-checks, fix levels, progress review, guard."""

    def test_fresh_health_is_quiet(self):
        out = self.wf_ok("health")
        self.assertIn("Health: OK | no steps yet", out)
        self.assertNotIn("warning", out)

    def test_correction_twice_then_rule_kept(self):
        P = self.P
        self.history([P, P, P, P + " correction:missing-source", P, P, P,
                      P + " correction:missing-source", P, P])
        self.assertIn("correction:missing-source", self.warning_ids())
        code, out = self.add_rule_change()
        self.assertEqual(code, 0, out)
        evo = self.fixes()
        self.assertIn("## F-1 | testing", evo)
        self.assertIn("- Before: 0.20 (2 of the last 10 steps)", evo)
        self.assertIn("- Re-check at: S-015", evo)
        self.assertIn("- Made by: AI (level 2)", evo)
        self.assertNotIn("No fixes yet.", evo)
        self.assertIn("made workflow fix F-1 (small)", self.log_text())
        self.assertNotIn("correction:missing-source", self.warning_ids())
        self.assertIn("check: OK", self.wf_ok("check"))
        self.history([P] * 4)
        self.assertEqual(self.health()["rechecks"], [])
        self.history([P])
        [cb] = self.health()["rechecks"]
        self.assertEqual((cb["id"], cb["verdict"]), ("F-1", "helped"))
        self.assertIn("re-check of F-1", self.wf_ok("status"))
        self.wf_ok("fix", "mark", "F-1", "kept", "0.20 before, 0.00 since")
        evo = self.fixes()
        self.assertIn("## F-1 | kept", evo)
        self.assertRegex(evo, r"- Outcome: kept at S-015 \(.*\): 0.20 before, 0.00 since")
        self.wf_fails("fix", "mark", "F-1", "testing", "x", expect="it can move to: undone")
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_recheck_not_helped_says_undo(self):
        P = self.P
        self.history([P, P, P, P + " correction:missing-source", P, P, P,
                      P + " correction:missing-source", P, P])
        self.add_rule_change()
        self.history([P, P, P + " correction:missing-source", P, P])
        [cb] = self.health()["rechecks"]
        self.assertEqual(cb["verdict"], "not helped")
        self.assertIn("undo it (the AI made it)", cb["text"])
        self.wf_ok("fix", "mark", "F-1", "undone", "came back at S-013")
        self.assertIn("## F-1 | undone", self.fixes())

    def test_removed_rule_keeps_old_log_lines_valid(self):
        rules = self.root / "RULES.md"
        original = rules.read_text(encoding="utf-8")
        rules.write_text(original + "\n## R-3 Check every source exists\nOrigin: F-1.\n",
                         encoding="utf-8")
        self.history([self.P + " rule:R-3"])
        rules.write_text(original, encoding="utf-8")           # R-3 deleted (undone)
        self.wf_fails("check", expect="no rule R-3")           # unknown without a record
        code, out = run([self.wf, "fix", "add", 'added R-3 "check every source exists"',
                         "--size", "small", "--by", "ai", "--measure",
                         "correction:missing-source", "--evidence", "x", "--undo",
                         "delete R-3, then wf fix mark F-<n> undone"])
        self.assertEqual(code, 0, out)
        self.assertIn("then wf fix mark F-1 undone", self.fixes())
        self.assertIn("check: OK", self.wf_ok("check"))       # recorded in WORKFLOW-FIXES.md

    def test_level_rules(self):
        self.history([self.P] * 3)
        self.assertNotEqual(self.add_rule_change(size="yours")[0], 0)
        code, out = self.add_rule_change(size="big")
        self.assertNotEqual(code, 0)
        self.assertIn("a big fix is proposed", out)
        self.assertEqual(self.add_rule_change(size="big", by="proposed")[0], 0)
        evo = self.fixes()
        self.assertIn("## F-1 | proposed", evo)
        self.assertIn("- Before: -", evo)
        self.assertEqual(self.health()["waiting"], ["F-1"])
        self.assertIn("F-1 waits for the user's answer", self.wf_ok("status"))
        self.wf_fails("fix", "mark", "F-1", "kept", "x", expect="rejected, testing")
        self.wf_ok("fix", "mark", "F-1", "testing", "yes, do it")
        evo = self.fixes()
        self.assertIn("- Made by: you (approved)", evo)
        self.assertIn("- Re-check at: S-008", evo)
        self.assertIn("check: OK", self.wf_ok("check"))
        self.state(fix_level=1)
        code, out = self.add_rule_change()
        self.assertIn("level 1: every fix is proposed", out)
        self.state(fix_level=2)
        # a hand-written big fix by the AI is caught by the check
        p = self.root / "WORKFLOW-FIXES.md"
        p.write_text(self.fixes().replace("- Size: big", "- Size: big").replace(
            "- Made by: you (approved)", "- Made by: AI (level 2)"), encoding="utf-8")
        self.wf_fails("check", expect="a big fix is proposed, not made by the AI")

    def test_other_warnings(self):
        P = self.P
        self.history([P, "fail", P, "redo", P, "fail", "", "", "", ""])
        ids = self.warning_ids()
        self.assertIn("progress", ids)
        self.assertIn("rework", ids)
        self.history(["workflow", "workflow", P, "workflow", P])
        self.assertIn("workflow", self.warning_ids())
        self.history([P] * 5 + [{"tags": P, "minutes": 120}])
        self.assertIn("overrun", self.warning_ids())
        self.wf_ok("log", "AI", "one-off: a big download", "--tags", "noted:overrun")
        self.assertNotIn("overrun", self.warning_ids())
        self.wf_fails("log", "AI", "x", "--tags", "noted:nonsense", expect="health warning id")
        self.history([P + " repeat:use-apa", P + " repeat:use-apa", P + " escaped:review"])
        ids = self.warning_ids()
        self.assertNotIn("repeat:use-apa", ids)
        self.assertIn("escaped", ids)
        self.history([P + " repeat:use-apa"])
        self.assertIn("repeat:use-apa", self.warning_ids())

    def test_questions_and_silent_rule(self):
        q = self.root / "QUESTIONS.md"
        old = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        q.write_text("# Questions\n\n## Open\n- Q-1 | asked {} | which venue? | why: x\n\n"
                     "## Just in time\n\n## Answered\n".format(old), encoding="utf-8")
        self.history([{"tags": self.P, "days": 1}] * 4)
        [w] = [w for w in self.health()["warnings"] if w["id"] == "questions"]
        self.assertIn("Q-1", w["text"])
        rules = self.root / "RULES.md"
        rules.write_text(rules.read_text(encoding="utf-8") +
                         "\n## R-3 Check every source exists\nOrigin: the user said so.\n",
                         encoding="utf-8")
        self.history([self.P] * 25)
        self.assertNotIn("silent:R-3", self.warning_ids())
        self.history([self.P])
        self.assertIn("silent:R-3", self.warning_ids())
        rules.write_text(rules.read_text(encoding="utf-8").replace(
            "## R-3 Check", "## R-3 (paused) Check"), encoding="utf-8")
        self.assertNotIn("silent:R-3", self.warning_ids())
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_review_due(self):
        self.history([self.P] * 9)
        self.assertFalse(self.health()["review_due"])
        self.history([self.P])
        self.assertTrue(self.health()["review_due"])
        self.assertIn("Due: progress review (10 steps since the last one)", self.wf_ok("status"))
        self.wf_ok("log", "AI", "progress review 1: fine", "--tags", "workflow review")
        self.assertFalse(self.health()["review_due"])
        self.state(phase="pilot")
        self.assertIn("phase 'drafting' ended", self.wf_ok("status"))
        self.wf_ok("log", "AI", "progress review 2: end of drafting", "--tags", "workflow review")
        self.assertEqual(self.state()["review_phase"], "pilot")
        self.assertFalse(self.health()["review_due"])

    def test_guard_on_the_users_files(self):
        self.history([self.P])
        self.wf_ok("begin")
        brief = self.root / "BRIEF.md"
        brief.write_text(brief.read_text(encoding="utf-8") + "\nFinish line: changed\n",
                         encoding="utf-8")
        self.wf_fails("check", expect="BRIEF.md changed in step S-002")
        self.wf_ok("log", "YOU", "approved the new finish line", "--tags", "answered")
        self.assertIn("check: OK", self.wf_ok("check"))
        self.wf_ok("begin")
        self.state(fix_level=3)
        self.wf_fails("check", expect="STATE.json fix_level changed")


class AddonTest(HistoryCase):
    """v0.3: add-ons (budget, second opinion, experiment plans) and the core lines."""

    def budget(self, cap=30, ask_over=5):
        limits = self.state()["limits"]
        limits["budget"] = {"cap": cap, "currency": "USD", "ask_over": ask_over}
        self.state(limits=limits)

    def test_switching_on_and_off(self):
        self.wf_fails("log", "AI", "x", "--tags", "used:budget", expect="not on")
        self.wf_fails("addon", "on", "hours", expect="unknown add-on")
        self.wf_fails("addon", "on", "budget", expect="first put the user's answer")
        self.budget()
        self.wf_ok("addon", "on", "budget")
        self.assertTrue((self.root / "SPENDING.md").exists())
        self.assertIn("Add-ons: budget 0.00 of 30.00 USD", self.wf_ok("status"))
        self.assertIn("check: OK", self.wf_ok("check"))
        self.wf_fails("addon", "off", "budget", "not needed", expect="only the user may")
        self.wf_ok("log", "YOU", "said: switch the budget off", "--tags", "answered")
        self.wf_ok("addon", "off", "budget", "you asked")
        self.assertFalse(self.state()["addons"]["budget"]["on"])
        self.wf_ok("addon", "on", "experiment-plans")
        self.wf_ok("addon", "off", "experiment-plans", "unused")     # the AI may
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_spending_cap_and_ask_first(self):
        self.budget(cap=10, ask_over=2)
        self.wf_ok("addon", "on", "budget")
        self.wf_ok("spend", "1.50", "pilot: 150 grader calls", "--estimate")
        self.assertIn("| 1.50 | estimate | pilot: 150 grader calls",
                      (self.root / "SPENDING.md").read_text(encoding="utf-8"))
        self.assertIn("[used:budget]", self.log_text())
        self.wf_fails("spend", "3", "bigger run", expect="needs the user's OK first")
        self.wf_ok("log", "YOU", "said: yes, spend 3", "--tags", "answered")
        self.wf_ok("spend", "3", "bigger run")
        self.wf_fails("spend", "6", "too much", expect="over the cap")
        self.assertNotIn("budget", self.warning_ids())
        self.wf_ok("spend", "4", "third run")                         # 8.50 of 10
        self.assertIn("budget", self.warning_ids())
        self.wf_ok("spend", "-0.5", "third run: measured, cost less")
        self.assertIn("check: OK", self.wf_ok("check"))
        sp = self.root / "SPENDING.md"
        sp.write_text(sp.read_text(encoding="utf-8") +
                      "- 2026-01-01 10:00 | - | 5.00 | measured | by hand\n", encoding="utf-8")
        self.wf_fails("check", expect="over the cap")

    def test_second_opinion(self):
        self.history([self.P])
        self.wf_fails("addon", "on", "second-opinion", expect="--parts is needed")
        self.wf_fails("addon", "on", "second-opinion", "--parts", "nope", expect="not parts")
        self.wf_ok("addon", "on", "second-opinion", "--parts", "outline")
        self.wf_fails("check", expect="missing file: tools/second-opinion.md")
        (self.root / "tools" / "second-opinion.md").write_text("# Second opinion\n",
                                                               encoding="utf-8")
        self.assertIn("check: OK", self.wf_ok("check"))
        self.wf_ok("opinion", "outline", "fail", "heading 3 has no source")
        self.wf_fails("opinion", "intro", "pass", "x", expect="not listed")
        self.assertIn("- SO-1 |", (self.root / "SECOND-OPINIONS.md").read_text(encoding="utf-8"))
        for _ in range(15):
            self.wf_ok("opinion", "outline", "pass", "no problems found")
        self.assertIn("second-opinion-quiet", self.warning_ids())
        self.wf_ok("log", "YOU", "said keep it as it is", "--tags",
                   "answered noted:second-opinion-quiet")
        self.assertNotIn("second-opinion-quiet", self.warning_ids())
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_experiment_plan_is_locked(self):
        self.wf_ok("addon", "on", "experiment-plans")
        path = self.wf_ok("experiment", "new", "Pilot: longer answers?").strip()
        self.assertEqual(path, "experiments/X-001-pilot-longer-answers.md")
        plan = self.root / path
        self.wf_fails("experiment", "start", "X-001", expect="fill in 'Question'")
        text = plan.read_text(encoding="utf-8")
        self.assertIn("pilot before scale", text)
        plan.write_text(text.replace("(what we want to find out)", "Longer answers?"),
                        encoding="utf-8")
        self.wf_fails("experiment", "start", "X-001", expect="fill in 'Setup'")
        setup = re.search(r"## Setup\n(\(.*\))\n", text).group(1)
        for old, new in (("(what we want to find out)", "Do graders prefer longer answers?"),
                         (setup, "20 pairs, mock grader"),
                         ("(for each likely result: what we would conclude, and what we would "
                          "do next)", "Longer wins over 60%: go on. Otherwise: stop.")):
            text = text.replace(old, new)
        plan.write_text(text.replace("## Results\n(after the run)", "## Results\nlonger won 70%"),
                        encoding="utf-8")
        self.wf_fails("check", expect="was never started")
        self.wf_fails("experiment", "start", "X-001", expect="results are already written")
        plan.write_text(text, encoding="utf-8")
        self.wf_ok("experiment", "start", "X-001")
        self.wf_fails("experiment", "start", "X-001", expect="already started")
        plan.write_text(text.replace("over 60%", "over 50%"), encoding="utf-8")
        self.wf_fails("check", expect="was changed after the experiment started")
        plan.write_text(text.replace("## Results\n(after the run)", "## Results\nlonger won 70%"),
                        encoding="utf-8")
        self.assertIn("check: OK", self.wf_ok("check"))
        self.assertIn("experiment plans (1 started)", self.wf_ok("status"))

    def test_unused_addons(self):
        self.budget()
        self.wf_ok("addon", "on", "budget")
        self.wf_ok("addon", "on", "experiment-plans")
        self.history([self.P] * 19)
        self.assertFalse([w for w in self.warning_ids() if w.startswith("unused")])
        self.history([self.P])
        warnings = {w["id"]: w for w in self.health()["warnings"]}
        self.assertIn("switch it off (a small fix)", warnings["unused:experiment-plans"]["fix"])
        self.assertIn("ask the user", warnings["unused:budget"]["fix"])
        code, out = run([self.wf, "fix", "add", "switched off experiment plans (unused)",
                         "--size", "small", "--by", "ai", "--measure",
                         "unused:experiment-plans", "--evidence", "unused 20 steps",
                         "--undo", "wf addon on experiment-plans"])
        self.assertEqual(code, 0, out)
        self.assertIn("- Before: 0 (not measured per step)", self.fixes())
        self.assertNotIn("unused:experiment-plans", self.warning_ids())
        self.assertIn("check: OK", self.wf_ok("check"))

    def test_task_for_the_user_needs_an_estimate(self):
        nxt = self.root / "NEXT.md"
        nxt.write_text("Actor: YOU\nAction: label 50 answers\nPart: outline\nDone when: x\n",
                       encoding="utf-8")
        self.wf_fails("check", expect="needs an 'Estimated:' line")
        nxt.write_text(nxt.read_text(encoding="utf-8") + "Estimated: 1 h\n", encoding="utf-8")
        self.assertIn("check: OK", self.wf_ok("check"))


class LessonTest(ProjectCase):
    """v0.4: the lessons that a script can check (the stop record)."""

    def test_stop_note(self):
        st = self.root / "STATE.json"
        state = json.loads(st.read_text(encoding="utf-8"))
        state["phase"] = "stopped"
        st.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        self.wf_fails("check", expect="no STOP-NOTE.md")
        note = self.root / "STOP-NOTE.md"
        head = "# Stop notes\n\n## 2026-11-20 | stopped: the project\n"
        note.write_text(head + "- Tried: a 40-pair pilot\n- Found: 29 of 40\n", encoding="utf-8")
        self.wf_fails("check", expect="missing or empty: - Reusable:, - Could still go:")
        note.write_text(head + "- Tried: a 40-pair pilot\n- Found: 29 of 40\n"
                        "- Reusable: the pairs file\n- Could still go:\n  a workshop paper\n",
                        encoding="utf-8")
        self.assertIn("check: OK", self.wf_ok("check"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
