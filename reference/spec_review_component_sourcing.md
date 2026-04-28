# DocAgent Workbench 方案审查：现成组件替代建议

> 目标：针对 `spec_v0_1.md` 的每层选型，寻找可直接复用的开源组件，**最大化"抄"，最小化自研**。

---

## 一、Agent Runtime 层（核心底座）

### Spec 选型
OpenHands SDK / Agent Server

### 审查结论
**OpenHands 可以保留，但建议补充或评估 LangGraph 作为替代/并行方案。** OpenHands 在 2025-2026 年已完成 V1 架构重构，确实提供了 pause/resume、security analyzer、event stream、Docker sandbox 等能力。但风险也很明显：它天生为 coding agent 设计，默认工具集（shell、browser、file editor）与文档写作场景不匹配。

### 可抄的现成方案

| 方案 | 适用场景 | stars/成熟度 | 建议 |
|------|---------|-------------|------|
| **OpenHands SDK V1** | 需要 sandbox + remote execution + 事件流 | 64k+，持续迭代 | **保留作为候选**，PoC 验证文档场景适配成本 |
| **LangGraph** | 需要 stateful agent loop + HITL + checkpoint | LangChain 生态核心，Klarna/Replit 生产使用 | **强烈建议评估**。原生支持 `interrupt()`、`Command(resume=...)`、`MemorySaver`/`PostgresSaver` checkpoint，与文档写作的非固定 workflow 理念完美契合 |
| **Dify (开源版)** | 需要完整 LLM 应用平台（workflow + RAG + agent + 观测） | 114k+ stars，2025 推出 plugin 生态 | **如果愿意放宽架构自由度**，Dify 本身就是一个可自托管的完整平台，含可视化 workflow、Agent node、知识库、日志观测，可大幅减少前后端自研量 |
| **Flowise** | 低代码 agent/workflow 构建 | 30k+ stars | 比 Dify 更轻，但生态稍弱 |

### 推荐策略
```
路线 A（保守）：OpenHands SDK + 自研 Document Skill Pack + Runtime Adapter
路线 B（推荐）：LangGraph + LangChain + 自研 Document Tools + Postgres Checkpoint
路线 C（激进少自研）：Dify 开源版二次开发，复用其 workflow + RAG + 观测能力，只自研文档工作台前端
```

**如果团队目标是"最少自研"，路线 C（基于 Dify）值得认真考虑。** Dify 的 self-host 架构本身就是 PostgreSQL + Redis + 向量存储 + Docker Compose，与 spec 的存储层完全对齐。

---

## 二、后端业务服务层

### Spec 选型
FastAPI / Python

### 审查结论
**FastAPI 正确，无需替换。** 但需要为每个业务模块寻找现成库，避免从零写 CRUD、权限、Admin。

### 可抄的现成组件

#### 2.1 权限与认证（RBAC）
| 组件 | 能力 | 建议 |
|------|------|------|
| **fastapi-user-auth** | 基于 Casbin 的完整 RBAC，自带 JWT/Db/Redis Token 后端，**自带可视化管理后台**（基于 Amis Admin） | **强烈推荐**。一行代码搞定用户/角色/权限/菜单/字段级权限，且自带 admin UI，MVP 可直接用 |
| **casbin-fastapi-decorator** | 更轻量的 Casbin 装饰器，支持 DB 动态策略加载 | 如果不需要 admin UI，选这个 |
| **fastapi-users** | 经典用户认证库，支持 OAuth2/JWT | 只解决认证，不解决授权，需配合 Casbin |

**推荐：直接用 `fastapi-user-auth`，MVP 连管理员后台都省了。**

#### 2.2 Admin 管理后台
| 组件 | 能力 | 建议 |
|------|------|------|
| **FastAPI-Amis-Admin** | 基于百度 Amis 低代码前端，自动从 SQLModel 生成增删改查界面 | 与 fastapi-user-auth 同源，配合极佳 |
| **Refine + Ant Design** | React 生态的 admin 框架 | 如果前端自研，可用 Refine 快速搭后台 |

**推荐：MVP 用 FastAPI-Amis-Admin 生成基础管理界面，后续再替换为自研 React 前端。**

