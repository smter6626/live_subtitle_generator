# deployment_runtime.md

最后更新：2026-08-19  
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

当前 Step 8 状态：

```text
M4 Max clean-machine 核心 E2E：PASS
M4 Max packaged large-v3 Metal backend runtime evidence：PASS
M5 当前 checkpoint 实机 App / transcription regression：PENDING
Step 8：ACTIVE
```

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

主工作区正式 orchestrator、第二次 idempotent 执行、throwaway Fresh Clone、`.command` shell 等价调用、36 项联合 unittest 与 `git diff --check` 全部 PASS。Finder GUI 真实双击已在 Step 8 的 M4 Max clean-machine 实测中补齐。

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

Step 8 已补充真实大型模型证据：M4 Max clean-machine App 通过 Model Manager 实际下载并验证 `large-v3` 成功，可选择并用于真实转写。

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 8 - 新机器 Clean-machine App / Model / Microphone / Transcription E2E
```

### 3.1 目标

在真实验收机上验证 Developer Deployment MVP：不靠旧开发机历史环境、不靠临时人工修补，从干净 `main` 的正式入口得到 App，再通过 App 自己完成模型获取与真实音频转写，最终生成完整 session evidence layer。

Primary clean-machine acceptance target：

```text
MacBook Pro / Apple M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

M5 Developer / Reference Machine 仍需做当前 checkpoint 的实际 App/runtime/ASR regression，用于形成 M5 当前 checkpoint 实际验证证据；但它不是 clean-machine 证据的替代品。

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

### 3.3 M4 Max Clean-machine 实测结果（2026-08-19）

状态：**核心 E2E PASS**。

实际验收路径：

```text
fresh clone main
-> Finder 真实双击 Build ClassroomTranscriber.command
-> 自动下载并准备 uv 0.12.5
-> 自动安装 managed Python 3.12.14
-> uv.lock frozen sync / .venv
-> 自动下载并校验 CMake 4.2.3
-> 自动获取 pinned whisper.cpp 8443cf05...
-> M4 Max 本机编译 whisper-cli + required dylib
-> source Runtime architecture / closure / --help smoke PASS
-> PyInstaller Release build
-> packaged Runtime normalize + ad-hoc codesign + strict verifier PASS
-> dist/ClassroomTranscriber.app
-> App 启动
-> Model Manager 自选模型下载目录
-> UI 正式下载 large-v3
-> hidden staging / exact-size / SHA-256 / atomic publish PASS
-> large-v3 available / selectable
-> 使用实际 YouTube 音频进行转写
-> UI 出现真实非空转写
-> session evidence files 生成
```

关键 Build / Runtime 证据：

```text
Python: 3.12.14
PyInstaller: 6.22.1
PySide6 / Qt: 6.11.1
whisper.cpp: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
architecture: arm64
GGML_NATIVE=ON build on M4 Max: PASS
CLI + 6 dylib architecture: PASS
source dependency closure: PASS
source whisper-cli --help: PASS
packaged Runtime components: PASS
packaged architecture: PASS
packaged dependency closure / RPath: PASS
bundled downloader: PASS
model integrity manifest: PASS
ad-hoc codesign verification: PASS
bundled CLI smoke: PASS
isolated Runtime smoke: PASS
packaged large-v3 Metal backend runtime initialization: PASS
```

为确认实际计算 backend，而不是仅依赖 UI 中的 `whisper.cpp Metal` 标签，使用**最终 App 内同一个 packaged `whisper-cli` + 同一份已验证 large-v3 + whisper.cpp `samples/jfk.wav`**执行独立 runtime probe。关键原生日志：

```text
use gpu = 1
gpu_device = 0
ggml_metal_library_init: using embedded metal library
ggml_metal_device_init: GPU name: MTL0 (Apple M4 Max)
whisper_model_load: MTL0 total size = 3094.36 MB
whisper_backend_init_gpu: using MTL0 backend
ggml_metal_init: found device: Apple M4 Max
ggml_metal_init: picking default device: Apple M4 Max
whisper_backend_init: using BLAS backend
system_info: ... MTL : EMBED_LIBRARY = 1 ... ACCELERATE = 1 ...
```

