[toc]



# LLMsteps.md

## 0. 当前结论

这次任务应定位为 **DeepSeek / OpenAI-compatible LLM 后处理模块**，不是实时转写主链路的一部分。

关键判断：

1. **Phase 1A：After-stop 中文总结**：当前第一优先级。Stop complete 后读取完整 `clean.txt`，生成中文结构化 summary。
2. **Phase 1B：After-stop 中文阅读稿**：在 Phase 1A 基础上新增完整中文 readable transcript 派生稿，真实状态源是 state JSON，Markdown / HTML 是 renderer 派生视图。
3. **Phase 2A：动态中文阅读稿 sidecar**：录音期间可选运行，默认关闭，只读 newline-complete `clean.txt` 快照和当前 state，不进入实时 ASR 主链路。
4. **Phase 2B：应用内 Markdown / HTML 渲染**：Phase 2A 稳定后接 PySide6 `QTextBrowser.setHtml()`，Typora / 外部浏览器只用于开发 spot check，不引入 `QWebEngineView`。
5. **DeepSeek / OpenAI-compatible API**：代码里不应把具体模型名或 endpoint 写死，应做成 env/provider settings 可配置。
6. **中文输出**：Phase 1A 和 Phase 1B 默认中文。

必须保护的边界：

- 不修改实时 ASR 主链路参数。
- 不让 LLM 进入 `TranscriptionEngine` 的 chunk 转写 worker 主循环。
- 不覆盖、追加、截断、重命名、删除或替换 `raw.txt` / `clean.txt` / `session.log` / `config.json`。
- API key 只从 `DEEPSEEK_API_KEY` 读取，不写入仓库、`/docs`、settings、`config/settings.json`、session 输出、request/response log、Markdown、HTML、JSON state 或错误日志。
- API 失败、断网、超时、取消任务，都不得影响 Start/Stop、麦克风释放、session 文件关闭和 UI 主线程。
- Renderer failure、schema validation failure、sidecar backlog、应用关闭也不得影响 ASR 主链路。

---

## 1. 临时需求与 goalForNextLevel.md 的关系判断

| 临时需求 | 与现有目标关系 | 判断 | 实现条件 |
|---|---|---|---|
| 使用 DeepSeek / OpenAI-compatible API | 已有方向 | 一致 | provider 层抽象；模型名和 endpoint 可配置 |
| After-stop 中文总结 | 已有 P0 | Phase 1A | Stop 完成、clean.txt 完整后再运行 summary pipeline |
| After-stop 中文阅读稿 | 新增细化 | Phase 1B | state JSON 为真实状态源，本地 renderer 输出 Markdown / HTML |
| 录音期间动态中文阅读稿 | 新增细化 | Phase 2A | 默认关闭；可选 sidecar；不阻塞实时转写；不默认逐 chunk 调 LLM |
| 应用内 HTML 预览 | 新增细化 | Phase 2B | 使用 PySide6 `QTextBrowser.setHtml()`，不依赖 Typora/外部浏览器/QWebEngineView |
| 总结按“阶段1、阶段2...”组织 | 已有 timeline/section summary 的具体化 | Phase 1A | section chunker 按时间段输出中文阶段标题和时间戳 |

严格结论：**Phase 1A/1B after-stop 产物先做；Phase 2A 动态 sidecar 后做；Phase 2B UI 预览最后做。** 原因是 after-stop 风险最低；动态 sidecar 和 UI 预览如果过早实现，容易把 LLM 拉进实时链路或 UI 主线程，破坏现有稳定性边界。

---

## 2. 按 goalForNextLevel.md，LLM 接入后应实现的功能

Phase 1A 必须实现：

