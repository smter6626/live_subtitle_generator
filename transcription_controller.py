from enum import Enum
from uuid import uuid4

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
        self.active_session_id = None
        self.active_session_generation = 0

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

        settings = default_settings(
            beam_size=beam_size,
            original_language_label=original_language_label,
            selected_model_path=selected_model_path,
            selected_model_name=selected_model_name,
            output_base_dir=output_base_dir,
        )
        errors = validate_runtime_paths(settings)
        if errors:
            message = "\n\n".join(errors)
            self._set_state(EngineState.ERROR, message=message)
            raise RuntimeError(message)

        store = TranscriptStore(settings.output_root)
        store.write_config(settings.to_config())
        store.log(
            "Session started with "
            f"backend={settings.backend}, model={settings.model}, "
            f"model_path={settings.whisper_cpp_model}, "
            f"beam_size={settings.beam_size}, "
            f"language={settings.original_language_label}, "
            f"whisper_language_code={settings.whisper_language_code}, "
            f"task={settings.task}, "
            f"prompt_used={settings.prompt_used or '<none>'}, "
            f"hallucination_filter_mode={HALLUCINATION_FILTER_MODE}, "
            f"hallucination_denylist_count={len(HALLUCINATION_DENYLIST)}."
        )

        session_id = uuid4().hex
        session_generation = self.active_session_generation + 1
        self.settings = settings
        self.store = store
        self.active_session_id = session_id
        self.active_session_generation = session_generation
        self._emit(
            {
                "type": "session",
                "session_dir": str(store.session_dir),
                "raw_path": str(store.raw_path),
                "clean_path": str(store.clean_path),
                "config": settings.to_config(),
                "raw_count": 0,
                "clean_count": 0,
            },
            session_id=session_id,
            session_generation=session_generation,
        )
        self._set_state(
            EngineState.STARTING,
            session_id=session_id,
            session_generation=session_generation,
        )

        self.engine = TranscriptionEngine(
            settings,
            store,
            event_callback=lambda event, owner_id=session_id, owner_generation=session_generation: (
                self._handle_engine_event(owner_id, owner_generation, event)
            ),
        )
        self.engine.start()
        return store.session_dir

    def stop(self):
        if self.state not in (
            EngineState.STARTING,
            EngineState.RECORDING,
            EngineState.STOPPING,
            EngineState.ERROR,
        ) and self.engine is None:
            return

        session_id = self.active_session_id
        session_generation = self.active_session_generation
        if self.state != EngineState.STOPPING:
            self._set_state(
                EngineState.STOPPING,
                session_id=session_id,
                session_generation=session_generation,
            )
        if self.engine:
            self.engine.stop()
        self.engine = None
        self._set_state(
            EngineState.IDLE,
            session_id=session_id,
            session_generation=session_generation,
        )

    def _handle_engine_event(self, session_id, session_generation, event):
        if (
            session_id != self.active_session_id
            or session_generation != self.active_session_generation
        ):
            return

        event_type = event.get("type")
        if event_type == "recording" and self.state == EngineState.STARTING:
            self._set_state(
                EngineState.RECORDING,
                session_id=session_id,
                session_generation=session_generation,
            )
        elif event_type == "error":
            self._set_state(
                EngineState.ERROR,
                message=event.get("message", "Unknown error."),
                session_id=session_id,
                session_generation=session_generation,
            )
        self._emit(
            event,
            session_id=session_id,
            session_generation=session_generation,
        )

    def _set_state(
        self,
        state: EngineState,
        message: str = "",
        session_id=None,
        session_generation=None,
    ):
        self.state = state
        self._emit(
            {"type": "state", "state": state.value, "message": message},
            session_id=session_id,
            session_generation=session_generation,
        )

    def _emit(self, event, session_id=None, session_generation=None):
        if self.event_callback:
            scoped_event = dict(event)
            if session_id is not None:
                scoped_event["session_id"] = session_id
            if session_generation is not None:
                scoped_event["session_generation"] = session_generation
            self.event_callback(scoped_event)
