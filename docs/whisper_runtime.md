# whisper_runtime.md

最后更新：2026-06-22  
文档角色：动态执行状态（runtime state）

本文件用于记录 Classroom Live Transcriber / whisper 项目的已执行步骤、唯一 ACTIVE 任务、当前任务的可执行说明、后续步骤摘要。长期合同见 `docs/whisper_static.md`。

---

## 0. 使用规则

### 0.1 更新规则

每完成一个开发步骤后更新本文件：

1. 将刚完成的 ACTIVE step 标记为已完成；
2. 在已完成步骤记录中追加结果、验证命令和结论；
3. 激活下一步，保证全文件只有一个 ACTIVE；
4. 将下一步细化到可以直接交给 Codex 或人工照搬执行；
5. 不删除历史完成记录。

### 0.2 Codex 与 runtime

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
当前 checkpoint：Step 9 已完成并已 push
唯一 ACTIVE 任务：Step 10 - 补齐 mock tests、failure isolation、secret leakage tests 与 hardening
```

已完成：

```text
Step 1：冻结需求和架构边界
Step 2：更新设计文档
Step 3：创建独立 llm/ 模块骨架
Step 4：实现 transcript parser / chunker version1
Step 5：实现 provider interface、mock provider，并完成 Step 4 parser/chunker hardening
Step 6：实现 output writer、state schema、renderer
Step 7：实现 Phase 1A after-stop summary mock pipeline
Step 8：实现 Phase 1B after-stop readable transcript mock pipeline
Step 9：新增 CLI 入口并用 mock 跑通 Phase 1A / Phase 1B
```

当前尚未实现：

```text
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
Phase 1A summary mock pipeline
Phase 1B readable transcript mock pipeline
mock CLI entrypoint
```

---

## 2. 已完成步骤记录

### Step 1：冻结需求和架构边界

状态：已完成。

核心结论：LLM 是 DeepSeek / OpenAI-compatible 后处理模块，不是实时 ASR 主链路的一部分；Phase 1A 是 after-stop 中文总结；Phase 1B 是 after-stop 中文阅读稿；Phase 2A 是动态中文阅读稿 sidecar，默认关闭，后置；Phase 2B 是应用内 Markdown / HTML 渲染，后置；`raw.txt`、`clean.txt`、`session.log`、`config.json` 是不可变 evidence layer；LLM 失败不得影响 Start/Stop、麦克风释放、UI 主线程或原 session 文件。

---

### Step 2：更新设计文档

状态：已完成。

完成内容：固定 LLM sidecar 架构边界；明确 API key、Markdown/HTML 派生视图、UI 和动态 sidecar 后置；明确当前执行顺序为 Step 1 到 Step 18。

---

### Step 3：创建独立 `llm/` 模块骨架

状态：已完成，已 commit 并 push。

```text
commit: ebc95b6
message: Add LLM sidecar design and isolated module skeleton
```

验证结果：import smoke test PASS；compileall PASS；`test_ui_support.py` PASS；`test_backends.py --skip-faster-smoke` PASS/SKIP；ASR 主链路无修改；真实网络/API 未实现；API key 未写入。

---

### Step 4：实现 transcript parser / chunker

状态：已完成，已 commit 并 push。

```text
commit: 920b0bb
message: Implement LLM transcript parser and chunker version1
```

完成内容：`parse_clean_transcript(text)`；timestamp/no timestamp/malformed fallback；0-based `source_line`；`chunk_transcript(lines, max_chars, max_seconds)` deterministic 切块；稳定 `chunk-0001` id；单行超长不拆分原文。

验证结果：`test_llm_chunker.py` PASS；compileall PASS；原有 UI/backend 回归无新增 FAIL；ASR 主链路无修改；provider/API/UI/writer/renderer/sidecar 未接入。

---

### Step 5：实现 provider interface、mock provider，并完成 Step 4 parser/chunker hardening

状态：已完成，已 commit 并 push。

```text
commit: 00e2d1c
message: Implement LLM provider interface and mock provider
```

完成内容：`LLMProvider` Protocol；typed provider errors；deterministic `MockProvider`；mock provider 支持 text/JSON success 和 error injection；不读取 `DEEPSEEK_API_KEY`；不访问网络；不写 request/response log；`DeepSeekProvider` 保持 placeholder；`TranscriptLine.raw_line`；`end < start` fallback。

验证结果：`test_llm_provider_mock.py` PASS；`test_llm_chunker.py` PASS；compileall PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/writer/renderer/sidecar 未接入。

---

### Step 6：实现 output writer、state schema、renderer

状态：已完成，已 commit 并 push。

```text
commit: 7d20e6c
message: Implement LLM output writer and renderer
```

完成内容：`session_dir/llm/` output writer；atomic text/json write；Phase 1A/1B output paths；sanitized error log；Phase 1A/1B state schema；renderer 支持 summary/readable/review Markdown 和 Markdown-to-HTML；HTML escaping；annotation semantics；fake secret 不落盘；evidence layer 保持不变。

验证结果：`test_llm_outputs.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/pipeline/CLI/Phase 2A sidecar 未接入。

