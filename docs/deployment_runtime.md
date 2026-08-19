# deployment_runtime.md

最后更新：2026-08-18  
文档角色：Deployment 工作线动态执行状态（runtime state）

本文件只记录 Classroom Live Transcriber 在 `main` 分支上的 deployment / packaging / clean-machine reproducibility / bugfix 执行状态。

长期稳定合同见：`docs/deployment_static.md`。

LLM 功能线动态状态仍由 `llm-sidecar-phase1` 分支中的 `docs/whisper_runtime.md` 维护。两条工作线不得混用 ACTIVE step、完成记录或验收状态。

---

## 0. 使用规则

每完成一个 Deployment Step 后：

1. 将当前 ACTIVE step 标记为已完成；
2. 记录实现 commit、实际产物、测试与审核结果；
3. 激活下一步，并保证全文件只有一个 ACTIVE Step；
4. 下一步必须细化到可直接交给 Codex / 人工执行；
5. 不删除历史完成记录。

`deployment_static.md` 负责长期方向和硬合同；本文件负责 checkpoint、唯一 ACTIVE Step、完成记录、当前风险、未敲定参数和下一步执行说明。

除非用户明确要求，Codex 默认只读取本文件，不主动修改本文件。通常流程：

```text
Codex 执行当前 Step
-> commit + push main
-> 人工 / ChatGPT 基于 GitHub 实际内容审核
-> 再受控更新 deployment_runtime.md
```

---

## 1. 当前 checkpoint

```text
当前分支：main
当前实现 checkpoint：fa3652043993b3567a292876e8b5b148cdc09301
checkpoint 内容：fix: harden model downloads
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
唯一 ACTIVE：Deployment Step 8 - 新机器 Clean-machine App / Model / Microphone / Transcription E2E
```

当前一句话目标：

> **让符合硬件要求的 macOS Apple Silicon 机器无需手动配置开发或运行环境，仅需安装 App、下载模型，即可直接完成本地实时转录。**

---

## 2. 已完成步骤

### Deployment Step 0：稳定 ASR 基线

状态：已存在并长期验证。

稳定链路：

```text
PySide6 UI
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore
```

真实课堂路线已验证：`whisper.cpp + Metal + large-v3`。

---

### Deployment Step 0.5：Vendor 模型下载脚本修复

状态：已完成并 push `main`。

```text
2aa7bafc99c5f872719b22a0e431e4634cb22d92
fix: vendor whisper model download script
```

结果：`vendor/whisper.cpp/download-ggml-model.sh` 已进入主仓库并进入 PyInstaller resource；Fresh Clone 不再依赖 `external/whisper.cpp/models/download-ggml-model.sh` 才能获得下载脚本。该步骤只解决 downloader provenance / packaging，不代表下载完整性已经加固。

---

### Deployment Step 1：Clean-machine Gap Audit

状态：已完成，仅审计。

确认主要缺口：Fresh Clone 无 bootstrap / `.command`；Python 环境不可复现；Fresh Clone 无 whisper Runtime；旧 packaging 对 Runtime 不够严格；模型下载缺完整性与失败恢复；尚无 clean-machine E2E。

---

### Deployment Step 2：部署合同与 Runtime Manifest

状态：已完成并经 GitHub 实际内容审核通过。

```text
988eb5d8af61044175236d851a838a6f2793e0c0
chore: define deployment runtime manifest
```

主要产物：`PACKAGING.md`、`packaging/runtime_manifest.json`、`testCodes/test_runtime_manifest.py`。

冻结 / 记录：macOS arm64、whisper.cpp pinned commit、第一版 Build Profile、Runtime component、Bundle baseline、fail-fast contract、Python 环境方向以及 frozen / observed / pending 分层。Manifest JSON / 14 项 manifest unittest / `git diff --check` 全部 PASS。

---

### Deployment Step 3：建立可重建的 Python 环境

状态：已完成，并经 GitHub 实际实现审核通过。

```text
643dee844a55f1e45467714f6fd65280aa6cd8ff
chore: add reproducible python environment
```

正式 Python 合同：Python 3.12.14、`>=3.12,<3.13`、uv 0.12.5、PySide6 6.11.1、PyInstaller 6.22.1、numpy 2.5.2、sounddevice 0.5.6、`.venv/`、`.tools/`、`uv sync --frozen`。

首次 bootstrap、`--recreate`、20 项联合 unittest、带空格路径 throwaway clean-repo rebuild 与 `git diff --check` 均 PASS。历史 `venv/` 不参与正式环境。

