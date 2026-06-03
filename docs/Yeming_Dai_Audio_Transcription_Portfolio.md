# Classroom Live Transcriber

## Real-Time On-Device Speech Transcription on Apple Silicon

Yeming Dai  
GitHub: https://github.com/smter6626/live_subtitle_generator  
Portfolio context: xAI "AI Tutor - Chinese" application

## ![image-20260530045041945](/Users/smter-mac/Library/Application Support/typora-user-images/image-20260530045041945.png). Project Overview

Classroom Live Transcriber is a local macOS Apple Silicon desktop application for real-time classroom speech transcription. It targets live learning environments where spoken explanations need to become reviewable text during or shortly after class, while keeping audio processing on the user's machine. The design captures microphone input locally, divides the rolling audio stream into overlapping chunks, runs `whisper.cpp` with Metal acceleration, and stores both raw timestamped output and a conservative clean transcript for later human review.

## 2. Audio Processing Pipeline

```text
Microphone Input
→ Rolling Audio Buffer
→ Overlapping Audio Chunks
→ whisper.cpp + Metal Inference
→ Raw Timestamped Transcript
→ Conservative Boundary Deduplication
→ Clean Transcript for Review
```

The current implementation records mono microphone audio, maintains a rolling buffer, and submits fixed-length chunks with overlap so speech near chunk boundaries is less likely to be lost. Each chunk is resampled for Whisper input, written as temporary PCM audio, and transcribed through the `whisper.cpp` command-line backend. The transcript parser converts backend segment timestamps into absolute session timestamps.

## 3. Core Capabilities

* On-device live transcription
* Apple Silicon Metal acceleration
* English, Chinese, and mixed Chinese-English input modes
* Raw and clean transcript views
* Session-level logs and configuration metadata for reproducibility
* Conservative cleanup designed for human review

## 4. Transcript Quality-Control Methodology

The project separates evidence from cleanup. Raw backend output is preserved in a timestamped transcript so the original recognition result remains available for audit, debugging, and manual correction. The clean transcript is a separate derivative artifact, not a replacement for the raw record.

Cleanup is intentionally narrow. Boundary deduplication targets repeated phrases introduced by overlapping audio windows, using exact and fuzzy overlap checks at chunk boundaries. This reduces duplicate text without applying unrestricted semantic rewriting. A limited high-confidence subtitle-template hallucination filter is applied only to the clean output; filtered text is logged, and the raw transcript remains preserved.

This approach favors reviewability over hidden correction. If text is ambiguous, uncertain, or not covered by a narrow cleanup rule, it should remain visible for a human reviewer rather than being silently rewritten.

## 5. Raw vs. Clean Transcript Example

RAW Sample
[1.01s -> 6.01s] 不会真有人觉得正值青春期的纯情男大真的抵挡魅力人妻的诱惑吧
[6.01s -> 10.01s] 世上最难的考验就是一边是纯情可爱的青梅竹马
[7.01s -> 9.33s] 就是一边是纯情可爱的青梅竹马
[9.33s -> 11.27s] 一边是诱惑拉满的顶级魅魔
[11.27s -> 12.93s] 如果你是这位纯情男大
[12.93s -> 14.45s] 你会做出什么样的选择
[14.45s -> 16.03s] 今天这一部小早不玩
[16.03s -> 17.01s] 就把异地恋里
[14.01s -> 16.01s] 今天这一部小枣不娃
[16.01s -> 18.01s] 就把异地恋里最真实最难堪
[18.01s -> 20.01s] 最不愿承认的人性
[20.01s -> 22.01s] 赤裸裸展现的淋漓尽致
[22.01s -> 24.01s] 故事的开始小枣和男友金
[21.01s -> 22.01s] 故事的开始
[22.01s -> 25.01s] 小枣和男友金是一对特别普通的情侣
[25.01s -> 26.01s] 两人从高中就在一起
[26.01s -> 28.01s] 感情稳定彼此依赖
[28.01s -> 31.01s] 可高考结束后他们却考进了不同大学
[28.01s -> 30.75s] 可高考结束后他们却考进了不同大学
[30.75s -> 33.05s] 小枣留在老家而今去了东京
[33.05s -> 36.43s] 离别前一晚小枣本想将自己的第一次交给男友
[36.43s -> 38.01s] 让这段感情更加牢固
[35.01s -> 36.43s] 自己的第一次交别男友
[36.43s -> 38.17s] 让这段感情更加牢固



CLEAN Sample
[1.01s -> 6.01s] 不会真有人觉得正值青春期的纯情男大真的抵挡魅力人妻的诱惑吧
[6.01s -> 10.01s] 世上最难的考验就是一边是纯情可爱的青梅竹马
[7.01s -> 9.33s] 就是一边是纯情可爱的青梅竹马
[9.33s -> 11.27s] 一边是诱惑拉满的顶级魅魔
[11.27s -> 12.93s] 如果你是这位纯情男大
[12.93s -> 14.45s] 你会做出什么样的选择
[14.45s -> 16.03s] 今天这一部小早不玩
[16.03s -> 17.01s] 就把异地恋里
[14.01s -> 16.01s] 今天这一部小枣不娃
[16.01s -> 18.01s] 就把异地恋里最真实最难堪
[18.01s -> 20.01s] 最不愿承认的人性
[20.01s -> 22.01s] 赤裸裸展现的淋漓尽致
[22.01s -> 24.01s] 故事的开始
[22.01s -> 25.01s] 小枣和男友金是一对特别普通的情侣
[25.01s -> 26.01s] 两人从高中就在一起
[26.01s -> 28.01s] 感情稳定彼此依赖
[28.01s -> 31.01s] 可高考结束后他们却考进了不同大学
[30.75s -> 33.05s] 小枣留在老家而今去了东京
[33.05s -> 36.43s] 离别前一晚小枣本想将自己的第一次交给男友
[36.43s -> 38.01s] 让这段感情更加牢固

## 6. Validation Approach

Repository evidence supports validation of the transcript storage and processing mechanics rather than benchmark claims. Existing tests cover timestamp parsing, session `config.json` generation, raw and clean file appends, English/Chinese/mixed language mapping to `whisper.cpp` arguments, rejection of translate-mode flags, clean-only subtitle-template filtering, final partial chunk handling, stop behavior that preserves queued audio, and boundary-overlap deduplication scenarios.

The project README indicates Apple Silicon is the primary validated environment and the implementation is oriented around `whisper.cpp` with Metal. No benchmark numbers or broad language-variety coverage results are included in the repository evidence reviewed here.

[INSERT MANUAL VALIDATION SUMMARY FROM REAL CLASSROOM OR ANONYMIZED TEST AUDIO, IF AVAILABLE]

## 7. Current Scope

* Validated primarily on macOS Apple Silicon
* Current backend invokes `whisper.cpp` per chunk; a persistent server or native binding may reduce overhead
