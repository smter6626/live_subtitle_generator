# user_understand.md

最后更新：2026-06-03

这份文档的用途是：当你对项目“有印象但记不住细节”时，用最短时间恢复上下文，并明确当前 LLM 分支到底要做什么、不能做什么、下一步怎么推进。它基于 `docs/工程细节.md`、`docs/goalForNextLevel.md`、`docs/LLM_POSTPROCESSING_DESIGN.md`、`docs/LLMsteps.md` 和 portfolio 文档整理。

## 1. 一句话理解项目

Classroom Live Transcriber 是一个本地 macOS Apple Silicon 课堂实时转写工具：麦克风录音后切成重叠音频块，用 `whisper.cpp` + Metal 转写，实时在 PySide6 UI 中显示，并为每次录音保存 `raw.txt`、`clean.txt`、`session.log`、`config.json`。

当前项目已经完成“本地近实时课堂转写”的基础产品形态。现在的重点不是继续改 ASR 主链路，而是把已完成的 transcript 变成更有学习价值的材料，优先方向是 LLM 后处理总结。

## 2. 当前主链路

稳定主链路如下：

```text
PySide6 UI
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore
```

运行时音频和文本流程如下：

```text
麦克风输入
-> 48kHz mono capture
-> ring buffer
-> 10s chunk / 3s overlap
-> 16kHz resample
-> whisper.cpp CLI + Metal + ggml/gguf model
-> raw lines
-> simple_dedup()
-> fuzzy_boundary_dedup()
-> clean lines
-> UI tables + session files
```

关键点：

- UI 入口是 `ui_app.py`。
- 状态机在 `transcription_controller.py`。
- 录音、chunk 调度、worker、dedup 在 `transcription_engine.py`。
- whisper.cpp 后端和旧 CLI helper 在 `stream_transcribe.py`。
- session 文件写入在 `transcript_store.py`。
- settings、模型选择、路径默认值在 `settings.py`、`model_manager.py`、`resource_paths.py`。

## 3. 当前已有能力

用户层面：

- 可以 Start / Stop 实时录音转写。
- Stop 会释放麦克风，并等待已提交音频块处理完成。
- UI 有 Clean Transcript、Raw Transcript、Logs 三个主要视图。
- Beam Size 可选 `3-8`，默认 `5`。
- Original Language 支持 English、Chinese、Mixed Chinese/English。
- 固定为 transcribe，不启用 translate。
- Model Manager 支持扫描、导入、下载、选择模型。
- 每次录音生成独立 session。

输出目录：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
  raw.txt
  clean.txt
  session.log
  config.json
```

`raw.txt` 是后端原始 timestamp 转写，尽量保存证据。`clean.txt` 是保守去重后的可读版本，不做语义纠错，不替代 raw evidence。

## 4. 已验证和已知限制

已验证路线：

- macOS Apple Silicon。
- `whisper.cpp` + Metal。
- 推荐模型 `large-v3`。
- 真实课堂测试中 raw/clean 能正常写入，10 分钟测试机身只是温，不烫。
- 当前转写质量比早期 `turbo` baseline 更适合作为课堂实时输入。

已知限制：

- 目前没有正式 notarization。
- 没有 Windows 打包。
- `whisper.cpp` 仍按每个 chunk 启动 CLI，存在进程启动开销。
- 没有 LLM summary 或语义结构化笔记功能。
- 没有 OpenCC / 简繁体规范化。
- `stream_transcribe.py` 长期看承担职责偏多。
- settings 还是简单 JSON，没有 schema migration。

## 5. 项目方向优先级

后续高价值方向按优先级排序：

1. LLM 离线/在线 API 后处理管线。
2. Session Browser / Search。
3. Persistent whisper backend。
4. Benchmark / Regression suite。
5. 多语言 clean 层。
6. Release / packaging 自动化。

当前阶段是第 1 项：LLM 后处理分支。

## 6. 当前阶段：LLM 分支目标

LLM 分支的核心目标是：把已有 session 的 `clean.txt` 作为只读输入，通过 DeepSeek / OpenAI-compatible LLM API 生成中文学习材料和中文阅读稿，并全部写成 `session_dir/llm/` 下的派生文件。

当前 Phase 1 拆成 Phase 1A 和 Phase 1B：先做 after-stop 中文总结，再做 after-stop 中文阅读稿。动态 sidecar 和 UI 预览属于 Phase 2，不是当前第一步。

第一版输入：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
  clean.txt
```

