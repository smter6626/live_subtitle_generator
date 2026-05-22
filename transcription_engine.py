import queue
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

from settings import (
    HALLUCINATION_DENYLIST,
    HALLUCINATION_FILTER_MODE,
    TranscriptionSettings,
)
from stream_transcribe import (
    BLOCK_SECONDS,
    CAPTURE_RATE,
    CHANNELS,
    RING_BUFFER_SECONDS,
    STEP_SECONDS,
    TRANSCRIBE_RATE,
    WhisperCppBackend,
    build_whisper_cpp_command,
    fuzzy_boundary_dedup,
    render_safe_whisper_cpp_command,
    resample_audio,
    simple_dedup,
)
from transcript_store import TranscriptStore

FINAL_PARTIAL_MIN_SECONDS = 2.0
FINAL_PARTIAL_MIN_RMS = 0.0015


def audio_rms(audio) -> float:
    audio_array = np.asarray(audio, dtype=np.float32)
    if len(audio_array) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio_array))))


def filter_clean_hallucinations(lines):
    kept_lines = []
    filtered = []
    for line in lines:
        matched_pattern = next(
            (pattern for pattern in HALLUCINATION_DENYLIST if pattern in line),
            None,
        )
        if matched_pattern:
            filtered.append({"line": line, "pattern": matched_pattern})
        else:
            kept_lines.append(line)
    return kept_lines, filtered


