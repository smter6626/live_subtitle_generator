[toc]



# LLMsteps.md

## 0. 当前结论

这次任务应定位为 **DeepSeek / OpenAI-compatible LLM 后处理模块**，不是实时转写主链路的一部分。

关键判断：

1. **录音结束且转文字结束后生成详细总结**：与 `goalForNextLevel.md` 完全一致，属于 P0 主功能。
2. **每一分钟输出一次中文翻译**：不属于原文第一版明确要求，属于新增/细化需求；只有在“可选、异步、旁路、不阻塞、不覆盖 clean/raw”的实现方式下才不冲突。
3. **DeepSeek V4 API**：与文档中的“DeepSeek V4 API 或 OpenAI-compatible API”方向一致，但代码里不应把具体模型名写死，应做成 settings/env 可配置。
4. **中文输出**：`goalForNextLevel.md` 把 summary 输出语言列为未确认项；现在可以明确第一版输出语言默认为中文，但必须保留后续可配置空间。

必须保护的边界：

- 不修改实时 ASR 主链路参数。
- 不让 LLM 进入 `TranscriptionEngine` 的 chunk 转写 worker 主循环。
- 不覆盖 `raw.txt` / `clean.txt`。
- API key 不写入仓库、不写入 session 输出、不写入 request/response log。
- API 失败、断网、超时、取消任务，都不得影响 Start/Stop、麦克风释放、session 文件关闭和 UI 主线程。

---

## 1. 临时需求与 goalForNextLevel.md 的关系判断

| 临时需求 | 与现有目标关系 | 判断 | 实现条件 |
|---|---|---|---|
| 使用 DeepSeek V4 API | 已有方向 | 一致 | provider 层做成 DeepSeek / OpenAI-compatible；模型名可配置 |
| 每一分钟输出一次对话的中文翻译 | 新增需求 | 条件性兼容 | 必须是可选 sidecar job；不能阻塞实时转写；不能默认逐 chunk 调 LLM |
| 录音结束且转文字结束后输出详细总结 | 已有 P0 | 完全一致 | Stop 完成、clean.txt 完整后再运行 summary pipeline |
| 总结按“阶段1、阶段2...”组织 | 已有 timeline/section summary 的具体化 | 一致 | section chunker 按时间段输出中文阶段标题和时间戳 |
| 输出中文翻译/中文总结 | goal 中未确认项的决策 | 属于补充确认 | 第一版默认中文，后续保留 output_language 配置 |

严格结论：**“课后总结”先做；“每分钟中文翻译”后做。** 原因是课后总结完全贴合 P0，风险低；每分钟翻译接近在线实时功能，如果先做，容易把 LLM 拉进实时链路，破坏现有稳定性边界。

---

## 2. 按 goalForNextLevel.md，LLM 接入后应实现的功能

第一版必须实现：

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
12. UI 中 Stop 完成后允许点击 `Generate Summary`，并提供 `Open Summary` 与 LLM 状态显示。

DeepSeek 可以承担的任务：

- 英文课堂 transcript → 中文阶段总结。
- 英文课堂 transcript → 每 60 秒一段中文翻译/解释性翻译。
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

---

## 3. 实施前统一约束

默认运行目录：

