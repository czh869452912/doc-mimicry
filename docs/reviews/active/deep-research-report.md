# doc-mimicry 实现分析、改进方案与整体规划评估

## 结论判断

从仓库现状看，这个项目的**产品方向判断是对的**：它已经明确把目标定义为“文档版 Claude Code / Codex 式工作台”，强调可审计的 workspace、可复用的 doc type skill pack、渐进式披露的 agent 过程，以及 Markdown-only 的内部文档边界；同时明确拒绝把产品做成固定工作流编排器、模板生成器或 RAG 优先的写作器。这与您这次给出的目标——“文档仿写平台”“通过 skill 和 workspace 让智能体模仿优秀案例、规范与检查单”“GUI 驱动的 vibe 文档撰写”——在战略上是高度一致的。fileciteturn12file0L1-L1 fileciteturn16file0L1-L1 fileciteturn17file0L1-L1 fileciteturn21file0L1-L1 fileciteturn22file0L1-L1

我对当前代码与设计的总评是：**方向正确，原型价值已经很高，但瓶颈已经从“缺少组件”转移为“状态架构、后端持久化与产品边界漂移”**。换句话说，当前最该改的不是视觉层，而是前后端交联方式、后台运行模型、skill pack 的数据模型，以及 authoring 与 skill-creator 两套界面的边界恢复。fileciteturn28file0L1-L1 fileciteturn30file0L1-L1 fileciteturn35file0L1-L1 fileciteturn38file0L1-L1

最核心的建议是：**保留现在已经选对的“积木”——Vite/React/TypeScript、assistant-ui、CodeMirror、Radix/Tailwind、FastAPI、runtime adapter 边界、OpenHands 作为首个 authoring runtime——不要再做大规模 UI/框架推倒重来；但要尽快把 server-state、URL-state、事件流、后台任务、skill pack 版本化和导入导出边界升级为真正可扩展的架构。** assistant-ui 的官方能力本来就支持自定义后端、ExternalStoreRuntime、自定义消息格式、attachments、branching、selection/quote 等；OpenHands 也天然提供了 document workspace 需要的文件编辑、命令执行、沙箱和 runtime 隔离能力，因此你们最有价值的路径不是“再换一套聊天 UI 或自己搭 agent loop”，而是把当前原型升级成一个**有稳定状态模型的文档操作系统**。fileciteturn13file0L1-L1 fileciteturn31file0L1-L1 fileciteturn32file0L1-L1 fileciteturn47file0L1-L1 citeturn12search0turn13search3turn3search0turn3search4turn3search6

## 当前实现的成熟度与已经做对的事情

当前仓库最强的一点，是**上层产品模型已经比较收敛**。README、vision、workspace contract、UI surfaces、Markdown pipeline 和若干 architectural decisions 彼此之间并不冲突：authoring 面要以三栏工作台为主，management 面负责 doc type / skill pack 的构建与维护；workspace 是 agent 的长期工作记忆；输入和输出在边界层做格式转换；内部只使用 Markdown；examples/specs/checklists 教 agent 学习文档结构与叙事，而不是直接拿来做语义检索素材。这个抽象是稳的，也足以支撑后续落地。fileciteturn12file0L1-L1 fileciteturn15file0L1-L1 fileciteturn17file0L1-L1 fileciteturn19file0L1-L1 fileciteturn20file0L1-L1 fileciteturn21file0L1-L1 fileciteturn22file0L1-L1 fileciteturn40file0L1-L1

技术选型方面，authoring 主界面的底座已经不差。前端使用 React 19、TypeScript、Vite，聊天/线程层已经实接 assistant-ui，编辑器使用 CodeMirror 6，Markdown 预览使用 react-markdown + remark-gfm + rehype-sanitize，布局使用 react-resizable-panels，树视图使用 react-arborist，设计系统沿着 Radix + Tailwind + CVA 的方向走；后端使用 FastAPI，并保留了 mock / OpenHands 两类 runtime adapter 的工厂边界。对于“尽量不自己手写大量前后端组件，而是用成熟 agent SDK 和 UI 组件搭积木”这个目标来说，这一组选择**总体是对的**。fileciteturn13file0L1-L1 fileciteturn14file0L1-L1 fileciteturn31file0L1-L1 fileciteturn32file0L1-L1 fileciteturn33file0L1-L1 fileciteturn47file0L1-L1

