@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   windows禁止更新工具  -  一键打包
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo 错误：没有找到 python，请先安装 Python 3.9 以上版本。
    pause
    exit /b 1
)

echo [1/4] 安装依赖 ...
python -m pip install --disable-pip-version-check --quiet PySide6 pyinstaller pillow
if errorlevel 1 (
    echo 错误：依赖安装失败，请检查网络。
    pause
    exit /b 1
)

echo [2/4] 修正脚本编码 ...
python ensure_bom.py

echo [3/4] 生成图标 ...
python make_icon.py

echo [4/4] 打包 ...
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
    --name NoAutoRestartTool --icon app.ico --version-file version.txt ^
    --add-data "scripts;scripts" --add-data "icon_preview.png;." --add-data "app.ico;." ^
    main.py
if errorlevel 1 (
    echo 错误：打包失败。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   完成：dist\NoAutoRestartTool.exe
echo   发布时改名为 windows禁止更新工具.exe 即可
echo ============================================================
pause
