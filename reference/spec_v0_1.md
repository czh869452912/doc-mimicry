# 文档仿写 Agent 平台初步方案设计 Spec v0.1

## 1. 项目名称

暂定名：

**DocAgent Workbench**

中文名：

**文档 Agent 工作台**

---

## 2. 背景与问题定义

团队希望构建一个面向企业内网环境的文档仿写智能体平台。用户可以为不同文档类型配置最佳示例、文档规范、检查单和提示词，之后通过一个可交互、可观测、可多人使用的 Agent 工作台完成文档撰写、修改、审校和导出。

该平台不是简单的“一次性文档生成器”，也不是固定 workflow 式的表单工具，而是接近 **Claude Code / OpenHands 类 Agent Loop** 的交互式文档协作环境。

核心问题包括：

1. 如何基于多个最佳示例和规范，生成“结构、语气、表达方式都相似”的新文档。
2. 如何让 Agent 在生成过程中可被用户打断、纠正、继续迭代。
3. 如何可视化展示 Agent 的中间过程，而不是只返回最终 Word 文档。
4. 如何支持多个文档类型、多个用户、多个任务并行。
5. 如何在完全离线、内网、本地 LLM、无互联网、无 npm/pypi 镜像源的环境中部署。
6. 如何复用成熟 Agent Runtime，避免自建权限、沙箱、工具体系、上下文管理和 agent loop 等基础设施。

---

## 3. 设计目标

### 3.1 产品目标

平台应支持用户完成以下任务：

```text
配置一个文档类型 → 上传参考示例和规范 → 创建文档任务 →
与 Agent 交互式协作 → 观察过程 → 局部修改 → 检查质量 →
导出最终文档
```

核心体验应类似：

用户：“基于这些材料写一版 PRD。”

Agent：

1. 读取 PRD 文档类型配置；
2. 分析最佳示例；
3. 总结目标文档结构；
4. 提出写作计划；
5. 等待用户确认或修改；
6. 逐步撰写草稿；
7. 展示每一步工具调用和引用依据；
8. 用户可随时打断、局部重写、回滚；
9. Agent 运行检查单；
10. 用户批准后导出 DOCX/PDF。

---

### 3.2 技术目标

平台需要满足：

1. **复用成熟 Agent Runtime**
   优先基于 OpenHands SDK / Agent Server 或类似架构，而不是自建简易 runtime。

2. **Claude Code 类 Agent Loop**
   Agent 应具备自由推理、工具调用、事件流、上下文压缩、权限控制、人在环交互等能力。

3. **过程可视化**
   前端要展示 Agent 计划、工具调用、草稿 diff、检查单结果、引用示例、用户打断记录。

4. **多人使用**
   支持用户、团队、权限、任务列表、文档类型共享、任务归属、审计记录。

5. **完全离线部署**
   交付物应包含基础平台、依赖包、前端静态资源、服务端、Agent Server、沙箱镜像、字体、导出工具和初始化数据。

6. **对接内网 LLM**
   使用本地 OpenAI-compatible API，例如：

```text
http://local-llm.internal:8000/v1
```

7. **可扩展文档类型**
   每种文档类型可以配置不同示例、规范、检查单、模板、提示词、工具权限和导出格式。

---

## 4. 非目标

本阶段不追求：

1. 通用办公套件替代品。
2. 完整在线协同编辑器。
3. 类 Notion / Google Docs 的多人实时协作编辑。
4. 任意格式复杂排版 100% 还原。
5. 任意 Agent 自由联网搜索。
6. 让 Agent 拥有无限 shell 权限。
7. 一开始支持所有文档格式，MVP 先支持 Markdown → DOCX/PDF。
8. 直接 fork OpenHands UI 改造成最终产品。

---

## 5. 总体技术选型

### 5.1 推荐选型

| 层级            | 推荐方案                                             |
| ------------- | ------------------------------------------------ |
| Agent Runtime | OpenHands SDK / Agent Server                     |
| Agent 交互范式    | Claude Code-style reasoning-action loop          |
| 模型接口          | OpenAI-compatible `/v1` API                      |
| 后端业务服务        | FastAPI / Python                                 |
| 前端            | React / TypeScript                               |
| 数据库           | PostgreSQL                                       |
| 向量检索          | pgvector 或 Qdrant                                |
| 对象存储          | MinIO                                            |
| 队列            | Redis                                            |
| 导出            | Pandoc / LibreOffice headless / python-docx      |
| 沙箱            | Docker workspace per task/session                |
| 观测            | Agent event log + OpenTelemetry-compatible trace |
| 部署            | Air-gapped Docker Compose bundle                 |

---

### 5.2 为什么选择 OpenHands 作为候选底座

OpenHands SDK 官方架构中包含 agent reasoning loop、状态管理、LLM 集成、工具系统、workspace abstraction、skills、condenser、MCP 和安全扩展能力。它更接近一个可嵌入应用的 Agent Runtime，而不是单纯的 prompt 框架。([OpenHands Docs][1])

OpenHands 的 Agent 组件本身实现 reasoning-action loop，负责查询 LLM、执行工具、管理上下文，并通过 security analyzer 对动作做安全校验。([OpenHands Docs][2])

OpenHands 的 Conversation 组件负责 agent 生命周期、pause、terminate、conversation history、events、execution status、workspace coordination 和 runtime services；这正好对应你要求的人在环、可打断、过程可观测能力。([OpenHands Docs][3])

