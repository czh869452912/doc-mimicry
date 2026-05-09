# Assistant-UI 集成修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 assistant-ui 全链路接入中的 9 个已知问题，确保前端组件正确性、后端 API 契约一致性、以及测试可靠性。

**Architecture:** 保持现有 FastAPI 路由模块和 assistant-ui runtime/primitive 集成不变。修复集中在：Pydantic 模型字段匹配、React 组件生命周期管理、状态同步、异步竞态保护、以及边界测试覆盖。

**Tech Stack:** React 19, @assistant-ui/react 0.12.28, Vitest, FastAPI, Pydantic, pytest

---

## 文件结构

**后端（services/api）:**
- `docagent_api/response_models.py` — TaskResponse Pydantic 模型定义
- `tests/test_sse.py` — SSE 端点测试（需修复请求体）

**前端（apps/web）:**
- `src/shell/assistant/DocAgentThread.tsx` — 消息线程渲染（useMemo 反模式）
- `src/shell/assistant/DocAgentComposer.tsx` — 输入编辑器（双状态管理）
- `src/shell/conversation/cards/OutlineCard.tsx` — 大纲卡片（异步竞态）
- `src/shell/assistant/docAgentAttachmentAdapter.ts` — 附件适配器（remove 空实现）
- `src/shell/assistant/useDocAgentAssistantRuntime.ts` — runtime hook（unstable_capabilities）
- `src/shell/panes/ConversationPane.tsx` — 会话面板（inputForReload 边界）
- `src/shell/conversation/docagentRuntime.ts` — timeline 工具函数（dedup 简化）
- `package.json` — 依赖版本锁定

**测试（apps/web）:**
- `src/shell/panes/__tests__/ConversationPane.test.tsx` — 新增 reload 边界测试
- `src/shell/__tests__/docagentRuntime.test.ts` — 替换 dedup 测试

---

### Task 1: 修复 test_sse.py 测试失败（TaskResponse 模型字段不匹配）

**问题:** `TaskResponse` 要求 `title: str` 和 `description: str` 为必填，但测试请求只发送 `brief`。

**Files:**
- Modify: `services/api/tests/test_sse.py`

- [ ] **Step 1: 修改 test_sse.py 中的请求体**

在 `services/api/tests/test_sse.py` 中，将两个测试函数的请求体从：
```python
task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "SSE test"}).json()
```
改为：
```python
task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "SSE test", "title": "SSE test", "description": "SSE test"}).json()
```

需要修改两处：
1. `test_stream_timeline_returns_sse_content_type` 函数第 29 行
2. `test_stream_timeline_sends_existing_events` 函数第 41 行

- [ ] **Step 2: 运行修复后的测试**

```bash
cd services/api
python -m pytest tests/test_sse.py -v
```

Expected: 4/4 tests PASS（包括 `test_stream_timeline_unknown_session_returns_404`）

- [ ] **Step 3: Commit**

```bash
git add services/api/tests/test_sse.py
git commit -m "fix: add title and description to SSE test requests"
```

---

### Task 2: 修复 DocAgentThread 使用 useMemo 创建组件

**问题:** 在 render 阶段用 `useMemo` 动态创建 `AssistantMessageComponent` 函数，导致 React 将其视为新组件类型而卸载/重新挂载子树。

**Files:**
- Modify: `apps/web/src/shell/assistant/DocAgentThread.tsx`

- [ ] **Step 1: 将 AssistantMessage 改为顶层组件定义**

修改 `apps/web/src/shell/assistant/DocAgentThread.tsx`：

删除 `DocAgentThread` 组件内的 `AssistantMessageComponent` useMemo：
```tsx
// 删除这整个 useMemo
const AssistantMessageComponent = useMemo(
  () =>
    function AssistantMessageComponent() {
      return (
        <AssistantMessage
          activeSessionId={activeSessionId}
          taskId={taskId}
          onApproved={onApproved}
          onOpenPath={onOpenPath}
          onReloadMessage={onReloadMessage}
        />
      );
    },
  [activeSessionId, taskId, onApproved, onOpenPath, onReloadMessage],
);
```

