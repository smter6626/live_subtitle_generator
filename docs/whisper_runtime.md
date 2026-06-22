# whisper_runtime.md

最后更新：2026-06-22  
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
当前 checkpoint：Step 6 已完成并已 push
唯一 ACTIVE 任务：Step 7 - 实现 Phase 1A after-stop summary mock pipeline
```

已完成：

```text
Step 1：冻结需求和架构边界
Step 2：更新设计文档
Step 3：创建独立 llm/ 模块骨架
Step 4：实现 transcript parser / chunker version1
Step 5：实现 provider interface、mock provider，并完成 Step 4 parser/chunker hardening
Step 6：实现 output writer、state schema、renderer
```

当前尚未实现：

```text
Phase 1A summary pipeline
Phase 1B readable transcript pipeline
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
output writer
state schema
renderer
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
- 增加 typed provider errors：`LLMConfigurationError`、`MissingAPIKeyError`、`LLMAuthenticationError`、`LLMRateLimitError`、`LLMTimeoutError`、`LLMMalformedResponseError`、`LLMInvalidResponseError`、`LLMSchemaError`；
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

### Step 6：实现 output writer、state schema、renderer

状态：已完成，已 commit 并 push。

提交：

```text
commit: 7d20e6c
message: Implement LLM output writer and renderer
branch: llm-sidecar-phase1
remote: origin/llm-sidecar-phase1
```

修改文件：

```text
llm/output_writer.py
llm/state_schema.py
llm/renderer.py
testCodes/test_llm_outputs.py
```

完成内容：

- `ensure_llm_dir(session_dir)` 创建并返回标准 `session_dir/llm/` 输出路径；
- `atomic_write_text()` / `atomic_write_json()` 使用 temp file + flush/fsync + `os.replace()`；
- 写入路径必须位于 `session_dir/llm/` 下，否则抛 `ValueError`；
- `append_error_log()` 只追加 sanitized diagnostics；
- `write_phase1a_outputs()` 写 `summary.md`、`summary.json`、`sections.json`、`key_terms.json`、`action_items.json`；
- `write_phase1b_outputs()` 写 `readable_zh_final_state.json`、readable/review Markdown/HTML；
- Phase 1A schema 包含 `SummaryState`、`SectionSummary`、`KeyTerm`、`ActionItem`、`UnclearPart`、`SourceInfo`；
- Phase 1B schema 包含 `ReadableTranscriptState`、`ReadableSegment`、`SegmentAnnotation`；
- 控制枚举包含 `SegmentStatus`、`AnnotationType`；
- `validate_summary_state()` / `validate_readable_state()` 失败时抛 `LLMSchemaError`；
- `state_to_dict()` 生成 JSON-compatible state；
- renderer 支持 `render_summary_markdown()`、`render_readable_markdown()`、`render_review_markdown()`、`render_markdown_to_html()`；
- renderer deterministic，无 Qt / Typora / browser / QWebEngineView 依赖；
- HTML escaping 覆盖 transcript/source/user text；
- annotation semantics 覆盖 duplicate/deletion、term/uncertain translation、suspicious、high-risk suspicious；
- JSON / Markdown / HTML 使用 atomic replace；
- fake secret 不出现在 Markdown、HTML、JSON state、error log；
- `raw.txt` / `clean.txt` / `session.log` / `config.json` 保持不变。

Step 6 验证结果：

```text
testCodes/test_llm_outputs.py：PASS，19 项 focused tests
compileall llm + testCodes/test_llm_outputs.py：PASS
testCodes/test_llm_chunker.py：PASS
testCodes/test_llm_provider_mock.py：PASS
testCodes/test_ui_support.py：PASS
testCodes/test_backends.py --skip-faster-smoke：PASS，whisper.cpp CLI 未配置时 SKIP
git diff --check：PASS
network/API grep：无输出
API key grep：无输出
ASR 主链路文件：无修改
docs 文件：无修改
真实 API / UI / pipeline / CLI / Phase 2A sidecar：未接入
merge：未执行
```

审查结论：Step 6 通过，不需要 Step 6 v2。

#### Step 6 非阻塞问题点

以下问题不阻塞 Step 7，但后续可作为 polish / hardening 记录：

1. `sanitize_text()` 当前会 redaction 所有输出文本中的 secret-like pattern。安全性较强，但可能过度保守：如果课堂 transcript 或 LLM 输出中自然出现类似 `sk-...` 的普通文本，也会被替换为 `[REDACTED]`。后续可评估是否只对 error log、provider diagnostics 或明确 secret fields 做更精细 redaction。
2. renderer 当前可能产生双重 HTML escaping，例如 `<script>` 在 Markdown 阶段已转义后，HTML 阶段再次转义为 `&amp;lt;script&amp;gt;`。这对安全可接受，但显示效果可能偏保守。后续 Phase 1B 视图 polish 时，可评估将 escaping 统一收敛到 HTML 渲染阶段，确保安全同时减少双重 escape。

