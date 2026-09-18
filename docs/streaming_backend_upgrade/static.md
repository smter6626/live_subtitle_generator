# Streaming Backend Upgrade — Static 稳定合同

## 1. 合同身份

- Task ID：`streaming-backend-upgrade`
- 合同状态：`AUTHORIZED`
- Human Owner：本仓库 Owner / 本任务当前用户
- Reviewer / Orchestrator：当前与 Human Owner 对接的 Reviewer 对话
- Executor：由 Human Owner 转交 Reviewer 编译 prompt 的其他执行对话；Executor 不兼任最终 Reviewer
- 适用范围：`live_subtitle_generator` 的 streaming backend 分阶段升级，以及为未来 iPadOS 复用而建立的跨平台 backend 边界
- 合同版本：`1.0`
- 最后一次授权变更：2026-09-11，Human Owner 明确要求后续实际操作使用 Static + Runtime 规划执行，并锁定现有 `update_plan`

### Locked investigation identity

- Canonical path：`docs/streaming_backend_upgrade/update_plan.md`
- Source commit：`1e0cdd9fda1870a8277a553c3f7af7cc67480fe9`
- Git blob：`536ff6412166bce9c77c2b42e8cf981d2fccbc18`
- SHA-256：`ae4566dd27dca2ba96d5beedd8d35ab490a46e51188fa82cbd05eef4d7917c40`
- 状态：`FROZEN INPUT`
- 规则：移动文件不改变其 identity；正文任何字节变化都视为锁定失效，必须进入 Human Decision Gate，并以新版本或显式 supersession 处理。

## 2. Objective

在保留现有本地转录、evidence、model integrity 与 session lifecycle 合同的前提下，把当前“固定重叠音频块 + 每块独立 `whisper-cli` + 事后字符串去重”分阶段升级为可嵌入、可审核、可在未来 iPadOS 复用的 streaming backend。

目标结果是：

- 模型和 whisper.cpp context/state 在 session 内长期存在；
- 音频以 PCM 直接进入 embedded backend，不依赖每块 subprocess、临时 WAV 或 stdout parser；
- backend 拥有 bounded rolling audio、bounded text/token context，以及 provisional / committed 的结构化事件语义；
- clean transcript 只追加永久 committed 内容；raw evidence 足以重放并解释 commit/reject 决策；
- 默认方案优先使用不需要 whisper.cpp fork 的 token-level LocalAgreement / hybrid policy；
- macOS prototype 与未来 SwiftUI + AVAudioEngine iPad App 复用同一 portable core 与 C ABI，而不是维护两套 streaming algorithm；
- 任何性能、稳定性、iPad 可行性或 AlignAtt 收益 claim 均由可定位实验 evidence 支持。

## 3. Scope and Deliverables

### 范围内

- 按 locked `update_plan.md` 的 Level 1、Level 2 和条件性 Level 3 分阶段执行。
- 建立 portable C++ core / C ABI、Python adapter、embedded whisper.cpp lifecycle 与结构化 streaming events。
- 重构 rolling audio、token context、commit policy、session evidence 与相关 settings/tests。
- 更新构建、runtime pin、打包与 provenance contract，使 embedded library 可验证。
- 进行与阶段风险相称的 deterministic tests、真实音频 parity、长时间运行和 physical iPad experiments。
- Reviewer 基于直接 evidence 对每个 Active Step 独立验收，并维护 `runtime.md`。

### 最终交付物

- 已验收的 embedded backend，不再让新主路径按 chunk 启动 `whisper-cli`。
- 已验收的 rolling token streaming 与 append-only commit contract。
- 可由 macOS Python UI 和未来 Swift/iPadOS adapter 共用的 backend API 边界。
- 覆盖 lifecycle、token stability、rollback、long-form、runtime packaging 的自动化与实验 evidence。
- 与最终实现一致的 architecture/build/user documentation。

### 范围外 / Non-goals