改为在 `ThreadPrimitive.Messages` 中直接使用稳定的 `AssistantMessage` 组件，并通过 assistant-ui 的 context 传递 props：
```tsx
// 在文件顶部添加类型
interface AssistantMessageProps {
  activeSessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  onReloadMessage: (messageId: string | null) => Promise<void>;
}

// 修改 ThreadPrimitive.Messages
<ThreadPrimitive.Messages
  components={{
    UserMessage: UserMessage,
    AssistantMessage: AssistantMessage,
  }}
/>
```

- [ ] **Step 2: 使用 React Context 传递动态 props**

创建局部 context：
```tsx
// 在 DocAgentThread.tsx 顶部添加
import { createContext, useContext } from "react";

const DocAgentThreadContext = createContext<{
  activeSessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  onReloadMessage: (messageId: string | null) => Promise<void>;
} | null>(null);

function useDocAgentThreadContext() {
  const ctx = useContext(DocAgentThreadContext);
  if (!ctx) throw new Error("DocAgentThreadContext not found");
  return ctx;
}
```

修改 `DocAgentThread` 组件：
```tsx
export function DocAgentThread({...props}: DocAgentThreadProps) {
  return (
    <DocAgentThreadContext.Provider value={{
      activeSessionId: props.activeSessionId,
      taskId: props.taskId,
      onApproved: props.onApproved,
      onOpenPath: props.onOpenPath,
      onReloadMessage: props.onReloadMessage,
    }}>
      <ThreadPrimitive.Root className="aui-thread">
        {/* ... existing viewport code ... */}
        <ThreadPrimitive.Messages
          components={{
            UserMessage: UserMessage,
            AssistantMessage: AssistantMessage,
          }}
        />
        {/* ... status code ... */}
      </ThreadPrimitive.Root>
    </DocAgentThreadContext.Provider>
  );
}
```

修改 `AssistantMessage` 组件：
```tsx
function AssistantMessage() {
  const { activeSessionId, taskId, onApproved, onOpenPath, onReloadMessage } = useDocAgentThreadContext();
  
  return (
    <MessagePrimitive.Root className="aui-message aui-message--assistant">
      <MessagePrimitive.Content
        components={{
          Text: TextPart,
          data: {
            by_name: {
              "docagent.tool-call": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.outline-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.checklist-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.artifact-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.approval-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
            },
          },
        }}
      />
      <MessageActions canReload onReloadMessage={onReloadMessage} />
    </MessagePrimitive.Root>
  );
}
```

- [ ] **Step 3: 运行现有测试确保无回归**

```bash
cd apps/web
npx vitest run src/shell/assistant/__tests__/DocAgentMessageParts.test.tsx src/shell/panes/__tests__/ConversationPane.test.tsx --reporter=verbose
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/shell/assistant/DocAgentThread.tsx
git commit -m "fix: replace useMemo component creation with stable component + context"
```

---

### Task 3: 修复 DocAgentComposer 双状态管理

**问题:** Composer 同时维护 `query` state 和 `aui.composer().setText()`，两套状态可能不同步。

**Files:**
- Modify: `apps/web/src/shell/assistant/DocAgentComposer.tsx`

- [ ] **Step 1: 移除独立的 query state，改用响应式 composer text**

修改 `apps/web/src/shell/assistant/DocAgentComposer.tsx`：

删除 `useState`：
```tsx
// 删除
const [query, setQuery] = useState("");
```

使用 `useAuiState` 订阅 composer text（`aui.composer()` 暴露方法，当前文本在 state 中）：
```tsx
const aui = useAui();
const query = useAuiState((state) => state.composer.text);
```

修改 `onChange` handler：
```tsx
// 删除 onChange prop；ComposerPrimitive.Input 会同步 assistant-ui composer state
```

修改 `selectCommand`：
```tsx
function selectCommand(command: string) {
  const nextValue = `${command} `;
  aui.composer().setText(nextValue);
  inputRef.current?.focus();
  // 不需要 setQuery，因为 query 直接从 useAuiState 读取
}
```