```bash
cd /Users/smter-mac/personalAPPS/whisper
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

### Step 1：冻结 LLM 第一版范围

**当前步骤目标**  
把“必须做”和“后续做”切开，避免 Codex 直接把每分钟翻译接进实时主链路。

**当前步骤具体干什么**

- 确认第一版目标是 after-stop summary。
- 把每分钟中文翻译列为 Phase 2 sidecar，不进入初始 UI 主流程。
- 明确默认输出语言为中文。
- 明确 `clean.txt` 是第一输入源，`raw.txt` 只作为可选 evidence，不参与第一版 summary。

**如果要用 Codex 应该写什么**

- 让 Codex 只更新设计文档/roadmap，不改生产代码。
- 要求 Codex 明确“不进入实时主链路、不改 audio/chunk/dedup/backend 参数”。
- 要求 Codex 输出需要改哪些文件、哪些文件禁止改、测试命令和回滚方式。

**验收信号**

- `docs/LLM_POSTPROCESSING_DESIGN.md` 或 roadmap 中明确 Phase 1/Phase 2。
- 文档明确 Phase 1 不包含每分钟翻译。
- 文档明确所有 LLM 任务失败不影响 raw/clean/session。

---

### Step 2：建立 LLM 设计文档

**当前步骤目标**  
先做设计文档，减少 Codex 直接乱改 UI 和主链路的风险。

**当前步骤具体干什么**

新增：

```text
docs/LLM_POSTPROCESSING_DESIGN.md
```

内容覆盖：

- provider interface
- DeepSeek settings
- transcript parsing / chunking
- prompt templates
- output schema
- privacy / API key
- error handling
- CLI workflow
- UI workflow
- tests
- rollback

**如果要用 Codex 应该写什么**

- 让 Codex 基于 `goalForNextLevel.md`、`工程细节.md`、当前源码写设计文档。
- 要求 Codex 不写具体 API key，不调用真实 API。
- 要求 Codex 在文档里列出生产代码最小改动路径。

**验收信号**

- 新文档存在。
- 文档包含 provider、chunker、pipeline、writer、UI、tests 六部分。
- 文档明确 `DEEPSEEK_API_KEY` 只从环境变量读取。

---

### Step 3：创建 LLM 模块骨架

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
```

第一轮只写接口、数据结构、空实现或 mockable 实现。

**如果要用 Codex 应该写什么**

- 让 Codex 新增 `llm/` 包，并保持主转写代码不变。
- 要求 Codex 只做可导入的骨架，不接 UI。
- 要求 Codex 跑 import smoke test。

**验收信号**

```bash
venv/bin/python - <<'PY'
import llm
from llm.provider_base import LLMProvider
from llm.transcript_chunker import chunk_transcript
print('PASS')
PY
```

预期输出：

```text
PASS
```

---

### Step 4：实现 transcript parser 与 chunker

**当前步骤目标**  
把 `clean.txt` 解析成带 start/end/text 的结构，并按时间/字符预算切块。

**当前步骤具体干什么**

- 复用或兼容当前 timestamp 格式：`[12.34s -> 18.90s] text`。
- 支持无 timestamp 行 fallback。
- 支持按最大字符数、最大时间跨度切块。
- 保留每个 chunk 的 `start_time`、`end_time`、原始行列表。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 parser/chunker 和测试。
- 要求测试覆盖 timestamp line、multi-line、empty file、no timestamp fallback、chunk boundary。
- 要求不修改 `transcript_store.py` 的现有行为。

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

### Step 5：实现 output writer

**当前步骤目标**  
稳定生成 `llm/` 目录和 Markdown/JSON/error log，不碰 raw/clean。

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
```

约束：

- 不修改 `raw.txt`。
- 不修改 `clean.txt`。
- 不写 API key。
- 写文件失败时记录错误并返回失败状态。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 `output_writer.py` 和对应测试。
- 要求测试显式扫描输出目录，确认没有 API key 字符串。
- 要求测试确认 raw/clean 内容前后一致。

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
```

---

### Step 6：实现 prompt templates 与结构化 schema

**当前步骤目标**  
让模型输出可解析、可测试、可追溯，不生成泛泛总结。

**当前步骤具体干什么**

- 分段 prompt 输出 JSON。
- 全局 prompt 输出 Markdown。
- 明确要求中文输出。
- 明确要求 timestamp grounding。
- 明确要求不编造、不补充 transcript 外知识。
- 明确 ASR 修正只能进入 `unclear_parts`。

**如果要用 Codex 应该写什么**