- 本合同不授权现在创建 SwiftUI/iOS project或发布 TestFlight build。
- 本合同不保证 large-v3 / large-v3-turbo 已适合任何 iPad；该结论必须由 physical-device evidence形成。
- 本合同不把 incremental encoder、CIF、Flash Attention weight extraction、state clone/save/restore 或完整 SimulStreaming PyTorch port列为默认交付。
- 本合同不授权 release、tag、merge到产品主分支、删除历史 evidence、修改外部参考仓库或对外提交 whisper.cpp PR。
- locked `update_plan.md` 不是 Runtime，不记录当前进度，也不得被 Executor更新。

## 4. Hard Constraints

1. **Single Active Step**：任一时刻最多一个权威 Active Step；并行探索也必须汇入同一 Reviewer verdict。
2. **Role separation**：Human Owner 管理目标、风险容忍度与合同变化；Reviewer 编译 prompt、直接检查 evidence、形成 verdict并更新 Runtime；Executor只执行 prompt，不自我验收。
3. **Locked plan**：`update_plan.md` 内容按第 1 节 identity冻结。Static/Runtime不得静默重写或弱化其中的 evidence结论、Unknown 或条件 gate。
4. **No silent scope expansion**：Executor只可修改当前 Runtime / Reviewer prompt明确允许的对象；未列出的 repository、branch、artifact、外部系统和发布状态均不可修改。
5. **Governance files protected**：Executor默认不得修改 `static.md`、`runtime.md` 或 locked `update_plan.md`。只有 Human Owner可授权 Static/plan变化；Runtime只由 Reviewer在独立审核后更新。
6. **Evidence before transition**：commit、测试通过或 Executor声明完成本身都不等于 acceptance。Reviewer必须能直接定位 diff、test output、artifact identity和必要的实机 observation。
7. **Portable boundary first**：新 streaming algorithm不得依赖 Qt、`sounddevice`、Python string dedup、CLI stdout、临时 WAV或 macOS-only process semantics。平台 adapter与 portable core必须分离。
8. **Committed output is immutable**：已 emitted 的 committed token/text不得被修改；provisional可以替换。clean只追加 committed，raw保存足够的 hypothesis/decision evidence。
9. **No stale-KV assumption**：同一 encoded window内可使用 decoder KV；音频更新后跨窗口复用 self-KV必须先有等价性 evidence，否则必须从 retained prefix重建。
10. **No unverified performance claims**：不得把低延迟等同于较低计算量，也不得从 model file可下载推导 iPad可运行。
11. **Local/private processing preserved**：转录不得新增云端 ASR/LLM依赖；model integrity的 size/SHA/atomic publish/evidence boundary不得被绕过。
12. **Reference repositories read-only by default**：`/Users/smterpro/Workspace/Tools/SimulStreaming` 与 `/Users/smterpro/Workspace/Tools/whisper.cpp` 只作为 evidence输入，除非 Human Owner明确授权 fork工作目录。
13. **Safe Git boundary**：Executor可否 commit/push必须由当前 Active Step明确写出；merge、rebase shared branch、force-push、tag、release始终需要 Human Owner明确授权。

## 5. Stable Background and Inputs

### 已确认事实

- 当前生产 inference path、SimulStreaming机制、whisper.cpp能力与 iPad implications 以 locked `update_plan.md` 为权威调查输入。
- 当前项目实施基线从 commit `1e0cdd9fda1870a8277a553c3f7af7cc67480fe9` 分出；该 commit只在先前代码基线上增加调查文档。
- 当前 packaged whisper.cpp runtime pin 是 `8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae`，由 `packaging/runtime_manifest.json` 与 bootstrap contract约束。
- 调查参考 SimulStreaming commit：`077ea37d5ab4ff98bc567e4507f140dc4e5d5ad6`。
- 调查参考 whisper.cpp commit：`1da4dc82fa7996d4edda05890dca65aeceaafd6d`。
- vanilla whisper.cpp 已有 persistent context/state、low-level encode/decode/`n_past`/logits、prompt tokens、DTW `t_dtw`、Metal与 Apple XCFramework；raw per-token cross-attention仅内部存在。
- SimulStreaming跨 audio update持久化 audio/token/prompt，不持久化本轮 decoder KV；每轮重算 rolling encoder。

