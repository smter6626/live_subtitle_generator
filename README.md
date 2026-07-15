# Classroom Live Transcriber

github address: https://github.com/smter6626/live_subtitle_generator

## 中文版

### 1. 项目简介

Classroom Live Transcriber 是一个本地课堂实时转写工具，主要面向 macOS Apple Silicon。它把麦克风音频实时切成带重叠的短片段，使用 `whisper.cpp` + Metal 转写，并在界面中持续显示课堂文本。

项目目标是提供“有一定延迟但课堂中可查看”的本地转写系统。它不是云服务，也不是 LLM 笔记工具；当前不会做总结、语义改写或自动课堂笔记整理。

### 2. 当前状态

当前主力路线：

- UI：PySide6 / Qt for Python，入口为 `ui_app.py`
- 后端：`whisper.cpp` CLI
- 加速：Apple Silicon Metal
- 推荐模型：`large-v3`
- 输出：每次录音生成独立 session，包含 `raw.txt`、`clean.txt`、`session.log`、`config.json`
- 模型管理：UI 内可检测、选择、导入和下载 ggml/gguf 模型
- 打包：已有 macOS Apple Silicon PyInstaller 开发版 `.app` 打包脚本

旧的 `stream_transcribe.py` 命令行入口和 `faster-whisper` fallback 仍保留，用于回滚和对比；普通 UI 不暴露 `turbo` 或 `faster-whisper` 选项。

### 3. 核心功能

- Start / Stop 实时录音转写
- Stop 后会停止继续采集，并尽量处理停止前已经录入的最后片段
- Clean / Raw 两种转写视图
- Timeline 和正文分列显示
- Logs tab 显示运行事件
- Beam Size 可选 `3-8`，默认 `5`
- Original Language 可选：
  - `English` -> `-l en`
  - `Chinese` -> `-l zh`
  - `Mixed Chinese/English` -> `-l auto`
- 固定为 transcribe，不启用 translate：不会传 `-tr` 或 `--translate`
- Model Manager 支持本地扫描、导入已有模型、下载模型、选择模型
- Clean 层有保守的边界去重和少量字幕模板幻觉过滤

### 4. 系统要求

推荐环境：

- macOS Apple Silicon
- Python 3.11 或更高版本
- 可用麦克风权限
- `whisper.cpp` Metal 构建，或使用打包版内置的 `whisper-cli`
- 至少一个 Whisper ggml/gguf 模型文件

如果使用打包版，用户不需要自己编译 `whisper.cpp`；app 内置 `whisper-cli` 和相关动态库，但不内置大模型。

源码模式要真正进行转写，仍需在 `external/whisper.cpp` 准备 Metal 构建的
`build/bin/whisper-cli`。该目录是被 Git 忽略的本地源码和构建依赖，不随仓库 Clone。

### 5. 安装依赖

源码模式需要 Python 依赖。当前项目没有强制的 `requirements.txt`，最少需要：

```bash
cd /path/to/whisper
python -m venv venv
source venv/bin/activate
python -m pip install PySide6 numpy sounddevice
```

如果要重新打包：

```bash
python -m pip install pyinstaller
```

如果要使用旧的 `faster-whisper` fallback，需要另外安装 `faster-whisper`，但这不是当前 UI 主路径。

### 6. 启动 UI

源码模式：

```bash
cd /path/to/whisper
source venv/bin/activate
python ui_app.py
```

打包版：

```bash
open dist/ClassroomTranscriber.app
```

如果从别人那里收到 zip，先解压 `ClassroomTranscriber.zip`，再右键 Open 或双击打开。开发版没有 notarization，macOS 可能要求右键 Open。

### 7. 模型管理

点击左侧 `Manage Models` 打开模型管理器。

支持的操作：

- 自动扫描本地模型
- 从列表中选择当前模型
- `Import Existing Model`：使用已有 `.bin` / `.gguf` 模型文件，不默认复制大文件
- `Download Model`：下载 `large-v3`、`large-v3-turbo`、`medium.en`、`small.en`、`base.en`
- `Choose Folder`：选择模型下载目录

默认下载目录：

```text
~/Documents/ClassroomTranscriber/models
```

模型下载脚本作为版本锁定的第三方资源随主项目保存在
`vendor/whisper.cpp/download-ggml-model.sh`。因此全新 Clone 中 UI 的模型下载功能不再依赖
`external/whisper.cpp`。下载模型只会准备模型文件；它不代表源码模式所需的
`whisper-cli` 后端已经安装或构建。

当前扫描目录包括：

```text
当前 Download Location
~/Documents/ClassroomTranscriber/models
~/Library/Application Support/ClassroomTranscriber/models
项目目录 models/
external/whisper.cpp/models/
```

模型文件和下载目录会写入 settings。源码模式默认 settings 在 `config/settings.json`；打包版在：

```text
~/Library/Application Support/ClassroomTranscriber/config/settings.json
```

### 8. 使用流程

