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
当前实现 checkpoint：fdefbc10e945f693def35d9896e0101c6f766b00
checkpoint 内容：chore: add one-click build orchestration
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
唯一 ACTIVE：Deployment Step 6 - 严格打包门禁与 post-build Runtime smoke
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

### Deployment Step 5：可双击的一键构建入口与 Orchestration

状态：已完成，并经 GitHub 实际实现审核通过。

实现 commit：

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

正式仓库产物：

```text
Build ClassroomTranscriber.command
scripts/bootstrap_and_build.sh
testCodes/test_build_orchestration.py
```

同时最小同步 Runtime Manifest、PACKAGING、README、deployment static 与工程文档；未修改 `scripts/build_macos.sh`、ASR 主链路、模型下载或 LLM。

GitHub 审核确认：

- commit 相对 Step 5 runtime checkpoint ahead 1 / behind 0；
- 修改范围仅为 8 个 Step 5 entry / orchestration / test / manifest / doc 文件；
- `.command` 仅解析 repo root，并以 `exec` 将控制权交给 orchestrator；
- orchestrator 按固定顺序调用 Python bootstrap、whisper Runtime bootstrap、Release build；
- Release build 通过 `PYTHON=<repo>/.venv/bin/python` 显式使用正式 Python，不重新依赖历史 `venv/` / Conda / Homebrew Python；
- orchestrator 使用 `set -euo pipefail` 并传播失败；
- 成功后检查 App、Contents、Resources 和主 executable 基本结构；
- orchestration tests 验证 executable bit、thin wrapper、调用顺序、正式 Python injection、repo-relative path，以及不提前加入 Step 6 的 `otool/install_name_tool/codesign` gate。

实施验证：

```text
主工作区正式 orchestrator                            PASS
生成 dist/ClassroomTranscriber.app                   PASS
第二次 / idempotent orchestration                    PASS
throwaway Fresh Clone / 无 .venv/.tools/external     PASS
.command shell 等价调用（主工作区 + throwaway）       PASS
联合 unittest                                         PASS / 36 tests
git diff --check                                      PASS
```

远程模式没有声称 Finder GUI 真实双击已验收；当前仅验证 `.command` 可执行位与 shell 等价调用。

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 6 - 严格打包门禁与 post-build Runtime smoke
```

### 3.1 目标

把 Step 5 已能“生成 App”的正式构建流程升级为“只有 Runtime 完整、架构正确、动态链接闭包可在 App bundle 内成立时才允许 Build PASS”。

本 Step 解决的是最终 App Packaging 完整性，不改变 ASR 算法，也不处理模型下载完整性。

### 3.2 Step 6 预期工作

1. 审查当前 Release Spec、`scripts/build_macos.sh`、Runtime Manifest 与实际 `dist/ClassroomTranscriber.app` 布局，先以当前代码为事实，不凭文档猜 bundle 结构；
2. 让正式 Packaging 对 Manifest 中所有 required Runtime component 执行 Fail Fast，不再允许缺 CLI / dylib 后 Warning 或 optional skip 继续生成名义 App；
3. 尽量让 Runtime component source / bundle target 由 `packaging/runtime_manifest.json` 驱动，避免 Spec、build script、验证脚本维护多份独立硬编码文件列表；
4. 对最终 App 内 `whisper-cli` 和 required dylib 验证文件存在、可执行/可读、Mach-O arm64 架构；
5. 通过 `otool -L` / `otool -l` 建立最终 App dependency closure / RPath gate，禁止 packaged Runtime 依赖旧 `external/whisper.cpp/build` 或其他开发机绝对路径；
6. 对 bundle 内 Runtime 做必要且最小的 install-name / RPath 处理，并使处理失败成为明确失败，不再用 `|| true` 静默吞掉关键错误；
7. 建立 packaged `whisper-cli` 无模型 smoke（优先沿用 Manifest 的 `--help` 合同或经实际验证的等价命令），必须从 App bundle 内路径直接启动并退出 0；
8. 验证 vendored model downloader 确实进入正式 bundle 且保持可用；
9. 建立一个明确的 post-build verifier / test surface，使 `scripts/build_macos.sh` 或正式 orchestrator 在报告成功前必须通过该 verifier；
10. 在旧开发机和 throwaway Fresh Clone one-entry flow 中实际执行完整 build + post-build gate；
11. 不在本 Step 下载模型、不做麦克风真实转录、不做新机器完整 E2E、不进入 LLM 工作。

### 3.3 Step 6 验收方向

至少证明：

```text
Fresh Clone
-> 正式 one-entry build
-> App 生成
-> required Runtime 全部进入 bundle
-> CLI / dylib arm64
-> packaged dependency closure 只依赖 bundle-relative / 系统合法路径
-> packaged whisper-cli no-model smoke PASS
-> vendored downloader 存在
-> post-build verifier PASS
-> Build 才允许报告成功
```

反向失败测试至少覆盖：

```text
缺一个 required Runtime component -> build FAIL
错误 / 非法 dependency path -> verify FAIL
缺 bundled downloader -> verify FAIL
packaged CLI smoke 非零 -> verify FAIL
```

具体测试注入方式根据当前代码实现选择，避免破坏旧开发机 reference Runtime。

### 3.4 Step 6 边界

本 Step不做：

```text
模型 checksum / atomic download / retry
真实模型下载
真实麦克风录音与转录
新机器 Fresh Clone E2E
GitHub Release ZIP acceptance
Developer ID / notarization / DMG polish
ASR 主链路修改
LLM 开发
```

Ad-hoc codesign 当前只作为现有构建行为存在。其失败是否属于 Step 6 hard gate，先以“Runtime completeness 是否依赖该签名步骤”为依据审查当前代码和产物后再定，不要在没有证据时扩大到正式 Developer ID / notarization 范围。

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. 第一版冻结 `GGML_NATIVE=ON`；旧开发机与 throwaway source build 已 PASS，但不同 Apple Silicon 代际 portability 仍必须在 M4 Max / M5 实际验收。
2. 正式 `GGML_OPENMP=OFF` 已解决 host OpenMP availability 漂移；旧 `requested ON / effective OFF` 继续作为历史证据保留。
3. Step 4 source Runtime 允许 build-tree absolute LC_RPATH；Step 6 必须保证最终 App 不再依赖这些 source-build 绝对路径。
4. 第一版继续沿用 `Contents/Resources/bin/` Runtime 布局；Step 6 优先在现有布局内建立严格 closure，不为目录美化做额外迁移。
5. Python 合同同时保留历史 broad floor `>=3.11` 与正式 managed environment `3.12.14 / >=3.12,<3.13`；实际可复现构建环境以 3.12.14 为准。
6. Source-build 仍依赖 Git、网络、Apple Command Line Tools 与 macOS host 工具；普通 Release 用户不承担这些源码构建前提。
7. Finder GUI 双击尚未在 remote 模式真实验收；Step 5 仅证明 `.command` shell 等价调用。该项继续留到本机 / clean-machine acceptance。
8. Step 5 已证明“Fresh Clone 可以生成 App”，但该 PASS 不代表当前 commit 的 packaged Runtime 已经完整；Step 6 正是关闭该缺口。
9. 当前普通用户最小发布形式仍为 ZIP + `.app`，Developer ID / Notarization / DMG 不是 Deployment MVP blocker。
10. 旧 `test_pseudo_real_chunk_sequences.py` 的 pseudo-oral 期望失败输出仍是既有非阻塞项，不归 Deployment Step 6 修复。

---

## 5. 当前未敲定参数

```text
# Step 6
最终 App 内 exact Runtime destination / symlink 处理（以实际 bundle 结构审计为准）
Manifest 驱动 Spec / build / verifier 的具体接口
final install-name / RPath 修复实现方式
post-build verifier 的具体文件/入口形式
ad-hoc codesign failure 的 hard-fail 边界

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