更重要的是，assistant-ui 的迁移已经不是“计划中”，而是**真接上了 runtime 与 primitives**：ConversationPane 用 `AssistantRuntimeProvider` 包裹中心时间线，`useDocAgentAssistantRuntime` 通过 `useExternalStoreRuntime` 把 timeline event 映射成 assistant-ui 的 `ThreadMessage[]`，并通过自定义 data parts 处理 outline/checklist/artifact/approval/tool-call 这些 DocAgent 特有语义；E2E 也已经覆盖了 message send、reload、text attachment 和 slash suggestion 等关键路径。这说明你们已经迈过去了“自己手写 chatbox 的 prototype 阶段”。fileciteturn31file0L1-L1 fileciteturn32file0L1-L1 fileciteturn33file0L1-L1 fileciteturn34file0L1-L1 fileciteturn46file0L1-L1

在 runtime 方向上，仓库也做了正确的抽象。`create_runtime_adapter()` 通过配置选择 mock 或 OpenHands，而设计文档也明确要求产品后端只持有 workspace / session / timeline / semantic event / artifact 这些产品概念，不向 runtime 内部的事件形态和工具系统泄漏。这一点非常关键，因为它让你们未来可以继续坚持“不要自己搭 agent loop”，但同时仍然可以在 OpenHands、OpenAI Agents SDK 或别的 runtime 之间留出空间。fileciteturn47file0L1-L1 fileciteturn48file0L1-L1

另外，虽然 management 与 skill creator 目前还没有真正做完，但 repo 至少已经保留了 PRD 类型的 `SKILL.md` 和 checklist 雏形，这证明“skill pack 驱动 authoring”不是一句空话，而是已经开始和 workspace、timeline、session 这些机制联动了。fileciteturn54file0L1-L1 fileciteturn55file0L1-L1

## 关键问题与根因分析

当前最大的产品级偏差，不在代码细节，而在**界面边界发生了漂移**。仓库更早的产品文档与 decision 明确说产品有两个 primary UI surfaces：Management interface 用于构建和维护 document type skill packs，Authoring interface 用于实际的文档仿写工作台；但是后来的 shell redesign 文档把“当前两页式 Workbench/Management split”收缩成了“单一 Codex 风格三栏 shell + 全局 settings drawer”，而当前代码中的 `SettingsDrawer` 也确实只是把 doc type 细节与 Skill Creator placeholder 放进了一个只读抽屉里。这对于 PoC 阶段可以接受，但与您现在明确提出的产品目标——“两组用户界面，其中 skill creator 界面是正式能力而非附属设置项”——已经不一致了。我的判断是：**不能继续把 skill creator 缩在 SettingsDrawer 里**；它必须被恢复为一等公民的 route / app surface。fileciteturn17file0L1-L1 fileciteturn20file0L1-L1 fileciteturn52file0L1-L1 fileciteturn53file0L1-L1

第二个根因，是前端现在仍然以**命令式 hook 编排**为主，而不是以稳定的 server-state / event-state 模型为主。`AppShell` 一层就承担了 URL 参数同步、draft 加载、command palette 状态、queued command、queued composer draft、running session 轮询、workspace refresh、timeline refresh 等多种职责；`useWorkspaces` 又把 task、session、workspace tree 的加载与刷新绑在一起；`useTimeline` 则独立管理另一套异步流。这就导致大量“改一个地方，三块 pane 都要跟着重新拉数据”的行为。更关键的是，`AppShell` 在每次重载 active draft 前会先把 `draft` 清空；而当 session 处于 running 状态时，它又每 1.5 秒刷新 workspace 并强制递增 `draftReloadToken`。这类“先清空、再回填”的模式很容易造成 preview/editor 闪烁、状态回退、交互不正常，也会制造大量不必要的网络和渲染开销。fileciteturn28file0L1-L1 fileciteturn30file0L1-L1

