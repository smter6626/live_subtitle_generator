# whisper_static.md

最后更新：2026-06-22  
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
可选 LLM sidecar 读取 clean.txt 并生成一个中文 Markdown 辅助阅读稿
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
旁路读取 clean.txt snapshot
额外派生 Markdown 输出到 session_dir/llm/
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

### 4.1 Markdown-only 原则

LLM sidecar 只生成用户可读 Markdown artifact。程序不得把模型生成内容作为稳定内部状态源。

稳定主路径必须满足：

```text
不解析模型生成 JSON 作为程序状态
不依赖模型生成 enum
不依赖 segment status
不依赖 annotation type
不依赖机器可读 key_terms/action_items
不做局部冻结/局部删除/局部合并
不做结构化 review state
```

LLM 输出可以内容质量不稳定，但不得导致程序状态不稳定。程序只负责：

```text
读取 clean.txt snapshot
调用 provider.generate_text()
接收 Markdown/text
做 basic sanity / secret safety check
atomic write 到 session_dir/llm/readable_zh.md
把状态和错误写入 session_dir/llm/log.md
失败时保留上一版 readable_zh.md
```

---

## 5. LLM Markdown sidecar 合同

### 5.1 输入

LLM sidecar 的唯一 transcript 输入是：

```text
session_dir/clean.txt
```

可选只读输入：

```text
session metadata
```

第一版不使用：

```text
raw.txt
audio
cross-session history
external knowledge base
```

### 5.2 输出

LLM 输出目录固定为：

```text
session_dir/llm/
```

必需输出仅限：

```text
readable_zh.md
log.md
```

文件语义：

```text
readable_zh.md = 当前 LLM 中文 Markdown 输出快照
log.md = LLM sidecar 状态、错误和诊断记录，必须 sanitized
```

不得要求或生成作为稳定合同的：

```text
summary.json
sections.json
key_terms.json
action_items.json
readable_zh_final_state.json
readable_zh_final.html
review_zh_final.md
review_zh_final.html
live_readable_zh_state.json
live_readable_zh_revisions.jsonl
live_readable_zh.html
live_review_zh.md
live_review_zh.html
*.log
```

如果已有旧实现仍生成上述 legacy 文件，它们不得作为新主路径、UI 或验收标准。后续应逐步旁路或清理。

### 5.3 触发模式

LLM sidecar 可以有两种触发模式，但输出仍写同一组文件：

```text
Stop 后 final refresh
录音中 live refresh
```

两种模式都写：

```text
session_dir/llm/readable_zh.md
session_dir/llm/log.md
```

Stop 后 final refresh 成功时覆盖 `readable_zh.md` 为最终快照。录音中 live refresh 成功时覆盖 `readable_zh.md` 为当前快照。失败时保留上一版 `readable_zh.md`，只向 `log.md` 追加 sanitized 记录。

### 5.4 Live refresh 稳定性合同

live refresh 只做 Markdown snapshot refresh，不做结构化增量合并。

必须满足：

```text
默认关闭或显式启用
只读 clean.txt snapshot
最多一个 in-flight API request
pending snapshot coalescing
不产生 backlog
可配置最小刷新间隔
atomic replace readable_zh.md
失败保留上一版 readable_zh.md
不进入 ASR 主链路
```

不得实现：

```text
frozen segment
editable segment
replace / annotate / mark_duplicate
base_revision
state revisions
局部 merge
```

### 5.5 UI preview 合同

UI 只显示 `readable_zh.md` 的当前内容。

允许路径：

```text
readable_zh.md
-> 本地 Markdown 渲染或 QTextBrowser 兼容显示
-> UI refresh
```

不得引入：

```text
Typora 产品依赖
外部浏览器产品依赖
QWebEngineView
```

Typora 和浏览器只能作为开发 spot check 工具。

sidecar worker 不得直接操作 Qt widget，只能通过 signal 让 Qt 主线程重新读取或渲染 Markdown。

---

## 6. Provider 与 API key 合同

### 6.1 Provider 抽象

LLM 实现必须使用 provider abstraction，使 parser、chunker、prompt、writer 与具体 provider 解耦。

稳定主路径最小 provider 能力：

```text
generate_text(...)
typed provider errors
```

`generate_json(...)` 不属于稳定主路径合同。若代码中保留，只能作为 legacy、测试或未来实验能力，不得驱动主 UI、主 sidecar 或程序状态。

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
readable_zh.md
log.md
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