旧 `test_pseudo_real_chunk_sequences.py` 仍保持既有行为：脚本退出码为 0，但会打印 pseudo-oral 期望失败；该项不是 Deployment 引入，不阻塞当前工作线。

---

### Deployment Step 4：Whisper Runtime Bootstrap

状态：已完成，并经 GitHub 实际实现审核通过。

```text
cc4d3bde05c110e14bac8185e3485a70ddb98565
chore: add reproducible whisper runtime bootstrap
```

正式合同：CMake 4.2.3、Kitware official artifact + frozen SHA-256、whisper.cpp `8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae`、Unix Makefiles、Release、explicit arm64、`GGML_OPENMP=OFF`、`GGML_NATIVE=ON`、target `whisper-cli`、minimal smoke `--help`。

主工作区与 throwaway 无 CMake / 无 external 的恢复、删除后二次恢复、CLI + 6 dylib arm64、`@rpath` dependency、minimal smoke、29 项联合 unittest 和 `git diff --check` 全部 PASS。

---

### Deployment Step 5：可双击的一键构建入口与 Orchestration

状态：已完成，并经 GitHub 实际实现审核通过。

```text
fdefbc10e945f693def35d9896e0101c6f766b00
chore: add one-click build orchestration
```

正式调用链：

```text
Build ClassroomTranscriber.command
-> scripts/bootstrap_and_build.sh
-> scripts/bootstrap_python_env.sh
-> scripts/bootstrap_whisper_runtime.sh
-> PYTHON=.venv/bin/python scripts/build_macos.sh
-> dist/ClassroomTranscriber.app
```

主工作区正式 orchestrator、第二次 idempotent 执行、throwaway Fresh Clone、`.command` shell 等价调用、36 项联合 unittest 与 `git diff --check` 全部 PASS。Finder GUI 真实双击继续作为 Clean-machine acceptance 项保留。

---

### Deployment Step 6：严格打包门禁与 post-build Runtime smoke

状态：已完成，并经 GitHub 实际实现审核通过。

```text
b38fbeae5d8a9cec1c8caf1bd179715920947bcf
fix: enforce packaged runtime gates
```

正式 Packaging 成功路径：

```text
Manifest source preflight
-> PyInstaller
-> App 内 Runtime normalization
-> required ad-hoc codesign
-> packaged Runtime verifier
-> Build complete
```

Release / Debug Spec、source preflight、normalizer、verifier 与 tests 共享 Runtime Manifest；required Runtime 不再 optional。最终 App 内 CLI + 6 dylib 必须 arm64-only，dependency closure 仅允许 bundle-relative / 系统合法路径；App 内 CLI smoke、isolated Runtime smoke、downloader、codesign 均为 Build PASS 前 hard gate。

主工作区 one-entry build、独立 verifier、throwaway Fresh Clone、反向 failure injection、47 项联合 unittest 与 `git diff --check` 全部 PASS。

---

### Deployment Step 7：模型下载完整性、失败恢复与重试

状态：已完成，并经 GitHub 实际实现与 upstream metadata 审核通过。

实现 commit：

```text
fa3652043993b3567a292876e8b5b148cdc09301
fix: harden model downloads
```

正式新增：

```text
packaging/model_manifest.json
model_integrity.py
testCodes/test_model_integrity.py
testCodes/test_model_manager_ui_contract.py
```

正式下载链路：

```text
Model Manager background worker
-> hidden staging directory on target filesystem
-> unchanged vendored downloader
-> exact byte-size validation
-> SHA-256 validation
-> os.replace atomic publish
-> atomic integrity receipt
-> refresh
-> only verified model becomes available / selectable
```

Downloadable model 单一事实源由 `packaging/model_manifest.json` 管理，与 Runtime component contract 分离。当前冻结：

```text
upstream repository: https://huggingface.co/ggerganov/whisper.cpp
revision: 5359861c739e955e79d9a303bcbc70fb988958b1
models:
  large-v3
  large-v3-turbo
  medium.en
  small.en
  base.en
```

Manifest 记录 exact size、SHA-256、upstream blob id、revision-pinned artifact URL 和 metadata API provenance。GitHub / upstream 审核确认 large-v3、large-v3-turbo、medium.en、small.en、base.en 的 SHA-256 与公开 Hugging Face artifact/LFS metadata 一致；实现未使用旧开发机模型文件作为 checksum authority。

下载事务审核确认：

