# 课堂实时转写系统

## 1. 项目目标

本项目是在 macOS Apple Silicon 上运行的本地课堂实时转写系统。目标是从“录完以后再转写”推进到“有一定延迟但课堂中即可查看”的实时转写流程。

当前不做 LLM 笔记，不做 summary，不做语义纠错或重写。

## 2. 当前状态

当前主力路径：

- 桌面 UI：`ui_app.py`
- 后端：`whisper.cpp` + Apple Silicon Metal
- 模型：`large-v3`
- 输出：每个 session 独立生成 `raw.txt`、`clean.txt`、`session.log`、`config.json`
- 去重：两阶段保守边界去重
- 旧命令行入口和旧 `faster-whisper` fallback 保留，用于回滚和对比；UI 不显示 `turbo` 或 `faster-whisper`

当前主链路：

```text
PySide6 UI -> sounddevice 麦克风采集 -> 48kHz ring buffer
-> 10 秒 chunk / 3 秒 overlap -> 16kHz 重采样
-> whisper.cpp CLI + Metal + large-v3
-> raw transcript -> simple_dedup -> fuzzy_boundary_dedup -> clean transcript
```

## 3. 架构

主要文件：

- `ui_app.py`：PySide6 桌面 UI。
- `settings.py`：固定路径、Beam 范围、原语言映射、config 字段。
- `transcription_controller.py`：Start/Stop 状态机。
- `transcription_engine.py`：录音、ring buffer、chunk 调度、后端调用、dedup、UI 事件。
- `transcript_store.py`：session 输出目录和 transcript/log/config 文件管理。
- `stream_transcribe.py`：旧 CLI 入口，以及可复用的后端和 dedup helper。

状态机：

- `IDLE`
- `STARTING`
- `RECORDING`
- `STOPPING`
- `ERROR`

## 4. 后端：whisper.cpp Metal + large-v3

UI 固定使用：

```text
Backend: whisper.cpp Metal
Model: large-v3
whisper-cli:
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/build/bin/whisper-cli

model:
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/models/ggml-large-v3.bin
```

后端会把每个 16kHz mono chunk 写成临时 PCM16 WAV，调用 `whisper-cli`，解析带 timestamp 的输出，然后自动清理临时文件。

当前只启用转写模式：

- 会传 `-l <language_code>`
- 不传 `-tr`
- 不传 `--translate`

`backend_migration.md` 保留为从 `faster-whisper` 迁移到 `whisper.cpp` 的历史记录。

## 5. UI 使用

如果未安装 PySide6：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python -m pip install PySide6
```

启动 UI：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python ui_app.py
```

UI 提供：

- Start / Stop
- Beam Size 选择
- Original Language 选择
- Clean transcript tab
- Raw transcript tab
- Logs tab
- 运行时间、queue backlog、后端/模型/beam/语言、输出目录状态

详细 UI 操作说明见 `UI_README.md`。

## 6. Original Language 选择

UI 中有 `Original Language` 选择控件。它直接控制 `whisper-cli -l` 参数。

默认值：

- `English`

映射关系：

| UI 选项 | whisper-cli 参数 |
| --- | --- |
| `English` | `-l en` |
| `Chinese` | `-l zh` |
| `Mixed Chinese/English` | `-l auto` |

目标是保留原语言转写，不启用翻译模式。

当前不再使用 `whisper-cli --prompt` 控制简体/繁体。Chinese 使用 `-l zh`，Mixed Chinese/English 使用 `-l auto`，程序仍然固定运行 `task=transcribe`，不会传 `-tr` 或 `--translate`。

如果后续需要简繁体规范化，应作为 clean 层 text normalization 实现，例如 OpenCC，而不是 Whisper prompt。

每个 session 的 `config.json` 会写入：

```json
{
  "original_language_label": "Chinese",
  "whisper_language_code": "zh",
  "task": "transcribe",
  "prompt_used": ""
}
```

`session.log` 会记录语言选择、prompt 状态、安全版 `whisper-cli` 命令模板、每个 chunk 的语言/prompt 信息，以及解析前后的 segment 数量。

## 7. Beam Size

Beam Size 可选 `3-8`，默认 `5`。

启动时会传给 `whisper-cli`：

```bash
-bs <beam_size>
```

录音中不能修改 Beam Size 和 Original Language。要修改，需要先 Stop，再重新 Start。

## 8. 输出文件

UI 每次录音会创建一个 session 目录：