- `readable_zh.md` 必须使用 atomic write / atomic replace；
- `log.md` 只记录 sanitized diagnostics；
- 失败时保留上一版有效 `readable_zh.md`；
- 不记录 API key、Authorization header、完整 raw request body 或完整 raw response body；
- 不落盘模型 raw response；
- 不落盘模型生成 JSON state；
- 不落盘 HTML 作为稳定交付物。

---

## 8. Prompt 与输出质量合同

prompt 只用于提高输出质量，不是程序稳定性保证。程序稳定性不得依赖模型遵守特定 JSON schema、enum 或结构化字段。

prompt 应要求：

```text
中文 Markdown 输出
适合课堂中实时查看或课后复习
不编造 transcript 外事实
尽量保留 timestamp grounding
区分 transcript 明确证据和模型推断
不确定内容用自然语言标记
ASR 修正只能作为 possible correction
不得覆盖 clean.txt
不得输出 API key 或敏感诊断信息
```

`readable_zh.md` 推荐包含但不强制结构化解析：

```text
当前课堂/片段总结
重要提醒或任务
可能的截止日期、作业、项目要求
不确定或疑似 ASR 错误内容
```

这些栏目只是 Markdown 文本。程序不得解析它们作为机器可读状态。

高风险内容，如 deadline、考试要求、作业要求、评分规则和项目提交要求，必须保留不确定性标注，不得过度自信。

---

## 9. 测试合同

自动测试必须使用 mock provider，不得真实调用 DeepSeek 或任何外部 LLM API。

现有基线测试：

```bash
venv/bin/python testCodes/test_ui_support.py
venv/bin/python testCodes/test_backends.py --skip-faster-smoke
```

LLM Markdown sidecar 测试必须覆盖：

```text
clean.txt timestamp parser
no timestamp fallback
empty transcript
deterministic chunking
Markdown prompt construction
mock provider text success/failure
missing DEEPSEEK_API_KEY behavior
API key 不出现在 readable_zh.md / log.md
raw.txt / clean.txt / session.log / config.json unchanged
readable_zh.md atomic write / replace
log.md sanitized diagnostics
failure preserves previous readable_zh.md
single in-flight request
pending snapshot coalescing
sidecar disabled/off leaves ASR independently usable
```

不再作为稳定合同测试的内容：

```text
schema validation failure
model-generated JSON normalization
summary/readable/review JSON outputs
HTML file outputs
annotation rendering
renderer deterministic from state JSON
editable/frozen window
invalid schema rejection
base_revision mismatch rejection
structured review state
```

---

## 10. 非目标

当前 LLM 分支不做：

```text
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
机器可读 key_terms/action_items
结构化 summary JSON
结构化 readable state
segment annotation
segment status
局部冻结
局部删除
局部合并
review state
LLM JSON schema parsing as core path
落盘 HTML
QWebEngineView
```

当前 LLM 分支只推进：

```text
clean.txt snapshot -> provider.generate_text() -> readable_zh.md -> UI Markdown preview
```

---

## 11. 长期 roadmap

当前优先级：

1. LLM Markdown sidecar + UI preview；
2. Session Browser / Search；
3. Persistent whisper backend；
4. Benchmark / Regression suite；
5. 多语言 clean 层；
6. Release / packaging 自动化。

除 LLM Markdown sidecar + UI preview 外，其余方向尚未进入详细实现状态。实现前必须单独细化目标、边界、测试和回滚。

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
2. 如果真实 provider 有问题，禁用真实 provider；
3. 如果 UI preview 有问题，隐藏或禁用 LLM preview，保留 ASR UI；
4. 如果 live refresh 不稳定，关闭 live refresh，保留 Stop 后 final refresh 或完全禁用 LLM；
5. 任何时候 raw/clean/session/config 主链路必须能单独运行。

禁止使用粗暴回滚破坏其他未提交工作：

```bash
git reset --hard
git clean -fd
```

除非用户明确确认当前工作区可以全部丢弃。

---

## 14. 最终交付物

LLM Markdown sidecar 完成后，应能提供：

```text
session_dir/llm/readable_zh.md
session_dir/llm/log.md
应用内 LLM Markdown 预览区域
provider status / last updated time
Open Markdown
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