---

## 3. ACTIVE：Step 7 - 实现 Phase 1A after-stop summary mock pipeline

状态：ACTIVE。

### 3.1 目标

实现 Phase 1A after-stop 中文总结的 mock pipeline。

本步骤只使用 mock provider，目标是跑通：

```text
completed session_dir/clean.txt
-> parse_clean_transcript
-> chunk_transcript
-> prompt payload construction
-> MockProvider.generate_json / generate_text
-> state_schema validation
-> renderer
-> output_writer
-> session_dir/llm/summary.md
-> session_dir/llm/summary.json
-> session_dir/llm/sections.json
-> session_dir/llm/key_terms.json
-> session_dir/llm/action_items.json
```

Step 7 不接真实 DeepSeek HTTP，不要求 `DEEPSEEK_API_KEY`，不实现 CLI，不接 UI，不做 Phase 1B readable transcript pipeline，不做 Phase 2A rolling sidecar。

---

### 3.2 允许修改范围

原则上允许：

```text
llm/summary_pipeline.py
llm/prompt_templates.py
testCodes/test_llm_pipeline.py
```

允许只读使用已完成模块：

```text
llm/transcript_chunker.py
llm/provider_base.py
llm/mock_provider.py
llm/state_schema.py
llm/renderer.py
llm/output_writer.py
```

如需新增小型 helper module，必须只服务 Step 7，并在最终汇报中说明理由。

如果确有必要导出 pipeline/prompt symbols，可以最小修改：

```text
llm/__init__.py
```

Codex 默认不得修改：

```text
docs/whisper_runtime.md
docs/whisper_static.md
README.md
```

Step 7 完成后，由人工审查后再受控更新 runtime。

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
CLI
UI
Phase 1B readable transcript pipeline
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

不要生成 Phase 1B / Phase 2A 输出：

```text
readable_zh_final_state.json
readable_zh_final.md
readable_zh_final.html
review_zh_final.md
review_zh_final.html
live_readable_zh_state.json
live_readable_zh_revisions.jsonl
live_readable_zh.md
live_readable_zh.html
live_review_zh.md
live_review_zh.html
```

---

### 3.4 Step 7 实现要求

#### 3.4.1 Summary pipeline

完善 `llm/summary_pipeline.py`。

建议能力：

```text
run_summary_pipeline(session_dir, provider, output_language="zh", ...)
read clean.txt
parse and chunk transcript
build section prompt payloads
call provider for section summaries
combine section summaries into SummaryState
render summary Markdown
write Phase 1A outputs
return result/status object
```

命名可按现有骨架调整，但必须满足：

- 输入是 completed `session_dir`；
- 必须读取 `session_dir/clean.txt`；
- 不读取 raw.txt 作为 Phase 1A 输入；
- 可只读读取 `config.json` 或 session metadata，但不得修改；
- 空 transcript 要有可预测行为：成功生成空 summary，或返回清晰 failure；
- provider error / schema error / malformed response 要被隔离，写 sanitized `llm_errors.log`；
- pipeline failure 不修改 evidence layer；
- 不要求 API key；
- 不真实调用 API；
- 不生成 request/response log。

#### 3.4.2 Prompt templates

完善 `llm/prompt_templates.py`。

至少应提供 Phase 1A prompt builder 或 prompt payload builder。

Prompt / payload 必须包含或表达以下约束：

```text
中文输出
不要编造 transcript 外信息
保留 timestamp grounding
区分 transcript 明确证据和模型推断
不确定内容标记 unclear
ASR 修正只能作为 possible correction
不得覆盖 clean.txt
输出结构化 JSON 或可验证结构
```

Step 7 不要求真实 prompt 质量完美，但应为后续真实 provider 做出稳定接口。

#### 3.4.3 Mock provider integration

只使用 `MockProvider` 或自定义测试 provider。

允许 mock provider 返回固定 section summary / global summary 数据；不要求真实 LLM 质量。

如果需要测试 malformed response / schema failure，可通过 mock provider mode 或测试内 fake provider 注入 typed error。

#### 3.4.4 Output behavior

成功时只写 Phase 1A 输出：

```text
session_dir/llm/summary.md
session_dir/llm/summary.json
session_dir/llm/sections.json
session_dir/llm/key_terms.json
session_dir/llm/action_items.json
```

失败或 recoverable warning 时可写：

```text
session_dir/llm/llm_errors.log
```

不得修改：

```text
raw.txt
clean.txt
session.log
config.json
```

---

### 3.5 建议测试文件

新增：

```text
testCodes/test_llm_pipeline.py
```

测试必须可直接运行：

```bash
venv/bin/python testCodes/test_llm_pipeline.py
```

运行，不依赖 pytest。

建议 PASS 输出：

