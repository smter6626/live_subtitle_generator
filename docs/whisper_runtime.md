# whisper_runtime.md

最后更新：2026-06-21  
文档角色：动态执行状态（runtime state）

本文件用于记录 Classroom Live Transcriber / whisper 项目的**已执行步骤、唯一 active 任务、当前任务的可执行说明、后续步骤摘要**。每完成一个步骤后更新状态，不删除已完成记录。

对应稳定合同见：`docs/whisper_static.md`。

---

## 0. 使用规则

### 0.1 本文件什么时候更新

每完成一个开发步骤后更新本文件：

1. 将刚完成的 active step 标记为 `已完成`；
2. 在“已完成步骤记录”中追加结果、验证命令和结论；
3. 激活下一步，保证全文件只有一个 `ACTIVE`；
4. 将下一步细化到可以直接交给 Codex 或人工照搬执行；
5. 不删除历史完成记录。

### 0.2 本文件不负责什么

本文件不重新定义长期方向。以下内容属于 `docs/whisper_static.md`：

- 项目身份；
- 稳定 ASR 主链路；
- 不可变 evidence layer；
- LLM sidecar 长期边界；
- Phase 1A / 1B / 2A / 2B 的定义；
- API key、隐私、失败隔离；
- 最终交付物；
- 非目标和长期 roadmap。

如果方向或计划发生变化，先更新 `docs/whisper_static.md`，再同步本文件。

### 0.3 Codex 与 runtime

除非用户明确要求，Codex 默认只读取本文件，不主动修改本文件。

通常流程：

```text
Codex 执行代码 Step
-> commit + push 到当前 feature branch
-> 人工审查实现和测试
-> 再由人工/ChatGPT 受控更新 docs/whisper_runtime.md
```

这样避免 runtime 提前进入完成态，或与实际代码实现发生版本漂移。

---

## 1. 当前 checkpoint

```text
当前分支：llm-sidecar-phase1
当前 checkpoint：Step 5 已完成并已 push
唯一 ACTIVE 任务：Step 6 - 实现 output writer、state schema、renderer
```

已完成：

```text
Step 1：冻结需求和架构边界
Step 2：更新设计文档
Step 3：创建独立 llm/ 模块骨架
Step 4：实现 transcript parser / chunker version1
Step 5：实现 provider interface、mock provider，并完成 Step 4 parser/chunker hardening
```

当前尚未实现：

```text
output writer
state schema
renderer
summary pipeline
readable transcript pipeline
CLI
真实 HTTP API
UI
Phase 2A rolling sidecar
```

当前 `llm/` package 已包含：

```text
provider interface
mock provider
parser / chunker
parser/chunker hardening: raw_line + end<start fallback
```

---

## 2. 已完成步骤记录

### Step 1：冻结需求和架构边界

状态：已完成。

核心结论：

- LLM 是 DeepSeek / OpenAI-compatible 后处理模块，不是实时 ASR 主链路的一部分。
- Phase 1A 是 after-stop 中文总结。
- Phase 1B 是 after-stop 中文阅读稿。
- Phase 2A 是动态中文阅读稿 sidecar，默认关闭，后置。
- Phase 2B 是应用内 Markdown / HTML 渲染，后置。
- `raw.txt`、`clean.txt`、`session.log`、`config.json` 是不可变 evidence layer。
- LLM 失败不得影响 Start/Stop、麦克风释放、UI 主线程或原 session 文件。

完成信号：

- 设计文档中已明确 Phase 1A / 1B / 2A / 2B。
- 文档已明确 Phase 1A/1B 不包含动态 sidecar。
- 文档已明确所有 LLM 任务失败不影响 raw/clean/session/config。

---

### Step 2：更新设计文档

状态：已完成。

已同步的设计文档包括：

```text
docs/LLM_POSTPROCESSING_DESIGN.md
docs/goalForNextLevel.md
docs/user_understand.md
docs/工程细节.md
docs/LLMsteps.md
README.md
```

完成内容：

- 固定 LLM sidecar 架构边界；
- 明确 DeepSeek API key 第一版只从 `DEEPSEEK_API_KEY` 读取；
- 明确 Markdown / HTML 是派生视图，state JSON 是真实状态源；
- 明确 UI 和动态 sidecar 后置；
- 明确当前执行顺序为 Step 1 到 Step 18。