OpenHands Agent Server 提供 HTTP API server，用于 remote agent execution、workspace isolation、container orchestration 和 multi-user support；这比自建多用户 Agent Runtime 更贴近目标架构。([OpenHands Docs][4])

OpenHands Local Agent Server 示例也展示了 RemoteConversation 可以通过 WebSocket 接收实时事件，并通过 conversation state 访问事件历史，这可以作为你们过程可视化 UI 的底层事件来源。([OpenHands Docs][5])

---

### 5.3 Claude Agent SDK 的参考价值

Claude Agent SDK 不一定适合作为你们主 runtime，因为你们强依赖内网 OpenAI-compatible LLM。但它的权限和人在环设计非常值得参考。

Claude Agent SDK 的权限系统包括 permission modes、`canUseTool` callback、hooks、settings.json permission rules；其权限流包括 PreToolUse Hook、deny rules、allow rules、ask rules、permission mode、canUseTool callback 和 PostToolUse Hook。([Claude API Docs][6])

这些概念应被借鉴到平台的文档工具权限设计中。

---

## 6. 总体架构

```text
┌──────────────────────────────────────────────────────────┐
│                    DocAgent Workbench                    │
├──────────────────────────────────────────────────────────┤
│ Frontend: React / TypeScript                             │
│                                                          │
│  - 文档类型管理                                          │
│  - 任务管理                                              │
│  - Agent Session UI                                      │
│  - 工具调用时间线                                        │
│  - 文档预览 / diff / 评论                                │
│  - 检查单结果                                            │
│  - 人工审批 / 打断 / 回滚                                │
├──────────────────────────────────────────────────────────┤
│ Product Backend: FastAPI                                 │
│                                                          │
│  - 用户 / 团队 / 权限                                    │
│  - 文档类型配置管理                                      │
│  - 任务管理                                              │
│  - Artifact 管理                                         │
│  - Trace / Audit 管理                                    │
│  - Agent Runtime Adapter                                 │
├──────────────────────────────────────────────────────────┤
│ Agent Runtime Layer                                      │
│                                                          │
│  - OpenHands SDK                                         │
│  - OpenHands Agent Server                                │
│  - Conversation / RemoteConversation                     │
│  - Event Stream                                          │
│  - Tool Execution                                        │
│  - Workspace / Sandbox                                   │
│  - Skills / Context Condenser                            │
├──────────────────────────────────────────────────────────┤
│ Document Agent Layer                                     │
│                                                          │
│  - 文档类型 Skill Pack                                   │
│  - 示例检索工具                                          │
│  - 规范检索工具                                          │
│  - 风格分析工具                                          │
│  - 草稿编辑工具                                          │
│  - 检查单工具                                            │
│  - DOCX/PDF 导出工具                                     │
├──────────────────────────────────────────────────────────┤
│ Storage Layer                                            │
│                                                          │
│  - PostgreSQL                                            │
│  - pgvector / Qdrant                                     │
│  - MinIO                                                 │
│  - Redis                                                 │
├──────────────────────────────────────────────────────────┤
│ Offline LLM                                              │
│                                                          │
│  - OpenAI-compatible API                                 │
│  - /v1/chat/completions                                  │
│  - /v1/embeddings 可选                                   │
└──────────────────────────────────────────────────────────┘
```

---

## 7. 核心概念模型

### 7.1 文档类型 DocType

文档类型是平台中最核心的配置单元。

例如：

```text
PRD
解决方案建议书
法务备忘录
竞品分析
项目周报
复盘报告
投标文件
客户成功方案
```

每个文档类型包含：

1. 最佳示例；
2. 文档规范；
3. 检查单；
4. 模板；
5. 风格配置；
6. Agent 指令；
7. 工具权限；
8. 导出格式；
9. 版本号。

---

### 7.2 文档类型包 DocType Pack

推荐目录结构：

```text
doc-types/
  prd/
    manifest.yaml
    SKILL.md
    instructions/
      writing_principles.md
      review_principles.md
    examples/
      example_001.md
      example_002.docx
      example_003.pdf
    specs/
      style_guide.md
      structure_rules.md
      terminology.md
    checklists/
      quality_checklist.yaml
      compliance_checklist.yaml
    templates/
      outline_template.yaml
      markdown_template.md
      docx_template.docx
    profiles/
      style_profile.yaml
      structure_signature.yaml
```

---

### 7.3 任务 Task

Task 是用户发起的一次文档撰写任务。

Task 包含：

1. 任务标题；
2. 文档类型；
3. 用户 brief；
4. 上传素材；
5. 当前 Agent Session；
6. 当前草稿；
7. 导出产物；
8. 状态；
9. 权限；
10. 审计记录。

---

### 7.4 Agent Session

Agent Session 是一次可持续交互的 Agent 工作过程，不是一次性运行。

特点：

1. 有 conversation history；
2. 有 event log；
3. 有 workspace；
4. 可 pause/resume；
5. 可接收用户插话；
6. 可调用工具；
7. 可产生多个草稿版本；
8. 可被用户回滚；
9. 可导出最终结果。

---

## 8. Agent 交互模式

### 8.1 基本交互流

```text
用户创建任务
  ↓
Agent 读取文档类型配置
  ↓
Agent 分析任务 brief 和素材
  ↓
Agent 检索最佳示例和规范
  ↓
Agent 输出写作计划
  ↓
用户确认 / 修改 / 打断
  ↓
Agent 分章节写草稿
  ↓
用户实时查看和评论
  ↓
Agent 局部修订
  ↓
Agent 跑检查单
  ↓
用户批准
  ↓
导出 DOCX/PDF
```