1. 从已有 session 读取 `clean.txt`、`config.json`，必要时读取 `session.log` 元数据。
2. 将 transcript 按时间戳和字符/token 预算切分。
3. 调用 DeepSeek provider 生成分段结构化结果。
4. 用 map-reduce 方式生成全局总结。
5. 输出 `llm/summary.md`。
6. 输出机器可读 JSON：`summary.json`、`sections.json`、`key_terms.json`、`action_items.json`。
7. 输出 `llm_errors.log`，记录 API 错误、超时、解析失败、取消任务。
8. 输出必须包含 timestamp grounding。
9. 输出必须包含：阶段性总结、关键术语、重要细节、行动项、复习问题、可能 ASR 错误/不确定部分。
10. 没有 API key 时给清晰错误，不崩溃。
11. 单元测试使用 mock provider，不真实打 API。
12. UI 集成暂缓，CLI/mock pipeline 和真实 API smoke test 之后再接。

Phase 1B 必须规划：

1. 读取完整 `clean.txt`。
2. LLM 输出结构化 readable transcript state。
3. 写入 `readable_zh_final_state.json`。
4. 本地 renderer 生成 `readable_zh_final.md`、`readable_zh_final.html`、`review_zh_final.md`、`review_zh_final.html`。
5. `readable_zh_errors.log` 记录 LLM/schema/renderer 错误。
6. Markdown / HTML 是派生视图，不是真实状态源。

DeepSeek 可以承担的任务：

- 英文课堂 transcript → 中文阶段总结。
- 英文课堂 transcript → 中文总结、中文阅读稿、动态中文阅读稿 sidecar。
- 提取 key terms、assignment、deadline、project instruction、professor emphasized points。
- 生成 review questions。
- 标记疑似 ASR 错误，但只能作为 possible correction，不能改写 clean.txt。
- 对长课做 map-reduce summary。

DeepSeek 不应该承担的任务：

- 不参与 Whisper 实时识别。
- 不替换 clean 层 dedup。
- 不自动修改 raw/clean。
- 不自动上传音频。
- 不在测试中真实调用 API。
- 不做跨 session RAG；这应留到 session browser/search 之后。
- 不直接自由生成并覆盖整个 Markdown / HTML。
- 不把 Markdown 当真实状态源。

---

## 3. 实施前统一约束

