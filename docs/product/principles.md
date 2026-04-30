# Product Principles

## Preserve The Vibe Coding Loop

The system should feel like Claude Code for documents: conversational, iterative, interruptible, tool-using, and context-aware.

## Skills Over Workflows

Document types should be represented as skill packs: examples, specs, checklists, and guidance. Avoid encoding a fixed DAG per document type.

## Structure And Style Over Semantic Matching

Best-practice examples primarily teach structure, information density, narrative style, table usage, and review habits. They are not assumed to be semantically related to the user's project.

## Workspace As Memory

The workspace should hold durable context files that make long sessions recoverable and inspectable.

## Markdown As The Internal Format

All user inputs and document type resources should be converted to Markdown before agent use. DOCX, PDF, PPTX, images, and HTML exist at import/export boundaries, not inside the agent loop.

## Separate Management From Authoring

Document type management and live document authoring are different jobs. Use a dashboard-style management interface for skill pack construction, and a Claude Code/Codex-style authoring interface for task sessions.

## Product State Outside The Agent

The backend owns versions, artifacts, audit, permissions, and semantic timeline enrichment. The agent owns reasoning, drafting, and revision.

## Start Narrow

Phase 0 should validate one document type and one core loop before adding RAG, multi-doc-type management, or high-fidelity export.