1. 启动 UI。
2. 打开 `Manage Models`，下载、导入或选择一个模型。
3. 选择 Beam Size，默认 `5`。
4. 选择 Original Language。
5. 点击 `Start Recording`。
6. 如 macOS 请求麦克风权限，允许。
7. 等待第一个 chunk 完成后查看 Clean Transcript。
8. 需要排查时查看 Raw Transcript 和 Logs。
9. 点击 `Stop Recording`。Stop 会释放麦克风并等待队列中已提交音频处理完成。
10. 点击 `Open Output Folder` 查看本次 session。

### 9. 输出文件说明

源码模式默认输出到项目内：

```text
outputs/YYYY-MM-DD_HH-MM-SS/
```

打包版默认输出到：

```text
~/Documents/ClassroomTranscriber/outputs/YYYY-MM-DD_HH-MM-SS/
```

每个 session 包含：

```text
raw.txt       # 后端原始 timestamp 转写
clean.txt     # conservative dedup 后的转写
session.log   # 启动、chunk、后端、警告、错误、停止日志
config.json   # 本次 session 的模型、语言、beam、路径和音频配置
```

`raw.txt` 尽量保留后端原始证据。`clean.txt` 只做保守边界去重和少量高置信字幕模板过滤，不做语义纠错。

### 10. 打包 / 重打包

构建 macOS 开发版 `.app`：

```bash
cd /path/to/whisper
./scripts/build_macos.sh
```

输出：

```text
dist/ClassroomTranscriber.app
```

生成方便发送的 zip：

```bash
cd dist
ditto -c -k --sequesterRsrc --keepParent ClassroomTranscriber.app ClassroomTranscriber.zip
```

清理构建产物：

```bash
./scripts/clean_build.sh
```

打包版内置来自 `vendor/whisper.cpp` 的版本锁定模型下载脚本，以及构建机
`external/whisper.cpp` 中的 `whisper-cli` 和相关动态库。它不内置 `large-v3` 等模型文件；
模型由 Model Manager 下载或导入。重新打包前，构建机仍需准备本地 whisper.cpp 后端。

### 11. 已知限制

- 当前只验证 macOS Apple Silicon。
- 没有 notarization，不是正式发布版。
- 没有 Windows 打包。
- 没有 LLM summary。
- 没有语义纠错或课堂笔记结构化。
- `whisper.cpp` 当前仍按 chunk 调用 CLI，后续可优化为 server 或 native binding。
- Mixed Chinese/English 使用 `-l auto`，实际效果依赖模型和音频。
- Chinese 使用 `-l zh`，不使用 prompt 控制简体/繁体；如需简繁规范化，应在 clean 层单独实现，例如 OpenCC。

### 12. 后续计划

- 长时间课堂实测 UI 稳定性和 queue backlog。
- 缩小 PyInstaller app 体积。
- 做正式签名和 notarization。
- 研究 whisper.cpp server/native binding，减少每个 chunk 的进程启动开销。
- 后续可增加离线 LLM cleanup / summary，但不放入实时转写主链路。

更多实现细节见 `工程细节.md`。

---

## English Version

### 1. Project Overview

Classroom Live Transcriber is a local live classroom transcription tool designed primarily for macOS Apple Silicon. It records microphone audio, splits it into overlapping chunks, transcribes each chunk with `whisper.cpp` + Metal, and continuously displays the transcript in a desktop UI.

The goal is a practical local workflow where the transcript is visible during class with some delay. This is not a cloud service and not an LLM note-taking system. It does not summarize, rewrite, or semantically correct the transcript.

### 2. Current Status

Current main path:

- UI: PySide6 / Qt for Python, entry point `ui_app.py`
- Backend: `whisper.cpp` CLI
- Acceleration: Apple Silicon Metal
- Recommended model: `large-v3`
- Output: each recording creates a session with `raw.txt`, `clean.txt`, `session.log`, and `config.json`
- Model management: the UI can scan, select, import, and download ggml/gguf models
- Packaging: macOS Apple Silicon PyInstaller development `.app` build scripts are available

The legacy `stream_transcribe.py` CLI and old `faster-whisper` fallback remain for rollback and comparison. The normal UI does not expose `turbo` or `faster-whisper`.

### 3. Core Features

- Start / Stop live recording and transcription
- Stop drains already captured/submitted audio before closing the session
- Clean and Raw transcript views
- Separate Time and Text columns
- Logs tab for runtime events
- Beam Size selector from `3` to `8`, default `5`
- Original Language selector:
  - `English` -> `-l en`
  - `Chinese` -> `-l zh`
  - `Mixed Chinese/English` -> `-l auto`
- Transcribe only; translate mode is disabled and the app does not pass `-tr` or `--translate`
- Model Manager for scanning local models, importing models, downloading models, and choosing the active model
- Conservative clean-layer boundary dedup and a small subtitle-template hallucination filter

### 4. System Requirements

Recommended environment:

- macOS Apple Silicon
- Python 3.11 or newer
- Microphone permission
- A Metal-enabled `whisper.cpp` build, or the packaged app with bundled `whisper-cli`
- At least one Whisper ggml/gguf model file

