# goalForNextLevel.md

## 0. 文档目的

本文档记录 Classroom Live Transcriber 后续“高价值功能”的开发目标、优先级、设计边界和验收标准。

当前项目已经具备一个可用的本地 near-real-time 课堂转写主链路：

```text
PySide6 UI
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore
```

运行时链路：

```text
麦克风 48kHz mono
-> ring buffer
-> 10s chunk / 3s overlap
-> 16kHz resample
-> whisper.cpp CLI + Metal + ggml/gguf model
-> raw
-> simple_dedup()
-> fuzzy_boundary_dedup()
-> clean
-> UI/session files
```

每个 session 当前输出：

```text
raw.txt
clean.txt
session.log
config.json
```

后续开发必须保护这条稳定主链路。任何 LLM、搜索、总结、benchmark、session browser 都应优先设计成主链路之外的附加层，除非经过单独验证。

证据层不可变：

```text
raw.txt
clean.txt
session.log
config.json
```

LLM 功能不得修改、覆盖、删除、重命名、截断、追加 LLM 内容、替换为翻译稿、替换为纠错稿，或把 LLM 输出混入这些文件。

---

## 1. 设计思路与优先级判断

### 1.1 核心判断

当前项目已经完成了“可实时查看课堂转写”的基础产品形态。下一阶段不应继续堆小功能，而应围绕三个方向提升价值：

1. **把 transcript 变成可学习材料**
   - 通过 LLM 后处理生成 timestamp-grounded summary、key terms、action items、review questions。
2. **把单次转写变成可管理的知识库**
   - 通过 session browser / search 管理历史课堂、搜索全文、跳转时间线。
3. **把当前原型架构推向更低延迟和更可测**
   - 通过 persistent whisper backend 降低每 chunk CLI 开销；
   - 通过 benchmark / regression suite 量化 ASR、dedup、latency、resource usage。

### 1.2 不能做错的边界

后续最容易出错的方向是把 LLM 接进实时主链路。当前原则是：

```text
实时主链路：本地 ASR + clean/raw 输出
LLM：可选、异步、离线/在线 API 后处理
```

LLM 必须是 sidecar：可选、异步、旁路读取、额外派生输出。它不得进入 audio capture、ring buffer、chunk scheduling、resample、WhisperCppBackend、`TranscriptionEngine` 转写 worker 主循环、`simple_dedup()`、`fuzzy_boundary_dedup()`、`TranscriptStore` raw/clean 主写入路径、Start/Stop、麦克风释放或 UI 主线程。

LLM 失败时，不得影响：

```text
raw.txt
clean.txt
session.log
config.json
Start/Stop
麦克风释放
UI 主线程稳定性
```

没有 API key、API 超时、断网、HTTP error、provider error、JSON parse error、schema validation failure、renderer failure、sidecar backlog、用户取消任务或应用关闭，都只能影响 LLM 自己的派生输出和错误日志。

### 1.3 简历价值排序

按“工程含金量 + 可展示成果 + 简历可写性”排序：

1. **LLM 离线/在线 API 后处理管线**
2. **Session Browser / Search**
3. **Persistent whisper backend**
4. **Benchmark / Regression suite**
5. **多语言 clean 层**
6. **Release / packaging 自动化**

---

## 2. P0：LLM 离线/在线 API 后处理管线

> 状态：需求已初步确认，值得优先做。
> 目标：把 `clean.txt` 进一步转成带时间戳引用的中文总结、中文阅读稿、知识点、行动项和复习材料。
> 推荐第一实现：DeepSeek / OpenAI-compatible API。
> 关键边界：不进入实时主链路；失败不影响 transcript；API key 不进仓库、不进 settings、不进 session 输出。

### 2.0 统一 Phase 划分

当前 LLM roadmap 统一为：

```text
Phase 1A：After-stop 中文总结
Phase 1B：After-stop 中文阅读稿
Phase 2A：动态中文阅读稿 sidecar
Phase 2B：应用内 Markdown / HTML 渲染
```

Phase 1A 是当前第一优先级：Stop complete 后读取完整 `clean.txt`，经过 parser、chunker、map-reduce summary pipeline，输出中文结构化总结到 `session_dir/llm/`。

Phase 1B 在 Phase 1A 基础上新增适合人类阅读的完整中文 transcript 派生稿。它不是证据层，也不是 summary。真实状态源是 `readable_zh_final_state.json`，Markdown / HTML 是本地 renderer 生成的派生视图。

