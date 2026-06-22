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
当前 checkpoint：Step 12 已完成；旧 Step 13 真实结构化输出验证已尝试但被方向变更取代
当前 static 方向：Markdown-only LLM sidecar
唯一 ACTIVE 任务：Step 13A - 实现 Markdown-only LLM sidecar 主路径
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
Step 11：实现 DeepSeek / OpenAI-compatible provider
Step 12：本地手动真实 API smoke test
Static direction update：简化为 Markdown-only LLM sidecar
```

当前代码中仍存在但不再作为新稳定合同主路径的 legacy/structured 能力：

```text
state schema
renderer
Phase 1A summary structured mock pipeline
Phase 1B readable structured mock pipeline
mock CLI summary/readable/both
provider.generate_json()
summary.json / sections.json / key_terms.json / action_items.json 输出逻辑
readable_zh_final_state.json / review_zh_final.* 输出逻辑
```

当前新目标只推进：

```text
clean.txt snapshot
-> parser/chunker
-> Markdown prompt
-> provider.generate_text()
-> readable_zh.md
-> log.md
-> UI Markdown preview
```

---

## 2. 已完成步骤记录

### Step 1：冻结需求和架构边界

状态：已完成。

历史结论：LLM 是 DeepSeek / OpenAI-compatible 后处理模块，不是实时 ASR 主链路的一部分；LLM 失败不得影响 Start/Stop、麦克风释放、UI 主线程或原 session 文件；`raw.txt`、`clean.txt`、`session.log`、`config.json` 是不可变 evidence layer。

当前修正：后续不再以结构化 Phase 1A/1B/2A state 作为主方向，转为 Markdown-only sidecar。

---

### Step 2：更新设计文档

状态：已完成。

历史完成内容：固定 LLM sidecar 架构边界；明确 API key、Markdown/HTML 派生视图、UI 和动态 sidecar 后置；明确旧执行顺序为 Step 1 到 Step 18。

当前修正：2026-06-22 已更新 static，将旧结构化 LLM phase 合同简化为 Markdown-only sidecar 合同。

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

当前保留价值：parser/chunker 仍可用于 Markdown-only sidecar 的 clean snapshot 预处理和 prompt 控长。

---

### Step 5：实现 provider interface、mock provider，并完成 Step 4 parser/chunker hardening

状态：已完成，已 commit 并 push。

```text
commit: 00e2d1c
message: Implement LLM provider interface and mock provider
```

完成内容：`LLMProvider` Protocol；typed provider errors；deterministic `MockProvider`；mock provider 支持 text/JSON success 和 error injection；不读取 `DEEPSEEK_API_KEY`；不访问网络；不写 request/response log；`DeepSeekProvider` 保持 placeholder；`TranscriptLine.raw_line`；`end < start` fallback。

验证结果：`test_llm_provider_mock.py` PASS；`test_llm_chunker.py` PASS；compileall PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/writer/renderer/sidecar 未接入。

当前保留价值：`generate_text()`、typed provider errors 和 mock text response 仍是 Markdown-only sidecar 的基础。

---

### Step 6：实现 output writer、state schema、renderer

状态：已完成，已 commit 并 push。

```text
commit: 7d20e6c
message: Implement LLM output writer and renderer
```

完成内容：`session_dir/llm/` output writer；atomic text/json write；Phase 1A/1B output paths；sanitized error log；Phase 1A/1B state schema；renderer 支持 summary/readable/review Markdown 和 Markdown-to-HTML；HTML escaping；annotation semantics；fake secret 不落盘；evidence layer 保持不变。

验证结果：`test_llm_outputs.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/pipeline/CLI/Phase 2A sidecar 未接入。

当前保留价值：atomic text write、path containment、sanitized diagnostics 可继续复用。state schema、renderer、HTML 和 JSON 输出不再是新稳定主路径。

#### Step 6 非阻塞问题点

1. `sanitize_text()` 当前会 redaction 所有输出文本中的 secret-like pattern。安全性强但可能过度保守。后续可评估更精细 redaction。
2. renderer 当前可能产生双重 HTML escaping。新 Markdown-only 方向不要求落盘 HTML，但 legacy renderer 仍可能保留。

---

### Step 7：实现 Phase 1A after-stop summary mock pipeline

状态：已完成，已 commit 并 push。

```text
commit: 811386c
message: Implement Phase 1A summary mock pipeline
```

