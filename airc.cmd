@echo off
REM airc.cmd -- Windows shim that lets `airc <verb>` work from any shell
REM (PowerShell, cmd, Run dialog, Task Scheduler) by launching the
REM built-in Windows PowerShell on airc.ps1 with all forwarded arguments.
REM
REM Uses powershell.exe (PS 5.1, ships with Windows 10+) instead of pwsh
REM (PS 7+) -- airc.ps1 is a thin bash shim with no PS-7-only features,
REM so requiring pwsh forced an extra winget install for no benefit.
REM
REM install.ps1 places this next to airc.ps1 in
REM   %USERPROFILE%\AppData\Local\Programs\airc
REM and adds that directory to user PATH.
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0airc.ps1" %*