修改 send button 的 `onClick`：
```tsx
<ComposerPrimitive.Send className="aui-send-button" disabled={disabled}>
  <Send size={15} />
</ComposerPrimitive.Send>
// 删除 onClick={() => setQuery("")}
```

- [ ] **Step 2: 运行 Composer 测试**

```bash
cd apps/web
npx vitest run src/shell/assistant/__tests__/DocAgentComposer.test.tsx --reporter=verbose
```

Expected: All 3 tests PASS

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shell/assistant/DocAgentComposer.tsx
git commit -m "fix: unify composer state with assistant-ui state"
```

---

### Task 4: 修复 OutlineCard 异步竞态保护

**问题:** `useEffect` 中调用 `api.getWorkspaceFile` 没有取消信号和竞态保护。

**Files:**
- Modify: `apps/web/src/shell/conversation/cards/OutlineCard.tsx`

- [ ] **Step 1: 添加取消信号和竞态保护**

修改 `apps/web/src/shell/conversation/cards/OutlineCard.tsx`：

```tsx
useEffect(() => {
  if (!taskId) return;
  let cancelled = false;
  
  api
    .getWorkspaceFile(taskId, outlinePath)
    .then((file) => {
      if (!cancelled) setOutline(file.content);
    })
    .catch(() => {
      if (!cancelled) setOutline(event.summary);
    });
  
  return () => {
    cancelled = true;
  };
}, [event.summary, outlinePath, taskId]);
```

- [ ] **Step 2: 运行相关测试**

```bash
cd apps/web
npx vitest run src/shell/assistant/__tests__/DocAgentMessageParts.test.tsx --reporter=verbose
```

Expected: All tests PASS（OutlineCard 在 message parts 测试中被渲染）

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shell/conversation/cards/OutlineCard.tsx
git commit -m "fix: add cancellation guard to OutlineCard async file load"
```

---

### Task 5: 替换 MessageActions 原生 button 为 assistant-ui Primitive

**问题:** Reload 动作使用了原生 HTML `<button>` 而不是 `ActionBarPrimitive.Reload`。使用 primitive 时必须让 assistant-ui runtime 的 `onReload` 单独处理 reload，不能再额外调用 `onReloadMessage`，否则一次点击会触发两次 reload。

**Files:**
- Modify: `apps/web/src/shell/assistant/DocAgentThread.tsx`

- [ ] **Step 1: 使用 ActionBarPrimitive.Reload 替换原生 button**

修改 `apps/web/src/shell/assistant/DocAgentThread.tsx`：

```tsx
function MessageActions({
  canReload = false,
}: {
  canReload?: boolean;
}) {
  return (
    <ActionBarPrimitive.Root className="aui-message-actions">
      <ActionBarPrimitive.Copy className="aui-message-action" aria-label="Copy text">
        Copy
      </ActionBarPrimitive.Copy>
      {canReload && (
        <ActionBarPrimitive.Reload className="aui-message-action" aria-label="Reload response">
          Reload
        </ActionBarPrimitive.Reload>
      )}
    </ActionBarPrimitive.Root>
  );
}
```

同时删除 `MessageActions` 调用处的 `onReloadMessage` prop。`useExternalStoreRuntime` 已经通过 `onReload` 收到 assistant-ui 计算出的 parent message id，并委托给 `ConversationPane.reloadInput`。

- [ ] **Step 2: 运行测试**

```bash
cd apps/web
npx vitest run src/shell/panes/__tests__/ConversationPane.test.tsx --reporter=verbose
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shell/assistant/DocAgentThread.tsx
git commit -m "fix: use ActionBarPrimitive.Reload instead of native button for reload action"
```

---

### Task 6: 锁定 @assistant-ui/react 版本

**问题:** `unstable_capabilities` 是 assistant-ui 的不稳定 API，patch 版本可能改变。

**Files:**
- Modify: `apps/web/package.json`

- [ ] **Step 1: 将版本从 ^ 改为固定版本**

修改 `apps/web/package.json`：

```json
"@assistant-ui/react": "0.12.28"
```

（移除 `^` 前缀）

- [ ] **Step 2: 重新安装依赖**

```bash
cd apps/web
npm install
```

Expected: `package-lock.json` 更新，版本锁定为 `0.12.28`

