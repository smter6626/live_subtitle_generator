# whisper_static.md

最后更新：2026-06-16  
文档角色：稳定合同（static contract）

本文件记录 Classroom Live Transcriber / whisper 项目的长期稳定要求、架构边界、交付目标和非目标。只有当项目方向、范围、Phase 设计、交付物或硬约束发生实质变化时才更新本文件。

动态执行状态见：`docs/whisper_runtime.md`。

---

## 1. 项目身份

Classroom Live Transcriber 是一个 macOS Apple Silicon 本地 near-real-time 课堂转写工具。

核心价值：

```text
本地实时课堂转写
稳定保存 raw / clean evidence
后续通过可选 LLM sidecar 生成学习材料
```

当前稳定主链路：

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

每个 session 基础输出：

```text
raw.txt
clean.txt
session.log
config.json
```

---

## 2. 稳定 ASR 主链路合同

### 2.1 主链路职责

ASR 主链路负责：

- 录音；
- chunk 调度；
- whisper.cpp 转写；
- raw evidence 写入；
- clean 去重输出；
- UI 实时展示；
- session 文件保存；
- Stop drain；
- 麦克风释放。

### 2.2 关键音频参数

当前基础参数：

```text
CAPTURE_RATE = 48000
TRANSCRIBE_RATE = 16000
CHANNELS = 1
BLOCK_SECONDS = 10
OVERLAP_SECONDS = 3
STEP_SECONDS = 7
RING_BUFFER_SECONDS = 30
```

这些参数属于稳定主链路的一部分。除非任务明确针对 ASR 调优，否则 LLM 分支不得修改它们。

### 2.3 后端

当前 UI 主路径使用 `WhisperCppBackend`：

```text
16kHz mono float32 chunk
-> 临时 PCM16 WAV
-> whisper-cli
-> timestamped raw lines
```

模型由 Model Manager 管理，`.app` 内置 `whisper-cli`，不内置模型文件。

---

## 3. Evidence layer 不可变合同

以下文件是每个 session 的不可变 evidence layer：

```text
raw.txt
clean.txt
session.log
config.json
```

任何 LLM、搜索、总结、阅读稿、benchmark、session browser 或 UI 预览功能都不得：

```text
修改
覆盖
删除
重命名
截断
追加 LLM 内容
替换为翻译稿
替换为纠错稿
把 LLM 输出混入
```

这些文件必须始终能作为 ASR session 的原始证据层独立存在。

---

## 4. LLM sidecar 合同

LLM 分支是独立 sidecar，不属于实时 ASR 主链路。

LLM 只能做：

```text
可选
异步
旁路读取
额外派生输出到 session_dir/llm/
```

LLM 不得进入：

```text
audio capture
ring buffer
chunk scheduling
resample
WhisperCppBackend
TranscriptionEngine 转写 worker 主循环
simple_dedup()
fuzzy_boundary_dedup()
TranscriptStore raw / clean 主写入路径
Start / Stop
麦克风释放
UI 主线程
```

LLM 失败不得影响：

```text
raw.txt
clean.txt
session.log
config.json
Start/Stop
麦克风释放
UI 主线程稳定性
future recordings
```

所有 LLM 输出都是派生产物，不是 evidence layer。

---

## 5. LLM Phase 合同

### 5.1 Phase 1A：After-stop 中文总结

Phase 1A 是第一优先级。

触发条件：

```text
Stop complete 后
Whisper queue drained 后
```

输入：

```text
session_dir/clean.txt
```

可选输入：

```text
只读 session metadata
```

第一版不使用：

```text
raw.txt
audio
cross-session history
external knowledge base
```

输出目录：

```text
session_dir/llm/
```

必需输出：

```text
summary.md
summary.json
sections.json
key_terms.json
action_items.json
llm_errors.log
```

内容要求：

- 中文输出；
- timeline / section summary；
- key terms；
- important details；
- assignments / deadlines / project instructions；
- professor-emphasized points；
- action items；
- review questions；
- unclear / possible ASR errors；
- timestamp grounding；
- 不编造 transcript 外的信息。

---

### 5.2 Phase 1B：After-stop 中文阅读稿

Phase 1B 生成完整中文 readable transcript 派生稿。它不是 evidence，也不是 summary。

输入：

```text
完整 clean.txt
```

输出：

```text
readable_zh_final_state.json
readable_zh_final.md
readable_zh_final.html
review_zh_final.md
review_zh_final.html
readable_zh_errors.log
```

合同：