第三个根因，是**你们现在其实已经有 SSE，但仍然没有真正事件驱动的状态链路**。前端 `useTimeline` 已经使用 `EventSource` 订阅 `/timeline/stream`，失败时才 fallback 到 1.5 秒轮询；这说明“timeline 纯轮询”已经不是现状了。真正的问题在于：后端的 SSE 实现本身仍是一个 polling bridge，它每 0.2 秒 `list_timeline_events(session_id)` 一次，靠切片发送新增 event；而 `DocAgentState.append_timeline_event()` 每次只是把整个 timeline JSON 文件读出来、append、再整文件重写回去。也就是说，UI 层看似是 SSE，后端实现却是“频繁全量读磁盘 + 全量重写磁盘”的伪实时方案。session 越长，event 越多，这套机制越吃亏。fileciteturn29file0L1-L1 fileciteturn37file0L1-L1 fileciteturn38file0L1-L1

第四个根因，是后端持久化与后台执行模型仍然是**典型 prototype 级方案**。当前状态存储把 tasks、sessions、timelines 放在 `.local/docagent` 下的 JSON 文件里，用 `RLock` 保证单进程内安全；`BackgroundRuntimeRunner` 只是进程内 `ThreadPoolExecutor`；应用启动时如果发现 session 还停留在各种 `running_*` 状态，会直接把它们恢复为 `failed`。这说明现有设计只能在“单机、单进程、单租户、开发态”下稳定工作，一旦进入多用户或容器重启场景，就会遇到状态丢失、运行丢失和一致性问题。fileciteturn35file0L1-L1 fileciteturn36file0L1-L1 fileciteturn38file0L1-L1

第五个根因，是**skill pack / import-export 边界只有设计，没有完整实现**。仓库文档明确把导入边界定义为“各种输入 -> Markdown + assets + conversion report”，导出边界定义为“Markdown -> DOCX/PDF”，并建议引入多引擎转换策略；但当前真实 API 只提供 `/tasks/{task_id}/inputs/text`，附件适配器也只接受 txt/md/csv/json/xml/html/css 等 text-like 文件，`import_text_input()` 只是把文本同时写成 original `.txt` 和 markdown `.md`，转换报告的 `engine` 甚至直接是 `"manual"`。与此同时，`tools/export/README.md` 仍然写着 planned scripts，`packages/doctypes/README.md` 与 `agent/skills/README.md` 也都还是 placeholder。也就是说，真正决定“文档仿写平台是否可用”的导入、校验、发布、导出四条主链路，目前还没从产品声明变成稳定实现。fileciteturn19file0L1-L1 fileciteturn39file0L1-L1 fileciteturn57file0L1-L1 fileciteturn58file0L1-L1 fileciteturn42file0L1-L1 fileciteturn43file0L1-L1 fileciteturn44file0L1-L1

第六个根因，是**审计与交互语义还缺少关键元数据**。现在 timeline event 映射到 assistant-ui message 时，`createdAt` 被统一写成 `new Date(0)`；这虽然是为了兼容当前合同里没有 timestamp 字段，但它会限制 UI 做真正的时间排序、时延展示、run tracing 和更自然的 reload/branch 语义。assistant-ui 的 branching、reload、selection/quote 等能力本身是成熟的，但你们后端还没有 branch id、message parent、quote context、binary attachment import 状态等产品语义，所以很多高级能力只能停在“UI 已有、语义暂缺”的状态。fileciteturn34file0L1-L1 fileciteturn23file0L1-L1 citeturn13search0turn13search2turn15search0turn15search1

