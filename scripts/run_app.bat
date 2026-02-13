@echo off
setlocal

if not exist .venv\Scripts\python.exe (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Create it first: py -m venv .venv
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m streamlit run app.py
