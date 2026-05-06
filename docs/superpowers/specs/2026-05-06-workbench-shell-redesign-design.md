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
- New runtime adapter. Existing mock and OpenHands adapters keep working unchanged.
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

The center is a single time-ordered stream rendered top-to-bottom inside a scrollable container, with a fixed Composer at the bottom.

### Stream Items

Each timeline event rendered by the API maps to one of:

- **User message**: 14px ink, no avatar prefix, soft-left alignment.
- **Agent message**: 14px body, with a small `🤖` glyph.
- **Event pill row**: a single line containing a colored timeline pill plus a one-line summary. Pill color by event kind:
  - `THINKING` `colors.timeline-thinking` — agent reasoning / waiting on LLM
  - `GREP` `colors.timeline-grep` — listing or searching workspace
  - `READ` `colors.timeline-read` — reading brief, examples, SKILL.md, inputs
  - `EDIT` `colors.timeline-edit` — writing outline, draft, context, checkpoint
  - `DONE` `colors.timeline-done` — stage completion (outline approved, draft generated, checklist passed, exported)
- **Inline cards** (white surface, `rounded.lg`, `hairline`):
  - **Outline card**: title `Outline · waiting for review`, embedded editable Markdown preview, three actions `[Approve] [Edit] [Reject]`. Approve maps to `POST /sessions/{id}/outline/approve` with the (possibly edited) outline.
  - **Checklist card**: title `Checklist · {pass}/{total}` with each item ✓/✗; failed items expand to show the reason.
  - **Artifact card**: title `Artifact · {filename}` with `[Open]` and `[Download]` actions, where Open routes to a new Editor tab.
  - **Approval card** (general purpose): used when the agent asks for explicit confirmation before a destructive or irreversible action.

### Composer

- Single-line text input that auto-grows up to ~6 lines. Background `colors.surface-card`, `rounded.md`, `hairline-strong` border.
- Right-side send button uses `button-download` style (ink background, canvas text). Cursor Orange is reserved for the Approve actions and other primary CTAs.
- Enter sends. Shift+Enter inserts a newline.
- Typing `/` at the start opens an inline command picker; the same picker is reachable via ⌘K from anywhere.

### Slash Commands

The composer and command palette share the same registry. Commands map to existing API calls so no new endpoints are needed.

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

## Right Panel — Tabbed Editor

- Tab bar across the top. The first tab `📌 Draft` is pinned and not closable. Other tabs are opened by clicking files / versions / artifacts in the left tree, or by slash commands like `/diff` and `/files`.
- Tab content:
  - **Draft tab**:
    - Toolbar: `[Preview] [Source]` mode toggle on the left; `+ Checkpoint` (Cursor Orange) and `last save · Xs ago` on the right.
    - Source mode renders the draft as JetBrains Mono 13px in a textarea.
    - Preview mode renders Markdown with CursorGothic body type.
    - **Auto-save**: `PUT /tasks/{id}/draft` is debounced 800ms after the last edit. A small spinner / saved state appears in the toolbar.
    - **Selected text affordance**: when the user selects text inside the draft, a floating mini-bar appears with `[💬 Send to chat] [✨ Revise]`.
      - Send to chat injects the selection as a Markdown blockquote into the composer.
      - Revise calls `POST /sessions/{id}/revision/selection` directly.
  - **File tab**: read-only file content. Path shown in the tab title.
  - **Version tab**: full text of one version, no editing.
  - **Diff tab**: two-pane diff (left = older version, right = newer or current draft) using a line-level diff. Initial implementation can use a small dependency or hand-rolled line diff.
  - **Artifact tab**: rendered preview of an exported Markdown artifact, plus a `[Reveal in folder]` action.
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

## Code Layout

The new shell replaces `pages/` entirely.

```text
apps/web/src/
  App.tsx               # mounts <AppShell/>
  api.ts                # unchanged
  types.ts              # unchanged
  shell/
    AppShell.tsx        # 3-col grid + collapse + splitter
    TopBar.tsx
    SettingsDrawer.tsx
    CommandPalette.tsx
    panes/
      WorkspacePane.tsx
      ConversationPane.tsx
      EditorPane.tsx
    conversation/
      EventPill.tsx
      OutlineCard.tsx
      ChecklistCard.tsx
      ArtifactCard.tsx
      ApprovalCard.tsx
      Composer.tsx
      slashCommands.ts
    editor/
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
      useCollapse.ts
    theme/
      tokens.css        # all DESIGN.md tokens as CSS variables
      reset.css
      typography.css
```

`pages/ManagementPage.tsx` and `pages/WorkbenchPage.tsx` are deleted.

## Migration Strategy — In-Place Rewrite

- The current UI (~400 lines of React) is rewritten in-place. There is no `?ui=v2` flag. The repo holds one canonical UI per commit.
- Each commit on the redesign branch must keep the app bootable, even if not feature-complete. The recommended sequence is shell scaffold → left tree (read-only) → editor pane (draft only) → conversation pane (basic chat) → inline cards → slash commands → settings drawer → empty/loading states.
- After the redesign branch lands, delete `apps/web/src/pages/` in the same merge.

## Behavior Notes

- **Auto-save vs explicit save**: The "Save" button is removed. The draft saves on debounce. Manual snapshots are taken via `+ Checkpoint` (which lands a row in `versions/`).
- **Revise selection** still uses `api.reviseSelection` and produces a checkpoint, matching current Phase 2 behavior.
- **Outline editing inside the card** is local state until `Approve` is clicked; on approve, the edited outline is sent as `outline_markdown`.
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
- **Diff library**: hand-rolled line diff vs a small dependency (e.g. `diff`, `jsdiff`). Decide during planning.
- **Drag-and-drop file upload**: Phase 1 only has text input upload. File drop into the conversation can be a follow-up; the spec captures `/import <path>` only.
- **Webfont**: ship Inter via a self-hosted font file or a CDN; CursorGothic is intentionally not licensed for this project.

## Out-of-Scope Follow-Ups

- Real-time agent streaming (SSE/WebSocket).
- Dark mode.
- Multi-window or "open Draft in new window".
- Mobile / narrow-viewport optimization beyond degraded usability.