最后，CI 也还带着明显的原型痕迹。当前 CI 会检查 repo 结构、跑 Python foundation tests，并在 web job 中只执行 `npm run build`；它没有把前端 unit tests 与 Playwright smoke tests 作为正式门槛。另外，seed pack 的检查主要验证目录与文件存在，而不是验证内容完整性，这会让“examples/specs 目录存在但没有有效案例”的情况仍然通过流水线。对于将来要支持多人维护 skill packs 和多种文档类型的平台，这种 CI 严格度是不够的。fileciteturn46file0L1-L1 fileciteturn59file0L1-L1

## 组件、框架与 SDK 的评估结论

**assistant-ui：建议保留，且继续作为中心时间线的主干。**  
这不是“凑合能用”，而是当前最适合你们的选择。assistant-ui 官方把 primitives 定义为无样式但已处理好状态管理、键盘交互、自动滚动、streaming、tool calls 的 building blocks；更关键的是，它的 `ExternalStoreRuntime` 明确就是为“已有后端消息模型、已有状态管理、已有持久化逻辑”的场景设计的，甚至文档里直接提到可与 TanStack Query 之类方案集成。你们现在已经在 `useDocAgentAssistantRuntime` 中用 `useExternalStoreRuntime` 把 timeline event 映射进来了，这条路应该继续走，而不是再换一套 chat UI。fileciteturn31file0L1-L1 fileciteturn32file0L1-L1 fileciteturn33file0L1-L1 citeturn12search0turn13search3turn13search5

**Vercel AI SDK / AI Elements：值得关注，但不建议现在替换 assistant-ui。**  
官方资料显示，AI SDK 是面向 TypeScript 的统一 AI toolkit，AI Elements 则是围绕 `useChat` 等 AI SDK hooks 构建的可组合 AI UI 组件库，并强调与 shadcn/ui 的结合。它们很适合“前后端都围绕 TypeScript / AI SDK 重构”的体系，尤其适合直接把聊天状态、streaming 和 message parts 全放到 TS 栈里。但你们当前的核心不是“缺一个更漂亮的聊天 UI”，而是“已有 FastAPI + 自定义 timeline + runtime adapter + 三栏 authoring shell，怎么把状态与运行模型做稳”。在这个前提下，改到 AI SDK/AI Elements 的迁移收益，远低于把现有 assistant-ui + FastAPI 体系做实。citeturn11search0turn11search4turn11search6

**CopilotKit：是备选，而不是当前最优。**  
CopilotKit 官方把自己定位为“agents 与 generative UI 的前端栈”，强调 threads + persistence、React/Angular SDK、以及把 agent 渲染成自定义 React 组件的能力。它对业务表单、canvas、gen UI 的确很有吸引力；但如果此时再引入 CopilotKit，相当于在 assistant-ui 之外再叠一层 agent 前端抽象，会直接增加语义映射与状态边界复杂度。我的建议是把它列入观察清单，仅在未来 skill creator 界面非常强调“生成式表单/工作流控件”时再评估。citeturn5search5turn5search6

**shadcn/ui CLI 与自建 registry：建议尽快正式采用。**  
用户的目标是“搭积木式低成本、高质量”。这与 shadcn 的官方定位完全契合：CLI 可以自动初始化、添加组件和依赖；registry 机制允许你们自建代码注册表，把自定义组件、hooks、pages、config 作为可复用积木分发到任意项目类型和框架中。你们现在的 UI 底座本来就是 Radix + Tailwind + CVA 路线，review 文档也已经指出当前组件是手工维护而不是通过 CLI/registry 管理。因此，在不推翻设计系统的前提下，**应该把“通用组件”和“DocAgent 专用组件”都逐步纳入内部 shadcn registry**：前者如 dialog, sheet, tabs, command；后者如 workspace tree item、artifact card、conversion warning panel、skill pack version badge、resource review table。fileciteturn23file0L1-L1 citeturn2search0turn2search1turn2search4

