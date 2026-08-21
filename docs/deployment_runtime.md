# deployment_runtime.md

最后更新：2026-08-20  
文档角色：Deployment 工作线动态执行状态（runtime state）

本文件只记录 Classroom Live Transcriber 在 `main` 分支上的 deployment / packaging / clean-machine reproducibility / bugfix 执行状态。

长期稳定合同见：`docs/deployment_static.md`。

LLM 功能线动态状态仍由 `llm-sidecar-phase1` 分支中的 `docs/whisper_runtime.md` 维护。两条工作线不得混用 ACTIVE step、完成记录或验收状态。

---

## 0. 使用规则

每完成一个 Deployment Step 后：

1. 将当前 ACTIVE step 标记为已完成；
2. 记录实现 commit、实际产物、测试与审核结果；
3. 若仍有下一步则激活下一步，并保证全文件只有一个 ACTIVE Step；若当前 Deployment 工作线已完成，则明确记录“当前无 ACTIVE Step”；
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
当前实现 checkpoint：02cc099ee674631ce8d5f5886966846a6623caa5
checkpoint 内容：chore: add reproducible release zip packaging
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
Deployment Step 8：PASS
Step 9 总体：PASS
Step 9A：PASS
Step 9B：PASS
Step 9C：PASS
当前 Deployment ACTIVE：无（Step 9 已完成，等待用户选择下一工作线）
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
Step 9A Release ZIP tooling / round-trip verification：PASS
Step 9B GitHub Release 0.2.0 publication / remote asset verification：PASS
Step 9C M5 same-artifact ordinary-user / portability acceptance：PASS
Step 9C M4 Max primary ordinary-user classroom acceptance：PASS
Deployment Step 9：PASS
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

## 3. Deployment Step 9：Release ZIP / GitHub Release / ordinary-user acceptance

Step 9 状态：**PASS / 已完成（2026-08-20）**。

```text
Step 9A：补齐正式 Release ZIP 生成与本地验证入口              PASS
Step 9B：使用已审核入口实际创建并发布 GitHub Release 0.2.0   PASS
Step 9C：人工 Release 下载 / ordinary-user / same-artifact 验收 PASS
```

### 3.1 Step 9 总目标

验证普通用户交付路径，而不是再次验证源码开发环境：

```text
GitHub Release ZIP
-> 解压 ClassroomTranscriber.app
-> 双击启动
-> Model Manager 获取模型
-> 音频输入权限
-> Start Recording
-> 正常转录
-> Stop
-> 完整 session evidence layer
```

Step 9 不默认扩大为：

```text
Developer ID signing
Notarization
DMG
GitHub Actions release automation
minimum macOS 冻结
M1 / M2 / M3 实机支持
UX/Product backlog 修复
```

这些继续作为后续独立工作；当前没有实证表明它们是 0.2.0 ordinary-user ZIP 路径的 blocker。

### 3.2 Step 9A：正式 Release ZIP 生成与本地验证入口

状态：**PASS / 已完成并经 GitHub 实际实现审核通过（2026-08-19）**。

实现 commit：

```text
02cc099ee674631ce8d5f5886966846a6623caa5
chore: add reproducible release zip packaging
```

GitHub compare：相对 Step 9A 起点 `aff768978b9800bc10577cbef9f2314c5124f9bc` ahead 1 / behind 0，仅修改 4 个 Step 9A 允许范围文件：

```text
PACKAGING.md
README.md
scripts/build_release_zip.py
testCodes/test_release_zip.py
```

未修改稳定 ASR、UI、Model Manager、model integrity、model manifest 或 LLM sidecar。

正式 Release ZIP 入口：

```text
./Build\ ClassroomTranscriber.command
.venv/bin/python scripts/build_release_zip.py --version <version>
```

`--version` 为必填显式输入；脚本从 `packaging/runtime_manifest.json` 读取 artifact filename / payload contract，不自动猜版本、不修改项目版本、不创建 tag / GitHub Release、不上传 asset。

ZIP 实现采用 macOS `/usr/bin/zip -r -y -X`，其中 `-y` 保留 symlink、`-X` 排除易变 ZIP extra fields；解压采用 macOS `ditto`。正式脚本会：