完成内容：`run_summary_pipeline(...)`；读取 `clean.txt`；parser/chunker；section/global prompt payload；provider `generate_json()`；归一化为 `SummaryState`；renderer；`write_phase1a_outputs()`；返回 `SummaryPipelineResult`；失败写 sanitized `llm_errors.log`；fake secret 不落盘；evidence layer 保持不变。

历史输出文件：

```text
session_dir/llm/summary.md
session_dir/llm/summary.json
session_dir/llm/sections.json
session_dir/llm/key_terms.json
session_dir/llm/action_items.json
```

验证结果：`test_llm_pipeline.py` PASS；compileall PASS；`test_llm_chunker.py` PASS；`test_llm_provider_mock.py` PASS；`test_llm_outputs.py` PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/CLI/Phase 1B/Phase 2A sidecar 未接入。

当前状态：legacy structured pipeline。后续不再作为稳定主路径。不得继续在该路径上追加 normalization hardening 作为主方向。

---

### Step 8：实现 Phase 1B after-stop readable transcript mock pipeline

状态：已完成，已 commit 并 push。

```text
commit: 0267d76
message: Implement Phase 1B readable transcript mock pipeline
```

完成内容：新增 Phase 1B `run_readable_pipeline(...)`；链路为 `clean.txt -> parser/chunker -> readable prompt -> mock/fake provider -> ReadableTranscriptState -> renderer -> write_phase1b_outputs`；成功输出 readable/review state、Markdown、HTML；失败写 sanitized `readable_zh_errors.log`；failure 不修改 evidence layer；Step 7 Phase 1A summary regression 仍 PASS；不接真实 API、UI、CLI 或 Phase 2A sidecar。

历史输出文件：

```text
session_dir/llm/readable_zh_final_state.json
session_dir/llm/readable_zh_final.md
session_dir/llm/readable_zh_final.html
session_dir/llm/review_zh_final.md
session_dir/llm/review_zh_final.html
```

验证结果：`test_llm_pipeline.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/CLI/Phase 2A sidecar 未接入。

当前状态：legacy structured pipeline。后续不再作为稳定主路径。`readable_zh_final_state.json`、review view、annotation/status 语义均不进入新合同。

---

### Step 9：新增 CLI 入口并用 mock 跑通 Phase 1A / Phase 1B

状态：已完成，已 commit 并 push。

```text
commit: 81767bb
message: Add mock LLM postprocess CLI
```

完成内容：新增 `llm_postprocess.py`；支持 `--session`、`--provider mock`、`--task summary|readable|both`、`--max-chars`、`--max-seconds`、`--output-language zh`；只支持 mock provider；内置 schema-aware deterministic `CLIMockProvider`；summary/readable/both 均可生成对应 Phase 1A/1B 输出；missing session、missing `clean.txt`、non-mock provider 均返回非 0；CLI 错误显示使用 `sanitize_text()`，不打印 traceback、prompt 全文、raw request 或 raw response；evidence layer 保持不变；未生成 Phase 2A live sidecar 文件。

验证结果：`test_llm_cli.py` PASS；`test_llm_pipeline.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/Phase 2A sidecar 未接入。

当前状态：legacy mock CLI。后续若保留 CLI，应改为 Markdown-only，输出 `readable_zh.md` + `log.md`。

#### Step 9 非阻塞问题点

1. `CLIMockProvider` 当前在 `llm_postprocess.py` 内部定义。对旧 Step 9/10 离线 CLI smoke 可接受；后续 Markdown-only CLI 若继续扩展，可考虑简化 mock text fixture。
2. `--task both` 当前采用 partial success 策略。新合同不再区分 summary/readable/both，后续可移除该复杂状态。

---

### Step 10：补齐 mock tests、failure isolation、secret leakage tests 与 hardening

状态：已完成，已 commit 并 push。

```text
commit: 68b7923
message: Harden mock LLM pipelines and CLI tests
```

完成内容：CLI `--task both` partial success 策略固定；CLI 不打印 traceback/prompt/raw request/raw response；provider exception 中 fake secret redacted；summary/readable failure 不破坏上一版有效输出；state validation 增强：重复 `section_id` / `segment_id` 拒绝、`end < start` 拒绝、readable `revision >= 1`、默认 revision 改为 `1`；`CLIMockProvider` 保持 CLI smoke-only provider；隐藏 `--mock-fail-schema` 仅用于 failure-policy 测试。

