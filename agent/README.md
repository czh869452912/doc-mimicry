# Agent Assets

Agent-facing prompts, skills, and runtime adapter notes.

This directory defines the behavior expected from a document coding agent.

Contents:

- `system-prompts/`: shared system prompts.
- `skills/`: reusable agent skill guidance.
- `runtime-adapters/`: runtime-specific notes.

Agent runtime integration is ACP-first. Product-facing runtime adapters emit ACP
updates, and provider-backed model calls go through LiteLLM aliases.