第一版输出：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
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

第一版默认输出语言：中文。

第一版核心产物：

- 课程整体总结。
- 按时间段 / 阶段组织的 timeline summary。
- 关键术语和解释。
- 重要细节。
- Action items。
- Review questions。
- Unclear / possible ASR errors。
- 尽可能带 timestamp grounding。

## 7. LLM 分支 Phase 划分

### Phase 1A：After-stop 中文总结

Phase 1A 是当前第一优先级。

规则：

- Stop 完成后运行。
- 读取当前 session 的 `clean.txt`。
- `clean.txt` 是第一输入源，也是 Phase 1A 唯一必需 transcript 输入。
- `raw.txt` 只保留为未来 optional evidence，不参与 Phase 1A。
- 输出默认中文。
- 输出写入 `session_dir/llm/`。
- 所有 LLM 失败都不能影响原有 ASR session。

Phase 1A 不包含：

- 动态中文阅读稿 sidecar。
- 实时逐 chunk 调 LLM。
- LLM cleanup / semantic rewrite。
- 自动替换 `clean.txt`。
- 修改 `raw.txt`。
- 把 API key 写入 settings 或 session 文件。

### Phase 1B：After-stop 中文阅读稿

Phase 1B 在 Phase 1A 基础上新增完整中文 readable transcript 派生稿。它不是证据层，也不是 summary。

规则：

- Stop complete 后读取完整 `clean.txt`。
- LLM 做结构化过滤、翻译和保守修订。
- 写入 state JSON。
- 本地 renderer 从 state JSON 生成 Markdown / HTML。
- Markdown / HTML 是派生视图，不是真实状态源。
- 真实状态源是 `readable_zh_final_state.json`。
- 不允许 LLM 直接自由生成并覆盖整个 Markdown / HTML。
- 输出阅读版和审计版。

输出规划：

```text
session_dir/llm/
  readable_zh_final_state.json
  readable_zh_final.md
  readable_zh_final.html
  review_zh_final.md
  review_zh_final.html
  readable_zh_errors.log
```

Markdown 标记语义：

- `~~删除线~~`：疑似语义重复、口头 restart、被后续完整表达覆盖的片段。
- `*斜体*`：专业术语、专有名词、暂不确定翻译、需要保留英文原词的词汇。
- `**[可疑] 文本**`：逻辑不完整、疑似 ASR 错误、需要人工核对。
- `<u><strong>[高风险可疑] 文本</strong></u>`：deadline、考试要求、作业要求、评分规则、项目提交要求等高价值但识别不可靠的信息。

### Phase 2A：动态中文阅读稿 sidecar

Phase 2A 是后续功能，不是当前 Phase 1A/1B 验收标准。

规则：

- 默认关闭。
- 录音期间持续生成中文阅读稿。
- 只读 newline-complete `clean.txt` 快照和当前结构化 state。
- 不进入 audio capture。
- 不进入 chunk scheduling。
- 不进入 dedup。
- 不进入 backend。
- 不进入 `TranscriptStore` 主写入链路。
- 不修改 `raw.txt`、`clean.txt`、`session.log`、`config.json`。
- 初始参数可配置：`interval_seconds = 30`、`clean_context_window_seconds = 40`、`editable_window_seconds = 60`。
- 最多一个 in-flight API request。
- 使用 pending snapshot coalescing，不形成 backlog。
- 最近 editable window 可修订，更早 frozen segment 不可改写。
- 动态文件使用 atomic replace，失败时保留上一版有效输出。

未来可能输出：

```text
session_dir/llm/
  live_readable_zh_state.json
  live_readable_zh_revisions.jsonl
  live_readable_zh.md
  live_readable_zh.html
  live_review_zh.md
  live_review_zh.html
  live_readable_zh_errors.log
```

### Phase 2B：应用内 Markdown / HTML 渲染

Phase 2B 是 Phase 2A 稳定后的 UI 预览。

