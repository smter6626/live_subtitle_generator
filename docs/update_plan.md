# Streaming Backend Upgrade Investigation

> 调查日期：2026-09-11（America/Phoenix）
>
> 调查性质：静态代码审计与实施规划；本次没有修改运行时代码、构建脚本或测试。
>
> 状态词仅使用：**Supported**、**Internally supported but not exposed**、**Not supported**、**Unknown / needs experiment**。
>
> 文中的 `UNVERIFIED` 表示代码阅读不足以证明设备性能、质量或运行时行为，后文给出最小实验。

## 1. Executive Summary

结论：**可以升级，而且应先升级到“embedded whisper.cpp + 应用层 rolling context + token-level LocalAgreement/hybrid commit”，不应第一步就复刻完整 AlignAtt。**

当前项目不是 decoder-level streaming。生产路径每 7 秒提交一个 10 秒音频块（3 秒重叠），把 48 kHz 音频重采样为 16 kHz，写临时 WAV，启动一个新的 `whisper-cli` 进程，解析其最终 segment 文本，再以字符串 exact/fuzzy dedup 生成 clean transcript。每个进程都会重新加载模型；Whisper 的 encoder、decoder、KV cache 和文本条件都不跨块保留。证据：`stream_transcribe.py::WhisperCppBackend.transcribe_chunk()`、`build_whisper_cpp_command()`；`transcription_engine.py::TranscriptionEngine._maybe_submit_chunk()`、`_worker_loop()`。

SimulStreaming 的实际优势不是“神奇地增量运行整个 Whisper”。它持久化模型、rolling audio segments、已接纳 token 和较老的 prompt/context；在一次 `infer()` 内使用 self/cross-attention KV cache 并逐 token 解码，以 alignment-head cross-attention 的峰值是否接近当前音频末端决定停止。**但每次新增音频后的 `infer()` 都重算完整 rolling window 的 mel/encoder/cross-KV，并在本轮结束清空 decoder KV；下一轮会强制重放已有 token 来重建 cache。** 证据：`simulstreaming/whisper/simul_whisper/simul_whisper.py::PaddedAlignAttWhisper.infer()`、`_clean_cache()`、`insert_audio()`。

vanilla whisper.cpp 已公开大部分“机械能力”：长期存在的 `whisper_context` / `whisper_state`、PCM→mel、encode、带 `n_past` 的 decode、logits/token API、prompt tokens、rolling text prompt、beam search、DTW token timestamp、Metal 和 iOS XCFramework。它缺少的关键能力是：

1. **实现 AlignAtt 的直接缺口**：public C API 不能读取逐 token raw cross-attention；内部只为 DTW 物化所选 alignment heads，最后只公开 `whisper_token_data.t_dtw`。
2. **降低 streaming 总计算量的根本缺口**：没有 incremental encoder。音频增加或窗口移动时必须重跑当前窗口的 conv、encoder 和 cross-attention K/V projection。
3. **iPad 上的额外冲突**：whisper.cpp 当前会在 `flash_attn && dtw_token_timestamps` 时关闭 DTW；Flash Attention 不物化完整 attention matrix。小 patch 的 AlignAtt 原型应先接受 `flash_attn=false`，其 iPad 代价必须实机测量。
4. rollback 不是最大缺口：`whisper_decode_with_state(..., n_past, ...)` 在内部调用 `whisper_kv_cache_seq_rm(..., n_past, -1)`，下一次 decode 可以隐式截断 self-KV 后重放；只是没有独立的 public truncate/clone/save/restore API。

建议路线：

- **立即 Go：Level 1**，把 CLI/subprocess/temp-WAV 换成同进程 C API，模型只加载一次，同时定义可被 Python/macOS 与 Swift/iPadOS 共用的 C ABI streaming core。
- **优先 Go：Level 2 hybrid**，应用层持有 rolling audio、committed/provisional token、显式 prompt tokens；默认用 token-ID LocalAgreement + 时间安全边界提交，DTW 作为实验性信号而不是默认依赖。
- **Conditional Go：Level 3 AlignAtt patch**，仅在 Level 2 基准证明 attention-guided early stop 对延迟/稳定性有显著且可复现的增益，并且 physical iPad 上关闭 Flash Attention 后仍满足内存、热和实时性预算时继续。
- **暂不做**：跨音频更新盲目复用 decoder KV、incremental encoder 大改、CIF、把 SimulStreaming 的 PyTorch fork直接移植到 App。

## 2. Repositories and Revisions

以下是开始写本文档前实际分析的 revision。当前项目 SHA 是运行时代码基线；提交本文档后仓库 HEAD 会自然前移一次。

| Repository | Path | Branch | Analyzed HEAD | Repository URL | Initial worktree state |
| --- | --- | --- | --- | --- | --- |
| live_subtitle_generator | `/Users/smterpro/Workspace/whisper/live_subtitle_generator` | `multiLanguage_v1` | `088f1071280e656f85b5abb2bbce1fc06bc9925c` | `git@github.com:smter6626/live_subtitle_generator.git` | clean |
| SimulStreaming | `/Users/smterpro/Workspace/Tools/SimulStreaming` | `main` | `077ea37d5ab4ff98bc567e4507f140dc4e5d5ad6` | `https://github.com/ufal/SimulStreaming.git` | freshly cloned, clean |
| whisper.cpp | `/Users/smterpro/Workspace/Tools/whisper.cpp` | `master` | `1da4dc82fa7996d4edda05890dca65aeceaafd6d` | `https://github.com/ggml-org/whisper.cpp.git` | freshly cloned, clean |

当前产品构建并不跟随上述 whisper.cpp `master`。`packaging/runtime_manifest.json` 的实际 runtime pin 是 `8443cf05e3fa8ce1b32348e1bcbcf8fc31f7f3ae`，且 `scripts/bootstrap_whisper_runtime.sh::ensure_pinned_source()` 强制 detached checkout。对该 pinned commit 做了额外只读核对：本文涉及的 `whisper_init_state`、`whisper_encode_with_state`、`whisper_decode_with_state`/`n_past`、prompt context、DTW、large-v3/large-v3-turbo alignment presets 均已存在。真正实施前仍应把 fork/embedded runtime 的唯一 pin 显式升级或继续固定，不能混用两个 SHA。

## 3. Current Project Architecture

### 3.1 Production inference path

真实生产路径是：

```text
PySide6 UI
  -> TranscriptionController.start()
  -> TranscriptionEngine
     capture thread:
       sounddevice.InputStream(blocksize=0, 48 kHz, mono, float32)
       -> deque ring buffer (30 s)
     scheduler (poll every 0.5 s):
       -> 10 s block, next start +7 s, therefore 3 s overlap
       -> task queue
     worker thread:
       -> per-block linear interpolation 48 kHz -> 16 kHz
       -> temporary PCM16 WAV
       -> subprocess.run(whisper-cli -m ... -f ... -l ... -bs ...)
       -> parse stdout/stderr timestamped segments
       -> raw.txt
       -> exact boundary dedup
       -> fuzzy boundary dedup
       -> clean-only hallucination denylist
       -> clean.txt + UI events
```

Evidence:

- `stream_transcribe.py:33-38`: `CAPTURE_RATE=48000`、`TRANSCRIBE_RATE=16000`、`BLOCK_SECONDS=10`、`OVERLAP_SECONDS=3`、`RING_BUFFER_SECONDS=30`；`:135-141` 定义 `STEP_SECONDS=7` 和 ring capacity。
- `transcription_engine.py::audio_callback()` 将 callback samples 放入 `deque`; `::_capture_loop()` 使用 `blocksize=0`。这里 `blocksize=0` 是让 sounddevice/host 选择 callback frame size，不是 ASR 的 10 秒 inference block。
- `transcription_engine.py::_maybe_submit_chunk()` 每次只提交完整 10 秒块，起点增加 7 秒；若 worker 落后导致目标离开 30 秒 ring，会 realign 到 buffer start。
- `transcription_engine.py::_worker_loop()` 做 resample、backend 调用、raw/clean 写入和两阶段 dedup。
- `stream_transcribe.py::WhisperCppBackend.transcribe_chunk()` 使用 `TemporaryDirectory`、`write_pcm16_wav()` 和 `subprocess.run()`；进程结束后没有任何 Whisper state 可复用。
- `transcription_engine.py::_submit_final_partial_chunk()` 在 Stop 时补交至少 2 秒且 RMS 至少 `0.0015` 的尾块；`stop()` 先关 capture，再 drain queue，最后关闭 store。

