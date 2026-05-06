# Workbench Shell Redesign

## Purpose

Replace the current two-page Workbench/Management split with a single Codex-app-style three-column shell, themed with the Cursor design system in `DESIGN.md`. The redesign is UI-only: the FastAPI backend, workspace contract, timeline mapping, and existing REST endpoints stay unchanged.

## Product Outcome

A user can:

1. Open the app and see one unified shell.
2. Browse and switch between workspaces and their sessions in a left tree.
3. Talk to the agent in a single conversation flow that interleaves user messages, agent messages, semantic event pills, and inline approval/result cards.
4. View, edit, and version the working draft in a multi-tab editor on the right, with the Draft tab pinned.
5. Collapse left and right panels to icon rails for focus, and drag splitters to rebalance.
6. Manage document types from a global settings drawer instead of a separate page.

## Non-Goals

- Backend changes. API, workspace contract, and timeline mapping stay as-is.
- Real-time streaming. Phase 1 refresh-after-action behavior is preserved; SSE/WebSocket is out of scope.
- Dark mode. Token system is structured to allow it later, but only light theme ships now.
- New backend runtime adapter. Existing mock and OpenHands execution adapters keep working unchanged. (The new `docagentRuntime.ts` discussed later is a frontend bridge to `assistant-ui`, not a backend execution adapter.)
- Mobile. Desktop-first; narrow-viewport behavior is best-effort, not validated.

## Information Architecture

```text
DocType (read-only resource pack)
  └── used by: Workspace.brief intent

Workspace  (= existing Task; 1:1 mapping; treated as a versioned repo)
  ├── brief.md
  ├── inputs/
  ├── context/
  ├── draft/
  ├── versions/         # checkpoints
  ├── reviews/
  └── artifacts/
  └── Sessions[]        # multiple agent runs against the same draft
```

- "Workspace" replaces "Task" in user-facing copy. The backend type stays `TaskRecord`.
- DocType management does not appear in the main shell; it lives in a global settings drawer.

## Application Skeleton

```text
┌──────────────────────── Top Bar (36px) ────────────────────────┐
│ DocAgent · {Workspace} / session #{N} · ●status · ⌘K · ⚙       │
├────┬────────────────────────────────┬──────────────────────────┤
│ L  │              C                 │            R             │
│ 树 │      Conversation + Composer   │   Tabbed Editor (📌Draft) │
│240 │              flex              │          ~320            │
└────┴────────────────────────────────┴──────────────────────────┘
```

- Three columns. Splitters between columns are drag-resizable.
- Left and right columns can collapse to a ~48px icon rail. The center column never collapses.
- A click on a rail icon temporarily overlays the panel above the center column. A double click expands the panel back to its previous width.
- Top bar shows current workspace name, session #, status dot, ⌘K command palette trigger, and a gear icon that opens the settings drawer.

## Top Bar

- Height 36px. Background `colors.canvas`. Bottom hairline `colors.hairline`.
- Left side: DocAgent wordmark in `typography.title-sm`, then `· {workspace.brief}` in `body-sm`, then `/ session #{N}` in `muted`, then a status dot using `semantic-success` for running, `muted` for idle, `semantic-error` for failed.
- Right side: `⌘K` chip (`button-secondary`-like, JetBrains Mono 11px) opens the command palette; gear icon opens the settings drawer.

## Left Panel — Workspace Tree

- Section label `WORKSPACES` in `caption-uppercase`, with a `+` button that creates a new workspace (prompts for doc type and brief; calls `POST /tasks`).
- Each workspace is a tree node:
  - Header: `📁 {brief}` with `▾/▸` chevron. Click expands to show children.
  - Children:
    - `💬 #N · status` — sessions, sorted newest first. Active session shows a pinned card.
    - `📁 versions/`, `📁 inputs/`, `📁 context/`, `📁 artifacts/` — open the corresponding folder view in the right panel as a new tab.
- Active workspace and active session are visually distinct: white surface card on canvas-soft background with `hairline-strong` outline.
- Collapsed icon rail shows: `📁` (workspace list overlay trigger), `💬` (jump to active session), `+` (new workspace).
- Empty state: a single dashed card "Create your first workspace" with a `button-primary` CTA.

## Center Panel — Conversation

