@echo off
chcp 65001 >nul
title 存储维护组加班申报系统

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo 首次运行：正在创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo 请先安装 Python 3.9+ 并勾选 "Add Python to PATH"
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo 检查依赖...
pip install -r requirements.txt -q

if not exist "db.sqlite3" (
    echo 首次运行：正在初始化数据库...
    python manage.py migrate
    echo.
    echo 请创建管理员账号（用于登录 /admin/ 后台）：
    python manage.py createsuperuser
)

python manage.py migrate

echo.
echo 服务启动后，在浏览器打开: http://127.0.0.1:8000/
echo 按 Ctrl+C 可停止服务。
echo.
python manage.py runserver 0.0.0.0:8000

pause
