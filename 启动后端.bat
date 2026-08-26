@echo off
chcp 65001 >nul
cd /d "%~dp0backend"
echo 正在启动星途客服后端 http://127.0.0.1:8000
conda run -n langchain --no-capture-output python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
