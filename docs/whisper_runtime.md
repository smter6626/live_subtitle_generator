# whisper_runtime.md

最后更新：2026-06-16  
文档角色：动态执行状态（runtime state）

本文件用于记录 Classroom Live Transcriber / whisper 项目的**已执行步骤、唯一 active 任务、当前任务的可执行说明、后续步骤摘要**。每完成一个步骤后，只追加/更新状态，不删除已完成记录。

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

---

## 1. 当前 checkpoint

```text
当前分支：llm-sidecar-phase1
当前 checkpoint：Step 3 已完成并已 push
唯一 ACTIVE 任务：Step 4 - 实现 transcript parser / chunker
```

已完成：

```text
Step 1：冻结需求和架构边界
Step 2：更新设计文档
Step 3：创建独立 llm/ 模块骨架
```

当前尚未实现：

```text
parser / chunker 业务逻辑
mock provider
真实 HTTP API
summary pipeline
output writer
renderer
CLI
UI
Phase 2A rolling sidecar
```

当前 `llm/` package 只代表可导入骨架和模块边界。

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

## 3. ACTIVE：Step 4 - 实现 transcript parser / chunker

状态：ACTIVE。

### 3.1 目标

实现 `llm/transcript_chunker.py` 中的 parser / chunker 业务逻辑，并新增 focused tests。

Step 4 只处理纯文本解析和 deterministic chunking，不接 provider，不接 API，不写 summary，不接 UI。

输入：

```text
clean.txt 文本
```

典型 timestamp 行格式：

```text
[12.34s -> 18.90s] transcript text
```

输出：

```text
TranscriptLine[]
TranscriptChunk[]
```

必须保留 evidence text，不得改写 `clean.txt`。

---

### 3.2 允许修改范围

原则上允许：

```text
llm/transcript_chunker.py
testCodes/test_llm_chunker.py
```

如果 Codex 认为骨架中的 dataclass / type signature 需要微调，也允许最小修改：

```text
llm/__init__.py
```

但必须说明理由。

---

### 3.3 禁止修改范围

不要修改：

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

不要修改：

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
mock provider
DeepSeek HTTP
OpenAI-compatible HTTP
summary pipeline
output writer
renderer
CLI
UI
Phase 2A sidecar
```

---

### 3.4 Step 4 实现要求

#### 3.4.1 Parser

实现 clean transcript parser：

- 解析 `[12.34s -> 18.90s] text`；
- `start_time` / `end_time` 使用 float 秒；
- `text` 保留原文文本，不做语义改写；
- 跳过空行；
- 对无 timestamp 行做 fallback，而不是让整个 job 失败；
- malformed timestamp 行保留为 text-only entry；
- 记录原始行号或 line index，方便后续 evidence tracking；
- 不读取真实 session，测试使用字符串或临时 fixture。

建议数据字段：

```text
TranscriptLine:
  line_index
  raw_line
  text
  start_time: float | None
  end_time: float | None
```

如果现有骨架字段不同，可以在保持最小兼容的前提下调整。

#### 3.4.2 Chunker

实现 deterministic chunking：

- 输入 `TranscriptLine[]`；
- 按输入顺序稳定切块；
- 支持最大字符数预算；
- 支持最大时间跨度预算；
- 每个 chunk 包含：
  - `chunk_id`
  - `start_time`
  - `end_time`
  - `lines`
  - `text`
  - 原始行范围或 line indexes；
- 无 timestamp lines 也必须能进入 chunk；
- 空 transcript 返回空列表；
- 不跨越预算时尽量保持连续上下文；
- 不做 LLM prompt overlap 逻辑，除非作为显式可选参数且默认关闭；
- 不访问网络；
- 不写文件。

---

### 3.5 建议测试文件

新增：

```text
testCodes/test_llm_chunker.py
```

测试必须可直接用：

```bash
venv/bin/python testCodes/test_llm_chunker.py
```

运行，不依赖 pytest。

测试输出建议使用现有项目风格：

```text
PASS: transcript line parser
PASS: transcript parser skips empty lines
PASS: no timestamp fallback
PASS: malformed timestamp fallback
PASS: empty transcript
PASS: deterministic chunking
PASS: chunk respects max chars
PASS: chunk respects max duration
PASS: chunk preserves source line indexes
```

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
```

预期当前分支：

```text
llm-sidecar-phase1
```

Step 4 测试：

```bash
venv/bin/python testCodes/test_llm_chunker.py
```

预期：所有 Step 4 focused tests PASS。

语法检查：

```bash
venv/bin/python -m compileall -q llm testCodes/test_llm_chunker.py
```

预期：无输出，退出码为 0。

原有回归：

```bash
venv/bin/python testCodes/test_ui_support.py
venv/bin/python testCodes/test_backends.py --skip-faster-smoke
```

预期：

```text
无新增 FAIL
whisper.cpp availability 在 CLI 未配置时可 SKIP
```

修改范围检查：

```bash
git diff --name-only
git status --short --untracked-files=all
```

预期只涉及：

```text
llm/transcript_chunker.py
testCodes/test_llm_chunker.py
```

如果出现其他文件，必须说明原因。

---

### 3.7 Step 4 完成标准

全部满足才可标记 Step 4 已完成：

```text
parser 能解析标准 timestamp 行
parser 能处理 no timestamp fallback
parser 能处理 malformed timestamp fallback
parser 跳过空行
chunker deterministic
chunker 支持 max chars
chunker 支持 max duration
chunk 保留 line indexes / source evidence
testCodes/test_llm_chunker.py PASS
compileall PASS
原有 baseline tests 无新增 FAIL
ASR 主链路无修改
未接 provider / API / UI / writer / renderer / sidecar
```

---

### 3.8 风险

重点防止：

- 直接复用或修改 `transcript_store.py` 的写入逻辑；
- 修改 `stream_transcribe.py` 中现有 timestamp parser 或 backend parser；
- 把 chunker 做成读取真实 session 的高层 pipeline；
- 提前生成 prompt；
- 提前接 provider；
- 提前写 `session_dir/llm/`；
- 为了测试而读取真实 outputs；
- 对 text 做语义清洗或翻译；
- chunking 结果不 deterministic。

---

### 3.9 回滚

如果 Step 4 实现方向错误：

```bash
git diff -- llm/transcript_chunker.py testCodes/test_llm_chunker.py
```

只回滚本步骤相关文件：

```bash
git restore llm/transcript_chunker.py
rm -f testCodes/test_llm_chunker.py
```

不要使用：

```bash
git reset --hard
git clean -fd
```

---

## 4. 后续步骤简要内容

### Step 5：实现 provider interface 和 mock provider

目标：

- 完善 `LLMProvider` 接口和 typed errors；
- 新增 mock provider；
- 支持 deterministic success response；
- 支持错误注入；
- 不真实调用 API；
- 不要求 `DEEPSEEK_API_KEY`。

验收：

```bash
venv/bin/python testCodes/test_llm_provider_mock.py
```

---

### Step 6：实现 output writer、state schema、renderer

目标：

- 写 `session_dir/llm/` 下的 Markdown / JSON / HTML / state / error log；
- 不修改 raw/clean/session/config；
- state JSON 是真实状态源；
- Markdown / HTML 是派生视图；
- 支持 atomic replace；
- 测试 API key 不泄露。

验收：

```bash
venv/bin/python testCodes/test_llm_outputs.py
```

---

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
文档同步可以并入同 Step commit
```

当前下一次合理 commit：

```text
Implement LLM transcript parser and chunker
```

push：

```bash
git push
```
