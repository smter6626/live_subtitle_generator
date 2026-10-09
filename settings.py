import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from resource_paths import (
    app_support_model_dir,
    default_download_model_dir,
    default_download_script_path,
    default_model_dirs,
    default_whisper_cli_path,
    is_frozen_app,
    project_root,
    source_whisper_cpp_model_dir,
    user_documents_dir,
    writable_config_dir,
    writable_models_dir,
    writable_outputs_dir,
)

from stream_transcribe import (
    BLOCK_SECONDS,
    CAPTURE_RATE,
    OVERLAP_SECONDS,
    TRANSCRIBE_RATE,
)


PROJECT_ROOT = project_root()
CONFIG_DIR = writable_config_dir()
APP_SETTINGS_PATH = CONFIG_DIR / "settings.json"
OUTPUTS_DIR = writable_outputs_dir()
DEFAULT_OUTPUT_BASE_DIR = user_documents_dir()
PROJECT_MODEL_DIR = writable_models_dir()
APP_SUPPORT_MODEL_DIR = app_support_model_dir()
DEFAULT_DOWNLOAD_MODEL_DIR = default_download_model_dir()
WHISPER_CPP_MODEL_DIR = PROJECT_MODEL_DIR if is_frozen_app() else source_whisper_cpp_model_dir()
DEFAULT_WHISPER_CPP_CLI = default_whisper_cli_path()
DEFAULT_WHISPER_CPP_MODEL = WHISPER_CPP_MODEL_DIR / "ggml-large-v3.bin"
DEFAULT_MODEL_DIRS = default_model_dirs()
DEFAULT_DOWNLOAD_SCRIPT = default_download_script_path()
MIN_MODEL_FILE_SIZE_BYTES = 10 * 1024 * 1024

BACKEND_ID = "whisper_cpp"
BACKEND_DISPLAY = "whisper.cpp Metal"
MODEL_ID = "large-v3"
MODEL_DISPLAY = "large-v3"
DEFAULT_BEAM_SIZE = 5
MIN_BEAM_SIZE = 3
MAX_BEAM_SIZE = 8

ORIGINAL_LANGUAGE_ENGLISH = "English"
ORIGINAL_LANGUAGE_CHINESE = "Chinese"
ORIGINAL_LANGUAGE_JAPANESE = "Japanese"
ORIGINAL_LANGUAGE_FRENCH = "French"
ORIGINAL_LANGUAGE_SPANISH = "Spanish"
ORIGINAL_LANGUAGE_GERMAN = "German"
ORIGINAL_LANGUAGE_KOREAN = "Korean"
ORIGINAL_LANGUAGE_AUTO_DETECT = "Auto Detect"
# Retained for source compatibility with callers that used the former constant.
ORIGINAL_LANGUAGE_MIXED = ORIGINAL_LANGUAGE_AUTO_DETECT