- 让 Codex 集中改 `prompt_templates.py`，不要把 prompt 写进 UI。
- 要求 Codex 增加 prompt payload 构造测试。
- 要求 Codex 测试 prompt 中包含 no hallucination、timestamp、Chinese output、possible correction 等约束关键词。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_pipeline.py
```

预期输出至少包含：

```text
PASS: section prompt payload
PASS: global prompt payload
PASS: timestamp grounding instruction
PASS: chinese output instruction
```

---

### Step 7：实现 mock provider 与 summary pipeline

**当前步骤目标**  
在不真实调用 API 的情况下跑通完整 pipeline。

**当前步骤具体干什么**

- 定义 `LLMProvider.generate()` 或等价接口。
- 写 `MockProvider` 返回固定 section JSON 和 summary markdown。
- `summary_pipeline.py` 执行：读取 clean → chunk → section summaries → global summary → output writer。
- 支持失败注入：模拟 API error、timeout、invalid JSON。

**如果要用 Codex 应该写什么**

- 让 Codex 先做 mock pipeline，不接 DeepSeek。
- 要求 Codex 测试成功路径和失败路径。
- 要求 Codex 保证失败时 `llm_errors.log` 有记录，raw/clean 不变。

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
```

---

### Step 8：实现 DeepSeek provider

**当前步骤目标**  
接入真实 DeepSeek API，但仍保持 provider 抽象和错误隔离。

**当前步骤具体干什么**

- 从 `DEEPSEEK_API_KEY` 读取 API key。
- 支持 `DEEPSEEK_MODEL` 或 settings 中的 model 字段。
- 设置 timeout。
- 捕获 HTTP error、timeout、JSON parse error。
- 不在日志中打印 Authorization header。
- 不在 request/response log 中写 API key。

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

手动真实 API smoke test：

```bash
DEEPSEEK_API_KEY=... venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID>
```

预期：

```text
outputs/<SESSION_ID>/llm/summary.md
outputs/<SESSION_ID>/llm/summary.json
outputs/<SESSION_ID>/llm/sections.json
outputs/<SESSION_ID>/llm/llm_errors.log
```

---

### Step 9：实现 CLI 入口

**当前步骤目标**  
先用 CLI 验证 LLM 后处理，不直接碰 UI。

**当前步骤具体干什么**

新增：

```text
llm_postprocess.py
```

支持：

```bash
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID>
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --provider mock
venv/bin/python llm_postprocess.py --session outputs/<SESSION_ID> --output-language zh
```

**如果要用 Codex 应该写什么**

- 让 Codex 新增 CLI，默认 mock provider 可跑通。
- 要求 Codex 不改 UI，不改 ASR 主链路。
- 要求 Codex 给出 dry-run 或 mock 模式，方便无 API key 测试。

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

### Step 10：接入 UI 的 Generate Summary / Open Summary / Cancel

**当前步骤目标**  
把 after-stop summary 接进 UI，但仍保持后台线程和状态隔离。

**当前步骤具体干什么**

- Stop complete 后启用 `Generate Summary`。
- 点击后启动独立 LLM worker thread。
- UI 显示：Idle / Running / Failed / Complete / Cancelled。
- Logs tab 显示进度。
- `Open Summary` 打开 `llm/summary.md`。
- `Cancel` 设置取消标志；已完成的安全文件可保留，未完成状态写入 `llm_errors.log`。

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
7. 断网/无 API key 时 UI 显示 Failed，但 app 不崩溃。
8. 再次 Start Recording 仍可正常工作。

回归测试：

```bash
venv/bin/python testCodes/test_ui_support.py
```

---

### Step 11：Phase 2 增加每分钟中文翻译 sidecar

**当前步骤目标**  
实现用户临时提出的“一分钟一次中文翻译”，但必须作为可选 sidecar，不进入主链路。

**当前步骤具体干什么**

设计为：

```text
LLM Live Translation Sidecar
interval_seconds = 60
input = clean.txt 增量内容或 UI clean line buffer snapshot
output = llm/live_translation.md + llm/live_translation.jsonl
```

实现规则：

- 默认关闭。
- 只处理已经写入 clean 的文本。
- 用 last_processed_timestamp 或 line offset 防止重复翻译。
- API 失败只写 `llm_errors.log`，不影响 ASR。
- 输出每段保留原始时间范围。
- 不在每 10 秒 chunk 后调用 LLM。

**如果要用 Codex 应该写什么**

- 让 Codex 实现 sidecar job，不要改 ASR worker。
- 要求 Codex 增加配置开关，例如 `enable_live_translation=false`。
- 要求 Codex 用 mock provider 测试 interval、offset、防重复、失败隔离。

**验收信号**

