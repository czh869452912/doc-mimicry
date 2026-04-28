# DocAgent Workbench 快速原型审查 V2：极致套壳（零自定义 Tools）

> 核心思路：Document Tools 全部砍掉，内化成 Skill Prompt + 默认文件操作。
> 目标：进一步压缩自研量，做到"OpenHands 套个文档皮肤"。

---

## 一、为什么不写 Document Tools

OpenHands 默认已带的工具（V1 SDK）：

| 默认工具 | 文档场景中的用途 |
|---------|----------------|
| `read_file` | 读示例、读规范、读检查单、读草稿 |
| `write_file` | 写大纲、写草稿、写风格签名 |
| `edit_file` | 局部改章节、替换段落 |
| `execute_bash` | 跑 pandoc 导出 docx、文件列表、文本处理 |
| `glob` / `grep` | 发现示例文件、搜索规范内容 |

**这些工具已经足够完成所有文档操作。**

之前 spec 设计 Document Tools 的出发点是：
1. 更安全（限制路径）
2. 更容易审批（语义清晰）
3. 更容易可视化（tool name 就知道在干什么）

但代价是：
- 要写 ~15 个工具的 Definition + Executor + Schema
- 要注册到 OpenHands
- 要维护工具文档让 Agent 理解

**对于"最快原型"这个约束，代价大于收益。**

---

## 二、零自定义 Tools 的套壳架构

```
┌─────────────────────────────────────────────────────────────┐
│  自研前端：文档工作台（React）                               │
│  - 三栏布局                                                 │
│  - Markdown 预览（react-markdown）                          │
│  - diff 视图（@git-diff-view/react）                        │
│  - Agent Timeline（对接 OpenHands event stream）            │
├─────────────────────────────────────────────────────────────┤
│  自研薄层：FastAPI 网关（~300行，更薄了）                    │
│  - /doc-types：配置 CRUD + 文件上传                         │
│  - /tasks：任务元数据                                       │
│  - /sessions：透传 OpenHands Agent Server                   │
├─────────────────────────────────────────────────────────────┤
│  ████████████████████████████████████████████████████████   │
│  █ 直接搬：OpenHands Agent Server + SDK V1              █   │
│  █  - Agent Loop + Event Stream + Sandbox（完全不动）   █   │
│  █  - 默认工具集：read/write/edit/bash/glob/grep（不动） █   │
│  ████████████████████████████████████████████████████████   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  只读挂载：/doc-types/{doctype}/examples/           │    │
│  │           /doc-types/{doctype}/specs/               │    │
│  │           /doc-types/{doctype}/checklists/          │    │
│  │           /doc-types/{doctype}/templates/           │    │
│  │           /doc-types/{doctype}/SKILL.md             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  可写 Workspace：/workspace/{task}/brief.md          │    │
│  │                /workspace/{task}/draft/              │    │
│  │                  - outline.md                        │    │
│  │                  - draft_v1.md                       │    │
│  │                  - draft_v2.md                       │    │
│  │                /workspace/{task}/artifacts/          │    │
│  │                /workspace/{task}/logs/               │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、Agent 怎么干活（Skill Prompt 驱动）

不再通过 Tools 约束 Agent，而是通过 **SKILL.md + system prompt** 约束。

### SKILL.md 示例

```markdown
---
skill: prd-writer
---

# PRD 写作指南

## 可访问的资产

所有示例和规范都在只读目录：
- `/doc-types/prd/examples/` — 最佳示例
- `/doc-types/prd/specs/` — 写作规范
- `/doc-types/prd/checklists/prd_quality.yaml` — 质量检查单

## 工作流程

1. 读取 `/doc-types/prd/SKILL.md`（本文件）
2. 用 `glob` 列出 `/doc-types/prd/examples/` 下的所有示例
3. 读取 2-3 个最相关的示例，分析结构和风格
4. 读取 `/doc-types/prd/specs/` 下的规范文件
5. 向用户提出写作计划，等待确认
6. 在 `/workspace/{task}/draft/` 下工作：
   - 先写 `outline.md`
   - 用户确认后，逐步写 `draft_v1.md`
   - 每次重要修改前，先复制当前版本（如 draft_v1 → draft_v2）
7. 完成草稿后，读取检查单并逐条自检
8. 导出时，用 bash 执行：
   ```
   pandoc /workspace/{task}/draft/draft_v2.md \
     -o /workspace/{task}/artifacts/output.docx \
     --reference-doc=/doc-types/prd/templates/template.docx
   ```

