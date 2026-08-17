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

`deployment_static.md` 记录：

```text
长期方向
产品目标
平台边界
稳定 ASR 合同
Runtime / Python / Packaging / Release 硬约束
Git 与工作线规则
```

本文件记录：

```text
当前 checkpoint
当前唯一 ACTIVE Step
已完成 Step
当前已知缺口
旧机器观察值
Pending decisions
下一步执行说明
```

如果 runtime 与 static 冲突：

- 先判断是否发生了方向变更；
- 如果是方向变更，先更新 static；
- 再同步 runtime；
- 不允许 runtime 静默覆盖 static 的长期合同。

### 0.3 Codex 与 runtime

除非用户明确要求，Codex 默认只读取本文件，不主动修改本文件。

通常流程：

```text
Codex 执行当前代码 Step
-> commit + push main
-> 人工 / ChatGPT 审查实现和测试
-> 再受控更新 deployment_runtime.md
```

这样避免 runtime 提前进入完成态或与代码实现漂移。

---

## 1. 当前 checkpoint

```text
当前分支：main
当前代码 checkpoint：2aa7bafc99c5f872719b22a0e431e4634cb22d92
checkpoint 内容：fix: vendor whisper model download script
当前工作线：Deployment / Packaging / Reproducibility / Bugfix
唯一 ACTIVE：Deployment Step 2 - 冻结部署合同与 Runtime Manifest
```

说明：

- `2aa7baf...` 是当前 Deployment 工作开始时的生产代码 checkpoint；
- 后续文档整理 commit 不改变该生产代码 checkpoint 的含义；
- 每个实际实现 Step 开始前仍必须通过 Git 命令确认最新 `main` 和 `origin/main` 状态。

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

真实课堂路线已验证：

```text
whisper.cpp + Metal + large-v3
```

本工作线默认保护该主链路，不以部署优化为理由重构 ASR。

---

### Deployment Step 0.5：Vendor 模型下载脚本修复

状态：已完成并 push `main`。

生产代码 checkpoint：

```text
2aa7bafc99c5f872719b22a0e431e4634cb22d92
fix: vendor whisper model download script
```

主要结果：

- `vendor/whisper.cpp/download-ggml-model.sh` 进入主仓库；
- Fresh Clone 的模型下载脚本不再依赖 `external/whisper.cpp/models/`；
- 上游来源、固定 Commit 和 MIT License 已记录；
- source / frozen resource path 已区分；
- 模型下载脚本进入 PyInstaller resource；
- Fresh Clone 的“下载脚本不存在”问题已修复。

未解决：

```text
whisper-cli Runtime 自动准备
Python 环境可复现
严格 Packaging gate
模型下载完整性
Clean-machine E2E
```

---

### Deployment Step 1：Clean-machine Gap Audit

状态：已完成，仅审计，无生产代码修改。

审计基线：

```text
main / 2aa7bafc99c5f872719b22a0e431e4634cb22d92
```

关键结论：

1. Fresh Clone 没有 Bootstrap；
2. Fresh Clone 没有可双击 `.command` 构建入口；
3. Python 环境不可复现；
4. 旧 `venv/bin/pip` 因仓库移动仍指向旧 shebang，证明 venv 不应迁移复用；
5. Fresh Clone 没有 `external/whisper.cpp`；
6. Fresh Clone 没有 `whisper-cli` 和 whisper/ggml dylib；
7. release build 对缺失 `whisper-cli` 只 Warning 后继续；
8. PyInstaller Spec 使用 optional `existing_resource()`，会静默略过缺失 Runtime；
9. 当前可能生成能打开 UI、能下载模型但不能转录的残缺 App；
10. 没有 post-build CLI / dylib / architecture smoke；
11. 模型下载没有 `.part`、atomic rename、checksum、可靠失败清理和安全重试；
12. 当前构建结果仍依赖旧开发机 Python、PyInstaller、PySide6 和本地 whisper.cpp 历史状态。

本 Step 允许的静态验证已通过：

```text
bash -n scripts/build_macos.sh
bash -n scripts/build_macos_debug.sh
sh -n vendor/whisper.cpp/download-ggml-model.sh
Python import smoke
```

未运行：

```text
完整 App build
UI
模型下载
麦克风录音
新机器验收
App 内 whisper-cli runtime
```