#### Step 6 非阻塞问题点

1. `sanitize_text()` 当前会 redaction 所有输出文本中的 secret-like pattern。安全性强但可能过度保守。后续可评估更精细 redaction。
2. renderer 当前可能产生双重 HTML escaping。安全可接受，但显示效果可能偏保守。后续 Phase 1B 视图 polish 时可优化。

---

### Step 7：实现 Phase 1A after-stop summary mock pipeline

状态：已完成，已 commit 并 push。

```text
commit: 811386c
message: Implement Phase 1A summary mock pipeline
```

修改文件：

```text
llm/summary_pipeline.py
llm/prompt_templates.py
testCodes/test_llm_pipeline.py
```

完成内容：`run_summary_pipeline(...)`；读取 `clean.txt`；parser/chunker；section/global prompt payload；provider `generate_json()`；归一化为 `SummaryState`；renderer；`write_phase1a_outputs()`；返回 `SummaryPipelineResult`；失败写 sanitized `llm_errors.log`；fake secret 不落盘；evidence layer 保持不变。

Phase 1A 输出文件：

```text
session_dir/llm/summary.md
session_dir/llm/summary.json
session_dir/llm/sections.json
session_dir/llm/key_terms.json
session_dir/llm/action_items.json
```

验证结果：`test_llm_pipeline.py` PASS；compileall PASS；`test_llm_chunker.py` PASS；`test_llm_provider_mock.py` PASS；`test_llm_outputs.py` PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/CLI/Phase 1B/Phase 2A sidecar 未接入。

#### Step 7 非阻塞问题点

1. `SummaryPipelineResult.error` 当前直接保存 `str(exc)`。这不会落盘，但后续 CLI/UI 如果直接打印 `result.error`，理论上可能暴露 provider exception 中的敏感文本。Step 9 CLI 已在显示层使用 sanitized error display。
2. no live sidecar outputs 测试最初未覆盖 `live_readable_zh_errors.log`。Step 8 已补充 live error forbidden check；保留此项作为历史审查记录。

---

### Step 8：实现 Phase 1B after-stop readable transcript mock pipeline

状态：已完成，已 commit 并 push。

```text
commit: 0267d76
message: Implement Phase 1B readable transcript mock pipeline
```

修改文件：

```text
llm/prompt_templates.py
llm/readable_pipeline.py
testCodes/test_llm_pipeline.py
```

完成内容：新增 Phase 1B `run_readable_pipeline(...)`；链路为 `clean.txt -> parser/chunker -> readable prompt -> mock/fake provider -> ReadableTranscriptState -> renderer -> write_phase1b_outputs`；成功输出 readable/review state、Markdown、HTML；失败写 sanitized `readable_zh_errors.log`；failure 不修改 evidence layer；Step 7 Phase 1A summary regression 仍 PASS；不接真实 API、UI、CLI 或 Phase 2A sidecar。

Phase 1B 输出文件：

```text
session_dir/llm/readable_zh_final_state.json
session_dir/llm/readable_zh_final.md
session_dir/llm/readable_zh_final.html
session_dir/llm/review_zh_final.md
session_dir/llm/review_zh_final.html
```