### 3.2 Context、prompt 与 dedup 的实际状态

- **Whisper context 跨 chunk：Not supported。** Python 的 `WhisperCppBackend` 对象虽存在于 worker 生命周期内，但只保存路径/参数；每块都是新 CLI process。
- **模型跨 chunk：Not supported。** 每次 `subprocess.run()` 都启动独立 `whisper-cli`，模型和 state 随进程创建/销毁。
- **文本 prompt：Not supported。** `TranscriptionSettings.prompt_used` 被传给 `WhisperCppBackend(initial_prompt=...)`，但 `build_whisper_cpp_command()` 从未把 `initial_prompt` 放入 `cmd`。`settings.py::ORIGINAL_LANGUAGE_PROMPTS` 当前也全部为空。测试 `testCodes/test_backends.py::check_whisper_cpp_command_builder()` 与 `testCodes/test_ui_support.py::test_whisper_cpp_command_language_args()` 明确断言即使给非空 prompt 也不得出现 `--prompt`。
- **dedup 位置**：`transcription_engine.py::_worker_loop()` 先 `simple_dedup(combined, last_output_text)`，再 `fuzzy_boundary_dedup(last_output_text, stage1)`；`last_output_text` 只累计已经写入 clean 的文本，不进入模型。
- **exact dedup**：`stream_transcribe.py::find_overlap_and_cut_index()` 比较旧文本尾部与新文本头部的 normalization token，最多 60 tokens，最少 3 tokens 或 12 characters。
- **fuzzy dedup**：`stream_transcribe.py::fuzzy_boundary_dedup()` 在边界窗口上组合 edit similarity、bigram overlap、content-word overlap 和 unigram Jaccard，以多个 hard threshold 决定裁剪。这是事后字符串启发式，不是 token hypothesis agreement，也不使用 acoustic alignment。
- **raw / clean**：`raw.txt` 是 CLI 已完成解码并解析成 segment 后、尚未去重/过滤的行；不是 raw logits/token/attention。`clean.txt` 是 exact/fuzzy dedup 后再经过 `filter_clean_hallucinations()` denylist 的行。命中的 hallucination 仍保留在 raw，符合 evidence-preserving 设计。证据：`transcript_store.py::TranscriptStore`；`transcription_engine.py::_worker_loop()`。

### 3.3 Existing tests and what they protect

- `testCodes/test_backends.py`：CLI command、临时 WAV、stdout parser 和 backend smoke；其中 prompt 被忽略是当前显式 contract。
- `testCodes/test_dedup_cases.py`、`test_dedup_expanded_cases.py`、`test_dedup_uncovered_cases.py`、`test_multilingual_dedup.py`：exact/fuzzy 边界裁剪，包括 contraction、相似但不同文本、日语/韩语无空格 tokenization。
- `testCodes/test_pseudo_real_chunk_sequences.py` 与三个 boundary sequence suites：模拟 overlap chunks，检查 clean compression、保留/禁止片段与空输出数。它们不是声学或 decoder 稳定性测试。
- `testCodes/test_ui_support.py`：语言命令、hallucination filter、store append、final partial、queue drain、short final chunk。
- `testCodes/test_model_integrity.py`、`test_model_download_resources.py`、`test_runtime_manifest.py`、`test_whisper_runtime_bootstrap.py`、`test_packaged_runtime.py`：model SHA/size transaction、runtime pin、dylib closure 和 packaged CLI。

迁移时不要删除这些测试；应把它们分成“legacy backend regression”和“新 streaming acceptance fixture”，逐步替换它们保护的机制，而不是失去它们代表的边界案例。

## 4. How SimulStreaming Actually Works

### 4.1 Entry path and persistent objects

ASR 主调用链：

```text
simulstreaming_whisper.py::simul_asr_factory()
  -> SimulWhisperASR
  -> PaddedAlignAttWhisper (model loaded once)
  -> SimulWhisperOnline.insert_audio_chunk()
  -> SimulWhisperOnline.process_iter()
     -> PaddedAlignAttWhisper.insert_audio()
     -> PaddedAlignAttWhisper.infer()
     -> tokens + attention-derived word times
```

`PaddedAlignAttWhisper` 长期持有 `self.model`、`self.segments`（audio chunks）、`self.tokens`（当前 rolling audio 对应的已接纳 token tensors）、`self.context`（较旧 token 转成的 prompt text）、alignment hooks 和本轮 KV cache。`SimulWhisperOnline` 长期持有 timestamp offset 与 incomplete-Unicode buffer。

### 4.2 Streaming policies must not be conflated

#### AlignAtt

AlignAtt 是本仓库 ASR 的实际 commit gate：

1. `PaddedAlignAttWhisper.infer()` 对当前 rolling audio 完整 encode。
2. decoder 首次输入 context + mandatory SOT/language/task tokens + 已接纳 tokens；之后每步只输入最后一个 token，依赖本轮 KV cache。
3. 每生成一个 token 后，代码聚合 selected alignment heads，取该 token 的 `most_attended_frame`。
4. 如果 `content_mel_len - most_attended_frame <= frame_threshold`，代码删除刚生成的最后一个 token并停止本轮 decode。
5. 剩余新 tokens 通过 `self.tokens.append(new_tokens)` 成为下一轮强制 prefix，等价于永久接纳；没有再经过两轮 agreement。

证据：`simulstreaming/whisper/simul_whisper/simul_whisper.py::PaddedAlignAttWhisper.infer()`，尤其 decoding loop、`most_attended_frames` 和 end-of-buffer branch。`simulstreaming_whisper.py::simulwhisper_args()` 的 CLI 默认 `frame_threshold=25`；encoder frame 是 20 ms，故该默认危险区是 0.5 秒。`AlignAttConfig` dataclass 自身默认值是 4；通过 CLI 构造时实际使用 25。`is_last=True` 时代码强制用 4 frames。

AlignAtt 的“commit”语义因此是：**一个 token 已生成，且其 selected-head aggregate attention peak 不在当前音频末端危险区，同时没有触发 rewind guard；再经过可选词尾处理后，本轮保留的 token 立即成为 committed prefix。** 它不是对概率阈值的判断，也不是 DTW。

#### LocalAgreement

LocalAgreement 的定义是对相邻两次完整 hypothesis 取最长公共前缀，仅提交共同前缀；它不需要 attention。证据：`README.md` 的 “Simultaneous policies” 段。

但在本次 SimulStreaming HEAD 中，**speech ASR 的 LocalAgreement backend 并未实现**：`simulstreaming/whisper/whisper_streaming/whisper_online_main.py` 和 `whisper_server.py` 的注释都写明 default WhisperStreaming LocalAgreement backends “not implemented but could be”。仓库内可执行的 longest-common-prefix code 位于 `simulstreaming_translate.py`，服务于 LLM simultaneous translation，不是 `PaddedAlignAttWhisper` ASR 路径。因此 matrix 中 SimulStreaming ASR 的 LocalAgreement 必须标为 Not supported，不能因 README 描述而标成现有 ASR 功能。

#### CIF / truncation detection

CIF 与 AlignAtt 的 near-end token stop 是两层不同逻辑：

- `simulstreaming/whisper/simul_whisper/eow_detection.py::load_cif()` 加载一个独立线性层 checkpoint。
- `::fire_at_boundary()` 对 encoder features 做 linear→sigmoid→累计积分，判断输入块末端是否有 end-of-word firing。
- 在 AlignAtt decoding loop 已停止之后，`PaddedAlignAttWhisper.infer()` 才根据 `fire_detected` 决定是否保留最后一个 space-delimited word；未 fire 时把最后一个 word 的 token 暂不加入 committed token buffer。
- 这是“输入是否在词中间结束”的 guard，不是 token alignment、不是 LocalAgreement，也不决定 earlier tokens。

重要代码/文档不一致：`simulstreaming_whisper.py` 的 help 声称无 CIF checkpoint 时总是裁掉最后一词，`--never_fire` 时从不裁；但当前 `load_cif()` 在无 checkpoint 且 `never_fire=False` 时设置 `always_fire=True`，而 `infer()` 对 `fire_detected=True` 保留全部 tokens。`never_fire=True` 反而令 `fire_detected=False` 并进入裁词分支。静态调用链显示实际代码与 help 相反。标记：**UNVERIFIED runtime**；最小实验是无 checkpoint/`--never_fire` 两组固定音频，检查 `generation["result_truncated"]` 和 emitted tokens。另据 CLI help，large-v3 没有对应 CIF checkpoint，所以 CIF 不能作为 large-v3 路线的既定能力。