Phase 2A 是录音期间运行的可选动态中文阅读稿 sidecar，默认关闭。它只读 newline-complete 的 `clean.txt` 快照和当前结构化 state，使用 configurable `interval_seconds = 30`、`clean_context_window_seconds = 40`、`editable_window_seconds = 60` 作为初始值，并通过 pending snapshot coalescing 避免 backlog。

Phase 2B 在 Phase 2A 稳定后接入 PySide6 UI。正式产品使用 `QTextBrowser.setHtml()` 预览本地 renderer 生成的 HTML，不依赖 Typora、外部浏览器或 `QWebEngineView`。

### 2.1 目标

实现一个可选 LLM 后处理模块，对已完成的 session 进行结构化处理。

输入：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
  raw.txt
  clean.txt
  session.log
  config.json
```

输出：

```text
llm/
  summary.md
  summary.json
  sections.json
  key_terms.json
  action_items.json
  llm_errors.log
  readable_zh_final_state.json
  readable_zh_final.md
  readable_zh_final.html
  review_zh_final.md
  review_zh_final.html
  readable_zh_errors.log
```

可选输出：

```text
llm_requests.jsonl
llm_responses.jsonl
```

注意：如果保存 request/response log，必须确保不保存 API key。

Phase 2A 后续动态输出规划：

```text
llm/
  live_readable_zh_state.json
  live_readable_zh_revisions.jsonl
  live_readable_zh.md
  live_readable_zh.html
  live_review_zh.md
  live_review_zh.html
  live_readable_zh_errors.log
```

### 2.2 非目标

第一版不要做：

```text
实时逐 chunk 调 LLM
自动替换 clean.txt
强制联网
本地大模型推理
RAG across all sessions
云端同步
自动上传 raw 音频
```

当前暂缓：

```text
不修改现有 ASR 主链路
不接 UI
不实现动态 sidecar
不调用真实 API
不记录 request / response log
不保存 API key
不引入 Typora 依赖
不依赖外部浏览器
不引入 QWebEngineView
不做跨 session RAG
不做 session browser
不做 persistent whisper backend
不做自动纠错并覆盖 clean.txt
不上传音频
```

LLM 输出应是额外产物，不应覆盖原始 evidence。Markdown 和 HTML 只是派生视图，state JSON 才是阅读稿真实状态源。

### 2.3 主要使用场景

#### 场景 A：课后生成全文学习笔记

用户录完一节课后点击：

```text
Generate Summary
```

系统读取当前 session 的 `clean.txt`，调用 LLM API，生成：

```text
llm/summary.md
```

内容包括：

- High-level overview
- Timeline-based sections
- Key concepts
- Important details
- Action items
- Review questions
- Possible ASR errors / unclear parts

#### 场景 B：阶段性总结

用户在长课或长会议中希望分段处理：

```text
每 5-10 分钟生成一个阶段 summary
```

但这仍应是异步后处理，不阻塞实时转写。

#### 场景 C：全文信息提炼

用户希望从 transcript 中提取：

- 课程主题
- 术语
- assignment / deadline / project instruction
- professor emphasized points
- unclear / likely misrecognized terms

### 2.4 Timestamp-grounded 输出要求

LLM 输出必须尽量带时间戳引用，避免“泛泛总结”。

推荐格式：

```markdown
## Timeline Summary

### 00:00-05:00 - Topic introduction
- The instructor introduced ...
- Key term: ...

### 05:00-12:00 - Requirements elicitation
- The instructor explained ...
- Possible ASR issue: "..." may refer to "..."
```

Key terms 格式：

```markdown
## Key Terms

| Term | Meaning | Evidence |
|---|---|---|
| Requirements elicitation | ... | 00:12:20-00:15:40 |
| Technical debt | ... | 00:28:10-00:31:00 |
```

Action items 格式：

```markdown
## Action Items

- [00:42:15] Submit ...
- [00:50:02] Review ...
```

Unclear parts 格式：

```markdown
## Unclear / Possible ASR Errors

- [00:18:40] "first down first server" may mean "first come, first served".
- Confidence: medium.
- Reason: phrase appears in a project selection context.
```

### 2.5 LLM 模块架构建议

建议新增：

```text
llm/
  __init__.py
  provider_base.py
  deepseek_provider.py
  openai_compatible_provider.py
  transcript_chunker.py
  summary_pipeline.py
  prompt_templates.py
  llm_settings.py
  output_writer.py
  state_schema.py
  renderer.py