---

### 8.2 非固定 Workflow 原则

本平台不应把文档生成硬编码为固定 DAG，例如：

```text
Step1 → Step2 → Step3 → Step4 → Done
```

而应采用 Agent Loop：

```text
Observe context
  ↓
Think / plan
  ↓
Select tool or respond
  ↓
Execute tool
  ↓
Observe result
  ↓
Continue / ask user / finish
```

Agent 可以根据情况决定：

1. 先问用户问题；
2. 先读示例；
3. 先写大纲；
4. 先跑检查；
5. 先修改某一节；
6. 暂停等待审批；
7. 回滚到上一版本；
8. 继续细化某个章节。

---

### 8.3 人在环交互

必须支持以下能力。

#### 8.3.1 Plan Approval

Agent 在写全文前先给出计划：

```text
我准备按以下方式处理：

1. 参考示例 A 的章节结构；
2. 参考示例 B 的指标写法；
3. 背景部分使用用户上传的会议纪要；
4. 风险部分按照规范要求简写；
5. 最后运行 PRD 检查单。

需要确认：
- 本文档读者是否主要是研发和设计？
- 是否需要包含上线排期？
```

用户可以选择：

```text
确认计划
修改计划
跳过计划直接写
只生成大纲
先分析示例
```

---

#### 8.3.2 Runtime Interrupt

用户可以在 Agent 运行中插话：

```text
停，方向错了。
先不要继续写。
第三章改成面向高管。
只改指标部分，其他不要动。
先把你参考了哪些示例列出来。
```

系统应将用户消息注入当前 session，而不是重新创建任务。

---

#### 8.3.3 Tool Approval

敏感工具调用需要审批：

| 工具       | 默认策略     |
| -------- | -------- |
| 读取示例     | 自动允许     |
| 检索规范     | 自动允许     |
| 写临时草稿    | 自动允许     |
| 覆盖正式草稿   | 需要审批     |
| 删除版本     | 禁止或管理员审批 |
| 导出 DOCX  | 需要用户确认   |
| 执行 shell | 默认禁用     |
| 访问外部网络   | 禁止       |
| 读取其他任务目录 | 禁止       |

---

#### 8.3.4 Section-level Edit

用户可以要求局部修改：

```text
只重写“风险与应对”章节。
保留表格，压缩文字。
这一节改成更像示例 2。
不要动背景和目标章节。
```

这要求文档内部结构化管理，而不是只存一个纯文本 blob。

---

#### 8.3.5 Version Rollback

每次 Agent 对草稿做重要修改时，应创建版本：

```text
draft_v1
draft_v2
draft_v3
```

用户可以：

1. 查看 diff；
2. 回滚；
3. 锁定某个版本；
4. 从某个版本继续。

---

#### 8.3.6 Final Approval

只有用户批准后，系统才生成最终 DOCX/PDF。

---

## 9. 文档 Agent 工具体系

### 9.1 工具设计原则

工具不应只暴露底层 Bash / Read / Write，而应提供文档领域高层工具。

原因：

1. 更安全；
2. 更容易审批；
3. 更容易可视化；
4. 更容易约束 Agent；
5. 更容易复现执行过程。

---

### 9.2 工具清单 v0.1

#### 文档类型工具

```text
read_doc_type_manifest(doc_type_id)
list_doc_type_assets(doc_type_id)
read_doc_type_skill(doc_type_id)
read_style_profile(doc_type_id)
```

#### 示例工具

```text
list_examples(doc_type_id)
read_example(example_id)
retrieve_example_passages(doc_type_id, query, top_k)
compare_draft_with_examples(task_id, example_ids)
extract_style_signature(example_ids)
```

#### 规范工具

```text
list_specs(doc_type_id)
read_spec(spec_id)
search_specs(doc_type_id, query)
```

#### 草稿工具

```text
create_draft(task_id, outline)
read_draft(task_id)
edit_section(task_id, section_id, instruction)
replace_section(task_id, section_id, content)
append_section(task_id, after_section_id, content)
delete_section(task_id, section_id)
lock_section(task_id, section_id)
unlock_section(task_id, section_id)
```

#### 检查工具

```text
read_checklist(checklist_id)
run_checklist(task_id, checklist_id)
run_consistency_check(task_id)
run_style_check(task_id, doc_type_id)
```

#### 导出工具

```text
render_markdown(task_id)
export_docx(task_id, template_id)
export_pdf(task_id)
```

#### 人在环工具

```text
ask_user(question, options)
request_approval(action, summary, risk_level)
pause_for_review(task_id)
```

---

### 9.3 工具调用事件格式

每次工具调用都应产生事件：

```json
{
  "event_id": "evt_001",
  "run_id": "run_123",
  "type": "tool_call",
  "tool_name": "retrieve_example_passages",
  "status": "completed",
  "input": {
    "doc_type_id": "prd",
    "query": "metrics section style",
    "top_k": 3
  },
  "output_summary": "检索到 3 个与指标章节相关的示例片段",
  "started_at": "2026-04-28T10:01:21Z",
  "ended_at": "2026-04-28T10:01:25Z"
}
```

---

## 10. 文档类型 Skill 设计

### 10.1 SKILL.md 示例

每个文档类型都可以包含一个 `SKILL.md`，用于指导 Agent。

示例：

