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
当前 checkpoint：Step 8 已完成并已 push
唯一 ACTIVE 任务：Step 9 - 新增 CLI 入口并用 mock 跑通 Phase 1A / Phase 1B
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
```

当前尚未实现：

```text
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
Phase 1A summary mock pipeline
Phase 1B readable transcript mock pipeline
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

完成内容：`run_summary_pipeline(session_dir, provider, settings=None, max_chars=..., max_seconds=...)`；读取 `clean.txt`；parser/chunker；section/global prompt payload；provider `generate_json()`；归一化为 `SummaryState`；renderer；`write_phase1a_outputs()`；返回 `SummaryPipelineResult`；失败写 sanitized `llm_errors.log`；fake secret 不落盘；evidence layer 保持不变。

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

1. `SummaryPipelineResult.error` 当前直接保存 `str(exc)`。这不会落盘，但后续 CLI/UI 如果直接打印 `result.error`，理论上可能暴露 provider exception 中的敏感文本。Step 9 CLI 接入前建议统一使用 sanitized display error。
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

完成内容：

- 新增 Phase 1B `run_readable_pipeline(...)`；
- 链路：`clean.txt -> parser/chunker -> readable prompt -> mock/fake provider -> ReadableTranscriptState -> renderer -> write_phase1b_outputs`；
- 成功输出 `readable_zh_final_state.json`、`readable_zh_final.md`、`readable_zh_final.html`、`review_zh_final.md`、`review_zh_final.html`；
- provider/schema/renderer failure 写入 sanitized `readable_zh_errors.log`；
- failure 不修改 `raw.txt`、`clean.txt`、`session.log`、`config.json`；
- Phase 1B prompt 明确 clean transcript evidence only、中文 readable transcript、timestamp grounding、no hallucination、state JSON 是真实状态源、Markdown/HTML 由本地 renderer 派生、unclear/suspicious/possible correction、不覆盖 `clean.txt`；
- Step 7 Phase 1A summary regression 仍 PASS；
- 不接真实 API、UI、CLI 或 Phase 2A sidecar。

Phase 1B 输出文件：

```text
session_dir/llm/readable_zh_final_state.json
session_dir/llm/readable_zh_final.md
session_dir/llm/readable_zh_final.html
session_dir/llm/review_zh_final.md
session_dir/llm/review_zh_final.html
```

验证结果：

```text
testCodes/test_llm_pipeline.py：PASS
compileall llm + testCodes/test_llm_pipeline.py：PASS
testCodes/test_llm_chunker.py：PASS
testCodes/test_llm_provider_mock.py：PASS
testCodes/test_llm_outputs.py：PASS
testCodes/test_ui_support.py：PASS
testCodes/test_backends.py --skip-faster-smoke：PASS，faster-whisper smoke/whisper.cpp availability 可按环境 SKIP
git diff --check：PASS
network/API grep：无输出
API key grep：无输出
ASR 主链路文件：无修改
docs 文件：无修改
真实 API / UI / CLI / Phase 2A sidecar：未接入
merge：未执行
```

审查结论：Step 8 通过，不需要 Step 8 v2。

#### Step 8 非阻塞问题点

1. `ReadablePipelineResult.error` 当前仍直接保存 `str(exc)`。和 Step 7 的 `SummaryPipelineResult.error` 类似，这不会落盘，但后续 CLI/UI 如果直接打印 `result.error`，理论上可能暴露 provider exception 中的敏感文本。Step 9 CLI 接入前应统一使用 sanitized display error。
2. Phase 1B 当前按 chunk 直接生成 segments，`revision` 固定为 1。对 after-stop mock pipeline 足够；后续 Step 10 或 Phase 2A 前可考虑补充更强 state consistency 检查，例如 segment_id 去重、`end < start` validation、revision policy。

---

## 3. ACTIVE：Step 9 - 新增 CLI 入口并用 mock 跑通 Phase 1A / Phase 1B

状态：ACTIVE。

### 3.1 目标

新增一个最小 CLI 入口，使用户可以对 existing completed session 运行 LLM mock postprocess。

目标链路：

