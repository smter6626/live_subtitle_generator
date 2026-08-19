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
Deployment Step 8：PASS
唯一 ACTIVE：Deployment Step 9 - 普通用户 GitHub Release ZIP 验收
```

当前一句话目标：

> **让符合硬件要求的 macOS Apple Silicon 机器无需手动配置开发或运行环境，仅需安装 App、下载模型，即可直接完成本地实时转录。**

当前状态：

```text
M4 Max clean-machine build / App / large-v3 / evidence E2E：PASS
M4 Max packaged large-v3 Metal backend runtime evidence：PASS
M5 current-checkpoint build / App / large-v3 / Chinese transcription regression：PASS
M5 packaged large-v3 Metal backend runtime evidence：PASS
M5 Stop -> Start / audio input reacquire：PASS
Deployment Developer MVP：PASS
Step 9：ACTIVE
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

下载事务审核确认：vendored upstream downloader 保持原样；downloader 只在 `.classroom-model-download-*` 隐藏 staging 中运行；nonzero、缺输出、size mismatch、SHA mismatch 均不得 publish final；验证成功后 `os.replace` 发布并原子写 receipt；无 receipt existing final 必须后台全量验证后才能复用；invalid final unavailable；retry 清理 managed stale staging；明确 Import 的 custom `.bin/.gguf` 继续走独立 local validation；网络下载和 SHA-256 均在后台 worker，不进入 Qt 主线程。

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
```

Step 8 已补充真实大型模型证据：M4 Max clean-machine App 通过 Model Manager 实际下载并验证 `large-v3` 成功，可选择并用于真实转写。

---

### Deployment Step 8：新机器 Clean-machine App / Model / Microphone / Transcription E2E

状态：**PASS / 已完成（2026-08-19）**。

#### M4 Max Clean-machine acceptance

Primary acceptance machine：

```text
MacBook Pro / Apple M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

真实路径：

```text
fresh clone main
-> Finder 真实双击 Build ClassroomTranscriber.command
-> 自动准备 uv / Python 3.12.14 / .venv
-> 自动准备 CMake 4.2.3
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
-> 实际音频转写 PASS
-> session evidence files PASS
```

M4 Max packaged Metal runtime probe 使用最终 App 内 `whisper-cli` + 同一份 verified large-v3 + `samples/jfk.wav`，原生日志确认：

```text
use gpu = 1
gpu_device = 0
ggml_metal_library_init: using embedded metal library
ggml_metal_device_init: GPU name: MTL0 (Apple M4 Max)
whisper_model_load: MTL0 total size = 3094.36 MB
whisper_backend_init_gpu: using MTL0 backend
ggml_metal_init: found device: Apple M4 Max
ggml_metal_init: picking default device: Apple M4 Max
```

11 秒 JFK sample 正常输出，`total time = 1316.25 ms`。因此确认 packaged large-v3 inference 实际启用 Apple M4 Max Metal GPU backend。日志同时初始化 BLAS/Accelerate/CPU 路径，所以准确表述是“Metal GPU backend active”，不是“整个 pipeline 100% GPU-only”。

M4 真实 session：

```text
/Users/smterpro/Documents/ClassroomTranscriber/outputs/2026-08-19_13-57-05
raw.txt        421 bytes
clean.txt      421 bytes
session.log   3014 bytes
config.json   1150 bytes
```

#### M5 current-checkpoint regression

Developer / Reference Machine：

```text
MacBook Air / Apple M5 / 16 GB / 512 GB / macOS 27 Beta
```

Git preflight：

```text
branch: main
HEAD before final Step 8 governance update: b59bae4c73bc4215964d048502067ba637e83a8a
origin/main: b59bae4c73bc4215964d048502067ba637e83a8a
worktree: clean
```

正式 one-entry build 实测：

