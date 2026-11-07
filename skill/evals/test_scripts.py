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
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
CORE = SKILL / "templates" / "core"
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}")


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
        dest = root / ("tools/step.md" if f.name == "step.md" else f.name)
        text = f.read_text(encoding="utf-8")
        if f.name == "step.md":
            text = re.sub(r"<!-- no-python -->.*<!-- /no-python -->\n?", "", text, flags=re.S)
        if f.name == "STATE.json":
            state = json.loads(PLACEHOLDER.sub("x", text))
            state.update({"project": "Toy", "phase": "drafting", "autonomy": "one-step",
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


class WfTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main(verbosity=1)