### 4.3 Cross-attention code path

真实路径如下：

```text
PaddedAlignAttWhisper.__init__()
  -> for decoder block: block.cross_attn.register_forward_hook(layer_hook)

modified Whisper TextDecoder
  -> ResidualAttentionBlock.forward()
  -> MultiHeadAttention.forward()
  -> MultiHeadAttention.qkv_attention()
     returns (attention output, detached raw qk logits)

layer_hook(net_output)
  -> softmax(net_output[1], dim=-1)
  -> self.dec_attns.append(...)

PaddedAlignAttWhisper.infer(), after each generated token
  -> select model.alignment_heads
  -> z-normalize
  -> median_filter(width=7)
  -> average selected heads
  -> crop to content_mel_len
  -> argmax(last-token attention over audio frames)
  -> compare to frame_threshold
```

Evidence:

- `simulstreaming/whisper/simul_whisper/simul_whisper.py::PaddedAlignAttWhisper.__init__()` 安装 hook、建立 `align_source`。
- `simulstreaming/whisper/simul_whisper/whisper/model.py::MultiHeadAttention.forward()` / `qkv_attention()` 显式返回 qk；为得到权重，hook 再 softmax。
- `simulstreaming/whisper/simul_whisper/whisper/__init__.py::_ALIGNMENT_HEADS` 包含 large-v3 和 large-v3-turbo preset，`load_model()` 调用 `model.set_alignment_heads()`。
- `PaddedAlignAttWhisper.infer()` 将 mel pad/trim 到 Whisper 3000 mel frames，encoder stride 后 attention frame 为 20 ms；`content_mel_len` 是有效 encoder frames。
- `simulstreaming_whisper.py::SimulWhisperOnline.timestamped_text()` 用 `most_attended_frame * 0.02 + audio_buffer_offset` 生成展示用 word time。这不是 DTW path。

beam 模式下 `BeamPyTorchInference.rearrange_kv_cache()` 按 beam source indices 重排 self-attention KV；cross-attention KV 对同一 audio features 共享。AlignAtt stop 使用 top beam（index 0）的 most-attended frame控制本轮停止。证据：`simulstreaming/whisper/simul_whisper/beam.py` 和 `PaddedAlignAttWhisper.infer()`。

### 4.4 Decoder state: what is and is not reused

**同一次 `infer()` 内：**

- self-attention K/V：Supported。第一次 forward 处理完整 forced prefix；以后只送最后 token，hook append self K/V。
- cross-attention K/V：Supported。第一次由 encoder features 投影；`MultiHeadAttention.forward()` 在 `xa != None` 且 cache 命中时复用。
- beam self-KV：Supported，随 beam reorder。

**两次 audio update 之间：**

- model weights/object：Supported。
- previous accepted tokens、audio segment list、old prompt/context：Supported。
- encoder output：Not supported；每次重算。
- self-attention KV：Not supported；`infer()` 末尾 `_clean_cache()` 令 `self.kv_cache={}`。
- cross-attention KV：Not supported；同样清空。
- rejected token rollback：逻辑 rollback Supported，但不是 KV rollback。near-end branch 从 `current_tokens` 去掉最后 token；随后整份 cache 被清空。下一 update 以保留 token 重新跑 prefix。rewind guard 也恢复 `current_tokens` 后清 cache。

因此“SimulStreaming 持久化 decoder KV across chunks”是不准确的。它持久化的是**可重放的 token state**；KV 只优化单次 autoregressive loop。

这也符合模型语义：新增音频后 encoder features 与 cross-attention K/V 已改变；decoder 每层 hidden state 又依赖 cross-attention。盲目保留基于旧音频计算的 self-KV 可能产生 stale state。即使 C API 允许保存，也必须以实验或重建保证正确性，不能把“persistent state object”误写成“跨音频更新安全复用 KV”。

### 4.5 Rolling context and >30-second operation

- `PaddedAlignAttWhisper.insert_audio()` 将新 audio tensor 加到 `self.segments`，总长度超过 `audio_max_len`（默认 30 秒）时从最旧 segment 开始移除。
- 移除一个 audio segment 时，对应的 `self.tokens[1]` 被 decode 成文本并追加到 `TokenBuffer context`；当前 rolling window 的 token list同步左移。
- `_current_tokens()` 构造 `[sot_prev + context tokens] + mandatory SOT/language/task + tokens belonging to retained audio segments`。
- `trim_context()` 逐词删除 dynamic context，直到不超过 `max_context_tokens` 且总 decoder input 留出 20 token余量；`static_init_prompt` 的字符前缀不滚动删除，`init_prompt` 会进入可滚动部分。
- 音频时间轴由 `SimulWhisperOnline.audio_bufer_offset` 加上被移除的秒数维持。

所以长音频不是送入一个超过 30 秒的 encoder。它靠“最多 30 秒 rolling audio + 更老 confirmed text 作为 prompt + 当前窗口 forced tokens”跨窗继续。证据：`PaddedAlignAttWhisper.insert_audio()`、`_current_tokens()`、`trim_context()`；`token_buffer.py::TokenBuffer`。

### 4.6 Actual computational savings

相对当前项目，SimulStreaming 明确节省：

- 模型只加载一次，无每块 process startup/model initialization。
- 无临时 WAV/CLI stdout round trip。
- 单次 decode loop 以 self/cross KV 避免每生成一个 token 都重算完整 prefix/cross projections。
- AlignAtt 在危险区停止，不继续生成很可能被未来音频推翻的 speculative suffix；相对需要连续两次完整 hypothesis 的 LocalAgreement，可能减少 decoder speculative work。
- rolling buffers 使长音频的内存/每轮上下文有上限。

它**没有**节省：

- 每次新增音频后，当前 rolling audio 的 mel、全 encoder、cross K/V projection 都重算。
- 已接纳 forced token 的 decoder KV 跨 update 不保留；它们至少需要作为 prefix 再 forward 一次以重建 cache。
- 更高更新频率可能对较长 rolling window 做更多次 encoder；因此相对当前“每 7 秒一次、10 秒窗”的总 FLOPs 不一定更低。

结论：低延迟、较稳定提交和较少文本 dedup 是明确的架构收益；总计算下降是 **UNVERIFIED**，必须用相同音频、相同模型、相同 update cadence 统计 encoder/decode time 与实时因子。

## 5. whisper.cpp Capability Audit

### 5.1 Persistent model/context/state

Supported。

- `include/whisper.h::whisper_init_from_file_with_params()` 创建含 model 与默认 state 的 `whisper_context`；`whisper_free()` 释放。
- `whisper_init_from_file_with_params_no_state()` 只载入 context/model；`whisper_init_state(ctx)` 可创建一个或多个显式 state；`whisper_free_state()` 释放。
- `src/whisper.cpp::whisper_context` 持有只读 model/vocab 与可选 default state；`whisper_state` 持有 mel、encoder output、self/cross KV、logits、results 和 prompt history。
- `include/whisper.h` 的 thread-safety contract：同一个 `whisper_context` 不可被多个线程并发使用。iPad wrapper 应用 Swift `actor` 或单一 serial queue；官方 `examples/whisper.swiftui/whisper.cpp.swift/LibWhisper.swift::WhisperContext` 正是 actor，并在 `deinit` 调用 `whisper_free()`。

长期复用 context/state 是 API 支持的；但 `whisper_full_with_state()` 是否保留某类计算 cache 是另一问题。它保留 prompt history，却在每个 decode window clear self-KV。

### 5.2 Incremental decoding primitives

Public C API 足以做自定义 greedy incremental decoder：

- `whisper_pcm_to_mel_with_state()` / `whisper_set_mel_with_state()`
- `whisper_encode_with_state()`
- `whisper_decode_with_state(tokens, n_tokens, n_past, n_threads)`
- `whisper_get_logits_from_state()`
- `whisper_tokenize()`、`whisper_token_to_str()` 和 special-token APIs
- model/context size queries，如 `whisper_n_text_ctx()`

`src/whisper.cpp::whisper_batch_prep_legacy()` 把新 token positions 设为 `n_past+i`；`whisper_decode_with_state()` 先删掉 self-KV 中 position `>=n_past` 的 sequence-0 cells，再 decode 新 tokens。官方 Swift sample `LibWhisper.swift::benchFull()` 也展示第一次 prompt decode 后用 `n_past` 做单 token decode。