```markdown
---
name: prd-writer
description: use when writing, revising, reviewing, or imitating product requirement documents using configured prd examples, specifications, templates, and quality checklists.
---

# PRD Writing Instructions

## Core Behavior

When working on a PRD task:

1. Read the task brief.
2. Inspect the configured PRD examples.
3. Extract the expected structure and tone.
4. Ask the user before making major assumptions.
5. Draft incrementally by section.
6. Preserve locked sections.
7. Prefer targeted edits over full rewrites.
8. Run the PRD checklist before final export.

## Imitation Rules

Do not copy example wording directly. Instead, imitate:

- section order
- information density
- evidence style
- table usage
- decision framing
- risk framing
- metric definition style

## Revision Rules

When the user asks for changes:

- identify the affected sections
- explain what will change
- avoid modifying unrelated sections
- create a new draft version
- show a diff summary

## Finalization Rules

Before export:

- run the quality checklist
- disclose failed checklist items
- ask for user approval
```

---

### 10.2 文档仿写的关键中间产物

不要只做普通 RAG。需要抽取结构与风格签名。

示例：

```yaml
structure_signature:
  common_sections:
    - 背景
    - 目标
    - 非目标
    - 用户场景
    - 方案设计
    - 指标
    - 风险
  section_order_strictness: high

tone_signature:
  style: business_decision_oriented
  sentence_length: medium
  evidence_pattern: conclusion_first
  table_density: high
  bullet_depth: 2

rhetorical_patterns:
  - 先描述问题，再描述影响，最后描述方案
  - 每个核心需求都包含用户价值和验收标准
  - 指标必须包含定义、口径、观察方式

anti_patterns:
  - 避免空泛愿景
  - 避免未定义指标
  - 避免复制示例原文
```

---

## 11. 前端 UI 设计

### 11.1 页面结构

MVP 至少包含：

1. 登录页；
2. 文档类型管理页；
3. 文档类型详情页；
4. 任务列表页；
5. 任务工作台页；
6. Agent Session 可视化页；
7. 审计与日志页；
8. 系统配置页。

---

### 11.2 文档工作台布局

建议采用三栏布局。

```text
┌─────────────────────────────────────────────────────────────┐
│ 顶部：任务标题 / 状态 / 文档类型 / 当前版本 / 导出按钮       │
├───────────────┬─────────────────────────────┬───────────────┤
│ 左侧资产栏     │ 中间文档画布                 │ 右侧 Agent 栏  │
│               │                             │               │
│ - Brief        │ - 大纲                       │ - 对话         │
│ - 示例         │ - 草稿预览                   │ - 事件时间线   │
│ - 规范         │ - diff                       │ - 工具调用     │
│ - 检查单       │ - 评论                       │ - 审批请求     │
│ - 素材         │ - 锁定章节                   │ - 检查结果     │
└───────────────┴─────────────────────────────┴───────────────┘
```

---

### 11.3 Agent Timeline

右侧时间线展示：

```text
10:01 用户提交任务
10:02 Agent 读取 PRD 文档类型配置
10:02 Tool: list_examples
10:03 Agent 总结示例结构
10:04 Agent 请求确认写作计划
10:05 用户修改计划
10:06 Tool: create_draft
10:07 Tool: edit_section(background)
10:08 Agent 生成第一版草稿
10:09 Tool: run_checklist
10:10 Agent 发现 2 个检查项未通过
```

每个事件可以展开：

1. 输入；
2. 输出摘要；
3. 原始输出；
4. 耗时；
5. token 消耗；
6. 关联文件；
7. 用户审批记录。

---

### 11.4 文档画布

文档画布需要支持：

1. Markdown 预览；
2. 章节树；
3. section-level selection；
4. diff view；
5. 评论；
6. 锁定章节；
7. 当前版本切换；
8. 导出预览。

---

### 11.5 人工审批 UI

当 Agent 请求工具审批时，前端展示：

```text
Agent 请求执行：覆盖正式草稿

原因：
- 根据用户要求重写了“风险与应对”章节
- 将创建 draft_v4

影响：
- 会修改 1 个章节
- 不会修改已锁定章节

操作：
[批准] [拒绝] [改为只生成建议]
```

---

## 12. 后端服务设计

### 12.1 服务划分

```text
doc-agent-api
  - REST API
  - Auth
  - RBAC
  - DocType Management
  - Task Management
  - Artifact Management
  - Audit Log

doc-agent-runtime-adapter
  - OpenHands Agent Server adapter
  - Session lifecycle
  - Event ingestion
  - Tool approval routing
  - Interrupt handling

doc-agent-worker
  - indexing
  - document conversion
  - checklist execution
  - export jobs
  - background cleanup

openhands-agent-server
  - remote agent execution
  - conversation
  - workspace
  - tool execution
  - event streaming

storage
  - postgres
  - redis
  - minio
  - pgvector/qdrant
```

MVP 可以先合并 API 和 runtime-adapter，后续拆分。

---

### 12.2 API 草案

#### 文档类型

```http
POST   /api/doc-types
GET    /api/doc-types
GET    /api/doc-types/{doc_type_id}
POST   /api/doc-types/{doc_type_id}/versions
POST   /api/doc-types/{doc_type_id}/examples
POST   /api/doc-types/{doc_type_id}/specs
POST   /api/doc-types/{doc_type_id}/checklists
POST   /api/doc-types/{doc_type_id}/publish
```

#### 任务

```http
POST   /api/tasks
GET    /api/tasks
GET    /api/tasks/{task_id}
PATCH  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
```