- [ ] **Step 3: 运行测试确认无回归**

```bash
npx vitest run --reporter=verbose
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "chore: pin @assistant-ui/react to exact version 0.12.28"
```

---

### Task 7: 明确 attachmentAdapter.remove() 的 no-op 语义

**问题:** 当用户在 composer 中移除附件 chip 时，`remove()` 不做任何操作但缺少明确契约。已发送的 imported workspace file 应继续作为 workspace context 保留；remove 只代表从 composer 附件列表移除，不删除 workspace 文件，也不记录可能包含敏感信息的附件名到 console。

**Files:**
- Modify: `apps/web/src/shell/assistant/docAgentAttachmentAdapter.ts`

- [ ] **Step 1: 明确 remove 为有意 no-op**

修改 `apps/web/src/shell/assistant/docAgentAttachmentAdapter.ts`：

```tsx
async remove() {
  // The imported workspace file remains as context once a send has completed.
}
```

不要添加 `console.log` 记录附件名；文件名可能包含用户或企业上下文信息。

- [ ] **Step 2: 运行附件测试**

```bash
cd apps/web
npx vitest run src/shell/assistant/__tests__/docAgentAttachmentAdapter.test.ts --reporter=verbose
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shell/assistant/docAgentAttachmentAdapter.ts
git commit -m "docs: clarify attachment remove retains workspace context"
```

---

### Task 8: 为 inputForReload 添加边界测试

**问题:** `inputForReload` 逻辑复杂但缺乏单元测试覆盖。

**Files:**
- Create: `apps/web/src/shell/panes/__tests__/inputForReload.test.ts`
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`（提取函数）

- [ ] **Step 1: 将 inputForReload 提取为独立导出函数**

修改 `apps/web/src/shell/panes/ConversationPane.tsx`，将 `inputForReload` 移到文件底部并添加 `export`：

```tsx
export function inputForReload(events: TimelineEvent[], parentMessageId: string | null) {
  const parentIndex = parentMessageId
    ? events.findIndex((event) => event.id === parentMessageId)
    : events.length;
  if (parentIndex >= 0 && parentIndex < events.length) {
    const parentEvent = events[parentIndex];
    if (parentEvent.kind === "user_message" && parentEvent.summary.trim()) return parentEvent.summary;
  }
  const endIndex = parentIndex >= 0 ? parentIndex : events.length;
  for (let index = endIndex - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.kind === "user_message" && event.summary.trim()) return event.summary;
  }
  return null;
}
```

- [ ] **Step 2: 编写边界测试**

创建 `apps/web/src/shell/panes/__tests__/inputForReload.test.ts`：

```ts
import { describe, expect, it } from "vitest";
import type { TimelineEvent } from "../../../types";
import { inputForReload } from "../ConversationPane";

function userEvent(id: string, summary: string): TimelineEvent {
  return {
    id,
    actor: "user",
    kind: "user_message",
    raw_event_id: null,
    session_id: "s1",
    summary,
    paths: [],
    status: "succeeded",
    task_id: "t1",
  };
}

function agentEvent(id: string, summary: string): TimelineEvent {
  return {
    id,
    actor: "agent",
    kind: "agent_message",
    raw_event_id: null,
    session_id: "s1",
    summary,
    paths: [],
    status: "succeeded",
    task_id: "t1",
  };
}

