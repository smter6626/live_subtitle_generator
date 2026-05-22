# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent


def existing_resource(relative_path, destination):
    source = ROOT / relative_path
    if source.exists():
        return (str(source), destination)
    return None


resource_specs = [
    ("external/whisper.cpp/build/bin/whisper-cli", "bin"),
    ("external/whisper.cpp/models/download-ggml-model.sh", "bin"),
    ("external/whisper.cpp/build/src/libwhisper.1.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/libggml.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/libggml-cpu.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/ggml-blas/libggml-blas.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/ggml-metal/libggml-metal.0.dylib", "bin"),
    ("external/whisper.cpp/build/ggml/src/libggml-base.0.dylib", "bin"),
]
datas = [
    resource
    for resource in (existing_resource(path, destination) for path, destination in resource_specs)
    if resource is not None
]


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
    name="ClassroomTranscriber",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name="ClassroomTranscriber",
)
app = BUNDLE(
    coll,
    name="ClassroomTranscriber.app",
    icon=None,
    bundle_identifier="com.local.classroomtranscriber",
    info_plist={
        "NSMicrophoneUsageDescription": (
            "ClassroomTranscriber needs microphone access to record classroom audio "
            "for local real-time transcription."
        ),
        "CFBundleName": "ClassroomTranscriber",
        "CFBundleDisplayName": "ClassroomTranscriber",
    },
)