```text
验证 clean source / locked project Python
-> 对 dist/ClassroomTranscriber.app 复用现有 packaged Runtime verifier
-> snapshot App bundle bytes / mode / symlink target
-> 生成 staging ZIP
-> 校验 ZIP entry boundary + CRC
-> 解压到 source tree 外的临时目录
-> 比较完整 bundle structure / bytes / permissions / symlinks
-> 对 extracted App 再次复用 packaged Runtime verifier
-> 所有验证 PASS 后才 os.replace 发布最终 ZIP
-> 输出 version / source commit / exact bytes / SHA-256
```

脚本额外拒绝模型 binary、`.venv`、`.tools`、`external`、Git/source metadata、用户 settings、broken/out-of-bundle symlink 等非 Release payload。

Step 9A 单元测试新增 10 项，覆盖：显式安全 version、locked project Python、dirty worktree rejection、bytes/mode/symlink round-trip、同一 App byte-identical ZIP、extracted verifier failure 不发布 artifact、model/dev file rejection、ZIP boundary、host symlink rejection、SHA-256 exactness。

M5 Developer / Reference Machine 实测：

```text
正式 one-entry build / Python / whisper Runtime / Step 6 packaged verifier PASS
release tests                                                   PASS / 10
全 testCodes suite                                              PASS / 75
git diff --check                                                PASS
final worktree                                                  clean
```

Step 9A dry-run artifact：

```text
version: 0.0.0-step9a
source commit: 02cc099ee674631ce8d5f5886966846a6623caa5
artifact: ClassroomTranscriber-0.0.0-step9a-macOS-AppleSilicon.zip
exact bytes: 46,564,856
SHA-256: 9aad6f881a8f8ed54600e5079998a7564701972714edee5b0f3362a114fc5529
ZIP entries: 492
source/extracted symlinks: 117 / 117
same App second packaging: byte-identical PASS
```

独立 extracted-App 验证再次 PASS：Runtime components、arm64-only、dependency closure / RPath、codesign、downloader、model manifest、bundled CLI smoke、isolated Runtime smoke 全部正常；ZIP 顶层唯一 payload 为 `ClassroomTranscriber.app`，模型 / `.venv` / `.tools` / `external` / source metadata / 用户配置均为 0。

ChatGPT GitHub 审核确认：实现复用现有 `verify_packaged_runtime`，没有复制第二套 Runtime contract；最终 artifact 只在 source App verifier、ZIP CRC/boundary、round-trip snapshot 和 extracted-App verifier 全部 PASS 后发布。Step 9A 可接受。

非阻塞 release-engineering caveat：`build_release_zip.py` 的正式合同是“**先正式 build，再 package**”；脚本本身验证 clean worktree 和当前 source commit，但不单独嵌入/比对 App 的源码构建 provenance marker。因此正式发布必须在目标 source commit 上重新执行正式 one-entry build，并紧接着从该次 `dist/ClassroomTranscriber.app` 生成唯一 Release ZIP；不得复用来源不明的旧 `dist` App 后仅凭 clean HEAD 宣布 source binding。

Step 9A 未创建 tag、未创建 GitHub Release、未上传 asset，符合边界。

### 3.3 Step 9B：实际 GitHub Release 发布

状态：**PASS / 已完成（2026-08-20）**。

正式发布：

```text
version/tag: 0.2.0
release title: Classroom Transcriber 0.2.0
prerelease: No
source commit / tag target: 314326ab30c033090d1287793e3a47ef8f2c8971
artifact: ClassroomTranscriber-0.2.0-macOS-AppleSilicon.zip
exact bytes: 46,549,839
SHA-256: 09722cd4502103ab8f5751365438975cf05f2b1902dd7005f3c7e32b62dfabbd
```

GitHub Release 页面与 `gh release view 0.2.0` 显示：Release 已发布、title 正确、asset 存在，Release notes 明确 0.2.0 修复 deployment/runtime dependency issues，提供 self-contained macOS Apple Silicon downloadable release；模型不内置，继续由 Model Manager 下载或导入。

发布后在 M5 Developer / Reference Machine 执行远端核验：

```text
git fetch origin --tags
gh release view 0.2.0
git rev-list -n 1 0.2.0
```

确认 tag `0.2.0` 精确指向：

```text
314326ab30c033090d1287793e3a47ef8f2c8971
```

随后通过 `gh release download 0.2.0` 重新从 GitHub 获取正式 asset 到 `/tmp`，得到：