```text
outputs/
  YYYY-MM-DD_HH-MM-SS/
    raw.txt
    clean.txt
    session.log
    config.json
```

`raw.txt` 保存后端原始 timestamp 输出。

`clean.txt` 保存保守边界去重后的文本。clean 层有一个很小的 denylist，只过滤高度确定的字幕模板幻觉，例如 `中文字幕由 Amara.org 社群提供` 和 `请订阅我的频道`；`raw.txt` 保留这些原始行，方便排查。

`session.log` 记录启动配置、后端事件、chunk 提交、转写事件、warning、error 和停止完成。

`config.json` 记录后端、模型、beam、语言、prompt 状态、音频参数、路径和幻觉过滤设置。

## 9. Dedup 流程

dedup 层只处理 overlap chunk 带来的边界重复，策略保守。

第一阶段：

- `simple_dedup()`
- 精确 / 标准化词边界 overlap 裁剪
- contraction expansion 只用于比较，不改写输出

第二阶段：

- `fuzzy_boundary_dedup()`
- 保守 fuzzy 边界裁剪
- 只比较 old tail 和 new head
- 使用编辑相似度、bigram overlap、内容词 overlap、共享内容词数量等指标

它不是：

- 语义清理
- 段落重写
- LLM summary
- 全文去重

## 10. 安装

Python 环境：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python -m pip install PySide6
```

`whisper.cpp` 和 `large-v3` 预期路径：

```text
external/whisper.cpp/build/bin/whisper-cli
external/whisper.cpp/models/ggml-large-v3.bin
```

手动验证 Metal：

```bash
/Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/build/bin/whisper-cli \
  -m /Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/models/ggml-large-v3.bin \
  -f /Users/smter-mac/Documents/personalAPPS/whisper/external/whisper.cpp/samples/jfk.wav \
  -l en \
  -bs 5
```

查看启动日志中的 Metal/GPU 信息。实时 UI 路径不要使用 `-ng`、`-tr` 或 `--translate`。

## 11. 运行 UI

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python ui_app.py
```

手动验收：

1. 选择 `Original Language = English`，Start，说英文，确认输出英文转写。
2. Stop。
3. 选择 `Original Language = Chinese`，Start，说中文，确认输出中文转写，而不是英文翻译。
4. Stop。
5. 选择 `Mixed Chinese/English`，Start，混合说中文和英文，确认尽量保留原语言。
6. 检查 `outputs/<session>/config.json`。
7. 检查 `outputs/<session>/session.log`。

## 12. 运行测试

UI 支撑测试：

```bash
python testCodes/test_ui_support.py
```

后端支撑测试：

```bash
python testCodes/test_backends.py --skip-faster-smoke
```

dedup 回归测试：

```bash
PYTHONPATH=. python testCodes/test_dedup_expanded_cases.py
PYTHONPATH=. python testCodes/test_pseudo_real_boundary_sequences_v3.py
```

测试覆盖：

- Original Language 映射：`English -> en`、`Chinese -> zh`、`Mixed Chinese/English -> auto`
- CLI 参数不包含 `-tr` 或 `--translate`
- config language/task/prompt/filter 字段
- 生成的 CLI 参数不包含 `--prompt`
- clean-only 字幕模板幻觉过滤
- final partial chunk 时长阈值和低 RMS 跳过
- timestamp 行解析
- transcript store append
- dedup 回归

## 13. 旧 CLI 入口

旧入口仍保留：

```bash
python stream_transcribe.py
```

它用于回滚、调试和后端对比。当前主力用户入口是 UI。

旧文档保留但已废弃：

- `ReadMe.md`
- `README_updated.md`
- `backend_migration.md`

请以 `README.md` 为主文档。

## 14. 已知限制

- 没有 LLM cleanup。
- 没有 LLM summary。
- 没有语义结构化笔记。
- 还没有打包成 macOS app。
- `whisper.cpp` 仍然是每个 chunk 调用一次 CLI；后续可考虑常驻 server 或 native binding。
- clean 只是保守边界 dedup，不是语义纠错。
- Mixed Chinese/English 使用 `-l auto`，真实效果仍需要课堂实测。

## 15. Roadmap

近期：

- 做更长时间课堂 session 稳定性验证。
- 观察 queue backlog 和 Stop 行为。
- 根据真实使用继续优化 UI。

后续：

- UI 稳定后再打包 macOS app。
- 考虑 whisper.cpp server 或 native binding，减少每个 chunk 启动进程的开销。
- LLM cleanup 和 summary 作为离线后处理模块单独加入，不进入实时主链路。
