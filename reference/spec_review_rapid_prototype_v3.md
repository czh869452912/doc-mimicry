# DocAgent Workbench 快速原型审查 V3：文档版 Claude Code

> 核心修正：目标不是 Dify 式固定工作流，也不是 RAG 知识库问答，而是把 Claude Code / OpenHands 的 vibe coding 体验迁移到文档创作。
>
> V3 保留 V2 的低成本路线：优先复用成熟 coding-agent runtime、默认文件工具、workspace、event stream 和 sandbox。
> 但 V3 不再追求“极致零自研”，而是补齐文档版 Claude Code 所需的最小产品纪律：工作区契约、上下文文件、通用系统提示词、文档类型 Skill Pack、版本纪律和 Timeline 语义增强。

---

## 一、V2 哪里需要修正

V2 的关键判断是对的：

1. 文档创作不应该做成固定 DAG workflow。
2. 第一版不应该为每个文档动作都写高层 Document Tool。
3. OpenHands / Claude Code 类 coding-agent runtime 的心智，比 Dify / Flowise / n8n 更接近目标体验。
4. 默认 `read_file`、`write_file`、`edit_file`、`bash`、`glob`、`grep` 已经足够支撑第一条链路。

但 V2 有几个偏差：

| V2 表述 | 问题 | V3 修正 |
|---|---|---|
| “这些工具已经足够完成所有文档操作” | 工具够用，但产品纪律不够 | 保留默认工具，补工作区契约和上下文文件 |
| “RAG / 语义检索可选 Phase 1 后” | 容易把重点带偏到内容语义匹配 | 主线改为结构/风格/组织方式提取，RAG 仅用于大规模资产发现 |
| “Agent 自己读示例后写 style_notes” | 方向对，但缺少强制产物 | 将 `style_notes.md`、`structure_notes.md`、`doc_map.md` 设为必写上下文文件 |
| “每次重要修改前复制版本” | 只靠 prompt 容易失效 | 后端或脚本自动做 checkpoint，Timeline 记录版本 |
| “Timeline 通过 Agent 主动汇报” | 可以演示，但审计语义不稳定 | 后端基于路径和上下文文件做事件语义增强 |
| “FastAPI 只做透传” | 太薄，无法支撑多人、版本、审计 | FastAPI 做产品状态，不介入 Agent 推理 |

一句话：

> V2 应从“零自定义 Tools 的套壳”修正为“默认工具 + 文档工作区契约 + 通用 Skill 机制 + 最小产品薄层”。

---

## 二、产品定位

DocAgent Workbench 的正确定位是：

> 文档版 Claude Code。

它不是：

1. 一次性文档生成器；
2. 表单驱动的文档模板工具；
3. Dify 式固定流程应用；
4. 面向语义问答的 RAG 知识库；
5. 针对每类文档单独定制的 workflow 系统。

它是：

1. 用户把需求、材料、示例、规范放进一个 workspace；
2. Agent 像 Claude Code 读代码仓库一样读文档资产；
3. Agent 总结这个文档类型的组织方式和表达习惯；
4. Agent 给出计划，等待用户确认；
5. 用户随时插话、纠偏、局部要求重写；
6. Agent 维护上下文、版本、草稿和检查记录；
7. 用户观察过程，最终批准导出。

核心体验关键词：

```text
自由对话
人在环
可打断
可继续
可局部重写
自动组织上下文
基于 skill 泛化到不同文档类型
仿结构、仿叙事、仿组织方式，而不是按语义检索套内容
```

---

## 三、修正后的总体架构

```
┌───────────────────────────────────────────────────────────────┐
│  React 文档工作台                                                │
│  - Chat / Agent Timeline / Tool Events                         │
│  - Markdown 预览 / Diff / 版本列表                              │
│  - 用户打断 / 审批 / 导出                                        │
├───────────────────────────────────────────────────────────────┤
│  FastAPI 产品薄层                                                │
│  - 用户、团队、任务、文档类型配置                                 │
│  - Workspace 初始化与资产挂载                                    │
│  - 版本、artifact、审计、Timeline 语义增强                       │
│  - 透传或适配 Agent Server                                       │
├───────────────────────────────────────────────────────────────┤
│  Coding-Agent Runtime                                            │
│  - 优先验证 OpenHands Agent Server / SDK                         │
│  - 保留替代可能：Goose、OpenCode、Continue headless、Claude Code SDK │
│  - 必须具备 agent loop、文件工具、事件流、sandbox、上下文压缩       │
├───────────────────────────────────────────────────────────────┤
│  Document Workspace Contract                                     │
│  - 固定目录结构                                                   │
│  - 上下文文件                                                     │
│  - 版本纪律                                                       │
│  - 检查单与导出约定                                               │
├───────────────────────────────────────────────────────────────┤
│  DocType Skill Pack                                               │
│  - SKILL.md                                                       │
│  - examples/                                                      │
│  - specs/                                                         │
│  - checklists/                                                    │
│  - optional export references/                                    │
└───────────────────────────────────────────────────────────────┘
```

