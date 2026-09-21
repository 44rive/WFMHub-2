@echo off
setlocal EnableExtensions
title WFMHub 2 Hybrid Host Doctor

for %%I in ("%~dp0.") do set "WFMHUB_HOME=%%~fI"
set "WFMHUB_PYTHON=%WFMHUB_HOME%\_system\runtime\python.exe"
set "PYTHONHOME="
set "PYTHONPATH="

if not exist "%WFMHUB_PYTHON%" goto :missing_runtime

echo Running the WFMHub 2 policy-compatible host doctor...
echo.
"%WFMHUB_PYTHON%" -I -m wfmhub2_compat.doctor --home "%WFMHUB_HOME%"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo Host doctor passed. Run WFMHub.cmd and then Run all probes in Edge.
) else (
  echo Host doctor failed with exit code %EXIT_CODE%.
)
echo.
pause
exit /b %EXIT_CODE%

:missing_runtime
echo ERROR: The official embedded Python runtime is missing.
echo Extract the complete WFMHub 2 Source Preview ZIP first.
pause
exit /b 9009