---

## 3. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 2 - 冻结部署合同与 Runtime Manifest
```

### 3.1 目标

建立后续 Deployment 的稳定事实源，使 Step 3 以后不再依赖：

```text
旧机器记忆
被忽略的 CMakeCache
多份独立硬编码 Runtime 文件列表
隐式 Python 环境
口头约定
```

本 Step 计划产物：

```text
docs/deployment_static.md
docs/deployment_runtime.md
PACKAGING.md
packaging/runtime_manifest.json
testCodes/test_runtime_manifest.py
```

以及必要的最小 README / 工程文档同步。

### 3.2 已锁定需求

#### 平台与实际验收范围

```text
目标平台：macOS / Apple Silicon / arm64
实际验收硬件：
- MacBook Air / M5 / 16 GB / 512 GB / macOS 27 Beta
- MacBook Pro / M4 Max / 48 GB / 1 TB / macOS 27 Beta

实际支持声明目标：M4 / M5 两代在项目两台机器上通过验收
M1 / M2 / M3：仅标记为理论兼容 Apple Silicon / arm64，未经项目实际验证，不作保证
旧版 macOS：不作保证
minimum_macos：保持未设置
```

#### 普通用户交付合同

```text
普通用户不得被要求通过 Terminal 或其他技术手段安装 Git、Python、pip、uv、venv、CMake、whisper.cpp、whisper-cli 或 dylib。

允许：
- App / Installer 自动检查依赖并一键完成所需安装；
- 将运行依赖直接打包进 App；
- 用户通过 App 内 Model Manager 下载模型。
```

#### 开发者源码构建起点

```text
git clone 视为开发者流程起点。
Clone 之后的 Python、Python packages、项目环境、whisper.cpp Runtime、Packaging 所需准备应由正式流程尽可能自动处理。
```

#### Python 环境方案

```text
uv
+ pyproject.toml
+ uv.lock
+ 项目本地 .venv

