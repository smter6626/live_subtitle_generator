import os
import re
import shlex
import shutil
import subprocess
import time
import queue
import threading
import tempfile
import wave
from difflib import SequenceMatcher
from collections import deque
from datetime import datetime

import numpy as np
import sounddevice as sd

# =========================
# 固定配置（按当前基线）
# =========================
BACKEND = os.environ.get("WHISPER_BACKEND", "faster_whisper").strip().lower()
MODEL_NAME = "turbo"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
LANGUAGE = "en"

#SAMPLE_RATE = 16000           # 转写阶段统一按 16k
#CHANNELS = 1                  # 单声道
#BLOCK_SECONDS = 10            # 分块长度
#OVERLAP_SECONDS = 3           # 重叠长度
#RING_BUFFER_SECONDS = 20      # 环形缓冲区长度，必须 > BLOCK_SECONDS + OVERLAP_SECONDS
#这部分内容被修改为：
CAPTURE_RATE = 48000        # 先按你 README 中已验证的默认输入设备采样率固定
TRANSCRIBE_RATE = 16000     # Whisper 输入采样率
CHANNELS = 1
BLOCK_SECONDS = 10
OVERLAP_SECONDS = 3
RING_BUFFER_SECONDS = 30    # 先放大一点，减少边界问题

BEAM_SIZE = 5
VAD_FILTER = True  # Keep current baseline behavior.
MIN_SILENCE_MS = 500

WHISPER_CPP_CLI = os.environ.get("WHISPER_CPP_CLI", "").strip()
WHISPER_CPP_MODEL = os.environ.get("WHISPER_CPP_MODEL", "").strip()
WHISPER_CPP_THREADS = os.environ.get("WHISPER_CPP_THREADS", "").strip()
WHISPER_CPP_EXTRA_ARGS = os.environ.get("WHISPER_CPP_EXTRA_ARGS", "").strip()
WHISPER_CPP_TIMEOUT_SECONDS = float(os.environ.get("WHISPER_CPP_TIMEOUT_SECONDS", "120"))
WHISPER_CPP_TASK = "transcribe"

RUN_START_TIME = datetime.now()
RUN_FILE_PREFIX = (
    f"{RUN_START_TIME.month}_{RUN_START_TIME.day}_"
    f"{RUN_START_TIME.hour}_{RUN_START_TIME.minute}"
)
RAW_OUTPUT_FILE = f"{RUN_FILE_PREFIX}_raw.txt"
CLEAN_OUTPUT_FILE = f"{RUN_FILE_PREFIX}_clean.txt"

OVERLAP_WINDOW_WORDS = 60
OVERLAP_MIN_WORDS = 3
OVERLAP_MIN_CHARS = 12

FUZZY_WINDOW_WORDS = 20
FUZZY_MIN_PREFIX_WORDS = 6
FUZZY_MAX_PREFIX_WORDS = 18
FUZZY_SUFFIX_LEN_DELTA = 2
FUZZY_TAIL_EXACT_WORDS = 2
FUZZY_MIN_SHARED_CONTENT_WORDS = 3
FUZZY_SCORE_THRESHOLD = 0.88
FUZZY_EDIT_SIM_THRESHOLD = 0.84
FUZZY_BIGRAM_THRESHOLD = 0.45
FUZZY_CONTENT_OVERLAP_THRESHOLD = 0.70
FUZZY_DEBUG_NEAR_THRESHOLD = 0.75
# If fuzzy overlap still misses after contraction expansion, try:
# FUZZY_SCORE_THRESHOLD = 0.85 and FUZZY_BIGRAM_THRESHOLD = 0.45