限制：

- public low-level API 注释仍有 “TODO: add support for multiple decoders”；production beam search、temperature fallback、timestamp rules、grammar/logit filters 都在 `whisper_full_with_state()` 内部。自行用 low-level API做 greedy 可行；完整复制 upstream beam/full sampling 行为会扩大维护面。
- `whisper_full_with_state()` 自身在每一 decode iteration 前 `whisper_kv_cache_clear(state->kv_self)`，并有 TODO “do not recompute the prompt if it is the same”。所以调用 high-level full API不会自动得到跨 update decoder-KV 增量。

### 5.3 Text context is not decoder KV state

Public text-conditioning support是 Supported：

- `whisper_full_params.initial_prompt`
- `prompt_tokens` + `prompt_n_tokens`
- `carry_initial_prompt`
- `n_max_text_ctx`
- `no_context`

`src/whisper.cpp::whisper_full_with_state()` 将 history 分成 `prompt_past0`（可固定携带的 initial prompt）和 `prompt_past1`（decoded output rolling context），预算上限是 `min(n_max_text_ctx, whisper_n_text_ctx()/2)`，并以 `whisper_token_prev()` 开头重新喂给 decoder。

这只是把旧 token再次作为 prompt input；它不等于保存那些 token 的 decoder hidden state/KV。当前项目没有使用这些 public capabilities，因为它调用 CLI 且 command builder丢弃 `initial_prompt`。

### 5.4 Cross-attention, alignment heads and DTW

whisper.cpp 内部确实计算 decoder cross-attention：

- `src/whisper.cpp::whisper_build_graph_cross()` 把 encoder output 投影为每个 decoder layer 的 `kv_cross.k/v`。
- `::whisper_build_graph_decoder()` 的 cross-attention branch计算 Q、读取 `kv_cross`，non-Flash path 显式形成 `KQ_soft_max`。
- 当 context params `dtw_token_timestamps=true` 且该 layer 有 alignment-head mask 时，selected heads 被 concat 为 `aheads_cross_QKs`。

alignment heads：Supported。`include/whisper.h::whisper_alignment_heads_preset` 有 tiny/base/small/medium/large-v1/v2/v3/v3-turbo、N-top-most 和 custom；`src/whisper.cpp::g_aheads` 包含 large-v3 的 10 个 heads 与 large-v3-turbo 的 6 个 heads。

DTW token timestamp：Supported，但它是 post-hoc：

1. `whisper_full_with_state()` 先完成普通 transcription。
2. `whisper_exp_compute_token_level_timestamps_dtw()` 重新构造 SOT/language/no-timestamps + 全部结果 text token + EOT。
3. 清空 self-KV，再调用 private `whisper_decode_internal(..., save_alignment_heads_QKs=true)` 做一次 forced decode。
4. 对 selected heads normalize、median-filter(width=7)、mean、取负作为 cost，做 DTW/backtrace。
5. 把结果写进 `whisper_token_data.t_dtw`（centiseconds），public caller 通过 `whisper_full_get_token_data[_from_state]()` 读取。

因此 DTW 不会在普通 autoregressive decode 的每一步向 caller 暴露 attention，也不会让 caller提早停止生成。它反而有一遍额外 forced decoder pass。

Raw per-token cross-attention：**Internally supported but not exposed**。`whisper_state::aheads_cross_QKs` 与 CPU copy vector 都是 private；`whisper_decode_with_state()` 始终传 `save_alignment_heads_QKs=false`；`include/whisper.h` 没有 raw matrix/shape accessor。公开结果只有最终 `t_dtw`。

Flash Attention conflict：`whisper_init_with_params_no_state()` 在 `flash_attn && dtw_token_timestamps` 时记录 warning 并把 DTW关闭。因为 Flash Attention branch不构造 `KQ_soft_max`，当前 DTW/AlignAtt-style raw matrix path必须关闭 Flash Attention。Metal 仍可启用，但性能、内存与热影响是 **UNVERIFIED**。

### 5.5 Rollback, truncate and state copying

逐项结论：

- **remove last N decoded tokens / rewind self-KV**：Supported indirectly。下一次调用 `whisper_decode_with_state()` 时给较小 `n_past`，内部 `whisper_kv_cache_seq_rm()` 会删除该位置之后的 sequence-0 cache，再以新 token重建。
- **explicit truncate-only public API**：Not supported。`whisper_kv_cache_seq_rm()` 是 `src/whisper.cpp` private static function。
- **reset decoder while keeping current encoder/cross state**：Supported indirectly by calling decode with `n_past=0` and完整 retained prefix；没有专名 reset API。
- **clone/copy `whisper_state`**：Not supported。header 无 clone；state 包含 backend buffers/schedulers，不是可安全 `memcpy` 的 POD。
- **save/restore decoder state**：Not supported。
- **internal sequence copy for beam**：Internally supported but not exposed。`whisper_kv_cache_seq_cp/rm()` 被 `whisper_full_with_state()` beam loop使用。

对 AlignAtt 的意义：没有必要为“丢掉刚生成的危险 token”先做大型 state snapshot。可像 SimulStreaming 一样逻辑删除 token并重建，或用较小 `n_past` 在下一 decode隐式截断。需要实验验证的是 rollback 后 logits 是否与 fresh replay一致，特别是换了 encoder window之后。

### 5.6 Encoder recomputation

Incremental encoder：Not supported。

- `whisper_pcm_to_mel_with_state()` 针对 caller 给出的 samples 重新计算 spectrogram；没有 append-only mel public API。
- `whisper_encode_internal()` 每次依次执行 conv graph、完整 encoder graph，再执行完整 cross-projection graph。
- `whisper_encode_with_state(offset, ...)` 的 `offset` 是从已存 mel 选择一个窗口的起点，不是“仅 encode 新 frames”。
- `whisper_full_with_state()` 对每个约 30 秒 window调用完整 `whisper_encode_internal()`。

由于 Whisper encoder 是双向 self-attention，新增末尾音频理论上也能改变旧 frame representation；不是简单追加 encoder KV 即可保持完全等价。真正 incremental encoder 会是研究/模型近似工程，不是一个小 C API patch。

短于 30 秒的 PCM并不自动保证 encoder FLOPs按时长线性下降：默认 graph仍按 model audio context补零处理。`whisper_full_params.audio_ctx` 可缩小 experimental audio context，但 header 明确把它列为可能显著降低质量的 speed-up technique。必须分别测试“短 rolling PCM”和“缩小 `audio_ctx`”，不能把二者等同。

### 5.7 iPadOS viability

嵌入 iOS/iPadOS：Supported。

- `build-xcframework.sh` 同时构建 iOS simulator/device，默认 `BUILD_SHARED_LIBS=OFF`、`GGML_METAL=ON`、`GGML_METAL_EMBED_LIBRARY=ON`、`GGML_NATIVE=OFF`、`WHISPER_COREML=ON`；最终 `xcodebuild -create-xcframework` 生成 `build-apple/whisper.xcframework`。`BUILD_STATIC_XCFRAMEWORK=ON` 可把合并后的 static archive包装进 framework。
- 当前脚本 deployment target 是 iOS 16.4。device 是 arm64；simulator 是 arm64+x86_64。
- framework module map直接公开 `whisper.h` 等 C headers；Swift sample `import whisper` 后直接调用 C API。ObjC sample同样直接调用。
- `examples/whisper.swiftui/whisper.cpp.swift/LibWhisper.swift::WhisperContext` 用 actor串行化访问并管理 context lifetime；这是未来 SwiftUI backend的正确基本形态。
- `examples/whisper.swiftui/README.md` 说明 Core ML只替代 encoder，GGML model仍需要提供 decoder；XCFramework build允许 fallback。
- Metal：Supported；build脚本链接 Metal/Accelerate，并嵌入 metallib。

需要正视的设备约束：