验证结果：`test_llm_cli.py` PASS；`test_llm_pipeline.py` PASS；`test_llm_outputs.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/Phase 2A sidecar 未接入。

当前状态：旧 structured pipeline hardening 已完成但不再决定新主路径。failure isolation、secret redaction、保留上一版有效输出的原则仍适用于 Markdown-only sidecar。

#### Step 10 非阻塞问题点

1. `state_schema.py` 的 number validation 使用 `isinstance(value, (int, float))`。新主路径不依赖 state schema，但 legacy structured code 若保留仍存在该问题。
2. CLI partial success 策略已固定。新主路径不再需要 summary/readable partial success 分支。

---

### Step 11：实现 DeepSeek / OpenAI-compatible provider

状态：已完成，已 commit 并 push。

```text
commit: 41e2968
message: Implement DeepSeek provider
```

修改文件：

```text
llm/deepseek_provider.py
llm/openai_compatible_provider.py
llm/llm_settings.py
testCodes/test_llm_provider_deepseek.py
```

完成内容：

- `OpenAICompatibleProvider` 实现 chat completions request builder、`generate_text()`、`generate_json()`、response parsing、typed error mapping；
- `DeepSeekProvider` 是 DeepSeek 默认 endpoint/model 的窄包装；
- `LLMSettings.read_api_key()` 只从 `DEEPSEEK_API_KEY` 环境变量读取 key；不写 settings/config/session/docs/logs；
- HTTP transport 是可注入 `HTTPJSONClient`，默认 stdlib `UrllibHTTPJSONClient` 仅供后续手动 smoke；自动测试全部使用 fake client；
- CLI 仍只支持 mock，未开放真实 provider 参数；
- 不接 UI 或 Phase 2A sidecar。

Error mapping：

```text
missing key -> MissingAPIKeyError
malformed response JSON -> LLMMalformedResponseError
invalid JSON/schema contract -> LLMSchemaError
401/403 -> LLMAuthenticationError
429 -> LLMRateLimitError
timeout -> LLMTimeoutError
5xx/其他 provider failure -> LLMProviderError
```

验证结果：

```text
testCodes/test_llm_provider_deepseek.py：PASS
compileall llm + testCodes/test_llm_provider_deepseek.py：PASS
testCodes/test_llm_cli.py：PASS
testCodes/test_llm_pipeline.py：PASS
testCodes/test_llm_outputs.py：PASS
testCodes/test_llm_chunker.py：PASS
testCodes/test_llm_provider_mock.py：PASS
testCodes/test_ui_support.py：PASS
testCodes/test_backends.py --skip-faster-smoke：PASS，whisper.cpp availability 可按环境 SKIP
git diff --check：PASS
ASR 主链路文件：无修改
docs 文件：无修改
真实 API 自动测试：未执行，全部 HTTP 行为由 fake client 覆盖
UI / Phase 2A sidecar：未接入
merge：未执行
```

审查结论：Step 11 通过，不需要 Step 11 v2。

当前保留价值：`generate_text()` 是新 Markdown-only 主路径所需能力。`generate_json()` 不再作为稳定主路径。

#### Step 11 非阻塞问题点

1. `UrllibHTTPJSONClient` 遇到 HTTPError 且响应 body 不是 JSON 时，后续 `_normalize_response()` 可能先尝试解析 body，从而抛 `LLMMalformedResponseError`，而不是按 status code 映射为 `LLMProviderError` / `LLMAuthenticationError` / `LLMRateLimitError`。新主路径仍使用该 HTTP client，后续如遇真实错误响应，可优先修 status classification。
2. `OpenAICompatibleProvider` 的默认 endpoint/model 当前也是 DeepSeek 默认值。对当前项目目标没有问题，因为真实 provider 首站就是 DeepSeek；如果未来支持多个 OpenAI-compatible provider，可把通用默认值和 DeepSeek 默认值拆得更干净。

---

### Step 12：本地手动真实 API smoke test

状态：已完成。

完成内容：

- 使用真实 `DEEPSEEK_API_KEY` 在本地 shell 环境变量中执行最小真实 provider smoke；
- `DeepSeekProvider.generate_text()` 成功返回 `OK`；
- `DeepSeekProvider.generate_json()` 成功返回 `{'ok': True, 'message': 'smoke'}`；
- `DEEPSEEK_API_KEY` 已 unset；
- 精确 secret scan 显示真实 API key 未出现在项目文件或 smoke report；
- generic grep 只命中源码中的 `DEEPSEEK_API_KEY`、`Authorization`、`Bearer` 组装代码、文档说明、测试 fake key 和 external/whisper.cpp 相关非 LLM server 示例；
- 一次性脚本 `run_smoketest_6_22.sh` 已删除；
- `git status --short --untracked-files=all` 最终干净；
- 未修改 docs、ASR 主链路、UI 或 Phase 2A sidecar；
- 未修改 evidence layer；
- disposable pipeline session 已删除；
- 真实 pipeline smoke 在 SSL 修复前失败，最终 Step 12 完成标准以最小 provider text/json smoke 为准。

最终成功设置：

```text
Python: venv/bin/python 3.13.7
SSL_CERT_FILE=$(venv/bin/python -m certifi)
REQUESTS_CA_BUNDLE=$SSL_CERT_FILE
DEEPSEEK_API_KEY=<shell env only, not written to file>
Provider: DeepSeekProvider
Endpoint: https://api.deepseek.com/chat/completions
Model: deepseek-chat
```

关键成功输出：

```text
TEXT_SMOKE_OK 'OK'
JSON_SMOKE_OK {'ok': True, 'message': 'smoke'}
```

API 调用失效 / 阻塞情况记录：

```text
1. 未设置 certifi CA bundle 时，Python urllib 请求 DeepSeek 失败：ssl.SSLCertVerificationError / CERTIFICATE_VERIFY_FAILED / unable to get local issuer certificate。
2. 直接访问 https://api.deepseek.com 且不携带 Authorization header 时返回 401 Unauthorized；这说明 TLS 已通过、服务端已到达，但裸请求未授权。
3. SSL 未修复前，disposable session pipeline smoke 中 summary/readable 均失败，只生成 llm_errors.log / readable_zh_errors.log；disposable session 随后删除，未保留输出。
4. sudo 运行 /Applications/Python 3.13/Install Certificates.command 未能修复系统 Python certifi，报 certifi uninstall-no-record-file；最终采用 venv certifi + SSL_CERT_FILE / REQUESTS_CA_BUNDLE 解决。
```

审查结论：Step 12 通过。

---

### Step 13：旧方向真实课堂 structured pipeline 验证尝试

状态：已尝试，未完成，已被 Markdown-only 方向取代。保留本节作为影响记录，不删除。

真实 session：

```text
/Users/smter-mac/Documents/ClassroomTranscriber/outputs/2026-06-16_13-02-52
```

session 文件：

```text
raw.txt
clean.txt
session.log
config.json
```

`clean.txt` 基本情况：

```text
406 lines
17253 bytes
parser output: LINES 406
chunker output: CHUNKS 1
chunk-0001 chars=8317 source_lines=406 start=0.03 end=2327.09
```

第一次真实 structured pipeline 结果：

```text
SUMMARY_SUCCESS False
SUMMARY_CHUNKS 0
SUMMARY_ERROR Expected a list of strings.
READABLE_SUCCESS False
READABLE_CHUNKS 0
READABLE_ERROR Invalid segment status: clean
EVIDENCE_UNCHANGED True
LLM_OUTPUT_FILES ['llm_errors.log', 'readable_zh_errors.log']
```

错误日志：

```text
llm_errors.log: LLMSchemaError Expected a list of strings.
readable_zh_errors.log: LLMSchemaError Invalid segment status: clean
```

结构调试结果：

```text
SUMMARY SECTION RESPONSE STRUCTURE:
title: str
summary: str
key_terms: list[str]
action_items: list[str]
review_questions: list[str]
unclear_parts: list[str]