```text
state JSON 是真实状态源
Markdown / HTML 是派生视图
LLM 不直接自由生成并覆盖整个 Markdown / HTML
本地 renderer 负责从 state JSON 生成 Markdown / HTML
```

阅读版用于复习，审计版用于保留疑似重复、修订痕迹、不确定术语和 possible corrections。

---

### 5.3 Phase 2A：动态中文阅读稿 sidecar

Phase 2A 是后续功能，不是 Phase 1A/1B 的验收内容。

默认状态：

```text
关闭
```

运行时：

```text
录音期间可选运行
只读 newline-complete clean.txt 快照
只读当前结构化 state
```

初始可配置参数：

```text
interval_seconds = 30
clean_context_window_seconds = 40
editable_window_seconds = 60
```

输出：

```text
live_readable_zh_state.json
live_readable_zh_revisions.jsonl
live_readable_zh.md
live_readable_zh.html
live_review_zh.md
live_review_zh.html
live_readable_zh_errors.log
```

合同：

- 最多一个 in-flight API request；
- 使用 pending snapshot coalescing；
- 不产生 backlog；
- frozen segment 不可改写；
- editable segment 可在窗口内 replace / annotate / mark_duplicate；
- 动态文件使用 atomic replace；
- 失败保留上一版有效输出；
- 不进入 ASR 主链路。

---

### 5.4 Phase 2B：应用内 Markdown / HTML 渲染

Phase 2B 在 Phase 2A 稳定后实现。

正式 UI 使用：

```text
QTextBrowser.setHtml()
```

渲染路径：

```text
state JSON
-> local renderer
-> HTML
-> QTextBrowser.setHtml()
```

不得引入：

```text
Typora 产品依赖
外部浏览器产品依赖
QWebEngineView
```

Typora 和浏览器只能作为开发 spot check 工具。

sidecar worker 不得直接操作 Qt widget，只能通过 signal 让 Qt 主线程更新 UI。

---

## 6. Provider 与 API key 合同

### 6.1 Provider 抽象

LLM 实现必须使用 provider abstraction，使 parser、chunker、prompt、state、renderer、output 与具体 provider 解耦。

最小 provider 能力：

```text
generate_json(...)
generate_text(...)
typed provider errors
```

错误类型至少应能区分：

```text
missing API key
authentication failure
rate limit
timeout
malformed response
generic network/API failure
```

### 6.2 DeepSeek / OpenAI-compatible

第一版 provider 是 DeepSeek / OpenAI-compatible API。

API key 只允许从环境变量读取：

```text
DEEPSEEK_API_KEY
```

模型名和 endpoint 不得作为永久硬编码常量。应通过环境变量或 provider settings 保留可配置能力，例如：

```text
DEEPSEEK_MODEL
provider endpoint setting
```

### 6.3 禁止保存 API key

API key 不得写入：

```text
仓库
/docs
settings
config/settings.json
session config.json
raw.txt
clean.txt
request log
response log
Markdown
HTML
JSON state
错误日志
终端输出
异常消息
```

第一版不记录 request/response log。未来如果加入，必须 opt-in，并做 secret redaction。

---

## 7. 输出与文件写入合同

所有 LLM 输出写在：

```text
session_dir/llm/
```

创建或替换 `llm/` 下派生文件不得修改：

```text
raw.txt
clean.txt
session.log
config.json
```

写入原则：

- JSON / Markdown / HTML 输出尽量使用 atomic write；
- 动态 sidecar 文件必须使用 atomic replace；
- 失败时保留上一版有效输出；
- error log 只记录 sanitized diagnostics；
- 不记录 API key、Authorization header、完整 raw request body 或完整 raw response body。

---

## 8. Prompt 与输出质量合同

所有 Phase 1A/1B/2A prompt 必须要求：

```text
中文输出
不编造 transcript 外事实
保留 timestamp grounding
区分 transcript 明确证据和模型推断
不确定内容标记 unclear
ASR 修正只能作为 possible correction
不得覆盖 clean.txt
不得直接自由覆盖完整 Markdown / HTML
```

Summary 至少应包含：

```text
overview
timeline
key terms
important details
action items
review questions
unclear / possible ASR errors
```

高风险内容，如 deadline、考试要求、作业要求、评分规则和项目提交要求，必须保留不确定性标注，不得过度自信。

---

## 9. 测试合同

自动测试必须使用 mock provider，不得真实调用 DeepSeek 或任何外部 LLM API。

现有基线测试：

```bash
venv/bin/python testCodes/test_ui_support.py
venv/bin/python testCodes/test_backends.py --skip-faster-smoke
```

