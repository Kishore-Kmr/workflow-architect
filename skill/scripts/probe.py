#!/usr/bin/env python3
"""workflow-architect machine check.

Read-only: it never writes, moves or deletes anything. It reports facts about the machine and
the project folder so the interview only asks about intentions.

Usage: python probe.py [FOLDER] [--json]
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache",
             ".pytest_cache", ".tox", ".idea", ".vscode"}
MAX_FILES = 20000
AI_CLIS = ["claude", "codex", "gemini", "cursor-agent", "copilot", "aider", "opencode",
           "goose", "amp", "ollama"]
# Environment variables some tools set in the shells they start (best-effort hints only;
# the agent also knows which tool it is running in).
HARNESS_MARKERS = {"CLAUDECODE": "Claude Code", "GEMINI_CLI": "Gemini CLI",
                   "CODEX_SANDBOX": "Codex", "CODEX_SANDBOX_NETWORK_DISABLED": "Codex"}
AGENT_FILES = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", ".claude", ".codex", ".agents",
               ".cursor", ".cursorrules", ".windsurfrules", ".github/copilot-instructions.md"]
WORKFLOW_FILES = ["STATE.json", "NEXT.md", "BRIEF.md", "LOG.md", "tools/wf.py"]
PACKAGE_MANAGERS = ["winget", "choco", "scoop", "brew", "apt-get", "dnf", "pacman", "zypper"]
SECRET_RE = re.compile(r"(^\.env)|key|secret|token|credential|password|\.pem$|id_rsa|"
                       r"settings\.local\.json$", re.I)
SYNC_NAMES = ["OneDrive", "Dropbox", "iCloudDrive", "iCloud Drive", "Google Drive"]


def run(cmd, cwd=None, timeout=10):
    """Run a read-only command; return (exit code, output) or (None, error text)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           errors="replace")
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)


def check_pythons():
    found = []
    for name in ["python3", "python", "py"]:
        path = shutil.which(name)
        if not path:
            continue
        code, out = run([path, "--version"])
        real = code == 0 and out.startswith("Python ")
        item = {"cmd": name, "path": path, "version": out.split()[1] if real else None}
        if not real:
            item["note"] = ("Microsoft Store placeholder, not a real Python"
                            if "WindowsApps" in path else "does not run: " + out[:80])
        elif not out.startswith("Python 3"):
            item["note"] = "Python 2: too old"
        found.append(item)
    return found


def strip_credentials(url):
    return re.sub(r"://[^@/]+@", "://", url)


def check_git(folder):
    git = shutil.which("git")
    if not git:
        return {"installed": False}
    info = {"installed": True}
    code, out = run([git, "--version"])
    info["version"] = out.replace("git version ", "") if code == 0 else None
    for key in ["user.name", "user.email"]:
        code, out = run([git, "config", "--get", key], cwd=folder)
        info[key] = bool(code == 0 and out)
    code, out = run([git, "rev-parse", "--is-inside-work-tree"], cwd=folder)
    info["repo"] = code == 0 and out == "true"
    if info["repo"]:
        code, out = run([git, "rev-parse", "--show-toplevel"], cwd=folder)
        info["top"] = out if code == 0 else None
        code, _ = run([git, "rev-parse", "--verify", "-q", "HEAD"], cwd=folder)
        info["has_commits"] = code == 0
        code, out = run([git, "remote", "-v"], cwd=folder)
        remotes = sorted({strip_credentials(" ".join(line.split()[:2]))
                          for line in out.splitlines() if line.strip()}) if code == 0 else []
        info["remotes"] = remotes
    return info


def scan_folder(folder):
    files, size, exts, secrets, truncated = 0, 0, {}, [], False
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            files += 1
            p = Path(root) / n
            try:
                size += p.stat().st_size
            except OSError:
                pass
            ext = p.suffix.lower() or "(none)"
            exts[ext] = exts.get(ext, 0) + 1
            if SECRET_RE.search(n) and len(secrets) < 10:
                secrets.append(p.relative_to(folder).as_posix())
            if files >= MAX_FILES:
                truncated = True
                break
        if truncated:
            break
    top = []
    try:
        for e in sorted(folder.iterdir(), key=lambda e: e.name.lower()):
            if e.name != ".git":
                top.append(e.name + ("/" if e.is_dir() else ""))
    except OSError:
        pass
    common = sorted(exts.items(), key=lambda kv: -kv[1])[:8]
    return {"files": files, "truncated": truncated, "bytes": size, "top": top[:40],
            "top_total": len(top), "types": dict(common), "possible_secrets": secrets}


