# Rules

At most 12 rules: to add one, merge or retire another. Each rule says where it came from and how
it is checked, if it can be.

## R-1 When unsure, ask; don't assume
Origin: workflow-architect core rule.
Check: judgement; the cases are listed in AGENTS.md.

## R-2 One action per step; NEXT.md always holds exactly one next action
Origin: workflow-architect core rule.
Check: `tools/wf.py check`.
