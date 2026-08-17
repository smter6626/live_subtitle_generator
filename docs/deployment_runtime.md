# deployment_runtime.md

最后更新：2026-08-17  
文档角色：Deployment 工作线动态执行状态（runtime state）

本文件只记录 Classroom Live Transcriber 在 `main` 分支上的 deployment / packaging / clean-machine reproducibility / bugfix 执行状态。

长期稳定合同见：`docs/deployment_static.md`。

LLM 功能线的动态状态仍由 `llm-sidecar-phase1` 分支中的 `docs/whisper_runtime.md` 维护。两条工作线不得混用 ACTIVE step、完成记录或验收状态。

---

## 0. 使用规则

### 0.1 更新规则

每完成一个 Deployment Step 后：

1. 将刚完成的 ACTIVE step 标记为已完成；
2. 追加完成内容、测试命令和验证结论；
3. 激活下一步；
4. 保证全文件只有一个 ACTIVE Step；
5. 将下一步细化到可以直接交给 Codex 或人工执行；
6. 不删除历史完成记录。

### 0.2 static / runtime 职责

`deployment_static.md` 记录长期方向、产品目标、平台边界、稳定 ASR 合同，以及 Runtime / Python / Packaging / Release 的长期硬约束。

本文件记录当前 checkpoint、唯一 ACTIVE Step、已完成 Step、当前已知缺口、旧机器观察值、未敲定参数和下一步执行说明。

如果 runtime 与 static 冲突：先判断是否发生方向变更；如是，先更新 static，再同步 runtime。runtime 不得静默覆盖 static。

### 0.3 Codex 与 runtime

除非用户明确要求，Codex 默认只读取本文件，不主动修改本文件。

通常流程：

```text
Codex 执行当前代码 Step
-> commit + push main
-> 人工 / ChatGPT 审查 GitHub 实际实现和测试
-> 再受控更新 deployment_runtime.md
```

---

## 1. 当前 checkpoint

```text
当前分支：main
当前实现 checkpoint：988eb5d8af61044175236d851a838a6f2793e0c0
checkpoint 内容：chore: define deployment runtime manifest
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
唯一 ACTIVE：Deployment Step 3 - 建立可重建的 Python 环境
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

生产代码 checkpoint：

```text
2aa7bafc99c5f872719b22a0e431e4634cb22d92
fix: vendor whisper model download script
```

结果：

- `vendor/whisper.cpp/download-ggml-model.sh` 已进入主仓库；
- Fresh Clone 的模型下载脚本不再依赖 `external/whisper.cpp/models/`；
- 上游来源、固定 Commit 和 MIT License 已记录；
- source / frozen resource path 已区分；
- 模型下载脚本进入 PyInstaller resource。

---

### Deployment Step 1：Clean-machine Gap Audit

状态：已完成，仅审计，无生产代码修改。

审计确认的核心缺口：

- Fresh Clone 没有 Bootstrap 和可双击 `.command` 构建入口；
- Python 环境不可复现，旧 venv 不能作为正式交付环境；
- Fresh Clone 没有 `whisper-cli` 和 whisper/ggml dylib；
- release build 对缺失 `whisper-cli` 仅 Warning；
- PyInstaller Spec 会静默略过缺失 Runtime；
- 没有 post-build CLI / dylib / architecture smoke；
- 模型下载缺少完整性、失败恢复和安全重试机制。

---

### Deployment Step 2：部署合同与 Runtime Manifest

状态：已完成、已人工 / ChatGPT 基于 GitHub 实际内容审核通过。

实现 commit：

```text
988eb5d8af61044175236d851a838a6f2793e0c0
chore: define deployment runtime manifest
```

创建：

```text
PACKAGING.md
packaging/runtime_manifest.json
testCodes/test_runtime_manifest.py
```

最小更新：

```text
docs/deployment_static.md
README.md
docs/工程细节.md
```

未修改生产代码、ASR 主链路、LLM 代码、现有 build/spec/runtime 行为或模型下载行为。

Runtime Manifest 已冻结 / 记录：

```text
platform: macOS / Apple Silicon / arm64
Python minimum: >= 3.11
Python env strategy: uv + pyproject.toml + uv.lock + project-local .venv
whisper.cpp repo: https://github.com/ggml-org/whisper.cpp.git
whisper.cpp commit: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
first build profile: old-machine successful Runtime profile
runtime components: whisper-cli + required whisper/ggml dylibs
bundle baseline: Contents/Resources/bin
formal build: fail-fast contract
model: not bundled / not part of Runtime Manifest
```

旧开发机实际观察值已记录，包括：

```text
CMake 4.2.3
Unix Makefiles
Release
arm64
shared libraries ON
Metal ON
Accelerate / Apple BLAS ON
GGML_NATIVE ON
GGML_OPENMP cache option ON, old build effective OpenMP OFF
libwhisper.1.dylib
libggml.0.dylib
libggml-base.0.dylib
libggml-cpu.0.dylib
libggml-blas.0.dylib
libggml-metal.0.dylib
```

Manifest 将逻辑 Runtime component 与 observed ABI filename 分开，并记录旧 CLI 使用 `@rpath`、旧 build 含开发机绝对 RPath 的事实，但不保存绝对路径值。

Step 2 测试：

```text
python3 -m json.tool packaging/runtime_manifest.json >/dev/null      PASS
python3 -m unittest testCodes.test_runtime_manifest -v              PASS / 14 tests
git diff --check                                                     PASS
```

GitHub 审核确认该 commit 仅包含 6 个预期文本文件，`main` 在该实现 commit 上相对前一 checkpoint ahead 1 / behind 0。

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 3 - 建立可重建的 Python 环境
```

