# Execution Plans

Use execution plans for multi-step work that changes behavior, structure, or architecture.

There are two plan tracks in this repository:

- `docs/exec-plans/`: durable phase, architecture, and milestone plans.
- `docs/superpowers/`: task-sized agent execution plans and their completed records.
- `docs/superpowers/specs/`: design references that may seed plans, but are not executable checklists by themselves.

Durable execution plans live in:

```text
docs/exec-plans/active/
docs/exec-plans/completed/
```

Superpowers task plans live in:

```text
docs/superpowers/plans/
docs/superpowers/completed/
```

## Plan File Naming

```text
YYYY-MM-DD-short-topic.md
```

Example:

```text
docs/exec-plans/active/YYYY-MM-DD-short-topic.md
```

Superpowers task plans use the same filename shape:

```text
docs/superpowers/plans/YYYY-MM-DD-short-topic.md
```

## Required Sections

Each plan should include:

1. Goal
2. Scope
3. Non-goals
4. Files and modules likely to change
5. Step-by-step implementation checklist
6. Verification commands
7. Rollback or recovery notes
8. Open questions

## Plan Discipline

- Keep active plans current as work proceeds.
- Move completed durable plans to `docs/exec-plans/completed/`.
- Move completed superpowers task plans to `docs/superpowers/completed/`.
- If implementation discovers a better architecture, update the plan before continuing.
- Do not use plans as vague wishlists. They should be executable by a fresh agent.
- If a plan is partially executed outside its checklist, add a status note before any new agent continues it.