- vendored upstream downloader 保持原样；
- downloader 只在 `.classroom-model-download-*` 隐藏 staging 中运行；
- downloader nonzero、缺输出、size mismatch、SHA mismatch 都不会 publish final；
- 验证成功后 `os.replace` 发布 final，再原子写 contract + file-stat bound receipt；
- existing final 有 current receipt 时快速复用；无 receipt 时在后台全量 size/SHA 验证后才能复用；
- corrupt final 不 available、不 selected，并允许 retry 用 verified staging 原子替换；
- stale managed staging 不会被 scan，retry 会自动清理；
- 明确 Import 的 custom `.bin/.gguf` 保留独立 use-in-place 校验，不强制进入 downloadable checksum contract；
- 网络下载和 SHA-256 继续在后台 daemon worker，不进入 Qt 主线程；失败恢复 UI controls 并允许再次下载。

Packaging 审核确认 `model_manifest.json` 是 required App resource，source/frozen path 均由 `resource_paths.py` 解析；Step 6 strict Runtime verifier 继续 PASS，model binary 仍不进入 Git / App / Runtime components。

实施验证：

```text
model integrity / failure injection tests               PASS / 13
Model Manager UI orchestration tests                    PASS / 3
model resource tests                                    PASS / 6
既有 UI / ASR safety regression                         PASS / 22
Deployment unittest                                     PASS / 65
正式 one-entry App build + Step 6 verifier              PASS
model manifest packaged                                 PASS
git diff --check                                        PASS
真实大型模型自动下载                                    未执行（符合 Step 7 边界）
```

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 8 - 新机器 Clean-machine App / Model / Microphone / Transcription E2E
```

### 3.1 目标

在真实验收机上验证 Developer Deployment MVP：不靠旧开发机历史环境、不靠临时人工修补，从干净 `main` 的正式入口得到 App，再通过 App 自己完成模型获取与真实麦克风转写，最终生成完整 session evidence layer。

Primary clean-machine acceptance target：

```text
MacBook Pro / Apple M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

M5 Developer / Reference Machine 仍需做当前 checkpoint 的实际 App/runtime/ASR regression，用于形成 M5 实际验证证据；但它不是 clean-machine 证据的替代品。

### 3.2 Clean-machine 硬约束

新 M4 Max 必须保持验收机角色。不得先手工准备或复制：

```text
项目 .venv / .tools
external/whisper.cpp
whisper-cli / dylib
模型文件
项目专用 CMake / Python 修补
临时 PATH / DYLD 修补
只存在于新机器本地的脚本或代码修改
```

允许的正常 host / OS 交互：Git clone 所需 Git、网络、Apple Command Line Tools（如正式源码构建入口确实需要并由系统正常提供/提示）、macOS Gatekeeper 正常提示、麦克风权限。

任何为成功而额外执行、但没有进入正式项目流程的技术命令，默认视为 deployment bug：记录证据 -> 回旧开发机修正式流程 -> commit/push main -> 新机重新从干净状态验证。

### 3.3 Step 8 验收流程

至少完成：

```text
新 M4 Max
-> fresh clone main
-> 确认无项目历史 .venv/.tools/external/model
-> 从 Finder 实际启动 Build ClassroomTranscriber.command 至少一次
-> 正式 bootstrap + build 全流程 PASS
-> dist/ClassroomTranscriber.app 生成且 Step 6 verifier PASS
-> 启动 App
-> Model Manager 通过正式下载链路获取至少一个 manifest-managed model
-> model integrity PASS / available
-> 授予麦克风权限
-> Start Recording
-> 产生真实非空转写
-> Stop
-> 麦克风正常释放 / App 保持可用
-> session 生成 raw.txt / clean.txt / session.log / config.json
-> evidence layer 非空/结构合理且未被部署功能破坏
```

模型应通过 Model Manager 正式下载，不得从旧机复制。若为降低下载时间选择较小 manifest-managed model，可以完成 Deployment E2E；但不得据此声称 large-v3 已在该新机完整验证。若需要保留“large-v3 clean-machine 实测”声明，则必须额外实际下载/使用 large-v3。

### 3.4 M5 回归要求

旧 M5 Developer / Reference Machine 在 Step 8 checkpoint 上至少验证：

```text
正式 App build / packaged Runtime gate PASS
App 启动
至少一个 integrity-valid model 可用
麦克风 Start / Stop
真实非空转写
完整 evidence layer
```

该结果可以证明当前 checkpoint 在 M5 上实际运行，但不能被描述为 fresh clean-machine acceptance。

### 3.5 Step 8 PASS 判定

Step 8 只有在以下条件同时满足时 PASS：