### 已授权候选路线

- Level 1：embedded whisper.cpp，先保留现有 overlap/dedup用于 parity。
- Level 2：应用层 rolling audio/token context、token-ID LocalAgreement、时间 safety horizon；DTW为实验性 signal。
- Level 3：只有前序 evidence支持时才考虑小型 whisper.cpp patch / fork。

### 未知项

- `TO_CONFIRM`：用于 parity与性能基准的固定真实音频 corpus、model identity与可公开程度；由 Human Owner或 Reviewer在 Step 1前/中确认。
- `TO_CONFIRM`：最终 embedded binding/build形态和唯一 whisper.cpp pin；由 Step 1 evidence支持后 Reviewer提出，Human Owner在影响分发或长期 fork时决定。
- `TO_CONFIRM`：默认 update cadence、rolling window、agreement depth、time safety margin；由 Level 2实验决定。
- `TO_CONFIRM`：目标 physical iPad型号、最低 OS、可接受 memory/thermal/RTF budget与默认模型；由 Human Owner提供设备/产品边界。
- `TO_CONFIRM`：是否进入 Level 3 AlignAtt patch；只能在 no-fork hybrid基准后进入 Human Decision Gate。

## 6. Authority and Approval

- 可修改 Static 的主体：Human Owner；Reviewer只能依据明确授权落实修订。
- 可修改 locked update plan 的主体：Human Owner通过显式 reopen/version/supersession授权；默认任何主体都不得修改。
- 可形成最终 acceptance verdict 的主体：Reviewer；必须直接访问所需 evidence。
- 可更新 Runtime 的主体：Reviewer；Executor只能提交报告与 locator。
- Executor 的授权范围：当前 Runtime Active Step和 Reviewer编译 prompt明确列出的文件、命令、测试、commit/push范围。
- 必须进入 Human Decision Gate：改变 Static/plan、扩大 scope、进入 whisper.cpp fork产品化、创建 iOS project、选择产品风险预算、merge/release/tag、force-push、删除或覆盖 material evidence、不可逆外部操作。
- Reviewer可以基于证据在已授权候选范围内选择 repair path和激活下一 Step，但不能替 Human Owner确定主观产品取舍。

## 7. Permitted and Prohibited Mutations

### 允许

- Reviewer在当前 task branch读取整个项目与 reference repositories，运行非破坏性诊断和验收检查。
- Executor按 Active Step修改明确列出的项目文件，新增隔离的 prototype/tests/evidence，并运行与 scope匹配的命令。
- Executor在 prompt明确授权时创建普通 commit并 push当前 task branch。
- Reviewer在 acceptance/rejection后更新 `runtime.md`，记录 fixed evidence locator、verdict、transition、pending task和下一 Active Step。

### 禁止

- Executor修改 `docs/streaming_backend_upgrade/static.md`、`runtime.md`、`update_plan.md`。
- 静默修改 runtime pin、model integrity policy、privacy boundary、release configuration或现有 transcript evidence语义。
- 直接修改两个 `/Workspace/Tools` reference checkout；对 whisper.cpp的候选 patch必须使用另行授权的 fork/worktree并固定 identity。
- force-push、历史改写、merge到产品分支、tag、release、TestFlight发布或外部 PR。
- 提交模型二进制、真实用户音频、转录隐私数据、凭证、个人路径生成物或未获授权的大型 artifact。
- 将未跑、不可定位、陈旧或与 acceptance claim不匹配的检查报告为 PASS。

## 8. Acceptance Criteria