class TranscriptionEngine:
    def __init__(
        self,
        settings: TranscriptionSettings,
        store: TranscriptStore,
        event_callback=None,
    ):
        self.settings = settings.normalized()
        self.store = store
        self.event_callback = event_callback

        self.total_audio_seconds = 0.0
        self.audio_buffer = deque(maxlen=int(RING_BUFFER_SECONDS * CAPTURE_RATE))
        self.task_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.last_chunk_start = None
        self.last_output_text = ""

        self.capture_thread = None
        self.worker_thread = None
        self.started_at = None
        self._closed = False

    def start(self):
        self.started_at = time.time()
        self._emit("log", message="Starting transcription engine.")
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="transcription-worker",
            daemon=True,
        )
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            name="audio-capture",
            daemon=True,
        )
        self.worker_thread.start()
        self.capture_thread.start()

    def stop(self):
        self._emit("log", message="Stopping transcription engine.")
        self.stop_event.set()

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=5)

        self._submit_final_partial_chunk()
        pending_tasks = self.task_queue.qsize()
        self.task_queue.put(None)
        self._emit_queue_size()

        if self.worker_thread and self.worker_thread.is_alive():
            drain_timeout = max(
                180,
                (pending_tasks + 1) * (self.settings.block_seconds + 130) + 30,
            )
            self._log(
                "Finishing transcription for queued audio "
                f"({pending_tasks} pending task(s))."
            )
            self.worker_thread.join(timeout=drain_timeout)
            if self.worker_thread.is_alive():
                self._log(
                    "Worker did not finish before the stop timeout.",
                    level="WARNING",
                )

        self.store.log("Stop complete.")
        self.store.close()
        self._closed = True
        self._emit("stopped", message="Stop complete.")

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            self._log(f"Audio status: {status}", level="WARNING")
        mono = indata[:, 0]
        self.audio_buffer.extend(mono.tolist())
        self.total_audio_seconds += frames / CAPTURE_RATE

    def _capture_loop(self):
        try:
            with sd.InputStream(
                samplerate=CAPTURE_RATE,
                channels=CHANNELS,
                dtype="float32",
                callback=self.audio_callback,
                blocksize=0,
            ):
                self._log("Microphone stream opened.")
                self._emit("recording")
                while not self.stop_event.is_set():
                    time.sleep(0.5)
                    self._maybe_submit_chunk()
        except Exception as exc:
            self._emit_error(f"Audio capture failed: {exc}")
            self.stop_event.set()
        finally:
            self._log("Microphone stream closed.")

    def _worker_loop(self):
        try:
            self._log("Initializing whisper.cpp backend.")
            backend = WhisperCppBackend(
                cli_path=str(self.settings.whisper_cpp_cli),
                model_path=str(self.settings.whisper_cpp_model),
                beam_size=self.settings.beam_size,
                language_code=self.settings.whisper_language_code,
                task=self.settings.task,
                initial_prompt=self.settings.prompt_used,
            )
            self._log(
                "Backend ready: "
                f"{self.settings.backend_display}, {self.settings.model_display}, "
                f"beam={self.settings.beam_size}, "
                f"language={self.settings.original_language_label}, "
                f"task={self.settings.task}."
            )
            self._log(f"whisper-cli language: {self.settings.whisper_language_code}")
            self._log(f"whisper-cli prompt_used: {self.settings.prompt_used or '<none>'}")
            self._log(
                "hallucination_filter: "
                f"mode={HALLUCINATION_FILTER_MODE}, "
                f"denylist_count={len(HALLUCINATION_DENYLIST)}."
            )
            safe_command = render_safe_whisper_cpp_command(
                build_whisper_cpp_command(
                    cli_path=str(self.settings.whisper_cpp_cli),
                    model_path=str(self.settings.whisper_cpp_model),
                    wav_path="<chunk.wav>",
                    language_code=self.settings.whisper_language_code,
                    beam_size=self.settings.beam_size,
                    task=self.settings.task,
                    initial_prompt=self.settings.prompt_used,
                )
            )
            self._log(f"whisper-cli command template: {safe_command}")
        except Exception as exc:
            self._emit_error(f"Backend initialization failed: {exc}")
            self.stop_event.set()
            return

        while True:
            try:
                task = self.task_queue.get(timeout=0.5)
            except queue.Empty:
                if self.stop_event.is_set():
                    continue
                continue

            if task is None:
                self.task_queue.task_done()
                break

            chunk_audio, chunk_start_time, chunk_end_time = task
            self._emit_queue_size()
            self._log(
                f"Transcribing chunk {chunk_start_time:.2f}s -> {chunk_end_time:.2f}s."
            )
            self._log(
                "whisper-cli chunk call: "
                f"chunk_start={chunk_start_time:.2f}, "
                f"chunk_end={chunk_end_time:.2f}, "
                f"duration={chunk_end_time - chunk_start_time:.2f}, "
                f"language={self.settings.whisper_language_code}, "
                f"prompt_used={'yes' if self.settings.prompt_used else 'no'}."
            )

            try:
                chunk_audio_16k = resample_audio(
                    chunk_audio,
                    CAPTURE_RATE,
                    TRANSCRIBE_RATE,
                )
                if len(chunk_audio_16k) == 0:
                    self._log("Empty chunk after resampling; skipped.", level="WARNING")
                    self.task_queue.task_done()
                    continue

                raw_lines = backend.transcribe_chunk(chunk_audio_16k, chunk_start_time)
                result_info = getattr(backend, "last_result_info", {}) or {}
                self._log(
                    "whisper-cli parse stats: "
                    f"stdout_lines={result_info.get('stdout_lines', 'n/a')}, "
                    f"stderr_lines={result_info.get('stderr_lines', 'n/a')}, "
                    "segment_candidates_before_parse="
                    f"{result_info.get('segment_candidates_before_parse', 'n/a')}, "
                    f"segments_after_parse={result_info.get('segments_after_parse', len(raw_lines))}."
                )
            except Exception as exc:
                self._emit_error(f"Backend transcription failed: {exc}")
                self.task_queue.task_done()
                continue

            if raw_lines:
                self.store.append_raw(raw_lines)
                self._emit(
                    "raw_lines",
                    lines=raw_lines,
                    raw_count=self.store.raw_lines,
                    clean_count=self.store.clean_lines,
                )
                self._log(f"Raw written: {len(raw_lines)} line(s).")

                combined = "\n".join(raw_lines)
                stage1 = simple_dedup(combined, self.last_output_text)
                stage2 = fuzzy_boundary_dedup(self.last_output_text, stage1)
                clean_lines = [line for line in stage2.splitlines() if line.strip()]
                clean_lines, filtered_hallucinations = filter_clean_hallucinations(clean_lines)
                for item in filtered_hallucinations:
                    self._log(
                        "Filtered clean hallucination: "
                        f"pattern={item['pattern']!r}, line={item['line']!r}. "
                        "Raw transcript is preserved.",
                        level="WARNING",
                    )

                if clean_lines:
                    self.store.append_clean(clean_lines)
                    self._emit(
                        "clean_lines",
                        lines=clean_lines,
                        raw_count=self.store.raw_lines,
                        clean_count=self.store.clean_lines,
                    )
                    self.last_output_text += "\n" + "\n".join(clean_lines)
                    self._log(f"Clean written: {len(clean_lines)} line(s).")
                elif filtered_hallucinations:
                    self._log("Clean write skipped after conservative hallucination filtering.")
                else:
                    self._log("Chunk fully overlapped after dedup; clean write skipped.")
            else:
                self._log("No valid text recognized in this chunk.")

            self.task_queue.task_done()
            self._emit_queue_size()

        self._log("Worker stopped.")

    def _maybe_submit_chunk(self):
        if self.total_audio_seconds < BLOCK_SECONDS:
            return

        if self.last_chunk_start is None:
            candidate_start = 0.0
        else:
            candidate_start = self.last_chunk_start + STEP_SECONDS

        candidate_end = candidate_start + BLOCK_SECONDS
        if self.total_audio_seconds < candidate_end:
            return

        buffer_array = np.array(self.audio_buffer, dtype=np.float32)
        buffer_end_time = self.total_audio_seconds
        buffer_start_time = max(0.0, buffer_end_time - len(buffer_array) / CAPTURE_RATE)

        epsilon = 0.05
        if candidate_start < buffer_start_time:
            drift = buffer_start_time - candidate_start
            if drift <= epsilon:
                self._log(
                    f"Small drift detected ({drift:.3f}s); clamping to buffer start.",
                    level="WARNING",
                )
            else:
                self._log(
                    "Candidate chunk fell out of ring buffer window "
                    f"by {drift:.3f}s; realigning.",
                    level="WARNING",
                )
            candidate_start = buffer_start_time
            candidate_end = candidate_start + BLOCK_SECONDS
            if self.total_audio_seconds < candidate_end:
                return

        start_idx = int((candidate_start - buffer_start_time) * CAPTURE_RATE)
        end_idx = int((candidate_end - buffer_start_time) * CAPTURE_RATE)
        chunk_audio = buffer_array[start_idx:end_idx]

        expected_samples = int(BLOCK_SECONDS * CAPTURE_RATE)
        if len(chunk_audio) != expected_samples:
            self._log(
                f"Chunk length mismatch ({len(chunk_audio)} vs {expected_samples}); skipped.",
                level="WARNING",
            )
            return

        self.task_queue.put((chunk_audio, candidate_start, candidate_end))
        self.last_chunk_start = candidate_start
        self._log(f"Chunk submitted {candidate_start:.2f}s -> {candidate_end:.2f}s.")
        self._emit_queue_size()

    def _submit_final_partial_chunk(self):
        final_end = self.total_audio_seconds
        if self.last_chunk_start is None:
            final_start = 0.0
        else:
            final_start = self.last_chunk_start + STEP_SECONDS

        duration = final_end - final_start
        if duration < FINAL_PARTIAL_MIN_SECONDS:
            self._log(
                "Final partial chunk skipped: "
                f"duration={duration:.2f}s below {FINAL_PARTIAL_MIN_SECONDS:.2f}s.",
            )
            return False

        buffer_array = np.array(self.audio_buffer, dtype=np.float32)
        if len(buffer_array) == 0:
            self._log("Final partial chunk skipped: audio buffer is empty.", level="WARNING")
            return False

        buffer_end_time = self.total_audio_seconds
        buffer_start_time = max(0.0, buffer_end_time - len(buffer_array) / CAPTURE_RATE)

        if final_start < buffer_start_time:
            drift = buffer_start_time - final_start
            self._log(
                "Final partial chunk start fell out of the ring buffer by "
                f"{drift:.3f}s; clamping to buffer start.",
                level="WARNING",
            )
            final_start = buffer_start_time
            duration = final_end - final_start
            if duration < FINAL_PARTIAL_MIN_SECONDS:
                self._log(
                    "Final partial chunk skipped after clamp: "
                    f"duration={duration:.2f}s below {FINAL_PARTIAL_MIN_SECONDS:.2f}s.",
                )
                return False

        start_idx = int((final_start - buffer_start_time) * CAPTURE_RATE)
        end_idx = int((final_end - buffer_start_time) * CAPTURE_RATE)
        chunk_audio = buffer_array[start_idx:end_idx]

        min_samples = int(FINAL_PARTIAL_MIN_SECONDS * CAPTURE_RATE)
        if len(chunk_audio) < min_samples:
            self._log(
                "Final partial chunk skipped: "
                f"{len(chunk_audio)} sample(s) below {min_samples}.",
            )
            return False

        rms = audio_rms(chunk_audio)
        if rms < FINAL_PARTIAL_MIN_RMS:
            self._log(
                "Final partial chunk skipped: "
                f"rms={rms:.6f} below {FINAL_PARTIAL_MIN_RMS:.6f}.",
                level="WARNING",
            )
            return False

        self.task_queue.put((chunk_audio, final_start, final_end))
        self._log(
            f"Final partial chunk submitted {final_start:.2f}s -> {final_end:.2f}s "
            f"({duration:.2f}s, rms={rms:.6f})."
        )
        self._emit_queue_size()
        return True

    def _clear_pending_tasks(self):
        # Reserved for a future force-stop path. Normal Stop drains the queue.
        cleared = 0
        while True:
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
            else:
                cleared += 1
                self.task_queue.task_done()
        if cleared:
            self._log(f"Cleared {cleared} pending chunk(s) during stop.")

    def _emit_queue_size(self):
        self._emit("queue", queue_size=self.task_queue.qsize())

    def _log(self, message: str, level: str = "INFO"):
        if not self._closed:
            self.store.log(message, level=level)
        self._emit("log", message=message, level=level)

    def _emit_error(self, message: str):
        if not self._closed:
            self.store.log(message, level="ERROR")
        self._emit("error", message=message)

    def _emit(self, event_type: str, **payload):
        event = {
            "type": event_type,
            "runtime": time.time() - self.started_at if self.started_at else 0.0,
            "queue_size": self.task_queue.qsize(),
            **payload,
        }
        if self.event_callback:
            try:
                self.event_callback(event)
            except Exception:
                pass