```text
Python 3.12.14 bootstrap / smoke                         PASS
whisper.cpp pinned commit 8443cf05...                  PASS
GGML_NATIVE / -mcpu=native profile on M5               PASS
Metal + BLAS build                                     PASS
CLI + 6 dylib arm64                                    PASS
source dependency closure / --help smoke               PASS
PyInstaller                                            PASS
Runtime normalization                                  PASS
packaged architecture / dependency closure / RPath     PASS
model manifest / downloader                            PASS
ad-hoc codesign                                        PASS
bundled CLI smoke / isolated Runtime smoke             PASS
post-build Runtime verifier                            PASS
Build ClassroomTranscriber.command                     PASS
```

现有 large-v3：

```text
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/models/ggml-large-v3.bin
exact bytes: 3,095,033,483
```

M5 packaged Metal runtime probe 使用最终 App 内 `whisper-cli` + large-v3 + JFK sample，原生日志确认：

```text
use gpu = 1
gpu_device = 0
ggml_metal_device_init: GPU name: MTL0 (Apple M5)
ggml_metal_device_init: GPU family: MTLGPUFamilyApple10
ggml_metal_device_init: has tensor = true
whisper_model_load: MTL0 total size = 3094.36 MB
whisper_backend_init_gpu: using MTL0 backend
ggml_metal_init: found device: Apple M5
ggml_metal_init: picking default device: Apple M5
```

11 秒 JFK sample 正常输出，`total time = 2673.73 ms`。因此确认当前 packaged Runtime 在 Apple M5 上也实际启用 Metal GPU backend；M4 Max 与 M5 两代机器的 `GGML_NATIVE=ON` 当前版本实机运行证据均已闭环。

M5 App regression 额外选择 `Chinese`，使用 large-v3 实际转写中文音频成功，输出为连续可读中文。该结果用于 deployment regression，不视为正式 WER benchmark。

同一轮 UI 实测执行：

```text
Start
-> 实际中文非空转写
-> Stop
-> 再次 Start
-> 再次产生真实转写
-> Stop
```

截图中第一段时间轴运行至约 50+ 秒，Stop 后再次 Start 的新段从 `00:00` 重新计时并继续正常转写。由此记录：

```text
Stop / idle transition: PASS
second Start: PASS
audio input release / reacquire: no observed issue
second transcription: PASS
```

M5 最终 session evidence：

```text
/Users/smter-mac/Documents/ClassroomTranscriber/outputs/2026-08-19_15-30-15
raw.txt        1091 bytes
clean.txt      1091 bytes
session.log    2938 bytes
config.json    1121 bytes
```

四文件全部存在且非空。测试完成后仓库 `git status --short` 无输出。

#### Step 8 最终 PASS 判定

```text
1. M4 Max clean-machine 正式流程无隐藏手工修补                         PASS
2. Finder .command 真实双击                                           PASS
3. Fresh Clone 自动 Python/CMake/whisper Runtime + App build           PASS
4. M4 packaged Runtime strict verifier                                PASS
5. Model Manager 真实 large-v3 download + integrity transaction        PASS
6. model available / selectable                                       PASS
7. M4 actual non-empty transcription                                  PASS
8. M4 evidence layer                                                  PASS
9. M4 packaged large-v3 Metal GPU backend                             PASS
10. M5 current checkpoint formal build / packaged Runtime             PASS
11. M5 packaged large-v3 Metal GPU backend                            PASS
12. M5 actual Chinese transcription                                   PASS
13. M5 Stop -> Start / reacquire                                      PASS
14. M5 evidence layer                                                 PASS
15. final M5 worktree clean                                           PASS
```

**Deployment Step 8 PASS。Developer Deployment MVP 已达到。**

