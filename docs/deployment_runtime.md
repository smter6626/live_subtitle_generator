# deployment_runtime.md

最后更新：2026-08-17  
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
当前实现 checkpoint：cc4d3bde05c110e14bac8185e3485a70ddb98565
checkpoint 内容：chore: add reproducible whisper runtime bootstrap
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
唯一 ACTIVE：Deployment Step 5 - 可双击的一键构建入口与 Orchestration
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

结果：Vendored downloader 已进入主仓库并进入 PyInstaller resource；Fresh Clone 不再依赖 `external/whisper.cpp/models/download-ggml-model.sh` 才能获得下载脚本。

---

### Deployment Step 1：Clean-machine Gap Audit

状态：已完成，仅审计。

确认主要缺口：Fresh Clone 无 bootstrap / `.command`；Python 环境不可复现；Fresh Clone 无 whisper Runtime；当前 packaging 对缺 Runtime 不够严格；模型下载缺完整性与失败恢复；尚无 clean-machine E2E。

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

冻结 / 记录：macOS arm64、whisper.cpp pinned commit、第一版旧机 Build Profile、Runtime component、Bundle baseline、fail-fast contract、Python 环境方向以及 frozen / observed / pending 分层。

Step 2 测试：

```text
python3 -m json.tool packaging/runtime_manifest.json >/dev/null   PASS
python3 -m unittest testCodes.test_runtime_manifest -v           PASS / 14 tests
git diff --check                                                  PASS
```

---

### Deployment Step 3：建立可重建的 Python 环境

状态：已完成，并经 GitHub 实际实现审核通过。

实现 commit：

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

正式仓库产物：

```text
.python-version
pyproject.toml
uv.lock
scripts/bootstrap_python_env.sh
testCodes/test_python_environment.py
```

Bootstrap 使用官方 Astral artifact + SHA-256，在 `.tools/` 下准备 uv / managed Python / cache，建立 `.venv` 并执行 `uv sync --frozen`；历史 `venv/` 不参与正式环境。

实施验证：首次 bootstrap、`--recreate`、20 项联合 unittest、带空格路径 throwaway clean-repo rebuild 与 `git diff --check` 均 PASS。

旧 `test_pseudo_real_chunk_sequences.py` 仍保持其既有行为：脚本退出码为 0，但会打印 pseudo-oral 期望失败；该项不是 Step 3 引入，且未触碰 dedup / ASR，因此不阻塞 Deployment。

---

### Deployment Step 4：Whisper Runtime Bootstrap

状态：已完成，并经 GitHub 实际实现审核通过。

实现 commit：

```text
cc4d3bde05c110e14bac8185e3485a70ddb98565
chore: add reproducible whisper runtime bootstrap
```

正式 Runtime bootstrap 合同：

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

正式仓库产物：

```text
scripts/bootstrap_whisper_runtime.sh
scripts/whisper_runtime_contract.py
testCodes/test_whisper_runtime_bootstrap.py
```

Runtime Manifest 已从 Step 4 pending 转为 frozen：CMake exact acquisition contract、显式 `CMAKE_OSX_ARCHITECTURES=arm64`、正式 `GGML_OPENMP=OFF`、source artifact paths 和 minimal smoke。旧机器历史证据仍保留 `GGML_OPENMP requested ON / effective OFF`。

Bootstrap / helper 行为审核确认：

- CMake 从 Manifest 读取，不 fallback 到 Homebrew / Conda / 系统 CMake；
- official Kitware artifact 下载后按冻结 SHA-256 验证；
- `external/whisper.cpp` 缺失时获取 exact commit，存在时验证 official origin / clean worktree，异常状态不静默覆盖；
- whisper.cpp 最终 detached HEAD 固定在 exact commit；
- CMake 配置使用 `--fresh`，Build Profile 由 Manifest helper 生成，不在 shell 中复制 GGML flags；
- 只构建 `whisper-cli` target 及依赖；
- verify-only 不下载、不 checkout、不 configure、不 compile；
- CLI / 6 个 dylib 必须为 arm64-only Mach-O；
- CLI 对 required dylib 使用 `@rpath`；source-build tree RPath 允许存在，但必须位于当前 build tree；
- minimal smoke `whisper-cli --help` 必须退出 0。

实施验证：

```text
主工作区 Python bootstrap                              PASS
Whisper bootstrap                                      PASS
verify-only                                            PASS
CLI + 6 dylib arm64                                    PASS
CLI @rpath dependency                                  PASS
minimal --help smoke                                   PASS
throwaway 无 CMake / 无 external 首轮恢复             PASS
throwaway 删除 external + .tools/cmake 后二次恢复      PASS
联合 unittest                                          PASS / 29 tests
git diff --check                                       PASS
```