```

职责划分：

- `provider_base.py`：定义统一 `LLMProvider` 接口。
- `deepseek_provider.py`：DeepSeek API 适配器。
- `openai_compatible_provider.py`：为后续其他兼容 API 预留。
- `transcript_chunker.py`：按时间戳和 token/字符预算切分 clean transcript。
- `summary_pipeline.py`：实现 map-reduce 式分段总结和全局总结。
- `prompt_templates.py`：集中管理 prompts，避免散落在 UI 代码中。
- `output_writer.py`：写 Markdown / JSON / error log。
- `state_schema.py`：定义 readable transcript 的结构化状态和 patch schema。
- `renderer.py`：从 state JSON 本地渲染 Markdown / HTML。

### 2.6 API key 与隐私设计

必须满足：

1. API key 不写入仓库；
2. API key 不写入 session 输出；
3. UI 中应提醒用户：LLM 后处理会把 transcript 文本发送到外部 API；
4. 用户可以不配置 API key，项目仍可完成本地 ASR；
5. LLM 功能应有开关；
6. LLM 失败不影响 raw/clean/session；
7. 未来可支持多个 provider。

第一版只允许从环境变量读取：

```text
DEEPSEEK_API_KEY
```

禁止写入仓库、`/docs`、settings、`config/settings.json`、session `config.json`、`raw.txt`、`clean.txt`、request log、response log、Markdown、HTML、JSON state 或错误日志。DeepSeek 模型名和 endpoint 不应硬编码，应预留环境变量或 provider settings 配置能力。

### 2.7 Prompt 设计要求

LLM 必须被要求：

- 不编造；
- 不补充 transcript 之外的信息；
- 不确定时标记 unclear；
- 输出必须保留 timestamp grounding；
- ASR 修正只能作为“possible correction”，不能直接覆盖原文；
- 区分“教授明确说了”和“模型推断”。
- 对阅读稿阶段，LLM 只输出结构化 JSON/state 或 JSON patch；
- 不允许 LLM 直接自由生成并覆盖整个 Markdown / HTML。

分段总结 prompt 输入：

```text
session metadata
chunk start/end time
clean transcript chunk
```

分段总结 prompt 输出：

```json
{
  "start_time": "...",
  "end_time": "...",
  "summary": "...",
  "key_terms": [],
  "action_items": [],
  "unclear_parts": []
}
```

全局总结 prompt 输入：

```text
all section summaries
selected high-value transcript excerpts
```

全局总结 prompt 输出：

```markdown
# Lecture Summary
## Overview
## Timeline
## Key Concepts
## Important Details
## Action Items
## Review Questions
## Unclear Parts
```

### 2.8 UI 集成建议

第一版 UI 不要复杂。

在左侧或 session 区域加：

```text
LLM Post-processing
[Generate Summary]
[Open Summary]
[Cancel]
Provider: DeepSeek
Status: Idle / Running / Failed / Complete
```

流程：

1. Stop Recording 后启用 `Generate Summary`；
2. 点击后后台线程执行；
3. Logs tab 显示进度；
4. 输出写入当前 session 目录；
5. 完成后可打开 `summary.md`。

不要在录音中默认自动调用 LLM。

Phase 2B 后续 UI 预览应使用 PySide6 `QTextBrowser.setHtml()` 渲染本地 HTML。Typora 和外部浏览器只作为开发 spot check，不作为正式产品依赖；不要引入 `QWebEngineView`。

可选后续：

```text
Auto-generate summary after Stop
Generate selected range summary
Regenerate summary
Open Readable Markdown
Open Readable HTML
Open Review Markdown
Open Review HTML
```

### 2.9 输出文件设计

推荐：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
  raw.txt
  clean.txt
  session.log
  config.json
  llm/
    summary.md
    summary.json
    sections.json
    key_terms.json
    action_items.json
    llm_errors.log
    readable_zh_final_state.json
    readable_zh_final.md
    readable_zh_final.html
    review_zh_final.md
    review_zh_final.html
    readable_zh_errors.log
```

动态 sidecar 后续输出规划：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
  llm/
    live_readable_zh_state.json
    live_readable_zh_revisions.jsonl
    live_readable_zh.md
    live_readable_zh.html
    live_review_zh.md
    live_review_zh.html
    live_readable_zh_errors.log