验证结果：`test_llm_pipeline.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/CLI/Phase 2A sidecar 未接入。

#### Step 8 非阻塞问题点

1. `ReadablePipelineResult.error` 当前仍直接保存 `str(exc)`。和 Step 7 的 `SummaryPipelineResult.error` 类似，这不会落盘，但后续 CLI/UI 如果直接打印 `result.error`，理论上可能暴露 provider exception 中的敏感文本。Step 9 CLI 已在显示层使用 sanitized error display。
2. Phase 1B 当前按 chunk 直接生成 segments，`revision` 固定为 1。对 after-stop mock pipeline 足够；后续 Step 10 或 Phase 2A 前可考虑补充更强 state consistency 检查，例如 segment_id 去重、`end < start` validation、revision policy。

---

### Step 9：新增 CLI 入口并用 mock 跑通 Phase 1A / Phase 1B

状态：已完成，已 commit 并 push。

```text
commit: 81767bb
message: Add mock LLM postprocess CLI
```

修改文件：

```text
llm_postprocess.py
testCodes/test_llm_cli.py
```

完成内容：

- 新增 `llm_postprocess.py`；
- 支持 `--session`、`--provider mock`、`--task summary|readable|both`、`--max-chars`、`--max-seconds`、`--output-language zh`；
- 只支持 mock provider，non-mock 返回非 0；
- 内置 schema-aware deterministic `CLIMockProvider`，只服务 Step 9 离线 CLI smoke，不读取 `DEEPSEEK_API_KEY`，不访问网络；
- `--task summary` 生成 Phase 1A outputs；
- `--task readable` 生成 Phase 1B outputs；
- `--task both` 按 summary -> readable 顺序生成两组输出；
- missing session、missing `clean.txt`、non-mock provider 均返回非 0；
- CLI 错误显示使用 `sanitize_text()`，不打印 traceback、prompt 全文、raw request 或 raw response；
- `raw.txt`、`clean.txt`、`session.log`、`config.json` 保持不变；
- 未生成 Phase 2A live sidecar 文件。

验证结果：

```text
testCodes/test_llm_cli.py：PASS
testCodes/test_llm_pipeline.py：PASS，Step 7/8 regression 仍通过
compileall llm + llm_postprocess.py + tests：PASS
testCodes/test_llm_chunker.py：PASS
testCodes/test_llm_provider_mock.py：PASS
testCodes/test_llm_outputs.py：PASS
testCodes/test_ui_support.py：PASS
testCodes/test_backends.py --skip-faster-smoke：PASS，whisper.cpp availability 可按环境 SKIP
git diff --check：PASS
network/API grep：无输出
API key grep：无输出
ASR 主链路文件：无修改
docs 文件：无修改
真实 API / UI / Phase 2A sidecar：未接入
merge：未执行
```

审查结论：Step 9 通过，不需要 Step 9 v2。

#### Step 9 非阻塞问题点

1. `CLIMockProvider` 当前在 `llm_postprocess.py` 内部定义。对 Step 9 离线 CLI smoke 可接受；后续如果测试/CLI/provider mock 逻辑继续扩展，可考虑抽到 `llm/mock_provider.py` 或专门的 mock fixtures，避免 CLI 文件承载过多测试 provider 逻辑。
2. `--task both` 当前 summary 失败后仍会继续执行 readable。这不会破坏 evidence layer，也能暴露两个 pipeline 的独立失败状态；但 Step 10 应明确策略：`both` 模式是否 fail-fast，还是保留 partial success。

---

## 3. ACTIVE：Step 10 - 补齐 mock tests、failure isolation、secret leakage tests 与 hardening

状态：ACTIVE。

### 3.1 目标

对 Step 7/8/9 已实现的 mock pipeline 和 CLI 做集中 hardening。重点不是新增产品功能，而是补齐 failure isolation、secret leakage、state consistency、CLI partial failure policy 和 regression coverage。

Step 10 不接真实 DeepSeek/OpenAI HTTP，不要求 `DEEPSEEK_API_KEY`，不接 UI，不做 Phase 2A rolling sidecar，不改变 ASR 主链路。

---

### 3.2 允许修改范围

原则上允许：

```text
testCodes/test_llm_pipeline.py
testCodes/test_llm_cli.py
llm/summary_pipeline.py
llm/readable_pipeline.py
llm_postprocess.py
```

如需集中测试工具，允许新增：

```text
testCodes/llm_test_utils.py
```

如确有必要，可最小修改：

```text
llm/state_schema.py
llm/output_writer.py
llm/mock_provider.py
llm/llm_settings.py
llm/__init__.py
```

Codex 默认不得修改：

```text
docs/whisper_runtime.md
docs/whisper_static.md
README.md
```

Step 10 完成后，由人工审查后再受控更新 runtime。

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

不要生成 Phase 2A live sidecar 输出，除非测试明确验证这些文件不存在。

---

### 3.4 Step 10 hardening 要求

#### 3.4.1 CLI partial failure policy

明确 `llm_postprocess.py --task both` 的失败策略，并用测试固定。

可选方案：

```text
A. fail-fast：summary 失败后不运行 readable；返回非 0。
B. partial success：summary 失败仍运行 readable；返回非 0，并清楚打印 summary failed + readable status。
```

任选其一，但必须：

- 行为 deterministic；
- stdout/stderr sanitized；
- 测试覆盖；
- evidence layer unchanged；
- 不打印 prompt/raw response/traceback。

当前实现是偏向 partial success。若保留该行为，需要测试明确记录 readable 仍被运行；若改为 fail-fast，需要相应调整测试。

#### 3.4.2 Sanitized result / display hardening

检查 `SummaryPipelineResult.error`、`ReadablePipelineResult.error`、CLI error display 的使用路径。

要求：

- CLI 不直接打印 unsanitized exception；
- 测试覆盖 provider exception 中含 fake secret 时，stdout/stderr、`llm_errors.log`、`readable_zh_errors.log`、所有 JSON/Markdown/HTML 输出均不包含 fake secret；
- 不打印 traceback；
- 不打印 prompt/raw request/raw response。

#### 3.4.3 State consistency hardening

对 Phase 1A / Phase 1B state 增加必要的一致性验证，优先覆盖：

```text
segment_id / section_id 不应重复
end < start 应被拒绝或明确 fallback
revision 应为非负整数，必要时 readable revision >= 1
status / annotation type 仍为受控枚举
source.transcript = clean.txt
source.raw_used = false
```

实现位置可选择：

```text
llm/state_schema.py validation helper
或 pipeline normalization 阶段
或测试先覆盖现状并记录 TODO
```

优先做最小必要 hardening，不要重构 schema 全部结构。

#### 3.4.4 Mock provider / CLI mock organization

`CLIMockProvider` 目前在 `llm_postprocess.py` 内。Step 10 可选择：

```text
1. 保持不动，只补测试，记录它是 CLI smoke-only provider；或
2. 抽到 llm/mock_provider.py，作为 schema-aware mock response provider；或
3. 抽到 test helper，但 CLI 仍需要 runtime 可用的 mock provider。
```

不要为了抽象过度重构。若移动代码，必须保证现有 provider mock tests 仍 PASS。

#### 3.4.5 Output failure preservation

补测或实现：

- 如果已有上一版有效 `summary.md/json`，summary failure 不应破坏上一版文件；
- 如果已有上一版有效 `readable_zh_final_state.json/md/html`，readable failure 不应破坏上一版文件；
- renderer failure 不应留下半写入文件；
- atomic writer 行为仍 PASS。

---

### 3.5 测试要求

优先扩展现有测试：

```text
testCodes/test_llm_pipeline.py
testCodes/test_llm_cli.py
testCodes/test_llm_outputs.py
```

如测试公共逻辑重复明显，可新增：

```text
testCodes/llm_test_utils.py
```

测试必须可直接运行，不依赖 pytest。

建议新增/强化 PASS 输出：

```text
PASS: cli both partial failure policy
PASS: cli failure display sanitized across stdout stderr
PASS: summary failure preserves previous outputs
PASS: readable failure preserves previous outputs
PASS: duplicate segment ids rejected
PASS: duplicate section ids rejected
PASS: invalid time range rejected or normalized
PASS: readable revision policy enforced
PASS: all llm outputs contain no fake secret
PASS: no traceback printed
PASS: no prompt or raw response printed
```

至少覆盖：

- CLI `--task both` 一边失败时的既定策略；
- summary provider failure/schema failure 不破坏旧输出；
- readable provider failure/schema failure/renderer failure 不破坏旧输出；
- fake secret 不出现在 stdout/stderr/error logs/JSON/Markdown/HTML；
- duplicate ids 或 invalid time range 的策略；
- no prompt/raw response/traceback；
- raw/clean/session/config unchanged；
- 不生成 Phase 2A live sidecar files；
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

Step 10 focused/regression tests：

```bash
venv/bin/python testCodes/test_llm_cli.py
venv/bin/python testCodes/test_llm_pipeline.py
venv/bin/python testCodes/test_llm_outputs.py
```

预期：全部 PASS。

语法检查：

```bash
venv/bin/python -m compileall -q llm llm_postprocess.py testCodes/test_llm_cli.py testCodes/test_llm_pipeline.py testCodes/test_llm_outputs.py
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