The center is a single time-ordered stream rendered top-to-bottom inside a scrollable container, with a fixed Composer at the bottom. Implemented on top of `assistant-ui`'s `Thread` + `Composer` primitives, fed by `docagentRuntime` (see Component Architecture).

### Two-Layer Event Model

The conversation has two layers — keep them separate:

1. **Semantic event kinds** (closer to backend domain). The backend `TimelineEvent` model is the source of truth. The implementation must use the exact values from `packages/contracts/docagent_contracts/models.py::SemanticEventKind`:
   - `user_message`, `agent_message`
   - `read_skill`, `analyze_examples`, `convert_input`
   - `build_context`, `extract_style`, `extract_structure`
   - `generate_outline`, `propose_outline`, `approve_outline`
   - `update_draft`, `revise_selection`, `create_checkpoint`
   - `run_checklist`
   - `export_markdown`, `export_docx`, `export_pdf`
   - `approval_requested`, `approval_resolved`
   - `error`

   Future event names such as checklist pass/fail detail events, workspace scan events, or artifact-specific events must be added to the shared contract before `timelinePresentation.ts` depends on them.

2. **Presentation mapping**. `timelinePresentation.ts` is a pure mapper from a `TimelineEvent` to a UI presentation:

   ```ts
   type Presentation =
     | { kind: 'message'; role: 'user' | 'agent'; body: string }
     | { kind: 'pill'; category: 'thinking' | 'grep' | 'read' | 'edit' | 'done'; summary: string; meta?: string }
     | { kind: 'card'; cardType: 'outline' | 'checklist' | 'approval' | 'artifact'; payload: unknown };
   ```

   The five pill categories map to the `colors.timeline-*` tokens in `DESIGN.md`:

   - `thinking` (peach) — agent reasoning / waiting on LLM
   - `grep` (mint) — listing or scanning workspace, examples, inputs
   - `read` (blue) — reading specific files (brief, examples, SKILL.md)
   - `edit` (lavender) — writing outline, draft, context, checkpoints
   - `done` (gold) — phase completion (outline approved, checklist passed, artifact exported)

   The mapper covers each known event kind explicitly. Unknown events fall back to `kind: 'pill'`, `category: 'thinking'` with the raw event name as summary, so an unmapped backend event is visible without being styled wrong.

### Timeline To Thread Mapping

`docagentRuntime.ts` bridges the existing REST/polling API into `assistant-ui`. It does not treat `GET /sessions/{id}/timeline` as an append-only UI list. It maintains an idempotent event store keyed by `TimelineEvent.id`, merges each refreshed timeline by id, then derives assistant-ui thread messages from the sorted event list.

Mapping rules:

- One `TimelineEvent.id` maps to exactly one assistant-ui message or message part.
- `user_message` and `agent_message` become normal text messages using `event.summary` as the body.
- Pill presentations become compact assistant/system message parts, preserving `event.id`, `event.kind`, `event.status`, `event.paths`, and `event.summary` in metadata.
- Card presentations become custom data/tool message parts keyed by `cardType`; the DocAgent card components render from that payload and retain the source `event.id`.
- Refresh after submit, slash command, approval, checklist, export, or draft action merges by event id rather than appending blindly, so repeated polling cannot duplicate messages.
- Event order is stable by backend order from `GET /sessions/{id}/timeline`; if the backend later adds `created_at` to the frontend type, the mapper may use it as a secondary sort key.
- Unknown events still render as fallback pills and keep their raw `event.kind` visible for debugging.

### Inline Cards (DocAgent surfaces)

Cards are rendered as custom message renderers when `timelinePresentation` returns `kind: 'card'`. Visual frame: white surface, `rounded.lg`, `hairline`.

- **Outline card**: title `Outline · waiting for review`, embedded editable Markdown preview, three actions `[Approve] [Edit] [Reject]`. Approve calls `POST /sessions/{id}/outline/approve` with the (possibly edited) outline.
- **Checklist card**: title `Checklist · {pass}/{total}` with each item ✓/✗; failed items expand to show the reason.
- **Artifact card**: title `Artifact · {filename}` with `[Open]` and `[Download]` actions; Open routes to a new Editor tab.
- **Approval card**: used when the agent emits `approval_requested` before a destructive or irreversible action.

