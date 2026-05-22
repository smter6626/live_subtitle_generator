# Deprecated

This file is retained for historical context. Use `README.md` as the primary English documentation and `README_cn.md` as the Chinese counterpart. Detailed UI operation notes remain in `UI_README.md`.

# Whisper 本地流式转写（当前实现状态 / 2026-04 更新版）

## 1. 项目目标
本项目用于在本地持续采集英文语音并进行流式转写，同时对相邻 chunk 之间由于时间重叠带来的重复文本做保守去重，输出两份对照文件：

- `raw`：原始转写结果
- `clean`：两阶段 dedup 后结果

当前设计目标不是“自动生成高质量课堂笔记”，也不是“语义理解后自动总结”，而是：

1. 稳定完成本地实时英文转写
2. 在不破坏原始语义和时间戳结构的前提下，压掉 chunk 边界重复
3. 为后续 GUI、课后离线总结、结构化笔记提供较干净的文本输入

---

## 2. 当前项目能力概述
当前 `stream_transcribe.py` 已具备以下能力：

- 本地麦克风持续录音，直到手动停止（`Ctrl+C`）。
- 使用滚动环形缓冲区保存最近一段音频。
- 以固定窗口做流式转写：`10` 秒 chunk，`3` 秒 overlap。
- 录音链路为：`48kHz` 采集 -> 转写前重采样到 `16kHz`。
- 使用 `faster-whisper` 的 `turbo` 模型进行英文转写。
- 当前 VAD 已启用（`VAD_FILTER = True`）。
- 输出双文件：
  - `*_raw.txt`
  - `*_clean.txt`
- clean 输出采用两阶段去重：
  - 第一阶段：`simple_dedup()`
  - 第二阶段：`fuzzy_boundary_dedup()`

程序主流程如下：

持续录音 -> 环形缓冲区累积 -> 满足条件后提交 chunk -> 48kHz -> 16kHz 重采样 -> Whisper 转写 -> 写入 raw -> Stage 1 dedup -> Stage 2 dedup -> 写入 clean

说明：

- raw 文件只要当前 chunk 有识别文本就会写入。
- clean 文件只有在两阶段 dedup 后仍有内容时才写入。
- raw 是否写入不受 clean 是否为空影响。

---

## 3. 当前关键配置参数
以下参数来自当前代码基线（`stream_transcribe.py`）：

| 参数 | 当前值 | 说明 |
| --- | --- | --- |
| `MODEL_NAME` | `"turbo"` | Whisper 模型 |
| `DEVICE` | `"cpu"` | 推理设备 |
| `COMPUTE_TYPE` | `"int8"` | 推理精度 |
| `LANGUAGE` | `"en"` | 固定英文 |
| `CAPTURE_RATE` | `48000` | 录音采样率 |
| `TRANSCRIBE_RATE` | `16000` | Whisper 输入采样率 |
| `CHANNELS` | `1` | 单声道 |
| `BLOCK_SECONDS` | `10` | 每个 chunk 的时长 |
| `OVERLAP_SECONDS` | `3` | 相邻 chunk 重叠时长 |
| `RING_BUFFER_SECONDS` | `30` | 环形缓冲区时长 |
| `STEP_SECONDS` | `7` | 新 chunk 提交步长（`10 - 3`） |
| `BEAM_SIZE` | `5` | 解码 beam size |
| `VAD_FILTER` | `True` | 是否启用 VAD |
| `MIN_SILENCE_MS` | `500` | VAD 最小静音时长 |
| `OVERLAP_WINDOW_WORDS` | `60` | 第一阶段 dedup 比较窗口 |
| `OVERLAP_MIN_WORDS` | `3` | 第一阶段最少匹配词数 |
| `OVERLAP_MIN_CHARS` | `12` | 第一阶段最少匹配字符数 |
| `FUZZY_WINDOW_WORDS` | `20` | 第二阶段 fuzzy 比较窗口 |
| `FUZZY_MIN_PREFIX_WORDS` | `6` | fuzzy 最短候选前缀词数 |
| `FUZZY_MAX_PREFIX_WORDS` | `18` | fuzzy 最长候选前缀词数 |
| `FUZZY_SUFFIX_LEN_DELTA` | `2` | fuzzy 后缀长度偏差 |
| `FUZZY_TAIL_EXACT_WORDS` | `2` | fuzzy 尾部强约束词数 |
| `FUZZY_MIN_SHARED_CONTENT_WORDS` | `3` | fuzzy 最少共享内容词 |
| `FUZZY_SCORE_THRESHOLD` | `0.88` | fuzzy 综合分阈值 |
| `FUZZY_EDIT_SIM_THRESHOLD` | `0.84` | fuzzy 编辑相似度阈值 |
| `FUZZY_BIGRAM_THRESHOLD` | `0.45` | fuzzy bigram 重叠阈值 |
| `FUZZY_CONTENT_OVERLAP_THRESHOLD` | `0.70` | fuzzy 内容词重叠阈值 |