GitHub 审核确认该 commit 相对 Step 4 runtime checkpoint ahead 1 / behind 0，修改范围仅为 9 个 Step 4 script / helper / test / manifest / doc 文件；没有 binary、`external/` 或 `.tools/` 进入 Git。

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 5 - 可双击的一键构建入口与 Orchestration
```

### 3.1 目标

把已经可独立重建的 Python 环境与 whisper Runtime 串成正式源码构建主入口，使开发者从 Fresh Clone 后只需要启动一个入口即可得到 `ClassroomTranscriber.app`。

正式调用链目标：

```text
Build ClassroomTranscriber.command
-> scripts/bootstrap_and_build.sh
-> scripts/bootstrap_python_env.sh
-> scripts/bootstrap_whisper_runtime.sh
-> 使用正式 .venv/bin/python 执行现有 macOS Release build
-> dist/ClassroomTranscriber.app
```

`.command` 只做 Finder thin wrapper；全部可测试逻辑必须位于 `scripts/bootstrap_and_build.sh`。

### 3.2 Step 5 预期工作

1. 创建仓库根目录 `Build ClassroomTranscriber.command`，设置可执行位，能够从 Finder 双击进入正式构建流程；
2. 创建 `scripts/bootstrap_and_build.sh`，使用 `set -euo pipefail`、仓库相对路径，并正确处理路径空格；
3. Orchestrator 必须按固定顺序调用 Python bootstrap、whisper Runtime bootstrap，再进入现有 Release build；
4. 正式 build interpreter 必须明确为 `.venv/bin/python`，不得重新回退到历史 `venv/`、Conda、Homebrew 或系统 Python；
5. 优先利用现有 `scripts/build_macos.sh` 已支持的 `PYTHON` override，将 `.venv/bin/python` 显式传入，而不是在 Step 5 顺带重写 packaging 逻辑；
6. 保留 `scripts/build_macos.sh` / PyInstaller Spec 当前 packaging 行为的 Step 6 边界：Step 5 的职责是 orchestration，不在本 Step 完成 strict Runtime gate / final dependency closure；
7. 入口失败必须传播非零退出码并打印可理解阶段信息，不允许前序 bootstrap 失败后继续构建；
8. 成功后必须明确打印最终 App 路径；
9. 创建 orchestration contract/unit test，验证 wrapper、调用顺序、正式 Python injection、路径处理和禁止旧 venv fallback；
10. 在旧开发机实际运行正式 orchestrator，完成至少一次真实 PyInstaller App build；
11. 使用 throwaway clean repo 从无 `.venv`、无 `.tools`、无 `external/` 的状态执行正式 orchestrator，并确认能够生成 App；
12. 不在本 Step 做模型下载、麦克风录音、新机器完整 E2E 或 LLM 工作。

### 3.3 Step 5 验收方向

至少证明：

```text
Fresh Clone / 无 .venv / 无 .tools / 无 external
-> 一个正式构建入口
-> Python bootstrap
-> whisper Runtime bootstrap
-> PyInstaller Release build
-> dist/ClassroomTranscriber.app 存在
```

当前 Step 5 只证明“正式入口可以完成构建编排并生成 App”。

以下仍明确属于 Step 6，而不是 Step 5 PASS 的必要条件：

```text
Spec 将所有 Runtime 从 optional 改为 required
缺 whisper-cli / dylib 时严格 Fail Fast
install_name_tool 错误不再被吞掉
最终 App 内 arm64 / dylib closure / RPath gate
post-build bundled whisper-cli smoke
完整 packaging completeness 判定
```

Step 5 commit + push 后仍由人工 / ChatGPT 基于 GitHub 实现与测试审核；审核通过后才激活 Step 6。

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. 第一版冻结 `GGML_NATIVE=ON`；当前旧开发机 bootstrap 已 PASS，但不同 Apple Silicon 代际 portability 仍必须在 M4 Max / M5 实际验收。
2. 正式 `GGML_OPENMP=OFF` 已解决 host OpenMP availability 漂移；旧 `requested ON / effective OFF` 继续作为历史证据保留。
3. Step 4 source Runtime 允许当前 build tree absolute LC_RPATH；最终 App 不得依赖这些路径，Step 6 必须建立 final bundle dependency closure / RPath gate。
4. 第一版沿用 `Contents/Resources/bin/` Bundle Runtime 布局，不在当前阶段重构目录。
5. 当前 Runtime component 集合以 pinned build 为合同基线；Step 6 仍必须通过最终 App 的 `otool -L` closure 验证实际 bundle 完整性。
6. Python 合同同时保留历史 broad floor `>=3.11` 与正式 managed environment `3.12.14 / >=3.12,<3.13`；实际可复现构建环境以 3.12.14 为准。
7. Source-build bootstrap 依赖 macOS host 提供 `git/curl/tar/shasum/xcrun/clang/make/file/otool` 和 Apple Command Line Tools；旧机 / throwaway 已验证，最终 clean-machine 仍需确认无需额外人工技术修补。普通 Release 用户不承担这些 source-build prerequisites。
8. Step 5 将继续复用现有 `build_macos.sh` 与 Spec 的非严格 packaging 行为以保持任务边界；因此 Step 5 生成 App 不等于最终 Packaging 完整性 PASS，严格门禁属于 Step 6。
9. 当前普通用户最小发布形式为 ZIP + `.app`，暂不要求 Developer ID / Notarization / DMG。
10. 远程自动化可以验证 `.command` 文件、可执行位及其 shell 等价调用；真实 Finder 双击交互仍需在后续本机 / clean-machine 验收中确认，不因远程 shell 调用自动视为 Finder UX 已实际验证。

---

## 5. 当前未敲定参数

```text
# Step 5
Build ClassroomTranscriber.command 的最小 Finder wrapper 行为
bootstrap_and_build.sh 的阶段日志 / 失败展示细节
远程环境下 Finder 双击的实际交互验证方式

