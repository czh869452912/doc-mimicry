# DocAgent Workbench PoC 快速启动指南

> 基于 OpenHands 极致套壳路线。目标：Week 1 验证核心链路。

---

## 一、总体目录结构

```
doc-agent-workbench/
├── docker-compose.yaml              # 一键启动全部服务
├── .env                             # 配置本地 LLM endpoint
│
├── openhands/                       # OpenHands 官方仓库（submodule 或直接 clone）
│   └── ...                          # 不改源码，只挂载配置
│
├── doc-types/                       # 文档类型资产（只读挂载到 OpenHands sandbox）
│   └── prd/
│       ├── SKILL.md
│       ├── examples/
│       │   ├── ex1_best_prd.md
│       │   └── ex2_metrics_prd.md
│       ├── specs/
│       │   ├── style_guide.md
│       │   └── structure_rules.md
│       ├── checklists/
│       │   └── quality.yaml
│       └── templates/
│           └── reference.docx
│
├── workspaces/                      # 任务工作区（可写，sandbox 隔离）
│   └── (运行时创建)
│
├── gateway/                         # 自研 FastAPI 网关（~200行）
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                        # 自研文档工作台前端（Week 2 再开）
│   └── (placeholder)
│
└── scripts/
    ├── setup.sh                     # 初始化 doc-types、workspaces 目录
    └── export-docx.py               # Pandoc 包装脚本（Agent 用 bash 调用）
```

---

## 二、Step 1：启动 OpenHands Agent Server

### 2.1 Clone OpenHands

```bash
git clone https://github.com/All-Hands-AI/OpenHands.git
cd OpenHands
# 建议锁定到稳定 tag，避免 breaking change
git checkout 0.30.0  # 或当时最新稳定版
```

### 2.2 写 docker-compose.yaml

```yaml
version: "3.8"

services:
  openhands-agent-server:
    image: all-hands-ai/openhands:0.30.0
    ports:
      - "3000:3000"          # OpenHands Web UI（临时调试用）
      - "8001:8001"          # Agent Server REST API
    environment:
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY:-dummy}
      - LLM_MODEL=${LLM_MODEL}
      - LOG_LEVEL=info
    volumes:
      # 只读挂载：文档类型资产
      - ../doc-types:/doc-types:ro
      # 可写挂载：任务工作区
      - ../workspaces:/workspaces
      # 预置脚本
      - ../scripts:/scripts:ro
    # 网络隔离：禁止外网（除 LLM endpoint）
    networks:
      - doc-agent-net

  # （可选）本地 LLM，如果你还没有部署
  # local-llm:
  #   image: vllm/vllm-openai:latest
  #   ...

  gateway:
    build: ./gateway
    ports:
      - "8080:8080"
    environment:
      - OPENHANDS_API_URL=http://openhands-agent-server:8001
    volumes:
      - ./doc-types:/app/doc-types:ro
    networks:
      - doc-agent-net

networks:
  doc-agent-net:
    driver: bridge
```

### 2.3 .env 配置

```env
# 本地 LLM（OpenAI-compatible）
LLM_BASE_URL=http://local-llm.internal:8000/v1
LLM_API_KEY=dummy
LLM_MODEL=Qwen/Qwen2.5-72B-Instruct  # 或你的本地模型名

# 如需 embedding（Phase 1 再做）
# EMBEDDING_BASE_URL=...
# EMBEDDING_MODEL=...
```

### 2.4 启动

```bash
# 在项目根目录
docker-compose up -d openhands-agent-server

# 检查日志
docker-compose logs -f openhands-agent-server
```

---

## 三、Step 2：准备第一个文档类型（PRD）

### 3.1 创建目录

```bash
mkdir -p doc-types/prd/{examples,specs,checklists,templates}
mkdir -p workspaces
```

### 3.2 写 SKILL.md

`doc-types/prd/SKILL.md`：

