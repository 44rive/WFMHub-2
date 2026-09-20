@echo off
setlocal EnableExtensions
title WFMHub 2 Hybrid Compatibility Spike

for %%I in ("%~dp0.") do set "WFMHUB_HOME=%%~fI"
set "WFMHUB_PYTHON=%WFMHUB_HOME%\_system\runtime\python.exe"
set "PYTHONHOME="
set "PYTHONPATH="

if not exist "%WFMHUB_PYTHON%" goto :missing_runtime

"%WFMHUB_PYTHON%" -I -m wfmhub2_compat --home "%WFMHUB_HOME%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%

:missing_runtime
echo.
echo ERROR: WFMHub's official embedded CPython runtime is missing:
echo   "%WFMHUB_PYTHON%"
echo.
echo Extract the complete Phase 0.4 Hybrid Spike ZIP before running WFMHub.cmd.
echo Do not use GitHub's Source code ZIP or copy this launcher by itself.
echo.
pause
exit /b 9009