默认运行目录：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
```

默认虚拟环境：

```bash
source venv/bin/activate
```

如果本地实际路径不同，以 `pwd` 和当前 repo 根目录为准。

基础测试命令建议：

```bash
venv/bin/python testCodes/test_ui_support.py
venv/bin/python testCodes/test_backends.py
```

LLM 模块新增后建议增加：

```bash
venv/bin/python testCodes/test_llm_chunker.py
venv/bin/python testCodes/test_llm_pipeline.py
venv/bin/python testCodes/test_llm_outputs.py
venv/bin/python testCodes/test_llm_provider_mock.py
```

真实 API 手动 smoke test 只在本地有 `DEEPSEEK_API_KEY` 时运行：

```bash
DEEPSEEK_API_KEY=... venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID>
```

---

## 4. 步骤清单

当前进度：

```text
已完成：Step 1、Step 2、Step 3
当前下一步：Step 4
```

### Step 1：冻结需求和架构边界

状态：已完成。

**当前步骤目标**
把“必须做”和“后续做”切开，避免 Codex 直接把动态 sidecar 接进实时主链路。

**当前步骤具体干什么**

- 确认 Phase 1A 目标是 after-stop 中文总结。
- 确认 Phase 1B 目标是 after-stop 中文阅读稿。
- 把动态中文阅读稿列为 Phase 2A sidecar，不进入初始 UI 主流程。
- 把应用内渲染列为 Phase 2B，不依赖 Typora、外部浏览器或 `QWebEngineView`。
- 明确默认输出语言为中文。
- 明确 `clean.txt` 是第一输入源，`raw.txt` 只作为可选 evidence，不参与第一版 summary。
- 明确 `raw.txt`、`clean.txt`、`session.log`、`config.json` 是不可变 evidence layer。

**如果要用 Codex 应该写什么**

- 让 Codex 只更新设计文档/roadmap，不改生产代码。
- 要求 Codex 明确“不进入实时主链路、不改 audio/chunk/dedup/backend 参数”。
- 要求 Codex 输出需要改哪些文件、哪些文件禁止改、测试命令和回滚方式。

**验收信号**

- `docs/LLM_POSTPROCESSING_DESIGN.md` 或 roadmap 中明确 Phase 1A/1B/2A/2B。
- 文档明确 Phase 1A/1B 不包含动态 sidecar。
- 文档明确所有 LLM 任务失败不影响 raw/clean/session/config。

---

### Step 2：更新设计文档

状态：已完成。

**当前步骤目标**
先做设计文档，减少 Codex 直接乱改 UI 和主链路的风险，并统一 Phase 1A / Phase 1B / Phase 2A / Phase 2B。

**当前步骤具体干什么**

更新相关设计文档：

```text
docs/LLM_POSTPROCESSING_DESIGN.md
docs/goalForNextLevel.md
docs/user_understand.md
docs/工程细节.md
docs/LLMsteps.md
```

**如果要用 Codex 应该写什么**

- 让 Codex 基于 `goalForNextLevel.md`、`工程细节.md`、当前源码写设计文档。
- 要求 Codex 不写具体 API key，不调用真实 API。
- 要求 Codex 在文档里列出生产代码最小改动路径和禁止修改路径。

**验收信号**

- 文档包含 provider、chunker、pipeline、writer、state schema、renderer、UI、tests。
- 文档明确 `DEEPSEEK_API_KEY` 只从环境变量读取。
- 文档明确 Markdown / HTML 是派生视图，state JSON 是真实状态源。
- 文档明确 Phase 2A / 2B 后置。

---

### Step 3：创建独立 llm/ 模块骨架

状态：已完成。

**当前步骤目标**
建立独立模块，不污染 `TranscriptionEngine`、`WhisperCppBackend` 和 dedup 逻辑。

**当前步骤具体干什么**

新增目录：

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

第一轮只写接口、数据结构、空实现或 mockable 实现。不要实现 parser、provider HTTP、writer、renderer、pipeline、CLI、UI 或动态 sidecar。

**如果要用 Codex 应该写什么**

- 让 Codex 新增 `llm/` 包，并保持主转写代码不变。
- 要求 Codex 只做可导入的骨架，不接 UI。
- 要求 Codex 跑 import smoke test、`compileall` 和原有基线测试。

**验收信号**

```bash
venv/bin/python - <<'PY'
import llm
from llm.provider_base import LLMProvider
from llm.llm_settings import LLMSettings
from llm.transcript_chunker import chunk_transcript
print('PASS: llm skeleton imports')
PY
```

预期输出：

```text
PASS: llm skeleton imports
```

---

### Step 4：实现 transcript parser / chunker

状态：下一步。

**当前步骤目标**
把 `clean.txt` 解析成带 start/end/text 的结构，并按时间/字符预算切块。

**当前步骤具体干什么**

- 复用或兼容当前 timestamp 格式：`[12.34s -> 18.90s] text`。
- 支持无 timestamp 行 fallback。
- 支持按最大字符数、最大时间跨度切块。
- 保留每个 chunk 的 `start_time`、`end_time`、原始行列表。
- 只读测试 fixture 或临时目录，不读取或修改真实 session evidence。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 parser/chunker 和测试。
- 要求测试覆盖 timestamp line、multi-line、empty file、no timestamp fallback、chunk boundary。
- 要求不修改 `transcript_store.py` 的现有行为。
- 要求不接 provider、pipeline、CLI、UI。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_chunker.py
```

预期输出：

```text
PASS: transcript line parser
PASS: transcript chunking
PASS: no timestamp fallback
```

---

### Step 5：实现 provider interface 和 mock provider

状态：待做。

**当前步骤目标**
让后续 pipeline 可以通过统一 provider interface 调用 mock provider 或真实 provider，但本步骤不接真实 API。

**当前步骤具体干什么**