### 3.1 目标

将当前依赖旧机器历史 Python / venv 的状态替换为可从仓库合同重新建立的正式 Python 构建环境。

正式方案已经锁定：

```text
uv
+ pyproject.toml
+ uv.lock
+ 项目本地 .venv
```

Python 最低要求：

```text
>= 3.11
```

本 Step 必须通过实际验证后确定并冻结：

```text
Python exact minor / patch
PySide6 exact version
PyInstaller exact version
numpy exact version
sounddevice exact version
uv exact version / bootstrap policy
lockfile 更新策略
```

### 3.2 Step 3 预期工作

1. 盘点当前应用和 packaging 实际 Python import / dependency；
2. 在不依赖旧 `venv` 的前提下建立正式 `pyproject.toml`；
3. 选择并验证一个明确 Python 版本；
4. 锁定 PySide6 / PyInstaller / numpy / sounddevice 及必要间接依赖；
5. 生成并提交 `uv.lock`；
6. 提供可重复建立项目 `.venv` 的正式命令 / 脚本入口；
7. 建立 import smoke / dependency smoke；
8. 在旧开发机使用 throwaway / clean environment 验证从零重建；
9. 不复用、修复或迁移旧历史 venv。

### 3.3 Step 3 边界

本 Step 不做：

```text
whisper.cpp clone / compile / Runtime bootstrap
修改 whisper.cpp Build Profile
修改 ASR 主链路
模型下载加固
正式一键 .command orchestration
严格 PyInstaller Runtime gate
新机器完整 App E2E
LLM 开发
```

如为了验证 Python packaging 必须执行最小 PyInstaller import/build smoke，应先确认不会把 Step 4-6 的 Runtime / App 完整性工作混入本 Step。

### 3.4 Step 3 验收方向

至少需要证明：

```text
删除 / 不使用旧 venv
-> 从仓库声明的 Python/uv 合同建立新的项目环境
-> uv 使用 lock 精确同步
-> 关键 imports PASS
-> PyInstaller 可被正式环境调用
-> 不依赖系统偶然存在的 Conda/Homebrew Python package
```

Step 3 完成后再由人工 / ChatGPT 审核 GitHub 实现，审核通过后将 Step 4 激活。

---

## 4. 当前为简化而保留、后续可能产生影响的内容

