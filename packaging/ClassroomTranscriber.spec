# -*- mode: python ; coding: utf-8 -*-

import json
from pathlib import Path, PurePosixPath

ROOT = Path(SPECPATH).resolve().parent


def required_resource(relative_path, destination):
    source = ROOT / relative_path
    if not source.is_file():
        raise FileNotFoundError(f"Required packaging resource not found: {source}")
    return (str(source), destination)


def pyinstaller_destination(bundle_path):
    relative = PurePosixPath(bundle_path).relative_to("Contents/Resources")
    return relative.as_posix()


manifest = json.loads((ROOT / "packaging/runtime_manifest.json").read_text())
datas = [
    required_resource(
        component["source_path"],
        pyinstaller_destination(component["bundle_directory"]),
    )
    for component in manifest["frozen"]["runtime_components"]
    if component["required"] is True
]
datas.extend(
    required_resource(
        resource["repository_path"],
        pyinstaller_destination(str(PurePosixPath(resource["bundle_target"]).parent)),
    )
    for resource in manifest["frozen"]["vendored_resources"]
    if resource["required"] is True
)
model_integrity = manifest["frozen"]["model_integrity"]
if model_integrity["required_packaged_resource"] is True:
    datas.append(
        required_resource(
            model_integrity["manifest_repository_path"],
            pyinstaller_destination(
                str(PurePosixPath(model_integrity["manifest_bundle_target"]).parent)
            ),
        )
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