### Composer

`assistant-ui`'s composer styled with our tokens.

- Single-line text input that auto-grows up to ~6 lines. Background `colors.surface-card`, `rounded.md`, `hairline-strong` border.
- Right-side send button uses `button-download` style (ink background, canvas text). Cursor Orange is reserved for Approve actions and other primary CTAs.
- Enter sends. Shift+Enter inserts a newline.
- Typing `/` at the start opens an inline command picker; the same picker is reachable via ⌘K (`cmdk`) from anywhere.

### Slash Commands

The composer picker and command palette share one registry exported from `slashCommands.ts`. Commands map to existing API calls so no new endpoints are needed.

| Command | Action |
|---|---|
| `/start` | Start outline loop. `POST /sessions/{id}/loop/start`. |
| `/check` | Run checklist. `POST /sessions/{id}/checklist/run`. |
| `/export` | Export Markdown artifact. `POST /sessions/{id}/artifacts/export-markdown`. |
| `/checkpoint <name?>` | Persist a draft snapshot to `versions/`. Implementation note: Phase 1 has no dedicated checkpoint endpoint; either piggyback on `PUT /tasks/{id}/draft` (mock runtime auto-checkpoints on revise) or add a follow-up endpoint. **Open question**: confirm during planning. |
| `/import <path>` | Upload local input. `POST /tasks/{id}/inputs/text` for text bodies; drag-and-drop file uploads can land in a follow-up. |
| `/files` | Open Files tab in the right panel. |
| `/versions` | Open Versions tab in the right panel. |
| `/diff <vA> <vB>` | Open a two-version diff tab in the right panel. |
| `/help` | Inline help card listing all commands. |

A line that starts with `/` and matches a known command in the registry is parsed at submit time and routed to the corresponding action instead of being sent as a chat message. Unknown `/foo` is sent as plain text. The picker (opened on `/`) is convenience, not the only entry point.

## Right Panel — Tabbed Editor

- Tab bar across the top, implemented with `@radix-ui/react-tabs`. The first tab `📌 Draft` is pinned and not closable. Other tabs are opened by clicking files / versions / artifacts in the left tree, or by slash commands like `/diff` and `/files`.
- Tab content:
  - **Draft tab**:
    - Toolbar: `[Preview] [Source]` mode toggle on the left; `+ Checkpoint` (Cursor Orange) and `last save · Xs ago` on the right.
    - Source mode renders the draft via **CodeMirror 6** with `@codemirror/lang-markdown`, JetBrains Mono 13px, line wrapping on.
    - Preview mode renders Markdown via **react-markdown + remark-gfm + rehype-sanitize** with CursorGothic body type.
    - **Auto-save**: `PUT /tasks/{id}/draft` is debounced 800ms after the last edit. A small spinner / saved state appears in the toolbar.
    - **Selected text affordance**: when the user selects text inside the draft, a floating mini-bar appears with `[💬 Send to chat] [✨ Revise]`.
      - Send to chat injects the selection as a Markdown blockquote into the composer.
      - Revise calls `POST /sessions/{id}/revision/selection` directly.
  - **File tab**: read-only file content rendered with CodeMirror in read-only mode (or `MarkdownPreview` if the file is `.md`). Path shown in the tab title.
  - **Version tab**: full text of one version in read-only CodeMirror, no editing.
  - **Diff tab**: two-pane line diff (left = older version, right = newer or current draft). Phase 1 implementation uses `jsdiff` (`diff` npm package) to compute line diffs and renders them with our own minimal two-pane component. Monaco diff editor is reserved as a Phase 2 option if the diff UX needs richer features.
  - **Artifact tab**: rendered preview of an exported Markdown artifact (via `MarkdownPreview`), plus a `[Reveal in folder]` action.
- Collapsed icon rail shows: `📌` (Draft), `📁` (File list), `🕘` (Versions).

## Settings / Management Drawer

- Triggered by the gear icon in the top bar. Slides in from the right at ~520px width with a `hairline` left edge. Non-modal — clicking outside closes it; `Esc` closes it.
- Contents replace the current `ManagementPage`:
  - Section: **Document Types**. List of doc types with selectable detail. Detail shows the resource groups (best-practice examples, specs, checklists, export references, SKILL.md) using the existing read-only layout.
  - Section: **Skill Creator** — Phase 2 placeholder retained as-is.
  - Section: **Runtime** — read-only display of current runtime adapter (mock vs OpenHands) for transparency. No interactive switching in this redesign.