#### 2.3 任务队列与后台作业
| 组件 | 能力 | 建议 |
|------|------|------|
| **Celery + Redis** | 成熟任务队列，支持定时、重试、优先级、worker 横向扩展 | **推荐**。spec 中 worker 的 indexing/export/checklist 都适合用 Celery |
| **RQ (Redis Queue)** | 更轻量，API 简洁 | 如果任务逻辑简单，可用 RQ 减少依赖 |

#### 2.4 ORM 与迁移
| 组件 | 建议 |
|------|------|
| **SQLAlchemy 2.0 (async)** + **Alembic** | 已成标准，无需讨论 |
| **SQLModel** | 如果配合 FastAPI-Amis-Admin，需要 SQLModel；否则 SQLAlchemy 即可 |

#### 2.5 API 文档
FastAPI 原生自带 Swagger UI + ReDoc，**直接可用**。

---

## 三、前端 UI 层

### Spec 选型
React / TypeScript

### 审查结论
**React/TS 正确。** 但 spec 中提到的"文档画布 + diff + 评论 + Agent Timeline"有大量现成组件可用，不需要从零写编辑器。

### 可抄的现成组件

#### 3.1 Markdown 编辑器/预览
| 组件 | 能力 | 建议 |
|------|------|------|
| **@uiw/react-md-editor** | 轻量 Markdown 编辑器，支持 toolbar、暗色模式、自定义命令 | **推荐用于 brief/素材编辑** |
| **MDXEditor** | 基于 Lexical 的 WYSIWYG 编辑器，支持表格、代码块、diff/source 模式切换 | **推荐用于文档画布**，体验更接近 Word |
| **react-markdown + remark-gfm** | 纯预览，支持 GFM（表格、脚注、删除线等） | **必读组件**，用于草稿预览 |

#### 3.2 Diff 查看器
| 组件 | 能力 | 建议 |
|------|------|------|
| **react-diff-viewer** | 经典 diff 组件，split/inline view、语法高亮、自定义样式 | 基础可用，但维护较缓 |
| **@git-diff-view/react** | GitHub 风格 diff viewer，2026 年仍在活跃更新，支持大文件虚拟滚动 | **更推荐**，性能和样式更现代 |
| **@pierre/diffs** (Plannotator 在用) | 支持行内批注、annotation overlay | 如果找到开源实现，可直接用于"评论"功能 |

#### 3.3 评论/批注系统
**纯前端现成方案较少**，但可以基于 diff viewer 的 `onLineSelection` 扩展：
- 参考 **Plannotator Code Review** 的设计：行内 `comment` / `suggestion` / `concern` 三种批注类型
- 自研成本不高：在 diff viewer 基础上加浮动 toolbar + sidebar 评论列表即可

#### 3.4 Agent Timeline / 事件流
| 组件 | 能力 | 建议 |
|------|------|------|
| **react-chrono** | 垂直/水平时间轴组件，支持卡片、媒体、嵌套 | 可作为 Timeline UI 基础 |
| **自研（参考 OpenHands UI）** | OpenHands 前端本身就是 React + event stream | 可直接参考其事件流渲染逻辑，不 fork UI 但抄组件思路 |

#### 3.5 三栏布局与整体 UI
| 组件/框架 | 建议 |
|-----------|------|
| **shadcn/ui + Tailwind** | 2025-2026 最推荐的 React 组件方案，可组合、无样式锁定 |
| **Ant Design Pro** | 如果追求快速搭建完整后台+工作台，可用其 PageContainer/ProLayout |
| **Refine** | 专门做 admin + CRUD 的 React 框架，内置 auth/router/data provider | 适合快速搭任务列表、文档类型管理等标准页面 |

#### 3.6 WebSocket / 事件流
| 组件 | 建议 |
|------|------|
| **react-use-websocket** | 轻量 hook，自动重连 |
| **SWR / TanStack Query** | 配合 HTTP API 做数据获取和缓存 |

---

## 四、文档 Agent 工具体系

### Spec 设计
自定义文档领域工具：read_example、edit_section、run_checklist、export_docx 等

### 审查结论
**工具接口设计合理，但实现层有大量现成库可复用。**

### 可抄的现成组件