```markdown
---
skill: prd-writer
version: "1.0"
---

# PRD 写作助手

你是资深产品经理，擅长撰写高质量 PRD。你的任务是基于用户提供的 brief 和配置好的示例/规范，写出结构清晰、可落地的 PRD。

## 可用资产（只读）

所有资产都在 `/doc-types/prd/` 下：
- `examples/` — 优秀 PRD 示例，供你学习结构和风格
- `specs/` — 写作规范
- `checklists/quality.yaml` — 质量检查单
- `templates/reference.docx` — Pandoc 参考模板（导出用）

## 工作目录

你在 `/workspaces/{task_id}/` 下工作：
- `brief.md` — 用户提供的 brief（已存在）
- `draft/` — 草稿目录
  - `outline.md` — 大纲
  - `draft_v1.md`, `draft_v2.md` ... — 各版本草稿
- `artifacts/` — 产物目录
- `logs/` — 日志目录

## 工作流程

1. **读 brief**：先读 `brief.md`，理解用户需求
2. **读 SKILL.md**：读本文件，确认角色和约束
3. **分析示例**：用 `glob` 列出 `examples/`，选择 2-3 个最相关的读取，分析：
   - 章节结构
   - 信息密度
   - 表格使用方式
   - 指标定义风格
4. **读规范**：读取 `specs/` 下的规范
5. **写大纲**：写 `draft/outline.md`，然后**停下来问用户确认**
6. **写草稿**：用户确认后，写 `draft/draft_v1.md`
7. **用户修改**：如果用户要求局部修改，用 `edit_file` 精准修改，修改前复制为新版本
8. **跑检查单**：读 `checklists/quality.yaml`，逐条自检，结果写入 `logs/checklist.md`
9. **导出**：用户确认后，执行 bash 命令导出 DOCX：
   ```bash
   pandoc /workspaces/{task_id}/draft/draft_v1.md \
     -o /workspaces/{task_id}/artifacts/prd.docx \
     --reference-doc=/doc-types/prd/templates/reference.docx
   ```

## 风格约束

- 不要复制示例原文
- 模仿章节结构、语气、信息密度
- 每个核心需求包含：用户价值 + 验收标准
- 指标必须包含：定义 + 口径 + 观察方式
- 非目标必须明确说明

## 检查单要点

- [ ] 目标是否清晰可验证
- [ ] 指标是否可度量
- [ ] 是否说明非目标
- [ ] 方案设计是否有逻辑链条
- [ ] 风险是否对应应对措施
```

### 3.3 放一个示例 PRD

`doc-types/prd/examples/ex1_best_prd.md`：

```markdown
# 示例：电商购物车改版 PRD

## 背景
当前购物车转化率仅 12%，竞品平均 18%。用户调研显示主要流失点在...

## 目标
- 将购物车转化率从 12% 提升至 16%（Q3 末）
- 减少购物车放弃率 20%

## 非目标
- 本次不改支付流程
- 不涉跨境税费计算

## 用户场景
| 场景 | 用户 | 痛点 |
|------|------|------|
| 加购后比价 | 价格敏感型 | 找不到之前加购的商品 |
| 凑单免运费 | 低频买家 | 不知道还差多少钱 |

## 方案设计
...

## 指标
| 指标 | 定义 | 口径 | 观察方式 |
|------|------|------|----------|
| 购物车转化率 | 支付成功 UV / 进入购物车 UV | 去重，自然日 | 数据看板 |
| 放弃率 | 放弃支付 UV / 发起支付 UV | 去重，自然日 | 数据看板 |

## 风险与应对
| 风险 | 影响 | 应对 |
|------|------|------|
| 性能下降 | 页面加载慢导致流失 | 压测标准 < 1.5s |
```

### 3.4 写检查单

`doc-types/prd/checklists/quality.yaml`：

```yaml
id: prd_quality_v1
name: PRD 质量检查
items:
  - id: goal_clear
    label: 目标是否清晰可验证
    severity: critical
    instruction: 检查是否有具体数字、时间、可验证标准
  - id: metrics_defined
    label: 指标是否可度量
    severity: high
    instruction: 检查每个指标是否有定义、口径、观察方式
  - id: non_goals_present
    label: 是否说明非目标
    severity: medium
    instruction: 检查是否明确说明本期不做的事
  - id: risk_handled
    label: 风险是否有应对
    severity: medium
    instruction: 检查每个风险是否对应具体应对措施
```

### 3.5 准备 Pandoc 参考模板

```bash
# 先用 pandoc 生成一个空白参考模板
pandoc -o doc-types/prd/templates/reference.docx \
  --print-default-data-file reference.docx

# 然后用 Word 打开，调好样式（标题、正文、表格），保存
```

---

## 四、Step 3：FastAPI 网关（极简版）

`gateway/main.py`：

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import uuid
from pathlib import Path