```text
existing completed session_dir
-> CLI args
-> provider = mock
-> run_summary_pipeline optional
-> run_readable_pipeline optional
-> write session_dir/llm/ outputs
-> terminal summary only
```

Step 9 只用 mock provider 或测试 fake provider，不接真实 DeepSeek/OpenAI HTTP，不要求 `DEEPSEEK_API_KEY`，不接 UI，不做 Phase 2A rolling sidecar。

---

### 3.2 允许修改范围

原则上允许：

```text
llm_postprocess.py
testCodes/test_llm_cli.py
```

允许最小修改：

```text
llm/summary_pipeline.py
llm/readable_pipeline.py
llm/prompt_templates.py
llm/llm_settings.py
llm/__init__.py
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

Codex 默认不得修改：

```text
docs/whisper_runtime.md
docs/whisper_static.md
README.md
```

Step 9 完成后，由人工审查后再受控更新 runtime。

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

不要生成 Phase 2A live sidecar 输出。

---

### 3.4 Step 9 实现要求

#### 3.4.1 CLI 入口

新增根目录 CLI 文件：

```text
llm_postprocess.py
```

建议命令形态：

```bash
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock --task summary
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock --task readable
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock --task both
```

可接受参数：

```text
--session <path>      required，completed session dir
--provider mock      required/默认，仅支持 mock
--task summary|readable|both
--max-chars <int>
--max-seconds <float>
--output-language zh
```

必须满足：

- session path 必须存在；
- `clean.txt` 必须存在，否则返回非 0 exit code，并打印 sanitized error；
- 只支持 mock provider；如果传入其他 provider，应返回非 0 exit code 并说明 Step 9 only supports mock；
- `--task summary` 只运行 Phase 1A；
- `--task readable` 只运行 Phase 1B；
- `--task both` 按 summary -> readable 顺序运行；
- terminal 只打印简洁状态摘要和输出路径；
- 不打印 prompt 全文；
- 不打印 provider raw request / raw response；
- 不打印 API key 或 secret-like text；
- failure 不修改 evidence layer；
- 不接 UI；
- 不接真实 API。

#### 3.4.2 Mock provider behavior

CLI 默认使用 `MockProvider`。

如果现有 `MockProvider` 的默认 JSON 输出无法满足 summary/readable pipeline schema，可以：

1. 在 CLI 内为 summary/readable 使用专用 deterministic fake provider；或
2. 在 `MockProvider` 中增加仅 mock pipeline 用的 schema-aware deterministic response；或
3. 在 pipeline normalization 中兼容当前 mock provider 输出。

选择方案时优先保持最小改动和测试可读性。

禁止真实 HTTP/API。

#### 3.4.3 Sanitized CLI error display

Step 7/8 已记录：pipeline result `error` 直接保存 `str(exc)`，后续 CLI/UI 不能直接无过滤打印。

Step 9 必须在 CLI 层实现 sanitized error display：

- 对 `result.error` 打印前 redaction；
- 可复用 `output_writer.sanitize_text()`；
- 不打印 traceback，除非有 explicit debug flag；Step 9 默认不要做 debug flag；
- 不打印 prompt、raw request、raw response。

---

### 3.5 建议测试文件

新增：

```text
testCodes/test_llm_cli.py
```

测试必须可直接运行：

```bash
venv/bin/python testCodes/test_llm_cli.py
```

运行，不依赖 pytest。

建议 PASS 输出：

```text
PASS: cli summary mock success
PASS: cli readable mock success
PASS: cli both mock success
PASS: cli rejects missing session
PASS: cli rejects missing clean transcript
PASS: cli rejects non-mock provider
PASS: cli failure output sanitized
PASS: cli does not print prompts or raw responses
PASS: cli raw clean session config unchanged
PASS: cli no live sidecar outputs
PASS: cli no real API call
```

至少覆盖：

- `--task summary` 生成 Phase 1A outputs；
- `--task readable` 生成 Phase 1B outputs；
- `--task both` 同时生成 Phase 1A/1B outputs；
- missing session 返回非 0；
- missing clean.txt 返回非 0；
- non-mock provider 返回非 0；
- fake secret 不出现在 stdout/stderr 或任何 output/error log；
- CLI 不打印 prompt 全文，不打印 raw response；
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

Step 9 focused test：

```bash
venv/bin/python testCodes/test_llm_cli.py
```

预期：全部 PASS。

LLM pipeline 回归：

```bash
venv/bin/python testCodes/test_llm_pipeline.py
```

预期：Step 7/8 tests 全部 PASS。

语法检查：

```bash
venv/bin/python -m compileall -q llm llm_postprocess.py testCodes/test_llm_cli.py testCodes/test_llm_pipeline.py
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
llm_postprocess.py
testCodes/test_llm_cli.py
```

可能允许：

```text
llm/mock_provider.py
llm/llm_settings.py
llm/__init__.py
llm/summary_pipeline.py
llm/readable_pipeline.py
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
grep -RInE 'requests|httpx|aiohttp|urllib|urlopen|socket|Authorization|Bearer |chat\.completions|client\.chat|api\.deepseek|https?://' llm llm_postprocess.py testCodes/test_llm_cli.py testCodes/test_llm_pipeline.py || true
```

预期：无实际网络/API 实现。若只命中注释、prompt 文本、测试 fake secret 或 placeholder 文本，必须说明。

API key 检查：

```bash
grep -RInE 'sk-[A-Za-z0-9_-]{16,}' llm llm_postprocess.py testCodes/test_llm_cli.py testCodes/test_llm_pipeline.py || true
```

预期：无真实 key。若测试中故意使用 fake key pattern，必须说明它是测试字符串，并确保不会写入 stdout/stderr/output/error log。

---

### 3.7 Step 9 完成标准

全部满足才可标记 Step 9 已完成：

```text
llm_postprocess.py 存在
CLI 支持 --session / --provider mock / --task summary|readable|both
--task summary 生成 Phase 1A outputs
--task readable 生成 Phase 1B outputs
--task both 生成 Phase 1A + Phase 1B outputs
missing session / missing clean.txt / non-mock provider 返回非 0
CLI stdout/stderr 不泄露 fake secret
CLI 不打印 prompt 全文 / raw request / raw response
provider/schema failure 被隔离，错误显示 sanitized
raw.txt / clean.txt / session.log / config.json unchanged
不生成 Phase 2A live sidecar outputs
testCodes/test_llm_cli.py PASS
testCodes/test_llm_pipeline.py PASS
compileall PASS
LLM 既有 tests PASS
原有 baseline tests 无新增 FAIL
ASR 主链路无修改
未接真实 API / UI / Phase 2A sidecar
docs/whisper_runtime.md 未由 Codex 修改
```

---

### 3.8 风险

重点防止：

- CLI 打印 unsanitized `result.error`；
- CLI 打印 prompt 或 raw provider response；
- CLI 接入真实 API 或读取 `DEEPSEEK_API_KEY`；
- CLI 修改 evidence layer；
- `--task both` 部分失败时错误处理不清晰；
- 为 CLI 方便而修改 ASR 主链路；
- 破坏 Step 7/8 pipeline regression；
- Codex 提前改 runtime。

---

### 3.9 回滚

如果 Step 9 实现方向错误，先看 diff：

```bash
git diff -- llm_postprocess.py testCodes/test_llm_cli.py llm/mock_provider.py llm/llm_settings.py llm/__init__.py llm/summary_pipeline.py llm/readable_pipeline.py
```

只回滚本步骤相关文件：

```bash
git restore llm/mock_provider.py llm/llm_settings.py llm/__init__.py llm/summary_pipeline.py llm/readable_pipeline.py
rm -f llm_postprocess.py testCodes/test_llm_cli.py
```

不要使用：

```bash
git reset --hard
git clean -fd
```

除非用户明确确认当前工作区可以全部丢弃。

---

## 4. 后续步骤简要内容

### Step 10：补齐 mock tests、error injection、secret leakage tests

目标：failure isolation、malformed response、schema validation failure、renderer failure、API key leakage scan、raw/clean/session/config unchanged、pipeline result sanitized display policy hardening、state consistency hardening。

---

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
Add mock LLM postprocess CLI
```

push：

```bash
git push
```
