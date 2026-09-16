# PyInstaller specification for the Python engine sidecar.
# Run through scripts/build_portable.ps1 so the resulting executable is renamed
# with the Tauri target triple before bundling.

from PyInstaller.utils.hooks import collect_all

hiddenimports = []
datas = []
binaries = []

for package in ("duckdb", "polars", "ortools", "xgboost", "statsforecast", "mlforecast", "hierarchicalforecast"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

analysis = Analysis(
    ["src/wfmhub2/cli.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    console=False,
)