#### 4.1 文档解析与处理
| 组件 | 用途 | 建议 |
|------|------|------|
| **markitdown** (Microsoft) | 将 PDF/DOCX/PPT 转为 Markdown | **强烈推荐**。示例上传后自动解析为文本，比自研 parser 靠谱 |
| **python-markdown + beautifulsoup4** | Markdown 解析与 HTML 转换 | 基础工具 |
| ** unstructured.io ** | 多格式文档解析（PDF、DOCX、PPT、图片） | 功能强但依赖重，离线部署需确认 |

#### 4.2 风格/结构分析（Style Signature）
**暂无直接可用的开源"文档风格指纹提取"工具**，这部分需要自研。但可借鉴：
- **textstat**（Python）：提取可读性指标（句长、复杂度）
- **spaCy / jieba**：分词、句法分析，用于提取修辞模式
- **scikit-learn**：TF-IDF / 聚类分析示例结构

#### 4.3 Checklist 执行
| 组件 | 建议 |
|------|------|
| **自研 YAML 规则引擎** | spec 中的 checklist 本质是结构化规则 + LLM 评判，无需复杂工作流引擎 |
| **Pydantic** | 用 Pydantic 模型做 checklist item 的输入输出校验 |

#### 4.4 导出工具链
| 组件 | 能力 | 建议 |
|------|------|------|
| **Pandoc + pypandoc** | Markdown → DOCX/PDF/RTF，支持 reference doc 模板 | **核心工具，必须保留** |
| **markdown2docx** (cnkang/markdown2docx) | 封装好的 Markdown→DOCX，支持模板、TOC、语法高亮、脚注 | **可直接集成**，减少自研封装工作量 |
| **python-docx** | 细粒度 DOCX 操作（后处理样式、页眉页脚） | 用于 Pandoc 输出后的精修 |
| **LibreOffice headless** | DOCX → PDF | 离线环境可靠方案 |
| **WeasyPrint** | HTML → PDF | 如果走 Markdown→HTML→PDF 路线，可替代 LibreOffice |

**推荐导出链路：**
```
structured draft (JSON/MD)
  → markdown2docx / pypandoc (带 reference-doc 模板)
  → python-docx 后处理（页眉页脚、封面微调）
  → 用户下载
  → (可选) LibreOffice headless → PDF
```

---

## 五、存储与基础设施层

### Spec 选型
PostgreSQL + pgvector / Qdrant + MinIO + Redis

### 审查结论
**选型合理，全部可复用成熟开源方案，无需自研。**

| 组件 | 确认 | 备注 |
|------|------|------|
| **PostgreSQL 15+** | ✅ | 用官方 Docker 镜像 |
| **pgvector** | ✅ | 向量检索 MVP 足够，无需另起 Qdrant |
| **MinIO** | ✅ | 对象存储，兼容 S3 API |
| **Redis** | ✅ | 队列 + 缓存 + session |
| **Qdrant** | ⚠️ 暂缓 | 除非向量规模极大，否则 pgvector 够用到 Phase 2 |

---

## 六、观测与审计层

### Spec 设计
Agent event log + OpenTelemetry-compatible trace

### 可抄的现成组件

| 组件 | 能力 | 建议 |
|------|------|------|
| **Langfuse** | LLM 应用观测平台，支持 trace、eval、prompt 管理，**可自托管** | **强烈推荐**。2026 年被 ClickHouse 收购，成熟度极高。spec 中的 session_events、token usage、latency、model 等字段 Langfuse 原生支持 |
| **LangSmith** | LangChain 官方观测平台 | 不能自托管，排除 |
| **OpenTelemetry + Jaeger** | 通用分布式追踪 | 可作为基础设施 trace，但缺乏 LLM 语义层 |
| **Prometheus + Grafana** | 指标监控 | 监控服务健康、队列长度、导出任务耗时 |

**推荐：Langfuse（自托管）+ Prometheus/Grafana。**

如果采用 **Dify 路线**，其内置的日志和 annotation 系统可直接复用。

---

## 七、沙箱与部署层

### Spec 选型
Docker workspace per task + Air-gapped Docker Compose

### 审查结论
**选型正确，全部现成。**

| 组件 | 建议 |
|------|------|
| **Docker + Docker Compose** | 标准方案 |
| **OpenHands DockerWorkspace** | 如果用 OpenHands，直接复用其 sandbox 镜像 |
| **LangGraph 默认无 sandbox** | 如果用 LangGraph，需自研 Docker sandbox（或复用 OpenHands 的 sandbox 方案） |