- upstream SwiftUI README明确建议 iOS device从 tiny/base/small 开始，而不是 large。当前项目 manifest 的未量化 `large-v3` 文件为 3,095,033,483 bytes，`large-v3-turbo` 为 1,624,555,275 bytes；运行时还需要 model buffers、encoder output、self/cross/pad KV 和 compute schedulers。能否在目标 iPad稳定运行是 **Unknown / needs experiment**，不能由“文件能下载”推导。
- `whisper_state` 初始化会同时分配 self/cross/pad caches。beam 模式需要更多 decoder sequences，`whisper_full_with_state()` 在扩大 cache时按 `n_decoders+2` over-allocate；当前 UI beam 3–8 对移动内存并不友好。具体峰值不在代码中保证，必须测。
- DTW default `dtw_mem_size` 是 128 MiB，`whisper_exp_compute_token_level_timestamps_dtw()` 当前每次另建 ggml context，源码有 FIXME；另保存 attention data。iPad默认启用 DTW之前必须证明收益高于 memory/Flash-Attention代价。
- 同一 context不可并发。一个 session一个串行 owner最简单；多 session或后台并行不能共享同 context并发调用。
- 官方 Swift/ObjC examples证明集成路径，不证明 large-v3/turbo 的实时性、持续热稳定性或长时间 memory plateau。

## 6. Capability Matrix

说明：SimulStreaming 一栏指本次 HEAD 的 ASR `PaddedAlignAttWhisper` 路径；whisper.cpp 一栏指 vanilla public API，若只有 private implementation则按指定状态标出。

| Capability | Current live_subtitle_generator | SimulStreaming ASR | vanilla whisper.cpp | Evidence / qualification |
| --- | --- | --- | --- | --- |
| persistent model | **Not supported** | **Supported** | **Supported** | Current 每块新 CLI；Simul `PaddedAlignAttWhisper.__init__`; C API `whisper_init_*` |
| persistent allocated context/state | **Not supported** | **Supported** | **Supported** | C API `whisper_init_state`, `whisper_free_state` |
| persistent decoder KV across audio updates | **Not supported** | **Not supported** | **Unknown / needs experiment** | Simul `_clean_cache()`；C low-level能保留，但换 encoder 后 state可能 stale；high-level full会 clear |
| rolling audio context | **Supported** | **Supported** | **Not supported** | Current deque；Simul `insert_audio()`；library不拥有应用层 rolling policy |
| rolling text context used by model | **Not supported** | **Supported** | **Supported** | Current `last_output_text` 仅 dedup；Simul `TokenBuffer`; C full `prompt_past0/1` |
| prompt tokens | **Not supported** | **Supported** | **Supported** | Current command builder故意忽略；C `prompt_tokens` |
| incremental decode within one encoded window | **Not supported** | **Supported** | **Supported** | Simul last-token loop；C decode/logits/`n_past` |
| `n_past` equivalent | **Not supported** | **Internally supported but not exposed** | **Supported** | Simul KV offset由 cache tensor length推导；C API显式参数 |
| self-attention KV reuse | **Not supported** | **Supported** | **Supported** | 两者均在单次 decode sequence中复用 |
| cross-attention KV reuse | **Not supported** | **Supported** | **Supported** | 均在同一 encoder window的 decoder steps中复用；new audio后重算 |
| raw per-token cross-attention access | **Not supported** | **Supported** | **Internally supported but not exposed** | Simul forward hook；C private `aheads_cross_QKs` |
| alignment-head presets/config | **Not supported** | **Supported** | **Supported** | 两者都有 large-v3 与 turbo presets |
| DTW token timestamp | **Not supported** | **Supported** | **Supported** | Simul modified OpenAI timing module；C `t_dtw` |
| token-level permanent commit policy | **Not supported** | **Supported** | **Not supported** | AlignAtt app policy；C library只给 primitives/results |
| logical token rollback | **Not supported** | **Supported** | **Supported** | Simul删 tensor suffix并清 cache；C lower `n_past` on next decode |
| explicit public KV truncate API | **Not supported** | **Not supported** | **Internally supported but not exposed** | private `whisper_kv_cache_seq_rm` |
| clone/copy/save/restore state | **Not supported** | **Not supported** | **Not supported** | 无 public API；Simul选择重建 |
| LocalAgreement for ASR | **Not supported** | **Not supported** | **Not supported** | Simul repo只描述 ASR policy；现有 LCP code在 translation path |
| CIF truncation detection | **Not supported** | **Supported** | **Not supported** | Simul optional checkpoint；large-v3 checkpoint缺失且 CLI/help语义需实验 |
| beam search | **Supported** | **Supported** | **Supported** | Current `-bs`; Simul custom beam；C `WHISPER_SAMPLING_BEAM_SEARCH` |
| large-v3 | **Supported** | **Supported** | **Supported** | model lists/presets；设备性能另行实验 |
| large-v3-turbo | **Supported** | **Supported** | **Supported** | model lists/presets；设备性能另行实验 |
| Metal | **Supported** | **Not supported** | **Supported** | Current pinned Metal build；Simul chooses CUDA else CPU；C GGML Metal |
| iOS/iPadOS embedding | **Not supported** | **Not supported** | **Supported** | XCFramework + SwiftUI/ObjC examples |
| incremental encoder after audio append | **Not supported** | **Not supported** | **Not supported** | Simul和C每次重跑 current audio window encoder |

## 7. Core Architectural Gaps

按目标区分，最大 gap 不是同一个：

### 7.1 If the goal is AlignAtt behavior

最大直接缺口是 **public per-token alignment signal**。whisper.cpp 已在 private DTW graph里形成 selected-head cross-attention，但低层 public decode拿不到它，high-level API也没有“attention进入危险区就停止”的 callback。

rollback 是次要缺口：已有 `n_past` 隐式 truncate，或可以像 SimulStreaming一样丢 token后重建。显式 truncate API会改善清晰度和测试性，但不是 blocker。

### 7.2 If the goal is less repeated computation

最大根本缺口是 **incremental encoder**，其次是 audio update 后 decoder cache的有效性。即使暴露 raw attention并实现完美 AlignAtt，当前 rolling audio每更新一次仍重跑 encoder与cross projections。AlignAtt主要减少 unsafe decoder suffix和事后 dedup，不会消除 encoder repetition。

### 7.3 If the goal is iPad product viability

最大不确定性是 **model/working-memory/thermal budget + Flash Attention trade-off**。vanilla embedding成熟，但 large-v3/turbo、beam 3–8、DTW raw attention同时存在时是否可持续运行完全未验证。

### 7.4 Other gaps

- 当前 transcript contract以完整 timestamped lines为单位；streaming需要 committed/provisional token event和 revision语义。
- 当前 Python scheduler、resampler、temp-WAV/CLI parser混在 `stream_transcribe.py`；不能直接成为 Swift backend。
- 当前测试集中在 text-level dedup，没有 PCM→hypothesis→commit 的 deterministic fixture、latency/stability/long-form tests。
- whisper.cpp public low-level decode不直接提供 production-grade beam control；要么先用 greedy prototype，要么把 policy hook放进 full decoder内部。

## 8. Reusable Components

### A. Can be retained essentially as-is

- `transcript_store.py::TranscriptStore` 的 session directory、append/flush/close、config/log evidence ownership；只需上层把 committed events格式化成现有行。
- `transcription_controller.py::EngineState`、Start/Stop、error/event边界和 Stop drain理念。
- session logging/config snapshot机制。
- `model_manager.py` 的 model discovery/selection、download transaction入口，以及 `model_integrity.py` 的 exact size/SHA-256/atomic publish/receipt设计。
- output-root、language/model compatibility、UI language逻辑。
- clean-only hallucination denylist可作为 committed text后的最后一道保守 guard；raw hypothesis evidence仍保留。
- 现有 dedup/pseudo-real测试作为 legacy baseline与新 policy regression corpus，不应立即删除。

### B. Concept reusable, implementation must change

- **ring buffer**：保留 bounded rolling audio与绝对时间轴概念；改成 sample-index驱动、可截断、可供 C++ core/Swift共享的结构。
- **chunk scheduler**：保留单 worker、backpressure、final flush；把固定 10/3/7 调度改成 update cadence + rolling window + commit cycle。
- **resampling**：保留 Whisper接收 16 kHz mono float PCM的 contract；当前逐块 `np.interp` 不适合跨平台持续流，应由平台 adapter或可移植 streaming resampler维护相位/边界。iPad端 AVAudioEngine转换后直接送 core。
- **raw/clean**：raw应演化为完整 hypothesis/commit decision evidence（可另加 JSONL），clean仍只追加永久 committed text；不要把 provisional text不可逆写入 clean。
- **settings**：从 block/overlap扩展为 update cadence、audio window、commit policy、agreement depth/safety margin、prompt budget、DTW/attention flags。
- **tests**：把字符串 dedup案例转成 token sequence稳定性、跨语言无空格、时间边界和 rollback fixtures。
- **model manager**：保留 integrity逻辑，但 iPad路径、可用模型/量化选择、可用存储与内存准入需要平台 adapter。

