@echo off
rem Runs research jobs queued from the website admin (Research tab). Leave this window open.
cd /d "%~dp0"
.venv\Scripts\python -m gse_research worker
pause
