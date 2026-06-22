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
当前 checkpoint：Step 10 已完成并已 push
唯一 ACTIVE 任务：Step 11 - 实现 DeepSeek / OpenAI-compatible provider
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
Step 10：补齐 mock tests、failure isolation、secret leakage tests 与 hardening
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
mock pipeline/CLI hardening
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
2. Phase 1B 当前按 chunk 直接生成 segments，`revision` 固定为 1。对 after-stop mock pipeline 足够；Step 10 已补充 revision >= 1、duplicate id 和 invalid time range validation；Phase 2A 前仍可继续细化 revision policy。

---

### Step 9：新增 CLI 入口并用 mock 跑通 Phase 1A / Phase 1B

状态：已完成，已 commit 并 push。

```text
commit: 81767bb
message: Add mock LLM postprocess CLI
```

完成内容：新增 `llm_postprocess.py`；支持 `--session`、`--provider mock`、`--task summary|readable|both`、`--max-chars`、`--max-seconds`、`--output-language zh`；只支持 mock provider；内置 schema-aware deterministic `CLIMockProvider`；summary/readable/both 均可生成对应 Phase 1A/1B 输出；missing session、missing `clean.txt`、non-mock provider 均返回非 0；CLI 错误显示使用 `sanitize_text()`，不打印 traceback、prompt 全文、raw request 或 raw response；evidence layer 保持不变；未生成 Phase 2A live sidecar 文件。

验证结果：`test_llm_cli.py` PASS；`test_llm_pipeline.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/Phase 2A sidecar 未接入。

#### Step 9 非阻塞问题点

1. `CLIMockProvider` 当前在 `llm_postprocess.py` 内部定义。对 Step 9/10 离线 CLI smoke 可接受；后续如果测试/CLI/provider mock 逻辑继续扩展，可考虑抽到 `llm/mock_provider.py` 或专门的 mock fixtures。
2. `--task both` 当前采用 partial success 策略：summary 失败后仍会继续执行 readable，最终返回非 0。Step 10 已用测试固定该行为；后续接真实 provider 后可继续优化 terminal wording。

---

### Step 10：补齐 mock tests、failure isolation、secret leakage tests 与 hardening

状态：已完成，已 commit 并 push。

```text
commit: 68b7923
message: Harden mock LLM pipelines and CLI tests
```

修改文件：

```text
llm/state_schema.py
llm_postprocess.py
testCodes/test_llm_cli.py
testCodes/test_llm_outputs.py
testCodes/test_llm_pipeline.py
```

完成内容：

- CLI `--task both` 策略固定为 partial success：summary 失败后仍运行 readable，最终返回非 0，并打印 sanitized summary failure + readable status；
- CLI 不打印 traceback、prompt、raw request、raw response；provider exception 中的 fake secret 会被 redacted；
- summary/readable failure 不破坏上一版有效输出，覆盖 provider failure、schema failure、readable renderer failure；
- state validation 增强：重复 `section_id` / `segment_id` 拒绝，`end < start` 拒绝，readable `revision >= 1`，默认 revision 改为 `1`；
- `CLIMockProvider` 保持在 `llm_postprocess.py` 内作为 CLI smoke-only provider；增加隐藏 `--mock-fail-schema` 仅用于 failure-policy 测试，并移除固定 readable segment id，避免多 chunk 时重复 id。

验证结果：

```text
testCodes/test_llm_cli.py：PASS
testCodes/test_llm_pipeline.py：PASS
testCodes/test_llm_outputs.py：PASS
compileall llm + llm_postprocess.py + Step 10 tests：PASS
testCodes/test_llm_chunker.py：PASS
testCodes/test_llm_provider_mock.py：PASS
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

审查结论：Step 10 通过，不需要 Step 10 v2。

#### Step 10 非阻塞问题点

1. `state_schema.py` 的 number validation 使用 `isinstance(value, (int, float))`。Python 中 `bool` 是 `int` 的子类，所以 `True/False` 理论上会被当作合法 number。当前测试和正常 pipeline 不会触发；后续 schema strictness 可改为排除 bool。
2. CLI partial success 策略已固定，但将来接真实 provider 后，summary/readable 的 partial output 对用户可能需要更清晰的 terminal wording，例如区分 “summary failed, readable succeeded, overall failed”。当前 Step 10 已满足 mock CLI hardening，不阻塞 Step 11。