- Drawer state lives in component state; closing returns the user to the workspace.

## Visual System Mapping

All colors and typography follow `DESIGN.md` (Cursor warm-cream editorial). Token usage by surface:

| DESIGN.md token | Surface |
|---|---|
| `colors.canvas` #f7f7f4 | Top bar, conversation background, drawer body |
| `colors.canvas-soft` #fafaf7 | Left panel, right panel |
| `colors.surface-card` #ffffff | Inline cards, active tab content area, draft editor |
| `colors.surface-strong` #e6e5e0 | Pill backgrounds for non-timeline badges |
| `colors.ink` #26251e | Primary text |
| `colors.body` #5a5852 | Secondary text |
| `colors.muted` #807d72 | Timestamps, status text, file paths |
| `colors.hairline` #e6e5e0 | All 1px dividers |
| `colors.hairline-strong` #cfcdc4 | Active card outlines, input borders |
| `colors.primary` #f54e00 | Outline `Approve`, `+ Checkpoint`, primary command palette CTA. **Used scarcely**. |
| `colors.timeline-*` | Conversation event pills, mapped to event kinds above |
| `typography.body-md` | Default conversation text |
| `typography.title-md` / `title-sm` | Card titles, panel headers |
| `typography.caption-uppercase` | Section labels (`WORKSPACES`, `Outline · …`) |
| `typography.code` | Draft source view, file paths, slash commands, timestamps |
| `rounded.md` 8px | Buttons, inputs |
| `rounded.lg` 12px | Cards |
| `rounded.pill` | Timeline pills, badges |

Fonts: Inter 400 with letter-spacing -1.5% as the CursorGothic fallback (CursorGothic is licensed). JetBrains Mono on every code surface.

## Component Architecture

Generic interaction primitives (chat thread, composer, resizable panels, tree, code editor, command palette, drawer, tabs) come from mature React libraries. DocAgent owns only the pieces that are specific to it: semantic event mapping, the inline cards (Outline, Checklist, Approval, Artifact), the slash command registry, and the runtime adapter that bridges our REST/polling API to the chosen libraries.

| Surface | Library | Notes |
|---|---|---|
| Conversation thread + composer | `@assistant-ui/react` | Uses a custom `ChatModelAdapter` (not streaming). `docagentRuntime.ts` maps refreshed timeline events idempotently into assistant-ui messages/message parts. Inline cards render from custom data/tool parts keyed off `timelinePresentation`. |
| Three-column shell + collapse + splitter | `react-resizable-panels` | `Panel` with `collapsible`, `defaultSize`, `minSize`, plus persistence to `localStorage`. |
| Workspace tree | `react-arborist` | Virtualized tree; we provide the data adapter that flattens `tasks → sessions/folders`. |
| Draft / file / version source view | `CodeMirror 6` via `@uiw/react-codemirror` | `@codemirror/lang-markdown`, line wrapping, read-only flag for file/version views. |
| Markdown preview | `react-markdown` + `remark-gfm` + `rehype-sanitize` | Styled with `typography.body-md`. Sanitizer prevents XSS from agent-generated Markdown. |
| Diff view | `diff` (jsdiff) for Phase 1 | Hand-rendered two-pane line diff. Monaco diff editor is a Phase 2 option if richer diff UX is needed. |
| Command palette | `cmdk` | Same registry as the composer slash menu. |
| Settings drawer | `@radix-ui/react-dialog` (Sheet pattern) | Non-modal slide-in from right. |
| Tabs (right panel) | `@radix-ui/react-tabs` | Pinned `📌 Draft` is the first tab and not closable. |
| Tooltips, dropdowns, focus management | Radix primitives | As needed. |
| Icons | `lucide-react` | Already in the project. |

We deliberately do NOT pull in shadcn/ui's pre-styled component set. shadcn ships a Tailwind theme that conflicts with the Cursor token system in `DESIGN.md`. Instead, we use Radix headless primitives (and `cmdk`, which is already headless) directly and style them with our tokens.

