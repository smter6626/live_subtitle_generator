import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from settings import (
    APP_SETTINGS_PATH,
    DEFAULT_BEAM_SIZE,
    DEFAULT_DOWNLOAD_SCRIPT,
    DEFAULT_MODEL_DIRS,
    DEFAULT_WHISPER_CPP_CLI,
    MIN_MODEL_FILE_SIZE_BYTES,
    PROJECT_ROOT,
    PROJECT_MODEL_DIR,
    WHISPER_CPP_MODEL_DIR,
)


KNOWN_MODEL_FILES = {
    "ggml-large-v3.bin": "large-v3",
    "ggml-large-v3-turbo.bin": "large-v3-turbo",
    "ggml-medium.en.bin": "medium.en",
    "ggml-small.en.bin": "small.en",
    "ggml-base.en.bin": "base.en",
}
DOWNLOADABLE_MODELS = ("large-v3", "large-v3-turbo", "medium.en", "small.en", "base.en")
MODEL_EXTENSIONS = (".bin", ".gguf")
DOWNLOAD_SCRIPT_PATH = DEFAULT_DOWNLOAD_SCRIPT


@dataclass(frozen=True)
class ModelInfo:
    name: str
    path: Path
    size_bytes: int
    status: str

    @property
    def size_label(self) -> str:
        return format_file_size(self.size_bytes)

    @property
    def display_path(self) -> str:
        return format_model_path(self.path)

    @property
    def display_label(self) -> str:
        return f"{self.name} | {self.size_label} | {self.display_path} | {self.status}"

    @property
    def is_available(self) -> bool:
        return self.status == "available"


@dataclass
class AppSettings:
    whisper_cpp_cli: Path
    selected_model_path: Path | None
    selected_model_name: str
    default_beam_size: int
    model_dirs: list[Path]
    imported_model_paths: list[Path]

    def to_json(self):
        return {
            "whisper_cpp_cli": str(self.whisper_cpp_cli),
            "selected_model_path": str(self.selected_model_path) if self.selected_model_path else "",
            "selected_model_name": self.selected_model_name,
            "default_beam_size": self.default_beam_size,
            "model_dirs": [str(path) for path in self.model_dirs],
            "imported_model_paths": [str(path) for path in self.imported_model_paths],
        }


def parse_model_name(filename: str) -> str:
    name = Path(filename).name
    if name in KNOWN_MODEL_FILES:
        return KNOWN_MODEL_FILES[name]
    if name.startswith("ggml-") and Path(name).suffix.lower() in MODEL_EXTENSIONS:
        return "Custom Model"
    return "Custom Model"


def format_file_size(size_bytes: int) -> str:
    size = float(max(0, size_bytes))
    units = ("B", "KB", "MB", "GB", "TB")
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024.0
    if unit == "B":
        return f"{int(size)} B"
    return f"{size:.1f} {unit}"


def format_model_path(path: Path) -> str:
    path = Path(path).expanduser()
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def ensure_model_dirs(model_dirs=None):
    model_dirs = [Path(path).expanduser() for path in (model_dirs or DEFAULT_MODEL_DIRS)]
    PROJECT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for model_dir in model_dirs:
        if model_dir == PROJECT_MODEL_DIR:
            model_dir.mkdir(parents=True, exist_ok=True)
    return model_dirs


def model_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "not a file"
    if path.stat().st_size <= MIN_MODEL_FILE_SIZE_BYTES:
        return "too small"
    return "available"


def scan_model_dirs(model_dirs=None, extra_paths=None) -> list[ModelInfo]:
    model_dirs = ensure_model_dirs(model_dirs)
    extra_paths = extra_paths or []
    found = {}

    for model_dir in model_dirs:
        if not model_dir.exists() or not model_dir.is_dir():
            continue
        for path in sorted(model_dir.iterdir()):
            if _looks_like_model_file(path):
                found[_path_key(path)] = path

    for extra_path in extra_paths:
        path = Path(extra_path).expanduser()
        if path.exists() and path.is_file() and path.suffix.lower() in MODEL_EXTENSIONS:
            found[_path_key(path)] = path

    models = [
        ModelInfo(
            name=parse_model_name(path.name),
            path=path,
            size_bytes=path.stat().st_size if path.exists() and path.is_file() else 0,
            status=model_status(path),
        )
        for path in found.values()
    ]
    return sorted(models, key=_model_sort_key)