### C. Remove from the new primary streaming backend

- 每块 `whisper-cli` subprocess。
- inference path中的临时 WAV writer与stdout/stderr parser。
- 固定 10 秒 + 3 秒 overlap作为唯一策略。
- `simple_dedup()` / `fuzzy_boundary_dedup()` 作为主正确性机制；可暂留 legacy backend fallback，不应作用于新 committed token stream。
- 以累积 clean string作为“模型上下文”的替代品。
- production path对 `stream_transcribe.py` legacy console/faster-whisper全局变量的依赖。

## 9. Proposed Upgrade Levels

### Level 1 — Low-risk, no whisper.cpp fork

目标：换 transport/lifetime，不改变识别 policy。

- 同进程加载 pinned whisper.cpp library；一个 session持有一个长期 `whisper_context` / `whisper_state`。
- 直接送 16 kHz float PCM给 `whisper_full_with_state()`，消除 temp WAV、process startup/model reload和stdout parser。
- 暂时保留 10 秒块、3 秒 overlap与现有 dedup，建立 A/B parity。
- backend输出结构化 segment/token data，而不是文本解析结果。
- 从第一天把核心封装成平台中立 C++ owner + 稳定 C ABI；Python只做薄 binding，未来 Swift直接复用同一 core和 state machine。

收益：明确消除每块模型初始化、进程和磁盘中转；可读取 token IDs/probabilities/timestamps；iPad build path开始复用。限制：encoder/decoder仍重复处理 overlap，transcript仍依赖事后 dedup，首个完整块延迟不变。

### Level 2 — Medium-risk, still no whisper.cpp fork

可实现的最高合理形态：

- application-owned rolling audio window和绝对 sample clock。
- application-owned committed/provisional token buffers；显式 `prompt_tokens`，避免依赖隐式 `prompt_past`。
- 对连续 updates的 text token IDs做 LocalAgreement longest common prefix；只把稳定前缀写入 clean。
- 以公开 segment/token timestamps或可选 `t_dtw` 设置 safety horizon：只提交 alignment time明显早于当前 audio edge的 token。
- 逐词/Unicode-safe边界提交，未完成 suffix保持 provisional。
- 可以使用 low-level `encode/decode/n_past/logits` 做 greedy incremental decode原型和 rollback实验。
- 可实验 `audio_ctx`，但只有质量/计算基准通过才启用。

DTW + delayed commit 在 API层**可实现**：context init启用 `dtw_token_timestamps`和对应 large-v3/turbo preset，`whisper_full_with_state()` 后读取 token `t_dtw`，结合下一轮 token-ID agreement提交。但它不提供 early stop、不减少 encoder，并有 forced decoder pass且需关闭 Flash Attention。因此应是 feature flag/实验组，不是 Level 2 默认。

Level 2 的边界：不能读取 raw attention，不能做真正 AlignAtt逐 token stop；不能增量 encoder；high-level beam每轮仍重建 self-KV。尽管如此，它已能消除 fuzzy text dedup作为主机制，并达到“persistent embedded backend + rolling contexts + token-level stable commit”。

### Level 3 — SimulStreaming-style, small whisper.cpp patch/fork

最小原型 patch应集中在：

- `include/whisper.h`：只新增 ABI，不改现有函数签名。
- `src/whisper.cpp::whisper_build_graph_decoder()`：复用现有 selected-head `aheads_cross_QKs` path。
- `src/whisper.cpp::whisper_decode_internal()` / `whisper_decode_with_state()`：允许某个新 opt-in decode API请求保留本 token的 alignment heads。
- `src/whisper.cpp` public accessors：返回 shape + caller-owned copy，或更小地只返回经标准 normalize/median/mean后的 last-token peak frame。
- tests/new example：验证 preset、tensor shape、frame index、rollback与旧 ABI行为。

两种 patch设计：

1. **Raw primitive patch**：新增类似 `whisper_decode_with_state_alignment(...)` 与 `whisper_get_alignment_*_from_state(...)`。优点是 upstream diff小、policy在本项目；缺点是应用需自己做 greedy/beam/suppression，且 raw tensor ABI耦合 layout。
2. **Policy callback patch**：在 `whisper_full_with_state()` token loop内部计算 last-token alignment peak，新增 callback返回 continue/stop。优点是复用 upstream beam/logit rules；缺点是侵入 full decoder控制流，diff和回归面更大。

显式 KV API可选增加 `whisper_kv_self_truncate_with_state(state, seq_id, n_past)` 或更窄的 sequence-0 reset。它主要改善语义/测试，不是第一 blocker，因为现有 lower-`n_past` decode已经做同一 removal。不要一开始增加 state clone/save/restore。

若要求 Flash Attention同时输出 raw weights，就不再是小 patch：fused path本来不物化完整 KQ matrix。第一版应明确 `alignment_capture => flash_attn=false`，而不是修改 Metal flash kernels。

CIF不应进入第一版：whisper.cpp public API不暴露 encoder features给外部 CIF layer，SimulStreaming又没有 large-v3 checkpoint，且其当前 flag语义存在冲突。简单“暂缓最后一个词”可由 tokenizer/commit policy完成。

维护成本判断：源码行数可能小，但耦合 `whisper_state` private layout、ggml graph、backend tensor synchronization、DTW masks与Flash分支，**维护负担为中到高**。必须 pin fork commit、每次 upstream rebase跑固定 audio parity/alignment/device suite；若只做 accessor且保持旧 ABI，成本可控；若进入 beam/full控制流或Flash kernels，成本明显上升。

## 10. Recommended Architecture

### 10.1 Compare candidate policies

| Approach | Latency | Transcript stability | Computation | Complexity | iPad suitability | Upstream burden | Robustness / testability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Current overlap + dedup | 首次至少等完整块；边界后处理 | 中；fuzzy可能漏删/误删 | 很差的当前实现：每块重载模型；embedded后仍重算 overlap | 低，已有 | 当前 CLI架构不适合；embedded版本可用 | 无 | text tests多，但与声学证据脱节 |
| 2. LocalAgreement-style | 至少等待下一次 hypothesis确认；由 cadence决定 | 高；共同 token前缀不可逆 | 每次仍完整 encode/decode rolling window | 中 | 好；无 raw attention/特殊 patch | 无 | 很好；token sequence deterministic、易 A/B |
| 3. DTW timestamp + delayed commit | safety horizon增加一定 commit lag | 潜在较高，取决于 alignment可靠性 | 比普通 full更多 forced decode；当前需关闭 Flash | 中 | **Unknown / needs experiment** | 无 | 可测，但 DTW为 experimental、后处理 |
| 4. Full AlignAtt-style | 有潜力低于 LocalAgreement；危险区阈值可调 | 潜在高；阈值/head/model敏感 | 少解 unsafe decoder suffix；encoder仍全重算 | 高 | **Unknown / needs experiment**，尤其 non-Flash attention | 中到高 fork负担 | 需逐 token attention golden tests和实机回归 |
| 5. Hybrid | LocalAgreement为主，时间边界减少错误提交；可选 attention | 高，且可降级 | 默认不付 raw-attention成本；仍重算 encoder | 中 | 最适合分阶段落地 | 默认无；AlignAtt实验才有 | 最好：每个信号可独立关闭、对照 |

### 10.2 Recommendation

推荐 hybrid：

```text
platform audio adapter (macOS sounddevice / iPad AVAudioEngine)
  -> 16 kHz mono Float32 + monotonic sample index
  -> cross-platform StreamingCore (C++ implementation, C ABI)
       owns one whisper_context + one whisper_state
       owns rolling PCM and absolute time mapping
       runs repeated hypothesis updates
       owns static prompt + bounded dynamic prompt tokens
       tracks committed tokens and provisional tokens
       default commit = token-ID LocalAgreement + time safety horizon
       optional signal = public t_dtw
       experimental signal = patched AlignAtt peak
  -> structured events
       HypothesisUpdated(provisional)
       TokensCommitted(append-only)
       SegmentFinalized
       Metrics/Warning/Error
  -> existing controller/UI/store adapters
```

核心 invariants：