11 秒 JFK sample 正常输出转写，`total time = 1316.25 ms`。因此可以确认 **packaged large-v3 inference 已实际启用 Apple M4 Max Metal GPU backend**；同时 whisper.cpp 也初始化 BLAS/Accelerate 和 CPU 路径，因此准确表述是“Metal GPU backend active / 参与主要推理”，而不是“整个 pipeline 100% 只使用 GPU”。

其中 `tensor API disabled for pre-M5 and pre-A19 devices` 仅表示 M4 Max 不启用该较新的 Metal tensor API；后续日志明确初始化并使用 `MTL0 (Apple M4 Max)`，所以它不是 Metal fallback 或 GPU 未启用证据。

CMake 在 macOS 27 SDK 下出现 whisper.cpp / Metal upstream deprecation warnings，但编译、链接和 Runtime verifier 均成功；当前不作为 blocker。

真实模型证据：

```text
model: large-v3
expected exact bytes: 3,095,033,483
下载方式: App -> Model Manager
下载位置: 用户通过 UI 自选
staging: .classroom-model-download-*
integrity transaction: PASS
final state: available / selectable
real transcription with large-v3 on M4 Max: PASS
```

这证明当前冻结的 `GGML_NATIVE=ON` profile 至少在 M4 Max 上能够完成实际构建并运行 large-v3 推理，不再只是 `--help` smoke 证据；额外 packaged CLI probe 已确认 Metal GPU backend 实际 active。

真实 session：

```text
/Users/smterpro/Documents/ClassroomTranscriber/outputs/2026-08-19_13-57-05
```

Evidence layer 实测：

```text
raw.txt        421 bytes   非空
clean.txt      421 bytes   非空
session.log   3014 bytes   非空
config.json   1150 bytes   非空
```

未观察到此次 Deployment 功能破坏 evidence layer。session 已形成完整四文件结构。当前没有单独的系统级 instrumentation 去证明麦克风 resource release；若后续发现 Stop / 再次 Start 异常才升级为 blocker，否则不因缺少额外 instrumentation 阻塞当前 M4 acceptance。

### 3.4 M4 Max 非阻塞 UX / 功能观察

M4 实机首次暴露以下 polish 项，不阻塞 Deployment MVP：

1. **模型下载缺少明显进度反馈**：large-v3 下载期间后台 staging 文件持续增长且任务正常运行，但 Model Manager 控件被禁用、没有 progress/spinner/byte counter，视觉上容易误判为 UI 卡死；实际下载最终成功。
2. **模型选择成功反馈不足**：建议选择模型成功后显示非模态短暂提示，例如 `已成功选择模型：large-v3`，约 2 秒后自动消失；不要使用必须点击 OK 的阻塞式对话框。
3. **输出根目录应支持用户自定义**：当前 session 默认位于 `~/Documents/ClassroomTranscriber/outputs/<timestamp>/`。后续允许用户把根目录例如改为 `~/Workspace/transcriptionTXT/`，但 `outputs/<timestamp>/` 及 `raw.txt / clean.txt / session.log / config.json` 结构保持不变；应持久化选择、验证目录可写，并只影响后续新 session，不迁移正在进行的 session。
4. **主界面“当前模型”区域长路径可读性不足**：当前模型名称、大小和绝对路径在窄区域换行后被下方控件截断，且无法滚动查看。后续应优化信息层级，例如模型名/大小优先显示、长路径 middle-elide + tooltip/可复制，必要时提供可滚动区域；不要让长路径破坏左侧 panel 布局。

这些项目记录为后续 UX / product improvement，不回滚 Step 7/8，也不为了当前验收临时改 UI。

### 3.5 M5 回归要求

旧 M5 Developer / Reference Machine 在当前 Step 8 checkpoint 上仍需至少验证：