---

### Step 3：创建独立 `llm/` 模块骨架

状态：已完成，已 commit 并 push。

提交：

```text
commit: ebc95b6
message: Add LLM sidecar design and isolated module skeleton
branch: llm-sidecar-phase1
remote: origin/llm-sidecar-phase1
```

新增骨架：

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

Step 3 验证结果：

```text
import smoke test：PASS
compileall：PASS
testCodes/test_ui_support.py：PASS
testCodes/test_backends.py --skip-faster-smoke：PASS
ASR 主链路文件：无修改
真实网络/API：未实现
API key：未写入
__pycache__：已清理
```

当前分支已设置 upstream：

```text
llm-sidecar-phase1 -> origin/llm-sidecar-phase1
```

---

### Step 4：实现 transcript parser / chunker

状态：已完成，已 commit 并 push。

提交：

```text
commit: 920b0bb
message: Implement LLM transcript parser and chunker version1
branch: llm-sidecar-phase1
remote: origin/llm-sidecar-phase1
```

修改文件：

```text
llm/transcript_chunker.py
testCodes/test_llm_chunker.py
docs/whisper_runtime.md
```

完成内容：

- `parse_clean_transcript(text)` 解析标准 clean timestamp 行；
- 支持整数或小数秒，例如 `[1s -> 2s]`、`[1.0s -> 2.50s]`；
- 支持 no timestamp fallback；
- 支持 malformed timestamp fallback；
- 跳过空行；
- 保留 0-based `source_line`；
- `chunk_transcript(lines, max_chars, max_seconds)` 按输入顺序 deterministic 切块；
- 支持稳定 `chunk-0001` 格式 chunk id；
- 支持 `max_chars` 和 `max_seconds`；
- 单行超出 `max_chars` 时保留为单独 chunk，不拆分原文；
- `TranscriptChunk` 保留 source lines，并提供只读 `text` / `source_lines` convenience properties。

Step 4 验证结果：

```text
testCodes/test_llm_chunker.py：PASS，14 项 focused tests
compileall llm + testCodes/test_llm_chunker.py：PASS
testCodes/test_ui_support.py：PASS
testCodes/test_backends.py --skip-faster-smoke：PASS，whisper.cpp CLI 未配置时 SKIP
git diff --check：PASS
network/API grep：无实际网络/API 实现；仅既有 DeepSeek 骨架注释命中 "network requests"
API key grep：无输出
ASR 主链路文件：无修改
provider/API/UI/writer/renderer/sidecar：未接入
```

Step 4 version1 已验收通过。Step 4 后续两个 hardening 小点已并入 Step 5 完成。

---

### Step 5：实现 provider interface、mock provider，并完成 Step 4 parser/chunker hardening

状态：已完成，已 commit 并 push。

提交：

```text
commit: 00e2d1c
message: Implement LLM provider interface and mock provider
branch: llm-sidecar-phase1
remote: origin/llm-sidecar-phase1
```

修改文件：

```text
llm/provider_base.py
llm/mock_provider.py
llm/deepseek_provider.py
llm/transcript_chunker.py
testCodes/test_llm_provider_mock.py
testCodes/test_llm_chunker.py
```

完成内容：

- 保留并完善 `LLMProvider` Protocol：`provider_id`、`generate_text(...)`、`generate_json(...)`；
- 增加 typed provider errors：
  - `LLMConfigurationError`；
  - `MissingAPIKeyError`；
  - `LLMAuthenticationError`；
  - `LLMRateLimitError`；
  - `LLMTimeoutError`；
  - `LLMMalformedResponseError`；
  - `LLMInvalidResponseError`；
  - `LLMSchemaError`；
- 保留旧 error class 兼容别名/继承关系；
- 新增 deterministic `MockProvider`；
- mock provider 支持 text / JSON success；
- mock provider 支持 error injection：`missing_api_key`、`authentication`、`rate_limit`、`timeout`、`provider_error`、`invalid_json`、`schema_error`；
- mock provider 不读取 `DEEPSEEK_API_KEY`，不访问网络，不写文件，不写 request / response log；
- `DeepSeekProvider` 仍保持 placeholder，不实现 HTTP，不读取 API key；
- `TranscriptLine` 增加 `raw_line: str | None = None`；
- timestamp、no timestamp fallback、malformed fallback 都保存完整 `raw_line`；
- 单行 `end < start` timestamp 作为 text-only fallback，不抛异常。