**OpenHands：应该保留为 authoring runtime 的首选候选。**  
你们自己的设计文档已经说得很清楚：目标不是自己重复造 agent loop、sandbox、tool registry，而是拿成熟 coding-agent runtime 来适配 document workspace。OpenHands 官方也确实提供了 Docker / Local / Remote runtime、沙箱执行、文件编辑、命令执行、microagents，以及 SDK 级能力。对于“软件工程文档或强格式化文档”的仿写场景，这类以文件树和工作区为中心的 runtime 非常合适。我的判断是：**authoring runtime 不要从 OpenHands 撤退**，相反应该把产品层边界再做厚一点，把 runtime-specific 细节再收得更严。fileciteturn48file0L1-L1 citeturn3search0turn3search1turn3search2turn3search4turn3search5turn3search6

**OpenAI Responses / Agents SDK：适合做 skill creator 或轻量任务的第二 runtime，而不是直接替代 OpenHands。**  
OpenAI 官方文档显示，Responses API 现在支持 background mode、会话 state、built-in tools 与 function calling；Agents SDK 则强调 handoff、streaming、trace，并且新能力已经覆盖文件检查、命令运行与受控 sandbox。对你们来说，它最适合的不是“顶掉 OpenHands 的 authoring 主循环”，而是作为**skill creator / pack builder / resource summarizer 的轻量执行层**：这类任务往往是“读资源、提炼结构、输出结构化 manifest + `SKILL.md` + checklist 建议”，对强沙箱和长驻工作区依赖没那么高。作者工作台仍走 OpenHands；skill creator 可以预留第二 runtime capability。这样既不自己造 loop，又能控制成本。citeturn14search0turn14search1turn14search2turn14search4turn14search5turn14search7

**Router 与 Server State：当前最值得新增的两块基础设施是 TanStack Router + TanStack Query。**  
现在你们 URL 深链接、workspace/session 选择与 refresh 逻辑主要靠自定义 hook + searchParams 手写同步来管理，而 TanStack Router 的官方能力正好是“校验和类型化 search params”；TanStack Query 的核心价值则是把 async server state 从组件控制流里剥离出来，做缓存、失效、重取和结构共享。assistant-ui 的 ExternalStoreRuntime 官方文档甚至直接把 TanStack Query 作为推荐接法之一。对你们现在这种“左栏 task/session/tree、中心 timeline、右栏 draft/preview 都依赖后端状态”的应用，这是比“再上一个全局客户端状态库”更重要的基础。citeturn7search1turn8search0turn8search4turn12search0

## 推荐的整体方案与改造技术路线

我建议把整个系统正式收敛为**双工作区、双界面、单一产品模型**。所谓“双工作区”，是指 authoring workspace 与 skill-pack workspace；所谓“双界面”，是指 authoring 三栏工作台与 management / skill creator 界面；所谓“单一产品模型”，是指二者底层都使用同一套 resource、session、timeline、artifact、run、publish/version 机制，只是对象不同：一个面向“任务文档”，一个面向“文档类型能力包”。这比现在的“authoring 是正式面，skill creator 暂存于 settings drawer”更稳，也更接近你们的真实产品目标。fileciteturn17file0L1-L1 fileciteturn20file0L1-L1 fileciteturn52file0L1-L1

建议的目标形态如下：

```text
Authoring App
  -> Workspace / Session / Timeline / Preview
  -> assistant-ui + CodeMirror + Query/Router

Skill Creator App
  -> Resource Upload / Conversion Review / Skill Creator Chat / Pack Editor / Publish
  -> assistant-ui + Structured Editors + Query/Router

Shared Product Backend
  -> FastAPI command/read APIs
  -> Postgres metadata + event store
  -> Object storage or named volumes for resources/artifacts/workspace snapshots
  -> Worker queue for conversion / runtime / export jobs
  -> Runtime adapters: Mock / OpenHands / Responses-or-Agents-SDK
```

