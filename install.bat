@echo off

if not exist venv (
    python -m venv venv
)

call venv\Scripts\activate.bat

pip install --upgrade pip
pip install -r requirements.txt

pause