可接受涉及：

```text
llm_postprocess.py
testCodes/test_llm_cli.py
testCodes/test_llm_pipeline.py
testCodes/test_llm_outputs.py
llm/summary_pipeline.py
llm/readable_pipeline.py
llm/state_schema.py
llm/output_writer.py
llm/mock_provider.py
llm/llm_settings.py
llm/__init__.py
testCodes/llm_test_utils.py
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
grep -RInE 'requests|httpx|aiohttp|urllib|urlopen|socket|Authorization|Bearer |chat\.completions|client\.chat|api\.deepseek|https?://' llm llm_postprocess.py testCodes/test_llm_cli.py testCodes/test_llm_pipeline.py testCodes/test_llm_outputs.py || true
```

预期：无实际网络/API 实现。若只命中注释、prompt 文本、测试 fake secret 或 placeholder 文本，必须说明。

API key 检查：

```bash
grep -RInE 'sk-[A-Za-z0-9_-]{16,}' llm llm_postprocess.py testCodes/test_llm_cli.py testCodes/test_llm_pipeline.py testCodes/test_llm_outputs.py || true
```

预期：无真实 key。若测试中故意使用 fake key pattern，必须说明它是测试字符串，并确保不会写入 stdout/stderr/output/error log。

---

### 3.7 Step 10 完成标准

