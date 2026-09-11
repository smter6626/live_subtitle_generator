# Streaming Backend Upgrade — Runtime 当前权威状态

## 1. Current Status

- Task ID：`streaming-backend-upgrade`
- 状态：`ACTIVE`
- 当前 verdict：`NOT EVALUATED`
- 唯一 Active Step：`Step 1 — Embedded whisper.cpp parity prototype`
- 最近 Pending 截止：`Step 2`
- Static identity：`docs/streaming_backend_upgrade/static.md` version `1.0`，状态 `AUTHORIZED`
- Locked plan identity：Git blob `536ff6412166bce9c77c2b42e8cf981d2fccbc18`；SHA-256 `ae4566dd27dca2ba96d5beedd8d35ab490a46e51188fa82cbd05eef4d7917c40`
- Repository baseline：branch `codex/streaming-backend-upgrade` 从 `1e0cdd9fda1870a8277a553c3f7af7cc67480fe9` 创建
- Evidence snapshot / review identity：调查基线与 revision table见 locked `update_plan.md`；本 Runtime 初始化尚未审核任何 implementation result
- 最后更新：2026-09-11（America/Phoenix）

## 2. Completed

- Precondition — Investigation baseline locked：技术审计已在 commit `1e0cdd9fda1870a8277a553c3f7af7cc67480fe9` 完成；`update_plan.md` 以 blob与 SHA-256 固定。当前语义是“已接受为实施输入”，不是任何 implementation Step 已验收。
- Governance bootstrap：Human Owner 已指定 Static/Runtime + Reviewer/Executor职责分离模式；本文件建立唯一 Active Step。此项不构成 Step 1 acceptance。

## 3. Active Step

### Step 1：Embedded whisper.cpp parity prototype

- Objective：在不切换生产 inference path 的前提下，建立一个隔离、可运行、可测试的 embedded whisper.cpp prototype，证明同一 model/context在至少两个连续 audio updates间只初始化一次，并能直接从 16 kHz mono Float32 PCM获得结构化 segment/token结果，为 Level 1 production integration提供 evidence。
- Inputs 及固定 identity：
  - Static：`docs/streaming_backend_upgrade/static.md` version `1.0`
  - Plan：`docs/streaming_backend_upgrade/update_plan.md`，blob `536ff6412166bce9c77c2b42e8cf981d2fccbc18`
  - Repository implementation baseline：`1e0cdd9fda1870a8277a553c3f7af7cc67480fe9`
  - Packaged whisper.cpp runtime pin：`8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae`
  - Reference whisper.cpp audit：`1da4dc82fa7996d4edda05890dca65aeceaafd6d`
  - 模型与音频 fixture：`TO_CONFIRM`；必须记录 path之外的 model identity/hash、audio identity/hash或受控生成方式，敏感内容不得提交
- Permitted changes：
  - 新增隔离 prototype，例如 `native/streaming_core/` 下的 C/C++ source/header/build files。
  - 新增只针对 embedded lifecycle/PCM/result extraction的 tests或 harness。
  - 为构建隔离 prototype所必需的最小 project-local build配置。
  - 新增无敏感内容的小型 deterministic synthetic fixture；真实模型/真实音频只能引用，不得提交。
  - 当前 Step默认不授权修改 production `transcription_engine.py`、`stream_transcribe.py` backend selection或 packaged release path。
- Prohibited changes：
  - `docs/streaming_backend_upgrade/static.md`
  - `docs/streaming_backend_upgrade/runtime.md`
  - `docs/streaming_backend_upgrade/update_plan.md`
  - 生产 backend切换、删除 legacy CLI path、改变 transcript语义、修改 model integrity contract。
  - 修改 `/Users/smterpro/Workspace/Tools/SimulStreaming` 或 `/Users/smterpro/Workspace/Tools/whisper.cpp` reference checkout。
  - whisper.cpp fork/patch、iOS project、release/tag/merge/force-push、提交模型或私有音频。
- Required evidence：
  - 最终 commit SHA、完整 changed-file list与 clean worktree status。
  - 精确 build/test命令及完整输出 locator。
  - source-level locator证明 context/model init在 update loop之外，且 destructor/free路径明确。
  - 至少两个连续 PCM updates的运行 evidence；记录 model hash、audio hash/生成方式、whisper.cpp SHA和参数。
  - instrumentation证明 model/context init count为1；每次 update返回结构化 segment/token结果或有可解释的 silence结果。
  - 与当前 CLI对同一 PCM/model的 parity comparison；文本/token/timestamp差异必须列出，不得只写“基本一致”。
  - memory/lifetime检查：至少证明连续调用和 destroy无 crash；任何更强 leak claim需要匹配工具 evidence。
- Acceptance criteria：`AC-01`、`AC-02`，并满足 `AC-07` 的 claim纪律；本 Step不验收 production integration。
- Executor self-check：
  - 编译隔离 prototype并运行 targeted tests。
  - 在可用时运行 sanitizer或平台等价 memory diagnostic；若不可用，明确 limitation。
  - `git diff --check`；列出 `git status --short`。
  - 确认三个 protected governance files未变化，locked plan hash仍匹配。