```text
filename: ClassroomTranscriber-0.2.0-macOS-AppleSilicon.zip
exact bytes: 46,549,839
SHA-256: 09722cd4502103ab8f5751365438975cf05f2b1902dd7005f3c7e32b62dfabbd
```

该 SHA-256 与 Release notes、GitHub asset digest 完全一致。由此确认 GitHub 上实际可下载的 0.2.0 asset identity 已闭环；Step 9B PASS。

注意：上述 `gh release download` 仅属于 Step 9B 的 remote artifact verification，不替代 Step 9C 的浏览器/Finder ordinary-user path。

### 3.4 Step 9C：人工 ordinary-user Release 验收

状态：**PASS / 已完成（2026-08-20）**。

Step 9C 保留了真实 ordinary-user GUI 交互。浏览器下载、Finder 解压、Finder 启动、Gatekeeper GUI、Model Manager、Start / Stop 均由人工真实执行，没有使用 source tree / Terminal 启动替代。

#### 9C-2 M5 same-artifact portability + ordinary-user acceptance

状态：**PASS**。

正式 Release identity：

```text
tag: 0.2.0
source commit: 314326ab30c033090d1287793e3a47ef8f2c8971
browser-downloaded ZIP: /Users/smter-mac/Downloads/ClassroomTranscriber-0.2.0-macOS-AppleSilicon.zip
exact bytes: 46,549,839
SHA-256: 09722cd4502103ab8f5751365438975cf05f2b1902dd7005f3c7e32b62dfabbd
```

Finder 解压 App：

```text
/Users/smter-mac/Downloads/ClassroomTranscriber-0.2.0-acceptance/ClassroomTranscriber.app
```

首次启动前存在 `com.apple.quarantine`，来源记录为 Chrome。Finder 双击后出现“Apple 无法验证”警告；用户通过 System Settings -> Privacy & Security -> Open Anyway -> 输入密码成功启动。未使用 `xattr -d`、`spctl disable`、手工重签或 bundle patch。最终测试进程来自该 Release App 的 App Translocation 路径，并与 Finder 解压 App 的 binary/signature resource hash 对应，排除了旧 `/Applications` 实例或 `repo/dist` App。

M5 Release App 的 Model Manager 使用 fresh 目录：

```text
/Users/smter-mac/Downloads/ClassroomTranscriber-0.2.0-models-release-app
```

通过 Release App 自己下载 `base.en`：

```text
file: ggml-base.en.bin
bytes: 147,964,211
integrity receipt: present
status: available
selectable: PASS
```

旧目录中无 receipt 的同名模型被正确拒绝为 `integrity unverified`，没有用于最终验收。

GUI 实测：English / base.en，microphone/capture、Start、多个 ASR chunk 的真实非空转写、Stop、idle、Stop 后再次 Start 全部 PASS；未观察到 crash、freeze 或 Backend Error。

M5 Release session：

```text
/Users/smter-mac/Documents/ClassroomTranscriber/outputs/2026-08-20_11-24-22
raw.txt        407 bytes
clean.txt      345 bytes
session.log   2477 bytes
config.json   1167 bytes
```

四文件全部存在且非空；日志记录两个 chunk 推理并以 `Worker stopped` 正常结束。

同一 Release App 内 packaged `whisper-cli` 在 M5 直接 Runtime probe：

```text
architecture: Mach-O arm64
use gpu = 1
gpu_device = 0
GPU = MTL0 (Apple M5)
backend = using MTL0 backend
found device: Apple M5
picking default device: Apple M5
JFK inference exit: 0
JFK transcript: PASS
```

因此正式确认：**同一个由 M4 Max release engineering 构建并发布的 0.2.0 Release artifact 可在 Apple M5 上直接运行并使用 Metal；当前 `GGML_NATIVE=ON` 未暴露 M4 Max -> M5 的 cross-generation artifact incompatibility。**

M5 最终 repo `main` / HEAD / origin/main 一致，`git status --short` 空；本轮 zero source changes、zero commits、未重新 build、未修改 tag / Release / asset / runtime。

#### 9C-1 M4 Max primary ordinary-user acceptance

状态：**PASS**。

M4 Max 使用 GitHub Release 页面实际下载的 0.2.0 ZIP，Finder 解压并启动 Release App；首次启动与 M5 一样受到 Gatekeeper 拦截，随后仅通过标准 macOS GUI：