app = FastAPI(title="DocAgent Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENHANDS_URL = os.getenv("OPENHANDS_API_URL", "http://localhost:8001")
DOC_TYPES_DIR = Path("/app/doc-types")

# ---------- 文档类型管理 ----------

@app.get("/api/doc-types")
async def list_doc_types():
    """列出所有文档类型"""
    return [
        {"id": d.name, "name": d.name.upper()}
        for d in DOC_TYPES_DIR.iterdir()
        if d.is_dir()
    ]

@app.get("/api/doc-types/{doc_type_id}")
async def get_doc_type(doc_type_id: str):
    """获取文档类型详情"""
    path = DOC_TYPES_DIR / doc_type_id
    if not path.exists():
        raise HTTPException(404, "Doc type not found")
    
    skill_md = (path / "SKILL.md").read_text() if (path / "SKILL.md").exists() else ""
    examples = [f.name for f in (path / "examples").glob("*.md")] if (path / "examples").exists() else []
    
    return {
        "id": doc_type_id,
        "skill_md": skill_md,
        "examples": examples,
    }

# ---------- 任务管理 ----------

TASKS = {}

@app.post("/api/tasks")
async def create_task(doc_type_id: str, title: str, brief: str):
    """创建文档任务"""
    task_id = str(uuid.uuid4())[:8]
    
    # 创建 workspace 目录
    workspace = Path(f"/workspaces/{task_id}")
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "draft").mkdir(exist_ok=True)
    (workspace / "artifacts").mkdir(exist_ok=True)
    (workspace / "logs").mkdir(exist_ok=True)
    
    # 写入 brief
    (workspace / "brief.md").write_text(brief)
    
    TASKS[task_id] = {
        "id": task_id,
        "doc_type_id": doc_type_id,
        "title": title,
        "workspace": str(workspace),
        "status": "created",
    }
    
    return TASKS[task_id]

@app.get("/api/tasks")
async def list_tasks():
    return list(TASKS.values())

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(404, "Task not found")
    return TASKS[task_id]

# ---------- OpenHands Session 透传 ----------

@app.post("/api/tasks/{task_id}/sessions")
async def create_session(task_id: str):
    """在 OpenHands 创建 conversation"""
    if task_id not in TASKS:
        raise HTTPException(404, "Task not found")
    
    task = TASKS[task_id]
    
    # 构建初始消息：把 SKILL.md + brief 注入
    skill_path = DOC_TYPES_DIR / task["doc_type_id"] / "SKILL.md"
    skill_md = skill_path.read_text() if skill_path.exists() else ""
    brief_path = Path(task["workspace"]) / "brief.md"
    brief = brief_path.read_text() if brief_path.exists() else ""
    
    initial_prompt = f"""
{skill_md}

---

用户任务：
{brief}

请按 SKILL.md 中的工作流程开始。先读 brief 和示例，然后给出写作计划。
"""
    
    async with httpx.AsyncClient() as client:
        # 调用 OpenHands Agent Server 创建 conversation
        # 具体 API 路径以 OpenHands 文档为准，这里示意
        resp = await client.post(
            f"{OPENHANDS_URL}/api/conversations",
            json={
                "initial_message": initial_prompt,
                "workspace": f"/workspaces/{task_id}",
            }
        )
        resp.raise_for_status()
        data = resp.json()
    
    return {
        "task_id": task_id,
        "session_id": data["conversation_id"],
        "websocket_url": f"{OPENHANDS_URL}/ws/conversations/{data['conversation_id']}",
    }

@app.get("/api/sessions/{session_id}/events")
async def stream_events(session_id: str):
    """透传 OpenHands event stream（前端直接连 WebSocket 也行）"""
    # 实际实现中，前端可以直接连 OpenHands 的 WebSocket
    # 这里留一个 HTTP fallback
    pass

# ---------- 产物下载 ----------

@app.get("/api/tasks/{task_id}/artifacts/{filename}")
async def download_artifact(task_id: str, filename: str):
    """下载 DOCX/Markdown"""
    path = Path(f"/workspaces/{task_id}/artifacts/{filename}")
    if not path.exists():
        raise HTTPException(404, "Artifact not found")
    from fastapi.responses import FileResponse
    return FileResponse(path)
```

`gateway/requirements.txt`：

```
fastapi
uvicorn
httpx
python-multipart
```

`gateway/Dockerfile`：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 五、Step 4：前端对接事件流

### 5.1 前端直接连 OpenHands WebSocket

OpenHands Agent Server 提供 WebSocket endpoint（路径参考官方文档，通常是 `/ws/conversations/{id}`）。

前端核心逻辑：

```typescript
// 创建 session 后，拿到 websocket_url
const ws = new WebSocket(websocket_url);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  // OpenHands event 格式示例：
  // { type: "message", source: "agent", content: "..." }
  // { type: "tool_call", name: "read_file", arguments: {...} }
  // { type: "tool_output", content: "..." }
  // { type: "error", message: "..." }
  
  switch (msg.type) {
    case "message":
      appendChat(msg.source, msg.content);
      break;
    case "tool_call":
      appendTimeline("🔧", msg.name, msg.arguments);
      break;
    case "tool_output":
      appendTimeline("✅", "完成", msg.content.slice(0, 200));
      break;
  }
};

