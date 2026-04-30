# Two UI Surfaces

## Context

The product has two different user jobs:

1. Configure reusable document imitation resources.
2. Use those resources in an interactive document authoring session.

Combining these into one interface would blur management, skill creation, workspace navigation, and drafting.

## Decision

DocAgent Workbench will have two primary UI surfaces:

- Management interface: dashboard for document type packs, resource upload, conversion review, Skill Creator, checklist management, publishing, and versioning.
- Authoring interface: three-column Codex/Claude Code-style workspace for selecting document type/project/session, interacting with the agent timeline, and editing/previewing Markdown drafts.

## Consequences

- Management can stay operational and resource-oriented.
- Authoring can stay focused on the live agent loop.
- Skill Creator becomes part of document type construction, not task authoring.
- The left navigation in authoring can model document type -> project -> session.
- The right preview/editor can support selection-based revision requests.

## Alternatives Considered

- Single all-in-one UI: rejected because it would overload the authoring session.
- Traditional CMS/admin UI only: rejected because the product needs Claude Code-style interaction.
- Wizard-based creation flow: rejected because it would push the product toward fixed workflow behavior.

