# Agent Readability

This repo should be easy for a fresh agent to understand.

## Rules

- Keep top-level docs short and navigational.
- Put detailed design in focused files under `docs/`.
- Record decisions in `docs/decisions/`.
- Use explicit directory boundaries.
- Prefer small modules with clear contracts.
- Keep generated artifacts out of source directories.
- Add verification commands to plans and READMEs.
- Do not hide critical assumptions in chat.

## Smells

- A file explains multiple unrelated subsystems.
- A directory has no README or obvious purpose.
- A plan lacks verification.
- Product behavior is duplicated in UI, backend, and agent prompt.
- A document type becomes a fixed workflow.

