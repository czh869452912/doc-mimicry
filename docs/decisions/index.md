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

## Records

- `2026-04-30-document-claude-code-not-workflow-rag.md`: product is document-version Claude Code, not workflow/RAG.
- `2026-04-30-markdown-only-internal-format.md`: Markdown is the only internal document format.
- `2026-04-30-two-ui-surfaces.md`: product has separate management and authoring interfaces.
- `2026-05-14-acp-interaction-plane-and-litellm-gateway.md`: ACP is the canonical agent interaction and timeline contract; LiteLLM is the model gateway.
