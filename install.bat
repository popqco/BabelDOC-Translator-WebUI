@echo off
chcp 65001 >nul
title 安装 BabelDOC 翻译器环境
echo ============================================================
echo   正在为你自动配置 BabelDOC 翻译环境...
echo ============================================================

if not exist venv (
    echo [1/3] 正在创建 Python 独立虚拟环境 (venv)...
    python -m venv venv
)

echo [2/3] 正在激活虚拟环境并升级 pip...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [3/3] 正在安装依赖核心库 (BabelDOC 0.6.4 + Gradio + PDF 组件)...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

echo ============================================================
echo   恭喜！安装已顺利完成！
echo   请双击运行 run.bat 启动翻译服务。
echo ============================================================
pause