1. M4 Max clean-machine 正式流程无隐藏手工修补；
2. Finder `.command` 真实双击入口至少一次实际 PASS；
3. Fresh Clone 自动准备 Python/CMake/whisper Runtime 并构建 App；
4. Step 6 packaged Runtime verifier 在新机 PASS；
5. Model Manager 实际下载至少一个 manifest-managed model，Step 7 integrity transaction PASS；
6. 下载后的 model 状态为 available，可正常选择；
7. App 获得麦克风权限并成功 Start；
8. 实际音频产生真实非空 raw / clean 转写；
9. Stop 完成且麦克风释放；
10. `raw.txt`、`clean.txt`、`session.log`、`config.json` 全部生成且保持 evidence-layer 语义；
11. M5 当前 checkpoint 实机 App / transcription regression PASS；
12. 未把新机的一次性人工修补当作正式通过。

### 3.6 失败处理

Step 8 原则上是验收，不主动新增功能。出现失败时先完整记录：机器、macOS、入口、错误日志、缺失依赖、是否发生 Gatekeeper / permission / network 问题。

如果属于项目正式路径缺口：

```text
新机停止修补
-> 回旧开发机定位和实现最小修复
-> 一个明确 bugfix commit + push main
-> ChatGPT / 人工审核
-> 新机重新 fresh/clean 验收相关路径
```

不得直接在新机手工复制缺失资源后宣布 PASS。

### 3.7 Step 8 边界

本 Step不要求：

```text
GitHub Release ZIP acceptance（Step 9）
Developer ID signing
Notarization
DMG
GitHub Actions release automation
M1 / M2 / M3 实机验证
旧版 macOS compatibility
LLM 功能开发
```

达到 Step 8 Developer MVP 后即可建立干净 main checkpoint，并允许恢复 `llm-sidecar-phase1`；Step 9 / signing / notarization / DMG 属于 Release polish，不无限阻塞 LLM。

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. `GGML_NATIVE=ON` 已在旧 M5 的 source/build/packaging 自动测试通过，但真正跨 M4 Max/M5 的实际转写 portability 仍由 Step 8 闭环。
2. 正式 `GGML_OPENMP=OFF` 已消除 host OpenMP availability 漂移；旧 requested ON / effective OFF 仅保留为历史证据。
3. 第一版继续使用 `Contents/Resources/bin/` Runtime 布局；Step 6 已在该布局内建立严格 closure。
4. Python 合同仍保留 broad floor `>=3.11`，但正式可复现 build environment 是 `3.12.14 / >=3.12,<3.13`。
5. Developer source build 仍依赖 Git、网络、Apple Command Line Tools 与 macOS host 工具；普通 Release 用户不承担这些源码构建前提。
6. Step 6 当前使用 ad-hoc codesign；Developer ID / notarization 仍属于 Release polish。
7. 当前普通用户最小发布形式仍为 ZIP + `.app`；Step 9 不阻塞 Step 8 Developer MVP。
8. minimum macOS 仍为 pending；当前只验证两台 macOS 27 Beta 机器，不据此推断旧版本。
9. Model integrity contract 当前冻结 Hugging Face revision `5359861c739e955e79d9a303bcbc70fb988958b1`；vendored downloader 仍解析 upstream `main`，但只有与冻结 size/SHA-256 完全匹配的 bytes 才会被接受。若 upstream main 后续替换为新 bytes，下载会 fail closed，需显式维护 manifest，而不能静默接受新 artifact。
10. Integrity receipt 以当前合同 + size + mtime 作为快速 available 证据；文件 stat 变化会使 receipt 失效并要求重新验证。它是性能优化，不替代首次 cryptographic validation。
11. 明确 Import 的 custom `.bin/.gguf` 不受官方 downloadable checksum contract 约束，仍只使用独立本地 import validation；这属于产品设计边界而非 official model integrity 保证。
12. 旧 pseudo-oral 测试输出仍是既有非阻塞项，不归 Deployment Step 8 修复。

---

## 5. 当前未敲定参数

```text
# Step 8
M4 Max Clean-machine 首次实际 model 选择（至少一个 manifest-managed model）
是否额外要求 large-v3 在 M4 Max 完整下载/转写，以形成 large-v3 clean-machine 声明
M4 Max / M5 实际 GGML_NATIVE portability 结果
Finder .command 真实双击中的系统提示 / CLT / Gatekeeper 体验

# 后续
minimum macOS（当前不承诺旧系统，保持未设置）
Developer ID signing / notarization 实施时间点
GitHub Release 正式版本和自动发布流程
```

---

## 6. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine，用于开发、自动测试、clean-repo simulation、构建验证、稳定 ASR 回归、Commit / Push；当前实际硬件为 MacBook Air / M5 / 16 GB / 512 GB / macOS 27 Beta。

