import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from model_integrity import (
    ModelContract,
    ModelDownloadResult,
    downloaded_model_status,
    execute_model_download,
    load_model_contract,
    metadata_for_model,
)
from settings import (
    APP_SETTINGS_PATH,
    APP_SUPPORT_MODEL_DIR,
    DEFAULT_BEAM_SIZE,
    DEFAULT_DOWNLOAD_MODEL_DIR,
    DEFAULT_DOWNLOAD_SCRIPT,
    DEFAULT_MODEL_DIRS,
    DEFAULT_OUTPUT_BASE_DIR,
    DEFAULT_WHISPER_CPP_CLI,
    MIN_MODEL_FILE_SIZE_BYTES,
    PROJECT_ROOT,
    PROJECT_MODEL_DIR,
)


MODEL_CONTRACT = load_model_contract()
KNOWN_MODEL_FILES = {
    model.filename: model.name for model in MODEL_CONTRACT.models
}
DOWNLOADABLE_MODELS = tuple(model.name for model in MODEL_CONTRACT.models)
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
    def current_summary_label(self) -> str:
        return f"{self.name} | {self.size_label} | {self.status}"

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
    download_model_dir: Path
    model_dirs: list[Path]
    imported_model_paths: list[Path]
    output_base_dir: Path = DEFAULT_OUTPUT_BASE_DIR

    def to_json(self):
        return {
            "whisper_cpp_cli": str(self.whisper_cpp_cli),
            "selected_model_path": str(self.selected_model_path) if self.selected_model_path else "",
            "selected_model_name": self.selected_model_name,
            "default_beam_size": self.default_beam_size,
            "download_model_dir": str(self.download_model_dir),
            "model_dirs": [str(path) for path in self.model_dirs],
            "imported_model_paths": [str(path) for path in self.imported_model_paths],
            "output_base_dir": str(self.output_base_dir),
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


def dedupe_paths(paths) -> list[Path]:
    unique = []
    seen = set()
    for path in paths:
        if path is None or not str(path).strip():
            continue
        expanded = Path(path).expanduser()
        key = _path_key(expanded)
        if key in seen:
            continue
        seen.add(key)
        unique.append(expanded)
    return unique


def default_scan_model_dirs(download_model_dir=None, configured_model_dirs=None) -> list[Path]:
    return dedupe_paths(
        [
            download_model_dir or DEFAULT_DOWNLOAD_MODEL_DIR,
            DEFAULT_DOWNLOAD_MODEL_DIR,
            APP_SUPPORT_MODEL_DIR,
            PROJECT_MODEL_DIR,
            *DEFAULT_MODEL_DIRS,
            *(configured_model_dirs or []),
        ]
    )


def ensure_model_dir(path: Path) -> Path:
    path = Path(path).expanduser()
    try:
        if path.exists() and not path.is_dir():
            raise RuntimeError("Path exists but is not a directory.")
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise RuntimeError("Path is not a directory after creation.")

        probe_path = path / f".write_test_{uuid.uuid4().hex}"
        with open(probe_path, "w", encoding="utf-8") as probe_file:
            probe_file.write("ok")
        probe_path.unlink(missing_ok=True)
    except RuntimeError as exc:
        raise RuntimeError(f"Cannot create model download directory: {path}\n{exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Cannot create model download directory: {path}\n{exc}") from exc
    return path


def try_ensure_model_dir(path: Path) -> tuple[bool, str]:
    try:
        ensure_model_dir(path)
    except RuntimeError as exc:
        return False, str(exc)
    return True, ""


def ensure_model_dirs(model_dirs=None, download_model_dir=None):
    download_model_dir = Path(download_model_dir or DEFAULT_DOWNLOAD_MODEL_DIR).expanduser()
    model_dirs = default_scan_model_dirs(download_model_dir, model_dirs)
    for required_dir in (DEFAULT_DOWNLOAD_MODEL_DIR, download_model_dir):
        try_ensure_model_dir(required_dir)
    return model_dirs


def model_status(
    path: Path,
    *,
    download_model_dir: Path | None = None,
    imported_model_paths=(),
    contract: ModelContract = MODEL_CONTRACT,
) -> str:
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "not a file"
    imported_keys = {_path_key(imported) for imported in imported_model_paths}
    is_explicit_import = _path_key(path) in imported_keys
    is_managed_downloadable = bool(
        path.name in contract.by_filename and not is_explicit_import
    )
    if is_managed_downloadable:
        metadata = contract.by_filename[path.name]
        return downloaded_model_status(path, metadata, contract)
    if path.stat().st_size <= MIN_MODEL_FILE_SIZE_BYTES:
        return "too small"
    return "available"


def scan_model_dirs(
    model_dirs=None,
    extra_paths=None,
    download_model_dir=None,
    *,
    contract: ModelContract = MODEL_CONTRACT,
) -> list[ModelInfo]:
    download_model_dir = Path(
        download_model_dir or DEFAULT_DOWNLOAD_MODEL_DIR
    ).expanduser()
    model_dirs = ensure_model_dirs(model_dirs, download_model_dir=download_model_dir)
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
            status=model_status(
                path,
                download_model_dir=download_model_dir,
                imported_model_paths=extra_paths,
                contract=contract,
            ),
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

    download_model_dir = Path(
        data.get("download_model_dir", DEFAULT_DOWNLOAD_MODEL_DIR)
    ).expanduser()
    try_ensure_model_dir(download_model_dir)

    configured_model_dirs = [
        Path(path).expanduser()
        for path in data.get("model_dirs", [])
    ]
    model_dirs = ensure_model_dirs(configured_model_dirs, download_model_dir=download_model_dir)
    imported_paths = [
        Path(path).expanduser()
        for path in data.get("imported_model_paths", [])
        if str(path).strip()
    ]
    selected_model_path = data.get("selected_model_path", "")
    selected_model_path = Path(selected_model_path).expanduser() if selected_model_path else None
    output_base_dir = Path(
        data.get("output_base_dir") or DEFAULT_OUTPUT_BASE_DIR
    ).expanduser()

    app_settings = AppSettings(
        whisper_cpp_cli=Path(data.get("whisper_cpp_cli", DEFAULT_WHISPER_CPP_CLI)).expanduser(),
        selected_model_path=selected_model_path,
        selected_model_name=data.get("selected_model_name", ""),
        default_beam_size=int(data.get("default_beam_size", DEFAULT_BEAM_SIZE)),
        download_model_dir=download_model_dir,
        model_dirs=model_dirs,
        imported_model_paths=imported_paths,
        output_base_dir=output_base_dir,
    )

    models = scan_model_dirs(
        app_settings.model_dirs,
        app_settings.imported_model_paths,
        download_model_dir=app_settings.download_model_dir,
    )
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
    try:
        return metadata_for_model(model_name, MODEL_CONTRACT).filename
    except RuntimeError as exc:
        raise ValueError(f"Unsupported downloadable model: {model_name}") from exc


def download_target_path(model_name: str, target_dir: Path = DEFAULT_DOWNLOAD_MODEL_DIR) -> Path:
    return Path(target_dir).expanduser() / downloadable_model_filename(model_name)


def build_download_command(
    model_name: str,
    script_path: Path = DOWNLOAD_SCRIPT_PATH,
    target_dir: Path = DEFAULT_DOWNLOAD_MODEL_DIR,
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


def download_and_publish_model(
    model_name: str,
    target_dir: Path = DEFAULT_DOWNLOAD_MODEL_DIR,
    *,
    script_path: Path = DOWNLOAD_SCRIPT_PATH,
    contract: ModelContract = MODEL_CONTRACT,
    command_runner=run_download_command,
    log_callback=None,
) -> ModelDownloadResult:
    if model_name not in contract.by_name:
        raise ValueError(f"Unsupported downloadable model: {model_name}")

    def downloader(metadata, staging_dir, callback):
        command = build_download_command(
            metadata.name,
            script_path=script_path,
            target_dir=staging_dir,
        )
        if callback:
            callback("download command: " + " ".join(command))
        return command_runner(command, cwd=staging_dir, log_callback=callback)

    return execute_model_download(
        model_name,
        target_dir,
        downloader,
        contract=contract,
        log_callback=log_callback,
    )


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
    priority = {name: index for index, name in enumerate(DOWNLOADABLE_MODELS)}.get(
        model.name, 20
    )
    return (priority, model.name.lower(), str(model.path).lower())
