@echo off
for /f "tokens=3" %a in ('qwinsta ^| findstr "console"') do tscon %a /dest:console
