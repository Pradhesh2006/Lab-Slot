@echo off
REM LabSlot: create .venv, install dependencies, initialise the DB and start the app.
cd /d "%~dp0"
if not exist requirements.txt (
  echo ERROR: requirements.txt not found in %CD%
  echo You are probably running this from inside the ZIP. Right-click the ZIP, choose "Extract All",
  echo then run setup_and_run.bat from the extracted project20_research_equipment_assistant folder.
  pause
  exit /b 1
)
if not exist .venv (
  py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r "%~dp0requirements.txt" || goto :error
if not exist .env copy .env.example .env >nul
python database.py || goto :error
python app.py
goto :eof
:error
echo Setup failed - see the messages above.
pause