测试：

```bash
venv/bin/python testCodes/test_llm_live_translation.py
```

预期输出：

```text
PASS: live translation disabled by default
PASS: translates only new clean lines
PASS: preserves timestamp range
PASS: api failure isolated
PASS: no duplicate translation
```

手动验收：

- 录音运行时 UI 不卡。
- 每 60 秒最多触发一次 LLM job。
- `llm/live_translation.md` 按时间段追加中文翻译。
- Stop 后 summary 仍可正常生成。

---

### Step 12：增加 LLM 质量/成本 benchmark

**当前步骤目标**  
避免“能跑但质量不可判断”，给真实课堂 session 做基本质量记录。

**当前步骤具体干什么**

记录：

- summary generation time
- input char/token estimate
- output length
- API failures
- number of sections
- number of timestamp references
- action item count
- unclear part count
- manual quality notes

输出：

```text
llm/llm_metrics.json
llm/quality_check.md
```

**如果要用 Codex 应该写什么**

- 让 Codex 增加轻量 metrics，不引入复杂 benchmark 框架。
- 要求 Codex 不上传真实课堂内容。
- 要求 Codex 给出 mock data 测试。

**验收信号**

```bash
venv/bin/python testCodes/test_llm_outputs.py
```

预期新增：

```text
PASS: llm metrics written
PASS: timestamp reference count computed
PASS: no transcript upload in benchmark tests
```

人工验收：

- 抽 1-2 节真实课堂 session。
- 检查 summary 是否覆盖主线。
- 检查 action items 是否乱编。
- 检查 timestamp 是否可回溯。
- 检查 unclear parts 是否真的有用。

---

### Step 13：文档更新与 git 阶段提交

**当前步骤目标**  
把阶段成果固定下来，方便回滚。

**当前步骤具体干什么**

更新：

```text
README.md
工程细节.md
goalForNextLevel.md 或 docs/LLM_POSTPROCESSING_DESIGN.md
```

说明：

- LLM 是可选后处理。
- API key 用 `DEEPSEEK_API_KEY`。
- 输出目录是 `llm/`。
- 不修改 raw/clean。
- UI 使用 Generate Summary。
- 每分钟中文翻译如果实现，说明默认关闭。

**如果要用 Codex 应该写什么**

- 让 Codex 只更新文档，不改功能代码。
- 要求 Codex 给出 git diff 摘要。
- 要求 Codex 建议 commit message。

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

---

## 5. 推荐执行顺序压缩版

1. 先写 `docs/LLM_POSTPROCESSING_DESIGN.md`。
2. 建 `llm/` 模块骨架。
3. 做 parser/chunker。
4. 做 output writer。
5. 做 mock provider + summary pipeline。
6. 做 CLI：`llm_postprocess.py --session ... --provider mock`。
7. 接 DeepSeek provider。
8. 做真实 API smoke test。
9. 接 UI：Generate/Open/Cancel。
10. 质量验收后再做每分钟中文翻译 sidecar。
11. 文档更新。
12. 测试全过后 commit/push。

---

## 6. 风险与回滚

### 主要风险

1. **把 LLM 放进实时主链路**：会增加延迟、API 失败传播、UI 卡顿风险。
2. **API key 泄露**：可能出现在 log、request dump、session config、git diff。
3. **LLM hallucination**：summary 可能编造课堂没有说过的内容。
4. **输出覆盖 evidence**：如果改写 clean/raw，会破坏可追溯性。
5. **UI 线程阻塞**：如果直接在按钮回调里调用 API，窗口会卡死。
6. **一分钟翻译重复处理**：如果不记录 offset/timestamp，会重复翻译重叠内容。

### 回滚策略

- LLM 所有代码保持在 `llm/`、`llm_postprocess.py`、少量 UI glue 中。
- 如果真实 API 或 UI 集成出问题，先禁用 UI 按钮，保留 CLI/mock pipeline。
- 如果 `llm/` 影响打包，先从 spec 中排除或延后打包集成。
- 如果每分钟翻译不稳定，保留 after-stop summary，删除/关闭 live translation sidecar。
- 任何时候 raw/clean/session 主链路必须可单独运行。
