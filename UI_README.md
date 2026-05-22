# UI v1.1: Classroom Transcriber

更新日期：2026-05-21

## 当前路线

UI v1.1 仍默认推荐：

- Backend: `whisper.cpp Metal`
- Model: `large-v3`
- CLI: `/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/build/bin/whisper-cli`
- Model file: `/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/models/ggml-large-v3.bin`

现在 UI 已加入 Model Manager，可以检测、选择、导入和下载模型。默认路线不变：如果检测到 `ggml-large-v3.bin`，优先选择 `large-v3`。

UI 不显示 `turbo`，也不把 `faster-whisper` 暴露为普通用户选项。旧命令行代码仍保留，方便回滚和对照。

## 安装 PySide6

当前 UI 使用 PySide6 / Qt for Python。如果启动时报 `PySide6 is not installed`，在项目虚拟环境中安装：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python -m pip install PySide6
```

## 启动 UI

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python ui_app.py
```

默认窗口大小约 `1200x800`。

## 普通用户操作指南

1. 打开 UI。
2. 确认顶部显示：
   - Status: `Idle`
   - Backend: `whisper.cpp Metal`
   - Model: `large-v3`，或当前 Model Manager 选中的模型
   - Beam: `5`
   - Language: `English`
3. 在左侧 Model 区域确认当前模型；如需调整，点击 `Manage Models`。
4. 根据课堂环境选择 Beam Size，范围是 `3-8`，默认 `5`。
5. 选择 Original Language：
   - `English` -> `-l en`
   - `Chinese` -> `-l zh`
   - `Mixed Chinese/English` -> `-l auto`
6. 点击 `Start Recording`。
7. macOS 如果弹出麦克风权限请求，允许 Python / Terminal / Codex 使用麦克风。
8. 等待第一个 10 秒 chunk 完成后，Clean Transcript 和 Raw Transcript 会开始追加内容。
9. 默认看 `Clean Transcript`，它是保守 dedup 后的课堂实时文本。
10. 如需排查识别原文，切换到 `Raw Transcript`。
11. 如需看系统事件，切换到 `Logs`。
12. 点击 `Stop Recording` 停止。Stop 会通过 UI 内部停止录音、关闭麦克风 stream、通知 worker 退出并 flush 文件，不依赖 `Ctrl+C`。
13. 点击 `Open Output Folder` 查看本次 session 文件。

## Model Manager

左侧控制区有 Model 区域：

- Current：当前选中的模型摘要
- Model 下拉框：从已检测到的本地模型中切换
- Refresh Models：重新扫描模型目录
- Manage Models：打开模型管理弹窗

Model Manager 弹窗显示本地模型表格：

| Name | Size | Path | Status |
| --- | --- | --- | --- |
| `large-v3` | `2.9 GB` | `external/whisper.cpp/models/ggml-large-v3.bin` | `available` |

扫描目录：

```text
当前 Download Location
~/Documents/ClassroomTranscriber/models
~/Library/Application Support/ClassroomTranscriber/models
项目目录 models/
external/whisper.cpp/models/
```

默认 Download Location 是 `~/Documents/ClassroomTranscriber/models`。启动时会确保默认模型目录存在；点击 `Download Model` 前也会确保当前下载目录存在。

识别规则：

- `ggml-large-v3.bin` -> `large-v3`
- `ggml-large-v3-turbo.bin` -> `large-v3-turbo`
- `ggml-medium.en.bin` -> `medium.en`
- `ggml-small.en.bin` -> `small.en`
- `ggml-base.en.bin` -> `base.en`
- 其他 `ggml-*.bin` 或 `.gguf` -> `Custom Model`

默认选择逻辑：

1. 优先恢复上次保存的模型。
2. 如果没有保存模型，优先选 `large-v3`。
3. 如果没有 `large-v3`，选择 `large-v3-turbo`。
4. 如果都没有，显示 `No model selected`，并禁用 Start Recording。

### 导入已有模型

点击 `Import Existing Model` 后选择 `.bin` 或 `.gguf` 文件。第一版采用 `Use in place`：

- 不复制 2.9GB 模型文件
- 只把该路径加入 settings
- 文件必须存在
- 文件大小必须大于 10MB
- 文件名建议以 `ggml-` 开头，但不强制

### 下载模型

点击 `Download Model`，第一版支持：

- `large-v3`
- `large-v3-turbo`
- `medium.en`
- `small.en`
- `base.en`

下载通过 whisper.cpp 自带脚本执行：

```bash
sh external/whisper.cpp/models/download-ggml-model.sh <model-name> <download_model_dir>
```

默认下载目标是：

```text
~/Documents/ClassroomTranscriber/models/
```