```text
pull 当前 main
正式 App build / packaged Runtime gate PASS
App 启动
至少一个 integrity-valid model 可用
Start / Stop
真实非空转写
完整 evidence layer
```

该结果用于证明当前 checkpoint 在 M5 上实际运行；它不能被描述为 fresh clean-machine acceptance。

### 3.6 Step 8 PASS 判定

Step 8 只有在以下条件同时满足时 PASS：

1. M4 Max clean-machine 正式流程无隐藏手工修补；**PASS**
2. Finder `.command` 真实双击入口至少一次实际 PASS；**PASS**
3. Fresh Clone 自动准备 Python/CMake/whisper Runtime 并构建 App；**PASS**
4. Step 6 packaged Runtime verifier 在新机 PASS；**PASS**
5. Model Manager 实际下载 manifest-managed model，Step 7 integrity transaction PASS；**PASS（large-v3）**
6. 下载后的 model 状态为 available，可正常选择；**PASS**
7. App 获得音频输入能力并成功 Start；**PASS（实际转写已产生）**
8. 实际音频产生真实非空 raw / clean 转写；**PASS**
9. packaged large-v3 Runtime 实际启用 Metal GPU backend；**PASS（MTL0 / Apple M4 Max）**
10. Stop / 麦克风释放无异常；**未单独 instrumentation，当前无异常报告**
11. `raw.txt`、`clean.txt`、`session.log`、`config.json` 全部生成且保持 evidence-layer 语义；**PASS**
12. M5 当前 checkpoint 实机 App / transcription regression PASS；**PENDING**
13. 未把新机的一次性人工修补当作正式通过；**PASS**

因此当前 Step 8 继续 ACTIVE，主要剩余 blocker 是 **M5 当前 checkpoint 实机 regression**。若 M5 regression PASS 且没有新 Stop/麦克风异常证据，即可完成 Step 8。

### 3.7 失败处理

Step 8 原则上是验收，不主动新增功能。出现失败时先完整记录：机器、macOS、入口、错误日志、缺失依赖、是否发生 Gatekeeper / permission / network 问题。

如果属于项目正式路径缺口：

```text
验收机停止修补
-> 回 Developer / Reference Machine 定位和实现最小修复
-> 一个明确 bugfix commit + push main
-> ChatGPT / 人工审核
-> 验收机重新验证相关路径
```

不得直接在验收机手工复制缺失资源后宣布 PASS。

### 3.8 Step 8 边界

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

1. `GGML_NATIVE=ON` 已在 M4 Max clean-machine 上完成实际 build + large-v3 transcription PASS，并由 packaged CLI probe 确认 Metal GPU backend active；M5 仍需当前 checkpoint 的实际 regression 才形成双机当前版本证据。
2. 正式 `GGML_OPENMP=OFF` 已消除 host OpenMP availability 漂移；旧 requested ON / effective OFF 仅保留为历史证据。
3. 第一版继续使用 `Contents/Resources/bin/` Runtime 布局；Step 6 已在该布局内建立严格 closure。
4. Python 合同仍保留 broad floor `>=3.11`，但正式可复现 build environment 是 `3.12.14 / >=3.12,<3.13`。
5. Developer source build 仍依赖 Git、网络、Apple Command Line Tools 与 macOS host 工具；普通 Release 用户不承担这些源码构建前提。
6. Step 6 当前使用 ad-hoc codesign；Developer ID / notarization 仍属于 Release polish。
7. 当前普通用户最小发布形式仍为 ZIP + `.app`；Step 9 不阻塞 Step 8 Developer MVP。
8. minimum macOS 仍为 pending；当前只验证 macOS 27 Beta，不据此推断旧版本。
9. Model integrity contract 当前冻结 Hugging Face revision `5359861c739e955e79d9a303bcbc70fb988958b1`；vendored downloader 仍解析 upstream `main`，但只有与冻结 size/SHA-256 完全匹配的 bytes 才会被接受。若 upstream main 后续替换为新 bytes，下载会 fail closed，需显式维护 manifest，而不能静默接受新 artifact。
10. Integrity receipt 以当前合同 + size + mtime 作为快速 available 证据；文件 stat 变化会使 receipt 失效并要求重新验证。它是性能优化，不替代首次 cryptographic validation。
11. 明确 Import 的 custom `.bin/.gguf` 不受官方 downloadable checksum contract 约束，仍只使用独立本地 import validation；这属于产品设计边界而非 official model integrity 保证。
12. M4 Max 实测发现四个非阻塞 UX / product polish：Model Manager 下载缺少 progress feedback、选择模型成功缺少短暂 confirmation toast、输出根目录不可自定义、当前模型长路径显示被截断且不可访问完整内容。
13. whisper.cpp pinned commit 在 macOS 27 SDK 下产生部分 Metal deprecated API compiler warning，但 M4 build/runtime/large-v3 inference PASS；当前只记录，不在 Deployment MVP 中升级 upstream。
14. M4 Max 的 Metal runtime probe 同时初始化 Metal GPU 与 BLAS/Accelerate/CPU 路径；支持“Metal GPU backend active”结论，但不应描述为整个 pipeline 100% GPU-only。
15. 旧 pseudo-oral 测试输出仍是既有非阻塞项，不归 Deployment Step 8 修复。

