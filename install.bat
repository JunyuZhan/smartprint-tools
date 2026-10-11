@echo off
rem ============================================
rem  SmartPrint 一键安装脚本（须先执行 build.bat 打包）
rem  安装到 %LOCALAPPDATA%\SmartPrint，并创建桌面快捷方式
rem ============================================
setlocal
set "TARGET=%LOCALAPPDATA%\SmartPrint"

if not exist "%~dp0dist\SmartPrint\SmartPrint.exe" (
    echo 未找到 dist\SmartPrint\SmartPrint.exe，请先运行 build.bat 打包
    pause
    exit /b 1
)

echo [1/2] 复制程序到 %TARGET% ...
if exist "%TARGET%" rmdir /s /q "%TARGET%"
xcopy /e /i /q "%~dp0dist\SmartPrint" "%TARGET%" >nul

echo [2/2] 创建桌面快捷方式...
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\SmartPrint 扫码打印.lnk'); $s.TargetPath='%TARGET%\SmartPrint.exe'; $s.WorkingDirectory='%TARGET%'; $s.Save()" >nul

echo 安装完成！
echo   桌面快捷方式：SmartPrint 扫码打印
echo   程序位置：%TARGET%
echo 首次运行后，可在管理页「设置」中开启开机自启，并打印二维码海报贴墙。
pause