- 完善 `LLMProvider` 接口和 typed LLM errors。
- 新增或完善 mock provider。
- mock provider 返回固定结构化响应。
- 支持错误注入：missing API key、timeout、HTTP/provider error、invalid JSON、schema validation failure。
- 不要求存在 `DEEPSEEK_API_KEY`。
- 不发送网络请求。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 provider interface 和 mock provider。
- 要求 Codex 不实现 DeepSeek HTTP。
- 要求 Codex 使用 deterministic 固定响应和临时目录。
- 要求 Codex 测试异常消息和日志中不包含 API key。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_provider_mock.py
```

预期输出：

```text
PASS: mock provider success
PASS: mock provider failure
PASS: provider errors are typed
PASS: no real API call
```

---

### Step 6：实现 output writer、state schema、renderer

状态：待做。

**当前步骤目标**
稳定生成 `llm/` 目录、Markdown/JSON/HTML/state/error log，不碰 raw/clean/session/config。

**当前步骤具体干什么**

生成：

```text
outputs/<SESSION_ID>/llm/
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

约束：

- 不修改 `raw.txt`。
- 不修改 `clean.txt`。
- 不修改 `session.log`。
- 不修改 `config.json`。
- 不写 API key。
- 写文件失败时记录错误并返回失败状态。
- state JSON 是真实状态源，Markdown / HTML 是派生视图。
- LLM 不直接自由生成并覆盖整个 Markdown / HTML。
- 本地 renderer 负责输出 Markdown / HTML。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 `output_writer.py`、`state_schema.py`、`renderer.py` 和对应测试。
- 要求测试显式扫描输出目录，确认没有 API key 字符串。
- 要求测试确认 raw/clean/session/config 内容前后一致。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_outputs.py
```

预期输出：

```text
PASS: llm output directory created
PASS: summary markdown written
PASS: json outputs written
PASS: raw and clean unchanged
PASS: api key not written
PASS: readable state written
PASS: readable/review markdown and html rendered
PASS: renderer failure preserves previous valid output
```

---

### Step 7：实现 Phase 1A after-stop summary mock pipeline

状态：待做。

**当前步骤目标**
在不真实调用 API 的情况下跑通 Phase 1A summary pipeline。

**当前步骤具体干什么**

- 完善 `prompt_templates.py` 中的 Phase 1A prompt builder。
- 分段 prompt 输出 JSON。
- 全局 prompt 输出 Markdown。
- 明确中文输出、timestamp grounding、不编造、不补充 transcript 外知识。
- 明确 ASR 修正只能进入 unclear / possible correction。
- `summary_pipeline.py` 执行：读取 clean → chunk → section summaries → global summary → output writer。
- 支持失败注入：模拟 API error、timeout、invalid JSON。
- 只使用 mock provider。

**如果要用 Codex 应该写什么**

- 让 Codex 先做 mock pipeline，不接 DeepSeek。
- 要求 Codex 测试成功路径和失败路径。
- 要求 Codex 保证失败时 `llm_errors.log` 有记录，raw/clean 不变。
- 要求 Codex 测试 prompt 中包含 no hallucination、timestamp、Chinese output、possible correction 等约束关键词。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_provider_mock.py
venv/bin/python testCodes/test_llm_pipeline.py
```

预期输出：

```text
PASS: mock provider success
PASS: mock provider failure
PASS: pipeline writes summary
PASS: api error isolated
PASS: timestamp grounding instruction
PASS: chinese output instruction
```

---

### Step 8：实现 Phase 1B after-stop readable transcript mock pipeline

**当前步骤目标**
在不真实调用 API 的情况下跑通 Phase 1B readable transcript pipeline。

**当前步骤具体干什么**

- 完善 Phase 1B prompt builder。
- 读取完整 `clean.txt`。
- 使用 mock provider 生成结构化 readable transcript state。
- schema validation 后写入 `readable_zh_final_state.json`。
- 通过本地 renderer 生成 `readable_zh_final.md`、`readable_zh_final.html`、`review_zh_final.md`、`review_zh_final.html`。
- 失败时写 `readable_zh_errors.log`。
- Markdown / HTML 只是派生视图，state JSON 是真实状态源。