---

## 3. ACTIVE：Step 11 - 实现 DeepSeek / OpenAI-compatible provider

状态：ACTIVE。

### 3.1 目标

实现真实 provider 的代码路径，但自动测试必须使用 mock HTTP client / monkeypatch，不得真实访问网络。

目标：

```text
DEEPSEEK_API_KEY env var
-> OpenAI-compatible chat completions request builder
-> HTTP client abstraction / injectable transport
-> DeepSeekProvider.generate_text / generate_json
-> typed provider errors
-> no secret leakage
-> no request/response log
```

Step 11 只实现 provider 层，不接 UI，不实现 Phase 2A sidecar，不改变 ASR 主链路。CLI 可以继续只支持 mock，除非用户另行批准开放真实 provider CLI 参数。

---

### 3.2 允许修改范围

原则上允许：

```text
llm/deepseek_provider.py
llm/openai_compatible_provider.py
llm/provider_base.py
llm/llm_settings.py
testCodes/test_llm_provider_deepseek.py
```

如需复用 secret redaction，可最小修改：

```text
llm/output_writer.py
```

如需导出 provider symbols，可最小修改：

```text
llm/__init__.py
```

Codex 默认不得修改：

```text
docs/whisper_runtime.md
docs/whisper_static.md
README.md
```

