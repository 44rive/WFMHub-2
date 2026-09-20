# Portable Windows Deployment

## Supported target experience

```text
download GitHub Release ZIP -> Extract All -> DOCTOR.cmd -> WFMHub.cmd
```

Normal use requires no administrator rights, installed Python, Node, Rust,
database server, installer, upload, or runtime internet. WFMHub reads configured
local source folders directly.

## Why the Phase 0.4 profile exists

The target workstation runs official embedded CPython 3.13.7, SQLite, and the
pure-Python Excel stack. It blocks third-party native Python libraries through
enterprise App Control. Consequently, the target profile does not import or
ship FastAPI/Pydantic Core, native DuckDB, Polars, PyArrow, NumPy, XGBoost,
OR-Tools, or the native forecast graph.

This is a policy-compatible architecture, not a security-control bypass.

## Release layout

```text
WFMHub-2/
├─ WFMHub.cmd
├─ DOCTOR.cmd
├─ README-FIRST.txt
├─ SHA256SUMS.txt
├─ Feed/
├─ Reports/
└─ _system/
   ├─ runtime/
   │  ├─ python.exe            official CPython 3.13.7
   │  └─ wheels/               four reviewed pure-Python Excel wheels
   ├─ app/wfmhub2_compat/      stdlib-only host
   ├─ web/                     React, Workers, WASM, Pyodide packages
   └─ manifests/               origin and exact SHA-256 inventories
```

`data/control.sqlite` and browser compatibility reports are created only after
extraction. Releases never contain operational extracts, databases, reports,
logs, local configuration, or employee/customer data.

## Launch and security contract

`WFMHub.cmd` clears machine Python variables and invokes the embedded runtime
with isolated paths. The host:

1. creates/checks SQLite;
2. binds the stable `127.0.0.1:8420` origin so the rebuildable OPFS cache can
   survive launches;
3. creates a fresh 256-bit session token;
4. serves the compiled UI and self-hosted browser runtimes;
5. opens the browser with the token in the URL fragment;
6. requires that token for protected local requests;
7. remains visible until Ctrl+C stops the application.

The server restricts Host headers to loopback and emits CSP, COOP, COEP,
same-origin resource, no-frame, no-referrer, and no-sniff headers.

## Two-stage doctor

### `DOCTOR.cmd` — host boundary

Runs before the UI and checks:

- isolated official runtime paths;
- SQLite WAL and integrity;
- OpenPyXL/XlsxWriter XLSX generation and readback;
- presence of the complete browser runtime.

### `WFMHub.cmd` — browser boundary

Select **Run all probes**. The browser reports independently:

- standard WebAssembly inside a Worker;
- DuckDB-Wasm SQL plus OPFS checkpoint/terminate/reopen;
- Pyodide with scikit-learn and statsmodels model fitting;
- HiGHS-Wasm mixed-integer optimization.

The complete result is atomically stored at:

```text
data/compatibility/last-browser-report.json
```

Return that file when reporting a managed-workstation result. It contains
capability/version/timing information, not workforce extracts.

## Build

After installing the locked Node dependencies:

```powershell
python scripts/stage_browser_runtime.py
pnpm build:web
python packaging/windows/build_hybrid_spike.py --web-dist web/dist
```

Or on Windows:

```powershell
./scripts/build_hybrid_spike.ps1
```

The Python builder is intentionally cross-platform. It downloads and
hash-verifies the official Windows embeddable runtime, downloads four
hash-locked pure-Python wheels, rejects host-native additions, builds a
deterministic ZIP, extracts it, and verifies every member/hash.

## Release gate

Ordinary CI and local Chromium can prove completeness and browser semantics.
Only the exact extracted ZIP on the managed corporate workstation can prove
the applicable App Control and Edge policies. A Phase 0.4 pass authorizes the
first RTA vertical slice; it does not prove production-scale model performance.

GitHub's automatically generated source ZIP is never a supported runnable
package.