### Orchestration

- Python bootstrap、Whisper Runtime bootstrap 与 Release build 已串成一个正式入口；主工作区与 throwaway Fresh Clone 均能生成 App。
- Finder GUI 双击仍未在 remote 模式实际验证。

### Packaging

- 当前 Release Spec 对 whisper CLI / dylib 仍可 optional collection；缺 Runtime 可能不阻止 PyInstaller 生成 App。
- `scripts/build_macos.sh` 对缺 whisper-cli 仍可能只 Warning。
- `install_name_tool` 部分错误仍被忽略。
- 当前尚无最终 App 内 CLI / dylib / architecture / dependency closure / RPath / dyld smoke 的统一 hard gate。
- source Runtime build-tree absolute RPath 必须在最终 bundle 中消除其作为运行前提的影响。
- 这些是当前 Step 6 的直接目标。

### Whisper Runtime

- `GGML_NATIVE=ON` portability 尚未跨 M4/M5 验证。
- Source bootstrap 已将 OpenMP 显式固定 OFF，不再依赖宿主机 libomp 状态。

### 模型下载

- 当前仍直接写最终 `.bin`；中断 / HTTP failure / partial file / retry / checksum 问题尚未解决，留 Step 7。

---

## 8. 后续步骤

```text
Step 1：Clean-machine Gap Audit                     已完成
Step 2：部署合同与 Runtime Manifest                已完成
Step 3：建立可重建的 Python 环境                   已完成
Step 4：Whisper Runtime Bootstrap                   已完成
Step 5：可双击的一键构建入口与 Orchestration       已完成
Step 6：严格打包门禁与 post-build smoke             ACTIVE
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
4. 审查 build_macos.sh / Release Spec / 当前 dist App 实际布局，不凭旧假设设计 final RPath
5. 只执行 Deployment Step 6
6. Codex 不修改 deployment_runtime.md
7. 先建立 packaged Runtime verifier，再将其接入正式 Build PASS 路径
8. required Runtime 缺失或 closure/smoke 失败必须 fail fast
9. 不下载模型、不做真实转录、不提前进入 Step 7
10. 实现、自检通过后一个 commit 并 push main
11. 人工 / ChatGPT 审核后再推进 Step 7
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
