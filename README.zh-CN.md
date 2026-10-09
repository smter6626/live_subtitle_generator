# Classroom Live Transcriber

[English](README.md) | 简体中文

Classroom Live Transcriber 是一款面向 macOS Apple Silicon 的本地、近实时课堂转写应用。它使用带 Metal 加速的 `whisper.cpp`，麦克风转写在 Mac 本机完成。

```text
麦克风 -> 本地 Whisper 转写 -> 实时转写界面 -> Session 文件
```

当前转写链路不依赖云端 LLM。Release 1.0.0 不包含 LLM 总结、翻译 sidecar、语义改写或笔记服务。

## 功能

- 在 PySide6 桌面界面中开始和停止课堂转写
- 使用 Metal backend 进行本地 `whisper.cpp` inference
- Clean Transcript 和 Raw Transcript 两种视图
- Model Manager 支持模型下载、导入、选择和下载位置设置
- 对官方模型下载执行精确文件大小和 SHA-256 完整性验证
- 模型下载期间显示持续可见的 busy/progress 反馈
- 可配置 Output Location
- 中文和 English 两种界面语言
- 主窗口高度受当前屏幕可用范围约束，左侧控制栏可独立纵向滚动
- Session 独占的 Clean 工具栏，支持无覆盖重命名、增量文本复制、在访达中定位和复制绝对路径
- 当当前 writer 在原 Session 中确定不存在 `.txt` 路径时，可从完整历史恢复 Clean 文件
- 独立的 Original Language 设置，支持英语、中文、日语、法语、西班牙语、德语、韩语和自动检测音频
- Beam 范围为 3–8，默认值为 5
- 持久保存模型、Beam、界面语言、模型位置和输出位置设置
- 按时间戳保存完整 Session evidence 文件
- 正式打包版包含自定义 macOS App 图标

## 下载

当前正式版本为 **1.0.0**：

- [Classroom Transcriber 1.0.0 GitHub Release](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.0.0)
- 正式 asset：`ClassroomTranscriber-1.0.0-macOS-AppleSilicon.zip`

1.1.0 是 `codex/release-1-1-0-automation` 上尚未构建、尚未发布的候选版。其固定候选标题为 **Classroom Transcriber 1.1.0**，预定 asset 为 `ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip`，其中包含 `ClassroomTranscriber.app`。当前可下载的 1.0.0 App 不包含这些候选改动。过去对 1.0.0 完成的 clean-machine 验收仅是历史证据，不会验收任何新的 1.1.0 App 或 ZIP 字节。

普通用户**不需要** clone 本仓库，不需要安装 Python，也不需要自行编译 `whisper.cpp`。ZIP 不包含 Whisper 模型；打开 App 后，请通过 Model Manager 下载或导入模型。

## 系统要求

- Apple Silicon（`arm64`）Mac
- macOS；正式 Release 验收已在运行 macOS 27 Beta 的 Apple M4 Max 和 Apple M5 机器上完成
- 麦克风使用权限
- 足够容纳所选模型及其临时下载 staging 的可用磁盘空间
- 使用 Model Manager 下载模型时需要网络连接

项目尚未验证 Intel Mac、Windows、M1/M2/M3 硬件或更早的 macOS 版本，也尚未确定最低 macOS 版本。

## 快速开始

整个流程不需要 Terminal 命令。