// 用户发送消息
function sendUserMessage(text: string) {
  ws.send(JSON.stringify({ type: "user_message", content: text }));
}
```

### 5.2 语义增强（后端做，可选）

如果 Timeline 上全是 "read_file" / "write_file" 不够直观，后端加一个轻量 event 翻译层：

```python
EVENT_TRANSLATION = {
    ("read_file", "/doc-types/*/examples/*"): ("📖", "分析示例"),
    ("read_file", "/doc-types/*/specs/*"): ("📋", "阅读规范"),
    ("read_file", "*/brief.md"): ("🎯", "理解需求"),
    ("write_file", "*/outline.md"): ("📝", "生成大纲"),
    ("write_file", "*/draft_v*.md"): ("✍️", "撰写草稿"),
    ("edit_file", "*/draft*.md"): ("✏️", "修改草稿"),
    ("execute_bash", "pandoc*"): ("📄", "导出文档"),
}

def translate_event(tool_name: str, args: dict) -> tuple:
    path = args.get("path", "")
    command = args.get("command", "")
    for (t, pattern), (emoji, label) in EVENT_TRANSLATION.items():
        if tool_name == t and fnmatch(path or command, pattern):
            return emoji, label
    return "🔧", tool_name
```

---

## 六、Step 5：Week 1 验证清单

| 步骤 | 验证点 | 成功标准 |
|------|--------|----------|
| 1 | 启动 OpenHands | `docker-compose up` 成功，Web UI 能访问 |
| 2 | 接入本地 LLM | 在 OpenHands UI 里发一句"hello"，模型有响应 |
| 3 | 准备 PRD doc-type | `doc-types/prd/` 下 SKILL.md + 示例 + 规范齐全 |
| 4 | 启动 Gateway | `docker-compose up gateway` 成功，API 可访问 |
| 5 | 创建任务 | `POST /api/tasks` 成功，workspace 目录已创建 |
| 6 | 创建 Session | `POST /api/tasks/{id}/sessions` 成功，返回 session_id |
| 7 | Agent 读 SKILL | Timeline 看到 `read_file /doc-types/prd/SKILL.md` |
| 8 | Agent 读示例 | Timeline 看到 `read_file examples/ex1_*.md` |
| 9 | Agent 写大纲 | Timeline 看到 `write_file draft/outline.md` |
| 10 | 用户插话 | 前端发送消息，Agent 中断当前思考，响应用户 |
| 11 | Agent 导出 DOCX | `execute_bash pandoc ...` 成功，artifacts/ 下出现 docx |
| 12 | 下载产物 | `GET /api/tasks/{id}/artifacts/prd.docx` 成功 |

**Week 1 跑通 1-12 = 核心链路验证完成。**

---

## 七、Week 2-3：补齐前端

Week 1 可以用 OpenHands 自带 Web UI 调通后端。Week 2 开始自研文档工作台：

```
frontend/
├── src/
│   ├── components/
│   │   ├── DocTypePanel.tsx      # 左侧：示例/规范/检查单列表
│   │   ├── DocumentCanvas.tsx    # 中间：Markdown 预览 + 章节树
│   │   ├── DiffViewer.tsx        # diff 视图
│   │   ├── AgentTimeline.tsx     # 右侧：事件时间线
│   │   └── ChatInput.tsx         # 底部：用户输入
│   ├── hooks/
│   │   └── useOpenHandsStream.ts # WebSocket 事件流 hook
│   └── App.tsx
```

**不急着做复杂功能，先把三栏布局和事件流渲染出来。**

---

## 八、常见问题

### Q：Agent 不读 SKILL.md 怎么办？

在创建 session 的 initial prompt 里**强制要求**：
```
你必须首先读取 /doc-types/prd/SKILL.md，然后按其中的工作流程执行。
如果不读 SKILL.md 就行动，我会打断你。
```

### Q：Agent 用 bash 执行了危险命令？

OpenHands 的 security analyzer 会拦截。同时可以在 initial prompt 里加限制：
```
你只能用 bash 执行以下命令：
- pandoc（导出文档）
- ls / cat / grep（查看文件）
禁止：rm, curl, wget, sudo, 任何网络请求
```

### Q：Agent 写的 Markdown 格式不对？

在 SKILL.md 里加明确格式要求，并给示例。如果还不行，Phase 1 加一个后处理脚本规范化 Markdown。

### Q：本地 LLM tool call 能力弱？

- 选支持 function calling 的模型（Qwen2.5、DeepSeek-V3、Llama 3.1+）
- 如果模型不支持 function calling，OpenHands 有 prompt-based tool use fallback（需确认 V1 版本）

---

## 九、最小可运行包

如果你现在就想跑起来，最小只需要这 5 个文件：

1. `docker-compose.yaml` — 启动 OpenHands
2. `.env` — LLM 配置
3. `doc-types/prd/SKILL.md` — 告诉 Agent 怎么写 PRD
4. `doc-types/prd/examples/ex1.md` — 一个示例
5. `doc-types/prd/checklists/quality.yaml` — 检查单

然后进 OpenHands 的 Web UI，手动上传/挂载这些文件，发一句 prompt 就能开始验证。

**Gateway 和前端可以 Week 1 后半周再补。**