规则：

- 正式产品使用 PySide6 `QTextBrowser.setHtml()`。
- 渲染路径：state JSON -> local renderer -> HTML -> `QTextBrowser.setHtml()`。
- Typora 和外部浏览器只用于开发 spot check。
- 不依赖 Typora。
- 不依赖外部浏览器。
- 不引入 `QWebEngineView`。
- sidecar worker 不能直接操作 Qt widget，只能发 signal 给 Qt 主线程。

## 8. LLM 分支硬边界

这是当前阶段最重要的约束。

绝对不能做：

- 不能把 LLM 接进实时 ASR 主链路。
- 不能让 LLM 影响 Start / Stop。
- 不能让 LLM 影响麦克风释放。
- 不能让 LLM 影响 UI 主线程稳定性。
- 不能让 LLM 修改 `raw.txt`。
- 不能让 LLM 修改 `clean.txt`。
- 不能让 LLM 修改 `session.log`。
- 不能让 LLM 修改 `config.json`。
- 不能把 API key 写进仓库。
- 不能把 API key 写进 settings。
- 不能把 API key 写进 `config.json`。
- 不能把 API key 写进 request/response log。
- 不能把 API key 写进 Markdown、HTML、JSON state 或错误日志。
- 不能在单元测试里真实调用 API。
- 不能把 Markdown 当真实状态源。
- 不能让 LLM 直接自由覆盖整个 Markdown / HTML。

所有 LLM 输出都应该是额外产物，不覆盖原始 evidence。`raw.txt`、`clean.txt`、`session.log`、`config.json` 属于不可变证据层。

## 9. DeepSeek / API key 规则

第一版 DeepSeek API key 只从环境变量读取：

```text
DEEPSEEK_API_KEY
```

第一版不要从这些地方读 key：

- app settings。
- `config/settings.json`。
- session `config.json`。
- 命令行参数。
- 仓库文件。
- `/docs`。
- session 输出文件。
- Markdown / HTML / JSON state。
- 错误日志。

第一版不要记录 request/response log。后续如果要加，也必须 opt-in，并且必须做 secret redaction。

DeepSeek 模型名和 endpoint 不应硬编码，应预留环境变量或 provider settings 配置能力。

## 10. 推荐实现顺序

当前 checkpoint：Step 1、Step 2、Step 3 已完成；当前暂停点是 Step 3 checkpoint。`docs/LLM_POSTPROCESSING_DESIGN.md` 已冻结第一版范围，独立 `llm/` package 骨架已创建并通过基础验证。

当前只有骨架，尚未实现 parser / chunker 业务逻辑、mock provider、真实 HTTP API、summary pipeline、output writer、renderer、CLI、UI 或 Phase 2A sidecar。恢复开发后的下一步是 Step 4：实现 transcript parser / chunker。

后续推荐顺序：

1. 冻结需求和架构边界。
2. 更新设计文档。
3. 创建独立 `llm/` 模块骨架。
4. 实现 transcript parser / chunker。
5. 实现 provider interface 和 mock provider。
6. 实现 output writer、state schema、renderer。
7. 实现 Phase 1A after-stop summary mock pipeline。
8. 实现 Phase 1B after-stop readable transcript mock pipeline。
9. 新增 CLI 入口并用 mock 跑通。
10. 补齐 mock tests、error injection、secret leakage tests。
11. 实现 DeepSeek / OpenAI-compatible provider。
12. 本地手动真实 API smoke test。
13. 验证 Phase 1A / 1B 真实课堂 session 输出质量。
14. 实现 Phase 2A rolling sidecar。
15. 验证单 worker、coalescing、atomic replace、final reconciliation。
16. 实现 Phase 2B 应用内 QTextBrowser 预览。
17. 长时间课堂稳定性测试。
18. 确认稳定后再考虑默认开关策略。

推荐 CLI 形态：

```bash
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --output-language zh
```

真实 API 手动测试只在本地 shell 里临时提供环境变量：

```bash
DEEPSEEK_API_KEY=... venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID>
```

## 11. 未来 LLM 模块建议结构

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

职责：

