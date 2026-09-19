@echo off
chcp 65001 >nul
title BabelDOC 翻译器 - 环境初始化
echo ============================================================
echo   正在为 BabelDOC 桌面翻译器初始化 Python 运行环境...
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python。请先安装 Python 3.11 并勾选 "Add Python to PATH"。
    pause
    exit /b 1
)

if not exist venv (
    echo [1/3] 正在创建虚拟环境 venv ...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] venv 创建失败。
        pause
        exit /b 1
    )
) else (
    echo [1/3] 检测到已有 venv，跳过创建。
)

echo [2/3] 正在升级 pip ...
venv\Scripts\python.exe -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [3/3] 正在安装依赖（BabelDOC 0.6.4 / Gradio / pywebview ...）...
venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   安装完成！双击 start_silent.vbs 即可静默启动桌面窗口。
echo ============================================================
pause