## 风格规则

- 不要复制示例原文
- 模仿章节结构、信息密度、表格使用方式
- 每个核心需求必须包含用户价值和验收标准
- 指标必须包含定义、口径、观察方式

## 检查单

导出前必须运行 `/doc-types/prd/checklists/prd_quality.yaml` 中的检查，
并在 `/workspace/{task}/logs/checklist_result.md` 记录结果。
```

### Agent 的实际操作流

```text
用户：基于这些材料写一版 PRD

Agent:
1. bash: ls /doc-types/prd/examples/          → 发现 3 个示例
2. read_file: /doc-types/prd/examples/ex1.md  → 分析结构
3. read_file: /doc-types/prd/examples/ex2.md  → 分析风格
4. read_file: /doc-types/prd/specs/style.md   → 读规范
5. write_file: /workspace/task_123/draft/outline.md → 写大纲
6. [event: ask_user] "计划如下：... 确认吗？"

用户：确认，第三章改成面向高管

Agent:
7. write_file: /workspace/task_123/draft/draft_v1.md → 写全文
8. read_file: /workspace/task_123/draft/draft_v1.md  → 自检
9. edit_file: /workspace/task_123/draft/draft_v1.md  → 改第三章
10. bash: pandoc ... → 导出 docx
```

**Agent 全程只使用了默认工具：`read_file`、`write_file`、`edit_file`、`execute_bash`、`glob`。**

---

## 四、还要保留什么"非默认"的东西？

理论上可以做到 100% 零自定义 Tools，但以下两点建议保留轻量封装：

### 4.1 RAG / 语义检索（可选 Phase 1 后）

如果示例很多（>10 个），Agent 用 `glob` + `read_file` 全读会爆上下文。

**最小方案：**
- 后端预先把所有示例切成 chunk，embed 到 pgvector
- 提供一个 **HTTP API**（不是 OpenHands Tool）：`POST /api/retrieve?q=metrics+section`
- Agent 通过 `execute_bash` + `curl` 调用这个 API
- 或者更直接：Agent 用 bash 调用一个预置的 Python 脚本 `python /tools/retrieve.py "metrics section"`

**更懒的方案（Phase 0）：**
- 示例不超过 5 个，Agent 直接全部读进上下文
- 不需要 RAG

### 4.2 检查单结构化执行（可选）

Agent 读 YAML 检查单，自己判断 pass/fail，结果写入 markdown log。**这完全不需要工具**，只是 prompt 里要求 Agent 按格式输出：

```markdown
## 检查单结果

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 目标清晰 | ✅ | 第2节明确了业务目标 |
| 指标可度量 | ❌ | 第4节"提升用户体验"未定义指标 |
```

如果后续需要**机器可读的**检查单结果（打分、趋势图），再写一个简单的 checklist runner 脚本，Agent 用 bash 调用它。

### 4.3 风格签名提取（Phase 1 后）

Phase 0 可以让 Agent 自己读示例后，在 `style_notes.md` 里写分析笔记。

Phase 1 再考虑自动提取（用一个离线脚本跑，不入 Agent Loop）。

---

## 五、自研量再次压缩后的清单

| 模块 | V1 方案（自定义Tools） | V2 方案（零自定义Tools） |
|------|----------------------|------------------------|
| **Agent Loop / Event Stream / Sandbox** | 搬 OpenHands | 搬 OpenHands |
| **自定义 Tools（~15个）** | 自研 2-3 天 | **砍掉，工作量=0** |
| **Tool 注册框架** | 照抄 OpenHands | **不需要** |
| **Document Agent Preset** | 照抄 preset 结构 | 简化为 **SKILL.md + system prompt** |
| **SKILL.md 设计** | 需要 | 需要（1天） |
| **FastAPI 业务网关** | ~500行 | **~200行**（只做配置管理+透传） |
| **前端文档工作台** | 3-5 天 | 3-5 天（不变） |
| **RAG 检索** | 自定义 Tool | **bash 调用脚本 / 暂缓** |
| **检查单执行** | 自定义 Tool | **Agent 自评 / bash 调用脚本** |
| **导出 DOCX** | 自定义 Tool | **Agent 执行 bash: pandoc** |
| **风格签名** | 自定义 Tool | **Agent 写笔记 / 离线脚本** |

**V2 相比 V1，又省了 ~3-4 天的工具开发量。**

---

## 六、Week 1 就能验证的 PoC

### 目标：Agent 能读示例、写大纲、写草稿、导出 DOCX

**Day 1：搭壳**
```bash
git clone https://github.com/All-Hands-AI/OpenHands
cd OpenHands
# 启动 local agent server（官方文档有 docker-compose）
```

**Day 2：准备资产**
```text
doc-types/
  prd/
    SKILL.md              ← 写一份 PRD 写作 skill prompt
    examples/
      ex1.md
      ex2.md
    specs/
      style_guide.md
    checklists/
      quality.yaml        ← 简单 YAML，Agent 自己会读
    templates/
      template.docx       ← Pandoc reference doc