这个形态的意义是：**skill creator 不再是配置页，而是与 authoring 平级的“能力构建工作台”**；同时，你们又不需要拆成两套前端技术栈，因为三栏思路、assistant-ui timeline、preview/editor 模式、artifact/card 组件都可以复用。fileciteturn17file0L1-L1 fileciteturn53file0L1-L1 citeturn12search0turn13search3

在具体改造上，我建议按四段走，而不是一次性大重写。

**第一段先做状态治理，不做视觉重构。**  
目标是把“操作不正常、反馈不稳、性能差”这批问题先砍掉。这里最应该做的是：把 tasks、sessions、workspace tree、draft、timeline、artifacts 全部迁到 Query keys 上；把 URL query params 迁到类型化路由；把 `AppShell` 中的 draft reset + interval refresh 改成“只在收到 session / draft / artifact 更新事件时失效对应 query”；把 `useTimeline` 里的“refresh 时先清空 events”去掉；把 timeline contract 补上 `created_at`、`run_id`、`step_id`、`message_parent_id` 这类元数据。这一步做完，UI 交联会稳很多，而且几乎不需要触碰视觉组件。fileciteturn28file0L1-L1 fileciteturn29file0L1-L1 fileciteturn30file0L1-L1 fileciteturn34file0L1-L1 citeturn7search1turn8search0turn12search0

**第二段把 skill pack 从“文件夹约定”提升为“版本化产品对象”。**  
这里的关键不是只保留一个 `SKILL.md`，而是要新增一层正式的 pack manifest。也就是说，一个 published skill pack 至少要包含：版本号、资源清单、转换报告摘要、结构模式摘要、风格摘要、checklist、export profile、prompt fragments、来源追踪和发布时间。`packages/doctypes` 这个 placeholder 应该就地升级成 validator + loader + summary generator；task/session 创建时应该**固定绑定 `doc_type_version_id`**，而不是运行时临时读取当前文件夹里的资源。否则 skill pack 一变，历史任务就不可复现。fileciteturn17file0L1-L1 fileciteturn40file0L1-L1 fileciteturn42file0L1-L1 fileciteturn54file0L1-L1

**第三段再替换后端持久化与作业执行层。**  
这一段是从 prototype 迈向“多人可用”的分水岭。FastAPI 官方文档自己就提醒，如果任务是重计算、且不依赖同进程共享内存，应考虑 Celery 这类可跨进程、跨服务器运行的任务系统；Celery 官方则明确把自己定义为分布式 task queue，支持多 worker 与 broker。对 doc-mimicry 来说，转换、导出、runtime runs、checklist runs 都是标准的 background jobs，因此可以把当前 `BackgroundRuntimeRunner` 退化为 dev-mode fallback，把生产路径改成 `API -> enqueue job -> worker 执行 -> 事件写库 -> SSE 推前端`。与此同时，状态从 JSON 文件迁到 Postgres 元数据 / 事件表，workspace 文件和 artifacts 放到对象存储或单机卷里，worker 在运行 authoring/runtime 时把 workspace materialize 到本地盘或 runtime volume。fileciteturn35file0L1-L1 fileciteturn36file0L1-L1 fileciteturn38file0L1-L1 citeturn9search0turn9search6turn9search8

**第四段补全真正决定产品可用性的边界能力。**  
这一步包括：二进制文件导入、转换报告可视化、DOCX/PDF 导出、binary attachment、selection/quote 上下文、pack publish/version、artifact download，以及 skill creator 的资源审阅与修正闭环。assistant-ui 官方已经把 attachments、branching、selection quote 等关键前端模式做成了现成 primitives/registry components；你们后端只要把 binary import 和 quote context 这些产品语义补上，就可以继续低成本叠能力，而不需要重新设计中心聊天 UI。fileciteturn19file0L1-L1 fileciteturn43file0L1-L1 fileciteturn57file0L1-L1 citeturn12search1turn12search2turn13search0turn15search0turn15search1

