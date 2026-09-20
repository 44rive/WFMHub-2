@echo off
setlocal EnableExtensions
title WFMHub 2 Portable

for %%I in ("%~dp0.") do set "WFMHUB_HOME=%%~fI"
set "WFMHUB_PYTHON=%WFMHUB_HOME%\_system\runtime\python.exe"
set "WFMHUB_DUCKLAKE=%WFMHUB_HOME%\_system\duckdb_extensions\ducklake.duckdb_extension"
set "PYTHONHOME="
set "PYTHONPATH="

if not exist "%WFMHUB_PYTHON%" goto :missing_runtime
if not exist "%WFMHUB_DUCKLAKE%" goto :missing_extension

"%WFMHUB_PYTHON%" -I -m wfmhub2 --home "%WFMHUB_HOME%" --ducklake-extension "%WFMHUB_DUCKLAKE%" portable
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%

:missing_runtime
echo.
echo ERROR: WFMHub's official embedded CPython runtime is missing:
echo   "%WFMHUB_PYTHON%"
echo.
echo Extract the complete GitHub Release ZIP before running WFMHub.cmd.
echo Do not use GitHub's Source code ZIP or copy this launcher by itself.
echo.
pause
exit /b 9009

:missing_extension
echo.
echo ERROR: WFMHub's pinned offline DuckLake extension is missing:
echo   "%WFMHUB_DUCKLAKE%"
echo.
echo Extract the complete GitHub Release ZIP again.
echo.
pause
exit /b 2
