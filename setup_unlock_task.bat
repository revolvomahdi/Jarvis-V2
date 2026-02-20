@echo off
:: Check for permissions
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting Admin Privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"

echo [NASA AI] Setting up Unlock Task...

:: Delete existing task if any
schtasks /Delete /TN "NASA_Unlock" /F >nul 2>&1

:: Create new task
:: Runs as SYSTEM (/RU "SYSTEM")
:: Run with highest privileges (/RL HIGHEST)
:: Command: executes the dynamic finding of session ID and unlocks it.
:: Note: The command inside cmd /c validation is tricky in schtasks. We point to a helper bat or complex command.
:: Simplifiction: We'll create a helper script 'unlock_action.bat' to avoid quoting hell in schtasks, 
:: OR use a very carefully escaped command. 
:: Let's use a helper script approach for stability. It's cleaner.

echo Creating unlock_action.bat helper...
(
echo @echo off
echo for /f "tokens=3" %%a in ^('qwinsta ^^^| findstr "console"'^) do tscon %%a /dest:console
) > "unlock_action.bat"

echo Registering Task...
schtasks /Create /TN "NASA_Unlock" /TR "'%CD%\unlock_action.bat'" /SC ONCE /ST 00:00 /RU "SYSTEM" /RL HIGHEST /F

echo.
echo [SUCCESS] Task 'NASA_Unlock' created.
echo You can now delete PsExec if you want.
echo.
pause