- Stop conditions / Human Gate：
  - 没有可合法使用的 model/audio fixture，无法形成真实 parity evidence。
  - 必须修改 production path、runtime pin、packaging contract、reference checkout或 locked documents才能继续。
  - API/ABI选择会锁定长期分发方式但现有 evidence不足。
  - 发现 Static、plan或当前 repository identity冲突。
- Executor report format：
  1. Result：完成 / 未完成，不给最终 acceptance verdict。
  2. Changes：逐文件说明。
  3. Evidence：commit、diff、命令、输出、model/audio/whisper identity。
  4. AC mapping：AC-01/AC-02/AC-07分别由什么支持。
  5. Limitations / unknowns。
  6. Explicit confirmation：未修改 protected files、未切换 production backend、未修改 reference repos。
- Git authorization：Executor可在 task branch创建普通 commit；**本 Step默认不授权 push**，由 Reviewer审核后再决定是否推送或下发 repair。
- 完成后停止于：`AWAITING_REVIEW`

## 4. Independent Review

| Acceptance criterion | Direct evidence | Evidence sufficiency judgment | Result |
| --- | --- | --- | --- |
| AC-01 — scope/permission | 尚无 Executor implementation evidence | 尚不可判断 | INSUFFICIENT |
| AC-02 — persistent embedded PCM path | 尚无 prototype、运行或 parity evidence | 尚不可判断 | INSUFFICIENT |
| AC-07 — measured claims | 尚无固定 model/audio/config结果 | 尚不可判断 | INSUFFICIENT |

- 独立 evidence access：`NOT APPLICABLE`（尚未提交 Step 1结果）
- 独立 verdict formation：`NOT APPLICABLE`
- 独立 evidence-sufficiency judgment：`NOT APPLICABLE`
- Review verdict：`NOT EVALUATED`
- Review limitations：当前只完成合同/状态初始化，没有 implementation artifact可审。

## 5. State Transition

- Previous state：无 task-local Runtime
- Triggering evidence 或 Human decision：2026-09-11 Human Owner要求建立新分支与集中管理的 Static/Runtime/locked plan，并指定 Reviewer/Executor工作方式
- Current state：`ACTIVE / Step 1`
- Meaning：允许 Reviewer编译 Step 1 Executor prompt；没有 implementation被接受
- Transition authorized by：Human Owner

## 6. Blockers and Human Decision Gates

- 当前 blocker：无。
- Human Gate H-01：任何产品化 whisper.cpp fork/patch；在 Level 2 baseline和 AlignAtt/iPad evidence齐全前禁止启动。
- Human Gate H-02：创建 iOS project、TestFlight、release、tag或merge产品分支；当前未授权。
- Human Gate H-03：修改 locked plan或 Static；必须由 Human Owner明确授权。

## 7. Residual Validation Items

- 无已验收 Step，因此当前没有 acceptance residual item。

## 8. Pending Tasks — Non-blocking Blocks

当前顶层 Step：`1`

| ID | 非阻塞性 block | 引入于 | 截止 Step | 剩余安全迁移次数 | 当前状态 | 关闭条件与所需 evidence | 责任人 / 触发器 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PT-01 | 目标 physical iPad型号、最低 OS与 memory/thermal/RTF budget尚未确认 | Step 1 | Step 4 | 2 | OPEN_NON_BLOCKING | Human Owner给出设备/产品边界并在 Runtime固定；或明确 Step 4不做 device acceptance | Human Owner，在激活 Step 4前 |
| PT-02 | Level 1后使用现有 runtime pin还是升级 upstream revision尚未决定 | Step 1 | Step 2 | 0 | DUE_NEXT | Step 1 API/packaging evidence + Reviewer比较报告；若改变长期 pin/fork策略则取得 Human decision | Reviewer，在激活 Step 2前 |

### Pending Gate Check

- 下一顶层 Step：`Step 2 — Production Level 1 integration`（仅候选，尚未激活）
- 激活前必须关闭的 Pending Task：`PT-02`
- Gate verdict：`BLOCKED`（只阻止激活 Step 2，不阻止当前 Step 1）
- 支持 evidence 或 Human authorization：尚无；Step 1结果将提供决策输入

## 9. Superseded Decisions

- 无。

## 10. Next Direction

- Step 1 accepted后，先关闭 PT-02，再条件性激活 Step 2 production Level 1 integration。
- Level 1 production path accepted后，才激活 Level 2 rolling token LocalAgreement/hybrid。
- DTW与 AlignAtt保持实验性；Level 3受 H-01约束。
- iPad project保持范围外；portable C ABI/XCFramework readiness可以在不创建 App的情况下逐步验证。

## 11. Current Executor Handoff

- 本轮唯一任务：实现并证明隔离的 embedded whisper.cpp parity prototype；不得切换生产 backend。
- 必须读取：`static.md`、`runtime.md`、locked `update_plan.md`，以及其中指向的 current source/runtime manifest。
- 可以修改：仅 Active Step “Permitted changes” 中的范围。
- 不得修改：三个 governance/locked documents、production backend、reference repos及未授权外部状态。
- 必须返回的 evidence locator：commit SHA、完整 diff、build/test outputs、model/audio/whisper identities、init-count和两次 update/parity evidence。
- 完成后停止于：`AWAITING_REVIEW`，等待 Reviewer独立审核。