#### Session

```http
POST   /api/tasks/{task_id}/sessions
GET    /api/sessions/{session_id}
POST   /api/sessions/{session_id}/messages
POST   /api/sessions/{session_id}/interrupt
POST   /api/sessions/{session_id}/pause
POST   /api/sessions/{session_id}/resume
POST   /api/sessions/{session_id}/cancel
GET    /api/sessions/{session_id}/events
GET    /api/sessions/{session_id}/events/stream
```

#### 审批

```http
GET    /api/approvals/pending
POST   /api/approvals/{approval_id}/approve
POST   /api/approvals/{approval_id}/reject
```

#### 草稿与版本

```http
GET    /api/tasks/{task_id}/draft
GET    /api/tasks/{task_id}/draft/versions
GET    /api/tasks/{task_id}/draft/versions/{version_id}
POST   /api/tasks/{task_id}/draft/versions/{version_id}/restore
POST   /api/tasks/{task_id}/sections/{section_id}/lock
POST   /api/tasks/{task_id}/sections/{section_id}/unlock
```

#### 导出

```http
POST   /api/tasks/{task_id}/exports/docx
POST   /api/tasks/{task_id}/exports/pdf
GET    /api/artifacts/{artifact_id}/download
```

---

## 13. 数据模型初稿

### 13.1 users

```sql
users (
  id uuid primary key,
  email text unique not null,
  name text,
  status text,
  created_at timestamptz,
  updated_at timestamptz
)
```

### 13.2 teams

```sql
teams (
  id uuid primary key,
  name text not null,
  created_at timestamptz
)
```

### 13.3 memberships

```sql
memberships (
  user_id uuid,
  team_id uuid,
  role text,
  created_at timestamptz
)
```

### 13.4 doc_types

```sql
doc_types (
  id uuid primary key,
  team_id uuid,
  key text not null,
  name text not null,
  description text,
  current_version_id uuid,
  status text,
  created_by uuid,
  created_at timestamptz,
  updated_at timestamptz
)
```

### 13.5 doc_type_versions

```sql
doc_type_versions (
  id uuid primary key,
  doc_type_id uuid,
  version text,
  manifest jsonb,
  skill_md text,
  status text,
  created_by uuid,
  created_at timestamptz,
  published_at timestamptz
)
```

### 13.6 doc_assets

```sql
doc_assets (
  id uuid primary key,
  doc_type_version_id uuid,
  asset_type text, -- example/spec/checklist/template/profile
  name text,
  storage_uri text,
  parsed_text_uri text,
  metadata jsonb,
  created_at timestamptz
)
```

### 13.7 tasks

```sql
tasks (
  id uuid primary key,
  team_id uuid,
  doc_type_id uuid,
  doc_type_version_id uuid,
  title text,
  brief text,
  status text,
  owner_id uuid,
  current_session_id uuid,
  current_draft_version_id uuid,
  created_at timestamptz,
  updated_at timestamptz
)
```

### 13.8 sessions

```sql
sessions (
  id uuid primary key,
  task_id uuid,
  runtime text,
  runtime_session_id text,
  status text,
  model_profile_id uuid,
  workspace_uri text,
  created_at timestamptz,
  updated_at timestamptz
)
```

### 13.9 session_events

```sql
session_events (
  id uuid primary key,
  session_id uuid,
  event_index bigint,
  event_type text,
  actor text, -- user/agent/tool/system
  payload jsonb,
  created_at timestamptz
)
```

### 13.10 draft_versions

```sql
draft_versions (
  id uuid primary key,
  task_id uuid,
  version_index int,
  content_uri text,
  content_format text,
  summary text,
  created_by_actor text,
  created_at timestamptz
)
```

### 13.11 approvals

```sql
approvals (
  id uuid primary key,
  session_id uuid,
  tool_call_id text,
  action text,
  risk_level text,
  status text,
  requested_by text,
  decided_by uuid,
  request_payload jsonb,
  decision_payload jsonb,
  created_at timestamptz,
  decided_at timestamptz
)
```

### 13.12 artifacts

```sql
artifacts (
  id uuid primary key,
  task_id uuid,
  draft_version_id uuid,
  artifact_type text, -- docx/pdf/markdown
  storage_uri text,
  created_at timestamptz
)
```

---

## 14. Agent Runtime Adapter 设计

为了避免平台和 OpenHands 强耦合，建议定义 Runtime Adapter 接口。

```python
class AgentRuntimeAdapter:
    def create_session(self, task_id, doc_type_version_id, workspace_config):
        ...

    def send_message(self, session_id, message, user_id):
        ...

    def stream_events(self, session_id):
        ...

    def pause(self, session_id):
        ...

    def resume(self, session_id):
        ...

    def cancel(self, session_id):
        ...

    def approve_tool_call(self, approval_id, user_id):
        ...

    def reject_tool_call(self, approval_id, user_id, reason):
        ...

    def get_state(self, session_id):
        ...
```

第一版实现：

```text
OpenHandsRuntimeAdapter
```

未来可扩展：

```text
ClaudeAgentSdkRuntimeAdapter
LangGraphRuntimeAdapter
CustomRuntimeAdapter
```

---

## 15. Workspace 与沙箱设计

### 15.1 每个任务一个 workspace

```text
/workspaces/
  tenant_001/
    task_abc123/
      brief.md
      inputs/
      draft/
        draft.md
        versions/
      artifacts/
      logs/
      .agent/
```

### 15.2 只读挂载

