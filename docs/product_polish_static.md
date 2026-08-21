# product_polish_static.md

最后更新：2026-08-20  
文档角色：`main` 分支 Product / UX polish 稳定合同（static contract）

本文件记录 Classroom Live Transcriber 在完成 Deployment Step 9 / Release 0.2.0 后，针对已确认使用体验问题开展的小范围 Product / UX polish 的长期目标、不可破坏边界与验收原则。

动态执行状态见：`docs/product_polish_runtime.md`。

Deployment 历史与发布合同继续由 `docs/deployment_static.md` / `docs/deployment_runtime.md` 维护；LLM sidecar 继续由 `llm-sidecar-phase1` 的 `docs/whisper_static.md` / `docs/whisper_runtime.md` 维护。三条工作线不得混用 ACTIVE step。

---

## 1. Product / UX polish 总目标

当前 Product / UX polish 只处理已经在实际使用中确认、但不阻塞 Release 0.2.0 的体验问题，以及进入下一轮产品化前已经明确需要补齐的 UI / packaging polish。

目标不是重构 ASR，而是在保持现有转写正确性、稳定性、evidence layer 与 Model integrity 合同不变的前提下，提高普通用户日常使用时的信息可读性、操作反馈、输出位置可控性、双语一致性与 App 完整度。

当前冻结的六个产品目标如下。

### 1.1 Current-model panel readability

主窗口与 Model Manager 的“当前模型”摘要应优先让用户看到：

```text
模型名
模型大小
available / integrity 状态
```

长 absolute path 不应持续占满主摘要区域。

完整模型路径仍必须可访问，例如通过 tooltip、可复制 detail 或等价方式；Model Manager 表格中的 Path 信息不得丢失。

### 1.2 Model selection transient confirmation

用户实际成功选择模型后，应得到一个短时、明确、non-modal 的成功反馈，目标持续约 2 秒。

该反馈必须：

```text
不阻塞 UI 主线程
自动消失
只在真实 successful selection 后出现
refresh / scan 不伪装成用户选择成功
失败或 unavailable selection 不显示 success
中英文继续使用现有 UI translation 机制
```

### 1.3 Model download visible progress / busy feedback

模型下载期间必须持续显示“仍在工作”的可见反馈，避免 large-v3 等大模型下载时用户误判为卡死。

最低产品合同：

```text
visible busy / indeterminate progress indicator
+ 当前 model name
+ 明确 downloading 状态
```

如果现有 downloader 能稳定提供、且无需耦合脆弱 upstream 文本格式的 byte progress，可以进一步显示 bytes / percent；否则不为精确百分比引入脆弱解析。

优先级固定为：

```text
用户明确知道下载仍在进行
> 精确百分比
```

### 1.4 Configurable output root

普通用户可以配置 ClassroomTranscriber 的 output base/root。

默认 base/root 保持：

```text
~/Documents/ClassroomTranscriber
```

用户选择其他 root 后，新 session 仍必须保持现有 evidence 子结构：

```text
<chosen-root>/outputs/<timestamp>/raw.txt
<chosen-root>/outputs/<timestamp>/clean.txt
<chosen-root>/outputs/<timestamp>/session.log
<chosen-root>/outputs/<timestamp>/config.json
```

不得改成 `<chosen-root>/<timestamp>/...`。

新的 root 必须持久化，只影响之后创建的新 session；不得移动、重命名、修改历史 session。失效或不可写 root 必须在 Start 前明确失败，不得静默 fallback 到未知目录，也不得先创建半个 session 再切换路径。

### 1.5 中文 / English UI switch 与语义对齐

当前项目已经存在中文 / English 文案基础，但普通用户需要一个明确的 UI language 切换入口；同时两套 UI 文案、状态、按钮、错误提示与功能名称需要做一次系统性的 semantic alignment。

目标不是机械逐字翻译，而是保证同一功能在两种 UI 下表达同一产品语义、操作结果和状态含义。

至少应满足：

```text
用户可以从 UI 明确选择中文或 English
两种 UI 的主要按钮、状态、Model Manager、session 信息和错误提示语义对应
不因翻译遗漏而出现明显的无意中英混杂
允许保留必要且一致的技术术语，例如 Beam / Raw / Clean / Model 等
切换语言不得改变 ASR language / Original Language 的业务含义
```

“UI language”和“被转录音频的 Original Language / whisper language”必须在产品语义上明确区分，不能因为加入 UI language switch 而混为同一个设置。

具体采用即时切换还是其他最小可靠交互、是否需要额外 persistence 细节，由该 Step 开始时结合当前 UI 架构确认；static 不预先指定具体 widget / function 实现。

### 1.6 Packaged App icon

最终 packaged `ClassroomTranscriber.app` 应具有明确的自定义 App icon，避免继续使用默认 / 无图标状态，提高 Finder / Dock / Release artifact 的产品完整度。

当前**不冻结图标视觉方案**。图标设计、源 asset、尺寸/格式与最终视觉选择在对应 Step 开始时再确认，不提前生成或锁死。

长期验收原则：

```text
正式 build 使用确定后的项目图标
Finder / Dock 中 packaged App 能显示该图标
图标 asset 进入正式可重建 packaging 路径
不依赖某台开发机的外部绝对路径
Release ZIP round-trip 后图标仍存在
```

---

## 2. 稳定 ASR 主链路不可破坏

Product / UX polish 默认禁止修改：

```text
audio capture
ring buffer
10s chunk / 3s overlap scheduling
48kHz -> 16kHz resample
WhisperCppBackend inference semantics
simple_dedup()
fuzzy_boundary_dedup()
TranscriptStore raw / clean append semantics
Stop / microphone release 主逻辑
```