# This tuple is the authoritative ordered list for selectors and configuration.
ORIGINAL_LANGUAGE_CHOICES = (
    ORIGINAL_LANGUAGE_ENGLISH,
    ORIGINAL_LANGUAGE_CHINESE,
    ORIGINAL_LANGUAGE_JAPANESE,
    ORIGINAL_LANGUAGE_FRENCH,
    ORIGINAL_LANGUAGE_SPANISH,
    ORIGINAL_LANGUAGE_GERMAN,
    ORIGINAL_LANGUAGE_KOREAN,
    ORIGINAL_LANGUAGE_AUTO_DETECT,
)
ORIGINAL_LANGUAGE_OPTIONS = {
    ORIGINAL_LANGUAGE_ENGLISH: "en",
    ORIGINAL_LANGUAGE_CHINESE: "zh",
    ORIGINAL_LANGUAGE_JAPANESE: "ja",
    ORIGINAL_LANGUAGE_FRENCH: "fr",
    ORIGINAL_LANGUAGE_SPANISH: "es",
    ORIGINAL_LANGUAGE_GERMAN: "de",
    ORIGINAL_LANGUAGE_KOREAN: "ko",
    ORIGINAL_LANGUAGE_AUTO_DETECT: "auto",
}
ORIGINAL_LANGUAGE_PROMPTS = {
    label: "" for label in ORIGINAL_LANGUAGE_CHOICES
}
ORIGINAL_LANGUAGE_ALIASES = {
    "en": ORIGINAL_LANGUAGE_ENGLISH,
    "english": ORIGINAL_LANGUAGE_ENGLISH,
    "英文": ORIGINAL_LANGUAGE_ENGLISH,
    "zh": ORIGINAL_LANGUAGE_CHINESE,
    "cn": ORIGINAL_LANGUAGE_CHINESE,
    "zh-cn": ORIGINAL_LANGUAGE_CHINESE,
    "chinese": ORIGINAL_LANGUAGE_CHINESE,
    "中文": ORIGINAL_LANGUAGE_CHINESE,
    "ja": ORIGINAL_LANGUAGE_JAPANESE,
    "japanese": ORIGINAL_LANGUAGE_JAPANESE,
    "日语": ORIGINAL_LANGUAGE_JAPANESE,
    "fr": ORIGINAL_LANGUAGE_FRENCH,
    "french": ORIGINAL_LANGUAGE_FRENCH,
    "法语": ORIGINAL_LANGUAGE_FRENCH,
    "es": ORIGINAL_LANGUAGE_SPANISH,
    "spanish": ORIGINAL_LANGUAGE_SPANISH,
    "西班牙语": ORIGINAL_LANGUAGE_SPANISH,
    "de": ORIGINAL_LANGUAGE_GERMAN,
    "german": ORIGINAL_LANGUAGE_GERMAN,
    "德语": ORIGINAL_LANGUAGE_GERMAN,
    "ko": ORIGINAL_LANGUAGE_KOREAN,
    "korean": ORIGINAL_LANGUAGE_KOREAN,
    "韩语": ORIGINAL_LANGUAGE_KOREAN,
    "auto": ORIGINAL_LANGUAGE_AUTO_DETECT,
    "auto detect": ORIGINAL_LANGUAGE_AUTO_DETECT,
    "mixed": ORIGINAL_LANGUAGE_AUTO_DETECT,
    "mixed chinese/english": ORIGINAL_LANGUAGE_AUTO_DETECT,
    "mixed chinese english": ORIGINAL_LANGUAGE_AUTO_DETECT,
    "中英混合": ORIGINAL_LANGUAGE_AUTO_DETECT,
    "自动检测": ORIGINAL_LANGUAGE_AUTO_DETECT,
}
DEFAULT_ORIGINAL_LANGUAGE_LABEL = ORIGINAL_LANGUAGE_ENGLISH
TRANSCRIPTION_TASK = "transcribe"
HALLUCINATION_FILTER_MODE = "clean_only"
HALLUCINATION_DENYLIST = (
    "中文字幕由 Amara.org 社群提供",
    "请订阅我的频道",
    "请点赞",
    "点赞 订阅 转发",
)

UI_LANGUAGE_ZH = "zh"
UI_LANGUAGE_EN = "en"
UI_LANGUAGE_OPTIONS = (UI_LANGUAGE_ZH, UI_LANGUAGE_EN)
UI_LANGUAGE_LABELS = {
    UI_LANGUAGE_ZH: "中文",
    UI_LANGUAGE_EN: "English",
}


def normalize_ui_language(language: str) -> str:
    normalized = (language or UI_LANGUAGE_ZH).strip().lower()
    aliases = {
        "cn": UI_LANGUAGE_ZH,
        "zh-cn": UI_LANGUAGE_ZH,
        "chinese": UI_LANGUAGE_ZH,
        "中文": UI_LANGUAGE_ZH,
        "en-us": UI_LANGUAGE_EN,
        "english": UI_LANGUAGE_EN,
        "英文": UI_LANGUAGE_EN,
    }
    return aliases.get(normalized, normalized)


DEFAULT_UI_LANGUAGE = normalize_ui_language(
    os.environ.get("WHISPER_UI_LANGUAGE", UI_LANGUAGE_ZH)
)
if DEFAULT_UI_LANGUAGE not in UI_LANGUAGE_OPTIONS:
    DEFAULT_UI_LANGUAGE = UI_LANGUAGE_ZH


def normalize_original_language_label(language_label: str) -> str:
    if language_label in ORIGINAL_LANGUAGE_OPTIONS:
        return language_label
    normalized = (language_label or DEFAULT_ORIGINAL_LANGUAGE_LABEL).strip().lower()
    return ORIGINAL_LANGUAGE_ALIASES.get(normalized, DEFAULT_ORIGINAL_LANGUAGE_LABEL)


def whisper_language_code_for_label(language_label: str) -> str:
    normalized_label = normalize_original_language_label(language_label)
    return ORIGINAL_LANGUAGE_OPTIONS[normalized_label]