```text
PASS: summary pipeline reads clean transcript
PASS: summary pipeline writes summary outputs
PASS: prompt includes chinese output instruction
PASS: prompt includes timestamp grounding instruction
PASS: prompt includes no hallucination instruction
PASS: mock provider success path
PASS: provider failure isolated
PASS: schema failure isolated
PASS: raw clean session config unchanged
PASS: api key not written
PASS: no phase1b outputs
PASS: no live sidecar outputs
```

至少覆盖：

- completed temp session 中读取 `clean.txt`；
- parse/chunk/prompt/provider/write 成功路径；
- 输出 `summary.md`、`summary.json`、`sections.json`、`key_terms.json`、`action_items.json`；
- prompt/payload 包含中文输出、timestamp grounding、不编造、unclear / possible correction 等约束；
- provider error / timeout / malformed response 或 schema failure 被隔离，并写 sanitized `llm_errors.log`；
- fake API key 不出现在任何输出或 error log；
- `raw.txt`、`clean.txt`、`session.log`、`config.json` 内容前后一致；
- 不生成 Phase 1B readable outputs；
- 不生成 Phase 2A live sidecar outputs；
- 不调用真实网络/API。

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

Step 7 focused test：

```bash
venv/bin/python testCodes/test_llm_pipeline.py
```

预期：所有 Step 7 focused tests PASS。

语法检查：

```bash
venv/bin/python -m compileall -q llm testCodes/test_llm_pipeline.py
```

预期：无输出，退出码为 0。

LLM 已有回归：

```bash
venv/bin/python testCodes/test_llm_chunker.py
venv/bin/python testCodes/test_llm_provider_mock.py
venv/bin/python testCodes/test_llm_outputs.py
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
llm/summary_pipeline.py
llm/prompt_templates.py
testCodes/test_llm_pipeline.py
```

可能允许：

```text
llm/__init__.py
llm/ 内新增 Step 7 专用小型 helper module
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
grep -RInE 'requests|httpx|aiohttp|urllib|urlopen|socket|Authorization|Bearer |chat\.completions|client\.chat|api\.deepseek|https?://' llm testCodes/test_llm_pipeline.py || true
```

预期：无实际网络/API 实现。若只命中注释、prompt 文本、测试 fake secret 或 placeholder 文本，必须说明。

API key 检查：

```bash
grep -RInE 'sk-[A-Za-z0-9_-]{16,}' llm testCodes/test_llm_pipeline.py || true
```

预期：无真实 key。若测试中故意使用 fake key pattern，必须说明它是测试字符串，并确保不会写入输出。

---

### 3.7 Step 7 完成标准

全部满足才可标记 Step 7 已完成：

```text
summary pipeline 可读取 completed session_dir/clean.txt
summary pipeline 使用 parser/chunker
prompt payload builder 包含中文输出、timestamp grounding、不编造、unclear/possible correction 约束
mock provider success path 可生成 Phase 1A outputs
summary.md / summary.json / sections.json / key_terms.json / action_items.json 写入 session_dir/llm/
provider/schema failure 被隔离并写 sanitized llm_errors.log
raw.txt / clean.txt / session.log / config.json unchanged
fake API key 不出现在任何输出或 error log
testCodes/test_llm_pipeline.py PASS
compileall PASS
testCodes/test_llm_chunker.py PASS
testCodes/test_llm_provider_mock.py PASS
testCodes/test_llm_outputs.py PASS
原有 baseline tests 无新增 FAIL
ASR 主链路无修改
未接真实 API / UI / CLI / Phase 1B / Phase 2A sidecar
docs/whisper_runtime.md 未由 Codex 修改
```

---

### 3.8 风险

重点防止：

- pipeline 读取或修改 raw.txt；
- pipeline 修改 clean.txt / session.log / config.json；
- 失败时删除已有 transcript 或 session 文件；
- prompt 中缺少 no hallucination / timestamp grounding / Chinese output 约束；
- 把 mock pipeline 写成真实 API 调用；
- 生成 request/response log；
- 提前实现 CLI / UI / Phase 1B / Phase 2A；
- 把 Markdown 当真实状态源；
- Codex 提前改 runtime。

---

### 3.9 回滚

如果 Step 7 实现方向错误，先看 diff：

```bash
git diff -- llm/summary_pipeline.py llm/prompt_templates.py testCodes/test_llm_pipeline.py llm/__init__.py
```

只回滚本步骤相关文件：

```bash
git restore llm/summary_pipeline.py llm/prompt_templates.py llm/__init__.py
rm -f testCodes/test_llm_pipeline.py
```

如果新增了 `llm/` 内 Step 7 helper module，并且确认它只属于 Step 7，也一并删除。

不要使用：

```bash
git reset --hard
git clean -fd
```

除非用户明确确认当前工作区可以全部丢弃。

---

## 4. 后续步骤简要内容

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
Implement Phase 1A summary mock pipeline
```

push：

```bash
git push
```