READABLE RESPONSE STRUCTURE:
segments: list[dict]
segments[0].segment_id: int
segments[0].start: float
segments[0].end: float
segments[0].source_text: str
segments[0].text_zh: str
segments[0].annotations: str
segments[0].evidence: str
segments[0].status: str

Observed status values:
clean
unclear
```

结论：

```text
真实 DeepSeek 能返回可 parse JSON，但其内层 JSON 字段结构、字段类型和 enum 值不稳定。
旧结构化路线需要 prompt + normalization + schema validation 才能维持，但这会让程序稳定性依赖模型输出形态。
用户决定不继续沿结构化 JSON/state 路线 harden。
```

保留的潜在影响：

```text
1. 旧 structured pipeline 代码仍在仓库中，后续测试或调用可能继续生成 legacy 文件。
2. 旧 CLI 仍按 summary/readable/both mock structured 任务设计，后续应改为 Markdown-only 或旁路。
3. state_schema / renderer / structured output writer 仍可能被 tests 引用；迁移时不要误删导致无关回归。
4. Step 13 暴露的真实 LLM 输出不稳定问题，是 Markdown-only 方向的直接依据。
5. 后续不应把 Step 13A 做成 JSON normalization hardening；应改为 Markdown-only sidecar 主路径。
```

---

### Static direction update：简化为 Markdown-only LLM sidecar

状态：已完成，已 commit 并 push。

```text
commit: aef99b4
message: Simplify LLM contract to Markdown sidecar
```

完成内容：

- 将 static LLM 合同改为 Markdown-only sidecar；
- 唯一稳定输出收敛为：

```text
session_dir/llm/readable_zh.md
session_dir/llm/log.md
```

- 明确稳定主路径为：

```text
clean.txt snapshot -> provider.generate_text() -> readable_zh.md -> UI Markdown preview
```

- 明确 `generate_json()`、结构化 state、机器可读 key_terms/action_items、segment annotation、segment status、局部冻结/删除/合并、review state、落盘 HTML 均不是稳定主路径。

---

## 3. ACTIVE：Step 13A - 实现 Markdown-only LLM sidecar 主路径

状态：ACTIVE。

### 3.1 目标

按最新 static 合同，实现最小稳定 LLM Markdown sidecar 主路径：

```text
session_dir/clean.txt
-> parse_clean_transcript()
-> chunk_transcript()
-> build Markdown prompt
-> provider.generate_text()
-> basic sanity / secret safety check
-> atomic write session_dir/llm/readable_zh.md
-> append sanitized session_dir/llm/log.md
```

本 Step 不是继续修旧 JSON schema / state pipeline。不得让程序稳定性依赖模型生成 JSON、enum 或结构化字段。

---

### 3.2 约束

必须满足：

```text
不修改 raw.txt / clean.txt / session.log / config.json
LLM 输出只写入 session_dir/llm/readable_zh.md 和 session_dir/llm/log.md
API key 仍只从 shell env 读取
API key 不写入 repo/docs/session/logs/Markdown/终端输出/异常消息
不接 QWebEngineView
不生成落盘 HTML
不生成 JSON state
不生成 key_terms/action_items JSON
不做 segment annotation/status
不做局部冻结/局部删除/局部合并
不做结构化 review state
```

允许复用：

```text
parse_clean_transcript()
chunk_transcript()
provider.generate_text()
MockProvider text path
existing atomic text write / path containment helpers
sanitize_text()
```

需要旁路或停止作为主路径：

```text
provider.generate_json()
SummaryState / ReadableTranscriptState 作为主输出 state
state_schema validation
structured renderer
summary/readable/review JSON/HTML outputs
old summary/readable/both CLI tasks
```

---

### 3.3 建议实现范围

建议新增或改造文件：

```text
llm/markdown_pipeline.py
llm/prompt_templates.py
llm/output_writer.py
llm_postprocess.py
testCodes/test_llm_markdown_pipeline.py
testCodes/test_llm_cli.py
```

可保留 legacy 文件不删：

```text
llm/summary_pipeline.py
llm/readable_pipeline.py
llm/state_schema.py
llm/renderer.py
```

但 legacy 文件不得作为新主路径。

---

### 3.4 输出合同

成功后只要求：

```text
session_dir/llm/readable_zh.md
session_dir/llm/log.md
```

`readable_zh.md` 内容：

```text
中文 Markdown
适合课堂中实时查看或课后复习
可以包含当前课堂/片段总结、重要提醒、任务、可能的截止日期、疑似 ASR 错误提示
不要求固定章节名
不要求机器解析
```

`log.md` 内容：

```text
sanitized timestamped diagnostics
provider status
success/failure
error type
不得包含 API key、Authorization header、raw request、raw response、完整 prompt
```

失败时：

```text
保留上一版 readable_zh.md
向 log.md 追加 sanitized failure record
返回 success=False 或非 0 CLI exit code
```

---

### 3.5 推荐测试命令

Codex 执行前必须先检查：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
git branch --show-current
git status --short --untracked-files=all
```