def choose_default_model(models: list[ModelInfo], preferred_path=None) -> ModelInfo | None:
    preferred_key = _path_key(preferred_path) if preferred_path else None
    if preferred_key:
        for model in models:
            if _path_key(model.path) == preferred_key and model.is_available:
                return model

    for preferred_name in ("large-v3", "large-v3-turbo"):
        for model in models:
            if model.name == preferred_name and model.is_available:
                return model

    return None


def load_app_settings(settings_path: Path = APP_SETTINGS_PATH) -> AppSettings:
    settings_path = Path(settings_path)
    data = {}
    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            data = json.load(settings_file)

    model_dirs = [
        Path(path).expanduser()
        for path in data.get("model_dirs", [str(path) for path in DEFAULT_MODEL_DIRS])
    ]
    model_dirs = ensure_model_dirs(model_dirs)
    imported_paths = [
        Path(path).expanduser()
        for path in data.get("imported_model_paths", [])
        if str(path).strip()
    ]
    selected_model_path = data.get("selected_model_path", "")
    selected_model_path = Path(selected_model_path).expanduser() if selected_model_path else None

    app_settings = AppSettings(
        whisper_cpp_cli=Path(data.get("whisper_cpp_cli", DEFAULT_WHISPER_CPP_CLI)).expanduser(),
        selected_model_path=selected_model_path,
        selected_model_name=data.get("selected_model_name", ""),
        default_beam_size=int(data.get("default_beam_size", DEFAULT_BEAM_SIZE)),
        model_dirs=model_dirs,
        imported_model_paths=imported_paths,
    )

    models = scan_model_dirs(app_settings.model_dirs, app_settings.imported_model_paths)
    selected = choose_default_model(models, app_settings.selected_model_path)
    if selected:
        app_settings.selected_model_path = selected.path
        app_settings.selected_model_name = selected.name

    return app_settings


def save_app_settings(app_settings: AppSettings, settings_path: Path = APP_SETTINGS_PATH):
    settings_path = Path(settings_path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as settings_file:
        json.dump(app_settings.to_json(), settings_file, indent=2, ensure_ascii=False)
        settings_file.write("\n")


def validate_import_model(path: Path) -> list[str]:
    path = Path(path).expanduser()
    errors = []
    if not path.exists():
        errors.append(f"Model file does not exist: {path}")
    elif not path.is_file():
        errors.append(f"Model path is not a file: {path}")
    elif path.suffix.lower() not in MODEL_EXTENSIONS:
        errors.append("Model file must be .bin or .gguf.")
    elif path.stat().st_size <= MIN_MODEL_FILE_SIZE_BYTES:
        errors.append(
            f"Model file is too small; expected > {format_file_size(MIN_MODEL_FILE_SIZE_BYTES)}."
        )
    return errors


def downloadable_model_filename(model_name: str) -> str:
    if model_name not in DOWNLOADABLE_MODELS:
        raise ValueError(f"Unsupported downloadable model: {model_name}")
    return f"ggml-{model_name}.bin"


def download_target_path(model_name: str, target_dir: Path = WHISPER_CPP_MODEL_DIR) -> Path:
    return Path(target_dir).expanduser() / downloadable_model_filename(model_name)


def build_download_command(
    model_name: str,
    script_path: Path = DOWNLOAD_SCRIPT_PATH,
    target_dir: Path = WHISPER_CPP_MODEL_DIR,
):
    if model_name not in DOWNLOADABLE_MODELS:
        raise ValueError(f"Unsupported downloadable model: {model_name}")
    return ["sh", str(Path(script_path).expanduser()), model_name, str(Path(target_dir).expanduser())]


def run_download_command(command, cwd: Path | None = None, log_callback=None) -> int:
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdout:
        for line in process.stdout:
            if log_callback:
                log_callback(line.rstrip())
    return process.wait()


def _looks_like_model_file(path: Path) -> bool:
    if not path.is_file():
        return False
    suffix = path.suffix.lower()
    if suffix == ".gguf":
        return True
    return suffix == ".bin" and path.name.startswith("ggml-")


def _path_key(path) -> str:
    if not path:
        return ""
    return str(Path(path).expanduser().resolve())


def _model_sort_key(model: ModelInfo):
    priority = {
        "large-v3": 0,
        "large-v3-turbo": 1,
        "medium.en": 2,
        "small.en": 3,
        "base.en": 4,
    }.get(model.name, 20)
    return (priority, model.name.lower(), str(model.path).lower())