def prompt_for_original_language_label(language_label: str) -> str:
    normalized_label = normalize_original_language_label(language_label)
    return ORIGINAL_LANGUAGE_PROMPTS[normalized_label]


_ENGLISH_ONLY_MODEL_NAME = re.compile(r"(?:^|[._-])en(?:[._-]|$)", re.IGNORECASE)


def is_english_only_whisper_model(model_identity=None, model_path=None) -> bool:
    """Recognize Whisper's conventional English-only ``.en`` model names."""
    candidates = (model_identity, model_path)
    for candidate in candidates:
        if candidate is None:
            continue
        filename = Path(str(candidate)).name.strip()
        if filename and _ENGLISH_ONLY_MODEL_NAME.search(filename):
            return True
    return False


def validate_model_language_compatibility(settings) -> list[str]:
    """Return user-facing errors for invalid model and source-language pairs."""
    if not is_english_only_whisper_model(settings.model, settings.whisper_cpp_model):
        return []
    if settings.whisper_language_code == ORIGINAL_LANGUAGE_OPTIONS[ORIGINAL_LANGUAGE_ENGLISH]:
        return []
    return [
        "Cannot start transcription: English-only .en Whisper models support only "
        "English (en). "
        f"Selected language: {settings.original_language_label} "
        f"({settings.whisper_language_code}). Select English or a multilingual model."
    ]


@dataclass(frozen=True)
class TranscriptionSettings:
    backend: str = BACKEND_ID
    backend_display: str = BACKEND_DISPLAY
    model: str = MODEL_ID
    model_display: str = MODEL_DISPLAY
    beam_size: int = DEFAULT_BEAM_SIZE
    block_seconds: int = BLOCK_SECONDS
    overlap_seconds: int = OVERLAP_SECONDS
    capture_rate: int = CAPTURE_RATE
    transcribe_rate: int = TRANSCRIBE_RATE
    whisper_cpp_cli: Path = DEFAULT_WHISPER_CPP_CLI
    whisper_cpp_model: Path = DEFAULT_WHISPER_CPP_MODEL
    output_root: Path = OUTPUTS_DIR
    ui_language: str = DEFAULT_UI_LANGUAGE
    original_language_label: str = DEFAULT_ORIGINAL_LANGUAGE_LABEL
    whisper_language_code: str = ORIGINAL_LANGUAGE_OPTIONS[DEFAULT_ORIGINAL_LANGUAGE_LABEL]
    task: str = TRANSCRIPTION_TASK
    prompt_used: str = ORIGINAL_LANGUAGE_PROMPTS[DEFAULT_ORIGINAL_LANGUAGE_LABEL]

    def normalized(self):
        original_language_label = normalize_original_language_label(self.original_language_label)
        model_path_text = "" if self.whisper_cpp_model is None else str(self.whisper_cpp_model).strip()
        whisper_cpp_model = (
            Path(model_path_text).expanduser()
            if model_path_text
            else Path("")
        )
        return TranscriptionSettings(
            backend=self.backend,
            backend_display=self.backend_display,
            model=self.model,
            model_display=self.model_display,
            beam_size=int(self.beam_size),
            whisper_cpp_cli=Path(self.whisper_cpp_cli).expanduser(),
            whisper_cpp_model=whisper_cpp_model,
            output_root=Path(self.output_root).expanduser(),
            ui_language=normalize_ui_language(self.ui_language),
            original_language_label=original_language_label,
            whisper_language_code=whisper_language_code_for_label(original_language_label),
            task=TRANSCRIPTION_TASK,
            prompt_used=prompt_for_original_language_label(original_language_label),
        )

    def to_config(self):
        settings = self.normalized()
        return {
            "backend": settings.backend,
            "backend_display": settings.backend_display,
            "model": settings.model,
            "model_display": settings.model_display,
            "model_path": str(settings.whisper_cpp_model),
            "beam_size": settings.beam_size,
            "block_seconds": settings.block_seconds,
            "overlap_seconds": settings.overlap_seconds,
            "capture_rate": settings.capture_rate,
            "transcribe_rate": settings.transcribe_rate,
            "whisper_cpp_cli": str(settings.whisper_cpp_cli),
            "whisper_cpp_model": str(settings.whisper_cpp_model),
            "selected_model_path": str(settings.whisper_cpp_model),
            "ui_language": settings.ui_language,
            "ui_language_label": UI_LANGUAGE_LABELS.get(settings.ui_language, settings.ui_language),
            "original_language_label": settings.original_language_label,
            "whisper_language_code": settings.whisper_language_code,
            "task": settings.task,
            "prompt_used": settings.prompt_used,
            "hallucination_filter": {
                "mode": HALLUCINATION_FILTER_MODE,
                "denylist": list(HALLUCINATION_DENYLIST),
            },
        }


