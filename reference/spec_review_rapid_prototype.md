# DocAgent Workbench 快速原型审查：套壳路线

> 前提：Claude Code 式自由 agent loop 是强约束，目标是**最快出原型**，能直接搬就直接搬，走"套壳"路线。

---

## 一、套壳目标定义

我们要找的"壳"必须已经具备：

1. ✅ Claude Code 式自由 agent loop（LLM → think → tool call → observe → continue）
2. ✅ 人在环交互（用户插话、打断、审批）
3. ✅ 事件流实时推送（WebSocket/SSE，让前端能看到过程）
4. ✅ 工具注册机制（能替换/扩展 tools）
5. ✅ 多 session 管理 + sandbox/workspace 隔离
6. ✅ 支持 OpenAI-compatible 本地模型
7. ✅ 可离线部署（Docker）

**候选壳：OpenHands SDK V1、OpenCode、LangGraph**

---

## 二、候选壳对比（套壳视角）

| 维度 | OpenHands SDK V1 | OpenCode | LangGraph |
|------|------------------|----------|-----------|
| **语言** | Python（与后端一致） | TS/Bun（后端不一致） | Python（与后端一致） |
| **Agent Loop** | ✅ 完整，event-sourced | ✅ 完整，SSE stream | ✅ 完整，graph-based |
| **HITL/打断** | ✅ pause/resume/interrupt | ✅ 支持 | ✅ `interrupt()`/`Command` |
| **事件流** | ✅ WebSocket + event log | ✅ SSE + event bus | ✅ stream + checkpoint |
| **Custom Tools** | ✅ **极度成熟**，有完整注册机制 | ⚠️ 需要hack | ⚠️ 需要wrap |
| **Sandbox** | ✅ DockerWorkspace 原生 | ❌ 无 | ❌ 需自研 |
| **Remote Server** | ✅ Agent Server 原生 | ✅ `opencode serve` | ❌ 需自研部署 |
| **前端UI** | ✅ 有（偏coding） | ✅ 有（偏coding） | ❌ 无 |
| **本地LLM** | ✅ LiteLLM 100+ providers | ✅ OpenAI-compatible | ✅ 通过 LangChain |
| **文档/成熟度** | ✅ 完善 | ✅ 完善 | ✅ 完善 |
| **Stars/社区** | 64k+ | 140k+ | LangChain生态核心 |

### 套壳结论

**OpenHands SDK V1 是最佳套壳底座**，原因：

1. **Python 生态**，FastAPI 后端可以直接 import OpenHands SDK，技术栈零割裂
2. **Custom Tool 机制极度成熟** — 刚刚验证过，有 `register_tool` + `ToolDefinition` + `ToolExecutor` 完整接口，写文档工具和写 coding 工具一样简单
3. **Agent Server 原生支持 remote execution** — 业务后端（FastAPI）→ OpenHands Agent Server → Docker sandbox，这套链路已经打通
4. **事件流已经ready** — WebSocket event stream 可以直接接到自研前端
5. **已有 Planning Agent preset** — 可以照抄它的 preset 机制，写一个 `DocumentAgentPreset`

**LangGraph 也很好，但没有现成 Server + Sandbox + UI，套壳工作量更大。**

**OpenCode 生态活跃但 TS/Bun 技术栈割裂，且 sandbox 缺失。**

---

## 三、套壳架构（最快原型版）

### 核心原则：OpenHands 的尽量不动，只换 skin 和 tools

