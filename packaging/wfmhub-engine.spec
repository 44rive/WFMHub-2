# PyInstaller specification for the Python engine sidecar.
# Run through scripts/build_portable.ps1 so the resulting executable is renamed
# with the Tauri target triple before bundling.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent.resolve()

analysis = Analysis(
    [str(ROOT / "src" / "wfmhub2" / "cli.py")],
    pathex=[str(ROOT / "src")],
    binaries=collect_dynamic_libs("xgboost"),
    datas=collect_data_files("xgboost", includes=["VERSION"]),
    hiddenimports=[],
    excludes=[
        "PIL",
        "matplotlib",
        "nvidia",
        "openpyxl",
        "pytest",
        "sklearn",
        "tkinter",
        "xlsxwriter",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="wfmhub-engine",
    # The desktop handshake consumes the machine-readable WFMHUB2_READY line
    # from stdout. Tauri owns the child process, so this does not expose an
    # interactive shell to the end user.
    console=True,
)