1. 从 [1.0.0 Release](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.0.0) 下载 `ClassroomTranscriber-1.0.0-macOS-AppleSilicon.zip`。
2. 在 Finder 中双击 ZIP，解压得到 `ClassroomTranscriber.app`。
3. 打开 `ClassroomTranscriber.app`。
4. 当前 Release 未 notarize。如果 macOS 提示无法验证 App，请关闭提示，打开**系统设置 → 隐私与安全性**，选择**仍要打开（Open Anyway）**，按提示认证，然后再次打开 App。
5. macOS 请求麦克风权限时允许访问；通常会在第一次开始录音时出现此请求。
6. 点击**管理模型（Manage Models）**打开 Model Manager。
7. 使用**下载模型（Download Model）**或**导入已有模型（Import Existing Model）**。下载后等待完整性验证结束并显示 `available`；如有需要，再选择该模型。
8. 选择**语言/Language（Interface Language）**：`中文` 或 `English`。
9. 选择**音频原始语言（Audio / Original Language）**：英语、中文、日语、法语、西班牙语、德语、韩语或自动检测。
10. 一般情况下保持 **Beam** 默认值 `5` 即可。
11. 如有需要，使用**选择输出位置（Choose Output Location）**设置未来 Session 的保存位置。
12. 点击**开始录音（Start Recording）**。第一个音频 chunk 处理完成后，Clean Transcript 会开始更新。
13. 课堂或录音结束时，点击**停止录音（Stop Recording）**。App 会停止继续采集，并完成已经提交处理的音频。
14. 如果运行当前 feature branch，请使用下述 Clean 文件操作。可下载的 1.0.0 App 中还没有这些控件。

### 当前 feature branch 的 Clean 文件操作

- 左侧的**定位 Clean（Reveal Clean）**和**复制 Clean 路径（Copy Clean Path）**位于同一紧凑行。每次使用都会重新确认路径仍对应当前 Session 的 Clean writer；验证失败时，访达和剪贴板保持不变。
- **重命名 Clean TXT（Rename Clean TXT）**位于 Clean 表格工具栏左侧。只输入文件名主体，`.txt` 后缀由 App 固定管理。普通重命名不会覆盖已有目标，会保留 writer inode，并且在录制中或 Stop 后都可使用。
- 如果完整检查证明 writer 在经过验证的原 Session 中没有任何普通 `.txt` 路径，App 会询问是否用完整 Clean 历史创建指定文件。选择**是**会无覆盖地创建一个包含切换前全部 Clean 字节的文件；若仍在录制，之后的内容只追加到新文件。选择**否**或取消不会创建或切换文件。提示框会明确说明：仍可写入已打开的文件句柄，不等于关闭文件或退出 App 后仍有可持久访问的路径。
- 权限错误、检查结果不确定或 Session 目录被不安全替换时，不会被当成“文件已消失”。操作会报错停止，不提供恢复选项。
- **复制新增文本（Copy New Text）**位于**跳到最新（Jump to Live）**左侧。第一次成功使用时复制当前显示的全部 Clean 行，之后只复制上一次成功复制后新增的行。
- 开启新 Session 会清空 Clean/Raw 显示并重置增量复制断点。此后所有 Clean 文件操作都归属于新 Session，之前已停止的 Session 不再是 UI 操作对象。

如果屏幕高度不足以显示全部控件，可使用左侧控制/Session 栏的滚动条、鼠标滚轮、触控板或键盘焦点遍历继续访问。顶部状态栏保持在滚动区外；Clean Transcript、Raw Transcript 和 Logs 仍各自独立滚动。

## Model Manager

从主窗口打开**管理模型（Manage Models）**。Model Manager 提供：

- **下载模型（Download Model）**——下载 manifest 中定义的官方模型
- **导入已有模型（Import Existing Model）**——直接使用已有 `.bin` 或 `.gguf` 模型
- **选择模型（Select Model）**——将状态为 `available` 的模型设为当前模型
- **下载位置 / 选择文件夹（Download Location / Choose Folder）**——更改未来模型下载位置
- 显示名称、大小、路径和 available/integrity 状态的模型列表

默认下载位置：

```text
~/Documents/ClassroomTranscriber/models
```

官方模型会先下载到隐藏 staging 目录。只有精确文件大小和 SHA-256 完整性检查全部通过，并发布到最终路径后，模型才会显示为 `available`。下载期间会持续显示 busy indicator 和当前模型名。无效、未完成或尚未验证的官方下载模型不能作为 available 模型使用。用户明确 Import 的自定义模型使用 App 独立的本地导入检查。

