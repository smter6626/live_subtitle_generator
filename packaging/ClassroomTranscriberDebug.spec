# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent


def existing_resource(relative_path, destination):
    source = ROOT / relative_path
    if source.exists():
        return (str(source), destination)
    return None


def required_resource(relative_path, destination):
    source = ROOT / relative_path
    if not source.is_file():
        raise FileNotFoundError(f"Required packaging resource not found: {source}")
    return (str(source), destination)


resource_specs = [
    ("external/whisper.cpp/build/bin/whisper-cli", "bin"),
    ("external/whisper.cpp/build/src/libwhisper.1.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/libggml.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/libggml-cpu.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/ggml-blas/libggml-blas.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/ggml-metal/libggml-metal.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/libggml-base.0.dylib", "bin"),
]
datas = [required_resource("vendor/whisper.cpp/download-ggml-model.sh", "bin")]
datas.extend(
    resource
    for resource in (existing_resource(path, destination) for path, destination in resource_specs)
    if resource is not None
)


a = Analysis(
    [str(ROOT / "ui_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ClassroomTranscriberDebug",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ClassroomTranscriberDebug",
)