- `provider_base.py`：统一 provider interface。
- `deepseek_provider.py`：DeepSeek API adapter。
- `openai_compatible_provider.py`：预留其他兼容 API。
- `transcript_chunker.py`：解析 `clean.txt` 并按时间戳 / token / 字符预算切块。
- `summary_pipeline.py`：map-reduce summary pipeline。
- `prompt_templates.py`：集中管理 prompt，避免散落在 UI。
- `output_writer.py`：写 Markdown / JSON / error log。
- `state_schema.py`：定义 readable transcript state 和 patch schema。
- `renderer.py`：从 state JSON 本地渲染 Markdown / HTML。

## 12. 测试策略

已有测试重点：

- `testCodes/test_ui_support.py`
- `testCodes/test_backends.py`
- dedup 相关测试
- pseudo-real chunk / boundary 测试

LLM 新增后建议测试：

```text
testCodes/test_llm_chunker.py
testCodes/test_llm_pipeline.py
testCodes/test_llm_outputs.py
testCodes/test_llm_provider_mock.py
```

LLM 测试必须覆盖：

- `clean.txt` timestamp parser。
- no timestamp fallback。
- 空 transcript。
- deterministic chunking。
- prompt payload construction。
- mock provider success。
- mock provider failure。
- malformed response。
- missing `DEEPSEEK_API_KEY`。
- output schema。
- API key 不出现在输出或日志中。
- LLM error 不修改 `raw.txt` / `clean.txt` / `session.log` / `config.json`。
- readable final state / Markdown / HTML。
- review Markdown / HTML。
- HTML escaping。
- annotation rendering。
- renderer deterministic。
- atomic replace。
- Phase 1A/1B 不生成 live sidecar 输出。
- Phase 2A 覆盖 newline-complete snapshot、high-water mark、30/40/60 参数、editable/frozen window、coalescing、single in-flight request、Stop final reconciliation。

## 13. UI 接入原则

UI 接入是最后一步。

未来 UI 最小形态：

```text
LLM Post-processing
[Generate Summary]
[Open Summary]
[Cancel]
Provider: DeepSeek
Status: Idle / Running / Failed / Complete
```

规则：

- Stop complete 后才允许 Generate Summary。
- LLM job 必须跑在后台线程。
- Qt 主线程只更新状态，不直接调用 API。
- 无 API key 时提示明确，但 app 不崩溃。
- 断网 / 超时 / API error 时写 `llm_errors.log`，UI 显示 Failed。
- 完成后可以打开 `summary.md`。
- 不在录音中默认调用 LLM。
- Phase 2B 正式预览使用 `QTextBrowser.setHtml()`。
- Typora 和外部浏览器只做开发 spot check。
- 不引入 `QWebEngineView`。
- sidecar worker 不能直接操作 Qt widget。

## 14. 如果你回来继续开发，先看这里

快速恢复上下文：

1. 先读本文件。
2. 再读 `docs/LLM_POSTPROCESSING_DESIGN.md`，确认 Phase 1A/1B/2A/2B 边界。
3. 再读 `docs/LLMsteps.md`，从 Step 4 开始继续。
4. 如果要理解原 ASR 主链路，读 `docs/工程细节.md`。
5. 如果要写对外介绍，读 `docs/Yeming_Dai_Audio_Transcription_Portfolio.md`。

当前下一步应该是：

```text
实现 transcript parser / chunker，然后按 mock provider -> output writer/state schema/renderer -> Phase 1A/1B mock pipeline 推进；不接 UI，不碰 ASR 主链路。
```

## 15. 当前不要做的事

为了保护已有稳定性，当前不要做：

- 不要改 `ui_app.py` 接 LLM，除非 CLI/mock pipeline 已经完成。
- 不要改 `transcription_engine.py`。
- 不要改 `transcription_controller.py`。
- 不要改 `transcript_store.py` 的 raw/clean 写入逻辑。
- 不要改 `stream_transcribe.py` 的 chunk / backend / dedup 逻辑。
- 不要改 `settings.py` 来保存 API key。
- 不要运行真实 API 测试，除非已经完成 mock 测试并明确进入手动 smoke test。
- 不要把 Phase 2A 动态 sidecar 当成 Phase 1A/1B。
- 不要把 Markdown 当真实状态源。
- 不要让 LLM 直接覆盖完整 Markdown / HTML。
- 不要引入 Typora、外部浏览器或 `QWebEngineView` 作为正式依赖。