---

## 5. 当前未敲定参数

```text
# Step 8
M5 当前 checkpoint App / large-v3-or-other-valid-model / real transcription regression
M5 当前 checkpoint 的 GGML_NATIVE 实际运行结果
是否需要额外独立做一次 Stop -> 再 Start 作为 microphone release UX 证据（若正常使用未出现异常，可不作为 blocker）

# 后续 UX / Product
Model download progress / spinner / bytes feedback
Model selection success transient toast（约 2 秒）
Configurable output root（默认保持 ~/Documents/ClassroomTranscriber；session 子结构不变）
Current-model panel long-path readability / tooltip / copy / optional scroll

# 后续 Release
minimum macOS（当前不承诺旧系统，保持未设置）
Developer ID signing / notarization 实施时间点
GitHub Release 正式版本和自动发布流程
```

---

## 6. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine，用于开发、自动测试、clean-repo simulation、构建验证、稳定 ASR 回归、Commit / Push；当前实际硬件为 MacBook Air / M5 / 16 GB / 512 GB / macOS 27 Beta。当前 Step 8 regression：PENDING。

新 Mac：Clean-machine Acceptance Machine；当前实际硬件为 MacBook Pro / M4 Max / 48 GB / 1 TB / macOS 27 Beta。

M4 Max 本次 clean-machine acceptance 已证明：Fresh Clone、Finder 正式构建入口、Python/CMake/whisper bootstrap、strict packaged Runtime、App launch、UI 自选模型路径、UI large-v3 下载+完整性验证、large-v3 实际转写、四文件 evidence layer 均 PASS，且没有通过手工复制 `.venv/.tools/external/Runtime/model` 或临时 PATH/DYLD 修补正式流程。额外 packaged CLI runtime probe 已确认 `use gpu = 1`、`gpu_device = 0`、embedded Metal library、`MTL0 (Apple M4 Max)` 与 `using MTL0 backend`，因此实际 Metal GPU backend 使用已形成直接证据。

对外支持声明：M4 Max 当前可以记录为**项目已实际验证当前 Deployment checkpoint 的 clean-machine build + large-v3 transcription + Metal GPU backend active**。M5 只有完成当前 checkpoint regression 后，才将当前版本的 M5 实际验证一并闭环。M1 / M2 / M3 仅理论兼容，不作保证。旧版 macOS 当前不作保证。

---

## 7. 当前已知 Failure Modes / Step 8 观察点

### Build / Packaging