**如果要用 Codex 应该写什么**

- 让 Codex 只做 after-stop readable mock pipeline。
- 要求 Codex 不做 rolling sidecar。
- 要求 Codex 不让 LLM 直接覆盖完整 Markdown / HTML。
- 要求 Codex 测试 renderer deterministic、HTML escaping、annotation rendering。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_pipeline.py
venv/bin/python testCodes/test_llm_outputs.py
```

预期输出：

```text
PASS: readable final state written
PASS: readable markdown rendered
PASS: readable html rendered
PASS: review markdown rendered
PASS: review html rendered
PASS: raw and clean unchanged
```

---

### Step 9：新增 CLI 入口并用 mock 跑通

状态：待做。

**当前步骤目标**
先用 CLI 验证 Phase 1A/1B 后处理，不直接碰 UI。

**当前步骤具体干什么**

新增 CLI 入口：

```text
llm_postprocess.py
```

支持 mock 模式：

```bash
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --output-language zh
```

**如果要用 Codex 应该写什么**

- 让 Codex 新增 CLI，默认 mock provider 可跑通。
- 要求 Codex 不改 UI，不改 ASR 主链路。
- 要求 Codex 给出 dry-run 或 mock 模式，方便无 API key 测试。
- 要求 Codex 不要求 `DEEPSEEK_API_KEY` 即可跑 mock。

**验收信号**

```bash
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock
```

预期输出：

```text
LLM post-processing complete
summary: outputs/<SESSION_ID>/llm/summary.md
```

并且：

```bash
git diff -- raw.txt clean.txt
```

预期：无 raw/clean 改动。

---

### Step 10：补齐 mock tests、error injection、secret leakage tests

状态：待做。

**当前步骤目标**  
在接真实 API 前补齐可重复自动测试，确保 failure isolation 和 secret safety。

**当前步骤具体干什么**

- 覆盖 mock provider success/failure。
- 覆盖 timeout、provider error、invalid JSON、schema validation failure。
- 覆盖 renderer failure 保留上一版有效输出。
- 扫描输出，确认没有 API key。
- 确认 `raw.txt`、`clean.txt`、`session.log`、`config.json` 不变化。
- 确认 Phase 1A/1B 不生成 live sidecar 输出。

**如果要用 Codex 应该写什么**

- 让 Codex 增加测试，不接真实 API。
- 要求 Codex 使用临时目录和固定响应。
- 要求 Codex 测试失败路径和 secret leakage。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_chunker.py
venv/bin/python testCodes/test_llm_provider_mock.py
venv/bin/python testCodes/test_llm_pipeline.py
venv/bin/python testCodes/test_llm_outputs.py
```

预期输出：

```text
PASS: mock provider success
PASS: mock provider failure
PASS: schema validation failure isolated
PASS: renderer failure preserves previous valid output
PASS: api key not written
PASS: raw/clean/session/config unchanged
```

---

### Step 11：实现 DeepSeek / OpenAI-compatible provider

状态：待做。

**当前步骤目标**  
接入真实 provider adapter，但自动测试仍然只用 monkeypatch/mock HTTP client，不真实调用 API。

**当前步骤具体干什么**

