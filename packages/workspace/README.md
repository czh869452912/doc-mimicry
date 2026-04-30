# Workspace Package

Helpers for creating, validating, and inspecting task workspaces.

Expected responsibilities:

- Workspace layout constants.
- Required file checks.
- Safe path resolution.
- Draft version naming.
- Workspace tree summaries.

## Phase 0 Helpers

Executable helpers live in `docagent_workspace/`.

- `create_workspace(root, brief)`: creates the Markdown-only task workspace directories and `brief.md`.
- `validate_workspace(root)`: checks required pre-drafting files.
- `workspace_paths(root)`: returns common contract paths.