If you use the packaged app, users do not need to compile `whisper.cpp`; the app bundles `whisper-cli` and the required dynamic libraries. Large model files are not bundled.

To transcribe in source mode, you must still prepare a Metal build at
`external/whisper.cpp/build/bin/whisper-cli`. The ignored `external/whisper.cpp`
directory is a local source and build dependency and is not included in a clone.

### 5. Install Dependencies

Source mode needs Python dependencies. There is currently no required `requirements.txt`; the minimum set is:

```bash
cd /path/to/whisper
python -m venv venv
source venv/bin/activate
python -m pip install PySide6 numpy sounddevice
```

For rebuilding the app:

```bash
python -m pip install pyinstaller
```

The legacy `faster-whisper` fallback requires installing `faster-whisper` separately. It is not the current UI path.

### 6. Start the UI

Source mode:

```bash
cd /path/to/whisper
source venv/bin/activate
python ui_app.py
```

Packaged app:

```bash
open dist/ClassroomTranscriber.app
```

If you receive `ClassroomTranscriber.zip`, unzip it and open the app. Since this is a development build without notarization, macOS may require right-click -> Open.

### 7. Model Management

Click `Manage Models` in the left panel.

Supported actions:

- Scan local models automatically
- Select the active model from a table
- `Import Existing Model`: use an existing `.bin` / `.gguf` file in place
- `Download Model`: download `large-v3`, `large-v3-turbo`, `medium.en`, `small.en`, or `base.en`
- `Choose Folder`: select the model download directory

Default download directory:

```text
~/Documents/ClassroomTranscriber/models
```

The version-pinned model download script is vendored with this repository at
`vendor/whisper.cpp/download-ggml-model.sh`. Model Manager downloads therefore
do not depend on `external/whisper.cpp` in a fresh clone. A successful model
download only supplies a model file; it does not install or build the
`whisper-cli` backend required by source mode.

Scanned directories:

```text
Current Download Location
~/Documents/ClassroomTranscriber/models
~/Library/Application Support/ClassroomTranscriber/models
project models/
external/whisper.cpp/models/
```

Model choices and download directory are saved in settings. In source mode settings are stored in `config/settings.json`; in the packaged app:

```text
~/Library/Application Support/ClassroomTranscriber/config/settings.json
```

### 8. Usage Flow

1. Start the UI.
2. Open `Manage Models`, then download, import, or select a model.
3. Choose Beam Size, default `5`.
4. Choose Original Language.
5. Click `Start Recording`.
6. Allow microphone permission if macOS asks.
7. After the first chunk completes, watch Clean Transcript.
8. Use Raw Transcript and Logs for debugging.
9. Click `Stop Recording`. Stop releases the microphone and waits for already queued audio to finish.
10. Click `Open Output Folder` to inspect the session files.

### 9. Output Files

Source mode default:

```text
outputs/YYYY-MM-DD_HH-MM-SS/
```

Packaged app default:

```text
~/Documents/ClassroomTranscriber/outputs/YYYY-MM-DD_HH-MM-SS/
```

Each session contains:

```text
raw.txt       # direct timestamped backend output
clean.txt     # conservative deduped transcript
session.log   # startup, chunk, backend, warning, error, and stop logs
config.json   # model, language, beam, paths, and audio settings
```

`raw.txt` preserves backend evidence as much as possible. `clean.txt` applies conservative boundary dedup and a small high-confidence subtitle-template filter. It does not perform semantic correction.

### 10. Packaging / Rebuild

Build the macOS development `.app`:

```bash
cd /path/to/whisper
./scripts/build_macos.sh
```

Output:

```text
dist/ClassroomTranscriber.app
```

Create a shareable zip:

```bash
cd dist
ditto -c -k --sequesterRsrc --keepParent ClassroomTranscriber.app ClassroomTranscriber.zip
```

Clean build artifacts:

```bash
./scripts/clean_build.sh
```

The packaged app bundles the version-pinned download script from
`vendor/whisper.cpp`, plus `whisper-cli` and its libraries from the build
machine's `external/whisper.cpp`. It does not bundle `large-v3` or any other
model file. The build machine must still provide the local whisper.cpp backend;
models are downloaded or imported through Model Manager.

### 11. Known Limitations

- Only macOS Apple Silicon has been tested.
- No notarization; this is not a formal release build.
- No Windows build.
- No LLM summary.
- No semantic correction or structured note generation.
- `whisper.cpp` is still called as a CLI process per chunk; a server or native binding may reduce overhead later.
- Mixed Chinese/English uses `-l auto`; real quality depends on model and audio.
- Chinese uses `-l zh`; the app does not use prompts for Simplified/Traditional Chinese control. Future normalization should be a clean-layer text normalization step, for example OpenCC.

### 12. Roadmap

- Longer classroom stability testing and queue backlog monitoring.
- Reduce PyInstaller app size.
- Add proper signing and notarization.
- Explore a persistent `whisper.cpp` server or native binding.
- Add optional offline LLM cleanup / summary later, outside the live transcription path.

For implementation details, see `工程细节.md`.