按长期合同，完成 Step 8 后已经允许恢复 `llm-sidecar-phase1`；Step 9 / Developer ID / notarization / DMG / GitHub Actions 不无限阻塞 LLM。

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 9 - 普通用户 GitHub Release ZIP 验收
```

### 3.1 Step 9 目标

验证普通用户交付路径，而不是再次验证源码开发环境：

```text
GitHub Release ZIP
-> 解压 ClassroomTranscriber.app
-> 双击启动
-> Model Manager 获取模型
-> 授予音频输入权限
-> Start Recording
-> 正常转录
-> Stop
-> 完整 session evidence layer
```

### 3.2 Step 9 当前边界

Step 9 不默认扩大为：

```text
Developer ID signing
Notarization
DMG
GitHub Actions release automation
minimum macOS 冻结
M1 / M2 / M3 实机支持
```

这些仍属于后续 Release polish，除非执行中发现它们是 ZIP 普通用户路径的真实 blocker。

### 3.3 Step 9 下一次执行前先确认

当前 runtime 只冻结了 Step 9 的交付目标，尚不假设 repo 已存在完整的 Release ZIP 生成 / 发布脚本。执行时先基于当前 `README.md`、`PACKAGING.md`、build/release scripts 与实际 repo 检查：

```text
1. 是否已有正式 ZIP 生成入口
2. ZIP 是否只包含完整 .app 及必要 release 文件，不包含模型/开发环境
3. 解压后 App bundle 是否保持 Runtime / dylib / signature / resource 完整性
4. 应如何在 GitHub Release 上发布并下载同一 artifact
5. Acceptance machine 如何以 ordinary-user 路径验证，而不借用 source tree
```

若正式 ZIP 入口缺失，再在旧 Developer / Reference Machine 上实现最小、可复现的 Release ZIP 流程；一个明确 Step 一个 commit，测试通过后 push `main`，再由 Acceptance Machine 测真实下载 artifact。

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. `GGML_NATIVE=ON` 已在 M4 Max 与 M5 上分别完成当前 profile 的实际 build + packaged large-v3 Metal inference PASS。注意这证明两个目标机器各自从当前源码构建出的 Runtime 可工作；未来单一 Release artifact 的跨代分发仍应由 Step 9 artifact acceptance 补充证据。
2. 正式 `GGML_OPENMP=OFF` 已消除 host OpenMP availability 漂移；旧 requested ON / effective OFF 仅保留为历史证据。
3. 第一版继续使用 `Contents/Resources/bin/` Runtime 布局；Step 6 已在该布局内建立严格 closure。
4. Python 合同仍保留 broad floor `>=3.11`，但正式可复现 build environment 是 `3.12.14 / >=3.12,<3.13`。
5. Developer source build 仍依赖 Git、网络、Apple Command Line Tools 与 macOS host 工具；普通 Release 用户不承担这些源码构建前提。
6. Step 6 当前使用 ad-hoc codesign；Developer ID / notarization 仍属于 Release polish。
7. minimum macOS 仍为 pending；当前只验证 macOS 27 Beta，不据此推断旧版本。
8. Model integrity contract 当前冻结 Hugging Face revision `5359861c739e955e79d9a303bcbc70fb988958b1`；vendored downloader 仍解析 upstream `main`，只有与冻结 size/SHA-256 完全匹配的 bytes 才接受；upstream bytes 漂移应 fail closed。
9. Integrity receipt 以当前合同 + size + mtime 作为快速 available 证据；它是性能优化，不替代首次 cryptographic validation。
10. 明确 Import 的 custom `.bin/.gguf` 不受官方 downloadable checksum contract 约束，仍只使用独立 local import validation。
11. whisper.cpp pinned commit 在 macOS 27 SDK 下会产生部分 Metal deprecated API compiler warning；M4/M5 build/runtime inference 均 PASS，当前不升级 upstream。
12. 旧 pseudo-oral 测试输出仍是既有非阻塞项。

---

## 5. 非阻塞 UX / Product backlog

Step 8 实机验收暴露以下项目，均不回滚 Deployment MVP：

1. **Model download progress feedback**：large-v3 下载期间后台正常运行，但 UI 没有 progress/spinner/byte counter，视觉上容易误判为卡死。
2. **Model selection confirmation**：选择模型成功后增加约 2 秒 non-modal transient toast，例如 `已成功选择模型：large-v3`。
3. **Configurable output root**：默认继续 `~/Documents/ClassroomTranscriber/`，允许用户改根目录；`outputs/<timestamp>/raw.txt|clean.txt|session.log|config.json` 子结构必须保持不变；配置持久化，只影响后续新 session。
4. **Current-model panel readability**：长绝对路径在当前模型区域被截断且无法访问完整内容；后续优先模型名/大小，路径 middle-elide + tooltip/可复制，必要时提供滚动。

这些项目可在 Step 9 之后处理，或由用户显式调整优先级后作为独立 product-polish step 处理；不要把它们混入稳定 ASR 主链路修改。

---

## 6. 当前未敲定参数

```text
# Step 9
正式 Release ZIP 生成 / 发布入口是否已经存在
单一 Release artifact 在 M4 Max / M5 间的实际 portability
GitHub Release 下载后的 Gatekeeper / quarantine 行为
ordinary-user Model Manager / audio permission / transcription / evidence E2E

