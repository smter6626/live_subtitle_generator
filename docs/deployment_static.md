# deployment_static.md

最后更新：2026-08-17  
文档角色：Deployment 工作线稳定合同（static contract）

本文件记录 Classroom Live Transcriber 在 `main` 分支上的 **deployment / packaging / clean-machine reproducibility / bugfix** 长期边界、交付目标和不可破坏的工程约束。

只有当部署方向、支持范围、交付目标或硬约束发生实质变化时才更新本文件。

动态执行状态见：`docs/deployment_runtime.md`。

LLM 功能线的稳定合同与动态状态继续由 `llm-sidecar-phase1` 分支中的 `docs/whisper_static.md` / `docs/whisper_runtime.md` 维护。两条工作线不得混用 ACTIVE step、验收状态或 roadmap。

---

## 1. Main 分支当前产品目标

一句话目标：

> **让符合硬件要求的 macOS Apple Silicon 机器无需手动配置开发或运行环境，仅需安装 App、下载模型，即可直接完成本地实时转录。**

开发者交付路径：

```text
Git clone
-> 双击正式构建入口
-> 自动准备可复现 Python 环境
-> 自动准备 whisper.cpp Runtime
-> 生成完整 ClassroomTranscriber.app
```

普通用户交付路径：

```text
GitHub Release ZIP
-> 解压 ClassroomTranscriber.app
-> 双击启动
-> Model Manager 下载模型
-> 授予麦克风权限
-> Start Recording
-> 正常转录
-> Stop
-> 生成完整 session
```

普通用户不应需要接触：

```text
Git
Python
pip / uv / venv
CMake
Shell
external/whisper.cpp
whisper-cli 手工安装
```

---

## 2. 当前平台范围

当前目标平台：

```text
macOS
Apple Silicon / arm64
```

当前不承诺：

```text
Intel
Universal2
Windows
```

当前 Deployment 实际验收目标硬件仅为：

```text
MacBook Air / Apple M5 / 16 GB / 512 GB / macOS 27 Beta
MacBook Pro / Apple M4 Max / 48 GB / 1 TB / macOS 27 Beta
```

M4 / M5 只有在上述对应机器完成实际验收后，才可声明“项目已实际验证”。M1 / M2 / M3 只能声明“理论兼容 Apple Silicon / arm64，但未经项目实际验证”，不得保证支持。当前不保证旧版 macOS；`minimum_macos` 保持 `null` / pending，必须经过实际验证后才能冻结，不得猜测或写死。

正式 Developer ID signing / notarization 属于发布层工作，不是 Runtime 完整性的替代条件。即使当前仅使用 ad-hoc signing，正式构建仍必须保证完整可转录 Runtime。

---

## 3. 稳定 ASR 主链路合同

稳定主链路：

```text
PySide6 UI
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore
```

运行时链路：

```text
麦克风 48kHz mono
-> ring buffer
-> 10s chunk / 3s overlap
-> 16kHz resample
-> whisper.cpp CLI + Metal + ggml/gguf model
-> raw
-> simple_dedup()
-> fuzzy_boundary_dedup()
-> clean
-> UI/session files
```

每个 session 的基础 evidence layer：

```text
raw.txt
clean.txt
session.log
config.json
```

Deployment 工作默认只处理：

```text
依赖可复现
Runtime 准备
Packaging
首次运行
模型下载可靠性
Release artifact
与上述流程直接相关的既有 Bug
```

除非任务明确针对相关 Bug，否则避免修改：

```text
audio capture
ring buffer
chunk scheduling
resample
WhisperCppBackend
simple_dedup()
fuzzy_boundary_dedup()
TranscriptStore raw / clean 写入
Start / Stop
麦克风释放
UI 主线程
```

任何部署改动都不得降低现有稳定 ASR 行为。

---

## 4. 与 LLM 工作线的边界

`main` 当前 Deployment 工作线与 `llm-sidecar-phase1` 功能线并行存在。

```text
main
  -> 稳定 ASR 基线
  -> deployment / packaging / reproducibility / bugfix
  -> docs/deployment_static.md
  -> docs/deployment_runtime.md

llm-sidecar-phase1
  -> LLM sidecar 功能线
  -> docs/whisper_static.md
  -> docs/whisper_runtime.md
```

Deployment 工作不得顺带推进：

```text
LLM provider
summary
readable pipeline
rolling sidecar
LLM UI preview
session browser
persistent whisper backend
```

反过来，LLM runtime 的 ACTIVE step 不得被用来推断 `main` 的 Deployment 状态。

---

## 5. Whisper Runtime 合同

最终 `.app` 的本地转写 Runtime 至少由以下部分构成：

```text
whisper-cli
libwhisper
libggml
libggml-base
libggml-cpu
libggml-blas
libggml-metal
vendor/whisper.cpp/download-ggml-model.sh
```

模型文件不内置在 App 中，由 Model Manager 管理和下载。

### 5.1 external/whisper.cpp 的定位

`external/whisper.cpp` 是：

```text
本地、可重建的第三方源码 + 构建目录
```

它必须继续被主仓库 Git 忽略，不得成为 Fresh Clone 的隐式前提。