- M4 Max Fresh Clone Finder `.command` 已实际 PASS；自动 Python/CMake/whisper Runtime 准备与 strict packaged Runtime gate 均 PASS。
- M4 编译期间出现 pinned whisper.cpp 对 macOS 27 Metal SDK 的 deprecation warning；非 fatal，当前不阻塞。
- 新机未发现需要项目外手工准备 Runtime、CMake、Python 或模型的 deployment gap。

### Whisper Runtime

- `GGML_NATIVE=ON` 已在 M4 Max 上完成实际 build + large-v3 inference PASS。
- 使用最终 App 内 packaged `whisper-cli` + 已验证 large-v3 + JFK sample 的 runtime probe 直接记录 `use gpu = 1`、`gpu_device = 0`、`ggml_metal_device_init: GPU name: MTL0 (Apple M4 Max)`、`whisper_backend_init_gpu: using MTL0 backend`、`ggml_metal_init: found device: Apple M4 Max`；因此 M4 Max 实际 Metal GPU backend 使用 PASS。
- 同一日志同时存在 `using BLAS backend` 与 CPU/Accelerate capability，说明 GPU 与 CPU/BLAS backend 可协同存在；不得将其误述为“CPU 完全未参与”。
- M5 的当前 checkpoint actual App transcription regression 仍待补齐，之后才能把双机 portability 当前版本证据闭环。

### Model Manager

- Step 7 的 checksum/staging/atomic publish 已在 M4 Max 首次真实 large-v3 upstream download 中 PASS。
- 用户可通过 UI 自选模型下载位置。
- 下载 large-v3 期间后台工作正常，但 UI 没有 progress feedback，视觉上容易误判为“卡死”；本次最终成功，因此记录为非阻塞 UX issue。
- 选择模型后建议增加 2 秒左右的 non-modal success toast；非阻塞 UX issue。
- 主界面当前模型区域对长绝对路径显示不清、内容被截断且无法访问完整信息；记录为非阻塞 UX issue。
- vendored downloader 指向 upstream `main`；若未来 bytes 与 frozen contract 不符，应继续 fail closed。

### ASR / Evidence

- M4 Max 已通过实际 YouTube 音频 + large-v3 产生非空真实转写。
- session `2026-08-19_13-57-05` 产生完整 `raw.txt / clean.txt / session.log / config.json`，四文件均非空。
- 当前 session output root 默认为 `~/Documents/ClassroomTranscriber/`；用户希望后续可配置根目录，同时保持 `outputs/<timestamp>/` 与四文件 evidence 子结构不变。记录为非阻塞 product improvement。
- 当前没有单独 instrumentation 的 microphone-release 证明；未报告实际 Stop/再次 Start 异常，因此不单独作为当前 blocker。

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
Step 8：新机器 Clean-machine App / Model / Microphone / Transcription E2E ACTIVE（M4 PASS / M5 regression pending）
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

继续时只做 Step 8 收尾：

```text
1. M5 Developer / Reference Machine git fetch + git pull --ff-only origin main
2. 确认 main / clean worktree / HEAD == origin/main
3. 读取 deployment_static.md / deployment_runtime.md
4. 使用当前正式入口完成 App build / packaged Runtime gate
5. 启动 App，使用 integrity-valid model
6. Start -> 实际非空转写 -> Stop
7. 检查 raw.txt / clean.txt / session.log / config.json
8. 若 M5 regression PASS，不额外改代码；汇报实际证据
9. 若失败，先记录并判定是否 deployment bug，不为通过而临时修改 ASR / Runtime
10. Codex 默认不修改 deployment_runtime.md；最终 Step 8 状态由人工 / ChatGPT 更新
11. 不提前进入 Step 9 / Developer ID / notarization / LLM
```

M4 Max 当前不需要为了 Step 8 重做 Fresh Clone；本次 clean-machine sequence 已形成有效证据。只有发现新的 M4 blocker 或需要复现特定失败时才重跑对应路径。

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
8. Step 8 M4 clean-machine / Metal runtime / M5 regression 实测证据
```

恢复 LLM：

```text
git switch llm-sidecar-phase1
-> docs/whisper_static.md
-> docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
