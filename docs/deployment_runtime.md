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
当前实现 checkpoint：b38fbeae5d8a9cec1c8caf1bd179715920947bcf
checkpoint 内容：fix: enforce packaged runtime gates
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
唯一 ACTIVE：Deployment Step 7 - 模型下载完整性、失败恢复与重试
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

主要产物：

```text
PACKAGING.md
packaging/runtime_manifest.json
testCodes/test_runtime_manifest.py
```

冻结 / 记录：macOS arm64、whisper.cpp pinned commit、第一版 Build Profile、Runtime component、Bundle baseline、fail-fast contract、Python 环境方向以及 frozen / observed / pending 分层。

Step 2 测试：Manifest JSON / 14 项 manifest unittest / `git diff --check` 全部 PASS。

---

### Deployment Step 3：建立可重建的 Python 环境

状态：已完成，并经 GitHub 实际实现审核通过。

```text
643dee844a55f1e45467714f6fd65280aa6cd8ff
chore: add reproducible python environment
```

正式 Python 合同：

```text
Python exact: 3.12.14
requires-python: >=3.12,<3.13
uv exact: 0.12.5
PySide6: 6.11.1
PyInstaller: 6.22.1
numpy: 2.5.2
sounddevice: 0.5.6
formal venv: .venv/
managed tool/runtime root: .tools/
normal sync: uv sync --frozen
```

正式产物：`.python-version`、`pyproject.toml`、`uv.lock`、`scripts/bootstrap_python_env.sh`、`testCodes/test_python_environment.py`。

首次 bootstrap、`--recreate`、20 项联合 unittest、带空格路径 throwaway clean-repo rebuild 与 `git diff --check` 均 PASS。历史 `venv/` 不参与正式环境。

旧 `test_pseudo_real_chunk_sequences.py` 仍保持既有行为：脚本退出码为 0，但会打印 pseudo-oral 期望失败；该项不是 Deployment 引入，不阻塞当前工作线。

---

### Deployment Step 4：Whisper Runtime Bootstrap

状态：已完成，并经 GitHub 实际实现审核通过。

```text
cc4d3bde05c110e14bac8185e3485a70ddb98565
chore: add reproducible whisper runtime bootstrap
```

正式合同：

```text
CMake exact: 4.2.3
CMake asset: cmake-4.2.3-macos-universal.tar.gz
CMake SHA-256: c2302d3e9c48daabee5ea7c4db4b2b93b989bcc89dae8b760880e00120641b5b
CMake local path: .tools/cmake/4.2.3/CMake.app/Contents/bin/cmake
whisper.cpp commit: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
generator: Unix Makefiles
build type: Release
architecture: explicit arm64
GGML_OPENMP: OFF
GGML_NATIVE: ON
build target: whisper-cli
minimal smoke: whisper-cli --help
```

正式产物：`scripts/bootstrap_whisper_runtime.sh`、`scripts/whisper_runtime_contract.py`、`testCodes/test_whisper_runtime_bootstrap.py`。

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

正式产物：`Build ClassroomTranscriber.command`、`scripts/bootstrap_and_build.sh`、`testCodes/test_build_orchestration.py`。

主工作区正式 orchestrator、第二次 idempotent 执行、throwaway Fresh Clone、`.command` shell 等价调用、36 项联合 unittest 与 `git diff --check` 全部 PASS。Finder GUI 真实双击当时未单独完成验收，因此继续作为后续 acceptance 项保留。

---

### Deployment Step 6：严格打包门禁与 post-build Runtime smoke

状态：已完成，并经 GitHub 实际实现审核通过。

实现 commit：

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

正式新增：

```text
scripts/package_runtime.py
scripts/verify_packaged_runtime.py
testCodes/test_packaged_runtime.py
```

Release / Debug Spec、source preflight、packaged-copy normalization、verifier 和 tests 共享 `packaging/runtime_manifest.json` 的 required Runtime component / bundle contract。Release / Debug Spec 已移除 optional Runtime collection，缺任何 required source artifact 直接 hard fail。