- committed token一旦发出永不修改；provisional可完全替换。
- clean transcript只接受 committed events。
- raw evidence保留每轮 hypothesis、token IDs、时间、policy reason和revision；推荐新增 JSONL，同时保留人类可读 raw.txt。
- sample index是时间真相，不从文本 timestamp字符串反推。
- model/context/state只由一个 serial executor访问。
- dynamic prompt从 committed tokens生成并有显式 token budget；static terminology prompt独立保留。
- audio window eviction、token prompt migration与绝对时间 offset必须同一事务更新。
- backend policy不依赖 Python string normalization；语言无关的 token IDs是首选比较单位。

### 10.3 Why not persistent decoder KV across updates by default

新的 audio会重算 encoder和cross-KV；既有 token在每层产生 self-K/V前已经受到旧 cross-attention影响。直接保留旧 self-KV不是无损优化。推荐：同一 encoded window内用 `n_past`增量；audio更新后从 committed/forced prefix批量 rebuild self-KV。只有实验能证明质量等价时才加入选择性复用。

## 11. iPadOS Implications

为了避免先做一套 macOS-only backend再重写：

1. **先定义 portable core boundary。** 音频输入是 `(Float32*, sample_count, absolute_sample_start)`，输出是 token/commit events；不要把 `sounddevice`, temp file, subprocess或Qt type放进 core。
2. **核心用 C++实现、导出纯 C ABI。** whisper.cpp本身就是 C API；C ABI可以由 Python binding和Swift module map共同调用，避免把 algorithm重写成两份。
3. **平台只负责 capture/resample/lifecycle。** macOS现阶段可保留 sounddevice adapter；iPad未来用 AVAudioEngine/AVAudioConverter，向同一 core送 16 kHz mono流。
4. **同一 build source。** macOS library与iOS XCFramework来自同一个 pinned whisper.cpp revision/patch series；runtime manifest从“CLI+dylibs”演化为“library/XCFramework+headers+patch provenance”。
5. **Swift并发模型从现在就镜像。** core session单 owner；Python worker serial queue对应未来 Swift `actor`。Stop/finish必须 drain最后 provisional audio并决定 final commit。
6. **模型下载/验证保持 contract。** iPad把模型放 Application Support/Documents合适目录，下载后继续 exact size/SHA/atomic publish；不要 bundle large model进 App。模型可用性还需加入设备内存/format/quantization准入实验。
7. **UI与backend状态分离。** SwiftUI只订阅 structured events，不参与 dedup/commit；这样 TestFlight UI迭代不会触碰 decoder policy。
8. **先以小模型建立 correctness。** 官方 iOS example建议 tiny/base/small；large-v3/turbo仅在 physical iPad基准通过后开放。模型质量选择与 backend correctness不能绑在同一个 prototype里。
9. **保留 Metal开关和降级。** 默认测试 Metal+Flash；DTW/AlignAtt实验明确记录因关闭 Flash带来的差异。不要把“Metal enabled”误认为“所有算子/策略同样高效”。
10. **不要现在创建 iOS project。** 先完成 C ABI、host tests、XCFramework smoke contract；之后 iPad App只需做 capture/download/UI adapter。

## 12. Risks and Unknowns

| Risk / unknown | Status | Evidence / impact | Minimum resolution |
| --- | --- | --- | --- |
| large-v3/turbo在目标 iPad持续实时 | **Unknown / needs experiment** | 官方 sample只建议 tiny/base/small；当前 model files 3.095 GB/1.625 GB，工作内存更多 | physical device 30–60 min benchmark |
| DTW关闭 Flash后的 Metal代价 | **Unknown / needs experiment** | `whisper_init_with_params_no_state()` 禁止两者并用 | same model/audio A/B，记录 RTF/peak RSS/thermal |
| LocalAgreement commit lag | **Unknown / needs experiment** | 取决于 update cadence、window和两轮 hypothesis稳定度 | parameter grid + WER/CER/revision/lag |
| `n_past` rollback等价性 | **Unknown / needs experiment** | seq_rm路径明确，但无专门 public correctness test | 与 fresh state replay逐 logits比较 |
| audio更新后保留 self-KV是否错误 | **Unknown / needs experiment** | decoder state依赖旧 cross-attention，理论上 stale | changed-audio A/B；默认 rebuild |
| SimulStreaming CIF flags实际语义 | **Unknown / needs experiment** | help与 `load_cif()`/`infer()`分支相反 | 两 flag组合固定 fixture |
| DTW timestamp适合在线 commit吗 | **Unknown / needs experiment** | 它是完成 hypothesis后的 global DTW，不是训练为 commit confidence | 对照人工 word ends和未来 revision |
| smaller PCM window是否省 encoder | **Unknown / needs experiment** | 默认 fixed audio context pad；`audio_ctx`另有质量风险 | timings with PCM length vs `audio_ctx` |
| raw attention patch能否保持小 | **Unknown / needs experiment** | non-Flash private tensor已有；beam/Flash扩展会变大 | greedy non-Flash spike验证，统计 diff/rebase冲突 |
| multilingual token-boundary策略 | **Unknown / needs experiment** | 空格词尾策略不适合中日韩所有情况 | token/Unicode/CJK fixtures，不依赖 space-only truncation |
| long-form context drift/hallucination | **Unknown / needs experiment** | rolling prompt可能放大错误；current denylist有限 | 30–60 min lecture corpus、prompt reset tests |

## 13. Required Experiments

按 gate 顺序执行；前一 gate不通过，不进入后面的 fork工作。

### E1. Embedded parity and lifetime

- 在 current pinned whisper.cpp上做最小 C/C++ harness：context/model只初始化一次，连续处理多个现有 10 秒 overlap PCM块。
- 对比现有 CLI的 token IDs、segment timestamps、文本、encoder/decode timings、process/model-load wall time、peak resident memory。
- 通过条件：结果差异有解释且 session第二/后续调用稳定，无 state leak；不预设速度数字。

### E2. Token LocalAgreement prototype

- 每 0.5/1.0/2.0 秒 update，rolling window 10/20/30 秒做 parameter grid；固定同一模型/音频。
- 每轮显式传 committed prompt tokens；比较连续 hypothesis的最长公共 token前缀，记录 provisional revisions和 commit lag。
- corpus至少覆盖 English、Chinese、Japanese/Korean无空格、数字/专名、停顿、重启、当前 hallucination案例和 chunk-boundary tests对应音频。
- 指标：WER/CER、time-to-first-provisional、time-to-commit、revision rate、RTF、encoder/decode time、queue backlog、peak memory。

### E3. Timestamp/hybrid commit

- 先用普通 public segment/token timestamps建立 safety horizon baseline。
- 再启用正确 model alignment preset + DTW，显式 `flash_attn=false`，读 `t_dtw`。
- 比较 LocalAgreement only、timestamp only、DTW only、hybrid；验证 DTW额外计算是否换来显著稳定性/延迟收益。
- 验证 rolling window offset后 `t_dtw`到absolute sample time的映射。

### E4. `n_past` rollback and cache validity

- 同一 encoder window：decode到 N，降低 `n_past`至 K并重放，逐 token logits与 fresh state从0重放比较。
- 新增音频并重新 encode：比较保留旧 self-KV与全部重建；若不等价，明确禁止跨 update复用。
- 测试 Unicode多 token字符、special tokens、EOT、prompt trim边界。

### E5. AlignAtt spike

- 只做 greedy、single state、non-Flash、一个已知 alignment preset。
- patch公开 last-token selected-head attention peak或raw matrix；与 whisper.cpp DTW forced pass及 SimulStreaming同音频 frame trend对照。
- 实现 near-edge stop + logical last-token drop，不做 CIF、不做 state clone、不改 Flash kernels。
- 只有明显优于 E2/E3且代码/ABI足够小才进入产品化。

### E6. Physical iPad matrix

- 用 XCFramework在至少一个目标 iPad运行；模型从 base/small开始，再测试候选 quantized/large-v3-turbo/large-v3，不能只测 simulator。
- 记录首次加载、稳态 RTF、峰值内存、memory warning/termination、thermal state、耗电趋势、30–60 min memory plateau、后台/中断恢复。
- 分别测试 greedy/beam、Metal on/off、Flash on/off、DTW on/off；不把不同配置的结果混合。

### E7. Long-form and failure semantics

- 超过 30 分钟音频验证 audio buffer、prompt token budget、absolute timestamps、session file增长和 memory bounded。
- Stop during encode、microphone interruption、model load failure、slow inference backlog、final partial、second Start。
- raw hypothesis evidence应能解释每次 commit/reject；clean始终 append-only。

