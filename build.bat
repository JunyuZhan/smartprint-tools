@echo off
rem ============================================
rem  SmartPrint 打包脚本（自动创建 .venv 虚拟环境）
rem  用法：双击 build.bat，或命令行执行 build.bat
rem  产物：dist\SmartPrint\SmartPrint.exe（绿色版）
rem ============================================
cd /d "%~dp0"

rem 自动选择 python 命令（优先 py 启动器）
where py >nul 2>nul
if %errorlevel%==0 ( set "PY=py -3" ) else ( set "PY=python" )

rem 首次运行自动创建项目内虚拟环境（避免污染系统 Python）
if not exist ".venv\Scripts\python.exe" (
    echo 创建虚拟环境 .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo 创建虚拟环境失败，请安装 Python 3.10+ 并勾选 PATH
        pause
        exit /b 1
    )
)
set "VPY=.venv\Scripts\python.exe"
echo 使用解释器：%VPY%

echo [1/3] 安装依赖（含 PyInstaller）...
%VPY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo 依赖安装失败，请检查网络或 pip 源
    pause
    exit /b 1
)

echo [2/3] 开始打包（首次约 2-5 分钟）...
%VPY% -m PyInstaller --noconfirm --clean smartprint.spec
if errorlevel 1 (
    echo 打包失败，请查看上方错误信息
    pause
    exit /b 1
)

echo [3/3] 打包完成！
echo 产物目录：%~dp0dist\SmartPrint\
echo 将该文件夹复制到办公室电脑，双击 SmartPrint.exe 即可运行。
echo 也可以运行 install.bat 一键安装到本机。
pause