关键原则：

1. Agent Runtime 仍然是 coding-agent runtime，不改造成工作流引擎。
2. 文档类型不是模板流程，而是一组 Agent 可阅读的项目资产。
3. FastAPI 不替 Agent 做推理，只维护产品状态和安全边界。
4. RAG 不是主心智；优先让 Agent 阅读少量高质量示例并生成结构/风格笔记。
5. 自定义 Document Tools 暂缓，但允许固定脚本作为 workspace utilities。

---

## 四、Workspace Contract

每个任务都创建一个独立 workspace。

```text
/workspace/{task_id}/
  brief.md                    # 用户原始需求，后端创建
  inputs/                     # 用户上传材料，后端放入
  context/
    user_intent.md            # Agent 对用户目标和约束的理解
    doc_map.md                # 当前草稿章节地图
    style_notes.md            # 从示例中抽取的叙述方式、语气、信息密度
    structure_notes.md        # 从示例中抽取的章节组织、表格/列表模式
    decision_log.md           # 用户确认过的关键决定
    open_questions.md         # 未解决问题
    draft_summary.md          # 当前草稿摘要，供长会话压缩后恢复
  draft/
    outline.md
    draft.md                  # 当前工作稿
    sections/                 # 可选：结构化章节拆分
  versions/
    v001.md
    v002.md
    v003.md
  reviews/
    checklist_result.md
    self_review.md
  artifacts/
    output.docx
    output.pdf
  logs/
    agent_notes.md
```

文档类型资产只读挂载：

```text
/doc-types/{doc_type}/
  SKILL.md
  examples/
  specs/
  checklists/
  templates/
```

### 必写上下文文件

V3 要求 Agent 在正式写草稿前必须产出：

1. `context/user_intent.md`
2. `context/style_notes.md`
3. `context/structure_notes.md`
4. `draft/outline.md`

这些文件相当于文档版的 repo map、plan 和 working memory。

当用户插话、修改方向、锁定章节或确认计划时，Agent 必须更新：

1. `context/decision_log.md`
2. `context/open_questions.md`
3. `context/draft_summary.md`
4. `context/doc_map.md`

---

## 五、通用系统提示词

V3 的重点不是给每种文档类型写 workflow，而是设计一套通用文档协作 system prompt。

通用系统提示词应约束 Agent：

```markdown
# DocAgent Core Behavior

你是一个文档协作 Agent，工作方式类似 Claude Code，但对象是文档 workspace。

## 你的核心任务

1. 读取用户需求、输入材料、文档类型 SKILL 和参考示例。
2. 从参考示例中学习结构、叙述方式、信息密度、标题层级、表格/列表模式和检查习惯。
3. 不要把参考示例当成和当前任务语义相关的资料，除非用户明确要求。
4. 不要复制示例原文。
5. 写全文前先输出计划和大纲，等待用户确认。
6. 用户随时插话时，优先遵守最新用户指令，并更新 decision_log。
7. 局部修改时，只改相关章节，保护用户明确要求保留的部分。
8. 每次重要修改前创建新版本。
9. 导出前运行检查单并记录结果。

## 工作区纪律

- 在正式写作前维护 context/style_notes.md 和 context/structure_notes.md。
- 当前草稿写在 draft/draft.md。
- 版本写在 versions/vNNN.md。
- 检查结果写在 reviews/checklist_result.md。
- 不要修改 /doc-types 下的只读资产。

## 交互纪律

- 遇到重大假设时先问用户。
- 每完成一个关键阶段，用自然语言向用户简短说明。
- 不要把内部推理完整展开给用户，但要说明你基于哪些文件和约束行动。
```

---

## 六、DocType Skill Pack

每个文档类型只定义“这个文档类型的写作习惯”，不定义固定流程。

```text
doc-types/
  prd/
    SKILL.md
    examples/
      example_001.md
      example_002.md
    specs/
      style_guide.md
      structure_rules.md
      terminology.md
    checklists/
      quality.yaml
  export-references/
    reference.docx              # 仅用于导出样式，不作为写作模板
```

`SKILL.md` 示例：