Step 11 完成后，由人工审查后再受控更新 runtime。

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
UI
Phase 2A sidecar
request / response log
API key settings / Keychain
自动测试真实网络调用
```

不要修改 evidence layer：

```text
raw.txt
clean.txt
session.log
config.json
```

---

### 3.4 Step 11 实现要求

#### 3.4.1 Provider API

实现或完善：

```text
DeepSeekProvider
OpenAICompatibleProvider
```

要求：

- 从环境变量 `DEEPSEEK_API_KEY` 读取 key；
- key 缺失时抛 `MissingAPIKeyError` 或等价 typed error；
- 不把 key 保存到 settings/config/session/docs/logs；
- 不打印 key；
- 不记录 Authorization header；
- 不记录完整 request/response body；
- 支持 `generate_text(system_prompt, user_prompt)`；
- 支持 `generate_json(system_prompt, user_prompt, schema_name)`；
- JSON response 解析失败时抛 `LLMMalformedResponseError` 或 `LLMInvalidResponseError`；
- schema / JSON contract 失败时抛 `LLMSchemaError` 或明确 typed error；
- HTTP 401/403 映射为 `LLMAuthenticationError`；
- HTTP 429 映射为 `LLMRateLimitError`；
- timeout 映射为 `LLMTimeoutError`；
- 其他 provider/HTTP error 映射为 `LLMProviderError` 或等价 typed error。

#### 3.4.2 HTTP client / transport abstraction

自动测试不得真实访问网络。

建议实现 injectable HTTP transport，例如：

```text
OpenAICompatibleProvider(api_key=None, endpoint=..., model=..., http_client=...)
```

`http_client` 可为极小接口，例如：

```text
post_json(url, headers, payload, timeout) -> response-like object
```

或使用 stdlib `urllib` 的 wrapper，但测试必须 monkeypatch wrapper，不真实请求。

不要在自动测试中调用真实 `api.deepseek.com`。

#### 3.4.3 Request shape

OpenAI-compatible chat completions 请求应包含：

```text
model
messages: system + user
temperature 可配置，默认低温
response_format 可选 JSON object，用于 generate_json
```

默认 endpoint 可指向 DeepSeek OpenAI-compatible endpoint，但不得在测试中真实访问。

#### 3.4.4 Secret safety

测试必须验证：

- fake `DEEPSEEK_API_KEY` 不出现在 exception message；
- fake key 不出现在 provider returned text/json；
- fake key 不出现在 stdout/stderr；
- fake key 不出现在 any local output/error logs（如果测试构造 session 输出）；
- Authorization header 不被记录或暴露。

---

### 3.5 测试要求

新增：

```text
testCodes/test_llm_provider_deepseek.py
```

测试必须可直接运行，不依赖 pytest：

```bash
venv/bin/python testCodes/test_llm_provider_deepseek.py
```

自动测试只用 fake env key 和 fake http client。

建议 PASS 输出：

```text
PASS: deepseek provider requires api key
PASS: deepseek provider builds chat completion request
PASS: deepseek provider text success
PASS: deepseek provider json success
PASS: deepseek provider malformed json response
PASS: deepseek provider invalid json contract
PASS: deepseek provider authentication error
PASS: deepseek provider rate limit error
PASS: deepseek provider timeout error
PASS: deepseek provider secret not leaked
PASS: deepseek provider no real network
```

至少覆盖：

- `DEEPSEEK_API_KEY` 缺失；
- fake key 从 env 读取；
- request headers 包含 Authorization，但不会被打印/记录；
- request payload 包含 system/user prompt 和 model；
- text success；
- json success；
- invalid JSON body；
- JSON object 缺失或类型不对；
- 401/403；
- 429；
- timeout；
- arbitrary HTTP 5xx/provider error；
- fake key 不泄露；
- 无真实网络调用。

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

Step 11 focused test：

```bash
venv/bin/python testCodes/test_llm_provider_deepseek.py
```

预期：全部 PASS。

语法检查：

```bash
venv/bin/python -m compileall -q llm testCodes/test_llm_provider_deepseek.py
```

预期：无输出，退出码为 0。

LLM 既有回归：

```bash
venv/bin/python testCodes/test_llm_cli.py
venv/bin/python testCodes/test_llm_pipeline.py
venv/bin/python testCodes/test_llm_outputs.py
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
llm/deepseek_provider.py
llm/openai_compatible_provider.py
llm/provider_base.py
llm/llm_settings.py
llm/output_writer.py
llm/__init__.py
testCodes/test_llm_provider_deepseek.py
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
grep -RInE 'requests|httpx|aiohttp|urlopen|socket|api\.deepseek|https?://' llm testCodes/test_llm_provider_deepseek.py || true
```

预期：如果 provider implementation 使用 stdlib/network wrapper 或 endpoint 字符串，grep 可能有命中；必须说明没有在自动测试中真实请求网络，并且所有 HTTP 行为由 fake client/monkeypatch 覆盖。

API key 检查：

```bash
grep -RInE 'sk-[A-Za-z0-9_-]{16,}|DEEPSEEK_API_KEY|Authorization|Bearer ' llm testCodes/test_llm_provider_deepseek.py || true
```

预期：只允许出现环境变量名、Authorization header 组装代码、测试 fake key 或测试断言；不得出现真实 key；不得输出 key。

---

### 3.7 Step 11 完成标准

全部满足才可标记 Step 11 已完成：

```text
DeepSeek/OpenAI-compatible provider 可构造
缺失 DEEPSEEK_API_KEY 抛 typed error
fake env key 可被 provider 使用但不泄露
text success PASS
json success PASS
malformed/invalid json PASS
401/403 -> authentication typed error
429 -> rate limit typed error
timeout -> timeout typed error
5xx/provider error -> provider typed error
自动测试无真实网络调用
testCodes/test_llm_provider_deepseek.py PASS
既有 LLM tests PASS
compileall PASS
原有 baseline tests 无新增 FAIL
ASR 主链路无修改
未接 UI / Phase 2A sidecar
docs/whisper_runtime.md 未由 Codex 修改
```

---

### 3.8 风险

重点防止：

- 自动测试真实访问 DeepSeek；
- API key 写入 repo/docs/session/config/logs；
- exception message 泄露 key 或 Authorization header；
- 为接 provider 修改 ASR 主链路；
- CLI 默认开放真实 provider；
- request/response body 被落盘或打印；
- Codex 提前改 runtime。

---

### 3.9 回滚

如果 Step 11 实现方向错误，先看 diff：

```bash
git diff -- llm/deepseek_provider.py llm/openai_compatible_provider.py llm/provider_base.py llm/llm_settings.py llm/output_writer.py llm/__init__.py testCodes/test_llm_provider_deepseek.py
```

只回滚本步骤相关文件，优先使用：

```bash
git restore <path>
```

如果新增了 `testCodes/test_llm_provider_deepseek.py` 且确认只属于 Step 11：

```bash
rm -f testCodes/test_llm_provider_deepseek.py
```

不要使用：

```bash
git reset --hard
git clean -fd
```

除非用户明确确认当前工作区可以全部丢弃。

---

## 4. 后续步骤简要内容

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
Implement DeepSeek provider
```

push：

```bash
git push
```