全部满足才可标记 Step 10 已完成：

```text
CLI both partial failure policy 已明确并有测试
CLI stdout/stderr 不泄露 fake secret
CLI 不打印 traceback/prompt/raw response
summary/readable failure 不破坏上一版有效输出
state consistency hardening 或明确测试记录已完成
duplicate ids / invalid time range / revision policy 有测试或明确策略
raw.txt / clean.txt / session.log / config.json unchanged
不生成 Phase 2A live sidecar outputs
testCodes/test_llm_cli.py PASS
testCodes/test_llm_pipeline.py PASS
testCodes/test_llm_outputs.py PASS
testCodes/test_llm_chunker.py PASS
testCodes/test_llm_provider_mock.py PASS
compileall PASS
原有 baseline tests 无新增 FAIL
ASR 主链路无修改
未接真实 API / UI / Phase 2A sidecar
docs/whisper_runtime.md 未由 Codex 修改
```

---

### 3.8 风险

重点防止：

- 为 hardening 过度重构 pipeline/schema；
- 修改 ASR 主链路；
- 接入真实 API 或读取 `DEEPSEEK_API_KEY`；
- CLI 继续打印 unsanitized exception；
- 测试只检查 stdout/stderr，不扫描 outputs/error logs；
- 新增测试依赖 pytest 或真实 outputs；
- Codex 提前改 runtime。

---

### 3.9 回滚

如果 Step 10 实现方向错误，先看 diff：

```bash
git diff -- llm_postprocess.py llm/summary_pipeline.py llm/readable_pipeline.py llm/state_schema.py llm/output_writer.py llm/mock_provider.py llm/llm_settings.py llm/__init__.py testCodes/test_llm_cli.py testCodes/test_llm_pipeline.py testCodes/test_llm_outputs.py testCodes/llm_test_utils.py
```

只回滚本步骤相关文件，优先使用 `git restore <path>`，仅删除确认属于 Step 10 的新增文件。

不要使用：

```bash
git reset --hard
git clean -fd
```

除非用户明确确认当前工作区可以全部丢弃。

---

## 4. 后续步骤简要内容

### Step 11：实现 DeepSeek / OpenAI-compatible provider

目标：从 `DEEPSEEK_API_KEY` 读取 key；model / endpoint 可配置；typed provider errors；测试用 monkeypatch/mock HTTP client；自动测试不真实调用 API。

---

### Step 12：本地手动真实 API smoke test

目标：mock tests 全部通过后，用 disposable session 手动测试真实 API；不打印 key；不保存 key；扫描 repo/session/log。

---

### Step 13：验证 Phase 1A / 1B 真实课堂 session 输出质量

目标：人工检查 1-2 节真实课堂 session；检查 hallucination、timestamp grounding、action items、unclear parts、readable/review 视图可读性。

---

### Step 14：实现 Phase 2A rolling sidecar

目标：默认关闭；只读 clean snapshot；single in-flight request；pending snapshot coalescing；frozen/editable window；atomic replace；不进入 ASR 主链路。

---

### Step 15：验证 single worker、coalescing、atomic replace、final reconciliation

目标：验证 Phase 2A 不形成 backlog；Stop 后 final reconciliation；失败保留上一版有效输出。

---

### Step 16：实现 Phase 2B 应用内 QTextBrowser 预览

目标：最小 UI 预览；`QTextBrowser.setHtml()`；不引入 `QWebEngineView`；sidecar worker 不直接操作 Qt widget。

---

### Step 17：长时间课堂稳定性测试

目标：验证 ASR 主链路、LLM 后处理、sidecar、UI preview 在真实课堂长度下稳定；检查 Stop drain、queue backlog、麦克风释放、UI 稳定性。

---

### Step 18：确认稳定后再考虑默认开关策略

目标：汇总质量和稳定性结果；决定 LLM 功能默认关闭、默认开启或按 provider/API key 状态启用。

---

## 5. 提交与推送规则

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
Harden mock LLM pipelines and CLI tests
```

push：

```bash
git push
```