def default_settings(
    beam_size: int = DEFAULT_BEAM_SIZE,
    original_language_label: str = DEFAULT_ORIGINAL_LANGUAGE_LABEL,
    selected_model_path=None,
    selected_model_name: str | None = None,
    output_base_dir=None,
) -> TranscriptionSettings:
    model_path = selected_model_path if selected_model_path is not None else DEFAULT_WHISPER_CPP_MODEL
    model_name = selected_model_name or MODEL_ID
    output_root = (
        output_root_for_base(output_base_dir)
        if output_base_dir is not None
        else OUTPUTS_DIR
    )
    return TranscriptionSettings(
        model=model_name,
        model_display=model_name,
        beam_size=beam_size,
        whisper_cpp_model=model_path,
        output_root=output_root,
        original_language_label=original_language_label,
    ).normalized()


def output_root_for_base(output_base_dir) -> Path:
    return Path(output_base_dir).expanduser() / "outputs"


def validate_output_root(output_root: Path):
    output_root = Path(output_root).expanduser()
    try:
        if output_root.exists() and not output_root.is_dir():
            raise RuntimeError("path exists but is not a directory")
        output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=".classroom_transcriber_write_test_",
            dir=output_root,
        ):
            pass
    except (OSError, RuntimeError) as exc:
        return [
            "Cannot start transcription: output directory is not writable.\n"
            f"Expected writable directory: {output_root}\n"
            f"Reason: {exc}"
        ]
    return []


def validate_runtime_paths(settings: TranscriptionSettings):
    settings = settings.normalized()
    errors = []

    if settings.beam_size < MIN_BEAM_SIZE or settings.beam_size > MAX_BEAM_SIZE:
        errors.append(
            f"Beam Size must be between {MIN_BEAM_SIZE} and {MAX_BEAM_SIZE}."
        )

    if settings.ui_language not in UI_LANGUAGE_OPTIONS:
        errors.append(
            f"UI language must be one of: {', '.join(UI_LANGUAGE_OPTIONS)}."
        )

    if settings.original_language_label not in ORIGINAL_LANGUAGE_OPTIONS:
        errors.append(
            "Original language must be one of: "
            f"{', '.join(ORIGINAL_LANGUAGE_OPTIONS.keys())}."
        )

    if settings.whisper_language_code != whisper_language_code_for_label(settings.original_language_label):
        errors.append("Whisper language code does not match original language selection.")

    errors.extend(validate_model_language_compatibility(settings))

    if settings.task != TRANSCRIPTION_TASK:
        errors.append("Only task='transcribe' is supported.")

    cli_path = settings.whisper_cpp_cli
    if not cli_path.exists():
        errors.append(
            "Cannot start transcription: whisper-cli not found.\n"
            f"Expected path: {cli_path}"
        )
    elif not os.access(cli_path, os.X_OK):
        errors.append(
            "Cannot start transcription: whisper-cli is not executable.\n"
            f"Expected executable path: {cli_path}"
        )

    model_path = settings.whisper_cpp_model
    model_path_text = str(model_path).strip()
    if not model_path_text or model_path_text == ".":
        errors.append("Cannot start transcription: no model selected.")
    elif not model_path.exists():
        errors.append(
            "Cannot start transcription: selected model not found.\n"
            f"Expected path: {model_path}"
        )
    elif not model_path.is_file():
        errors.append(
            "Cannot start transcription: selected model path is not a file.\n"
            f"Expected file path: {model_path}"
        )
    elif model_path.stat().st_size <= MIN_MODEL_FILE_SIZE_BYTES:
        errors.append(
            "Cannot start transcription: selected model file is too small.\n"
            f"Expected a model larger than {MIN_MODEL_FILE_SIZE_BYTES} bytes: {model_path}"
        )

    errors.extend(validate_output_root(settings.output_root))

    return errors


def write_config_json(path: Path, config: dict):
    with open(path, "w", encoding="utf-8") as config_file:
        json.dump(config, config_file, indent=2, ensure_ascii=False)
        config_file.write("\n")