输出文件命名规则：

- 启动时生成一次前缀：`month_day_hour_minute`
- raw：`月_日_时_分_raw.txt`
- clean：`月_日_时_分_clean.txt`
- 示例：`4_14_4_16_raw.txt`、`4_14_4_16_clean.txt`

---

## 4. 当前音频与设备说明
- 使用 `sounddevice.InputStream(...)` 采集音频。
- 当前默认使用系统默认输入设备，不在代码内硬编码具体麦克风型号。
- 录音采样率固定为 `48kHz`。
- 转写前统一重采样到 `16kHz`。
- 当前项目依赖麦克风输入链路，不依赖扬声器型号或播放设备设置。

---

## 5. 当前去重逻辑（核心）

### 5.1 第一阶段：`simple_dedup()`
作用：处理**精确边界重复**。

当前行为：

- 对 old tail / new head 做标准化比较。
- 使用词级最长边界重叠匹配。
- 适合处理相邻 chunk 的完全重复、缩写展开后高度一致重复、明显边界重叠。
- 裁剪后尽量保留原始输出格式。
- 已支持：
  - 第一行内部裁剪后的 timestamp 保留
  - 第一行整行删除后跳到下一行时，保留该行 timestamp

### 5.2 第二阶段：`fuzzy_boundary_dedup()`
作用：处理**保守 fuzzy 边界重复**。

当前行为：

- 只比较 old 尾部窗口与 new 头部窗口。
- 不做全文级模糊匹配。
- 从较长前缀向较短前缀枚举，优先裁剪最长可靠前缀。
- 联合多指标判定：
  - 编辑相似度
  - bigram 重叠
  - 内容词重叠
  - 共享内容词数量
  - 综合分
- 只有多条件同时满足时才裁剪，整体策略偏保守。
- 命中时保留原始文本与时间戳风格。
- 未命中但接近阈值时，会打印最佳失败候选 debug 信息。

### 5.3 compare layer 缩写处理
当前比较层已经加入常见英文 contraction expansion，用于提升比较鲁棒性，例如：

- `we'll` -> `we will`
- `we're` -> `we are`
- `don't` -> `do not`
- `can't` -> `cannot`

注意：

- 这些 expansion 仅用于比较层，不会改写最终写入 raw / clean 文件的原始文本。

---

## 6. 当前已经验证通过的能力
项目当前不只是“代码写出来了”，而且已经通过了一轮文本级测试与伪真实边界测试，验证了以下能力：

### 6.1 基础单元测试通过
已验证：

- no overlap 不会误删
- exact overlap 可由 Stage 1 处理
- full overlap 可删空
- contraction overlap 可由 compare layer + Stage 1 处理
- 一部分 lexical variation 可由 Stage 2 处理
- negative cases（相似框架但不同含义 / 不同实体）不会被误删
- timestamp 在关键裁剪场景下能够保留
- multiline boundary overlap 基本可工作

### 6.2 扩展本地合成测试通过
已验证：

- Stage 1 与 Stage 2 的分工合理
- 中等复杂度的 local paraphrase / contraction / lexical variation 能触发 dedup
- negative case 仍然稳定

### 6.3 第三版 precise-boundary sequence 测试通过
这是当前最有代表性的伪真实边界测试。结论如下：

#### Medium precise-boundary sequence v3
- `compression_ratio = 0.590`
- `Stage1 hits = 2`
- `Stage2 hits = 3`
- 说明在**中等强度边界口语干扰**下，clean 相比 raw 有明显压缩收益，并且 Stage 1 / Stage 2 都发挥了作用。

#### High precise-boundary sequence v3
- `compression_ratio = 0.714`
- `Stage1 hits = 4`
- `Stage2 hits = 1`
- 说明在**较高强度边界口语干扰**下，系统仍能处理相当一部分边界重复与局部改写，整体收益明显，但仍保持保守。

当前可以认为：

- **中等强度边界干扰**下，程序已能较稳定压掉 chunk 边界重复。
- **较高强度边界干扰**下，程序已能处理相当一部分 overlap / contraction / 局部改写，但并不会清除所有口语噪音。

---

## 7. 当前系统的能力边界（非常重要）
当前 dedup 模块的定位是：

> **边界型重复去重器**，不是语义摘要器，也不是课堂内容重构器。