Python minimum：>= 3.11
Python exact minor / patch：本 Step 不冻结
```

#### whisper.cpp 上游与版本

```text
repository: https://github.com/ggml-org/whisper.cpp.git
commit: 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
architecture target: arm64
```

#### whisper.cpp 第一版 Build Profile

第一版冻结旧开发机当前已验证成功的完整 Build Profile。Step 2 实现时从旧开发机现有 `CMakeCache.txt` / 构建状态提取并写入正式 Runtime Manifest / Packaging 合同。

当前已知至少包含：

```text
Build type: Release
Shared libraries: ON
Metal: ON
Accelerate / BLAS: ON
GGML_NATIVE: ON
Generator: Unix Makefiles
```

#### Runtime 文件合同

逻辑必需组件：

```text
whisper-cli
libwhisper
libggml
libggml-base
libggml-cpu
libggml-blas
libggml-metal
```

Manifest 同时记录当前观察到的实际 ABI 文件名；后续正式构建通过 `otool -L` 验证实际 dependency closure。

#### App Bundle Runtime 布局

```text
沿用当前 Bundle / Resources 布局，不在本 Step 重构目录结构。
主要 Runtime 资源继续以当前 Contents/Resources/bin/ 方向为基线。
```

#### 模型与 Runtime Manifest 边界

```text
packaging/runtime_manifest.json 不包含模型文件。
模型继续不进入 Git、不内置在 App。
模型 URL / size / checksum 如需机器可读合同，后续使用独立 model manifest。
```

#### 正式 Build 失败策略

```text
正式构建关键 Runtime 缺失时必须 Fail Fast。
不允许 Warning 后生成残缺 App。
当前不建立 UI-only 正式构建模式。
```

#### 开发者双击入口

```text
Build ClassroomTranscriber.command
-> scripts/bootstrap_and_build.sh
```

`.command` 只作为 Finder 入口；正式构建逻辑放在可测试脚本中。

#### 普通用户第一版 Release 形式

```text
GitHub Release ZIP
-> ClassroomTranscriber.app
```

当前 Deployment MVP 不要求 DMG / PKG / Developer ID / Notarization / GitHub Actions 自动 Release。

#### Deployment MVP 完成标准

```text
Fresh Clone main
-> 双击正式构建入口
-> 自动准备所需环境
-> 生成完整 App
-> 启动 App
-> Model Manager 下载模型
-> 授予麦克风权限
-> Start
-> 实际录音与转录
-> Stop
-> 麦克风正常释放
-> raw.txt / clean.txt / session.log / config.json 正常生成
```

### 3.3 当前为简化而保留、后续可能产生影响的内容

1. 第一版直接冻结旧开发机当前成功的完整 whisper.cpp Build Profile，包括 `GGML_NATIVE=ON`；该选择可能影响不同 Apple Silicon 代际之间的 Runtime portability，必须在 M4 Max 与 M5 两台机器的后续 Clean-machine / E2E 验收中实际验证。
2. 第一版沿用当前 App Bundle Runtime 布局，不在本阶段重构 `Contents/Resources/bin/` 等资源结构；后续如需更清晰的 `bin/lib/scripts` 分层，需要独立迁移并重新验证 RPath、Spec 和签名。
3. 第一版 Runtime 组件以当前已知 `whisper-cli + whisper/ggml dylib` 集合为合同基线，同时通过 `otool -L` 校验实际依赖闭包；上游未来 ABI 或依赖新增可能要求更新 Manifest。
4. 当前普通用户最小发布形式先采用 ZIP + `.app`，暂不要求 Developer ID / Notarization / DMG；后续正式公开分发仍可能需要补充这些发布层工作。

### 3.4 当前未敲定、留待后续 Step 决定的参数

```text
Python exact minor / patch
PySide6 version
PyInstaller version
numpy version
sounddevice version
uv / lock 具体版本与更新策略
CMake 的自动获取 / 安装实现方式
minimum macOS 版本（当前不承诺旧系统，保持未设置）
模型 checksum / size manifest 的来源与维护策略
Developer ID signing / notarization 的正式实施时间点
GitHub Release 的正式版本号与自动发布流程
```

### 3.5 本 Step 禁止范围

```text
重建 Python 环境
pip / uv 安装依赖
Whisper Bootstrap
Clone / 编译 whisper.cpp
PyInstaller App build
修改现有 build behavior
模型下载实现修改
ASR 主链路修改
LLM 开发
```

### 3.6 验收信号

- static 与 runtime 职责清晰；
- Runtime Manifest 可机器读取；
- Manifest 只包含仓库相对路径；
- 不包含模型、用户绝对路径或 secret；
- 已冻结值与未敲定值明确区分；
- Manifest 测试可在没有 PySide6 / PyInstaller / external 的情况下运行；
- 本 Step 不改变生产代码行为。

---

## 4. 旧机器观察状态

旧开发机仓库路径：

```text
/Users/smter-mac/Documents/personalAPPS/whisper
```

旧机器拥有但 Fresh Clone 不会获得：

### 4.1 Python

```text
venv/bin/python 可运行
旧 venv Python：3.13.7（审计观察值）
旧 venv numpy：2.4.3
旧 venv sounddevice：0.5.5
旧 venv 缺 PySide6 / PyInstaller
venv/bin/pip shebang 已因仓库移动失效
```

这些版本只作为历史观察，不得直接锁成正式环境。

### 4.2 whisper.cpp

```text
external/whisper.cpp
约 3 GiB
官方 ggml-org/whisper.cpp clone
commit 8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
```

旧 build 观察：

```text
Release
shared libraries
Metal ON
Accelerate / BLAS ON
GGML_NATIVE ON
Unix Makefiles
```

本地已有：

```text
whisper-cli
libwhisper.1.dylib
libggml.0.dylib
libggml-base.0.dylib
libggml-cpu.0.dylib
libggml-blas.0.dylib
libggml-metal.0.dylib
```

旧 CLI 原始 RPath 包含开发机构建目录的绝对路径；正式 App 不能依赖这些路径。

### 4.3 模型

旧机器已有 `large-v3` 模型，但没有正式可信 checksum 记录。

因此旧模型只能用于旧机回归，不作为可复现交付证据。

---

## 5. 当前已知 Failure Modes

### 5.1 Build 阶段

当前已知：

- 缺 Python / PyInstaller / PySide6 会 fail；
- 缺 Vendored 下载脚本会 fail；
- 缺 `whisper-cli` 目前只 Warning；
- Spec 会对 CLI/dylib 使用 optional collection；
- `install_name_tool` 部分错误会被忽略；
- 没有 post-build CLI/dyld smoke；
- codesign 失败不会被当作 Runtime 完整性失败。

### 5.2 App / Start 阶段

- UI 启动时不要求 CLI 已存在；
- Start 时会检查 CLI 是否存在和可执行；
- CLI 架构 / dylib / RPath / 模型损坏通常直到首个 chunk 才暴露；
- 因此“App 能打开”不是“App 能转录”的验证。

### 5.3 模型下载阶段

当前下载风险：

- 直接写最终 `.bin` 文件；
- curl 未形成正式 HTTP failure gate；
- 中断可能留下最终文件名残片；
- 已存在文件会阻止正常重试；
- 大于最小大小的残片可能被误判为 available；
- 无 checksum / 可信大小 manifest。

---

## 6. 新机器验收规则

新机器是 Clean-machine acceptance machine。

新机器原则：

```text
不手工复制 external/
不手工编译 whisper-cli
不手工复制模型
不使用旧机器 venv
不采用实验性本地 UI 修改
不通过临时命令补正式流程
```

后续 Developer E2E 验收必须为：

```text
Fresh Clone main
-> 正式双击构建入口
-> 自动准备环境
-> 生成 App
-> 启动 App
-> 下载模型
-> Start
-> 实际转录
-> Stop
-> raw.txt / clean.txt / session.log / config.json 正常
```

任何额外人工修补命令都算 deployment bug。

普通用户最终验收进一步要求：

```text
GitHub Release ZIP
-> 无源码仓库
-> 解压 App
-> 启动
-> 下载模型
-> 转录
```

---

## 7. 后续步骤

当前规划：

```text
Step 1：Clean-machine Gap Audit                     已完成
Step 2：部署合同与 Runtime Manifest                ACTIVE
Step 3：建立可重建的 Python 环境                   待做
Step 4：Whisper Runtime Bootstrap                   待做
Step 5：可双击的一键构建入口                        待做
Step 6：严格打包门禁与 post-build smoke             待做
Step 7：模型下载完整性、失败恢复与重试               待做
Step 8：新机器 Clone -> App -> 转录端到端验收         待做
Step 9：普通用户 GitHub Release ZIP 验收              待做
```

Deployment MVP 的暂停点：

```text
完成 Step 8
-> 建立一个干净可复现的 main checkpoint
-> 可以恢复 llm-sidecar-phase1 开发
```

Step 9 及 Developer ID / Notarization / DMG / GitHub Actions 可以作为后续 Release polish，不无限阻塞 LLM 功能线。

---

## 8. 当前未敲定参数

以下参数留待对应后续 Step 实测后确定：

```text
Python exact minor / patch
PySide6 version
PyInstaller version
numpy version
sounddevice version
uv / lock 具体版本与更新策略
CMake 的自动获取 / 安装实现方式
minimum macOS（当前不承诺旧系统，保持未设置）
模型 checksum / size manifest 来源与维护策略
Developer ID signing / notarization 实施时间点
GitHub Release 正式版本和自动发布流程
```

---

## 9. 下一步执行提示

当前继续开发时，优先顺序：

```text
1. 读取 docs/deployment_static.md
2. 读取本文件
3. 确认 git branch --show-current == main
4. 确认 git status --short 为空
5. fetch origin 并确认本地 main 与 origin/main 一致
6. 只执行 Deployment Step 2
```

Step 2 完成并人工审核后：

- 本文件将 Step 2 移入“已完成”；
- 唯一 ACTIVE 改为 Step 3；
- Step 3 再细化 Python 环境重建、锁定和 smoke test；
- 不在 Step 2 顺带开始 Python 安装。

---

## 10. 上下文恢复入口

如果项目再次停滞，恢复 `main` Deployment 工作线时按顺序读取：

```text
1. docs/deployment_static.md
2. docs/deployment_runtime.md
3. README.md
4. docs/工程细节.md
5. packaging/ 和 scripts/ 中与 ACTIVE Step 相关文件
```

如果要恢复 LLM 功能线：

```text
git switch llm-sidecar-phase1
-> docs/whisper_static.md
-> docs/whisper_runtime.md
```

不要使用另一条工作线的 ACTIVE Step 推断当前分支下一步。