```text
/doc-types/prd/v1.3.0/examples      readonly
/doc-types/prd/v1.3.0/specs         readonly
/doc-types/prd/v1.3.0/checklists    readonly
/doc-types/prd/v1.3.0/templates     readonly
```

### 15.3 可写挂载

```text
/workspace/task_abc123/draft        readwrite
/workspace/task_abc123/artifacts    readwrite
/workspace/task_abc123/logs         readwrite
```

### 15.4 禁止

```text
外网访问
宿主机任意目录访问
其他用户 workspace 访问
未审批 shell
未审批删除
未审批导出正式 artifact
```

---

## 16. 权限模型

### 16.1 用户角色

| 角色            | 权限                 |
| ------------- | ------------------ |
| Admin         | 系统配置、用户管理、所有文档类型管理 |
| DocType Owner | 管理某类文档的示例、规范、检查单   |
| Writer        | 创建和编辑任务            |
| Reviewer      | 评论、审批、导出           |
| Viewer        | 查看任务和结果            |

---

### 16.2 Agent 工具权限等级

| 等级         | 含义      | 示例                  |
| ---------- | ------- | ------------------- |
| auto_allow | 自动允许    | 读取示例、检索规范           |
| ask        | 请求用户批准  | 覆盖草稿、导出             |
| admin_ask  | 请求管理员批准 | 删除版本、修改文档类型         |
| deny       | 禁止      | 外网访问、读取其他 workspace |

---

### 16.3 权限策略配置示例

```yaml
tool_permissions:
  read_example: auto_allow
  retrieve_example_passages: auto_allow
  read_spec: auto_allow
  create_draft: auto_allow
  edit_section: auto_allow
  replace_section: ask
  delete_section: ask
  export_docx: ask
  export_pdf: ask
  shell: deny
  network_access: deny
```

---

## 17. 上下文管理设计

### 17.1 上下文来源

Agent 运行时上下文包括：

1. 用户当前消息；
2. 任务 brief；
3. 当前草稿摘要；
4. 当前章节内容；
5. 文档类型 SKILL；
6. 相关示例片段；
7. 相关规范片段；
8. 检查单摘要；
9. 历史用户偏好；
10. 最近事件摘要。

---

### 17.2 上下文压缩策略

当 session 变长时，需要进行 condenser 压缩。

保留：

1. 用户明确要求；
2. 已确认计划；
3. 当前大纲；
4. 当前草稿摘要；
5. 锁定章节；
6. 未解决问题；
7. 最近检查失败项；
8. 用户对风格的偏好；
9. 当前文档类型关键规范。

压缩：

1. 旧工具调用完整输出；
2. 已过期草稿；
3. 重复示例内容；
4. 无关讨论。

禁止压缩掉：

1. 用户明确说“不要改”的内容；
2. 锁定章节；
3. 已批准的结构；
4. 合规要求；
5. 最终导出格式要求。

---

## 18. 文档检查单设计

### 18.1 检查单格式

```yaml
id: prd_quality_v1
name: PRD 质量检查
items:
  - id: goal_clear
    label: 目标是否清晰
    severity: critical
    instruction: 判断文档是否明确说明业务目标、用户目标和成功标准。
    pass_criteria: 必须有可验证目标，不能只有愿景描述。

  - id: metrics_defined
    label: 指标是否可度量
    severity: high
    instruction: 检查每个核心指标是否有定义、口径、观测方式。
    pass_criteria: 指标必须可计算、可观察、可归因。

  - id: non_goals_present
    label: 是否说明非目标
    severity: medium
    instruction: 检查文档是否说明本期不做什么。
```

---

### 18.2 检查结果格式

```json
{
  "overall_score": 0.82,
  "status": "passed_with_warnings",
  "items": [
    {
      "id": "goal_clear",
      "pass": true,
      "score": 0.92,
      "evidence": "第 2 节列出了目标和成功标准。"
    },
    {
      "id": "non_goals_present",
      "pass": false,
      "score": 0.3,
      "suggestion": "建议增加“非目标”小节，说明本期不覆盖的用户场景。"
    }
  ]
}
```

---

## 19. 文档导出设计

### 19.1 MVP 支持格式

```text
Markdown
DOCX
PDF
```

### 19.2 推荐导出路径

```text
structured draft
  ↓
markdown
  ↓
pandoc / python-docx
  ↓
docx
  ↓
LibreOffice headless
  ↓
pdf
```

### 19.3 模板能力

每个文档类型可配置：

```text
docx_template.docx
style_map.yaml
cover_page.md
header_footer.yaml
```

MVP 可以先简化为：

1. 标题层级；
2. 正文样式；
3. 表格；
4. 页眉页脚；
5. 封面；
6. 目录。

---

## 20. 离线部署设计

### 20.1 交付形态

推荐交付为一个离线部署包，而不是强行单容器。

```text
doc-agent-release/
  docker-compose.yaml
  install.sh
  .env.example

  images/
    doc-agent-web.tar
    doc-agent-api.tar
    doc-agent-worker.tar
    openhands-agent-server.tar
    doc-agent-sandbox.tar
    postgres.tar
    redis.tar
    minio.tar
    qdrant.tar

  seed/
    default-doc-types/
    migrations/
    admin-user.json

  offline-deps/
    python-wheels/
    apt-debs/
    fonts/
    pandoc/
    libreoffice/
```

---

### 20.2 Docker Compose 服务