以下可下载列表和精确大小来自 [`packaging/model_manifest.json`](packaging/model_manifest.json)：

| 模型 | 精确字节数 | 界面近似大小 | 选择建议 |
| --- | ---: | ---: | --- |
| `large-v3` | 3,095,033,483 | 2.9 GB | 多语言、质量优先；下载体积最大 |
| `large-v3-turbo` | 1,624,555,275 | 1.5 GB | 体积更小的多语言 large 模型变体 |
| `medium.en` | 1,533,774,781 | 1.4 GB | English-only 模型 |
| `small.en` | 487,614,201 | 465.0 MB | 更小的 English-only 模型，适合较快试用 |
| `base.en` | 147,964,211 | 141.1 MB | 最小的可下载 English-only 试用模型 |

模型质量、速度和内存占用会受到 Mac、音频、语言和模型本身影响。本项目没有为这些模型发布具体的速度或准确率百分比 benchmark。

## Interface Language 与 Original Language

这两个设置彼此独立：

- **界面语言（Interface Language）**只改变 App 的按钮、标签和提示显示为中文或 English。
- **音频原始语言（Audio / Original Language）**告诉 Whisper 麦克风音频主要使用什么语言。

界面语言的两个选项只是 App 的 UI locale；它们不会限制可选的音频原始语言。

Original Language 的八个规范选择及其 Whisper code 为：

- `English`（中文界面显示为“英语”）→ `en`
- `Chinese`（中文界面显示为“中文”）→ `zh`
- `Japanese`（中文界面显示为“日语”）→ `ja`
- `French`（中文界面显示为“法语”）→ `fr`
- `Spanish`（中文界面显示为“西班牙语”）→ `es`
- `German`（中文界面显示为“德语”）→ `de`
- `Korean`（中文界面显示为“韩语”）→ `ko`
- `Auto Detect`（中文界面显示为“自动检测”）→ `auto`（自动检测语言）

`Auto Detect` 是自动语言选择的规范名称。已有保存的 `Mixed Chinese/English`、`中英混合`、`mixed` 或 `auto` 仍然兼容，并会归一化为 `Auto Detect`。

英语专用的 `.en` 模型（例如 `medium.en`、`small.en`、`base.en`）只接受 `English`（`en`）。其他所有列出的音频原始语言选项（包括 `Auto Detect`）都需要多语言模型；不兼容的 `.en` 组合会被明确拒绝，不会回退为英语。

切换 Interface Language 不会改变 ASR Original Language、模型、Beam 或转写内容。

## Beam

Beam 控制转写时的搜索量。当前范围为 `3` 到 `8`，默认值为 `5`。

大多数用户保持默认值即可。更高的 Beam 可能增加搜索开销和处理时间，并不保证每段录音都得到更好的转写结果。

## Output Location 与 Session 文件

打包版 App 的默认输出 base 为：

```text
~/Documents/ClassroomTranscriber
```

每个 Session 都保存在 `outputs` 子目录中：

```text
<chosen-root>/outputs/<timestamp>/
├── raw.txt
├── clean.txt                 # 当前 Clean 的初始文件名
├── session.log
└── config.json
```

- `raw.txt`——后端产生的原始 timestamp transcript evidence
- `clean.txt` -- 当前 Clean transcript 的初始文件名。在 feature branch 中，重命名可将它改为用户指定的 `.txt`，同时保留已有内容和后续追加；当原 Session 路径确定不可用时，也可将完整 writer 历史无覆盖地恢复到新的 `.txt`。因此不能假设每个已完成的 feature-branch Session 都仍有一个字面名称为 `clean.txt` 的文件。
- `session.log`——Session、chunk、backend、warning、error 和 stop 事件日志
- `config.json`——本次 Session 使用的模型、语言、Beam、路径和音频配置

选择新的 Output Location 只改变未来 Session 的 base，不会移动或改写历史 Session。目录结构始终为 `<chosen-root>/outputs/<timestamp>/`，不是 `<chosen-root>/<timestamp>/`。