```
┌─────────────────────────────────────────────────────────────┐
│  自研薄层：文档工作台前端（React）                           │
│  - 三栏布局（资产 | 文档画布 | Agent对话+Timeline）          │
│  - 复用 OpenHands event stream 协议渲染 timeline            │
│  - 对接 OpenHands WebSocket / REST API                      │
├─────────────────────────────────────────────────────────────┤
│  自研薄层：FastAPI 业务网关（~500行）                        │
│  - /doc-types（文档类型配置CRUD）                            │
│  - /tasks（任务管理）                                        │
│  - /sessions（透传 OpenHands Agent Server API）              │
│  - /approvals（工具审批路由）                                │
├─────────────────────────────────────────────────────────────┤
│  ████████████████████████████████████████████████           │
│  █ 直接搬：OpenHands Agent Server + SDK V1  █           │
│  ████████████████████████████████████████████████           │
│  - Agent reasoning loop（完全不动）                          │
│  - Event sourcing + state management（完全不动）             │
│  - Conversation / RemoteConversation（完全不动）             │
│  - Docker sandbox / workspace（完全不动）                    │
│  - LLM routing via LiteLLM（完全不动）                       │
│  - Security analyzer（完全不动）                             │
│  - pause/resume/interrupt（完全不动）                        │
├─────────────────────────────────────────────────────────────┤
│  自研模块：Document Tools（注册进 OpenHands）                │
│  - read_example / list_examples                              │
│  - retrieve_example_passages（RAG）                          │
│  - read_spec / search_specs                                  │
│  - create_draft / edit_section / replace_section             │
│  - run_checklist                                             │
│  - export_docx（调用 markdown2docx）                         │
│  - ask_user / request_approval（人在环）                     │
├─────────────────────────────────────────────────────────────┤
│  自研模块：Document Agent Preset                             │
│  - 照抄 OpenHands planning agent preset 结构                 │
│  - system_prompt_document.j2（文档写作专用system prompt）    │
│  - tools = [DocumentTools...]                                │
│  - 不用bash/browser，文件操作限制在/workspace内               │
├─────────────────────────────────────────────────────────────┤
│  基础设施（spec原选型，全部保留）                            │
│  - PostgreSQL + pgvector                                     │
│  - Redis                                                     │
│  - MinIO                                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、各模块"抄/搬"清单

### 4.1 完全不动，直接搬（OpenHands 原生能力）

| 能力 | 来源 | 工作量 |
|------|------|--------|
| Agent reasoning-action loop | OpenHands SDK | **0** |
| Event sourcing + deterministic replay | OpenHands SDK | **0** |
| Conversation state management | OpenHands SDK | **0** |
| RemoteConversation / WebSocket events | OpenHands Agent Server | **0** |
| Docker workspace sandbox | OpenHands DockerWorkspace | **0** |
| LLM multi-provider routing | OpenHands via LiteLLM | **0** |
| Security analyzer + risk levels | OpenHands SDK | **0** |
| Pause / Resume / Interrupt | OpenHands Conversation | **0** |
| Tool call approval flow | OpenHands confirmation policy | **0** |

### 4.2 照抄改个名字（复用 OpenHands 机制，换内容）

| 要自研的模块 | 照抄对象 | 工作量 |
|-------------|---------|--------|
| **Document Agent Preset** | OpenHands `planning_agent` preset | **低**：照抄 preset 结构（system prompt template + tool list + agent config），把 coding 内容换成 document 内容 |
| **Document Tools 框架** | OpenHands `FileEditorTool` / `GlobTool` / `GrepTool` | **低**：照抄 `ToolDefinition` + `ToolExecutor` 模式，把 file/bash 操作换成 doc-type 操作 |
| **前端 Event Stream 渲染** | OpenHands Web UI 的 event list 组件 | **低**：不 fork UI，但抄它的 event type 判断逻辑和渲染逻辑 |

### 4.3 需要自研的核心模块（躲不掉，但量不大）

| 模块 | 说明 | 预估工作量 |
|------|------|-----------|
| **Document Tools 实现**（~10个） | `read_example`、`edit_section`、`run_checklist` 等工具的内部业务逻辑 | 2-3 天 |
| **DocType Pack 加载器** | 解析 `manifest.yaml` + 挂载 `examples/` `specs/` `templates/` 到 workspace | 1 天 |
| **风格签名提取** | 分析示例文档，提取结构/语气/修辞模式（可先用简单启发式） | 1-2 天 |
| **FastAPI 业务网关** | doc-types/tasks/approvals CRUD + OpenHands API 透传 | 1-2 天 |
| **文档工作台前端** | 三栏布局 + Markdown预览 + diff + 章节树 | 3-5 天 |
| **导出工具链** | markdown2docx + python-docx 后处理 | 1 天 |

**总原型周期：1-2 周（PoC）到 3-4 周（可演示原型）**

---

## 五、Phase 0 具体执行步骤（套壳路线）

### Week 1：把壳跑起来

1. **部署 OpenHands Agent Server**（已有 docker-compose）
   ```bash
   git clone https://github.com/All-Hands-AI/OpenHands
   # 按官方文档启动 local agent server
   ```

2. **验证本地 LLM 接入**
   - 配置 `LLM_BASE_URL=http://local-llm.internal:8000/v1`
   - 跑通一个 OpenHands 示例 conversation，确认 tool call 和 event stream 正常