App 内 required Runtime：

```text
whisper-cli
libwhisper.1.dylib
libggml.0.dylib
libggml-base.0.dylib
libggml-cpu.0.dylib
libggml-blas.0.dylib
libggml-metal.0.dylib
```

GitHub 审核确认：

- commit 相对 Step 6 checkpoint ahead 1 / behind 0，改动仅为 12 个 Step 6 packaging / helper / test / manifest / doc 文件；
- `scripts/package_runtime.py` 只修改 App 内 Runtime 副本，不修改 Step 4 source Runtime；
- required Runtime 统一规范为 `@loader_path` LC_RPATH，声明的非系统 dylib dependency 统一为 Manifest 对应的 `@rpath/<bundle_filename>`；
- normalizer 对 `install_name_tool` 使用 hard-fail 语义，不再吞掉关键错误；
- `scripts/verify_packaged_runtime.py` 检查 required component、权限、Mach-O arm64-only、`otool` dependency closure、允许的系统依赖边界、downloader、codesign、bundle CLI smoke 和 isolated Runtime smoke；
- verifier 明确拒绝 undeclared / absolute / source-tree dependency，不允许 packaged Runtime 依赖 `/Users/...`、`external/whisper.cpp/build`、Homebrew 或 Conda dylib；
- App 内 Runtime normalization 后必须重新 ad-hoc sign，`codesign --verify --deep --strict` 必须 PASS；Developer ID / notarization 未提前引入；
- Manifest 已冻结 packaged Runtime contract：`@loader_path` Runtime RPath、允许系统前缀 `/usr/lib/` 与 `/System/Library/`、source-tree dependency forbidden、isolated smoke required。

实施验证：

```text
主工作区 one-entry build + 自动 verifier                  PASS
独立 verifier 复跑                                        PASS
CLI + 6 dylib arm64-only                                  PASS
final dependency closure / RPath                          PASS
App 内 whisper-cli --help                                 PASS
isolated 七组件 Runtime smoke                             PASS
bundled downloader + sh -n                               PASS
ad-hoc codesign verify                                    PASS
反向 failure injection                                   PASS
throwaway Fresh Clone build + strict verifier             PASS
联合 unittest                                             PASS / 47 tests
git diff --check                                          PASS
```

