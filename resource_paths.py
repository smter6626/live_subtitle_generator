import sys
from pathlib import Path


APP_NAME = "ClassroomTranscriber"


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    return Path(__file__).resolve().parent


def app_contents_dir() -> Path | None:
    executable = Path(sys.executable).resolve()
    if executable.parent.name == "MacOS" and executable.parent.parent.name == "Contents":
        return executable.parent.parent
    return None


def resource_root() -> Path:
    if is_frozen_app():
        candidates = []
        contents = app_contents_dir()
        if contents:
            candidates.append(contents / "Resources")
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS))
        candidates.append(Path(sys.executable).resolve().parent)

        for candidate in candidates:
            if candidate.exists():
                return candidate

    return project_root()


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def user_app_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def user_documents_dir() -> Path:
    return Path.home() / "Documents" / APP_NAME


def writable_config_dir() -> Path:
    if is_frozen_app():
        return user_app_support_dir() / "config"
    return project_root() / "config"


def writable_outputs_dir() -> Path:
    if is_frozen_app():
        return user_documents_dir() / "outputs"
    return project_root() / "outputs"


def writable_models_dir() -> Path:
    if is_frozen_app():
        return user_app_support_dir() / "models"
    return project_root() / "models"


def default_download_model_dir() -> Path:
    return user_documents_dir() / "models"


def app_support_model_dir() -> Path:
    return user_app_support_dir() / "models"


def source_project_model_dir() -> Path:
    return project_root() / "models"


def bundled_whisper_cli_path() -> Path:
    return resource_path("bin", "whisper-cli")


def bundled_download_script_path() -> Path:
    return resource_path("bin", "download-ggml-model.sh")


def bundled_model_manifest_path() -> Path:
    return resource_path("model_manifest.json")


def source_whisper_cli_path() -> Path:
    return project_root() / "external" / "whisper.cpp" / "build" / "bin" / "whisper-cli"


def source_whisper_cpp_model_dir() -> Path:
    return project_root() / "external" / "whisper.cpp" / "models"


def vendored_download_script_path() -> Path:
    return project_root() / "vendor" / "whisper.cpp" / "download-ggml-model.sh"


def source_model_manifest_path() -> Path:
    return project_root() / "packaging" / "model_manifest.json"


def default_whisper_cli_path() -> Path:
    bundled = bundled_whisper_cli_path()
    if bundled.exists():
        return bundled
    return source_whisper_cli_path()


def default_download_script_path() -> Path:
    if is_frozen_app():
        bundled = bundled_download_script_path()
        if bundled.exists():
            return bundled
    return vendored_download_script_path()


def default_model_manifest_path() -> Path:
    if is_frozen_app():
        bundled = bundled_model_manifest_path()
        if bundled.exists():
            return bundled
    return source_model_manifest_path()


def default_model_dirs() -> tuple[Path, ...]:
    candidates = [
        default_download_model_dir(),
        app_support_model_dir(),
        source_project_model_dir(),
        source_whisper_cpp_model_dir(),
    ]
    seen = set()
    unique = []
    for candidate in candidates:
        key = str(candidate.expanduser().resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return tuple(unique)
