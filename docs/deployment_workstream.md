# Deployment Workstream

最后更新：2026-08-16  
文档角色：部署 / 可复现构建工作线的长期边界 + 动态执行状态

本文件专门维护 Classroom Live Transcriber 的 **deployment / packaging / clean-machine reproducibility / bugfix** 工作线。

它与 `llm-sidecar-phase1` 分支中的 LLM 开发状态完全分离：

```text
main
  -> 稳定 ASR 基线
  -> deployment / packaging / reproducibility / bugfix
  -> 本文件维护当前工作线状态

llm-sidecar-phase1
  -> LLM sidecar 功能线
  -> docs/whisper_static.md
  -> docs/whisper_runtime.md
```

禁止把两条工作线的 ACTIVE step、验收状态或 roadmap 混在同一 runtime 记录中。

---

## 1. 当前工作线目标

当前唯一产品化目标：

```text
开发者：
Git clone
-> 双击构建入口
-> 自动准备 Python 环境
-> 自动准备 whisper.cpp Runtime
-> 生成完整 ClassroomTranscriber.app

普通用户：
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

当前支持范围：

```text
macOS
Apple Silicon / arm64
```

当前不承诺：

```text
Intel
Universal2
Windows
正式 notarization
```

最低 macOS 版本尚未验证，不在本文档中猜测。

---

## 2. 稳定 ASR 基线

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

本工作线默认只修复部署、打包、依赖、Runtime、首次运行和既有 Bug，不重构上述稳定主链路。

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

---

## 3. 与 LLM 工作线的边界

LLM Sidecar 不是本工作线的 ACTIVE 范围。

当前 deployment 工作不得顺带推进：

```text
LLM provider
summary
readable pipeline
rolling sidecar
LLM UI preview
session browser
persistent whisper backend
```

`llm-sidecar-phase1` 中已有的 `docs/whisper_static.md` 和 `docs/whisper_runtime.md` 继续只描述 LLM 功能线。

本工作线不得根据其中的 ACTIVE LLM step 自动继续开发。

---

## 4. 当前 Git 基线

当前稳定分支：

```text
main
```

建立本工作线文档前已确认的远程基线：

```text
2aa7bafc99c5f872719b22a0e431e4634cb22d92
fix: vendor whisper model download script
```

该提交已完成：

- 将 `download-ggml-model.sh` 作为 Vendored Resource 纳入主仓库；
- Fresh Clone 的模型下载不再依赖 `external/whisper.cpp/models/download-ggml-model.sh`；
- 上游来源和 MIT License 已记录；
- 源码模式实际转写仍依赖本地 `whisper-cli` Runtime。

---

## 5. Clean-machine Gap Audit 已确认结果

Step 1 Clean-machine Gap Audit 已完成。

关键结论：

1. Fresh Clone 没有 Bootstrap。
2. Fresh Clone 没有可双击 `.command` 构建入口。
3. Python 环境不可复现：当前没有正式依赖锁，也不能依赖旧 venv。
4. 旧机器 `venv/bin/pip` 因仓库移动保留旧 shebang，证明 venv 不应被迁移复用。
5. Fresh Clone 没有 `external/whisper.cpp`。
6. Fresh Clone 没有 `whisper-cli` 和 whisper/ggml dylib。
7. 当前 release build 对缺少 `whisper-cli` 只 Warning 后继续。
8. PyInstaller Spec 对 CLI/dylib 使用 optional `existing_resource()`，会静默略过缺失 Runtime。
9. 因此当前可能生成能启动、能下载模型、但不能转录的残缺 App。
10. 当前没有 post-build CLI / dylib / architecture smoke test。
11. 模型下载尚无 `.part`、原子 rename、checksum、可靠失败清理和安全重试。
12. 当前正式构建结果仍受构建机 Python、PyInstaller、PySide6 和本地 whisper.cpp 状态影响。

---

## 6. 旧机器与新机器职责

### 6.1 旧机器：开发 / 回归机器

本地仓库路径：

```text
/Users/smter-mac/Documents/personalAPPS/whisper
```

旧机器已有历史环境、`external/whisper.cpp`、Runtime 和模型，可用于：

```text
开发
单元测试
构建验证
稳定 ASR 回归
Commit / Push
```

但旧机器成功不能证明 Fresh Clone 可复现，因为它存在历史隐式依赖。

### 6.2 新机器：Clean-machine 验收机器

新机器用于验证正式交付流程。

原则：

```text
不手工复制 external/
不手工编译 whisper-cli
不手工复制模型
不采用实验性本地 UI 修改
不通过临时命令修补正式流程
```

正式验收只能通过：

```text
干净 main
-> 正式构建入口
-> App
-> 模型下载
-> 实际转录
```

任何必须人工补做的命令，都应视为新的 deployment bug。

---

## 7. Runtime 组成

最终 `.app` 的转写 Runtime 至少需要：

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

模型文件不打入 App，由 Model Manager 管理。

`external/whisper.cpp` 的定位：

```text
本地、可重建的第三方源码 + 构建目录
继续被主仓库 Git 忽略
不得作为 Fresh Clone 隐式前提
```

后续 Bootstrap 必须能够从固定上游版本重建正式 Runtime。

当前旧机器观察到的 whisper.cpp Commit：

```text
8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae
```

该值目前是已验证旧机器观察值；在 Runtime Manifest 正式冻结前，不应把所有旧机器 CMake 状态自动提升为永久合同。

---

## 8. 构建安全合同

最终正式构建必须满足：

```text
缺 Python 环境 -> fail
缺关键 Python package -> fail
缺 whisper-cli -> fail
缺必需 dylib -> fail
错误架构 -> fail
RPath / dylib closure 不完整 -> fail
模型下载脚本缺失 -> fail
post-build Runtime smoke 失败 -> fail
```

不得继续使用：

```text
Warning 后生成残缺 App
静默跳过关键 Runtime
Build complete 但无法实际转录
```

签名 / notarization 与 Runtime 完整性属于不同层级；即使暂时只有 ad-hoc signing，也不能降低 Runtime 完整性门禁。

---

## 9. Python 环境原则

旧 venv 不是交付物，也不是可复现环境。

长期原则：

```text
不保存 venv 本体
保存重建 venv 所需的版本合同 + lock + bootstrap
```

当前只冻结：

```text
Python >= 3.11
```

以下内容仍待后续步骤验证后确定：

```text
Python minor / patch
PySide6 version
PyInstaller version
numpy version
sounddevice version
依赖锁格式
uv / venv / 其他 bootstrap 方案
```

不要根据旧机器当前偶然安装版本直接锁定正式环境。

---

## 10. 当前唯一 ACTIVE Step

```text
ACTIVE: Deployment Step 2 - 冻结部署合同与 Runtime Manifest
```

目标：

- 将支持平台、Python 状态、whisper.cpp 上游、Runtime 文件和 pending decisions 形成稳定合同；
- 创建机器可读 Runtime Manifest；
- 明确哪些值已经冻结、哪些只是旧机器观察值；
- 不改变当前应用运行行为。

本 Step 不做：

```text
Python 环境重建
依赖安装
Whisper Bootstrap
whisper.cpp 编译
PyInstaller 构建
模型下载加固
UI 新功能
ASR 主链路修改
LLM 开发
```

---

## 11. 后续 Deployment Steps

当前规划：

```text
Step 1：Clean-machine Gap Audit                  已完成
Step 2：部署合同与 Runtime Manifest             ACTIVE
Step 3：建立可重建的 Python 环境                待做
Step 4：Whisper Runtime Bootstrap                待做
Step 5：可双击的一键构建入口                     待做
Step 6：严格打包门禁与 post-build smoke          待做
Step 7：模型下载完整性、失败恢复与重试            待做
Step 8：新机器 Clone -> App -> 转录端到端验收      待做
Step 9：普通用户 GitHub Release ZIP 验收           待做
```

Step 9 普通用户目标：

```text
GitHub Release ZIP
-> 解压 ClassroomTranscriber.app
-> 双击启动
-> 下载模型
-> Start
-> 正常转录
```

普通用户不应接触 Git、Python、CMake、Shell 或 `external/whisper.cpp`。

---

## 12. 当前 Pending Decisions

仍需后续验证后冻结：

1. 正式 Python minor / patch；
2. PySide6 / PyInstaller / numpy / sounddevice 版本；
3. Python 依赖锁工具和格式；
4. 最低支持 macOS；
5. `GGML_NATIVE` 是否适合可分发 Runtime；
6. CMake 获取方式；
7. whisper.cpp 正式 Bootstrap CMake 参数；
8. Runtime dylib 使用固定文件名还是依赖闭包发现；
9. post-build smoke test 的最小命令；
10. 模型 checksum / size manifest 来源和维护策略；
11. Developer ID signing / notarization 的实施时间点；
12. GitHub Release ZIP 的版本与发布流程。

Pending decision 不得通过猜测自动转成稳定合同。

---

## 13. 工作规则

本工作线每个明确 Step：

```text
先确认当前 main / 工作区
-> 实现一个范围明确的 Step
-> 自动测试 / 静态检查
-> Commit
-> Push main
-> 审查
-> 更新本文件 ACTIVE 状态
```

除非用户明确要求：

- 不创建新 branch；
- 不修改 `llm-sidecar-phase1`；
- 不 merge LLM 分支；
- 不 force push；
- 不顺带做新功能。

如果发现当前分支不是 `main`，或工作区有未说明修改，应停止并报告。

---

## 14. 上下文恢复入口

如果项目再次停滞，恢复 deployment 工作线时按顺序读取：

```text
1. docs/deployment_workstream.md
2. README.md
3. docs/工程细节.md
4. packaging/ 和 scripts/ 中与当前 ACTIVE Step 相关文件
```

如果恢复 LLM 功能线，则切换到 `llm-sidecar-phase1`，读取：

```text
docs/whisper_static.md
docs/whisper_runtime.md
```

不要用 LLM runtime 的 ACTIVE Step 推断 main deployment 工作线状态，反之亦然。