在 Model Manager 中可以通过 `Download Location` 旁边的 `Choose Folder` 修改下载位置。选择后会保存到 settings，下次启动自动恢复。

下载在后台线程执行，不阻塞 UI。Logs tab 会显示下载日志。目标文件已存在时会提示 `Model already exists.`，不会重复下载。

### 模型设置保存位置

UI 模型选择会保存到：

```text
config/settings.json
```

示例：

```json
{
  "whisper_cpp_cli": ".../external/whisper.cpp/build/bin/whisper-cli",
  "selected_model_path": ".../ClassroomTranscriber/models/ggml-large-v3.bin",
  "selected_model_name": "large-v3",
  "default_beam_size": 5,
  "download_model_dir": "~/Documents/ClassroomTranscriber/models",
  "model_dirs": [
    ".../ClassroomTranscriber/models",
    ".../Application Support/ClassroomTranscriber/models",
    ".../models",
    ".../external/whisper.cpp/models"
  ],
  "imported_model_paths": []
}
```

## Beam Size 含义

Beam Size 会在启动时传给 `whisper-cli` 的 `-bs` 参数。

- `3`: 更轻，可能略快，可能更容易漏或错。
- `5`: 默认值，当前推荐起点。
- `8`: 更重，可能更稳，但延迟和资源占用可能上升。

Recording 中不能修改 Beam Size。要改 beam，先 Stop，再选择新值并重新 Start。

## Original Language

Original Language 控制 `whisper-cli -l` 参数，目标是原语言转写，不是翻译。

| UI 选项 | whisper-cli 参数 |
| --- | --- |
| `English` | `-l en` |
| `Chinese` | `-l zh` |
| `Mixed Chinese/English` | `-l auto` |

当前默认值是 `English`，因为项目主要用于英文课堂。中文或中英混合场景请在 Start 前切换。Recording 中不能修改 Original Language；要改语言，先 Stop，再重新 Start。

程序不会传 `-tr` 或 `--translate`。

程序当前也不会传 `--prompt`。Chinese 只使用 `-l zh`，Mixed Chinese/English 只使用 `-l auto`。

如果后续需要简繁体规范化，应作为 clean 层 text normalization 实现，例如 OpenCC，而不是 Whisper prompt。

## 输出文件

UI 不再优先把输出散落在项目根目录，而是创建 session 目录：

```text
outputs/
  YYYY-MM-DD_HH-MM-SS/
    raw.txt
    clean.txt
    session.log
    config.json
```

`config.json` 包含：

```json
{
  "backend": "whisper_cpp",
  "backend_display": "whisper.cpp Metal",
  "model": "large-v3",
  "model_display": "large-v3",
  "model_path": ".../ggml-large-v3.bin",
  "beam_size": 5,
  "block_seconds": 10,
  "overlap_seconds": 3,
  "capture_rate": 48000,
  "transcribe_rate": 16000,
  "whisper_cpp_cli": ".../whisper-cli",
  "whisper_cpp_model": ".../ggml-large-v3.bin",
  "selected_model_path": ".../ggml-large-v3.bin",
  "original_language_label": "English",
  "whisper_language_code": "en",
  "task": "transcribe",
  "prompt_used": "",
  "hallucination_filter": {
    "mode": "clean_only",
    "denylist": [
      "中文字幕由 Amara.org 社群提供",
      "请订阅我的频道",
      "请点赞",
      "点赞 订阅 转发"
    ]
  }
}
```

`raw.txt` 保留 whisper.cpp 的原始输出。`clean.txt` 在 dedup 之后会过滤少量高度确定的字幕模板幻觉；过滤记录会写入 `session.log`。

## 管理员视角：UI 操作对应的内部动作

### 启动 UI

用户操作：

```bash
python ui_app.py
```

内部动作：

- 导入 PySide6。
- 创建 Qt 主窗口。
- UI 主线程只负责显示和事件处理。
- `TranscriptionController` 初始状态为 `IDLE`。

### 点击 Start Recording

内部动作：

1. 读取 UI 当前 Beam Size 和 Original Language。
2. 读取 UI 当前选中的模型路径和模型名。
3. 构造 `TranscriptionSettings`，固定 backend，动态使用当前模型路径。
4. 执行路径检查：
   - `whisper-cli` 是否存在且可执行。
   - 当前选中的模型是否存在。
   - 当前选中的模型是否是文件。
   - 当前选中的模型大小是否大于 10MB。
5. 创建 session 目录：
   - `outputs/YYYY-MM-DD_HH-MM-SS/`
6. 创建并打开：
   - `raw.txt`
   - `clean.txt`
   - `session.log`