`@assistant-ui/react` is adopted for its runtime adapter abstraction, not for streaming. Phase 1 keeps the existing FastAPI REST endpoints and refresh-after-action behavior. The adapter (`docagentRuntime.ts`) implements `ChatModelAdapter` over our existing API client and re-fetches `GET /sessions/{id}/timeline` after each user turn or action. The adapter owns the event-id merge store and converts `timelinePresentation` outputs into assistant-ui text/data/tool parts. If we later move to SSE/WebSocket (out of scope here), the same runtime contract can switch to streaming without changing UI components — and at that point the [AG-UI protocol](https://github.com/ag-ui-protocol/ag-ui) is a natural fit to evaluate.

## Code Layout

The new shell replaces `pages/` entirely.

```text
apps/web/src/
  App.tsx                     # mounts <AppShell/>, wires runtime + theme
  api.ts                      # unchanged
  types.ts                    # unchanged
  shell/
    AppShell.tsx              # react-resizable-panels composition
    TopBar.tsx
    SettingsDrawer.tsx        # Radix Dialog (Sheet pattern)
    CommandPalette.tsx        # cmdk
    panes/
      WorkspacePane.tsx       # react-arborist adapter
      ConversationPane.tsx    # assistant-ui Thread adapter
      EditorPane.tsx          # Radix Tabs + per-tab content
    conversation/
      docagentRuntime.ts      # bridges REST/polling API to assistant-ui ChatModelAdapter
      timelinePresentation.ts # TimelineEvent → UI presentation (message | pill | card)
      slashCommands.ts        # shared registry for composer picker + cmdk
      cards/
        OutlineCard.tsx
        ChecklistCard.tsx
        ArtifactCard.tsx
        ApprovalCard.tsx
    editor/
      DraftEditor.tsx         # CodeMirror 6 + Markdown lang
      MarkdownPreview.tsx     # react-markdown + remark-gfm + rehype-sanitize
      DiffViewer.tsx          # jsdiff-backed two-pane line diff (Phase 1)
      tabs/
        DraftTab.tsx
        FileTab.tsx
        VersionTab.tsx
        DiffTab.tsx
        ArtifactTab.tsx
      useTabs.ts
      useAutoSave.ts
    state/
      useWorkspaces.ts
      useTimeline.ts
      useCollapse.ts          # persistence wrapper around react-resizable-panels
    theme/
      tokens.css              # all DESIGN.md tokens as CSS variables
      reset.css
      typography.css
      assistant-ui.css        # overrides assistant-ui defaults to Cursor tokens
```

`pages/ManagementPage.tsx` and `pages/WorkbenchPage.tsx` are deleted.

### New runtime dependencies

Added to `apps/web/package.json`:

- `@assistant-ui/react`
- `react-resizable-panels`
- `react-arborist`
- `@uiw/react-codemirror` `codemirror` `@codemirror/lang-markdown` `@codemirror/state` `@codemirror/view`
- `react-markdown` `remark-gfm` `rehype-sanitize`
- `cmdk`
- `@radix-ui/react-dialog` `@radix-ui/react-tabs` `@radix-ui/react-tooltip`
- `diff` (jsdiff)

Exact versions and React 19 compatibility are confirmed during planning before installation.

## Migration Strategy — In-Place Rewrite

- The current UI (~400 lines of React) is rewritten in-place. There is no `?ui=v2` flag. The repo holds one canonical UI per commit.
- Each commit on the redesign branch must keep the app bootable, even if not feature-complete. The recommended sequence is shell scaffold → left tree (read-only) → editor pane (draft only) → conversation pane (basic chat) → inline cards → slash commands → settings drawer → empty/loading states.
- After the redesign branch lands, delete `apps/web/src/pages/` in the same merge.

## Behavior Notes

- **Auto-save vs explicit save**: The "Save" button is removed. The draft saves on debounce. Manual snapshots are taken via `+ Checkpoint` (which lands a row in `versions/`).
- **Revise selection** still uses `api.reviseSelection` and produces a checkpoint, matching current Phase 2 behavior.
- **Outline editing inside the card** is local state until `Approve` is clicked; on approve, the edited outline is sent as `outline_markdown`.
- **Runtime adapter**: `docagentRuntime.ts` implements `assistant-ui`'s `ChatModelAdapter` over our existing REST client. On user submit, it `POST`s the message and re-fetches `GET /sessions/{id}/timeline`; the new events flow through `timelinePresentation` and into the `Thread`. This keeps the UI on a single, library-level data contract while the backend stays REST/polling.
- **Approval polling**: when an action returns, the conversation refreshes with `GET /sessions/{id}/timeline`. There is no SSE in this redesign; if perceived latency is bad, surface a small "Agent working…" indicator instead of changing data flow.
- **Slash command execution**: a line that starts with `/` and matches a known command in the registry is parsed at submit time and routed to the corresponding action instead of being sent as a chat message. Unknown `/foo` is sent as plain text. The picker (opened on `/`) is convenience, not the only entry point.
- **Session vs draft scope**: the draft lives at the workspace level. Switching sessions inside the same workspace does not change the draft. Switching workspaces does.
- **Auto-create session on first message**: if the active workspace has no live session and the user sends a message or invokes a slash command that needs a session, the shell calls `POST /tasks/{id}/sessions` first, then proceeds. No manual "create session" button is needed in the new shell.

## Empty States

- **No workspaces**: left panel shows the dashed "Create your first workspace" card; center shows a quiet hero with the same CTA in `button-primary`; right panel shows "Open or create a workspace to see the draft" in muted text.
- **Workspace selected, no session yet**: center shows the brief as the first stream item plus a hint "Send a message or run `/start` to begin"; the composer is enabled.
- **Workspace selected, no draft yet**: Draft tab shows a placeholder "The draft will appear here after the agent generates it"; `+ Checkpoint` is disabled until a draft exists.

## Persisted UI State

`localStorage` persists, scoped per app:

- Left and right panel widths (px).
- Left and right collapsed state (boolean).
- The last active workspace and session IDs (so reload returns to the same place).
- Draft tab mode (`preview` vs `source`).

## Verification

When the redesign branch is implementation-ready, smoke-verify with:

```powershell
.\start-dev.cmd
```

Then in a browser at `http://127.0.0.1:5173`:

1. Create a new workspace via the empty-state CTA.
2. Send a message in the conversation.
3. Run `/start`, edit the outline in the inline card, click Approve.
4. Run `/check`, observe the checklist card.
5. Open Files tab from the left tree, then open a version and `/diff` it against current draft.
6. Click the gear to open the settings drawer; verify doc-type list renders.
7. Collapse left then right panels; resize splitters; reload — verify state persistence (panel widths can be in `localStorage`).

Add a small Vitest or Playwright smoke check covering at least: shell mounts, tree renders, composer submits, draft auto-save fires.

## Open Questions

- **Checkpoint endpoint**: Phase 2 created checkpoints implicitly during revise. The new `+ Checkpoint` button needs an explicit endpoint or must reuse an existing flow. Decide during planning.
- **Diff library**: Phase 1 assumes `jsdiff` (`diff` npm package) for a lightweight two-pane line diff. Confirm during planning that `jsdiff` covers our needs (line + word-level highlighting) and that we don't need Monaco's full diff editor yet.
- **assistant-ui custom-renderer surface**: confirm during planning that `@assistant-ui/react` exposes a stable extension point for "render this message as a custom React component when its kind is X" (custom message parts / content types) without forcing a specific MIME or schema. If the API is too constrained, fall back to using assistant-ui only for the composer + scroll container and rendering the stream ourselves.
- **CodeMirror bundle size**: CM6 plus the Markdown language adds a non-trivial chunk to the web bundle. If size becomes a problem, fall back to a plain `<textarea>` for source mode and keep `react-markdown` for preview. Decide during planning if we want a size budget assertion.
- **Drag-and-drop file upload**: Phase 1 only has text input upload. File drop into the conversation can be a follow-up; the spec captures `/import <path>` only.
- **Webfont**: ship Inter via a self-hosted font file or a CDN; CursorGothic is intentionally not licensed for this project.

## Out-of-Scope Follow-Ups

- Real-time agent streaming (SSE/WebSocket).
- Dark mode.
- Multi-window or "open Draft in new window".
- Mobile / narrow-viewport optimization beyond degraded usability.