## 隐私与本地处理

- 麦克风转写和 `whisper.cpp` inference 在 Mac 本机运行。
- Session transcript 保存在用户选择的 Output Location 下。
- Model Manager 下载模型时会通过网络访问 upstream `ggerganov/whisper.cpp` 模型仓库。
- Release 1.0.0 不会把 transcript 发送给云端 LLM 做总结、翻译或语义改写。

以上说明针对当前 App 链路，不代表对 macOS、本机网络或电脑上其他第三方软件行为作绝对承诺。

## 故障排查

### macOS 不允许打开 App

当前 Release 未 notarize。出现无法验证的提示后，请打开**系统设置 → 隐私与安全性 → 仍要打开（Open Anyway）**，按提示认证，然后再次启动 App。已完成验证的 Release 路径不需要 Terminal workaround。

### 没有可用模型，或“开始录音”不可用

打开**管理模型（Manage Models）**，下载或导入模型，等待状态变为 `available`，然后选择该模型。显示 `integrity unverified` 或 `integrity invalid` 的官方模型不能用于 Start。

### 模型下载时间很长

大模型包含数 GB 数据。请保持 Model Manager 打开，并观察 busy indicator 和当前模型名。下载时间取决于模型和网络；当前界面显示持续活动状态，不提供估算百分比。

### 没有麦克风权限

打开**系统设置 → 隐私与安全性 → 麦克风**，允许 ClassroomTranscriber 使用麦克风，然后回到 App 再次开始。

### Output Location 不可写

App 会在创建 Session 前检查实际的 `<chosen-root>/outputs` 目录；失败时会明确报错，而不会静默切换位置。使用**选择输出位置（Choose Output Location）**选择一个可写文件夹，然后再次开始。

### 模型下载或完整性验证失败

检查网络、可用磁盘空间和当前 Download Location，然后再次点击**下载模型（Download Model）**。失败或未完成的下载会保持 unavailable；重试会重新使用受控下载事务。也可以选择另一个可写的 Download Location，或导入已有的有效模型。

### 如何找到 Session 输出

Start 创建 Session 后，点击**打开输出目录（Open Output Folder）**。主窗口也会显示当前 Session 路径。默认位置为 `~/Documents/ClassroomTranscriber/outputs/<timestamp>/`。

### 点击“定位 Clean”或“复制 Clean 路径”没有反应

在 feature branch 中，如果 Store 无法证明哪个 Session 内的 `.txt` 才是当前 writer，这两个操作会主动保持访达或剪贴板不变。请等待外部文件操作停止后重试。如果路径已经被安全地确认不存在，可通过**重命名 Clean TXT**选择是否创建全文恢复文件。

### Clean 重命名提示目标已存在

普通重命名和恢复都不会覆盖已有文件、目录、symlink 或同名 decoy。请换一个文件名主体，或在确认冲突项内容后自行移动它。

### Clean 重命名提示无法验证源文件

权限、I/O、Session 目录身份或文件类型不确定时会 fail closed。App 不会把不确定状态解释成“文件已消失”，也不会在安全确认缺失之前提供“是”的恢复路径。

## 已知限制

- 1.0.0 下载 asset 仅面向 macOS Apple Silicon，没有 Intel Mac 或 Windows Release。
- Release 验收已在 Apple M4 Max 和 Apple M5 的 macOS 27 Beta 环境完成。其他 Apple Silicon 代际和更早 macOS 版本未经过项目实机验证，最低 macOS 版本尚未定义。
- 当前 Release 使用 ad-hoc signing，未进行 Developer ID notarization，因此 Gatekeeper 首次启动时可能要求“仍要打开”。
- 当前 inference 按重叠音频 chunk 调用 `whisper.cpp` CLI。转写属于近实时，不是零延迟，也不提供固定延迟保证。
- Release 1.0.0 没有 LLM summary、云端翻译 sidecar、语义纠错或结构化课堂笔记。
- 自动检测使用自动语言识别，效果取决于模型和音频。
- Clean Transcript 只执行保守去重和有限的高置信过滤，不是语义改写。
- Feature-branch Clean 路径验证面向本 App 的 single-writer 工作流。无锁的外部程序仍可能在最后一次检查之后立刻修改 Session；App 不提供跨程序文件系统锁。