正式 Bootstrap 必须能够从固定上游版本重新生成所需 Runtime。

### 5.2 Vendored 模型下载脚本

模型下载脚本固定由主仓库维护：

```text
vendor/whisper.cpp/download-ggml-model.sh
```

其上游来源、Commit 和 License 必须可追溯。

Vendored 模型下载脚本只解决“模型如何下载”，不代表 `whisper-cli` Runtime 已被提供。

### 5.3 固定上游与第一版 Build Profile

第一版正式 Runtime 固定为：

```text
repository: https://github.com/ggml-org/whisper.cpp.git
commit: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
architecture: arm64
```

Bootstrap 必须使用该固定 Commit，不得跟随 upstream main。

第一版同时冻结旧开发机已成功工作的 Runtime Build Profile：

```text
CMake 4.2.3
Unix Makefiles
Release
explicit arm64
shared libraries
Metal ON
Accelerate / BLAS ON
GGML_OPENMP OFF
GGML_NATIVE ON
```

正式 CMake 4.2.3 从 Kitware 官方 macOS universal tarball 获取，使用官方 SHA-256 校验并保存于被忽略的项目 `.tools/cmake/4.2.3/`，不 fallback 到 Homebrew / Conda / 系统 CMake。正式配置显式设置 `CMAKE_OSX_ARCHITECTURES=arm64`，并通过 `cmake --fresh` 排除历史 cache。

旧机 cache 曾请求 `GGML_OPENMP=ON`，但成功 Runtime 的 effective OpenMP 为 OFF；正式 Profile 因此固定 `GGML_OPENMP=OFF`，避免宿主机 libomp 状态造成漂移，同时保留 requested/effective 历史证据。完整、去除机器路径和 cache 噪声后的 Profile 以 `packaging/runtime_manifest.json` 为准。`GGML_NATIVE=ON` 是当前为了简化而冻结的值，可能影响不同 Apple Silicon 代际之间的 portability；本阶段不修改，后续必须在 M4 Max 与 M5 的 Clean-machine / E2E 验收中确认。

---

## 6. Python 环境合同

旧 venv 不是交付物，也不是可复现环境。

长期原则：

```text
不保存或迁移 venv 本体
保存重建环境所需的 Python 版本合同 + dependency lock + bootstrap
```

项目 Python 环境合同：

```text
Python >= 3.11
正式 minor 系列 >=3.12,<3.13
实际冻结 Python 3.12.14
```

正式环境方案固定为：

```text
uv
+ pyproject.toml
+ uv.lock
+ .python-version
+ 项目本地 .venv
```

uv 冻结为 0.12.5，由 `scripts/bootstrap_python_env.sh` 从 Astral 官方 release 获取并校验
SHA-256；uv、managed Python 和 cache 保存在被 Git 忽略的项目 `.tools/` 下。正常重建固定执行
`uv sync --frozen`，不得静默更新 lock。冻结的直接依赖为 PySide6 6.11.1、numpy 2.5.2、
sounddevice 0.5.6，以及 build/development 依赖 PyInstaller 6.22.1。

正式部署环境必须：

- 由项目正式入口创建或恢复；
- 不依赖系统偶然存在的 Conda/Homebrew Python；
- 不依赖开发机历史 venv；
- 能从锁定信息重新建立；
- 在构建前进行关键 package/import smoke test；
- 构建过程始终使用项目选定的 Python 环境。

Python minor/patch、uv、PySide6、PyInstaller、numpy、sounddevice 和依赖锁已经通过独立环境重建验证冻结；后续更新必须是显式维护并重新测试，不得采用开发机偶然版本。

---

## 7. Build / Packaging 安全合同

正式构建成功必须意味着生成的 App 具备实际本地转录能力，而不是仅能打开 UI。

构建必须 Fail Fast：

```text
缺 Python 环境 -> fail
缺关键 Python package -> fail
缺 whisper-cli -> fail
缺必需 dylib -> fail
错误 CPU 架构 -> fail
RPath / dylib closure 不完整 -> fail
模型下载脚本缺失 -> fail
post-build Runtime smoke 失败 -> fail
```

禁止：

```text
Warning 后继续生成残缺 App
静默跳过关键 Runtime
Build complete 但无法实际转录
```

PyInstaller Spec、Build Script、packaged Runtime helper / verifier 和 Runtime Manifest 共享同一套 required Runtime 事实源，避免多处独立硬编码后漂移。正式 Release build 只在 App 内组件、arm64、Mach-O dependency closure、下载脚本、ad-hoc 签名和 bundled/isolated CLI smoke 全部通过后报告成功。

---

## 8. 模型管理与下载合同

模型继续不进入 Git，也不内置在 `.app`。

普通用户通过 Model Manager 下载或导入模型。

模型下载正式流程必须满足：

- HTTP 错误不能被误认为成功；
- 中断下载不能留下可被识别为完整模型的最终文件；
- 下载失败后可以安全重试；
- 最终文件应通过可信的完整性验证；
- 完成前使用临时/partial 文件；
- 成功后再原子切换到最终文件名；
- 磁盘空间不足应尽可能提前给出明确错误。