7. 写入 `config.json`。
8. 启动后台 audio capture thread。
9. 启动后台 transcription worker thread。
10. capture thread 打开：

```python
sounddevice.InputStream(
    samplerate=48000,
    channels=1,
    dtype="float32",
    callback=audio_callback,
    blocksize=0,
)
```

11. worker 初始化：

```bash
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/build/bin/whisper-cli \
  -m <selected_model_path> \
  -f <temporary chunk.wav> \
  -l <language_code> \
  -bs <beam>
```

每个 chunk 会写一个临时 16k mono PCM16 WAV，CLI 调完后临时目录自动清理。

### 录音中

内部动作：

- audio callback 持续把 48k mono audio 追加进 ring buffer。
- 每满 `10s` chunk，按 `7s` step 提交一次任务，保持 `3s` overlap。
- worker 将 48k chunk 重采样到 16k。
- `whisper-cli` 输出被解析成：

```text
[start.xx s -> end.xx s] text
```

- raw lines 立即写入 `raw.txt` 并发送给 Raw tab。
- raw chunk 经过：
  - `simple_dedup()`
  - `fuzzy_boundary_dedup()`
- clean 层过滤高度确定的字幕模板幻觉，raw 保留证据。
- clean lines 写入 `clean.txt` 并发送给 Clean tab。
- UI 显示层会把 timestamp 拆成两列：
  - Time: `MM:SS` 或 `HH:MM:SS`
  - Text: 正文

### 点击 Stop Recording

内部动作：

1. UI 状态变 `Stopping`。
2. 禁止继续点击 Start/Stop。
3. 后台 stop thread 调用 controller stop。
4. engine 设置 `stop_event`。
5. capture loop 退出 `InputStream` context，麦克风释放。
6. 提交 Stop 前已录入但尚未提交的 final partial chunk。
   - final partial 小于 2 秒会跳过。
   - final partial RMS 过低会跳过，减少短静音尾块触发的幻觉。
7. 不清空已有 task queue，worker 会继续 drain backlog 和 final partial。
8. worker 收到 sentinel 后退出；如果当前 chunk 正在跑，会等待当前 CLI 调用完成或超时。
9. flush 并关闭 raw/clean/session log。
10. UI 状态回到 `Idle`。

## 如何判断 Metal 路径正确

先单独运行：

```bash
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/build/bin/whisper-cli \
  -m /Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/models/ggml-large-v3.bin \
  -f /Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/samples/jfk.wav \
  -l en \
  -bs 5
```

检查输出日志中的 `system_info` 或初始化信息，应看到 Metal/GPU 相关能力。不要使用 `-ng` 或 `--no-gpu`，那会禁用 GPU。

课堂实测时同时观察：

- Activity Monitor 中 CPU idle 是否维持高位。
- Memory pressure 是否基本绿色。
- 机身是否只是温、不烫。
- `Logs` tab 中 queue backlog 是否长期累积。

## 手动测试 Start / Stop

1. 启动 UI。
2. 选择 Beam `5`。
3. 选择 Original Language。
4. 点击 Start。
5. 对着麦克风连续说对应语言 30-60 秒。
6. 确认 Raw tab 有原始行追加。
7. 确认 Clean tab 有 dedup 后文本追加。
8. 确认 Logs tab 有：
   - backend initialization
   - whisper-cli language
   - microphone stream opened
   - chunk submitted
   - transcribing chunk
   - raw written
   - clean written
9. 点击 Stop。
10. 确认状态回到 Idle。
11. 打开输出目录，确认 `raw.txt`、`clean.txt`、`session.log`、`config.json` 都存在且有内容。
12. 再次点击 Start，确认能开启第二个新 session。

## 错误提示

如果 CLI 不存在，UI 会显示：

```text
Cannot start transcription: whisper-cli not found.
Expected path: ...
```

如果没有选择模型，UI 会显示：

```text
Cannot start transcription: no model selected.
```

如果模型不存在，UI 会显示：

```text
Cannot start transcription: selected model not found.
Expected path: ...
```

如果 PySide6 不存在，终端会显示：

```text
PySide6 is not installed.
Install it with: python -m pip install PySide6
```

## 已知限制

- 当前没有 LLM summary。
- 当前没有语义纠错或课堂笔记重写。
- 当前已有 PyInstaller macOS 开发版打包脚本；详细见 `PACKAGING.md`。它不是 notarized release build。
- 当前 `whisper.cpp` 后端仍是 CLI 调用方式，每个 chunk 启动一次进程；后续可以优化成 long-running server 或 native binding。
- 当前 clean 是保守 dedup，不是语义纠错。
- `Mark Now` 按钮预留但暂未实现。