新 Mac：Clean-machine Acceptance Machine；当前实际硬件为 MacBook Pro / M4 Max / 48 GB / 1 TB / macOS 27 Beta。不得手工复制 `.venv`、`.tools`、`external/`、CLI、dylib 或模型，不通过临时 Terminal 命令修补正式流程。

对外支持声明：M4 / M5 只有各自完成当前 checkpoint 的实际运行验收后，才可声明“项目已实际验证”。M1 / M2 / M3 仅理论兼容，不作保证。旧版 macOS 当前不作保证。

---

## 7. 当前已知 Failure Modes / Step 8 观察点

### Build / Packaging

- Step 3–6 已在旧机和 throwaway 建立 reproducible source build 与 strict App Runtime gate；新 M4 Max 尚未完成真实 clean-machine build。
- Finder GUI `.command` 之前只做过 shell 等价验证，Step 8 必须补真实双击。
- 新机若缺 Apple Command Line Tools 或出现权限/Gatekeeper 提示，必须区分正常 OS prerequisite 与项目未自动处理的 deployment gap。

### Whisper Runtime

- `GGML_NATIVE=ON` 是当前最大剩余 Runtime portability 风险；必须通过 M4 Max 与 M5 实际 App transcription 结果闭环，而不只看 `--help`。

### Model Manager

- Step 7 的 checksum/staging/atomic publish/retry 目前只有 fixture + packaging 验证；Step 8 首次执行真实 upstream model download transaction。
- vendored downloader 指向 upstream `main`，如果 upstream bytes 已变化而不匹配 frozen revision，正式行为应 fail closed；这不是自动“修复 checksum”的理由。

### ASR / Evidence

- Deployment 自动化没有替代真实 microphone / Start / Stop / raw-clean evidence 验收；Step 8 必须实际产生转写。
- 任何 real E2E 失败先判定 deployment / permission / model / Runtime / existing ASR bug，不得为了让验收通过而随意调 ASR 参数或 dedup。

---

## 8. 后续步骤

```text
Step 1：Clean-machine Gap Audit                                      已完成
Step 2：部署合同与 Runtime Manifest                                 已完成
Step 3：建立可重建的 Python 环境                                    已完成
Step 4：Whisper Runtime Bootstrap                                    已完成
Step 5：可双击的一键构建入口与 Orchestration                        已完成
Step 6：严格打包门禁与 post-build smoke                              已完成
Step 7：模型下载完整性、失败恢复与重试                                已完成
Step 8：新机器 Clean-machine App / Model / Microphone / Transcription E2E ACTIVE
Step 9：普通用户 GitHub Release ZIP 验收                              待做
```

Deployment MVP 暂停点：

```text
完成 Step 8
-> 建立干净可复现 main checkpoint
-> 可以恢复 llm-sidecar-phase1 开发
```

Step 9 及 Developer ID / Notarization / DMG / GitHub Actions 属于后续 Release polish，不无限阻塞 LLM。

---

## 9. 下一步执行提示

继续时：

```text
1. 旧开发机先 pull 当前 main，确认 Step 7 implementation + Step 8 runtime governance 均同步
2. M5 做当前 checkpoint 的 App / model / microphone / real transcription regression
3. 新 M4 Max 保持 clean acceptance 状态，从 fresh clone main 开始
4. 新机优先真实 Finder 双击 Build ClassroomTranscriber.command，记录任何系统提示或失败
5. 不手工复制 .venv/.tools/external/Runtime/model，不用临时 PATH/DYLD 修补
6. App build PASS 后从 Model Manager 正式下载至少一个 manifest-managed model
7. 实际授权麦克风，Start -> 非空真实转写 -> Stop -> 检查 evidence layer
8. 任何新机缺口先记录，不在新机做永久手工修补；回旧机最小修复并 push 后再验收
9. Codex 默认不修改 deployment_runtime.md；Step 8 结果由人工 / ChatGPT 审核后更新
10. 不提前进入 Step 9 / Developer ID / notarization / LLM
```

---

## 10. 上下文恢复入口

恢复 `main` Deployment：

```text
1. docs/deployment_static.md
2. docs/deployment_runtime.md
3. PACKAGING.md
4. packaging/runtime_manifest.json
5. packaging/model_manifest.json
6. README.md
7. docs/工程细节.md
8. Step 8 相关 build / packaging / Model Manager / App E2E 证据
```

恢复 LLM：

```text
git switch llm-sidecar-phase1
-> docs/whisper_static.md
-> docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
