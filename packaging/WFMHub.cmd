@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%_system\python\python.exe"
if not exist "%PY%" (
  echo Embedded Python runtime not found.
  exit /b 1
)
"%PY%" -m wfmhub2.cli serve
endlocal