```markdown
---
name: prd-document-skill
description: Use when writing, revising, reviewing, or imitating PRD-style documents.
---

# PRD 文档写作 Skill

## 你要模仿什么

从 examples/ 中学习：

- 章节顺序
- 标题颗粒度
- 背景、目标、非目标的叙述节奏
- 指标和验收标准的表达方式
- 表格、列表、编号的使用方式
- 风险、依赖、决策记录的组织方式

不要模仿：

- 示例项目的业务内容
- 示例中的具体指标数值
- 示例里的专有名称
- 示例原文句子

## PRD 通常需要包含

- 背景
- 目标
- 非目标
- 用户与场景
- 需求说明
- 交互或流程
- 指标与验收标准
- 风险与依赖
- 待确认问题

如果用户需求不足，不要编造关键事实，先列出假设或问题。

## 检查习惯

导出前读取 checklists/quality.yaml，并在 reviews/checklist_result.md 中记录逐项结果。
```

这个设计可以泛化到：

1. 方案建议书；
2. 法务备忘录；
3. 竞品分析；
4. 复盘报告；
5. 投标文件；
6. 周报；
7. 客户成功方案。

每类文档都只是换一组示例、规范、检查单和 Skill，而不是单独写 workflow。
如果存在 `reference.docx`，它只用于 Pandoc/LibreOffice 的导出样式参考，不参与内容组织和章节模板设计。

---

## 七、RAG 的位置：后置，而不是主线

V3 明确不把 RAG 作为核心路线。

原因：

1. 目标不是根据 A 项目内容回答 B 项目问题。
2. 参考示例的价值主要是结构、叙述方式和组织习惯。
3. 语义检索容易错误地把“内容相似”当成“格式可仿”。
4. 第一版示例数量应控制在 2-5 篇高质量文档，Agent 可以直接阅读。

更适合的能力是：

```text
doc map / style map / structure map
```

也就是让 Agent 先读示例，抽取：

1. 章节地图；
2. 标题层级；
3. 段落长度；
4. 表格模式；
5. 指标写法；
6. 决策表达；
7. 风险表达；
8. 结尾方式。

当示例数量超过 10 篇后，可以增加“结构索引”，但它仍然不是传统 RAG：

```text
example_id
section_title
section_role
heading_level
paragraph_density
table_pattern
list_pattern
style_tags
```

Agent 检索的是“哪份示例有我需要模仿的章节组织方式”，不是“哪段内容和用户问题语义相似”。

---

## 八、最小脚本，而不是自定义 Document Tools

V3 仍然不建议第一版写 15 个 OpenHands custom tools。

但可以放少量固定脚本到 sandbox 中，由 Agent 通过受控 bash 调用：

```text
/tools/
  parse_inputs.py        # 把 docx/pdf/txt/md 转为 workspace 可读 markdown
  checkpoint.py          # 保存 draft/draft.md 到 versions/vNNN.md
  export_docx.py         # 调 pandoc / libreoffice 导出
  render_diff.py         # 可选：生成 diff 摘要
  validate_workspace.py  # 检查必写上下文文件是否存在
```

这些脚本不是 Agent 高层工具，不参与复杂 tool schema 设计。

它们的定位是 workspace utilities：

1. 降低 bash 风险；
2. 固化版本和导出纪律；
3. 减少 Agent 手写命令出错；
4. 方便 Timeline 识别语义。

Phase 0 可以只做：

```text
checkpoint.py
export_docx.py
validate_workspace.py
```

`parse_inputs.py` 可以根据输入格式复杂度决定是否加入。

---

## 九、Timeline 语义增强

只展示 `read_file` / `write_file` / `bash` 会让用户感觉过程不可理解。

V3 采用“路径 + 文件角色 + 脚本名”的语义映射：

| 原始事件 | 展示语义 |
|---|---|
| `read_file /doc-types/prd/SKILL.md` | 读取 PRD 写作 Skill |
| `read_file /doc-types/prd/examples/*` | 分析最佳实践示例 |
| `write_file context/style_notes.md` | 提取文档风格 |
| `write_file context/structure_notes.md` | 提取文档结构 |
| `write_file draft/outline.md` | 生成大纲 |
| `write_file draft/draft.md` | 生成或更新草稿 |
| `bash python /tools/checkpoint.py` | 创建草稿版本 |
| `write_file reviews/checklist_result.md` | 运行检查单 |
| `bash python /tools/export_docx.py` | 导出 DOCX |

Timeline 默认展示语义事件，允许展开原始 tool call。

这比写自定义 Document Tool 成本低，但比 V2 的“让 Agent 主动汇报”更稳。

---

## 十、安全和权限修正

V3 不应让 `execute_bash` 成为无限 shell。

Phase 0 的安全策略：

1. `/doc-types` 只读；
2. 每个 task 独立 workspace；
3. Agent sandbox 禁止外网；
4. bash 命令默认高风险；
5. 自动允许固定脚本：
   - `python /tools/checkpoint.py ...`
   - `python /tools/export_docx.py ...`
   - `python /tools/validate_workspace.py ...`
   - `pandoc` 仅由 `export_docx.py` 间接调用；