```

不要把 LLM 状态写回 `config.json`。如果未来需要 LLM state，写入 `session_dir/llm/` 下的独立 JSON state 文件。注意：不要记录 API key。

### 2.10 测试要求

必须做 mock provider，不要在单元测试里真实调用 API。

测试文件建议：

```text
testCodes/test_llm_chunker.py
testCodes/test_llm_pipeline.py
testCodes/test_llm_outputs.py
testCodes/test_llm_provider_mock.py
```

测试内容：

1. `clean.txt` timestamp parser；
2. transcript chunking；
3. chunk overlap；
4. no timestamp fallback；
5. prompt payload construction；
6. mock provider response parsing；
7. summary.md 写入；
8. summary.json schema；
9. API error 不影响已有 session；
10. API key 不写入输出文件；
11. cancel / timeout behavior；
12. readable final state / Markdown / HTML；
13. review Markdown / HTML；
14. HTML escaping；
15. annotation rendering；
16. raw.txt / clean.txt / session.log / config.json 均不变化；
17. renderer deterministic；
18. atomic replace；
19. Phase 2A 的 editable window、frozen segment、coalescing、single in-flight request、Stop final reconciliation。

### 2.11 LLM 后处理验收标准

#### 功能验收

- 没配置 API key 时，UI 提示明确，不崩溃；
- 配置 API key 后，可以对一个已有 session 生成 `summary.md`；
- 输出包含 timeline sections；
- 输出包含 key terms；
- 输出包含 action items；
- 输出包含 unclear / possible ASR errors；
- 输出带 timestamp references；
- 失败时写入 `llm_errors.log`；
- 不修改 `raw.txt`、`clean.txt`、`session.log`、`config.json`；
- Phase 1B 输出 `readable_zh_final_state.json`、`readable_zh_final.md`、`readable_zh_final.html`、`review_zh_final.md`、`review_zh_final.html`。

#### 稳定性验收

- LLM job 不阻塞 UI；
- LLM job 失败不影响 Start/Stop；
- 断网时能给出错误；
- API 超时时能结束；
- session 目录结构不被破坏；
- renderer failure 保留上一版有效输出；
- sidecar backlog 不影响 ASR；
- Stop drain 和麦克风释放不被阻塞。

#### 质量验收

抽取 1-2 节真实课堂 session 人工检查：

- summary 是否覆盖主线；
- 是否明显 hallucinate；
- timestamp 是否可追溯；
- unclear parts 是否有帮助；
- action items 是否没有乱编。

### 2.12 简历可写点

实现后可以写：

```text
Built an optional LLM post-processing pipeline for classroom transcripts, generating timestamp-grounded summaries, key terms, action items, review questions, and ASR-uncertainty notes from local raw/clean session outputs.
```

如果接入 DeepSeek/OpenAI-compatible provider：

```text
Designed a provider-based LLM API layer with mockable adapters, transcript chunking, timestamp grounding, structured Markdown/JSON outputs, and failure isolation from the live ASR pipeline.
```

---

## 3. P1：Session Browser / Search

> 状态：值得做，但尚未与用户细化。
> 当前只写方向，不定具体实现。
> 需要后续确认 UI 形态、搜索范围、隐私策略和导出格式。

### 3.1 初步目标

把当前散落在 `outputs/YYYY-MM-DD_HH-MM-SS/` 中的 session 变成可浏览、可搜索、可复习的历史库。

功能方向：

```text
Session list
Session metadata preview
Open clean/raw/log/config
Full-text search
Keyword highlight
Timestamp jump
Favorite/bookmark
Course/tag grouping
Export Markdown/PDF
```

### 3.2 初步 UI

可能新增：

```text
左侧：Session History
右侧：当前 transcript / summary
顶部：Search box
```

或作为单独窗口：

```text
Session Browser Dialog
```

### 3.3 可能的数据结构

新增：

```text
session_index.json
```

或 SQLite：

```text
classroom_transcriber.db
```

第一版建议 JSON index，不要直接上 SQLite，除非搜索和数据量变大。

### 3.4 待确认问题

- 用户是否需要按课程分组？
- 是否需要手动重命名 session？
- 是否需要自动从 transcript 推断标题？
- 是否需要全文搜索 raw、clean、summary，还是只搜 clean？
- 是否需要导出 Markdown / PDF？
- 是否需要删除 session 的 UI？
- 是否需要保护隐私，避免误删/误上传？

### 3.5 简历可写点

```text
Implemented a session browser for transcript history, metadata indexing, full-text search, timestamp navigation, and structured export of classroom recordings.
```

---

## 4. P1/P2：Persistent whisper backend

> 状态：值得做，但需要进一步技术验证。
> 当前 `whisper.cpp` 仍按 chunk 调 CLI，存在进程启动开销。
> 目标是替代 per-chunk CLI，降低延迟和资源抖动。

### 4.1 初步目标

当前：

```text
每个 chunk -> 写临时 WAV -> 启动 whisper-cli -> 解析输出 -> 结束进程
```

目标：

```text
app 启动时加载模型一次
每个 chunk 直接发给长驻 backend
返回 timestamped segments
```

可能路线：

1. `whisper.cpp` server；
2. Python native binding；
3. 自写 local daemon；
4. C++/Python bridge。

### 4.2 初步收益

- 减少每 chunk 进程启动；
- 减少模型反复加载；
- 降低 latency jitter；
- 更接近产品级 architecture；
- 为更长课堂运行提供稳定性。

### 4.3 风险

- native binding 编译复杂；
- PyInstaller 打包更难；
- server 生命周期和端口管理复杂；
- crash 后恢复策略需要设计；
- timestamp alignment 要重新验证。

### 4.4 待确认问题

- 当前 CLI 实测延迟是否已经足够？
- 优化收益是否值得复杂度？
- 优先 server 还是 binding？
- 是否需要保留 CLI fallback？
- 如何 benchmark before/after？

### 4.5 简历可写点

```text
Replaced per-chunk whisper.cpp CLI calls with a persistent backend to reduce process startup overhead and improve latency stability in near-real-time classroom transcription.
```

---

## 5. P1：Benchmark / Regression suite

> 状态：非常值得做，但需要设计测试数据和指标。
> 当前已有 dedup、backend、UI support、pseudo-real chunk 测试；下一步应把这些升级成系统级 benchmark。

### 5.1 初步目标

量化以下指标：

```text
ASR quality
dedup behavior
latency per chunk
queue backlog
raw vs clean compression ratio
resource usage
Stop drain correctness
LLM summary quality
```

### 5.2 指标建议

#### ASR

```text
WER / CER
domain term error rate
obvious hallucination count
timestamp drift
```

#### Dedup

```text
Stage1 hit count
Stage2 hit count
over-delete cases
under-delete cases
compression ratio
empty clean chunks
```

#### Latency

```text
chunk_start_time
chunk_submit_time
backend_start_time
backend_end_time
ui_render_time
end-to-end delay
```

#### Resource

```text
CPU idle
memory pressure
RSS
queue size
temperature proxy if available
```

### 5.3 初步产物

```text
benchmarks/
  fixtures/
  reports/
  run_benchmark.py
  metrics.py
