from enum import Enum

from settings import (
    HALLUCINATION_DENYLIST,
    HALLUCINATION_FILTER_MODE,
    default_settings,
    validate_runtime_paths,
)
from transcript_store import TranscriptStore
from transcription_engine import TranscriptionEngine


class EngineState(str, Enum):
    IDLE = "Idle"
    STARTING = "Starting"
    RECORDING = "Recording"
    STOPPING = "Stopping"
    ERROR = "Error"


class TranscriptionController:
    def __init__(self, event_callback=None):
        self.event_callback = event_callback
        self.state = EngineState.IDLE
        self.settings = None
        self.store = None
        self.engine = None

    def start(
        self,
        beam_size: int,
        original_language_label: str,
        selected_model_path=None,
        selected_model_name: str | None = None,
        output_base_dir=None,
    ):
        if self.state not in (EngineState.IDLE, EngineState.ERROR):
            raise RuntimeError(f"Cannot start while state is {self.state.value}.")

        self.settings = default_settings(
            beam_size=beam_size,
            original_language_label=original_language_label,
            selected_model_path=selected_model_path,
            selected_model_name=selected_model_name,
            output_base_dir=output_base_dir,
        )
        errors = validate_runtime_paths(self.settings)
        if errors:
            message = "\n\n".join(errors)
            self._set_state(EngineState.ERROR, message=message)
            raise RuntimeError(message)

        self._set_state(EngineState.STARTING)
        self.store = TranscriptStore(self.settings.output_root)
        self.store.write_config(self.settings.to_config())
        self.store.log(
            "Session started with "
            f"backend={self.settings.backend}, model={self.settings.model}, "
            f"model_path={self.settings.whisper_cpp_model}, "
            f"beam_size={self.settings.beam_size}, "
            f"language={self.settings.original_language_label}, "
            f"whisper_language_code={self.settings.whisper_language_code}, "
            f"task={self.settings.task}, "
            f"prompt_used={self.settings.prompt_used or '<none>'}, "
            f"hallucination_filter_mode={HALLUCINATION_FILTER_MODE}, "
            f"hallucination_denylist_count={len(HALLUCINATION_DENYLIST)}."
        )
        self._emit(
            {
                "type": "session",
                "session_dir": str(self.store.session_dir),
                "raw_path": str(self.store.raw_path),
                "clean_path": str(self.store.clean_path),
                "config": self.settings.to_config(),
                "raw_count": 0,
                "clean_count": 0,
            }
        )

        self.engine = TranscriptionEngine(
            self.settings,
            self.store,
            event_callback=self._handle_engine_event,
        )
        self.engine.start()
        return self.store.session_dir

    def stop(self):
        if self.state not in (
            EngineState.STARTING,
            EngineState.RECORDING,
            EngineState.STOPPING,
            EngineState.ERROR,
        ) and self.engine is None:
            return

        if self.state != EngineState.STOPPING:
            self._set_state(EngineState.STOPPING)
        if self.engine:
            self.engine.stop()
        self.engine = None
        self._set_state(EngineState.IDLE)

    def _handle_engine_event(self, event):
        event_type = event.get("type")
        if event_type == "recording" and self.state == EngineState.STARTING:
            self._set_state(EngineState.RECORDING)
        elif event_type == "error":
            self._set_state(EngineState.ERROR, message=event.get("message", "Unknown error."))
        self._emit(event)

    def _set_state(self, state: EngineState, message: str = ""):
        self.state = state
        self._emit({"type": "state", "state": state.value, "message": message})

    def _emit(self, event):
        if self.event_callback:
            self.event_callback(event)
