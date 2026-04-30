# Architecture Overview

DocAgent Workbench uses a product backend to prepare a workspace, then delegates writing work to a coding-agent runtime.

```text
User
  -> Web Workbench
  -> FastAPI Product Backend
  -> Runtime Adapter
  -> Coding-Agent Runtime
  -> Task Workspace and DocType Skill Pack
```

## Main Components

- Web Workbench: conversation, timeline, draft preview, diff, versions, approvals.
- Product Backend: task state, workspace creation, runtime sessions, artifacts, audit.
- Runtime Adapter: abstracts OpenHands or another coding-agent runtime.
- Workspace: durable files that the agent reads and writes.
- DocType Skill Pack: examples, specs, checklists, and skill guidance.
- Fixed Tools: small scripts for checkpoint, validation, parsing, and export.
- Markdown Pipeline: converts imported resources to Markdown and exports Markdown to DOCX/PDF.

## Current Runtime Bias

OpenHands is the first runtime to validate because it already aligns with coding-agent behavior: file tools, shell, sandbox, event stream, skills, and context mechanisms.

The architecture should still isolate runtime-specific details behind an adapter.

## UI Surfaces

The product has two primary UI surfaces:

- Management dashboard for document type resources, conversion review, Skill Creator, and publishing.
- Three-column authoring workspace for document type/project/session selection, agent timeline, and Markdown preview/edit/export.