1. 第一版冻结旧开发机成功的 whisper.cpp Build Profile，包括 `GGML_NATIVE=ON`；可能影响不同 Apple Silicon 代际 portability，后续必须在 M4 Max / M5 实际验收。
2. 旧 Build Profile 中 `GGML_OPENMP=ON` 是 cache 请求值，但旧构建实际 effective OpenMP 为 OFF；Step 4 必须显式处理这一差异，避免 clean machine 上因 OpenMP 可用性不同而产生不同 Runtime。
3. 第一版沿用当前 `Contents/Resources/bin/` Bundle Runtime 布局，不在当前阶段重构目录。
4. 当前 Runtime 组件集合以旧成功 build 为合同基线；Step 6 仍必须通过 `otool -L` 验证 dependency closure。
5. 当前普通用户最小发布形式为 ZIP + `.app`，暂不要求 Developer ID / Notarization / DMG。

---

## 5. 当前未敲定参数

```text
# Step 3
Python exact minor / patch
PySide6 exact version
PyInstaller exact version
numpy exact version
sounddevice exact version
uv exact version / bootstrap policy
lockfile 更新策略

# Step 4
CMake 的自动获取 / 安装实现方式
GGML_OPENMP requested/effective 状态如何稳定复现

# 后续
minimum macOS（当前不承诺旧系统，保持未设置）
模型 checksum / size manifest 来源与维护策略
Developer ID signing / notarization 实施时间点
GitHub Release 正式版本和自动发布流程
```

---

## 6. 开发机与验收机状态

旧 MacBook：Developer / Reference Machine。

用于：

```text
开发
单元测试
clean-repo / throwaway-environment simulation
构建验证
稳定 ASR 回归
Commit / Push
```

新 Mac：Clean-machine Acceptance Machine。

原则：

```text
不手工复制 external/
不手工编译 whisper-cli
不手工复制模型
不使用旧机器 venv
不采用实验性本地 UI 修改
不通过临时命令补正式流程
```

当前实际硬件基线：

```text
MacBook Air / M5 / 16 GB / 512 GB / macOS 27 Beta
MacBook Pro / M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

M4 / M5 支持声明必须分别有项目实际验证证据；M1 / M2 / M3 仅理论兼容，不作保证。旧版 macOS 当前不作保证。

---

## 7. 当前已知 Failure Modes

### Python / Build

- 旧 venv 不可迁移，历史 `pip` shebang 已失效；
- 当前仓库尚未有正式 `pyproject.toml + uv.lock` 环境合同；
- 当前构建仍受构建机已有 Python/PyInstaller/PySide6 状态影响；
- 缺 `whisper-cli` 目前仍只 Warning；
- Spec 对 Runtime 仍可 optional collection；
- `install_name_tool` 部分错误仍可能被忽略；
- 尚无 post-build CLI / dyld smoke。

### App / Start

- UI 启动不代表 CLI Runtime 完整；
- CLI 架构 / dylib / RPath / 模型问题可能直到首个 chunk 才暴露。

### 模型下载

- 当前仍直接写最终 `.bin`；
- 中断 / HTTP failure / partial file / retry / checksum 问题尚未解决。

---

## 8. 后续步骤

```text
Step 1：Clean-machine Gap Audit                     已完成
Step 2：部署合同与 Runtime Manifest                已完成
Step 3：建立可重建的 Python 环境                   ACTIVE
Step 4：Whisper Runtime Bootstrap                   待做
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
1. git pull / fetch 后确认 main 与 origin/main 一致
2. 确认工作区干净
3. 读取 docs/deployment_static.md
4. 读取 docs/deployment_runtime.md
5. 读取 PACKAGING.md
6. 读取 packaging/runtime_manifest.json
7. 只推进 Deployment Step 3
```

在开始写 Step 3 实现前，先完成 Python 依赖盘点和版本方案确认；不得直接根据旧 venv 的偶然版本生成 lock。

---

## 10. 上下文恢复入口

恢复 `main` Deployment 工作线时按顺序读取：

```text
1. docs/deployment_static.md
2. docs/deployment_runtime.md
3. PACKAGING.md
4. packaging/runtime_manifest.json
5. README.md
6. docs/工程细节.md
7. 与 ACTIVE Step 相关的 packaging/ 和 scripts/
```

恢复 LLM 功能线时切换到 `llm-sidecar-phase1`，读取：

```text
docs/whisper_static.md
docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