### 当前擅长处理的内容
- chunk 边界 exact overlap
- contraction overlap
- 局部 lexical variation
- multiline boundary overlap
- 局部 spoken filler 附近的边界重复

### 当前不打算由 dedup 处理的内容
- 老师在后续内容中“结构性重讲同一知识点”
- 段落级重述
- 全文语义压缩
- 课堂笔记结构化整理
- LLM 风格总结或重写

这些更适合放到后续模块，例如：
- 课后离线 summarizer
- LLM 结构化笔记
- GUI 中的二次整理视图

---

## 8. 输出文件说明
每次程序启动会生成同一前缀的一组文件：

- `*_raw.txt`
  - 保存每个 chunk 的原始识别结果
  - 保留时间戳格式
  - 不经过 dedup
- `*_clean.txt`
  - 保存两阶段 dedup 后结果
  - 保留时间戳格式
  - dedup 后为空时跳过该次写入

raw / clean 文件前缀相同，便于对照分析。

---

## 9. 当前已知限制
- 当前只做文本级转写与边界 dedup，不做课堂笔记结构化整理。
- Stage 2 仍然采用保守阈值，可能漏删一部分轻微重复，这是有意取舍。
- 在复杂噪声、极快语速、明显口音、多人重叠说话、或长距离语义重述场景下，仍可能保留一些重复。
- 某些 chunk 在裁剪后，可能只剩较短尾部（例如非常短的收尾短语）；这在逻辑上未必错误，但在真实运行中需要继续观察其观感。
- 当前没有 GUI。
- 当前没有 summary。
- 当前没有 LLM 后处理。
- 当前尚未完成长时间真实录音稳定性验证。

---

## 10. 运行方式
### 10.0 后端选择
旧命令行入口 `stream_transcribe.py` 仍保留后端切换能力，用于回滚和对照。当前桌面 UI 主力路线固定为 `whisper.cpp Metal + large-v3`。Apple Silicon / `whisper.cpp` 的接入说明见：

- `backend_migration.md`
- `UI_README.md`

### 10.1 直接运行
```bash
python stream_transcribe.py
```

### 10.2 使用虚拟环境
```bash
source venv/bin/activate
python stream_transcribe.py
```

程序启动后会打印本次运行输出文件名，例如：

- `Raw output file: 4_14_4_16_raw.txt`
- `Clean output file: 4_14_4_16_clean.txt`

---

## 11. 当前推荐验证方式
### 11.1 文本级 / 合成测试
当前已存在或建议保留以下测试：

- `test_dedup_cases.py`
- `test_dedup_uncovered_cases.py`
- `test_dedup_expanded_cases.py`
- `test_pseudo_real_boundary_sequences_v3.py`

其中，`test_pseudo_real_boundary_sequences_v3.py` 是当前最推荐的伪真实边界测试。

### 11.2 验证重点
验证时重点看：

- `Stage1 hits`
- `Stage2 hits`
- `compression_ratio`
- `RAW HISTORY` vs `CLEAN HISTORY`
- 是否存在明显 over-trim
- 是否仍保留关键内容和时间戳结构

---

## 12. 下一阶段计划（README 更新版新增）
当前 dedup 基本完成后，后续优先级建议如下：

### 第一优先级：真实录音长时间稳定性测试
目标：

- 连续录音 30 分钟甚至更久
- 检查是否出现卡顿
- 检查 raw / clean 文件是否持续正常写入
- 检查 Stage 2 是否异常频繁触发
- 检查是否出现大量过短残片或观感明显变差的 clean 输出
- 观察内存 / CPU 是否持续升高

### 第二优先级：轻量 clean 文本可读性提升
前提：真实录音稳定性测试通过后再考虑。

候选方向：

- 空白整理
- 过短残片观察与限制
- 非侵入式表层格式优化

注意：

- 这一步仍然不做语义改写，不引入重型智能后处理。

### 第三优先级：GUI
已新增 UI v1.0 入口：

```bash
python ui_app.py
```

UI 使用 `whisper.cpp Metal + large-v3`，并把输出写入 `outputs/YYYY-MM-DD_HH-MM-SS/`。详细说明见：

- `UI_README.md`

### 第四优先级：课后离线总结 / 结构化笔记
这部分不属于当前 dedup 模块，应与实时主链路解耦。

---

## 13. 当前项目状态一句话总结
当前项目已经从“只有基本转写”推进到：

> **具备可验证的本地实时英文转写 + 双文件输出 + 两阶段保守边界 dedup 的阶段，且在精确边界测试与伪真实边界测试中已表现出明确收益。**

下一步不再是继续堆 dedup 规则，而是进入：

> **真实录音长时间稳定性测试 -> 轻量可读性优化 -> GUI / 离线总结模块分离推进。**