```text
System Settings
-> Privacy & Security
-> Open Anyway
-> 输入密码
-> 正常启动
```

未使用 `xattr -d`、`spctl disable`、手工重签或 bundle patch，因此 Gatekeeper / quarantine 不构成当前 0.2.0 ordinary-user blocker。

本轮复用 M4 Max 上已存在且此前通过项目验证的 `large-v3`：

```text
/Users/smterpro/Workspace/Tools/clean-machine-test-livetranscription/models/ggml-large-v3.bin
```

实际运行参数：

```text
backend: whisper.cpp Metal
model: large-v3
beam_size: 7
language: English
chunk: 10 s
overlap: 3 s
capture: 48 kHz
transcribe: 16 kHz
```

`config.json` 与实际 `whisper-cli` command 均确认 `-l en -bs 7`。Release Runtime 路径来自 App Translocation 下的 `ClassroomTranscriber.app/Contents/Resources/bin/whisper-cli`，不是 source tree / `repo/dist` Runtime。

真实课堂连续运行约 35 分钟稳定。期间日志持续保持：

```text
Chunk submitted
-> Transcribing chunk
-> whisper-cli parse stats
-> Raw written
-> Clean written
```

未观察到 `ERROR`、Exception、Traceback、Backend Error、crash 或持续 backlog。启动阶段仅出现一次 `Small drift detected (0.011s); clamping to buffer start.`，后续没有持续 drift；另有一次短暂 inference latency spike，系统自行追平，没有形成持续 queue growth，记录为 non-blocking runtime observation。

人工执行一次 Stop 并立即再次 Start / Resume：

```text
Stop
-> 回 idle
-> Start / Resume
-> UI 时间轴从 00:00 重新开始
-> 新 session 正常产生真实转写
-> 输出目录自动切换到新实时时间戳
```

新的 session 输出目录：

```text
/Users/smterpro/Documents/ClassroomTranscriber/outputs/2026-08-20_17-06-49
```

由此确认 M4 Max Release ordinary-user 路径上的 Stop / microphone release / second Start / session reset / timestamped evidence-directory rotation 正常。

本轮已确认 `raw.txt`、`clean.txt`、`session.log`、`config.json` 四个 evidence 文件存在；课堂长时间实测与 Stop -> Resume 均无 blocker。

M4 Max 本轮没有重复执行 fresh Model Manager download；这是**明确记录的 non-blocking follow-up，不作为 Step 9 blocker**。理由：

1. Step 8 已在 M4 Max clean-machine App 上完成真实 `large-v3` Model Manager download + integrity transaction；
2. Step 9C-2 已在同一正式 0.2.0 Release App 上、M5 机器使用 fresh 空目录完成 `base.en` download + integrity receipt + available/selectable；
3. Step 9C-1 当前 M4 Max 已证明同一正式 0.2.0 Release App 能加载已验证 `large-v3` 并进行约 35 分钟稳定课堂转写。

后续有需要时可在 M4 Max 对 Release App 再重复一次 fresh model download，但它不影响当前 Deployment Step 9 PASS。

#### Step 9 最终 PASS 判定

```text
9A release ZIP tooling / extracted-App verification              PASS
9B exact verified artifact published to GitHub Release           PASS
9C M5 browser-downloaded artifact identity                       PASS
9C M5 Finder / Gatekeeper standard-GUI launch                    PASS
9C M5 Release App fresh Model Manager download                   PASS
9C M5 transcription / Stop / evidence layer                      PASS
9C same Release artifact M5 Metal/runtime portability            PASS
9C M4 Max browser-download / Finder / Gatekeeper standard GUI    PASS
9C M4 Max Release App large-v3 / beam=7 classroom ~35 min        PASS
9C M4 Max Stop -> Resume / new session timestamp                 PASS
9C M4 Max evidence layer                                         PASS
M4 Release App fresh Model Manager repeat                        NON-BLOCKING FOLLOW-UP
```