若分支不是 `llm-sidecar-phase1` 或工作区不干净，立即停止汇报。

建议测试：

```bash
source venv/bin/activate

venv/bin/python testCodes/test_llm_markdown_pipeline.py
venv/bin/python testCodes/test_llm_provider_mock.py
venv/bin/python testCodes/test_llm_chunker.py
venv/bin/python testCodes/test_llm_provider_deepseek.py
venv/bin/python testCodes/test_llm_cli.py
venv/bin/python -m compileall -q llm testCodes llm_postprocess.py

git diff --check
git status --short --untracked-files=all
```

若 legacy tests 仍运行，应确保旧测试要么继续通过，要么被明确重写为 Markdown-only 合同。不得留下既要求 legacy structured outputs、又要求 Markdown-only outputs 的冲突测试合同。

---

### 3.6 真实 API 手动复测命令

自动测试不得真实调用 DeepSeek。真实 API 只由用户本地手动运行。

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
export SSL_CERT_FILE="$(venv/bin/python -m certifi)"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
export DEEPSEEK_API_KEY='用户本地手动设置，不写入文件'

venv/bin/python - <<'PY'
from pathlib import Path
import hashlib
from llm.deepseek_provider import DeepSeekProvider
from llm.markdown_pipeline import run_markdown_pipeline

