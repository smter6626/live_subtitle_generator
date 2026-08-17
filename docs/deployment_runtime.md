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
当前实现 checkpoint：643dee844a55f1e45467714f6fd65280aa6cd8ff
checkpoint 内容：chore: add reproducible python environment
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
唯一 ACTIVE：Deployment Step 4 - Whisper Runtime Bootstrap
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

同时更新 `.gitignore`、Runtime Manifest、Manifest tests、Packaging / README / 工程文档；未修改生产 ASR、whisper Runtime、模型下载或 LLM。

Bootstrap 行为：

```text
官方 Astral GitHub release 获取固定 uv 0.12.5 arm64 artifact
-> SHA-256 校验
-> .tools/uv/
-> uv-managed Python 3.12.14 放入 .tools/python/
-> cache 放入 .tools/cache/
-> 建立项目 .venv/
-> uv sync --frozen
-> environment smoke
```

历史 `venv/` 不读取、不修改、不删除；正式环境不依赖 Homebrew / Conda / 系统 Python package。

GitHub 审核确认：

- commit 相对 runtime checkpoint 仅 ahead 1 / behind 0；
- 修改范围为 Step 3 的 12 个合同 / bootstrap / test / doc 文件；
- `pyproject.toml` 将 runtime direct dependencies 与 PyInstaller dev dependency 分离；
- Runtime Manifest 已将 Step 3 的 Python / uv / direct package pending 项转为 frozen；
- Bootstrap 使用仓库相对路径、`set -euo pipefail`、固定 uv/Python、`uv sync --frozen`，`--recreate` 只删除 `.venv`；
- environment test 验证 exact Python/package 版本、项目局部 managed Python 和安全项目 import surface。

实施验证结果：

```text
bash -n scripts/bootstrap_python_env.sh                       PASS
Manifest JSON parse                                           PASS
首次 .venv bootstrap                                          PASS
Python 3.12.14                                                PASS
PyInstaller 6.22.1                                           PASS
environment smoke                                              PASS / 5 tests
--recreate 后重新建立 .venv                                  PASS
联合 unittest                                                  PASS / 20 tests
带空格路径 throwaway clean-repo/environment rebuild           PASS
git diff --check                                              PASS
```

旧 `test_pseudo_real_chunk_sequences.py` 仍保持其既有行为：脚本退出码为 0，但会打印 pseudo-oral 期望失败；该项不是 Step 3 引入，且本 Step 未触碰 dedup / ASR，因此不阻塞 Step 3。

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 4 - Whisper Runtime Bootstrap
```

### 3.1 目标

让 Fresh Clone 在没有历史 `external/whisper.cpp` 的情况下，能够通过正式项目脚本自动获得并构建固定版本的 whisper.cpp Runtime。

固定上游：

```text
repository: https://github.com/ggml-org/whisper.cpp.git
commit: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
target architecture: arm64
```

第一版继续以 `packaging/runtime_manifest.json` 已冻结的旧开发机成功 Build Profile 为合同基线。

### 3.2 Step 4 预期工作

1. 确认并实现 CMake 的正式自动获取 / 使用方式，不要求开发者手工 Homebrew 安装；
2. 创建可测试、可重复执行的 whisper Runtime bootstrap 脚本；
3. 自动 clone / fetch 固定 upstream，并 checkout exact commit；
4. 对已有 `external/whisper.cpp` 做来源 / commit 校验，异常状态不得静默覆盖；
5. 使用 Manifest 冻结的第一版 Build Profile 配置并构建所需 Runtime；
6. 明确处理 `GGML_OPENMP` cache requested ON / 旧机 effective OFF 的差异，确保 clean build 不因宿主机 OpenMP 可用性漂移；
7. 验证 `whisper-cli` 与必需 whisper/ggml dylib 均存在且为 arm64；
8. 验证生成结果不依赖旧开发机绝对路径作为正式运行前提；
9. 建立 bootstrap / manifest 一致性测试和最小 Runtime smoke；
10. 做删除 `external/whisper.cpp` 后重新 bootstrap 的 clean-repo simulation；
11. 不进入 PyInstaller App packaging gate、`.command` orchestration、模型下载加固或新机器完整 E2E。

### 3.3 Step 4 验收方向

至少证明：

```text
Fresh Clone / 无 external/
-> 正式 whisper bootstrap
-> exact pinned upstream commit
-> frozen build profile
-> arm64 whisper-cli + required dylibs
-> minimal CLI/runtime smoke PASS
-> 删除 external/ 后重新执行仍可恢复相同 Runtime
```

Step 4 完成、commit + push 后，由人工 / ChatGPT 基于 GitHub 实现与测试再次审核；审核通过后才激活 Step 5。

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. 第一版冻结旧开发机成功的 whisper.cpp Build Profile，包括 `GGML_NATIVE=ON`；可能影响不同 Apple Silicon 代际 portability，必须在 M4 Max / M5 实际验收。
2. 旧 Build Profile 中 `GGML_OPENMP=ON` 是 cache 请求值，但旧构建实际 effective OpenMP 为 OFF；Step 4 必须显式稳定该结果，避免不同宿主机生成不同 Runtime。
3. 第一版沿用当前 `Contents/Resources/bin/` Bundle Runtime 布局，不在当前阶段重构目录。
4. 当前 Runtime component 集合以旧成功 build 为合同基线；Step 6 仍必须通过 `otool -L` 验证最终 App dependency closure。
5. Python 合同同时保留历史 broad floor `>=3.11` 与正式 managed environment `3.12.14 / >=3.12,<3.13`；实际可复现构建环境以 3.12.14 为准，后续不应把 3.11 视为当前正式构建目标。
6. Python bootstrap 依赖 macOS host 提供 `curl`、`shasum`、`tar` 等系统工具；当前旧机 / throwaway 验证通过，最终 clean-machine 仍需验证这些宿主前提无需人工技术配置。
7. 当前普通用户最小发布形式为 ZIP + `.app`，暂不要求 Developer ID / Notarization / DMG。

---

## 5. 当前未敲定参数

```text
# Step 4
CMake exact version / 自动获取方式
GGML_OPENMP requested/effective 状态的最终固定方式
whisper bootstrap 的本地 tool/cache 布局
最小 whisper-cli Runtime smoke 命令