LLM 后续测试建议：

```text
testCodes/test_llm_chunker.py
testCodes/test_llm_provider_mock.py
testCodes/test_llm_outputs.py
testCodes/test_llm_pipeline.py
```

LLM 测试必须覆盖：

```text
clean.txt timestamp parser
no timestamp fallback
empty transcript
deterministic chunking
prompt payload construction
mock provider success/failure
malformed response
schema validation failure
missing DEEPSEEK_API_KEY behavior
API key 不出现在任何输出或日志
raw.txt / clean.txt / session.log / config.json unchanged
summary/readable/review Markdown/HTML outputs
HTML escaping
annotation rendering
renderer deterministic
atomic replace
Phase 1A/1B 不生成 live sidecar 输出
```

Phase 2A 额外覆盖：

```text
newline-complete snapshot
high-water mark
configurable 30/40/60 参数
editable/frozen window
coalescing
single in-flight request
invalid schema rejection
base_revision mismatch rejection
Stop final reconciliation
sidecar disabled/off leaves ASR independently usable
```

---

## 10. 非目标

当前 LLM 分支不做：

```text
实时逐 chunk 调 LLM
自动替换 clean.txt
强制联网
本地大模型推理
跨 session RAG
云端同步
自动上传 raw 音频
session browser
persistent whisper backend
OpenCC / 多语言 clean 层
API key settings / Keychain 管理
正式 UI 集成
Phase 2A 动态 sidecar
Phase 2B 应用内预览
```

这些可以作为后续 roadmap，但不得混入当前 Phase 1A/1B 的实现步骤。

---

## 11. 长期 roadmap

当前优先级：

1. LLM 离线/在线 API 后处理管线；
2. Session Browser / Search；
3. Persistent whisper backend；
4. Benchmark / Regression suite；
5. 多语言 clean 层；
6. Release / packaging 自动化。

除 LLM 后处理管线外，其余方向尚未进入详细实现状态。实现前必须单独细化目标、边界、测试和回滚。

---

## 12. Repo / artifact 合同

不应提交：

```text
venv/
external/whisper.cpp/
models/
outputs/
test_runs/
build/
dist/
*.bin
*.gguf
*_raw.txt
*_clean.txt
API key
大型日志
```

`.app` 打包：

- macOS Apple Silicon；
- PyInstaller；
- app 可内置 `whisper-cli`；
- app 不内置模型；
- 不把 settings/models/outputs 写进 app bundle。

---

## 13. 回滚合同

LLM 应天然容易回滚，因为它是 sidecar。

回滚优先级：

1. 如果 LLM 输出有问题，删除或忽略 `session_dir/llm/`；
2. 如果真实 provider 有问题，保留 mock pipeline，禁用真实 provider；
3. 如果 UI 集成有问题，禁用 UI 按钮，保留 CLI；
4. 如果 Phase 2A sidecar 不稳定，关闭 live sidecar，保留 Phase 1A/1B after-stop 输出；
5. 任何时候 raw/clean/session/config 主链路必须能单独运行。

禁止使用粗暴回滚破坏其他未提交工作：

```bash
git reset --hard
git clean -fd
```

除非用户明确确认当前工作区可以全部丢弃。

---

## 14. 最终交付物

LLM 后处理管线完成后，应能提供：

### Phase 1A

```text
summary.md
summary.json
sections.json
key_terms.json
action_items.json
llm_errors.log
```

### Phase 1B

```text
readable_zh_final_state.json
readable_zh_final.md
readable_zh_final.html
review_zh_final.md
review_zh_final.html
readable_zh_errors.log
```

### Phase 2A

```text
live_readable_zh_state.json
live_readable_zh_revisions.jsonl
live_readable_zh.md
live_readable_zh.html
live_review_zh.md
live_review_zh.html
live_readable_zh_errors.log
```

### Phase 2B

```text
应用内 LLM 中文阅读稿预览 tab
reading / review mode
provider status
last updated time
Open Markdown
Open HTML
```

所有交付物都必须保持 sidecar 属性，不得破坏稳定 ASR 主链路。

---

## 15. 修改本文件的条件

只有以下情况才更新本文件：

```text
项目目标变化
Phase 定义变化
证据层规则变化
LLM sidecar 边界变化
API key / privacy 规则变化
最终交付物变化
长期 roadmap 优先级变化
测试合同变化
```

普通 step 完成、active task 切换、临时执行命令更新，只修改：

```text
docs/whisper_runtime.md
```
