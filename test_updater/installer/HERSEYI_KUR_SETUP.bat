@echo off
title JARVIS AI - OTOMATIK KURULUM SIHIRBAZI (v2.0)
color 0a
cls

echo ==============================================================================
echo   JARVIS AI - TAM OTOMATIK KURULUM SIHIRBAZI
echo   (Arkadas Dostu Versiyon)
echo ==============================================================================
echo.
echo Bu program sirasiyla sunlari yapacak:
echo 1. Python kontrolu
echo 2. Gerekli tüm kütüphanelerin (Lib) yuklenmesi
echo 3. Ekran Kartina ozel (NVIDIA) hizlandiricilarin kurulmasi
echo 4. OLLAMA Model Platformunun kontrolu
echo.
echo Lutfen kurulum bitene kadar kapatmayin.
echo.
pause

echo.
echo [1/4] Python Kontrol Ediliyor...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi! Lutfen once Python 3.10 veya uzerini kurun.
    echo (Kurarken 'Add Python to PATH' secenegini isaretlemeyi unutmayin!)
    start https://www.python.org/downloads/
    pause
    exit
)
echo [OK] Python Tespit Edildi.

echo.
echo [2/4] Temel Kutuphaneler Yukleniyor...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [UYARI] Bazi paketler yuklenemedi. Tekrar deneniyor...
    pip install -r requirements.txt
)

echo.
echo [3/4] Ekran Karti (GPU) Secimi
echo.
echo Arkadasinizin/Kullanicinin Ekran Karti Hangisi?
echo 1) NVIDIA RTX 3000 / 4000 Serisi (Yaygin)
echo 2) NVIDIA RTX 5000 Serisi (Yeni Nesil - Blackwell)
echo 3) Sadece Islemci (GPU Yok / AMD)
echo.
set /p gpu_choice="Seciniz (1, 2 veya 3): "

if "%gpu_choice%"=="1" (
    echo.
    echo [NVIDIA] Standart CUDA 12.4 Yukleniyor...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
)
if "%gpu_choice%"=="2" (
    echo.
    echo [NVIDIA] RTX 5000 Ozel Surum (Nightly) Yukleniyor...
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
    if %errorlevel% neq 0 (
        echo [HATA] CUDA 12.8 bulunamadi, 12.6 deneniyor...
        pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu126
    )
)
if "%gpu_choice%"=="3" (
    echo.
    echo [CPU] Standart Surum Yukleniyor...
    pip install torch torchvision torchaudio
)

echo.
echo [4/4] OLLAMA Kontrolu...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo [UYARI] OLLAMA Bulunamadi!
    echo Yapay zeka modellerini calistirmak icin OLLAMA gereklidir.
    echo Tarayicinizda indirme sayfasi aciliyor...
    start https://ollama.com/download
    echo Lutfen OLLAMA'yi kurup bu pencereye donun.
    pause
) else (
    echo [OK] OLLAMA Zaten Kurulu.
)

echo.
echo ==============================================================================
echo   KURULUM TAMAMLANDI!
echo ==============================================================================
echo.
echo Uygulamayi baslatmak icin masaustundeki 'JARVIS_BASLAT.bat' dosyasini kullanabilirsiniz.
echo.
echo Simdi baslatilsin mi? (E/H)
set /p start_now="Secim: "
if /i "%start_now%"=="E" (
    python app.py
)
pause