Step 5 验证结果：

```text
testCodes/test_llm_provider_mock.py：PASS，9 项 focused tests
testCodes/test_llm_chunker.py：PASS，16 项 focused tests
compileall llm + Step 5 tests：PASS
testCodes/test_ui_support.py：PASS
testCodes/test_backends.py --skip-faster-smoke：PASS，whisper.cpp CLI 未配置时 SKIP
git diff --check：PASS
network/API grep：无输出
API key grep：无输出
ASR 主链路文件：无修改
docs 文件：无修改
真实 API / UI / writer / renderer / sidecar：未接入
merge：未执行
```

审查结论：Step 5 通过，不需要 Step 5 v2。

---

## 3. ACTIVE：Step 6 - 实现 output writer、state schema、renderer

状态：ACTIVE。

### 3.1 目标

实现 LLM sidecar 的输出层基础设施：

```text
output writer
state schema
renderer
```

Step 6 的目标是让后续 Phase 1A / Phase 1B pipeline 能安全、deterministic 地写入 `session_dir/llm/` 下的派生文件，并能从结构化 state 渲染 Markdown / HTML。

Step 6 不调用 provider，不实现 summary pipeline，不实现 readable transcript pipeline，不实现 CLI，不接真实 API，不接 UI，不做 Phase 2A rolling sidecar。

---

### 3.2 允许修改范围

原则上允许：

```text
llm/output_writer.py
llm/state_schema.py
llm/renderer.py
testCodes/test_llm_outputs.py
```

如需引用已完成模块，允许只读使用：

```text
llm/provider_base.py
llm/mock_provider.py
llm/transcript_chunker.py
```

如果确有必要导出 writer/schema/renderer symbols，可以最小修改：

```text
llm/__init__.py
```

但必须说明理由。

Codex 默认不得修改：

```text
docs/whisper_runtime.md
docs/whisper_static.md
README.md
```

Step 6 完成后，由人工审查后再受控更新 runtime。

---

### 3.3 禁止修改范围

不要修改 ASR 主链路文件：

```text
ui_app.py
transcription_engine.py
transcription_controller.py
transcript_store.py
stream_transcribe.py
settings.py
model_manager.py
resource_paths.py
```

不要修改 ASR 主链路行为：

```text
audio capture
ring buffer
chunk scheduling
resample
WhisperCppBackend
simple_dedup()
fuzzy_boundary_dedup()
TranscriptStore raw / clean 写入逻辑
Start / Stop
麦克风释放
UI 主线程
```

不要实现：

```text
真实 DeepSeek HTTP
真实 OpenAI-compatible HTTP
summary pipeline
readable transcript pipeline
prompt construction
CLI
UI
Phase 2A sidecar
request / response log
API key settings / Keychain
```

不要修改 evidence layer：

```text
raw.txt
clean.txt
session.log
config.json
```

---

### 3.4 Step 6 实现要求

#### 3.4.1 Output writer

完善 `llm/output_writer.py`。

应提供安全写入 `session_dir/llm/` 派生文件的能力。

建议能力：

```text
ensure_llm_dir(session_dir)
atomic_write_text(path, text)
atomic_write_json(path, data)
append_error_log(path, category, message, details=None)
write_phase1a_outputs(...)
write_phase1b_outputs(...)
```

命名可按现有骨架调整，但必须满足：

- 只写 `session_dir/llm/` 下文件；
- 不修改 `raw.txt`、`clean.txt`、`session.log`、`config.json`；
- JSON / Markdown / HTML 使用 atomic write 或等价的 temp file + replace；
- error log 只写 sanitized diagnostics；
- 不写 API key、Authorization header、完整 raw request body 或完整 raw response body；
- 如果 `llm/` 已存在，不得删除整个目录；只替换本步骤负责的目标文件。

#### 3.4.2 State schema

完善 `llm/state_schema.py`。

