# Historical Migration Note

This file is retained as the historical record of the `faster-whisper` to `whisper.cpp` migration. Use `README.md` as the current primary documentation and `README_cn.md` as the Chinese counterpart.

# Apple Silicon Whisper backend migration

更新日期：2026-05-19

## 当前默认后端

默认仍然是原来的 `faster-whisper` 后端：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
WHISPER_BACKEND=faster_whisper python stream_transcribe.py
```

不设置 `WHISPER_BACKEND` 时也会使用 `faster_whisper`。

当前主链路没有改变：

麦克风持续录音 -> 48kHz ring buffer -> 10 秒 chunk / 3 秒 overlap -> 16kHz 重采样 -> backend 转写 -> raw/clean 输出 -> 两阶段 dedup。

## 后端切换方式

后端由环境变量选择：

```bash
WHISPER_BACKEND=faster_whisper
WHISPER_BACKEND=whisper_cpp
```

`stream_transcribe.py` 中新增的最小接口是：

```python
transcribe_chunk(audio_16k, chunk_start_time) -> list[str]
```

每个后端都必须输出现有格式：

```text
[start.xx s -> end.xx s] text
```

这样 raw/clean 文件写入、timestamp 叠加、`simple_dedup()`、`fuzzy_boundary_dedup()` 都可以复用。

## faster-whisper baseline

优点：

- 当前项目已稳定运行。
- Python 内直接调用，接口简单。
- 当前 dedup、raw/clean 输出都是围绕这个输出格式调过的。

缺点：

- 当前配置是 `cpu + int8`，没有用 Apple Silicon Metal/GPU。
- MacBook Air 长时间运行时 CPU 压力和发热较高。

本轮没有改：

- `MODEL_NAME = "turbo"`
- `BEAM_SIZE = 5`
- VAD 设置
- chunk 调度
- dedup 逻辑

## whisper.cpp / Metal 候选后端

目标是把每个 16k mono float32 chunk 写成临时 16-bit WAV，然后调用 `whisper-cli`，再把 CLI timestamp 输出解析回现有 lines 格式。

官方 `whisper.cpp` README 说明它针对 Apple Silicon 支持 ARM NEON、Accelerate、Metal 和 Core ML，并且 Apple Silicon 上可走 Metal；CLI 当前要求 16-bit WAV，所以本项目后端会自动写临时 PCM16 WAV 后清理。参考：

- [whisper.cpp README](https://github.com/ggml-org/whisper.cpp/blob/master/README.md)
- [whisper.cpp CLI README](https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/README.md)

### 安装 / 编译 whisper.cpp

建议先放在项目外部目录，不要塞进当前 Python 项目：

```bash
mkdir -p ~/src
cd ~/src
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
```

先下载一个 ggml 模型。为了贴近当前 `turbo` baseline，可优先考虑：

```bash
sh ./models/download-ggml-model.sh large-v3-turbo
```

如果只是验证后端接线是否通，可以临时用较小模型，例如 `base.en`，但这不是公平的精度/性能对比。

Metal 构建：

```bash
cmake -B build -DGGML_METAL=ON
cmake --build build -j --config Release
```

Core ML 路线需要额外生成 encoder 模型并用 Core ML 选项构建。官方 README 建议 Python 3.11，并安装 `ane_transformers`、`openai-whisper`、`coremltools`：

```bash
pip install ane_transformers openai-whisper coremltools
./models/generate-coreml-model.sh large-v3-turbo
cmake -B build -DWHISPER_COREML=1 -DGGML_METAL=ON
cmake --build build -j --config Release
```

Core ML 首次运行可能会慢，因为系统需要编译 `.mlmodelc`。

## 运行 whisper.cpp 后端

设置 CLI 和模型路径：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate

export WHISPER_BACKEND=whisper_cpp
export WHISPER_CPP_CLI="$HOME/src/whisper.cpp/build/bin/whisper-cli"
export WHISPER_CPP_MODEL="$HOME/src/whisper.cpp/models/ggml-large-v3-turbo.bin"

python stream_transcribe.py
```

可选项：

```bash
export WHISPER_CPP_THREADS=4
export WHISPER_CPP_TIMEOUT_SECONDS=120
export WHISPER_CPP_EXTRA_ARGS=""
```

不要在目标测试中设置 `-ng` 或 `--no-gpu`，那会禁用 GPU。

## 如何检查 Metal / Core ML 是否生效

先直接跑一次 `whisper-cli`：

```bash
"$WHISPER_CPP_CLI" -m "$WHISPER_CPP_MODEL" -f ~/src/whisper.cpp/samples/jfk.wav -l en -bs 5
```

检查启动日志：

- Metal 构建通常会在 `system_info` 或加载日志中显示 Metal/GPU 相关能力。
- Core ML 构建成功时，日志应出现加载 `*-encoder.mlmodelc` 的信息，并在 `system_info` 中显示 `COREML = 1`。
- 如果看到 `--no-gpu` / `-ng` 被使用，说明这次不是 Metal 路径。

最终是否降低发热和 CPU 压力，需要在你的 MacBook Air 上用真实 20-40 分钟录音比较 Activity Monitor、温度和转写延迟。

## 测试命令

轻量检查，不加载 faster-whisper 模型：

```bash
cd /Users/smter-mac/Documents/personalAPPS/whisper
source venv/bin/activate
python testCodes/test_backends.py --skip-faster-smoke
```

完整 backend smoke：

```bash
python testCodes/test_backends.py
```

本机未安装 `whisper-cli` 时预期输出包含：

```text
PASS: whisper.cpp output parser
PASS: 16k mono pcm16 wav writer
PASS: faster-whisper availability
PASS: faster-whisper smoke
SKIP: whisper.cpp availability
```

安装并设置 `WHISPER_CPP_CLI` / `WHISPER_CPP_MODEL` 后，`whisper.cpp availability` 和 `whisper.cpp smoke` 应为 `PASS`。

## 当前未完成事项

- `whisper.cpp` 后端现在是 CLI 候选实现，每个 chunk 都启动一次进程；这适合最小可行验证，但不是最终低延迟架构。
- CLI 输出解析目前支持默认 timestamp 行，例如 `[00:00:01.000 --> 00:00:02.500] text`。
- 还没有做 Python native binding 或长驻 `whisper.cpp` server。
- 还没有做真实课堂音频的延迟、温度、CPU/GPU 占用对比。
- 还没有把 `faster-whisper` 和 `whisper.cpp` 模型完全对齐后的 WER/重复率评估自动化。