# UX / Product backlog
Model download progress / spinner / bytes feedback
Model selection success transient toast（约 2 秒）
Configurable output root
Current-model panel long-path readability / tooltip / copy / optional scroll

# 后续 Release
minimum macOS（当前不承诺旧系统，保持未设置）
Developer ID signing / notarization 实施时间点
DMG
GitHub Actions release automation
```

---

## 7. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine；MacBook Air / Apple M5 / 16 GB / 512 GB / macOS 27 Beta。Step 8 current-checkpoint build + packaged Runtime + large-v3 Metal + Chinese transcription + Stop/Start regression：PASS。

新 Mac：Clean-machine Acceptance Machine；MacBook Pro / Apple M4 Max / 48 GB / 1 TB / macOS 27 Beta。Step 8 clean-machine build + UI large-v3 download/integrity + packaged Metal + actual transcription + evidence：PASS。

当前可以记录：**项目已在 Apple M4 Max 与 Apple M5 设备上实际验证当前 Deployment checkpoint。** M1 / M2 / M3 仅理论兼容，不作保证；旧版 macOS 当前不作保证。

长期职责仍以 `deployment_static.md` 为准：默认继续在旧 Developer / Reference Machine 实现和回归，在 M4 Max Acceptance Machine 验证正式 artifact。若未来希望把 M4 Max 改成第二开发机，应先显式调整长期角色合同，而不是在验收机上直接积累项目专用手工开发状态。

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
Step 8：新机器 Clean-machine App / Model / Microphone / Transcription E2E 已完成 / PASS
Step 9：普通用户 GitHub Release ZIP 验收                              ACTIVE
```

Deployment Developer MVP 暂停点已经达到：

```text
Step 8 PASS
-> 干净可复现 main checkpoint 已形成
-> 可以恢复 llm-sidecar-phase1 开发
```

Step 9 及 Developer ID / Notarization / DMG / GitHub Actions 属于后续 Release 路线，不无限阻塞 LLM。

---

## 9. 下一步执行提示

继续 `main` Deployment 时只执行 Step 9：

```text
1. 在 Developer / Reference Machine pull 当前 main，确认 main + clean worktree
2. 读取 deployment_static.md / deployment_runtime.md / PACKAGING.md / README.md
3. 先审查 repo 现有 Release ZIP / release artifact 生成方式，不假设已有或缺失
4. 若已存在正式 ZIP 入口：验证它只打包完整 App，不打包模型/开发环境，并检查解压后 Runtime 完整性
5. 若不存在：设计并实现最小可复现 ZIP 生成入口，一个 Step 一个 commit，不改稳定 ASR 主链路
6. push main 后，在 Acceptance Machine 从 GitHub Release 实际下载同一 ZIP artifact
7. ordinary-user 路径：解压 -> 双击 App -> Model Manager -> audio permission -> Start -> 非空转写 -> Stop -> evidence layer
8. 记录 Gatekeeper / quarantine / signing 实际行为；只有成为普通用户路径 blocker 时才升级 Developer ID/notarization
9. Codex 默认只读取 deployment_runtime.md，不主动修改；实现后由 ChatGPT / 人工审核再更新 runtime
```

若用户选择先恢复 LLM，可直接切回 `llm-sidecar-phase1`；Step 9 保持 Deployment ACTIVE，不与 LLM runtime 混用。

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
8. Step 8 M4 clean-machine / M4+M5 Metal runtime / M5 regression 实测证据
```

恢复 LLM：

```text
git switch llm-sidecar-phase1
-> docs/whisper_static.md
-> docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