```

**Day 3：配置 OpenHands**
- 配置 `LLM_BASE_URL` 指向本地模型
- 配置 workspace 挂载路径
- 把 `doc-types/` 挂载为只读

**Day 4：跑通第一个会话**
```text
用户消息：
"请基于 /doc-types/prd/examples/ 下的示例，帮我写一份 PRD。
先读 SKILL.md 和示例，然后给我大纲。"

期望 Agent 行为：
1. read_file /doc-types/prd/SKILL.md
2. glob /doc-types/prd/examples/*.md
3. read_file ex1.md, ex2.md
4. write_file /workspace/task_001/draft/outline.md
5. [ask_user] "大纲如下：... 确认吗？"
```

**Day 5：验证导出**
```text
用户：确认，写全文并导出 DOCX

Agent：
1. write_file draft_v1.md
2. execute_bash "pandoc draft_v1.md -o output.docx --reference-doc=..."
3. [event] 告知用户完成
```

**Week 1 结束即完成核心链路验证。**

---

## 七、Timeline 可视化怎么办？

用户会问：如果 Agent 只用 `read_file`、`write_file`，Timeline 上不就全是"读文件""写文件"，看不出来它在"分析示例"还是"写大纲"？

**几个解决方案：**

### 方案 A：Agent 在关键节点主动发消息（推荐）

OpenHands 的 Agent 在思考过程中会输出自然语言消息（不是 tool call）。这些消息会作为 event 进入 event stream。

只要 prompt 里要求 Agent 在关键步骤主动汇报：
```
每完成一个重要阶段，用自然语言向用户汇报你的进展，例如：
- "我已读完3个示例，正在总结结构特征..."
- "大纲已写好，保存在 draft/outline.md"
- "正在根据你的意见修改第三章..."
```

Timeline 上就会显示：
```
10:01  Agent: 我已读完3个示例，正在总结结构特征...
10:02  Tool: read_file /doc-types/prd/examples/ex1.md
10:03  Tool: read_file /doc-types/prd/examples/ex2.md
10:04  Agent: 大纲已写好，保存在 draft/outline.md
10:05  Tool: write_file /workspace/task/draft/outline.md
```

### 方案 B：后端做 event 语义增强（Phase 1）

FastAPI 网关订阅 OpenHands event stream，根据文件路径做语义映射：
- `read_file /doc-types/*/examples/*` → 显示"📖 分析示例"
- `write_file */draft/outline.md` → 显示"📝 生成大纲"
- `edit_file */draft/*.md` → 显示"✏️ 修改草稿"
- `execute_bash pandoc*` → 显示"📄 导出文档"

这个映射规则很简单，不需要改 Agent，纯后端过滤层。

---

## 八、安全与隔离

| 风险 | 应对 |
|------|------|
| Agent 用 bash 执行危险命令 | OpenHands security analyzer 会给 bash 命令打风险标签，可配置高危命令需审批 |
| Agent 读写其他任务目录 | Docker workspace 每个 session 独立，天然隔离 |
| Agent 改 doc-types 资产 | 只读挂载，物理上不可写 |
| Agent 访问外网 | Docker 网络隔离，只允许访问内网 LLM endpoint |

**全部复用 OpenHands 原生安全机制，无需自研。**

---

## 九、一句话总结

> **OpenHands + SKILL.md + 默认文件工具 = 最快套壳路线。**
>
> 不需要写一个自定义 Tool，Agent 读示例、写草稿、跑检查单、导出 DOCX 全部用 `read/write/edit/bash` 完成。
>
> 自研只剩：**前端皮肤 + FastAPI 配置网关 + SKILL.md 设计**。