- 从 `DEEPSEEK_API_KEY` 读取 API key。
- 支持 `DEEPSEEK_MODEL` 或 provider settings 中的 model 字段。
- 支持 configurable endpoint，不硬编码为永久常量。
- 设置 timeout。
- 捕获 HTTP error、timeout、JSON parse error。
- 不在日志中打印 Authorization header。
- 不在 request/response log 中写 API key。
- 不引入不必要的第三方 HTTP 依赖。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 DeepSeek/OpenAI-compatible provider。
- 要求 Codex 不真实调用 API，只用 monkeypatch/mock HTTP client 测试。
- 要求 Codex 增加安全测试：异常消息、日志、输出文件中不得含 API key。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_provider_mock.py
```

预期输出：

```text
PASS: missing api key returns clear error
PASS: provider builds request without leaking key
PASS: provider parses response
PASS: provider handles timeout
```

---

### Step 12：本地手动真实 API smoke test

**当前步骤目标**  
在 mock tests 全部通过后，用一个可丢弃的真实 session 做手动 API smoke test。

**当前步骤具体干什么**

- 在 shell 中临时设置 `DEEPSEEK_API_KEY`。
- 对一个 disposable completed session 运行 CLI。
- 检查 `session_dir/llm/` 输出。
- 扫描 repo diff、session 输出、日志，确认没有 API key。
- 不把 key 写入 settings、config、Markdown、HTML、JSON state 或错误日志。

**如果要用 Codex 应该写什么**

- 让 Codex 只在用户明确提供/确认环境变量时运行 smoke test。
- 要求 Codex 不打印 key。
- 要求 Codex 记录命令结果和输出文件列表。

**验收信号**

```bash
DEEPSEEK_API_KEY=... venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID>
```

预期：

```text
outputs/<SESSION_ID>/llm/summary.md
outputs/<SESSION_ID>/llm/summary.json
outputs/<SESSION_ID>/llm/sections.json
outputs/<SESSION_ID>/llm/readable_zh_final_state.json
```

---

### Step 13：验证 Phase 1A / 1B 真实课堂 session 输出质量

状态：待做。

**当前步骤目标**  
避免“能跑但质量不可判断”，对 1-2 个真实课堂 session 做人工质量验收。

**当前步骤具体干什么**

- 记录 summary generation time、input char/token estimate、output length、API failures。
- 记录 section 数量、timestamp reference 数量、action item 数量、unclear part 数量。
- 人工检查 summary 是否覆盖主线。
- 人工检查 action items 是否乱编。
- 人工检查 timestamp 是否可回溯。
- 人工检查 readable/review 视图是否适合复习和审计。
- 不上传真实课堂内容。

**如果要用 Codex 应该写什么**

- 让 Codex 增加轻量 metrics，不引入复杂 benchmark 框架。
- 要求 Codex 不上传真实课堂内容。
- 要求 Codex 给出 mock data 测试。

**验收信号**

```text
summary 覆盖主线
timestamp 可追溯
action items 没有明显乱编
unclear parts 有帮助
readable/review 视图区分清楚
```

---

### Step 14：实现 Phase 2A rolling sidecar

状态：待做，必须在 Phase 1A/1B 稳定后。

**当前步骤目标**  
实现动态中文阅读稿 sidecar，但必须作为可选 sidecar，不进入主链路。

**当前步骤具体干什么**

设计为：

```text
LLM Dynamic Chinese Readable Sidecar
interval_seconds = 30
clean_context_window_seconds = 40
editable_window_seconds = 60
input = newline-complete clean.txt snapshot + editable state + glossary + revision
output = llm/live_readable_zh.md + llm/live_readable_zh.html
```

实现规则：

- 默认关闭。
- 只处理已经写入 clean 的 newline-complete 文本。
- 用 high-water mark、state revision 和 frozen boundary 防止重复处理。
- API 失败只写 `llm_errors.log`，不影响 ASR。
- 输出每段保留原始时间范围。
- 不在每 10 秒 chunk 后调用 LLM。
- 最多一个 in-flight API request。
- pending snapshot coalescing：只保留最新 pending snapshot，丢弃过时 snapshot。
- frozen segment 不可修改，editable segment 可在窗口内 replace/annotate/mark_duplicate。
- 动态文件使用 atomic replace。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 sidecar job，不要改 ASR worker。
- 要求 Codex 增加配置开关，例如 `enable_live_readable_zh=false`。
- 要求 Codex 用 mock provider 测试 interval、snapshot、editable/frozen、防重复、失败隔离。

**验收信号**

测试：

```bash
venv/bin/python testCodes/test_llm_live_readable.py
```

预期输出：

```text
PASS: live readable sidecar disabled by default
PASS: translates only new clean lines
PASS: preserves timestamp range
PASS: api failure isolated
PASS: no duplicate translation
PASS: pending snapshot coalescing
PASS: frozen segment cannot be rewritten
PASS: atomic replace preserves previous valid output
```

手动验收：

- 录音运行时 UI 不卡。
- 按 configurable `interval_seconds` 最多触发一次 LLM job。
- `llm/live_readable_zh.md` / `.html` 按结构化 state 派生生成。
- Stop 后 summary 仍可正常生成。

---

### Step 15：验证 single worker、coalescing、atomic replace、final reconciliation

**当前步骤目标**  
验证 Phase 2A 不会形成 backlog，不会破坏上一版有效输出，并能在 Stop 后收敛到最终状态。

**当前步骤具体干什么**

- 最多一个 in-flight API request。
- 如果上一次 request 未返回，只保留最新 pending snapshot。
- 丢弃过时 pending snapshot。
- 使用 atomic replace 写动态派生文件。
- API/schema/renderer failure 保留上一版有效输出。
- Stop complete 后执行 final reconciliation。
- 最终生成 `readable_zh_final.md` / `.html` 和 review final outputs。

**如果要用 Codex 应该写什么**

- 让 Codex 测试 single worker、coalescing、atomic replace、final reconciliation。
- 要求 Codex 不改 ASR worker。
- 要求 Codex 不操作 Qt widget。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_live_readable.py
```

