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
- 独立的 Original Language 设置，支持英语、中文、日语、法语、西班牙语、德语、韩语和自动检测音频
- Beam 范围为 3–8，默认值为 5
- 持久保存模型、Beam、界面语言、模型位置和输出位置设置
- 按时间戳保存完整 Session evidence 文件
- 正式打包版包含自定义 macOS App 图标

## 下载

当前正式版本为 **1.0.0**：

- [Classroom Transcriber 1.0.0 GitHub Release](https://github.com/smter6626/live_subtitle_generator/releases/tag/1.0.0)
- 正式 asset：`ClassroomTranscriber-1.0.0-macOS-AppleSilicon.zip`

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
8. 选择**界面语言（Interface Language）**：`中文` 或 `English`。
9. 选择**音频原始语言（Audio / Original Language）**：英语、中文、日语、法语、西班牙语、德语、韩语或自动检测。
10. 一般情况下保持 **Beam** 默认值 `5` 即可。
11. 如有需要，使用**选择输出位置（Choose Output Location）**设置未来 Session 的保存位置。
12. 点击**开始录音（Start Recording）**。第一个音频 chunk 处理完成后，Clean Transcript 会开始更新。
13. 课堂或录音结束时，点击**停止录音（Stop Recording）**。App 会停止继续采集，并完成已经提交处理的音频。
14. 点击**打开输出目录（Open Output Folder）**查看本次 Session 文件。

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
├── clean.txt
├── session.log
└── config.json
```

- `raw.txt`——后端产生的原始 timestamp transcript evidence
- `clean.txt`——经过保守边界去重和少量过滤后的可读版本
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

## 已知限制

- 1.0.0 下载 asset 仅面向 macOS Apple Silicon，没有 Intel Mac 或 Windows Release。
- Release 验收已在 Apple M4 Max 和 Apple M5 的 macOS 27 Beta 环境完成。其他 Apple Silicon 代际和更早 macOS 版本未经过项目实机验证，最低 macOS 版本尚未定义。
- 当前 Release 使用 ad-hoc signing，未进行 Developer ID notarization，因此 Gatekeeper 首次启动时可能要求“仍要打开”。
- 当前 inference 按重叠音频 chunk 调用 `whisper.cpp` CLI。转写属于近实时，不是零延迟，也不提供固定延迟保证。
- Release 1.0.0 没有 LLM summary、云端翻译 sidecar、语义纠错或结构化课堂笔记。
- 自动检测使用自动语言识别，效果取决于模型和音频。
- Clean Transcript 只执行保守去重和有限的高置信过滤，不是语义改写。

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

Release packaging 详见 [`PACKAGING.md`](PACKAGING.md)。简化流程是在 clean formal build 后执行：

```bash
.venv/bin/python scripts/build_release_zip.py --version <version>
```

本节只是快速入口，不能代替 packaging 和 deployment contracts。

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
- [`docs/repo_map.md`](docs/repo_map.md)——仓库 ownership、architecture 和 change-navigation map

Runtime/history 文档是工程证据；普通用户安装和使用 App 时不需要阅读。