```yaml
services:
  web:
    image: doc-agent-web:VERSION
    ports:
      - "8080:80"

  api:
    image: doc-agent-api:VERSION
    env_file: .env
    depends_on:
      - postgres
      - redis
      - minio

  worker:
    image: doc-agent-worker:VERSION
    env_file: .env
    depends_on:
      - postgres
      - redis
      - minio

  agent-server:
    image: openhands-agent-server:VERSION
    env_file: .env
    volumes:
      - ./workspaces:/workspaces
      - ./doc-types:/doc-types:ro

  postgres:
    image: postgres:VERSION

  redis:
    image: redis:VERSION

  minio:
    image: minio:VERSION

  qdrant:
    image: qdrant:VERSION
```

---

### 20.3 环境变量

```env
APP_BASE_URL=http://doc-agent.internal

LLM_BASE_URL=http://local-llm.internal:8000/v1
LLM_API_KEY=dummy
LLM_MODEL=local/doc-agent-model
EMBEDDING_MODEL=local/embedding-model

POSTGRES_URL=postgresql://...
REDIS_URL=redis://redis:6379/0
MINIO_ENDPOINT=http://minio:9000

ENABLE_NETWORK_ACCESS=false
DEFAULT_TOOL_PERMISSION_MODE=restricted
```

---

### 20.4 离线构建原则

构建机可以联网，部署机不能联网。

构建阶段必须完成：

1. 下载 Python wheels；
2. 下载系统 deb 包；
3. 构建前端静态资源；
4. 固化 Node 依赖；
5. 固化字体；
6. 固化 Pandoc / LibreOffice；
7. 打包所有 Docker images；
8. 输出 `docker save` tar 文件；
9. 生成 SBOM 可选。

部署阶段禁止：

1. pip install 在线拉包；
2. npm install 在线拉包；
3. apt-get 在线拉包；
4. 下载字体；
5. 下载模型；
6. 访问互联网。

---

## 21. 安全设计

### 21.1 网络安全

默认：

```text
Agent sandbox 无外网
Agent sandbox 只能访问内网 LLM endpoint
Agent sandbox 不能访问 metadata service
Agent sandbox 不能访问其他任务目录
```

---

### 21.2 文件安全

1. 文档类型资产只读；
2. 每个任务 workspace 隔离；
3. 所有导出 artifact 存 MinIO；
4. 文件下载走鉴权 API；
5. 删除操作保留审计记录。

---

### 21.3 Prompt / 示例安全

需要防范：

1. 示例文档中的 prompt injection；
2. 用户上传素材中的恶意指令；
3. Agent 误把示例内容当系统指令；
4. Agent 泄露其他文档类型内容；
5. Agent 读取无关文件。

处理策略：

1. 示例和素材作为 data，不作为 instruction；
2. 系统 prompt 明确声明优先级；
3. 工具层限制可读路径；
4. 文档类型规范与用户素材分通道输入；
5. UI 展示引用来源。

---

## 22. 观测与审计

### 22.1 需要记录的事件

```text
user_message
agent_message
tool_call_requested
tool_call_started
tool_call_completed
tool_call_failed
approval_requested
approval_approved
approval_rejected
draft_created
draft_updated
draft_version_created
checklist_started
checklist_completed
export_started
export_completed
session_paused
session_resumed
session_cancelled
```

---

### 22.2 Trace 展示字段

每个事件展示：

1. 时间；
2. actor；
3. action；
4. input summary；
5. output summary；
6. 原始 payload；
7. token usage；
8. latency；
9. model；
10. tool；
11. workspace file changes；
12. approval status。

---

### 22.3 审计要求

管理员应能查看：

1. 谁创建了任务；
2. 谁上传了示例；
3. 谁修改了文档类型；
4. Agent 读取了哪些资产；
5. Agent 调用了哪些工具；
6. 谁批准了导出；
7. 最终文档基于哪个版本生成。

---

## 23. MVP 范围

### 23.1 MVP 必须包含

1. 用户登录；
2. 基础团队/权限；
3. 文档类型管理；
4. 上传示例、规范、检查单；
5. 创建文档任务；
6. Agent session；
7. 实时事件流；
8. 用户打断；
9. 工具调用可视化；
10. 草稿预览；
11. 草稿版本；
12. 局部修改；
13. checklist 运行；
14. DOCX 导出；
15. 离线 Docker Compose 部署；
16. 对接内网 OpenAI-compatible LLM。

---

### 23.2 MVP 可以暂缓

1. 复杂审批流；
2. 多级组织架构；
3. 实时多人协同编辑；
4. 高保真 DOCX 样式；
5. Excel / PPT 输出；
6. 高级权限矩阵；
7. 文档类型市场；
8. 自动评测排行榜；
9. Kubernetes 部署；
10. SSO 集成。

---

## 24. 里程碑计划

### Phase 0：技术验证，1–2 周

目标：验证 OpenHands Agent Server + 本地 OpenAI-compatible LLM + WebSocket events + 文档工具可行性。

交付：

1. OpenHands runtime PoC；
2. 单个 PRD 文档类型；
3. 一个示例检索工具；
4. 一个草稿写入工具；
5. 一个 checklist 工具；
6. 简单事件流 UI；
7. 本地 LLM 接入验证。

验收：

1. Agent 能读取文档类型配置；
2. Agent 能调用工具；
3. 前端能看到实时事件；
4. 用户能中途发消息影响 Agent；
5. Agent 能输出 Markdown 草稿。

---

### Phase 1：MVP，4–6 周

