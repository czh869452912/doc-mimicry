# Architecture

DocAgent Workbench is organized around a coding-agent runtime operating inside a document workspace.

```text
React Workbench UI
  -> FastAPI Product Backend
    -> Coding-Agent Runtime Adapter
      -> Agent Runtime and Sandbox
        -> Task Workspace
          -> DocType Skill Pack
```

## Core Boundaries

### UI

`apps/web` owns the user experience: chat, timeline, draft preview, diff, version list, approvals, and export actions. It should not encode document writing workflows.

### Product Backend

`services/api` owns product state: users, teams, tasks, document type configuration, workspace initialization, versions, artifacts, audit records, and runtime adapter integration. It should not make writing decisions for the agent.

### Agent Runtime

The runtime should feel like Claude Code for documents: free-form conversation, file tools, event stream, sandbox, context management, user interrupt, and iterative edits.

OpenHands is the first runtime candidate, but the backend should keep a runtime adapter boundary.

### Workspace Contract

The workspace is the agent's durable working memory. It contains briefs, inputs, context files, drafts, versions, reviews, artifacts, and logs.

See `docs/architecture/workspace-contract.md`.

### Document Type Packs

`doc-types` contains examples, specs, checklists, and `SKILL.md` files. These teach the agent how a document type is organized and narrated.

They are not fixed workflows and not content templates.

### Shared Packages

`packages` contains contracts and helpers that must stay independent of any one UI or runtime implementation.

Dependency direction should be:

```text
apps/web -> packages/contracts
services/api -> packages/*
agent -> packages/contracts
tools -> packages/workspace
packages/* -> no app/service imports
```

## Non-Goals For Phase 0

- Per-document-type workflow engines.
- Semantic RAG as the main writing strategy.
- High-fidelity Word layout reproduction.
- Full enterprise RBAC.
- Direct fork of an existing coding-agent UI as the product UI.