# Keep ASCII words intact so contraction handling and existing English overlap
# behavior stay stable.  The Unicode-letter alternative deliberately emits one
# character per token: Japanese, Chinese, and Korean transcripts often have no
# spaces, and a whole sentence must not become one non-overlappable token.
TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['`][A-Za-z0-9]+)*|[^\W\d_]", re.UNICODE)
TIMESTAMP_TAG_RE = re.compile(r"\[\d+(?:\.\d+)?s\s*->\s*\d+(?:\.\d+)?s\]")
WHISPER_CPP_SEGMENT_RE = re.compile(
    r"\[(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\]\s*(?P<text>.+)"
)
WHITESPACE_RE = re.compile(r"\s+")
PUNCT_TO_SPACE_TABLE = str.maketrans(
    {
        ".": " ",
        ",": " ",
        "?": " ",
        "!": " ",
        ";": " ",
        ":": " ",
        '"': " ",
        "(": " ",
        ")": " ",
    }
)
PUNCT_DROP_TABLE = str.maketrans({"'": "", "`": ""})
COMMON_CONTRACTIONS_FOR_COMPARE = {
    "we'll": "we will",
    "i'll": "i will",
    "you'll": "you will",
    "they'll": "they will",
    "we're": "we are",
    "you're": "you are",
    "they're": "they are",
    "i'm": "i am",
    "it's": "it is",
    "that's": "that is",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "can't": "cannot",
    "couldn't": "could not",
    "won't": "will not",
    "wouldn't": "would not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "haven't": "have not",
    "hasn't": "has not",
    "hadn't": "had not",
    "we've": "we have",
    "i've": "i have",
    "they've": "they have",
    "you'd": "you would",
    "we'd": "we would",
    "they'd": "they would",
}

# 每次新块相对于上一次起点前进 7 秒（10 秒块，3 秒重叠）
STEP_SECONDS = BLOCK_SECONDS - OVERLAP_SECONDS

# 环形缓冲区总采样点数
# RING_BUFFER_SAMPLES = int(RING_BUFFER_SECONDS * SAMPLE_RATE)
# 这部分内容被修改为：
RING_BUFFER_SAMPLES = int(RING_BUFFER_SECONDS * CAPTURE_RATE)

# 当前录音累计的总秒数
total_audio_seconds = 0.0

# 用于存放最新音频的环形缓冲区
audio_buffer = deque(maxlen=RING_BUFFER_SAMPLES)

# 转写任务队列
task_queue = queue.Queue()

# 停止标志
stop_event = threading.Event()

# 最近一次已提交块的“起始时间”
last_chunk_start = None

# 最近一次输出的文本，用于简单去重
last_output_text = ""


def audio_callback(indata, frames, time_info, status):
    global total_audio_seconds
    if status:
        print(f"[Audio Status] {status}")
    mono = indata[:, 0]
    audio_buffer.extend(mono.tolist())
    # total_audio_seconds += frames / SAMPLE_RATE
    # 这段被修改为：
    total_audio_seconds += frames / CAPTURE_RATE


def simple_dedup(new_text, old_text):
    if not new_text or not new_text.strip():
        return ""

    if not old_text or not old_text.strip():
        return new_text

    overlap_words, overlap_chars, cut_index = find_overlap_and_cut_index(old_text, new_text)
    if overlap_words == 0 or cut_index is None:
        return new_text

    trimmed = new_text[cut_index:].lstrip()
    trimmed = _preserve_line_timestamp(new_text, trimmed, cut_index)

    print(
        f"[Dedup] Overlap matched: words={overlap_words}, chars={overlap_chars}, "
        f"trimmed={'yes' if trimmed else 'all'}"
    )
    return trimmed


def normalize_for_compare(text: str) -> str:
    # Normalize only for comparison; original text remains untouched.
    normalized = text.lower().strip()
    normalized = normalized.translate(PUNCT_TO_SPACE_TABLE)
    normalized = normalized.translate(PUNCT_DROP_TABLE)
    normalized = WHITESPACE_RE.sub(" ", normalized)
    return normalized.strip()


def expand_common_contractions_for_compare(token: str):
    normalized_token = token.lower().replace("`", "'")
    expanded = COMMON_CONTRACTIONS_FOR_COMPARE.get(normalized_token)
    if expanded is None:
        return [token]
    return expanded.split()


def tokenize_for_compare(text: str, skip_timestamps: bool = False):
    timestamp_spans = []
    if skip_timestamps:
        timestamp_spans = [match.span() for match in TIMESTAMP_TAG_RE.finditer(text)]

    def in_timestamp(pos: int) -> bool:
        for start, end in timestamp_spans:
            if start <= pos < end:
                return True
        return False

    tokens = []
    token_spans = []
    for match in TOKEN_RE.finditer(text):
        if skip_timestamps and in_timestamp(match.start()):
            continue

        for expanded_token in expand_common_contractions_for_compare(match.group(0)):
            token = normalize_for_compare(expanded_token)
            if token:
                tokens.append(token)
                token_spans.append((match.start(), match.end()))

    return tokens, token_spans


def find_overlap_and_cut_index(old_text: str, new_text: str):
    # Compare old tail vs new head in normalized word space.
    old_tokens, _ = tokenize_for_compare(old_text, skip_timestamps=True)
    new_tokens, new_spans = tokenize_for_compare(new_text, skip_timestamps=True)

    if not old_tokens or not new_tokens:
        return 0, 0, None

    old_tail = old_tokens[-OVERLAP_WINDOW_WORDS:]
    new_head = new_tokens[:OVERLAP_WINDOW_WORDS]
    max_overlap = min(len(old_tail), len(new_head))

    for overlap_words in range(max_overlap, 0, -1):
        if old_tail[-overlap_words:] != new_head[:overlap_words]:
            continue

        overlap_chars = len(" ".join(new_head[:overlap_words]))
        reliable = (
            overlap_words >= OVERLAP_MIN_WORDS
            or overlap_chars >= OVERLAP_MIN_CHARS
        )
        if not reliable:
            continue

        if overlap_words >= len(new_spans):
            return overlap_words, overlap_chars, len(new_text)

        cut_index = new_spans[overlap_words][0]
        return overlap_words, overlap_chars, cut_index

    return 0, 0, None


def build_ngrams(tokens, n):
    if n <= 0 or len(tokens) < n:
        return set()
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def normalized_edit_similarity(a_tokens, b_tokens):
    if not a_tokens or not b_tokens:
        return 0.0
    a_text = " ".join(a_tokens)
    b_text = " ".join(b_tokens)
    return SequenceMatcher(None, a_text, b_text).ratio()


def content_word_tokens(tokens):
    # Conservative heuristic: keep alnum tokens with length >= 4 as content words.
    return [token for token in tokens if token.isalnum() and len(token) >= 4]


def boundary_similarity_score(old_suffix_tokens, new_prefix_tokens):
    edit_similarity = normalized_edit_similarity(old_suffix_tokens, new_prefix_tokens)

    old_bigrams = build_ngrams(old_suffix_tokens, 2)
    new_bigrams = build_ngrams(new_prefix_tokens, 2)
    if old_bigrams and new_bigrams:
        bigram_overlap = len(old_bigrams & new_bigrams) / max(len(old_bigrams), len(new_bigrams))
    else:
        bigram_overlap = 0.0

    old_content = set(content_word_tokens(old_suffix_tokens))
    new_content = set(content_word_tokens(new_prefix_tokens))
    shared_content_words = len(old_content & new_content)
    if old_content and new_content:
        content_overlap = shared_content_words / max(len(old_content), len(new_content))
    else:
        content_overlap = 0.0

    old_unigrams = set(old_suffix_tokens)
    new_unigrams = set(new_prefix_tokens)
    union_size = len(old_unigrams | new_unigrams)
    if union_size:
        unigram_jaccard = len(old_unigrams & new_unigrams) / union_size
    else:
        unigram_jaccard = 0.0

    # Weighted score keeps precision high by requiring multiple signals.
    score = (
        0.45 * edit_similarity
        + 0.25 * bigram_overlap
        + 0.20 * content_overlap
        + 0.10 * unigram_jaccard
    )

    return {
        "score": score,
        "edit_similarity": edit_similarity,
        "bigram_overlap": bigram_overlap,
        "content_overlap": content_overlap,
        "shared_content_words": shared_content_words,
        "unigram_jaccard": unigram_jaccard,
    }


def _preserve_line_timestamp(original_text: str, trimmed_text: str, cut_index: int) -> str:
    if not trimmed_text:
        return trimmed_text

    if TIMESTAMP_TAG_RE.match(trimmed_text):
        return trimmed_text

    line_start = original_text.rfind("\n", 0, cut_index) + 1
    line_end = original_text.find("\n", line_start)
    if line_end == -1:
        line_end = len(original_text)

    line_text = original_text[line_start:line_end]
    line_timestamp = TIMESTAMP_TAG_RE.match(line_text)
    if line_timestamp is not None:
        return f"{line_timestamp.group(0)} {trimmed_text}"

    return trimmed_text


def fuzzy_boundary_dedup(old_text: str, new_text: str) -> str:
    if not new_text or not new_text.strip():
        return ""
    if not old_text or not old_text.strip():
        return new_text

    old_tokens, _ = tokenize_for_compare(old_text, skip_timestamps=True)
    new_tokens, new_spans = tokenize_for_compare(new_text, skip_timestamps=True)
    if not old_tokens or not new_tokens:
        return new_text

    old_tail = old_tokens[-FUZZY_WINDOW_WORDS:]
    new_head_tokens = new_tokens[:FUZZY_WINDOW_WORDS]
    new_head_spans = new_spans[:FUZZY_WINDOW_WORDS]

    max_prefix_words = min(len(new_head_tokens), len(old_tail), FUZZY_MAX_PREFIX_WORDS)
    if max_prefix_words < FUZZY_MIN_PREFIX_WORDS:
        return new_text

    best_near_miss = None

    for prefix_words in range(max_prefix_words, FUZZY_MIN_PREFIX_WORDS - 1, -1):
        new_prefix = new_head_tokens[:prefix_words]
        min_suffix_words = max(FUZZY_MIN_PREFIX_WORDS, prefix_words - FUZZY_SUFFIX_LEN_DELTA)
        max_suffix_words = min(len(old_tail), prefix_words + FUZZY_SUFFIX_LEN_DELTA)

        best_metrics = None
        for suffix_words in range(max_suffix_words, min_suffix_words - 1, -1):
            old_suffix = old_tail[-suffix_words:]
            metrics = boundary_similarity_score(old_suffix, new_prefix)

            tail_words = min(FUZZY_TAIL_EXACT_WORDS, len(old_suffix), len(new_prefix))
            tail_aligned = (
                tail_words == 0 or old_suffix[-tail_words:] == new_prefix[-tail_words:]
            )

            is_near_miss = (
                metrics["score"] >= FUZZY_DEBUG_NEAR_THRESHOLD
                or metrics["edit_similarity"] >= FUZZY_DEBUG_NEAR_THRESHOLD
            )
            if is_near_miss:
                candidate = {
                    "prefix_words": prefix_words,
                    "suffix_words": suffix_words,
                    "score": metrics["score"],
                    "edit_similarity": metrics["edit_similarity"],
                    "bigram_overlap": metrics["bigram_overlap"],
                    "content_overlap": metrics["content_overlap"],
                    "shared_content_words": metrics["shared_content_words"],
                }
                if (
                    best_near_miss is None
                    or candidate["score"] > best_near_miss["score"]
                    or (
                        candidate["score"] == best_near_miss["score"]
                        and candidate["edit_similarity"] > best_near_miss["edit_similarity"]
                    )
                ):
                    best_near_miss = candidate

            is_reliable = (
                tail_aligned
                and metrics["edit_similarity"] >= FUZZY_EDIT_SIM_THRESHOLD
                and metrics["bigram_overlap"] >= FUZZY_BIGRAM_THRESHOLD
                and metrics["content_overlap"] >= FUZZY_CONTENT_OVERLAP_THRESHOLD
                and metrics["shared_content_words"] >= FUZZY_MIN_SHARED_CONTENT_WORDS
                and (
                    metrics["score"] >= FUZZY_SCORE_THRESHOLD
                    # Conservative backup path: allow high-confidence candidates
                    # that fail the weighted score by a small margin.
                    or (
                        prefix_words >= 8
                        and metrics["edit_similarity"] >= 0.90
                        and metrics["bigram_overlap"] >= 0.70
                        and metrics["content_overlap"] >= 0.80
                        and metrics["shared_content_words"] >= 5
                    )
                )
            )
            if is_reliable:
                best_metrics = metrics
                break

        if best_metrics is None:
            continue

        if prefix_words >= len(new_head_spans):
            cut_index = len(new_text)
        else:
            cut_index = new_head_spans[prefix_words][0]

        trimmed = new_text[cut_index:].lstrip()
        trimmed = _preserve_line_timestamp(new_text, trimmed, cut_index)
        print(
            f"[FuzzyDedup] matched_prefix_words={prefix_words} "
            f"score={best_metrics['score']:.2f} "
            f"edit={best_metrics['edit_similarity']:.2f} "
            f"bigram={best_metrics['bigram_overlap']:.2f} "
            f"content={best_metrics['content_overlap']:.2f} "
            f"trimmed={'yes' if trimmed else 'all'}"
        )
        return trimmed

    if best_near_miss is not None:
        print(
            f"[FuzzyDedupDebug] best_near_match "
            f"prefix={best_near_miss['prefix_words']} "
            f"suffix={best_near_miss['suffix_words']} "
            f"score={best_near_miss['score']:.2f} "
            f"edit={best_near_miss['edit_similarity']:.2f} "
            f"bigram={best_near_miss['bigram_overlap']:.2f} "
            f"content={best_near_miss['content_overlap']:.2f} "
            f"shared={best_near_miss['shared_content_words']}"
        )

    return new_text


def resample_audio(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return audio.astype(np.float32, copy=False)

    if audio.size == 0:
        return np.array([], dtype=np.float32)

    src_len = audio.shape[0]
    dst_len = int(round(src_len * dst_rate / src_rate))
    if dst_len <= 0:
        return np.array([], dtype=np.float32)

    src_idx = np.arange(src_len, dtype=np.float32)
    dst_idx = np.linspace(0, src_len - 1, num=dst_len, dtype=np.float32)
    resampled = np.interp(dst_idx, src_idx, audio).astype(np.float32)
    return resampled


class FasterWhisperBackend:
    name = "faster_whisper"

    def __init__(self):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type=COMPUTE_TYPE)

    @staticmethod
    def availability():
        try:
            import faster_whisper  # noqa: F401
        except Exception as exc:
            return False, f"faster-whisper import failed: {exc}"
        return True, "faster-whisper import ok"

    def transcribe_chunk(self, audio_16k: np.ndarray, chunk_start_time: float):
        segments, info = self.model.transcribe(
            audio_16k,
            language=LANGUAGE,
            beam_size=BEAM_SIZE,
            vad_filter=VAD_FILTER,
            vad_parameters=dict(min_silence_duration_ms=MIN_SILENCE_MS),
        )

        lines = []
        for seg in segments:
            abs_start = chunk_start_time + seg.start
            abs_end = chunk_start_time + seg.end
            text = seg.text.strip()
            if text:
                lines.append(f"[{abs_start:.2f}s -> {abs_end:.2f}s] {text}")
        return lines


class WhisperCppBackend:
    name = "whisper_cpp"

    def __init__(
        self,
        cli_path: str = WHISPER_CPP_CLI,
        model_path: str = WHISPER_CPP_MODEL,
        threads: str = WHISPER_CPP_THREADS,
        extra_args: str = WHISPER_CPP_EXTRA_ARGS,
        timeout_seconds: float = WHISPER_CPP_TIMEOUT_SECONDS,
        beam_size: int = BEAM_SIZE,
        language_code: str = LANGUAGE,
        task: str = WHISPER_CPP_TASK,
        initial_prompt: str = "",
    ):
        self.cli_path = self._resolve_cli(cli_path)
        self.model_path = model_path
        self.threads = threads
        self.extra_args = extra_args
        self.timeout_seconds = timeout_seconds
        self.beam_size = beam_size
        self.language_code = language_code
        self.task = task
        self.initial_prompt = initial_prompt
        self.last_result_info = {}

        ok, message = self.availability()
        if not ok:
            raise RuntimeError(message)

    @staticmethod
    def _resolve_cli(cli_path: str):
        if cli_path:
            resolved = shutil.which(cli_path) if os.path.basename(cli_path) == cli_path else cli_path
            return resolved
        return shutil.which("whisper-cli")

    def availability(self):
        if not self.cli_path:
            return (
                False,
                "whisper.cpp CLI not found. Set WHISPER_CPP_CLI to whisper-cli or an absolute path.",
            )
        if not os.path.exists(self.cli_path) and shutil.which(self.cli_path) is None:
            return False, f"whisper.cpp CLI not found: {self.cli_path}"
        if not self.model_path:
            return False, "WHISPER_CPP_MODEL is required for WHISPER_BACKEND=whisper_cpp."
        if not os.path.exists(self.model_path):
            return False, f"whisper.cpp model file not found: {self.model_path}"
        return True, f"whisper.cpp cli={self.cli_path} model={self.model_path}"

    def transcribe_chunk(self, audio_16k: np.ndarray, chunk_start_time: float):
        with tempfile.TemporaryDirectory(prefix="whisper_cpp_chunk_") as tmp_dir:
            wav_path = os.path.join(tmp_dir, "chunk.wav")
            write_pcm16_wav(wav_path, audio_16k, TRANSCRIBE_RATE)

            cmd = build_whisper_cpp_command(
                cli_path=self.cli_path,
                model_path=self.model_path,
                wav_path=wav_path,
                language_code=self.language_code,
                beam_size=self.beam_size,
                threads=self.threads,
                extra_args=self.extra_args,
                task=self.task,
                initial_prompt=self.initial_prompt,
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )

        output = f"{result.stdout}\n{result.stderr}"
        segment_candidates = count_whisper_cpp_segments(output)
        lines = parse_whisper_cpp_output(output, chunk_start_time)
        self.last_result_info = {
            "returncode": result.returncode,
            "safe_command": render_safe_whisper_cpp_command(cmd),
            "stdout_lines": len(result.stdout.splitlines()),
            "stderr_lines": len(result.stderr.splitlines()),
            "segment_candidates_before_parse": segment_candidates,
            "segments_after_parse": len(lines),
        }
        if result.returncode != 0:
            raise RuntimeError(
                "whisper.cpp CLI failed with exit code "
                f"{result.returncode}.\nCommand: {render_safe_whisper_cpp_command(cmd)}\n"
                f"STDOUT:\n{result.stdout[-2000:]}\nSTDERR:\n{result.stderr[-2000:]}"
            )

        return lines


def build_whisper_cpp_command(
    cli_path: str,
    model_path: str,
    wav_path: str,
    language_code: str,
    beam_size: int,
    threads: str = "",
    extra_args: str = "",
    task: str = WHISPER_CPP_TASK,
    initial_prompt: str = "",
):
    if task != "transcribe":
        raise ValueError(f"Unsupported whisper.cpp task: {task!r}. Only 'transcribe' is allowed.")

    cmd = [
        cli_path,
        "-m",
        model_path,
        "-f",
        wav_path,
        "-l",
        language_code,
        "-bs",
        str(beam_size),
    ]
    if threads:
        cmd.extend(["-t", str(threads)])
    if extra_args:
        split_args = shlex.split(extra_args)
        forbidden_translate_flags = {"-tr", "--translate"}
        if any(arg in forbidden_translate_flags or arg.startswith("--translate=") for arg in split_args):
            raise ValueError("Translate mode is not allowed; this app only runs transcription.")
        cmd.extend(split_args)
    return cmd


def render_safe_whisper_cpp_command(cmd):
    safe_cmd = []
    replace_next_file = False
    for arg in cmd:
        if replace_next_file:
            safe_cmd.append("<chunk.wav>")
            replace_next_file = False
            continue

        safe_cmd.append(str(arg))
        if arg in ("-f", "--file"):
            replace_next_file = True

    return shlex.join(safe_cmd)


def count_whisper_cpp_segments(output: str) -> int:
    return sum(1 for line in output.splitlines() if WHISPER_CPP_SEGMENT_RE.search(line))


def write_pcm16_wav(path: str, audio_16k: np.ndarray, sample_rate: int):
    audio = np.asarray(audio_16k, dtype=np.float32)
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)

    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm16.tobytes())