# 后续
minimum macOS（当前不承诺旧系统，保持未设置）
最终 App dependency closure / RPath gate 细节
模型 checksum / size manifest 来源与维护策略
Developer ID signing / notarization 实施时间点
GitHub Release 正式版本和自动发布流程
```

---

## 6. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine，用于开发、自动测试、clean-repo simulation、稳定 ASR 回归、Commit / Push。

新 Mac：Clean-machine Acceptance Machine，不手工复制 `external/`、CLI、dylib 或模型，不使用旧 venv，不通过临时 Terminal 命令修补正式流程。

当前实际硬件验收基线：

```text
MacBook Air / M5 / 16 GB / 512 GB / macOS 27 Beta
MacBook Pro / M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

M4 / M5 支持声明必须分别有项目实际验证证据；M1 / M2 / M3 仅理论兼容，不作保证。旧版 macOS 当前不作保证。

---

## 7. 当前已知 Failure Modes

### Python / Build

- Python 环境已经可重建，但现有 `build_macos*.sh` 尚未统一消费正式 `.venv` / bootstrap；该整合留给 Step 5。
- 缺 `whisper-cli` 目前仍可能只 Warning；Spec 对 Runtime 仍可 optional collection。
- `install_name_tool` 部分错误仍可能被忽略；尚无最终 App post-build CLI / dyld smoke。

### Whisper Runtime

- Fresh Clone 尚不能自动生成 `external/whisper.cpp` 和 Runtime；Step 4 解决。
- `GGML_NATIVE=ON` portability 尚未跨 M4/M5 验证。
- `GGML_OPENMP` requested/effective 状态当前存在可复现性风险。
- 旧 CLI Build RPath 含开发机构建路径；最终 App closure / RPath gate 仍留 Step 6。

### 模型下载

- 当前仍直接写最终 `.bin`；中断 / HTTP failure / partial file / retry / checksum 问题尚未解决。

---

## 8. 后续步骤

```text
Step 1：Clean-machine Gap Audit                     已完成
Step 2：部署合同与 Runtime Manifest                已完成
Step 3：建立可重建的 Python 环境                   已完成
Step 4：Whisper Runtime Bootstrap                   ACTIVE
Step 5：可双击的一键构建入口                        待做
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
1. 主动 git fetch + git pull --ff-only origin main
2. 确认 main / clean worktree / HEAD == origin/main
3. 读取 deployment_static.md / deployment_runtime.md / PACKAGING.md / runtime_manifest.json
4. 检查现有 resource_paths / build scripts / specs / external whisper build 状态
5. 只执行 Deployment Step 4
6. Codex 不修改 deployment_runtime.md
7. 实现、自检通过后一个 commit 并 push main
8. 人工 / ChatGPT 审核后再推进 runtime
```

进入 Step 4 正式实现前，应先确认本 Step 的 CMake 自动获取方式和 `GGML_OPENMP` 最终固定策略；不得默认为当前宿主机环境决定。

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