目标是定义 Phase 1A / Phase 1B 的最小结构化 schema 和 validation helper，供后续 pipeline 使用。

建议包括：

```text
SummaryState / SummaryDocument
SectionSummary
KeyTerm
ActionItem
UnclearPart
ReadableTranscriptState
ReadableSegment
Annotation
Review/renderer view helpers
validate_summary_state(...)
validate_readable_state(...)
```

要求：

- 使用 dataclass 或简单 dict validation 均可；
- schema_version 必须存在；
- source 必须记录 transcript = clean.txt、raw_used = false；
- readable state 中必须有 revision 和 segments；
- segment 至少包含 `segment_id`、`start`、`end`、`source_text`、`text_zh`、`annotations`、`evidence`、`status`；
- status 只允许合理枚举，例如 `editable` / `frozen`；
- validation failure 应抛 typed error，例如 `LLMSchemaError` 或项目内 schema error。

#### 3.4.3 Renderer

完善 `llm/renderer.py`。

目标：从结构化 state 本地渲染 Markdown / HTML。

必须实现或预留：

```text
render_summary_markdown(summary_state)
render_readable_markdown(readable_state)
render_review_markdown(readable_state)
render_markdown_to_html(markdown_text)
```

要求：

- renderer deterministic；
- Markdown / HTML 是派生视图，不是真实状态源；
- HTML 必须 escape 用户/transcript 文本，避免原文里的 `<script>` 或 HTML tag 被当作真实 HTML；
- 支持 Phase 1B annotation semantics：
  - suspected duplicate / deletion -> `~~text~~`；
  - term / uncertain translation -> `*text*`；
  - suspicious -> `**[可疑] text**`；
  - high-risk suspicious -> `<u><strong>[高风险可疑] text</strong></u>`；
- 不引入 Typora、外部浏览器或 `QWebEngineView`；
- 不依赖 Qt。

#### 3.4.4 Error handling and secret safety

Step 6 不读取 API key。测试中可使用假 secret 字符串验证：

- fake API key 不出现在 Markdown；
- fake API key 不出现在 HTML；
- fake API key 不出现在 JSON state；
- fake API key 不出现在 error log。

如果 error details 包含疑似 secret，应做最小 redaction。

---

### 3.5 建议测试文件

新增：

```text
testCodes/test_llm_outputs.py
```

测试必须可直接运行：

```bash
venv/bin/python testCodes/test_llm_outputs.py
```

运行，不依赖 pytest。

建议 PASS 输出：

```text
PASS: llm output directory created
PASS: atomic text write
PASS: atomic json write
PASS: summary json outputs written
PASS: summary markdown rendered
PASS: readable state written
PASS: readable markdown rendered
PASS: readable html rendered
PASS: review markdown rendered
PASS: review html rendered
PASS: html escaping
PASS: annotation rendering
PASS: renderer deterministic
PASS: raw clean session config unchanged
PASS: api key not written
PASS: renderer failure preserves previous valid output
```

至少覆盖：

- `session_dir/llm/` 创建；
- atomic text/json write；
- Phase 1A `summary.md`、`summary.json`、`sections.json`、`key_terms.json`、`action_items.json` 写入；
- Phase 1B `readable_zh_final_state.json`、`readable_zh_final.md`、`readable_zh_final.html`、`review_zh_final.md`、`review_zh_final.html` 写入；
- Markdown renderer deterministic；
- HTML escaping；
- annotation rendering；
- schema validation failure；
- renderer failure 保留上一版有效输出；
- fake API key 不出现在任何输出或 error log；
- `raw.txt`、`clean.txt`、`session.log`、`config.json` 内容前后一致；
- 不生成 live sidecar 文件。

---

### 3.6 验收命令