3. **写第一个 Document Tool**
   - 照抄 `FileEditorTool` 的结构
   - 实现 `ReadExampleTool`：从 `/doc-types/{id}/examples/` 读取示例
   - 注册到 OpenHands，验证 agent 能调用

### Week 2：套上前端和业务层

4. **搭建 FastAPI 网关**（轻量，只做路由和配置管理）
   - `/doc-types` CRUD
   - `/tasks` CRUD
   - `/sessions` 透传 OpenHands Agent Server

5. **搭建 React 文档工作台前端**
   - 左侧：doc-type assets 列表（读取 FastAPI）
   - 中间：Markdown 预览（react-markdown）
   - 右侧：Agent 对话 + Event Timeline（对接 OpenHands WebSocket）

6. **写 Document Agent Preset**
   - 复制 `openhands/tools/preset/planning.py`
   - 改为 `document_tools/preset/writer.py`
   - system prompt 换成文档仿写指令

### Week 3：文档能力闭环

7. **实现核心 Document Tools**
   - `list_examples`, `read_example`, `retrieve_example_passages`（RAG用pgvector）
   - `create_draft`, `edit_section`, `replace_section`
   - `run_checklist`
   - `export_docx`（集成 markdown2docx）

8. **接入人在环**
   - `ask_user` tool → 前端弹窗
   - `request_approval` tool → 审批按钮
   - 复用 OpenHands 的 confirmation policy 机制

9. **跑通第一个 PRD PoC**
   - 上传 3 个 PRD 示例
   - 配置 PRD doc-type
   - 创建任务，agent 读取示例 → 写大纲 → 用户修改 → 生成草稿 → 局部修改 → checklist → 导出 DOCX

---

## 六、关键决策点

### Q1：OpenHands UI 能临时用吗？

**建议：Phase 0 可以临时用 OpenHands 自带 Web UI 验证 agent loop，但 Week 2 必须切自研文档工作台。**

OpenHands UI 能看到 event stream 和 tool calls，足够验证后端逻辑，但它没有：
- 文档画布（Markdown 预览+章节树）
- 三栏布局
- diff 视图
- 章节级锁定

所以**后端和 agent 可以先用 OpenHands UI 调通，前端并行开发**。

### Q2：需要 OpenHands Agent Server 吗？还是本地 Conversation 就够？

**建议：直接上 Agent Server。**

OpenHands Agent Server 提供：
- HTTP REST API（业务后端可以直接调用）
- WebSocket event stream（前端可以直接订阅）
- Docker sandbox（workspace 隔离）
- 多 conversation 管理

这些都是原型需要的能力，本地 `Conversation` 反而要自己搞进程管理。**一步到位上 Agent Server，不绕弯路。**

### Q3：OpenHands 的 security analyzer 会拦文档工具吗？

**建议：利用它，而不是绕过它。**

OpenHands 的 security analyzer 会给每个 action 打风险标签（LOW/MEDIUM/HIGH）。
- 读取示例 → LOW（自动执行）
- 编辑草稿 → MEDIUM（可配置为自动或询问）
- 导出正式 DOCX → HIGH（需要用户确认）

**这正好匹配 spec 的工具权限等级，无需自研审批逻辑。**

---

## 七、风险与应对

| 风险 | 应对 |
|------|------|
| OpenHands 升级 breaking change | 锁定版本，V1 架构已稳定 |
| OpenHands 前端改不动 | **不碰它的前端**，自研前端对接它的 WebSocket API |
| 文档工具性能差 | 先做同步工具，后续加 Celery worker 异步化 |
| 本地 LLM tool call 能力弱 | 选支持 function calling 的模型，或 fallback 到 prompt-based tool use |

---

## 八、一句话总结

> **OpenHands SDK V1 = 最好的壳。搬它的 Agent Server + Event Stream + Sandbox + Tool Framework，只换 tools 和 skin，3-4 周出原型。**

不需要在 LangGraph/Dify/OpenCode 之间纠结了，OpenHands 本身就是为"被嵌入/被扩展"设计的，套壳最自然。
