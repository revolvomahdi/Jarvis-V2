@echo off
chcp 65001 >nul 2>&1
title Otomatik Guncelleme Sistemi

echo.
echo ============================================
echo   Yapay Zeka Asistani v2 - Guncelleyici
echo ============================================
echo.

REM .venv aktif et
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Sanal ortam aktif edildi.
) else (
    echo [!] .venv bulunamadi, sistem Python kullaniliyor.
)

echo.
echo [*] Guncelleme baslatiliyor...
echo.

python updater.py

if errorlevel 1 (
    echo.
    echo [HATA] Guncelleme sirasinda bir sorun olustu!
    echo.
    pause
)
