@echo off
setlocal EnableExtensions
title WFMHub 2 Compatibility Doctor

for %%I in ("%~dp0.") do set "WFMHUB_HOME=%%~fI"
set "WFMHUB_PYTHON=%WFMHUB_HOME%\_system\runtime\python.exe"
set "WFMHUB_DUCKLAKE=%WFMHUB_HOME%\_system\duckdb_extensions\ducklake.duckdb_extension"
set "PYTHONHOME="
set "PYTHONPATH="

if not exist "%WFMHUB_PYTHON%" goto :missing_runtime
if not exist "%WFMHUB_DUCKLAKE%" goto :missing_extension

echo Running the complete offline WFMHub 2 compatibility test...
echo This checks the official Python runtime and every packaged native capability.
echo.
"%WFMHUB_PYTHON%" -I -m wfmhub2.portable_doctor --home "%WFMHUB_HOME%" --ducklake-extension "%WFMHUB_DUCKLAKE%" --full --require-offline
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo WFMHub 2 compatibility doctor PASSED.
) else (
  echo WFMHub 2 compatibility doctor FAILED with exit code %EXIT_CODE%.
  echo Copy the complete output above when reporting the failure.
)
pause
exit /b %EXIT_CODE%

:missing_runtime
echo.
echo ERROR: WFMHub's official embedded CPython runtime is missing:
echo   "%WFMHUB_PYTHON%"
echo.
echo Extract the complete GitHub Release ZIP before running DOCTOR.cmd.
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