反向测试覆盖：缺 source component、缺 bundled component、非法开发机 dependency、缺 downloader、CLI smoke 非零、错误 architecture，均正确 nonzero。

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 7 - 模型下载完整性、失败恢复与重试
```

### 3.1 目标

把当前“能调用 vendored downloader 下载模型”的能力升级为可安全失败、可恢复、不会把 partial / HTTP error 当成可用模型的正式 Model Manager 下载路径。

本 Step 只处理模型获取与本地完整性状态，不修改 whisper Runtime、ASR 算法或 evidence layer。

### 3.2 当前已确认风险

当前 vendored upstream downloader 仍具有以下行为：

```text
直接写最终 ggml-<model>.bin
已有最终文件就直接 skip
curl 使用 -L --output，但没有 --fail
失败 / 中断可能留下最终文件名的 partial artifact
无正式 checksum / expected size manifest
```

当前 `model_manager.py` 对模型可用性的主要完整性判断仍是“文件存在 + 大于 MIN_MODEL_FILE_SIZE_BYTES”，因此足够大的损坏 / HTML / partial 文件理论上仍可能被当成 available。

这些风险是 Step 7 的直接目标，不应延后到 Step 8 才发现。

### 3.3 Step 7 预期工作

1. 先审查 `model_manager.py`、Model Manager UI 调用链、`resource_paths.py`、vendored downloader、当前 downloadable model 集合与实际模型目录行为；
2. 确定并记录正式 downloadable model integrity metadata 策略，至少解决 trusted expected size / checksum 的来源与维护方式；不能凭旧开发机本地文件猜 checksum；
3. 正式下载必须写临时 / partial 文件，验证成功后再 atomic rename / replace 为最终模型文件；
4. HTTP / network / downloader failure 必须 nonzero，不能把错误响应或 incomplete file 留成“可用”的最终文件；
5. existing final model 只有通过正式 validation 才可复用 / skip；invalid final file 不得永久阻塞重试；
6. 下载失败后应清理或明确隔离临时 artifact，使下一次 retry 可以正常进行；
7. 下载完成后必须执行与正式 metadata 一致的完整性验证，验证失败不得更新 selected model / available 状态；
8. Model Manager UI 必须能向用户呈现下载失败并允许重试，且不得阻塞 / 破坏 ASR 主链路、Start/Stop、麦克风释放或 UI 主线程；
9. 保持模型文件不进入 App bundle，不进入 Runtime Manifest 的 Runtime component 集合；如建立独立 model manifest，应明确其职责与 provenance；
10. 建立 failure-injection tests，覆盖 HTTP failure / 中断或 partial / existing corrupt final / checksum-size mismatch / retry success；
11. 在旧开发机用小型 fixture / mock endpoint / fake downloader 完成测试，避免为了 Step 7 自动下载 large-v3 等大型模型；
12. 不进入新机器真实 E2E，真实 App + model + microphone + transcription 留 Step 8。

### 3.4 Step 7 验收方向

至少证明：

```text
开始下载
-> 只写 temporary/partial target
-> 下载命令真实失败可检测
-> 完整性验证 PASS
-> atomic publish 最终文件
-> Model Manager 才将其视为 available
```

失败路径至少证明：

```text
HTTP 失败 -> 无伪最终文件
中断 / partial -> 不 available，可重试
已有 corrupt final -> 不 skip，可恢复
size/checksum mismatch -> 不 publish
retry 成功 -> 正常恢复并可选中
```

### 3.5 Step 7 边界

本 Step 不做：

```text
修改 whisper.cpp Build Profile / packaged Runtime
修改 ASR chunk / dedup / backend 行为
真实课堂录音或转录 E2E
新机器 Fresh Clone acceptance
GitHub Release ZIP acceptance
Developer ID / notarization / DMG
LLM 开发
```

模型 integrity metadata 的 exact 来源 / checksum / size 在实现前必须以可信 upstream 实际证据确定；不要凭当前本地 large-v3 文件或记忆直接冻结。

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. 第一版仍冻结 `GGML_NATIVE=ON`；旧开发机 / throwaway 已通过 source build 和 packaged Runtime gate，但跨 M4 Max / M5 portability 必须在 Step 8 实机验证。
2. 正式 `GGML_OPENMP=OFF` 已消除 host OpenMP availability 漂移；旧 requested ON / effective OFF 仅保留为历史证据。
3. 第一版继续使用 `Contents/Resources/bin/` Runtime 布局；Step 6 已在该布局内建立 closure，不为目录美化额外迁移。
4. Python 合同保留 broad floor `>=3.11`，但正式可复现 build environment 是 `3.12.14 / >=3.12,<3.13`。
5. Developer source build 仍依赖 Git、网络、Apple Command Line Tools 与 macOS host 工具；普通 Release 用户不承担这些源码构建前提。
6. Finder GUI 双击尚需本机 / clean-machine acceptance；shell 等价入口已经验证。
7. Step 6 使用 ad-hoc codesign 作为当前开发 bundle integrity gate；Developer ID / notarization 仍属于后续 Release polish。
8. 当前普通用户最小发布形式仍为 ZIP + `.app`；Step 9 / signing / notarization / DMG 不无限阻塞 Deployment MVP。
9. 旧 pseudo-oral 测试输出仍是既有非阻塞项，不归 Step 7 修复。

---

## 5. 当前未敲定参数

```text
# Step 7
正式 model integrity metadata 的来源与维护方式
是否建立独立 packaging/model_manifest.json（或等价合同）
各 downloadable model 的 exact checksum / expected size
partial 文件命名 / cleanup / retry 细节
Model Manager 下载失败后的 UI 状态与重试细节