## 面向多用户、Docker 部署与远期扩展的预留

如果目标里明确包含多用户与 Docker 部署，那么现在就应该把系统按**单机可部署、以后可分布式放大**的方式设计。Docker 官方把 Compose 定义为“定义和运行多容器应用”的方式，并明确支持 services、networks、volumes；命名卷则适合承载 DB、对象存储或 workspace snapshot 这类持久数据。基于这个能力，一个合理的单机企业版部署拓扑是：`web`、`api`、`worker`、`postgres`、`redis`、可选 `minio`、可选 `openhands runtime`。这样今天就能离线/内网部署，未来若要上 K8s 或拆多节点，只需要把 queue 与 storage 换成更分布式的实现，而不用重写应用层。citeturn10search1turn10search0turn10search4

在多用户模型上，我建议尽早把对象边界固定为：`organization -> document type -> document type version -> workspace -> session -> run -> timeline event / artifact`。这里最关键的是两个“钉住”的动作：一是 workspace 必须 pin 某个 published doc type version，二是 run 必须 pin 某次具体运行的 runtime/config/model/version。这不仅关系到权限和复现，也关系到后续审计、回滚与对比。你们当前文档已经非常重视 audit、timeline 和 raw runtime events；这条路线应该保留，只是把“文件级日志”升级为“有 ID 的事件模型 + 可追踪 run metadata”。fileciteturn15file0L1-L1 fileciteturn18file0L1-L1 fileciteturn48file0L1-L1

针对 authoring runtime，本地与远程都应预留。OpenHands 官方已经明确支持 Docker Runtime、Local Runtime 和 Remote Runtime；这正好可以映射你们的三类部署诉求：开发机本地、企业内网单机 Docker、后续远程统一运行池。我的建议是：在产品层只暴露 `runtime profile` 和 `capability profile`，不要让 UI 直接感知 OpenHands 私有细节。这样将来如果 skill creator 改走 OpenAI Responses/Agents SDK 背景模式，而 authoring 继续走 OpenHands，也不会把界面和后端绑死在某个 vendor 上。citeturn3search0turn3search4turn14search0turn14search4turn14search7

最后，从“低成本、高质量”的长期原则看，最值得坚持的不是某个单独框架，而是下面这条总路线：**UI 尽量用 headless/component registry 积木，agent runtime 尽量用成熟 SDK/平台能力，产品壁垒放在 skill pack 数据模型、workspace contract、timeline semantics、conversion/report pipeline 与审计可见性上。** 这些恰好也是当前仓库已经做出雏形、同时还没完全做实的部分。把这些地方做深，系统就会从“能演示的原型”变成“能持续演进的平台”。fileciteturn15file0L1-L1 fileciteturn17file0L1-L1 fileciteturn19file0L1-L1 fileciteturn40file0L1-L1 citeturn2search1turn12search0turn3search6turn14search5

## 开放问题与本次评估边界

本次结论主要基于仓库中的设计文档、前后端关键实现文件与官方技术文档做判断。需要说明的是，仓库里有些 review / exec-plan 文档和当前代码状态并不完全同步；当文档与代码冲突时，我优先以当前实现为准，例如 timeline 现在已经有 EventSource + fallback，而不应再简单描述成“纯轮询聊天界面”。fileciteturn23file0L1-L1 fileciteturn28file0L1-L1 fileciteturn29file0L1-L1

另外，仓库中 skill creator 的正式界面、二进制导入转换、DOCX 导出和多用户权限体系都还没有完整落地，因此我对这些部分给出的不是“现状评价”，而是“基于当前设计方向的推荐落地方案”。这并不影响主结论，因为目前最重要的判断已经足够清楚：**当前选择的核心组件并不差，真正需要尽快重构的是状态架构、持久化与产品边界。** fileciteturn17file0L1-L1 fileciteturn19file0L1-L1 fileciteturn43file0L1-L1 fileciteturn52file0L1-L1