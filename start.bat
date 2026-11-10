@echo off
REM Mizan - Windows icin tek tikla kurulum ve calistirma
cd /d "%~dp0"
where python >nul 2>nul || (echo Python bulunamadi. https://www.python.org/downloads/ adresinden kurun ve "Add to PATH" kutusunu isaretleyin. & pause & exit /b 1)
if not exist .venv (
  echo [1/2] Sanal ortam olusturuluyor...
  python -m venv .venv || (pause & exit /b 1)
  .venv\Scripts\python -m pip install --upgrade pip -q
  echo [2/2] Paketler yukleniyor, bu bir kac dakika surebilir...
  .venv\Scripts\python -m pip install -e ".[dev]" -q || (pause & exit /b 1)
)
if not exist .env copy .env.example .env >nul
echo.
echo  Mizan calisiyor:  http://localhost:8000
echo  Durdurmak icin:   Ctrl+C
echo.
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn mizan.api:app --env-file .env
pause