## 开发者指南

正式开发者构建从 clean clone 开始，并自动准备锁定的 Python 环境和固定版本的 `whisper.cpp` Runtime：

```bash
git clone https://github.com/smter6626/live_subtitle_generator.git
cd live_subtitle_generator
./Build\ ClassroomTranscriber.command
```

构建会生成 `dist/ClassroomTranscriber.app`，并在报告成功前运行 packaged Runtime verifier。也可以在 Finder 中双击 `.command` 入口。

正式 bootstrap 准备好 `.venv` 后，可运行源码 UI：

```bash
.venv/bin/python ui_app.py
```

运行 unit/contract tests：

```bash
.venv/bin/python -m unittest discover -s testCodes -p 'test_*.py' -v
```

Release packaging 详见 [`PACKAGING.md`](PACKAGING.md)。REL1A ZIP 入口要求固定 1.1.0 identity、与 clean HEAD 一致的预期 source commit、本 clone 的 canonical App/provenance/Runtime Manifest，以及同一个 Downloads task-managed root 下显式指定的 artifact 和保留供人工检查的解压路径：

```bash
mkdir -p "$HOME/Downloads/classroom-transcriber-release/artifacts"
.venv/bin/python scripts/build_release_zip.py \
  --version 1.1.0 \
  --expected-source-commit "$(git rev-parse HEAD)" \
  --task-root "$HOME/Downloads/classroom-transcriber-release" \
  --artifact "$HOME/Downloads/classroom-transcriber-release/artifacts/ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip" \
  --human-review-extraction "$HOME/Downloads/classroom-transcriber-release/human-review"
```

本节只是快速入口，不能代替 packaging 和 deployment contracts。

### 当前轻量发布流程

当前 Owner 授权使用 [`scripts/release_lightweight.py`](scripts/release_lightweight.py)，
不部署下文保留兼容的 protected/signature 入口。批准来自真实 Reviewer/Human
对话 reference，普通本地记录固定输入，Git/gh 使用本机既有原生登录:

```bash
.venv/bin/python -B scripts/release_lightweight.py \
  --approval /absolute/Downloads/task/decisions/approval.json status
```