# 后续
minimum macOS（当前不承诺旧系统，保持未设置）
M4 Max / M5 实机 `GGML_NATIVE=ON` portability 证据
Developer ID signing / notarization 实施时间点
GitHub Release 正式版本和自动发布流程
```

---

## 6. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine，用于开发、自动测试、clean-repo simulation、构建验证、稳定 ASR 回归、Commit / Push。

新 Mac：Clean-machine Acceptance Machine，不手工复制 `.venv`、`.tools`、`external/`、CLI、dylib 或模型，不通过临时 Terminal 命令修补正式流程。

当前实际硬件验收基线：

```text
MacBook Air / M5 / 16 GB / 512 GB / macOS 27 Beta
MacBook Pro / M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

M4 / M5 支持声明必须分别有项目实际验证证据；M1 / M2 / M3 仅理论兼容，不作保证。旧版 macOS 当前不作保证。

---

## 7. 当前已知 Failure Modes

### Build / Packaging

- Python、whisper Runtime、一键 orchestration 和 strict packaged Runtime gate 已建立；Fresh Clone throwaway 可以生成通过 verifier 的 App。
- Finder GUI 真实双击仍待实机 acceptance。
- `GGML_NATIVE=ON` 跨 M4/M5 portability 尚未实机闭环。

### Model Manager / 下载

- vendored downloader 当前直接写最终 `.bin`；
- curl 路径未使用 `--fail`；
- interrupted / failed download 可能留下 partial final-name artifact；
- existing final filename 会阻止 downloader 正常 retry；
- 当前没有正式 downloadable model checksum / expected-size contract；
- `model_status()` 主要以文件大小阈值判断 available，无法证明内容正确；
- 这些是当前 Step 7 的 ACTIVE 风险。

---

## 8. 后续步骤

```text
Step 1：Clean-machine Gap Audit                     已完成
Step 2：部署合同与 Runtime Manifest                已完成
Step 3：建立可重建的 Python 环境                   已完成
Step 4：Whisper Runtime Bootstrap                   已完成
Step 5：可双击的一键构建入口与 Orchestration       已完成
Step 6：严格打包门禁与 post-build smoke             已完成
Step 7：模型下载完整性、失败恢复与重试               ACTIVE
Step 8：新机器 Clone -> App -> 转录端到端验收         待做
Step 9：普通用户 GitHub Release ZIP 验收              待做
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

继续开发时：

```text
1. git fetch + git pull --ff-only origin main，确认 main / clean worktree / HEAD == origin/main
2. 读取 deployment_static.md / deployment_runtime.md / PACKAGING.md / runtime_manifest.json
3. 审查 model_manager.py / Model Manager UI / resource_paths.py / vendored downloader / tests
4. 只执行 Deployment Step 7
5. Codex 不修改 deployment_runtime.md
6. 先确定可信 model integrity metadata / provenance，再实现 atomic download + validation + retry
7. 不下载大型真实模型作为自动测试前提；优先 fixture / fake downloader / local mock
8. 不修改 ASR 主链路、不做真实转录、不提前进入 Step 8
9. 实现、自检通过后一个 commit 并 push main
10. 人工 / ChatGPT 审核后再推进 Step 8
```

---

## 10. 上下文恢复入口

恢复 `main` Deployment：

```text
1. docs/deployment_static.md
2. docs/deployment_runtime.md
3. PACKAGING.md
4. packaging/runtime_manifest.json
5. README.md
6. docs/工程细节.md
7. 与 ACTIVE Step 有关的 model_manager / UI / resource_paths / vendor / tests
```

恢复 LLM：

```text
git switch llm-sidecar-phase1
-> docs/whisper_static.md
-> docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