现有大于最小文件大小的检查不能作为最终模型完整性验证方案。

---

## 9. Clean-machine 验收合同

### 9.1 开发机与验收机职责长期原则

当前 Deployment 工作线长期采用“两台机器分工”策略：

```text
旧 MacBook = Developer / Reference Machine
新 Mac = Clean-machine Acceptance Machine
```

核心原则：

> **继续在旧开发机完成实现、回归和已知依赖治理；尽可能在旧机器上消灭可预见的隐式依赖和安装缺口。新机器保持尽量纯净，只负责验证正式流程是否仍遗漏未知依赖。**

不得为了加快开发而把新机器逐步改造成第二台历史开发环境。尤其避免在新机器上长期保留项目专用的手工修补状态，例如：

```text
手工创建并维护项目 venv
手工复制 external/whisper.cpp
手工编译 whisper-cli
手工复制 dylib
手工复制模型
临时修改 PATH 以绕过正式流程
只存在于新机器本地的修补脚本或 UI 修改
```

新机器测试发现缺失依赖或额外操作时，默认处理方式必须是：

```text
记录为 deployment bug
-> 回旧开发机修复正式 Bootstrap / Build / App 流程
-> Commit / Push main
-> 新机器重新从正式入口验证
```

不得把一次性人工补救命令视为验收通过。

旧机器用于：

```text
开发
单元测试
构建验证
clean-repo simulation
稳定 ASR 回归
Commit / Push
```

旧机器已经存在历史环境，因此旧机器成功不能证明 Fresh Clone 可复现；旧机器上的 clean-repo simulation 也只能证明仓库状态较干净，不能替代真实 clean-machine 验收。

新机器作为 Clean-machine 验收机，原则上：

```text
不手工复制 external/
不手工编译 whisper-cli
不手工复制模型
不采用实验性本地 UI 修改
不通过临时命令修补正式流程
```

Developer E2E 必须从：

```text
干净 main
-> 正式构建入口
-> App
-> 模型下载
-> 实际转录
```

通过。

任何为了让新机器成功而额外执行、但没有进入正式流程的人工命令，都应视为新的 deployment bug。

普通用户 Release 验收则必须进一步从 GitHub Release ZIP 开始，不依赖源码仓库。

---

## 10. Git 与 Step 执行规则

Deployment 当前统一在 `main` 上推进，除非用户明确要求新分支或任务属于高风险实验。

默认行为：

1. 使用 `main`；
2. 不自行创建新 branch；
3. 不修改 `llm-sidecar-phase1`；
4. 不 merge LLM 分支；
5. 不 force push；
6. 一个明确 Step 一个 commit；
7. 自检通过后 push 到 `main`；
8. 如果当前分支不是 `main`，或工作区已有未说明修改，先停止并汇报。

每个实现 Step 的基本流程：

```text
确认 branch / worktree
-> 读取 deployment_static + deployment_runtime
-> 实现单一 Step
-> 自动测试 / 静态检查
-> Commit
-> Push main
-> 人工审查
-> 再受控更新 deployment_runtime
```

除非用户明确要求，Codex 默认只读取 `docs/deployment_runtime.md`，不主动修改其 ACTIVE 状态。

---

## 11. Runtime Manifest 原则

`packaging/runtime_manifest.json` 是机器可读 Runtime 合同，作为：

```text
平台
架构
whisper.cpp 上游版本
Runtime 文件
Bundle 目标
验证方法
Pending decisions
```

的稳定事实源。

Manifest 的 Python、CMake、whisper.cpp Build Profile、正式开发者构建入口和 Runtime component / bundle contract 已被 Bootstrap、orchestrator、PyInstaller Spec、packaging helper、严格 post-build verifier 与测试消费。

Manifest 不得包含：

```text
用户绝对路径
模型文件
API key / secret
旧机器缓存路径
```

---

## 12. Release 合同

Developer Deployment MVP 完成标准：

```text
Clean clone
-> 自动建立可复现 Python 环境
-> 自动准备固定 whisper.cpp Runtime
-> 双击正式构建入口
-> 完整 App
-> 新机器启动 App
-> 下载模型
-> 实际录音转写
-> Stop 正常
-> evidence layer 正常生成
```

达到上述里程碑后，可以恢复 LLM 功能开发；Developer ID、Notarization、DMG、GitHub Actions 自动发布不应无限阻塞 LLM。

普通用户最小 Release 形态：

```text
ClassroomTranscriber-<version>-macOS-AppleSilicon.zip
```

ZIP 内的 `.app` 必须先在没有源码仓库和开发环境的新机器上验证。

Developer ID signing / notarization 属于后续正式发布增强。

---

## 13. 非目标

当前 Deployment 工作线不负责：

```text
LLM 功能实现
Session Browser / Search
Persistent whisper backend
ASR 参数优化
Dedup 调参
OpenCC / 多语言 clean 层
Windows 支持
Intel 支持
Universal2
与部署无关的新 UI 功能
```

除非后续明确改变方向，否则这些内容不得混入当前 Deployment ACTIVE Step。