```

输出：

```text
benchmark_report.md
benchmark_metrics.json
latency.csv
resource_usage.csv
```

### 5.4 待确认问题

- 是否愿意保留匿名化课堂样本？
- 是否用 synthetic fixtures 代替真实录音？
- 是否需要固定一组公开音频作为 regression？
- 是否要人工标注 reference transcript？
- 是否要比较 large-v3 vs turbo / beam 3-8？

### 5.5 简历可写点

```text
Built a regression and benchmarking suite for ASR quality, deduplication precision, latency, queue backlog, and resource usage across classroom-style transcription scenarios.
```

---

## 6. P2：多语言 clean 层

> 状态：已有基础语言选择，但没有系统化 clean 层。
> 当前支持 English / Chinese / Mixed Chinese-English，但 mixed 和 Chinese 效果依赖模型与音频。
> 后续值得做，但应排在 LLM 和 session browser 之后。

### 6.1 初步方向

- 中文标点整理；
- 简繁体规范化；
- OpenCC 可选集成；
- 中英混合空格规则；
- language-specific denylist；
- Chinese/Mixed 模式测试集；
- 不启用 translate，保持 transcribe。

### 6.2 待确认问题

- 用户主要会录英文课，还是中英混合？
- 是否需要简体输出强制规范化？
- 是否接受引入 OpenCC 依赖？
- 是否需要中文 UI 文案和英文 UI 文案完全同步？

### 6.3 简历可写点

```text
Extended the clean-layer pipeline with multilingual transcript normalization, Chinese text normalization, and language-specific post-processing for English/Chinese classroom audio.
```

---

## 7. P2：Release / GitHub workflow

> 状态：已能打包 macOS Apple Silicon `.app`，但 release 流程仍可改进。
> 不作为最高优先级，但适合在阶段成果后处理。

### 7.1 初步方向

- GitHub Releases 发布 zip；
- 不把 zip push 到 repo；
- tag 版本号；
- release notes；
- 自动生成 shareable zip；
- smoke test before packaging；
- 后续 GitHub Actions 自动构建。

### 7.2 待确认问题

- 是否需要 notarization？
- 是否只给自己/朋友用？
- 是否需要签名？
- 是否需要 dmg？
- 是否需要版本检查？

### 7.3 简历可写点

```text
Set up a repeatable macOS packaging and release workflow with PyInstaller, GitHub Releases, reproducible build scripts, and external model management.
```

---

## 8. 推荐下一步执行顺序

当前 checkpoint：Step 1、Step 2、Step 3 已完成；独立 `llm/` package 骨架已创建。当前暂停点是 Step 3 checkpoint，恢复开发后的下一步是 Step 4：实现 transcript parser / chunker。

当前尚未实现：parser / chunker 业务逻辑、mock provider、真实 HTTP API、summary pipeline、output writer、renderer、CLI、UI、Phase 2A sidecar。

统一执行顺序如下：

```text
Step 1：冻结需求和架构边界
Step 2：更新设计文档
Step 3：创建独立 llm/ 模块骨架
Step 4：实现 transcript parser / chunker
Step 5：实现 provider interface 和 mock provider
Step 6：实现 output writer、state schema、renderer
Step 7：实现 Phase 1A after-stop summary mock pipeline
Step 8：实现 Phase 1B after-stop readable transcript mock pipeline
Step 9：新增 CLI 入口并用 mock 跑通
Step 10：补齐 mock tests、error injection、secret leakage tests
Step 11：实现 DeepSeek / OpenAI-compatible provider
Step 12：本地手动真实 API smoke test
Step 13：验证 Phase 1A / 1B 真实课堂 session 输出质量
Step 14：实现 Phase 2A rolling sidecar
Step 15：验证单 worker、coalescing、atomic replace、final reconciliation
Step 16：实现 Phase 2B 应用内 QTextBrowser 预览
Step 17：长时间课堂稳定性测试
Step 18：确认稳定后再考虑默认开关策略
```

---

## 9. 当前不确定项清单

以下内容尚未与用户充分确认，后续实现前必须单独讨论：

1. DeepSeek 具体模型名和 endpoint 的配置名；
2. Phase 1A/1B 是否需要用户可选输出语言，还是先固定中文；
3. `raw.txt` 未来是否作为 optional evidence 输入；
4. Phase 2A 默认开关策略；
5. Phase 2A 真实课堂测试后是否调整 30 / 40 / 60 参数；
6. 是否需要记录 LLM cost / token / generation time metrics；
7. session browser 是否需要数据库；
8. search 是否只搜 clean，还是同时搜 raw/summary/readable outputs；
9. benchmark 是否需要真实课堂样本。

已冻结，不再作为不确定项：

```text
API key 第一版只从 DEEPSEEK_API_KEY 读取
Phase 1A 默认中文
Phase 1A 必需输入是 clean.txt
raw.txt 不参与 Phase 1A
LLM 不修改 raw.txt / clean.txt / session.log / config.json
```

---

## 10. 总结

下一阶段最高价值不是继续微调 ASR，而是把已经生成的 transcript 变成有用的学习材料和可检索资料。

最优先开发：

```text
LLM 后处理管线
```

它应该满足：

```text
可选
异步
timestamp-grounded
不阻塞主链路
不覆盖 raw/clean/session.log/config.json
state JSON 是阅读稿真实状态源
Markdown / HTML 是派生视图
正式 UI 使用 QTextBrowser.setHtml()
失败可恢复
API key 不入仓库
API key 不入 settings / config / session output / logs
```

其余方向：

```text
Session Browser / Search
Persistent whisper backend
Benchmark / Regression suite
多语言 clean 层
Release workflow
```

都值得做，但目前还没有完全细化，应先作为 next-level roadmap 记录，后续逐项展开。
