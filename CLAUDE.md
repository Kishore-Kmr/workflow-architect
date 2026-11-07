# workflow-architect: project instructions

This repo builds `workflow-architect`, a personal Claude Code skill. In a new project folder it
interviews the user adaptively, builds the smallest workflow that fits, and lets that workflow
check itself and evolve.

**Start every session by reading `DESIGN.md`** (the spec). State on 2026-11-06: design agreed
(draft 3), nothing built yet. Next: build v0.1 (DESIGN.md section 10).

## How to work here

- Live the design's principles: check facts yourself, ask the user about intentions, never
  assume. Show the plan before writing files.
- Explain plainly, from the user's point of view.
- Build only what the current version needs (section 10). Put other ideas in DESIGN.md
  section 13 instead of building them.
- The skill package goes in `skill/` (section 8). Scripts in Python.
- Test each version by hand on a toy project before starting the next (section 9).
- Record the user's decisions in DESIGN.md section 12, with the date.
- Git: ask before the first commit (DESIGN.md section 13, question 1). Never push.
- Claude Code here is billed per token: keep sessions short and read only what you need.

## Related folder

`../AI eval human/` is the user's paused research repo. Its `research/` folder (RULES.md,
roles/, tools/rw.py) is a working example of the kind of workflow this skill generates. Read it
only if needed; never edit or commit there, and never open its review `key/` folders or the
user's in-progress review forms.
