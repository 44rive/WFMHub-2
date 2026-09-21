@echo off
setlocal EnableExtensions
title WFMHub 2 - Local Source Setup
for %%I in ("%~dp0.") do set "WFMHUB_HOME=%%~fI"
set "WFMHUB_PYTHON=%WFMHUB_HOME%\_system\runtime\python.exe"
set "PYTHONHOME="
set "PYTHONPATH="
if not exist "%WFMHUB_PYTHON%" (
  echo ERROR: Extract the complete portable ZIP first.
  pause
  exit /b 9009
)
"%WFMHUB_PYTHON%" -I -m wfmhub2_compat.setup --home "%WFMHUB_HOME%"
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%