def parse_whisper_cpp_timestamp(value: str) -> float:
    normalized = value.strip().replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"Unsupported whisper.cpp timestamp: {value}")


def parse_whisper_cpp_output(output: str, chunk_start_time: float):
    lines = []
    for raw_line in output.splitlines():
        match = WHISPER_CPP_SEGMENT_RE.search(raw_line)
        if not match:
            continue

        text = match.group("text").strip()
        if not text:
            continue

        rel_start = parse_whisper_cpp_timestamp(match.group("start"))
        rel_end = parse_whisper_cpp_timestamp(match.group("end"))
        abs_start = chunk_start_time + rel_start
        abs_end = chunk_start_time + rel_end
        lines.append(f"[{abs_start:.2f}s -> {abs_end:.2f}s] {text}")
    return lines


def create_transcription_backend():
    if BACKEND in ("faster_whisper", "faster-whisper"):
        return FasterWhisperBackend()
    if BACKEND in ("whisper_cpp", "whisper-cpp", "whisper.cpp"):
        return WhisperCppBackend()
    raise ValueError(
        f"Unsupported WHISPER_BACKEND={BACKEND!r}. "
        "Use 'faster_whisper' or 'whisper_cpp'."
    )


def transcription_worker():
    global last_output_text

    print(f"[Worker] Loading transcription backend: {BACKEND}")
    try:
        backend = create_transcription_backend()
    except Exception as exc:
        print(f"[Worker] Failed to load backend: {exc}")
        stop_event.set()
        return
    print(f"[Worker] Backend loaded: {backend.name}")

    while not stop_event.is_set():
        try:
            task = task_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if task is None:
            break

        chunk_audio, chunk_start_time, chunk_end_time = task

        print(f"[Worker] Transcribing chunk {chunk_start_time:.1f}s -> {chunk_end_time:.1f}s")
        chunk_audio_16k = resample_audio(chunk_audio, CAPTURE_RATE, TRANSCRIBE_RATE)
        print(
            f"[Worker] Resampled {len(chunk_audio)} samples @ {CAPTURE_RATE}Hz "
            f"-> {len(chunk_audio_16k)} samples @ {TRANSCRIBE_RATE}Hz"
        )

        if len(chunk_audio_16k) == 0:
            print("[Worker] Empty chunk after resampling; skipped.")
            task_queue.task_done()
            continue

        try:
            lines = backend.transcribe_chunk(chunk_audio_16k, chunk_start_time)
        except Exception as exc:
            print(f"[Worker] Backend transcription failed: {exc}")
            task_queue.task_done()
            continue

        if lines:
            combined = "\n".join(lines)
            with open(RAW_OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(combined + "\n")
            print(f"[Worker] Wrote raw transcript chunk to {RAW_OUTPUT_FILE}")

            stage1 = simple_dedup(combined, last_output_text)
            stage2 = fuzzy_boundary_dedup(last_output_text, stage1)

            if stage2:
                with open(CLEAN_OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(stage2 + "\n")
                print(f"[Worker] Wrote clean transcript chunk to {CLEAN_OUTPUT_FILE}")
                last_output_text += "\n" + stage2
            else:
                print("[Worker] Chunk recognized but fully overlapped; skipped clean writing.")
        else:
            print("[Worker] No valid text recognized in this chunk.")

        task_queue.task_done()


def maybe_submit_chunk():
    global last_chunk_start

    # 至少需要累计到一个完整块长度
    if total_audio_seconds < BLOCK_SECONDS:
        return

    if last_chunk_start is None:
        candidate_start = 0.0
    else:
        candidate_start = last_chunk_start + STEP_SECONDS

    candidate_end = candidate_start + BLOCK_SECONDS

    # 如果总录音时长还不够覆盖这个块，就不提交
    if total_audio_seconds < candidate_end:
        return

    # 从 ring buffer 里取“最近 RING_BUFFER_SECONDS 内”的音频
    buffer_array = np.array(audio_buffer, dtype=np.float32)

    # ring buffer 覆盖的绝对时间范围
    buffer_end_time = total_audio_seconds
    buffer_start_time = max(0.0, buffer_end_time - len(buffer_array) / CAPTURE_RATE)

    # 调试输出
    print(f"[Debug] total_audio_seconds={total_audio_seconds:.2f}")
    print(
        f"[Debug] buffer_start_time={buffer_start_time:.2f}, "
        f"buffer_end_time={buffer_end_time:.2f}, "
        f"candidate_start={candidate_start:.2f}, "
        f"candidate_end={candidate_end:.2f}, "
        f"buffer_len={len(buffer_array)}"
    )

    EPSILON = 0.05  # 50ms 容差

    # 目标 chunk 必须落在当前 buffer 覆盖范围内
    if candidate_start < buffer_start_time:
        drift = buffer_start_time - candidate_start

        if drift <= EPSILON:
            print(
                f"[Main] Small drift detected ({drift:.3f}s). "
                f"Clamping candidate_start to buffer_start_time."
            )
        else:
            print(
                f"[Main] Warning: candidate chunk fell out of ring buffer window "
                f"by {drift:.3f}s. Re-aligning to buffer start."
            )

        candidate_start = buffer_start_time
        candidate_end = candidate_start + BLOCK_SECONDS

        # 重对齐后如果总录音时长还不够覆盖这个块，就先等下一轮
        if total_audio_seconds < candidate_end:
            return

    start_idx = int((candidate_start - buffer_start_time) * CAPTURE_RATE)
    end_idx = int((candidate_end - buffer_start_time) * CAPTURE_RATE)

    chunk_audio = buffer_array[start_idx:end_idx]

    expected_samples = int(BLOCK_SECONDS * CAPTURE_RATE)
    if len(chunk_audio) != expected_samples:
        print(f"[Main] Warning: chunk length mismatch ({len(chunk_audio)} vs {expected_samples})")
        return

    task_queue.put((chunk_audio, candidate_start, candidate_end))
    print(f"[Main] Submitted chunk {candidate_start:.2f}s -> {candidate_end:.2f}s")
    last_chunk_start = candidate_start


def main():
    print("=== Streaming transcription test started ===")
    print(f"Raw output file: {RAW_OUTPUT_FILE}")
    print(f"Clean output file: {CLEAN_OUTPUT_FILE}")
    print("Press Ctrl+C to stop.\n")

    # 初始化本次运行输出文件
    for output_file in (RAW_OUTPUT_FILE, CLEAN_OUTPUT_FILE):
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("")

    worker = threading.Thread(target=transcription_worker, daemon=True)
    worker.start()

    try:
        with sd.InputStream(
            #samplerate=SAMPLE_RATE,
            #这句被替换为：
            samplerate=CAPTURE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=audio_callback,
            blocksize=0,
        ):
            print("[Main] Microphone stream opened.")
            while not stop_event.is_set():
                time.sleep(0.5)
                maybe_submit_chunk()

    except KeyboardInterrupt:
        print("\n[Main] Stopping...")
    finally:
        stop_event.set()
        task_queue.put(None)
        worker.join(timeout=5)
        print("[Main] Exited cleanly.")


if __name__ == "__main__":
    main()
