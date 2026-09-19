@echo off
chcp 65001 >nul
title BabelDOC 翻译器 - 环境初始化
echo ============================================================
echo   正在为 BabelDOC 桌面翻译器初始化 Python 运行环境...
echo ============================================================

rem BabelDOC 0.6.4 要求 Python >=3.10,<3.14。
rem 机器上的默认 python 可能是 3.14+（不兼容），因此优先通过 py 启动器
rem 显式挑选兼容版本，找不到再用 PATH 上的 python 兜底。
set "PY_CMD=python"

py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3.11" & goto :have_py

py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3.12" & goto :have_py

py -3.13 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3.13" & goto :have_py

py -3.10 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3.10" & goto :have_py

:check_path_python
%PY_CMD% -c "import sys; sys.exit(0 if sys.version_info[:2] < (3,14) else 1)" >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到兼容的 Python（需要 3.10 ~ 3.13，推荐 3.11）。
    echo        当前 PATH 上的 python 版本过新或不存在 Python。
    echo        请安装 Python 3.11 并勾选 "Add Python to PATH"。
    pause
    exit /b 1
)
goto :have_py

:have_py
echo 使用解释器: %PY_CMD%

rem 默认使用清华镜像加速；网络受限时可通过环境变量覆盖：
rem   set PIP_INDEX=https://pypi.org/simple
if "%PIP_INDEX%"=="" set "PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PIP_FALLBACK=https://pypi.org/simple"

rem 依赖版本以 requirements.lock 为准（完整锁定，可复现）；
rem lock 缺失时回退到 requirements.txt 的宽松版本约束
set "REQ_FILE=requirements.txt"
if exist requirements.lock set "REQ_FILE=requirements.lock"

if not exist venv (
    echo [1/3] 正在创建虚拟环境 venv ...
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo [错误] venv 创建失败。
        pause
        exit /b 1
    )
) else (
    echo [1/3] 检测到已有 venv，跳过创建。
)

echo [2/3] 正在升级 pip ...
venv\Scripts\python.exe -m pip install --upgrade pip -i %PIP_INDEX%

echo [3/3] 正在安装依赖（BabelDOC 0.6.4 / Gradio / pywebview ...）...
venv\Scripts\python.exe -m pip install -r %REQ_FILE% -i %PIP_INDEX%
if errorlevel 1 (
    echo [WARN] 镜像源安装失败，尝试官方 PyPI 源...
    venv\Scripts\python.exe -m pip install -r %REQ_FILE% -i %PIP_FALLBACK%
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
)

echo.
echo ============================================================
echo   安装完成！双击 start_silent.vbs 即可静默启动桌面窗口。
echo ============================================================
pause