预期输出：

```text
PASS: at most one in-flight request
PASS: pending snapshot coalescing
PASS: atomic replace preserves previous valid output
PASS: stop final reconciliation
PASS: sidecar failure does not affect ASR
```

---

### Step 16：实现 Phase 2B 应用内 QTextBrowser 预览

状态：待做，必须在 Phase 2A 稳定后。

**当前步骤目标**  
把 readable/review HTML 预览接进 PySide6 UI，但仍保持后台线程和状态隔离。

**当前步骤具体干什么**

- 新增 LLM 中文阅读稿 tab。
- 阅读模式 / 审计模式切换。
- sidecar 开关。
- Provider 状态和最后更新时间。
- Open Markdown / Open HTML。
- 使用 `QTextBrowser.setHtml()` 渲染本地 renderer 生成的 HTML。
- Typora 和外部浏览器只作为开发 spot check。
- 不引入 `QWebEngineView`。
- sidecar worker 发 signal，Qt 主线程读取 HTML 并更新 widget。

**如果要用 Codex 应该写什么**

- 让 Codex 最小改动 `ui_app.py`，不要改 `TranscriptionEngine` 的 worker loop。
- 要求 Codex 使用 Qt signal/bridge 或现有安全模式更新 UI。
- 要求 Codex 保证关闭窗口时 LLM job 可安全结束或标记取消。

**验收信号**

手动 UI 测试：

1. Start Recording。
2. Stop Recording。
3. 等 Stop complete。
4. 点击 Generate Summary。
5. UI 不冻结。
6. 完成后 Open Summary 可打开文件。
7. LLM 中文阅读稿 tab 可显示 HTML。
8. 断网/无 API key 时 UI 显示 Failed，但 app 不崩溃。
9. 再次 Start Recording 仍可正常工作。

回归测试：

```bash
venv/bin/python testCodes/test_ui_support.py
```

---

### Step 17：长时间课堂稳定性测试

状态：待做。

**当前步骤目标**
在真实课堂长度下验证 ASR 主链路、after-stop LLM、动态 sidecar、UI preview 的稳定性。

**当前步骤具体干什么**

- 长时间录音测试。
- 观察 queue backlog、Stop drain、麦克风释放。
- 检查 LLM failure isolation。
- 检查 sidecar 是否形成 backlog。
- 检查 UI 主线程是否稳定。
- 检查 raw/clean/session/config 是否保持 evidence layer 不变。