交付：

1. 文档类型管理；
2. 任务管理；
3. Agent 工作台；
4. 草稿版本；
5. 工具审批；
6. checklist；
7. DOCX 导出；
8. 离线部署包。

验收：

1. 至少支持 2 类文档；
2. 每类文档支持多个示例和规范；
3. 多用户可以创建任务；
4. 用户可打断 Agent；
5. 用户可局部重写；
6. Agent timeline 可审计；
7. 可在无互联网环境部署。

---

### Phase 2：产品化，6–10 周

交付：

1. 更完善 RBAC；
2. 文档类型版本发布；
3. 高级 diff；
4. 导出模板增强；
5. Agent trace 分析；
6. 任务归档；
7. 评测集；
8. 质量评分趋势；
9. 管理员控制台。

---

## 25. 关键风险与应对

### 风险 1：本地 LLM 能力不足

表现：

1. 长文档上下文不稳定；
2. 工具调用能力弱；
3. 遵循规范能力弱；
4. 局部修改时破坏其他章节。

应对：

1. 使用强 tool schema；
2. 减少任意自由生成；
3. 文档结构化存储；
4. 引入分章节编辑；
5. 使用 checklist 反复审校；
6. 要求本地模型至少支持较长上下文，建议 32k 以上，最好 64k/128k。

---

### 风险 2：OpenHands 偏 coding agent

表现：

1. 默认工具不适合文档任务；
2. UI 不适合直接复用；
3. Agent 可能倾向使用 shell 或代码方式解决问题。

应对：

1. 不直接复用 OpenHands UI；
2. 自研文档工作台；
3. 自定义文档工具；
4. 禁用或限制 shell；
5. 用文档 Skill Pack 约束 Agent 行为；
6. Runtime Adapter 解耦，避免锁死。

---

### 风险 3：文档仿写变成复制示例

应对：

1. 明确禁止复制示例原文；
2. 示例作为风格与结构参考；
3. 抽取 style signature；
4. 输出前做相似度检测；
5. UI 展示引用依据而非直接复制内容。

---

### 风险 4：过程可视化噪音过多

应对：

1. timeline 默认显示摘要；
2. 复杂 tool input/output 折叠；
3. 区分用户关心事件和 debug 事件；
4. 提供“普通视图 / 开发者视图”切换。

---

### 风险 5：离线依赖复杂

应对：

1. 从第一天使用离线构建；
2. CI 中固定所有 wheels、debs、node build；
3. 禁止运行时在线安装；
4. 定期做 air-gapped install 演练；
5. 输出完整 image tar 和 install script。

---

## 26. 推荐 PoC 任务

建议第一个 PoC 只做一种文档类型，例如 **PRD**。

### 输入

1. 3 篇优秀 PRD 示例；
2. 1 份 PRD 写作规范；
3. 1 份 PRD 检查单；
4. 1 段用户 brief；
5. 1 份会议纪要。

### 用户目标

```text
请基于这些材料写一版 PRD，风格参考示例 1 和示例 2。
先给我大纲，不要直接写全文。
```

### 期望过程

1. Agent 读取 PRD Skill；
2. Agent 分析示例；
3. Agent 输出大纲；
4. 用户修改大纲；
5. Agent 生成第一版；
6. 用户要求只重写指标章节；
7. Agent 局部修改；
8. Agent 跑 checklist；
9. 用户批准导出 DOCX。

### 验收指标

1. 能中途打断；
2. 能局部修改；
3. 能展示工具调用；
4. 能展示引用示例；
5. 能展示 checklist；
6. 能导出 DOCX；
7. 能离线运行。

---

## 27. 初版结论

这套系统的正确定位不是“文档生成 workflow”，而是：

> 基于成熟 Agent Runtime 的离线文档协作工作台。

推荐路线是：

```text
OpenHands SDK / Agent Server
  + 自研 Document Workbench UI
  + 文档类型 Skill Pack
  + 文档领域工具层
  + 任务/权限/审计业务层
  + 内网 OpenAI-compatible LLM
  + Air-gapped Docker Compose 部署
```

这能同时满足你的两个强约束：

1. **完全离线部署**：平台、runtime、沙箱、依赖、前端、导出工具都打包进离线部署包。
2. **可配置、多文档类型、多用户、可观测**：文档类型包、Agent Session、工具事件、草稿版本、审批和审计都作为一等对象设计。

最重要的是，它保留了你强调的 Claude Code 类核心体验：

```text
可打断
可插话
可继续
可局部重写
可审批
可回滚
可观察过程
可持续迭代
```

而不是“一次生成失败就只能重来”的固定流程。

[1]: https://docs.openhands.dev/sdk/arch/sdk?utm_source=chatgpt.com "SDK Package - OpenHands Docs"
[2]: https://docs.openhands.dev/sdk/arch/agent?utm_source=chatgpt.com "Agent - OpenHands Docs"
[3]: https://docs.openhands.dev/sdk/arch/conversation?utm_source=chatgpt.com "Conversation - OpenHands Docs"
[4]: https://docs.openhands.dev/sdk/arch/agent-server?utm_source=chatgpt.com "Agent Server Package - OpenHands Docs"
[5]: https://docs.openhands.dev/sdk/guides/agent-server/local-server?utm_source=chatgpt.com "Local Agent Server - OpenHands Docs"
[6]: https://docs.claude.com/en/docs/agent-sdk/permissions?utm_source=chatgpt.com "Handling Permissions - Claude Docs"