6. 删除文件、覆盖版本、读取其他 workspace 一律禁止或审批。

如果 OpenHands security analyzer 足够可配，则复用其审批。
如果不够可配，FastAPI adapter 层做命令 allowlist。

---

## 十一、Phase 0 PoC

### 目标

验证“文档版 Claude Code”的最小体验，而不是验证 RAG 或 workflow。

### 输入

1. 一个文档类型：PRD；
2. 2-3 篇优秀 PRD 示例；
3. 1 份 PRD 写作规范；
4. 1 个检查单；
5. 用户可以只输入一句需求，也可以上传会议纪要、产品想法、竞品截图转文字等材料。

### 期望过程

```text
用户：帮我基于这些材料写一版 PRD，风格参考现有最佳实践。

Agent：
1. 读取 brief.md 和 inputs/
2. 读取 /doc-types/prd/SKILL.md
3. 读取 2-3 个 examples
4. 写 context/style_notes.md
5. 写 context/structure_notes.md
6. 写 draft/outline.md
7. 向用户说明计划并等待确认

用户：第三章要面向高管，不要写太细的技术方案。

Agent：
8. 更新 context/decision_log.md
9. checkpoint 当前状态
10. 写 draft/draft.md
11. 更新 context/doc_map.md 和 draft_summary.md

用户：只重写指标部分，像示例 2 一样。

Agent：
12. 读取示例 2 的指标章节
13. checkpoint
14. 只修改指标相关章节
15. 给出 diff 摘要

用户：导出。

Agent：
16. 读取 checklist
17. 写 reviews/checklist_result.md
18. 请求最终确认
19. 调用 export_docx.py
```

### 验收指标

1. 不需要为 PRD 写固定工作流；
2. 用户可中途插话；
3. Agent 能维护上下文文件；
4. Agent 能从示例抽取风格和结构，而不是复制内容；
5. Agent 能局部修改，不破坏无关章节；
6. Timeline 能显示“分析示例、提取风格、生成大纲、创建版本、运行检查、导出”等语义事件；
7. 能导出 DOCX；
8. 整体可离线运行。

---

## 十二、Week 1 实施建议

### Day 1：Runtime 验证

1. 启动 OpenHands Agent Server 或等价 coding-agent runtime。
2. 接入本地 OpenAI-compatible LLM。
3. 验证 event stream、文件读写、用户插话。

### Day 2：Workspace Contract

1. 创建固定 workspace 目录结构。
2. 准备 `/doc-types/prd`。
3. 写通用 system prompt 和 PRD `SKILL.md`。

### Day 3：上下文文件纪律

1. 要求 Agent 生成 `style_notes.md`、`structure_notes.md`、`outline.md`。
2. 测试只输入一句需求和上传材料两种入口。
3. 测试 Agent 是否能先计划再写作。

### Day 4：版本与局部修改

1. 加 `checkpoint.py`。
2. 测试用户插话和局部重写。
3. 前端或日志中展示 diff 摘要。

### Day 5：检查和导出

1. 加 `validate_workspace.py`。
2. 加 `export_docx.py`。
3. 跑 checklist。
4. 导出 DOCX。
5. 整理 Timeline 语义映射。

Week 1 不做：

1. RAG；
2. 多文档类型；
3. 高保真排版；
4. 完整 RBAC；
5. 高层 Document Tools；
6. 复杂审批流；
7. 文档类型模板设计器。

---

## 十三、V2 到 V3 的取舍总结

| 维度 | V2 | V3 |
|---|---|---|
| 产品心智 | OpenHands 套文档皮肤 | 文档版 Claude Code |
| 工作方式 | 默认工具 + Skill Prompt | 默认工具 + Skill + Workspace Contract |
| 文档类型 | 示例/规范/检查单目录 | 可泛化 Skill Pack |
| 仿写重点 | 风格规则，描述较粗 | 结构、叙述、组织方式、信息密度 |
| RAG | Phase 1 可选 | 明确后置，避免本末倒置 |
| 上下文 | Agent 自行分析 | 强制上下文文件 |
| 版本 | Agent 复制文件 | checkpoint 脚本或后端版本 |
| Timeline | Agent 主动汇报 | 路径/脚本语义增强 |
| FastAPI | 尽量透传 | 产品状态薄层 |
| 自定义 Tools | 0 | 仍为 0，但允许固定脚本 |

最终建议：

> Phase 0 不要做“文档工作流平台”，也不要做“知识库 RAG 写作”。
> 只做一个文档 workspace，让 Agent 像 Claude Code 读项目一样读文档类型资产、理解写法、维护上下文、反复改稿、可被用户随时打断。