**离线构建工具链：**
- `pip download` + `pip install --no-index --find-links` 固化 Python wheels
- `npm ci` + `npm cache` 固化 Node 依赖
- `docker save` / `docker load` 固化镜像

---

## 八、综合推荐：三条实现路线的自研量对比

| 模块 | 路线 A：OpenHands 底座 | 路线 B：LangGraph 底座（推荐） | 路线 C：Dify 二次开发（最少自研） |
|------|----------------------|---------------------------|---------------------------|
| Agent Runtime | 复用 OpenHands SDK，自研 Adapter | 复用 LangGraph，自研 Document Tools | **复用 Dify 全套** |
| 后端 API | 自研 CRUD + 权限 | 自研 CRUD + 权限 | **复用 Dify 后端** |
| 前端工作台 | 自研 React 三栏 UI | 自研 React 三栏 UI | **复用 Dify workflow canvas**，自研文档画布 |
| 用户/权限 | 自研 RBAC | 自研 RBAC | **复用 Dify RBAC** |
| RAG/向量检索 | 自研 + pgvector | 自研 + pgvector | **复用 Dify Knowledge** |
| 观测/审计 | 自研 event log | 自研 event log + Langfuse | **复用 Dify 日志** |
| Admin 后台 | fastapi-user-auth 自带 | fastapi-user-auth 自带 | **复用 Dify 管理端** |
| 导出 | markdown2docx + pandoc | markdown2docx + pandoc | markdown2docx + pandoc |
| **预估自研比例** | **~60%** | **~55%** | **~30%** |

### 路线选择建议

- **如果团队坚持 Claude Code 式自由 agent loop，且需要完全掌控交互范式** → **路线 B（LangGraph）**。LangGraph 的 `interrupt`/`Command`/`checkpoint` 机制与 spec 的"可打断、可插话、可回滚"需求天然匹配，且社区生态成熟。
  
- **如果团队目标是"最快出 MVP、最少代码"，且能接受在 Dify 的框架内做定制** → **路线 C（Dify 二次开发）**。Dify 的 agent workflow、RAG、权限、观测都是现成的，团队只需专注做"文档画布"和"文档类型 Skill Pack"两个差异化模块。

- **如果团队已投入 OpenHands PoC 且不愿换底座** → **路线 A**，但需接受其 coding-centric 的设计惯性，额外投入定制 document tools。

---

## 九、优先集成清单（Phase 0 就能开始抄）

按"ROI 最高、风险最低"排序：

1. **markdown2docx** → 导出链路直接可用，PoC 就能验证 DOCX 输出
2. **markitdown** → 示例文档上传后自动解析，无需自研 PDF/DOCX 文本提取
3. **fastapi-user-auth** → 用户/权限/Admin 后台一行搞定
4. **react-markdown + @git-diff-view/react** → 文档预览和 diff 基础能力
5. **LangGraph** → 如果选路线 B，Phase 0 直接验证 HITL 和 checkpoint
6. **Langfuse（自托管）** → 观测层直接替代自研 event trace
7. **FastAPI-Amis-Admin** → MVP 期间用自动生成后台管理 doc-types/tasks/users

---

## 十、必须自研的核心模块（躲不掉的）

无论选哪条路线，以下模块**没有现成可用方案**，必须自研：

1. **文档类型包（DocType Pack）解析与加载** — manifest.yaml + SKILL.md + 资产挂载机制
2. **文档结构化编辑协议** — section-level CRUD + lock/unlock + version tree
3. **风格签名提取（Style Signature）** — 基于示例的结构/语气/修辞模式分析
4. **领域工具实现** — `edit_section`、`compare_draft_with_examples`、`run_checklist` 等工具的内部逻辑
5. **文档画布前端** — 三栏布局 + 章节树 + diff + 评论 + 锁定（可用组件拼装，但交互逻辑需自研）
6. **Runtime Adapter 接口层** — 解耦业务后端与 Agent Runtime 的适配器

---

*审查完成时间：2026-04-28*
*建议下一步：基于本审查结果，选定路线后更新 spec_v0_2.md，明确各组件的集成接口和自研边界。*
