@echo off
setlocal
if not exist "%~dp0runtime\pythonw.exe" (
  echo RanNovel runtime is missing. Extract or download the complete folder first.
  pause
  exit /b 1
)
start "" /d "%~dp0" "%~dp0runtime\pythonw.exe" -I -B -X utf8 "%~dp0main.py"
endlocal