命令为 `status|integrate|prepare|resume|human-gate|publish`。主 Reviewer 复核后
提供对应记录；Executor 不能制造人工 PASS。`prepare` 复用原真实分叉集成和
完整 strict gate，停在精确最终 main 审核；得到记录后再次调用，复用原 fresh
六 checkpoint 构建及 ZIP 验证，再停在该精确保留 App/ZIP 的人工测试。
`publish` 同时要求 PASS 和明确的 `publish_allowed: true`。缺决定、FAIL、换包
或 App 字节改变都会在 tag/draft/upload 前停止；重建必须重新人工测试。
字段及制作示例见 [`PACKAGING.md`](PACKAGING.md#current-lightweight-release-workflow)。

不需要 root entry、签署私钥、专属 group、凭据复制或新认证桥。角色权限由
prompt 分工约束，hash 只绑定事实，不保证同 UID 恶意写入者不能伪造批准。
固定仓库/source/ZIP、no-force/no-clobber 和真实远端/下载对账继续生效。
详细日志/元数据只留本地，终端显示简短阶段或固定 STOP code。新实现仍待独立
审核，不声称已经存在正式 1.1.0 包。

下列 REL1B/C1/C2 段落是旧入口兼容说明，不是当前部署待办。轻量入口明确替代
旧 root/signature gate；旧入口本身的拒绝规则没有被静默取消。

### REL1B 集成控制器

REL1A 的版本、App/ZIP 身份基础层及 REL1B 集成控制器均已在各自有界实现范围内独立接受。
[`scripts/release_controller.py`](scripts/release_controller.py) 提供 `status`、
`integrate` 和 `resume`。整个 Step 1、真实 main 集成、新的
App/ZIP 和发布均未完成。控制器尚不提供 build、package、Human-pass、tag、
draft、upload 或 publish。

生产入口要求固定外部 trust root 中的独立批准及受保护入口；本轮**未部署**。
当前运行仓库入口会以 `TRUST_UNAVAILABLE` 停止，不提供 signer、approval、
fixture 或 trust-root CLI override。唯一位置参数接口是
`release_controller.py status|integrate|resume`。`status` 只读本地提示，不 fetch、
修复或启动测试；记录的状态不证明完成。

gate 使用集成 clone 自身的原 pinned bootstrap 和完整 strict suite。任何既有
ignored 环境都会在执行前被拒绝，随后 interpreter、uv、环境代码或源码被替换
也会停止。resume 不从 journal 恢复环境证明。停止后保留 evidence 交审核；若 main
已包含 merge，但缺少可信本地完成证明，返回 `MAIN_PRESENT_HUMAN_RECONCILIATION`，
不 rollback、不重复 push。Disposable fixture 签名和 callback gate 只授权新建的
本地测试仓库。部署待决方案、transport 限制、恢复及验证命令见
[`PACKAGING.md`](PACKAGING.md#rel1b-approval-integration-and-recovery)。

### REL1C1 workflow 候选

workflow 入口接受 `status|build|resume|human-gate|prepare|pipeline-status|pipeline-resume|publish`。
独立签署的 workflow 批准必须绑定全部控制模块及实际加载的包装 helper/dependency closure、完整构建工具集、父/REL1B/REL1C
合同及最终 Step 1 审核和 Owner 集成决定。REL1B 原入口继续使用原四模块范围。
生产 trust 和 protected entry 尚未部署；仓库入口缺少它们时停止，不提供 caller-selected
trust、receipt、source、signer 或 fixture 参数。

`status` 只读记录，不接受决定、不创建或修复文件。`build` 验证独立签署的精确最终 main
source receipt、真实 Git 对象/parents/tree/源码字节及精确远端 refs。它先持久化 intent，
创建全新 attempt/clone，再调用原 `bootstrap_and_build.sh`。Python 获取、Runtime
获取/构建、App 生成的前后各有 inherited-pipe checkpoint；每次重核批准、source/tools
和已获取的解释器/import 输入字节，只允许已审核阶段的输出路径新增。
成功执行后实际调用原 Runtime verifier、canonical App provenance 和 ZIP helper，
保留精确包和 Human 目录。本次实施未正式构建或发布；C1 已独立接受，C2/C3、生产部署、
整个 Step 1 验收及真实产物人工验收仍未完成。`resume` 验证幸存产物事实，或把未知
build/package outcome 标为待审核，不重跑。后续明确调用 `build` 使用新的唯一路径，
保留历史 attempt，不从记录恢复环境信任。

`human-gate` 验证独立外部签署的 Owner PASS，绑定精确 ZIP、source、attempt、App
身份/tree 及保留解压目录。每次 artifact/Human consultation 都直接比对 ZIP member
和保留 App 的 bytes、modes、结构及 symlink targets，分别重算 hash 不足以通过。workflow 不能制造或签署 PASS；记录状态和集成许可不能代替
receipt。PASS 本身不启用发布，还须独立 publication plan 和已批准 transport。新 workflow 状态及
artifact 使用独立于 REL1B journal 的目录；新 attempt 保留旧 ZIP、Human 目录和失败证据。

未来人工验收必须在 Finder 打开该精确保留目录中的 `ClassroomTranscriber.app`，验证
模型下载、麦克风/Start/Stop、第二个 Session、语言选择、增量复制、窗口/滚动、中英
Clean 控件、录制中/停止后重命名及全文恢复 Yes/No。该 App 使用 ad-hoc、未公证；
如被 macOS 阻止，通过“隐私与安全性 → 仍要打开”。记录实际硬件、语言及模型限制；
1.0.0 历史验收不能批准 1.1.0。receipt 协议及分阶段构建边界详见
[`PACKAGING.md`](PACKAGING.md#rel1c1-candidate-receipts-and-recovery)。

### C2/C3 发布与统一流程候选

候选实现增加固定 GitHub adapter，以及调用原集成/构建/Human 控制器的路由层，
仍待独立审核，不代表真实 main 已集成、新 App/ZIP 已构建或 Release 已接受。
生产 protected entry 和认证 transport 尚未部署，当前仓库 CLI 会安全停止。
未来部署后的固定入口为:

```text
release_workflow.py prepare
release_workflow.py pipeline-status
release_workflow.py pipeline-resume
release_workflow.py human-gate
release_workflow.py publish
```

`prepare` 先调用原集成控制器，停在独立 final-main receipt 门禁；获得该精确外部
批准后再次调用，才进入原 fresh build/package 链，最终停在精确产物人工验收。
已有 artifact 只核验、不覆盖。`pipeline-status` 只读本地提示，不证明完成。
任何命令都不会签署决定或替 Human 写 PASS。
`pipeline-resume` 只恢复已有阶段，不启动缺失的任务，也不自动重建未知 build。
独立 source/Human/远端 reconciliation 门禁仍须通过；原 `resume` 保留 C1 的精确语义。

`publish` 每阶段重核精确 ZIP 的签名 PASS、source/tools 和独立 publication plan，
依次处理确定性 annotated `1.1.0` tag、固定 draft/title/notes、唯一 ZIP，先核 draft
实际下载 bytes，再转正式/latest，最后复核公开 metadata 与下载 bytes。
没有 force、clobber 或删除历史对象。结果未知时停机；跨 invocation 的 release/asset
归属必须有独立签署、绑定精确 ID 的 reconciliation，不能凭同名、相同字段或 journal
checksum 捡回对象。保留证据，不手工改状态来跳 gate。准确协议及仍需 Owner 决定的
生产部署/认证事项见 [`PACKAGING.md`](PACKAGING.md#c2c3-publication-pipeline-and-production-gates)。

## 架构

```text
PySide6 UI
-> TranscriptionController
-> TranscriptionEngine
-> WhisperCppBackend
-> TranscriptStore

Model Manager
-> integrity-gated model management
```

ASR 链路采集麦克风音频，生成重叠 chunk，重采样后调用本地 Metal-enabled backend，并写入 raw 和经过保守清理的 transcript evidence。

## 文档索引

- [`README.md`](README.md)——英文主用户指南和 GitHub 默认主页
- [`README.zh-CN.md`](README.zh-CN.md)——完整简体中文用户指南
- [`PACKAGING.md`](PACKAGING.md)——开发者 build、packaging、runtime 和 Release ZIP 合同
- [`docs/deployment_static.md`](docs/deployment_static.md)——稳定 deployment 与 platform 边界
- [`docs/deployment_runtime.md`](docs/deployment_runtime.md)——deployment 和 Release 验收历史
- [`docs/product_polish_static.md`](docs/product_polish_static.md)——稳定 Product/UX 边界
- [`docs/product_polish_runtime.md`](docs/product_polish_runtime.md)——Product/UX 完成证据和 1.0.0 Release 记录
- [`docs/streaming_backend_upgrade/README.md`](docs/streaming_backend_upgrade/README.md)——分支范围内的 streaming backend 治理和调研归档，并非 `main` 已实施的声明
- [`docs/repo_map.md`](docs/repo_map.md)——仓库 ownership、architecture 和 change-navigation map

Runtime/history 文档是工程证据；普通用户安装和使用 App 时不需要阅读。