## 14. Concrete Implementation Plan

### Phase 0 — Baseline and contracts

1. 固定 reference audio corpus与现有 CLI输出；给每个 fixture保存 model SHA、whisper.cpp SHA和参数。
2. 定义 `StreamingEvent` schema：session/sample clock、hypothesis revision、token ID/text、relative/absolute time、provisional/committed、policy reason。
3. 定义 C ABI lifecycle：create/load/start/push_audio/poll_or_callback/finish/destroy；错误码和 ownership清晰。
4. 把 current raw/clean evidence contract映射到新事件，不先改 UI。

### Phase 1 — Level 1 embedded backend

1. 新建 portable C++ streaming core wrapper，内部使用 vanilla public C API；先仍执行固定块 full decode。
2. Python adapter替换 `WhisperCppBackend` subprocess，但保留 legacy backend开关用于 A/B。
3. 从 PCM直接调用，不创建 WAV；输出结构化 segment/token。
4. 构建/打包改为 library headers + runtime linkage；同步 pin/provenance与 smoke tests。
5. 跑全量现有 tests + E1；确认只有 transport/lifetime变化。

### Phase 2 — Level 2 token streaming

1. core加入 sample-accurate rolling audio、update cadence与backpressure。
2. 加入 committed/provisional token buffers、static/dynamic prompt budget、context trim。
3. 实现 token-ID LocalAgreement和 final flush；CJK/Unicode boundary不使用纯空格假设。
4. clean改为 committed append；raw增加 per-update structured evidence。
5. 删除新 backend对 exact/fuzzy dedup的依赖，legacy路径仍保留。
6. 跑 E2 与 long-form；选默认 cadence/window/agreement depth。

### Phase 3 — Public alignment experiment, no fork

1. 实现普通 timestamp safety horizon。
2. feature flag启用 DTW preset/t_dtw；强制配置检查避免 `flash_attn=true`时误以为 DTW生效。
3. 跑 E3/E6，决定 DTW保留为 debug/desktop option、iPad option或完全不用。

### Phase 4 — Conditional small fork

1. 完成 E5 raw/peak accessor spike，patch只增 API且默认关闭。
2. 为 tensor shape、head preset、peak frame、n_past rollback、old API parity添加 upstream-style tests。
3. 把 AlignAtt作为可插拔 commit gate，不替换 LocalAgreement fallback。
4. 实机确认 non-Flash成本；未通过则停止 fork路线。
5. 若通过，再评估把 callback集成到 upstream beam loop；不要同时加入 CIF/Flash-kernel改造。

### Phase 5 — iPad port readiness (still no iOS UI in this task)

1. 从同一 source/pin生成 static/dynamic XCFramework，验证 module map和 C ABI。
2. 建立 headless iOS validation harness，只做 load/push/finish和 event assertions。
3. model integrity/download state machine提供 Swift adapter；core不接触 URL/UI。
4. 通过 E6后才创建 SwiftUI/AVAudioEngine app层。

## 15. Files Expected to Change

以下是未来实施范围，不是本次修改。

### live_subtitle_generator likely changes

- 新建 portable native core，例如 `native/streaming_core/include/...`、`native/streaming_core/src/...` 与 C ABI tests。
- `transcription_engine.py`：从 fixed chunk/CLI worker改为 audio updates + structured commit events。
- `stream_transcribe.py`：legacy backend隔离；新 backend不再依赖 WAV/parser/dedup。
- `transcription_controller.py`：适配 provisional/committed/final events，保留状态机。
- `transcript_store.py`：保留 raw/clean，可能新增 hypothesis JSONL；clean只写 committed。
- `settings.py`：新增 streaming/context/commit/DTW/Metal参数；CLI路径不再是核心 preflight。
- `model_manager.py`、`model_integrity.py`：保留 integrity，增加 mobile/quantized compatibility metadata时再改。
- `resource_paths.py`、`packaging/runtime_manifest.json`、bootstrap/package/verify scripts和 PyInstaller specs：从 CLI runtime contract迁移到 embedded library contract。
- `testCodes/`：新增 C API lifecycle、token agreement、rolling buffer、rollback、long-form、event/store、runtime library tests；现有 dedup suites先留作 legacy回归。
- `docs/repo_map.md`、README/packaging docs：实施完成后同步真实架构。

### conditional whisper.cpp fork changes

- `include/whisper.h`
- `src/whisper.cpp`
- 一个 focused test/example（具体路径按 fork时 upstream测试布局确定）
- 不计划首版修改 ggml Metal Flash kernels、Core ML encoder或 model format。

## 16. Recommendation / Go-No-Go

### The six required answers

1. **当前项目与 SimulStreaming 的本质差异是什么？**

   当前项目是互相独立的 fixed overlapping batch ASR，再在文字层修补重复；SimulStreaming是持久模型 + rolling audio/token/prompt state，在每次更新内逐 token decode，用 alignment near-edge stop决定可接纳前缀。SimulStreaming仍会在每次 audio update重算 encoder并重建 KV，不能描述成完整 neural incremental streaming。

2. **哪些逻辑保留，哪些替换？**

   保留 controller lifecycle、single-worker/Stop drain、TranscriptStore/session logging、model manager/SHA transaction、language/settings、raw evidence和保守 hallucination guard。重写 ring/scheduler/resampler边界、raw/clean event semantics和 tests。替换 temp WAV、CLI subprocess/parser、固定 overlap作为唯一策略，以及新 backend主路径的 simple/fuzzy text dedup。

3. **vanilla whisper.cpp 已公开多少所需能力？**

   已公开绝大多数基础构件：persistent context/state、PCM/mel/encode、incremental decode/`n_past`/logits/tokens、prompt context、beam full decode、alignment preset、DTW `t_dtw`、Metal和iOS embedding。它足够做 Level 1 与高质量 Level 2 hybrid；不够无 patch复刻 AlignAtt，因为 raw per-token cross-attention和online attention-stop hook未公开，也没有 incremental encoder/state clone。

4. **最大缺口是 cross-attention、rollback、incremental encoder还是其他？**

   对“实现 AlignAtt policy”，最大直接缺口是 raw cross-attention public access及其与 Flash Attention的冲突；rollback已有 lower-`n_past`隐式路径，不是最大 blocker。对“减少总重复计算”，最大根本缺口是 incremental encoder；即使有 AlignAtt，新增音频仍重算 rolling encoder。另一个关键原则是 audio变化后旧 decoder self-KV可能 stale，不能把 persistent KV当作无条件目标。

5. **不 fork whisper.cpp，最高能升级到什么程度？**

   可以做到 embedded persistent model/state、直接 PCM、rolling audio、bounded static/dynamic prompt tokens、token-ID LocalAgreement、provisional/committed输出、普通/DTW timestamp delayed commit、logical rollback，以及自定义 greedy `n_past` decode实验。做不到 raw-attention-driven early stop、真正 incremental encoder，以及无需重实现的低层 beam AlignAtt。

6. **允许小 patch，值得实现 AlignAtt-style streaming吗？**

   **值得做受控 prototype，不值得现在承诺产品化。** whisper.cpp已有 selected-head attention与large-v3/turbo presets，小型 non-Flash accessor/peak API有现实基础；但 iPad上关闭 Flash的代价、rolling encoder重算、beam integration和upstream维护都未验证。只有它显著优于 no-fork hybrid且physical iPad通过预算，才值得维护。

### Final decision

- **Go now**：Level 1 embedded backend，且核心从第一天按 C++/C ABI跨平台设计。
- **Recommended first product direction**：Level 2 hybrid，token LocalAgreement为默认，时间 safety horizon为辅助；DTW先实验、默认关闭。
- **Do not implement yet**：CIF、Flash-attention weights、state clone/save、incremental encoder、跨 audio update盲目复用 self-KV、完整 SimulStreaming PyTorch移植。
- **First prototype must prove**：同一模型只加载一次的 embedded parity；rolling token LocalAgreement是否在目标语言上降低 revision/重复且保持可接受 commit lag；encoder重算在目标 cadence下的真实成本；physical iPad上 model/Metal/Flash/DTW组合的内存与持续实时性。

总体 Go/No-Go：**Level 1/2 = GO；Level 3 = CONDITIONAL GO；完整复刻 SimulStreaming与incremental encoder = NO-GO for now。**
