# PyInstaller specification for the Python engine sidecar.
# Run through scripts/build_portable.ps1 so the resulting executable is renamed
# with the Tauri target triple before bundling.

from PyInstaller.utils.hooks import collect_all

hiddenimports = []
datas = []
binaries = []

for package in (
    "duckdb",
    "polars",
    "ortools",
    "xgboost",
    "statsforecast",
    "mlforecast",
    "hierarchicalforecast",
    "openpyxl",
    "xlsxwriter",
):
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
    # The desktop handshake consumes the machine-readable WFMHUB2_READY line
    # from stdout. Tauri owns the child process, so this does not expose an
    # interactive shell to the end user.
    console=True,
)