| ID | 验收条件 | 所需 evidence | Evidence locator / identity | 通过边界 |
| --- | --- | --- | --- | --- |
| AC-01 | 所有变更符合唯一 Active Step与权限边界 | branch/commit identity、完整 diff、status、Executor report | fixed commit SHA + Reviewer直接 diff | 无越界文件、无未披露副作用 |
| AC-02 | Level 1 embedded path在 session内只加载一次 model/context，直接处理 PCM | lifecycle instrumentation、代码路径、至少两次 update、CLI parity结果 | fixed model/audio/commit + logs/tests | embedded path无 per-update subprocess/temp WAV/model reload；差异被解释 |
| AC-03 | 新 backend有 bounded rolling audio/text token context和 append-only commit | deterministic token fixtures、long-form run、event/store evidence | fixed fixtures + test output/artifact hash | committed永不修改；provisional可替换；memory/context有界 |
| AC-04 | 新默认 commit policy不依赖 fuzzy text dedup | token-ID agreement/hybrid tests、跨语言 fixtures | fixed commit + direct test output | clean来自 committed events；legacy dedup只存在于显式 legacy path |
| AC-05 | lifecycle、evidence与model integrity合同保持 | full relevant tests、Start/Stop/final partial/second Start、session artifact检查 | test command/output + artifact locator | 无丢尾音、queue/lifecycle回归；raw/clean/config/log语义可审核；integrity未绕过 |
| AC-06 | portable core可供 macOS与未来 iPad复用 | C ABI/header/build evidence、host harness、XCFramework smoke when activated | pinned source/build/artifact hash | core不依赖 Python/Qt/sounddevice/CLI；same API可由 Swift import |
| AC-07 | 性能/稳定性 claim由测量支持 | model/audio/device/config固定的 timings、memory、revision、WER/CER/RTF等 | immutable result artifact或带时间的 device observation | 不以主观描述代替测量；比较组配置一致 |
| AC-08 | Level 3只在 Human Gate后启动 | Level 2 baseline、AlignAtt spike结果、iPad non-Flash结果、Owner decision | fixed reports + Human authorization locator | 任一缺失则不得产品化 fork |
| AC-09 | 最终文档与实现/provenance一致 | repo map、README/build/runtime docs diff和验证 | final commit + docs review | 无仍把新主路径描述为 CLI/字符串 dedup的陈旧权威文档 |

## 9. Evidence and Privacy Boundary

- Reviewer 必须能够直接访问：目标 branch/commit、diff、相关源文件、完整测试输出、构建 artifact identity，以及 acceptance要求的实机 observation。
- Evidence 固定方式：优先 commit SHA、Git blob、SHA-256、固定 fixture、完整命令和输出 artifact；不得以漂移中的同名 `HEAD` 或无 hash文件做最终验收。
- 可以保持私有：本地模型、许可受限音频、设备日志和带隐私的真实转录；但 Reviewer必须有授权访问，公开报告只保留去敏 locator/摘要。
- 禁止记录或公开：凭证、访问 token、未获授权的用户音频/文本、个人身份信息。
- Executor self-report用于定位 evidence，不替代 Reviewer独立检查。

## 10. Change Control

- Static变化：Human Owner明确授权 → Reviewer列出准确 diff、原因、授权与影响 → 新版本生效；无授权只可提出候选修订。
- Locked plan变化：默认新建 versioned successor，并在 Static/Runtime记录 supersession；不得覆盖原 identity后继续声称“已锁定”。
- Runtime变化：Reviewer完成一致性预检与 evidence审核后更新；每次最多激活一个 Active Step。
- 已完成 task默认冻结；新目标使用新的 task-local Static/Runtime。只有 Human Owner明确 reopen才恢复。
- Static、Runtime、plan或 evidence冲突时暂停状态迁移，输出 `HUMAN DECISION REQUIRED`。

## 11. Open Decisions

- `REQUIRES_OWNER_DECISION`：目标 iPad设备、最低 OS、memory/thermal/RTF budget尚未给出；在开始 physical iPad acceptance前必须决定。
- `REQUIRES_OWNER_DECISION`：任何产品化 whisper.cpp fork/patch；只有 AC-08 evidence齐全后决定。
- `TO_CONFIRM`：Level 1之后沿用 runtime pin还是升级到已审计的新 upstream revision；必须先比较 API、packaging与回归影响。
- `TO_CONFIRM`：是否把 DTW保留为 desktop debug option、mobile option或完全移除；由 Level 2/physical-device实验决定。
