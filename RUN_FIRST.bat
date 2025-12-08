@echo off
:set_colors
title Setting colors...
color 00
echo [0m
cls

:Prereqs_Python
title Prereqs - Python
python --version >nul 2>&1

if %errorlevel% equ 0 (
    echo [32m. Python is installed.[0m
    echo.
    pause
    cls
    goto Prereqs_Python_pip
) else (
    echo [31m. Python is NOT installed or not found in PATH.[0m
    echo Please download this and install it to PATH [94mhttps://www.python.org/ftp/python/3.14.0/python-3.14.0-amd64.exe[0m
    echo.
    pause
    cls
    goto close
)

:Prereqs_Python_pip
title Prereqs - Pip
pip --version >nul 2>&1

if %errorlevel% equ 0 (
    echo [32m. Pip is installed.[0m
    echo.
    pause
    cls
    pip install imageio pillow requests
    goto close
) else (
    echo [31m. Pip is NOT installed or not found in PATH.[0m
    echo If this happens for any reason, that Pip is not found, your install of Python is corrupted.
    echo Please redownload this and install it to PATH [94mhttps://www.python.org/ftp/python/3.14.0/python-3.14.0-amd64.exe[0m
    echo.
    pause
    cls
    goto close
)

:close
title Command Prompt
echo [0;0m
cls