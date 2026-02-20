@echo off
title JARVIS - AG VE INTERNET SORUN GIDERICISI
color 1f
cls
echo ==============================================================================
echo   JARVIS - AG BAGLANTISI ONARIM ARACI
echo ==============================================================================
echo.
echo Bu islem sunlari yapacak:
echo 1. Windows 'Proxy' ayarlarini sifirlayacak.
echo 2. Winsock ve IP ayarlarini temizleyecek.
echo 3. DNS onbellegini silecek.
echo 4. Windows Magaza uygulamalari (WhatsApp, Instagram) icin ag ayarlarini onaracak.
echo.
echo Lutfen yonetici olarak calistirdiginizdan emin olun.
echo Devam etmek icin bir tusa basin...
pause >nul

echo.
echo [1/5] Proxy Ayarlari Sifirlaniyor...
netsh winhttp reset proxy

echo.
echo [2/5] Winsock Katalogu Sifirlaniyor...
netsh winsock reset

echo.
echo [3/5] TCP/IP Yigini Sifirlaniyor...
netsh int ip reset

echo.
echo [4/5] DNS Temizleniyor...
ipconfig /release
ipconfig /flushdns
ipconfig /renew

echo.
echo [5/5] Loopback (Localhost) Sorunlari Gideriliyor...
CheckNetIsolation LoopbackExempt -a -n="Microsoft.MicrosoftEdge_8wekyb3d8bbwe"
CheckNetIsolation LoopbackExempt -a -n="Microsoft.Win32WebViewHost_cw5n1h2txyewy"

echo.
echo ==============================================================================
echo   ISLEM TAMAMLANDI!
echo ==============================================================================
echo.
echo Degisikliklerin etkili olmasi icin BILGISAYARI YENIDEN BASLATMANIZ onerilir.
echo.
pause
