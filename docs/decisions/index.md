# Decision Records

This directory records architecture and product decisions that should outlive chat context.

## Format

Use:

```text
YYYY-MM-DD-short-title.md
```

Each decision should include:

1. Context
2. Decision
3. Consequences
4. Alternatives considered

## Current Decisions To Record

- Phase 0 uses one PRD document type.
- Best-practice examples teach structure and style, not project semantics.
- Runtime starts with OpenHands candidate behind an adapter.

## Records

- `2026-04-30-document-claude-code-not-workflow-rag.md`: product is document-version Claude Code, not workflow/RAG.
- `2026-04-30-markdown-only-internal-format.md`: Markdown is the only internal document format.
- `2026-04-30-two-ui-surfaces.md`: product has separate management and authoring interfaces.