如果某个 Product / UX 目标被证明必须修改这些区域才能实现，应停止当前 Step 并重新评估 scope；不得以“UI polish”为理由顺带重构稳定 ASR 主链路。

---

## 3. Evidence layer 合同保持不变

每个 session 的基础 evidence layer 仍为：

```text
raw.txt
clean.txt
session.log
config.json
```

Product / UX polish 不得：

```text
删除
重命名
覆盖历史文件
改变 raw / clean 内容语义
把 UX state 混写进 raw / clean
```

Configurable output root 只能改变这些文件所在的 session 根位置，不改变 session 子目录与文件合同。

---

## 4. Model integrity 合同保持不变

下载可见性改进不得弱化 Step 7 已冻结的事务：

```text
background worker
hidden staging directory
exact size validation
SHA-256 validation
atomic publish
integrity receipt
only verified model becomes available / selectable
```

网络下载和 SHA-256 计算继续不得进入 Qt 主线程。

UI 可以显示 downloading / verifying / complete / failed 等用户状态，但不得在 cryptographic validation 完成前将模型显示为 available，也不得因为 progress UI 绕过 fail-closed 行为。

---

## 5. Settings / UI 实现原则

Product / UX polish 优先采用现有 PySide6 / settings / controller 架构内的最小改动。

允许按实际需要修改：

```text
ui_app.py
model_manager.py
settings.py
resource_paths.py
transcription_controller.py
packaging 配置与图标资源（仅 App icon Step）
与目标直接相关的 tests / docs
```

`transcript_store.py` 默认只作为 evidence contract 参考；除非有明确、可审核的必要性，不应为了 output-root UI 改写其 raw / clean / log / config 行为。

禁止借机进行：

```text
UI framework replacement
Model Manager rewrite
controller architecture rewrite
persistent whisper backend
session browser
LLM sidecar integration
ASR backend replacement
```

### 5.1 Codex prompt / 实现分工原则

Product / UX polish 的 Codex prompt 默认遵循：

```text
static + runtime = 当前方向、边界、已知事实、验收的最权威上下文
ChatGPT / 人工负责方向、scope、不可破坏合同与验收标准
Codex 负责读取当前代码上下文并选择最小正确实现
```

因此 prompt 不应重复大篇幅 background，也不应在没有合同必要性的情况下指定具体 class / function / widget 或实现细节。只有当某个代码细节本身已经是冻结合同或明确风险边界时，才在 prompt 中写死。

Apple M4 Max 与 Apple M5 已完成当前项目实际运行验证；后续普通 Product / UX 开发把两台机器视为等价开发机。除非某个验收本身具有 hardware-specific 目的，否则 prompt 不强调当前在哪台机器，也不硬编码某台机器的开发路径；运行目录使用“当前已同步的项目 clone 根目录”这一实际上下文。

---

## 6. Output-root 语义边界

当前 `TranscriptStore` 的语义是接收实际 outputs directory，并在其下创建 timestamp session directory。

因此 Product / UX 层配置的是 base/root：

```text
<base>
```

传入稳定 session 创建链路的目标仍应等价于：

```text
<base>/outputs
```

旧 settings 若不存在新增 output-root 字段，必须向后兼容默认：

```text
~/Documents/ClassroomTranscriber
```

历史 session 不迁移。

---

## 7. Product polish 完成验收原则

每个小 Step 需要针对自身行为增加或更新最小 contract tests，并保持相关既有 regression tests PASS。

整轮 Product / UX polish 收口时必须重新验证 packaged App，而不是只验证 source-run UI。最终 packaged acceptance 至少覆盖：

```text
formal one-entry build
packaged Runtime verifier
current-model long-path readability
model scan / selection
selection transient confirmation
fresh small model download + visible busy feedback
model integrity transaction
custom output root persistence
中文 / English UI switch 与关键语义对齐
UI language 与 Original Language 语义区分
最终确定的 packaged App icon
Start -> real transcription -> Stop
Stop -> second Start
raw.txt / clean.txt / session.log / config.json
repo worktree clean
```

最终 packaged regression 可在任一当前已验证的 Apple Silicon 开发机完成。若实际实现始终只触及 UI / settings / packaging polish 层且 packaged regression 正常，不默认要求重新跑此前约 35 分钟课堂压力测试；若任何 Step 触碰 Runtime / ASR 边界，则必须升级验收并由人工决定是否继续。

---

## 8. 当前明确不属于 Product / UX polish 目标

以下内容不因为本工作线启动而自动进入范围：

```text
M4 长课堂偶发单次 inference latency spike 的优化
Developer ID signing
notarization
DMG
GitHub Actions release automation
minimum macOS 冻结
M1 / M2 / M3 实机验证
LLM sidecar
session browser
persistent whisper backend
ASR chunk / backend 重构
```

此前记录的“M4 Max 再重复一次 fresh Model Manager download”已经在 0.2.0 Release App 上通过“自选模型目录 -> 下载 base.en -> 实际转录成功”完成，不再是 open observation，也不进入 Product / UX scope。

剩余的偶发 latency spike 继续作为 non-blocking observation；只有出现可重复失败证据时才另行立项。

---

## 9. 分支 / Release 边界

当前 Product / UX polish 在 `main` 上推进，不为每个小 Step 新建 branch；每个明确 Step 一个 commit。

本工作线默认不创建新的 Git tag / GitHub Release。完成 packaged acceptance 后，再由用户决定是否发布后续版本，以及版本号与 release scope。