def probe(folder):
    folder = Path(folder).resolve()
    git = check_git(folder)
    scan = scan_folder(folder)
    secrets = []
    for rel in scan.pop("possible_secrets"):
        ignored = None
        if git.get("repo"):
            code, _ = run(["git", "check-ignore", "-q", rel], cwd=folder)
            ignored = code == 0
        secrets.append({"path": rel, "git_ignored": ignored})
    wa = folder / ".workflow-architect"
    return {
        "folder": str(folder),
        "os": platform.platform(),
        "shell": os.environ.get("SHELL") or os.environ.get("COMSPEC"),
        "shells_available": [s for s in ["bash", "zsh", "pwsh", "powershell", "sh"]
                             if shutil.which(s)],
        "python": check_pythons(),
        "probe_python": {"path": sys.executable, "version": platform.python_version()},
        "git": git,
        "ai_tools_installed": [c for c in AI_CLIS if shutil.which(c)],
        "running_in_hint": sorted({v for k, v in HARNESS_MARKERS.items() if os.environ.get(k)}),
        "package_managers": [m for m in PACKAGE_MANAGERS if shutil.which(m)],
        "folder_scan": scan,
        "agent_files": [f for f in AGENT_FILES if (folder / f).exists()],
        "workflow_files": [f for f in WORKFLOW_FILES if (folder / f).exists()],
        "saved_interview": (wa / "interview.json").exists(),
        "possible_secrets": secrets,
        "synced_folder": next((s for s in SYNC_NAMES if s in folder.parts), None),
    }


def human(r):
    real = [p for p in r["python"] if p["version"]]
    fake = [p for p in r["python"] if not p["version"]]
    py = ", ".join("{} {}".format(p["cmd"], p["version"]) for p in real) or "NOT FOUND"
    py += "".join("; {}: {}".format(p["cmd"], p["note"]) for p in fake)
    g = r["git"]
    if not g["installed"]:
        git = "NOT INSTALLED"
    else:
        git = "{} | name/email set: {}".format(
            g["version"], "yes" if g["user.name"] and g["user.email"] else "no")
        if g["repo"]:
            git += " | this folder is in a repo ({}), remotes: {}".format(
                "has commits" if g["has_commits"] else "no commits yet",
                ", ".join(g["remotes"]) or "none")
        else:
            git += " | this folder is not a git repo"
    s = r["folder_scan"]
    files = "{}{} files ({} KB)".format(s["files"], "+" if s["truncated"] else "",
                                        s["bytes"] // 1024)
    top = ", ".join(s["top"][:15]) + (" ..." if s["top_total"] > 15 else "")
    types = ", ".join("{} {}".format(k, v) for k, v in s["types"].items())
    secrets = ", ".join("{}{}".format(x["path"], {True: " (git-ignored)",
                        False: " (NOT git-ignored)", None: ""}[x["git_ignored"]])
                        for x in r["possible_secrets"]) or "none"
    lines = [
        "Machine check (read-only): " + r["folder"],
        "OS: {} | shell: {} | also: {}".format(r["os"], r["shell"],
                                               ", ".join(r["shells_available"]) or "-"),
        "Python: " + py,
        "Git: " + git,
        "AI tools installed: {} | running in (hint): {}".format(
            ", ".join(r["ai_tools_installed"]) or "none",
            ", ".join(r["running_in_hint"]) or "unknown"),
        "Package managers: " + (", ".join(r["package_managers"]) or "none"),
        "Folder: {} | top: {}".format(files, top or "(empty)"),
        "File types: " + (types or "-"),
        "Agent instruction files: " + (", ".join(r["agent_files"]) or "none"),
        "Workflow already set up here: " + (", ".join(r["workflow_files"]) or "no")
        + " | saved interview: " + ("yes" if r["saved_interview"] else "no"),
        "Possible secrets (names only): " + secrets,
        "Cloud-synced folder: " + (r["synced_folder"] or "no"),
    ]
    return "\n".join(lines)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    folder = args[0] if args else "."
    if not Path(folder).is_dir():
        print("probe: not a folder: " + folder, file=sys.stderr)
        return 2
    r = probe(folder)
    print(json.dumps(r, indent=2) if "--json" in argv else human(r))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    sys.exit(main(sys.argv[1:]))
