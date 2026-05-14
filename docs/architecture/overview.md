# Architecture Overview

DocAgent Workbench uses a product backend to prepare a workspace, then delegates writing work to a coding-agent runtime.

```text
User
  -> Web Workbench
  -> FastAPI Product Backend
  -> ACP Session Gateway and Event Log
  -> ACP Runtime Adapter or Shim
  -> Coding-Agent Runtime
  -> Task Workspace and DocType Skill Pack
  -> LiteLLM Model Gateway
```

## Main Components

- Web Workbench: conversation, ACP timeline, draft preview, diff, versions, approvals.
- Product Backend: task state, workspace creation, ACP session gateway, ACP event log, semantic projections, artifacts, audit.
- Runtime Adapter: exposes an ACP session surface for OpenHands or another coding-agent runtime.
- LiteLLM Gateway: central model-provider routing for provider-backed runtimes.
- Workspace: durable files that the agent reads and writes.
- DocType Skill Pack: examples, specs, checklists, and skill guidance.
- Fixed Tools: small scripts for checkpoint, validation, parsing, and export.
- Markdown Pipeline: converts imported resources to Markdown and exports Markdown to DOCX/PDF.

## Runtime Replacement Contract

OpenHands is the first runtime to validate because it already aligns with coding-agent behavior: file tools, shell, sandbox, event stream, skills, and context mechanisms.

The architecture isolates runtime-specific details behind ACP. New runtime work targets ACP events and LiteLLM model aliases, not a runtime-specific UI or product protocol.

## UI Surfaces

The product has two primary UI surfaces:

- Management dashboard for document type resources, conversion review, Skill Creator, and publishing.
- Three-column authoring workspace for document type/project/session selection, agent timeline, and Markdown preview/edit/export.