运行目录：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
```

虚拟环境：

```bash
source venv/bin/activate
```

基础检查：

```bash
git branch --show-current
git status --short --untracked-files=all
git pull
git log --oneline --decorate -5
```

预期当前分支：

```text
llm-sidecar-phase1
```

Step 6 focused test：

```bash
venv/bin/python testCodes/test_llm_outputs.py
```

预期：所有 Step 6 focused tests PASS。

语法检查：

```bash
venv/bin/python -m compileall -q llm testCodes/test_llm_outputs.py
```

预期：无输出，退出码为 0。

LLM 已有回归：

```bash
venv/bin/python testCodes/test_llm_chunker.py
venv/bin/python testCodes/test_llm_provider_mock.py
```

预期：全部 PASS。

原有 ASR/UI 回归：

```bash
venv/bin/python testCodes/test_ui_support.py
venv/bin/python testCodes/test_backends.py --skip-faster-smoke
```

预期：无新增 FAIL。`whisper.cpp availability` 在 CLI 未配置时可 SKIP。

修改范围检查：

```bash
git diff --name-only
git status --short --untracked-files=all
git diff --check
```

理想涉及：

```text
llm/output_writer.py
llm/state_schema.py
llm/renderer.py
testCodes/test_llm_outputs.py
```

可能允许：

```text
llm/__init__.py
```

不允许出现：

```text
docs/whisper_runtime.md
docs/whisper_static.md
README.md
ui_app.py
transcription_engine.py
transcription_controller.py
transcript_store.py
stream_transcribe.py
settings.py
model_manager.py
resource_paths.py
```

网络/API 检查：

```bash
grep -RInE 'requests|httpx|aiohttp|urllib|urlopen|socket|Authorization|Bearer |chat\.completions|client\.chat|api\.deepseek|https?://' llm testCodes/test_llm_outputs.py || true
```

预期：无实际网络/API 实现。若只命中注释或 placeholder 文本，必须说明。

API key 检查：

```bash
grep -RInE 'sk-[A-Za-z0-9_-]{16,}' llm testCodes/test_llm_outputs.py || true
```

预期：无输出。

Evidence unchanged 检查应由 `testCodes/test_llm_outputs.py` 自动覆盖。

---

### 3.7 Step 6 完成标准

全部满足才可标记 Step 6 已完成：

```text
output_writer 只写 session_dir/llm/
output_writer 不修改 raw.txt / clean.txt / session.log / config.json
JSON / Markdown / HTML 写入具备 atomic replace 或等价保护
error log sanitized，不写 API key / Authorization / raw request / raw response
state_schema 定义 Phase 1A 最小 summary schema
state_schema 定义 Phase 1B readable transcript state schema
schema validation failure 抛 typed schema error
renderer 从 state 渲染 Markdown / HTML
renderer deterministic
renderer HTML escaping PASS
annotation rendering PASS
fake API key 不出现在任何输出或 error log
testCodes/test_llm_outputs.py PASS
compileall PASS
testCodes/test_llm_chunker.py PASS
testCodes/test_llm_provider_mock.py PASS
原有 baseline tests 无新增 FAIL
ASR 主链路无修改
未接真实 API / UI / pipeline / CLI / Phase 2A sidecar
docs/whisper_runtime.md 未由 Codex 修改
```

---

### 3.8 风险

重点防止：

- output writer 写到 `session_dir` 根目录并误改 evidence layer；
- writer 为了清理旧输出删除整个 `llm/` 目录；
- 非 atomic 写导致失败时留下半截 JSON/HTML；
- error log 记录 API key、Authorization header、完整 raw request/response；
- Markdown 被当成真实状态源；
- LLM 直接自由生成并覆盖整个 Markdown / HTML；
- renderer 没有 HTML escaping；
- 提前接 summary pipeline、provider、CLI、UI 或 Phase 2A sidecar；
- 修改 ASR 主链路；
- Codex 提前改 runtime。

---

### 3.9 回滚

如果 Step 6 实现方向错误，先看 diff：

```bash
git diff -- llm/output_writer.py llm/state_schema.py llm/renderer.py testCodes/test_llm_outputs.py llm/__init__.py
```

只回滚本步骤相关文件：

```bash
git restore llm/output_writer.py llm/state_schema.py llm/renderer.py llm/__init__.py
rm -f testCodes/test_llm_outputs.py
```

不要使用：

```bash
git reset --hard
git clean -fd
```

除非用户明确确认当前工作区可以全部丢弃。

---

## 4. 后续步骤简要内容

### Step 7：实现 Phase 1A after-stop summary mock pipeline

目标：

- 用 mock provider 跑通 `clean.txt -> chunk -> section summary -> global summary -> outputs`；
- 不接真实 API；
- 不接 UI；
- 支持失败隔离。

验收：

```bash
venv/bin/python testCodes/test_llm_provider_mock.py
venv/bin/python testCodes/test_llm_pipeline.py
```

---

### Step 8：实现 Phase 1B after-stop readable transcript mock pipeline

目标：

- 用 mock provider 生成 readable transcript state；
- 本地 renderer 生成 readable/review Markdown 和 HTML；
- 不做 rolling sidecar。

验收：

```bash
venv/bin/python testCodes/test_llm_pipeline.py
venv/bin/python testCodes/test_llm_outputs.py
```

---

### Step 9：新增 CLI 入口并用 mock 跑通

目标：

- 新增 CLI；
- mock provider 模式下可对 existing completed session 运行；
- 不要求 API key；
- 不接 UI。

建议命令形态：

```bash
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock
```

---

### Step 10：补齐 mock tests、error injection、secret leakage tests

目标：

- failure isolation；
- malformed response；
- schema validation failure；
- renderer failure；
- API key leakage scan；
- raw/clean/session/config unchanged。

---

### Step 11：实现 DeepSeek / OpenAI-compatible provider

目标：

- 从 `DEEPSEEK_API_KEY` 读取 key；
- model / endpoint 可配置；
- typed provider errors；
- 测试用 monkeypatch/mock HTTP client；
- 自动测试不真实调用 API。

---

### Step 12：本地手动真实 API smoke test

目标：

- mock tests 全部通过后，用 disposable session 手动测试真实 API；
- 不打印 key；
- 不保存 key；
- 扫描 repo/session/log。

---

### Step 13：验证 Phase 1A / 1B 真实课堂 session 输出质量

目标：

- 人工检查 1-2 节真实课堂 session；
- 检查 hallucination、timestamp grounding、action items、unclear parts。

---

### Step 14：实现 Phase 2A rolling sidecar

目标：

- 默认关闭；
- 只读 clean snapshot；
- single in-flight request；
- pending snapshot coalescing；
- frozen/editable window；
- atomic replace；
- 不进入 ASR 主链路。

---

### Step 15：验证 single worker、coalescing、atomic replace、final reconciliation

目标：

- 验证 Phase 2A 不形成 backlog；
- Stop 后 final reconciliation；
- 失败保留上一版有效输出。

---

### Step 16：实现 Phase 2B 应用内 QTextBrowser 预览

目标：

- 最小 UI 预览；
- `QTextBrowser.setHtml()`；
- 不引入 `QWebEngineView`；
- sidecar worker 不直接操作 Qt widget。

---

### Step 17：长时间课堂稳定性测试

目标：

- 验证 ASR 主链路、LLM 后处理、sidecar、UI preview 在真实课堂长度下稳定；
- 检查 Stop drain、queue backlog、麦克风释放、UI 稳定性。

---

### Step 18：确认稳定后再考虑默认开关策略

目标：

- 汇总质量和稳定性结果；
- 决定 LLM 功能默认关闭、默认开启或按 provider/API key 状态启用。

---

## 5. 每步完成后的 runtime 更新模板

完成任一 Step 后，按以下方式更新本文件：

```text
1. 在“已完成步骤记录”中追加该 Step 的完成记录。
2. 将当前 ACTIVE Step 状态改为：已完成。
3. 新增或激活下一 Step 为唯一 ACTIVE。
4. 把下一 Step 写到可照搬执行的粒度：
   - 目标
   - 允许修改范围
   - 禁止修改范围
   - 实现要求
   - 测试命令
   - 预期输出
   - 风险
   - 回滚
5. 保留更早完成内容，不删除。
6. 如果方向发生变化，先更新 docs/whisper_static.md。
```

---

## 6. 提交与推送规则

每个明确 checkpoint 完成后建议提交：

```bash
git status --short --untracked-files=all
git diff --check
git diff --name-only
```

确认没有模型、outputs、日志、API key、venv、build、dist 被 staged。

推荐提交节奏：

```text
一个 Step 一个 commit
文档同步通常在人工审查后单独提交，除非用户明确允许 Codex 修改 runtime
```

当前下一次合理 commit：

```text
Implement LLM output writer and renderer
```

push：

```bash
git push
```
