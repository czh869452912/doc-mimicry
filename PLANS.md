# Execution Plans

Use execution plans for multi-step work that changes behavior, structure, or architecture.

Plans live in:

```text
docs/exec-plans/active/
docs/exec-plans/completed/
```

## Plan File Naming

```text
YYYY-MM-DD-short-topic.md
```

Example:

```text
docs/exec-plans/active/YYYY-MM-DD-short-topic.md
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
- Move completed plans to `docs/exec-plans/completed/`.
- If implementation discovers a better architecture, update the plan before continuing.
- Do not use plans as vague wishlists. They should be executable by a fresh agent.

