@echo off
echo ==============================================================================
echo   JARVIS YEDEK PARCA VE MODEL KONTROL UNITESI
echo ==============================================================================
echo.
echo Komutan ve Uzman Ajanlarin gorev yerinde oldugundan emin olunuyor...
echo.

:: 1. KOMUTAN (Llama 3.1)
echo [1/5] KOMUTAN (Router) Kontrol Ediliyor...
ollama list | findstr "llama3.1:8b" >nul
if %errorlevel% neq 0 (
    echo [UYARI] Komutan (llama3.1:8b) kayip! Goreve cagiriliyor...
    ollama pull llama3.1:8b
) else (
    echo [OK] Komutan gorev basinda.
)

:: 2. SOHBET AJANI (Gemma 2)
echo.
echo [2/5] SOHBET UZMANI (Gemma 2) Kontrol Ediliyor...
ollama list | findstr "gemma2:9b" >nul
if %errorlevel% neq 0 (
    echo [UYARI] Sohbet Uzmani (gemma2:9b) kayip! Goreve cagiriliyor...
    ollama pull gemma2:9b
) else (
    echo [OK] Sohbet uzmani hazir.
)

:: 3. SISTEM MUHENDISI (Qwen Coder)
echo.
echo [3/5] SISTEM MUHENDISI (Qwen 2.5 Coder) Kontrol Ediliyor...
ollama list | findstr "qwen2.5-coder:7b" >nul
if %errorlevel% neq 0 (
    echo [UYARI] Sistem Muhendisi (qwen2.5-coder:7b) kayip! Goreve cagiriliyor...
    ollama pull qwen2.5-coder:7b
) else (
    echo [OK] Sistem muhendisi hazir.
)

:: 4. BAS YAZILIMCI (DeepSeek Coder)
echo.
echo [4/5] BAS YAZILIMCI (DeepSeek Coder 6.7b) Kontrol Ediliyor...
ollama list | findstr "deepseek-coder:6.7b" >nul
if %errorlevel% neq 0 (
    echo [UYARI] Bas Yazilimci (deepseek-coder:6.7b) kayip! Goreve cagiriliyor...
    ollama pull deepseek-coder:6.7b
) else (
    echo [OK] Bas yazilimci hazir.
)

echo.
echo [5/5] Matematik ve Hizli Islem Birimi (Qwen 2.5 Math)
ollama list | findstr "qwen2.5-math:1.5b" >nul
if %errorlevel% neq 0 (
    echo [UYARI] Matematik Birimi (qwen2.5-math:1.5b) kayip! Goreve cagiriliyor...
    ollama pull qwen2.5-math:1.5b
) else (
    echo [OK] Matematik birimi hazir.
)

echo.
echo ==============================================================================
echo   TUM BIRIMLER HAZIR VE GOREV BASINDA!
echo ==============================================================================
echo.
echo Lutfen acik olan "python app.py" penceresini kapatip yeniden acin.
pause