## 16. 回滚思路

LLM 应该天然容易回滚，因为它是 sidecar。

回滚优先级：

1. 如果 LLM 输出有问题，删除或忽略 `session_dir/llm/`。
2. 如果 DeepSeek provider 有问题，保留 mock pipeline，禁用真实 provider。
3. 如果 UI 集成有问题，先禁用 UI 按钮，保留 CLI。
4. 如果 Phase 2A 动态 sidecar 不稳定，关闭或删除 live readable sidecar，保留 Phase 1A/1B after-stop 输出。
5. 任何时候 raw/clean/session 主链路必须能单独运行。

## 17. 动态维护区：LLM 分支需求清单

这一节用于后续动态维护。每次 LLM 分支需求变化，都优先更新这里。

当前已冻结需求：

- Phase 1A 是 after-stop 中文总结。
- Phase 1B 是 after-stop 中文阅读稿。
- Phase 2A 是动态中文阅读稿 sidecar，默认关闭。
- Phase 2B 是应用内 Markdown / HTML 渲染。
- Phase 1A/1B 默认中文输出。
- Phase 1A/1B 只要求读取 `clean.txt`。
- `raw.txt` Phase 1A 不参与，只作为未来 optional evidence。
- 输出目录固定为 `session_dir/llm/`。
- 输出包括 `summary.md`、`summary.json`、`sections.json`、`key_terms.json`、`action_items.json`、`llm_errors.log`。
- Phase 1B 输出包括 `readable_zh_final_state.json`、`readable_zh_final.md`、`readable_zh_final.html`、`review_zh_final.md`、`review_zh_final.html`、`readable_zh_errors.log`。
- Phase 2A 输出规划包括 `live_readable_zh_state.json`、`live_readable_zh_revisions.jsonl`、`live_readable_zh.md`、`live_readable_zh.html`、`live_review_zh.md`、`live_review_zh.html`、`live_readable_zh_errors.log`。
- API key 第一版只从 `DEEPSEEK_API_KEY` 读取。
- 不保存 API key 到仓库、`/docs`、settings、config、session 输出、request/response log、Markdown、HTML、JSON state、错误日志。
- LLM 失败不影响 raw/clean/session/config/Start/Stop/麦克风/UI 主线程。
- Markdown / HTML 是派生视图，state JSON 是真实状态源。
- 正式 UI 使用 `QTextBrowser.setHtml()`，Typora 和浏览器只用于开发 spot check。
- 实现顺序是 18 步：文档 -> llm skeleton -> parser/chunker -> mock provider -> output writer/state/renderer -> Phase 1A -> Phase 1B -> CLI -> mock tests -> DeepSeek provider -> real API manual smoke test -> Phase 2A -> Phase 2B。

待实现：

- transcript parser / chunker。
- prompt templates。
- output writer。
- state schema。
- renderer。
- mock provider。
- Phase 1A summary pipeline。
- Phase 1B readable transcript pipeline。
- CLI 入口。
- DeepSeek provider。
- LLM mock 测试。
- 真实 API 手动 smoke test。
- Phase 2A rolling sidecar。
- Phase 2B `QTextBrowser.setHtml()` UI preview。

待确认：

- DeepSeek 具体模型名是否使用环境变量配置，例如 `DEEPSEEK_MODEL`。
- DeepSeek endpoint 配置名。
- summary/readable 是否支持用户选择输出语言，还是第一阶段固定中文。
- `raw.txt` 未来是否要作为 unclear evidence 输入。
- Phase 2A 默认开关策略。
- Phase 2A 真实课堂测试后是否调整 30 / 40 / 60 参数。
- 是否需要记录 LLM cost / token / generation time metrics。

明确暂缓：

- Phase 2A 动态中文阅读稿 sidecar。
- Phase 2B 应用内预览。
- 跨 session RAG。
- Session Browser / Search。
- Persistent whisper backend。
- LLM 自动纠错 clean transcript。
- API key settings / Keychain 管理。
