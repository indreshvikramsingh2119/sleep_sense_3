# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for the Windows Sleep Sense desktop app."""

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata


project_root = Path(SPEC).resolve().parent
icon_path = project_root / "assets" / "icon.ico"

datas = [
    (str(project_root / "assets"), "assets"),
    (str(project_root / "icons"), "icons"),
    (str(project_root / "src" / "assets"), "src/assets"),
]
for distribution in ("pytz", "pandas", "numpy"):
    datas += copy_metadata(distribution)

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    # SciPy imports unittest at runtime in some signal-processing paths.
    # Keep it explicit so the frozen application has the standard library
    # package even though the app itself does not import it directly.
    hiddenimports=["PyQt5.sip", "unittest"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "pyi_rth_disable_optional_pyarrow.py")],
    excludes=[
        "tkinter",
        "pytest",
        "tensorflow",
        "keras",
        "torch",
        "IPython",
        "jupyter",
        "notebook",
        "h5py",
        "sklearn",
        "joblib",
        "pyarrow",
        "PyQt5.QtWebEngine",
        "PyQt5.QtWebEngineCore",
        "PyQt5.QtWebEngineWidgets",
        "PyQt5.QtWebChannel",
        "PyQt5.Qt3DCore",
        "PyQt5.Qt3DRender",
        "PyQt5.QtQml",
        "PyQt5.QtQuick",
        "PyQt5.QtQuickWidgets",
        "PyQt5.QtMultimedia",
        "PyQt5.QtBluetooth",
        "PyQt5.QtLocation",
        "PyQt5.QtPositioning",
        "PyQt5.QtDesigner",
        "PyQt5.QtSql",
        "PyQt5.QtTest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SleepSense",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SleepSense",
)