**Deployment Step 9 PASS。GitHub Release 0.2.0 的 ordinary-user ZIP 交付路径在 Apple M4 Max 与 Apple M5 上完成实机闭环。**

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. `GGML_NATIVE=ON` 已在 M4 Max 与 M5 各自本机构建时通过验证，并且 0.2.0 的同一个 M4 Max-built Release artifact 已在 M5 完成 GUI + Metal Runtime portability PASS；当前未发现跨代 artifact incompatibility。
2. 正式 `GGML_OPENMP=OFF` 已消除 host OpenMP availability 漂移；旧 requested ON / effective OFF 仅保留为历史证据。
3. 第一版继续使用 `Contents/Resources/bin/` Runtime 布局；Step 6 已在该布局内建立严格 closure。
4. Python 合同仍保留 broad floor `>=3.11`，但正式可复现 build environment 是 `3.12.14 / >=3.12,<3.13`。
5. Developer source build 仍依赖 Git、网络、Apple Command Line Tools 与 macOS host 工具；普通 Release 用户不承担这些源码构建前提。
6. 0.2.0 当前仅 ad-hoc codesign、未 Developer ID notarize。M4 Max 与 M5 从浏览器下载后均会触发 Gatekeeper“Apple 无法验证”，但两机都可仅通过标准 GUI `Privacy & Security -> Open Anyway -> password` 启动；不需要 Terminal workaround，因此当前不构成 blocker。
7. minimum macOS 仍为 pending；当前只验证 macOS 27 Beta，不据此推断旧版本。
8. Model integrity contract 当前冻结 Hugging Face revision `5359861c739e955e79d9a303bcbc70fb988958b1`；vendored downloader 仍解析 upstream `main`，只有与冻结 size/SHA-256 完全匹配的 bytes 才接受；upstream bytes 漂移应 fail closed。
9. Integrity receipt 以当前合同 + size + mtime 作为快速 available 证据；它是性能优化，不替代首次 cryptographic validation。
10. 明确 Import 的 custom `.bin/.gguf` 不受官方 downloadable checksum contract 约束，仍只使用独立 local import validation。
11. whisper.cpp pinned commit 在 macOS 27 SDK 下会产生部分 Metal deprecated API compiler warning；M4/M5 build/runtime inference 均 PASS，当前不升级 upstream。
12. Step 9A Release ZIP 对同一个 App 的重复打包已证明 byte-identical；这不等同于声明“不同时间重新 build 出的 App/ZIP 必然 byte-identical”。
13. Step 9A package script 依赖 documented `formal build -> package` 顺序；Step 9B 已在正式发布链路使用该顺序，发布的 0.2.0 asset 绑定 tag/source commit `314326ab30c033090d1287793e3a47ef8f2c8971`。
14. M4 Max 0.2.0 Release App 的 fresh Model Manager download repeat 尚未单独执行，但已有 Step 8 M4 fresh large-v3 download 与 Step 9C M5 同一 Release fresh base.en download 双重证据；当前仅保留为 non-blocking follow-up。
15. M4 Max 约 35 分钟课堂实测出现过一次短暂 inference latency spike，系统自行追平且未形成持续 backlog；当前记录为 non-blocking runtime observation。
16. 旧 pseudo-oral 测试输出仍是既有非阻塞项。

---

## 5. 非阻塞 UX / Product backlog

Step 8 实机验收暴露以下项目，均不回滚 Deployment MVP / Release 0.2.0：

1. **Model download progress feedback**：large-v3 下载期间后台正常运行，但 UI 没有 progress/spinner/byte counter，视觉上容易误判为卡死。
2. **Model selection confirmation**：选择模型成功后增加约 2 秒 non-modal transient toast，例如 `已成功选择模型：large-v3`。
3. **Configurable output root**：默认继续 `~/Documents/ClassroomTranscriber/`，允许用户改根目录；`outputs/<timestamp>/raw.txt|clean.txt|session.log|config.json` 子结构必须保持不变；配置持久化，只影响后续新 session。
4. **Current-model panel readability**：长绝对路径在当前模型区域被截断且无法访问完整内容；后续优先模型名/大小，路径 middle-elide + tooltip/可复制，必要时提供滚动。

Step 9 已完成。若继续处理这些项目，应新建独立 Product / UX task 文档，逐项定义优先级、允许修改范围、验收和回归；不要继续把长期产品 backlog 堆在 deployment runtime 中，也不要把这些修改混入稳定 ASR 主链路。

---

## 6. 当前未敲定参数 / 非阻塞后续

