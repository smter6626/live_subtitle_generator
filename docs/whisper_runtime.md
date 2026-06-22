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
当前 checkpoint：Step 11 已完成并已 push
唯一 ACTIVE 任务：Step 12 - 本地手动真实 API smoke test
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
```

当前尚未实现：

```text
真实 API smoke test
UI
Phase 2A rolling sidecar
```

当前 `llm/` package 已包含：

```text
provider interface
mock provider
DeepSeek / OpenAI-compatible provider
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

完成内容：CLI `--task both` partial success 策略固定；CLI 不打印 traceback/prompt/raw request/raw response；provider exception 中 fake secret redacted；summary/readable failure 不破坏上一版有效输出；state validation 增强：重复 `section_id` / `segment_id` 拒绝、`end < start` 拒绝、readable `revision >= 1`、默认 revision 改为 `1`；`CLIMockProvider` 保持 CLI smoke-only provider；隐藏 `--mock-fail-schema` 仅用于 failure-policy 测试。

验证结果：`test_llm_cli.py` PASS；`test_llm_pipeline.py` PASS；`test_llm_outputs.py` PASS；compileall PASS；LLM 回归 PASS；原有 UI/backend 回归无新增 FAIL；network/API grep 无输出；API key grep 无输出；ASR 主链路无修改；docs 无修改；真实 API/UI/Phase 2A sidecar 未接入。

#### Step 10 非阻塞问题点

1. `state_schema.py` 的 number validation 使用 `isinstance(value, (int, float))`。Python 中 `bool` 是 `int` 的子类，所以 `True/False` 理论上会被当作合法 number。当前测试和正常 pipeline 不会触发；后续 schema strictness 可改为排除 bool。
2. CLI partial success 策略已固定，但将来接真实 provider 后，summary/readable 的 partial output 对用户可能需要更清晰的 terminal wording，例如区分 “summary failed, readable succeeded, overall failed”。当前 Step 10 已满足 mock CLI hardening，不阻塞 Step 11。

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

#### Step 11 非阻塞问题点

1. `UrllibHTTPJSONClient` 遇到 HTTPError 且响应 body 不是 JSON 时，后续 `_normalize_response()` 可能先尝试解析 body，从而抛 `LLMMalformedResponseError`，而不是按 status code 映射为 `LLMProviderError` / `LLMAuthenticationError` / `LLMRateLimitError`。当前 fake-client 测试使用 `json_body={}` 覆盖了 status mapping；Step 12 真实 API smoke 可观察真实错误响应形态，必要时后续改为优先按 status code 分类，再解析 body。
2. `OpenAICompatibleProvider` 的默认 endpoint/model 当前也是 DeepSeek 默认值。对当前项目目标没有问题，因为真实 provider 首站就是 DeepSeek；如果未来真的支持多个 OpenAI-compatible provider，可以把通用默认值和 DeepSeek 默认值拆得更干净。

---

## 3. ACTIVE：Step 12 - 本地手动真实 API smoke test

状态：ACTIVE。

### 3.1 目标

在所有 mock/provider 自动测试通过后，使用 disposable session 和真实 `DEEPSEEK_API_KEY` 做一次最小真实 API smoke。

本步骤是人工/本地验证步骤，不建议 Codex 自动执行真实 API。Codex 可生成 smoke 脚本或命令，但真实 API key 由用户在本地 shell 设置，不写入仓库，不写入 docs，不写入任何 session/config/log。

---

### 3.2 原则

必须满足：

```text
不把 API key 写入 repo
不把 API key 写入 docs
不把 API key 写入 settings/config/session 输出
不把 API key 写入 logs
不把 API key 打印到 stdout/stderr
不提交任何包含 key 的文件
使用 disposable session
真实 smoke 后扫描 repo 和 session_dir
失败不得修改 evidence layer
CLI 仍不默认开放真实 provider，除非单独受控实现真实 provider CLI path
```

---

### 3.3 推荐执行方式

优先创建一个临时 smoke 脚本或一次性 Python command，只调用 provider 的 `generate_text()` / `generate_json()`，不先接入 CLI。

推荐流程：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
git status --short --untracked-files=all
export DEEPSEEK_API_KEY='在本地 shell 粘贴，不写入文件'
venv/bin/python - <<'PY'
from llm.deepseek_provider import DeepSeekProvider

provider = DeepSeekProvider()
text = provider.generate_text(
    system_prompt="You are a concise test assistant.",
    user_prompt="Reply with exactly: OK"
)
print("TEXT_SMOKE_OK", text[:20])

obj = provider.generate_json(
    system_prompt="Return JSON only.",
    user_prompt='Return {"ok": true, "message": "smoke"}.',
    schema_name="smoke_test"
)
print("JSON_SMOKE_OK", obj)
PY
unset DEEPSEEK_API_KEY
```

注意：上面的 command 不应打印 key。若 provider 返回内容异常或 JSON parse 失败，记录错误类型即可，不要打印 headers/request body/key。

---

### 3.4 smoke 后扫描

执行后运行：

```bash
git status --short --untracked-files=all
grep -RInE 'sk-[A-Za-z0-9_-]{16,}|DEEPSEEK_API_KEY|Authorization|Bearer ' . \
  --exclude-dir=.git \
  --exclude-dir=venv \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' || true
```

预期：

- 不应出现真实 key；
- 允许出现源码中的环境变量名、Authorization/Bearer 组装代码、测试 fake key；
- 不应出现新增未跟踪文件；
- 不应修改 docs/session/evidence 文件。

---

### 3.5 可选 disposable session smoke

如果 provider text/json smoke 通过，可再用一个临时 disposable session 测试 pipeline。但不要直接改 CLI 默认 provider 行为。

建议只写临时一次性 Python command，使用 `run_summary_pipeline()` 和 `run_readable_pipeline()` 传入 `DeepSeekProvider()`。

要求：

```text
session_dir 必须在 /tmp 或项目外临时目录，或项目内明确未提交的 disposable 目录
raw.txt / clean.txt / session.log / config.json 建立即固定，不被修改
只检查 session_dir/llm/ sidecar outputs
运行后扫描 secret leakage
测试结束可删除 disposable session
```

---

### 3.6 Step 12 完成标准

全部满足才可标记 Step 12 已完成：

```text
真实 DeepSeek provider text smoke 成功或失败类型明确
真实 DeepSeek provider json smoke 成功或失败类型明确
没有 API key 泄露到 stdout/stderr/repo/session/log
没有把 API key 写入任何文件
没有修改 docs
没有修改 ASR 主链路
没有修改 evidence layer
真实 smoke 后 git status 干净，或仅有明确 disposable 文件且已删除
grep secret scan 无真实 key 命中
若执行 disposable session pipeline smoke，llm outputs 仅在 session_dir/llm/ 下生成
```

---

### 3.7 风险

重点防止：

- 把真实 key 粘贴进源码、docs、runtime、README、test、shell 脚本；
- 把 key 打印出来；
- 把 request headers/body 写入 log；
- 把真实 smoke 输出误提交；
- 将 CLI 默认开放真实 provider，导致误调用真实 API；
- 在项目 outputs 里留下带真实测试内容的 session 并误提交。

---

## 4. 后续步骤简要内容

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

Step 12 是人工 smoke checkpoint，除非为了新增受控 smoke helper，否则通常不需要代码 commit。