**验收信号**

```text
ASR 可独立运行
Stop drain 正常完成
麦克风正常释放
UI 不冻结
LLM 错误只进入 LLM error log
raw/clean/session/config 不被修改
```

---

### Step 18：确认稳定后再考虑默认开关策略

状态：待做。

**当前步骤目标**
在长时间稳定性验证后，再决定 LLM 功能默认关闭、默认开启、或按 provider/API key 状态启用。

**当前步骤具体干什么**

- 汇总 Phase 1A/1B 质量结果。
- 汇总 Phase 2A 稳定性结果。
- 汇总 UI preview 结果。
- 评估隐私提示、API key 缺失提示、成本提示。
- 决定是否继续默认关闭动态 sidecar。

**验收信号**

```text
默认开关策略有明确理由
隐私和 API key 提示清晰
失败隔离仍然成立
不影响 ASR 主链路
```

---

## 5. 推荐执行顺序压缩版

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
15. 验证 single worker、coalescing、atomic replace、final reconciliation。
16. 实现 Phase 2B 应用内 QTextBrowser 预览。
17. 长时间课堂稳定性测试。
18. 确认稳定后再考虑默认开关策略。

---

## 6. 风险与回滚

### 主要风险

1. **把 LLM 放进实时主链路**：会增加延迟、API 失败传播、UI 卡顿风险。
2. **API key 泄露**：可能出现在 log、request dump、session config、git diff。
3. **LLM hallucination**：summary/readable transcript 可能编造课堂没有说过的内容。
4. **输出覆盖 evidence**：如果改写 clean/raw/session/config，会破坏可追溯性。
5. **UI 线程阻塞**：如果直接在按钮回调里调用 API，窗口会卡死。
6. **动态 sidecar 重复处理或 backlog**：如果不记录 high-water mark、revision 和 pending snapshot coalescing，会重复处理或堆积请求。
7. **Markdown 被误当状态源**：真实状态源必须是 state JSON，Markdown / HTML 只是 renderer 派生视图。
8. **LLM 直接覆盖 Markdown/HTML**：必须使用结构化输出、schema validation、本地 renderer。
9. **Typora/浏览器/QWebEngineView 被当产品依赖**：正式 UI 应使用 `QTextBrowser.setHtml()`。
10. **一次性实现过多功能**：应按 Step 4、5、6... 小步推进，避免跳到 API/UI/sidecar。

### 回滚策略

- LLM 所有代码保持在 `llm/`、`llm_postprocess.py`、少量 UI glue 中。
- 如果真实 API 或 UI 集成出问题，先禁用 UI 按钮，保留 CLI/mock pipeline。
- 如果 `llm/` 影响打包，先从 spec 中排除或延后打包集成。
- 如果 Phase 2A 动态 sidecar 不稳定，保留 Phase 1A/1B after-stop 输出，删除/关闭 live readable sidecar。
- 任何时候 raw/clean/session 主链路必须可单独运行。

### 阶段性文档同步

每个实现阶段完成后，按需同步文档，但不要把文档同步当作新的功能 Step 插入主路线。同步范围通常是：

```text
README.md
docs/工程细节.md
docs/goalForNextLevel.md
docs/LLM_POSTPROCESSING_DESIGN.md
docs/LLMsteps.md
docs/user_understand.md
```

**验收信号**

```bash
git status --short
git diff --stat
venv/bin/python testCodes/test_ui_support.py
venv/bin/python testCodes/test_llm_chunker.py
venv/bin/python testCodes/test_llm_pipeline.py
venv/bin/python testCodes/test_llm_outputs.py
venv/bin/python testCodes/test_llm_provider_mock.py
```

预期：

- 所有测试 PASS。
- 没有模型文件、outputs、大型日志、API key 被 staged。
- 可以 commit。

建议 commit message：

```text
Add optional LLM post-processing pipeline
```
