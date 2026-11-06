@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    python -m venv .venv
    if errorlevel 1 goto error
  )
)
.venv\Scripts\python.exe -c "import PySide6, cv2, scipy, numpy, PIL, matplotlib" >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto error
)
start "" .venv\Scripts\pythonw.exe app.py
exit /b 0
:error
pause
exit /b 1