session_dir = Path("/Users/smter-mac/Documents/ClassroomTranscriber/outputs/2026-06-16_13-02-52")
evidence_files = ["raw.txt", "clean.txt", "session.log", "config.json"]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

before = {name: digest(session_dir / name) for name in evidence_files}

result = run_markdown_pipeline(
    session_dir=session_dir,
    provider=DeepSeekProvider(),
    max_chars=12000,
)
print("MARKDOWN_SUCCESS", result.success)
print("MARKDOWN_CHUNKS", result.chunks_processed)
print("MARKDOWN_ERROR", result.error)

after = {name: digest(session_dir / name) for name in evidence_files}
print("EVIDENCE_UNCHANGED", before == after)

llm_dir = session_dir / "llm"
if llm_dir.exists():
    print("LLM_OUTPUT_FILES", sorted(p.name for p in llm_dir.iterdir() if p.is_file()))
PY

unset DEEPSEEK_API_KEY
```

预期输出：

```text
MARKDOWN_SUCCESS True
EVIDENCE_UNCHANGED True
LLM_OUTPUT_FILES 包含 readable_zh.md 和 log.md
```

---

### 3.7 完成标准

全部满足才可标记 Step 13A 完成：

```text
Markdown-only pipeline 可用 mock provider 成功生成 readable_zh.md / log.md
Markdown-only pipeline provider failure 保留上一版 readable_zh.md 并写 log.md
raw.txt / clean.txt / session.log / config.json unchanged
API key 不出现在 readable_zh.md / log.md / stdout / stderr
自动测试不真实调用 API
不生成新的 JSON state / HTML / review / key_terms/action_items 输出作为主路径
真实 DeepSeek 手动复测可生成 readable_zh.md
UI 尚未接入或仅按后续 Step 接入
```

---

### 3.8 风险

重点防止：

- 继续沿旧 JSON normalization hardening 方向开发；
- 保留旧 summary/readable/both 作为默认 CLI 主路径；
- 同时维护过多输出文件导致状态复杂度反弹；
- API key 泄露到 `readable_zh.md`、`log.md`、stdout/stderr、异常消息；
- 真实课堂 transcript 或 LLM 输出被提交到 repo；
- 为 LLM sidecar 修改 ASR 主链路。

---

## 4. 后续步骤简要内容

### Step 14：接入 UI Markdown preview

目标：UI 读取 `session_dir/llm/readable_zh.md` 并显示。可使用 QTextBrowser 兼容路径，但不引入 QWebEngineView，不落盘 HTML。

---

### Step 15：实现 live refresh worker

目标：录音期间可选 live refresh；single in-flight request；pending snapshot coalescing；最小刷新间隔；atomic replace `readable_zh.md`；失败保留上一版。

---

### Step 16：长时间课堂稳定性测试

目标：验证 ASR 主链路、Markdown sidecar、UI preview 在真实课堂长度下稳定；检查 Stop drain、queue backlog、麦克风释放、UI 稳定性。

---

### Step 17：确认默认开关策略

目标：决定 LLM 功能默认关闭、默认开启或按 provider/API key 状态启用。默认必须不影响 ASR 主链路。

---

## 5. 提交与推送规则

每个明确 checkpoint 完成后建议提交：

```bash
git status --short --untracked-files=all
git diff --check
git diff --name-only
```

确认没有模型、outputs、日志、API key、venv、build、dist 被 staged。

Step 13A 应一个明确 commit，建议信息：

```text
Implement Markdown-only LLM sidecar pipeline
```

自检通过后 push 到：

```text
origin/llm-sidecar-phase1
```