describe("inputForReload", () => {
  it("returns null for empty timeline", () => {
    expect(inputForReload([], null)).toBeNull();
  });

  it("returns last user message when parentMessageId is null", () => {
    const events = [
      userEvent("u1", "First message"),
      agentEvent("a1", "Agent reply"),
      userEvent("u2", "Last message"),
    ];
    expect(inputForReload(events, null)).toBe("Last message");
  });

  it("returns parent message when it is a user message", () => {
    const events = [
      userEvent("u1", "First"),
      userEvent("u2", "Target"),
      agentEvent("a1", "Reply"),
    ];
    expect(inputForReload(events, "u2")).toBe("Target");
  });

  it("skips agent messages and finds previous user message", () => {
    const events = [
      userEvent("u1", "First"),
      agentEvent("a1", "Agent"),
      agentEvent("a2", "Another agent"),
    ];
    expect(inputForReload(events, "a2")).toBe("First");
  });

  it("returns null when no user message found", () => {
    const events = [agentEvent("a1", "Only agent")];
    expect(inputForReload(events, null)).toBeNull();
  });

  it("falls back to the latest user message when parentMessageId is not found", () => {
    const events = [userEvent("u1", "Only")];
    expect(inputForReload(events, "nonexistent")).toBe("Only");
  });

  it("skips empty user messages", () => {
    const events = [
      userEvent("u1", "   "),
      userEvent("u2", "Valid"),
    ];
    expect(inputForReload(events, null)).toBe("Valid");
  });
});
```

- [ ] **Step 3: 运行新测试**

```bash
cd apps/web
npx vitest run src/shell/panes/__tests__/inputForReload.test.ts --reporter=verbose
```

Expected: All 7 tests PASS

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/shell/panes/ConversationPane.tsx apps/web/src/shell/panes/__tests__/inputForReload.test.ts
git commit -m "test: add boundary tests for inputForReload and extract as export"
```

---

### Task 9: 简化 replaceWithIdDedup 逻辑

**问题:** `replaceWithIdDedup` 同时使用了 Map 和 Set，可以简化。

**Files:**
- Modify: `apps/web/src/shell/conversation/docagentRuntime.ts`
- Modify: `apps/web/src/shell/__tests__/docagentRuntime.test.ts`

- [ ] **Step 1: 简化实现**

修改 `apps/web/src/shell/conversation/docagentRuntime.ts`：

```ts
export function replaceWithIdDedup(incoming: TimelineEvent[]): TimelineEvent[] {
  const byId = new Map(incoming.map((e) => [e.id, e]));
  const seen = new Set<string>();
  const result: TimelineEvent[] = [];

  for (const event of incoming) {
    if (seen.has(event.id)) continue;
    seen.add(event.id);
    result.push(byId.get(event.id) ?? event);
  }

  return result;
}
```

实际上当前实现已经是正确的，但可以简化为单遍扫描。保持当前实现不变（已是最小可行实现），但确保测试覆盖此函数。

验证现有测试已覆盖：
```ts
it("dedupes a refreshed timeline by id and keeps backend order", () => {
  const result = replaceWithIdDedup([event("a", "old"), event("b"), event("a", "new")]);

  expect(result.map((item) => item.id)).toEqual(["a", "b"]);
  expect(result[0]?.summary).toBe("new");
});
```

- [ ] **Step 2: 运行测试**

```bash
cd apps/web
npx vitest run src/shell/__tests__/docagentRuntime.test.ts --reporter=verbose
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

由于实现没有实际变更，此 Task 可以跳过或作为验证步骤。

---

## 验证清单

所有 Task 完成后，运行完整测试套件：

```bash
# 后端
cd services/api
python -m pytest tests/test_sse.py tests/test_background_runner.py -v

# 前端
cd apps/web
npx vitest run --reporter=verbose
```

Expected: 100% tests PASS

---

## Self-Review

**1. Spec coverage:**
- [x] test_sse.py 失败 → Task 1
- [x] useMemo 创建组件 → Task 2
- [x] Composer 双状态 → Task 3
- [x] OutlineCard 竞态 → Task 4
- [x] MessageActions 原生 button → Task 5
- [x] unstable_capabilities 版本锁定 → Task 6
- [x] attachmentAdapter.remove() → Task 7
- [x] inputForReload 边界测试 → Task 8
- [x] replaceWithIdDedup → Task 9（验证已有测试）

**2. Placeholder scan:**
- [x] 无 "TBD", "TODO", "implement later"
- [x] 无 "Add appropriate error handling" 等模糊描述
- [x] 每个 Task 包含完整代码

**3. Type consistency:**
- [x] `TimelineEvent`, `ThreadMessage` 类型与现有代码一致
- [x] `inputForReload` 签名保持一致
- [x] `ActionBarPrimitive.Reload` API 与 `@assistant-ui/react@0.12.28` 匹配

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-assistant-ui-fixes.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review

**Which approach?**