```text
# 已知 non-blocking follow-up
M4 Max Release App 再执行一次 fresh Model Manager download（当前非 Step 9 blocker）
M4 Max 长课堂偶发 inference latency spike 的长期观察（当前无持续 backlog）

# 后续 UX / Product task 文档
Model download progress / spinner / bytes feedback
Model selection success transient toast（约 2 秒）
Configurable output root
Current-model panel long-path readability / tooltip / copy / optional scroll

# 后续 Release polish
minimum macOS（当前不承诺旧系统，保持未设置）
Developer ID signing / notarization 实施时间点
DMG
GitHub Actions release automation
```

---

## 7. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine；MacBook Air / Apple M5 / 16 GB / 512 GB / macOS 27 Beta。Step 8 current-checkpoint build + packaged Runtime + large-v3 Metal + Chinese transcription + Stop/Start regression：PASS。Step 9A Release ZIP tooling / dry-run / extracted-App verification：PASS。Step 9C-2 同一 0.2.0 Release artifact 浏览器下载 / Gatekeeper GUI / fresh base.en / GUI transcription / evidence / Metal portability：PASS。

新 Mac：Clean-machine Acceptance Machine；MacBook Pro / Apple M4 Max / 48 GB / 1 TB / macOS 27 Beta。Step 8 clean-machine build + UI large-v3 download/integrity + packaged Metal + actual transcription + evidence：PASS。Step 9B release-engineering 发布正式 0.2.0 Release：PASS。Step 9C-1 浏览器下载 / Finder / Gatekeeper GUI / large-v3 beam=7 约 35 分钟真实课堂转写 / Stop -> Resume / 新 session timestamp：PASS。

当前可以记录：**项目 0.2.0 Release artifact 已在 Apple M4 Max 与 Apple M5 设备上完成 ordinary-user 实机验证；同一个 M4 Max-built Release artifact 在 M5 上完成 Metal portability 验证。** M1 / M2 / M3 仅理论兼容，不作保证；旧版 macOS 当前不作保证。

长期职责仍以 `deployment_static.md` 为准：默认 M5 为 Developer / Reference，M4 Max 为 Acceptance Machine。

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
Step 9A：正式 Release ZIP 生成与本地验证入口                         已完成 / PASS
Step 9B：实际 GitHub Release 0.2.0 发布                              已完成 / PASS
Step 9C：人工 Release 下载 / ordinary-user / same-artifact 验收       已完成 / PASS
```

当前 Deployment 工作线没有 ACTIVE Step。

```text
Step 9 PASS
-> 0.2.0 GitHub Release ordinary-user path 已闭环
-> M4 Max / M5 实机验证已闭环
-> 可以恢复 llm-sidecar-phase1 开发
```

若用户选择继续产品 polish，应新建独立 Product / UX task 文档；Developer ID / Notarization / DMG / GitHub Actions 继续作为 Release polish 管理，不自动激活。

---

## 9. 下一步执行提示

当前没有自动继承的 Deployment ACTIVE Step。下一步由用户显式选择工作线：

```text
A. 恢复 LLM sidecar：切换 llm-sidecar-phase1，按 docs/whisper_runtime.md 的唯一 ACTIVE step 推进
B. Product / UX polish：先新建独立 Product / UX task 文档，再逐项实施
C. Release polish：Developer ID / notarization / DMG / GitHub Actions / minimum macOS，单独立项
D. Deployment follow-up：仅在出现真实 blocker / regression 时重新激活
```

不要把 M4 fresh Model Manager repeat 或已知 UX backlog 自动升级为 blocker；若后续实测暴露失败，再按证据重新开启对应工作。

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
9. Step 9A commit 02cc099ee674631ce8d5f5886966846a6623caa5 / dry-run artifact evidence
10. Step 9B Release 0.2.0：tag/source 314326ab30c033090d1287793e3a47ef8f2c8971 / asset 46,549,839 bytes / SHA-256 09722cd4502103ab8f5751365438975cf05f2b1902dd7005f3c7e32b62dfabbd
11. Step 9C M5：browser/Finder/Gatekeeper/fresh base.en/GUI transcription/evidence/Metal portability PASS
12. Step 9C M4 Max：browser/Finder/Gatekeeper/large-v3 beam=7 ~35 min classroom/Stop->Resume/evidence PASS
```

恢复 LLM：

```text
git switch llm-sidecar-phase1
-> docs/whisper_static.md
-> docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