# Step 6
最终 App dependency closure / RPath gate 细节
Runtime components 如何从 Manifest 驱动 Spec / build gate
post-build bundled whisper-cli smoke 形式
codesign failure 的正式 Build 判定边界

# 后续
minimum macOS（当前不承诺旧系统，保持未设置）
模型 checksum / size manifest 来源与维护策略
Developer ID signing / notarization 实施时间点
GitHub Release 正式版本和自动发布流程
```

---

## 6. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine，用于开发、自动测试、clean-repo simulation、构建验证、稳定 ASR 回归、Commit / Push。

新 Mac：Clean-machine Acceptance Machine，不手工复制 `external/`、CLI、dylib 或模型，不使用旧 venv，不通过临时 Terminal 命令修补正式流程。

当前实际硬件验收基线：

```text
MacBook Air / M5 / 16 GB / 512 GB / macOS 27 Beta
MacBook Pro / M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

M4 / M5 支持声明必须分别有项目实际验证证据；M1 / M2 / M3 仅理论兼容，不作保证。旧版 macOS 当前不作保证。

---

## 7. 当前已知 Failure Modes

### Python / Orchestration

- Python 与 whisper Runtime 已可分别重建，但尚无统一 `bootstrap_and_build.sh` 和 Finder `.command` 正式入口；Step 5 解决。
- 当前 `build_macos.sh` 仍包含历史 interpreter selection fallback；Step 5 必须通过 orchestrator 显式注入 `.venv/bin/python`，后续是否进一步移除 fallback 可在不扩大风险时再治理。

### Packaging

- 缺 `whisper-cli` 当前仍只 Warning；Spec 对 CLI/dylib 仍使用 optional collection。
- `install_name_tool` 部分错误仍被 `|| true` 吞掉。
- 尚无最终 App 内 CLI / dylib / architecture / closure / RPath / dyld smoke。
- source Runtime build tree 的绝对 RPath 尚未转换为正式 App bundle closure。
- 这些都是 Step 6 的 ACTIVE-next 风险，不阻塞 Step 5 orchestration 本身。

### Whisper Runtime

- `GGML_NATIVE=ON` portability 尚未跨 M4/M5 验证。
- Source bootstrap 已将 OpenMP 显式固定 OFF，不再依赖宿主机 libomp 状态。

### 模型下载

- 当前仍直接写最终 `.bin`；中断 / HTTP failure / partial file / retry / checksum 问题尚未解决。

---

## 8. 后续步骤

```text
Step 1：Clean-machine Gap Audit                     已完成
Step 2：部署合同与 Runtime Manifest                已完成
Step 3：建立可重建的 Python 环境                   已完成
Step 4：Whisper Runtime Bootstrap                   已完成
Step 5：可双击的一键构建入口与 Orchestration       ACTIVE
Step 6：严格打包门禁与 post-build smoke             待做
Step 7：模型下载完整性、失败恢复与重试               待做
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
1. 远程模式主动 git fetch + git pull --ff-only origin main
2. 确认 main / clean worktree / HEAD == origin/main
3. 读取 deployment_static.md / deployment_runtime.md / PACKAGING.md / runtime_manifest.json
4. 检查 bootstrap_python_env.sh / bootstrap_whisper_runtime.sh / build_macos.sh / Release Spec
5. 只执行 Deployment Step 5
6. Codex 不修改 deployment_runtime.md
7. Orchestrator 显式使用正式 .venv/bin/python，不复用旧 venv
8. 允许实际 PyInstaller build；不把当前 App build 成功误报为 Step 6 packaging completeness PASS
9. 实现、自检通过后一个 commit 并 push main
10. 人工 / ChatGPT 审核后再推进 Step 6
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
7. 与 ACTIVE Step 有关的 scripts / specs / resource paths
```

恢复 LLM：

```text
git switch llm-sidecar-phase1
-> docs/whisper_static.md
-> docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
