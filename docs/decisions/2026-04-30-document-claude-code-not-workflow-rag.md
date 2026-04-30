# Document Claude Code, Not Workflow Or RAG

## Context

The original platform vision explored document agents, document tools, RAG, workflow-like checks, and OpenHands-style runtime reuse.

After reviewing the rapid prototype direction, the product target was clarified: the core experience should resemble Claude Code for documents. Users should interact with an agent that can read a workspace, infer writing style from examples, maintain context files, accept interruption, revise locally, checkpoint drafts, and show its process.

Best-practice examples are usually not semantically related to the user's project. They primarily teach structure, narration, information density, and document organization.

## Decision

The product will be designed as a document coding-agent workbench, not a fixed workflow builder or semantic RAG writing application.

Phase 0 will prioritize:

- coding-agent runtime behavior
- workspace contract
- document type skill packs
- context files
- checkpoints
- semantic timeline
- checklist and export scripts

Phase 0 will not prioritize:

- RAG
- per-document-type workflow DAGs
- template designers
- high-fidelity Word automation

## Consequences

- Document type packs contain examples, specs, checklists, and `SKILL.md`, but do not define fixed workflows.
- RAG can be introduced later for large-scale asset discovery, but it is not the default writing strategy.
- The backend owns product state and audit, while the agent owns reasoning and drafting.
- The repo should remain agent-friendly: explicit boundaries, small docs, and durable decisions.

## Alternatives Considered

- Dify-style workflow app: rejected because it would require per-document process design and reduce the free-form agent loop.
- RAG-first writing app: rejected because structure and narration matter more than semantic similarity.
- Full custom document tool suite in Phase 0: deferred because default coding-agent file tools plus fixed scripts are enough to validate the core loop.

